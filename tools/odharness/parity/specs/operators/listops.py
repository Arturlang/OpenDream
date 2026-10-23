"""List operators: + - | & ^ and their assignment forms, list[index] get/set, list == list, list.len,
list()/alist() construction, new /list(), concatenation order.

BYOND reference points targeted here (info.html: /list, /list/associations, /list/operators,
/operator/+ - | & ^ and their = forms, /proc/list, /proc/alist, /list/var/len):
- A + B / A += B: B a list adds each item; otherwise B is added as one item. A - B removes items
  (Remove: from the END, one copy per item in B).
- A | B: items from A, then items of B not already in A. A |= B adds B items not in A.
- A & B: items in both, in A's order. A &= B removes A items not in B.
- A ^ B: items only in A first, then items only in B. A ^= B removes common items from A, then
  adds B-only items.
- Indices range 1..len; associations need a text/object key (numeric = index); a missing key reads
  null. len grows with nulls, shrinks by dropping items.
- list(a = 1) uses the named-argument form: the key is the text "a", not a variable's value.
- alist(): strictly associative, keys may be numbers, keys unique, order not under user control,
  len can only be set to 0.

OpenDream code these cases aim at (DreamList.cs, DreamAssocList.cs, DMOpcodeHandlers.cs, DMProc.cs):
- DreamList.GetValue returns null for out-of-range integer indices (BYOND: "list index out of bounds").
- DreamList.SetValue silently ignores index < 1 and GROWS the list for index > len.
- CreateAssociativeList treats a numeric key as an index assignment (SetValue with growth) and a null
  key as a plain item.
- OperatorAdd/Append carry assoc values from B; OperatorOr uses Union (dedups A too, B's assoc
  values overwrite); BitAnd/BitXor copy assoc values; Mask/Combine (&=, |=) in place.
- BitXorValues only iterates B's values, so A-only items are dropped from A ^ B.
- len set: TryGetValueAsInteger (non-numbers -> 0), negative -> optional exception/0.
- alist: Dictionary order, Add of an existing key is a no-op, len != 0 errors, | == +.
"""
from gen import dm_str

S = "listops_"

HELPERS = r'''
/obj/listops_item

/datum/listops_d
	var/n = 0

/datum/listops_d/New(n)
	src.n = n

// "same"/"new" (did the operator keep the object in A) plus the value now in A
/proc/listops_st(old, now)
	return "[old == now ? "same" : "new"] [listops_show(now)]"

/proc/listops_show(v)
	if(istype(v, /alist))
		return listops_akv(v)
	return parity_canon(v)

// Code-point order, so the sort does not depend on either engine's text comparison
/proc/listops_less(a, b)
	var/la = length(a)
	var/lb = length(b)
	for(var/i in 1 to min(la, lb))
		var/ca = text2ascii(a, i)
		var/cb = text2ascii(b, i)
		if(ca != cb)
			return ca < cb
	return la < lb

/proc/listops_sort(list/L)
	var/list/out = L.Copy()
	for(var/i in 2 to out.len)
		var/j = i
		while(j > 1 && listops_less(out[j], out[j - 1]))
			out.Swap(j, j - 1)
			j--
	return out

// An alist (or any list) as len plus its key=value pairs sorted, so key order does not matter;
// numeric keys print their values too, unlike parity_canon
/proc/listops_akv(list/A)
	if(isnull(A))
		return "null"
	var/list/parts = list()
	for(var/k in A)
		parts += "[parity_canon(k)]=[parity_canon(A[k])]"
	return "A([length(A)])\[[jointext(listops_sort(parts), ", ")]\]"

// Items of a list in order with the assoc value of every non-numeric item (null shown)
/proc/listops_full(list/L)
	var/list/parts = list()
	for(var/i in 1 to L.len)
		var/k = L[i]
		var/s = parity_canon(k)
		if(!isnum(k) && !isnull(k))
			s += "=[parity_canon(L[k])]"
		parts += s
	return "F([L.len])\[[jointext(parts, ", ")]\]"
'''

OPS = [("+", "add"), ("-", "sub"), ("|", "or"), ("&", "and"), ("^", "xor")]

# Left operands: lists of each shape
A_POOL = [
    "list()", "list(1, 2, 3)", "list(1, 2, 2, 3, 1)", 'list("a", "b", "c")', 'list("a" = 1, "b" = 2)',
    'list("a" = 1, "b", 3)', "list(list(1), list(2))", "list(null, 1, null)", "list(/obj, /datum, 1.5)",
]
# Right operands: lists, items, null and other kinds
B_POOL = [
    "null", "1", "2", '"a"', '"z"', "/obj", "new /datum", "NAN",
    "list()", "list(1)", "list(2, 3)", "list(1, 1)", 'list("a")', 'list("a" = 9)', 'list("b" = 5, "c" = 6)',
    "list(null)", "list(list(1))", 'list(1, "a", /obj)',
]
# Smaller right pool for the assignment forms
B_ASSIGN = [
    "null", "1", '"a"', "/obj", "list()", "list(1)", "list(2, 3)", "list(1, 1)", 'list("a" = 9)',
    'list("b" = 5, "c" = 6)', "list(null)", "list(list(1))",
]
# Non-list left operands with list right operands
A_OTHER = ["null", "1", "0", '"a"', "/obj", "new /datum", "NAN"]
B_LISTS = ["list()", "list(1, 2)", 'list("a" = 1)', "list(null)"]


def build(s):
    s.dm(HELPERS.strip("\n"))
    ops(s)
    assign_ops(s)
    op_edges(s)
    index_ops(s)
    equality(s)
    length_ops(s)
    ctor(s)
    alist_ops(s)
    order(s)
    gaps(s)


# ---------------- binary operators ----------------
def ops(s):
    for op, name in OPS:
        p = f"list_{name}"
        s.sweep(p, [A_POOL, B_POOL], fmt=lambda a, b, op=op: f"({a}) {op} ({b})")
        s.sweep(p, [A_OTHER, B_LISTS], fmt=lambda a, b, op=op: f"({a}) {op} ({b})")
        # The operand lists are not changed
        s.body(p, ["var/list/A = list(1, 2, 3)", "var/list/B = list(3, 4)", f"var/list/C = A {op} B"],
               "list(A, B, C, A == C, B == C)")
        s.body(p, ['var/list/A = list("a" = 1, "b" = 2)', 'var/list/B = list("b" = 3, "c" = 4)',
                   f"var/list/C = A {op} B"], "list(listops_full(A), listops_full(B), listops_full(C))")
        # Same list on both sides
        for L in ["list(1, 2, 3)", "list(1, 1, 2)", 'list("a" = 1, "b" = 2)', "list()", "list(null)"]:
            s.body(p, [f"var/list/A = {L}", f"var/list/C = A {op} A"], "list(A, C, A == C)")
        # Always a new list, even with an empty operand
        s.body(p, ["var/list/A = list(1)", f"var/list/C = A {op} list()"], "list(A == C, C)")
        s.body(p, ["var/list/A = list(1)", f"var/list/C = A {op} null"], "list(A == C, C)")
        # Shared datums
        s.body(p, ["var/datum/D = new /datum/listops_d(1)", "var/datum/E = new /datum/listops_d(2)",
                   f"var/list/C = list(D, E, 1) {op} list(E, 2)"],
               "list(C.len, C.Find(D), C.Find(E), C.Find(1), C.Find(2))")
        # Assoc values with object keys
        s.body(p, ["var/datum/D = new /datum/listops_d(1)", "var/list/A = list()", 'A[D] = "x"',
                   "var/list/B = list()", 'B[D] = "y"', f"var/list/C = A {op} B"],
               "list(C.len, C.len ? C[D] : -1)")
        # Number edge items
        for a, b in [("list(NAN)", "NAN"), ("list(NAN)", "list(NAN)"), ("list(0)", "null"), ("list(null)", "0"),
                     ("list(PINF, NINF)", "PINF"), ("list(1)", "1.0"), ("list(0.1 + 0.2)", "0.3"),
                     ("list(16777217)", "16777216"), ('list("1")', "1"), ('list("A")', '"a"'),
                     ("list(/obj)", '"/obj"'), ("list(/obj)", "/obj/listops_item")]:
            s.case(p, f"({a}) {op} ({b})")
        # Chained
        s.case(p, f"list(1, 2) {op} list(2, 3) {op} list(3, 4)")
        s.case(p, f"list(1, 2) {op} 2 {op} 3")
        # Result len and assoc reads
        s.case(p, f'(list("a" = 1, "b" = 2) {op} list("b" = 3, "c" = 4))["b"]')
        s.case(p, f'(list("a" = 1, "b" = 2) {op} list("b" = 3, "c" = 4))["c"]')
        s.case(p, f'(list("a" = 1, "b" = 2) {op} list("b" = 3, "c" = 4))["a"]')
        s.case(p, f'length(list(1, 2, 3) {op} list(2, 3, 4))')
        # Operators on special lists
        s.body(p, ["var/datum/D = new", f"var/list/C = D.vars {op} list()"], "list(islist(C), C.len > 0)")
        s.body(p, [f"var/list/C = args {op} list(1)"], "C")
        s.body(p, ["var/list/A = new /list(2)", f"var/list/C = A {op} list(null)"], "C")


# ---------------- assignment forms ----------------
def assign_ops(s):
    for op, name in OPS:
        p = f"list_{name}_assign"
        for a in A_POOL:
            for b in B_ASSIGN:
                s.body(p, [f"var/list/L = {a}", "var/list/O = L", f"L {op}= {b}"], "listops_st(O, L)")
        for a in A_OTHER:
            for b in B_LISTS:
                s.body(p, [f"var/L = {a}", "var/O = L", f"L {op}= {b}"], "listops_st(O, L)")
        # L op= L (self)
        for L in ["list(1, 2, 3)", "list(1, 1, 2)", 'list("a" = 1, "b" = 2)', "list()", "list(null, null)"]:
            s.body(p, [f"var/list/L = {L}", "var/list/O = L", f"L {op}= L"], "listops_st(O, L)")
        # The value of the assignment expression
        s.body(p, ["var/list/L = list(1, 2)", f"var/r = (L {op}= list(2, 3))"], "list(r == L, r)")
        s.body(p, ["var/list/L = list(1, 2)", f"var/r = (L {op}= 2)"], "list(r == L, r)")
        # Other references to the list see the change only when it is done in place
        s.body(p, ["var/list/L = list(1, 2)", "var/list/H = list(L)", f"L {op}= list(2, 3)"], "list(H[1], L)")
        # Through a field and an index
        s.body(p, ["var/list/H = list(list(1, 2))", f"H[1] {op}= list(2, 3)"], "H")
        s.body(p, ['var/list/H = list("k" = list(1, 2))', f'H["k"] {op}= list(2, 3)'], "listops_full(H)")
        s.body(p, ['var/list/H = list("k" = null)', f'H["k"] {op}= list(2, 3)'], "listops_full(H)")
        s.body(p, ["var/datum/listops_d/D = new(1)", "var/list/L = list(1)", f"L {op}= D.n"], "L")
        # Shared datum removal / addition
        s.body(p, ["var/datum/D = new /datum/listops_d(1)", "var/list/L = list(D, 1, D)", f"L {op}= D"],
               "list(L.len, L.Find(D), L.Find(1))")
        s.body(p, ["var/datum/D = new /datum/listops_d(1)", "var/list/L = list(D, 1)", f"L {op}= list(D, D)"],
               "list(L.len, L.Find(D), L.Find(1))")
        # Assoc values on the left survive or not
        s.body(p, ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', f'L {op}= list("b", "d")'], "listops_full(L)")
        s.body(p, ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', f'L {op}= list("b" = 20, "d" = 40)'],
               "listops_full(L)")
        s.body(p, ['var/list/L = list("a" = 1, "b" = 2)', f'L {op}= "b"'], "listops_full(L)")
        s.body(p, ['var/list/L = list("a" = 1, "b" = 2)', f'L {op}= "b"', 'L += "b"'], "listops_full(L)")


# ---------------- hand-picked operator edges ----------------
def op_edges(s):
    # Remove from the end, one copy per item
    for e in ["list(1, 2, 1, 2) - 1", "list(1, 2, 1, 2) - list(1)", "list(1, 2, 1, 2) - list(1, 1)",
              "list(1, 2, 1, 2) - list(1, 1, 1)", "list(1, 2, 3, 1) - list(1, 2, 3)",
              'list("a", "b", "a") - "a"', 'list("a" = 1, "b", "a") - "a"', "list(null, 1, null) - null",
              "list(null, 1, null) - list(null)", "list(list(1), 1) - list(1)", "list(1, 2, 3) - list(list(1))"]:
        s.case("list_sub", e)
    for e in ["list(1, 2, 1) & list(1)", "list(1, 1, 2) & list(1, 1)", "list(3, 2, 1) & list(1, 2, 3)",
              "list(1, 2, 3) & 2", "list(2, 1, 2) & 2", 'list("a" = 1, "a") & list("a")',
              "list(null, 1) & list(null)", "list(1, 2) & list()"]:
        s.case("list_and", e)
    for e in ["list(1, 1, 2) | list(1, 1, 1)", "list(1, 1) | list(2, 2)", "list(1, 1) | 1", "list(1, 1) | 2",
              "list() | list(1, 1)", 'list("a" = 1) | list("a" = 2)', 'list("a" = 1) | list("a")',
              'list("a") | list("a" = 2)', "list(null) | list(null, null)"]:
        s.case("list_or", e)
    for e in ["list(1, 2) ^ list(2, 3)", "list(1, 2, 3) ^ list(4, 2)", "list(1, 1, 2) ^ list(2)",
              "list(1) ^ list(1, 1)", "list(1, 1) ^ list(1)", "list(1, 2) ^ 2", "list(1, 2) ^ 3",
              'list("a" = 1, "b" = 2) ^ list("b" = 3, "c" = 4)', "list() ^ list(1, 1)",
              "list(3, 1) ^ list(2, 4)"]:
        s.case("list_xor", e)
    for e in ['list("a" = 1) + list("a" = 2)', 'list("a" = 1) + list("a")', 'list("a") + list("a" = 2)',
              'list("a" = 1) + "a"', "list(1) + list(list(2, 3))", "list(1) + list(list())",
              "list() + list()", "list() + null", "list(1) + list(null, null)"]:
        s.case("list_add", e)
    # Assoc readback after combining
    for op, name in OPS:
        s.case(f"list_{name}", f'listops_full(list("a" = 1, "b") {op} list("a" = 2, "b" = 3))')
        s.case(f"list_{name}", f'listops_full(list("a", "a") {op} list("a" = 2))')
    # Remove and re-add keeps or drops the association
    s.body("list_sub_assign", ['var/list/L = list("a", "a")', 'L["a"] = 1', 'L -= "a"'], "listops_full(L)")
    s.body("list_sub_assign", ['var/list/L = list("a" = 1)', 'L -= "a"', 'L += "a"'], "listops_full(L)")
    s.body("list_sub_assign", ['var/list/L = list("a" = 1)', 'L -= "a"', 'L["a"] = null'], "listops_full(L)")
    s.body("list_sub_assign", ['var/list/L = list("a" = 1, "b" = 2)', 'L -= list("a" = 5)'], "listops_full(L)")
    s.body("list_and_assign", ['var/list/L = list("a" = 1, "b" = 2)', 'L &= list("a" = 5)'], "listops_full(L)")
    s.body("list_or_assign", ['var/list/L = list("a" = 1, "b" = 2)', 'L |= list("a" = 5, "c" = 6)'],
           "listops_full(L)")
    s.body("list_xor_assign", ['var/list/L = list("a" = 1, "b" = 2)', 'L ^= list("a" = 5, "c" = 6)'],
           "listops_full(L)")
    s.body("list_add_assign", ['var/list/L = list("a" = 1, "b" = 2)', 'L += list("a" = 5, "c" = 6)'],
           "listops_full(L)")
    # Building a list in a loop
    s.body("list_add_assign", ["var/list/L = list()", "for(var/i in 1 to 5)", "\tL += i", "for(var/i in 1 to 3)",
                               "\tL -= i"], "L")
    s.body("list_add_assign", ["var/list/L = list()", "for(var/i in 1 to 5)", "\tL += list(list(i))"], "L")
    s.body("list_or_assign", ["var/list/L = list()", "for(var/i in 1 to 10)", "\tL |= i % 3"], "L")
    s.body("list_xor_assign", ["var/list/L = list()", "for(var/i in 1 to 6)", "\tL ^= i % 3"], "L")
    s.body("list_and_assign", ["var/list/L = list(1, 2, 3, 4, 5, 6)", "L &= list(6, 4, 2, 7)"], "L")
    # Big lists
    s.body("list_or", ["var/list/A = list()", "var/list/B = list()", "for(var/i in 1 to 200)", "\tA += i",
                       "\tB += i + 100"], "length(A | B)")
    s.body("list_and", ["var/list/A = list()", "var/list/B = list()", "for(var/i in 1 to 200)", "\tA += i",
                        "\tB += i + 100"], "(A & B)[1]")
    s.body("list_xor", ["var/list/A = list()", "var/list/B = list()", "for(var/i in 1 to 200)", "\tA += i",
                        "\tB += i + 100"], "list(length(A ^ B), (A ^ B)[1], (A ^ B)[101])")
    s.body("list_sub", ["var/list/A = list()", "for(var/i in 1 to 200)", "\tA += i % 7"], "length(A - list(0, 1))")
    # Unary minus / other arithmetic on a list
    for e in ["-list(1)", "list(1) * 2", "list(1) / 2", "list(1) % 2", "list(1) ** 2", "~list(1)",
              "!list()", "!list(1)", "list(1) << 1", "list(1) >> 1", "list(1) && 5", "list() || 5"]:
        s.case("list_misc", e)
    s.body("list_misc", ["var/list/L = list(1)", "L++"], "L")
    s.body("list_misc", ["var/list/L = list(1)", "L *= 2"], "L")


# ---------------- list[index] ----------------
IDX = ["0", "1", "2", "3", "4", "-1", "1.5", "2.9", "0.5", '"a"', '"b"', '"1"', "null", "NAN", "PINF",
       "/obj", "list()", "new /datum"]
IDX_LISTS = ["list(10, 20, 30)", 'list("a" = 1, "b" = 2)', "list()", 'alist("a" = 1, 2 = "two")']


def index_ops(s):
    for L in IDX_LISTS:
        for i in IDX:
            s.body("list_index", [f"var/list/L = {L}"], f"L[{i}]")
            s.body("list_index_set", [f"var/list/L = {L}", f'L[{i}] = "v"'], "listops_show(L)")
    # Assoc keys of each kind
    for k in ['"k"', '"K"', '""', '" "', '"1"', "/obj", "/datum", "/list", 'new /datum/listops_d(1)',
              "parity_track(new /obj)", "list(1)", "null", "1", "1.5", "PINF", "NAN", '"é"', "'test.dmi'",
              "matrix()"]:
        s.body("list_index_set", ["var/list/L = list()", f"var/key = {k}", "L[key] = 5"],
               "list(L.len, L.len ? L[1] == key : null, L[key])")
    # Datum key identity
    s.body("list_index", ["var/datum/D = new /datum/listops_d(1)", "var/datum/E = new /datum/listops_d(1)",
                          "var/list/L = list()", "L[D] = 1", "L[E] = 2"], "list(L.len, L[D], L[E])")
    s.body("list_index", ["var/list/L = list()", "L[/obj] = 1", "L[/obj/listops_item] = 2", "L[/obj] = 3"],
           "listops_full(L)")
    s.body("list_index", ["var/list/L = list()", 'L["a"] = 1', 'L["A"] = 2'], "listops_full(L)")
    # Missing key
    s.case("list_index", 'list("a" = 1)["b"]')
    s.case("list_index", 'list("a" = 1)["a"]')
    s.case("list_index", "list(1, 2)[2]")
    s.body("list_index", ['var/list/L = list("a" = 1)', 'var/x = L["zz"]'], "list(x, L.len)")
    # Index on a key-only item
    s.body("list_index", ['var/list/L = list("a", "b" = 2)'], 'list(L["a"], L["b"], L[1], L[2])')
    # Same key twice
    s.body("list_index_set", ['var/list/L = list("a", "a")', 'L["a"] = 1'], "listops_full(L)")
    s.body("list_index_set", ['var/list/L = list("a" = 1)', 'L["a"] = null'], "listops_full(L)")
    s.body("list_index_set", ['var/list/L = list("a" = 1)', 'L["a"] = 2', 'L["b"] = 3'], "listops_full(L)")
    # Replacing a key by index: what happens to its association
    s.body("list_index_set", ['var/list/L = list("a" = 1, "x" = 2)', 'L[2] = "b"'],
           'list(listops_full(L), L["x"], L["b"])')
    s.body("list_index_set", ['var/list/L = list("a" = 1, "x" = 2)', 'L[2] = "a"'],
           'list(listops_full(L), L["x"], L["a"])')
    s.body("list_index_set", ['var/list/L = list("a" = 1, "x" = 2)', "L[2] = 5"], 'list(L, L["x"])')
    s.body("list_index_set", ['var/list/L = list("a" = 1, "x" = 2)', 'L[2] = "b"', 'L["x"] = 7'],
           "listops_full(L)")
    s.body("list_index_set", ['var/list/L = list("a" = 1, "a" = 2)'], "listops_full(L)")
    # Out of bounds writes and reads
    for e, r in [("L[4] = 1", "L"), ("L[5] = 1", "L"), ("L[0] = 1", "L"), ("L[-1] = 1", "L"), ("L[100] = 1", "L.len"),
                 ("L[3.5] = 1", "L"), ("L[0.5] = 1", "L"), ("L[NAN] = 1", "L"), ("L[NINF] = 1", "L")]:
        s.body("list_index_set", ["var/list/L = list(1, 2, 3)", e], r)
    for i in ["0", "4", "-1", "-3", "100", "3.99", "0.99", "NINF"]:
        s.body("list_index", ["var/list/L = list(1, 2, 3)"], f"L[{i}]")
    # Compound assignment through an index
    for e in ['L["a"] += 1', 'L["a"]++', '++L["a"]', 'L["a"] -= 3', 'L["a"] *= 4', 'L["zz"] += 1', 'L["zz"]++',
              'L["zz"] += "t"', 'L["zz"] |= 4', "L[1] += 1", "L[1] += \"x\"", "L[2]++", "L[3] = L[3] + 1",
              'L["a"] = L', 'L["a"] ||= 9', 'L["zz"] ||= 9', 'L["a"] &&= 9', 'L["a"] |= list(2)']:
        s.body("list_index_set", ['var/list/L = list("a" = 1, "b", 3)', e], "listops_full(L)")
    s.body("list_index_set", ['var/list/L = list("a" = 1)', 'var/r = (L["a"] += 5)'], "list(r, L[\"a\"])")
    s.body("list_index_set", ['var/list/L = list(5)', "var/r = L[1]++"], "list(r, L)")
    # Nested
    s.body("list_index", ["var/list/L = list(list(1, 2), list(3, 4))"], "L[2][1]")
    s.body("list_index", ['var/list/L = list("a" = list("b" = 5))'], 'L["a"]["b"]')
    s.body("list_index", ["var/list/L = list(list(1, 2))"], "L[1][3]")
    s.body("list_index", ["var/list/L = list(1)"], "L[1][1]")
    s.body("list_index", ['var/list/L = list("a" = 1)'], 'L["b"]["c"]')
    s.body("list_index_set", ["var/list/L = list(list(1, 2), list(3, 4))", "L[2][1] = 9"], "L")
    s.body("list_index_set", ['var/list/L = list("a" = list())', 'L["a"]["b"] = 5'], 'listops_full(L["a"])')
    s.body("list_index_set", ["var/list/L = list(list(1, 2))", "L[1][5] = 9"], "L")
    s.body("list_index_set", ["var/list/L[2][3]", "L[2][3] = 7"], "L")
    s.body("list_index", ["var/list/L[2][3]"], "list(L.len, length(L[1]), L[2][3])")
    s.body("list_index", ["var/list/L = new /list(2, 3)"], "L")
    # ?[] and indexing non-lists
    s.body("list_index", ["var/list/L = null"], "L?[1]")
    s.body("list_index", ["var/list/L = list(5)"], "L?[1]")
    s.body("list_index", ["var/list/L = null"], "L[1]")
    s.body("list_index_set", ["var/list/L = null", "L?[1] = 2"], "L")
    s.body("list_index_set", ["var/list/L = null", "L[1] = 2"], "L")
    s.body("list_index", ["var/L = 5"], "L[1]")
    s.body("list_index", ["var/L = new /datum"], "L[1]")
    s.body("list_index", ["var/L = /obj"], "L[1]")
    s.body("list_index_set", ["var/L = 5", "L[1] = 2"], "L")
    s.body("list_index_set", ["var/L = new /datum", "L[1] = 2"], "L")
    # Index of an index result used as key
    s.body("list_index", ['var/list/L = list("a" = "b", "b" = "c")'], "L[L[\"a\"]]")
    s.body("list_index", ["var/list/L = list(2, 3, 1)"], "L[L[L[1]]]")
    # Text index into an item
    s.body("list_index", ['var/list/L = list("abc")'], "L[1][2]")
    # Index writes keep other references in sync
    s.body("list_index_set", ["var/list/L = list(1, 2)", "var/list/M = L", "M[1] = 5"], "L")


# ---------------- == != ~= ----------------
def equality(s):
    for a, b in [("list()", "list()"), ("list(1)", "list(1)"), ('list("a" = 1)', 'list("a" = 1)'),
                 ("list()", "null"), ("list()", "0"), ("list()", '""'), ("list(1)", "1"), ("list()", "alist()"),
                 ("alist()", "alist()"), ('alist("a" = 1)', 'alist("a" = 1)'), ("list(1, 2)", "list(2, 1)"),
                 ("list(1)", "list(1.0)"), ('list("a" = 1)', 'list("a" = 2)'), ('list("a" = 1)', 'list("a")'),
                 ('alist("a" = 1)', 'list("a" = 1)'), ('list("a" = 1)', 'alist("a" = 1)'),
                 ('alist("a" = 1, "b" = 2)', 'alist("b" = 2, "a" = 1)'), ('alist(1 = 2)', 'alist(1 = 3)'),
                 ("list(list(1))", "list(list(1))"), ("new /list(2)", "list(null, null)")]:
        s.case("list_eq", f"({a}) == ({b})")
        s.case("list_eq", f"({a}) != ({b})")
        s.case("list_eq", f"({a}) ~= ({b})")
        s.case("list_eq", f"({a}) ~! ({b})")
    s.body("list_eq", ["var/list/L = list(1, 2)", "var/list/M = L"], "list(L == M, L != M, L ~= M)")
    s.body("list_eq", ["var/list/L = list(1, 2)"], "list(L == L.Copy(), L ~= L.Copy(), L == L)")
    s.body("list_eq", ["var/list/L = list(1, 2)", "var/list/M = L.Copy()", "M += 3", "M -= 3"],
           "list(L == M, L ~= M)")
    s.body("list_eq", ["var/list/L = list()", "L += L"], "list(L.len, L == list())")
    s.body("list_eq", ["var/list/L = list(1)"], 'list(L == "[L]", "[L]")')
    s.body("list_eq", ["var/list/L = list()"], "list(L ? 1 : 0, list(1) ? 1 : 0)")
    s.body("list_eq", ["var/list/L = list()"], "list(L > list(), L < 1, L >= null)")


# ---------------- len ----------------
LEN_VALS = ["0", "1", "2", "3", "5", "10", "-1", "-5", "0.5", "1.5", "2.9", "-0.5", '"4"', '"a"', "null",
            "list()", "list(1, 2)", "NAN", "NINF", "/obj", "TRUE"]


def length_ops(s):
    for v in LEN_VALS:
        s.body("list_len", ["var/list/L = list(1, 2, 3)", f"L.len = {v}"], "L")
        s.body("list_len", ['var/list/L = list("a" = 1, "b" = 2, "c" = 3)', f"L.len = {v}"], "listops_full(L)")
        s.body("list_len", ["var/list/L = list()", f"L.len = {v}"], "L")
        s.body("list_len", ['var/alist/A = alist("a" = 1, 2 = 3)', f"A.len = {v}"], "listops_akv(A)")
    # Shrinking drops associations; growing back does not restore them
    s.body("list_len", ['var/list/L = list("a" = 1, "b" = 2)', "L.len = 1", "L.len = 2"],
           'list(listops_full(L), L["b"], L["a"])')
    s.body("list_len", ['var/list/L = list("a" = 1, "b" = 2)', "L.len = 1", 'L += "b"'], "listops_full(L)")
    s.body("list_len", ['var/list/L = list("a" = 1, "b" = 2)', "L.len = 0", 'L["b"] = 9'], "listops_full(L)")
    # Compound ops on len
    for e in ["L.len++", "L.len--", "++L.len", "L.len += 2", "L.len -= 2", "L.len *= 2", "L.len /= 2",
              "L.len -= 10", "L.len |= 4", "L.len &= 1", "L.len ^= 1", "L.len %= 2"]:
        s.body("list_len", ["var/list/L = list(1, 2, 3)", e], "L")
    s.body("list_len", ["var/list/L = list(1, 2, 3)", "var/r = (L.len = 5)"], "list(r, L.len)")
    s.body("list_len", ["var/list/L = list(1, 2, 3)", "var/r = L.len++"], "list(r, L.len)")
    # Reads
    for L in ["list()", "list(null)", "list(1, 2, 3)", 'list("a" = 1)', "list(list(1, 2))", "new /list(4)",
              "new /list(0)", "alist()", 'alist("a" = 1, "b" = 2)', 'alist("a" = 1, "a" = 2)']:
        s.case("list_len", f"({L}).len")
        s.body("list_len", [f"var/list/L = {L}"], "list(L.len, length(L))")
    s.body("list_len", ["var/list/L = null"], "L.len")
    s.body("list_len", ["var/list/L = null", "L.len = 2"], "L")
    s.body("list_len", ["var/list/L = list(1, 2)", "L.len = 2000", "L[2000] = 5"], "list(L.len, L[1999], L[2000], L[2])")
    s.body("list_len", ["var/list/L = list(1, 2)"], 'L.vars ? 1 : 0')
    s.body("list_len", ["var/list/L = list(1, 2)"], "L.type")
    s.body("list_len", ["var/list/L = list(1, 2)", "var/x = L:len"], "x")
    s.body("list_len", ["var/list/L = list(1, 2)"], 'L.vars["len"]')
    s.body("list_len", ["var/list/L = list(1, 2)"], 'L.nonexistent_var')


# ---------------- list() / new /list construction ----------------
def ctor(s):
    for e in ["list()", "list(1, 2, 3)", "list(a = 1)", "list(a = 1, b = 2)", 'list("a" = 1)', 'list("a b" = 1)',
              'list("a" = 1, "a" = 2)', 'list("a", "a" = 2)', 'list("a" = 1, "a")', 'list("a" = null)',
              'list("a" = list(1, 2))', 'list(1, 2, "k" = 3)', 'list("k" = 3, 1, 2)', "list(/obj = 1)",
              "list(/obj = 1, /obj = 2)", 'list("" = 1)', "list(null)", "list(null, null)", "list(list())",
              "list(1 = 2)", "list(1.5 = 2)", "list(0 = 2)", "list(-1 = 2)", "list(5 = 2)", "list(null = 2)",
              "list(PINF = 2)", "list(NAN = 2)", 'list("1" = 2)', "list((1) = 2)", "list(1 + 1 = 2)",
              'list("a" + "b" = 1)', "list(new /datum = 1)", "list(list() = 1)", "list(a = 1, 2, b = 3)",
              "list(x = 1, y = 2, z = 3)", "list(type = 1)", "list(len = 1)", "list(list = 1)",
              "list(null = null)", "list(1, 2, 3 = 4)", "list(\"a\" = 1, 1 = \"b\")"]:
        s.case("list_ctor", e)
        s.case("list_ctor", f"listops_full({e})")
    # Named-arg key form ignores local variables of the same name
    s.body("list_ctor", ['var/a = "zz"', "var/list/L = list(a = 1)"], "listops_full(L)")
    s.body("list_ctor", ['var/a = "zz"', "var/list/L = list((a) = 1)"], "listops_full(L)")
    s.body("list_ctor", ['var/a = "zz"', 'var/list/L = list("[a]" = 1)'], "listops_full(L)")
    for n in ["1", "2", "0", "-1", "1.5", "5", "NAN", "null"]:
        s.body("list_ctor", [f"var/n = {n}", 'var/list/L = list((n) = "x")'], "listops_full(L)")
        s.body("list_ctor", [f"var/n = {n}", 'var/list/L = list(7, (n) = "x")'], "listops_full(L)")
    s.body("list_ctor", ["var/datum/D = new /datum/listops_d(1)", "var/list/L = list(D = 1)"], "listops_full(L)")
    s.body("list_ctor", ["var/datum/D = new /datum/listops_d(1)", "var/list/L = list((D) = 1)"],
           "list(L.len, L[1] == D, L[D])")
    s.body("list_ctor", ['var/k = "key"', "var/v = 7", "var/list/L = list((k) = v)"], "listops_full(L)")
    s.body("list_ctor", ["var/list/L = list(1, 2)", "var/list/M = list(L)"], "list(M.len, M[1] == L)")
    # new /list and list declarations
    for e in ["new /list()", "new /list(3)", "new /list(0)", "new /list(-1)", "new /list(1.5)", "new /list(2.9)",
              'new /list("3")', "new /list(null)", "new /list(2, 2)", "new /list(2, 0)", "new /list(0, 2)",
              "new /list(1, 2, 3)", "new /list(list(1))", "new /list(NAN)", "new /alist()", "new /alist(3)",
              "list(1, 2).Copy()"]:
        s.case("list_ctor", e)
    s.body("list_ctor", ["var/list/L[3]"], "L")
    s.body("list_ctor", ["var/list/L[0]"], "L")
    s.body("list_ctor", ["var/L[] = list(1)"], "L")
    s.body("list_ctor", ["var/list/L[2][2]", "L[1][1] = 1"], "L")
    s.body("list_ctor", ["var/n = 3", "var/list/L[n]"], "L")
    s.body("list_ctor", ["var/list/L = new"], "L")
    s.body("list_ctor", ["var/list/L = new(2)"], "L")
    s.body("list_ctor", ["var/list/L = list(1)", "var/list/M = list(1)"], "L == M")
    s.case("list_ctor", 'islist(list())')
    s.case("list_ctor", 'istype(list(), /list)')
    s.case("list_ctor", 'list(1, 2)[2]')
    s.case("list_ctor", 'list("a" = 5)["a"]')


# ---------------- alist ----------------
def alist_ops(s):
    for e in ["alist()", 'alist("a" = 1)', 'alist(a = 1, b = 2)', 'alist("a" = 1, "a" = 2)', "alist(1 = 2)",
              'alist(1 = "x", 2 = "y")', "alist(0 = 1)", "alist(-1 = 1)", "alist(1.5 = 1)", "alist(/obj = 1)",
              "alist(null = 1)", 'alist("a" = null)', 'alist("a" = list(1))', "alist(PINF = 1)",
              'alist("1" = 1, 1 = 2)', 'alist(1 = 1, 1.0 = 2)', "alist(list() = 1)", "alist(new /datum = 1)",
              'alist("b" = 2, "a" = 1, "c" = 3)', 'alist(3 = 1, 1 = 2, 2 = 3)', 'alist("a")', "alist(1, 2)"]:
        s.case("alist", f"listops_akv({e})")
        s.case("alist", e)
    for e in ["islist(alist())", "istype(alist(), /list)", "istype(alist(), /alist)", "alist().type",
              "istype(list(), /alist)", "length(alist(a = 1))"]:
        s.case("alist", e)
    # Reads
    for k in ['"a"', "1", "2", "3", "0", '"1"', "null", "1.5", "/obj", '"zz"']:
        s.body("alist_index", ['var/alist/A = alist("a" = 10, 1 = 20, 2 = 30)'], f"A[{k}]")
        s.body("alist_index_set", ['var/alist/A = alist("a" = 10, 1 = 20, 2 = 30)', f'A[{k}] = "v"'],
               "listops_akv(A)")
    s.body("alist_index", ['var/alist/A = alist("a" = 10)', "var/list/out = list()", "for(var/k in A)",
                           "\tout += k"], "out")
    s.body("alist_index", ["var/alist/A = alist(5 = 10, 6 = 12)", "var/t = 0", "for(var/k in A)",
                           "\tt += k * 100 + A[k]"], "t")
    s.body("alist_index", ['var/alist/A = alist("a" = 1)', "var/list/L = A"], 'L["a"]')
    s.body("alist_index_set", ["var/alist/A = alist()", "A[1] = 2", "A[1] = 3", "A[2] = 4"], "listops_akv(A)")
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1)', 'A["a"]++', 'A["b"] += 5'], "listops_akv(A)")
    s.body("alist_index_set", ["var/alist/A = alist()", "var/datum/D = new /datum/listops_d(1)", "A[D] = 1"],
           "list(A[D], length(A))")
    # Operators with alists
    AL = ['alist("a" = 1, "b" = 2)', 'alist(1 = "x", 2 = "y")', "alist()"]
    BL = ['"a"', '"c"', "1", "null", 'list("a")', 'list("c" = 3)', 'list("a" = 9)', 'alist("b" = 7, "c" = 8)',
          "alist(1 = \"z\", 3 = \"w\")"]
    for op, name in OPS:
        for a in AL:
            for b in BL:
                s.case(f"alist_{name}", f"listops_show(({a}) {op} ({b}))")
                s.body(f"alist_{name}_assign", [f"var/alist/A = {a}", "var/O = A", f"A {op}= {b}"],
                       "listops_st(O, A)")
        # list op alist
        for a in ['list("a" = 1, "b")', "list(1, 2)"]:
            for b in ['alist("a" = 5, "c" = 6)', "alist(1 = 7, 3 = 8)"]:
                s.case(f"alist_{name}", f"listops_show(({a}) {op} ({b}))")
                s.body(f"alist_{name}_assign", [f"var/list/L = {a}", "var/O = L", f"L {op}= {b}"],
                       "listops_st(O, L)")
        s.body(f"alist_{name}_assign", ['var/alist/A = alist("a" = 1, "b" = 2)', "var/O = A", f"A {op}= A"],
               "listops_st(O, A)")
        s.body(f"alist_{name}", ['var/alist/A = alist("a" = 1, "b" = 2)', f"var/r = A {op} list()"],
               "list(r == A, listops_show(r), istype(r, /alist))")
    # Raw iteration order (order is engine-defined; a parity point of its own)
    for e in ['alist("b" = 2, "a" = 1, "c" = 3)', "alist(3 = 1, 1 = 2, 2 = 3)", 'alist("z" = 1, 5 = 2, "a" = 3)']:
        s.body("alist_order", [f"var/alist/A = {e}", "var/list/out = list()", "for(var/k in A)", "\tout += k"],
               "out")
    s.body("alist_order", ["var/alist/A = alist()", 'A["z"] = 1', 'A["a"] = 2', 'A["m"] = 3', "var/list/out = list()",
                           "for(var/k in A)", "\tout += k"], "out")
    s.body("alist_order", ['var/alist/A = alist("a" = 1, "b" = 2)', 'A -= "a"', 'A["a"] = 3', "var/list/out = list()",
                           "for(var/k in A)", "\tout += k"], "out")
    # Procs/vars that alists reject or change
    s.body("alist", ['var/alist/A = alist("a" = 1)', 'A.Add("a")'], "listops_akv(A)")
    s.body("alist", ['var/alist/A = alist("a" = 1)', 'A.Add("b")'], "listops_akv(A)")
    s.body("alist", ['var/alist/A = alist("a" = 1)', 'A.Insert(1, "b")'], "listops_akv(A)")
    s.body("alist", ['var/alist/A = alist("a" = 1, "b" = 2)', "A.Swap(1, 2)"], "listops_akv(A)")
    s.body("alist", ['var/alist/A = alist("a" = 1)'], 'A.Find("a")')
    s.body("alist", ['var/alist/A = alist("a" = 1, "b" = 2)'], "listops_akv(A.Copy())")
    s.body("alist", ['var/alist/A = alist("a" = 1, "b" = 2)', "A.Cut()"], "listops_akv(A)")
    s.body("alist", ['var/alist/A = alist("a" = 1, "b" = 2)'], "A == A.Copy()")
    s.body("alist", ['var/alist/A = alist("a" = 1, "b" = 2)', 'A.Remove("a")'], "listops_akv(A)")


# ---------------- concatenation order ----------------
def order(s):
    for e in ["list(1) + list(2) + list(3)", "list(3) + list(1) + 2", "list(1, 2) + list(2, 1)",
              "list(3, 1) | list(2, 1)", "list(1, 2, 3) & list(3, 2)", "list(1, 2) ^ list(2, 3)",
              "list(1, 2, 3) ^ list(4, 2)", "list(4, 2) ^ list(1, 2, 3)", "list(5, 4, 3) - list(4) + list(4)",
              "(list(1) + list(2)) | (list(3) + list(1))", "list(\"b\", \"a\") + list(\"a\" = 1)",
              "list(1, 2) + list(list(3, 4)) + 5"]:
        s.case("list_order", e)
    s.body("list_order", ["var/list/L = list(1)", "L += 2", "L |= 0", "L += list(3, 4)", "L ^= list(4, 5)",
                          "L &= list(5, 3, 2, 1, 0)", "L -= 3"], "L")
    s.body("list_order", ["var/list/L = list()", 'L["c"] = 1', "L += \"a\"", 'L["b"] = 2', "L |= list(\"a\", \"d\")"],
           "listops_full(L)")


# ---------------- gaps found by review ----------------
GAP_DM = r'''
#define LISTOPS_K 5
#define LISTOPS_T "q"

// Datum with list-like operator overloads; every call is logged
/datum/listops_ix
	var/list/calls = list()

/datum/listops_ix/proc/operator[](i)
	calls += "g:[i]"
	if(i == "nest")
		return list(10, 20)
	if(isnum(i))
		return i * 10
	return "r[i]"

/datum/listops_ix/proc/operator[]=(i, v)
	calls += "s:[i]=[v]"

// Read overload only
/datum/listops_ixr

/datum/listops_ixr/proc/operator[](i)
	return "r[i]"

// A list var on a datum, null at first
/datum/listops_f
	var/list/L

// Lists in compile-time var initializers. BYOND 516 rejects list operators here
// ("expected a constant expression" for list(1, 2) + list(3), | and -), so only list()/alist()/[n] forms
/datum/listops_init
	var/list/a = list(1, 2, list(3))
	var/list/b = list("a" = 1, "b")
	var/list/c = list(k = 1)
	var/alist/d = alist(1 = 2)
	var/list/e[3]
	var/list/f = list("x" = list("y" = 2), /obj = 5)
	var/list/g[2][2]

// Writes to args, seen through the named arguments
/proc/listops_args_set(a, b)
	args[1] = 9
	return list(a, b, args.Copy())

/proc/listops_args_len(a, b)
	args.len = 5
	return list(a, b, args.len)

/proc/listops_args_add(a, b)
	var/list/A = args
	A += 1
	return list(a, b, args.len)
'''

BIG = ["var/list/L = list()", "for(var/i in 1 to 70)", "\tL += i"]


def gaps(s):
    s.dm(GAP_DM.strip("\n"))
    # Duplicate key: one copy replaced by index (OD's SetValue drops the association)
    for e in ['L[1] = "b"', 'L[3] = "b"', 'L[1] = "a"', 'L[2] = "a"', "L[1] = 5"]:
        s.body("list_index_set", ['var/list/L = list("a", "x", "a")', 'L["a"] = 1', e],
               'list(listops_full(L), L["a"])')
    # len shrink / Cut where a copy of the key remains (OD's Cut drops the association)
    s.body("list_len", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', "L.len = 2"], 'list(listops_full(L), L["a"])')
    s.body("list_len", ['var/list/L = list("a", "a")', 'L["a"] = 1', "L.len = 1"], 'list(listops_full(L), L["a"])')
    s.body("list_len", ['var/list/L = list("a", "a")', 'L["a"] = 1', "L.Cut(2)"], 'list(listops_full(L), L["a"])')
    s.body("list_len", ['var/list/L = list("a", "a")', 'L["a"] = 1', "L.Cut(1, 2)"], 'list(listops_full(L), L["a"])')
    s.body("list_sub_assign", ['var/list/L = list("a", "b", "a")', 'L["a"] = 1', 'L -= "a"'],
           'list(listops_full(L), L["a"])')
    # B holds the same assoc key twice
    for op, name in OPS:
        for a in ["list(1)", 'list("a" = 5)', "list()"]:
            s.body(f"list_{name}", ['var/list/B = list("a", "a")', 'B["a"] = 1', f"var/list/C = {a} {op} B"],
                   "listops_full(C)")
            s.body(f"list_{name}_assign", ['var/list/B = list("a", "a")', 'B["a"] = 1', f"var/list/L = {a}",
                                           f"L {op}= B"], "listops_full(L)")
    # Lists of 64+ items (OD caches a value set): the cache must follow every change
    big = [
        (['L[5] = "x"', 'L |= "x"', "L |= 5"], 'list(L.len, L.Find("x"), L.Find(5), "x" in L, 5 in L)'),
        (['L[5] = "x"'], 'list("x" in L, 5 in L, L.Find(5), L.Find("x"))'),
        (['L[5] = "x"', "L -= 5"], "L.len"),
        (['L[5] = "x"', 'L -= "x"'], 'list(L.len, "x" in L)'),
        (["L.Swap(1, 70)", "L |= 1", "L |= 70"], "list(L.len, L[1], L[70])"),
        (['L.Insert(1, "y")', 'L |= "y"'], 'list(L.len, L.Find("y"))'),
        (['L.Insert(1, "y")', "L.Cut(1, 2)", 'L |= "y"'], 'list(L.len, L.Find("y"))'),
        (["L.Cut(1, 3)", "L |= 1", "L |= 3"], "list(L.len, L.Find(1), L.Find(3))"),
        (["L.len = 65", "L |= 70"], "list(L.len, L.Find(70))"),
        (["L.len = 75", "L |= null"], "list(L.len, L.Find(null))"),
        (["L.Remove(10)", "L |= 10"], "list(L.len, L.Find(10))"),
        (['L.Splice(1, 2, "s")', 'L |= "s"', "L |= 1"], 'list(L.len, L.Find("s"), L.Find(1))'),
        (['L.Add("q")', 'L |= "q"'], "L.len"),
        (['L["k"] = 1', 'L |= "k"'], 'list(L.len, L["k"])'),
        (["var/list/M = L.Copy()", 'M[1] = "c"', 'L |= "c"', "M |= 1"], 'list(L.len, M.len, "c" in L)'),
        (["L.Cut()", "L |= 1"], "L"),
        (["L -= 3", "L |= 3"], "list(L.len, L.Find(3))"),
        (["L -= 3"], "list(3 in L, L.Find(3), L & list(3), length(L ^ list(3)))"),
        (["L += NAN"], "list(length(L | NAN), length(L & list(NAN)), length(L ^ list(NAN)), NAN in L, L.Find(NAN))"),
        (["L |= NAN", "L |= NAN"], "L.len"),
        (["L += NAN", "L -= NAN"], "L.len"),
        ([], "list(length(L | 1.0), length(L & list(1.0)), length(L ^ list(1.0)), 1.0 in L)"),
        (["L += 5", "L += 5"], "list(length(L | 5), length(L & list(5)), length(L ^ list(5)), length(L - 5), L.Find(5))"),
        (["L += 5"], "list(length(L & L), length(L | L), length(L ^ L))"),
        (["L += 5", "L &= list(5, 6)"], "L"),
        (["L += 5", "L ^= list(5, 71)"], "list(L.len, L.Find(5), L.Find(71))"),
        (["L += null", "L |= null"], "L.len"),
        ([], 'list(length(L | "5"), "5" in L)'),
        (["L[70] = 1"], "list(length(L | list(70)), length(L & list(1)), L.Find(1))"),
    ]
    for lines, r in big:
        s.body("list_big", BIG + lines, r)
    # ~= with NAN (C# double.Equals(NaN, NaN) is true), length and duplicate mismatch
    for a, b in [("list(NAN)", "list(NAN)"), ('list("a" = NAN)', 'list("a" = NAN)'), ('alist("a" = NAN)', 'alist("a" = NAN)'),
                 ("list(1)", "list(1, 2)"), ("list(1, 2)", "list(1)"), ("list(1, 1, 2)", "list(1, 2, 2)"),
                 ('list("a", "b" = 1)', 'list("a" = 1, "b")'), ("null", "list()"), ("null", "null"),
                 ("alist(1 = NAN)", "alist(1 = NAN)"), ('list("a" = list(1))', 'list("a" = list(1))')]:
        s.case("list_eq", f"({a}) ~= ({b})")
        s.case("list_eq", f"({a}) ~! ({b})")
    s.body("list_eq", ["var/list/L = list(NAN)"], "list(L ~= L, L == L)")
    # Datum operator[] / operator[]= (also used by ?[])
    IX = "var/datum/listops_ix/D = new"
    for lines in [["var/r = D[1]"], ['var/r = D["k"]'], ["var/r = D?[2]"], ["var/r = (D[3] = 5)"],
                  ["var/r = (D[2] += 1)"], ['var/r = (D["k"] += "x")'], ["var/r = D[1]++"], ["var/r = ++D[1]"],
                  ['var/r = D["nest"][2]'], ['D["nest"][2] = 7', "var/r = null"], ["var/r = D[1][2]"],
                  ["D?[3] = 5", "var/r = null"], ["var/X = D", "var/r = X[4]"], ["var/X = D", "X[4] = 1", "var/r = null"],
                  ["var/r = D[list(1)]"], ["var/r = D[null]"], ["var/r = D[1.5]"], ["var/r = (D[1] ||= 3)"]]:
        s.body("datum_index", [IX] + lines, "list(r, D.calls)")
    s.body("datum_index", ["var/datum/listops_ix/D = null"], "D?[2]")
    s.body("datum_index", ["var/datum/listops_ix/D = null", "D?[2] = 1"], "D")
    s.body("datum_index", ["var/datum/listops_ixr/D = new", "D[1] = 5"], "D")
    s.body("datum_index", ["var/datum/listops_ixr/D = new"], "D[7]")
    s.body("datum_index", ["var/X = new /datum/listops_ixr", "X[1] = 5"], "X")
    s.body("datum_index", ["var/datum/D = new"], "D[1]")
    s.body("datum_index", ["var/datum/D = new", "D[1] = 2"], "D")
    # Nested set through a missing or out-of-range outer element
    for init, e, r in [("list(list(1))", "L[3][1] = 9", "L"), ("list(list(1))", "L[2][1] = 9", "L"),
                       ("list(list(1))", "L[0][1] = 9", "L"), ("list()", 'L["missing"]["b"] = 5', "listops_full(L)"),
                       ("list(1)", "L[1][1] = 2", "L"), ('list("abc")', 'L[1][1] = "x"', "L"),
                       ("list(null)", "L[1][1] = 2", "L"), ('list("a" = 3)', 'L["a"]["b"] = 5', "listops_full(L)")]:
        s.body("list_index_set", [f"var/list/L = {init}", e], r)
    # Alias visibility of op= through an index, a key and a field
    for op, name in OPS:
        p = f"list_{name}_assign"
        s.body(p, ["var/list/I = list(1, 2)", "var/list/H = list(I)", f"H[1] {op}= list(2, 3)"], "list(I, H[1] == I, H[1])")
        s.body(p, ["var/list/I = list(1, 2)", 'var/list/H = list("k" = I)', f'H["k"] {op}= list(2, 3)'],
               'list(I, H["k"] == I, H["k"])')
        s.body(p, ["var/datum/listops_f/D = new", f"D.L {op}= 1"], "listops_show(D.L)")
        s.body(p, ["var/datum/listops_f/D = new", "D.L = list(1, 2)", "var/O = D.L", f"D.L {op}= 2"],
               "list(D.L == O, D.L, O)")
        s.body(p, ["var/datum/listops_f/D = new", "D.L = list(1, 2)", "var/O = D.L", f"D.L {op}= list(2, 3)"],
               "list(D.L == O, D.L, O)")
    # Compile-time var initializers (DMObject / DMCodeTree.Vars path)
    for v in "abcdefg":
        s.body("list_init", ["var/datum/listops_init/D = new"], f"listops_show(D.{v})")
        s.body("list_init", ["var/datum/listops_init/D = new"], f"listops_show(initial(D.{v}))")
    s.body("list_init", ["var/datum/listops_init/D = new", "D.a += 4", "var/datum/listops_init/E = new"], "list(D.a, E.a)")
    s.body("list_init", ["var/datum/listops_init/D = new", "var/datum/listops_init/E = new"],
           "list(D.a == E.a, D.e == E.e, D.d == E.d)")
    s.body("list_init", ["var/datum/listops_init/D = new", "D.a += 4"], "initial(D.a)")
    # Named-arg keys: macros and builtin names
    for k in ["LISTOPS_K", "LISTOPS_T", "src", "usr", "args", "global", "step", "world", "loc", "TRUE"]:
        s.case("list_ctor", f"listops_full(list({k} = 1))")
        s.case("alist", f"listops_akv(alist({k} = 1))")
    s.case("list_ctor", 'listops_full(list("a" = 1, a = 2))')
    s.case("list_ctor", 'listops_full(list(a = 1, "a" = 2))')
    s.case("alist", 'listops_akv(alist(a = 1, "a" = 2))')
    s.case("alist", 'listops_akv(alist("a" = 1, a = 2))')
    # arglist() into list() / alist()
    for e in ["list(arglist(list(1, 2)))", 'list(arglist(list("a" = 1, "b")))', "list(arglist(list(1 = 2)))",
              "list(arglist(list()))", "list(arglist(null))"]:
        s.case("list_ctor", f"listops_full({e})")
    for e in ['alist(arglist(list("a" = 1, "b" = 2)))', "alist(arglist(list(1 = 2)))", 'alist(arglist(list("a")))']:
        s.case("alist", f"listops_akv({e})")
    # new /list multi-dim with odd sizes, named args (OD: new DreamList[size * n] unchecked)
    for e in ["new /list(-1, 2)", "new /list(2, -1)", "new /list(2.5, 2)", 'new /list("2", 2)', "new /list(2, null)",
              "new /list(a = 3)", "new /list(-2, -2)", "new /list(0, -1)"]:
        s.case("list_ctor", e)
    s.body("list_ctor", ["var/list/L[2][-1]"], "L")
    s.body("list_ctor", ["var/list/L[-1]"], "L")
    for e in ["new /alist(a = 1)", 'new /alist("a" = 1, "b" = 2)', "new /alist(1 = 2)"]:
        s.case("alist", f"listops_akv({e})")
    # alist null assignment and removal
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1, "b" = 2)', 'A["a"] = null'], 'list(listops_akv(A), "a" in A)')
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1)', 'A["zz"] = null'], 'list(listops_akv(A), "zz" in A)')
    s.body("alist_index_set", ["var/alist/A = alist()", "A[5] = null"], "list(listops_akv(A), 5 in A)")
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1)', "A -= null"], "listops_akv(A)")
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1)', "A += null"], "list(listops_akv(A), null in A)")
    s.body("alist_index_set", ['var/alist/A = alist("a" = 1)', "A += null", "A -= null"], "listops_akv(A)")
    # Deleted datum as item / key
    s.body("list_del", ["var/datum/listops_d/D = new(1)", "var/list/L = list(D, 1)", 'L[D] = "x"', "del(D)"],
           "listops_full(L)")
    s.body("list_del", ["var/datum/listops_d/D = new(1)", "var/list/L = list(D, 1)", "var/datum/E = D", "del(D)"],
           "list(E, listops_full(L - E), L.Find(null))")
    s.body("list_del", ["var/datum/listops_d/D = new(1)", "var/alist/A = alist()", "A[D] = 1", "del(D)"],
           "listops_akv(A)")
    s.body("list_del", ["var/datum/listops_d/D = new(1)", "var/list/L = list(1)", 'L[D] = "x"', "del(D)", 'L[null] = 2'],
           "listops_full(L)")
    # Special lists: vars (OD's DreamListVars has its own Get/SetValue; ElementAt throws out of range)
    DV = "var/datum/listops_d/D = new(1)"
    for lines, r in [(['D.vars["n"] = 5'], "D.n"), (['D.vars["zz"] = 1'], 'list(D.n, "zz" in D.vars)'),
                     (["D.vars[1] = 2"], "list(D.n, D.vars[1])"), (['D.vars += "x"'], 'list(D.n, "x" in D.vars)'),
                     (['D.vars -= "n"'], 'list(D.n, "n" in D.vars)'), (["D.vars.len = 0"], "list(D.n, D.vars.len > 0)"),
                     (['D.vars["n"]++'], "D.n"), (['D.vars["n"] += 2'], "D.n"), (['D.vars["n"] = list(1)'], "D.n"),
                     ([], 'D.vars["n"]'), ([], 'D.vars["zz"]'), ([], '"n" in D.vars'), ([], "D.vars[1000]"),
                     ([], "D.vars[0]"), ([], "D.vars[-1]"), ([], "istext(D.vars[1])"), (['D.vars |= "n"'], "D.n")]:
        s.body("special_vars", [DV] + lines, r)
    # Special lists: args (through helpers so the chunk proc's own args stay untouched)
    s.case("special_args", "listops_args_set(1, 2)")
    s.case("special_args", "listops_args_set(b = 2)")
    s.case("special_args", "listops_args_len(1, 2)")
    s.case("special_args", "listops_args_add(1, 2)")
    s.case("special_args", "listops_args_add()")
    # Pointers to list elements (516)
    for init, lines, r in [
            ("list(1, 2, 3)", ["var/p = &L[2]", "*p = 9"], "L"),
            ("list(1, 2, 3)", ["var/p = &L[2]", "*p += 1"], "L"),
            ("list(1, 2, 3)", ["var/p = &L[2]", "*p *= 10"], "L"),
            ("list(1, 2, 3)", ["var/p = &L[2]"], "*p"),
            ('list("b" = 1)', ['var/p = &L["a"]', "*p = 5"], "listops_full(L)"),
            ('list("b" = 1)', ['var/p = &L["b"]', "*p = 5"], "listops_full(L)"),
            ('list("b" = 1)', ['var/p = &L["a"]'], "list(*p, L.len)"),
            ("list(1, 2, 3)", ["var/p = &L[5]", "*p = 9"], "L"),
            ("list(1, 2, 3)", ["var/p = &L[5]"], "*p"),
            ("list(1, 2, 3)", ["var/p = &L[3]", "L.len = 1"], "*p"),
            ("list(1, 2, 3)", ["var/p = &L[3]", "L.len = 1", "*p = 4"], "L"),
            ("list(1, 2, 3)", ["var/p = &L[2]", "L.Insert(1, 0)"], "*p"),
            ("list(1, 2, 3)", ["var/p = &L[1]"], "ispointer(p)"),
            ("list(1, 2, 3)", ["var/p = &L", "*p += 4"], "L")]:
        s.body("list_pointer", [f"var/list/L = {init}"] + lines, r)
    # len set to huge / infinite values: OD casts through (int), undefined for inf/1e30.
    # These may crash or hang an engine; the runner records SKIP for that.
    for v in ["PINF", "1e30", "16777216.5"]:
        s.body("list_len", ["var/list/L = list(1, 2, 3)", f"L.len = {v}"], "L.len")
    s.case("list_len", "length(new /list(PINF))")
    # Assoc keys of value-like kinds: matched by identity or by value?
    s.body("list_index_set", ["var/list/L = list()", "L[vector(1, 2)] = 1"], "list(L.len, L[vector(1, 2)])")
    s.body("list_index_set", ["var/list/L = list()", "var/vector/V = vector(1, 2)", "L[V] = 1"], "list(L.len, L[V])")
    s.body("list_index_set", ["var/list/L = list()", "L[world] = 1"], "list(L.len, L[world], L[1] == world)")
    s.body("list_index_set", ["var/list/L = list()", "L[global.vars] = 1"], "list(L.len, L[global.vars])")
    s.body("list_index_set", ["var/list/L = list()", "L[pixloc(1, 2, 1)] = 1"], "list(L.len, L[pixloc(1, 2, 1)])")
    s.case("alist", "listops_akv(alist(vector(1, 2) = 1))")
    s.case("alist", "listops_akv(alist((vector(1, 2)) = 1))")
    s.body("alist_index", ["var/alist/A = alist()", "A[vector(1, 2)] = 1"], "list(length(A), A[vector(1, 2)])")
