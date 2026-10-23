"""Appearance-related vars: assign odd values on /obj, /image and /mutable_appearance and read back
what was stored. Covers color (names, short/long hex, alpha hex, rgb(), color matrices of 9/12/16/20
numbers and of row strings, invalid lists), alpha, dir, layer, plane, icon, icon_state, name, desc,
transform, pixel_x/y/w/z, icon_w/z, appearance_flags, blend_mode, invisibility, opacity, density,
mouse_opacity, luminosity, maptext*, screen_loc, render_target/source, vis_flags, gender, suffix,
mouse pointers, filters (filter() vars and per-type defaults, abstract vs attached, named filters,
list forms), appearance copying (atom/appearance/image/mutable_appearance/type/icon sources),
new /mutable_appearance(src) copies and image() constructor argument forms.

BYOND reference points targeted (info.html /atom/var/*, /image, /mutable_appearance, /proc/image,
/proc/filter, /{notes}/filters/*):
- color: null = white; rgb() text or a color matrix list. An alpha component in the color also sets
  alpha. A matrix reads back as a 20-item list (RGBA) that is a copy, so editing it does nothing.
- alpha 0..255; invisibility 0..101; luminosity integer 0..6; plane -10000..10000 integers only,
  FLOAT_PLANE (+p) relative; mouse_opacity 0/1/2; blend_mode BLEND_DEFAULT..BLEND_INSET_OVERLAY.
- transform: reading gives a copy; null reverts to identity; a list of 6 numbers is legal.
- appearance: reading gives a copy; assigning copies the listed vars but NOT density, dir,
  screen_loc, verbs - those ARE copied when a /mutable_appearance is assigned. Assigning an atom
  copies its appearance.
- image(icon, loc, icon_state, layer, dir): icon may be an icon, icon_state text, prototype, object
  or image; text icon becomes icon_state when no icon_state is given; loc can never be text so
  image('x.dmi', "state") works. Default image layer for a plain icon is FLY_LAYER.
- filter(type=..., ...): abstract filter copied into atom.filters; attached filters are live.
  Same-name filter replaces the old one. Per-type defaults (blur size 1, drop_shadow x 1 y -1
  size 1 color #00000080, radial_blur size 0.01, rays density 10 threshold 0.5 flags
  FILTER_OVERLAY|FILTER_UNDERLAY, ripple repeat 2 falloff 1, layer flags FILTER_OVERLAY, ...).

OpenDream code these cases aim at (AtomManager.SetAppearanceVar/GetAppearanceVar,
DreamObjectAtom/Movable/Image SetVar, DreamObjectFilter, NativeProc_filter/image):
- color: text goes through Color parsing ("white" when not text); readback drops the alpha channel
  and lowercases; list that is not a valid matrix throws; identity matrix reads back as null.
- dir: <= 0 or non-number ignored, > 255 clamped to 255; no rounding rules of BYOND.
- alpha: float clamped then truncated to byte; invisibility clamped to -127..127 (not 0..101).
- pixel_*/maptext_*/plane: TryGetValueAsInteger (truncation), non-numbers leave old value or 0.
- blend_mode out of range -> BLEND_DEFAULT; mouse_opacity unclamped; opacity != 0.
- icon_state "" stored as null; name non-text -> ""; desc non-text -> null; render_* non-text.
- transform: non-matrix (incl. list of 6) -> identity.
- filters: filter vars read back as the /dm_filter declaration (null) - "TODO: Variable getting";
  filter with null args drops them; filter(type="bogus") returns null; OD has an extra "greyscale".
- FILTER_OVERLAY is 0 and FILTER_UNDERLAY 1 in OD's Defines.dm.
- image(): text icon is not treated as icon_state; OD accepts extra pixel_x/pixel_y arguments.
- appearance = X: OD keeps dir, copies everything else (density/screen_loc are not appearance).
"""
from gen import dm_str

OBJ = "var/obj/O = parity_track(new /obj(locate(1, 1, 1)))"
OBJ2 = "var/obj/P = parity_track(new /obj(locate(2, 1, 1)))"
IMG = "var/image/I = image('test.dmi', \"solid\")"
MA = "var/mutable_appearance/M = new /mutable_appearance"

HELPERS = r'''
/obj/appearance_typed
	name = "typed thing"
	desc = "typed desc"
	icon = 'test.dmi'
	icon_state = "solid"
	dir = EAST
	alpha = 100
	color = "#00ff00"
	layer = 7
	plane = 3
	pixel_x = 4
	pixel_y = -2
	density = 1
	opacity = 1
	invisibility = 5
	mouse_opacity = 2
	maptext = "mt"
	screen_loc = "2,3"
	blend_mode = BLEND_ADD
	appearance_flags = KEEP_TOGETHER
	render_target = "rt"
	luminosity = 2
	suffix = "sfx"
	gender = FEMALE

/obj/appearance_ct_dir3
	dir = 3

/obj/appearance_ct_dir0
	dir = 0

/obj/appearance_ct_alpha_frac
	alpha = 100.7

/obj/appearance_ct_color_name
	color = "red"

/obj/appearance_ct_color_short
	color = "#f008"

/obj/appearance_ct_layer
	layer = 3.5

/obj/appearance_ct_plane_float
	plane = FLOAT_PLANE

/obj/appearance_ct_pixel
	pixel_x = 2.5

/obj/appearance_ct_state
	icon_state = ""

/obj/appearance_ct_name_empty
	name = ""

/obj/appearance_ct_color_matrix
	color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)

/obj/appearance_ct_color_alpha
	color = "#ff000080"

/obj/appearance_ct_transform
	transform = matrix(2, 0, 0, 0, 2, 0)

/obj/appearance_ct_filter
	filters = filter(type = "blur", size = 2)

/obj/appearance_ct_screen
	screen_loc = "CENTER"

/obj/appearance_ct_lum
	luminosity = 10

/matrix/appearance_sub

/proc/appearance_ftypes(list/L)
	var/list/R = list()
	for(var/F in L)
		try
			R += F:type
		catch(var/exception/e)
			R += "ERR [e.name]"
	return R

/image/appearance_img
	name = "img"
	icon_state = "typed"
	layer = 9
	alpha = 50

// Never instantiated: declares the filter parameter names so the ":" operator compiles on BYOND,
// which only accepts a name declared on some type
/datum/appearance_fnames
	var/threshold
	var/factor
	var/falloff
	var/radius
	var/repeat
	var/space
	var/render_source
	var/offset
	var/density
	var/flags
	var/size
	var/bogus

/proc/appearance_rd(D, n)
	try
		var/v = D:vars[n]
		if(n == "icon")
			return appearance_icon_info(v)
		if(n == "overlays" || n == "underlays" || n == "filters" || n == "vis_contents" || n == "verbs")
			if(islist(v))
				var/list/L = v
				return "len=[L.len]"
		return v
	catch(var/exception/e)
		return "ERR [e.name]"

/proc/appearance_dump(D, list/names)
	var/list/R = list()
	for(var/n in names)
		R[n] = appearance_rd(D, n)
	return R

// What kind of icon value this is, without printing anything resource-id dependent
/proc/appearance_icon_info(x)
	var/list/L = list("null" = isnull(x), "file" = isfile(x), "icon" = istype(x, /icon), "text" = istext(x), "num" = isnum(x), "is_test" = ("[x]" == "test.dmi"), "is_small" = ("[x]" == "small.dmi"))
	try
		L["states"] = x ? icon_states(x) : null
	catch(var/exception/e)
		L["states"] = "ERR [e.name]"
	return L

/proc/appearance_kind(x)
	return list("null" = isnull(x), "datum" = istype(x, /datum), "image" = istype(x, /image), "ma" = istype(x, /mutable_appearance), "atom" = istype(x, /atom), "list" = islist(x), "text" = istext(x), "num" = isnum(x))
'''

# Names dumped for copies
DUMP = ["name", "desc", "icon", "icon_state", "dir", "alpha", "color", "layer", "plane", "pixel_x",
        "pixel_y", "density", "opacity", "invisibility", "mouse_opacity", "maptext", "screen_loc",
        "blend_mode", "appearance_flags", "render_target", "luminosity", "suffix", "gender",
        "transform", "overlays", "filters", "glide_size"]
MA_NAMES = DUMP + ["animate_movement"]
DUMP_IMG = ["icon", "icon_state", "layer", "dir", "loc", "pixel_x", "pixel_y", "plane", "alpha",
            "color", "name", "appearance_flags", "blend_mode", "transform", "overlays", "filters"]


def dump(expr, names):
    return f"appearance_dump({expr}, list({', '.join(dm_str(n) for n in names)}))"


# ---------------- value pools (DM source) ----------------
COLOR = [
    '"red"', '"RED"', '"Red"', '"white"', '"black"', '"blue"', '"gray"', '"grey"', '"teal"',
    '"#f00"', '"#F00"', '"#ff0000"', '"#FF0000"', '"#ff000080"', '"#FF000080"', '"#f008"', '"#ff00"',
    '"#ffffff"', '"#FFFFFF"', '"#fff"', '"#000"', '"#00000000"', '"#ffffffff"', '"#12345"', '"#1234567"',
    '"#zzzzzz"', '"#"', '""', '"ff0000"', '"notacolor"', '" red"', '"rgb(1,2,3)"',
    "rgb(255, 0, 0)", "rgb(1, 2, 3, 4)", "rgb(0, 0, 0, 0)",
    "null", "0", "1", "16711680", "-1", "0.5", "NAN", "PINF",
    "new /datum", "/obj", "matrix()", "'test.dmi'",
]
CMATRIX = [
    "list()", "list(1)", "list(1, 2, 3)",
    "list(1, 0, 0, 0, 1, 0, 0, 0, 1)",
    "list(0, 1, 0, 1, 0, 0, 0, 0, 1)",
    "list(0.33, 0.33, 0.33, 0.59, 0.59, 0.59, 0.11, 0.11, 0.11)",
    "list(2, 0, 0, 0, 2, 0, 0, 0, 2)",
    "list(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.1, 0.2, 0.3)",
    "list(-1, 0, 0, 0, -1, 0, 0, 0, -1, 1, 1, 1)",
    "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5)",
    "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)",
    "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0)",
    "list(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0)",
    "list(0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 1, 0.1, 0.2, 0.3, 0)",
    "list(1, 2, 3, 4, 5, 6, 7, 8)",
    "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)",
    "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)",
    "list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)",
    'list("#ff0000", "#00ff00", "#0000ff")',
    'list("#f00", "#0f0", "#00f", "#000")',
    'list("#ff000080", "#00ff0080", "#0000ff80", "#00000080")',
    'list("#ff000000", "#00ff0000", "#0000ff00", "#000000ff", "#00000000")',
    'list(null, null, null, null, "#333f")',
    'list(null, null, null)',
    'list("red", "green", "blue")',
    'list("a", "b", "c")',
    'list(1, 2, "x", 4, 5, 6, 7, 8, 9)',
    "list(NAN, 0, 0, 0, 1, 0, 0, 0, 1)",
    "list(PINF, 0, 0, 0, 1, 0, 0, 0, 1)",
    'list("x" = 1)',
    "list(list(1, 0, 0), list(0, 1, 0), list(0, 0, 1))",
]
COLOR_S = ['"red"', '"#f00"', '"#ff000080"', '"#ABCDEF"', '"#f008"', '""', '"bogus"', "null", "0",
           "list(1, 0, 0, 0, 1, 0, 0, 0, 1)", "list(0, 1, 0, 1, 0, 0, 0, 0, 1)",
           'list("#ff0000", "#00ff00", "#0000ff")', "list(1, 2, 3)", "new /datum"]
ALPHA = ["0", "1", "128", "255", "256", "1000", "-1", "-1000", "0.5", "0.4", "1.4", "1.5", "2.5",
         "127.6", "254.9", "255.5", "-0.5", '"128"', '"abc"', "null", "PINF", "NINF", "NAN",
         "list()", "new /datum", "1e7", "16777217"]
ALPHA_S = ["0", "128", "300", "-5", "1.5", "127.6", '"128"', "null", "NAN"]
DIR = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
       "17", "32", "64", "255", "256", "1000", "-1", "-2", "-16", "1.5", "2.7", "0.5", "4.9", '"2"',
       '"north"', "null", "PINF", "NINF", "NAN", "list()", "new /datum", "NORTH|SOUTH", "EAST|WEST",
       "UP", "DOWN", "NORTH|UP", "1e7"]
DIR_S = ["0", "3", "4", "15", "16", "-1", "100", "2.7", '"4"', "null"]
LAYER = ["0", "1", "-1", "3.5", "1e7", "-1e7", "FLOAT_LAYER", "MOB_LAYER + 1", "AREA_LAYER",
         "FLY_LAYER", "BACKGROUND_LAYER", "EFFECTS_LAYER", "TOPDOWN_LAYER", "BACKGROUND_LAYER + 3",
         "EFFECTS_LAYER + 0.5", "0.0001", "1e-7", "16777217", '"5"', "null", "PINF", "NINF", "NAN",
         "list()", "new /datum"]
LAYER_S = ["0", "-1", "3.5", "FLOAT_LAYER", "1e7", '"5"', "null", "NAN"]
PLANE = ["0", "1", "-1", "5", "10000", "10001", "-10000", "-10001", "32766", "32767", "32768",
         "-32767", "-32768", "-32769", "65536", "1e7", "-1e7", "0.5", "1.5", "-1.5", "2.7", "-2.7",
         "FLOAT_PLANE", "FLOAT_PLANE + 1", "FLOAT_PLANE - 1", "FLOAT_PLANE + 0.5", '"3"', "null",
         "PINF", "NINF", "NAN", "list()", "new /datum"]
PLANE_S = ["0", "-1", "1.5", "-2.7", "10001", "FLOAT_PLANE", "FLOAT_PLANE + 1", '"3"', "null"]
ICON = ["'test.dmi'", "'small.dmi'", "'rect.dmi'", "icon('test.dmi')", "icon('test.dmi', \"solid\")",
        "icon('small.dmi', \"grad\")", "new /icon", '"test.dmi"', '"nonexistent.dmi"', '""',
        "file(\"test.dmi\")", "null", "0", "1", "list()", "new /datum", "/obj", "/obj/appearance_typed",
        "image('test.dmi', \"solid\")", "PINF"]
ICON_S = ["'test.dmi'", "icon('test.dmi', \"solid\")", '"test.dmi"', "null", "1", "list()"]
STATE = ['"solid"', '""', '"nonexistent"', '"SOLID"', '" solid"', '"a\\nb"', "1", "0", "-1", "1.5",
         "null", "list()", 'list("a")', "new /datum", "/obj", "'test.dmi'", "PINF", "NAN"]
STATE_S = ['"solid"', '""', "1", "1.5", "null", "list()", "/obj"]
NAME = ['"x"', '""', '" "', '"The Box"', '"\\improper thing"', '"\\proper Bob"', '"<b>x</b>"',
        "1", "0", "-1.5", "1e7", "null", "list()", 'list("a")', "new /datum", "/obj", "'test.dmi'",
        "PINF", "NAN"]
NAME_S = ['"x"', '""', "1", "1.5", "null", "list()", "/obj"]
TRANSFORM = ["matrix()", "matrix(2, 0, 0, 0, 2, 0)", "matrix(1, 2, 3, 4, 5, 6)", "matrix(0, 0, 0, 0, 0, 0)",
             "matrix(NAN, 0, 0, 0, 1, 0)", "matrix(PINF, 0, 0, 0, 1, 0)", "matrix(0.5, 0.25, -3, 1.5, -2, 10)",
             "list(1, 2, 3, 4, 5, 6)", "list(1, 0, 0, 0, 1, 0)", "list(2, 0, 5, 0, 2, 7)", "list(1, 2, 3)",
             "list(1, 2, 3, 4, 5, 6, 7)", 'list("a", 2, 3, 4, 5, 6)', "list(null, 2, 3, 4, 5, 6)",
             "list()", "null", "0", "1", "2", '"x"', '"1,2,3,4,5,6"', "new /datum", "/matrix"]
TRANSFORM_S = ["matrix(2, 0, 0, 0, 2, 0)", "list(1, 2, 3, 4, 5, 6)", "list(1, 2, 3)", "null", "2", '"x"']
PIXEL = ["0", "1", "-1", "0.5", "-0.5", "1.5", "-1.5", "2.7", "-2.7", "0.999", "32", "1000", "-1000",
         "32767", "32768", "-32768", "-32769", "65536", "1e7", "-1e7", "16777217", "2147483648",
         "PINF", "NINF", "NAN", '"5"', '"abc"', "null", "list()", "new /datum"]
PIXEL_S = ["0", "-1", "1.5", "-2.7", "32768", "1e7", "NAN", '"5"', "null"]
AFLAGS = ["0", "1", "KEEP_TOGETHER", "PLANE_MASTER | NO_CLIENT_COLOR", "TILE_MOVER", "4095", "4096",
          "8192", "65535", "65536", "1 << 20", "16777215", "16777216", "-1", "-2", "1.5", "2.9",
          '"1"', "null", "PINF", "NAN", "list()"]
BLEND = ["0", "1", "2", "3", "4", "5", "6", "7", "100", "255", "256", "-1", "1.5", "2.7", "4.99",
         '"2"', "null", "PINF", "NAN", "list()"]
INVIS = ["0", "1", "50", "100", "101", "102", "126", "127", "128", "200", "255", "256", "1000",
         "-1", "-100", "-127", "-128", "-129", "-1000", "0.5", "1.5", "100.7", "-0.5", '"5"',
         "null", "PINF", "NINF", "NAN", "list()"]
BOOLISH = ["0", "1", "2", "-1", "0.5", "0.1", "-0.5", "100", '"1"', '"0"', '""', "null", "list()",
           "new /datum", "PINF", "NAN"]
MOP = ["0", "1", "2", "3", "4", "-1", "100", "255", "256", "1.5", "2.5", "0.5", '"2"', "null",
       "PINF", "NAN", "list()"]
LUM = ["0", "1", "6", "7", "100", "-1", "1.5", "2.7", "0.5", '"3"', "null", "PINF", "NAN", "list()"]
MAPTEXT = ['"hi"', '""', '"<b>x</b> & y"', '"<span style=\'color:red\'>r</span>"', "1", "0", "1.5",
           "null", "list()", 'list("a")', "new /datum", "'test.dmi'", "/obj"]
MAPNUM = ["0", "1", "-1", "1.5", "2.7", "-2.7", "64", "1000", "1e7", "-1e7", '"5"', "null", "PINF",
          "NAN", "list()"]
SCREEN = ['"1,1"', '"CENTER"', '"NORTH,WEST"', '"WEST,NORTH"', '"NORTHWEST"', '"NORTH WEST"',
          '"1:16,2:-4"', '"1,1 to 3,3"', '"CENTER+2,CENTER-1"', '"WEST+50%"', '"LEFT,TOP"',
          '"TOPLEFT"', '"SCREEN_SOUTHWEST"', '"mapwindow:1,1"', '"1.5,2.5"', '" 1 , 1 "', '"1,1,1"',
          '"0,0"', '"-1,-1"', '""', '"garbage"', '"center"', "1", "0", "1.5", "null", "list()",
          "new /datum"]
RENDER = ['"x"', '"*x"', '""', '"*"', '"a b"', '"x y z"', "1", "0", "null", "list()", "new /datum",
          "/obj", "'test.dmi'"]
VISF = ["0", "1", "VIS_INHERIT_ID", "VIS_INHERIT_ICON | VIS_INHERIT_DIR", "VIS_HIDE", "255", "256",
        "65535", "-1", "1.5", '"1"', "null", "PINF", "NAN", "list()"]
GENDER = ["MALE", "FEMALE", "PLURAL", "NEUTER", '"male"', '"Male"', '"bogus"', '""', "1", "0", "null",
          "list()"]
POINTER = ["0", "1", "MOUSE_HAND_POINTER", "MOUSE_CROSSHAIRS_POINTER", "100", "-1", "1.5", '"solid"',
           "'test.dmi'", "icon('test.dmi', \"solid\")", "null", "list()"]


def setread(s, proc, setup, target, var, values, result=None):
    """For each value: setup, target.var = value, record result (default target.var)."""
    for v in values:
        s.body(proc, setup + [f"{target}.{var} = {v}"], result or f"{target}.{var}")


def build(s):
    s.dm(HELPERS)

    # ================= defines the vars use =================
    for d in ["FLOAT_LAYER", "AREA_LAYER", "TURF_LAYER", "OBJ_LAYER", "MOB_LAYER", "FLY_LAYER",
              "EFFECTS_LAYER", "TOPDOWN_LAYER", "BACKGROUND_LAYER", "FLOAT_PLANE",
              "BLEND_DEFAULT", "BLEND_OVERLAY", "BLEND_ADD", "BLEND_SUBTRACT", "BLEND_MULTIPLY",
              "BLEND_INSET_OVERLAY", "LONG_GLIDE", "RESET_COLOR", "RESET_ALPHA", "RESET_TRANSFORM",
              "NO_CLIENT_COLOR", "KEEP_TOGETHER", "KEEP_APART", "PLANE_MASTER", "TILE_BOUND",
              "PIXEL_SCALE", "PASS_MOUSE", "TILE_MOVER", "VIS_INHERIT_ICON", "VIS_INHERIT_ICON_STATE",
              "VIS_INHERIT_DIR", "VIS_INHERIT_LAYER", "VIS_INHERIT_PLANE", "VIS_INHERIT_ID",
              "VIS_UNDERLAY", "VIS_HIDE", "MASK_INVERSE", "MASK_SWAP", "FILTER_OVERLAY",
              "FILTER_UNDERLAY", "FILTER_COLOR_RGB", "FILTER_COLOR_HSV", "FILTER_COLOR_HSL",
              "FILTER_COLOR_HCY", "OUTLINE_SHARP", "OUTLINE_SQUARE", "WAVE_BOUNDED", "WAVE_SIDEWAYS",
              "MOUSE_INACTIVE_POINTER", "MOUSE_ACTIVE_POINTER", "MOUSE_DRAG_POINTER",
              "MOUSE_DROP_POINTER", "MOUSE_ARROW_POINTER", "MOUSE_CROSSHAIRS_POINTER",
              "MOUSE_HAND_POINTER", "MALE", "FEMALE", "PLURAL", "NEUTER"]:
        s.case("defines", d)

    # ================= color =================
    for v in COLOR + CMATRIX:
        s.body("color", [OBJ, f"O.color = {v}"], "list(O.color, O.alpha)")
    for v in COLOR_S:
        s.body("color.image", [IMG, f"I.color = {v}"], "list(I.color, I.alpha)")
        s.body("color.ma", [MA, f"M.color = {v}"], "list(M.color, M.alpha)")
        s.body("color.vars", [OBJ, f'O.vars["color"] = {v}'], "list(O.vars[\"color\"], O.alpha)")
    # Alpha interplay: color alpha sets alpha; plain color keeps alpha; alpha later keeps color
    s.body("color.alpha", [OBJ, "O.alpha = 100", 'O.color = "#ff0000"'], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, "O.alpha = 100", 'O.color = "#ff0000ff"'], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, 'O.color = "#ff000080"', "O.alpha = 255"], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, 'O.color = "#ff000080"', "O.color = null"], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, 'O.color = "#ff000080"', 'O.color = "#00ff00"'], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, "O.alpha = 10", "O.color = list(1, 0, 0, 0, 1, 0, 0, 0, 1)"], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, "O.alpha = 10", "O.color = list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5)"], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, 'O.color = list(1, 0, 0, 0, 1, 0, 0, 0, 1)', 'O.color = "#f00"'], "list(O.color, O.alpha)")
    s.body("color.alpha", [OBJ, 'O.color = "#ff000080"'], "list(O.color, O.alpha, rgb(255, 0, 0, 128))")
    # The matrix readback is a copy
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "var/list/C = O.color",
                          "if(islist(C))", "\tC[1] = 0.5"], "list(O.color, C)")
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)"], "O.color == O.color")
    s.body("color.copy", [OBJ, "var/list/L = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "O.color = L", "L[1] = 7"], "list(O.color, L)")
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)"], "islist(O.color) ? length(O.color) : -1")
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "O.color[1] = 0.5"], "O.color")
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "var/list/C = O.color", "O.color = C"], "O.color")
    s.body("color.copy", [OBJ, "O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)"], "initial(O.color)")
    s.body("color.copy", [OBJ, 'O.color = "red"'], "O.color == \"red\"")
    s.body("color.ops", [OBJ, 'O.color = "#123456"', 'O.color += "x"'], "O.color")
    s.body("color.ops", [OBJ, "O.color = 5", "O.color += 1"], "O.color")
    s.body("color.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_color_name(")], "list(O.color, O.alpha, initial(O.color))")
    s.body("color.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_color_short(")], "list(O.color, O.alpha, initial(O.color))")

    # ================= alpha =================
    setread(s, "alpha", [OBJ], "O", "alpha", ALPHA)
    setread(s, "alpha.image", [IMG], "I", "alpha", ALPHA_S)
    setread(s, "alpha.ma", [MA], "M", "alpha", ALPHA_S)
    s.body("alpha.ops", [OBJ, "O.alpha += 300"], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 10", "O.alpha -= 20"], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 100", "O.alpha *= 1.5"], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 0.5", "O.alpha += 0.5"], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 100", "O.alpha++"], "O.alpha")
    s.body("alpha.ops", [OBJ, 'O.alpha = 100', 'O.alpha = "x"'], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 100", "O.alpha = null"], "O.alpha")
    s.body("alpha.ops", [OBJ, "O.alpha = 128"], "O.color")
    s.body("alpha.vars", [OBJ, 'O.vars["alpha"] = 300'], 'O.vars["alpha"]')
    s.body("alpha.vars", [OBJ, 'O.vars["alpha"] = 1.5'], "O.alpha")
    s.body("alpha.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_alpha_frac(")], "list(O.alpha, initial(O.alpha))")

    # ================= dir =================
    setread(s, "dir", [OBJ], "O", "dir", DIR)
    setread(s, "dir.image", [IMG], "I", "dir", DIR_S)
    setread(s, "dir.ma", [MA], "M", "dir", DIR_S)
    for v in DIR_S:
        s.body("dir.after_east", [OBJ, "O.dir = EAST", f"O.dir = {v}"], "O.dir")
    s.body("dir.ops", [OBJ, "O.dir++"], "O.dir")
    s.body("dir.ops", [OBJ, "O.dir |= NORTH"], "O.dir")
    s.body("dir.ops", [OBJ, "O.dir = EAST", "O.dir -= 4"], "O.dir")
    s.body("dir.ops", [OBJ, "O.dir = turn(O.dir, 90)"], "O.dir")
    s.body("dir.ops", [OBJ, "O.dir = 3"], "list(O.dir, turn(O.dir, 90))")
    s.body("dir.vars", [OBJ, 'O.vars["dir"] = 0'], "O.dir")
    s.body("dir.vars", [OBJ, 'O.vars["dir"] = 3'], "O.dir")
    s.body("dir.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_dir3(")], "list(O.dir, initial(O.dir))")
    s.body("dir.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_dir0(")], "list(O.dir, initial(O.dir))")
    s.body("dir.mob", ["var/mob/D = parity_track(new /mob(locate(1, 1, 1)))", "D.dir = 3"], "D.dir")
    s.body("dir.mob", ["var/mob/D = parity_track(new /mob(locate(1, 1, 1)))", "D.dir = 0"], "D.dir")

    # ================= layer / plane =================
    setread(s, "layer", [OBJ], "O", "layer", LAYER)
    setread(s, "layer.image", [IMG], "I", "layer", LAYER_S)
    setread(s, "layer.ma", [MA], "M", "layer", LAYER_S)
    s.body("layer.ops", [OBJ, "O.layer += 0.25"], "O.layer")
    s.body("layer.ops", [OBJ, "O.layer = 3", 'O.layer = "x"'], "O.layer")
    s.body("layer.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_layer(")], "list(O.layer, initial(O.layer))")
    setread(s, "plane", [OBJ], "O", "plane", PLANE)
    setread(s, "plane.image", [IMG], "I", "plane", PLANE_S)
    setread(s, "plane.ma", [MA], "M", "plane", PLANE_S)
    s.body("plane.ops", [OBJ, "O.plane = 3", "O.plane += 0.5", "O.plane += 0.5"], "O.plane")
    s.body("plane.ops", [OBJ, "O.plane = 3", 'O.plane = "x"'], "O.plane")
    s.body("plane.ops", [OBJ, "O.plane = 3", "O.plane = null"], "O.plane")
    s.body("plane.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_plane_float(")], "list(O.plane, initial(O.plane))")
    s.body("plane.default", [IMG], "I.plane")
    s.body("plane.default", [MA], "M.plane")
    s.body("plane.default", [OBJ], "O.plane")

    # ================= icon / icon_state =================
    for v in ICON:
        s.body("icon", [OBJ, f"O.icon = {v}"], "appearance_icon_info(O.icon)")
    for v in ["'test.dmi'", "'small.dmi'", "file(\"test.dmi\")", '"test.dmi"', "null"]:
        s.body("icon.raw", [OBJ, f"O.icon = {v}"], "O.icon")
        s.body("icon.raw", [OBJ, f"O.icon = {v}"], "O.icon == 'test.dmi'")
    s.body("icon.dynamic", [OBJ, "var/icon/I = icon('test.dmi', \"solid\")", "O.icon = I"], "O.icon == I")
    s.body("icon.dynamic", [OBJ, "var/icon/I = icon('test.dmi', \"solid\")", "O.icon = I"], "istype(O.icon, /icon)")
    s.body("icon.dynamic", [OBJ, "var/icon/I = icon('test.dmi')", "O.icon = I", "I.Scale(16, 16)"], "appearance_icon_info(O.icon)")
    s.body("icon.dynamic", [OBJ, "var/icon/I = icon('test.dmi', \"solid\")", "O.icon = I"], "icon(O.icon)")
    s.body("icon.dynamic", [OBJ, "O.icon = 'test.dmi'", "O.icon = null"], "O.icon")
    s.body("icon.dynamic", [OBJ, "O.icon = 'test.dmi'", "O.icon = 5"], "appearance_icon_info(O.icon)")
    for v in ICON_S:
        s.body("icon.image", [IMG, f"I.icon = {v}"], "appearance_icon_info(I.icon)")
        s.body("icon.ma", [MA, f"M.icon = {v}"], "appearance_icon_info(M.icon)")
    setread(s, "icon_state", [OBJ], "O", "icon_state", STATE)
    setread(s, "icon_state.image", [IMG], "I", "icon_state", STATE_S)
    setread(s, "icon_state.ma", [MA], "M", "icon_state", STATE_S)
    s.body("icon_state", [OBJ, 'O.icon_state = "solid"', 'O.icon_state = ""'], "isnull(O.icon_state)")
    s.body("icon_state", [OBJ, 'O.icon_state = "solid"', "O.icon_state = 5"], "O.icon_state")
    s.body("icon_state", [OBJ, 'O.icon_state = 5'], "isnum(O.icon_state)")
    s.body("icon_state.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_state(")], "list(O.icon_state, isnull(O.icon_state), initial(O.icon_state))")

    # ================= name / desc / suffix / text / gender =================
    for v in NAME:
        s.body("name", [OBJ, f"O.name = {v}"], "O.name")
        s.body("name.text", [OBJ, f"O.name = {v}"], '"[O]"')
        s.body("desc", [OBJ, f"O.desc = {v}"], "O.desc")
    for v in NAME_S:
        s.body("name.image", [IMG, f"I.name = {v}"], "I.name")
        s.body("name.ma", [MA, f"M.name = {v}"], "M.name")
        s.body("desc.ma", [MA, f"M.desc = {v}"], "M.desc")
        s.body("suffix", [OBJ, f"O.suffix = {v}"], "O.suffix")
        s.body("text", [OBJ, f"O.text = {v}"], "O.text")
    s.body("name", [OBJ, 'O.name = "abc"'], "O.text")
    s.body("name", [OBJ, 'O.name = 5', 'O.name += "x"'], "O.name")
    s.body("name.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_name_empty(")], "list(O.name, \"[O]\", initial(O.name))")
    setread(s, "gender", [OBJ], "O", "gender", GENDER)
    s.body("gender.text", [OBJ, "O.gender = FEMALE", 'O.name = "Ann"'], r'"[O]: \he \him \his"')

    # ================= transform =================
    setread(s, "transform", [OBJ], "O", "transform", TRANSFORM)
    setread(s, "transform.image", [IMG], "I", "transform", TRANSFORM_S)
    setread(s, "transform.ma", [MA], "M", "transform", TRANSFORM_S)
    s.body("transform.copy", [OBJ, "var/matrix/T = O.transform", "T.Scale(2)"], "list(O.transform, T)")
    s.body("transform.copy", [OBJ, "var/matrix/T = matrix(2, 0, 0, 0, 2, 0)", "O.transform = T", "T.Scale(3)"], "list(O.transform, T)")
    s.body("transform.copy", [OBJ], "O.transform == O.transform")
    s.body("transform.copy", [OBJ, "var/matrix/T = matrix(2, 0, 0, 0, 2, 0)", "O.transform = T"], "O.transform == T")
    s.body("transform.copy", [OBJ], "istype(O.transform, /matrix)")
    s.body("transform.copy", [OBJ, "O.transform = null"], "istype(O.transform, /matrix)")
    s.body("transform.ops", [OBJ, "O.transform *= 2"], "O.transform")
    s.body("transform.ops", [OBJ, "O.transform = turn(O.transform, 90)"], "O.transform")
    s.body("transform.ops", [OBJ, "O.transform = matrix(2, 0, 0, 0, 2, 0)", "O.transform = null"], "O.transform")
    s.body("transform.ops", [OBJ, "O.transform = matrix(2, 0, 0, 0, 2, 0)", 'O.transform = "x"'], "O.transform")
    s.body("transform.ops", [OBJ, "O.transform = matrix(2, 0, 0, 0, 2, 0)", "O.transform += matrix(1, 0, 0, 0, 1, 0)"], "O.transform")
    s.body("transform.ops", [OBJ, "var/matrix/T = O.transform", "T.Translate(3, 4)", "O.transform = T"], "O.transform")
    s.body("transform.ops", [OBJ, "O.transform = new /matrix(1, 2, 3, 4, 5, 6)"], "O.transform.type")
    s.body("transform.vars", [OBJ, 'O.vars["transform"] = list(1, 2, 3, 4, 5, 6)'], "O.transform")

    # ================= pixel offsets =================
    for var in ["pixel_x", "pixel_y", "pixel_w", "pixel_z"]:
        setread(s, var, [OBJ], "O", var, PIXEL)
        setread(s, var + ".image", [IMG], "I", var, PIXEL_S)
        setread(s, var + ".ma", [MA], "M", var, PIXEL_S)
        s.body(var + ".ops", [OBJ, f"O.{var} += 0.5", f"O.{var} += 0.5"], f"O.{var}")
        s.body(var + ".ops", [OBJ, f"O.{var} = 5", f'O.{var} = "x"'], f"O.{var}")
        s.body(var + ".ops", [OBJ, f"O.{var} = 5", f"O.{var} = null"], f"O.{var}")
    for var in ["icon_w", "icon_z"]:
        setread(s, var, [OBJ], "O", var, PIXEL_S)
        setread(s, var + ".ma", [MA], "M", var, PIXEL_S)
    s.body("pixel_x.compiletime", [OBJ.replace("new /obj(", "new /obj/appearance_ct_pixel(")], "list(O.pixel_x, initial(O.pixel_x))")
    s.body("pixel_x.vars", [OBJ, 'O.vars["pixel_x"] = 2.5'], "O.pixel_x")

    # ================= flags-like numeric vars =================
    setread(s, "appearance_flags", [OBJ], "O", "appearance_flags", AFLAGS)
    setread(s, "appearance_flags.image", [IMG], "I", "appearance_flags", AFLAGS[:12])
    setread(s, "appearance_flags.ma", [MA], "M", "appearance_flags", AFLAGS[:12])
    s.body("appearance_flags.ops", [OBJ, "O.appearance_flags |= KEEP_TOGETHER", "O.appearance_flags |= PIXEL_SCALE"], "O.appearance_flags")
    s.body("appearance_flags.ops", [OBJ, "O.appearance_flags = 4095", "O.appearance_flags &= ~KEEP_TOGETHER"], "O.appearance_flags")
    setread(s, "blend_mode", [OBJ], "O", "blend_mode", BLEND)
    setread(s, "blend_mode.image", [IMG], "I", "blend_mode", BLEND[:13])
    setread(s, "blend_mode.ma", [MA], "M", "blend_mode", BLEND[:13])
    s.body("blend_mode.ops", [OBJ, "O.blend_mode = BLEND_ADD", "O.blend_mode = 9"], "O.blend_mode")
    setread(s, "invisibility", [OBJ], "O", "invisibility", INVIS)
    setread(s, "invisibility.ma", [MA], "M", "invisibility", INVIS[::3])
    s.body("invisibility.ops", [OBJ, "O.invisibility = 100", "O.invisibility += 50"], "O.invisibility")
    setread(s, "opacity", [OBJ], "O", "opacity", BOOLISH)
    setread(s, "opacity.ma", [MA], "M", "opacity", BOOLISH[::2])
    setread(s, "density", [OBJ], "O", "density", BOOLISH)
    setread(s, "density.ma", [MA], "M", "density", BOOLISH[::2])
    setread(s, "mouse_drop_zone", [OBJ], "O", "mouse_drop_zone", BOOLISH[::2])
    setread(s, "mouse_opacity", [OBJ], "O", "mouse_opacity", MOP)
    setread(s, "mouse_opacity.ma", [MA], "M", "mouse_opacity", MOP[::2])
    setread(s, "luminosity", [OBJ], "O", "luminosity", LUM)
    setread(s, "luminosity.ma", [MA], "M", "luminosity", LUM[::2])
    setread(s, "infra_luminosity", [OBJ], "O", "infra_luminosity", LUM[::2])
    for var in ["mouse_over_pointer", "mouse_drag_pointer", "mouse_drop_pointer"]:
        for v in POINTER:
            s.body(var, [OBJ, f"O.{var} = {v}"], f"isfile(O.{var}) || istype(O.{var}, /icon) ? appearance_icon_info(O.{var}) : O.{var}")

    # ================= maptext =================
    setread(s, "maptext", [OBJ], "O", "maptext", MAPTEXT)
    setread(s, "maptext.image", [IMG], "I", "maptext", MAPTEXT[::2])
    setread(s, "maptext.ma", [MA], "M", "maptext", MAPTEXT[::2])
    for var in ["maptext_width", "maptext_height", "maptext_x", "maptext_y"]:
        setread(s, var, [OBJ], "O", var, MAPNUM)
        setread(s, var + ".ma", [MA], "M", var, MAPNUM[::3])
    s.body("maptext.ops", [OBJ, 'O.maptext = "a"', 'O.maptext += "b"'], "O.maptext")
    s.body("maptext.ops", [OBJ, "O.maptext_width += 0.5", "O.maptext_width += 0.5"], "O.maptext_width")

    # ================= screen_loc =================
    setread(s, "screen_loc", [OBJ], "O", "screen_loc", SCREEN)
    setread(s, "screen_loc.ma", [MA], "M", "screen_loc", SCREEN[::3])
    s.body("screen_loc.ops", [OBJ, 'O.screen_loc = "1,1"', 'O.screen_loc += ":4"'], "O.screen_loc")
    s.body("screen_loc.ops", [OBJ, 'O.screen_loc = "1,1"', "O.screen_loc = null"], "O.screen_loc")

    # ================= render_target / render_source / vis_flags =================
    setread(s, "render_target", [OBJ], "O", "render_target", RENDER)
    setread(s, "render_source", [OBJ], "O", "render_source", RENDER)
    setread(s, "render_target.image", [IMG], "I", "render_target", RENDER[::2])
    setread(s, "render_source.ma", [MA], "M", "render_source", RENDER[::2])
    setread(s, "vis_flags", [OBJ], "O", "vis_flags", VISF)
    s.body("vis_flags.ops", [OBJ, "O.vis_flags |= VIS_INHERIT_ID", "O.vis_flags |= VIS_HIDE"], "O.vis_flags")

    # ================= typed object: every value from the definition =================
    TYPED = OBJ.replace("new /obj(", "new /obj/appearance_typed(")
    s.body("typed", [TYPED], dump("O", DUMP))
    for n in DUMP:
        if n in ("icon", "overlays", "filters", "transform"):
            continue
        s.body("typed.initial", [TYPED], f"initial(O.{n})")

    # ================= filters =================
    build_filters(s)

    # ================= appearance copy semantics =================
    build_appearance(s)

    # ================= mutable_appearance =================
    build_ma(s)

    # ================= image() =================
    build_image(s)

    # ================= gaps found by review =================
    build_gaps(s)


# Documented parameters per filter type (BYOND "Filter effects" pages); OD adds "greyscale"
FILTERS = {
    "alpha": ["x", "y", "icon", "render_source", "flags"],
    "angular_blur": ["x", "y", "size", "offset"],
    "bloom": ["threshold", "size", "offset", "alpha"],
    "blur": ["size"],
    "color": ["color", "space"],
    "displace": ["x", "y", "size", "icon", "render_source", "flags"],
    "drop_shadow": ["x", "y", "size", "offset", "color"],
    "layer": ["x", "y", "icon", "render_source", "flags", "color", "transform", "blend_mode"],
    "motion_blur": ["x", "y"],
    "outline": ["size", "color", "flags"],
    "radial_blur": ["x", "y", "size", "offset"],
    "rays": ["x", "y", "size", "color", "offset", "density", "threshold", "factor", "flags"],
    "ripple": ["x", "y", "size", "repeat", "radius", "falloff", "flags"],
    "wave": ["x", "y", "size", "offset", "flags"],
}
# A non-default value for each parameter
PARAM_VAL = {
    "x": "3", "y": "-4", "size": "2.5", "offset": "1.5", "threshold": "0.25", "alpha": "100",
    "color": '"#ff0000"', "space": "FILTER_COLOR_HSV", "flags": "1", "icon": "'test.dmi'",
    "render_source": '"*src"', "transform": "matrix(2, 0, 0, 0, 2, 0)", "blend_mode": "BLEND_ADD",
    "density": "5", "factor": "0.5", "repeat": "4", "radius": "7", "falloff": "0.5",
}
# Odd values for a few parameters
PARAM_ODD = {
    "size": ["0", "-1", '"2"', "null", "NAN", "1e7", "list()"],
    "x": ["1.5", '"3"', "null", "-1e7"],
    "color": ['"red"', '"#f00"', '"#ff000080"', "list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "null", "5", '"bogus"'],
    "flags": ["3", "1.5", "-1", '"1"', "null"],
    "density": ["10.5", "0", "-3", '"7"'],
    "threshold": ["2", "-1", '"#808080"'],
    "icon": ["icon('test.dmi', \"solid\")", '"test.dmi"', "null", "5"],
    "transform": ["list(1, 2, 3, 4, 5, 6)", "null", "2"],
    "space": ["5", "-1", "null"],
}
FVAL = ["type", "name"]


def fget(name):
    """Colon access compiles everywhere, so undeclared names error at runtime only."""
    return f"F:{name}"


def build_filters(s):
    ABSTRACT = lambda t, extra="": f'var/F = filter(type = "{t}"{extra})'
    ATTACH = lambda t, extra="": [OBJ, f'O.filters = filter(type = "{t}"{extra})', "var/F = O.filters[1]"]
    types = list(FILTERS) + ["greyscale", "bogus", "BLUR", ""]
    for t in types:
        s.case("filter.make", f'filter(type = "{t}")')
        s.case("filter.make", f'appearance_kind(filter(type = "{t}"))')
        s.body("filter.attach", [OBJ, f'O.filters = filter(type = "{t}")'], "length(O.filters)")
    for t, params in FILTERS.items():
        # Defaults, abstract and attached, plus type/name and a name that is not a parameter
        for p in FVAL + params + (["bogus"] if t != "blur" else ["bogus", "x", "color"]):
            s.body("filter.default", [ABSTRACT(t)], fget(p))
            s.body("filter.default_attached", ATTACH(t), fget(p))
        # Every parameter set to a non-default value and read back, abstract and attached
        for p in params:
            extra = f", {p} = {PARAM_VAL[p]}"
            s.body("filter.param", [ABSTRACT(t, extra)], fget(p))
            s.body("filter.param_attached", ATTACH(t, extra), fget(p))
        # All parameters at once
        allx = "".join(f", {p} = {PARAM_VAL[p]}" for p in params)
        s.body("filter.all", [ABSTRACT(t, allx)], "list(" + ", ".join(fget(p) for p in FVAL + params) + ")")
    for p, vals in PARAM_ODD.items():
        t = {"size": "blur", "x": "drop_shadow", "color": "outline", "flags": "outline", "density": "rays",
             "threshold": "rays", "icon": "alpha", "transform": "layer", "space": "color"}[p]
        for v in vals:
            s.body("filter.odd", [ABSTRACT(t, f", {p} = {v}")], fget(p))
            s.body("filter.odd_attached", ATTACH(t, f", {p} = {v}"), fget(p))
    # Unknown parameters and argument forms
    s.case("filter.args", 'filter(type = "blur", bogus = 1)')
    s.case("filter.args", 'filter(type = "blur", x = 1)')
    s.case("filter.args", 'filter("blur")')
    s.case("filter.args", 'filter(size = 2)')
    s.case("filter.args", 'filter()')
    s.case("filter.args", 'filter(type = null)')
    s.case("filter.args", 'filter(type = 1)')
    s.case("filter.args", 'filter(type = list("blur"))')
    s.body("filter.args", ['var/F = filter(type = "blur", name = "n", size = 3)'], "list(F:type, F:name, F:size)")
    s.body("filter.args", ['var/F = filter(type = "blur", name = 5)'], "F:name")
    s.body("filter.args", ['var/F = filter(size = 3, type = "blur")'], "F:size")
    s.body("filter.args", ['var/dm_filter/F = filter(type = "blur")'], '"[F]"')
    s.body("filter.args", ['var/dm_filter/F = filter(type = "blur")'], "F.type")
    s.body("filter.args", ['var/dm_filter/F = filter(type = "blur")'], "istype(F, /dm_filter)")
    s.case("filter.args", 'filter(type = "blur") == filter(type = "blur")')
    s.body("filter.args", ['var/F = filter(type = "blur")'], "F == F")
    # Abstract stays separate from the attached copy
    s.body("filter.copy", [OBJ, 'var/dm_filter/F = filter(type = "blur", size = 1)', "O.filters += F", "F:size = 5"], "list(F:size, O.filters[1]:size)")
    s.body("filter.copy", [OBJ, 'var/dm_filter/F = filter(type = "blur", size = 1)', "O.filters += F"], "O.filters[1] == F")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "blur", size = 1)', "var/dm_filter/F = O.filters[1]", "F:size = 4"], "O.filters[1]:size")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "blur", size = 1)', "O.filters[1]:size = 6"], "O.filters[1]:size")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "blur", size = 1)'], "O.filters[1] == O.filters[1]")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "blur", size = 1)', 'O.filters[1]:color = "red"'], "O.filters[1]:color")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "outline", size = 1)', 'O.filters[1]:color = "red"'], "O.filters[1]:color")
    s.body("filter.copy", [OBJ, 'O.filters = filter(type = "blur", size = 1)', 'O.filters[1]:type = "outline"'], "O.filters[1]:type")
    # List forms and wrong types
    for v in ['filter(type = "blur")', 'list(filter(type = "blur"), filter(type = "outline"))', "null", "list()",
              'list(type = "blur", size = 3)', 'list("type" = "blur")', 'list(list(type = "blur"), list(type = "wave"))',
              'list(filter(type = "blur"), 5, "x", null)', 'list(filter(type = "bogus"))', "5", '"blur"', "new /datum",
              "list(1, 2)", 'list(type = "bogus")', 'list(filter(type = "blur"), filter(type = "blur"))']:
        s.body("filters.assign", [OBJ, f"O.filters = {v}"], "length(O.filters)")
        s.body("filters.assign", [OBJ, f"O.filters = {v}"], "O.filters")
    s.body("filters.assign", [OBJ, 'O.filters = list(type = "blur", size = 3)'], "O.filters[1]:size")
    s.body("filters.assign", [OBJ, 'O.filters = list(list(type = "wave", size = 3))'], "O.filters[1]:type")
    s.body("filters.assign", [OBJ, 'O.filters = filter(type = "blur")', "O.filters = null"], "length(O.filters)")
    s.body("filters.assign", [OBJ, 'O.filters = filter(type = "blur")', 'O.filters = filter(type = "wave")'], "list(length(O.filters), O.filters[1]:type)")
    # List operations on filters
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters += filter(type = "outline")'], "list(length(O.filters), O.filters[1]:type, O.filters[2]:type)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur", name = "a")', 'O.filters += filter(type = "outline", name = "a")'], "list(length(O.filters), O.filters[1]:type)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur", name = "a")', 'O.filters += filter(type = "outline", name = "b")'], 'list(O.filters["a"]:type, O.filters["b"]:type)')
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur", name = "a")'], 'O.filters["zz"]')
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur", name = "a")'], '("a" in O.filters)')
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', "O.filters -= O.filters[1]"], "length(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur", size = 2)', 'O.filters -= filter(type = "blur", size = 2)'], "length(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters += filter(type = "wave")', "O.filters.Cut(1, 2)"], "list(length(O.filters), O.filters[1]:type)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters[1] = filter(type = "wave")'], "O.filters[1]:type")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters += 5'], "length(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += list(filter(type = "blur"), filter(type = "wave"))'], "length(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', "var/list/L = O.filters", "L += filter(type = \"wave\")"], "length(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', "var/list/L = O.filters.Copy()", "L += filter(type = \"wave\")"], "list(length(O.filters), length(L))")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")'], "O.filters[2]")
    s.body("filters.ops", [OBJ], "O.filters.type")
    s.body("filters.ops", [OBJ], "islist(O.filters)")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")'], "O.filters.Find(O.filters[1])")
    s.body("filters.ops", [OBJ, 'O.filters += filter(type = "blur")', "O.filters.len = 0"], "length(O.filters)")
    # Images and mutable appearances
    for setup, t in [(IMG, "I"), (MA, "M")]:
        s.body("filters.other", [setup, f'{t}.filters = filter(type = "blur", size = 2)'], f"list(length({t}.filters), {t}.filters[1]:size)")
        s.body("filters.other", [setup, f'{t}.filters += filter(type = "blur")', f'{t}.filters += filter(type = "wave")'], f"length({t}.filters)")
        s.body("filters.other", [setup, f'{t}.filters = list(filter(type = "blur"), filter(type = "wave"))', f"{t}.filters = null"], f"length({t}.filters)")
        s.body("filters.other", [setup, f'{t}.filters = list(type = "blur")'], f"length({t}.filters)")
        s.body("filters.other", [setup], f"{t}.filters")


def build_appearance(s):
    SETUP_SRC = [OBJ.replace("new /obj(", "new /obj/appearance_typed("), OBJ2]
    # Assigning from many sources onto a plain obj, then dumping it
    for src in ["O", "O.appearance", "image('test.dmi', \"solid\")", "image(O)", "/obj/appearance_typed",
                "/obj", "'test.dmi'", "icon('test.dmi', \"solid\")", '"solid"', "null", "5", "list()",
                "new /datum", "new /mutable_appearance(O)", "new /mutable_appearance", "matrix()"]:
        s.body("appearance.assign", SETUP_SRC + [f"P.appearance = {src}"], dump("P", DUMP))
    # Documented: density, dir, screen_loc not copied from an atom/appearance; copied from an MA
    s.body("appearance.assign", SETUP_SRC + ["P.dir = WEST", "P.appearance = O"], "list(P.dir, P.density, P.screen_loc)")
    s.body("appearance.assign", SETUP_SRC + ["var/mutable_appearance/M = new(O)", "M.dir = NORTH", "M.density = 1", 'M.screen_loc = "5,5"', "P.appearance = M"], "list(P.dir, P.density, P.screen_loc)")
    s.body("appearance.assign", SETUP_SRC + ["var/mutable_appearance/M = new(O)", "P.appearance = M", 'M.name = "later"'], "P.name")
    s.body("appearance.assign", SETUP_SRC + ["P.appearance = O", 'O.name = "later"'], "P.name")
    # Overlays, filters, transform and color travel with the appearance
    s.body("appearance.assign", SETUP_SRC + ["O.overlays += 'test.dmi'", "O.underlays += 'small.dmi'", "P.appearance = O"], "list(length(P.overlays), length(P.underlays))")
    s.body("appearance.assign", SETUP_SRC + ['O.filters = filter(type = "blur", size = 3)', "P.appearance = O", "var/S = null", "if(length(P.filters))", "	var/F = P.filters[1]", "	S = F:size"], "list(length(P.filters), S)")
    s.body("appearance.assign", SETUP_SRC + ["O.transform = matrix(2, 0, 0, 0, 2, 0)", "P.appearance = O"], "P.transform")
    s.body("appearance.assign", SETUP_SRC + ["O.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "P.appearance = O"], "P.color")
    s.body("appearance.assign", SETUP_SRC + ["O.verbs += /proc/appearance_rd", "P.appearance = O"], "length(P.verbs)")
    s.body("appearance.assign", SETUP_SRC + ["P.appearance = O"], "P.appearance == O.appearance")
    # Reading appearance
    for setup in [[OBJ], SETUP_SRC]:
        s.body("appearance.read", setup, "appearance_kind(O.appearance)")
        s.body("appearance.read", setup, "O.appearance == O.appearance")
        s.body("appearance.read", setup, "O.appearance:name")
        s.body("appearance.read", setup, "O.appearance:icon_state")
        s.body("appearance.read", setup, "O.appearance:alpha")
        s.body("appearance.read", setup, "O.appearance:dir")
        s.body("appearance.read", setup, "O.appearance:density")
        s.body("appearance.read", setup, "O.appearance:type")
        s.body("appearance.read", setup, dump("O.appearance", DUMP))
    s.body("appearance.read", [OBJ, OBJ2], "O.appearance == P.appearance")
    s.body("appearance.read", [OBJ, OBJ2, 'P.name = "obj"'], "O.appearance == P.appearance")
    s.body("appearance.read", [OBJ, OBJ2, 'P.name = "other"'], "O.appearance == P.appearance")
    s.body("appearance.read", [OBJ, "var/A = O.appearance", 'O.name = "changed"'], "A:name")
    s.body("appearance.read", [OBJ, "var/A = O.appearance", 'A:name = "changed"'], "list(A:name, O.name)")
    s.body("appearance.read", [OBJ, IMG], "appearance_kind(I.appearance)")
    s.body("appearance.read", [MA], "appearance_kind(M.appearance)")
    s.body("appearance.read", [OBJ, IMG, "O.appearance = I.appearance"], "list(O.icon_state, O.layer)")
    s.body("appearance.read", [OBJ, 'O.overlays += "solid"'], "appearance_kind(O.overlays[1])")
    s.body("appearance.read", [OBJ, 'O.icon = \'test.dmi\'', 'O.overlays += "solid"'], dump("O.overlays[1]", DUMP_IMG))
    s.body("appearance.read", [OBJ, "O.overlays += image('test.dmi', \"grad\", layer = 9)"], dump("O.overlays[1]", DUMP_IMG))
    s.body("appearance.read", [OBJ, "O.overlays += /obj/appearance_typed"], dump("O.overlays[1]", DUMP_IMG))
    # Image appearance assign
    s.body("appearance.image", [OBJ.replace("new /obj(", "new /obj/appearance_typed("), IMG, "I.appearance = O"], dump("I", DUMP_IMG))
    s.body("appearance.image", [MA, 'M.icon_state = "grad"', "M.layer = 8", IMG, "I.appearance = M"], dump("I", DUMP_IMG))


def build_ma(s):
    TYPED = OBJ.replace("new /obj(", "new /obj/appearance_typed(")
    for src_setup, src in [([TYPED], "O"), ([OBJ], "O"), ([IMG], "I"), ([], "/obj/appearance_typed"),
                           ([], "'test.dmi'"), ([], "icon('test.dmi', \"solid\")"), ([], "null"),
                           ([], '"solid"'), ([], "5"), ([], "new /datum"), ([TYPED], "O.appearance"),
                           ([TYPED, "var/mutable_appearance/M0 = new(O)", 'M0.name = "m0"'], "M0"),
                           ([], "image('test.dmi', \"grad\", layer = 6)")]:
        s.body("ma.new", src_setup + [f"var/mutable_appearance/M = new /mutable_appearance({src})"], dump("M", MA_NAMES))
    s.body("ma.new", [MA], dump("M", MA_NAMES))
    s.body("ma.new", [MA], "appearance_kind(M)")
    s.body("ma.new", [MA], "M.type")
    s.body("ma.new", [MA], "M.loc")
    # Changes to the copy leave the source alone and vice versa
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", 'M.name = "q"', "M.alpha = 1"], "list(O.name, O.alpha, M.name, M.alpha)")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", 'O.name = "q"'], "M.name")
    s.body("ma.copy", [TYPED, "O.overlays += 'small.dmi'", "var/mutable_appearance/M = new(O)", "M.overlays += 'rect.dmi'"], "list(length(O.overlays), length(M.overlays))")
    s.body("ma.copy", [TYPED, "O.overlays += 'small.dmi'", "var/mutable_appearance/M = new(O)"], "M.overlays.type")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", "M.overlays += 'rect.dmi'", "O.appearance = M"], "length(O.overlays)")
    s.body("ma.copy", [TYPED, 'O.filters = filter(type = "blur", size = 2)', "var/mutable_appearance/M = new(O)", "var/S = null", "if(length(M.filters))", "	var/F = M.filters[1]", "	S = F:size"], "list(length(M.filters), S)")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", "M.transform = matrix(3, 0, 0, 0, 3, 0)", "O.appearance = M"], "O.transform")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", "M.color = list(0, 1, 0, 1, 0, 0, 0, 0, 1)", "O.appearance = M"], "O.color")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", "M.dir = WEST", "O.appearance = M"], "O.dir")
    s.body("ma.copy", [TYPED, "var/mutable_appearance/M = new(O)", "O.appearance = M"], "O.appearance == M")
    s.body("ma.copy", [OBJ, MA, 'M.icon = \'test.dmi\'', 'M.icon_state = "grad"', "O.overlays += M"], dump("O.overlays[1]", DUMP_IMG))
    s.body("ma.copy", [OBJ, MA, 'M.icon_state = "grad"', "O.overlays += M", 'M.icon_state = "solid"'], "O.overlays[1]:icon_state")


def build_image(s):
    T = OBJ  # an atom to use as loc
    forms = [
        "image()", "image('test.dmi')", "image('test.dmi', \"solid\")", "image('test.dmi', O)",
        "image('test.dmi', O, \"solid\")", "image('test.dmi', O, \"solid\", 7)",
        "image('test.dmi', O, \"solid\", 7, EAST)", "image('test.dmi', \"solid\", 7)",
        "image('test.dmi', \"solid\", 7, EAST)", "image('test.dmi', null, \"solid\")",
        "image('test.dmi', null, \"solid\", null, NORTH)", "image(\"solid\")", "image(\"solid\", O)",
        "image(\"solid\", \"grad\")", "image(\"solid\", O, \"grad\")", "image(icon('test.dmi'))",
        "image(icon('test.dmi', \"solid\"), \"grad\")", "image(O)", "image(O, O)", "image(O, \"grad\")",
        "image(/obj/appearance_typed)", "image(/obj/appearance_typed, \"grad\")",
        "image(/obj/appearance_typed, O, null, 2, WEST)", "image(image('test.dmi', \"grad\", layer = 6))",
        "image(new /mutable_appearance(O))", "image(O.appearance)", "image(5)", "image(list())",
        "image(new /datum)", "image(null, O)", "image(null, null, \"solid\")",
        "image(icon = 'test.dmi', icon_state = \"solid\")", "image(icon_state = \"solid\")",
        "image(layer = 7)", "image(dir = EAST)", "image('test.dmi', loc = O)", "image(loc = O)",
        "image('test.dmi', O, \"solid\", 7, EAST, 3, 4)", "image('test.dmi', pixel_x = 5)",
        "image('test.dmi', O, \"solid\", \"5\", \"4\")", "image('test.dmi', O, 5)",
        "image('test.dmi', O, \"solid\", -1, 0)", "image('test.dmi', O, \"solid\", FLOAT_LAYER, -1)",
        "image('test.dmi', O, \"solid\", 3.5, 2.5)", "image('test.dmi', O, \"solid\", null, 100)",
        "image('test.dmi', O, \"\")", "image('test.dmi', O, list())",
        "image('test.dmi', 5)", "image('test.dmi', new /datum)", "image('test.dmi', locate(1, 1, 1))",
        "image('test.dmi', locate(/area))",
        "new /image", "new /image('test.dmi', O, \"solid\", 7, EAST)", "new /image(\"solid\")",
        "new /image('test.dmi', \"solid\")", "new /image/appearance_img", "new /image/appearance_img('test.dmi')",
        "new /image/appearance_img('test.dmi', O, \"grad\", 3)", "new /image/appearance_img(\"grad\")",
    ]
    for f in forms:
        s.body("image.new", [T, f"var/image/I = {f}"], dump("I", DUMP_IMG))
    s.body("image.new", [T, "var/image/I = image('test.dmi', O)"], "I.loc == O")
    s.body("image.new", [T, "var/image/I = image('test.dmi', O)"], "(I in O.overlays)")
    s.body("image.new", [T, "var/image/I = image('test.dmi', O)"], "list(length(O.overlays), O.x, O.y, I.x, I.y, I.z)")
    s.body("image.new", [], "image('test.dmi').type")
    s.body("image.new", [], "istype(image('test.dmi'), /image)")
    s.body("image.new", [], "image('test.dmi') == image('test.dmi')")
    # Changing an image after it became an overlay does not change the overlay
    s.body("image.snapshot", [T, IMG, "O.overlays += I", 'I.icon_state = "grad"'], "O.overlays[1]:icon_state")
    s.body("image.snapshot", [T, IMG, "I.loc = O"], "list(I.loc == O, length(O.overlays))")
    s.body("image.snapshot", [T, IMG, 'I.loc = "x"'], "I.loc")
    s.body("image.snapshot", [T, IMG, "I.loc = 5"], "I.loc")
    s.body("image.snapshot", [T, IMG, "I.override = 1"], "I.override")
    s.body("image.snapshot", [T, IMG, "I.override = 5"], "I.override")
    s.body("image.snapshot", [T, IMG, 'I.override = "x"'], "I.override")


# ---------------- gaps a review found ----------------
GLIDE = ["0", "1.5", "0.25", "-1", "1e7", '"4"', "null", "NAN", "list()"]
ANIM = ["NO_STEPS", "FORWARD_STEPS", "SLIDE_STEPS", "SYNC_STEPS", "4", "-1", "1.5", '"2"', "null",
        "LONG_GLIDE | SLIDE_STEPS"]
# Color filter values: 9/12/16/20 matrices, row strings, names, alpha hex, null, too short
CF_COLOR = [
    "list(0, 1, 0, 1, 0, 0, 0, 0, 1)",
    "list(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.1, 0.2, 0.3)",
    "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5)",
    "list(0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 1, 0.1, 0.2, 0.3, 0)",
    'list("#ff0000", "#00ff00", "#0000ff")',
    '"red"', '"#ff000080"', "null", "list(1, 2, 3)",
]


def ctobj(t):
    return OBJ.replace("new /obj(", f"new /obj/{t}(")


def build_gaps(s):
    TYPED = ctobj("appearance_typed")

    # ---- glide_size / animate_movement ----
    setread(s, "glide_size", [OBJ], "O", "glide_size", GLIDE)
    setread(s, "glide_size.ma", [MA], "M", "glide_size", GLIDE)
    setread(s, "animate_movement", [OBJ], "O", "animate_movement", ANIM)
    setread(s, "animate_movement.ma", [MA], "M", "animate_movement", ANIM)
    for d in ["NO_STEPS", "FORWARD_STEPS", "SLIDE_STEPS", "SYNC_STEPS"]:
        s.case("defines", d)

    # ---- color stored first, alpha changed after (an RGB-only matrix takes alpha in) ----
    for c in ["list(0, 1, 0, 1, 0, 0, 0, 0, 1)",
              "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5)",
              "list(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0.5, 0, 0, 0, 0.1)",
              '"#ff000080"', '"#ff0000"']:
        s.body("color.alpha_after", [OBJ, f"O.color = {c}", "O.alpha = 50"], "list(O.color, O.alpha)")
    # rgb() in other colour spaces
    for c in ["rgb(0, 100, 50, space = COLORSPACE_HSL)", "rgb(120, 100, 100, space = COLORSPACE_HSV)",
              "rgb(120, 100, 100, 50, space = COLORSPACE_HSV)", "rgb(240, 50, 50, space = COLORSPACE_HCY)"]:
        s.body("color.rgb_space", [OBJ, f"O.color = {c}"], "list(O.color, O.alpha)")
        s.case("color.rgb_space", c)

    # ---- compile-time values (the definition's appearance) ----
    # BYOND's compiler rejects out-of-range invisibility = 200, alpha = 300, blend_mode = 99,
    # mouse_opacity = 5, plane = 1.5 and icon_state = 5 in a type definition (a whole-build error), so
    # those cannot be cases here
    for t, var in [("appearance_ct_color_matrix", "color"), ("appearance_ct_color_alpha", "color"),
                   ("appearance_ct_screen", "screen_loc"), ("appearance_ct_lum", "luminosity")]:
        s.body("compiletime", [ctobj(t)], f"O.{var}")
        s.body("compiletime.initial", [ctobj(t)], f"initial(O.{var})")
    s.body("compiletime", [ctobj("appearance_ct_color_alpha")], "list(O.color, O.alpha)")
    s.body("compiletime", [ctobj("appearance_ct_color_matrix")], "list(O.color, O.alpha)")
    s.body("compiletime", [ctobj("appearance_ct_transform")], "O.transform")
    s.body("compiletime", [ctobj("appearance_ct_filter")], "length(O.filters)")
    s.body("compiletime", [ctobj("appearance_ct_filter")], "O.filters[1]:size")
    s.body("compiletime", [ctobj("appearance_ct_filter")], "appearance_ftypes(O.filters)")
    s.body("compiletime", ["var/mutable_appearance/M = new /mutable_appearance(/obj/appearance_ct_color_matrix)"], "list(M.color, M.alpha)")
    s.body("compiletime", ["var/mutable_appearance/M = new /mutable_appearance(/obj/appearance_ct_transform)"], "M.transform")

    # ---- initial() of transform / icon / filters ----
    for t in ["appearance_typed", "appearance_ct_transform", "appearance_ct_filter"]:
        s.body("initial.special", [ctobj(t)], "initial(O.transform)")
        s.body("initial.special", [ctobj(t)], "appearance_icon_info(initial(O.icon))")
        s.body("initial.special", [ctobj(t)], "length(initial(O.filters))")
        s.body("initial.special", [ctobj(t), "O.transform = matrix(5, 0, 0, 0, 5, 0)"], "initial(O.transform)")

    # ---- color filter: colour forms and spaces ----
    for c in CF_COLOR:
        s.body("filter.color", [f'var/F = filter(type = "color", color = {c})'], "F:color")
        s.body("filter.color_attached", [OBJ, f'O.filters = filter(type = "color", color = {c})', "var/F = O.filters[1]"], "F:color")
    for sp in ["FILTER_COLOR_HSV", "FILTER_COLOR_HSL", "FILTER_COLOR_HCY", "FILTER_COLOR_RGB"]:
        x = f'filter(type = "color", color = list(0, 1, 0, 1, 0, 0, 0, 0, 1), space = {sp})'
        s.body("filter.color_space", [f"var/F = {x}"], "list(F:color, F:space)")
        s.body("filter.color_space_attached", [OBJ, f"O.filters = {x}", "var/F = O.filters[1]"], "list(F:color, F:space)")
    # rays (a matrix: only the diagonal is used), layer (colour or matrix), drop_shadow colour forms
    for t, c in [("rays", "list(2, 0, 0, 0, 2, 0, 0, 0, 2)"), ("layer", "list(0, 1, 0, 1, 0, 0, 0, 0, 1)"),
                 ("layer", '"#ff000080"'), ("drop_shadow", '"#f00"'), ("drop_shadow", '"#ff000080"'),
                 ("drop_shadow", '"red"'), ("drop_shadow", "list(0, 1, 0, 1, 0, 0, 0, 0, 1)")]:
        s.body("filter.color_forms", [f'var/F = filter(type = "{t}", color = {c})'], "F:color")
        s.body("filter.color_forms_attached", [OBJ, f'O.filters = filter(type = "{t}", color = {c})', "var/F = O.filters[1]"], "F:color")

    # ---- an attached filter shared between atoms ----
    s.body("filters.shared", [OBJ, OBJ2, 'O.filters += filter(type = "blur", size = 1)', "P.filters += O.filters[1]",
                              "O.filters[1]:size = 5"], "list(P.filters[1]:size, O.filters[1] == P.filters[1])")
    s.body("filters.shared", [OBJ, OBJ2, 'O.filters += filter(type = "blur", size = 1)', "P.filters = O.filters",
                              'O.filters += filter(type = "wave")'], "list(length(O.filters), length(P.filters))")
    s.body("filters.shared", [OBJ, OBJ2, 'O.filters += filter(type = "blur", size = 1)', "P.filters = O.filters",
                              "O.filters[1]:size = 7"], "list(P.filters[1]:size, O.filters == P.filters)")

    # ---- removal by name and list procs ----
    BLUR_A = 'O.filters += filter(type = "blur", name = "a")'
    s.body("filters.listprocs", [OBJ, BLUR_A, 'O.filters -= "a"'], "length(O.filters)")
    s.body("filters.listprocs", [OBJ, BLUR_A, 'O.filters.Remove(O.filters["a"])'], "length(O.filters)")
    s.body("filters.listprocs", [OBJ, BLUR_A, 'O.filters.Remove("a")'], "length(O.filters)")
    s.body("filters.listprocs", [OBJ, BLUR_A, 'O.filters["a"] = filter(type = "wave")'], "appearance_ftypes(O.filters)")
    s.body("filters.listprocs", [OBJ, 'O.filters["a"] = filter(type = "wave")'], "appearance_ftypes(O.filters)")
    s.body("filters.listprocs", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters.Insert(1, filter(type = "wave"))'], "appearance_ftypes(O.filters)")
    s.body("filters.listprocs", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters += filter(type = "wave")', "O.filters.Swap(1, 2)"], "appearance_ftypes(O.filters)")
    s.body("filters.listprocs", [OBJ, 'O.filters += filter(type = "blur")', 'O.filters.Add(filter(type = "wave"))'], "appearance_ftypes(O.filters)")

    # ---- filters and icon through vars[] ----
    s.body("filters.vars", [OBJ, 'O.vars["filters"] = filter(type = "blur", size = 2)'], "O.filters[1]:size")
    s.body("filters.vars", [OBJ, 'O.vars["filters"] = filter(type = "blur", size = 2)'], "length(O.filters)")
    s.body("filters.vars", [OBJ, 'O.vars["filters"] = list(filter(type = "blur"), filter(type = "wave"))'], "appearance_ftypes(O.filters)")
    s.body("icon.vars", [OBJ, "O.vars[\"icon\"] = 'test.dmi'"], "appearance_icon_info(O.icon)")
    s.body("icon.vars", [OBJ, "O.vars[\"icon\"] = icon('test.dmi', \"solid\")"], "appearance_icon_info(O.icon)")

    # ---- assigning M.appearance ----
    for setup, src in [([TYPED], "O"), ([], "image('test.dmi', \"grad\")"), ([], "null"), ([], "5"),
                       ([TYPED], "O.appearance"), ([], "/obj/appearance_typed")]:
        s.body("ma.appearance", setup + [MA, f"M.appearance = {src}"], dump("M", MA_NAMES))

    # ---- appearance / MA from an overlay entry or a turf ----
    OVL = [OBJ, "O.icon = 'test.dmi'", 'O.overlays += "grad"']
    s.body("appearance.overlay_src", OVL + [OBJ2, "P.appearance = O.overlays[1]"], dump("P", DUMP))
    s.body("ma.overlay_src", OVL + ["var/mutable_appearance/M = new /mutable_appearance(O.overlays[1])"], dump("M", MA_NAMES))
    s.body("ma.turf_src", ["var/mutable_appearance/M = new /mutable_appearance(locate(1, 1, 1))"], dump("M", MA_NAMES))
    s.body("appearance.turf_src", [OBJ, "O.appearance = locate(1, 1, 1)"], dump("O", DUMP))

    # ---- image() of an atom instance, with overrides ----
    s.body("image.instance", [OBJ, "var/image/I = image(parity_track(new /obj/appearance_typed(locate(1, 1, 1))), null, \"grad\", 2, WEST)"], dump("I", DUMP_IMG))
    s.body("image.instance", [OBJ, "var/image/I = image(parity_track(new /obj/appearance_typed(locate(1, 1, 1))))"], dump("I", DUMP_IMG))
    s.body("image.instance", [OBJ, "O.icon = 'test.dmi'", "O.overlays += 'small.dmi'", 'O.filters += filter(type = "blur")',
                              "var/image/I = image(O)"], "list(length(I.overlays), length(I.filters))")

    # ---- image() text icon with a named icon_state, mixed named args ----
    for f in ['image("solid", icon_state = "grad")', 'image("solid", O, icon_state = "grad")',
              "image('test.dmi', \"solid\", icon_state = \"grad\")", "image('test.dmi', O, layer = 5, dir = WEST)",
              "image('test.dmi', O, \"solid\", icon_state = \"grad\")"]:
        s.body("image.named", [OBJ, f"var/image/I = {f}"], dump("I", DUMP_IMG))

    # ---- which vars /image and /mutable_appearance have ----
    for n in ["density", "opacity", "invisibility", "luminosity", "mouse_opacity", "desc", "gender",
              "screen_loc", "suffix", "vis_flags", "glide_size", "animate_movement", "text", "icon_w"]:
        s.body("vars.exist", [IMG], f'("{n}" in I.vars)')
        s.body("vars.exist", [MA], f'("{n}" in M.vars)')
    for n in ["density", "invisibility", "vis_flags", "desc"]:
        s.body("vars.exist", [IMG], f'appearance_rd(I, "{n}")')
    s.body("vis_flags.area", ["var/area/A = locate(/area)"], "A:vis_flags")
    # Set and restore inside the case so the area is left as found
    s.body("vis_flags.area", ["var/area/A = locate(/area)", "var/r", "try", "\tA:vis_flags = VIS_HIDE",
                              "\tr = A:vis_flags", "catch(var/exception/e2)", '\tr = "ERR [e2.name]"',
                              "try", "\tA:vis_flags = 0", "catch(var/exception/e3)", "\tr += \" restore [e3.name]\""], "r")
    s.body("vis_flags.ma", [MA], "M:vis_flags")
    s.body("vis_flags.ma", [MA, "M:vis_flags = VIS_HIDE"], "M:vis_flags")

    # ---- image maptext_* / icon_w / icon_z / text ----
    setread(s, "maptext_width.image", [IMG], "I", "maptext_width", MAPNUM[::3])
    setread(s, "maptext_x.image", [IMG], "I", "maptext_x", MAPNUM[::3])
    setread(s, "icon_w.image", [IMG], "I", "icon_w", PIXEL_S)
    setread(s, "icon_z.image", [IMG], "I", "icon_z", PIXEL_S)
    setread(s, "text.image", [IMG], "I", "text", NAME_S)
    s.body("text.image", [IMG], "I.text")

    # ---- does transform keep a /matrix subtype? ----
    s.body("transform.subtype", [OBJ, "O.transform = new /matrix/appearance_sub(2, 0, 0, 0, 2, 0)"], "O.transform.type")
    s.body("transform.subtype", [OBJ, "O.transform = new /matrix/appearance_sub(2, 0, 0, 0, 2, 0)"], "istype(O.transform, /matrix/appearance_sub)")
    s.body("transform.subtype", [OBJ, "O.transform = new /matrix/appearance_sub(2, 0, 0, 0, 2, 0)"], "O.transform")
    s.body("transform.subtype", [MA, "M.transform = new /matrix/appearance_sub(2, 0, 0, 0, 2, 0)"], "M.transform.type")
