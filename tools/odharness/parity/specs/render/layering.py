"""Render suite: layer and plane order, overlays and underlays, FLOAT_*, KEEP_*, vis_contents, render targets,
plane masters, invisibility."""


def build(s):
    s.render()
    n = [0]

    def tag():
        n[0] += 1
        return f"render_x_l{n[0]}"

    two = ['var/obj/A = render_x_obj(T, "solid")', 'var/obj/B = render_x_obj(T, "half")', "B.pixel_x = 8", "B.pixel_y = 8"]

    # layer and plane between two objs
    for name, lines in [
            ("same layer, creation order", []),
            ("A layer 4 over B", ["A.layer = 4"]),
            ("B layer 2.5 under A", ["B.layer = 2.5"]),
            ("A layer 1.5 under turf layer", ["A.layer = 1.5", "B.layer = 1"]),
            ("A plane 1, B layer 10", ["A.plane = 1", "B.layer = 10"]),
            ("B plane -1 under turfs", ["B.plane = -1"]),
            ("A plane 2, B plane 1", ["A.plane = 2", "B.plane = 1"]),
            ("negative layer -5", ["A.layer = -5"]),
            ("FLOAT_LAYER on atom", ["A.layer = FLOAT_LAYER"]),
            ("FLOAT_PLANE on atom", ["A.plane = FLOAT_PLANE", "A.layer = 5"])]:
        s.cell(f"order: {name}", two + lines)
    s.cell("order: three objs, middle layer highest", [
        'var/obj/A = render_x_obj(T, "solid")', 'var/obj/B = render_x_obj(T, "half")', 'var/obj/C = render_x_obj(T, "grad")',
        "B.pixel_x = 10", "C.pixel_x = 20", "B.layer = 5"])
    s.cell("order: obj on next turf, pixel_x into this one", [
        'var/obj/A = render_x_obj(T, "solid")', 'var/obj/B = render_x_obj(get_step(T, WEST), "half")', "B.pixel_x = 24"])
    s.cell("order: obj on north turf, pixel_y down into this", [
        'var/obj/A = render_x_obj(T, "solid")', 'var/obj/B = render_x_obj(get_step(T, NORTH), "half")', "B.pixel_y = -24"])

    # overlays and underlays
    img = lambda st, px, py, ic="small.dmi": f"image(icon = '{ic}', icon_state = \"{st}\", pixel_x = {px}, pixel_y = {py})"
    s.cell("overlays: three in add order", [
        'var/obj/O = render_x_obj(T, "half")',
        f"O.overlays += {img('solid', 4, 4)}", f"O.overlays += {img('grad', 10, 10)}", f"O.overlays += {img('solid', 16, 16, 'test.dmi')}"])
    s.cell("overlays: list assigned at once", [
        'var/obj/O = render_x_obj(T, "half")',
        f"O.overlays = list({img('solid', 4, 4)}, {img('grad', 10, 10)})"])
    s.cell("underlays: two in add order", [
        'var/obj/O = render_x_obj(T, "half")',
        f"O.underlays += {img('solid', 20, 0, 'test.dmi')}", f"O.underlays += {img('grad', 10, 10)}"])
    s.cell("overlays and underlays together", [
        'var/obj/O = render_x_obj(T, "half")',
        f"O.overlays += {img('solid', 8, 8)}", f"O.underlays += {img('solid', 8, -8, 'test.dmi')}"])
    s.cell("overlays: removed with -=", [
        'var/obj/O = render_x_obj(T, "half")', f"var/image/I = {img('solid', 8, 8)}",
        "O.overlays += I", f"O.overlays += {img('grad', 0, -8)}", "O.overlays -= I"])
    s.cell("overlays: icon file and state text", [
        'var/obj/O = render_x_obj(T, "half")', "O.overlays += 'small.dmi'", 'O.overlays += "grad"'])
    s.cell("overlays: an obj appearance", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/X = render_x_free("grad", \'small.dmi\')',
        "X.pixel_x = 12", "O.overlays += X"])
    for name, lyr in [("layer 2 under parent", "2"), ("layer 4 over parent", "4"), ("FLOAT_LAYER", "FLOAT_LAYER"),
                      ("FLOAT_LAYER - 1", "FLOAT_LAYER - 1")]:
        s.cell(f"overlay: {name}", [
            'var/obj/O = render_x_obj(T, "half")', f"var/image/I = {img('solid', 0, 0, 'test.dmi')}",
            "I.pixel_x = 8", f"I.layer = {lyr}", "O.overlays += I"])
    s.cell("overlays: FLOAT_LAYER - 1 added after FLOAT_LAYER", [
        'var/obj/O = render_x_obj(T, "half")',
        f"var/image/A = {img('solid', 4, 4)}", "A.layer = FLOAT_LAYER",
        f"var/image/B = {img('grad', 8, 8)}", "B.layer = FLOAT_LAYER - 1",
        "O.overlays += A", "O.overlays += B"])
    s.cell("overlay: layer 4 over a neighbour obj at layer 3.5", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/N = render_x_obj(T, "solid")',
        "N.pixel_x = 12", "N.layer = 3.5", f"var/image/I = {img('grad', 12, 0)}", "I.layer = 4", "O.overlays += I"])
    s.cell("overlay: plane 1 over a neighbour obj", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/N = render_x_obj(T, "solid")',
        "N.pixel_x = 12", "N.layer = 10", f"var/image/I = {img('grad', 12, 0)}", "I.plane = 1", "O.overlays += I"])
    s.cell("overlay: FLOAT_PLANE follows parent plane 1", [
        'var/obj/O = render_x_obj(T, "half")', "O.plane = 1", 'var/obj/N = render_x_obj(T, "solid")',
        "N.pixel_x = 12", "N.layer = 10", f"var/image/I = {img('grad', 12, 0)}", "I.plane = FLOAT_PLANE", "O.overlays += I"])
    s.cell("overlay: nested overlay", [
        'var/obj/O = render_x_obj(T, "half")', f"var/image/I = {img('solid', 10, 0)}",
        f"I.overlays += {img('grad', 0, 10)}", "O.overlays += I"])
    s.cell("overlay: dir follows parent on dirs4", [
        'var/obj/O = render_x_obj(T, "half")', "O.dir = EAST",
        "O.overlays += image(icon = 'test.dmi', icon_state = \"dirs4\", pixel_x = 12)"])

    # KEEP_TOGETHER / KEEP_APART
    kt = ['var/obj/O = render_x_obj(T, "solid")', f"var/image/I = {img('solid', 10, 10, 'test.dmi')}", 'I.color = "#00ff00"']
    for name, lines in [
            ("alpha 128, no KEEP_TOGETHER", ["O.alpha = 128"]),
            ("alpha 128, KEEP_TOGETHER", ["O.alpha = 128", "O.appearance_flags = KEEP_TOGETHER"]),
            ("alpha 128, KEEP_TOGETHER, overlay KEEP_APART",
             ["O.alpha = 128", "O.appearance_flags = KEEP_TOGETHER", "I.appearance_flags = KEEP_APART"]),
            ("color red, KEEP_TOGETHER", ['O.color = "#ff0000"', "O.appearance_flags = KEEP_TOGETHER"]),
            ("blend add, KEEP_TOGETHER", ["O.blend_mode = BLEND_ADD", "O.appearance_flags = KEEP_TOGETHER"]),
            ("turn 45, KEEP_TOGETHER", ["O.transform = turn(matrix(), 45)", "O.appearance_flags = KEEP_TOGETHER"]),
            ("overlay plane 1, KEEP_TOGETHER", ["O.appearance_flags = KEEP_TOGETHER", "I.plane = 1"])]:
        s.cell(f"KEEP: {name}", kt + lines + ["O.overlays += I"], tol=(0.06, 6.0) if "45" in name else None)

    # vis_contents
    vis = ['var/obj/O = render_x_obj(T, "half")', 'var/obj/V = render_x_free("asym")', "V.pixel_x = 12", "V.pixel_y = 6"]
    for name, lines in [
            ("plain", []),
            ("VIS_INHERIT_ICON", ["V.icon = 'small.dmi'", "V.vis_flags = VIS_INHERIT_ICON"]),
            ("VIS_INHERIT_ICON_STATE", ['V.icon_state = "grad"', "V.vis_flags = VIS_INHERIT_ICON_STATE"]),
            ("VIS_INHERIT_ICON | ICON_STATE", ["V.icon = null", "V.vis_flags = VIS_INHERIT_ICON | VIS_INHERIT_ICON_STATE"]),
            ("VIS_INHERIT_DIR", ['V.icon_state = "dirs4"', "O.dir = WEST", "V.vis_flags = VIS_INHERIT_DIR"]),
            ("no VIS_INHERIT_DIR", ['V.icon_state = "dirs4"', "O.dir = WEST"]),
            ("VIS_INHERIT_LAYER", ["V.layer = 1", "V.vis_flags = VIS_INHERIT_LAYER"]),
            ("layer 1 below parent", ["V.layer = 1"]),
            ("VIS_INHERIT_PLANE", ["V.plane = -1", "V.vis_flags = VIS_INHERIT_PLANE"]),
            ("VIS_UNDERLAY", ["V.vis_flags = VIS_UNDERLAY"]),
            ("VIS_HIDE", ["V.vis_flags = VIS_HIDE"]),
            ("VIS_INHERIT_ID", ["V.vis_flags = VIS_INHERIT_ID"]),
            ("parent color red", ['O.color = "#ff0000"']),
            ("parent color red, RESET_COLOR", ['O.color = "#ff0000"', "V.appearance_flags = RESET_COLOR"]),
            ("parent alpha 100", ["O.alpha = 100"]),
            ("parent scale 2", ["O.transform = matrix(2, 0, 0, 0, 2, 0)"]),
            ("parent scale 2, RESET_TRANSFORM", ["O.transform = matrix(2, 0, 0, 0, 2, 0)", "V.appearance_flags = RESET_TRANSFORM"]),
            ("own overlay", [f"V.overlays += {img('solid', 0, 8)}"])]:
        s.cell(f"vis_contents: {name}", vis + lines + ["O.vis_contents += V"])
    s.cell("vis_contents: two objs, add order", vis + [
        'var/obj/W = render_x_free("grad", \'small.dmi\')', "W.pixel_x = 16", "O.vis_contents += V", "O.vis_contents += W"])
    s.cell("vis_contents: nested two deep", vis + [
        'var/obj/W = render_x_free("solid", \'small.dmi\')', "W.pixel_y = 16", "V.vis_contents += W", "O.vis_contents += V"])
    s.cell("vis_contents: same obj in two parents", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/P = render_x_obj(T, "half")', "P.pixel_x = 32",
        'var/obj/V = render_x_free("solid", \'small.dmi\')', "O.vis_contents += V", "P.vis_contents += V"])
    s.cell("vis_contents: a turf on the map", [
        'var/obj/O = render_x_obj(T, "half")', "O.pixel_y = 0", "O.vis_contents += get_step(T, EAST)"])

    # render_target / render_source
    for name, extra in [("hidden *target", []), ("receiver turned 90", ["R.transform = turn(matrix(), 90)"]),
                        ("receiver colour blue", ['R.color = "#0000ff"']), ("source with outline", ["SRC_F"]),
                        ("receiver with own icon", ['R.icon = \'test.dmi\'', 'R.icon_state = "solid"'])]:
        tg = "*" + tag()
        lines = ['var/obj/S = render_x_obj(T, "asym")', f'S.render_target = "{tg}"',
                 "var/obj/R = parity_track(new /obj(T))", "R.pixel_x = 20", f'R.render_source = "{tg}"']
        lines += ['S.filters = filter(type = "outline", size = 1, color = "#ff0000")' if e == "SRC_F" else e for e in extra]
        s.cell(f"render_target: {name}", lines, tol=(0.05, 4.0) if "outline" in name else None)
    tg = tag()
    s.cell("render_target: shown target (no *)", [
        'var/obj/S = render_x_obj(T, "asym")', f'S.render_target = "{tg}"',
        "var/obj/R = parity_track(new /obj(T))", "R.pixel_x = 20", f'R.render_source = "{tg}"'])
    s.cell("render_target: missing source name", [
        'var/obj/R = render_x_obj(T, "half")', f'R.render_source = "*{tag()}_none"'])
    tg = "*" + tag()
    s.cell("render_target: source with overlay", [
        'var/obj/S = render_x_obj(T, "half")', f"S.overlays += {img('solid', 10, 10)}", f'S.render_target = "{tg}"',
        "var/obj/R = parity_track(new /obj(T))", "R.pixel_y = 16", f'R.render_source = "{tg}"'])

    # plane masters (whole view)
    obj5 = ['render_x_solo()', 'var/obj/O = render_x_obj(T, "grad")', "O.plane = 5",
            'var/obj/H = render_x_obj(T, "half")', "H.plane = 5", "H.pixel_x = 16"]
    for name, lines in [
            ("plain", []),
            ("color red", ['P.color = "#ff0000"']),
            ("color matrix", ["P.color = list(0,0,1, 0,1,0, 1,0,0)"]),
            ("alpha 128", ["P.alpha = 128"]),
            ("blur 2", ['P.filters = filter(type = "blur", size = 2)']),
            ("outline", ['P.filters = filter(type = "outline", size = 2, color = "#ffff00")']),
            ("blend multiply", ["P.blend_mode = BLEND_MULTIPLY"]),
            ("blend add", ["P.blend_mode = BLEND_ADD"]),
            ("KEEP_TOGETHER flag, alpha 128", ["P.appearance_flags = PLANE_MASTER | KEEP_TOGETHER", "P.alpha = 128"]),
            ("transform scale 0.5", ["P.transform = matrix(0.5, 0, 0, 0, 0.5, 0)"]),
            ("render_target hidden", [f'P.render_target = "*{tag()}"']),
            ("rays filter overlay", ['P.filters = filter(type = "rays", size = 48, color = "#ffffff")']),
            ("invisibility 101", ["P.invisibility = 101"]),
            ("mouse_opacity 0, color green", ["P.mouse_opacity = 0", 'P.color = "#00ff00"'])]:
        s.cell(f"solo: plane master {name}", obj5 + ["var/obj/P = render_x_master(5)"] + lines, solo=True,
               tol=(0.30, 20.0) if "rays" in name else (0.10, 6.0) if "blur" in name or "outline" in name or "0.5" in name else None)
    tg = "*" + tag()
    s.cell("solo: plane master render_target drawn by obj", obj5 + [
        "var/obj/P = render_x_master(5)", f'P.render_target = "{tg}"',
        "var/obj/R = parity_track(new /obj(get_step(T, NORTH)))", f'R.render_source = "{tg}"',
        "R.transform = matrix(0.25, 0, 0, 0, 0.25, 0)"], solo=True, tol=(0.10, 6.0))
    s.cell("solo: two plane masters, 5 and 6", obj5 + [
        'var/obj/K = render_x_obj(T, "asym")', "K.plane = 6",
        "var/obj/P = render_x_master(5)", 'P.color = "#ff0000"', "var/obj/Q = render_x_master(6)", "Q.alpha = 100"], solo=True)
    s.cell("solo: plane master for plane 0 (turfs too)", [
        "render_x_solo()", 'var/obj/O = render_x_obj(T, "grad")', "var/obj/P = render_x_master(0)",
        "P.color = list(0.3,0.3,0.3, 0.59,0.59,0.59, 0.11,0.11,0.11)"], solo=True)

    # invisibility
    s.cell("invisibility: 0, 1, 50, 101 at default see_invisible", [
        'var/obj/A = render_x_obj(T, "solid", \'small.dmi\')', "A.invisibility = 0",
        'var/obj/B = render_x_obj(T, "grad", \'small.dmi\')', "B.invisibility = 1", "B.pixel_x = 16",
        'var/obj/C = render_x_obj(T, "solid")', "C.invisibility = 50", "C.pixel_y = 16",
        'var/obj/D = render_x_obj(T, "half")', "D.invisibility = 101", "D.pixel_x = -16"])
    for see in [1, 50, 60, 101]:
        s.cell(f"solo: see_invisible {see}, objs invisibility 0 1 50 60 101", [
            "render_x_solo()",
            'var/obj/A = render_x_obj(T, "solid", \'small.dmi\')', "A.pixel_x = -16",
            'var/obj/B = render_x_obj(T, "grad", \'small.dmi\')', "B.invisibility = 1",
            'var/obj/C = render_x_obj(T, "solid", \'small.dmi\')', "C.invisibility = 50", "C.pixel_x = 16",
            'var/obj/D = render_x_obj(T, "grad", \'small.dmi\')', "D.invisibility = 60", "D.pixel_y = 16",
            'var/obj/E = render_x_obj(T, "solid", \'small.dmi\')', "E.invisibility = 101", "E.pixel_y = -16",
            f"live_client.mob.see_invisible = {see}"], solo=True)
