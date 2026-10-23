"""/list and /alist procs: Add, Copy, Cut, Find, Insert, Remove, RemoveAll, Swap, Splice, Join, plus
list(...), new /list(n), new /list(a, b) (multi-dimensional), var/L[n] and alist().

Every proc call runs inside a local try/catch so a runtime error prints "ERR" in the return slot and
the list is still printed as it stood after the call: list(return value, list state).

Reference (516): Add/Insert/Splice/Remove/RemoveAll flatten list arguments; Remove removes from the
end; Copy/Cut/Find/Join take Start=1, End=0 (0 = past the end); Insert returns the index after the
inserted items, Index 0 or len+1 appends; Splice clamps out-of-range indexes, accepts negative ones
and swaps End < Start; Swap keeps associations. alist keys are unique, may be numbers and always
carry a value.

OD (DreamProcNativeList.cs / DreamList.cs / DreamAssocList.cs) targets: MustGetValueAsInteger on
null/text indexes, Cut() throwing on negative start, Insert(index <= 0) appending, Splice() doing
Cut+Insert without negative/clamp/swap handling, Copy() throwing past len+1, Find() indexing
_values[start-1] for start < 1, Add() dropping associations of list args, Remove(L) on itself,
ContainsValue switching to a HashSet at 64 items, alist Find returning 0/1."""
from pools import TEXT_S, NUM_S, OTHER

# ---------- base lists (DM source) ----------
B4 = 'list("a", "b", "c", "d")'
ASSOC = 'list("a" = 1, "b" = 2, "c" = 3, "d" = 4)'
DUP = 'list("a", "b", "a", "c", "a")'
MIXED = 'list(1, "a", null, 2.5, /datum, "b" = 7, "1", list(1), 0)'
EMPTY = 'list()'

# Index arguments for a 4-item list: in range, 0, len+1, len+2, negatives down to -len-1, odd kinds
IDX = ["0", "1", "2", "3", "4", "5", "6", "-1", "-2", "-4", "-5", "1.5", "null", '"2"', "NAN"]
# Further index kinds, each tried with the other argument fixed
IDX_X = ["2.9", "-0.5", "0.5", "10", "-10", "PINF", "NINF", "1e30", "list()", "new /datum", "/datum", '""',
         "TRUE", "-3"]
# Small index pool for 3+ argument sweeps
IDX_S = ["0", "1", "2", "4", "5", "-1", "-5", "null"]
# Second index for 2-argument sweeps (odd kinds are covered by IDX_X with the other argument fixed)
IDX2 = ["0", "1", "2", "3", "4", "5", "-1", "-2", "-5", "null"]

# Items for Add/Insert/Splice: scalars, nested, assoc, flattened-or-not
ITEMS = ['"x"', '5', 'null', 'list()', 'list("x", "y")', 'list("k" = 9)', 'list(list("n"))', '"a"',
         '/datum', 'list(null)', 'new /datum', 'list("x", "k" = 9, "y")', 'NAN', 'alist("q" = 3)']
ITEMS_S = ['"x"', 'null', 'list("x", "y")', 'list("k" = 9)', 'list(list("n"))', '"a"']

# Items for Remove/RemoveAll against lists holding "a"/"b"/...
RITEMS = ['"a"', '"b"', '"z"', '"A"', 'null', '1', '0', 'list()', 'list("a", "b")', 'list("a", "a")',
          'list("a" = 5)', 'list(list("a"))', 'list("z", "c")', '/datum', 'new /datum', '2.5', '"1"', 'alist("a" = 1)']
RITEMS_S = ['"a"', '"z"', 'null', 'list("a", "b")', 'list("a", "a")', '"c"']

# Elements for Find
FELEMS = ['"a"', '"A"', '"b"', '1', '"1"', '0', 'null', '2.5', '/datum', 'list(1)', 'list()', '7', '"z"',
          'new /datum', 'NAN', 'PINF', '-0', '""']
FELEMS_S = ['"a"', '1', 'null', '"z"', '0']

GLUES = ['","', '""', '", "', 'null', '1', '"é🙂"', 'list()', 'new /datum', '"\\["', '/datum']

LISTS = [B4, ASSOC, DUP, MIXED, EMPTY, 'list(null, null)', 'new /list(3)', 'list("a" = list(1), "b")']


def build(s):
    s.dm(r'''/proc/list_show(x, depth = 0)
	if(depth > 4)
		return "..."
	if(istype(x, /alist))
		return "A([length(x)])\[[list_apairs(x)]\]"
	if(islist(x))
		var/list/L = x
		var/list/out = list()
		for(var/v in L)
			var/sv = list_show(v, depth + 1)
			out.len++
			out[out.len] = sv
			if(!isnum(v) && !isnull(v))
				var/av = L[v]
				if(!isnull(av))
					out[sv] = list_show(av, depth + 1)
		return out
	return x

/proc/list_apairs(L)
	var/t = ""
	for(var/k in L)
		if(t != "")
			t += " "
		t += "[parity_canon(k)]=[parity_canon(list_show(L[k]))]"
	return t

/proc/list_asorted(L)
	var/list/out = list()
	for(var/k in L)
		var/v = "[parity_canon(k)]=[parity_canon(list_show(L[k]))]"
		out.len++
		var/j = out.len
		while(j > 1 && sorttextEx(out[j - 1], v) < 0)
			out[j] = out[j - 1]
			j--
		out[j] = v
	var/t = ""
	for(var/x in out)
		t += "[x];"
	return t

/datum/list_thing
	var/n = 0

/datum/list_thing/New(n)
	src.n = n
''')

    def run(proc, src, args, typ="list", tag=None, post=None):
        """Run L.proc(args) on a fresh list and record (return value, list after)."""
        lines = [f'var/{typ}/L = {src}', 'var/r = "noerr"', 'try', f'\tr = L.{proc}({args})',
                 'catch(var/exception/E)', '\tr = "ERR"']
        res = f'list(list_show(r), list_show(L))' if post is None else post
        s.body(tag or f"{typ}.{proc}", lines, res)

    def sweep(proc, src, pools, min_args, typ="list", full_upto=2):
        from gen import pairwise
        import itertools
        for count in range(min_args, len(pools) + 1):
            ps = pools[:count]
            if count <= full_upto:
                rows = itertools.product(*ps)
            else:
                rows = ([ps[i][v] for i, v in enumerate(r)] for r in pairwise(ps))
            for args in rows:
                run(proc, src, ", ".join(args), typ)

    # ================= Copy / Cut =================
    for p in ("Copy", "Cut"):
        sweep(p, B4, [IDX, IDX2], 0)
        for x in IDX_X:
            run(p, B4, x)
            run(p, B4, f"1, {x}")
            run(p, B4, f"{x}, 0")
        sweep(p, ASSOC, [IDX_S, IDX_S], 0)
        sweep(p, DUP, [["0", "2", "3", "-2"], ["0", "3", "4", "-1"]], 2)
        for src in LISTS:
            run(p, src, "")
            run(p, src, "2")
            run(p, src, "1, 2")
        for e in ["Start = 2", "End = 3", "End = 3, Start = 2", "2, End = 4", "Start = -2", "End = -1",
                  "1, 1", "5, 5", "4, 2", "3, 3", "0, 0", "-1, 0", "-4, -1", "2, -1", "1, 2, 3"]:
            run(p, B4, e)
        for e in ["", "1, 1", "0, 0", "1", "2", "0, 1", "1, 2", "-1"]:
            run(p, EMPTY, e)
        # Assoc values on duplicates and on keys cut away
        s.body(f"list.{p}", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', 'var/r = L.' + p + '(1, 2)'],
               'list(list_show(r), list_show(L), L["a"])')
        s.body(f"list.{p}", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', 'var/r = L.' + p + '(3)'],
               'list(list_show(r), list_show(L), L["a"])')
        s.body(f"list.{p}", ['var/list/L = list("a" = 1, "b" = 2)', 'var/r = L.' + p + '(1, 2)', 'L += "a"'],
               'list(list_show(r), list_show(L), L["a"])')
        # Large list (OD's ContainsValue hash set starts at 64 items)
        s.body(f"list.{p}", ['var/list/L = list()', 'for(var/i in 1 to 200) L += i', 'var/r = L.' + p + '(50, 150)'],
               'list(length(r), length(L), L[1], L[L.len], L.Find(150), L.Find(49))')
        # Nested list kept by reference (shallow)
        s.body(f"list.{p}", ['var/list/N = list(1)', 'var/list/L = list(N, "b" = N)', 'var/list/r = L.' + p + '()'],
               'list(length(r) && r[1] == N, length(L), N.len)')
    s.body("list.Copy", ['var/list/L = list("a" = 1)', 'var/list/C = L.Copy()', 'C["a"] = 2', 'C += "z"'],
           'list(list_show(L), list_show(C))')
    s.body("list.Copy", ['var/list/N = list(1)', 'var/list/L = list(N)', 'var/list/C = L.Copy()', 'N += 2'],
           'list_show(C)')
    s.body("list.Copy", ['var/list/L = list(1, 2)', 'var/list/C = L.Copy()'], 'list(C == L, C ~= L, C != L)')
    s.body("list.Copy", ['var/list/L = new /list(3)', 'var/list/C = L.Copy(2)'], 'list_show(C)')
    s.body("list.Copy", ['var/list/L = list()', 'for(var/i in 1 to 100) L["k[i]"] = i', 'var/list/C = L.Copy(98)'],
           'list_show(C)')
    s.body("list.Cut", ['var/list/L = list(1, 2, 3)', 'L.Cut()', 'L.Add(4)'], 'list_show(L)')
    s.body("list.Cut", ['var/list/L = list("a" = 1, "b" = 2)', 'L.Cut()'], 'list(L["a"], L.len)')
    s.body("list.Cut", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', 'L.Cut(2, 3)'],
           'list(L["a"], L["b"], L["c"], "b" in L)')

    # ================= Find =================
    sweep("Find", MIXED, [FELEMS], 1)
    sweep("Find", DUP, [FELEMS_S, IDX], 2)
    sweep("Find", DUP, [FELEMS_S, IDX_S, IDX_S], 3, full_upto=2)
    for x in IDX_X:
        run("Find", DUP, f'"a", {x}')
        run("Find", DUP, f'"a", 1, {x}')
    for src in LISTS:
        run("Find", src, '"a"')
        run("Find", src, 'null')
        run("Find", src, '1')
    for e in ['"a", 2', '"a", 4', '"a", 1, 3', '"a", 2, 3', '"a", 4, 5', '"a", 5, 6', '"a", 0, 0', '"a", 3, 2',
              '"c", -2', '"c", -1', '"a", -1', '"a", 1, -1', '"a", 1, -2', 'Elem = "c"', '"a", Start = 2',
              '"a", End = 2', 'Start = 2', '', '"a", 1, 0, 9']:
        run("Find", DUP, e)
    # The assoc value is not an element; a key is
    run("Find", ASSOC, '1')
    run("Find", ASSOC, '"c"')
    run("Find", MIXED, '7')
    run("Find", MIXED, '"b"')
    # Identity of objects and lists
    s.body("list.Find", ['var/datum/D = new', 'var/list/L = list(1, D, new /datum)'],
           'list(L.Find(D), L.Find(new /datum), L.Find(/datum))')
    s.body("list.Find", ['var/list/N = list(1)', 'var/list/L = list(list(1), N)'], 'list(L.Find(N), L.Find(list(1)))')
    s.body("list.Find", ['var/list/L = list(1, 2, 3)'], 'L.Find(list(2))')
    s.body("list.Find", ['var/list/L = list(NAN, 1)'], 'list(L.Find(NAN), L.Find(1))')
    s.body("list.Find", ['var/z = 0', 'z *= -1', 'var/list/L = list(z, 1)'], 'list(L.Find(0), L.Find(z))')
    s.body("list.Find", ['var/list/L = list("x", 1.0, "1")'], 'list(L.Find(1), L.Find("1"), L.Find(1.0000001))')
    # 64+ items: OD switches ContainsValue to a hash set
    for e in ['L.Find(NAN)', 'L.Find(0)', 'L.Find("v70")', 'L.Find(70)', 'L.Find(70, 71)', 'L.Find(70, 1, 70)',
              'L.Find(null)', 'L.Find(z)']:
        s.body("list.Find", ['var/z = 0', 'z *= -1', 'var/list/L = list()', 'for(var/i in 1 to 100) L += i',
                             'L += "v70"', 'L += NAN', 'L += z', 'L += null'], e)
    s.body("list.Find", ['var/list/L = list("a", "b")', 'L[1] = "c"'], 'list(L.Find("a"), L.Find("c"))')

    # ================= Insert =================
    sweep("Insert", B4, [IDX, ITEMS], 1)
    for x in IDX_X:
        run("Insert", B4, f'{x}, "x"')
    sweep("Insert", B4, [IDX_S, ITEMS_S, ITEMS_S], 3)
    sweep("Insert", ASSOC, [["0", "1", "3", "5"], ITEMS_S], 2)
    for src in LISTS:
        run("Insert", src, '1, "x"')
        run("Insert", src, '0, "x"')
        run("Insert", src, '2, list("k" = 9)')
    for e in ['1, "x", "y", "z"', '3, list(1, 2), 3, list(4)', '0, "x", "y"', '5, "x", "y"', '2, list()',
              '2, list(), list()', '2, list(list(1, 2))', 'Index = 2, "x"', '2, Item1 = "x"',
              '2, null, null', '1', '', '2, list("a" = 1)', '2, list("x" = 1, "y")', '2, alist("m" = 1, "n" = 2)']:
        run("Insert", B4, e)
    for e in ['1, "x"', '0, "x"', '2, "x"', '-1, "x"']:
        run("Insert", EMPTY, e)
    # Return value is index after the items; inserting list values counts flattened items
    s.body("list.Insert", ['var/list/L = list(1, 2)', 'var/a = L.Insert(1, list(7, 8, 9))', 'var/b = L.Insert(a, "m")'],
           'list(a, b, list_show(L))')
    s.body("list.Insert", ['var/list/L = list(1, 2)', 'var/a = L.Insert(0, "x")'], 'list(a, list_show(L))')
    # Inserting the list into itself
    s.body("list.Insert", ['var/list/L = list(1, 2)', 'var/r = L.Insert(2, L)'], 'list(r, list_show(L))')
    # Associations of other keys survive, inserted assoc keys keep or lose their value
    s.body("list.Insert", ['var/list/L = list("a" = 1, "b" = 2)', 'L.Insert(2, list("k" = 9))'],
           'list(list_show(L), L["a"], L["k"])')
    s.body("list.Insert", ['var/list/L = list("a" = 1, "b" = 2)', 'L.Insert(1, "a")'],
           'list(list_show(L), L["a"], L.Find("a"))')
    s.body("list.Insert", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i', 'L.Insert(50, "m")'],
           'list(L.len, L[50], L[51], L.Find("m"), L.Find(100))')

    # ================= Splice =================
    sweep("Splice", B4, [IDX, IDX2], 0)
    for x in IDX_X:
        run("Splice", B4, f'{x}, 0, "x"')
        run("Splice", B4, f'2, {x}, "x"')
    sweep("Splice", B4, [IDX_S, IDX_S, ITEMS], 3)
    sweep("Splice", B4, [IDX_S, IDX_S, ITEMS_S, ITEMS_S], 4)
    sweep("Splice", ASSOC, [["1", "2", "-1"], ["0", "3"], ['"x"', 'list("k" = 9)']], 3)
    for src in LISTS:
        run("Splice", src, '2, 3, "x"')
        run("Splice", src, '1, 0, "x"')
    for e in ['2, 4, "firetruck", "camel", "joystick", "balloon"', '4, 2, "x"', '-3, -1, "x"', '-1, -3, "x"',
              '-100, 100, "x"', '-100, 2, "x"', '3, 100, "x"', '100, 200, "x"', '5, 5, "x"', '5, 0, "x"',
              '6, 0, "x"', '0, 0, "x"', '0, 2, "x"', '2, 2, "x"', '3, 3, "x", "y"', '2, 3', '2', '',
              '2, 3, list("x", "y")', '2, 3, list(list("x"))', '2, 3, list()', '2, 3, null', '2, 3, list("k" = 9)',
              'Start = 2, End = 3', 'End = 2', 'Start = 3', '2, 3, Item1 = "x"', '-4, 0, "x"', '-5, 0, "x"',
              '-4, -4, "x"', '1, -1, "x"', '1.5, 3.5, "x"']:
        run("Splice", B4, e)
    # Doc example
    s.body("list.Splice", ['var/list/L = list("apple", "banana", "orange", "pear")',
                           'L.Splice(2, 4, "firetruck", "camel", "joystick", "balloon")'], 'L.Join(", ")')
    s.body("list.Splice", ['var/list/L = list(1, 2, 3)', 'var/r = "noerr"', 'try', '\tr = L.Splice(2, 3, L)',
                           'catch', '\tr = "ERR"'], 'list(r, list_show(L))')
    s.body("list.Splice", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', 'L.Splice(2, 3, "x")'],
           'list(list_show(L), L["a"], L["b"], L["c"])')
    s.body("list.Splice", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i', 'L.Splice(-10, 0, "t")'],
           'list(L.len, L[L.len], L[L.len - 1], L.Find("t"))')

    # ================= Swap =================
    SW = ["0", "1", "2", "4", "5", "-1", "-4", "1.5", "null", '"2"', "NAN"]
    sweep("Swap", B4, [SW, SW], 0)
    for x in IDX_X:
        run("Swap", B4, f"1, {x}")
        run("Swap", B4, f"{x}, 2")
    sweep("Swap", ASSOC, [IDX_S, IDX_S], 2)
    for src in LISTS:
        run("Swap", src, "1, 2")
    for e in ["Index1 = 1, Index2 = 3", "1, Index2 = 4", "Index2 = 2", "2, 2", "4, 1", "1, 2, 3"]:
        run("Swap", B4, e)
    # Doc example: associations travel with their keys
    s.body("list.Swap", ['var/list/L = list("orange" = 3, "green" = 2, "blue" = 5)', 'L.Swap(1, 3)'],
           'list(list_show(L), L["orange"], L["blue"])')
    s.body("list.Swap", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', 'L.Swap(1, 2)'], 'list(list_show(L), L["a"])')
    s.body("list.Swap", ['var/list/L = list("a" = 1, 5, "b" = 2)', 'L.Swap(1, 2)'],
           'list(list_show(L), L["a"], L["b"])')
    s.body("list.Swap", ['var/list/L = list("a" = 1, "b" = 2)', 'L.Swap(1, 1)'], 'list_show(L)')
    s.body("list.Swap", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i', 'L.Swap(1, 100)'],
           'list(L[1], L[100], L.Find(1), L.Find(100))')

    # ================= Add =================
    for src in (B4, ASSOC, EMPTY):
        sweep("Add", src, [ITEMS], 1)
    sweep("Add", B4, [ITEMS_S, ITEMS_S], 2)
    for src in LISTS:
        run("Add", src, '"z"')
    for e in ['', '"x", "y", list("z", "w")', 'list(list(1), list(2))', 'Item1 = 5', 'new /list(2)',
              'list("a" = 1, "b" = 2)', 'list("k" = list(1))', '"a", "a"', 'arglist(list(1, 2))',
              'list(1, list(2, list(3)))', '1, null, 2']:
        run("Add", B4, e)
    # Association of an assoc list argument: kept or dropped?
    s.body("list.Add", ['var/list/L = list()', 'L.Add(list("k" = 9, "j" = 8))'], 'list(list_show(L), L["k"], L["j"])')
    s.body("list.Add", ['var/list/L = list("k" = 1)', 'L.Add(list("k" = 9))'], 'list(list_show(L), L["k"])')
    s.body("list.Add", ['var/list/L = list("k" = 1)', 'L.Add("k")'], 'list(list_show(L), L["k"], L.len)')
    s.body("list.Add", ['var/list/L = list()', 'L.Add(alist("k" = 9))'], 'list(list_show(L), L["k"])')
    s.body("list.Add", ['var/list/L = list(1, 2)', 'L.Add(L)'], 'list_show(L)')
    s.body("list.Add", ['var/list/L = list(1, 2)', 'L.Add(L, L)'], 'list_show(L)')
    s.body("list.Add", ['var/list/N = list(1)', 'var/list/L = list()', 'L.Add(list(N))', 'N += 2'],
           'list(list_show(L), L[1] == N)')
    s.body("list.Add", ['var/list/L = new /list(2)', 'L.Add(3)'], 'list_show(L)')
    s.body("list.Add", ['var/list/L = list()', 'for(var/i in 1 to 100) L.Add(i, "s[i]")'],
           'list(L.len, L[200], L.Find(100), L.Find("s50"))')

    # ================= Remove / RemoveAll =================
    for p in ("Remove", "RemoveAll"):
        for src in (DUP, ASSOC, 'list("a", "b", null, 1, 0, "a" = 2, /datum, 2.5, "1")'):
            sweep(p, src, [RITEMS], 1)
        sweep(p, DUP, [RITEMS_S, RITEMS_S], 2)
        for src in LISTS:
            run(p, src, '"a"')
            run(p, src, 'null')
        for e in ['', '"a", "b", "c"', '"a", "a"', 'list("a", "c"), "b"', 'Item1 = "a"', '"z", "a"',
                  'arglist(list("a", "b"))', 'list("a", "a", "a", "a")']:
            run(p, DUP, e)
        for e in ['"a"', 'null', 'list()', 'list("a")']:
            run(p, EMPTY, e)
        # Removing the list from itself
        s.body(f"list.{p}", ['var/list/L = list(1, 2, 1)', f'var/r = L.{p}(L)'], 'list(r, list_show(L))')
        s.body(f"list.{p}", ['var/list/L = list(1, 2, 1)', f'var/r = L.{p}(1, L)'], 'list(r, list_show(L))')
        # Association removed with the key; duplicate keys share one association
        s.body(f"list.{p}", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', f'var/r = L.{p}("a")'],
               'list(r, list_show(L), L["a"])')
        s.body(f"list.{p}", ['var/list/L = list("a" = 1, "b" = 2)', f'var/r = L.{p}("a")', 'L += "a"'],
               'list(r, list_show(L), L["a"])')
        s.body(f"list.{p}", ['var/list/L = list("a" = 1, "b" = 2)', f'var/r = L.{p}(1)'], 'list(r, list_show(L))')
        # Objects by identity
        s.body(f"list.{p}", ['var/datum/D = new', 'var/list/L = list(D, new /datum, D)', f'var/r = L.{p}(D)'],
               'list(r, list_show(L), L.Find(D))')
        s.body(f"list.{p}", ['var/list/N = list(1)', 'var/list/L = list(N, list(1), N)', f'var/r = L.{p}(list(N))'],
               'list(r, L.len, L.Find(N))')
        s.body(f"list.{p}", ['var/list/L = list(NAN, 1, NAN)', f'var/r = L.{p}(NAN)'], 'list(r, list_show(L))')
        # 64+ items
        s.body(f"list.{p}", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i % 10', f'var/r = L.{p}(3, 7)'],
               'list(r, L.len, L.Find(3), L.Find(7), L.Find(4))')
        s.body(f"list.{p}", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i % 10', 'L += NAN',
                             f'var/r = L.{p}(NAN)'], 'list(r, L.len)')
    # Remove goes from the end (the reverse of Add)
    s.body("list.Remove", ['var/list/L = list("a", "b", "a", "b")', 'L.Remove("a")'], 'list_show(L)')
    s.body("list.Remove", ['var/list/L = list("a", "b", "a", "b")', 'L.Remove(list("b", "a"))'], 'list_show(L)')
    s.body("list.Remove", ['var/list/L = list(1, 2, 3)', 'L.Add(4, 5)', 'L.Remove(4, 5)'], 'list_show(L)')
    s.body("list.RemoveAll", ['var/list/L = list("a", "b", "a", "b", "c")', 'var/r = L.RemoveAll("a", "b", "a")'],
           'list(r, list_show(L))')
    s.body("list.RemoveAll", ['var/list/L = list()', 'for(var/i in 1 to 300) L += i % 3', 'var/r = L.RemoveAll(0)'],
           'list(r, L.len)')

    # ================= Join =================
    J = 'list("a", 1, null, 2.5, /datum, list(1), "b" = 2, "é")'
    sweep("Join", J, [GLUES], 0)
    sweep("Join", B4, [['","', 'null', '""'], IDX, IDX_S], 2)
    for x in IDX_X:
        run("Join", B4, f'",", {x}')
        run("Join", B4, f'",", 1, {x}')
    for src in LISTS:
        run("Join", src, '"|"')
    for e in ['Glue = "-"', '"-", Start = 2', '"-", End = 3', 'Start = 2', '"-", 1, 0, 5']:
        run("Join", B4, e)
    s.body("list.Join", ['var/list/L = list(new /datum/list_thing(1), new /obj, 1e7, 0.1, 1e-7, PINF, NAN)'],
           'L.Join(",")')
    s.body("list.Join", ['var/list/L = list("a" = 1, "b" = 2)'], 'list(L.Join(","), jointext(L, ","))')
    s.body("list.Join", ['var/list/L = list()', 'for(var/i in 1 to 100) L += i'], 'length(L.Join(","))')

    build_ctor(s)
    build_alist(s, run, sweep)
    build_gaps(s, run)


def build_ctor(s):
    # ================= list(...) =================
    for e in ['list()', 'list(1, 2, 3)', 'list("a" = 1)', 'list(a = 1, b = 2)', 'list("a" = 1, "a" = 2)',
              'list("a", "a" = 2)', 'list("a" = 2, "a")', 'list(1, "a" = 2, 3)', 'list(null)', 'list(null, null)',
              'list(list())', 'list(list(1, 2), list())', 'list(/datum = 1)', 'list("a" = list(1, 2))',
              'list("a" = null)', 'list("" = 1)', 'list("1" = 2)', 'list(1 = 2)', 'list(null = 1)', 'list((1) = 2)',
              'list((null) = 2)', 'list(("x") = 2)', 'list(list(1) = 2)', 'list(new /datum = 1)',
              'list(arglist(list(1, 2)))', 'list(arglist(list("a" = 1)))', 'list(NAN)', 'list(PINF, NINF)',
              'list("a" = 1, 2, "b")', 'list(1, list(2, list(3)))', 'list(1e7, 16777217)', 'list(a = 1, "b" = 2, c = 3)',
              'list(type = 1)', 'list(len = 5)', 'list("len" = 5)']:
        s.case("list()", e)
    s.body("list()", ['var/k = "x"'], 'list(k = 1)')
    s.body("list()", ['var/k = "x"'], 'list((k) = 1)')
    s.body("list()", ['var/k = "x"'], 'list("[k]" = 1)')
    s.body("list()", ['var/list/L = list(1, 2)'], 'list(L)')
    s.body("list()", ['var/list/L = list(1, 2)'], 'list(L, L)')
    s.body("list()", ['var/list/L = list("a" = 1, "b" = 2)'], 'list(L["a"], L["b"], L["c"], L.len)')
    s.body("list()", ['var/list/L = list("a" = 1, "a" = 2)'], 'list(L["a"], L.len)')
    s.body("list()", ['var/list/L = list("a", "a" = 2)'], 'list(L["a"], L.len, L.Find("a"))')
    s.body("list()", ['var/list/L = list(1, 2)', 'var/list/M = list(1, 2)'], 'list(L == M, L ~= M)')
    s.body("list()", ['var/list/L = list(1, 2)', 'L.len = 4'], 'list_show(L)')
    s.body("list()", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', 'L.len = 1'],
           'list(list_show(L), L["a"], L["b"])')
    s.body("list()", ['var/list/L = list(1, 2)', 'L.len = 0', 'L.len = 2'], 'list_show(L)')
    for v in ['-1', '2.7', '"3"', 'null', 'NAN']:
        s.body("list()", ['var/list/L = list(1, 2, 3)', 'var/r = "noerr"', 'try', f'\tL.len = {v}', 'catch',
                          '\tr = "ERR"'], 'list(r, list_show(L))')

    # ================= new /list =================
    for a in ['', '0', '1', '3', '-1', '2.5', '2.9', '"3"', 'null', 'NAN', 'list()', 'list(1, 2)',
              '2, 3', '2, 0', '0, 2', '2, 2, 2', '1, 1, 1, 1', '-1, 2', '2, -1', '2, "3"', '2, null', '"2", 2',
              '2, 2.5', 'Size = 3', '3, list()', '1, 2, 0']:
        s.body("new/list", ['var/r = "noerr"', 'try', f'\tr = new /list({a})', 'catch', '\tr = "ERR"'], 'list_show(r)')
    s.case("new/list", 'length(new /list(100000))')
    s.body("new/list", ['var/list/L = new /list(3, 2)', 'L[1][1] = "x"'], 'list(list_show(L), L[1] != L[2])')
    s.body("new/list", ['var/list/L = new /list(2, 2)'], 'list(L[1] == L[2], islist(L[1]), length(L[2]))')
    s.body("new/list", ['var/list/L = new /list(3)', 'L[2] = 5'], 'list_show(L)')
    s.body("new/list", ['var/list/L = new'], 'list_show(L)')
    s.body("new/list", ['var/list/L = new()', 'L += 1'], 'list_show(L)')
    s.body("new/list", ['var/L[3]'], 'list_show(L)')
    s.body("new/list", ['var/L[0]'], 'list_show(L)')
    s.body("new/list", ['var/L[]'], 'list_show(L)')
    s.body("new/list", ['var/L[2][3]'], 'list_show(L)')
    s.body("new/list", ['var/L[2][3]', 'L[2][3] = 1'], 'list_show(L)')
    s.body("new/list", ['var/n = 4', 'var/L[n]'], 'list_show(L)')
    s.body("new/list", ['var/list/L[2]'], 'list_show(L)')
    s.body("new/list", ['var/list/L = new /list(2)', 'L["a"] = 1'], 'list_show(L)')
    s.body("new/list", ['var/t = /list', 'var/list/L = new t(2)'], 'list_show(L)')
    s.body("new/list", ['var/list/L = new /list(2)'], 'list(L.type, istype(L, /list), islist(L))')


def build_alist(s, run, sweep):
    A2 = 'alist("a" = 1, "b" = 2)'
    A3 = 'alist("a" = 1, "b" = 2, "c" = 3)'
    show = 'list(list_show(r), list_show(L), list_asorted(L))'
    srcs = ['alist()', A3, 'alist("x" = 0, "y" = "")', 'alist("a" = list(1), "b" = null)']
    # ================= alist() construction =================
    for e in ['alist()', A2, 'alist(a = 1, b = 2)', 'alist("a" = 1, "a" = 2)', 'alist("x")', 'alist("x", "y")',
              'alist(1 = 2)', 'alist((1) = 2)', 'alist(null)', 'alist("a" = null)', 'alist(/datum = 1)',
              'alist("a" = list(1, 2))', 'alist(arglist(list("a" = 1, "b" = 2)))', 'alist("c" = 3, "a" = 1, "b" = 2)',
              'alist("b" = 1, "a" = 2, 3 = 4)', 'alist(list(1) = 2)']:
        s.body("alist()", ['var/r = "noerr"', 'try', f'\tr = {e}', 'catch', '\tr = "ERR"'],
               'list(list_show(r), list_asorted(r), length(r))')
    for e in ['', '5', '"a" = 1', 'list("a" = 1)']:
        s.body("alist()", ['var/r = "noerr"', 'try', f'\tr = new /alist({e})', 'catch', '\tr = "ERR"'],
               'list(list_show(r), list_asorted(r))')
    s.body("alist()", ['var/alist/A = alist()', 'A[1] = "x"', 'A[2.5] = "y"', 'A["1"] = "z"'],
           'list(list_show(A), list_asorted(A), A[1], A[2.5], A["1"], A[2], length(A))')
    s.body("alist()", ['var/alist/A = alist()', 'A["c"] = 1', 'A["a"] = 2', 'A["b"] = 3'],
           'list(list_show(A), list_asorted(A))')
    s.body("alist()", ['var/alist/A = alist()', 'A[3] = 1', 'A[1] = 2', 'A[2] = 3', 'A[-1] = 4'],
           'list(list_show(A), list_asorted(A))')
    s.body("alist()", ['var/alist/A = alist("a" = 1)', 'A["a"] = 5'], 'list(list_show(A), length(A))')
    s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)'], 'list(A["a"], A["zz"], A[1], "a" in A, 1 in A, 2 in A)')
    s.body("alist()", ['var/alist/A = alist("a" = 1)', 'var/r = "noerr"', 'try', '\tA[null] = 3', 'catch',
                       '\tr = "ERR"'], 'list(r, list_show(A), list_asorted(A))')
    s.body("alist()", ['var/datum/D = new /datum/list_thing(4)', 'var/alist/A = alist()', 'A[D] = 1'],
           'list(A[D], length(A), D in A)')
    s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/out = ""', 'for(var/k in A)', '\tout += "[k];"'],
           'out')
    s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/out = ""', 'for(var/k, v in A)',
                       '\tout += "[k]=[v];"'], 'out')
    s.body("alist()", ['var/alist/A = alist("a" = 1)', 'var/list/L = A'], 'list(islist(A), istype(A, /alist), istype(A, /list), A.type, length(L))')
    s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/alist/B = alist("b" = 2, "a" = 1)'],
           'list(A == B, A ~= B, A ~= alist("a" = 1, "b" = 3))')
    for v in ['0', '2', '-1', 'null', '"x"']:
        s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/r = "noerr"', 'try', f'\tA.len = {v}',
                           'catch', '\tr = "ERR"'], 'list(r, list_asorted(A))')
    # Operators on alists
    for e in ['A + "c"', 'A + list("c" = 3)', 'A + list("a" = 9)', 'A - "a"', 'A - list("a", "b")', 'A | list("z")',
              'A & list("a")', 'A + alist("q" = 1)', 'list("x") + A']:
        s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/r = "noerr"', 'try', f'\tr = {e}', 'catch',
                           '\tr = "ERR"'], 'list(list_show(r), list_asorted(r), list_asorted(A))')
    for e in ['A += "c"', 'A += list("a" = 9, "c" = 3)', 'A -= "a"', 'A -= A', 'A |= list("z" = 1)', 'A &= list("a")',
              'A &= "a"', 'A ^= list("a", "z")', 'A += 5']:
        s.body("alist()", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/r = "noerr"', 'try', f'\t{e}', 'catch',
                           '\tr = "ERR"'], 'list(r, list_asorted(A), length(A))')

    # ================= alist procs =================
    def arun(proc, src, args):
        run(proc, src, args, typ="alist", post=show)

    for src in srcs:
        for p, args in [("Add", '"z"'), ("Add", '"a"'), ("Copy", ''), ("Cut", ''), ("Find", '"a"'), ("Find", '1'),
                        ("Remove", '"a"'), ("RemoveAll", '"a"'), ("Join", '","'), ("Insert", '1, "z"'),
                        ("Swap", '1, 2'), ("Splice", '1, 2, "z"')]:
            arun(p, src, args)
    for args in ['"z", "y"', 'list("q" = 1)', 'list("q" = 1, "a" = 9)', 'alist("q" = 1)', 'null', '5', 'list("z", "z")',
                 '', 'list(list(1))', 'new /datum', 'NAN']:
        arun("Add", A3, args)
    for args in ['1', '2', '0', '1, 0', '0, 0', '1, 2', '2, 3', '1, 4', '1, 5', '-1', '2, 0', 'null', '1, null',
                 'Start = 1', 'End = 2']:
        arun("Copy", A3, args)
        arun("Cut", A3, args)
    for args in ['"a", 2', '"a", 1, 2', '"c", 1, 2', '"c", 3', '"zz"', 'null', '3', '"b", 0, 0', '"b", -1', 'list("a")',
                 '2', '']:
        arun("Find", A3, args)
    for args in ['"a", "b"', 'list("a", "c")', 'list("a" = 5)', 'alist("a" = 1)', '"zz"', 'null', '1', '', '"a", "a"']:
        arun("Remove", A3, args)
        arun("RemoveAll", A3, args)
    for args in ['', '"-"', 'null', '"-", 2', '"-", 1, 2', '"-", -1', '"-", 1, 4', '"-", 1, 5', '"-", 0, 0']:
        arun("Join", A3, args)
    for args in ['0, "z"', '4, "z"', '2, list("q" = 1)', '1']:
        arun("Insert", A3, args)
    for args in ['1, 1', '2, 3', '0, 1']:
        arun("Swap", A3, args)
    for args in ['', '1, 0', '1, 0, "z"', '2, 3', '0, 0, "z"']:
        arun("Splice", A3, args)
    # Remove/Find with numeric keys
    for p, args in [("Find", '1'), ("Find", '2'), ("Find", '"1"'), ("Remove", '1'), ("Remove", '"1"'),
                    ("RemoveAll", '2'), ("Copy", ''), ("Copy", '2'), ("Cut", '1, 2'), ("Join", '","'), ("Add", '1'),
                    ("Add", '3')]:
        s.body(f"alist.{p}", ['var/alist/L = alist()', 'L[1] = "x"', 'L[2] = "y"', 'L["1"] = "z"', 'var/r = "noerr"',
                              'try', f'\tr = L.{p}({args})', 'catch(var/exception/E)', '\tr = "ERR"'], show)
    # Copy is independent of the source
    s.body("alist.Copy", ['var/alist/A = alist("a" = 1)', 'var/alist/C = A.Copy()', 'C["a"] = 2', 'C["b"] = 3'],
           'list(list_asorted(A), list_asorted(C), istype(C, /alist))')
    # list.Copy of an alist argument and list procs taking alist arguments
    s.body("alist.Copy", ['var/alist/A = alist("a" = 1)', 'var/list/L = list(1)', 'L.Insert(1, A)'], 'list_show(L)')
    s.body("alist.Copy", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/list/L = list("a", "b", "c")', 'var/r = L.Remove(A)'],
           'list(r, list_show(L))')
    s.body("alist.Copy", ['var/alist/A = alist("a" = 1, "b" = 2)', 'var/list/L = list("x")', 'L.Splice(1, 2, A)'],
           'list_show(L)')


def build_gaps(s, run):
    """Gaps from review: for-in under mutation, del() and OD's list pool, special lists, named/arglist
    arguments, null and dynamic calls, 2D sublists, type-level list vars, big assoc lists, flattening of
    special lists, Copy()/Join() types, new /list argument forms, repeated Remove/RemoveAll items."""
    # args-list helpers: each is called with (1, 2, 3) and reports (return, args.len, args)
    arg_ops = {"cut": "args.Cut(1, 2)", "ins": "args.Insert(1, 9)", "swap": "args.Swap(1, 3)",
               "rem": "args.Remove(2)", "splice": 'args.Splice(1, 2, "z")', "add": "args.Add(4)",
               "copy": "args.Copy(2)", "find": "args.Find(3)", "join": 'args.Join("-")',
               "copytype": "args.Copy().type"}
    for name, call in arg_ops.items():
        s.dm(f'''/proc/list_args_{name}()
	var/r = "noerr"
	try
		r = {call}
	catch
		r = "ERR"
	var/t = ""
	for(var/i in 1 to args.len)
		t += "[args[i]];"
	return list(list_show(r), args.len, t)
''')
    s.dm('''/proc/list_args_flat_ins()
	var/list/L = list("p")
	var/r = "noerr"
	try
		r = L.Insert(1, args)
	catch
		r = "ERR"
	return list(r, list_show(L))

/proc/list_args_flat_splice()
	var/list/L = list("p")
	var/r = "noerr"
	try
		r = L.Splice(1, 0, args)
	catch
		r = "ERR"
	return list(r, list_show(L))

/proc/list_args_flat_add()
	var/list/L = list()
	L.Add(args)
	return list_show(L)

/datum/list_holder
	var/L[3]
	var/list/M = list(1, 2)
	var/list/G = new /list(2, 2)
	var/list/A = list("a" = 1)
	var/alist/Q = alist("k" = 1)
''')
    for name in arg_ops:
        s.case("list.args", f"list_args_{name}(1, 2, 3)")
    s.case("list.args", "list_args_cut()")
    s.case("list.args", "list_args_swap(1)")
    s.case("list.args", "list_args_flat_ins(1, 2)")
    s.case("list.args", "list_args_flat_splice(1, 2)")
    s.case("list.args", "list_args_flat_add(1, 2)")
    s.case("list.args", 'list_args_flat_add(1, "k" = 2)')

    # ================= for-in while the loop body mutates the list =================
    MUT = ["L.Cut()", "L.Add(x + 10)", 'if(x == 1) L.Remove(4)', "L.Swap(1, 4)", 'L.Insert(1, "z")',
           'L.Splice(2, 0, "q")', "L.Cut(1, 2)", "L.len = 2", "L.Remove(x)", 'L.Copy()', 'L += x']
    for m in MUT:
        for init in (['var/list/L = list(1, 2, 3, 4)'],
                     ['var/list/L = list()', 'for(var/i in 1 to 100) L += i']):
            s.body("list.forin", init + ['var/out = ""', 'var/n = 0', 'for(var/x in L)', '\tif(++n > 300) break',
                                         '\tout += "[x];"', f'\t{m}'],
                   'list(n, out, L.len, L.Join(","))')
    # Indexed loop sees the live list
    s.body("list.forin", ['var/list/L = list(1, 2, 3, 4)', 'var/out = ""', 'for(var/i = 1, i <= L.len && i < 50, i++)',
                          '\tout += "[L[i]];"', '\tif(i == 1) L.Add(5)'], 'list(out, L.len)')
    s.body("list.forin", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', 'var/out = ""', 'for(var/k in L)',
                          '\tout += "[k]=[L[k]];"', '\tL.Remove("c")'], 'list(out, L.Join(","))')
    s.body("list.forin", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', 'var/out = ""', 'for(var/k, v in L)',
                          '\tout += "[k]=[v];"', '\tL["c"] = 9'], 'list(out, L["c"])')

    # ================= del() on a list, OD's list pool =================
    s.body("list.del", ['var/list/L = list(1, 2)', 'var/list/M = L', 'del(L)'], 'list(isnull(M), isnull(L))')
    s.body("list.del", ['var/list/L = list(1, 2)', 'var/list/M = L', 'del(L)', 'var/r = "noerr"', 'try',
                        '\tM.Add(1)', '\tr = M.len', 'catch', '\tr = "ERR"'], 'r')
    s.body("list.del", ['var/list/L = list(1, 2)', 'var/list/W = list(L)', 'del(L)'], 'list(W.len, isnull(W[1]))')
    s.body("list.del", ['var/list/L = new /list(3000)', 'var/list/M = L', 'del(L)', 'var/list/N = new /list(3000)',
                        'N[1] = 7', 'var/r = "noerr"', 'try',
                        '\tr = list(M ? M.len : "null", M ? M[1] : "-", N.len, N[1])', 'catch', '\tr = "ERR"'], 'r')
    s.body("list.del", ['var/list/P = new /list(3000)', 'P[1] = 7', 'P[2999] = 7', 'P = null',
                        'var/list/L = new /list(3000)'], 'list(length(L) == 3000, L.Find(7), L[1], L[2999])')
    s.body("list.del", ['var/list/P = new /list(3000)', 'P[1] = 7', 'P[2999] = 7', 'del(P)',
                        'var/list/L = new /list(3000)'], 'list(length(L) == 3000, L.Find(7), L[1], L[2999])')
    s.body("list.del", ['var/list/P = list()', 'for(var/i in 1 to 3000) P += i', 'del(P)',
                        'var/list/L = list()', 'L.len = 3000'], 'list(length(L), L.Find(5), L[5])')

    # ================= procs on special lists =================
    def obj_case(lines, res):
        s.body("list.special", ['var/obj/O = parity_track(new /obj)', 'var/r = "noerr"'] + lines, res)

    for call in ['O.overlays.Insert(1, "x")', 'O.overlays.Splice(1, 0, "x")', 'O.overlays.Swap(1, 2)',
                 'O.overlays.Cut(1, 2)', 'O.overlays.Add("y")', 'O.overlays.Remove("a")', 'O.overlays.Find("a")',
                 'O.overlays.Find("x")', 'O.overlays.Copy().len', 'O.overlays.Join(",")', 'O.overlays.RemoveAll("a")',
                 'O.underlays.Insert(1, "x")', 'O.underlays.Swap(1, 2)']:
        obj_case(['O.overlays += "a"', 'O.overlays += "b"', 'O.underlays += "a"', 'O.underlays += "b"', 'try',
                  f'\tr = {call}', 'catch', '\tr = "ERR"'],
                 'list(isnum(r) || istext(r) || isnull(r) ? r : "other", O.overlays.len, O.underlays.len)')
    obj_case(['O.overlays += "a"', 'var/list/C = O.overlays.Copy()'], 'list(C.type, C.len)')
    for call in ['O.contents.Insert(1, B)', 'O.contents.Swap(1, 2)', 'O.contents.Splice(1, 0, B)',
                 'O.contents.Cut(1, 2)', 'O.contents.Add(B)', 'O.contents.Remove(A1)', 'O.contents.Find(A2)',
                 'O.contents.Copy().len', 'O.contents.Copy().type', 'O.contents.Join(",")', 'O.contents.RemoveAll(A1)']:
        obj_case(['var/obj/A1 = parity_track(new /obj(O))', 'A1.name = "a1"', 'var/obj/A2 = parity_track(new /obj(O))',
                  'A2.name = "a2"', 'var/obj/B = parity_track(new /obj)', 'B.name = "b"', 'try', f'\tr = {call}',
                  'catch', '\tr = "ERR"'],
                 'list(isnum(r) || istext(r) || isnull(r) || ispath(r) ? r : "other", O.contents.Join(","), B.loc == O, A1.loc == O)')
    for call in ['D.vars.Insert(1, "x")', 'D.vars.Cut()', 'D.vars.Add("x")', 'D.vars.Swap(1, 2)', 'D.vars.Copy().type',
                 'D.vars.Find("type")', 'D.vars.Remove("type")']:
        s.body("list.special", ['var/datum/D = new', 'var/n = D.vars.len', 'var/r = "noerr"', 'try', f'\tr = {call}',
                                'catch', '\tr = "ERR"'],
               'list(isnum(r) || istext(r) || isnull(r) || ispath(r) ? r : "other", D.vars.len - n, D.type)')

    # ================= named arguments with unknown or wrong-case names =================
    for e in ['start = 2', 'Start = 2, start = 3', 'Foo = 2']:
        run("Copy", B4, e)
    for e in ['Foo = 2', 'start = 2', 'end = 2']:
        run("Cut", B4, e)
    for e in ['"a", end = 2', '"c", start = 4', 'elem = "c"', '"c", Foo = 1']:
        run("Find", B4, e)
    for e in ['Foo = 5', '"x", Item2 = "y"', 'item1 = 5', '"x", Foo = "y"']:
        run("Add", B4, e)
    for e in ['Foo = "a"', '"a", Foo = "b"', 'item1 = "a"']:
        run("Remove", B4, e)
        run("RemoveAll", B4, e)
    for e in ['2, Item2 = "x"', 'index = 2, "x"', '2, Foo = "x"']:
        run("Insert", B4, e)
    for e in ['Item1 = "x"', '2, 3, Item2 = "x"', 'start = 2, end = 3', '2, 3, Foo = "x"']:
        run("Splice", B4, e)
    for e in ['glue = "-"', '"-", start = 2', 'Foo = "-"']:
        run("Join", B4, e)
    for e in ['Index1 = 1, Foo = 2', 'index1 = 1, index2 = 2', 'Index2 = 4, Index1 = 1']:
        run("Swap", B4, e)

    # ================= arglist() with named entries =================
    for proc, e in [("Add", 'arglist(list("x" = 1, "y" = 2))'), ("Add", 'arglist(list(1, "Item1" = 5))'),
                    ("Copy", 'arglist(list("Start" = 2, "End" = 4))'), ("Copy", 'arglist(list(2, "End" = 3))'),
                    ("Cut", 'arglist(list("Start" = 2, "End" = 4))'), ("Cut", 'arglist(list("End" = 2))'),
                    ("Find", 'arglist(list("Elem" = "c", "Start" = 2))'), ("Find", 'arglist(list("c", "End" = 2))'),
                    ("Insert", 'arglist(list("Index" = 2, "Item1" = "x"))'), ("Insert", 'arglist(list(2, "x", "y"))'),
                    ("Splice", 'arglist(list(2, 3, "x", "y"))'), ("Splice", 'arglist(list("Start" = 2, "End" = 3))'),
                    ("Join", 'arglist(list("Glue" = "-", "End" = 3))'), ("Join", 'arglist(list("-", 2))'),
                    ("Swap", 'arglist(list("Index1" = 1, "Index2" = 4))'), ("Swap", 'arglist(list(1, 4))'),
                    ("Remove", 'arglist(list("a" = 1, "b" = 2))'), ("RemoveAll", 'arglist(list("Item1" = "a"))'),
                    ("Add", 'arglist(list())'), ("Copy", 'arglist(list())'), ("Find", 'arglist(list("b"))')]:
        run(proc, B4, e, tag=f"list.{proc}.arglist")

    # ================= null lists and dynamic dispatch =================
    s.body("list.dyn", ['var/list/L', 'var/r = "noerr"', 'try', '\tL.Add(1)', 'catch', '\tr = "ERR"'], 'list(r, L)')
    s.body("list.dyn", ['var/list/L', 'var/r = "noerr"', 'try', '\tr = L.Find(1)', 'catch', '\tr = "ERR"'], 'r')
    s.body("list.dyn", ['var/list/L', 'var/r = "noerr"', 'try', '\tr = L?.Add(1)', 'catch', '\tr = "ERR"'], 'list(r, L)')
    s.body("list.dyn", ['var/list/L', 'var/r = "noerr"', 'try', '\tr = L?.Copy()', 'catch', '\tr = "ERR"'], 'r')
    for call in ['L:Add(1)', 'L:Find("b")', 'L:Copy(2)', 'L:Cut(1, 2)', 'L:Join("-")', 'L:Insert(1, "z")',
                 'L:Swap(1, 2)', 'L:Remove("a")', 'L:Splice(1, 2, "z")', 'L:Foo()',
                 'call(L, "Add")(1, list(2))', 'call(L, "Find")("b")', 'call(L, "Copy")(2)', 'call(L, "Cut")(1, 2)',
                 'call(L, "Join")("-")', 'call(L, "Foo")()', 'hascall(L, "Add")', 'hascall(L, "Foo")',
                 'hascall(L, "add")', 'L?.Add(5)', 'L?.Find("b")']:
        s.body("list.dyn", ['var/list/L = list("a", "b")', 'var/r = "noerr"', 'try', f'\tr = {call}', 'catch',
                            '\tr = "ERR"'], 'list(list_show(r), list_show(L))')
    s.body("list.dyn", ['var/L = list("a", "b")', 'var/r = "noerr"', 'try', '\tr = L:Find("b")', 'catch',
                        '\tr = "ERR"'], 'r')
    s.body("list.dyn", ['var/alist/A = alist("a" = 1)', 'var/r = "noerr"', 'try', '\tr = A:Add("b")', 'catch',
                        '\tr = "ERR"'], 'list(r, list_asorted(A))')

    # ================= procs on sublists of 2D lists =================
    G = 'var/list/L = new /list(2, 2)'
    for lines, res in [
        (['L[1].Add(5)'], 'list_show(L)'),
        (['L[2].Cut()'], 'list_show(L)'),
        (['L[1].Insert(1, "x")'], 'list_show(L)'),
        (['L[1].Add(5)', 'L[2].Cut()', 'L[1].Insert(1, "x")'], 'list(list_show(L), L[1] != L[2])'),
        (['var/list/C = L.Copy()', 'C[1][1] = 9'], 'list(list_show(L), list_show(C), C[1] == L[1])'),
        (['var/list/C = L.Copy()', 'C[1] = 9'], 'list(list_show(L), list_show(C))'),
        (['var/list/A = L[1]', 'L.Swap(1, 2)'], 'list(list_show(L), L[2] == A)'),
        ([], 'list(L.Find(L[2]), L.Find(L[1]), L.Find(list(null, null)))'),
        (['L.Remove(L[1])'], 'list(L.len, list_show(L))'),
        ([], 'L.Join(",")'),
        (['L.Add(L[1])'], 'list(L.len, L[3] == L[1])'),
        (['L[1].Add(L[2])'], 'list_show(L)'),
        (['var/list/S = L[2]', 'S.Swap(1, 2)', 'S[1] = 1'], 'list_show(L)'),
        (['L.Cut(1, 2)'], 'list(L.len, length(L[1]))'),
    ]:
        s.body("list.2d", [G, 'var/r = "noerr"', 'try'] + ['\t' + l for l in lines] + ['catch', '\tr = "ERR"'],
               f'list(r, {res})')
    s.body("list.2d", ['var/L[2][3]', 'L[2].Add(7)', 'L[1].Cut(1, 2)'], 'list_show(L)')
    s.body("list.2d", ['var/list/L = new /list(2, 2, 2)', 'L[1][1].Add(5)'], 'list_show(L)')

    # ================= type-level list vars =================
    hold = ['var/datum/list_holder/X = new', 'var/datum/list_holder/Y = new']
    s.body("list.typevar", hold + ['X.M.Add(3)', 'X.L[1] = 1', 'X.G[1].Add(5)', 'X.A["b"] = 2', 'X.Q["z"] = 3'],
           'list(list_show(Y.M), list_show(Y.L), list_show(Y.G), list_show(Y.A), X.M == Y.M, X.G[1] == Y.G[1], '
           'length(Y.Q), list_asorted(X.Q))')
    s.body("list.typevar", hold, 'list(list_show(X.M), list_show(X.L), list_show(X.G), list_show(X.A), '
                                 'list_asorted(X.Q), X.G[1] == X.G[2])')
    s.body("list.typevar", hold, 'list(X.L.type, X.M.type, X.G.type, X.Q.type, istype(X.Q, /alist))')
    s.body("list.typevar", hold + ['X.M.Add(3)'], 'list(length(initial(X.M)), length(initial(X.L)))')
    s.body("list.typevar", hold + ['var/r = "noerr"', 'try', '\tr = initial(X.M) == X.M', 'catch', '\tr = "ERR"'], 'r')
    s.body("list.typevar", hold + ['X.M = null'], 'list(length(initial(X.M)), length(Y.M))')
    s.body("list.typevar", hold + ['var/list/V = X.vars["M"]', 'V.Cut()'], 'list(length(X.M), length(Y.M))')
    s.body("list.typevar", hold + ['X.L.len = 5', 'X.G[2].len = 0'],
           'list(length(Y.L), length(Y.G[2]), list_show(X.G))')
    s.body("list.typevar", hold, 'list(X.L.Find(null), X.M.Find(2), X.A.Find("a"), X.Q.Find("k"), X.G.Find(X.G[2]))')

    # ================= assoc lists: ranges, and past 64 items =================
    for e in ['"c", 2, 3', '"c", 4', '"c", 3, 4', '3, 1, 0', '"a", 2', '"d", 1, 4', '"d", -1', '1, 1, 0', 'null, 1, 0']:
        run("Find", ASSOC, e)
    for e in ['2, 4', '-2', '2, -1']:
        run("Copy", ASSOC, e)
        run("Join", ASSOC, f'",", {e}')
    BIG = ['var/list/L = list()', 'for(var/i in 1 to 100) L["k[i]"] = i']
    for lines, res in [
        ([], 'list(L.Find("k70"), L.Find(70), L.Find("k70", 71), L.Find("k70", 1, 70), L.Find("k70", 1, 71))'),
        (['var/r = L.Remove("k70")'], 'list(r, L.Find("k70"), L["k70"], L.len, L["k71"])'),
        (['var/r = L.RemoveAll("k1", "k2")'], 'list(r, L["k1"], L["k2"], L["k3"], L.len, L.Find("k1"))'),
        (['L.Cut(1, 50)'], 'list(L["k10"], L["k60"], L.len, L.Find("k10"), L.Find("k50"), L[1])'),
        (['L.Swap(1, 100)'], 'list(L[1], L[100], L["k1"], L["k100"], L.Find("k1"), L.Find("k100"))'),
        (['L.Insert(50, "new")'], 'list(L.Find("new"), L.Find("k50"), L["k50"], L["new"], L.len)'),
        (['L.Splice(10, 20, "s")'], 'list(L.Find("s"), L["k10"], L["k15"], L["k20"], L.Find("k20"), L.len)'),
        (['var/list/C = L.Copy(60, 70)'], 'list(C.len, C["k60"], C["k69"], C["k70"], C.Find("k65"))'),
        ([], 'length(L.Join(",", 90))'),
        (['L.Add("k5")'], 'list(L.len, L["k5"], L.Find("k5"))'),
        (['L.Remove("k5")', 'L.Add("k5")'], 'list(L.len, L["k5"], L.Find("k5"))'),
        (['L["k5"] = null'], 'list(L.len, L.Find("k5"), "k5" in L)'),
        (['L -= "k5"'], 'list(L.len, L.Find("k5"), "k5" in L, L["k5"])'),
    ]:
        s.body("list.assocbig", BIG + lines, res)

    # ================= special lists as list arguments (flattened?) =================
    s.body("list.flatspecial", ['var/datum/D = new', 'var/list/L = list()', 'L.Add(D.vars)'],
           'list(L.len == D.vars.len, L.Find("type") > 0, L["type"])')
    s.body("list.flatspecial", ['var/datum/D = new', 'var/list/L = list()', 'L.Insert(1, D.vars)'],
           'list(L.len == D.vars.len, L.Find("type") > 0, L["type"])')
    s.body("list.flatspecial", ['var/datum/D = new', 'var/list/L = list("type", "tag", "x")', 'var/r = L.Remove(D.vars)'],
           'list(r, list_show(L))')
    s.body("list.flatspecial", ['var/datum/D = new', 'var/list/L = list()', 'L += D.vars'],
           'list(L.len == D.vars.len, L["type"])')
    for lines, res in [
        (['L.Add(O.contents)'], 'list(length(L), L[1] == A)'),
        (['L.Add(O.contents)', 'var/r = L.Remove(O.contents)'], 'list(r, length(L))'),
        (['L.Insert(1, O.contents)'], 'list(length(L), length(L) && L[1] == A)'),
        (['L.Splice(1, 0, O.contents)'], 'list(length(L), length(L) && L[1] == A)'),
        (['L.Add(A)', 'var/r = L.RemoveAll(O.contents)'], 'list(r, length(L))'),
        (['O.overlays += "x"', 'L.Add(O.overlays)'], 'list(length(L), islist(L[1]), istext(L[1]))'),
        (['L.Add(O.verbs)'], 'length(L)'),
    ]:
        s.body("list.flatspecial", ['var/obj/O = parity_track(new /obj)', 'var/obj/A = parity_track(new /obj(O))',
                                    'var/list/L = list()'] + lines, res)

    # ================= Join of lists holding alists, Copy types =================
    s.body("list.jointype", ['var/list/L = list(alist("a" = 1), list(1))'], 'L.Join(",")')
    s.body("list.jointype", ['var/alist/A = alist("a" = 1)', 'var/r = "noerr"', 'try', '\tr = A.Join(",", 1, 2)',
                             'catch', '\tr = "ERR"'], 'r')
    s.body("list.jointype", ['var/datum/D = new'], 'D.vars.Copy().type')
    s.body("list.jointype", ['var/datum/D = new', 'var/list/C = D.vars.Copy()'], 'list(C.len == D.vars.len, C["type"])')
    s.body("list.jointype", ['var/obj/O = parity_track(new /obj)', 'O.overlays += "x"', 'var/list/C = O.overlays.Copy()'],
           'list(C.type, C.len)')
    s.body("list.jointype", ['var/obj/O = parity_track(new /obj)', 'var/list/C = O.contents.Copy()'], 'list(C.type, C.len)')
    s.body("list.jointype", ['var/alist/A = alist()'], 'A.Copy().type')
    s.body("list.jointype", ['var/alist/A = alist("a" = 1, "b" = 2)'], 'list(A.Copy(1, 2).type, A.Copy(2).type)')
    s.body("list.jointype", ['var/list/L = list(alist("a" = 1))', 'var/list/C = L.Copy()', 'var/alist/X = C[1]'],
           'X.type')
    s.body("list.jointype", ['var/list/L = list(new /list(2), alist(), list("a" = 1))'], 'L.Join("|")')
    s.body("list.jointype", ['var/datum/D = new', 'var/list/L = list(D.vars)'], 'L.Join("|")')

    # ================= new /list argument forms =================
    for a in ['2, Size = 3', 'Size = 3, 2', '3, list(1)', 'list(1), 3', '2, 1.5', '1.5, 2', '2, NAN', 'PINF, 0',
              '0, 0', '1, 0, 3']:
        s.body("new/list", ['var/r = "noerr"', 'try', f'\tr = new /list({a})', 'catch', '\tr = "ERR"'], 'list_show(r)')
    s.body("new/list", ['var/list/L = new /list(2, 2)', 'L.len = 3'], 'list(list_show(L), isnull(L[3]))')
    s.body("new/list", ['var/list/L = new /list(2, 3)'], 'list(L.len, length(L[1]), length(L[2]), L[1] != L[2])')
    s.body("new/list", ['var/list/L = new /list(2, 3, 4)'],
           'list(L.len, length(L[2]), length(L[2][3]), L[1][1] != L[2][1])')

    # ================= repeated items across Remove/RemoveAll arguments =================
    for e in ['list("a", "a")', 'list("a"), "a"', '"a", list("a")', 'list("a", "a", "a", "a")', '"a", "a", "a"',
              'list("a", "b", "a")']:
        run("Remove", 'list("a", "a", "a")', e)
        run("RemoveAll", 'list("a", "a", "a")', e)
    for e in ['"a", list("a"), "b"', 'list("a", "b"), list("b", "a")', '"b", "a", "b"']:
        run("Remove", 'list("a", "b")', e)
        run("RemoveAll", 'list("a", "b")', e)
    for e in ['"a", "a"', 'list("a"), "a"', '"a", "b"']:
        run("RemoveAll", 'list("a", "b", "a", "b", "a")', e)
