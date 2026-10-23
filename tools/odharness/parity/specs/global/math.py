"""Global math builtins: abs sqrt sin cos tan arcsin arccos arctan log round floor ceil trunc fract sign
clamp min max lerp isnan isinf values_cut_over values_cut_under values_dot values_product values_sum
noise_hash, plus number literal forms.

BYOND ref (516): trig in degrees; arctan(x, y) is a polar angle -180..180 and 0 at (0,0); arctan takes a
vector; log(X, Y) is base X of Y, log(Y) natural; round(A) is floor (deprecated), round(A, B) nearest
multiple of B; floor/ceil/trunc/fract/round take numbers, pixlocs or vectors (fract keeps the sign);
sign(A) is -1/0/1 and takes vectors; clamp(Value, Low, High) takes num/text/pixloc/vector, null counts as
0, Low/High may be swapped, a list first argument is clamped IN PLACE and returned; min/max take any
count, a single argument is a list, nums/text/pixlocs/vectors or null but no mixing (null mixes with num
or text); lerp(A, B, factor) = A + (B-A)*factor for nums, vectors, matrices, turfs/pixlocs (same z);
isnan/isinf; values_cut_over/under(Alist, Max, inclusive=0) remove items whose value is over/under,
not a number, or NaN, return the count, and do nothing for a non-associative list; values_dot/product/
sum only use numeric associated values (product is 1 when none, sum 0 for non-assoc); noise_hash
hashes numbers (or a list of them, after an optional ignored hash name) to [0, 1).

OD details these cases aim at: sin..abs/sqrt/log/arctan are opcodes that read the raw float of any
value (text/list/datum act as 0, no runtime error), and are constant folded by OD's compiler when the
argument is a constant; floor/ceil/fract act on 0 for non-nums, fract(inf) is 0; round(A, B) uses
Math.Round(A/B, AwayFromZero)*B with B taken as 0 for non-nums; sign rejects != 1 args; clamp builds a
NEW list skipping non-numbers (BYOND: in place) and refuses text values; min/max compare with ordinal
string order, ties keep the later arg, a single non-list arg is returned as-is; lerp only does num,
vector and matrix (turfs throw NotImplemented); values_cut_* cut everything from a non-assoc list
and treat inclusive >= 1 as true; noise_hash is SHA256 of the "R" text forms, surely not BYOND's hash.
"""
from pools import NUM, OTHER

# Numbers for the one-argument procs: angles, logs, rounding edges, magnitudes, signed zero
M1_EXTRA = [
    "30", "45", "60", "90", "180", "270", "360", "-90", "720", "1/3", "-0", "0.1",
    "1e-30", "1e30", "3.4e38", "16777216", "0.707107", "-0.999", "1.0001", "2.5", "-2.5", "3.5",
    "-1.5", "0.49999997", "1e-45", "12345.678", "2.718282", "-1e7", "sqrt(3)",
]
# NUM minus a few redundant small integers
M1 = [n for n in NUM if n not in ("3", "5", "10", "-5", "2.9")] + M1_EXTRA
# Values of the wrong type
WRONG = OTHER + ['"a"', '"5"', '"-2.5"', "parity_track(new /obj)", "/obj", "matrix()"]
# Constant arguments, to exercise compile-time folding
LIT = ["0", "1", "-1", "0.5", "30", "90", "-0", "1e30", "null", '"a"', "list()", "/datum"]

P1 = ["abs", "sqrt", "sin", "cos", "tan", "arcsin", "arccos", "arctan", "log", "floor", "ceil",
      "trunc", "fract", "sign", "isnan", "isinf", "round"]

MATH_DM = """
/proc/math_v(x)
	return x

/proc/math_obj()
	return parity_track(new /obj(locate(1, 1, 1)))

/proc/math_o(list/O, x)
	O += x
	return x
"""

# Folded initializers: one datum per expression, so a compile error in one leaves the rest
MATH_INIT = {
    "a": "arcsin(2)", "b": "log(0)", "c": "sqrt(-1)", "d": "arctan(0, 0)", "e": "arccos(1.5)",
    "f": "log(-1)", "g": "log(2, 8)", "h": "abs(-5)", "t": 'sin("a")',
}


def rt(*args):
    """Arguments passed through a proc so nothing can be constant folded."""
    return ", ".join(f"math_v({a})" for a in args)


def name_of(e, fallback):
    head = e.split("(")[0]
    return head if "(" in e and head.isidentifier() else fallback


def build(s):
    s.dm(MATH_DM)

    # ---------- one-argument procs: runtime values and constants ----------
    for p in P1:
        for v in M1 + WRONG:
            s.case(p, f"{p}(math_v({v}))")
        for v in LIT:
            s.case(p, f"{p}({v})")
        # Arity, named argument, nesting
        s.case(p, f"{p}()")
        s.case(p, f"{p}(1, 2)")
        s.case(p, f"{p}(A = 2.5)")
        s.case(p, f"{p}({p}(math_v(0.5)))")

    # Documented examples and specific values
    for e in ["abs(1)", "abs(-1)", "abs(-0)", "abs(-PINF)", "abs(-NAN)", "abs(-16777217)",
              "sqrt(2)", "sqrt(4)", "sqrt(-1)", "sqrt(-0)", "sqrt(1e-45)", "sqrt(16777216)", "sqrt(PINF)",
              "sqrt(2) * sqrt(2)", "sqrt(math_v(-4)) == sqrt(math_v(-4))",
              "sin(0)", "sin(45)", "sin(90)", "sin(180)", "sin(360)", "sin(30)", "sin(-30)", "sin(1e7)",
              "cos(0)", "cos(45)", "cos(90)", "cos(180)", "cos(60)", "cos(270)", "cos(-60)",
              "tan(0)", "tan(45)", "tan(90)", "tan(-45)", "tan(135)", "tan(180)", "tan(270)", "tan(89.9)",
              "arcsin(0)", "arcsin(0.707107)", "arcsin(1)", "arcsin(-1)", "arcsin(0.5)", "arcsin(2)",
              "arcsin(-1.0000001)", "arccos(0)", "arccos(0.707107)", "arccos(1)", "arccos(-1)", "arccos(0.5)",
              "arccos(1.5)", "arctan(0)", "arctan(1)", "arctan(sqrt(3))", "arctan(-1)", "arctan(PINF)",
              "arctan(NINF)", "arctan(1e30)",
              "log(1)", "log(0)", "log(-1)", "log(2.718282)", "log(10)", "log(PINF)", "log(1e-45)",
              "log(10, 100)", "log(2, 8)", "log(2, 1024)", "log(10, 1000)", "log(10, 0.001)", "log(1, 5)",
              "log(0, 5)", "log(-2, 8)", "log(2, -8)", "log(0.5, 8)", "log(3, 81)",
              "10 ** log(10, 1000)", "2 ** log(2, 3)",
              "floor(1.45)", "floor(-1.45)", "floor(-0.5)", "floor(16777216.5)", "floor(-1e-45)",
              "ceil(1.45)", "ceil(-1.45)", "ceil(-0.5)", "ceil(1e-45)", "ceil(0.5)",
              "trunc(1.45)", "trunc(-1.45)", "trunc(-0.5)", "trunc(2.999999)",
              "fract(1.45)", "fract(-1.45)", "fract(-0.5)", "fract(1e7 + 0.5)", "fract(16777217)",
              "fract(PINF)", "fract(NINF)", "fract(NAN)", "fract(1e30)",
              "sign(20)", "sign(0)", "sign(-3)", "sign(-0)", "sign(1e-45)", "sign(-1e-45)", "sign(NAN)",
              "sign(PINF)", "sign(NINF)",
              "round(1.45)", "round(-1.45)", "round(1.45, 1.5)", "round(2.5, 1)", "round(-2.5, 1)",
              "round(3.5, 1)", "round(0.5, 1)", "round(-0.5, 1)", "round(1.25, 0.5)", "round(1.75, 0.5)",
              "round(7, 2)", "round(5, 2)", "round(-5, 2)", "round(0.15, 0.1)", "round(0.25, 0.1)",
              "round(123.456, 0.01)", "round(123.456, 10)", "round(123.456, -10)", "round(5, 0)",
              "round(0, 0)", "round(5, null)", "round(null, 1)", "round(5, PINF)", "round(5, NINF)",
              "round(PINF, 1)", "round(NAN, 1)", "round(5, NAN)", "round(1e7 + 0.5, 1)",
              "round(16777215.5, 1)", "round(A = 1.6, B = 1)", "round(B = 1, A = 2.5)", "round(1.6, B = 0.5)",
              "round(1, 2, 3)",
              "isnan(NAN)", "isnan(-NAN)", "isnan(PINF)", "isnan(0)", "isnan(null)", "isnan(\"nan\")",
              "isnan(PINF - PINF)", "isnan(PINF * 0)", "isnan(sqrt(-1))", "isnan(log(-1))", "isnan(arcsin(2))",
              "isnan(0 / 0)", "isnan(list(NAN))", "isnan(math_v(NAN), 1)",
              "isinf(PINF)", "isinf(NINF)", "isinf(NAN)", "isinf(1e38 * 10)", "isinf(3.4e38)", "isinf(\"inf\")",
              "isinf(log(0))", "isinf(1 / 0)", "isinf(tan(90))", "isinf(null)",
              "isnan(n = NAN)", "isinf(n = PINF)"]:
        s.case(name_of(e, "math_misc"), e)
    for e in ["NAN == NAN", "NAN != NAN", "NAN < 1", "NAN > 1", "NAN <= NAN"]:
        s.case("nan_cmp", e)

    # Vector and pixloc arguments
    for e in ["floor(vector(1.5, -1.5))", "ceil(vector(1.5, -1.5))", "trunc(vector(1.5, -1.5))",
              "fract(vector(1.5, -1.5))", "fract(vector(1.25, -2.75, 3.5))", "floor(vector(1.5, -1.5, 2.5))",
              "round(vector(1.4, 2.6))", "round(vector(1.45, 2.3), 0.5)", "round(vector(1.45, 2.3), vector(0.5, 1))",
              "round(vector(1.45, 2.3, 7.7), vector(0.5, 1, 5))", "sign(vector(-2, 0, 3))", "sign(vector(5, -0.1))",
              "abs(vector(-1, 2))", "sqrt(vector(4, 9))", "sin(vector(90, 0))", "arctan(vector(3, 4))",
              "arctan(vector(-1, 1))", "arctan(vector(0, -5, 7))", "arctan(vector(0, 0))", "isnan(vector(1, 2))",
              "floor(pixloc(33.5, 40.25, 1))", "fract(pixloc(33.5, 40.25, 1))", "round(pixloc(33.5, 40.25, 1), 2)",
              "ceil(pixloc(33.5, 40.25, 1))", "trunc(pixloc(33.5, 40.25, 1))", "sign(pixloc(33.5, 40.25, 1))",
              "round(vector(1.5, 2.5), vector(1, 1, 1))"]:
        s.case(e.split("(")[0] + "_vec", e)

    # ---------- arctan(x, y) ----------
    AT = ["0", "1", "-1", "4", "-5", "0.5", "PINF", "NINF", "NAN", "null", '"1"']
    s.sweep("arctan2", [AT, AT], fmt=lambda x, y: f"arctan({rt(x, y)})")
    for e in ["arctan(3, 4)", "arctan(-1, 1)", "arctan(0, -5)", "arctan(1, 0)", "arctan(0, 1)", "arctan(-1, 0)",
              "arctan(-1, -0)", "arctan(-0, -0)", "arctan(0, 0)", "arctan(-1, -1)", "arctan(1, -1)",
              "arctan(x = 3, y = 4)", "arctan(1, 2, 3)", "arctan(\"a\", 1)", "arctan(list(), 1)",
              "arctan(vector(3, 4), 1)"]:
        s.case("arctan2", e)

    # ---------- log(X, Y) ----------
    LB = ["2", "10", "0", "1", "-1", "0.5", "2.718282", "100", "PINF", "NAN", "null", '"2"']
    LV = ["0", "1", "2", "8", "100", "1000", "0.5", "-1", "PINF", "NAN", "null", "1e-7", '"8"']
    s.sweep("log2", [LB, LV], fmt=lambda x, y: f"log({rt(x, y)})")
    for e in ["log(X = 2, Y = 8)", "log(Y = 8)", "log(2, 8, 3)", "log(list(), 8)", "log(2, list())"]:
        s.case("log2", e)

    # ---------- round(A, B) ----------
    RA = ["0", "1.45", "-1.45", "2.5", "-2.5", "3.5", "1.25", "-7", "0.1+0.2", "1e7+0.5", "123.456",
          "PINF", "NAN", "null", '"3"']
    RB = ["1", "1.5", "0.5", "0.1", "10", "-1", "-2", "0", "0.25", "PINF", "NAN", "null", '"1"']
    s.sweep("round2", [RA, RB], fmt=lambda a, b: f"round({rt(a, b)})")

    # ---------- clamp ----------
    CV = ["0", "5", "-1", "20", "0.5", "null", "PINF", "NINF", "NAN", '"b"', "list()", "new /datum"]
    CL = ["0", "10", "-1", "null", "NAN", "PINF", '"a"', "list()"]
    CH = ["10", "0", "5", "null", "NAN", "NINF", '"c"', "/datum"]
    s.sweep("clamp", [CV, CL, CH], fmt=lambda v, l, h: f"clamp({rt(v, l, h)})")
    for e in ["clamp(5, 0, 10)", "clamp(-1, 0, 10)", "clamp(20, 0, 10)", "clamp(5, 10, 0)", "clamp(20, 10, 0)",
              "clamp(null, 1, 10)", "clamp(null, -10, -1)", "clamp(\"b\", \"a\", \"c\")", "clamp(\"z\", \"a\", \"c\")",
              "clamp(\"\", \"a\", \"c\")", "clamp(\"A\", \"a\", \"c\")", "clamp(null, \"a\", \"c\")", "clamp(\"b\", \"c\", \"a\")",
              "clamp(\"b\", 0, 10)", "clamp(5, \"a\", \"c\")", "clamp(5, 5, 5)", "clamp(NAN, 0, 10)",
              "clamp(5, NAN, 10)", "clamp(5, 0, NAN)", "clamp(PINF, 0, 10)", "clamp(5, null, null)",
              "clamp(Value = 15, Low = 0, High = 10)", "clamp(High = 1, Value = 15, Low = 0)", "clamp(5)", "clamp(5, 0)",
              "clamp(5, 0, 10, 20)", "clamp(vector(5, -5), 0, 1)", "clamp(vector(5, -5), vector(0, 0), vector(1, 1))",
              "clamp(vector(0.5, 2, -3), vector(0, 0, 0), vector(1, 1, 1))", "clamp(pixloc(100, 5, 1), 32, 64)",
              "clamp(1.5, 1, 2)", "clamp(-0, 0, 1)", "clamp(16777217, 0, 16777216)"]:
        s.case("clamp", e)
    # List form: modified in place (BYOND) and returned
    CLISTS = ["list(-5, 0, 5, 10, 15)", "list()", "list(1, \"a\", null, 20, list(), /datum)",
              "list(\"a\" = 50, \"b\" = -5)", "list(NAN, PINF, NINF, -0)", "list(0.5, 9.99, 10.01)",
              "list(vector(5, -5))", "alist(\"a\" = 50, \"b\" = 5)", "list(\"zz\", \"b\")"]
    for L in CLISTS:
        for lo, hi in [("0", "10"), ("10", "0"), ("null", "5"), ('"a"', '"c"')]:
            s.body("clamp_list", [f"var/list/L = {L}", f"var/R = clamp(L, {lo}, {hi})"], "list(R == L, L, R)")
    s.body("clamp_list", ["var/list/L = list(1, 20)", "var/list/C = L.Copy()", "clamp(C, 0, 10)"], "list(L, C)")
    s.body("clamp_list", ["var/list/L = list(1, 20)", "var/list/M = list(L)", "clamp(M, 0, 10)"], "list(L, M)")

    # ---------- min / max ----------
    MM = ["0", "1", "-1", "null", '""', '"a"', '"B"', '"abc"', "PINF", "NAN"]
    for p in ("min", "max"):
        s.sweep(p, [MM, MM], fmt=lambda a, b, p=p: f"{p}({rt(a, b)})")
        s.sweep(p, [MM[:6] + ["NAN"], MM[:6] + ['"a"'], ["2", "null", '"z"', "-2", "NAN"]],
                fmt=lambda a, b, c, p=p: f"{p}({rt(a, b, c)})")
        for v in MM + ["list()", "new /datum", "/datum", "vector(1, 2)"]:
            s.case(p, f"{p}(math_v({v}))")       # one argument that is not a list
        for e in ["(1, 2, 3)", "(3, 2, 1)", "(1, 1.0)", "(5)", "(\"a\")", "(null)", "()", "(null, null)",
                  "(0, null)", "(null, 0)", "(null, 1)", "(1, null)", "(null, -1)", "(-1, null)", "(null, \"a\")",
                  "(\"a\", null)", "(null, \"\")", "(\"\", null)", "(\"a\", \"B\")", "(\"abc\", \"abd\")", "(\"a\", \"A\")",
                  "(\"é\", \"z\")", "(\"日本\", \"z\")", "(\"\", \"a\")", "(\"a\", \"a\")", "(\"10\", \"9\")", "(\"b\", \"ab\")",
                  "(3, \"a\")", "(\"a\", 3)", "(1, \"1\")", "(new /datum, 1)", "(1, new /datum)", "(/datum, 1)",
                  "(/datum, /obj)", "(list(1, 2), 3)", "(3, list(1, 2))", "(list(3, 1), list(5))", "(NAN, 1)",
                  "(1, NAN)", "(NAN, NAN)", "(PINF, NAN)", "(NAN, NINF)", "(1, 2, NAN)", "(NAN, 2, 1)",
                  "(-0, 0)", "(0, -0)", "(16777216, 16777217)", "(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)",
                  "(list(1, 5, 3))", "(list())", "(list(\"a\", \"b\"))", "(list(\"b\", \"a\", \"C\"))",
                  "(list(1, \"a\"))", "(list(null, -1))", "(list(null, 1))", "(list(1, null))", "(list(null))",
                  "(list(list(1)))", "(list(\"a\" = 5, \"b\" = 1))", "(list(NAN, 1))",
                  "(list(1, NAN))", "(list(PINF, NINF))", "(list(new /datum))", "(list(/datum, /obj))",
                  "(list(3, 1, 2), 0)", "(alist(\"a\" = 1, \"b\" = 2))", "(vector(1, 5), vector(3, 2))",
                  "(vector(1, 5, 0), vector(3, 2, 9))", "(list(vector(1, 5), vector(3, 2)))", "(vector(1, 5), 3)",
                  "(pixloc(1, 50, 1), pixloc(40, 2, 1))", "(A = 5)", "(A = 5, 7)", "(\"a\", \"b\", null)"]:
            s.case(p, f"{p}{e}")
        # The list is not touched and the result is a copy of the value
        s.body(p, ["var/list/L = list(1, 9, 4)", f"var/x = {p}(L)", "L.Cut()"], "list(x, L)")

    # ---------- lerp ----------
    LA = ["0", "1", "-1", "10", "0.5", "null", "PINF", "NAN", '"a"']
    LBv = ["0", "5", "-10", "1", "null", "PINF", "NINF", '"b"', "list()"]
    LF = ["0", "1", "0.5", "0.25", "-1", "2", "null", "NAN", '"0.5"', "PINF"]
    s.sweep("lerp", [LA, LBv, LF], fmt=lambda a, b, f: f"lerp({rt(a, b, f)})")
    for e in ["lerp(1, 5, 0.25)", "lerp(1, 5, 0)", "lerp(1, 5, 1)", "lerp(1, 5, 1.5)", "lerp(1, 5, -0.5)",
              "lerp(5, 1, 0.25)", "lerp(0, 16777216, 0.5)", "lerp(1e30, -1e30, 0.5)", "lerp(PINF, PINF, 0.5)",
              "lerp(PINF, 1, 0)", "lerp(0, 1, 1/3)", "lerp(null, null, 0.5)", "lerp(A = 0, B = 10, factor = 0.3)",
              "lerp(0, 10)", "lerp(0)", "lerp(0, 10, 0.5, 1)",
              "lerp(vector(0, 0), vector(10, 20), 0.5)", "lerp(vector(0, 0, 0), vector(1, 1, 1), 0.25)",
              "lerp(vector(0, 0), vector(1, 1, 1), 0.5)", "lerp(vector(1, 2), vector(3, 4), 2)",
              "lerp(vector(1, 2), 5, 0.5)", "lerp(5, vector(1, 2), 0.5)",
              "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), 0.5)", "lerp(matrix(), matrix(1, 0, 10, 0, 1, 20), 0.5)",
              "lerp(matrix(), matrix(0, -1, 0, 1, 0, 0), 0.5)", "lerp(matrix(), matrix(-1, 0, 0, 0, -1, 0), 0.5)",
              "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), 0)", "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), 1)",
              "lerp(matrix(), 1, 0.5)",
              "lerp(locate(1, 1, 1), locate(3, 5, 1), 0.5)", "lerp(locate(1, 1, 1), locate(3, 5, 1), 0)",
              "lerp(locate(1, 1, 1), locate(3, 5, 1), 1)", "lerp(locate(2, 2, 1), locate(2, 2, 1), 0.5)",
              "lerp(pixloc(1, 1, 1), pixloc(65, 33, 1), 0.5)", "lerp(locate(1, 1, 1), pixloc(65, 33, 1), 0.5)",
              "lerp(math_obj(), locate(3, 3, 1), 0.5)", "lerp(list(1), list(2), 0.5)",
              "lerp(new /datum, new /datum, 0.5)", "lerp(\"a\", \"b\", 0.5)", "lerp(1, 2, list())"]:
        s.case("lerp", e)
    s.body("lerp", ["var/vector/A = vector(1, 2)", "var/vector/B = vector(3, 4)", "var/R = lerp(A, B, 0)"],
           "list(R == A, R, A)")
    s.body("lerp", ["var/matrix/A = matrix(2, 0, 0, 0, 2, 0)", "var/matrix/B = matrix()", "var/R = lerp(A, B, 0.5)"],
           "list(R == A, R, A, B)")

    # ---------- values_cut_over / values_cut_under ----------
    VL = ["list(\"a\" = 1, \"b\" = 2, \"c\" = -4)", "list()", "list(1, 2, 3)", "list(\"x\", \"a\" = 1, \"b\" = 5)",
          "list(\"a\" = \"x\", \"b\" = null, \"c\" = 3, \"d\" = list())", "list(\"a\" = NAN, \"b\" = 0, \"c\" = PINF, \"d\" = NINF)",
          "alist(a = 1, b = 5, c = 0)", "list(/datum = 0.5, /obj = 1.5)",
          "list(\"a\" = 0, \"b\" = -0, \"c\" = 1e-45)", "list(\"a\" = \"0\", \"b\" = vector(1, 2))"]
    for p in ("values_cut_over", "values_cut_under"):
        for L in VL:
            for args in ["0", "0, 1", "1", "1, 1"]:
                s.body(p, [f"var/list/L = {L}", f"var/n = {p}(L, {args})"], "list(n, L)")
        for args in ["0, 0", "0, 2", "0, 0.5", "0, 0.999", "0, -1", "0, \"yes\"", "0, null", "0, NAN", "0, PINF",
                     "NAN", "PINF", "NINF", "null", "\"a\"", "list()", "1, inclusive = 1",
                     "Max = 1" if p == "values_cut_over" else "Min = 1"]:
            s.body(p, ["var/list/L = list(\"a\" = 1, \"b\" = 2, \"c\" = -4, \"d\" = 0)", f"var/n = {p}(L, {args})"],
                   "list(n, L)")
        for arg in ["null", "new /datum", "\"abc\"", "5", "/datum"]:
            s.case(p, f"{p}({arg}, 0)")
        s.case(p, f"{p}(list(\"a\" = 1))")
        s.case(p, f"{p}(list(\"a\" = 1), 0, 1, 2)")
        s.case(p, f"{p}()")
        # Duplicate keys
        s.body(p, ["var/list/L = list(\"a\", \"b\", \"a\")", "L[\"a\"] = 5", "L[\"b\"] = -5", f"var/n = {p}(L, 0)"],
               "list(n, L)")

    # ---------- values_dot ----------
    DL = ["list(\"a\" = 1, \"b\" = 2, \"c\" = 3)", "list(\"b\" = 4, \"c\" = 5, \"d\" = 6)", "list()", "list(1, 2, 3)",
          "list(\"a\" = \"x\", \"b\" = null, \"c\" = 2)", "list(\"a\" = NAN, \"c\" = PINF)", "alist(a = 2, c = -1)",
          "list(\"x\", \"c\" = 10)", "null", "5"]
    s.sweep("values_dot", [DL, DL], fmt=lambda a, b: f"values_dot({a}, {b})")
    for e in ["values_dot(list(\"a\" = 1))", "values_dot()", "values_dot(list(\"a\" = 1), list(\"a\" = 1), list())",
              "values_dot(list(\"a\" = 0.1), list(\"a\" = 0.2))", "values_dot(list(\"a\" = 1e30), list(\"a\" = 1e30))",
              "values_dot(list(\"a\" = PINF), list(\"a\" = 0))", "values_dot(list(\"a\" = \"2\"), list(\"a\" = 3))",
              "values_dot(list(\"a\" = vector(1, 2)), list(\"a\" = vector(3, 4)))"]:
        s.case("values_dot", e)
    s.body("values_dot", ["var/list/L = list(\"a\" = 3, \"b\" = 4)"], "values_dot(L, L)")

    # ---------- values_product / values_sum ----------
    PL = ["list(\"foo\" = 3, \"bar\" = -4, \"banana\" = 5)", "list()", "list(2, 3)", "list(\"a\" = \"5\", \"b\" = 2)",
          "list(\"a\" = null, \"b\" = list())", "list(\"a\" = 0, \"b\" = 7)", "list(\"a\" = NAN, \"b\" = 1)",
          "list(\"a\" = PINF, \"b\" = NINF)", "list(\"a\" = PINF, \"b\" = 0)", "alist(a = 2, b = 3.5)",
          "list(/obj = 12, /datum = 1)", "list(\"x\", \"y\" = 4)", "list(\"a\" = vector(1, 2), \"b\" = 3)",
          "list(\"a\" = 0.1, \"b\" = 0.2, \"c\" = 0.3)", "list(\"a\" = 1e30, \"b\" = 1e30, \"c\" = 1e-30)",
          "list(\"a\" = 16777216, \"b\" = 1)", "list(\"a\" = TRUE)",
          "null", "new /datum", "5", "\"abc\""]
    for p in ("values_product", "values_sum"):
        for L in PL:
            s.case(p, f"{p}({L})")
            if L in PL[:4] or L in PL[-4:]:
                s.case(p, f"{p}(math_v({L}))")
        s.case(p, f"{p}()")
        s.case(p, f"{p}(list(\"a\" = 1), list(\"a\" = 2))")
        s.case(p, f"{p}(Alist = list(\"a\" = 3))")
        s.body(p, ["var/list/L = list(\"a\" = 2, \"b\" = 3)", f"var/n = {p}(L)"], "list(n, L)")

    # ---------- noise_hash ----------
    for e in ["noise_hash(1)", "noise_hash(0)", "noise_hash(-1)", "noise_hash(0.5)", "noise_hash(1e7)",
              "noise_hash(1, 2)", "noise_hash(2, 1)", "noise_hash(1, 2, 3, 4, 5)", "noise_hash(list(1, 2))",
              "noise_hash(\"x\", 1, 2)", "noise_hash(\"x\", list(1, 2))", "noise_hash(NAN)", "noise_hash(PINF)",
              "noise_hash()", "noise_hash(\"x\")", "noise_hash(null)", "noise_hash(list())", "noise_hash(-0)",
              "noise_hash(1, 2) == noise_hash(list(1, 2))", "noise_hash(1, 2) == noise_hash(\"x\", 1, 2)",
              "noise_hash(\"a\", 1) == noise_hash(\"b\", 1)", "noise_hash(1, 2) == noise_hash(2, 1)",
              "noise_hash(1) == noise_hash(1)", "noise_hash(1) == noise_hash(1, 0)", "noise_hash(0) == noise_hash(-0)",
              "noise_hash(1, \"a\", 2) == noise_hash(1, 2)", "noise_hash(1, null) == noise_hash(1)",
              "noise_hash(1, 2) == noise_hash(list(1), 2)", "noise_hash(list(1, \"a\", 2)) == noise_hash(1, 2)",
              "noise_hash(1, list(2, 3))"]:
        s.case("noise_hash", e)
    s.body("noise_hash", ["var/ok = 1", "for(var/i in -20 to 20)",
                          "\tvar/h = noise_hash(i, i * 0.37)", "\tif(!isnum(h) || h < 0 || h >= 1)", "\t\tok = 0"],
           "ok")
    s.body("noise_hash", ["var/list/seen = list()", "for(var/i in 1 to 50)", "\tseen[\"[noise_hash(i)]\"] = 1"],
           "seen.len > 45")

    # ---------- number literal forms ----------
    for e in ["0x1F", "0X1F", "0xff", "0xFF", "0x0", "0x7FFFFF", "0xFFFFFF", "0x1000000", "0x1000001",
              "0x7FFFFFFF", "0xFFFFFFFF", "0x100000000", "-0x10", "0x1F + 1", "0x10 * 0x10", "1e3", "1E3",
              "1e+3", "1e-3", "1.5e2", "1.5E-2", ".5", "5.", "0.5e1", "1e38", "1e39", "-1e39", "1e-45",
              "1e-46", "3.4028235e38", "16777217", "16777216.5", "0.1 + 0.2", "0.1 + 0.2 == 0.3", "010",
              "00", "-0", "1.#INF", "-1.#INF", "1.#IND", "1.#QNAN", "1.#INF == PINF", "isnan(1.#IND)",
              "1e1000", "123456789", "0.000001", "1e", "0x", "1e3 == 1000", "2e0", "0e5"]:
        s.case("literal", e)

    build_extra(s)


def build_extra(s):
    s.define("PARITY_MAXZ", 2)

    # ---------- named argument names from the ref ----------
    for e in ["sin(X = 30)", "cos(X = 60)", "tan(X = 45)", "arcsin(X = 0.5)", "arccos(X = 0.5)",
              "arctan(Num = 1)", "sin(X = math_v(30))", "arctan(Num = math_v(1))", "sqrt(A = 4)", "abs(A = -3)",
              "log(Y = math_v(8))", "log(X = math_v(2), Y = math_v(8))"]:
        s.case(name_of(e, "math_named"), e)

    # ---------- indirect calls of opcode builtins ----------
    for e in ['call(/proc/sin)(30)', 'call("sin")(30)', 'call(/proc/arctan)(3, 4)', 'call(/proc/arctan)(1)',
              'call(/proc/log)(2, 8)', 'call(/proc/log)(8)', 'call(/proc/sqrt)(16)', 'call(/proc/abs)(-2)',
              'call("abs")(-2)', 'call(/proc/cos)(60)', 'call(/proc/round)(1.45, 0.5)',
              'call(/proc/max)(1, 5, 3)', 'call("clamp")(15, 0, 10)',
              'sin(arglist(list(30)))', 'arctan(arglist(list(3, 4)))', 'arctan(arglist(list(1)))',
              'log(arglist(list(2, 8)))', 'log(arglist(list(8)))', 'sqrt(arglist(list(9)))', 'abs(arglist(list(-4)))',
              'max(arglist(list(1, 5, 3)))', 'min(arglist(list(4, 2, 3)))', 'clamp(arglist(list(15, 0, 10)))',
              'round(arglist(list(1.45, 0.5)))', 'lerp(arglist(list(0, 10, 0.5)))',
              'noise_hash(arglist(list(1, 2))) == noise_hash(1, 2)']:
        s.case("math_indirect", e)

    # ---------- one constant and one runtime operand ----------
    for e in ['arctan(3, math_v(4))', 'arctan(math_v(3), 4)', 'log(2, math_v(8))', 'log(math_v(2), 8)',
              'log(0, math_v(5))', 'log(math_v(-1), 8)', 'log("a", math_v(8))', 'log(math_v("a"), 8)',
              'log(10, math_v(0))', 'log(math_v(10), 0)', 'arctan(0, math_v(0))', 'arctan(math_v("a"), 1)']:
        s.case(e.split("(")[0] + "_mixed", e)

    # ---------- constant folding of text and other constants ----------
    for e in ['sin("30")', 'sqrt("4")', 'abs("-5")', 'log("10", 100)', 'log(10, "100")',
              'arctan("1", "1")', 'arcsin(-2)', 'arccos(-1.5)', 'cos("0")', 'tan("45")', 'log("5")',
              'arcsin("0.5")', 'sqrt(-4)', 'log(-5)', 'arctan(0, -0)']:
        s.case(e.split("(")[0] + "_fold", e)
    for stmt, res in [("var/const/C = 2", "arcsin(C)"), ("var/const/C = 2", "log(C)"),
                      ("var/const/C = 2", "sqrt(-C)"), ("var/const/C = 0", "log(C)"),
                      ("var/const/C = 2", "arccos(C)"), ("var/const/C = 2", "log(C, 8)"),
                      ("var/const/C = 0", "arctan(C, C)"), ('var/const/C = "a"', "sin(C)"),
                      ("var/const/C = -1", "log(C)"), ("var/const/C = 30", "sin(C)")]:
        s.body(res.split("(")[0] + "_const", [stmt], res)

    # ---------- folding in var initializers ----------
    for k, expr in MATH_INIT.items():
        s.dm(f"/datum/math_init_{k}\n\tvar/v = {expr}\n")
        s.body("math_init", [f"var/datum/math_init_{k}/D = new"], "list(D.v, initial(D.v))",
               display=f"/datum/math_init_{k}.v = {expr}")

    # ---------- argument evaluation order ----------
    for call in ["log(math_o(O, 2), math_o(O, 8))", "arctan(math_o(O, 2), math_o(O, 8))",
                 "round(math_o(O, 2), math_o(O, 8))", "clamp(math_o(O, 2), math_o(O, 8), math_o(O, 10))",
                 "max(math_o(O, 2), math_o(O, 8))", "lerp(math_o(O, 2), math_o(O, 8), math_o(O, 0.5))"]:
        s.body(call.split("(")[0] + "_order", ["var/list/O = list()", f"var/r = {call}"], "list(r, O)")

    # ---------- vector results are new objects ----------
    for stmt in ["var/vector/R = max(V, vector(1, 1))", "var/vector/R = min(V, vector(9, 9))",
                 "var/vector/R = max(list(V))", "var/vector/R = clamp(V, 0, 10)", "var/vector/R = round(V, 1)",
                 "var/vector/R = floor(V)", "var/vector/R = sign(V)", "var/vector/R = max(V)",
                 "var/vector/R = ceil(V)", "var/vector/R = trunc(V)", "var/vector/R = fract(V)",
                 "var/vector/R = abs(V)"]:
        s.body("math_vec_new", ["var/vector/V = vector(5, 5)", stmt, "if(istype(R))", "\tR.x = 99"],
               "list(V, R, R == V)")
    s.body("math_vec_new", ["var/pixloc/V = pixloc(5, 5, 1)", "var/pixloc/R = max(V, pixloc(1, 1, 1))",
                            "if(istype(R))", "\tR.x = 99"], "list(V, R, R == V)")
    s.body("math_vec_new", ["var/pixloc/V = pixloc(40, 40, 1)", "var/pixloc/R = clamp(V, 0, 100)",
                            "if(istype(R))", "\tR.x = 99"], "list(V, R, R == V)")

    # ---------- round(pixloc, vector) ----------
    for e in ["round(pixloc(33.5, 40.25, 1), vector(2, 5))", "round(pixloc(33.5, 40.25, 1), vector(2, 5, 3))",
              "round(pixloc(33.5, 40.25, 1), pixloc(2, 5, 1))", "round(pixloc(33.5, 40.25, 1))",
              "round(pixloc(33.5, 40.25, 1), 0)", "round(vector(33.5, 40.25), pixloc(2, 5, 1))"]:
        s.case("round_vec", e)

    # ---------- clamp with pixloc/vector bounds and mixed kinds ----------
    for e in ["clamp(pixloc(100, 5, 1), pixloc(32, 32, 1), pixloc(64, 64, 1))",
              "clamp(pixloc(100, 5, 1), vector(32, 32), vector(64, 64))", 'clamp(vector(5, -5), "a", "c")',
              "clamp(vector(5, -5), vector(1, 1), 3)", "clamp(vector(5, -5), null, null)",
              "clamp(vector(5, -5, 2), vector(0, 0), vector(1, 1))", "clamp(pixloc(100, 5, 1), 64, 32)",
              "clamp(vector(5, -5), vector(1, 1), vector(0, 0))"]:
        s.case("clamp_vec", e)
    for L, lo, hi in [('list("b", "z", 5)', '"a"', '"c"'), ("list(vector(5, -5))", "vector(0, 0)", "vector(1, 1)"),
                      ("list(pixloc(100, 5, 1))", "32", "64"), ('list("b", null, 5)', "0", "10")]:
        s.body("clamp_list", [f"var/list/L = {L}", f"var/R = clamp(L, {lo}, {hi})"], "list(R == L, L, R)")

    # ---------- min/max mixing kinds, named args ----------
    for p in ("min", "max"):
        for args in ["vector(1, 2), pixloc(1, 1, 1)", "pixloc(1, 1, 1), vector(1, 2)",
                     "vector(1, 5), vector(3, 2), vector(2, 9)", "vector(1, 2), null", "null, vector(1, 2)",
                     "list(vector(1, 2), null)", 'vector(1, 2), "a"', "pixloc(1, 50, 1), pixloc(40, 2, 1), pixloc(9, 9, 1)",
                     "vector(1, 2), vector(1, 2, 3)", "B = 5", "1, B = 5", "X = 1, Y = 2", "1, 9, C = 5"]:
            s.case(p + "_mix", f"{p}({args})")

    # ---------- lerp across z, matrix factors, turf results ----------
    for e in ["lerp(locate(1, 1, 1), locate(3, 3, 2), 0.5)", "lerp(pixloc(1, 1, 1), pixloc(65, 33, 2), 0.5)",
              "lerp(locate(1, 1, 1), locate(3, 3, 2), 0)", "lerp(locate(1, 1, 1), locate(3, 3, 2), 1)",
              "lerp(locate(2, 2, 2), locate(4, 4, 2), 0.5)",
              "lerp(matrix(), matrix(0, -1, 0, 1, 0, 0), 2)", "lerp(matrix(), matrix(0, -1, 0, 1, 0, 0), -1)",
              "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), 0.25)", "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), null)",
              "lerp(matrix(1, 2, 3, 4, 5, 6), matrix(), 0.5)", "lerp(matrix(), matrix(2, 0, 0, 0, 2, 0), 2)",
              "lerp(matrix(), matrix(1, 0, 10, 0, 1, 20), -0.5)",
              "lerp(locate(1, 1, 1), locate(2, 2, 1), 0.3)", "lerp(locate(1, 1, 1), locate(3, 5, 1), 1.5)",
              "lerp(locate(1, 1, 1), locate(3, 5, 1), -1)"]:
        s.case("lerp_ext", e)
    s.body("lerp_ext", ["var/R = lerp(locate(1, 1, 1), locate(2, 2, 1), 0.3)"],
           "list(isturf(R), istype(R, /pixloc), R)")

    # ---------- noise_hash ----------
    # A datum hashes by something allocation-dependent: only check the range
    s.body("noise_hash", ["var/h = noise_hash(new /datum)"], "list(isnum(h), isnum(h) && h >= 0 && h < 1)")
    for e in ["noise_hash(vector(1, 2))", "noise_hash(list(list(1, 2)))", 'noise_hash(list("x", 1, 2)) == noise_hash(1, 2)',
              'noise_hash(1, 2, "x")', 'noise_hash(1, 2, "x") == noise_hash(1, 2)',
              "noise_hash(16777216) == noise_hash(16777217)", "noise_hash(1e-45)", "noise_hash(NINF)",
              "noise_hash(1e-45) == noise_hash(0)", "noise_hash(vector(1, 2)) == noise_hash(1, 2)"]:
        s.case("noise_hash", e)

    # ---------- values_cut_* stress ----------
    for p in ("values_cut_over", "values_cut_under"):
        lim = "0" if p == "values_cut_over" else "10"
        s.body(p, ['var/list/L = list("a" = 5, "b" = 6, "c" = 7)', f"var/n = {p}(L, {lim})"], "list(n, L)")
        s.body(p, ['var/list/L = list("a" = 1, "a" = 5)', f"var/n = {p}(L, 0)"], "list(n, L)")
        s.body(p, ['var/list/L = list("k", "a" = 5, "m", "b" = 6)', f"var/n = {p}(L, {lim})"], "list(n, L)")
        s.body(p, ["var/list/L = list()", "L.len = 1", "L[1] = 5", f"var/n = {p}(L, 0)"], "list(n, L)")
        s.body(p, ["var/list/L = list(1, 2)", "L[1] = 5", f"var/n = {p}(L, 0)"], "list(n, L)")

    # ---------- values_sum/product/dot with duplicate keys and mixed kinds ----------
    for res in ["values_sum(L)", "values_product(L)", "values_dot(L, L)", "list(values_sum(L), L)"]:
        s.body(res.split("(")[0].replace("list", "values_sum") + "_dup",
               ['var/list/L = list("a", "b", "a")', 'L["a"] = 5'], res)
    for e in ['values_dot(alist(a = 2), list("a" = 3))', 'values_dot(list("a" = 3), alist(a = 2))',
              "values_sum(alist(1 = 2, 2 = 3))", "values_product(alist(1 = 2, 2 = 3))",
              "values_sum(list(1 = 2, 2 = 3))", 'values_sum(list("a" = 1, "a" = 5))']:
        s.case(e.split("(")[0] + "_mix", e)

    # ---------- more number literal forms ----------
    for e in ["1e+38", "1E-0", "0x1e3", "0xA.8", "-1.#IND", "1.#SNAN", "1#INF", "0.5e-1", "0x1E3", "0xe",
              "0x1e+3", "1e-0 == 1", "0xAbC"]:
        s.case("literal", e)
    s.body("literal", ["var/const/C = 1.#INF"], "C")
    s.body("literal", ["var/const/C = -1.#INF"], "list(C, isinf(C))")
