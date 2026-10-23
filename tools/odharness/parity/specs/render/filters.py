"""Render suite: every filter type, main parameters one at a time, flags, stacks, filters with overlays."""

BLUR = (0.10, 6.0)     # Gaussian kernels and sampling differ a little
WARP = (0.10, 8.0)     # distortion filters resample
RAYS = (0.30, 20.0)    # procedural noise


def build(s):
    s.render()
    n = [0]

    def tag():
        n[0] += 1
        return f"render_x_f{n[0]}"

    def f(name, state, filt, tol=None, pre=(), post=()):
        s.cell(name, [f'var/obj/O = render_x_obj(T, "{state}")', *pre, f"O.filters = {filt}", *post], tol=tol)

    # alpha
    m = "icon('test.dmi', \"half\")"
    f("alpha: mask half", "grad", f'filter(type = "alpha", icon = {m})')
    f("alpha: mask x 8", "grad", f'filter(type = "alpha", icon = {m}, x = 8)')
    f("alpha: mask x -12", "grad", f'filter(type = "alpha", icon = {m}, x = -12)')
    f("alpha: mask y 8", "grad", f'filter(type = "alpha", icon = {m}, y = 8)')
    f("alpha: MASK_INVERSE", "grad", f'filter(type = "alpha", icon = {m}, flags = MASK_INVERSE)')
    f("alpha: MASK_SWAP", "grad", f'filter(type = "alpha", icon = {m}, flags = MASK_SWAP)')
    f("alpha: MASK_INVERSE|MASK_SWAP", "grad", f'filter(type = "alpha", icon = {m}, flags = MASK_INVERSE | MASK_SWAP)')
    f("alpha: mask small 16x16 centred", "grad", 'filter(type = "alpha", icon = icon(\'small.dmi\', "solid"))')
    f("alpha: mask graded alpha", "solid", 'filter(type = "alpha", icon = icon(\'test.dmi\', "alpha"))')
    f("alpha: mask asym on half", "half", 'filter(type = "alpha", icon = icon(\'test.dmi\', "asym"))')
    for star in ("*", ""):
        t = star + tag()
        s.cell(f"alpha: render_source mask ({'hidden' if star else 'shown'} target)", [
            'var/obj/M = render_x_obj(T, "half")', f'M.render_target = "{t}"', "M.pixel_x = 32",
            'var/obj/O = render_x_obj(T, "grad")', f'O.filters = filter(type = "alpha", render_source = "{t}")'])

    # angular_blur
    for name, args in [("default", ""), ("size 5", ", size = 5"), ("size 20", ", size = 20"),
                       ("x 8 y -8", ", size = 10, x = 8, y = -8"), ("offset 8", ", size = 10, offset = 8")]:
        f(f"angular_blur: {name}", "asym", f'filter(type = "angular_blur"{args})', BLUR)

    # bloom
    for name, args in [("default", ""), ("threshold #808080", ', threshold = "#808080"'),
                       ("size 3", ', threshold = "#404040", size = 3'), ("offset 2", ', threshold = "#404040", offset = 2'),
                       ("alpha 128", ', threshold = "#404040", size = 2, alpha = 128')]:
        f(f"bloom: {name}", "grad", f'filter(type = "bloom"{args})', BLUR)

    # blur
    for name, args in [("default", ""), ("size 0", ", size = 0"), ("size 0.5", ", size = 0.5"), 
                       ("size 2", ", size = 2"), ("size 4", ", size = 4"), ("size 8", ", size = 8")]:
        f(f"blur: {name}", "asym", f'filter(type = "blur"{args})', BLUR)
    f("blur: size 3 on half", "half", 'filter(type = "blur", size = 3)', BLUR)

    # color
    for name, c in [("9 swap rb", "list(0,0,1, 0,1,0, 1,0,0)"),
                    ("12 with constant", "list(1,0,0, 0,1,0, 0,0,1, 0.2,0,0.4)"),
                    ("16 alpha half", "list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0.5)"),
                    ("20 invert", "list(-1,0,0,0, 0,-1,0,0, 0,0,-1,0, 0,0,0,1, 1,1,1,0)"),
                    ("greyscale matrix", "list(0.3,0.3,0.3, 0.59,0.59,0.59, 0.11,0.11,0.11)"),
                    ("colour strings", 'list("#00ff00", "#0000ff", "#ff0000")'),
                    ("text #ff8000", '"#ff8000"')]:
        f(f"color: {name}", "grad", f'filter(type = "color", color = {c})')
    f("color: 20 on alpha state", "alpha", 'filter(type = "color", color = list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,2, 0,0,0,0))')
    hue = "list(1,0,0, 0,1,0, 0,0,1, 0.5,0,0)"
    for sp in ("FILTER_COLOR_RGB", "FILTER_COLOR_HSV", "FILTER_COLOR_HSL", "FILTER_COLOR_HCY"):
        f(f"color: space {sp} shift", "grad", f'filter(type = "color", color = {hue}, space = {sp})', (0.03, 3.0))
    f("color: space HSV desaturate", "grad",
      'filter(type = "color", color = list(1,0,0, 0,0.2,0, 0,0,1), space = FILTER_COLOR_HSV)', (0.03, 3.0))

    # displace
    dm = "icon('test.dmi', \"grad\")"
    for name, args in [("size 4", ", size = 4"), ("size 8", ", size = 8"), ("size 16", ", size = 16"),
                       ("x 8", ", size = 8, x = 8"), ("y -8", ", size = 8, y = -8"),
                       ("FILTER_OVERLAY", ", size = 8, flags = FILTER_OVERLAY")]:
        f(f"displace: grad map {name}", "asym", f'filter(type = "displace", icon = {dm}{args})', WARP)
    f("displace: checker map size 4", "grad", 'filter(type = "displace", icon = icon(\'test.dmi\', "checker"), size = 4)', WARP)
    t = "*" + tag()
    s.cell("displace: render_source map", [
        'var/obj/M = render_x_obj(T, "grad")', f'M.render_target = "{t}"',
        'var/obj/O = render_x_obj(T, "asym")', f'O.filters = filter(type = "displace", render_source = "{t}", size = 6)'], tol=WARP)

    # drop_shadow
    for name, args in [("default", ""), ("x 4 y -4", ", x = 4, y = -4"), ("x -6 y 6", ", x = -6, y = 6"),
                       ("size 0", ", x = 4, y = -4, size = 0"), ("size 4", ", size = 4"), ("size -2 inset", ", size = -2"),
                       ("offset 2", ", offset = 2"), ("offset 3 size 0", ", x = 0, y = 0, offset = 3, size = 0"),
                       ("color red", ', x = 3, y = -3, color = "#ff0000"'),
                       ("color #00ff0080", ', x = 3, y = -3, size = 2, color = "#00ff0080"'),
                       ("halo", ', x = 0, y = 0, size = 5, offset = 2, color = rgb(255,255,170)')]:
        f(f"drop_shadow: {name}", "half", f'filter(type = "drop_shadow"{args})', BLUR)
    f("drop_shadow: on asym", "asym", 'filter(type = "drop_shadow", x = 2, y = -2, size = 1)', BLUR)

    # layer
    li = "icon('small.dmi', \"solid\")"
    for name, args in [("default overlay", ""), ("x 8 y -8", ", x = 8, y = -8"), ("FILTER_UNDERLAY", ", flags = FILTER_UNDERLAY"),
                       ("color red", ', color = "#ff0000"'), ("color matrix", ", color = list(0,0,1, 0,1,0, 1,0,0)"),
                       ("transform scale 2", ", transform = matrix(2, 0, 0, 0, 2, 0)"),
                       ("transform turn 90", ", transform = turn(matrix(), 90)"),
                       ("blend add", ", blend_mode = BLEND_ADD"), ("blend multiply", ", blend_mode = BLEND_MULTIPLY")]:
        f(f"layer: small {name}", "grad", f'filter(type = "layer", icon = {li}{args})',
          (0.05, 4.0) if "transform" in name else None)
    f("layer: asym over half", "half", 'filter(type = "layer", icon = icon(\'test.dmi\', "asym"))')
    t = "*" + tag()
    s.cell("layer: render_source", [
        'var/obj/M = render_x_obj(T, "asym")', f'M.render_target = "{t}"',
        'var/obj/O = render_x_obj(T, "half")', f'O.filters = filter(type = "layer", render_source = "{t}", x = 6)'])

    # motion_blur
    for name, args in [("default", ""), ("x 4", ", x = 4"), ("y 4", ", y = 4"), ("x 3 y 3", ", x = 3, y = 3"), ("x -6", ", x = -6")]:
        f(f"motion_blur: {name}", "asym", f'filter(type = "motion_blur"{args})', BLUR)

    # outline
    for name, args in [("default", ""), ("size 0.5", ", size = 0.5"), ("size 2", ", size = 2"), ("size 4", ", size = 4"),
                       ("color #00ffff80 size 2", ', size = 2, color = "#00ffff80"'),
                       ("OUTLINE_SHARP", ", size = 2, flags = OUTLINE_SHARP"), ("OUTLINE_SQUARE", ", size = 3, flags = OUTLINE_SQUARE"),
                       ("SHARP|SQUARE", ", size = 3, flags = OUTLINE_SHARP | OUTLINE_SQUARE")]:
        f(f"outline: half {name}", "half", f'filter(type = "outline"{args})', (0.05, 4.0))
    f("outline: asym size 1", "asym", 'filter(type = "outline", size = 1, color = "#ffff00")', (0.05, 4.0))
    f("outline: small icon size 2", "solid", 'filter(type = "outline", size = 2, color = "#ffffff")', (0.05, 4.0),
      pre=["O.icon = 'small.dmi'"])

    # radial_blur
    for name, args in [("default", ""), ("size 0.05", ", size = 0.05"), 
                       ("x 10 y 10", ", size = 0.08, x = 10, y = 10"), ("offset 8", ", size = 0.08, offset = 8")]:
        f(f"radial_blur: {name}", "asym", f'filter(type = "radial_blur"{args})', BLUR)

    # rays
    for name, args in [("default", ""), ("size 16", ", size = 16"), ("color red", ', size = 24, color = "#ff0000"'),
                       ("density 4", ", size = 24, density = 4"), 
                       ("threshold 0.9", ", size = 24, threshold = 0.9"),
                       ("factor 1", ", size = 24, factor = 1"), ("offset 3.5", ", size = 24, offset = 3.5"),
                       ("flags 0", ", size = 24, flags = 0"),
                       ("FILTER_OVERLAY", ", size = 24, flags = FILTER_OVERLAY"),
                       ("FILTER_UNDERLAY", ", size = 24, flags = FILTER_UNDERLAY")]:
        f(f"rays: {name}", "half", f'filter(type = "rays"{args})', RAYS)

    # ripple
    for name, args in [("default", ""), ("size 2 radius 12", ", size = 2, radius = 12"),
                       ("size 4 radius 12", ", size = 4, radius = 12"), ("repeat 6", ", size = 2, radius = 12, repeat = 6"),
                       ("falloff 0", ", size = 2, radius = 12, falloff = 0"),
                       ("x 8 y 8", ", size = 2, radius = 10, x = 8, y = 8"),
                       ("WAVE_BOUNDED", ", size = 3, radius = 14, flags = WAVE_BOUNDED")]:
        f(f"ripple: {name}", "asym", f'filter(type = "ripple"{args})', WARP)

    # wave
    for name, args in [("default", ""), ("x 8 size 2", ", x = 8, size = 2"), ("y 8 size 2", ", y = 8, size = 2"),
                       ("x 6 y 6 size 2", ", x = 6, y = 6, size = 2"),
                       ("offset 0.25", ", x = 8, size = 2, offset = 0.25"), ("offset 0.5", ", x = 8, size = 2, offset = 0.5"),
                       ("WAVE_SIDEWAYS", ", x = 8, size = 2, flags = WAVE_SIDEWAYS"),
                       ("WAVE_BOUNDED", ", x = 8, size = 3, flags = WAVE_BOUNDED"),
                       ("SIDEWAYS|BOUNDED", ", x = 8, size = 3, flags = WAVE_SIDEWAYS | WAVE_BOUNDED")]:
        f(f"wave: {name}", "asym", f'filter(type = "wave"{args})', WARP)

    # greyscale (OpenDream has it; BYOND reference does not list it)
    f("greyscale: grad", "grad", 'filter(type = "greyscale")')

    # stacks, in order
    o2 = 'filter(type = "outline", size = 2, color = "#ff0000")'
    b2 = 'filter(type = "blur", size = 2)'
    f("stack: blur then outline", "half", f"list({b2}, {o2})", BLUR)
    f("stack: outline then blur", "half", f"list({o2}, {b2})", BLUR)
    f("stack: color then drop_shadow", "half",
      'list(filter(type = "color", color = list(0,0,1, 0,1,0, 1,0,0)), filter(type = "drop_shadow", x = 4, y = -4, size = 0, color = "#ffff00"))')
    f("stack: drop_shadow then color", "half",
      'list(filter(type = "drop_shadow", x = 4, y = -4, size = 0, color = "#ffff00"), filter(type = "color", color = list(0,0,1, 0,1,0, 1,0,0)))')
    f("stack: wave then outline", "asym", f'list(filter(type = "wave", x = 8, size = 2), {o2})', WARP)
    f("stack: outline then alpha mask", "grad",
      f'list({o2}, filter(type = "alpha", icon = icon(\'test.dmi\', "half")))')
    f("stack: alpha mask then outline", "grad",
      f'list(filter(type = "alpha", icon = icon(\'test.dmi\', "half")), {o2})', (0.05, 4.0))
    f("stack: three outlines", "half",
      'list(filter(type = "outline", size = 1, color = "#ff0000"), filter(type = "outline", size = 1, color = "#00ff00"), filter(type = "outline", size = 1, color = "#0000ff"))',
      (0.05, 4.0))
    f("stack: layer then motion_blur", "half",
      'list(filter(type = "layer", icon = icon(\'small.dmi\', "solid"), x = 8), filter(type = "motion_blur", x = 4))', BLUR)
    f("stack: greyscale then color", "grad",
      'list(filter(type = "greyscale"), filter(type = "color", color = list(1,0,0, 0,0,0, 0,0,0)))')
    s.cell("stack: filters += one at a time", [
        'var/obj/O = render_x_obj(T, "half")',
        'O.filters += filter(type = "outline", size = 1, color = "#ffffff")',
        'O.filters += filter(type = "drop_shadow", x = 3, y = -3, size = 0, color = "#0000ff")'], tol=(0.05, 4.0))
    s.cell("stack: filters -= removes first", [
        'var/obj/O = render_x_obj(T, "half")',
        'O.filters = list(filter(type = "outline", size = 2, color = "#ff0000"), filter(type = "drop_shadow", x = 4, y = -4, size = 0))',
        "O.filters -= O.filters[1]"])
    s.cell("stack: change filter var after add", [
        'var/obj/O = render_x_obj(T, "half")',
        'O.filters = filter(type = "outline", size = 1, color = "#ff0000")',
        "var/dm_filter/F = O.filters[1]", "F.size = 3", 'F.color = "#00ff00"'], tol=(0.05, 4.0))

    # filters with overlays
    ov = "O.overlays += image(icon = 'small.dmi', icon_state = \"solid\", pixel_x = 20, pixel_y = 20)"
    f("overlays: outline, no KEEP_TOGETHER", "half", 'filter(type = "outline", size = 2, color = "#ffff00")', (0.05, 4.0), pre=[ov])
    f("overlays: outline, KEEP_TOGETHER", "half", 'filter(type = "outline", size = 2, color = "#ffff00")', (0.05, 4.0),
      pre=[ov, "O.appearance_flags = KEEP_TOGETHER"])
    f("overlays: drop_shadow with overlay", "half", 'filter(type = "drop_shadow", x = 4, y = -4, size = 0, color = "#000000")',
      pre=[ov])
    f("overlays: blur with underlay", "half", 'filter(type = "blur", size = 2)', BLUR,
      pre=["O.underlays += image(icon = 'test.dmi', icon_state = \"solid\", pixel_x = -10)"])
    f("overlays: wave, KEEP_TOGETHER", "half", 'filter(type = "wave", x = 8, size = 2)', WARP,
      pre=[ov, "O.appearance_flags = KEEP_TOGETHER"])
    f("overlays: color filter, overlay", "grad", 'filter(type = "color", color = list(0,0,1, 0,1,0, 1,0,0))', pre=[ov])
    s.cell("overlays: filter on the overlay image", [
        'var/obj/O = render_x_obj(T, "grad")',
        "var/image/I = image(icon = 'test.dmi', icon_state = \"half\", pixel_x = 12)",
        'I.filters = filter(type = "outline", size = 2, color = "#ff00ff")', "O.overlays += I"], tol=(0.05, 4.0))
    f("transformed: scale 2 then outline", "half", 'filter(type = "outline", size = 1, color = "#ffffff")', (0.05, 4.0),
      pre=["O.transform = matrix(2, 0, 0, 0, 2, 0)"])
    f("transformed: turn 90 then drop_shadow", "asym", 'filter(type = "drop_shadow", x = 4, y = -4, size = 0)',
      pre=["O.transform = turn(matrix(), 90)"])
    f("colored obj: outline keeps own color", "half", 'filter(type = "outline", size = 2, color = "#ffffff")', (0.05, 4.0),
      pre=['O.color = "#0000ff"'])
    f("alpha obj: drop_shadow", "half", 'filter(type = "drop_shadow", x = 4, y = -4, size = 0, color = "#ff0000")',
      pre=["O.alpha = 128"])
