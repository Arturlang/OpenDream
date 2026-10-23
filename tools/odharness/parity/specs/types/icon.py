"""/icon procs on the DMI fixtures: icon() / new /icon (file, state, dir, frame, moving), Blend (every
ICON_* mode, icons and colours, offsets), Crop, DrawBox, Flip, GetPixel, Width/Height, IconStates,
icon_states(), Insert (states, dirs, frames, delay, moving), MapColors (every arg-count form), Scale,
SetIntensity, Shift, SwapColor, Turn / turn(), icon arithmetic operators, fcopy of a modified icon.

Results go through icon_r(I) = list(I, probe) where I prints as size + per-state hash and the probe
is a readable grid of GetPixel values (rows top-down, columns 1,2,3,W/2,W/2+1,W-1,W). Icons with
dirs/frames go through icon_d(I), which also samples one pixel of every dir x frame per state.

Divergence targets in OD (DreamProcNativeIcon.cs, DreamIcon.cs, DreamObjectIcon.cs):
- Insert ignores moving and delay; GetPixel ignores moving; GetPixel frame bound check is off by one.
- Scale just sets Width/Height (resized nearest/bicubic by ImageSharp, BYOND antialiases).
- turn(icon, angle) turns the ORIGINAL and returns an unturned clone.
- Flip refuses NE/SW diagonals ((dir & NW)==NW check) and anything non-cardinal-combination.
- SetIntensity silently ignores negative factors; Shift ignores offset 0 / bad dirs.
- MapColors chooses the form from the trimmed argument count; SwapColor alpha rules.
- Only +, += and * exist for icons in OD's opcode handlers; -, &, |, / are BYOND features.
"""
from gen import pairwise

HELPERS = r'''
/proc/icon_probe(icon/I, state = null, dir = 0, frame = 0)
	var/w = I.Width()
	var/h = I.Height()
	var/list/xs = list(1, 2, 3, round(w / 2), round(w / 2) + 1, w - 1, w)
	var/list/ys = list(h, h - 2, h - 3, round(h / 2) + 1, round(h / 2), 5, 4, 3, 1)
	var/list/L = list()
	for(var/y in ys)
		var/list/row = list()
		for(var/x in xs)
			row += "[I.GetPixel(x, y, state, dir, frame)]"
		L += "[y]:[jointext(row, " ")]"
	return L

/proc/icon_r(icon/I, state = null, dir = 0, frame = 0)
	if(!istype(I, /icon))
		return list("not an icon", I)
	return list(I, icon_probe(I, state, dir, frame))

// Rows top-down of a small rectangle
/proc/icon_region(icon/I, x1, y1, x2, y2, state = null, dir = 0, frame = 0)
	var/list/L = list()
	for(var/y in y2 to y1 step -1)
		var/list/row = list()
		for(var/x in x1 to x2)
			row += "[I.GetPixel(x, y, state, dir, frame)]"
		L += "[y]:[jointext(row, " ")]"
	return L

// One pixel of every dir x frame 1..4 of every state
/proc/icon_desc(icon/I, x = 5, y = 5, moving = -1)
	var/list/out = list()
	for(var/s in icon_states(I))
		var/list/parts = list()
		for(var/d in list(SOUTH, NORTH, EAST, WEST, SOUTHEAST, SOUTHWEST, NORTHEAST, NORTHWEST))
			var/list/fr = list()
			for(var/f in 1 to 4)
				fr += "[I.GetPixel(x, y, s, d, f, moving)]"
			parts += jointext(fr, ",")
		out += "[s]=[jointext(parts, "/")]"
	return out

/proc/icon_d(icon/I, x = 5, y = 5)
	if(!istype(I, /icon))
		return list("not an icon", I)
	return list(I, icon_desc(I, x, y))

// Hash of every dir x frame of one state
/proc/icon_allhash(icon/I, state, frames = 3)
	var/list/out = list()
	for(var/d in list(SOUTH, NORTH, EAST, WEST))
		for(var/f in 1 to frames)
			out += "[d].[f]=[parity_icon_hash(I, state, d, f)]"
	return out

/proc/icon_new_err(a)
	var/icon/I = new /icon(a)
	return I
'''


def A(name):
    return f"icon('test.dmi', \"{name}\")"


ASYM = A("asym")
GRAD = A("grad")
ALPHA = A("alpha")
HALF = A("half")
CHECK = A("checker")
SMALL = "icon('small.dmi', \"grad\")"
SMALLS = "icon('small.dmi', \"solid\")"
RECT = "icon('rect.dmi')"
DIRS4 = A("dirs4")
DIRS8 = A("dirs8")
ANIM = A("anim")
ANIM4 = A("anim4")

DIRS_ALL = ["NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST"]
DIRS_BAD = ["0", "3", "12", "16", "32", "-1", "null", "2.5", "\"north\"", "list()"]


def op(s, proc, base, call, pre=(), result="icon_r(I)"):
    """var/icon/I = base; [pre]; var/ret = I.call; record list(ret, result)."""
    lines = [f"var/icon/I = {base}"] + list(pre) + [f"var/ret = I.{call}"]
    return s.body(proc, lines, f"list(ret, {result})")


def build(s):
    s.dm(HELPERS)

    # ================= icon() constructor =================
    FILES = ["'test.dmi'", "'small.dmi'", "'rect.dmi'", 'file("test.dmi")', '"test.dmi"', "icon('test.dmi')",
             "icon('test.dmi', \"dirs4\")", "null", "5", "list()", "new /datum", "/datum", '"nope.dmi"',
             "new /icon()", "'test.dmi' + \"#000000\""]
    for f in FILES:
        s.case("icon", f"icon_d(icon({f}))")
        s.case("new/icon", f"icon_d(new /icon({f}))")
    F2 = ["'test.dmi'", "icon('test.dmi')", "'small.dmi'", "null"]
    STATES = ['"asym"', '"dirs4"', '"dirs8"', '"anim"', '"anim4"', '"rewind"', '"moving"', '""', '"empty"',
              '"nope"', "null", "5", '"ASYM"', "list()", '"grad"']
    STATES_S = ['"dirs4"', '"dirs8"', '"anim4"', '"asym"', "null", '"moving"', '"nope"']
    DIRS = ["0", "1", "2", "4", "8", "5", "10", "3", "16", "-1", "null", "2.5"]
    FRAMES = ["0", "1", "2", "3", "4", "-1", "null", "1.5", '"2"']
    MOVING = ["null", "0", "1", "-1", "2", '"1"']
    s.sweep("icon", [F2, STATES], min_args=2, fmt=lambda *a: f"icon_d(icon({', '.join(a)}))")
    s.sweep("icon", [["'test.dmi'", "icon('test.dmi')"], STATES_S, DIRS, FRAMES, MOVING], min_args=3,
            fmt=lambda *a: f"icon_d(icon({', '.join(a)}))")
    for st in ['"anim"', '"anim4"', '"rewind"', '"dirs8"']:
        for fr in ["1", "2", "3", "4"]:
            s.case("icon", f"icon_d(icon('test.dmi', {st}, frame = {fr}))")
            s.case("icon", f"icon_d(icon('test.dmi', {st}, null, {fr}))")
    for d in DIRS_ALL:
        s.case("icon", f"icon_d(icon('test.dmi', dir = {d}))")
        s.case("icon", f"icon_d(icon('test.dmi', \"dirs8\", {d}))")
        s.case("icon", f"icon_d(icon('test.dmi', \"dirs4\", {d}))")
        s.case("icon", f"icon_d(icon('test.dmi', \"anim4\", {d}, 2))")
    for mv in ["0", "1", "null", "-1"]:
        s.case("icon", f"icon_d(icon('test.dmi', moving = {mv}))")
        s.case("icon", f"icon_d(icon('test.dmi', \"moving\", moving = {mv}))")
        s.case("icon", f"icon_d(icon('test.dmi', \"asym\", moving = {mv}))")
        s.case("icon", f"icon_states(icon('test.dmi', moving = {mv}))")
    s.case("icon", "icon_d(icon(icon = 'test.dmi', icon_state = \"asym\"))")
    s.case("icon", "icon_d(icon(icon_state = \"asym\", icon = 'test.dmi'))")
    s.case("icon", "icon_d(new /icon(icon = 'test.dmi', icon_state = \"dirs4\", dir = WEST))")
    s.case("icon", "icon_d(new /icon('test.dmi', \"anim\", frame = 2))")
    s.case("icon", "icon_d(new /icon())")
    s.case("icon", "icon_d(new /icon)")
    s.case("icon", "icon_d(icon())")
    s.case("icon", "istype(icon('test.dmi'), /icon)")
    s.case("icon", "icon('test.dmi').type")
    s.body("icon", ["var/icon/I = icon('test.dmi')"], "I.icon")
    s.body("icon", ["var/icon/I = icon('test.dmi')", "I.icon = 'small.dmi'"], "icon_d(I)")
    s.body("icon", ["var/icon/I = icon('test.dmi')"], "isfile(I)")
    s.body("icon", ["var/icon/I = icon('test.dmi')"], "isicon(I)")
    s.case("icon", "isicon('test.dmi')")
    s.case("icon", "isicon(\"test.dmi\")")
    # Copy independence: constructing from an /icon copies it
    s.body("icon", [f"var/icon/I = {ASYM}", "var/icon/J = icon(I)", "J.Flip(EAST)"], "list(icon_r(I), icon_r(J))")
    s.body("icon", [f"var/icon/I = {ASYM}", "var/icon/J = new /icon(I)", "I.DrawBox(\"#ffffff\", 1, 1, 32, 32)"],
           "list(icon_r(I), icon_r(J))")
    s.body("icon", [f"var/icon/I = {DIRS4}", "I.Flip(EAST)", "var/icon/J = icon(I, dir = EAST)"], "icon_d(J)")
    s.body("icon", [f"var/icon/I = icon('test.dmi')", "I.Turn(90)", "var/icon/J = icon(I, \"asym\")"], "icon_r(J)")
    s.body("icon", ["var/icon/I = icon('test.dmi')", "var/icon/J = icon(I, \"anim\", frame = 3)"], "icon_d(J)")
    s.case("icon", "icon_new_err(\"bogus\")")
    s.case("icon", "icon_new_err(list(1))")
    s.case("icon", "icon_d(icon(icon('small.dmi'), \"solid\"))")
    s.case("icon", "icon_d(icon('rect.dmi', \"wide\", SOUTH, 1, 0))")
    s.case("icon", "icon_d(icon('test.dmi', \"\", 0, 0, 0))")

    # ================= Width / Height =================
    for b in [ASYM, SMALL, RECT, "icon('test.dmi')", "new /icon()", "icon('test.dmi', \"nope\")", "icon(null)"]:
        s.case("Width", f"{b}.Width()")
        s.case("Height", f"{b}.Height()")
        s.body("Width", [f"var/icon/I = {b}"], "list(I.Width(), I.Height())")
    s.case("Width", f"{ASYM}.Width(5)")
    s.case("Height", f"{ASYM}.Height(\"x\")")

    # ================= icon_states / IconStates =================
    SRC = ["'test.dmi'", "'small.dmi'", "'rect.dmi'", 'file("test.dmi")', '"test.dmi"', "icon('test.dmi')",
           ASYM, "new /icon()", "null", "5", "list()", "new /datum", "/datum", "icon('test.dmi', \"moving\")",
           "icon('test.dmi', dir = NORTH)", '"nope.dmi"', "'test.dmi' + \"#101010\""]
    MODES = ["0", "1", "2", "3", "-1", "null", "0.5", '"1"']
    for src in SRC:
        s.case("icon_states", f"icon_states({src})")
    for src in SRC[:8]:
        for m in MODES:
            s.case("icon_states", f"icon_states({src}, {m})")
    for b in ["icon('test.dmi')", ASYM, SMALL, RECT, "new /icon()", "icon('test.dmi', \"moving\")"]:
        s.case("IconStates", f"{b}.IconStates()")
        for m in MODES:
            s.case("IconStates", f"{b}.IconStates({m})")
    s.case("IconStates", "icon('test.dmi').IconStates(mode = 2)")
    s.body("icon_states", ["var/list/L = icon_states('test.dmi')", "L += \"x\""], "list(L, icon_states('test.dmi'))")
    s.body("icon_states", ["var/icon/I = icon('test.dmi')", "var/list/L = I.IconStates()", "L.Cut()"],
           "I.IconStates()")

    # ================= GetPixel =================
    XY = ["1", "32", "0", "33", "-1", "16.5", "3", "29", "null", '"1"', "PINF", "NAN"]
    s.sweep("GetPixel", [XY, XY], fmt=lambda x, y: f"{ASYM}.GetPixel({x}, {y})")
    s.sweep("GetPixel", [XY], fmt=lambda x: f"{ASYM}.GetPixel({x})")
    s.case("GetPixel", f"{ASYM}.GetPixel()")
    GP_STATES = ['"asym"', "null", '""', '"nope"', "5", '"solid"', '"ASYM"', "list()"]
    for st in GP_STATES:
        s.case("GetPixel", f"{ASYM}.GetPixel(3, 29, {st})")
        s.case("GetPixel", f"icon('test.dmi').GetPixel(3, 29, {st})")
    for st in ['"asym"', '"solid"', '"grad"', '"alpha"', '"half"', '"checker"', '"empty"', '""', '"moving"',
               '"rewind"', '"anim"', '"dirs4"', '"dirs8"', '"anim4"']:
        s.case("GetPixel", f"icon_region(icon('test.dmi'), 1, 1, 3, 3, {st})")
        s.case("GetPixel", f"icon_region(icon('test.dmi'), 15, 30, 18, 32, {st})")
    GP_DIRS = ["0", "1", "2", "4", "8", "5", "6", "9", "10", "3", "16", "-1", "null", "1.5", '"4"']
    GP_FRAMES = ["0", "1", "2", "3", "4", "-1", "null", "1.5", '"2"', "100"]
    for st in ['"dirs4"', '"dirs8"', '"anim4"', '"anim"']:
        for d in GP_DIRS:
            s.case("GetPixel", f"icon('test.dmi').GetPixel(5, 5, {st}, {d})")
        for fr in GP_FRAMES:
            s.case("GetPixel", f"icon('test.dmi').GetPixel(5, 5, {st}, 0, {fr})")
            s.case("GetPixel", f"icon('test.dmi').GetPixel(5, 5, {st}, EAST, {fr})")
    s.case("GetPixel", "icon('test.dmi').GetPixel(2, 2, \"dirs4\", NORTH)")
    s.case("GetPixel", "icon('test.dmi', \"rewind\").GetPixel(5, 5, null, 0, 2)")
    s.case("GetPixel", "icon('test.dmi', \"anim\").GetPixel(5, 5, frame = 3)")
    s.case("GetPixel", "icon('test.dmi', \"anim\").GetPixel(5, 5, dir = SOUTH, frame = 2)")
    s.case("GetPixel", "icon('test.dmi', \"dirs8\").GetPixel(y = 5, x = 5, dir = NORTHWEST)")
    for mv in ["-1", "0", "1", "null", "2", '"1"']:
        for st in ['"moving"', '"asym"', "null"]:
            s.case("GetPixel", f"icon('test.dmi').GetPixel(5, 5, {st}, 0, 0, {mv})")
        s.case("GetPixel", f"icon('test.dmi', \"moving\").GetPixel(5, 5, null, 0, 0, {mv})")
    s.case("GetPixel", "icon('test.dmi').GetPixel(5, 5, \"moving\", moving = 1)")
    # Alpha output formats
    s.case("GetPixel", "icon_region(icon('test.dmi', \"alpha\"), 1, 1, 32, 1)")
    s.case("GetPixel", "icon_region(icon('test.dmi', \"half\"), 14, 1, 19, 1)")
    s.case("GetPixel", "icon_region(icon('small.dmi', \"grad\"), 1, 1, 16, 2)")
    s.case("GetPixel", "icon_region(icon('rect.dmi'), 1, 1, 32, 1)")
    s.case("GetPixel", "icon_region(icon('rect.dmi'), 1, 15, 3, 17)")
    s.case("GetPixel", "icon('rect.dmi').GetPixel(1, 17)")
    s.case("GetPixel", "icon('small.dmi').GetPixel(17, 1)")
    s.case("GetPixel", "new /icon().GetPixel(1, 1)")
    s.case("GetPixel", "icon('test.dmi', \"empty\").GetPixel(1, 1)")
    s.case("GetPixel", "istext(icon('test.dmi', \"solid\").GetPixel(1, 1))")

    # ================= Flip =================
    for b in [ASYM, RECT, SMALL]:
        for d in DIRS_ALL + DIRS_BAD:
            op(s, "Flip", b, f"Flip({d})")
    op(s, "Flip", ASYM, "Flip()")
    op(s, "Flip", ASYM, "Flip(dir = EAST)")
    for d in DIRS_ALL:
        op(s, "Flip", DIRS4, f"Flip({d})", result="icon_d(I, 2, 2)")
        op(s, "Flip", DIRS8, f"Flip({d})", result="icon_d(I)")
    op(s, "Flip", ANIM, "Flip(NORTH)", result="icon_allhash(I, \"anim\")")
    op(s, "Flip", ASYM, "Flip(EAST)", pre=["I.Flip(EAST)"])
    op(s, "Flip", ASYM, "Flip(NORTH)", pre=["I.Flip(EAST)"])
    op(s, "Flip", "icon('test.dmi')", "Flip(WEST)")

    # ================= Turn =================
    ANGLES = ["0", "90", "180", "270", "360", "-90", "-180", "-270", "450", "720", "-450", "45", "30", "15", "1",
              "-45", "135", "89.5", "90.4", "1e7", "NAN", "PINF", "null", '"90"', "list()"]
    for a in ANGLES:
        op(s, "Turn", ASYM, f"Turn({a})")
    for a in ["90", "180", "270", "45", "-90"]:
        op(s, "Turn", RECT, f"Turn({a})")
        op(s, "Turn", SMALL, f"Turn({a})")
        op(s, "Turn", CHECK, f"Turn({a})")
        op(s, "Turn", DIRS4, f"Turn({a})", result="icon_d(I, 2, 2)")
        op(s, "Turn", DIRS8, f"Turn({a})", result="icon_d(I)")
        op(s, "Turn", ANIM, f"Turn({a})", result="icon_allhash(I, \"anim\")")
    for a in ["30", "45", "10"]:
        op(s, "Turn", ASYM, f"Turn({a})", result="icon_region(I, 1, 1, 6, 6)")
        op(s, "Turn", GRAD, f"Turn({a})", result="icon_region(I, 14, 14, 19, 19)")
    op(s, "Turn", ASYM, "Turn()")
    op(s, "Turn", ASYM, "Turn(angle = 90)")
    op(s, "Turn", ASYM, "Turn(90)", pre=["I.Turn(-90)"])
    op(s, "Turn", ASYM, "Turn(45)", pre=["I.Turn(45)"])
    op(s, "Turn", "icon('test.dmi')", "Turn(90)")
    # turn() proc on an icon: returns a turned copy, original untouched (documented as counterclockwise for dirs)
    for a in ["90", "-90", "180", "45", "0", "null"]:
        s.body("turn", [f"var/icon/I = {ASYM}", f"var/icon/J = turn(I, {a})"], "list(icon_r(J), icon_r(I), I == J)")
    s.body("turn", [f"var/icon/I = {RECT}", "var/icon/J = turn(I, 90)"], "list(icon_r(J), icon_r(I))")
    s.case("turn", "icon_r(turn('test.dmi', 90))")
    s.case("turn", "icon_r(turn(icon('test.dmi', \"asym\"), 90))")

    # ================= Shift =================
    SH_DIRS = ["NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST",
               "0", "3", "16", "null", "-1"]
    SH_OFF = ["1", "5", "-3", "0", "31", "32", "33", "100", "2.5", "-2.5", "null", '"2"', "NAN"]
    SH_WRAP = ["0", "1", "null", "2", "0.5", "-1", '"1"']
    for d in SH_DIRS:
        for o in SH_OFF:
            op(s, "Shift", ASYM, f"Shift({d}, {o})")
    for d in ["NORTH", "EAST", "SOUTHWEST", "WEST"]:
        for o in ["1", "-3", "33", "2.5"]:
            for w in SH_WRAP:
                op(s, "Shift", ASYM, f"Shift({d}, {o}, {w})")
    op(s, "Shift", ASYM, "Shift(EAST)")
    op(s, "Shift", ASYM, "Shift()")
    op(s, "Shift", ASYM, "Shift(dir = NORTH, offset = 2, wrap = 1)")
    op(s, "Shift", RECT, "Shift(NORTH, 3, 1)")
    op(s, "Shift", RECT, "Shift(EAST, 5)")
    op(s, "Shift", SMALL, "Shift(WEST, 4, 1)")
    op(s, "Shift", DIRS4, "Shift(EAST, 1)", result="icon_d(I, 2, 2)")
    op(s, "Shift", ANIM, "Shift(NORTH, 4)", result="icon_allhash(I, \"anim\")")
    op(s, "Shift", ASYM, "Shift(EAST, 2)", pre=["I.Shift(WEST, 2)"])

    # ================= Crop =================
    CR = ["1", "-3", "16", "33", "0", "2.5", "null"]
    for row in pairwise([CR, CR, CR, CR]):
        op(s, "Crop", ASYM, f"Crop({', '.join(CR[v] for v in row)})")
    for (x1, y1, x2, y2) in [(1, 1, 32, 32), (1, 1, 16, 16), (17, 17, 32, 32), (32, 32, 1, 1), (32, 1, 1, 32),
                             (-5, -5, 10, 10), (20, 20, 40, 40), (0, 0, 0, 0), (5, 5, 5, 5), (1, 1, 64, 64),
                             (40, 40, 50, 50), (-10, -10, -1, -1), (1, 1, 1, 32), (1, 28, 20, 32), (3, 29, 3, 29),
                             (1.5, 2.5, 10.7, 10.2), (-31, -31, 32, 32), (2, 2, 3, 3)]:
        op(s, "Crop", ASYM, f"Crop({x1}, {y1}, {x2}, {y2})")
    for args in ["1, 1, 16", "1, 1", "1", "", "null, null, null, null", '"1", "1", "16", "16"',
                 "1, 1, NAN, 16", "1, 1, PINF, 16", "x1 = 1, y1 = 1, x2 = 8, y2 = 8", "list(), 1, 8, 8"]:
        op(s, "Crop", ASYM, f"Crop({args})")
    for b in [RECT, SMALL, DIRS4, "icon('test.dmi')"]:
        op(s, "Crop", b, "Crop(1, 1, 16, 8)")
        op(s, "Crop", b, "Crop(-3, -3, 40, 40)")
    op(s, "Crop", ANIM4, "Crop(3, 3, 10, 10)", result="icon_d(I, 2, 2)")
    op(s, "Crop", ASYM, "Crop(1, 1, 8, 8)", pre=["I.Crop(1, 1, 16, 16)"])
    op(s, "Crop", ASYM, "Crop(1, 1, 32, 32)", pre=["I.Crop(1, 1, 8, 8)"])
    for x1, y1, x2, y2 in [(1, 1, 6, 6), (-2, -2, 3, 3), (30, 26, 34, 32), (3, 29, 1, 27)]:
        op(s, "Crop", ASYM, f"Crop({x1}, {y1}, {x2}, {y2})", result="icon_region(I, 1, 1, I.Width(), I.Height())")

    # ================= DrawBox =================
    COLORS = ['"#ff0000"', '"#00ff0080"', "null", "rgb(1, 2, 3)", '"red"', '"#abc"', '"#12345678"',
              '"#00000000"', "5", '"bogus"', "list()", '"#ff00"', '"#FFFFFF"', "rgb(1, 2, 3, 4)"]
    BOXES = ["5, 5", "1, 1, 4, 4", "4, 4, 1, 1", "30, 30, 40, 40", "-5, -5, 2, 2", "40, 40", "0, 0",
             "1, 1, 32", "2, 2, null, 4", "2.5, 2.5, 4.5, 4.5", "1, 1, 32, 32", "33, 1, 33, 32",
             "6, 1, 2, 3", "3, 3, 3, 3"]
    for c in COLORS:
        op(s, "DrawBox", ASYM, f"DrawBox({c}, 2, 2, 4, 4)", result="icon_region(I, 1, 1, 5, 5)")
    for bx in BOXES:
        op(s, "DrawBox", ASYM, f"DrawBox(\"#ff0000\", {bx})")
        op(s, "DrawBox", ASYM, f"DrawBox(null, {bx})", result="icon_region(I, 1, 1, 6, 6)")
    for c in ['"#ff0000"', "null", '"#00ff0080"']:
        op(s, "DrawBox", ALPHA, f"DrawBox({c}, 1, 1, 32, 1)", result="icon_region(I, 1, 1, 32, 2)")
        op(s, "DrawBox", HALF, f"DrawBox({c}, 14, 1, 19, 2)", result="icon_region(I, 13, 1, 20, 3)")
    op(s, "DrawBox", ASYM, "DrawBox(\"#ff0000\")")
    op(s, "DrawBox", ASYM, "DrawBox(\"#ff0000\", 3)", result="icon_region(I, 1, 1, 5, 5)")
    op(s, "DrawBox", ASYM, "DrawBox()")
    op(s, "DrawBox", ASYM, "DrawBox(rgb = \"#0000ff\", x1 = 2, y1 = 3, x2 = 3, y2 = 2)", result="icon_region(I, 1, 1, 5, 5)")
    op(s, "DrawBox", ASYM, "DrawBox(\"#ff0000\", NAN, 1, 2, 2)", result="icon_region(I, 1, 1, 5, 5)")
    op(s, "DrawBox", ASYM, "DrawBox(\"#ff0000\", \"2\", \"2\", \"3\", \"3\")", result="icon_region(I, 1, 1, 5, 5)")
    op(s, "DrawBox", RECT, "DrawBox(\"#ff0000\", 1, 1, 40, 40)")
    op(s, "DrawBox", ANIM, "DrawBox(\"#ffffff\", 4, 4, 6, 6)", result="icon_d(I)")
    op(s, "DrawBox", ANIM4, "DrawBox(null, 4, 4, 6, 6)", result="icon_d(I)")
    op(s, "DrawBox", "icon('test.dmi')", "DrawBox(\"#ffffff\", 5, 5)", result="icon_d(I)")
    op(s, "DrawBox", "new /icon()", "DrawBox(\"#ffffff\", 1, 1, 4, 4)")

    # ================= SetIntensity =================
    INT = ["0.5", "2", "0", "1", "-1", "1.5", "100", "0.001", "NAN", "PINF", "null", '"2"', "list()"]
    for b in [GRAD, ALPHA, HALF]:
        for r in INT:
            op(s, "SetIntensity", b, f"SetIntensity({r})")
    INT_S = ["0", "0.5", "1", "2", "-1", "null"]
    s_rows = [(r, g, b) for r in INT_S for g in INT_S for b in INT_S]
    for (r, g, b) in s_rows[::5]:
        op(s, "SetIntensity", GRAD, f"SetIntensity({r}, {g}, {b})")
    for (r, g) in [("1", "0"), ("0", "1"), ("0.5", "2"), ("2", "null")]:
        op(s, "SetIntensity", GRAD, f"SetIntensity({r}, {g})")
    op(s, "SetIntensity", GRAD, "SetIntensity()")
    op(s, "SetIntensity", GRAD, "SetIntensity(r = 1, b = 0)")
    op(s, "SetIntensity", GRAD, "SetIntensity(g = 0)")
    op(s, "SetIntensity", ANIM4, "SetIntensity(0.5)", result="icon_d(I)")
    op(s, "SetIntensity", GRAD, "SetIntensity(2)", pre=["I.SetIntensity(0.5)"])

    # ================= SwapColor =================
    SW = [('"#ff0000"', '"#00ff00"'), ('"#282828"', '"#ffffff"'), ('"#282828ff"', '"#ffffff"'),
          ('"#28282880"', '"#ffffff"'), ("null", '"#ff0000"'), ('"#ff0000"', "null"), ('"#00c800"', '"#0000ff80"'),
          ('"#0000ff"', '"#00000000"'), ('"#00000000"', '"#ff0000"'), ("rgb(255, 0, 0)", "rgb(0, 0, 255)"),
          ('"red"', '"blue"'), ('"#f00"', '"#0f0"'), ("5", '"#ff0000"'), ('"#ff0000"', "5"), ("list()", '"#ff0000"'),
          ('"bogus"', '"#ff0000"'), ('"#ff0000"', '"bogus"'), ('"#FF0000"', '"#00FF00"'), ('"#ff0000"', '"#ff0000"'),
          ('"#282828"', '"#ffffff80"'), ('"#28282800"', '"#ffffff"'), ("null", "null")]
    for o, n in SW:
        op(s, "SwapColor", ASYM, f"SwapColor({o}, {n})")
        op(s, "SwapColor", ASYM, f"SwapColor({o}, {n})", result="icon_region(I, 1, 27, 5, 30)")
    for o, n in [('"#ffffff"', '"#ff0000"'), ('"#ffffff80"', '"#ff0000"'), ('"#ffffff80"', '"#ff000040"'),
                 ('"#ffffff"', '"#ff000040"'), ('"#ffffff"', '"#00000000"'), ("null", '"#ff0000"'),
                 ('"#ffffff00"', '"#ff0000"'), ("rgb(255, 255, 255, 128)", '"#00ff00"')]:
        op(s, "SwapColor", ALPHA, f"SwapColor({o}, {n})", result="icon_region(I, 1, 1, 32, 1)")
    op(s, "SwapColor", ASYM, "SwapColor(\"#ff0000\")")
    op(s, "SwapColor", ASYM, "SwapColor()")
    op(s, "SwapColor", ASYM, "SwapColor(old_rgb = \"#ff0000\", new_rgb = \"#ffffff\")", result="icon_region(I, 1, 27, 5, 30)")
    op(s, "SwapColor", DIRS4, "SwapColor(\"#ff0000\", \"#ffffff\")", result="icon_d(I)")
    op(s, "SwapColor", ANIM, "SwapColor(\"#00ff00\", \"#ffffff\")", result="icon_d(I)")

    # ================= MapColors =================
    MC = [
        # 3/4 rgb form
        '"#ff0000", "#00ff00", "#0000ff"',
        '"#00ff00", "#0000ff", "#ff0000"',
        "rgb(76, 76, 76), rgb(150, 150, 150), rgb(29, 29, 29)",
        "rgb(76, 76, 76), rgb(150, 150, 150), rgb(29, 29, 29), rgb(0, 0, 0)",
        '"#ff0000", "#00ff00", "#0000ff", "#202020"',
        '"#ff0000", "#00ff00", "#0000ff", null',
        '"red", "lime", "blue"',
        '"#f00", "#0f0", "#00f", "#111"',
        '"#ff000080", "#00ff0080", "#0000ff80"',
        # 4/5 rgba form
        '"#ff000000", "#00ff0000", "#0000ff00", "#000000ff"',
        '"#ff000000", "#00ff0000", "#0000ff00", "#000000ff", "#00000000"',
        '"#ff000000", "#00ff0000", "#0000ff00", "#00000080", "#10101000"',
        '"#00ff0000", "#0000ff00", "#ff000000", "#000000ff", "#00000040"',
        '"#ff0000", "#00ff00", "#0000ff", "#000000", "#000000"',
        # 9/12 number form
        "1, 0, 0, 0, 1, 0, 0, 0, 1",
        "0.299, 0.299, 0.299, 0.587, 0.587, 0.587, 0.114, 0.114, 0.114",
        "0.299, 0.299, 0.299, 0.587, 0.587, 0.587, 0.114, 0.114, 0.114, 0, 0, 0",
        "-1, 0, 0, 0, -1, 0, 0, 0, -1, 1, 1, 1",
        "0.2, 0.05, 0.05, 0.1, 0.3, 0.2, 0.1, 0.1, 0.4, 0, 0, 0",
        "2, 0, 0, 0, 2, 0, 0, 0, 2",
        "0, 1, 0, 0, 0, 1, 1, 0, 0, 0.5, 0, 0",
        "1, 0, 0, 0, 1, 0, 0, 0, 1, 0.5, 0.5, 0.5",
        "1, 0, 0, 0, 1, 0, 0, 0, 1, 1",
        "1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1",
        # 16/20 number form
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1",
        "0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 1",
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0.1, 0.2, 0.3",
        # odd arg counts / types
        "", "1", '"#ff0000"', "1, 0", '"#ff0000", "#00ff00"', "1, 0, 0", "1, 0, 0, 0, 1, 0, 0, 0",
        "1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0", "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0",
        '"#ff0000", 0, 0, 0, 1, 0, 0, 0, 1', '1, "#00ff00", "#0000ff"', "null, null, null",
        "null, 0, 0, 0, 1, 0, 0, 0, 1", "NAN, 0, 0, 0, 1, 0, 0, 0, 1", "PINF, 0, 0, 0, 1, 0, 0, 0, 1",
        '"bogus", "#00ff00", "#0000ff"', 'list(), "#00ff00", "#0000ff"', "1e7, 0, 0, 0, 1, 0, 0, 0, 1",
        '"#ff0000", "#00ff00", "#0000ff", "#000000", "#000000", "#000000"',
    ]
    for args in MC:
        for b in [GRAD, ALPHA]:
            op(s, "MapColors", b, f"MapColors({args})")
    for args in MC[:33:3]:
        op(s, "MapColors", HALF, f"MapColors({args})", result="icon_region(I, 14, 1, 19, 2)")
    op(s, "MapColors", ANIM4, "MapColors(0, 1, 0, 0, 0, 1, 1, 0, 0)", result="icon_d(I)")
    op(s, "MapColors", GRAD, "MapColors(-1, 0, 0, 0, -1, 0, 0, 0, -1, 1, 1, 1)",
       pre=["I.MapColors(-1, 0, 0, 0, -1, 0, 0, 0, -1, 1, 1, 1)"])

    # ================= Scale =================
    SC = [("64", "64"), ("16", "16"), ("32", "16"), ("16", "32"), ("48", "48"), ("1", "1"), ("0", "0"), ("0", "32"),
          ("32", "0"), ("-1", "-1"), ("-32", "32"), ("10.5", "10.5"), ("33", "31"), ("null", "null"), ("64", "null"),
          ("100", "3"), ("2", "2"), ("31", "31"), ('"16"', '"16"'), ("NAN", "16"), ("8", "8")]
    for w, h in SC:
        op(s, "Scale", ASYM, f"Scale({w}, {h})")
    for w, h in [("64", "64"), ("16", "16"), ("48", "48"), ("20", "20"), ("33", "33"), ("8", "4")]:
        op(s, "Scale", CHECK, f"Scale({w}, {h})")
        op(s, "Scale", GRAD, f"Scale({w}, {h})")
        op(s, "Scale", ALPHA, f"Scale({w}, {h})")
        op(s, "Scale", SMALL, f"Scale({w}, {h})")
        op(s, "Scale", RECT, f"Scale({w}, {h})")
    for w, h in [("4", "4"), ("6", "6"), ("64", "64")]:
        op(s, "Scale", ASYM, f"Scale({w}, {h})", result="icon_region(I, 1, 1, 6, 6)")
        op(s, "Scale", SMALL, f"Scale({w}, {h})", result="icon_region(I, 1, 1, 6, 6)")
    op(s, "Scale", ASYM, "Scale(64)")
    op(s, "Scale", ASYM, "Scale()")
    op(s, "Scale", ASYM, "Scale(width = 16, height = 8)")
    op(s, "Scale", ANIM4, "Scale(16, 16)", result="icon_d(I)")
    op(s, "Scale", "icon('test.dmi')", "Scale(16, 16)")
    op(s, "Scale", ASYM, "Scale(32, 32)", pre=["I.Scale(16, 16)"])
    op(s, "Scale", "new /icon()", "Scale(8, 8)")

    # ================= Blend =================
    BL_SRC = [HALF, ALPHA, CHECK, SMALLS, "'small.dmi'", RECT, A("empty"), "new /icon()", ANIM,
              '"#ff000080"', '"#204060"', "rgb(255, 0, 0)", '"red"', '"#f00"', '"#00000000"', "null", "5",
              '"bogus"', "list()"]
    BL_MODES = ["ICON_ADD", "ICON_SUBTRACT", "ICON_MULTIPLY", "ICON_OVERLAY", "ICON_AND", "ICON_OR", "ICON_UNDERLAY"]
    for b in [ASYM, ALPHA, HALF]:
        for src in BL_SRC:
            for m in BL_MODES:
                op(s, "Blend", b, f"Blend({src}, {m})")
    for src in BL_SRC:
        op(s, "Blend", ASYM, f"Blend({src})")
    for m in ["7", "-1", "null", "2.5", '"add"', "100"]:
        op(s, "Blend", ASYM, f"Blend({HALF}, {m})")
        op(s, "Blend", ASYM, f"Blend(\"#ff0000\", {m})")
    OFFS = [("1", "1"), ("0", "0"), ("-5", "3"), ("11", "1"), ("1", "21"), ("17", "17"), ("33", "1"),
            ("-40", "-40"), ("16.5", "1"), ("null", "null"), ("-15", "-15"), ('"5"', '"5"')]
    for src in [SMALLS, HALF, '"#ff0000"']:
        for m in ["ICON_ADD", "ICON_OVERLAY", "ICON_UNDERLAY", "ICON_OR"]:
            for x, y in OFFS:
                op(s, "Blend", ASYM, f"Blend({src}, {m}, {x}, {y})")
    op(s, "Blend", ASYM, f"Blend({SMALLS}, ICON_OVERLAY, 5)")
    op(s, "Blend", ASYM, f"Blend({SMALLS}, ICON_OVERLAY, y = 5)")
    op(s, "Blend", ASYM, f"Blend(icon = {SMALLS}, function = ICON_OVERLAY, x = 3, y = 3)",
       result="icon_region(I, 1, 1, 6, 6)")
    op(s, "Blend", ASYM, f"Blend({SMALLS}, ICON_OVERLAY, 30, 30)", result="icon_region(I, 28, 28, 32, 32)")
    op(s, "Blend", SMALL, f"Blend({RECT}, ICON_OVERLAY)")
    op(s, "Blend", SMALL, f"Blend({ASYM}, ICON_ADD)")
    op(s, "Blend", RECT, f"Blend({ASYM}, ICON_OVERLAY)")
    op(s, "Blend", DIRS4, "Blend(\"#808080\", ICON_MULTIPLY)", result="icon_d(I)")
    op(s, "Blend", DIRS4, f"Blend({DIRS4}, ICON_ADD)", result="icon_d(I)")
    op(s, "Blend", DIRS4, f"Blend({ASYM}, ICON_OVERLAY)", result="icon_d(I, 3, 29)")
    op(s, "Blend", ANIM, f"Blend({ANIM}, ICON_ADD)", result="icon_d(I)")
    op(s, "Blend", ANIM, f"Blend({DIRS4}, ICON_OVERLAY)", result="icon_d(I)")
    op(s, "Blend", ASYM, f"Blend({ANIM}, ICON_OVERLAY)")
    op(s, "Blend", "icon('test.dmi')", "Blend(\"#ff0000\", ICON_MULTIPLY)")
    op(s, "Blend", "icon('test.dmi')", f"Blend({ASYM}, ICON_OVERLAY)")
    op(s, "Blend", ASYM, "Blend(I, ICON_ADD)")
    op(s, "Blend", ASYM, "Blend('test.dmi', ICON_OVERLAY)")
    op(s, "Blend", ASYM, "Blend()")
    op(s, "Blend", "new /icon()", "Blend(\"#ff0000\")")

    # ================= Insert =================
    BASE = A("solid")
    ins = lambda call, base=BASE, pre=(), result="icon_d(I)": op(s, "Insert", base, call, pre, result)
    J = ASYM
    ins(f"Insert({J}, \"new\")")
    ins(f"Insert({J}, \"solid\")")
    ins(f"Insert({J})")
    ins(f"Insert({J}, null)")
    ins(f"Insert({J}, \"\")")
    for d in DIRS_ALL + ["0", "3", "16", "null", "-1"]:
        ins(f"Insert({J}, \"solid\", {d})")
        ins(f"Insert({J}, \"new\", {d})")
    for fr in ["1", "2", "3", "4", "16", "17", "18", "20", "0", "-1", "null", "1.5"]:
        ins(f"Insert({J}, \"solid\", frame = {fr})")
        ins(f"Insert({J}, \"new\", frame = {fr})")
    for dl in ["2", "-2", "0", "null", "0.5", "-0.5", '"3"', "100"]:
        ins(f"Insert({J}, \"anim\", frame = 2, delay = {dl})", base="icon('test.dmi')")
        ins(f"Insert({J}, \"new\", delay = {dl})")
    for mv in ["1", "0", "null", "-1", "2"]:
        ins(f"Insert({J}, \"solid\", moving = {mv})", result="list(icon_states(I), icon_states(I, 1), icon_desc(I, 5, 5, 1), icon_desc(I, 5, 5, 0))")
        ins(f"Insert({J}, \"moving\", moving = {mv})", base="icon('test.dmi')",
            result="list(icon_states(I), icon_desc(I, 5, 5, 1), icon_desc(I, 5, 5, 0))")
    ins(f"Insert({J}, \"solid\", NORTH, 2)")
    ins(f"Insert({J}, \"x\", EAST, 3)")
    ins(f"Insert(new_icon = {J}, icon_state = \"a\", dir = WEST)")
    ins(f"Insert({J}, icon_state = \"a\", frame = 2)")
    ins(f"Insert({DIRS4}, \"d\")")
    ins(f"Insert({DIRS4}, \"d\", NORTH)")
    ins(f"Insert({DIRS4}, \"solid\", EAST)")
    ins(f"Insert({ANIM}, \"a\")")
    ins(f"Insert({ANIM}, \"a\", frame = 2)")
    ins(f"Insert({ANIM4}, \"a4\", SOUTH)")
    ins(f"Insert(icon('test.dmi'), \"all\")")
    ins(f"Insert('test.dmi', \"f\")")
    ins(f"Insert('small.dmi', \"f\")")
    ins(f"Insert({SMALLS}, \"small\")")
    ins(f"Insert({SMALLS}, \"solid\")")
    ins(f"Insert({RECT}, \"wide\")")
    ins(f"Insert({SMALLS}, \"solid\", NORTH)")
    ins("Insert(\"#ff0000\", \"c\")")
    ins("Insert(null, \"c\")")
    ins("Insert(5, \"c\")")
    ins("Insert(list(), \"c\")")
    ins("Insert(new /datum, \"c\")")
    ins("Insert()")
    ins(f"Insert({J}, 5)")
    ins(f"Insert({J}, list())")
    ins(f"Insert(new /icon(), \"blank\")")
    ins("Insert(I, \"self\")")
    ins(f"Insert({J}, \"anim\", frame = 2)", base="icon('test.dmi')")
    ins(f"Insert({J}, \"anim\", frame = 5)", base="icon('test.dmi')")
    ins(f"Insert({J}, \"dirs4\", SOUTHEAST)", base="icon('test.dmi')")
    ins(f"Insert({J}, \"rewind\", delay = 2)", base="icon('test.dmi')")
    # Insert into an empty icon: the usual way of building icons from scratch
    ins(f"Insert({J}, \"a\")", base="new /icon()")
    ins(f"Insert({SMALLS}, \"b\")", base="new /icon()", pre=[f"I.Insert({J}, \"a\")"])
    ins(f"Insert({J}, \"b\")", base="new /icon()", pre=[f"I.Insert({SMALLS}, \"a\")"])
    ins(f"Insert({J}, \"a\", NORTH)", base="new /icon()", pre=[f"I.Insert({GRAD}, \"a\", SOUTH)"])
    ins(f"Insert({J}, \"a\", frame = 2)", base="new /icon()", pre=[f"I.Insert({GRAD}, \"a\", frame = 1)"])
    ins(f"Insert({J}, \"a\", frame = 3)", base="new /icon()", pre=[f"I.Insert({GRAD}, \"a\", frame = 1)"])
    ins(f"Insert({J}, \"\")", base="new /icon()")
    ins(f"Insert({J})", base="new /icon()")
    # The documented pulsating-arrow pattern
    s.body("Insert", [f"var/icon/I = {ASYM}", f"var/icon/J = {ASYM}", "I.Insert(J, \"blink\", delay = -1)",
                      "var/n = 2", "for(var/light = 9, light >= 5, light--)", f"\tJ = {ASYM}",
                      "\tJ.SetIntensity(light / 10)", "\tI.Insert(J, \"blink\", frame = n++)"],
           "list(icon_d(I, 3, 29), icon_allhash(I, \"blink\", 6))")
    # The inserted icon is copied: changing it afterwards does not change I
    s.body("Insert", [f"var/icon/I = {BASE}", f"var/icon/J = {ASYM}", "I.Insert(J, \"j\")", "J.Flip(EAST)"], "icon_d(I)")
    # Operations before an Insert apply to old states only
    s.body("Insert", [f"var/icon/I = {BASE}", "I.Blend(\"#000080\", ICON_ADD)", f"I.Insert({ASYM}, \"j\")"], "icon_d(I, 3, 29)")
    s.body("Insert", [f"var/icon/I = {BASE}", f"I.Insert({ASYM}, \"j\")", "I.Blend(\"#000080\", ICON_ADD)"], "icon_d(I, 3, 29)")

    # ================= Operators =================
    OPS = [("+", '"#101010"'), ("+", HALF), ("+", ALPHA), ("-", '"#101010"'), ("-", HALF), ("*", "0.5"),
           ("*", "2"), ("*", '"#808080"'), ("*", HALF), ("&", HALF), ("&", '"#ff0000"'), ("|", HALF),
           ("|", '"#ff0000"'), ("/", "2"), ("/", '"#808080"'), ("+", "null"), ("*", "null"), ("+", "5"),
           ("*", "0"), ("-", "null"), ("+", SMALLS), ("+", '"#ff000080"'), ("*", "-1"), ("+", "list()")]
    for o, rhs in OPS:
        s.body(f"icon{o}", [f"var/icon/I = {ASYM}", f"var/J = I {o} {rhs}"],
               "list(isicon(J), istype(J, /icon), isfile(J), icon_r(isicon(J) ? icon(J) : J), icon_r(I))")
        s.body(f"icon{o}=", [f"var/icon/I = {ASYM}", "var/icon/K = I", f"I {o}= {rhs}"],
               "list(I == K, icon_r(isicon(I) ? icon(I) : I), icon_r(K))")
    for o in ["+", "-", "*", "&", "|"]:
        s.body(f"file{o}", [f"var/J = 'test.dmi' {o} \"#202020\""],
               "list(isicon(J), istype(J, /icon), isfile(J), isicon(J) ? icon_d(icon(J)) : J)")
    s.body("icon+", [f"var/J = \"#101010\" + {ASYM}"], "list(isicon(J), J)")
    s.body("icon+", [f"var/J = 5 * {ASYM}"], "list(isicon(J), J)")
    s.body("icon+", [f"var/J = {DIRS4} + \"#101010\""], "icon_d(icon(J), 2, 2)")
    s.body("icon+", [f"var/J = {ANIM} * \"#808080\""], "icon_d(icon(J))")
    s.body("icon==", [f"var/icon/I = {ASYM}", f"var/icon/J = {ASYM}"], "list(I == J, I != J, I == I)")

    # ================= fcopy of a modified icon =================
    for i, (pre, chk) in enumerate([
        ([], "icon_r(icon(file(F)))"),
        (["I.Flip(EAST)"], "icon_r(icon(file(F)))"),
        (["I.Turn(90)", "I.Blend(\"#000040\", ICON_ADD)"], "icon_r(icon(file(F)))"),
        (["I.Scale(16, 8)"], "icon_r(icon(file(F)))"),
        ([f"I.Insert({DIRS4}, \"d\")", f"I.Insert({ANIM}, \"a\")"], "list(icon_states(file(F)), icon_d(icon(file(F))))"),
        (["I.DrawBox(\"#ff000080\", 1, 1, 8, 8)"], "icon_region(icon(file(F)), 7, 7, 9, 9)"),
    ]):
        F = f"icon_fcopy_{i}.dmi"
        s.body("fcopy", [f"var/F = \"{F}\"", "fdel(F)", f"var/icon/I = {ASYM}"] + pre +
               ["var/ok = fcopy(I, F)", f"var/list/res = list(ok, fexists(F), {chk})", "fdel(F)"], "res")
    s.body("fcopy", ["var/F = \"icon_fcopy_all.dmi\"", "fdel(F)", "var/icon/I = icon('test.dmi')", "I.Flip(NORTH)",
                     "var/ok = fcopy(I, F)", "var/list/res = list(ok, icon_states(file(F)), icon_d(icon(file(F))))",
                     "fdel(F)"], "res")
    s.body("fcopy", ["var/F = \"icon_fcopy_file.dmi\"", "fdel(F)", "var/ok = fcopy('test.dmi', F)",
                     "var/list/res = list(ok, icon_states(file(F)), icon_r(icon(file(F), \"asym\")))", "fdel(F)"], "res")
    s.body("fcopy", ["var/F = \"icon_fcopy_png.png\"", "fdel(F)", f"var/icon/I = {ASYM}", "I.Flip(WEST)",
                     "var/ok = fcopy(I, F)", "var/list/res = list(ok, fexists(F), icon_r(icon(file(F))))", "fdel(F)"], "res")
    s.body("fcopy", ["var/F = \"icon_fcopy_sum.dmi\"", "fdel(F)", f"var/J = {ASYM} + \"#101010\"",
                     "var/ok = fcopy(J, F)", "var/list/res = list(ok, icon_r(icon(file(F))))", "fdel(F)"], "res")

    # ================= Gap fill (critic round 2) =================
    # MapColors named arguments (OD's MapColors declares no parameters, reads positional args only)
    for args in ["rr = 0, rg = 1, rb = 0, gr = 0, gg = 0, gb = 1, br = 1, bg = 0, bb = 0",
                 'r_rgb = "#00ff00", g_rgb = "#0000ff", b_rgb = "#ff0000"',
                 'r_rgb = "#00ff00", g_rgb = "#0000ff", b_rgb = "#ff0000", rgb0 = "#202020"',
                 "1, 0, 0, 0, 1, 0, 0, 0, 1, r0 = 0.5",
                 "1, 0, 0, 0, 1, 0, 0, 0, 1, b0 = 0.25, g0 = 0.5",
                 '"#ff000000", "#00ff0000", "#0000ff00", "#000000ff", rgba0 = "#00000080"',
                 '"#ff000000", "#00ff0000", "#0000ff00", a_rgba = "#00000080"',
                 "rr = 1, gg = 1, bb = 1, aa = 0.5",
                 "rr = 1, gg = 1, bb = 1, a0 = -0.5",
                 "rr = 0.5"]:
        op(s, "MapColors", GRAD, f"MapColors({args})")
        op(s, "MapColors", HALF, f"MapColors({args})", result="icon_region(I, 14, 1, 19, 2)")

    # Blend offsets with the non-overlay modes (transparent regions ORed)
    for src in [SMALLS, HALF]:
        for m in ["ICON_MULTIPLY", "ICON_SUBTRACT", "ICON_AND"]:
            for x, y in [("11", "1"), ("17", "17"), ("-5", "3"), ("33", "1")]:
                op(s, "Blend", ASYM, f"Blend({src}, {m}, {x}, {y})",
                   result="list(icon_region(I, 14, 14, 19, 19), icon_region(I, 1, 1, 4, 4), icon_region(I, 26, 26, 29, 29))")

    # Insert of a larger icon into a smaller one (BYOND documents that the base is resized)
    for base, call in [("icon('small.dmi')", f"Insert({ASYM}, \"big\")"),
                       ("icon('small.dmi')", f"Insert({ASYM}, \"solid\")"),
                       ("icon('small.dmi')", f"Insert({ASYM}, \"grad\", NORTH)"),
                       (RECT, f"Insert({ASYM}, \"sq\")"),
                       (RECT, f"Insert({SMALLS}, \"sm\")"),
                       (ASYM, f"Insert({RECT}, \"r\")")]:
        op(s, "Insert", base, call,
           result="list(I.Width(), I.Height(), icon_d(I), icon_region(I, 1, 1, 3, 3, \"solid\"))")

    # Insert with no icon_state into a multi-state icon
    ins(f"Insert({ASYM})", base="icon('test.dmi')")
    ins(f"Insert({ASYM}, dir = NORTH)", base="icon('test.dmi')")
    ins(f"Insert({ASYM}, frame = 2)", base="icon('test.dmi')")

    # Insert delay / rewind: GetPixel can't see timing, so compare the bytes of saved .dmi files.
    # The same build twice must give the same bytes (sanity); a different delay/rewind must not.
    def dmi_cmp(tag, pre_a, pre_b):
        fa, fb = f"icon_dl_{tag}_a.dmi", f"icon_dl_{tag}_b.dmi"
        lines = [f"fdel(\"{fa}\")", f"fdel(\"{fb}\")"]
        for nm, pre in (("A", pre_a), ("B", pre_b)):
            lines += [f"var/icon/{nm} = {ASYM}"] + [p.replace("X.", f"{nm}.") for p in pre]
        lines += [f"fcopy(A, \"{fa}\")", f"fcopy(B, \"{fb}\")",
                  f"var/list/res = list(md5(file(\"{fa}\")) == md5(file(\"{fb}\")), "
                  f"icon_states(file(\"{fa}\")), icon_states(file(\"{fb}\")))",
                  f"fdel(\"{fa}\")", f"fdel(\"{fb}\")"]
        s.body("Insert", lines, "res")

    def two(dl1, dl2):
        return [f"X.Insert({GRAD}, \"an\", frame = 1{dl1})", f"X.Insert({HALF}, \"an\", frame = 2{dl2})"]
    dmi_cmp("same", two(", delay = 2", ""), two(", delay = 2", ""))
    dmi_cmp("d2d5", two(", delay = 2", ""), two(", delay = 5", ""))
    dmi_cmp("d0d2", two("", ""), two(", delay = 2", ""))
    dmi_cmp("rew", two(", delay = 2", ""), two(", delay = -2", ""))
    dmi_cmp("fr2", two("", ", delay = 1"), two("", ", delay = 3"))
    dmi_cmp("frac", two(", delay = 2", ""), two(", delay = 2.5", ""))
    dmi_cmp("txt", two(", delay = 2", ""), two(", delay = \"3\"", ""))
    dmi_cmp("zero", two(", delay = 0", ""), two(", delay = null", ""))
    # Rewind state of the fixture vs a copy with frame 1 re-inserted with a positive delay (turns rewind off)
    s.body("Insert", ["fdel(\"icon_dl_fx_a.dmi\")", "fdel(\"icon_dl_fx_b.dmi\")",
                      "var/icon/A = icon('test.dmi', \"rewind\")", "var/icon/B = icon('test.dmi', \"rewind\")",
                      "B.Insert(icon('test.dmi', \"rewind\", frame = 1), \"rewind\", frame = 1, delay = 1)",
                      "fcopy(A, \"icon_dl_fx_a.dmi\")", "fcopy(B, \"icon_dl_fx_b.dmi\")",
                      "var/list/res = list(md5(file(\"icon_dl_fx_a.dmi\")) == md5(file(\"icon_dl_fx_b.dmi\")))",
                      "fdel(\"icon_dl_fx_a.dmi\")", "fdel(\"icon_dl_fx_b.dmi\")"], "res")

    # icon_states / IconStates modes on icons bigger than world.icon_size
    for pre in [[f"var/icon/I = {ASYM}", "I.Scale(64, 64)"],
                [f"var/icon/I = {ASYM}", "I.Crop(1, 1, 64, 64)"],
                ["var/icon/I = icon('test.dmi')", "I.Scale(64, 64)"],
                [f"var/icon/I = {RECT}", "I.Scale(96, 32)"]]:
        for m in ["0", "1", "2"]:
            s.body("icon_states", pre, f"icon_states(I, {m})")
            s.body("IconStates", pre, f"I.IconStates({m})")
        s.body("icon_states", pre, "list(I.Width(), I.Height(), icon_states(I))")

    # turn() proc on directional / animated icons, non-45 angles
    s.body("turn", [f"var/icon/I = {DIRS4}", "var/icon/J = turn(I, 90)"], "list(icon_d(J, 2, 2), icon_d(I, 2, 2))")
    s.body("turn", [f"var/icon/I = {DIRS8}", "var/icon/J = turn(I, 45)"], "list(icon_d(J), icon_d(I))")
    s.body("turn", [f"var/icon/I = {DIRS8}", "var/icon/J = turn(I, 90)"], "list(icon_d(J), icon_d(I))")
    s.body("turn", [f"var/icon/I = {ANIM}", "var/icon/J = turn(I, 90)"],
           "list(icon_allhash(J, \"anim\"), icon_allhash(I, \"anim\"))")
    for a in ["30", "100", "-60", "44", "46"]:
        s.body("turn", [f"var/icon/I = {ASYM}", f"var/icon/J = turn(I, {a})", f"var/icon/K = {ASYM}",
                        f"K.Turn(-({a}))", f"var/icon/L = {ASYM}", f"L.Turn({a})"],
               "list(icon_r(J), icon_r(I), parity_icon_hash(J, \"asym\") == parity_icon_hash(K, \"asym\"), "
               "parity_icon_hash(J, \"asym\") == parity_icon_hash(L, \"asym\"))")

    # Procs on an empty new /icon()
    for call in ["Turn(90)", "Turn(45)", "Flip(EAST)", "Shift(NORTH, 1)", "Shift(EAST, 1, 1)", "Crop(1, 1, 8, 8)",
                 "SetIntensity(0.5)", "SwapColor(\"#000000\", \"#ff0000\")", "SwapColor(null, \"#ff0000\")",
                 "MapColors(\"#ff0000\", \"#00ff00\", \"#0000ff\")", "MapColors(0, 1, 0, 0, 0, 1, 1, 0, 0)",
                 f"Blend({ASYM}, ICON_OVERLAY)", f"Blend({ASYM}, ICON_ADD)", "Blend(\"#ff0000\", ICON_ADD)",
                 "IconStates()", "Width()", "GetPixel(1, 1, \"\")"]:
        op(s, "empty", "new /icon()", call, result="list(I, I.Width(), I.Height(), icon_states(I))")

    # Assigning a /icon to atom.icon (documented: becomes a static icon file)
    s.body("atom.icon", ["var/obj/O = parity_track(new /obj(locate(1, 1, 1)))", f"var/icon/I = {ASYM}",
                         "I.Flip(EAST)", "O.icon = I"],
           "list(isicon(O.icon), isfile(O.icon), istype(O.icon, /icon), icon_r(icon(O.icon)), icon_states(O.icon))")
    s.body("atom.icon", ["var/obj/O = parity_track(new /obj(locate(1, 1, 1)))", f"var/icon/I = {ASYM}",
                         "I.Flip(EAST)", "O.icon = I", "I.DrawBox(\"#ffffff\", 1, 1, 32, 32)"],
           "list(icon_r(icon(O.icon)), icon_r(I), O.icon == I)")
    s.body("atom.icon", ["var/obj/O = parity_track(new /obj(locate(1, 1, 1)))", "var/icon/I = icon('test.dmi')",
                         "I.Turn(90)", "O.icon = I", "O.icon_state = \"dirs4\""],
           "list(icon_states(O.icon), icon_d(icon(O.icon, \"dirs4\"), 2, 2))")
    s.body("atom.icon", ["var/obj/O = parity_track(new /obj(locate(1, 1, 1)))", f"O.icon = {ASYM} + \"#101010\""],
           "list(isicon(O.icon), istype(O.icon, /icon), icon_r(icon(O.icon)))")

    # Icon as text
    for e in ["icon('test.dmi')", f"{ASYM} + \"#101010\"", f"turn({ASYM}, 90)", "new /icon()", ASYM, "'test.dmi'",
              "'test.dmi' + \"#101010\""]:
        s.case("icon-text", f"\"[{e}]\"")
        s.case("icon-text", f"length(\"[{e}]\")")
    s.body("icon-text", [f"var/icon/I = {ASYM}", "I.Flip(EAST)"], "list(\"[I]\", \"x[I]y\", \"[I.type]\")")

    # GetPixel frame on the 2-frame rewind state
    for f in ["0", "1", "2", "3", "4"]:
        s.case("GetPixel", f"icon('test.dmi').GetPixel(5, 5, \"rewind\", 0, {f})")
        s.case("GetPixel", f"icon('test.dmi', \"rewind\").GetPixel(5, 5, null, 0, {f})")

    # Shift diagonals and wrap on non-square icons
    for call in ["Shift(NORTHEAST, 3, 1)", "Shift(SOUTHWEST, 20, 1)", "Shift(NORTH, 17, 0)", "Shift(NORTH, 17, 1)",
                 "Shift(EAST, 33, 1)", "Shift(SOUTHEAST, 5, 0)", "Shift(NORTHWEST, 18, 1)"]:
        op(s, "Shift", RECT, call,
           result="list(I.Width(), I.Height(), icon_region(I, 1, 1, 6, 16), icon_region(I, 27, 1, 32, 3))")

    # Turn arbitrary angles on non-square and small icons
    for a in ["30", "45", "90"]:
        op(s, "Turn", RECT, f"Turn({a})", result="list(I.Width(), I.Height(), icon_region(I, 1, 1, 6, 6))")
    for a in ["30", "45"]:
        op(s, "Turn", SMALL, f"Turn({a})", result="list(I.Width(), I.Height(), icon_region(I, 6, 6, 11, 11))")
