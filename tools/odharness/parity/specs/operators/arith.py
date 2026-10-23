"""Arithmetic operators: + - * / % %% **, unary - and +, ++/-- (pre/post) and the assignment forms
+= -= *= /= %= %%= **=.

BYOND reference points targeted here (info.html /operator/*):
- + - * / take "num or null (0)" on both sides; text + text concatenates; the result type "depends
  mostly on A". / "crashes if B is equivalent to 0".
- % truncates A and B to integers first ("for legacy reasons"); %% works on fractions and is
  documented as B * fract(A / B).
- ++A has the value A+1, A++ the value A; both add 1 to A (-- likewise).
- A #= B is shorthand for A = A # B; operator overloads: operator+ etc. on a datum, -A calls
  operator-() with no arguments, += falls back to + when no operator+= exists, and an operator+=
  that returns non-null replaces A. A++ calls operator++(1), ++A operator++().
- Operators of one precedence line group left to right; ** sits above * / % %%, unary above **.

OpenDream divergences these cases aim at (DMOpcodeHandlers.cs, DMCompiler Expressions/Binary.cs):
- Add: null + X returns X as is (any type, even a path or list); X + null returns X.
- Multiply / *= / ** / /=: a non-number right operand is silently treated as 0.
- Divide: null / X is 0 even for X = 0; /= never checks for zero (gives inf/nan, no error).
- Modulus: (int) cast of inf/nan/huge floats (C# gives int.MinValue); null as B is an error;
  x % 0 throws a .NET DivideByZeroException.
- %%: needs both operands to be numbers (null is an error); x %% 0 gives nan.
- ++/-- coerce every non-number (text, list, datum) to 0 without error.
- Negate: -X of any non-number is -0.
- Compiler constant folding (literal operands) uses C# float math: 1/0 folds to inf.
  NOTE: a literal "x % 0" (or a right side that truncates to 0, e.g. "5 % 0.5") makes OD's
  compiler do C# int % 0 and throw, so this spec keeps such cases runtime-only (arith_v()).
- ** is parsed right-associative in OD.

Operands go through arith_v() (an identity proc) so neither compiler can fold them; a separate,
smaller literal sweep covers constant folding.
"""
import re

from gen import dm_str

q = dm_str

OPS = [("add", "+"), ("sub", "-"), ("mul", "*"), ("div", "/"), ("mod", "%"), ("modmod", "%%"),
       ("pow", "**")]
# **= is not a DM operator: BYOND's parser stops at it ("missing left-hand argument to =") so it
# can't be covered without failing the whole file
ASSIGN = [(n + "_eq", o + "=") for n, o in OPS if o != "**"]

# Numbers: zero, signs, fractions, the float32 integer limit, tiny/huge, inf, nan
# (-7 and 1e-7 were dropped to keep the suite near 3000 cases; the hand-picked lists cover them)
NUMS = ["0", "1", "-1", "0.5", "-2.5", "16777217", "3e38", "PINF", "NINF", "NAN"]
# Values of every other kind (plus one number) for the type-mix sweep
KINDS = ["null", "1", q(""), q("abc"), q("5"), "list(1, 2)", "/datum", "new /datum",
         "new /datum/arith_op"]
# Assignment-form left and right sides
A_LHS = ["0", "5", "-2.5", "null", q("ab"), "PINF", "NAN", "list(1)", "new /datum/arith_op",
         "/datum"]
A_RHS = ["0", "2", "0.5", "null", q("c"), "NAN", "list(2)", "new /datum"]
# Literals for the constant-folding sweep (negatives get parentheses)
LITS = ["0", "1", "(-3)", "0.5", "(-2.5)", "16777217", "7"]
# Values for ++/--
INC = ["0", "-1", "2.5", "16777216", "-16777216", "16777215", "PINF", "NAN", "null", q("a"),
       q("5"), "list(1)", "/datum", "new /datum", "new /datum/arith_op"]


def v(x):
    return f"arith_v({x})"


HELPERS = r'''/proc/arith_v(x)
	return x

/proc/arith_s(x)
	if(isnull(x))
		return "null"
	if(islist(x))
		return "list"
	return "[x]"

/datum/arith_op
	var/v = 10
	var/last

/datum/arith_op/proc/operator+(b)
	return "op+ [arith_s(b)]"

/datum/arith_op/proc/operator-(b)
	if(!args.len)
		return "op-neg"
	return "op- [arith_s(b)]"

/datum/arith_op/proc/operator*(b)
	return "op* [arith_s(b)]"

/datum/arith_op/proc/operator/(b)
	return "op/ [arith_s(b)]"

/datum/arith_op/proc/operator%(b)
	return "op% [arith_s(b)]"

/datum/arith_op/proc/operator%%(b)
	return "op%% [arith_s(b)]"

/datum/arith_op/proc/operator**(b)
	return "op** [arith_s(b)]"

/datum/arith_op/proc/operator++(post)
	v += 1
	last = "++ [arith_s(post)]"

/datum/arith_op/proc/operator--(post)
	v -= 1
	last = "-- [arith_s(post)]"

// Only assignment overloads, returning null (A stays the same datum)
/datum/arith_acc
	var/v = 0
	var/last

/datum/arith_acc/proc/operator+=(b)
	v += 1
	last = "+= [arith_s(b)]"

/datum/arith_acc/proc/operator-=(b)
	v += 1
	last = "-= [arith_s(b)]"

/datum/arith_acc/proc/operator*=(b)
	v += 1
	last = "*= [arith_s(b)]"

/datum/arith_acc/proc/operator/=(b)
	v += 1
	last = "/= [arith_s(b)]"

/datum/arith_acc/proc/operator%=(b)
	v += 1
	last = "%= [arith_s(b)]"

/datum/arith_acc/proc/operator%%=(b)
	v += 1
	last = "%%= [arith_s(b)]"

// An assignment overload that returns a value: that value becomes the new A
/datum/arith_repl/proc/operator+=(b)
	return 99

/datum/arith_repl/proc/operator*=(b)
	return "repl"

// Both + and +=: += must win
/datum/arith_both
	var/last

/datum/arith_both/proc/operator+(b)
	return "plus"

/datum/arith_both/proc/operator+=(b)
	last = "pluseq"

/datum/arith_holder
	var/n = 5
	var/t = "x"
	var/z

/obj/arith_thing
	var/n = 1
'''


def build(s):
    s.dm(HELPERS)
    build2(s)

    # ---- numeric sweeps: every number pair, every operator, runtime evaluation ------------------
    for name, op in OPS:
        for a in NUMS:
            for b in NUMS:
                s.case(name, f"{v(a)} {op} {v(b)}")

    # ---- type mix: every kind on both sides -------------------------------------------------------
    for name, op in OPS:
        for a in KINDS:
            for b in KINDS:
                if a == "1" and b == "1":
                    continue
                s.case(name, f"{v(a)} {op} {v(b)}")
        # number on one side against inf/nan/text/null combos not in KINDS
        for b in ["PINF", "NAN", q("1e3"), "list()"]:
            s.case(name, f"{v('null')} {op} {v(b)}")
            s.case(name, f"{v(b)} {op} {v('null')}")

    # ---- constant folding: literal operands --------------------------------------------------------
    for name, op in OPS:
        for a in LITS:
            for b in LITS:
                # OD's compiler folds x % y with C# int %, which throws for a zero divisor
                if op == "%" and b in ("0", "0.5"):
                    continue
                s.case(name, f"{a} {op} {b}")
        # Literal null / text operands (the compilers may reject or fold these)
        for a, b in [("null", "1"), ("1", "null"), ("null", "null"), (q("a"), q("b")),
                     (q("a"), "1"), ("1", q("a")), (q("a"), "null"), ("null", q("a"))]:
            if op == "%" and b in ("null", q("a")):
                continue  # see above: a null/text divisor might be folded to int 0 too
            s.case(name, f"{a} {op} {b}")
    # Literal division by zero (BYOND may reject at compile time; OD folds to inf/nan)
    s.case("div", "1 / 0")
    s.case("div", "0 / 0")
    s.case("div", "-1 / 0")
    s.case("modmod", "5 %% 0")
    s.case("pow", "0 ** -1")

    # ---- unary minus / plus -------------------------------------------------------------------------
    for x in NUMS + KINDS + [q("-3"), "list()"]:
        s.case("neg", f"-{v(x)}")
    for x in ["0", "5", "(-0)", "0.5", "16777217", "null", q("7")]:
        s.case("neg", f"-{x}")
    s.case("neg", "-(-5)")
    s.case("neg", "- -5")
    s.case("neg", "-(0)")
    s.body("neg", ["var/z = 0", "z = -z"], "z")
    s.body("neg", ["var/z = 0", "z = -z"], '"[z]"')
    s.body("neg", ["var/z = 0", "z = -z"], "1 / z")
    s.body("neg", ["var/z = 0", "z = -z"], "z == 0")
    s.case("neg", '"[-0]"')
    s.case("neg", '"[-arith_v(0)]"')
    s.case("neg", '"[0 * -1]"')
    s.case("neg", '"[arith_v(0) * -1]"')
    s.case("neg", "-arith_v(new /datum/arith_op)")
    # Unary + is not DM syntax: BYOND's parser rejects it with a non-recoverable error that would
    # take the whole file down, so it is not covered here.

    # ---- ++ / -- pre and post, on a local --------------------------------------------------------
    for x in INC:
        for name, form in [("inc", "a++"), ("inc", "++a"), ("dec", "a--"), ("dec", "--a")]:
            s.body(name, [f"var/a = {x}", f"var/r = {form}"], "list(r, a)")
    # Overloaded ++/--: the argument, the datum's state and what the expression gives
    for form in ["a++", "++a", "a--", "--a"]:
        s.body("inc" if "+" in form else "dec",
               ["var/datum/arith_op/a = new", "var/datum/arith_op/o = a", f"var/r = {form}"],
               'list(arith_s(r), a == o, o.v, o.last)')
    # Repeated and combined forms
    s.body("inc", ["var/a = 0", "a++", "a++", "++a"], "a")
    s.body("inc", ["var/a = 1", "var/r = a++ + ++a"], "list(r, a)")
    s.body("inc", ["var/a = 1", "var/r = a++ * a++"], "list(r, a)")
    s.body("dec", ["var/a = 5", "var/r = --a - a--"], "list(r, a)")
    s.body("inc", ["var/a = 0", "var/r = -a++"], "list(r, a)")
    s.body("inc", ["var/a = 0", "var/r = - ++a"], "list(r, a)")
    s.body("inc", ["var/a = 16777215", "a++", "a++", "a++"], "a")
    s.body("dec", ["var/a = -16777215", "a--", "a--", "a--"], "a")
    s.body("inc", ["var/a = 0.1", "for(var/i in 1 to 10) a++"], "a")
    s.body("inc", ["var/a = 1e7", "a++"], "a")
    s.body("inc", ["var/a = 3e38", "a++"], "a")
    s.body("inc", ["var/a = 0", "for(var/i in 1 to 100) a += 0.1"], "a")
    s.body("inc", ["var/a = 0", "for(var/i in 1 to 100) a += 0.1"], "a == 10")
    # ++/-- on other kinds of lvalue
    s.body("inc", ["var/datum/arith_holder/h = new", "h.n++"], "h.n")
    s.body("inc", ["var/datum/arith_holder/h = new", "var/r = ++h.n"], "list(r, h.n)")
    s.body("inc", ["var/datum/arith_holder/h = new", "h.t++"], "h.t")
    s.body("inc", ["var/datum/arith_holder/h = new", "h.z++"], "h.z")
    s.body("dec", ["var/datum/arith_holder/h = new", "h.z--"], "h.z")
    s.body("inc", ["var/list/L = list(1, 2)", "L[1]++"], "L")
    s.body("inc", ["var/list/L = list(1, 2)", "var/r = ++L[2]"], "list(r, L)")
    s.body("dec", ["var/list/L = list(1, 2)", "var/r = L[2]--"], "list(r, L)")
    s.body("inc", ["var/list/L = list(1, 2)", "L[3]++"], "L")
    s.body("inc", ['var/list/L = list("k" = 1)', 'L["k"]++'], "L")
    s.body("inc", ["var/list/L = list()", 'L["k"]++'], "L")
    s.body("dec", ["var/list/L = list()", 'L["k"]--'], "L")
    s.body("inc", ['var/list/L = list("a")', "L[1]++"], "L")
    s.body("inc", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.n++", "o.pixel_x++"],
           "list(o.n, o.pixel_x)")
    s.body("inc", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.layer++"], "o.layer")
    s.body("dec", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.name--"], "o.name")
    s.body("inc", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.dir++"], "o.dir")
    s.body("inc", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.density++"], "o.density")

    # ---- assignment forms on a local --------------------------------------------------------------
    for name, op in ASSIGN:
        for a in A_LHS:
            for b in A_RHS:
                s.body(name, [f"var/a = {a}", f"a {op} {b}"], "a")
    # Values the assignment expression itself gives
    for name, op in ASSIGN:
        for a, b in [("5", "2"), ("null", "3"), (q("x"), q("y")), ("7", "0")]:
            if op in ("%=", "%%=", "/=") and b == q("y"):
                continue
            s.body(name, [f"var/a = {a}", f"var/r = (a {op} {b})"], "list(r, a)")
    # Runtime right sides (no literal the compiler could check)
    for name, op in ASSIGN:
        for a, b in [("10", "0"), ("10", "PINF"), ("10", "NAN"), ("PINF", "PINF"), ("0", "0"),
                     ("10", q("2")), ("-7", "3"), ("7.5", "-2")]:
            s.body(name, [f"var/a = {a}", f"a {op} arith_v({b})"], "a")
    # Overloads in assignment forms
    for name, op in ASSIGN:
        # Only the non-assignment overload: A becomes the operator's result
        s.body(name, ["var/datum/arith_op/a = new", "var/o = a", f"a {op} 2"], "list(arith_s(a), a == o)")
        # Only assignment overloads returning null: A stays the same datum
        s.body(name, ["var/datum/arith_acc/a = new", "var/datum/arith_acc/o = a", f"a {op} 2"], "list(a == o, o.v, o.last)")
        s.body(name, ["var/datum/arith_acc/a = new", "var/datum/arith_acc/o = a", f"var/r = (a {op} 2)"],
               "list(r == o, arith_s(r), o.last)")
        # A plain datum
        s.body(name, ["var/datum/a = new", f"a {op} 2"], "a")
    s.body("add_eq", ["var/a = new /datum/arith_repl", "a += 1"], "a")
    s.body("mul_eq", ["var/a = new /datum/arith_repl", "a *= 1"], "a")
    s.body("add_eq", ["var/a = new /datum/arith_repl", "var/r = (a += 1)"], "list(r, a)")
    s.body("sub_eq", ["var/datum/a = new /datum/arith_repl", "a -= 1"], "a")
    s.body("add_eq", ["var/datum/arith_both/a = new", "var/datum/arith_both/o = a", "a += 1"], "list(a == o, o.last)")
    s.body("add", ["var/datum/arith_both/a = new"], "a + 1")
    s.body("add", ["var/datum/arith_acc/a = new"], "a + 1")
    s.body("mul", ["var/datum/arith_acc/a = new"], "a * 2")
    # Overloads only apply on the left: number op datum
    for name, op in OPS:
        s.case(name, f"2 {op} {v('new /datum/arith_op')}")
    # Assignment forms on other lvalues
    for name, op in ASSIGN:
        s.body(name, ["var/datum/arith_holder/h = new", f"h.n {op} 2"], "h.n")
        s.body(name, ["var/datum/arith_holder/h = new", f"h.z {op} 2"], "h.z")
        s.body(name, ["var/list/L = list(10, 20)", f"L[2] {op} 3"], "L")
        s.body(name, ['var/list/L = list("k" = 9)', f'L["k"] {op} 2'], "L")
        s.body(name, ["var/list/L = list()", f'L["k"] {op} 2'], "L")
    s.body("add_eq", ["var/datum/arith_holder/h = new", 'h.t += "y"'], "h.t")
    s.body("add_eq", ["var/datum/arith_holder/h = new", 'h.z += "y"'], "h.z")
    s.body("add_eq", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", 'o.name += "!"'], "o.name")
    s.body("add_eq", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.pixel_x += 2.5"], "o.pixel_x")
    s.body("mul_eq", ["var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))", "o.layer *= 2"], "o.layer")
    # Chained (right to left)
    s.body("add_eq", ["var/a = 1", "var/b = 2", "a += b += 3"], "list(a, b)")
    s.body("mul_eq", ["var/a = 2", "var/b = 3", "a *= b -= 1"], "list(a, b)")
    s.body("add_eq", ["var/a = 1", "a += a += 1"], "a")
    # Text built up with +=
    s.body("add_eq", ['var/t = ""', "for(var/i in 1 to 5) t += \"[i]\""], "t")
    s.body("add_eq", ["var/t", 't += "a"', "t += null", 't += "b"'], "t")
    s.body("add_eq", ["var/t = null", "t += null"], "t")
    s.body("sub_eq", ["var/t = null", "t -= null"], "t")
    s.body("mul_eq", ["var/t = null", "t *= null"], "t")
    s.body("div_eq", ["var/t = null", "t /= null"], "t")
    s.body("mod_eq", ["var/t = null", "t %= null"], "t")
    s.body("modmod_eq", ["var/t = null", "t %%= null"], "t")

    # ---- hand-picked edges ----------------------------------------------------------------------
    hand = {
        "add": [
            # float32 precision and the 2^24 integer limit
            ("0.1", "0.2"), ("16777216", "1"), ("16777215", "1"), ("16777216", "2"), ("33554432", "1"),
            ("33554432", "3"), ("1e7", "0.5"), ("1e7", "0.25"), ("1e8", "1"), ("2147483647", "1"),
            ("3.4e38", "3.4e38"), ("-3.4e38", "-3.4e38"), ("1e-45", "0"), ("1e-38", "1e-38"),
            ("PINF", "NINF"), ("0.3", "-0.1"), ("1", "1e-8"), ("-0", "0"), ("-0", "-0"),
            # text concatenation
            (q("a"), q("b")), (q(""), q("")), (q("🙂"), q("x")), (q("é"), q("日本")),
            (q("1"), q("2")), (q("a\n"), q("b")), (q("a"), "null"), ("null", q("a")),
            (q("a"), "1"), ("1", q("a")), (q("a"), "PINF"), (q("a"), "list(\"b\")"),
            (q("a"), "/datum"), ("/datum", q("a")), ("/datum", "null"), ("null", "/datum"),
            ("/datum", "/obj"), ("null", "list(1)"),
        ],
        "sub": [
            ("0.3", "0.1"), ("16777217", "1"), ("16777216", "1"), ("1e7", "1e7"), ("1", "0.9"),
            ("PINF", "PINF"), ("0", "0"), ("-0", "0"), ("0", "-0"), (q("abc"), q("b")),
            (q("1"), "1"), ("1", q("1")), ("null", q("a")), (q("a"), "null"), ("list(1, 2)", "2"),
            ("/datum", "1"), ("1", "/datum"),
        ],
        "mul": [
            ("0.1", "3"), ("4096", "4097"), ("4096", "4096"), ("65536", "65536"), ("16777217", "1"),
            ("1e20", "1e20"), ("1e-30", "1e-30"), ("PINF", "0"), ("NINF", "-1"), ("-0", "5"), ("0", "-5"),
            ("1.1", "1.1"), (q("ab"), "3"), ("3", q("ab")), ("3", q("4")), ("null", q("a")),
            ("list(1)", "2"), ("2", "list(1)"), ("/datum", "2"), ("2", "/datum"), ("2", "new /datum"),
            ("null", "list()"),
        ],
        "div": [
            ("1", "3"), ("2", "3"), ("10", "4"), ("7", "-2"), ("-7", "2"), ("1", "0"), ("0", "0"),
            ("-1", "0"), ("1", "-0"), ("null", "0"), ("null", "null"), ("null", "2"), ("5", "null"),
            ("PINF", "PINF"), ("1", "PINF"), ("-1", "PINF"), ("1", "1e-40"), ("1e38", "1e-10"),
            ("16777217", "2"), ("16777216", "3"), ("1", "3e38"), ("NAN", "0"), ("PINF", "0"),
            (q("6"), "2"), ("6", q("2")), (q("a"), q("b")), ("6", "list()"), ("list(6)", "2"),
            ("/datum", "1"), ("6", "/datum"), ("6", "new /datum"),
        ],
        "mod": [
            ("7", "3"), ("-7", "3"), ("7", "-3"), ("-7", "-3"), ("7.9", "2.5"), ("-7.9", "2.5"),
            ("7", "2.9"), ("5", "0.5"), ("5", "0"), ("0", "0"), ("null", "3"), ("null", "0"),
            ("5", "null"), ("null", "null"), ("16777217", "2"), ("16777215", "2"), ("2147483647", "10"),
            ("2147483648", "10"), ("3e9", "7"), ("-3e9", "7"), ("1e10", "3"), ("1e20", "7"),
            ("5", "1e10"), ("PINF", "3"), ("NINF", "3"), ("NAN", "3"), ("5", "PINF"), ("5", "NAN"),
            ("0.9", "1"), ("-0.9", "1"), ("1", "0.9"), (q("7"), "3"), ("7", q("3")), ("list(7)", "3"),
            ("/datum", "3"), ("7", "new /datum"),
        ],
        "modmod": [
            ("7", "3"), ("-7", "3"), ("7", "-3"), ("-7", "-3"), ("7.5", "2"), ("-7.5", "2"),
            ("7.9", "2.5"), ("5", "0.5"), ("0.3", "0.1"), ("1", "0.1"), ("5", "0"), ("0", "0"),
            ("null", "3"), ("5", "null"), ("null", "null"), ("1e10", "3"), ("16777217", "2"),
            ("5", "1e10"), ("-5", "1e10"), ("PINF", "3"), ("5", "PINF"), ("-5", "PINF"), ("NAN", "3"),
            ("5", "NAN"), ("6", "3"), ("-6", "3"), ("1e-7", "1"), ("-1e-7", "1"), (q("7"), "3"),
            ("7", q("3")), ("list(7)", "3"), ("/datum", "3"),
        ],
        "pow": [
            ("2", "3"), ("2", "0.5"), ("4", "0.5"), ("2", "-1"), ("2", "-2"), ("0", "0"), ("0", "-1"),
            ("0", "-0.5"), ("-0", "-1"), ("-8", "1 / 3"), ("-2", "3"), ("-2", "2"), ("-2", "0.5"),
            ("-1", "PINF"), ("1", "PINF"), ("1", "NAN"), ("NAN", "0"), ("PINF", "0"), ("PINF", "-1"),
            ("NINF", "3"), ("NINF", "2"), ("0.5", "PINF"), ("2", "PINF"), ("2", "NINF"), ("2", "24"),
            ("2", "24.5"), ("2", "128"), ("2", "-149"), ("2", "-150"), ("10", "38"), ("10", "39"),
            ("10", "-38"), ("10", "-46"), ("3", "20"), ("1.0001", "10000"), ("16777217", "1"),
            ("null", "2"), ("null", "0"), ("2", "null"), ("null", "null"), (q("2"), "2"),
            ("2", q("2")), ("2", q("a")), ("list(2)", "2"), ("2", "list()"), ("/datum", "2"),
            ("2", "new /datum"),
        ],
    }
    for name, pairs in hand.items():
        op = dict(OPS)[name]
        for a, b in pairs:
            s.case(name, f"{v(a)} {op} {v(b)}")

    # Literal forms of the precision cases (compile-time folding vs runtime)
    for e in ["0.1 + 0.2", "16777216 + 1", "16777217", "16777217 - 1", "0.1 * 3", "1 / 3", "2 / 3",
              "1e7 + 0.5", "3.4e38 * 10", "1e-45", "1e-46", "2147483647", "2 ** 24 + 1", "2 ** 0.5",
              "(-8) ** (1 / 3)", "0 ** 0", "7.9 % 2.5", "-7 % 3", "-7 %% 3", "7.5 %% 2", "0.3 %% 0.1",
              "1e10 % 3", "3e9 % 7", "16777217 % 2"]:
        s.case("lit", e)

    # Precedence and associativity
    for e in ["-2 ** 2", "(-2) ** 2", "-(2 ** 2)", "2 ** 3 ** 2", "(2 ** 3) ** 2", "2 ** (3 ** 2)",
              "2 ** -1", "2 * 3 ** 2", "10 - 2 - 3", "100 / 10 / 5", "7 % 4 * 3", "2 * 7 % 4",
              "7 %% 4 * 3", "1 + 2 * 3", "(1 + 2) * 3", "8 / 2 * 4", "2 + 3 % 2", "10 - -2",
              "10 - - 2", "-3 % 2", "-3 %% 2", "1 - 2 + 3", "2 ** 2 * 3", "12 / 2 % 4",
              "\"a\" + \"b\" + \"c\"", "1 + 2 + \"x\""]:
        s.case("prec", e)
        # The same expression evaluated at run time
        s.case("prec", re.sub(r"(?<![\w.\"])(\d+(?:\.\d+)?)(?![\w.\"])", r"arith_v(\1)", e))

    # Mixed: results feeding further arithmetic, order of side effects
    s.body("add", ["var/list/L = list()", "var/r = arith_v(L) + 1"], "list(r, L)")
    s.body("add", ["var/list/L = list(1)", "var/r = arith_v(null) + L"], "list(r, r == L)")
    s.body("add", ["var/list/L = list(1)", "var/r = L + arith_v(null)"], "list(r, r == L)")
    s.body("sub", ["var/list/L = list(1)", "var/r = arith_v(null) - L"], "list(r, L)")
    s.body("add", ["var/datum/d = new", "var/r = arith_v(null) + d"], "r == d")
    s.body("add", ["var/datum/d = new", "var/r = d + arith_v(null)"], "r == d")
    s.body("add", ['var/r = arith_v(null) + arith_v("")'], 'list(r, istext(r))')
    s.body("add", ['var/r = arith_v("") + arith_v(null)'], 'list(r, istext(r))')
    s.body("add", ["var/r = arith_v(null) + arith_v(null)"], 'list(r, isnum(r), isnull(r))')
    s.body("sub", ["var/r = arith_v(null) - arith_v(null)"], 'list(r, isnum(r), isnull(r))')
    s.body("mul", ["var/r = arith_v(null) * arith_v(null)"], 'list(r, isnum(r), isnull(r))')
    s.body("pow", ["var/r = arith_v(null) ** arith_v(null)"], 'list(r, isnum(r), isnull(r))')
    s.body("neg", ["var/r = -arith_v(null)"], 'list(r, isnum(r), isnull(r))')
    s.body("add", ["var/r = arith_v(5) + arith_v(null)"], 'list(r, isnum(r))')
    # Errors stop evaluation: the statement after the failing operation never runs
    s.body("div", ["var/a = 1", "try", "\ta = arith_v(1) / arith_v(0)", "catch", "\ta = \"caught\""], "a")
    s.body("mod", ["var/a = 1", "try", "\ta = arith_v(1) % arith_v(0)", "catch", "\ta = \"caught\""], "a")
    s.body("div_eq", ["var/a = 1", "try", "\ta /= arith_v(0)", "catch", "\ta = \"caught\""], "a")
    s.body("mod_eq", ["var/a = 1", "try", "\ta %= arith_v(0)", "catch", "\ta = \"caught\""], "a")
    s.body("add", ["var/a = 1", "try", "\ta = arith_v(\"x\") + arith_v(1)", "catch", "\ta = \"caught\""], "a")
    # NaN behaviour after arithmetic
    s.body("sub", ["var/n = arith_v(PINF) - arith_v(PINF)"], "list(n == n, n != n, isnum(n), \"[n]\")")
    s.body("mul", ["var/n = arith_v(0) * arith_v(PINF)"], "list(n == n, \"[n]\")")
    s.body("div", ["var/n = arith_v(PINF) / arith_v(NINF)"], "list(n == n, \"[n]\")")
    # Display of results (text embedding of arithmetic results)
    for e in ["1 / 3", "2 / 3", "1e7 + 1", "16777216 + 1", "0.1 + 0.2", "100000 * 10", "999999 + 1",
              "1e6 - 1", "123456.7 * 1", "-1 / 3", "1 / 0.0001", "2 ** 31", "2 ** -20"]:
        rt = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?(?:e-?\d+)?)", r"arith_v(\1)", e)
        s.case("display", f'"[{rt}]"')



# ---- Helpers for the second pass (vectors, fallbacks, initializers, side effects) -----------------
HELPERS2 = r'''// Only operator+ (no +=, no ++)
/datum/arith_plus
	var/last

/datum/arith_plus/proc/operator+(b)
	last = "+ [arith_s(b)]"
	return "plus [arith_s(b)]"

// Only operator-= (for the -- fallback)
/datum/arith_minuseq
	var/last

/datum/arith_minuseq/proc/operator-=(b)
	last = "-= [arith_s(b)]"

// ++/-- overloads that return a value
/datum/arith_ret
	var/last

/datum/arith_ret/proc/operator++(post)
	last = "++ [arith_s(post)]"
	return 42

/datum/arith_ret/proc/operator--()
	last = "--"
	return "x"

// operator+ that returns nothing
/datum/arith_nullplus/proc/operator+(b)
	return

// An inherited overload calling the parent's
/datum/arith_op/kid/operator+(b)
	return "kid " + ..()

// An atom with an overload
/obj/arith_opobj/proc/operator+(b)
	return "obj+ [arith_s(b)]"

// operator- without an args.len check: unary minus calls it with no argument
/datum/arith_noargneg/proc/operator-(b)
	return "neg [arith_s(b)]"

// Text conversion overload
/datum/arith_str/proc/operator""()
	return "S"

// Var initializers folded by the compiler (and stored in OD's object JSON).
// 1/0, -1/0 and 0/0 are rejected by BYOND's compiler ("attempted division by zero") at the top
// level, and OD's compiler cannot write an infinite initial value to its JSON at all, so neither
// can be in a shared defs file.
/datum/arith_init
	var/k1 = 0.1 + 0.2
	var/k2 = 16777216 + 1
	var/k6 = 2 ** 0.5
	var/k7 = 3.4e38 * 10
	var/k8 = 7.9 % 2.5
	var/k9 = "a" + "b"
	var/k10 = 16777216 + 1 + 1
	var/k11 = 1 / 3 * 3
	var/k12 = -7 %% 3
	var/k13 = 0.1 * 3

var/const/arith_C = 16777217 - 1
var/global/arith_GI = 0.1 + 0.2
var/global/arith_g = 5
var/global/arith_calls = 0

/proc/arith_get(h)
	arith_calls++
	return h

/proc/arith_static()
	var/static/n = 0
	n += 2
	return n

/proc/arith_f(x)
	x += 1
	return x

/proc/arith_args(x)
	args[1] += 1
	return list(x, args[1])

/datum/arith_holder/proc/arith_bump()
	n += 1
	src.n *= 2
	return n
'''

_ecount = [0]


def _exc(s, name, expr):
    """Run expr inside try/catch and record the exception's name (or the value if none is thrown)."""
    _ecount[0] += 1
    e = f"arith_e{_ecount[0]}"
    s.body(name, ['var/r = "none"', "try", f"\tr = list(\"value\", {expr})", f"catch(var/exception/{e})",
                  f"\tr = list({e}.name, {e}.desc != null)"], "r")


def _rt(e):
    """The same expression with every number literal passed through arith_v() (no folding)."""
    return re.sub(r"(?<![\w.\"])(\d+(?:\.\d+)?(?:e-?\d+)?)(?![\w.\"])", r"arith_v(\1)", e)


def build2(s):
    s.dm(HELPERS2)
    OBJ = "var/obj/arith_thing/o = parity_track(new /obj/arith_thing(locate(1, 1, 1)))"

    # ---- vectors --------------------------------------------------------------------------------
    for e in ["vector(1, 2) + vector(3, 4)", "vector(1, 2, 3) - vector(1, 1)", "vector(1, 2) * vector(3, 4)",
              "vector(2, 4) * 3", "vector(2, 4) / 2", "vector(2, 4) / vector(2, 0)",
              "vector(7.9, -7.9) % vector(2.5, 2.5)", "vector(7.5, -7.5) %% 2", "vector(1, 2) %% vector(0.5, 0.3)",
              "-vector(1, 2)", "vector(1, 2) ** 2", "vector(1, 2) + 1", "vector(1, 2) + null",
              "null + vector(1, 2)", "2 * vector(1, 2)", "2 + vector(1, 2)", "vector(1, 2) - 1",
              "vector(2, 4) / 0", "vector(7, 9) % 4", "vector(1, 2) + vector(1, 2, 3)",
              "vector(1, 2) * vector(1, 2, 3)", "vector(1, 2) + \"a\"", "vector(1, 2) * null"]:
        s.case("vec", e)
    # The same through arith_v() on the left operand (no compile-time knowledge of the type)
    for e in ["vector(1, 2)) + vector(3, 4)", "vector(2, 4)) * 3", "vector(2, 4)) / 2", "vector(7, 9)) % 4",
              "vector(7.5, -7.5)) %% 2", "vector(1, 2)) + 1"]:
        s.case("vec", "arith_v(" + e)
    for op in ["+=", "-=", "*=", "/=", "%=", "%%="]:
        rhs = "vector(1, 1)" if op not in ("%=", "%%=") else "vector(2, 2)"
        s.body("vec_eq", ["var/v = vector(5, 7)", "var/w = v", f"v {op} {rhs}"], "list(v, w, v == w)")
        s.body("vec_eq", ["var/v = vector(5, 7)", "var/w = v", f"v {op} 2"], "list(v, w, v == w)")
    s.body("vec_eq", ["var/vector/v = vector(1, 2)", "v++"], "v")
    s.body("vec_eq", ["var/vector/v = vector(1, 2)", "v.x += 3", "v[2] *= 4"], "v")

    # ---- pixlocs and turfs ------------------------------------------------------------------------
    for e in ["locate(1, 1, 1) + vector(8, 0)", "pixloc(129, 129, 1) + vector(40, 0)",
              "pixloc(160, 160, 1) - pixloc(129, 129, 1)", "pixloc(140, 150, 1) % 32",
              "pixloc(140, 150, 1) %% 32", "vector(8, 0) + locate(1, 1, 1)", "pixloc(129, 129, 1) - vector(1, 1)",
              "locate(2, 2, 1) - vector(8, 8)", "pixloc(129, 129, 1) + 1", "locate(1, 1, 1) + 1",
              "pixloc(140, 150, 1) % vector(32, 10)", "pixloc(129, 129, 1) - locate(1, 1, 1)",
              "pixloc(129, 129, 1) * 2"]:
        s.case("pixloc", e)
    s.body("pixloc", ["var/p = pixloc(129, 129, 1)", "var/q = p", "p += vector(1, 0)"], "list(p, q, p == q)")
    s.body("pixloc", ["var/p = locate(1, 1, 1)", "p += vector(40, 0)"], "p")

    # ---- ++/-- fallbacks onto + / += overloads --------------------------------------------------
    for t in ["arith_acc", "arith_both", "arith_plus"]:
        for form in ["a++", "++a"]:
            s.body("inc", [f"var/datum/{t}/a = new", f"var/datum/{t}/o = a", f"var/r = {form}"],
                   "list(arith_s(r), a == o, o.last)")
    for form in ["a--", "--a"]:
        s.body("dec", ["var/datum/arith_minuseq/a = new", "var/datum/arith_minuseq/o = a", f"var/r = {form}"],
               "list(arith_s(r), a == o, o.last)")
        s.body("dec", ["var/datum/arith_acc/a = new", "var/datum/arith_acc/o = a", f"var/r = {form}"],
               "list(arith_s(r), a == o, o.last)")
    # Overloads returning a value
    for form in ["a++", "++a", "a--", "--a"]:
        s.body("inc" if "+" in form else "dec",
               ["var/datum/arith_ret/a = new", "var/datum/arith_ret/o = a", f"var/r = {form}"],
               "list(arith_s(r), arith_s(a), a == o, o.last)")

    # ---- overload fallbacks and inheritance --------------------------------------------------------
    s.body("add_eq", ["var/a = new /datum/arith_nullplus", "a += 1"], "a")
    s.body("add_eq", ["var/a = new /datum/arith_nullplus", "var/r = (a += 1)"], "list(r, a)")
    s.case("add", f"{v('new /datum/arith_nullplus')} + 1")
    s.case("add", f"{v('new /datum/arith_op/kid')} + 1")
    s.case("sub", f"{v('new /datum/arith_op/kid')} - 1")
    s.body("add_eq", ["var/a = new /datum/arith_op/kid", "a += 1"], "a")
    s.case("add", "parity_track(new /obj/arith_opobj(locate(1, 1, 1))) + 1")
    s.body("add_eq", ["var/a = parity_track(new /obj/arith_opobj(locate(1, 1, 1)))", "a += 2"], "a")
    s.body("sub_eq", ["var/datum/arith_plus/a = new", "a -= 1"], "a")
    s.body("add_eq", ["var/datum/arith_plus/a = new", "var/datum/arith_plus/o = a", "a += 1"], "list(a, o.last)")

    # ---- side effects in the target of compound assignment / ++ -------------------------------
    s.body("add_eq", ["var/i = 0", "var/list/L = list(1, 2, 3)", "L[++i] += 10"], "list(i, L)")
    s.body("inc", ["var/i = 1", "var/list/L = list(1, 2, 3)", "L[i++]++"], "list(i, L)")
    s.body("mul_eq", ["var/i = 1", "var/list/L = list(1, 2, 3)", "L[i++] *= 5"], "list(i, L)")
    s.body("add_eq", ["arith_calls = 0", "var/datum/arith_holder/h = new", "arith_get(h).n += 1"], "list(arith_calls, h.n)")
    s.body("inc", ["arith_calls = 0", "var/datum/arith_holder/h = new", "arith_get(h).n++"], "list(arith_calls, h.n)")
    s.body("inc", ["arith_calls = 0", "var/datum/arith_holder/h = new", "var/r = ++arith_get(h).n"],
           "list(r, arith_calls, h.n)")
    s.body("add_eq", ["arith_calls = 0", "var/list/L = list(1, 2)", "arith_get(L)[2] += 1"], "list(arith_calls, L)")
    s.body("add_eq", ["var/a = 1", "a += (a = 5)"], "a")
    s.body("mul_eq", ["var/a = 1", "a *= a++"], "a")
    s.body("mul_eq", ["var/a = 3", "a *= a++"], "a")
    s.body("add_eq", ["var/a = 2", "a += a++ + ++a"], "a")
    s.body("sub_eq", ["var/a = 10", "a -= --a"], "a")

    # ---- null += list / datum: aliasing ------------------------------------------------------------
    s.body("add_eq", ["var/a", "var/list/L = list(1)", "a += L", "L += 2"], "list(a, a == L)")
    s.body("add_eq", ["var/a", "var/datum/d = new", "a += d"], "a == d")
    s.body("add_eq", ["var/a", "a += /datum"], "a")
    s.body("sub_eq", ["var/a", "a -= list(1)"], "a")
    s.body("sub_eq", ["var/a", "var/list/L = list(1)", "a -= L"], "list(a, a == L)")
    s.body("add_eq", ["var/list/L = list(1)", "var/list/M = L", "L += 2"], "list(L, M, L == M)")
    s.body("add", ["var/list/L = list(1)", "var/list/M = L", "L = L + 2"], "list(L, M, L == M)")

    # ---- the exception arithmetic errors throw -----------------------------------------------------
    for e in ["arith_v(1) % arith_v(0)", "arith_v(1) / arith_v(0)", 'arith_v("x") + arith_v(1)',
              'arith_v("a") * arith_v(list())', "arith_v(null) % arith_v(null)", "arith_v(5) %% arith_v(null)",
              "arith_v(5) %% arith_v(0)", "-arith_v(new /datum/arith_plus)", "arith_v(new /datum) + arith_v(1)",
              'arith_v(1) - arith_v("a")', "arith_v(2) ** arith_v(list())"]:
        _exc(s, "exc", e)

    # ---- arithmetic in var initializers ------------------------------------------------------------
    for k in ["k1", "k2", "k6", "k7", "k8", "k9", "k10", "k11", "k12", "k13"]:
        s.body("init", ["var/datum/arith_init/d = new"], f'list(d.{k}, "[d.{k}]", d.{k} == d.{k}, d.{k} == initial(d.{k}))')
    s.case("init", 'list(arith_C, "[arith_C]", arith_C == 16777216, arith_C == 16777217)')
    s.case("init", 'list(arith_GI, "[arith_GI]", arith_GI == 0.1 + 0.2, arith_GI == arith_v(0.1) + arith_v(0.2))')
    s.body("init", ["var/datum/arith_init/d = new"], "d.k1 == arith_v(0.1) + arith_v(0.2)")
    s.body("init", ["var/datum/arith_init/d = new"], "d.k2 == arith_v(16777216) + arith_v(1)")

    # ---- chained constant folding vs runtime -------------------------------------------------------
    for e in ["16777216 + 1 + 1", "16777216 + (1 + 1)", "0.1 + 0.2 - 0.3", "1 / 3 * 3", "1e38 * 10 / 10",
              "3.4e38 + 3.4e38 - 3.4e38", "(2 ** 24 + 1) - 2 ** 24", "16777219", "16777218 + 1",
              "0.1 * 0.1 == 0.01", "0.1 + 0.2 == 0.3", "1 / 3 + 1 / 3 + 1 / 3",
              "16777217 * 1 == 16777216", "2 ** 0.5 * 2 ** 0.5"]:
        s.case("chain", e)
        s.case("chain", _rt(e))
    s.case("chain", "1e-45 * 0.5 * 2")
    s.case("chain", "arith_v(1e-45) * arith_v(0.5) * arith_v(2)")
    s.case("chain", '"[16777216 + 1 + 1]"')
    s.case("chain", '"[arith_v(16777216) + arith_v(1) + arith_v(1)]"')

    # ---- built-in atom vars changed with ++ and the assignment forms -------------------------------
    for lines, res in [
        (["o.alpha += 300"], "o.alpha"), (["o.alpha -= 300"], "o.alpha"),
        (["o.alpha = 255", "o.alpha++"], "o.alpha"), (["o.alpha *= 0.5"], "o.alpha"),
        (["o.invisibility += 200"], "o.invisibility"), (["o.luminosity -= 5"], "o.luminosity"),
        (["o.opacity++"], "o.opacity"), (["o.opacity += 5"], "o.opacity"),
        (["o.dir += 3"], "o.dir"), (["o.dir *= 3"], "o.dir"), (["o.dir--"], "o.dir"),
        (["o.step_x += 1.5"], "list(o.step_x, o.x)"), (["o.step_x += 40"], "list(o.step_x, o.x, o.loc)"),
        (["o.icon_state += 1"], "o.icon_state"), (['o.icon_state += "a"', 'o.icon_state += "b"'], "o.icon_state"),
        (["o.x++"], "list(o.x, o.y, o.loc)"), (["o.y += 2"], "list(o.x, o.y, o.loc)"),
        (["o.x--"], "list(o.x, o.y, o.loc)"), (["o.z += 5"], "list(o.x, o.y, o.z, o.loc)"),
        (["o.pixel_y = 17", "o.pixel_y %= 5"], "o.pixel_y"), (["o.pixel_y = 17.5", "o.pixel_y %%= 5"], "o.pixel_y"),
        (["o.layer -= 10"], "o.layer"), (["o.density -= 1"], "o.density"),
        (["o.pixel_x += 1e7"], "o.pixel_x"), (['o.name *= 2'], "o.name"),
    ]:
        s.body("atomvar", [OBJ] + lines, res)

    # ---- compound assignment on other variable kinds -----------------------------------------------
    s.body("add_eq", ["arith_g = 5", "arith_g += 2"], "arith_g")
    s.body("inc", ["arith_g = 5", "var/r = arith_g++"], "list(r, arith_g)")
    s.case("add_eq", "list(arith_static(), arith_static())")
    s.case("add_eq", "arith_f(1)")
    s.case("add_eq", "arith_f(null)")
    s.case("add_eq", 'arith_f("a")')
    s.case("add_eq", "arith_args(1)")
    s.body("add_eq", ["var/datum/arith_holder/h = new", "var/r = h.arith_bump()"], "list(r, h.n)")
    s.body("add_eq", ["var/list/L", "L[1] += 1"], "L")
    s.body("inc", ["var/list/L", "L[1]++"], "L")
    s.body("add_eq", ["var/list/L = list(1)", "L[0] += 1"], "L")
    s.body("inc", ["var/list/L = list(1)", "L[-1]++"], "L")
    s.body("add_eq", ["var/list/L = list(1)", "L[2] += 1"], "L")
    s.body("add_eq", ["var/datum/arith_holder/h", "h.n += 1"], "h")

    # ---- associative lists / alist with + - += -= --------------------------------------------------
    for e in ['list("a" = 1) + list("a" = 2)', 'list("a" = 1) + list("b" = 2)', 'list("a" = 1) - "a"',
              'list("a" = 1, "b" = 2) - list("a")', 'alist("a" = 1) + alist("b" = 2)', 'alist("a" = 1) + "c"',
              'alist("a" = 1) - "a"', 'alist("a" = 1) + list("a" = 9)', 'list("a" = 1) + alist("b" = 2)',
              'alist("a" = 1) * 2']:
        s.case("assoc", e)
    s.body("assoc", ['var/alist/A = alist("a" = 1)', 'A += alist("a" = 5)'], 'list(A, A["a"])')
    s.body("assoc", ['var/alist/A = alist("a" = 1)', 'A -= "a"'], "A")
    s.body("assoc", ['var/alist/A = alist("a" = 1)', 'A += "b"'], "A")
    s.body("assoc", ['var/list/L = list("a" = 1)', 'L += list("a" = 5)'], 'list(L, L["a"])')
    s.body("assoc", ['var/list/L = list("a" = 1)', 'L -= list("a" = 5)'], "L")

    # ---- unary minus: more overload forms -----------------------------------------------------------
    s.case("neg", f"-{v('new /datum/arith_noargneg')}")
    s.case("neg", f"-{v('new /datum/arith_plus')}")
    s.case("neg", f"- -{v('new /datum/arith_op')}")
    s.case("neg", f"1 - -{v('new /datum/arith_op')}")
    s.case("neg", f"-{v('new /datum/arith_op/kid')}")
    s.body("neg", ["var/datum/arith_holder/h = new"], "1 - -h.n")
    s.body("neg", ["var/list/L = list(3)"], "2 * -L[1]")
    s.body("neg", ["var/list/L = list(3)"], "-L[1] ** 2")
    s.case("neg", "-vector(0, 0)")
    s.case("neg", '"[-arith_v(1e-45)]"')

    # ---- icons and resources as operands ------------------------------------------------------------
    for e in ["'test.dmi' + \"#ff0000\"", "icon('test.dmi') * \"#80808080\"", "icon('test.dmi') - 1",
              "icon('test.dmi') - \"#101010\"", "icon('test.dmi') + icon('test.dmi')", "'test.dmi' * 2",
              "1 + 'test.dmi'", "\"a\" + 'test.dmi'", "'test.dmi' + \"a\"", "null + 'test.dmi'",
              "icon('small.dmi') + rgb(0, 0, 255)", "icon('test.dmi') / 2"]:
        s.case("icon", e)
    for op in ["+=", "-=", "*="]:
        s.body("icon", ["var/icon/I = icon('small.dmi')", "var/icon/J = I", f'I {op} "#00ff00"'], "list(I == J, I)")
    s.body("icon", ["var/I = 'small.dmi'", 'I += "#00ff00"'], "I")

    # ---- text concatenation edge inputs -------------------------------------------------------------
    for e in [f"{q('a')} + {v('new /datum/arith_str')}", f"{v('new /datum/arith_str')} + {q('a')}",
              f"{q('a')} + {v('NAN')}", f"{q('a')} + {v('NINF')}", f"{q('a')} + {v('16777217')}",
              f"{q('a')} + {v('0.1')}", f'"[{v("new /datum/arith_str")}]"']:
        s.case("text", e)
    s.body("text", ['var/t = "x"', "for(var/i in 1 to 16)", "\tt += t", "t = copytext(t, 2)", 't += "x"'],
           "list(length(t), copytext(t, -3))")
    s.body("text", ['var/t = "a"', 't += list("b")'], "t")
    s.body("text", ['var/t = "a"', "t += 1"], "t")
    s.body("text", ['var/t = "a"', "t -= 1"], "t")
    s.body("text", ["var/a = 1"], '"[a += 1][a]"')
    s.body("text", ["var/a = 0"], '"[a++][a]"')
    s.body("text", ["var/a = 0", 'var/t = "A++ = [a++]"', 't += "; ++A = [++a]"'], "t")
