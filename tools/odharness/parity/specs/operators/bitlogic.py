"""Bitwise, logical, comparison, equivalence, conditional-access and `in` operators.

BYOND reference points targeted here (info.html /operator/*):
- & | ^ ~ << >>: "A and B must be between 0 and 2**24 - 1, giving an effective width of 24 bits";
  shifted bits past the low 24 are lost. & | ^ on lists are intersection/union/symmetric
  difference (order of A first, then extra items of B); &= |= ^= change the list in place.
  ~ on a /matrix is its inverse. & and | on icons blend (a couple of cases only).
- && / || return the deciding operand, not 1/0, and short-circuit; &&= / ||= evaluate the left
  side once and skip the right side when not needed. ! gives 1/0.
- ?: (ternary) evaluates only the chosen branch. ?. / ?: (access) skip the access, the call and
  the right side of an assignment when the object is null; ?[] does the same for list indexes.
- ~= / ~!: lists are equivalent when their contents are equal (shallow; 516+ also compares
  associated values), matrices when components are equal, datums only via operator~= or identity.
- == / != / <>: plain equality. < > <= >= <=>: numbers, or text compared case-sensitively like
  sorttextEx(); NaN makes <=> "0 but ambiguous".
- in: list membership (List may be a non-list such as null), atom == atom.contents; low precedence
  (below ! and assignment). Ranges: `X in A to B [step S]`, and switch if(A to B).
- Overloads: operator& | ^ ~ << >> ~= < > (with fallbacks ~! from ~=, >= from <, <= from >) and
  the assign forms (|= with a null return keeps A; &= falls back to A = A & B).

OpenDream divergences these cases aim at (DMOpcodeHandlers.cs, DreamList.cs, DreamObjectMatrix.cs,
DMCompiler Binary.cs / SharedOperations.cs):
- & | ^ use (int) casts with no 24-bit mask; only << and ~ mask. C# shift counts are mod 32
  (1 << 32 == 1, negative counts), (int)NaN / (int)inf are int.MinValue.
- Constant folding in the compiler uses its own code paths (literal operands vs runtime operands
  are both tested; bitlogic_v() hides a value from the folder).
- `null | x` returns x unchanged (even text/list); `x ^ null`, `null ^ null` -> null.
- < > <= >= return the LEFT operand when the right operand is a list/datum/path; a datum on the
  left throws without trying operator< overloads. Text order is UTF-16 ordinal, BYOND's is bytes.
- `in` ranges ignore step and never match a reversed (5 to 1) range; non-numbers become 0.
- Matrix ~= uses float.Equals (NaN equals NaN); ~ on a matrix is NotImplemented.
"""
from pools import TEXT_S, NUM_S, OTHER
from gen import dm_str

q = dm_str

HELPERS = r'''
var/global/list/bitlogic_calls = list()

/proc/bitlogic_v(x)
	return x

/proc/bitlogic_t(x)
	bitlogic_calls += list(x)
	return x

/proc/bitlogic_log()
	var/list/parts = list()
	for(var/x in bitlogic_calls)
		parts += parity_canon(x)
	bitlogic_calls = list()
	return jointext(parts, ",")

/proc/bitlogic_mk(v)
	bitlogic_calls += list("mk")
	var/datum/bitlogic_d/D = new
	D.v = v
	return D

/proc/bitlogic_null()
	bitlogic_calls += list("null")
	return null

/datum/bitlogic_d
	var/v = 5
	var/datum/bitlogic_d/next
	var/list/items

/datum/bitlogic_d/proc/f(x)
	return v * 2 + (isnum(x) ? x : 0)

/datum/bitlogic_ov
	var/v = 3

/datum/bitlogic_ov/proc/operator&(b)
	return "and [b]"

/datum/bitlogic_ov/proc/operator|(b)
	return "or [b]"

/datum/bitlogic_ov/proc/operator^(b)
	return "xor [b]"

/datum/bitlogic_ov/proc/operator~()
	return "not [v]"

/datum/bitlogic_ov/proc/operator<<(b)
	return "shl [b]"

/datum/bitlogic_ov/proc/operator>>(b)
	return "shr [b]"

/datum/bitlogic_ov/proc/operator~=(b)
	return isnum(b) && b == v

/datum/bitlogic_ov/proc/operator<(b)
	return isnum(b) && v < b

/datum/bitlogic_ov/proc/operator>(b)
	return isnum(b) && v > b

/datum/bitlogic_ov/proc/operator|=(b)
	v |= b

/datum/bitlogic_ova
	var/v = 6

/datum/bitlogic_ova/proc/operator&(b)
	return v & b

/datum/bitlogic_ova/proc/operator<=>(b)
	return v - b

/proc/bitlogic_sw(x)
	switch(x)
		if(1 to 3)
			return "1-3"
		if(4.5 to 6)
			return "4.5-6"
		if(10)
			return "10"
		if(-5 to -1)
			return "neg"
		else
			return "else"

/obj/bitlogic_box
	name = "box"

/obj/bitlogic_box/verb/poke()
	set src in view()
	return

// Comparison fallbacks: only one operator of each opposing pair
/datum/bitlogic_ne
	var/v = 3

/datum/bitlogic_ne/proc/operator~!(b)
	return !(isnum(b) && b == v)

/datum/bitlogic_ge
	var/v = 3

/datum/bitlogic_ge/proc/operator>=(b)
	return isnum(b) && v >= b

/datum/bitlogic_le
	var/v = 3

/datum/bitlogic_le/proc/operator<=(b)
	return isnum(b) && v <= b

// Explicit assignment overloads (no return: A stays src) next to the plain ones
/datum/bitlogic_asg
	var/v = 3

/datum/bitlogic_asg/proc/operator&(b)
	return "and [b]"

/datum/bitlogic_asg/proc/operator&=(b)
	v &= b

/datum/bitlogic_asg/proc/operator^(b)
	return "xor [b]"

/datum/bitlogic_asg/proc/operator^=(b)
	v ^= b

/datum/bitlogic_asg/proc/operator<<(b)
	return "shl [b]"

/datum/bitlogic_asg/proc/operator<<=(b)
	v <<= b

/datum/bitlogic_asg/proc/operator>>(b)
	return "shr [b]"

/datum/bitlogic_asg/proc/operator>>=(b)
	v >>= b

// Assignment overload that returns a value: the value becomes the new A
/datum/bitlogic_asr
	var/v = 3

/datum/bitlogic_asr/proc/operator^=(b)
	v ^= b
	return "new [b]"

/datum/bitlogic_asr/proc/operator>>=(b)
	return null

// Only operator>> (>>= falls back to A = A >> B)
/datum/bitlogic_shr
	var/v = 3

/datum/bitlogic_shr/proc/operator>>(b)
	return "shr [b]"

// List access overloads
/datum/bitlogic_idx
	var/list/log = list()

/datum/bitlogic_idx/proc/operator[](i)
	return isnum(i) ? i * 10 : "idx [i]"

/datum/bitlogic_idx/proc/operator[]=(i, b)
	log += "[i]=[b]"

/proc/bitlogic_args(a, b)
	return list(2 in args, 3 in args, null in args, args ~= list(1, 2), args ~! list(1, 2), args ~= list(1))

/proc/bitlogic_sw3(x)
	switch(x)
		if(1, 5 to 7)
			return "1|5-7"
		else
			return "else"
'''

# ---- pools -------------------------------------------------------------------------------------
# Numbers for the bit operators: signs, fractions, the 24-bit edge, beyond int32, specials
BITS = ["0", "1", "-1", "6", "255", "0.5", "2.9", "-2.5", "16777215", "16777216", "16777218",
        "33554433", "2147483648", "1e10", "-16777216", "PINF", "NINF", "NAN", "null"]
BITS_S = ["0", "1", "-1", "6", "2.9", "-2.5", "16777215", "16777216", "33554433", "NAN", "null"]
BITS_M = ["0", "1", "-1", "6", "2.9", "16777216", "1e10", "NAN", "null"]
BITS_C = ["0", "-1", "6", "2.9", "16777215", "16777218", "null"]
SHIFT_A = ["0", "1", "-1", "3", "16777215", "16777216", "2.9", "-2.5", "1e10", "NAN", "null"]
SHIFT_N = ["0", "1", "8", "23", "24", "31", "32", "-1", "1.9", "NAN", "null"]
WRONG = ['"a"', '"3"', "list()", "list(1, 2)", "/datum", "new /datum"]

# Lists and non-lists for & | ^ on lists
LISTS = ["list()", "list(1, 2, 3)", "list(3, 2, 1, 1)", 'list("a" = 1, "b" = 2)',
         'list("b" = 5, "c")', "list(null, 1)", "2", '"a"', "null"]

# Truthiness pool for ! && || ?:
TRUTH = ["0", "1", "-0", "0.0001", '""', '"a"', '" "', '"0"', "null", "list()", "new /datum",
         "/datum", "NAN", "PINF"]
TRUTH_S = ["0", "1", '""', '"a"', "null", "list()", "/datum", "NAN"]

# Equality pool
EQ = ["0", "1", "0.1 + 0.2", '""', '"a"', '"A"', '"1"', "null", "NAN", "list()", "/datum",
      "new /datum", "'test.dmi'"]
EQ_S = ["0", "1", '""', '"a"', '"1"', "null", "NAN", "list()", "/datum"]

# Ordering pool: numbers, null, text (case, length, digits, multibyte, U+FFFD vs astral)
CMP = ["0", "1", "-1", "null", '""', '"a"', '"A"', '"ab"', '"10"', '"9"', q("🙂"), q("�"), "NAN"]
CMP_S = ["0", "1", "-1", "null", '""', '"a"', '"B"', '"ab"', "NAN"]
CMP_WRONG = ["list(1)", "/datum", "new /datum", "'test.dmi'"]

OPS2 = ["&", "|", "^"]
SHIFTS = ["<<", ">>"]
ORD = ["<", ">", "<=", ">="]

IN_ITEMS = ["1", '"a"', '"A"', '"b"', "null", "2", "1.0", "NAN", "list()", "/datum"]
IN_LISTS = ['list(1, "a")', 'list("a" = 1)', 'list("x" = "b")', "list(null)", "list(list())",
            "list(/datum, 2)", "null", '"abc"', "5", "/datum", "new /datum", "list(NAN)"]

RANGE_X = ["0", "1", "3", "5", "6", "2.5", "-1", "null", '"3"', "NAN"]
RANGES = ["1 to 5", "5 to 1", "1 to 1", "-5 to -1", "0.5 to 2.5", "1 to 5 step 2", "1 to 6 step 2",
          "5 to 1 step -1", "1 to PINF", "null to 5", "1 to null"]


def build(s):
    s.dm(HELPERS)

    def body(proc, lines, res, display=None):
        # bitlogic_calls is global: start each logging case from an empty log so a case that
        # errors between bitlogic_t() and bitlogic_log() cannot leak entries into the next one
        if "bitlogic_log()" in res:
            lines = ["bitlogic_calls = list()"] + list(lines)
        return s.body(proc, lines, res, display)

    v = lambda x: f"bitlogic_v({x})"

    # ---- & | ^ on numbers: runtime operands (full grid) and literal operands (folded) ----------
    for op in OPS2:
        pool = BITS_S if op == "&" else BITS_M
        s.sweep(op, [pool, pool], fmt=lambda a, b, op=op: f"{v(a)} {op} {v(b)}")
        s.sweep(op, [BITS_C, BITS_C], fmt=lambda a, b, op=op: f"({a}) {op} ({b})")
        # Extra numbers of the larger pool against a couple of partners
        for a in BITS:
            if a not in BITS_S:
                for b in ["-1", "16777215"]:
                    s.case(op, f"{v(a)} {op} {v(b)}")
                    s.case(op, f"{v(b)} {op} {v(a)}")
        # Wrong types on either side and against each other
        for w in WRONG:
            for n in ["1", "null"]:
                s.case(op, f"{v(w)} {op} {v(n)}")
                s.case(op, f"{v(n)} {op} {v(w)}")
            s.case(op, f"{v(w)} {op} {v(w)}")
        s.case(op, f'{v(q("a"))} {op} {v(q("b"))}')
        s.case(op, f"{v('/datum')} {op} {v('/obj')}")
        # Precedence: & above ^ above |, all below ==
        s.case(op, f"{v('6')} {op} {v('3')} == 2")
        s.case(op, f"(6 {op} 3) == 2")

    s.case("&", "1 | 2 & 3")
    s.case("&", "1 ^ 3 & 1")
    s.case("|", "4 | 1 ^ 1")
    s.case("&", "6 & 3 + 1")
    s.case("|", "1 | 2 == 3")
    s.case("&", "(1 | 2) == 3")

    # ---- ~ on numbers and other kinds ----------------------------------------------------------
    for a in BITS + WRONG:
        s.case("~", f"~{v(a)}")
    for a in BITS_C:
        s.case("~", f"~({a})")
    s.case("~", "~~5")
    s.case("~", f"~~{v('-5')}")
    s.case("~", f"~{v('5')} & 255")
    s.case("~", f"{v('255')} & ~{v('15')}")
    s.case("~", "-~0")
    s.case("~", "~-1")

    # ~ on matrices: inverse (new matrix, original unchanged)
    for m in ["matrix()", "matrix(2, 0, 0, 0, 2, 0)", "matrix(1, 2, 3, 4, 5, 6)",
              "matrix(0, 1, 5, -1, 0, 7)", "matrix(0, 0, 0, 0, 0, 0)", "matrix(1, 2, 0, 2, 4, 0)"]:
        s.case("~", f"~{m}")
    body("~", ["var/matrix/M = matrix(2, 0, 3, 0, 4, 5)", "var/matrix/N = ~M"],
           "list(M, N, M == N)")
    body("~", ["var/matrix/M = matrix(2, 0, 3, 0, 4, 5)", "var/matrix/N = ~M", "N.Multiply(M)"], "N")

    # ---- << >> ---------------------------------------------------------------------------------
    for op in SHIFTS:
        s.sweep(op, [SHIFT_A, SHIFT_N], fmt=lambda a, b, op=op: f"{v(a)} {op} {v(b)}")
        for a in ["1", "-1", "16777215", "2.9", "null"]:
            for b in ["0", "8", "24", "32", "-1", "null"]:
                s.case(op, f"({a}) {op} ({b})")
        for w in WRONG:
            s.case(op, f"{v(w)} {op} {v('1')}")
            s.case(op, f"{v('1')} {op} {v(w)}")
        s.case(op, f"{v('null')} {op} {v('null')}")
        # Precedence: shifts bind tighter than & and comparisons, looser than +
        s.case(op, f"{v('1')} {op} 2 + 1")
        s.case(op, f"{v('16')} {op} 1 & 6")
        s.case(op, f"{v('16')} {op} 1 < 9")
    s.case("<<", "1 << 23")
    s.case("<<", "1 << 24")
    s.case("<<", f"{v('1')} << 23 << 1")
    s.case(">>", f"{v('16777215')} >> 4 << 4")
    s.case("<<", f"{v('16777215')} << 4 >> 4")
    s.case(">>", f"{v('-16')} >> 2")

    # ---- assignment forms on numbers -----------------------------------------------------------
    AOPS = ["&=", "|=", "^=", "<<=", ">>="]
    for op in AOPS:
        for a, b in [("12", "10"), ("-1", "255"), ("16777215", "16777215"), ("2.9", "1.9"),
                     ("null", "5"), ("5", "null"), ("null", "null"), ("1e10", "1"), ("NAN", "1"),
                     ('"a"', "1"), ("3", '"a"'), ("16777215", "8"), ("1", "24"), ("1", "32")]:
            body(op, [f"var/x = {a}", f"x {op} {b}"], "x")
        # The assignment's value as an expression, and the target afterwards
        body(op, ["var/x = 12", f"var/r = (x {op} 3)"], "list(r, x)")
        # The target expression is evaluated once
        body(op, ["var/list/L = list(12, 12)", "var/i = 1", f"L[i++] {op} 3"], "list(L, i)")
        # On an object var
        body(op, ["var/datum/bitlogic_d/D = new", f"D.v {op} 2"], "D.v")

    # ---- & | ^ on lists ------------------------------------------------------------------------
    for op in OPS2:
        lp = LISTS if op == "&" else LISTS[:5] + LISTS[6:8]
        s.sweep(op, [lp, lp], fmt=lambda a, b, op=op: f"({a}) {op} ({b})")
        s.case(op, f"list(1, 2) {op} list(2, 3)")
        s.case(op, f"list(1, list(2)) {op} list(list(2), 1)")
        s.case(op, f"list(/datum, /obj) {op} list(/obj, /mob)")
        s.case(op, f'list("a", "A") {op} list("A")')
        s.case(op, f"list(1, 1, 2, 2) {op} list(2, 2, 3, 3)")
        s.case(op, f"list(1, 2) {op} 2")
        s.case(op, f"list(1, 2) {op} null")
        s.case(op, f"list(1, 2) {op} new /datum")
        s.case(op, f'list("k" = 1) {op} list("k" = 2)')
        # The result is a new list; the operands are unchanged
        body(op, ["var/list/A = list(1, 2)", "var/list/B = list(2, 3)", f"var/list/C = A {op} B"],
               "list(A, B, C, C == A)")
    s.case("&", "list(1, 2, 3) & list(3) & list(3, 1)")
    s.case("|", "list(1) | list(2) | list(1, 3)")
    s.case("^", "list(1, 2) ^ list(2, 3) ^ list(3, 4)")

    # In-place list forms: same object, items removed/added
    for op in ["&=", "|=", "^="]:
        for a, b in [("list(1, 2, 3)", "list(2, 3, 4)"), ("list(1, 1, 2)", "list(1)"),
                     ("list(3, 2, 1)", "list(1, 2)"), ('list("a" = 1, "b" = 2)', 'list("b" = 9, "c" = 3)'),
                     ("list(1, 2)", "2"), ("list(1, 2)", "null"), ("list()", "list(1)"),
                     ("list(1, 2)", "list()"), ("list(1, 2, 2)", "list(2, 2, 2)")]:
            body(op, [f"var/list/L = {a}", "var/list/M = L", f"L {op} {b}"], "list(L, L == M)")
        body(op, ["var/list/L = list(1, 2)", f"L {op} L"], "L")
        body(op, ["var/list/L = list(1, 2)", f"var/r = (L {op} list(2, 5))"], "list(r, L, r == L)")
        body(op, ["var/x = null", f"x {op} list(1, 2)"], "x")
        body(op, ["var/x = 3", f"x {op} list(1, 3)"], "x")

    # ---- icons (documented blend forms) --------------------------------------------------------
    s.case("&", "icon('test.dmi', \"half\") & \"#ff0000\"")
    s.case("|", "icon('test.dmi', \"half\") | \"#ff0000\"")
    s.case("|", "icon('test.dmi', \"half\") | icon('test.dmi', \"alpha\")")
    s.case("&", "icon('test.dmi', \"half\") & icon('test.dmi', \"alpha\")")
    body("&=", ["var/icon/I = icon('test.dmi', \"half\")", "var/icon/J = I", "I &= \"#00ff00\""],
           "list(I, I == J)")
    body("|=", ["var/icon/I = icon('test.dmi', \"half\")", "var/icon/J = I", "I |= \"#00ff00\""],
           "list(I, I == J)")

    # ---- operator overloads --------------------------------------------------------------------
    D = "new /datum/bitlogic_ov"
    for e in [f"({D}) & 1", f"({D}) | 2", f"({D}) ^ 3", f"~({D})", f"({D}) << 4", f"({D}) >> 5",
              f"({D}) ~= 3", f"({D}) ~= 4", f"({D}) ~! 3", f"({D}) ~! 4", f"({D}) < 5", f"({D}) < 1",
              f"({D}) > 1", f"({D}) >= 5", f"({D}) >= 3", f"({D}) <= 1", f"({D}) <= 3",
              f"({D}) == 3", f"({D}) && 0", f"!({D})", f"1 & ({D})", f"null | ({D})",
              f"({D}) <=> 1", "(new /datum/bitlogic_ova) <=> 2", "(new /datum/bitlogic_ova) < 7",
              "(new /datum/bitlogic_ova) > 2", "(new /datum/bitlogic_ova) & 3",
              "(new /datum/bitlogic_ova) | 1", f"3 ~= ({D})", f"3 < ({D})"]:
        s.case("overload", e)
    body("overload", [f"var/datum/bitlogic_ov/O = {D}", "var/datum/bitlogic_ov/P = O", "O |= 4"],
           "list(O == P, O.v)")
    body("overload", [f"var/datum/bitlogic_ov/O = {D}", "O &= 1"], "O")
    body("overload", [f"var/datum/bitlogic_ov/O = {D}", "O ^= 1"], "O")
    body("overload", [f"var/datum/bitlogic_ov/O = {D}", "O <<= 2"], "O")
    body("overload", ["var/datum/bitlogic_ova/O = new", "O &= 3"], "O")
    body("overload", ["var/datum/bitlogic_ova/O = new", "O |= 3"], "O")

    # ---- ! -------------------------------------------------------------------------------------
    for a in TRUTH:
        s.case("!", f"!{v(a)}")
        s.case("!", f"!!{v(a)}")
    for a in ["0", "1", '""', '"a"', "null"]:
        s.case("!", f"!({a})")
    s.case("!", "!1 + 1")
    s.case("!", "!0 == 1")
    s.case("!", "!-1")
    s.case("!", "-!0")
    s.case("!", "!~16777215")

    # ---- && || return values, short-circuit, chaining ------------------------------------------
    for op in ["&&", "||"]:
        s.sweep(op, [TRUTH_S, TRUTH_S], fmt=lambda a, b, op=op: f"{v(a)} {op} {v(b)}")
        for a in TRUTH:
            if a not in TRUTH_S:
                s.case(op, f"{v(a)} {op} {v(q('x'))}")
                s.case(op, f"{v('0')} {op} {v(a)}")
                s.case(op, f"{v('1')} {op} {v(a)}")
        for a in ["0", "1", '""', '"a"', "null"]:
            for b in ["0", '"b"']:
                s.case(op, f"{a} {op} {b}")
        # Which operands were evaluated
        for a, b, c in [("0", "1", "2"), ("1", "0", "2"), ("1", "2", "3"), ("0", "0", "0"),
                        ('""', '"a"', "null"), ("null", "0", '"z"')]:
            body(op, [f"var/r = bitlogic_t({a}) {op} bitlogic_t({b}) {op} bitlogic_t({c})"],
                   "list(r, bitlogic_log())")
    s.case("&&", "1 || 0 && 0")
    s.case("&&", "0 && 1 || 2")
    s.case("&&", "(0 || 3) && (4 || 5)")
    s.case("&&", "1 && 2 == 2")
    s.case("||", "0 || 2 | 1")
    s.case("&&", "3 & 1 && 2")
    body("&&", ["var/r = bitlogic_t(1) && bitlogic_t(2) || bitlogic_t(3)"], "list(r, bitlogic_log())")
    body("||", ["var/r = bitlogic_t(0) || bitlogic_t(0) && bitlogic_t(3)"], "list(r, bitlogic_log())")
    body("&&", ["var/list/L = list(1)", "var/r = L && L"], "r == L")
    body("||", ["var/datum/D = new", "var/r = 0 || D"], "r == D")

    # &&= ||=
    for op in ["&&=", "||="]:
        for a in ["0", "1", '""', '"a"', "null", "list()", "NAN"]:
            body(op, [f"var/x = {a}", f"var/r = (x {op} bitlogic_t(7))"], "list(x, r, bitlogic_log())")
        body(op, ["var/list/L = list(0, 1)", "var/i = 1", f"L[i++] {op} bitlogic_t(9)"],
               "list(L, i, bitlogic_log())")
        body(op, ["var/list/L = list(0, 1)", "var/i = 2", f"L[i++] {op} bitlogic_t(9)"],
               "list(L, i, bitlogic_log())")
        body(op, ["var/datum/bitlogic_d/D = new", "D.v = 0", f"D.v {op} 4"], "D.v")
        body(op, ["var/x = 2", f"x {op} 0", f"x {op} 5"], "x")

    # ---- ternary -------------------------------------------------------------------------------
    for a in TRUTH:
        s.case("?", f'{v(a)} ? "T" : "F"')
    for e in ["1 ? 2 : 3 ? 4 : 5", "0 ? 2 : 3 ? 4 : 5", "0 ? 2 : 0 ? 4 : 5", "1 ? 0 ? 6 : 7 : 8",
              "1 + 1 ? 5 : 6", "0 || 0 ? 5 : 6", "1 && 0 ? 5 : 6", "2 > 1 ? \"y\" : \"n\"",
              "null ? 1 : null", "(0 ? 1 : 2) + 10", "1 ? list(1) : list(2)",
              "0 ? 1 : 2 | 4", "1 | 0 ? 3 : 4"]:
        s.case("?", e)
    body("?", ["var/r = bitlogic_t(1) ? bitlogic_t(2) : bitlogic_t(3)"], "list(r, bitlogic_log())")
    body("?", ["var/r = bitlogic_t(0) ? bitlogic_t(2) : bitlogic_t(3)"], "list(r, bitlogic_log())")
    body("?", ["var/x = 1", "var/r = x ? (x = 5) : (x = 6)"], "list(r, x)")
    body("?", ["var/x", "x = 0 ? 1 : 2"], "x")

    # ---- ?. ?: ?[] -----------------------------------------------------------------------------
    nd = "var/datum/bitlogic_d/D"
    mk = "var/datum/bitlogic_d/D = new"
    for lines, res in [
        ([nd], "D?.v"), ([mk], "D?.v"), ([nd], "D?.f(1)"), ([mk], "D?.f(1)"),
        ([mk], "D?.next"), ([mk], "D?.next?.v"), ([mk, "D.next = new", "D.next.v = 8"], "D?.next?.v"),
        ([nd], "D?.next?.v"), ([mk], "D?.items?.len"), ([mk, "D.items = list(1, 2)"], "D?.items?.len"),
        ([nd, "var/r = D?.f(bitlogic_t(1))"], "list(r, bitlogic_log())"),
        ([mk, "var/r = D?.f(bitlogic_t(1))"], "list(r, bitlogic_log())"),
        ([nd, "D?.v = bitlogic_t(3)"], "list(D, bitlogic_log())"),
        ([mk, "D?.v = bitlogic_t(3)"], "list(D.v, bitlogic_log())"),
        ([mk, "D?.v += 3"], "D.v"),
        ([nd, "D?.v += bitlogic_t(3)"], "list(D, bitlogic_log())"),
        ([mk, "D?.v |= 2"], "D.v"),
        ([nd, "D?.v++"], "D"),
        (["var/r = bitlogic_mk(4)?.v"], "list(r, bitlogic_log())"),
        (["var/r = bitlogic_null()?.v"], "list(r, bitlogic_log())"),
        (["var/r = bitlogic_null()?:v"], "list(r, bitlogic_log())"),
        (["var/x = new /datum/bitlogic_d"], "x?:v"),
        (["var/x = null"], "x?:v"),
        (["var/x = null"], "x?:f(2)"),
        (["var/x = new /datum/bitlogic_d"], "x?:f(2)"),
        (["var/x = new /datum"], "x?:v"),
        (["var/x = 0"], "x?:v"),
        (["var/x = \"\""], "x?:v"),
        (["var/x = \"abc\""], "x?:v"),
        (["var/x = list(1, 2)"], "x?:len"),
        (["var/list/L = list(1, 2, 3)"], "L?.len"),
        (["var/list/L"], "L?.len"),
        (["var/x = null", "x?:v = bitlogic_t(1)"], "list(x, bitlogic_log())"),
        (["var/x = new /datum/bitlogic_d", "x?:v = 9"], "x:v"),
        (["var/obj/O = parity_track(new /obj/bitlogic_box(locate(1, 1, 1)))"], "O?.loc"),
        (["var/obj/O"], "O?.loc?.x"),
        (["var/obj/O = parity_track(new /obj/bitlogic_box(locate(2, 3, 1)))"], "O?.loc?.y"),
        # ?[] index
        (["var/list/L", "var/i = 1", "var/r = L?[i++]"], "list(r, i)"),
        (["var/list/L = list(5, 6, 7)", "var/i = 1", "var/r = L?[i++]"], "list(r, i)"),
        (["var/list/L", "var/i = 1", "L?[i++] = bitlogic_t(4)"], "list(L, i, bitlogic_log())"),
        (["var/list/L = list(5, 6, 7)", "var/i = 2", "L?[i++] = bitlogic_t(4)"], "list(L, i, bitlogic_log())"),
        (['var/list/L = list("a" = 1)'], 'L?["a"]'),
        (['var/list/L'], 'L?["a"]'),
        ([mk], "D?.items?[1]"),
        ([mk, "D.items = list(3)"], "D?.items?[1]"),
        (["var/list/L = list(5)"], "L?[2]"),
        (["var/x = 0"], "x?[1]"),
    ]:
        body("?.", lines, res)

    # ---- ~= ~! ---------------------------------------------------------------------------------
    EQV = [
        ("list()", "list()"), ("list(1, 2)", "list(1, 2)"), ("list(1, 2)", "list(2, 1)"),
        ("list(1, 2)", "list(1, 2, 3)"), ("list(1, 1)", "list(1)"), ("list(null)", "list()"),
        ("list(null)", "list(null)"), ('list("a")', 'list("A")'), ("list(list(1))", "list(list(1))"),
        ('list("a" = 1)', 'list("a" = 1)'), ('list("a" = 1)', 'list("a" = 2)'), ('list("a" = 1)', 'list("a")'),
        ('list("a" = 1, "b" = 2)', 'list("b" = 2, "a" = 1)'), ('list("a" = null)', 'list("a")'),
        ('list("a" = list())', 'list("a" = list())'), ("list(NAN)", "list(NAN)"), ("list(0)", "list(null)"),
        ("list(/datum)", "list(/datum)"), ("list(1)", "1"), ("1", "list(1)"), ("list()", "null"),
        ("null", "list()"), ("null", "null"), ("1", "1"), ("1", '"1"'), ('"a"', '"a"'), ('"a"', '"A"'),
        ("0", "null"), ('""', "null"), ("NAN", "NAN"), ("/datum", "/datum"), ("new /datum", "new /datum"),
        ("matrix()", "matrix()"), ("matrix()", "matrix(1, 0, 0, 0, 1, 0)"), ("matrix(1, 2, 3, 4, 5, 6)", "matrix(1, 2, 3, 4, 5, 6)"),
        ("matrix(1, 2, 3, 4, 5, 6)", "matrix(1, 2, 3, 4, 5, 7)"), ("matrix()", "list(1, 0, 0, 0, 1, 0)"),
        ("matrix(NAN, 0, 0, 0, 1, 0)", "matrix(NAN, 0, 0, 0, 1, 0)"), ("matrix(0, 0, 0, 0, 0, 0)", "matrix(-0, 0, 0, 0, 0, 0)"),
        ("matrix()", "null"), ("matrix()", "1"), ("list(1, 0, 0, 0, 1, 0)", "matrix()"),
        ("vector(1, 2)", "vector(1, 2)"), ('alist("a" = 1)', 'alist("a" = 1)'), ('alist("a" = 1)', 'list("a" = 1)'),
        ("icon('test.dmi')", "icon('test.dmi')"), ("'test.dmi'", "'test.dmi'"),
    ]
    for a, b in EQV:
        s.case("~=", f"({a}) ~= ({b})")
        s.case("~!", f"({a}) ~! ({b})")
    body("~=", ["var/datum/D = new"], "list(D ~= D, D ~! D)")
    body("~=", ["var/list/L = list(1)"], "list(L ~= L, L ~! L)")
    body("~=", ["var/list/L = list(1)", "var/list/M = list(L)", "var/list/N = list(L)"], "list(M ~= N, M == N)")
    body("~=", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/N = M"], "M ~= N")
    body("~=", ['var/list/L = list("a" = 1, "b")', 'var/list/M = list("a" = 1, "b")'], "L ~= M")
    s.case("~=", "1 ~= 1 == 1")
    s.case("~=", "list(1) ~= list(1) && 1")

    # ---- == != <> ------------------------------------------------------------------------------
    s.sweep("==", [EQ, EQ], fmt=lambda a, b: f"{v(a)} == {v(b)}")
    s.sweep("!=", [EQ_S, EQ_S], fmt=lambda a, b: f"{v(a)} != {v(b)}")
    for a, b in [("1", "1"), ("1", "2"), ('"a"', '"a"'), ("null", "0"), ("NAN", "NAN")]:
        s.case("<>", f"{v(a)} <> {v(b)}")
        s.case("==", f"({a}) == ({b})")
        s.case("!=", f"({a}) != ({b})")
    for a, b in [("list(1)", "list(1)"), ("matrix()", "matrix()"), ("vector(1, 2)", "vector(1, 2)"),
                 ("1e7", "1e7 + 0.5"), ("16777216", "16777217"), ("0.1 + 0.2", "0.3"),
                 ("-0", "0"), ("\"\"", "null"), ("0", "\"\""), ("0", "\"0\""), ("/datum", "\"/datum\""),
                 ("'test.dmi'", "'test.dmi'"), ("'test.dmi'", "'small.dmi'"), ("/proc/bitlogic_v", "/proc/bitlogic_v"),
                 ("PINF", "1e39"), ("NINF", "-PINF"), (q("é"), q("é")), (q("abc"), q("ABC")),
                 ("locate(1, 1, 1)", "locate(1, 1, 1)"), ("locate(1, 1, 1)", "locate(2, 1, 1)"),
                 ("world", "world"), ("locate(/area)", "locate(/area)")]:
        s.case("==", f"{v(a)} == {v(b)}")
        s.case("!=", f"{v(a)} != {v(b)}")
    body("==", ["var/datum/D = new", "var/datum/E = D"], "list(D == E, D != E)")
    body("==", ["var/list/L = list(1)", "var/list/M = L"], "list(L == M, L != M)")
    body("==", ["var/x = NAN"], "list(x == x, x != x)")
    s.case("==", "1 == 1 == 1")
    s.case("==", "2 == 2 == 2")
    s.case("==", "1 < 2 == 1")
    s.case("==", "3 != 3 == 0")

    # ---- < > <= >= <=> -------------------------------------------------------------------------
    for op in ORD:
        pool = CMP if op == "<" else CMP_S + [q("🙂")]
        s.sweep(op, [pool, pool], fmt=lambda a, b, op=op: f"{v(a)} {op} {v(b)}")
        for w in CMP_WRONG:
            for n in ["1", '"a"', "null"]:
                s.case(op, f"{v(w)} {op} {v(n)}")
                s.case(op, f"{v(n)} {op} {v(w)}")
            s.case(op, f"{v(w)} {op} {v(w)}")
        # Literal operands (compiler folding)
        for a, b in [("1", "2"), ("2", "1"), ("null", "1"), ("null", "-1"), ("1", "null"), ("null", "null"),
                     ('"a"', '"b"'), ('"b"', '"a"'), ('"a"', '"A"'), ("null", '""'), ('""', "null"),
                     ("null", '"a"'), ('"a"', "null"), ("0", "null"), ("1", '"1"'), ('"1"', "1")]:
            s.case(op, f"({a}) {op} ({b})")
    for a, b in [("1", "2"), ("2", "1"), ("1", "1"), ("NAN", "1"), ("1", "NAN"), ("null", "0"),
                 ("null", "1"), ('"a"', '"b"'), ('"b"', '"a"'), ('"a"', '"A"'), ('"a"', '"a"'),
                 ("null", '""'), ("null", '"a"'), ('""', '"a"'), ("1", '"1"'), ('"1"', "1"),
                 ("PINF", "PINF"), ("NINF", "PINF"), ("list()", "1"), ("1", "list()"),
                 (q("é"), q("🙂")), (q("🙂"), q("�")), ('"ab"', '"a"'), ("null", "null")]:
        s.case("<=>", f"{v(a)} <=> {v(b)}")
    s.case("<=>", "1 <=> 2")
    s.case("<=>", '"b" <=> "a"')
    # Text comparisons against sorttextEx, plus longer / embedded strings
    for a, b in [("abc", "abd"), ("abc", "ab"), ("Zebra", "apple"), ("a b", "ab"), ("a\tb", "a b"),
                 ("", " "), ("A", "a"), ("_", "a"), ("[", "Z"), ("ß", "ss"), ("é", "f"), ("É", "é"),
                 ("日本", "本日"), ("ﬁ", "\U0001f642"), ("a\x01", "a")]:
        s.case("<", f"list({v(q(a))} < {v(q(b))}, sorttextEx({q(a)}, {q(b)}))")
    s.case("<", "1 < 2 < 3")
    s.case("<", "3 > 2 > 1")
    s.case("<", "1 < 2 + 1")
    s.case("<", "!1 < 1")
    s.case("<", "1 << 2 > 3")

    # ---- in on lists, atoms, other containers --------------------------------------------------
    s.sweep("in", [IN_ITEMS, IN_LISTS], fmt=lambda a, b: f"({v(a)} in {v(b)})")
    for a, b in [("1", "list(1)"), ('"a"', 'list("a" = 1)'), ("1", 'list("a" = 1)'), ("null", "list()"),
                 ("null", "null"), ('"b"', '"abc"'), ("2", "list(1, 2)")]:
        s.case("in", f"({a} in {b})")
    for e in ['("a" in alist("a" = 1))', '(1 in alist("a" = 1))', "(1 in list(1.0))",
              "(1 in list(\"1\"))", "(16777216 in list(16777217))", "(0 in list(null))",
              '("" in list(null))', "(list(1) in list(list(1)))", "(/datum in list(/datum/bitlogic_d))",
              "(matrix() in list(matrix()))", '("a" in list("A"))',
              "(!1 in list(0))", "(!(1 in list(0)))", "(1 + 1 in list(2))", "(1 | 2 in list(3))",
              "(1 && 2 in list(9))", "(2 in list(1, 2) == 1)"]:
        s.case("in", e)
    body("in", ["var/x", "x = 2 in list(1)"], "x")
    body("in", ["var/list/L = list(1, 2)", "var/r = (L in list(L))"], "r")
    body("in", ["var/datum/D = new", "var/list/L = list(D)"], "list(D in L, (new /datum) in L)")
    body("in", ["var/list/L = list(1, 2, 3)", "var/n = 0", "for(var/x in L)", "\tif(x in L) n++"], "n")
    # Atoms: contents of turfs/objs/areas/world
    box = ["var/obj/O = parity_track(new /obj/bitlogic_box(locate(2, 2, 1)))", "var/turf/T = locate(2, 2, 1)",
           "var/area/A = T.loc"]
    for res in ["O in T", "O in locate(1, 1, 1)", "O in T.contents", "O in locate(2, 2, 1).contents",
                "O in world", "T in world", "T in A", "A in world", "O in A", "O in O", "O in O.loc",
                "T in O", "O in null", "O in list(T)", "/obj/bitlogic_box in T", "\"box\" in T",
                "T in T"]:
        body("in", box, f"list(({res}), O, T, A)")
    body("in", box + ["var/obj/P = parity_track(new /obj/bitlogic_box(O))"],
           "list(P in O, P in O.loc, P in world)")
    body("in", ["var/datum/D = new"], "(D in world)")

    # ---- in ranges -----------------------------------------------------------------------------
    s.sweep("in to", [RANGE_X, RANGES], fmt=lambda a, b: f"({v(a)} in {b})")
    for x in ["1", "3", "4"]:
        s.case("in to", f"({x} in 1 to 5 step 2)")
    s.case("in to", "(3 in 1 to 2 + 1)")
    s.case("in to", "(3 in 1 + 1 to 3)")
    body("in to", ["var/a = 2", "var/b = 4", "var/x = 3"], "(x in a to b)")
    body("in to", ['var/x = "b"'], '(x in "a" to "c")')
    body("in to", ["var/r = (bitlogic_t(3) in bitlogic_t(1) to bitlogic_t(5))"], "list(r, bitlogic_log())")
    body("in to", ["var/n = 0", "if(2 in 1 to 3)", "\tn = 1"], "n")
    body("in to", ["var/n = 0", "if(!(7 in 1 to 3))", "\tn = 1"], "n")
    # switch ranges (constant, inclusive, fractional, text)
    for x in ["0", "1", "2", "3", "3.5", "4.5", "6", "6.1", "10", "-3", "-0.5", '"b"', '"d"', "null",
              "NAN", "PINF"]:
        s.case("switch to", f"bitlogic_sw({x})")
    # for-in range loops: values visited, including step, reversed, fractional and empty
    for rng in ["1 to 5", "1 to 5 step 2", "5 to 1", "5 to 1 step -1", "5 to 1 step -2", "0 to 1 step 0.25",
                "1 to 1", "1 to 2.5", "1.5 to 4", "-2 to 2", "1 to 4 step 1.5", "3 to 3 step -1"]:
        body("for to", ["var/list/L = list()", f"for(var/i in {rng})", "\tL += i"], "L")
    body("for to", ["var/list/L = list()", "var/e = 3", "for(var/i in 1 to e)", "\tL += i", "\te = 10"], "L")
    body("for to", ["var/list/L = list()", "var/i", "for(i in 1 to 3)", "\tL += i"], "list(L, i)")

    # ==== gap fill ==============================================================================
    # ---- comparison fallbacks: ~= from ~!, < from >=, > from <= ---------------------------------
    for t, exprs in [("bitlogic_ne", ["~= 3", "~= 4", "~! 3", "~! 4"]),
                     ("bitlogic_ge", ["< 5", "< 1", "< 3", ">= 3", ">= 5"]),
                     ("bitlogic_le", ["> 1", "> 5", "> 3", "<= 3", "<= 1"])]:
        for e in exprs:
            s.case("overload fallback", f"(new /datum/{t}) {e}")
    body("overload fallback", ["var/datum/bitlogic_ne/D = new", "var/r = (D ~= D)"], "r")

    # ---- explicit assignment overloads ---------------------------------------------------------
    for op, b in [("&=", "1"), ("^=", "1"), ("<<=", "2"), (">>=", "1")]:
        body("overload assign", ["var/datum/bitlogic_asg/O = new", "var/datum/bitlogic_asg/P = O",
                                 f"O {op} {b}"], "list(O == P, O.v)")
        # The value of the assignment expression itself
        body("overload assign", ["var/datum/bitlogic_asg/O = new", f"var/r = (O {op} {b})"],
             "list(r == O, O.v)")
    body("overload assign", ["var/datum/bitlogic_asr/O = new", "var/datum/bitlogic_asr/P = O", "O ^= 7"],
         "list(O == P, O, P.v)")
    body("overload assign", ["var/datum/bitlogic_asr/O = new", "var/datum/bitlogic_asr/P = O", "O >>= 7"],
         "list(O == P, P.v)")
    body("overload assign", ["var/datum/bitlogic_shr/O = new", "O >>= 2"], "O")
    body("overload assign", ["var/datum/bitlogic_shr/O = new", "O <<= 2"], "O")
    body("overload assign", ["var/datum/bitlogic_ov/O = new", "var/datum/bitlogic_ov/P = O", "O >>= 2"],
         "list(O, O == P)")
    body("overload assign", ["var/datum/bitlogic_d/O = new", "O >>= 2"], "O")
    body("overload assign", ["var/datum/bitlogic_d/O = new", "O ^= 2"], "O")
    body("overload assign", ["var/datum/bitlogic_d/O = new", "O &= 2"], "O")

    # ---- [] / ?[] with operator[] and operator[]= ----------------------------------------------
    ix = "var/datum/bitlogic_idx/D = new"
    nix = "var/datum/bitlogic_idx/D"
    for lines, res in [
        ([ix], "D[3]"), ([ix], 'D["k"]'), ([ix], "D?[2]"), ([nix], "D?[2]"),
        ([ix, "D[1] = 4"], "D.log"),
        ([ix, "D?[1] = bitlogic_t(5)"], "list(D.log, bitlogic_log())"),
        ([nix, "D?[1] = bitlogic_t(5)"], "list(D, bitlogic_log())"),
        ([ix, "var/r = D?[bitlogic_t(4)]"], "list(r, bitlogic_log())"),
        ([nix, "var/r = D?[bitlogic_t(4)]"], "list(r, bitlogic_log())"),
        ([ix, "D[2] += 1"], "D.log"),
    ]:
        body("?[] overload", lines, res)

    # ---- ?[] compound / increment / chained -----------------------------------------------------
    for lines, res in [
        (["var/list/L", "L?[1] += bitlogic_t(2)"], "list(L, bitlogic_log())"),
        (["var/list/L", "var/i = 1", "L?[i++]++"], "list(L, i)"),
        (["var/list/L", "var/i = 1", "++L?[i++]"], "list(L, i)"),
        (["var/list/L", "L?[1] |= bitlogic_t(4)"], "list(L, bitlogic_log())"),
        (["var/list/L = list(1, 2)", "L?[1] |= 4"], "L"),
        (["var/list/L = list(1, 2)", "L?[1]++"], "L"),
        (["var/list/L = list(1, 2)", "var/r = L?[2]++"], "list(r, L)"),
        (["var/list/L = list(1, 2)", "L?[2] += bitlogic_t(5)"], "list(L, bitlogic_log())"),
        (["var/list/L = list(null)"], "L?[1]?[2]"),
        (["var/list/L = list(list(7, 8))"], "L?[1]?[2]"),
        (["var/list/L"], "L?[1]?[2]"),
        (["var/list/L = list(null)", "var/i = 1", "var/r = L?[1]?[i++]"], "list(r, i)"),
    ]:
        body("?[] compound", lines, res)

    # ---- ?. assignment chains and increments on a non-null datum -------------------------------
    for lines, res in [
        ([mk, "D?.next?.v = bitlogic_t(1)"], "list(D.next, D.v, bitlogic_log())"),
        ([mk, "D.next = new", "D?.next?.v = bitlogic_t(1)"], "list(D.next.v, bitlogic_log())"),
        ([mk, "D?.next?.v += bitlogic_t(1)"], "list(D.next, bitlogic_log())"),
        ([mk, "D?.v++"], "D.v"),
        ([mk, "var/r = D?.v++"], "list(r, D.v)"),
        ([mk, "++D?.v"], "D.v"),
        ([mk, "var/r = ++D?.v"], "list(r, D.v)"),
        ([mk, "D?.v--"], "D.v"),
        ([nd, "++D?.v"], "D"),
        ([mk, "D?.v &&= bitlogic_t(0)"], "list(D.v, bitlogic_log())"),
        ([mk, "D.v = 0", "D?.v &&= bitlogic_t(0)"], "list(D.v, bitlogic_log())"),
        ([mk, "D?.v ||= bitlogic_t(9)"], "list(D.v, bitlogic_log())"),
        ([nd, "D?.v &&= bitlogic_t(0)"], "list(D, bitlogic_log())"),
    ]:
        body("?. assign", lines, res)

    # ---- ?. on list procs ----------------------------------------------------------------------
    for decl in ["var/list/L", "var/list/L = list(1, 2)"]:
        body("?. list", [decl, "var/r = L?.Find(bitlogic_t(2))"], "list(r, bitlogic_log())")
        body("?. list", [decl, "var/r = L?.Add(bitlogic_t(1))"], "list(r, L, bitlogic_log())")
        body("?. list", [decl, "var/r = L?.Copy()"], "list(r, r == L)")
        body("?. list", [decl, 'var/r = L?.Join(",")'], "r")
        body("?. list", [decl.replace("var/list/L", "var/L"), "var/r = L?:Find(bitlogic_t(2))"],
             "list(r, bitlogic_log())")

    # ---- ternary vs ?. lexing, `in` against ternary --------------------------------------------
    for e in ["x ?.5 : 2", "x?2:3", "x ? 0.5 : 2", "x?.5:2", "x ? .5 : 2"]:
        for xv in ["1", "0"]:
            body("? lex", [f"var/x = {xv}", f"var/r = {e}"], "r")
    s.case("? lex", "(1 in list(1) ? 5 : 6)")
    s.case("? lex", "(1 in list(2) ? 5 : 6)")
    body("? lex", ["var/r = 2 in list(2) ? 7 : 8"], "r")
    body("? lex", ["var/r = 3 in list(2) ? 7 : 8"], "r")

    # ---- matrix | & |= -------------------------------------------------------------------------
    body("|=", ["var/matrix/M = matrix()", "var/N = M", "M |= matrix(2, 0, 0, 0, 2, 0)"], "list(M, M == N)")
    body("&=", ["var/matrix/M = matrix()", "var/N = M", "M &= matrix(2, 0, 0, 0, 2, 0)"], "list(M, M == N)")
    for e in ["matrix() | matrix(2, 0, 0, 0, 2, 0)", "matrix() & matrix()",
              "matrix(1, 2, 3, 4, 5, 6) & matrix(2, 0, 0, 0, 2, 0)", "matrix() ^ matrix()",
              "matrix() | 1", "matrix() << 1"]:
        s.case("matrix bit", e)
    body("matrix bit", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/R = M | matrix(2, 0, 0, 0, 2, 0)"],
         "list(M, R, M == R)")

    # ---- alist with & | ^ and reversed ~= ------------------------------------------------------
    for e in ['alist("a" = 1, "b" = 2) ^ list("b", "c")', 'list("a") & alist("a" = 1)',
              'alist("a" = 1) | alist("b" = 2)', 'alist("a" = 1, "b" = 2) & list("a")',
              'list("a" = 1) ~= alist("a" = 1)', 'list("a" = 1) ~! alist("a" = 1)',
              'alist("a" = 1) ~= alist("a" = 2)', 'list("a" = 2) ~= alist("a" = 1)']:
        s.case("alist ops", e)
    body("alist ops", ['var/alist/A = alist("a" = 1, "b" = 2)', "var/B = A", 'A ^= list("a")'], "list(A, A == B)")
    body("alist ops", ['var/alist/A = alist("a" = 1)', 'A |= alist("b" = 2)'], "A")

    # ---- in / ~= on special lists --------------------------------------------------------------
    s.case("in special", "bitlogic_args(1, 2)")
    body("in special", ["var/datum/bitlogic_d/D = new"],
         'list("v" in D.vars, 5 in D.vars, "type" in D.vars, "zz" in D.vars)')
    box2 = ["var/obj/O = parity_track(new /obj/bitlogic_box(locate(2, 2, 1)))", "var/turf/T = locate(2, 2, 1)"]
    body("in special", box2, "list(O in O.locs, T in O.locs, O.locs ~= list(T), O.locs ~= list())")
    body("in special", box2 + ["O.overlays += 'test.dmi'"],
         "list('test.dmi' in O.overlays, 'small.dmi' in O.overlays, O.overlays ~= list())")
    body("in special", box2, "list('test.dmi' in O.overlays, O.overlays ~= list(), O.overlays ~= null)")
    body("in special", box2,
         "list(/obj/bitlogic_box/verb/poke in O.verbs, /obj/bitlogic_box/verb/poke in O.verbs.Copy())")
    body("in special", box2, "list(O in T.contents, O in O.vis_locs, 1 in O.underlays)")
    body("in special", ["var/savefile/S = new", 'S["k"] << 5'], 'list("k" in S, "k" in S.dir, "z" in S.dir)')

    # ---- in-range with non-number operands -----------------------------------------------------
    for e in ["null in -1 to 1", '"x" in -1 to 1', "list() in -1 to 1", "1 in null to 2", '0 in "a" to 1',
              "/datum in -1 to 1", "0 in -1 to null"]:
        s.case("in to", f"({e})")
    for x, a, b in [("null", "-1", "1"), ('"x"', "-1", "1"), ("list()", "-1", "1"), ("1", "null", "2"),
                    ("0", '"a"', "1")]:
        s.case("in to", f"({v(x)} in {v(a)} to {v(b)})")

    # ---- in-range step variants ----------------------------------------------------------------
    for e in ["2.5 in 1 to 4 step 1.5", "3 in 1 to 4 step 1.5", "4 in 1 to 4 step 1.5",
              "3 in 1 to 5 step -1", "3 in 1 to 5 step 0", "3 in 5 to 1 step -2", "2 in 5 to 1 step -2",
              "1 in 1 to 5 step 0"]:
        s.case("in to", f"({e})")
    s.case("in to", f"({v('2.5')} in 1 to 4 step {v('1.5')})")

    # ---- switch range forms --------------------------------------------------------------------
    for x in ['"b"', '"a"', '"c"', '"d"', '"B"', '"bz"', "6", "8", "null", "1", "5", "7", "9", "0"]:
        # Text range inline (OD's compiler rejects it, so it must not live in defs.dm)
        body("switch to", [f"var/x = {x}", 'var/r = "else"', "switch(x)", '	if("a" to "c")', '		r = "a-c"'], "r")
        s.case("switch to", f"bitlogic_sw3({x})")
        # Reversed constant range inline (BYOND's compiler rejects it)
        body("switch to", [f"var/x = {x}", 'var/r = "else"', "switch(x)", "	if(9 to 7)", '		r = "9-7"'], "r")

    # ---- shift count edges ---------------------------------------------------------------------
    for op in SHIFTS:
        for n in ["33", "64", "16777217", "-24", "-32", "25", "-33"]:
            s.case(op, f"{v('1')} {op} {v(n)}")
            s.case(op, f"{v('16777215')} {op} {v(n)}")
    for e in ["1 << 25", "1 << 31", "1 << 33", "1 << -1", "16777215 >> -24", "8 >> 33"]:
        s.case("<<" if "<<" in e else ">>", e)

    # ---- <=> with datum/list on either side, >= <= derived from <=> --------------------------
    for e in ["(new /datum) <=> 1", "1 <=> (new /datum)", "list(1) <=> list(1)", '"a" <=> 1', '1 <=> "a"',
              "null <=> 1", "(new /datum/bitlogic_ova) >= 7", "(new /datum/bitlogic_ova) <= 7",
              "(new /datum/bitlogic_ova) >= 6", "(new /datum/bitlogic_ova) <= 6",
              "(new /datum/bitlogic_ova) >= 5", "(new /datum/bitlogic_ova) <= 5"]:
        s.case("<=>", e)

    # ---- <= >= null/zero special cases with runtime operands -----------------------------------
    for a, op, b in [("-0", "<=", "null"), ('""', "<=", "null"), ('""', ">=", "null"), ("null", "<=", '""'),
                     ("0", ">=", "null"), ("null", ">=", "0"), ("null", ">=", '""'), ("-0", ">=", "null"),
                     ("null", "<=", "0"), ("0", "<=", "null"), ('""', "<", "null"), ("null", "<", '""')]:
        s.case(op, f"{v(a)} {op} {v(b)}")

    # ---- ~= shallow with overloaded items -------------------------------------------------------
    for e in ["list(new /datum/bitlogic_ov) ~= list(3)", "list(matrix()) ~= list(matrix())",
              "list(list(1)) ~= list(list(1))", "list(3) ~= list(new /datum/bitlogic_ov)",
              'list("a" = matrix()) ~= list("a" = matrix())']:
        s.case("~=", e)
