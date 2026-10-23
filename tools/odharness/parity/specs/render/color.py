"""Render suite: color var forms, alpha, blend_mode, RESET_COLOR/RESET_ALPHA, client.color."""


def build(s):
    s.render()

    def c(name, state, lines):
        s.cell(name, [f'var/obj/O = render_x_obj(T, "{state}")', *lines])

    # color as text
    for col in ["red", "green", "blue", "teal", "black", "white", "Red",
                "#f00", "#08f", "#ff8000", "#FF8000", "#80808080", "#ff000040", "#0f08"]:
        c(f"color text {col} on grad", "grad", [f'O.color = "{col}"'])
    c("color rgb(255,128,0) on grad", "grad", ["O.color = rgb(255, 128, 0)"])
    c("color rgb(0,255,0,128) on grad", "grad", ["O.color = rgb(0, 255, 0, 128)"])
    c("color null on grad", "grad", ["O.color = null"])
    c("color red on alpha state", "alpha", ['O.color = "#ff0000"'])
    c("color #00ff0080 on alpha state", "alpha", ['O.color = "#00ff0080"'])

    # color matrices
    mats = [
        ("9 swap rb", "list(0,0,1, 0,1,0, 1,0,0)"),
        ("9 greyscale", "list(0.3,0.3,0.3, 0.59,0.59,0.59, 0.11,0.11,0.11)"),
        ("9 doubles red", "list(2,0,0, 0,1,0, 0,0,1)"),
        ("12 constant blue", "list(1,0,0, 0,1,0, 0,0,1, 0,0,0.5)"),
        ("12 invert", "list(-1,0,0, 0,-1,0, 0,0,-1, 1,1,1)"),
        ("16 alpha half", "list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0.5)"),
        ("16 red to alpha", "list(1,0,0,1, 0,1,0,0, 0,0,1,0, 0,0,0,0)"),
        ("20 invert", "list(-1,0,0,0, 0,-1,0,0, 0,0,-1,0, 0,0,0,1, 1,1,1,0)"),
        ("20 alpha constant", "list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0, 0,0,0,0.5)"),
        ("20 sepia", "list(0.39,0.35,0.27,0, 0.77,0.69,0.53,0, 0.19,0.17,0.13,0, 0,0,0,1, 0,0,0,0)"),
        ("3 strings", 'list("#00ff00", "#0000ff", "#ff0000")'),
        ("4 strings with constant", 'list("#ff0000", "#00ff00", "#0000ff", "#404040")'),
        ("5 strings rgba", 'list("#ff000000", "#00ff0000", "#0000ff00", "#000000ff", "#00000000")'),
        ("identity 20", "list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1, 0,0,0,0)"),
    ]
    for name, m in mats:
        c(f"color matrix {name} on grad", "grad", [f"O.color = {m}"])
    for name, m in [mats[8]]:
        c(f"color matrix {name} on alpha state", "alpha", [f"O.color = {m}"])

    # alpha var
    for a in [0, 1, 128, 254, 255, 300, -5, 127.6]:
        c(f"alpha {a} on solid", "solid", [f"O.alpha = {a}"])
    c("alpha 128 with color #ffffff80", "solid", ["O.alpha = 128", 'O.color = "#ffffff80"'])
    c("alpha 128 on alpha state", "alpha", ["O.alpha = 128"])
    c("alpha 128 with 16 matrix", "solid", ["O.alpha = 128", "O.color = list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0.5)"])

    # blend_mode
    modes = ["BLEND_DEFAULT", "BLEND_OVERLAY", "BLEND_ADD", "BLEND_SUBTRACT", "BLEND_MULTIPLY", "BLEND_INSET_OVERLAY"]
    for bm in modes:
        c(f"blend {bm} grad over background", "grad", [f"O.blend_mode = {bm}"])
    for bm in modes:
        s.cell(f"blend {bm} grad over checker obj", [
            'var/obj/B = render_x_obj(T, "checker")',
            'var/obj/O = render_x_obj(T, "grad")', "O.layer = B.layer + 1", f"O.blend_mode = {bm}"])
    for bm in ["BLEND_OVERLAY", "BLEND_ADD", "BLEND_MULTIPLY"]:
        s.cell(f"blend {bm} half over solid obj, alpha 128", [
            'var/obj/B = render_x_obj(T, "solid")',
            'var/obj/O = render_x_obj(T, "alpha")', "O.layer = B.layer + 1", "O.alpha = 128", f"O.blend_mode = {bm}"])
    for bm in ["BLEND_ADD", "BLEND_MULTIPLY", "BLEND_INSET_OVERLAY"]:
        s.cell(f"blend {bm} on an overlay", [
            'var/obj/O = render_x_obj(T, "half")',
            "var/image/I = image(icon = 'test.dmi', icon_state = \"grad\")", f"I.blend_mode = {bm}", "O.overlays += I"])
    s.cell("blend BLEND_ADD obj with color red", [
        'var/obj/B = render_x_obj(T, "checker")',
        'var/obj/O = render_x_obj(T, "grad")', "O.layer = B.layer + 1", 'O.color = "#ff0000"', "O.blend_mode = BLEND_ADD"])

    # RESET_COLOR / RESET_ALPHA on overlays and underlays
    ovl = "var/image/I = image(icon = 'small.dmi', icon_state = \"grad\", pixel_x = 16, pixel_y = 16)"
    for name, parent, flags in [
            ("parent red, overlay no flags", ['O.color = "#ff0000"'], None),
            ("parent red, overlay RESET_COLOR", ['O.color = "#ff0000"'], "RESET_COLOR"),
            ("parent matrix, overlay RESET_COLOR", ["O.color = list(0,0,1, 0,1,0, 1,0,0)"], "RESET_COLOR"),
            ("parent alpha 80, overlay no flags", ["O.alpha = 80"], None),
            ("parent alpha 80, overlay RESET_ALPHA", ["O.alpha = 80"], "RESET_ALPHA"),
            ("parent red alpha 80, overlay RESET_COLOR", ['O.color = "#ff0000"', "O.alpha = 80"], "RESET_COLOR"),
            ("parent red alpha 80, overlay RESET_ALPHA", ['O.color = "#ff0000"', "O.alpha = 80"], "RESET_ALPHA"),
            ("parent red alpha 80, overlay both", ['O.color = "#ff0000"', "O.alpha = 80"], "RESET_COLOR | RESET_ALPHA"),
            ("parent #ff000080 color, overlay RESET_ALPHA", ['O.color = "#ff000080"'], "RESET_ALPHA")]:
        lines = ['var/obj/O = render_x_obj(T, "grad")', *parent, ovl]
        if flags:
            lines.append(f"I.appearance_flags = {flags}")
        s.cell(f"overlay: {name}", lines + ["O.overlays += I"])
    s.cell("overlay: own color blue, parent red", [
        'var/obj/O = render_x_obj(T, "grad")', 'O.color = "#ff0000"', ovl, 'I.color = "#0000ff"', "O.overlays += I"])
    s.cell("overlay: own color blue RESET_COLOR, parent red", [
        'var/obj/O = render_x_obj(T, "grad")', 'O.color = "#ff0000"', ovl, 'I.color = "#0000ff"',
        "I.appearance_flags = RESET_COLOR", "O.overlays += I"])
    s.cell("overlay: own alpha 128, parent alpha 128", [
        'var/obj/O = render_x_obj(T, "grad")', "O.alpha = 128", ovl, "I.alpha = 128", "O.overlays += I"])
    s.cell("underlay: parent red, underlay RESET_COLOR", [
        'var/obj/O = render_x_obj(T, "half")', 'O.color = "#ff0000"',
        "var/image/I = image(icon = 'test.dmi', icon_state = \"grad\", pixel_x = 8)",
        "I.appearance_flags = RESET_COLOR", "O.underlays += I"])
    s.cell("underlay: parent alpha 80, underlay RESET_ALPHA", [
        'var/obj/O = render_x_obj(T, "half")', "O.alpha = 80",
        "var/image/I = image(icon = 'test.dmi', icon_state = \"grad\", pixel_x = 8)",
        "I.appearance_flags = RESET_ALPHA", "O.underlays += I"])

    # client.color (whole view)
    for name, col in [("#ff0000", '"#ff0000"'), ("swap rb 9", "list(0,0,1, 0,1,0, 1,0,0)"),
                      ("3 strings", 'list("#00ff00", "#0000ff", "#ff0000")'),
                      ("20 invert", "list(-1,0,0,0, 0,-1,0,0, 0,0,-1,0, 0,0,0,1, 1,1,1,0)"),
                      ("12 greyscale plus constant", "list(0.3,0.3,0.3, 0.59,0.59,0.59, 0.11,0.11,0.11, 0.1,0,0)")]:
        s.cell(f"solo: client.color {name}", [
            "render_x_solo()", 'var/obj/O = render_x_obj(T, "grad")',
            'var/obj/N = render_x_obj(T, "half")', "N.pixel_x = 32", "N.appearance_flags = NO_CLIENT_COLOR",
            f"live_client.color = {col}"], solo=True)
    s.cell("solo: client.color red with obj color blue", [
        "render_x_solo()", 'var/obj/O = render_x_obj(T, "grad")', 'O.color = "#0000ff"',
        'live_client.color = "#ff0000"'], solo=True)
