"""Render suite: icon_state choices, dir, icon procs, image() and mutable_appearance overlays, appearance copies,
maptext."""

TEXT = (0.30, 25.0)   # fonts and antialiasing differ


def build(s):
    s.render()

    # icon_state choices
    for name, st in [("asym", '"asym"'), ('missing state', '"missing"'), ('"" state', '""'), ("null", "null"),
                     ("numeric 1", "1"), ("empty state", '"empty"'), ("moving state", '"moving"'),
                     ("case ASYM", '"ASYM"')]:
        s.cell(f"icon_state: {name}", ["var/obj/O = parity_track(new /obj(T))", "O.icon = 'test.dmi'", f"O.icon_state = {st}"])
    s.cell("icon_state: missing on small.dmi (no \"\" state)", [
        "var/obj/O = parity_track(new /obj(T))", "O.icon = 'small.dmi'", 'O.icon_state = "missing"'])
    s.cell("icon_state: null on small.dmi", ["var/obj/O = parity_track(new /obj(T))", "O.icon = 'small.dmi'"])
    s.cell("icon: rect.dmi wide", ['var/obj/O = render_x_obj(T, "wide", \'rect.dmi\')'])

    # dir
    dirs = ["NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST"]
    for st in ["dirs4", "dirs8"]:
        for d in dirs:
            s.cell(f"dir: {st} {d}", [f'var/obj/O = render_x_obj(T, "{st}")', f"O.dir = {d}"])
    s.cell("dir: dirs4 dir 0", ['var/obj/O = render_x_obj(T, "dirs4")', "O.dir = 0"])
    s.cell("dir: asym (1 dir) EAST", ['var/obj/O = render_x_obj(T, "asym")', "O.dir = EAST"])

    # icon procs
    def ic(name, ops, state="asym", src="'test.dmi'"):
        s.cell(f"icon proc: {name}", [f"var/icon/I = new({src})", *ops,
                                      f'var/obj/O = render_x_obj(T, "{state}")', "O.icon = I"])
    for mode in ["ICON_ADD", "ICON_SUBTRACT", "ICON_MULTIPLY", "ICON_OVERLAY", "ICON_AND", "ICON_OR", "ICON_UNDERLAY"]:
        ic(f"Blend rgb(0,100,200) {mode} on grad", [f"I.Blend(rgb(0, 100, 200), {mode})"], "grad")
    for mode in ["ICON_ADD", "ICON_MULTIPLY", "ICON_OVERLAY", "ICON_UNDERLAY"]:
        ic(f"Blend small icon {mode} on half", [f"I.Blend(icon('small.dmi', \"grad\"), {mode})"], "half")
    ic("Blend icon ICON_OVERLAY at x 10 y 10", ["I.Blend(icon('small.dmi', \"solid\"), ICON_OVERLAY, 10, 10)"], "half")
    ic("Blend rgba(255,0,0,128) ICON_OVERLAY", ["I.Blend(rgb(255, 0, 0, 128), ICON_OVERLAY)"], "grad")
    ic("Blend alpha state ICON_MULTIPLY", ["I.Blend(icon('test.dmi', \"alpha\"), ICON_MULTIPLY)"], "grad")
    for name, op in [("Shift EAST 4", "I.Shift(EAST, 4)"), ("Shift NORTH 4", "I.Shift(NORTH, 4)"),
                     ("Shift WEST 8 wrap", "I.Shift(WEST, 8, 1)"),
                     ("Turn 90", "I.Turn(90)"), ("Turn 180", "I.Turn(180)"),
                     ("Flip NORTH", "I.Flip(NORTH)"), ("Flip EAST", "I.Flip(EAST)"), ("Flip NORTHEAST", "I.Flip(NORTHEAST)"),
                     ("Crop 1,1,16,16", "I.Crop(1, 1, 16, 16)"), ("Crop 9,9,40,40", "I.Crop(9, 9, 40, 40)"),
                     ("Crop -7,-7,24,24", "I.Crop(-7, -7, 24, 24)"),
                     ("Scale 64x64", "I.Scale(64, 64)"), ("Scale 16x16", "I.Scale(16, 16)"), ("Scale 48x24", "I.Scale(48, 24)"),
                     ("Scale 33x33", "I.Scale(33, 33)"),
                     ("SwapColor solid red to blue", None),
                     ("DrawBox red 4,4,12,20", "I.DrawBox(rgb(255, 0, 0), 4, 4, 12, 20)"),
                     ("DrawBox null clears 1,1,16,32", "I.DrawBox(null, 1, 1, 16, 32)"),
                     ("SetIntensity 0.5", "I.SetIntensity(0.5)"),
                     ("SetIntensity 1.5 0.5 1", "I.SetIntensity(1.5, 0.5, 1)")]:
        if op is None:
            ic(name, ["I.SwapColor(rgb(200, 30, 30), rgb(0, 0, 255))"], "solid")
        else:
            ic(name, [op], "asym")
    ic("Turn 45", ["I.Turn(45)"], "asym")
    ic("Turn 90 on rect.dmi", ["I.Turn(90)"], "wide", "'rect.dmi'")
    ic("Scale 64x32 on rect.dmi", ["I.Scale(64, 32)"], "wide", "'rect.dmi'")
    ic("SwapColor rgba alpha 0 to opaque", ["I.SwapColor(rgb(0, 0, 0, 0), rgb(255, 255, 0))"], "half")
    for name, args in [("swap rb rgb strings", 'rgb(0,0,255), rgb(0,255,0), rgb(255,0,0)'),
                       ("9 numbers greyscale", "0.3,0.3,0.3, 0.59,0.59,0.59, 0.11,0.11,0.11"),
                       ("12 numbers constant", "1,0,0, 0,1,0, 0,0,1, 0.5,0,0"),
                       ("20 numbers invert", "-1,0,0,0, 0,-1,0,0, 0,0,-1,0, 0,0,0,1, 1,1,1,0"),
                       ("4 strings with constant", 'rgb(255,0,0), rgb(0,255,0), rgb(0,0,255), rgb(0,0,128)')]:
        ic(f"MapColors {name}", [f"I.MapColors({args})"], "grad")
    ic("Turn 90 then Flip EAST", ["I.Turn(90)", "I.Flip(EAST)"], "asym")
    ic("Flip EAST then Turn 90", ["I.Flip(EAST)", "I.Turn(90)"], "asym")
    ic("Scale 64 then Crop 17,17,48,48", ["I.Scale(64, 64)", "I.Crop(17, 17, 48, 48)"], "asym")
    ic("icon(file, state) then Turn 90", ["I = icon('test.dmi', \"asym\")", "I.Turn(90)"], "asym")
    ic("icon of dirs4 dir EAST", ["I = icon('test.dmi', \"dirs4\", EAST)"], "dirs4")
    ic("Insert new state", ["I.Insert(icon('small.dmi', \"grad\"), \"render_x_new\")"], "render_x_new")
    ic("Blend icon with dirs, dir WEST shown", ["I.Blend(rgb(0, 0, 100), ICON_ADD)"], "dirs4")
    s.cell("icon proc: dirs4 Turn 90 then dir EAST", [
        "var/icon/I = new('test.dmi')", "I.Turn(90)", 'var/obj/O = render_x_obj(T, "dirs4")', "O.icon = I", "O.dir = EAST"])
    s.cell("icon proc: dirs4 Flip EAST then dir EAST", [
        "var/icon/I = new('test.dmi')", "I.Flip(EAST)", 'var/obj/O = render_x_obj(T, "dirs4")', "O.icon = I", "O.dir = EAST"])

    # image() and mutable_appearance overlays
    s.cell("image: positional (icon, null, state)", [
        'var/obj/O = render_x_obj(T, "half")', "O.overlays += image('small.dmi', null, \"solid\")"])
    s.cell("image: positional (icon, state)", [
        'var/obj/O = render_x_obj(T, "half")', "O.overlays += image('small.dmi', \"grad\")"])
    s.cell("image: with layer and dir args", [
        'var/obj/O = render_x_obj(T, "half")', "O.overlays += image('test.dmi', null, \"dirs4\", 4, WEST)"])
    s.cell("image: pixel_x pixel_y color alpha", [
        'var/obj/O = render_x_obj(T, "half")', "var/image/I = image('test.dmi', icon_state = \"grad\")",
        "I.pixel_x = 10", "I.pixel_y = -6", 'I.color = "#ff8000"', "I.alpha = 160", "O.overlays += I"])
    s.cell("image: transform turn 90", [
        'var/obj/O = render_x_obj(T, "half")', "var/image/I = image('test.dmi', icon_state = \"asym\")",
        "I.transform = turn(matrix(), 90)", "O.overlays += I"])
    s.cell("image: from icon object", [
        'var/obj/O = render_x_obj(T, "half")', "var/icon/C = icon('test.dmi', \"asym\")", "C.Flip(EAST)",
        "O.overlays += image(C)"])
    s.cell("image: from an obj (copies appearance)", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/X = render_x_free("grad")', 'X.color = "#00ff00"',
        "var/image/I = image(X)", "I.pixel_x = 12", "O.overlays += I"])
    s.cell("image: changed after add (no effect)", [
        'var/obj/O = render_x_obj(T, "half")', "var/image/I = image('small.dmi', icon_state = \"solid\")",
        "O.overlays += I", "I.pixel_x = 16"])
    s.cell("mutable_appearance: new, set vars", [
        'var/obj/O = render_x_obj(T, "half")', "var/mutable_appearance/MA = new", "MA.icon = 'small.dmi'",
        'MA.icon_state = "grad"', "MA.pixel_x = 14", "MA.pixel_y = 14", "O.overlays += MA"])
    s.cell("mutable_appearance: from obj, color changed", [
        'var/obj/O = render_x_obj(T, "half")', 'var/obj/X = render_x_free("asym")',
        "var/mutable_appearance/MA = new(X)", 'MA.color = "#ff0000"', "MA.pixel_x = 10", "O.overlays += MA"])
    s.cell("mutable_appearance: with own overlay", [
        'var/obj/O = render_x_obj(T, "half")', "var/mutable_appearance/MA = new", "MA.icon = 'small.dmi'",
        'MA.icon_state = "solid"', "MA.overlays += image('small.dmi', icon_state = \"grad\", pixel_x = 8)", "O.overlays += MA"])
    s.cell("mutable_appearance: as underlay with alpha", [
        'var/obj/O = render_x_obj(T, "half")', "var/mutable_appearance/MA = new", "MA.icon = 'test.dmi'",
        'MA.icon_state = "solid"', "MA.alpha = 128", "MA.pixel_x = 8", "O.underlays += MA"])

    # appearance copies
    s.cell("appearance: copy obj appearance", [
        'var/obj/A = render_x_obj(T, "asym")', 'A.color = "#00ffff"', "A.transform = turn(matrix(), 90)", "A.pixel_x = -16",
        "var/obj/B = parity_track(new /obj(T))", "B.appearance = A.appearance", "B.pixel_x = 16"])
    s.cell("appearance: copy keeps overlays", [
        'var/obj/A = render_x_obj(T, "half")', "A.overlays += image('small.dmi', icon_state = \"solid\", pixel_x = 18)",
        "A.pixel_y = -16", "var/obj/B = parity_track(new /obj(T))", "B.appearance = A.appearance", "B.pixel_y = 16"])
    s.cell("appearance: from mutable_appearance", [
        "var/mutable_appearance/MA = new", "MA.icon = 'test.dmi'", 'MA.icon_state = "dirs4"', "MA.dir = EAST",
        "MA.alpha = 200", "var/obj/O = parity_track(new /obj(T))", "O.appearance = MA"])
    s.cell("appearance: from image", [
        "var/image/I = image('test.dmi', icon_state = \"grad\")", "I.color = list(0,0,1, 0,1,0, 1,0,0)",
        "var/obj/O = parity_track(new /obj(T))", "O.appearance = I"])
    s.cell("appearance: copy then change source", [
        'var/obj/A = render_x_obj(T, "asym")', "A.pixel_x = -16", "var/obj/B = parity_track(new /obj(T))",
        "B.appearance = A.appearance", "B.pixel_x = 16", 'A.icon_state = "solid"'])

    # maptext
    mt = lambda name, lines: s.cell(f"maptext: {name}", ['var/obj/O = render_x_obj(T, "empty")', *lines], tol=TEXT)
    mt("Hi", ['O.maptext = "Hi"'])
    mt("width 96 height 32", ['O.maptext = "Hello world"', "O.maptext_width = 96", "O.maptext_height = 32", "O.maptext_x = -32"])
    mt("maptext_x 8 maptext_y 8", ['O.maptext = "XY"', "O.maptext_x = 8", "O.maptext_y = 8"])
    mt("font color red", ['O.maptext = "<font color=red>Red</font>"'])
    mt("obj color blue", ['O.maptext = "Blue"', 'O.color = "#0000ff"'])
    mt("two lines", ['O.maptext = "AB<br>CD"', "O.maptext_height = 64"])
    mt("center align", ['O.maptext = "<center>Mid</center>"', "O.maptext_width = 64", "O.maptext_x = -16"])
    mt("over icon", ['O.icon_state = "half"', 'O.maptext = "OK"'])
    mt("scale 2", ['O.maptext = "Ab"', "O.transform = matrix(2, 0, 0, 0, 2, 0)"])
