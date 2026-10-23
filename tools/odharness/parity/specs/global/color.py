"""Colour builtins: rgb() (3/4/5 args, named components, colour spaces), rgb2num() (all spaces),
gradient() (argument and list forms, index/space named args, loop, skipped stops) and colour
normalization through atom/image/mutable_appearance .color (text and colour matrices).

Divergence targets read from OpenDream:
- rgb() goes through SharedOperations.ParseRgb both at compile time (EvalRgb folds constant calls)
  and at runtime, so every family is run with literal args AND through color_id() to defeat folding.
  ParseRgb truncates with a (byte) cast after clamping, has no HCY, treats only r/g/b/h/s/v/l/a
  names (no c=, y=), and a 4th null arg is the same as no alpha.
- rgb2num(): HCY throws NotImplemented in OD; alpha is appended based on the text length (5 or 9).
- gradient(): OD's "space" key inside a gradient list is enumerated as a value and parsed as a
  colour; HSL interpolation uses HSV in OD; loop uses index %= max.
- atom.color: OD returns null for white, drops alpha, and accepts matrix lists of 0-5/9/12/16/20.
"""
from gen import dm_str

HELPERS = r'''
/proc/color_id(x)
	return x

/proc/color_obj_set(v)
	var/obj/o = parity_track(new /obj(locate(1, 1, 1)))
	o.color = v
	return o.color

/proc/color_obj_set_alpha(v)
	var/obj/o = parity_track(new /obj(locate(1, 1, 1)))
	o.color = v
	return list(o.color, o.alpha)

/proc/color_img_set(v)
	var/image/i = new
	i.color = v
	return i.color

/proc/color_ma_set(v)
	var/mutable_appearance/m = new
	m.color = v
	return m.color

/proc/color_round_list(list/L, p = 0.001)
	if(!islist(L))
		return L
	var/list/out = list()
	for(var/x in L)
		out += isnum(x) ? round(x, p) : x
	return out
'''

# ---------- rgb ----------
# Components: in range, edges, fractional (rounding vs truncation), out of range, special floats
COMP = ["0", "1", "127", "127.5", "128", "254.5", "255", "256", "-1", "-0.5", "0.5", "1000", "PINF", "NAN",
        "null"]
COMP_S = ["0", "127.5", "255", "256", "-1", "0.5", "NAN", "null"]
ALPHA = ["0", "127.5", "128", "254.6", "255", "256", "-1", "0.5", "null", "NAN"]
WRONG = ['"10"', '"#ff0000"', '""', "list()", "list(1)", "/datum", "new /datum", "matrix()"]
SPACES = ["0", "1", "2", "3", "4", "-1", "1.5", "2.9", "null", '"1"', "COLORSPACE_RGB", "COLORSPACE_HSV",
          "COLORSPACE_HSL", "COLORSPACE_HCY", "100", "NAN"]
HUE = ["0", "30", "60", "120", "180", "210", "240", "300", "359.9", "360", "420", "720",
       "-30", "45.5", "NAN", "null"]
HUE_S = ["0", "60", "210", "359.9", "360", "420", "-30", "45.5"]
PCT = ["0", "25", "50", "66.6667", "100", "101", "-1", "NAN"]
PCT_S = ["0", "50", "100", "101", "-1", "33.3"]

# ---------- colours as text ----------
COLORS = ['"#ff8000"', '"#5af"', '"#5af8"', '"#ff800080"', '"#FF8000"', '"#FfA0b1"', '"#000"', '"#fff"',
          '"#000000"', '"#ffffff"', '"#ffffff00"', '"#00000000"', '"#ff8000ff"', '"#ff800000"', '"#80808080"',
          '"#7f7f7f"', '"#010203"', '"#fefefe"', '"#ca60db"', '"#123456"', '"#abcdef"',
          '"red"', '"RED"', '"Red"', '"black"', '"white"', '"transparent"', '"gray"', '"grey"', '"green"',
          '"lime"', '"gold"', '"olive"', '"aqua"', '"cyan"', '"magenta"', '"fuchsia"', '"navy"', '"teal"',
          '"silver"', '"maroon"', '"purple"', '"yellow"', '"blue"', '"orange"', '"pink"', '"none"',
          '"#12"', '"#1"', '"#12345"', '"#1234567"', '"#123456789"', '"#ggg"', '"#gg0000"', '"#ff80zz"',
          '"ff8000"', '"0xff8000"', '""', '"#"', '" #fff"', '"#fff "', '" red"', '"red "', '"#ff 80 00"',
          '"#-12345"', '"rgb(1,2,3)"', '"#fF"', "rgb(1, 2, 3)", "rgb(1, 2, 3, 4)",
          "null", "0", "16711680", "1.5", "list()", 'list("#f00")', "/datum", "new /datum"]
COLORS_S = ['"#ff8000"', '"#5af"', '"#5af8"', '"#ff800080"', '"red"', '"transparent"', '"#ca60db"',
            '"#gg0000"', '""', "null", "0"]
# Systematic colours for the colour-space conversions
HUES = ["#ff0000", "#ff8000", "#ffff00", "#80ff00", "#00ff00", "#00ff80", "#00ffff", "#0080ff", "#0000ff",
        "#8000ff", "#ff00ff", "#ff0080", "#000000", "#ffffff", "#808080", "#7f7f7f", "#010101", "#fefefe",
        "#400000", "#ffc0c0", "#123456", "#ca60db", "#55aaff", "#fe0102",
        "#00ff0080", "#ff000000", "#11223344"]
R2N_SPACES = ["0", "1", "2", "3", "4", "-1", "null", "1.5", '"1"', "COLORSPACE_HSL", "PINF", "NAN"]

# ---------- gradient ----------
GIDX = ["0", "0.1", "0.2", "0.25", "1/3", "0.5", "0.6", "0.75", "0.9", "0.99", "1", "1.2", "-0.2", "2"]
GIDX_S = ["0", "0.25", "0.5", "0.75", "1"]
GPAIRS = [('"red"', '"black"'), ('"red"', '"blue"'), ('"#000"', '"#fff"'), ('"#ff000000"', '"#ff0000ff"'),
          ('"#00ff0080"', '"#0000ff"'), ('"white"', '"transparent"'), ('"#123456"', '"#fedcba"'),
          ('"#f008"', '"#0f08"')]
GSPACE_PAIRS = [('"red"', '"blue"'), ('"red"', '"#0ff"'), ('"#ff0000"', '"#00ff0080"'),
                ('"black"', '"white"'), ('"#ff8000"', '"#0080ff"'), ('"#808080"', '"#ff0000"')]


def build(s):
    s.dm(HELPERS)
    build_rgb(s)
    build_rgb2num(s)
    build_gradient(s)
    build_normalize(s)
    build_gaps(s)


def build_rgb(s):
    P = "rgb"
    # ---- generic sweeps, constant (possibly folded at compile time) and runtime ----
    s.sweep(P, [COMP, COMP, COMP])
    s.sweep(P, [COMP, COMP_S, COMP_S],
            fmt=lambda r, g, b: f"rgb(color_id({r}), color_id({g}), color_id({b}))")
    s.sweep(P, [COMP_S, COMP_S, COMP_S, ALPHA], min_args=4)
    s.sweep(P, [COMP_S, COMP_S, COMP_S, ALPHA], min_args=4,
            fmt=lambda r, g, b, a: f"rgb(color_id({r}), color_id({g}), color_id({b}), color_id({a}))")
    # Every single component through 0..255 at runtime for rounding: one channel walked, the others fixed
    for v in ["0.49", "0.5", "0.51", "1.49", "1.5", "2.5", "3.5", "15.5", "16.4", "127.4", "127.6", "128.5",
              "200.5", "254.4", "254.49", "254.5", "254.51", "254.9", "255.4", "255.5", "255.9", "-0.4", "-0.6",
              "1e-7", "1e7", "-1e7", "16777216", "-16777216"]:
        s.case(P, f"rgb({v}, 0, 0)")
        s.case(P, f"rgb(0, color_id({v}), 0)")
        s.case(P, f"rgb(0, 0, 0, {v})")
        s.case(P, f"rgb(0, 0, 0, color_id({v}))")
    # Wrong-typed components in each position
    for w in WRONG:
        s.case(P, f"rgb({w}, 0, 0)")
        s.case(P, f"rgb(0, {w}, 0)")
        s.case(P, f"rgb(0, 0, {w})")
        s.case(P, f"rgb(0, 0, 0, {w})")
        s.case(P, f"rgb(color_id({w}), 128, 255)")
        s.case(P, f"rgb(10, 20, 30, color_id({w}))")
        s.case(P, f"rgb(10, 20, 30, null, color_id({w}))")
    # ---- argument counts ----
    for e in ["rgb()", "rgb(1)", "rgb(1, 2)", "rgb(1, 2, 3, 4, 0, 6)", "rgb(1, 2, 3, 4, 0, 6, 7)",
              "rgb(null, null, null)", "rgb(null, null, null, null)", "rgb(null, null, null, null, null)",
              "rgb(1, 2, 3, null)", "rgb(1, 2, 3, null, 0)", "rgb(1, 2, 3, 255)", "rgb(1, 2, 3, 255, 0)",
              "rgb(1, 2, 3, 0)", "rgb(255, 0, 128)", "rgb(0, 0, 0)", "rgb(255, 255, 255)",
              "rgb(20, 0, 0)", "rgb(1, 2, 3, , 0)", "rgb(1, 2, 3, ,)", "rgb(1, 2, , )", "rgb(, , 3)",
              "rgb(1, , 3)", "rgb(1, 2, )"]:
        s.case(P, e)
    # ---- space as the 5th argument and as space= ----
    for sp in SPACES:
        s.case(P, f"rgb(0, 100, 50, null, {sp})")
        s.case(P, f"rgb(0, 100, 50, , {sp})")
        s.case(P, f"rgb(0, 100, 50, space = {sp})")
        # All-number positional calls are folded by OD's peephole EvalRgb, which throws (and kills the
        # whole OD compile) on any space other than 0-2, so those go through color_id()
        lit = sp in ("0", "1", "2", "1.5", "2.9", "COLORSPACE_RGB", "COLORSPACE_HSV", "COLORSPACE_HSL")
        s.case(P, f"rgb(120, 50, 50, 128, {sp})" if lit else f"rgb(color_id(120), 50, 50, 128, {sp})")
        s.case(P, f"rgb(color_id(120), 50, 50, null, color_id({sp}))")
        s.case(P, f"rgb(200, 100, 50, space = color_id({sp}))")
    # The three documented-equivalent HSL red lines
    s.case(P, "rgb(0, 100, 50, space=COLORSPACE_HSL)")
    s.case(P, "rgb(0, 100, 50, , COLORSPACE_HSL)")
    s.case(P, "rgb(h=0, s=100, l=50)")
    s.case(P, "rgb(0, 100, 50, , COLORSPACE_HSL) == rgb(h=0, s=100, l=50)")
    s.case(P, "rgb(0, 100, 50, space = COLORSPACE_HSLA)")
    # ---- colour-space sweeps: hue x saturation x value/luminance/Y, folded and runtime ----
    for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY"):
        s.sweep(P, [HUE, PCT, PCT], fmt=lambda h, x, y, sp=sp: f"rgb({h}, {x}, {y}, space = {sp})")
        s.sweep(P, [HUE_S, PCT_S, PCT_S],
                fmt=lambda h, x, y, sp=sp: f"rgb(color_id({h}), color_id({x}), color_id({y}), null, {sp})")
        # Hue walk at full saturation, every 15 degrees, value/luminance at their pure-hue point
        mid = "100" if sp == "COLORSPACE_HSV" else "50"
        for h in range(-60, 781, 30):
            s.case(P, f"rgb({h}, 100, {mid}, space = {sp})")
        # Alpha in other spaces
        for a in ["0", "128", "255", "null", "300", "-5", "127.5"]:
            if sp == "COLORSPACE_HCY" and a != "null":
                s.case(P, f"rgb(color_id(240), 100, {mid}, {a}, {sp})")
            else:
                s.case(P, f"rgb(240, 100, {mid}, {a}, {sp})")
            x, y = {"COLORSPACE_HSV": ("s", "v"), "COLORSPACE_HSL": ("s", "l"), "COLORSPACE_HCY": ("c", "y")}[sp]
            s.case(P, f"rgb(h = 240, {x} = 100, {y} = {mid}, a = {a})")
    # ---- named arguments ----
    for e in ["rgb(r=255, g=128, b=0)", "rgb(red=255, green=128, blue=0)", "rgb(b=0, r=255, g=128)",
              "rgb(g=128, b=0, r=255)", "rgb(r=255, g=128, b=0, a=64)", "rgb(r=255, g=128, b=0, alpha=64)",
              "rgb(a=64, b=0, g=128, r=255)", "rgb(rouge=255, gruen=128, bleu=0)", "rgb(R=255, G=128, B=0)",
              "rgb(r=255)", "rgb(g=255)", "rgb(b=255)", "rgb(a=128)", "rgb(r=255, g=128)", "rgb(r=1, g=2, b=3, a=null)",
              "rgb(255, g=128, b=0)", "rgb(255, 128, b=0)", "rgb(255, 128, 0, a=10)", "rgb(255, 128, 0, alpha=10)",
              "rgb(r=255, 128, 0)", "rgb(r=1, r=2, g=3, b=4)", "rgb(r=1, red=2, g=3, b=4)",
              "rgb(x=1, y=2, z=3)", "rgb(q=1, g=2, b=3)", "rgb(r=255, g=0, b=0, space=COLORSPACE_HSV)",
              "rgb(r=255, g=0, b=0, space=COLORSPACE_RGB)", "rgb(r=255, g=0, b=0, space=0)",
              "rgb(h=0, s=100, v=100)", "rgb(hue=0, saturation=100, value=100)", "rgb(h=120, s=100, v=50)",
              "rgb(h=240, s=50, v=100)", "rgb(v=100, s=100, h=60)", "rgb(h=0, s=100, l=50)",
              "rgb(hue=0, saturation=100, luminance=50)", "rgb(h=120, s=100, l=25)", "rgb(h=200, s=50, l=75)",
              "rgb(l=50, h=300, s=100)", "rgb(h=0, c=100, y=29.9)", "rgb(hue=0, chroma=100, y=29.9)",
              "rgb(h=120, c=100, y=58.7)", "rgb(h=240, c=100, y=11.4)", "rgb(h=0, c=0, y=50)",
              "rgb(h=60, c=50, y=50)", "rgb(y=50, c=50, h=60)", "rgb(h=0, s=100, y=50)", "rgb(h=0, c=100, l=50)",
              "rgb(h=0, c=100, v=100)", "rgb(h=0, s=100)", "rgb(h=0)", "rgb(s=100, v=100)", "rgb(l=50)",
              "rgb(v=100)", "rgb(y=50)", "rgb(c=100)", "rgb(h=0, s=100, v=100, a=128)",
              "rgb(h=0, s=100, l=50, alpha=0)", "rgb(h=0, c=100, y=29.9, a=200)",
              "rgb(h=0, s=100, v=100, space=COLORSPACE_HSL)", "rgb(h=0, s=100, l=50, space=COLORSPACE_HSV)",
              "rgb(h=0, s=100, v=100, space=COLORSPACE_RGB)", "rgb(h=0, s=100, l=50, space=COLORSPACE_HCY)",
              "rgb(0, 100, 100, space=COLORSPACE_HSV)", "rgb(h=0, g=100, b=50)", "rgb(r=0, s=100, l=50)",
              "rgb(r=255, s=100, v=100)", "rgb(h=30, s=100, v=100, b=0)", "rgb(red=10, green=20, blue=30, alpha=40)",
              "rgb(r=-10, g=300, b=127.5)", "rgb(h=-30, s=100, v=100)", "rgb(h=390, s=100, v=100)",
              "rgb(h=720, s=100, l=50)", "rgb(h=0, s=200, v=200)", "rgb(h=0, s=-10, v=50)", "rgb(h=NAN, s=100, v=100)",
              "rgb(space=COLORSPACE_HSV, 0, 100, 100)", "rgb(0, 100, 100, space=COLORSPACE_HSV, a=128)",
              "rgb(0, 100, 100, 128, space=COLORSPACE_HSV)", "rgb(0, 100, 50, null, space=COLORSPACE_HSL)",
              "rgb(1, 2, 3, space=null)", "rgb(1, 2, 3, space=\"hsv\")", "rgb(Space=1, h=0, s=100, v=100)",
              "rgb(spaces=1, h=0, s=100, v=100)", "rgb(h=0, s=100, v=100, sp=2)"]:
        s.case(P, e)
    # Named args at runtime too
    for e in ["rgb(r=color_id(255), g=color_id(128), b=color_id(0))", "rgb(h=color_id(0), s=100, v=100)",
              "rgb(h=color_id(210), s=100, l=color_id(66.6667))", "rgb(h=color_id(0), c=100, y=color_id(29.9))",
              "rgb(r=color_id(1.5), g=color_id(2.5), b=color_id(254.5), a=color_id(127.5))",
              "rgb(h=color_id(370), s=100, v=100)", "rgb(color_id(0), color_id(100), color_id(50), space=color_id(2))"]:
        s.case(P, e)
    # Result kind, case and length
    for e in ["istext(rgb(1, 2, 3))", "length(rgb(1, 2, 3))", "length(rgb(1, 2, 3, 4))", "rgb(171, 205, 239)",
              "rgb(171, 205, 239) == \"#abcdef\"", "uppertext(rgb(171, 205, 239, 1))",
              "rgb(10, 20, 30) + \"x\"", "list(rgb(255, 0, 0), rgb(0, 255, 0, 0))"]:
        s.case(P, e)
    # Arguments passed through arglist
    for e in ['rgb(arglist(list(1, 2, 3)))', 'rgb(arglist(list(1, 2, 3, 4)))', 'rgb(arglist(list(0, 100, 50, null, 2)))',
              'rgb(arglist(list("r" = 1, "g" = 2, "b" = 3)))', 'rgb(arglist(list("h" = 0, "s" = 100, "v" = 100)))',
              'rgb(arglist(list("h" = 0, "s" = 100, "l" = 50, "a" = 9)))', 'rgb(arglist(list()))',
              'rgb(arglist(list(1, 2)))', 'rgb(arglist(list(0, 100, 50, "space" = 2)))']:
        s.case(P, e)
    # Use as a proc reference / stored in a var
    s.body(P, ["var/c = rgb(12, 34, 56)", 'c += "ff"'], "c")
    s.body(P, ["var/list/out = list()", "for(var/i in 0 to 16)", "\tout += rgb(i * 16, 255 - i * 16, i)"], "out")
    s.body(P, ["var/list/out = list()", "for(var/i in 0 to 12)", "\tout += rgb(i * 30, 100, 50, null, COLORSPACE_HSL)"],
           "out")
    s.body(P, ["var/list/out = list()", "for(var/i in 0 to 12)", "\tout += rgb(i * 30, 100, 50, null, COLORSPACE_HCY)"],
           "out")
    s.body(P, ["var/list/out = list()", "for(var/i in 0 to 10)", "\tout += rgb(0, 0, 0, i * 25.5)"], "out")


def build_rgb2num(s):
    P = "rgb2num"
    s.sweep(P, [COLORS])
    s.sweep(P, [COLORS_S, R2N_SPACES])
    # Each documented space across systematic colours (rounded so float noise does not swamp the diff,
    # plus raw for a few)
    for c in HUES:
        src = dm_str(c)
        for sp in ("COLORSPACE_RGB", "COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY"):
            s.case(P, f"color_round_list(rgb2num({src}, {sp}))")
        s.case(P, f"rgb2num({src}, COLORSPACE_HCY)")
        # Round trip back through rgb() in each space
        for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY"):
            s.body(P, [f"var/list/L = rgb2num({src}, {sp})"], f"rgb(L[1], L[2], L[3], space = {sp})")
        s.body(P, [f"var/list/L = rgb2num({src})"], "L.len == 4 ? rgb(L[1], L[2], L[3], L[4]) : rgb(L[1], L[2], L[3])")
    s.body(P, ['var/list/L = rgb2num("#ff8000")'], "rgb(arglist(L))")
    s.body(P, ['var/list/L = rgb2num("#ff800080")'], "rgb(arglist(L))")
    # Documented examples
    s.body(P, ['var/list/RGB = rgb2num("#ff8000")'], "list(RGB[1], RGB[2], RGB[3], RGB.len)")
    s.body(P, ['var/list/HSL = rgb2num("#5af", COLORSPACE_HSL)'], "list(HSL[1], HSL[2], HSL[3], HSL.len)")
    # Named arguments, runtime values, argument counts
    for e in ['rgb2num(color = "#ff8000")', 'rgb2num("#ff8000", space = COLORSPACE_HSV)',
              'rgb2num(color = "#5af", space = 2)', 'rgb2num(space = 1, color = "#f00")', 'rgb2num()',
              'rgb2num("#f00", 1, 2)', 'rgb2num(color_id("#ff8000"), color_id(1))', 'rgb2num(c = "#ff8000")',
              'rgb2num("#f00", s = 1)', 'rgb2num(rgb(1, 2, 3, 4), 2)', 'rgb2num(rgb(1, 2, 3, null))',
              'rgb2num(rgb(0, 100, 50, null, COLORSPACE_HSL), COLORSPACE_HSL)',
              'rgb2num("#ff8000")[1]', 'length(rgb2num("#ff800080"))', 'length(rgb2num("#ff8000"))',
              'length(rgb2num("#ff8f"))', 'length(rgb2num("red"))', 'length(rgb2num("transparent"))',
              'islist(rgb2num("#000"))']:
        s.case(P, e)
    # Result list is a fresh list each call
    s.body(P, ['var/list/A = rgb2num("#102030")', 'var/list/B = rgb2num("#102030")', "A[1] = 99"],
           "list(A, B, A == B)")
    s.body(P, ['var/list/A = rgb2num("#102030")', 'A += 5'], "A")


def build_gradient(s):
    P = "gradient"
    # ---- two-colour argument form at many indices ----
    for a, b in GPAIRS:
        for i in GIDX:
            s.case(P, f"gradient({a}, {b}, {i})")
        s.case(P, f"gradient({a}, {b}, color_id(0.5))")
        s.case(P, f"gradient(list({a}, {b}), 0.5)")
    # Documented example
    s.case(P, 'gradient("red", "black", 0.2)')
    # Index values of every kind
    for i in ["0", "0.5", "1", "-1", "1e7", "-1e7", "PINF", "NINF", "NAN", "null", '"0.5"', '"abc"', "list()",
              "new /datum", "/datum", "0.0001", "0.9999", "1e-7"]:
        s.case(P, f'gradient("#000", "#fff", {i})')
        s.case(P, f'gradient(list("#000", "#fff"), {i})')
        s.case(P, f'gradient(list("#000", "#fff", "loop"), {i})')
    # Colour/stop values of other kinds
    for v in ['"notacolor"', '"#ggg"', '""', "null", "5", "list()", "new /datum", "/datum", '"#f008"',
              '"#ff000080"', '"transparent"', '"RED"', '"loop"', "NAN"]:
        s.case(P, f'gradient({v}, "#fff", 0.5)')
        s.case(P, f'gradient("#000", {v}, 0.5)')
        s.case(P, f'gradient(list("#000", {v}), 0.25)')
        s.case(P, f'gradient(list(0, "#000", 1, {v}), 0.75)')
    # ---- colour spaces: space= in argument form and "space"= in list form ----
    for sp in ["COLORSPACE_RGB", "COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY"]:
        for a, b in GSPACE_PAIRS:
            for i in GIDX_S:
                s.case(P, f"gradient({a}, {b}, {i}, space = {sp})")
            for i in ("0.25",):
                s.case(P, f'gradient(list({a}, {b}, "space" = {sp}), {i})')
                s.case(P, f"gradient({a}, {b}, space = {sp}, index = {i})")
                s.case(P, f'gradient(list(0, {a}, 1, {b}, "space" = {sp}, "loop"), {i} + 1)')
    for sp in ["4", "-1", "null", '"hsl"', "1.5", "COLORSPACE_HSLA"]:
        s.case(P, f'gradient("red", "blue", 0.5, space = {sp})')
        s.case(P, f'gradient(list("red", "blue", "space" = {sp}), 0.5)')
    # ---- named index / space, argument shapes ----
    for e in ['gradient("red", "blue", index = 0.25)', 'gradient(index = 0.25, "red", "blue")',
              'gradient("red", index = 0.25, "blue")', 'gradient("red", "blue", 0.75, index = 0.25)',
              'gradient(list("red", "blue"), index = 0.25)', 'gradient(list("red", "blue"), 0.25, space = 2)',
              'gradient(list("red", "blue"), 0.25, space = COLORSPACE_HSV)', 'gradient(list("red", "blue"))',
              'gradient("red", "blue")', 'gradient("red", 0.5)', 'gradient("red")', 'gradient()', 'gradient(0.5)',
              'gradient(list(), 0.5)', 'gradient(list("red"), 0.5)', 'gradient(list("red"), 2)',
              'gradient(list(0.5), 0.5)', 'gradient(list("loop"), 0.5)', 'gradient(list(0, 1), 0.5)',
              'gradient(null, 0.5)', 'gradient(5, 0.5)', 'gradient(new /datum, 0.5)',
              'gradient(list("red", "blue"), list("red", "blue"), 0.5)', 'gradient("red", "lime", "blue", 0.5)',
              'gradient("red", "lime", "blue", 0.25)', 'gradient("red", "lime", "blue", 0.75)',
              'gradient(0, "red", 1, "blue", 0.5)', 'gradient(0, "red", 2, "blue", 1)',
              'gradient("red", "blue", "loop", 1.25)', 'gradient("red", "blue", Index = 0.25)',
              'gradient("red", "blue", idx = 0.25)', 'gradient("red", "blue", 0.5, Space = 1)',
              'gradient(arglist(list("red", "blue", 0.25)))', 'gradient(arglist(list("red", "blue", "index" = 0.25)))',
              'gradient(arglist(list("red", "blue", 0.25, "space" = 1)))', 'gradient(arglist(list(list("red", "blue"), 0.25)))',
              'gradient(color_id("red"), color_id("blue"), color_id(0.25))']:
        s.case(P, e)
    # Documented loop example: HSL colour wheel 0..6, index 10 -> 4 (blue)
    s.case(P, 'gradient(0, "#f00", 3, "#0ff", 6, "#f00", "loop", space=COLORSPACE_HSL, index=10)')
    s.case(P, 'gradient(0, "#f00", 3, "#0ff", 6, "#f00", "loop", space=COLORSPACE_HSL, index=4)')
    s.case(P, 'gradient(0, "#f00", 3, "#0ff", 6, "#f00", "loop", index=10)')
    s.case(P, 'gradient(0, "#f00", 3, "#0ff", 6, "#f00", space=COLORSPACE_HSL, index=10)')
    # ---- documented gradient lists walked by index ----
    LISTS = [
        'list("red", "white")',
        'list(0, "red", 1, "white")',
        'list(0, "#f00", 1, "#ff0", 2, "#0f0", 3, "#0ff", 4, "#00f", 5, "#f0f", 6, "#f00", "loop")',
        'list(0.1, "#f00", 0.3, "#ff0", 0.4, 0.6, "#008000", 0.7, 0.9, "#00f")',
        'list(0.5, "#008000", 0.5, "#000000", "loop")',
        'list(0.5, "red", 0.5, "white", "loop")',
        'list(0, "#f00", 3, "#0ff", 6, "#f00", "loop", "space" = COLORSPACE_HSL)',
        'list(0.2, 0.5, "red", "blue")',
        'list("red", 0.5, "blue")',
        'list("red", "lime", "blue")',
        'list("red", "lime", 0.8, "blue")',
        'list(0.25, "red", 0.75, "blue")',
        'list(1, "red", 0, "blue")',
        'list(0, "red", 0.5, "lime", 0.5, "blue", 1, "white")',
        'list(-1, "red", 2, "blue")',
        'list(-1, "red", 2, "blue", "loop")',
        'list(0, "red", 1, "blue", 2)',
        'list(0, "red", "loop", 1, "blue")',
        'list("loop", "red", "blue")',
        'list(0, "#ff000000", 1, "#ff0000ff")',
        'list(0, "red", 0.5, null, 1, "blue")',
        'list(0, "red", 0.5, 0.6, 0.7, "blue")',
        'list(0, "red", 1, "blue", "space" = COLORSPACE_HSV, "loop")',
        'list(0, "red", 1, "blue", "space" = COLORSPACE_HCY)',
    ]
    WALK = ["-0.5", "0", "0.1", "0.25", "0.5", "0.65", "0.75", "0.9", "1", "1.5", "2", "10"]
    for L in LISTS:
        for i in WALK:
            s.case(P, f"gradient({L}, {i})")
    # Same lists passed as separate arguments
    for L in LISTS[:12]:
        inner = L[len("list("):-1]
        if '"space"' in inner:
            continue
        for i in ("0", "0.35", "0.5", "1", "1.5"):
            s.case(P, f"gradient({inner}, {i})")
    # Candy cane doc example at fixed times
    for t in range(0, 200, 13):
        s.body(P, ['var/candy_cane_gradient = list(0.5, "red", 0.5, "white", "loop")'],
               f"gradient(candy_cane_gradient, {t} / 100)")
    # The gradient list is not modified by the call
    s.body(P, ['var/list/G = list(0.5, "red", "white", "loop", "space" = 1)', "var/c = gradient(G, 0.7)"], "list(G, c)")
    # Many stops
    s.body(P, ["var/list/G = list()", "for(var/i in 0 to 20)", "\tG += i / 20", "\tG += rgb(i * 12, 0, 255 - i * 12)",
               "var/list/out = list()", "for(var/j in 0 to 10)", "\tout += gradient(G, j / 10 + 0.025)"], "out")
    s.body(P, ["var/list/out = list()", "for(var/j in 0 to 20)", '\tout += gradient("#000000", "#ffffff", j / 20)'], "out")
    s.body(P, ["var/list/out = list()", "for(var/j in 0 to 20)", '\tout += gradient("#00000000", "#ffffffff", j / 20)'],
           "out")
    s.body(P, ["var/list/out = list()", "for(var/j in 0 to 12)",
               '\tout += gradient("#ff0000", "#0000ff", j / 12, space = COLORSPACE_HSV)'], "out")
    s.body(P, ["var/list/out = list()", "for(var/j in 0 to 12)",
               '\tout += gradient("#ff0000", "#0000ff", j / 12, space = COLORSPACE_HSL)'], "out")
    s.body(P, ["var/list/out = list()", "for(var/j in 0 to 12)",
               '\tout += gradient("#ff0000", "#0000ff", j / 12, space = COLORSPACE_HCY)'], "out")


def build_normalize(s):
    # ---- text colours through atom/image/mutable_appearance .color ----
    for c in COLORS:
        s.case("color_var", f"color_obj_set({c})")
    for c in COLORS_S + ['"#FF8000"', '"white"', '"#ffffffff"', '"#fff"', '"WHITE"']:
        s.case("color_var", f"color_img_set({c})")
        s.case("color_var", f"color_ma_set({c})")
        s.case("color_var", f"color_obj_set_alpha({c})")
    # Default values
    for e in ["new /obj().color", "new /image().color", "new /mutable_appearance().color"]:
        s.case("color_var", e)
    # ---- colour matrices ----
    MATS = [
        "list()",
        'list("#f00")', 'list("#f00", "#0f0")', 'list("#f00", "#0f0", "#00f")', 'list("#f00", "#0f0", "#00f", "#000f")',
        'list("#f00", "#0f0", "#00f", "#000f", "#000")', 'list("#f00", "#0f0", "#00f", "#000f", "#0000")',
        'list("#f00", "#0f0", "#00f", "#000f", "#333", "#444")', 'list("#f00", null, "#00f")',
        'list(null, null, null)', 'list("#0f0", "#00f", "#f00")', 'list("#ff000080", "#00ff0080", "#0000ff80")',
        'list("red", "lime", "blue")', 'list(rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255), rgb(0, 0, 0, 255), rgb(51, 51, 51))',
        'list("#fff", "#fff", "#fff")', 'list("notacolor", "#0f0", "#00f")', 'list(1, "#0f0", "#00f")',
        "list(1, 0, 0, 0, 1, 0, 0, 0, 1)",
        "list(0.33, 0.33, 0.33, 0.59, 0.59, 0.59, 0.11, 0.11, 0.11)",
        "list(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.1, 0.2, 0.3)",
        "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)",
        "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0)",
        "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5, 0.1, 0.2, 0.3, 0)",
        "list(-1, 0, 0, 0, -1, 0, 0, 0, -1, 1, 1, 1)",
        "list(2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0)",
        "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)",
        "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)", "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)",
        "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)", "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)",
        "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)",
        "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)",
        "list(1, 2, 3, 4, 5, 6, 7, 8)", "list(1, 2, 3, 4, 5, 6)", "list(1)",
        'list(1, 0, 0, 0, 1, 0, 0, 0, "x")', "list(1, 0, 0, 0, 1, 0, 0, 0, null)", "list(1, 0, 0, 0, 1, 0, 0, 0, NAN)",
        "list(1, 0, 0, 0, 1, 0, 0, 0, 1e7)", "list(0.5, 0, 0, 0, 0.5, 0, 0, 0, 0.5)",
        "list(list(1, 0, 0), list(0, 1, 0), list(0, 0, 1))",
    ]
    for m in MATS:
        s.case("color_matrix", f"color_obj_set({m})")
    for m in MATS[:4] + MATS[17:23]:
        s.case("color_matrix", f"color_img_set({m})")
        s.case("color_matrix", f"color_ma_set({m})")
        s.case("color_matrix", f"color_obj_set_alpha({m})")
    # Matrix read back is a copy; setting text after a matrix; identity matrix collapses back?
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "o.color = list(1, 0, 0, 0, 1, 0, 0, 0, 1)"], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "o.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", 'o.color = "#f00"'], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            'o.color = "#f00"', "o.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)"], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "o.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "var/list/L = o.color", "L[1] = 7"], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "o.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "o.color = null"], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "var/list/M = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "o.color = M", "M[1] = 9"], "o.color")
    s.body("color_matrix", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                            "o.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)"], "o.color == o.color")
    s.body("color_var", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))", 'o.color = "#ff000080"',
                         "o.alpha = 10"], "list(o.color, o.alpha)")
    s.body("color_var", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))", "o.alpha = 10",
                         'o.color = "#ff000080"'], "list(o.color, o.alpha)")
    s.body("color_var", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))", 'o.color = "red"'],
           "rgb2num(o.color)")
    s.body("color_var", ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))", 'o.color = rgb(10, 20, 30)'],
           "o.color == rgb(10, 20, 30)")
    # Compile-time initial values on a type
    s.dm('/obj/color_tinted\n\tcolor = "#F00"\n\n/obj/color_named\n\tcolor = "blue"\n\n/obj/color_rgbvar\n\tcolor = rgb(1, 2, 3)'
         '\n\n/obj/color_alphavar\n\tcolor = "#11223344"\n\n/obj/color_mtx\n\tcolor = list(0, 1, 0, 1, 0, 0, 0, 0, 1)')
    for t in ("color_tinted", "color_named", "color_rgbvar", "color_alphavar", "color_mtx"):
        s.body("color_var", [f"var/obj/o = parity_track(new /obj/{t}(locate(1, 1, 1)))"], "o.color")
        s.body("color_var", [f"var/obj/{t}/o = parity_track(new /obj/{t}(locate(1, 1, 1)))", 'o.color = "#0f0"'], "initial(o.color)")


GAP_HELPERS = r"""
/proc/color_img_set_alpha(v, pre)
	var/image/i = new
	if(!isnull(pre))
		i.alpha = pre
	i.color = v
	return list(i.color, i.alpha)

/proc/color_ma_set_alpha(v, pre)
	var/mutable_appearance/m = new
	if(!isnull(pre))
		m.alpha = pre
	m.color = v
	return list(m.color, m.alpha)

/proc/color_obj_set_alpha_pre(v, pre)
	var/obj/o = parity_track(new /obj(locate(1, 1, 1)))
	o.alpha = pre
	o.color = v
	return list(o.color, o.alpha)

/obj/color_alpha_before
	alpha = 10
	color = "#ff000080"

/obj/color_alpha_after
	color = "#ff000080"
	alpha = 10

/obj/color_alpha_short
	color = "#5af8"
"""


def build_gaps(s):
    """Gaps found by review: gradient hue swap / seam / near-edge indices / offset loops, rgb() named
    space ordering and name spelling, constant folding contexts, alpha side effects, filters, raw rgb2num."""
    s.dm(GAP_HELPERS)
    G = "gradient"
    # ---- HSV/HSL hue swap: higher hue first, S/V/A differ (OD swaps only the hue) ----
    REV = [('"#00ff0080"', '"#ff0000"'), ('"#0000ff"', '"#400000"'), ('"blue"', '"red"'),
           ('"#00ffff"', '"#ff000080"'), ('"#0000ff80"', '"#80ff80"'), ('"#ff00ff"', '"#004000"')]
    for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY"):
        for a, b in REV:
            for i in ("0.25", "0.75"):
                s.case(G, f"gradient({a}, {b}, {i}, space = {sp})")
                s.case(G, f"gradient({b}, {a}, {i}, space = {sp})")
        for i in ("0.25", "0.75"):
            s.case(G, f'gradient(list(0, "#00f", 1, "#f00", "space" = {sp}), {i})')
            s.case(G, f'gradient(list(0, "#0000ff80", 1, "#400000", "space" = {sp}), {i})')
    # ---- hue across the 0/360 seam (shortest-path wrap) ----
    SEAM = [('"#ff0080"', '"#ff8000"'), ('"#ff8000"', '"#ff0080"'), ('"#ff0040"', '"#ff4000"'),
            ('"#ff00ff"', '"#ffff00"'), ('"#800040"', '"#ff8000"')]
    for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY", "COLORSPACE_RGB"):
        for a, b in SEAM:
            for i in ("0.25", "0.5", "0.75"):
                s.case(G, f"gradient({a}, {b}, {i}, space = {sp})")
    # ---- colour-space index near 0 and 1 (OD nudges by 0.001 / 0.00445 in HSV/HSL) ----
    NEAR = ["0.001", "0.01", "0.04", "0.049", "0.05", "0.051", "0.9", "0.901", "0.95", "0.99", "0.999"]
    for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL", "COLORSPACE_HCY", "COLORSPACE_RGB"):
        for i in NEAR:
            s.case(G, f'gradient("#ff0000", "#0000ff", {i}, space = {sp})')
    for i in NEAR:
        s.case(G, f'gradient(list(0, "#ff0000", 1, "#0000ff", "space" = COLORSPACE_HSV), {i})')
        s.case(G, f'gradient("#00ff00", "#ff00ff80", {i}, space = COLORSPACE_HSL)')
    # ---- loop ranges that do not start at 0 (OD: index %= max) ----
    for L in ['list(1, "red", 3, "blue", "loop")', 'list(0.5, "red", 1.5, "blue", "loop")',
              'list(1, "red", 3, "blue")', 'list(2, "red", 3, "lime", 4, "blue", "loop")']:
        for i in ("0", "0.25", "0.75", "1", "1.7", "3", "3.5", "4.2", "-0.5", "-2.5"):
            s.case(G, f"gradient({L}, {i})")
    WHEEL = 'list(0, "#f00", 1, "#ff0", 2, "#0f0", 3, "#0ff", 4, "#00f", 5, "#f0f", 6, "#f00", "loop")'
    for i in ("6", "12", "-6", "5.999", "6.001", "-0.001", "18", "7"):
        s.case(G, f"gradient({WHEEL}, {i})")
        s.case(G, f'gradient(0, "#f00", 3, "#0ff", 6, "#f00", "loop", space=COLORSPACE_HSL, index={i})')
    # ---- associated entries / other keys inside a gradient list ----
    for e in ['gradient(list("red" = 0.5, "blue"), 0.25)', 'gradient(list("red" = 0.5, "blue"), 0.75)',
              'gradient(list(0, "red", "index" = 0.9, 1, "blue"), 0.25)',
              'gradient(list(0, "red", 1, "blue", "loop" = 1), 1.25)',
              'gradient(list(0, "red", 1, "blue", "loop" = 0), 1.25)',
              'gradient(list(0, "red", 1, "blue", "Space" = 1), 0.25)',
              'gradient(list(0, "red", 1, "blue", "foo" = 2), 0.25)',
              'gradient(list(0, "red", 0.5 = "lime", 1, "blue"), 0.25)',
              'gradient(list(0 = "red", 1 = "blue"), 0.25)']:
        s.case(G, e)

    # ---- rgb(): named space= before named components ----
    R = "rgb"
    for e in ["rgb(space=COLORSPACE_HSV, h=0, s=100, v=100)", "rgb(h=0, space=COLORSPACE_HSL, s=100, l=50)",
              "rgb(space=COLORSPACE_HSL, 0, 100, 50)", "rgb(r=255, space=COLORSPACE_RGB, g=0, b=0)",
              "rgb(space=COLORSPACE_HSL, h=120, s=100, l=25)", "rgb(h=0, s=100, space=COLORSPACE_HSV, v=100)",
              "rgb(space=COLORSPACE_HCY, h=0, c=100, y=29.9)", "rgb(space=COLORSPACE_RGB, r=1, g=2, b=3)",
              "rgb(space=COLORSPACE_HSV, h=color_id(0), s=color_id(100), v=color_id(100))",
              "rgb(h=color_id(0), space=color_id(COLORSPACE_HSL), s=color_id(100), l=color_id(50))",
              "rgb(space=color_id(COLORSPACE_HSL), color_id(0), color_id(100), color_id(50))",
              "rgb(r=color_id(255), space=color_id(COLORSPACE_RGB), g=color_id(0), b=color_id(0))",
              "rgb(space=color_id(COLORSPACE_HSV), h=color_id(0), s=color_id(100), v=color_id(100), a=color_id(9))"]:
        s.case(R, e)
    # ---- rgb(): case and spelling of names (only the first letter is documented to matter) ----
    for e in ["rgb(H=0, S=100, V=100)", "rgb(HUE=0, Sat=100, Lum=50)", "rgb(H=0, C=100, Y=29.9)",
              "rgb(A=128, r=1, g=2, b=3)", "rgb(Alpha=5, r=1, g=2, b=3)", "rgb(hat=0, sock=100, vase=100)",
              "rgb(hat=0, cat=100, yak=29.9)", "rgb(hat=0, sock=100, lamp=50)", "rgb(ray=1, gem=2, bat=3, ant=4)",
              "rgb(H=color_id(0), S=color_id(100), V=color_id(100))",
              "rgb(HUE=color_id(0), Sat=color_id(100), Lum=color_id(50))",
              "rgb(H=color_id(0), C=color_id(100), Y=color_id(29.9))",
              "rgb(A=color_id(128), r=color_id(1), g=color_id(2), b=color_id(3))",
              "rgb(hat=color_id(0), sock=color_id(100), vase=color_id(100))"]:
        s.case(R, e)
    # ---- rgb() folded in other constant contexts ----
    for v in ["rgb(h=0, s=100, l=50)", "rgb(1.5, 2.5, 254.5, 127.5)", "rgb(0, 100, 50, , COLORSPACE_HSL)",
              "rgb(0, 100, 100, 128, COLORSPACE_HSV)", "rgb(r=1, g=2, b=3, a=4)",
              "rgb(0, 100, 29.9, , COLORSPACE_HCY)", "rgb(300, -5, 127.4)"]:
        s.body(R, [f"var/const/C = {v}"], "C")
    s.body(R, ['var/x = color_id("#ff0000")', "var/r = 0", "switch(x)", "\tif(rgb(255,0,0))", "\t\tr = 1",
               "\telse", "\t\tr = 2"], "r")
    s.body(R, ['var/x = color_id("#ff000080")', "var/r = 0", "switch(x)", "\tif(rgb(255, 0, 0, 128))", "\t\tr = 1",
               "\tif(rgb(h=0, s=100, v=100, a=128))", "\t\tr = 2", "\telse", "\t\tr = 3"], "r")

    # ---- constant values (HSLA separate: it may be undefined) ----
    s.case("color_const", "list(COLORSPACE_RGB, COLORSPACE_HSV, COLORSPACE_HSL, COLORSPACE_HCY, "
                          "FILTER_COLOR_RGB, FILTER_COLOR_HSV, FILTER_COLOR_HSL, FILTER_COLOR_HCY)")
    s.case("color_const", "COLORSPACE_HSLA")

    # ---- typed atoms with an alpha in the compile-time colour ----
    for t in ("color_alphavar", "color_alpha_before", "color_alpha_after", "color_alpha_short", "color_tinted"):
        s.body("color_var", [f"var/obj/o = parity_track(new /obj/{t}(locate(1, 1, 1)))"], "list(o.color, o.alpha)")
    # ---- alpha side effect of color on image / mutable_appearance (and obj with a preset alpha) ----
    AV = ['"#ff000080"', '"#5af8"', '"transparent"', '"#ff0000"', "null",
          "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5, 0, 0, 0, 0)"]
    for v in AV:
        for pre in ("null", "10"):
            s.case("color_var", f"color_img_set_alpha({v}, {pre})")
            s.case("color_var", f"color_ma_set_alpha({v}, {pre})")
        s.case("color_var", f"color_obj_set_alpha_pre({v}, 10)")

    # ---- colour matrices: RGB-only forms keep the existing alpha ----
    M = "color_matrix"
    for m in ["list(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.1, 0.2, 0.3)", "list(1, 0, 0, 0, 1, 0, 0, 0, 1)",
              'list("#f00", "#0f0", "#00f")', 'list("#f00", "#0f0", "#00f", "#fff")',
              'list(null, null, null, null, "#33333380")', 'list("#f00", "#0f0", "#00f", "#fff", "#333")',
              'list("#f008", "#0f08", "#00f8", "#fff8", "#3338")']:
        s.case(M, f"color_obj_set_alpha_pre({m}, 100)")
        s.case(M, f"color_obj_set({m})")

    # ---- filter(type="color") with colour spaces ----
    F = "color_filter"
    for args in ['color=list(1,0,0, 0,1,0, 0,0,1), space=FILTER_COLOR_HSL',
                 'color=list(1,0,0, 0,1,0, 0,0,1, 0.1,0.2,0.3)',
                 'color=list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)',
                 'color=list("#f00","#0f0","#00f")', 'color=list(1,0,0, 0,1,0, 0,0,1), space=FILTER_COLOR_HCY',
                 'color=list(1,0,0, 0,1,0, 0,0,1), space=FILTER_COLOR_HSV', 'color=list(1,0,0, 0,1,0, 0,0,1), space=5',
                 'space=FILTER_COLOR_HSL', '', 'color="#ff0000"']:
        sep = ", " if args else ""
        s.body(F, [f'var/dm_filter/f = filter(type="color"{sep}{args})'], "list(f.type, f.color, f.space)")
    for m in ["list(1,0,0, 0,1,0, 0,0,1)", "list(1,0,0, 0,1,0, 0,0,1, 0.1,0.2,0.3)", 'list("#f00","#0f0","#00f")',
              "list(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1, 0,0,0,0)"]:
        s.body(F, ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
                   f'o.filters += filter(type="color", color={m})', "var/dm_filter/f = o.filters[1]"],
               "list(f.color, f.space)")
    s.body(F, ["var/obj/o = parity_track(new /obj(locate(1, 1, 1)))",
               'o.filters += filter(type="color", color=list(1,0,0, 0,1,0, 0,0,1), space=FILTER_COLOR_HSL)',
               "var/dm_filter/f = o.filters[1]", "f.space = FILTER_COLOR_HCY"], "list(f.color, f.space)")

    # ---- rgb2num raw (unrounded) HSV/HSL ----
    for c in ('"#5af"', '"#ca60db"', '"#123456"', '"#fe0102"', '"#7f7f7f"', '"#ff800080"'):
        for sp in ("COLORSPACE_HSV", "COLORSPACE_HSL"):
            s.case("rgb2num", f"rgb2num({c}, {sp})")
