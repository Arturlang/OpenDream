"""/matrix: matrix() constructor forms (0/1/2/3/4/5/6 args, MATRIX_* opcode forms, MATRIX_MODIFY),
new /matrix, vars a-f, Add, Subtract, Multiply (num and matrix), Invert (incl. singular), Scale,
Translate, Turn, Interpolate, operators (* + - / unary - ~ ~= ~! == and the assignment forms),
turn(matrix, angle), atom.transform round trips.

BYOND reference points targeted here:
- Layout: x' = a*x + b*y + c, y' = d*x + e*y + f; default is identity (1,0,0,0,1,0).
- matrix() / matrix(Matrix) / matrix(a..f) / matrix(x, y, MATRIX_SCALE) / matrix(n, MATRIX_SCALE) /
  matrix(angle, MATRIX_ROTATE) / matrix(x, y, MATRIX_TRANSLATE). Undocumented opcodes (MATRIX_COPY,
  MATRIX_MULTIPLY, MATRIX_ADD, MATRIX_SUBTRACT, MATRIX_INVERT, MATRIX_INTERPOLATE, MATRIX_MODIFY)
  from the 2015 forum post are exercised too, by define and by literal number.
- Add/Subtract/Multiply/Scale/Translate/Turn/Invert return src (mutate in place); Interpolate
  returns a NEW matrix. Multiply(n) is "like scaling the whole matrix". Scale(x)/Translate(x) use x
  for y. Turn is clockwise. Invert of a degenerate matrix leaves it unchanged (no error).
- Operators create new matrices; assignment operators (*=, +=, -=, /=) modify the existing matrix.
  ~M is the inverse. A ~= B is true when components match.
- turn(Matrix, Angle) returns a new rotated matrix (clockwise).
- Interpolate: scale/shear first, then rotation, then translation; 180 degrees counts as a flip.
  t outside 0..1 extrapolates.

OpenDream divergences these cases aim at (DreamObjectMatrix.cs, DreamProcNativeMatrix.cs,
DreamProcNativeRoot.cs NativeProc_matrix, DMOpcodeHandlers.BitNot):
- Invert() of a singular matrix throws in OD (BYOND: unchanged); ~M throws NotImplemented in OD.
- *= and /= on a matrix return a NEW matrix in OD (OperatorMultiplyRef -> OperatorMultiply), so an
  alias of the original keeps the old values; += / -= modify in place.
- matrix() with 2..5 args always treats the last arg as an opcode, so matrix(1, 2, 3) is
  "MATRIX_SUBTRACT"; 1-arg non-matrix throws; 6 args with non-numbers throws.
- Multiply(invalid) zeroes the matrix in OD; Multiply(null) returns src unchanged.
- Turn(non-number) returns src; Scale(non-number) uses 0; Translate(x, "text") uses y=0.
- Translate/Scale/Turn use float32 trig with subnormal flush; Interpolate decomposition is OD's own.
- Operators build plain /matrix (MakeMatrix) even for subtypes; matrix(M) clones keep the subtype.
- ~= compares with float Equals (NaN ~= NaN true in OD; BYOND may differ).
"""
from pools import NUM, NUM_S, OTHER

# Matrices used as src / arguments (DM source, each a fresh matrix)
MAT = [
    "matrix()",
    "matrix(1, 2, 3, 4, 5, 6)",
    "matrix(2, 0, 0, 0, 3, 0)",
    "matrix(0, 0, 0, 0, 0, 0)",
    "matrix(1, 2, 0, 2, 4, 0)",          # singular (det 0), no translation
    "matrix(0, 1, 5, -1, 0, -7)",        # 90 degree rotation plus translation
    "matrix(0.5, 0.25, -3, 1.5, -2, 10)",
    "matrix(-1, 0, 0, 0, -1, 0)",        # 180 degree rotation / double flip
    "matrix(-1, 0, 4, 0, 1, 0)",         # horizontal mirror
    "matrix(1, 0, 0, 0, 0, 0)",          # b = e = 0 (OD's "degenerate" interpolation path)
    "matrix(1, 2, 3, 2, 4, 6)",          # singular with translation
]
MAT_S = MAT[:6]
# Matrices plus wrong-type arguments
MAT_ARG = MAT[:8] + OTHER + ["2", "-1", "0", "0.5", '"2"', "NAN", "matrix_sub_make()"]
# Numbers for Scale / Translate / Multiply(n)
SCALAR = NUM + ["null", '"2"', "list()", "new /datum", "matrix()"]
SCALAR_S = NUM_S + ["null", '"2"', "NAN", "PINF", "list()"]
# Angles in degrees
ANGLE = ["0", "90", "45", "180", "270", "360", "-90", "-45", "30", "60", "0.5", "-0.5", "720", "450",
         "1e7", "123.456", "-360", "135", "PINF", "NAN", "null", '"90"', "list()", "new /datum"]
ANGLE_S = ["0", "90", "45", "-90", "180", "360", "30", "null"]
# Interpolation factors
T = ["0", "1", "0.5", "0.25", "-1", "2", "0.1", "null", "NAN", '"0.5"']
T_S = ["0", "0.5", "1", "2", "-0.5"]


def build(s):
    s.dm("""/matrix/matrix_sub
	var/matrix_tag = "sub"

/matrix/matrix_newlog
	var/list/matrix_seen

/matrix/matrix_newlog/New(a, b, c, d, e, f)
	matrix_seen = args.Copy()
	..()

/proc/matrix_sub_make()
	return new /matrix/matrix_sub(2, 0, 1, 0, 2, 1)

// Return value, src after the call, and whether the return value is src itself
/proc/matrix_res(r, matrix/M)
	return list("r" = r, "src" = M, "same" = (r == M))

// Components as raw values (non-numbers survive), for var assignment checks
/proc/matrix_vars(matrix/M)
	return list(M.a, M.b, M.c, M.d, M.e, M.f)

// Apply a matrix to point (x, y), the documented layout
/proc/matrix_apply(matrix/M, x, y)
	return list(M.a * x + M.b * y + M.c, M.d * x + M.e * y + M.f)

// Components rounded to 1e-4, to compare trig results without float noise
/proc/matrix_round(matrix/M)
	return list(round(M.a, 0.0001), round(M.b, 0.0001), round(M.c, 0.0001), round(M.d, 0.0001), round(M.e, 0.0001), round(M.f, 0.0001))""")

    # ================= matrix() constructor =================
    s.case("matrix", "matrix()")
    s.case("matrix", "new /matrix")
    s.case("matrix", "new /matrix()")
    s.case("matrix", "matrix_vars(matrix())")
    # One argument: a matrix copies, anything else is undocumented
    s.sweep("matrix", [MAT + NUM_S + OTHER + ['"abc"', "matrix_sub_make()"]])
    for m in MAT[:4] + ["matrix_sub_make()"]:
        s.case("matrix", f"new /matrix({m})")
    # The copy is a different object with the same components
    s.body("matrix", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/C = matrix(M)", "C.a = 99"], "list(M, C, M == C)")
    s.body("matrix", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/C = new /matrix(M)", "C.Scale(2)"], "list(M, C, M == C)")
    s.case("matrix", "matrix(matrix_sub_make()).type")
    s.case("matrix", "matrix(matrix()).type")
    # Six arguments: every position over a small pool (all-pairs)
    SIX = ["0", "1", "-2", "0.5", "1e7", "NAN", "PINF", "null", '"3"', "list()"]
    s.sweep("matrix", [SIX] * 6)
    s.sweep("matrix", [["1", "0.5", "null", '"3"', "list()"]] * 6, fmt=lambda *a: f"new /matrix({', '.join(a)})")
    s.case("matrix", "matrix(1, 2, 3, 4, 5, 6).type")
    s.case("matrix", "matrix(a = 1, b = 2, c = 3, d = 4, e = 5, f = 6)")
    s.case("matrix", "matrix(f = 6, e = 5, d = 4, c = 3, b = 2, a = 1)")
    s.case("matrix", "matrix(1, 2, 3, 4, 5, 6, 7)")
    s.case("matrix", "matrix(1, 2, 3, 4, 5, 6, 7, 8)")
    s.case("matrix", "matrix(1, 2, 3, 4, 5, null)")
    s.case("matrix", "matrix(null, null, null, null, null, null)")
    s.case("matrix", "matrix(null)")
    # Two to five plain numbers (the last one doubles as an opcode in the undocumented forms)
    for args in ["1, 2", "2, 3", "1, 2, 3", "1, 2, 4", "1, 2, 0", "1, 2, 3, 4", "1, 2, 3, 5", "1, 2, 3, 4, 5",
                 "1, 2, 3, 4, 6", "0, 0", "2, 100", "2, 9", "2, 128", "2, 64", "2, 0.5", "2, -1",
                 "2, null", "null, 6", '2, "6"', "2, 6.5", "2, 134", "2, 133", "2, 135"]:
        s.case("matrix", f"matrix({args})")
    s.case("matrix", "new /matrix(1, 2)")
    s.case("matrix", "new /matrix(2, MATRIX_SCALE)")
    s.case("matrix", "new /matrix(1, 2, 3)")
    s.case("matrix", "new /matrix(1, 2, 3, 4, 5)")

    # --- documented shortcut forms ---
    s.case("matrix", "MATRIX_SCALE")
    s.case("matrix", "MATRIX_ROTATE")
    s.case("matrix", "MATRIX_TRANSLATE")
    s.case("matrix", "list(MATRIX_COPY, MATRIX_MULTIPLY, MATRIX_ADD, MATRIX_SUBTRACT, MATRIX_INVERT, MATRIX_INTERPOLATE, MATRIX_MODIFY)")
    s.sweep("matrix", [SCALAR], fmt=lambda n: f"matrix({n}, MATRIX_SCALE)")
    s.sweep("matrix", [SCALAR_S, SCALAR_S], fmt=lambda x, y: f"matrix({x}, {y}, MATRIX_SCALE)")
    s.sweep("matrix", [ANGLE], fmt=lambda a: f"matrix({a}, MATRIX_ROTATE)")
    s.sweep("matrix", [ANGLE], fmt=lambda a: f"matrix_round(matrix({a}, MATRIX_ROTATE))")
    s.sweep("matrix", [SCALAR_S, SCALAR_S], fmt=lambda x, y: f"matrix({x}, {y}, MATRIX_TRANSLATE)")
    s.sweep("matrix", [SCALAR_S], fmt=lambda x: f"matrix({x}, MATRIX_TRANSLATE)")
    # Rotation is clockwise: (0, 1) rotated 90 goes to (1, 0)
    s.case("matrix", "matrix_round(matrix_apply(matrix(90, MATRIX_ROTATE), 0, 1))")
    s.case("matrix", "matrix_apply(matrix(3, 4, MATRIX_TRANSLATE), 1, 1)")
    s.case("matrix", "matrix_apply(matrix(2, 5, MATRIX_SCALE), 1, 1)")

    # --- undocumented opcode forms on an existing matrix ---
    for m in MAT_S:
        s.case("matrix", f"matrix({m}, 2, MATRIX_SCALE)")
        s.case("matrix", f"matrix({m}, 2, 3, MATRIX_SCALE)")
        s.case("matrix", f"matrix({m}, 90, MATRIX_ROTATE)")
        s.case("matrix", f"matrix_round(matrix({m}, 45, MATRIX_ROTATE))")
        s.case("matrix", f"matrix({m}, 2, 3, MATRIX_TRANSLATE)")
        s.case("matrix", f"matrix({m}, MATRIX_COPY)")
        s.case("matrix", f"matrix({m}, MATRIX_INVERT)")
        s.case("matrix", f"matrix({m}, matrix(1, 2, 3, 4, 5, 6), MATRIX_MULTIPLY)")
        s.case("matrix", f"matrix({m}, 3, MATRIX_MULTIPLY)")
        s.case("matrix", f"matrix({m}, matrix(1, 2, 3, 4, 5, 6), MATRIX_ADD)")
        s.case("matrix", f"matrix({m}, matrix(1, 2, 3, 4, 5, 6), MATRIX_SUBTRACT)")
        s.case("matrix", f"matrix({m}, matrix(2, 0, 4, 0, 2, 6), 0.5, MATRIX_INTERPOLATE)")
    # Opcodes by literal number, unknown opcodes, and MATRIX_MODIFY combinations
    for op in range(0, 10):
        s.case("matrix", f"matrix(matrix(1, 2, 3, 4, 5, 6), {op})")
        s.case("matrix", f"matrix(matrix(1, 2, 3, 4, 5, 6), 2, {op})")
        s.case("matrix", f"matrix(matrix(1, 2, 3, 4, 5, 6), matrix(2, 0, 0, 0, 2, 0), {op})")
    for op in ["MATRIX_SCALE", "MATRIX_ROTATE", "MATRIX_TRANSLATE", "MATRIX_INVERT", "MATRIX_COPY",
               "MATRIX_MULTIPLY", "MATRIX_ADD", "MATRIX_SUBTRACT", "MATRIX_INTERPOLATE"]:
        if op in ("MATRIX_MULTIPLY", "MATRIX_ADD", "MATRIX_SUBTRACT"):
            call = f"matrix(M, matrix(2, 0, 1, 0, 2, 1), {op} | MATRIX_MODIFY)"
        elif op == "MATRIX_INTERPOLATE":
            call = f"matrix(M, matrix(2, 0, 1, 0, 2, 1), 0.5, {op} | MATRIX_MODIFY)"
        elif op in ("MATRIX_INVERT", "MATRIX_COPY"):
            call = f"matrix(M, {op} | MATRIX_MODIFY)"
        elif op == "MATRIX_TRANSLATE":
            call = f"matrix(M, 2, 3, {op} | MATRIX_MODIFY)"
        else:
            call = f"matrix(M, 2, {op} | MATRIX_MODIFY)"
        s.body("matrix", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = {call}"], "matrix_res(R, M)")
        # Without MATRIX_MODIFY the source must stay the same
        s.body("matrix", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = {call.replace(' | MATRIX_MODIFY', '')}"], "matrix_res(R, M)")
    # Wrong-type arguments to the opcode forms
    for args in ['"x", MATRIX_SCALE', "list(), MATRIX_SCALE", "null, MATRIX_SCALE", "new /datum, MATRIX_ROTATE",
                 '"x", MATRIX_ROTATE', "null, MATRIX_ROTATE", '"a", "b", MATRIX_TRANSLATE', "null, null, MATRIX_TRANSLATE",
                 "2, MATRIX_INVERT", "null, MATRIX_INVERT", "2, MATRIX_COPY", "2, 3, MATRIX_MULTIPLY",
                 "matrix(), null, MATRIX_SCALE", 'matrix(), "x", MATRIX_SCALE', "matrix(), null, MATRIX_ROTATE",
                 "matrix(), null, null, MATRIX_TRANSLATE", "matrix(), matrix(), null, MATRIX_INTERPOLATE",
                 "matrix(), 2, 0.5, MATRIX_INTERPOLATE", "2, matrix(), MATRIX_ADD", "matrix(), null, MATRIX_ADD",
                 "matrix(2, 0, 0, 0, 2, 0), null, MATRIX_MULTIPLY", "matrix(1, 2, 0, 2, 4, 0), MATRIX_INVERT",
                 "matrix(0, 0, 0, 0, 0, 0), MATRIX_INVERT", "matrix(), 2, \"3\"", "matrix(), 2, null",
                 "matrix(), 2, MATRIX_SCALE | 256", "matrix(), 2, MATRIX_SCALE + 0.5"]:
        s.case("matrix", f"matrix({args})")

    # ================= vars a-f =================
    for v in "abcdef":
        s.case("matrix_vars", f"matrix(1, 2, 3, 4, 5, 6).{v}")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.{v} = 7"], "M")
    VAL = ["7", "-2.5", "0", "1e30", "NAN", "PINF", "null", '"5"', '"abc"', "list(1)", "new /datum", "/datum"]
    for val in VAL:
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.a = {val}"], "matrix_vars(M)")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.c = {val}"], "matrix_vars(M)")
        # Then use the matrix
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.a = {val}", "M.Scale(2)"], "matrix_vars(M)")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.e = {val}"], "M * 2")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.f = {val}"], "M + matrix()")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.b = {val}"], "matrix(M)")
        s.body("matrix_vars", ["var/matrix/M = matrix()", f"M.d = {val}"], "M ~= matrix()")
    s.body("matrix_vars", ["var/matrix/M = matrix()", "M.a += 3", "M.b -= 2", "M.c *= 5", "M.f++"], "M")
    s.body("matrix_vars", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)"], 'list(M.vars["a"], M.vars["f"], ("e" in M.vars))')
    s.body("matrix_vars", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", 'M.vars["b"] = 9'], "M")
    s.case("matrix_vars", "initial(matrix(1, 2, 3, 4, 5, 6).a)")
    s.body("matrix_vars", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)"], "issaved(M.a)")
    s.case("matrix_vars", '"[matrix()]"')
    s.case("matrix_vars", '"[matrix_sub_make()]"')
    s.case("matrix_vars", "istype(matrix(), /matrix)")
    s.case("matrix_vars", "istype(matrix(), /datum)")
    s.case("matrix_vars", "isnum(matrix())")
    s.case("matrix_vars", "islist(matrix())")
    s.case("matrix_vars", "matrix().type")
    s.case("matrix_vars", "matrix().parent_type")
    s.case("matrix_vars", "json_encode(matrix(1, 2, 3, 4, 5, 6))")
    s.case("matrix_vars", "json_encode(list(matrix(1, 2.5, 3, 4, 5, 6)))")
    s.case("matrix_vars", "matrix_sub_make().matrix_tag")
    s.case("matrix_vars", "new /matrix/matrix_sub")
    s.case("matrix_vars", "new /matrix/matrix_sub(1, 2, 3, 4, 5, 6)")
    s.body("matrix_vars", ["var/matrix/matrix_newlog/M = new(1, 2, 3, 4, 5, 6)"], "list(M, M.matrix_seen)")
    s.body("matrix_vars", ["var/matrix/matrix_newlog/M = new(2, MATRIX_SCALE)"], "list(M, M.matrix_seen)")
    s.body("matrix_vars", ["var/matrix/matrix_newlog/M = new()"], "list(M, M.matrix_seen)")
    s.body("matrix_vars", ["var/matrix/matrix_newlog/M = new(matrix(1, 2, 3, 4, 5, 6))"], "list(M, M.matrix_seen)")

    # ================= Add / Subtract =================
    for p in ("Add", "Subtract"):
        for m in MAT_S:
            for a in MAT_ARG:
                s.body(p, [f"var/matrix/M = {m}", f"var/R = M.{p}({a})"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}()"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(M)"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(Matrix2 = matrix(1, 1, 1, 1, 1, 1))"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(matrix(), matrix())"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/N = matrix(1, 1, 1, 1, 1, 1)", f"M.{p}(N)"], "list(M, N)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"M.{p}(matrix(PINF, NAN, 0, 0, 0, 0))"], "M")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(list(1, 1, 1, 1, 1, 1))"], "matrix_res(R, M)")

    # ================= Multiply =================
    for m in MAT_S:
        for a in MAT_ARG + ["1e7", "PINF", "NINF", "-0.5", "1e-7"]:
            s.body("Multiply", [f"var/matrix/M = {m}", f"var/R = M.Multiply({a})"], "matrix_res(R, M)")
    # Order: src then Matrix2 (scale then translate vs translate then scale)
    s.body("Multiply", ["var/matrix/M = matrix(2, MATRIX_SCALE)", "M.Multiply(matrix(5, 7, MATRIX_TRANSLATE))"], "M")
    s.body("Multiply", ["var/matrix/M = matrix(5, 7, MATRIX_TRANSLATE)", "M.Multiply(matrix(2, MATRIX_SCALE))"], "M")
    s.body("Multiply", ["var/matrix/M = matrix(90, MATRIX_ROTATE)", "M.Multiply(matrix(3, 0, MATRIX_TRANSLATE))"], "matrix_round(M)")
    s.body("Multiply", ["var/matrix/M = matrix(3, 0, MATRIX_TRANSLATE)", "M.Multiply(matrix(90, MATRIX_ROTATE))"], "matrix_round(M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(M)"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply()"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(2, 3)"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(list(2, 0, 0, 0, 2, 0))"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/N = matrix(2, 0, 1, 0, 2, 1)", "M.Multiply(N)"], "list(M, N)")
    # Multiply(n) vs Scale(n): documented to be alike
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/N = matrix(1, 2, 3, 4, 5, 6)", "M.Multiply(3)", "N.Scale(3)"], "M ~= N")

    # ================= Invert =================
    for m in MAT + ["matrix(1e-20, 0, 0, 0, 1e-20, 0)", "matrix(1e20, 0, 5, 0, 1e20, 5)", "matrix(4, 0, 0, 0, 0.5, 0)",
                    "matrix(0, 0, 3, 0, 0, 4)", "matrix(1, 1, 0, 1, 1, 0)", "matrix(NAN, 0, 0, 0, 1, 0)",
                    "matrix(PINF, 0, 0, 0, 1, 0)", "matrix(2, 1, 3, 1, 1, 2)", "matrix(3, 0, 0, 0, 3, 0) * matrix(45, MATRIX_ROTATE)",
                    "matrix_sub_make()"]:
        s.body("Invert", [f"var/matrix/M = {m}", "var/R = M.Invert()"], "matrix_res(R, M)")
        s.case("Invert", f"~({m})")
    # Inverting twice restores; M * ~M is identity
    s.body("Invert", ["var/matrix/M = matrix(2, 1, 3, 1, 1, 2)", "M.Invert()", "M.Invert()"], "M")
    s.body("Invert", ["var/matrix/M = matrix(2, 1, 3, 1, 1, 2)"], "M * ~M")
    s.body("Invert", ["var/matrix/M = matrix(2, 1, 3, 1, 1, 2)", "var/matrix/I = ~M"], "list(M, I, M == I)")
    s.body("Invert", ["var/matrix/M = matrix(2, 1, 3, 1, 1, 2)", "var/R = M.Invert(5)"], "matrix_res(R, M)")
    s.body("Invert", ["var/matrix/M = matrix(30, MATRIX_ROTATE)", "M.Invert()"], "matrix_round(M)")
    s.body("Invert", ["var/matrix/M = matrix(2, 1, 3, 1, 1, 2)", "var/list/p = matrix_apply(M, 3, 4)", "M.Invert()"], "matrix_apply(M, p[1], p[2])")

    # ================= Scale / Translate =================
    for p in ("Scale", "Translate"):
        for m in ["matrix()", "matrix(1, 2, 3, 4, 5, 6)", "matrix(0, 1, 5, -1, 0, -7)"]:
            s.sweep(p, [SCALAR], fmt=lambda x, m=m, p=p: f"({m}).{p}({x})")
            if m == "matrix(1, 2, 3, 4, 5, 6)":
                s.sweep(p, [SCALAR_S, SCALAR_S], fmt=lambda x, y, m=m, p=p: f"({m}).{p}({x}, {y})")
            s.body(p, [f"var/matrix/M = {m}", f"var/R = M.{p}()"], "matrix_res(R, M)")
            s.body(p, [f"var/matrix/M = {m}", f"var/R = M.{p}(2, 3)"], "matrix_res(R, M)")
            s.body(p, [f"var/matrix/M = {m}", f"var/R = M.{p}(2)"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(x = 2, y = 3)"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(y = 3)"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = M.{p}(2, 3, 4)"], "matrix_res(R, M)")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"M.{p}(2, 3)", f"M.{p}(0.5)"], "M")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"M.{p}(2, null)"], "M")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"M.{p}(null, 2)"], "M")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f'M.{p}(2, "3")'], "M")
        s.body(p, ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f'M.{p}("2", 3)'], "M")
    # Translation is in pixels after the existing transform; Scale scales the translation too
    s.body("Translate", ["var/matrix/M = matrix(2, MATRIX_SCALE)", "M.Translate(3, 4)"], "matrix_apply(M, 1, 1)")
    s.body("Scale", ["var/matrix/M = matrix(3, 4, MATRIX_TRANSLATE)", "M.Scale(2)"], "matrix_apply(M, 1, 1)")

    # ================= Turn =================
    for m in ["matrix()", "matrix(1, 2, 3, 4, 5, 6)", "matrix(2, 0, 4, 0, 3, 5)"]:
        for a in ANGLE:
            s.body("Turn", [f"var/matrix/M = {m}", f"var/R = M.Turn({a})"], "matrix_res(R, M)")
            s.body("Turn", [f"var/matrix/M = {m}", f"M.Turn({a})"], "matrix_round(M)")
    s.body("Turn", ["var/matrix/M = matrix()", "var/R = M.Turn()"], "matrix_res(R, M)")
    s.body("Turn", ["var/matrix/M = matrix()", "var/R = M.Turn(angle = 90)"], "matrix_res(R, M)")
    s.body("Turn", ["var/matrix/M = matrix()", "var/R = M.Turn(90, 90)"], "matrix_res(R, M)")
    s.body("Turn", ["var/matrix/M = matrix()", "M.Turn(45)", "M.Turn(45)"], "matrix_round(M)")
    s.body("Turn", ["var/matrix/M = matrix()", "for(var/i in 1 to 8)", "\tM.Turn(45)"], "matrix_round(M)")
    s.body("Turn", ["var/matrix/M = matrix()", "for(var/i in 1 to 4)", "\tM.Turn(90)"], "M")
    s.body("Turn", ["var/matrix/M = matrix()", "M.Turn(90)"], "matrix_round(matrix_apply(M, 0, 1))")
    s.body("Turn", ["var/matrix/M = matrix()", "M.Turn(90)"], "matrix_round(matrix_apply(M, 1, 0))")
    s.body("Turn", ["var/matrix/M = matrix(5, 0, MATRIX_TRANSLATE)", "M.Turn(90)"], "matrix_round(M)")
    s.body("Turn", ["var/matrix/M = matrix()", "M.Turn(90)"], "M ~= matrix(90, MATRIX_ROTATE)")

    # ================= Interpolate =================
    INT_M = ["matrix()", "matrix(2, 0, 0, 0, 2, 0)", "matrix(0, 1, 5, -1, 0, -7)", "matrix(-1, 0, 0, 0, -1, 0)",
             "matrix(-1, 0, 4, 0, 1, 0)", "matrix(1, 0, 0, 0, 0, 0)", "matrix(1, 2, 3, 4, 5, 6)",
             "matrix(0, 0, 0, 0, 0, 0)", "matrix(45, MATRIX_ROTATE)"]
    s.sweep("Interpolate", [INT_M, INT_M, T_S], fmt=lambda a, b, t: f"matrix_round(({a}).Interpolate({b}, {t}))")
    for a in INT_M[:4]:
        for t in T:
            s.case("Interpolate", f"({a}).Interpolate(matrix(1, 2, 3, 4, 5, 6), {t})")
    for b in MAT_ARG:
        s.case("Interpolate", f"matrix(2, 0, 1, 0, 2, 1).Interpolate({b}, 0.5)")
    # Returns a new matrix; neither input changes
    s.body("Interpolate", ["var/matrix/A = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/B = matrix(2, 0, 1, 0, 2, 1)",
                           "var/matrix/R = A.Interpolate(B, 0.5)"], "list(R, A, B, R == A, R == B)")
    s.body("Interpolate", ["var/matrix/A = matrix(1, 2, 3, 4, 5, 6)", "var/R = A.Interpolate(A, 0.5)"], "list(R, A, R == A)")
    s.case("Interpolate", "matrix(1, 2, 3, 4, 5, 6).Interpolate(matrix())")
    s.case("Interpolate", "matrix(1, 2, 3, 4, 5, 6).Interpolate()")
    s.case("Interpolate", "matrix(1, 2, 3, 4, 5, 6).Interpolate(t = 0.5, Matrix2 = matrix())")
    s.case("Interpolate", "matrix_sub_make().Interpolate(matrix(), 0.5).type")
    # Rotation interpolation: 0 -> 90 halfway is 45; 0 -> 270 goes the short way; 180 is a flip
    for (a, b) in [(0, 90), (0, 270), (0, 180), (90, 0), (30, 330), (0, 135), (-90, 90), (10, 350), (0, 179), (0, 181)]:
        for t in ("0.5", "0.25", "2"):
            s.case("Interpolate", f"matrix_round(matrix({a}, MATRIX_ROTATE).Interpolate(matrix({b}, MATRIX_ROTATE), {t}))")
    s.case("Interpolate", "matrix_round(matrix(2, MATRIX_SCALE).Interpolate(matrix(90, MATRIX_ROTATE), 0.5))")
    s.case("Interpolate", "matrix_round(matrix(2, 3, MATRIX_SCALE).Interpolate(matrix(4, 1, MATRIX_SCALE) * matrix(60, MATRIX_ROTATE), 0.5))")
    s.case("Interpolate", "matrix_round(matrix(1, 1, 0, 0, 1, 0).Interpolate(matrix(), 0.5))")
    s.case("Interpolate", "matrix_round(matrix(10, 20, MATRIX_TRANSLATE).Interpolate(matrix(90, MATRIX_ROTATE) * matrix(-10, 0, MATRIX_TRANSLATE), 0.5))")

    # ================= operators =================
    OP_L = ["matrix(1, 2, 3, 4, 5, 6)", "matrix(2, 0, 1, 0, 2, 1)", "matrix(1, 2, 0, 2, 4, 0)", "matrix()"]
    OP_R = OP_L + ["2", "0", "-1", "0.5", "PINF", "NAN", "null", '"2"', "list(1, 2, 3, 4, 5, 6)", "new /datum", "matrix_sub_make()"]
    for op in ["*", "/", "+", "-"]:
        for l in OP_L:
            for r in OP_R:
                s.case(f"op{op}", f"({l}) {op} ({r})")
        # Number or non-matrix on the left
        for l in ["2", "0", "null", '"2"', "list(1, 2)", "PINF"]:
            s.case(f"op{op}", f"({l}) {op} matrix(1, 2, 3, 4, 5, 6)")
        # A new matrix, inputs untouched
        s.body(f"op{op}", ["var/matrix/A = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/B = matrix(2, 0, 1, 0, 2, 1)",
                           f"var/matrix/R = A {op} B"], "list(R, A, B, R == A, R == B)")
        s.body(f"op{op}", ["var/matrix/A = matrix(1, 2, 3, 4, 5, 6)", f"var/matrix/R = A {op} 2"], "list(R, A, R == A)")
        s.case(f"op{op}", f"(matrix_sub_make() {op} matrix()).type")
        s.case(f"op{op}", f"(matrix_sub_make() {op} 2).type")
        # Assignment forms modify the existing matrix (an alias sees the change)
        for r in ["matrix(2, 0, 1, 0, 2, 1)", "2", "null", '"2"', "matrix(1, 2, 0, 2, 4, 0)", "list(1, 2, 3, 4, 5, 6)"]:
            s.body(f"op{op}=", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/A = M", f"M {op}= {r}"],
                   "list(M, A, M == A)")
        s.body(f"op{op}=", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"var/R = (M {op}= matrix(2, 0, 1, 0, 2, 1))"],
               "list(R, M, R == M)")
        s.body(f"op{op}=", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", f"M {op}= M"], "M")
        s.body(f"op{op}=", ["var/M = 2", f"M {op}= matrix(1, 2, 3, 4, 5, 6)"], "M")
        s.body(f"op{op}=", ["var/M = null", f"M {op}= matrix(1, 2, 3, 4, 5, 6)"], "M")
    # Multiplication order: A * B is A then B
    s.case("op*", "matrix(2, MATRIX_SCALE) * matrix(5, 7, MATRIX_TRANSLATE)")
    s.case("op*", "matrix(5, 7, MATRIX_TRANSLATE) * matrix(2, MATRIX_SCALE)")
    s.case("op*", "matrix_round(matrix(90, MATRIX_ROTATE) * matrix(90, MATRIX_ROTATE))")
    s.case("op*", "(matrix(1, 2, 3, 4, 5, 6) * matrix(2, 0, 1, 0, 2, 1)) ~= matrix(1, 2, 3, 4, 5, 6).Multiply(matrix(2, 0, 1, 0, 2, 1))")
    s.case("op/", "matrix(2, 1, 3, 1, 1, 2) / matrix(2, 1, 3, 1, 1, 2)")
    s.case("op/", "matrix(1, 2, 3, 4, 5, 6) / matrix(0, 0, 0, 0, 0, 0)")
    # Unary and other operators
    for m in ["matrix(1, 2, 3, 4, 5, 6)", "matrix()", "matrix(0, 0, 0, 0, 0, 0)", "matrix(1, 2, 0, 2, 4, 0)"]:
        for e in ["-({m})", "!({m})", "~({m})", "({m}) % 2", "({m}) ** 2", "({m}) & 1", "({m}) | 1", "({m}) ^ 1",
                  "({m}) << 1", "({m}) > matrix()", "({m}) < 2", "({m}) == ({m})", "({m}) != ({m})",
                  "({m}) && 1", "isnull({m})", "({m}) in list()", "max({m})"]:
            s.case("op_other", e.format(m=m))
    s.body("op_other", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/N = -M"], "list(M, N, M == N)")
    s.body("op_other", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "M++"], "M")
    s.body("op_other", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "M %= 2"], "M")
    s.body("op_other", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/A = M", "M = M * 2"], "list(M, A, M == A)")

    # ================= ~= and ~! =================
    EQ = ["matrix(1, 2, 3, 4, 5, 6)", "matrix()", "matrix(1, 2, 3, 4, 5, 6.0001)", "matrix(NAN, 0, 0, 0, 1, 0)",
          "matrix(0, 0, 0, 0, 0, 0)", "matrix_sub_make()", "matrix(2, 0, 1, 0, 2, 1)",
          "list(1, 2, 3, 4, 5, 6)", "list(1, 0, 0, 0, 1, 0)", "null", "1", "0", '"1"', "new /datum"]
    for l in EQ[:7]:
        for r in EQ:
            s.case("op~=", f"({l}) ~= ({r})")
    for r in EQ:
        s.case("op~!", f"matrix(1, 2, 3, 4, 5, 6) ~! ({r})")
        s.case("op~=", f"({r}) ~= matrix(1, 2, 3, 4, 5, 6)")
    s.case("op~=", "matrix(90, MATRIX_ROTATE) ~= matrix(0, 1, 0, -1, 0, 0)")
    s.case("op~=", "matrix(0.1, 0, 0, 0, 1, 0) * 3 ~= matrix(0.3, 0, 0, 0, 3, 0)")
    s.case("op~=", "matrix(-0, 0, 0, 0, 1, 0) ~= matrix(0, 0, 0, 0, 1, 0)")
    s.body("op~=", ["var/matrix/M = matrix()"], "M ~= M")
    s.body("op~=", ["var/matrix/M = matrix()", "M.a = \"1\""], "M ~= matrix()")
    s.case("op~=", "matrix() == matrix()")

    # ================= turn(matrix, angle) =================
    for m in ["matrix()", "matrix(1, 2, 3, 4, 5, 6)", "matrix(2, 0, 4, 0, 3, 5)", "matrix(0, 0, 0, 0, 0, 0)", "matrix_sub_make()"]:
        for a in ANGLE:
            s.case("turn", f"turn({m}, {a})")
    for a in ANGLE:
        s.case("turn", f"matrix_round(turn(matrix(), {a}))")
    s.body("turn", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/R = turn(M, 90)"], "list(R, M, R == M)")
    s.case("turn", "turn(matrix_sub_make(), 90).type")
    s.case("turn", "turn(matrix(), 90) ~= matrix().Turn(90)")
    s.case("turn", "turn(matrix(), 90) ~= matrix(90, MATRIX_ROTATE)")
    s.case("turn", "matrix_round(matrix_apply(turn(matrix(), 90), 0, 1))")
    s.case("turn", "turn(matrix())")
    s.case("turn", "turn(Dir = matrix(), Angle = 90)")

    # ================= atom.transform =================
    O = "var/obj/O = parity_track(new /obj(locate(1, 1, 1)))"
    s.body("transform", [O], "O.transform")
    for v in ["matrix(1, 2, 3, 4, 5, 6)", "list(1, 2, 3, 4, 5, 6)", "null", "matrix(90, MATRIX_ROTATE)",
              "list(1, 2, 3)", "list()", "5", '"x"', "matrix_sub_make()", "list(1, 2, 3, 4, 5, 6, 7)", "new /datum"]:
        s.body("transform", [O, f"O.transform = {v}"], "O.transform")
    s.body("transform", [O, "var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "O.transform = M", "M.Scale(2)"], "list(O.transform, M)")
    s.body("transform", [O, "var/matrix/M = O.transform", "M.Scale(2)"], "list(O.transform, M)")
    s.body("transform", [O, "var/matrix/M = O.transform"], "M == O.transform")
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "O.transform *= 2"], "O.transform")
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "O.transform += matrix()"], "O.transform")
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "O.transform -= matrix()"], "O.transform")
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "O.transform /= 2"], "O.transform")
    s.body("transform", [O, "O.transform = turn(O.transform, 90)"], "matrix_round(O.transform)")
    s.body("transform", [O, "O.transform = matrix_sub_make()"], "O.transform.type")
    s.body("transform", [O, "O.transform = matrix(NAN, PINF, 0, 0, 1, 0)"], "O.transform")
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)"], "O.appearance.transform")
    s.body("transform", [O, "var/matrix/M = matrix()", 'M.a = "abc"', "O.transform = M"], "O.transform")

    build_gaps(s, O)


def build_gaps(s, O):
    # ================= subtypes with operator overloads / proc overrides =================
    s.dm("""/matrix/matrix_ovl
	var/matrix_last

/matrix/matrix_ovl/operator*(x)
	return "ovl*"

/matrix/matrix_ovl/operator+(x)
	return "ovl+"

/matrix/matrix_ovl/operator-(x)
	if(isnull(x))
		return "ovl-unary"
	return "ovl-"

/matrix/matrix_ovl/operator~=(x)
	return "ovl~="

/matrix/matrix_ovl/operator*=(x)
	matrix_last = "ovl*=[x]"

/matrix/matrix_ovr
	var/list/matrix_mark

/matrix/matrix_ovr/New()
	matrix_mark = list()
	..()

/matrix/matrix_ovr/Scale(x, y)
	matrix_mark += "Scale"
	return ..()

/matrix/matrix_ovr/Turn(angle)
	matrix_mark += "Turn"
	return ..()

/matrix/matrix_ovr/Multiply(m)
	matrix_mark += "Multiply"
	return ..()

/matrix/matrix_noinit/New(a, b, c, d, e, f)
	return

/matrix/matrix_set9/New(a, b, c, d, e, f)
	..()
	src.a = 9

/datum/matrix_holder
	var/matrix/mvar
""")
    OVL = "var/matrix/matrix_ovl/M = new /matrix/matrix_ovl"
    s.body("overload", [OVL], "M * 2")
    s.body("overload", [OVL], "M * matrix()")
    s.body("overload", [OVL], "M + matrix()")
    s.body("overload", [OVL], "M - matrix()")
    s.body("overload", [OVL], "M ~= matrix()")
    s.body("overload", [OVL], "M ~= M")
    s.body("overload", [OVL], "-M")
    s.body("overload", [OVL, "var/matrix/A = M", "M *= 2"], "list(M, A, M == A, A:matrix_last)")
    s.body("overload", [OVL], "2 * M")
    s.body("overload", [OVL], "matrix() * M")
    s.body("overload", [OVL], "M / 2")
    s.body("overload", [OVL, "M.Scale(2)"], "M")

    OVR = "var/matrix/matrix_ovr/M = new /matrix/matrix_ovr"
    s.body("override", [OVR, "var/R = M.Scale(2)"], "list(R, M, R == M, M.matrix_mark)")
    s.body("override", [OVR, "var/R = M.Turn(90)"], "list(matrix_round(R), M.matrix_mark)")
    s.body("override", [OVR, "var/R = turn(M, 90)"], "list(matrix_round(R), M.matrix_mark, R == M)")
    s.body("override", [OVR, "var/A = M", "M *= 2"], "list(M, A, M == A, A:matrix_mark)")
    s.body("override", [OVR, "var/A = M", "M *= matrix(2, 0, 0, 0, 2, 0)"], "list(M, A, A:matrix_mark)")
    s.body("override", [OVR, "var/R = M * 2"], "list(R, M.matrix_mark)")
    s.body("override", [OVR, "var/R = M.Multiply(3)"], "list(R, M.matrix_mark)")
    s.body("override", [OVR, "var/R = matrix(M, 2, MATRIX_SCALE | MATRIX_MODIFY)"], "list(R, M.matrix_mark)")
    s.body("override", [OVR, "var/R = matrix(M, 90, MATRIX_ROTATE | MATRIX_MODIFY)"], "list(matrix_round(R), M.matrix_mark)")

    # New() override that skips ..() and one that sets a after ..()
    s.case("new_override", "new /matrix/matrix_noinit(1, 2, 3, 4, 5, 6)")
    s.case("new_override", "new /matrix/matrix_noinit(2, MATRIX_SCALE)")
    s.case("new_override", "new /matrix/matrix_noinit")
    s.case("new_override", "new /matrix/matrix_noinit(matrix(1, 2, 3, 4, 5, 6))")
    s.case("new_override", "new /matrix/matrix_set9(1, 2, 3, 4, 5, 6)")
    s.case("new_override", "new /matrix/matrix_set9")
    s.case("new_override", "new /matrix/matrix_set9(2, MATRIX_SCALE)")
    s.case("new_override", "matrix(new /matrix/matrix_set9)")

    # ================= assignment operators through other references =================
    for op in ["*", "/", "+", "-"]:
        for r in ["2", "matrix(2, 0, 1, 0, 2, 1)"]:
            s.body(f"op{op}=ref", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/list/L = list(M)", f"L[1] {op}= {r}"],
                   "list(L[1], M, L[1] == M)")
            s.body(f"op{op}=ref", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/datum/matrix_holder/D = new",
                                   "D.mvar = M", f"D.mvar {op}= {r}"], "list(D.mvar, M, D.mvar == M)")
            s.body(f"op{op}=ref", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", 'var/list/L = list("k" = M)', f'L["k"] {op}= {r}'],
                   'list(L["k"], M, L["k"] == M)')
    s.body("op*=ref", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/datum/matrix_holder/D = new",
                       "D.mvar = M", "D.mvar *= 2", "D.mvar /= 2"], "list(D.mvar, M, D.mvar == M)")

    # -- / ++ and non-matrix right sides with an alias
    for st in ["M--", "--M", "M++", "++M", "M *= list(1, 2, 3, 4, 5, 6)", 'M /= "2"', "M -= 2", "M += 2",
               "M -= null", "M *= new /datum", "M /= 0", "M *= NAN"]:
        s.body("op_assign_alias", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/matrix/A = M", st], "list(M, A, M == A)")
    s.body("op_assign_alias", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M--"], "list(R, M)")
    s.body("op_assign_alias", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = --M"], "list(R, M)")

    # ================= matrices inside lists (identity, not component equality) =================
    s.case("matrix_list", "list(matrix()) ~= list(matrix())")
    s.body("matrix_list", ["var/matrix/M = matrix()"], "list(M) ~= list(M)")
    s.case("matrix_list", "matrix() in list(matrix())")
    s.body("matrix_list", ["var/matrix/M = matrix()"], "M in list(M)")
    s.case("matrix_list", "list(matrix()).Find(matrix())")
    s.case("matrix_list", "(list(matrix(1, 2, 3, 4, 5, 6)) - matrix(1, 2, 3, 4, 5, 6)).len")
    s.body("matrix_list", ["var/list/L = list()", "L[matrix()] = 1"], "L[matrix()]")
    s.body("matrix_list", ["var/list/L = list()", "var/matrix/M = matrix()", "L[M] = 1"], "list(L[M], L.len)")
    s.case("matrix_list", "(list(matrix()) | list(matrix())).len")
    s.case("matrix_list", "(list(matrix()) & list(matrix())).len")
    s.body("matrix_list", ["var/list/L = list(matrix(), matrix())", "L.Remove(matrix())"], "L.len")

    # ================= result type of unary ops on subtypes =================
    s.case("subtype_type", "(~matrix_sub_make()).type")
    s.case("subtype_type", "(-matrix_sub_make()).type")
    s.case("subtype_type", "matrix_sub_make().Invert().type")
    s.case("subtype_type", "matrix_sub_make().Scale(2).type")
    for st in ["M *= 2", "M /= 2", "M += matrix()", "M -= matrix()", "M *= matrix(2, 0, 0, 0, 2, 0)"]:
        s.body("subtype_type", ["var/matrix/M = matrix_sub_make()", st], "list(M.type, M)")

    # ================= vars list contents and order =================
    s.body("matrix_vars", ["var/list/out = list()", "for(var/v in matrix().vars)", "\tout += v"], "out")
    s.case("matrix_vars", "matrix().vars.len")
    s.case("matrix_vars", 'matrix_sub_make().vars["matrix_tag"]')
    s.body("matrix_vars", ["var/list/out = list()", "for(var/v in matrix_sub_make().vars)", "\tout += v"], "out")

    # ================= Invert / Turn / Interpolate on non-numeric components =================
    for comp in ["a", "e", "c"]:
        for val in ['"abc"', "null", "list(1)", "new /datum"]:
            pre = ["var/matrix/M = matrix(2, 0, 1, 0, 2, 1)", f"M.{comp} = {val}"]
            s.body("nonnum", pre + ["M.Invert()"], "matrix_vars(M)")
            s.body("nonnum", pre, "~M")
            s.body("nonnum", pre + ["M.Turn(90)"], "matrix_vars(M)")
            s.body("nonnum", pre + ["M.Translate(2)"], "matrix_vars(M)")
            s.body("nonnum", pre, "M.Interpolate(matrix(), 0.5)")
            s.body("nonnum", pre, "matrix().Interpolate(M, 0.5)")
            s.body("nonnum", pre, "M - matrix()")

    # ================= Multiply named arguments =================
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(Matrix2 = matrix(2, 0, 0, 0, 2, 0))"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(n = 3)"], "matrix_res(R, M)")
    s.body("Multiply", ["var/matrix/M = matrix(1, 2, 3, 4, 5, 6)", "var/R = M.Multiply(Matrix2 = 3)"], "matrix_res(R, M)")

    # ================= transform chaining and other appearance holders =================
    s.body("transform", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "O.transform.Scale(2)"], "O.transform")
    s.body("transform", [O, "O.transform.Turn(90)"], "matrix_round(O.transform)")
    s.body("transform", [O, "O.transform.Translate(3)"], "O.transform")
    MA = "var/mutable_appearance/ma = new(O)"
    s.body("transform", [O, MA, "ma.transform = matrix(2, 0, 0, 0, 2, 0)"], "ma.transform")
    s.body("transform", [O, MA, "ma.transform = matrix(2, 0, 0, 0, 2, 0)", "O.appearance = ma"], "O.transform")
    s.body("transform", [O, MA, "ma.transform = matrix(2, 0, 0, 0, 2, 0)", "O.appearance = ma"], "O.transform == ma.transform")
    s.body("transform", ["var/image/I = image(null)", "I.transform *= 2"], "I.transform")
    s.body("transform", ["var/image/I = image(null)"], "I.transform")
    s.body("transform", ["var/image/I = image(null)", "I.transform = matrix(1, 2, 3, 4, 5, 6)", "I.transform += matrix()"], "I.transform")
    s.body("transform", ["var/image/I = image(null)", "I.transform = list(1, 2, 3, 4, 5, 6)"], "I.transform")
    s.body("transform", ["var/mutable_appearance/ma = new", "ma.transform = turn(ma.transform, 90)"], "matrix_round(ma.transform)")

    # ================= turn() with extra or bad arguments =================
    s.case("turn", "turn(matrix(), 90, 5)")
    s.case("turn", "turn(90, matrix())")
    s.case("turn", 'turn(matrix_sub_make(), "90")')
    s.case("turn", "turn(matrix(1, 2, 0, 2, 4, 0), 90)")
    s.body("turn", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)"], "turn(O.transform, 90) == O.transform")
    s.body("turn", [O, "O.transform = matrix(1, 2, 3, 4, 5, 6)", "var/R = turn(O.transform, 90)"], "list(R, O.transform)")

    # ================= opcode shortcuts with the wrong arity =================
    for args in ["1, 2, 90, MATRIX_ROTATE", "90, 0, MATRIX_ROTATE", "1, 2, 3, MATRIX_TRANSLATE",
                 "2, MATRIX_TRANSLATE | MATRIX_MODIFY", "2, MATRIX_SCALE | MATRIX_MODIFY", "90, MATRIX_ROTATE | MATRIX_MODIFY",
                 "2, 3, MATRIX_TRANSLATE | MATRIX_MODIFY", "1, 2, 3, MATRIX_SCALE", "1, 2, 3, 4, MATRIX_SCALE"]:
        s.case("matrix", f"matrix({args})")
