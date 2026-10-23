"""Random procs: rand, prob, pick (plain, weighted, list), roll (text and 2-arg forms), rand_seed,
generator() / generator.Rand().

Every case that draws calls rand_seed(N) first. Two kinds of case:
- seeded values/sequences: compared exactly (BYOND's PRNG vs OD's System.Random will differ; that
  is the parity point the suite records);
- properties over many seeded draws (bounds hit, integer-ness, which values ever appear, how many
  generator draws a call consumes, same seed -> same sequence). These do not depend on which PRNG
  is used, so they isolate argument handling from generator choice.

OD notes the cases aim at: rand(H) with H < 0 calls Random.Next(negative) (throws); rand/roll
truncate fractional args to int; rand bounds above 2^31 overflow; roll("NdS-M") and roll("dS") are
rejected by OD's parser; prob() clamps; weighted pick defaults non-numeric weights to 100;
generator.Rand() uses IoC IRobustRandom, not the rand_seed()ed DreamManager.Random; OD has no
"color" generator; OD's LINEAR_RAND is sqrt(u)*(hi-lo)+lo, not proportional to |value|."""
from pools import TEXT_S, NUM, NUM_S, OTHER
from gen import dm_str

HELPERS = r"""
/proc/random_range(list/L)
	var/mn
	var/mx
	var/allint = TRUE
	for(var/v in L)
		if(!isnum(v))
			return list("nonnum", v)
		if(isnull(mn) || v < mn)
			mn = v
		if(isnull(mx) || v > mx)
			mx = v
		if(v != round(v))
			allint = FALSE
	return list("min" = mn, "max" = mx, "int" = allint, "n" = length(L))

/proc/random_within(list/L, lo, hi)
	var/inside = TRUE
	var/allint = TRUE
	for(var/v in L)
		if(!isnum(v))
			return list("nonnum", v)
		if(!(v >= lo && v <= hi))
			inside = FALSE
		if(v != round(v))
			allint = FALSE
	return list("in" = inside, "int" = allint, "n" = length(L))

/proc/random_before(a, b)
	if(isnum(a) && isnum(b))
		return a < b
	if(isnum(a))
		return TRUE
	if(isnum(b))
		return FALSE
	if(isnull(a))
		return !isnull(b)
	if(isnull(b))
		return FALSE
	return sorttext(a, b) > 0

// Distinct values seen, sorted (numbers, then null, then text)
/proc/random_set(list/L)
	var/list/out = list()
	for(var/v in L)
		if(out.Find(v))
			continue
		var/at = out.len + 1
		for(var/i in 1 to out.len)
			if(random_before(v, out[i]))
				at = i
				break
		out.Insert(at, v)
	return out

/proc/random_count(list/L, v)
	var/n = 0
	for(var/x in L)
		if(x == v)
			n++
	return n

/proc/random_mean(list/L)
	var/t = 0
	for(var/v in L)
		t += v
	return t / max(1, length(L))

// Which of k = 0..4 prior rand(1, 1000000) draws from seed gives the value a: tells how many
// generator steps the calls under test consumed (in rand(1, 1000000) units)
/proc/random_draws_used(seed, a)
	var/list/out = list()
	for(var/k in 0 to 4)
		rand_seed(seed)
		for(var/i in 1 to k)
			var/skip = rand(1, 1000000)
			skip = skip
		out += (rand(1, 1000000) == a)
	return out

/proc/random_seq(seed, n = 10)
	rand_seed(seed)
	var/list/L = list()
	for(var/i in 1 to n)
		L += rand(1, 1000000)
	return L

/proc/random_same(list/A, list/B)
	if(length(A) != length(B))
		return FALSE
	for(var/i in 1 to length(A))
		if(A[i] != B[i])
			return FALSE
	return TRUE

/proc/random_pick_args(...)
	return pick(args)

/proc/random_pick_arglist(list/L)
	return pick(arglist(L))

/proc/random_vlen(vector/V)
	return sqrt(V.x * V.x + V.y * V.y + V.z * V.z)

// Properties of n draws from a vector generator
/proc/random_vstats(generator/G, n = 300)
	var/allvec = TRUE
	var/zzero = TRUE
	var/minlen
	var/maxlen
	var/mnx
	var/mxx
	var/mny
	var/mxy
	var/mnz
	var/mxz
	var/diag = TRUE
	for(var/i in 1 to n)
		var/vector/V = G.Rand()
		if(!istype(V, /vector))
			return list("notvec", V)
		var/l = random_vlen(V)
		if(V.z != 0)
			zzero = FALSE
		if(abs(V.x - V.y) > 0.001)
			diag = FALSE
		if(isnull(minlen) || l < minlen)
			minlen = l
		if(isnull(maxlen) || l > maxlen)
			maxlen = l
		if(isnull(mnx) || V.x < mnx)
			mnx = V.x
		if(isnull(mxx) || V.x > mxx)
			mxx = V.x
		if(isnull(mny) || V.y < mny)
			mny = V.y
		if(isnull(mxy) || V.y > mxy)
			mxy = V.y
		if(isnull(mnz) || V.z < mnz)
			mnz = V.z
		if(isnull(mxz) || V.z > mxz)
			mxz = V.z
	return list("vec" = allvec, "z0" = zzero, "diag" = diag, "len" = list(round(minlen, 0.5), round(maxlen, 0.5)), "x" = list(round(mnx), round(mxx, 1)), "y" = list(round(mny), round(mxy, 1)), "z" = list(round(mnz), round(mxz, 1)))
"""


def seeded(seed, expr, n=12):
    """Lines that seed and collect n results of expr into L (L.len++ keeps lists and nulls whole)."""
    return [f"rand_seed({seed})", "var/list/L = list()", f"for(var/i in 1 to {n})", "\tL.len++",
            f"\tL[L.len] = {expr}"]


def build(s):
    s.dm(HELPERS)
    build_rand(s)
    build_prob(s)
    build_pick(s)
    build_roll(s)
    build_seed(s)
    build_generator(s)


# ---------------------------------------------------------------- rand
RAND_1 = NUM + [o for o in OTHER if o not in NUM] + TEXT_S + ['"5"', "-1e7", "2147483647", "2147483648",
                                                              "-2147483648", "4294967296", "1e10"]
RAND_2 = NUM_S + ["-0.5", "1.5", "2.9", "1e7", "NAN", "NINF"] + OTHER + ['"3"']
# Narrow values: 2000 draws hit both ends of every range these make
RAND_S = ["0", "1", "-1", "2", "5", "-3", "0.5", "1.5", "-0.5", "2.9", "-2.5", "null", '"3"', "list()",
          "new /datum", "/datum"]


def build_rand(s):
    # One seeded draw for every 1- and 2-argument shape
    for a in RAND_1:
        s.body("rand", ["rand_seed(1)"], f"rand({a})")
    for a in RAND_2:
        for b in RAND_2:
            s.body("rand", ["rand_seed(2)"], f"rand({a}, {b})")
    # Range and integer-ness over 2000 draws (PRNG-independent)
    for a in RAND_S:
        s.body("rand", seeded(3, f"rand({a})", 2000), "random_range(L)")
        for b in RAND_S:
            s.body("rand", seeded(4, f"rand({a}, {b})", 2000), "random_range(L)")
    # Which values appear at all
    for a, b in [("1", "6"), ("6", "1"), ("0", "1"), ("-2", "2"), ("0.5", "3.5"), ("0.4", "2.6"),
                 ("-1.5", "1.5"), ("1.9", "4.1"), ("0.1", "0.9"), ("2", "2"), ("-0.9", "-0.1")]:
        s.body("rand", seeded(5, f"rand({a}, {b})", 2000), "random_set(L)")
    for h in ["5", "-5", "0.5", "2.5", "-2.5", "0", "1"]:
        s.body("rand", seeded(5, f"rand({h})", 2000), "random_set(L)")
    # Seeded sequences
    for seed in ["1", "7", "42", "1000"]:
        for e in ["rand(1, 6)", "rand(1, 100)", "rand(0, 1000000)", "rand()", "rand(10)", "rand(-50, 50)",
                  "rand(100, 1)", "rand(1, 2)"]:
            s.body("rand", seeded(seed, e, 15), "L")
    # rand(): fraction in [0, 1), resolution and spread
    s.body("rand", seeded(6, "rand()", 2000), "random_within(L, 0, 0.99999999)")
    s.body("rand", seeded(6, "rand()", 2000), "length(random_set(L)) > 1900")
    s.body("rand", seeded(6, "rand()", 2000), "list(random_mean(L) > 0.45, random_mean(L) < 0.55)")
    s.body("rand", seeded(6, "rand()", 2000), "random_count(L, 0)")
    for k in [8, 12, 15, 16, 23, 24, 31, 32]:
        s.body("rand", seeded(6, "rand()", 500) + ["var/ok = TRUE", "for(var/v in L)",
                                                   f"\tif(v * {2 ** k} != round(v * {2 ** k}))", "\t\tok = FALSE"],
               "ok")
    s.body("rand", ["rand_seed(6)"], "isnum(rand())")
    # Large ranges: in bounds, integers, values far from the ends
    for a, b in [("0", "1e7"), ("-1e7", "1e7"), ("0", "16777216"), ("0", "1e10"), ("-1e10", "1e10"),
                 ("1e9", "1e9 + 100"), ("2147483600", "2147483647"), ("2147483647", "2147483647"),
                 ("-2147483648", "-2147483648"), ("4294967296", "4294967296"), ("0", "2147483647"),
                 ("-2147483648", "2147483647"), ("0", "4294967295")]:
        s.body("rand", seeded(7, f"rand({a}, {b})", 500), f"random_within(L, {a}, {b})")
        s.body("rand", seeded(7, f"rand({b}, {a})", 500), f"random_within(L, {a}, {b})")
    s.body("rand", seeded(7, "rand(0, 1e7)", 500), "list(random_mean(L) > 3e6, random_mean(L) < 7e6)")
    s.body("rand", seeded(7, "rand(1e7)", 500), "random_within(L, 0, 1e7)")
    s.body("rand", seeded(7, "rand(2147483647)", 200), "random_within(L, 0, 2147483647)")
    s.body("rand", seeded(7, "rand(1e10)", 200), "random_within(L, 0, 1e10)")
    # Uniformity of a die
    s.body("rand", seeded(8, "rand(1, 6)", 3000),
           "list(random_count(L, 1) > 400, random_count(L, 6) > 400, random_count(L, 3) < 600)")
    s.body("rand", seeded(8, "rand(1, 2)", 2000), "list(random_count(L, 1) > 900, random_count(L, 2) > 900)")
    # Named and odd argument forms
    for e in ["rand(L = 1, H = 1)", "rand(L = 3, H = 3)", "rand(H = 0)", "rand(L = 2, 2)", "rand(1, 1, 1)",
              "rand(4, 4)", "rand(-4, -4)", "rand(0, 0)", "rand(0)", "rand(1.5, 1.5)", "rand(NAN)",
              "rand(PINF, PINF)", "rand(NINF)", "isnum(rand(1, 6))", "rand(\"a\", \"b\")"]:
        s.body("rand", ["rand_seed(9)"], e)
    s.body("rand", seeded(9, "rand(L = 1, H = 3)", 1000), "random_set(L)")
    s.body("rand", seeded(9, "rand(H = 3)", 1000), "random_set(L)")
    s.body("rand", seeded(9, "rand(L = 3)", 1000), "random_set(L)")
    s.body("rand", seeded(9, "rand(H = 3, L = 1)", 1000), "random_set(L)")
    # Arguments from variables, and the variables are untouched
    s.body("rand", ["rand_seed(9)", "var/lo = 2.7", "var/hi = 5.2", "var/r = rand(lo, hi)"], "list(lo, hi, isnum(r))")
    s.body("rand", seeded(9, "rand(rand(1, 3), 3)", 1000), "random_set(L)")


# ---------------------------------------------------------------- prob
PROB_P = NUM + [o for o in OTHER if o not in NUM] + TEXT_S + ['"50"', '"100"', "99.9", "0.1", "1e-7", "-1e7", "200",
                                                              "1e30", "100.0001", "-0.0001"]


def build_prob(s):
    for p in PROB_P:
        s.body("prob", ["rand_seed(1)"], f"prob({p})")
        # all 0 / all 1 / mixed over 2000 draws
        s.body("prob", seeded(2, f"prob({p})", 2000),
               'random_set(L)')
    for seed in ["1", "3", "99"]:
        for p in ["50", "10", "90", "1", "99", "33.3"]:
            s.body("prob", seeded(seed, f"prob({p})", 20), "L")
    # Frequencies
    for p, lo, hi in [("50", 900, 1100), ("25", 400, 600), ("75", 1400, 1600), ("10", 120, 280), ("90", 1720, 1880),
                      ("1", 2, 50), ("99", 1950, 1998), ("0.5", 0, 30), ("12.5", 180, 320)]:
        s.body("prob", seeded(3, f"prob({p})", 2000), f"list(random_count(L, 1) >= {lo}, random_count(L, 1) <= {hi})")
    s.body("prob", ["rand_seed(3)", "var/p = prob(50)"], "list(isnum(p), p == 0 || p == 1)")
    s.body("prob", ["rand_seed(3)", "var/x = 50", "var/r = prob(x)"], "list(x, isnum(r))")
    s.body("prob", ["rand_seed(3)"], "prob(100) + prob(100)")
    s.body("prob", ["rand_seed(3)"], "prob(0) || prob(0)")
    s.body("prob", ["rand_seed(3)"], "!prob(100)")
    s.body("prob", ["rand_seed(3)"], "prob(prob(100) * 100)")
    s.body("prob", ["rand_seed(3)"], "prob(P = 100)")
    s.body("prob", ["rand_seed(3)"], "prob()")
    s.body("prob", ["rand_seed(3)"], "prob(50, 50)")
    s.body("prob", ["rand_seed(3)"], "prob(100, 0)")
    s.body("prob", ["rand_seed(3)"], 'prob(vector(1, 2))')
    s.body("prob", ["rand_seed(3)"], 'prob(matrix())')
    s.body("prob", ["rand_seed(3)", "var/r = 0", "if(prob(100))", "\tr = 1"], "r")
    s.body("prob", ["rand_seed(3)", "var/r = 0", "if(prob(0))", "\tr = 1"], "r")


# ---------------------------------------------------------------- pick
PICK_LISTS = ["list()", "list(1)", "list(null)", "new /list(3)", "list(1, 2, 3, 4, 5)", 'list("a" = 1, "b" = 2)',
              'list("a", "b", "c")', "list(list(1, 2), list(3))", "list(null, 1)", 'alist("x" = 1, "y" = 2)',
              'list(1, 1, 1, 2)', 'list("k" = null)', "list(5, null, null)", "list(1, 2, 3) - 2", "list(1, 2) + list(3)"]


def build_pick(s):
    # Single argument: list form or a lone value
    for a in PICK_LISTS + TEXT_S + NUM_S + OTHER + ["NAN", "NINF", '"list"', "new /obj"]:
        s.body("pick", ["rand_seed(1)"], f"pick({a})")
    for a in PICK_LISTS:
        s.body("pick", seeded(2, f"pick({a})", 600), "random_set(L)")
    s.body("pick", seeded(2, "pick(list(list(1, 2), list(3)))", 600),
           "list(random_count(L, null), length(L[1]) >= 1, islist(L[1]))")
    # Several arguments
    for e in ["1, 2", "1, 2, 3", '"a", "b", "c", "d"', "null, null", "null, 1", "list(1, 2), list(3, 4)", "list(), 5",
              "1, list(2, 3)", '"x", "x"', "NAN, NAN", "/datum, /obj", "1, 2, 3, 4, 5, 6, 7, 8, 9, 10"]:
        s.body("pick", ["rand_seed(3)"], f"pick({e})")
        s.body("pick", seeded(3, f"pick({e})", 600), "random_set(L)")
    s.body("pick", seeded(3, "pick(list(1, 2), list(3, 4))", 300),
           "list(islist(L[1]), length(L[1]), random_count(L, 1) + random_count(L, 3))")
    # Seeded sequences
    for seed in ["1", "7", "42"]:
        for e in ["pick(1, 2, 3)", "pick(list(1, 2, 3))", 'pick("a", "b")', "pick(list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10))",
                  "pick(1, 2, 3, 4, 5, 6)"]:
            s.body("pick", seeded(seed, e, 15), "L")
    # Uniformity
    s.body("pick", seeded(4, "pick(1, 2, 3)", 3000),
           "list(random_count(L, 1) > 850, random_count(L, 2) > 850, random_count(L, 3) > 850)")
    s.body("pick", seeded(4, "pick(list(1, 2, 3))", 3000),
           "list(random_count(L, 1) > 850, random_count(L, 2) > 850, random_count(L, 3) > 850)")
    # The list is not changed
    s.body("pick", ["rand_seed(5)", "var/list/P = list(1, 2, 3)", "var/x = pick(P)"], "list(P, x in P)")
    s.body("pick", ["rand_seed(5)", 'var/list/P = list("a" = 1, "b" = 2)', "var/x = pick(P)"], "list(P, P[x])")
    s.body("pick", ["rand_seed(5)", "var/list/P = new /list(4)", "var/x = pick(P)"], "list(P, x)")
    # Special lists
    s.body("pick", ["rand_seed(5)", "var/obj/O = parity_track(new /obj(locate(1, 1, 1)))",
                    "var/obj/I = parity_track(new /obj(O))", 'I.name = "inner"'], "pick(O.contents)")
    s.body("pick", ["rand_seed(5)", "var/obj/O = parity_track(new /obj(locate(1, 1, 1)))"], "pick(O.contents)")
    s.body("pick", ["rand_seed(5)", "var/datum/D = new"], "istext(pick(D.vars))")
    s.body("pick", ["rand_seed(5)", "var/datum/D = new", "var/v = pick(D.vars)"], "D.vars.Find(v) > 0")
    s.body("pick", ["rand_seed(5)", "var/obj/O = parity_track(new /obj(locate(1, 1, 1)))", 'O.overlays += "x"'],
           "isnull(pick(O.overlays))")
    s.body("pick", ["rand_seed(5)"], 'pick(splittext("a,b,c", ",")) in list("a", "b", "c")')
    s.body("pick", ["rand_seed(5)"], "random_pick_args(7)")
    s.body("pick", ["rand_seed(5)"], "random_pick_args()")
    s.body("pick", seeded(5, "random_pick_args(1, 2, 3)", 600), "random_set(L)")
    s.body("pick", ["rand_seed(5)"], "random_pick_arglist(list(9))")
    s.body("pick", seeded(5, "random_pick_arglist(list(1, 2, 3))", 600), "random_set(L)")
    s.body("pick", ["rand_seed(5)"], "random_pick_arglist(list(list(1, 2)))")
    s.body("pick", ["rand_seed(5)"], "random_pick_arglist(list())")
    s.body("pick", ["rand_seed(5)"], "pick()")
    s.body("pick", ["rand_seed(5)"], "pick(1, )")
    s.body("pick", ["rand_seed(5)"], "pick(List = list(4))")

    # ---- weighted ----
    W = [('50; "a", "b"', None), ('prob(50); "a", "b"', None), ('0; "a", 100; "b"', None), ('100; "a", 0; "b"', None),
         ('0; "a", 0; "b"', None), ('-10; "a", "b"', None), ('-10; "a", -10; "b"', None), ('"50"; "a", "b"', None),
         ('null; "a", "b"', None), ('null; "a", null; "b"', None), ('200; "a", "b"', None), ('1e-7; "a", 100; "b"', None),
         ('NAN; "a", "b"', None), ('PINF; "a", "b"', None), ('PINF; "a", PINF; "b"', None), ('NINF; "a", "b"', None),
         ('list(); "a", "b"', None), ('new /datum; "a", "b"', None), ('300; "a", "b", "c"', None), ('1; "a", 1; "b"', None),
         ('0.5; "a", 0.5; "b"', None), ('100; list(1, 2), 100; list(3)', None), ('100; null, 100; null', None),
         ('50; "a"', None), ('0; "a"', None), ('"b", 0; "a"', None), ('1e30; "a", 1; "b"', None),
         ('100; 1, 100; 2, 100; 3, 100; 4', None), ('25; "a", 25; "b", 50; "c"', None), ('prob(0); "a", "b"', None)]
    for e, _ in W:
        s.body("pick", ["rand_seed(6)"], f"pick({e})")
        s.body("pick", seeded(6, f"pick({e})", 600), "random_set(L)")
    for seed in ["1", "7"]:
        for e in ['pick(50; "a", "b")', 'pick(25; "a", 25; "b", 50; "c")', 'pick(1; 1, 1; 2, 1; 3)',
                  'pick(prob(10); "x", prob(90); "y")']:
            s.body("pick", seeded(seed, e, 15), "L")
    # Weights BYOND rejects as constants, given at run time through variables
    for a, b in [("0", "0"), ("-10", "-10"), ("-10", "100"), ("100", "-10"), ("null", "null"), ("NAN", "NAN"),
                 ("0", "null"), ("PINF", "NINF"), ("NINF", "NINF"), ("-1e-7", "0"), ('"x"', '"y"'), ("list()", "0"),
                 ("0", "1e-7"), ("-50", "50")]:
        lines = ["rand_seed(6)", f"var/wa = {a}", f"var/wb = {b}"]
        s.body("pick", lines, 'pick(wa; "a", wb; "b")')
        s.body("pick", lines + ["var/list/L = list()", "for(var/i in 1 to 600)", "	L.len++",
                                '	L[L.len] = pick(wa; "a", wb; "b")'], "random_set(L)")
    s.body("pick", ["rand_seed(6)", "var/w = -50", "var/list/L = list()", "for(var/i in 1 to 3000)", "	L.len++",
                    '	L[L.len] = pick(w; "a", 100; "b", 100; "c")'],
           'list(random_count(L, "a"), random_count(L, "b") > 1300)')
    s.body("pick", ["rand_seed(6)", "var/w = 0", "var/list/L = list()", "for(var/i in 1 to 600)", "	L.len++",
                    '	L[L.len] = pick(w; "a", w; "b", w; "c")'], "random_set(L)")
    # Weighted frequencies
    s.body("pick", seeded(7, 'pick(200; "a", "b")', 3000),
           'list(random_count(L, "a") > 1800, random_count(L, "a") < 2200)')
    s.body("pick", seeded(7, 'pick(25; "a", 75; "b")', 3000),
           'list(random_count(L, "a") > 600, random_count(L, "a") < 900)')
    s.body("pick", seeded(7, 'pick(300; "a", "b", "c")', 3000),
           'list(random_count(L, "a") > 1650, random_count(L, "a") < 1950, random_count(L, "b") > 450)')
    s.body("pick", seeded(7, 'pick(-50; "a", 100; "b", 100; "c")', 3000),
           'list(random_count(L, "a"), random_count(L, "b") > 1300)')
    s.body("pick", seeded(7, 'pick(1; "a", 1000; "b")', 3000), 'random_count(L, "a") < 30')
    # Weight from variables, expressions evaluated each call
    s.body("pick", ["rand_seed(8)", "var/w = 0"], 'pick(w; "a", 100 - w; "b")')
    s.body("pick", ["rand_seed(8)", "var/n = 0", "var/x = pick(100; n++, 100; n++)"], "list(n, isnum(x))")
    s.body("pick", ["rand_seed(8)", "var/n = 0", "var/x = pick(n++, n++, n++)"], "list(n, isnum(x))")
    s.body("pick", ["rand_seed(8)", "var/n = 0", "var/x = pick((n += 10); 1, (n += 1); 2)"], "list(n, isnum(x))")
    # The documented newline form, written on one line
    s.body("pick", ["rand_seed(8)"], 'pick(prob(100) "a", prob(0) "b")')


# ---------------------------------------------------------------- roll
ROLL_TEXT = ["3d6", "3d6+2", "3d6-2", "1d6", "d6", "D6", "3D6", "2d4+1", "2d4-1", "2d4 + 1", " 2d4", "2d4 ", "2 d4",
             "2d 4", "6", "0", "-3", "1", "2d", "d", "", "abc", "0d6", "-2d4", "2d0", "2d-4", "2d1", "1d1", "3d1+5",
             "1d1-5", "1.5d4", "2d4.5", "2d4+1.5", "2d4+-1", "2d4++1", "2d4+1+1", "2d4*2", "2d4x", "+2d4", "2d4+",
             "2d4d6", "1d1+1000000", "0x2d4", "1d1 +2", "2d4-0", "1e1d1", "02d03", "1d1+", "1d1-", "d1", "dd",
             "10d1", "1d1+0.5", "1d2", "3d2-3", "4"]
ROLL_N = ["0", "1", "2", "-1", "0.5", "1.5", "2.9", "null", '"2"']
ROLL_S = ["0", "1", "2", "3", "6", "-1", "-3", "0.5", "2.5", "null", '"6"']


def build_roll(s):
    for t in ROLL_TEXT:
        d = dm_str(t)
        s.body("roll", ["rand_seed(1)"], f"roll({d})")
        s.body("roll", seeded(2, f"roll({d})", 2000), "random_range(L)")
    # 1-argument non-text
    for a in NUM + ["new /datum", "list()", "list(1)", "/datum", "-6", "6", "2.5", "1e7"]:
        s.body("roll", ["rand_seed(1)"], f"roll({a})")
    for a in ["6", "1", "0", "-6", "2.5", "0.5", "-0.5", "null", "list()"]:
        s.body("roll", seeded(2, f"roll({a})", 2000), "random_range(L)")
    # 2-argument sweep: one seeded value, then the range over many draws on small values
    R2 = NUM_S + ["1.5", "2.9", "-0.5", "NAN", "null", '"3"', "list()", "new /datum", "/datum", '"2d4"']
    R2_SIDES = R2 + ["PINF", "NINF", "1e7"]
    for a in R2:
        for b in R2_SIDES:
            s.body("roll", ["rand_seed(3)"], f"roll({a}, {b})")
    for a in ROLL_N:
        for b in ROLL_S:
            s.body("roll", seeded(4, f"roll({a}, {b})", 2000), "random_range(L)")
    # Seeded sequences
    for seed in ["1", "7", "42"]:
        for e in ['roll("3d6")', "roll(3, 6)", 'roll("1d20+3")', "roll(1, 100)", 'roll("d6")', "roll(6)",
                  'roll("2d10-1")']:
            s.body("roll", seeded(seed, e, 15), "L")
    # Distribution of 2d6: 7 most common
    s.body("roll", seeded(5, "roll(2, 6)", 3000),
           "list(random_count(L, 7) > random_count(L, 2), random_count(L, 7) > random_count(L, 12), random_count(L, 7) > 400)")
    s.body("roll", seeded(5, 'roll("2d6")', 3000), "list(random_count(L, 7) > random_count(L, 3), random_count(L, 7) > 400)")
    s.body("roll", seeded(5, "roll(100, 6)", 300), "random_within(L, 100, 600)")
    s.body("roll", seeded(5, "roll(100, 6)", 300), "list(random_mean(L) > 300, random_mean(L) < 400)")
    s.body("roll", seeded(5, 'roll("100d6+50")', 300), "random_within(L, 150, 650)")
    s.body("roll", seeded(5, "roll(1, 1e7)", 300), "random_within(L, 1, 1e7)")
    s.body("roll", seeded(5, "roll(2, 2147483647)", 100), "random_within(L, 2, 4294967294)")
    s.body("roll", seeded(5, 'roll("1d1000000000")', 100), "random_within(L, 1, 1e9)")
    # Named arguments and the doc example
    for e in ["roll(ndice = 2, sides = 1)", "roll(sides = 1)", "roll(sides = 3) <= 3", "roll(ndice = 3)",
              "roll(dice = \"2d1\")", "roll(ndice = \"2d1\")", "roll(2, sides = 1)", "roll()", "roll(1, 1, 1)",
              "roll(4, 1)", "roll(0, 1)", 'roll("3d1+5") == 8', "isnum(roll(3, 6))", 'isnum(roll("3d6"))']:
        s.body("roll", ["rand_seed(6)"], e)
    s.body("roll", ["rand_seed(6)", 'var/dice = "3d6"', "var/h = roll(dice)"], "list(dice, h >= 3 && h <= 18)")
    s.body("roll", ["rand_seed(6)", "var/n = 3", "var/h = roll(n, 1)"], "list(n, h)")


# ---------------------------------------------------------------- rand_seed
SEEDS = ["0", "1", "2", "42", "12345", "-1", "-12345", "2147483647", "2147483648", "-2147483648", "4294967295",
         "4294967296", "4294967301", "1e10", "16777217", "0.5", "1.5", "1.9", "-0.5", "-1.5", "NAN", "PINF", "NINF",
         '"5"', '"abc"', "null", "list()", "new /datum", "/datum", "1e-7"]


def build_seed(s):
    for v in SEEDS:
        s.body("rand_seed", [f"rand_seed({v})", "var/list/L = list()", "for(var/i in 1 to 10)",
                             "\tL += rand(1, 1000000)"], "L")
    # BYOND has no value for rand_seed(): using it as an expression is a compile error there
    for v in ["5", "null", '"abc"']:
        s.case("rand_seed", f"rand_seed({v})")
    s.body("rand_seed", [f"var/x = rand_seed(5)"], "x")
    # Which seeds give the same sequence (PRNG-independent)
    for a, b in [("7", "7"), ("7", "8"), ("1", "1.5"), ("1", "1.9"), ("2", "1.9"), ("0", "0.5"), ("0", "-0.5"),
                 ("-1", "-1.5"), ("-2", "-1.5"), ("5", "4294967301"), ("-1", "4294967295"), ("0", "4294967296"),
                 ("2147483647", "2147483648"), ("-2147483648", "2147483648"), ('"5"', "5"), ('"5"', "0"), ("null", "0"),
                 ('"abc"', "0"), ("list()", "0"), ("NAN", "0"), ("PINF", "0"), ("NINF", "0"), ("1e-7", "0"),
                 ("0", "1"), ("16777217", "16777216"), ("16777217", "16777218"), ("1e10", "1410065408"),
                 ("/datum", "0"), ("new /datum", "0"), ("-0", "0"), ("1", "-1"), ("NAN", "PINF")]:
        s.body("rand_seed", [f"var/list/A = random_seq({a})", f"var/list/B = random_seq({b})"], "random_same(A, B)")
    # Re-seeding mid-sequence restarts it
    s.body("rand_seed", ["rand_seed(9)", "var/a = rand(1, 1000000)", "var/b = rand(1, 1000000)", "rand_seed(9)",
                         "var/c = rand(1, 1000000)", "var/d = rand(1, 1000000)"], "list(a == c, b == d, a == b)")
    s.body("rand_seed", ["rand_seed(9)", "var/list/A = list()", "for(var/i in 1 to 50)", "\tA += rand()", "rand_seed(9)",
                         "var/list/B = list()", "for(var/i in 1 to 50)", "\tB += rand()"], "random_same(A, B)")
    s.body("rand_seed", ["rand_seed(9)", "var/x = rand(1, 1000000)", "var/list/A = random_seq(9, 1)"], "A[1] == x")
    s.body("rand_seed", ["rand_seed()", "var/x = rand(1, 6)"], "isnum(x)")
    s.body("rand_seed", ["rand_seed(Seed = 9)", "var/x = rand(1, 1000000)", "rand_seed(9)"], "x == rand(1, 1000000)")
    s.body("rand_seed", ["rand_seed(9, 10)", "var/x = rand(1, 1000000)", "rand_seed(9)"], "x == rand(1, 1000000)")
    s.body("rand_seed", ["var/s = 9", "rand_seed(s)", "var/x = rand(1, 1000000)", "rand_seed(9)"],
           "list(s, x == rand(1, 1000000))")
    # A sequence mixing every random proc from one seed
    for seed in ["3", "77"]:
        s.body("rand_seed", [f"rand_seed({seed})"],
               'list(rand(1, 100), prob(50), pick(1, 2, 3), roll("1d6"), rand(), pick(list(4, 5, 6)), roll(2, 4), '
               'pick(50; "a", "b"), rand(10), prob(10))')
    # How each random proc maps onto the generator: same seed, compare 20 results
    rel = [("rand(1, 6)", "roll(1, 6)"), ("rand(1, 6)", 'roll("1d6")'), ("rand(1, 6)", "roll(6)"),
           ("rand(1, 6)", "pick(1, 2, 3, 4, 5, 6)"), ("rand(1, 6)", "pick(list(1, 2, 3, 4, 5, 6))"),
           ("rand(1, 6)", "rand(6, 1)"), ("rand(0, 5)", "rand(5)"), ("rand(1, 2) - 1", "prob(50)"),
           ("rand(0, 1)", "prob(50)"), ("rand(1, 100) <= 50", "prob(50)"), ("rand(1, 6) + 2", 'roll("1d6+2")'),
           ("pick(1, 2, 3)", "pick(list(1, 2, 3))"), ("pick(1, 2)", 'pick(100; 1, 100; 2)'),
           ("rand(1, 6)", "rand(1.5, 6.5)"), ("rand(1, 6)", "rand(1.9, 6.9)"), ("rand(0, 6)", "rand(0.5, 6)"),
           ("round(rand() * 6) + 1", "rand(1, 6)"), ("prob(50)", "rand() < 0.5"), ("prob(50)", "rand() >= 0.5"),
           ("rand(1, 1000)", "rand(1, 1000.4)"), ("rand(0, 9)", "rand(9.9)")]
    for a, b in rel:
        s.body("rand_seed", ["rand_seed(13)", "var/list/A = list()", "for(var/i in 1 to 20)", f"\tA += {a}",
                             "rand_seed(13)", "var/list/B = list()", "for(var/i in 1 to 20)", f"\tB += {b}"],
               "random_same(A, B)")
    # How many generator steps each call consumes
    calls = ["rand()", "rand(1, 10)", "rand(1, 1000000)", "rand(5, 5)", "rand(10)", "rand(0)", "rand(1, 2)",
             "rand(1, 1e10)", "prob(50)", "prob(0)", "prob(100)", "prob(-1)", "prob(1000)", "pick(1, 2, 3)", "pick(1, 2)",
             "pick(list(1, 2, 3))", "pick(list(1))", "pick(5)", "pick(1, 1)", 'pick(50; 1, 2)', 'pick(0; 1, 100; 2)',
             'roll("3d6")', "roll(3, 6)", 'roll("1d1")', "roll(1, 1)", 'roll("0d6")', "roll(0, 6)", 'roll("3d6+2")',
             "roll(6)", "roll(10, 1)", 'roll("2d1")', 'generator("num", 0, 1)', 'generator("num", 0, 1).Rand()',
             'generator("vector", vector(0, 0), vector(1, 1)).Rand()', 'generator("box", vector(0, 0), vector(1, 1)).Rand()',
             'generator("circle", 1, 2).Rand()']
    for c in calls:
        s.body("rand_seed", ["rand_seed(11)", f"var/x = {c}", "x = x", "var/a = rand(1, 1000000)"],
               "random_draws_used(11, a)")
    s.body("rand_seed", ["rand_seed(11)", "var/x = rand(1, 10)", "x = rand(1, 10)", "var/a = rand(1, 1000000)"],
           "random_draws_used(11, a)")
    s.body("rand_seed", ["rand_seed(11)", "rand_seed(11)", "var/a = rand(1, 1000000)"], "random_draws_used(11, a)")
    s.body("rand_seed", ["rand_seed(11)", "var/x = rand(1, 10)", "rand_seed(11)", "x = x", "var/a = rand(1, 1000000)"],
           "random_draws_used(11, a)")


# ---------------------------------------------------------------- generator
def build_generator(s):
    s.case("generator", "list(UNIFORM_RAND, NORMAL_RAND, LINEAR_RAND, SQUARE_RAND)")
    gens = ['"num", 0, 10', '"num", 10, 0', '"num", 5, 5', '"num", -3, 3', '"num", 0.25, 0.75', '"num", 5', '"num"',
            '"num", 0, 10, UNIFORM_RAND', '"num", 0, 10, NORMAL_RAND', '"num", 0, 10, LINEAR_RAND',
            '"num", 0, 10, SQUARE_RAND', '"num", 0, 10, 99', '"num", 0, 10, -1', '"num", 0, 10, null', '"num", "0", "10"',
            '"num", null, null', '"num", 0, PINF', '"num", 1e7, 1e7 + 1', '"num", vector(1, 2), vector(3, 4)',
            '"vector", vector(0, 0), vector(10, 10)', '"vector", vector(0, 0, 0), vector(10, 10, 10)',
            '"vector", vector(10, 10), vector(0, 0)', '"vector", list(0, 0), list(10, 10)', '"vector", 0, 10',
            '"vector", vector(1, 2), vector(1, 2)', '"vector", vector(0, 0), vector(10, 10), LINEAR_RAND',
            '"box", vector(0, 0), vector(10, 20)', '"box", vector(0, 0, 0), vector(10, 20, 30)',
            '"box", vector(10, 20), vector(0, 0)', '"box", list(0, 0), list(10, 20)', '"box", 0, 10',
            '"box", vector(-5, -5), vector(5, 5), NORMAL_RAND', '"circle", 2, 4', '"circle", 4, 2', '"circle", 0, 1',
            '"circle", 3, 3', '"circle", 2, 4, SQUARE_RAND', '"sphere", 2, 4', '"sphere", 0, 1', '"sphere", 4, 2',
            '"square", 2, 5', '"square", 0, 3', '"square", 5, 2', '"square", vector(2, 2), vector(5, 5)',
            '"cube", 2, 5', '"cube", 0, 3', '"cube", vector(2, 2, 2), vector(5, 5, 5)',
            '"color", "#ff0000", "#0000ff"', '"color", "#000000", "#ffffff"', '"color", "#ff0000", "#ff0000"',
            '"color", "red", "blue"', '"color", rgb(0, 0, 0, 0), rgb(255, 255, 255, 255)',
            '"color", list(1, 0, 0, 0, 1, 0, 0, 0, 1), list(0, 1, 0, 1, 0, 0, 0, 0, 1)',
            '"color", "#ff0000", list(0, 1, 0, 1, 0, 0, 0, 0, 1)', '"foo", 0, 1', '"NUM", 0, 1', 'null, 0, 1',
            '5, 0, 1', '', '"num", 0, 1, 0, 9']
    for g in gens:
        s.body("generator", [f"var/generator/G = generator({g})"], "G")
        s.body("generator", [f"var/generator/G = generator({g})"], "list(G.type, istype(G, /generator), istype(G, /datum))")
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(1)"], "G.Rand()")
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(1)", "var/list/L = list()",
                             "for(var/i in 1 to 300)", "\tL.len++", "\tL[L.len] = G.Rand()"],
               "list(isnum(L[1]), istext(L[1]), istype(L[1], /vector), islist(L[1]), istype(L[1], /matrix))")
    # Determinism under rand_seed (OD uses an RNG that rand_seed doesn't reach)
    for g in ['"num", 0, 1000', '"vector", vector(0, 0), vector(1000, 1000)', '"box", vector(0, 0), vector(1000, 1000)',
              '"circle", 1, 1000', '"sphere", 1, 1000', '"color", "#000000", "#ffffff"', '"num", 0, 1000, NORMAL_RAND']:
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(5)", "var/a = G.Rand()", "rand_seed(5)",
                             "var/b = G.Rand()"], '"[a]" == "[b]"')
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(5)", "var/list/A = list()",
                             "for(var/i in 1 to 10)", '\tA += "[G.Rand()]"'], "A")
    # Number generators: bounds and distribution shape over many draws
    for g, lo, hi in [('"num", 0, 10', 0, 10), ('"num", 10, 0', 0, 10), ('"num", -3, 3', -3, 3),
                      ('"num", 0.25, 0.75', 0.25, 0.75), ('"num", 0, 10, NORMAL_RAND', 0, 10),
                      ('"num", 0, 10, LINEAR_RAND', 0, 10), ('"num", 0, 10, SQUARE_RAND', 0, 10),
                      ('"num", -10, 10, LINEAR_RAND', -10, 10), ('"num", -10, 10, SQUARE_RAND', -10, 10),
                      ('"num", -10, 10, NORMAL_RAND', -10, 10), ('"num", 5, 5', 5, 5), ('"num", 5', 0, 5)]:
        lines = [f"var/generator/G = generator({g})", "rand_seed(2)", "var/list/L = list()", "for(var/i in 1 to 2000)",
                 "\tL += G.Rand()"]
        s.body("generator", lines, f"random_within(L, {lo}, {hi})")
        s.body("generator", lines, "list(round(random_mean(L), 0.5), length(random_set(L)) > 1000)")
        s.body("generator", lines + ["var/list/A = list()", "for(var/v in L)", "\tA += abs(v)"],
               "round(random_mean(A), 0.5)")
        s.body("generator", lines, f"list(random_count(L, {lo}), random_count(L, {hi}))")
    # Normal is narrower than uniform
    s.body("generator", ['var/generator/G = generator("num", 0, 10, NORMAL_RAND)', "rand_seed(2)", "var/n = 0",
                         "for(var/i in 1 to 2000)", "\tvar/v = G.Rand()", "\tif(v > 3 && v < 7)", "\t\tn++"], "n > 1300")
    # Vector generators
    for g in ['"vector", vector(0, 0), vector(10, 10)', '"vector", vector(0, 0, 0), vector(10, 10, 10)',
              '"vector", vector(10, 10), vector(0, 0)', '"vector", list(0, 0), list(10, 10)',
              '"box", vector(0, 0), vector(10, 20)', '"box", vector(0, 0, 0), vector(10, 20, 30)',
              '"box", vector(10, 20), vector(0, 0)', '"box", list(0, 0), list(10, 20)',
              '"circle", 2, 4', '"circle", 4, 2', '"circle", 0, 1', '"circle", 3, 3', '"sphere", 2, 4', '"sphere", 4, 2',
              '"sphere", 0, 1', '"square", 2, 5', '"square", 0, 3', '"square", vector(2, 2), vector(5, 5)', '"cube", 2, 5',
              '"cube", 0, 3', '"cube", vector(2, 2, 2), vector(5, 5, 5)', '"vector", 0, 10', '"box", 0, 10']:
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(3)"], "random_vstats(G)")
    for g in ['"square", 2, 5', '"cube", 2, 5', '"square", vector(2, 2), vector(5, 5)']:
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(3)", "var/ok = TRUE",
                             "for(var/i in 1 to 300)", "\tvar/vector/V = G.Rand()",
                             "\tif(max(abs(V.x), abs(V.y), abs(V.z)) < 1.999)", "\t\tok = FALSE"], "ok")
    # Colour generators
    for g in ['"color", "#ff0000", "#0000ff"', '"color", "#000000", "#ffffff"', '"color", "#ff0000", "#ff0000"']:
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(4)", "var/list/L = list()",
                             "for(var/i in 1 to 200)", "\tL += G.Rand()"],
               "list(length(L[1]), copytext(L[1], 1, 2), length(random_set(L)) > 1)")
        s.body("generator", [f"var/generator/G = generator({g})", "rand_seed(4)", "var/ok = TRUE",
                             "for(var/i in 1 to 200)", "\tvar/list/c = rgb2num(G.Rand())",
                             "\tif(c[1] + c[3] < 250 || c[1] + c[3] > 260)", "\t\tok = FALSE"], "ok")
    s.body("generator", ['var/generator/G = generator("color", "#ff0000", "#0000ff")', "rand_seed(4)", "var/ok = TRUE",
                         "for(var/i in 1 to 200)", "\tvar/list/c = rgb2num(G.Rand())", "\tif(c[2] != 0)", "\t\tok = FALSE"],
           "ok")
    # Rand() arguments, vars, copies
    s.body("generator", ['var/generator/G = generator("num", 3, 3)'], "G.Rand(1, 2, 3)")
    s.body("generator", ['var/generator/G = generator("num", 3, 3)'], "G.Rand()")
    s.body("generator", ['var/generator/G = generator("num", 3, 3)', "var/generator/H = generator(\"num\", 3, 3)"],
           "G == H")
    s.body("generator", ['var/generator/G = generator("num", 3, 3)'], '"[G]"')
    s.body("generator", ['var/generator/G = generator("num", 3, 3)'], 'G.vars.Find("type") > 0')
    s.body("generator", ["var/generator/G = new /generator"], "G")
    s.body("generator", ["var/generator/G = new /generator", "rand_seed(4)"], "G.Rand()")
    s.body("generator", ['var/generator/G = new /generator("num", 3, 3)'], "G.Rand()")
    s.body("generator", ['var/generator/G = generator(type = "num", A = 2, B = 2)'], "G.Rand()")
    s.body("generator", ['var/generator/G = generator("num", B = 2, A = 2)'], "G.Rand()")
    s.body("generator", ['var/x = generator("num", 1, 1)'], "istype(x, /generator)")
    s.case("generator", "generator(\"num\", 4, 4).Rand()")
    s.case("generator", "generator(\"vector\", vector(1, 2), vector(1, 2)).Rand()")
    s.case("generator", "generator(\"vector\", vector(1, 2, 3), vector(1, 2, 3)).Rand()")
    s.case("generator", "generator(\"box\", vector(1, 2), vector(1, 2)).Rand()")
    s.case("generator", "generator(\"circle\", 0, 0).Rand()")
    s.case("generator", "generator(\"sphere\", 0, 0).Rand()")
    s.case("generator", "generator(\"color\", \"#123456\", \"#123456\").Rand()")
    s.case("generator", "generator(\"vector\", list(1, 2), list(1, 2)).Rand()")
    s.case("generator", "generator(\"vector\", list(1, 2, 3), list(1, 2, 3)).Rand()")
