"""Render suite: transform matrices, order of operations, pixel offsets, RESET_TRANSFORM, PIXEL_SCALE."""

ROT = (0.06, 6.0)   # arbitrary angles resample with bilinear filtering


def build(s):
    s.render()

    def t(name, m, state="asym", tol=None, pre=(), icn=None):
        lines = [f'var/obj/O = render_x_obj(T, "{state}")']
        if icn:
            lines.append(f"O.icon = {icn}")
        s.cell(name, [*lines, *pre, f"O.transform = {m}"], tol=tol)

    # scale
    for name, m, tol in [
            ("scale 2", "matrix(2, 0, 0, 0, 2, 0)", None), 
            ("scale 0.5", "matrix(0.5, 0, 0, 0, 0.5, 0)", ROT), ("scale 0.25", "matrix(0.25, 0, 0, 0, 0.25, 0)", ROT),
            ("scale 1.5", "matrix(1.5, 0, 0, 0, 1.5, 0)", ROT), ("scale 0", "matrix(0, 0, 0, 0, 0, 0)", None),
            ("flip x (-1, 1)", "matrix(-1, 0, 0, 0, 1, 0)", None), ("flip y (1, -1)", "matrix(1, 0, 0, 0, -1, 0)", None),
            ("flip both (-1, -1)", "matrix(-1, 0, 0, 0, -1, 0)", None), ("scale -2", "matrix(-2, 0, 0, 0, -2, 0)", None),
            ("non-uniform 2 x 0.5", "matrix(2, 0, 0, 0, 0.5, 0)", ROT), ("non-uniform 0.5 x 2", "matrix(0.5, 0, 0, 0, 2, 0)", ROT),
            ("non-uniform -1 x 2", "matrix(-1, 0, 0, 0, 2, 0)", None),
            ("Scale(2, 1) proc", "matrix().Scale(2, 1)", None), ("Scale(2) one arg", "matrix().Scale(2)", None),
            ("matrix(2, 2, MATRIX_SCALE)", "matrix(2, 2, MATRIX_SCALE)", None),
            ("null transform", "null", None), ("identity matrix()", "matrix()", None)]:
        t(f"transform: {name}", m, tol=tol)

    # rotation
    for a in [90, 180, 270, -90, 360]:
        t(f"transform: turn {a}", f"turn(matrix(), {a})")
    for a in [45, 30, 10, -60, 135]:
        t(f"transform: turn {a}", f"turn(matrix(), {a})", tol=ROT)
    t("transform: Turn(90) proc", "matrix().Turn(90)")
    t("transform: matrix(45, MATRIX_ROTATE)", "matrix(45, MATRIX_ROTATE)", tol=ROT)

    # skew
    for name, m in [("skew x 0.5", "matrix(1, 0.5, 0, 0, 1, 0)"), ("skew y 0.5", "matrix(1, 0, 0, 0.5, 1, 0)"),
                    ("skew x -1", "matrix(1, -1, 0, 0, 1, 0)"), ("skew both 0.3", "matrix(1, 0.3, 0, 0.3, 1, 0)")]:
        t(f"transform: {name}", m, tol=ROT)

    # translate
    for name, m in [("translate 8, -8", "matrix(1, 0, 8, 0, 1, -8)"),
                    ("translate 0.5, 0.5", "matrix(1, 0, 0.5, 0, 1, 0.5)"), ("Translate(16) one arg", "matrix().Translate(16)"),
                    ("Translate(-10, 20) proc", "matrix().Translate(-10, 20)"),
                    ("matrix(5, 7, MATRIX_TRANSLATE)", "matrix(5, 7, MATRIX_TRANSLATE)")]:
        t(f"transform: {name}", m, tol=ROT if "0.5" in name else None)

    # combined order
    for name, lines in [
            ("Scale(2,1) then Turn(90)", ["var/matrix/M = matrix()", "M.Scale(2, 1)", "M.Turn(90)"]),
            ("Turn(90) then Scale(2,1)", ["var/matrix/M = matrix()", "M.Turn(90)", "M.Scale(2, 1)"]),
            ("Translate(16,0) then Turn(90)", ["var/matrix/M = matrix()", "M.Translate(16, 0)", "M.Turn(90)"]),
            ("Turn(90) then Translate(16,0)", ["var/matrix/M = matrix()", "M.Turn(90)", "M.Translate(16, 0)"]),
            ("Scale(2) then Translate(8,8)", ["var/matrix/M = matrix()", "M.Scale(2)", "M.Translate(8, 8)"]),
            ("Translate(8,8) then Scale(2)", ["var/matrix/M = matrix()", "M.Translate(8, 8)", "M.Scale(2)"]),
            ("Turn(45) then Scale(1.5, 0.5)", ["var/matrix/M = matrix()", "M.Turn(45)", "M.Scale(1.5, 0.5)"]),
            ("Multiply skew by turn 90", ["var/matrix/M = matrix(1, 0.5, 0, 0, 1, 0)", "M.Multiply(turn(matrix(), 90))"]),
            ("matrix * matrix", ["var/matrix/M = matrix(2, 0, 0, 0, 1, 0) * turn(matrix(), 90)"]),
            ("Invert of scale 0.5", ["var/matrix/M = matrix(0.5, 0, 0, 0, 0.5, 0)", "M.Invert()"])]:
        s.cell(f"transform: {name}", ['var/obj/O = render_x_obj(T, "asym")', *lines, "O.transform = M"],
               tol=ROT if "45" in name or "skew" in name else None)

    # with pixel offsets
    for name, pre, m in [
            ("pixel_x 16 + scale 2", ["O.pixel_x = 16"], "matrix(2, 0, 0, 0, 2, 0)"),
            ("pixel_y -16 + turn 90", ["O.pixel_y = -16"], "turn(matrix(), 90)"),
            ("pixel_w 12 + scale 2", ["O.pixel_w = 12"], "matrix(2, 0, 0, 0, 2, 0)"),
            ("pixel_z 12 + turn 90", ["O.pixel_z = 12"], "turn(matrix(), 90)"),
            ("pixel_x 8 pixel_y 8 + flip x", ["O.pixel_x = 8", "O.pixel_y = 8"], "matrix(-1, 0, 0, 0, 1, 0)"),
            ("pixel_w -8 pixel_z 8 + scale 0.5", ["O.pixel_w = -8", "O.pixel_z = 8"], "matrix(0.5, 0, 0, 0, 0.5, 0)")]:
        t(f"transform: {name}", m, pre=pre, tol=ROT if "0.5" in name else None)

    # rect.dmi 32x16
    for name, m, tol in [("none", "null", None), ("turn 90", "turn(matrix(), 90)", None),
                         ("scale 2", "matrix(2, 0, 0, 0, 2, 0)", None),
                         ("flip x", "matrix(-1, 0, 0, 0, 1, 0)", None), ("turn 45", "turn(matrix(), 45)", ROT),
                         ("non-uniform 1 x 2", "matrix(1, 0, 0, 0, 2, 0)", None)]:
        t(f"rect.dmi: {name}", m, state="wide", icn="'rect.dmi'", tol=tol)
    t("small.dmi: scale 2", "matrix(2, 0, 0, 0, 2, 0)", state="grad", icn="'small.dmi'")
    t("small.dmi: turn 90", "turn(matrix(), 90)", state="grad", icn="'small.dmi'")

    # RESET_TRANSFORM on overlays
    ov = "var/image/I = image(icon = 'small.dmi', icon_state = \"grad\", pixel_x = 16)"
    for name, flags in [("overlay no flags", None), ("overlay RESET_TRANSFORM", "RESET_TRANSFORM")]:
        for pm in ["matrix(2, 0, 0, 0, 2, 0)", "turn(matrix(), 90)"]:
            lines = ['var/obj/O = render_x_obj(T, "half")', ov]
            if flags:
                lines.append(f"I.appearance_flags = {flags}")
            s.cell(f"{name}, parent {'scale 2' if 'matrix(2' in pm else 'turn 90'}", lines + ["O.overlays += I", f"O.transform = {pm}"])
    s.cell("overlay own turn 90, parent scale 2", [
        'var/obj/O = render_x_obj(T, "half")', ov, "I.transform = turn(matrix(), 90)",
        "O.overlays += I", "O.transform = matrix(2, 0, 0, 0, 2, 0)"])

    # PIXEL_SCALE
    for name, m in [("scale 1.5", "matrix(1.5, 0, 0, 0, 1.5, 0)"), ("scale 2", "matrix(2, 0, 0, 0, 2, 0)"),
                    ("turn 45", "turn(matrix(), 45)"),
                    ("non-uniform 2.5 x 1", "matrix(2.5, 0, 0, 0, 1, 0)")]:
        t(f"PIXEL_SCALE: {name}", m, state="checker", pre=["O.appearance_flags = PIXEL_SCALE"],
          tol=ROT if "45" in name else None)
    t("no PIXEL_SCALE: checker scale 1.5", "matrix(1.5, 0, 0, 0, 1.5, 0)", state="checker", tol=ROT)
    t("no PIXEL_SCALE: checker scale 2.5 x 1", "matrix(2.5, 0, 0, 0, 1, 0)", state="checker", tol=ROT)
