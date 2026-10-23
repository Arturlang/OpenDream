"""Default values of builtin vars on every builtin type, read four ways:
D.vars["name"] (every instance shape), D.name (typed access), initial(D.name), issaved(D.name),
plus the names in D.vars (in order), its length, and which documented names are missing/extra.

BYOND reference points targeted here (info.html "vars (...)" and "<type>/var/<name>" entries):
- atom: alpha 255, dir SOUTH, gender "neuter", layer 1 area / 2 turf / 3 obj / 4 mob, luminosity 1 for
  areas, density 1 for mobs, mouse_drop_pointer 1, mouse_opacity 1, maptext_width/height 32 (world
  icon_size), plane FLOAT_PLANE, name = type name with underscores turned to spaces, text = first letter
  of the name, overlays/underlays/filters/vis_contents/vis_locs empty lists, verbs = prototype verbs.
- movable: animate_movement FORWARD_STEPS, bound_width/height and step_size 32 (icon_size), locs =
  list(loc), pixloc null off-map, particles null; mob: see_in_dark 2, group empty list.
- sound: volume 100, falloff 1, environment -1, everything else 0/null; matrix: identity.
- world: view 5, icon_size 32, fps 10, tick_lag 1, cache_lifespan 30, visibility 1, hub null,
  area /area, turf /turf, mob /mob, name = the .dmb name, version 0, sleep_offline 0.
- issaved(): 1 unless the var is global, const or tmp. initial(): the compile-time value.

OpenDream declarations (DMStandard/Types/*.dm) that these cases aim at:
- /atom/movable layer stays 2 (TURF_LAYER) in OD; plane 0 (not FLOAT_PLANE) on atoms; text/name null
  in the declaration (derived at runtime); vis_flags/step_x/step_y declared on /atom and null;
  bound_*/step_size declared null (no icon_size default); mouse_drag/over_pointer null not 0.
- OD's /image has its own var set (glide_size, pixel_step_size, verbs, contents...) and invisibility null;
  name "image", text "i".
- OD /world: name "OpenDream World", hub/hub_password/host/executor/status "", visibility 0,
  maxx/maxy/maxz null-typed, loop_checks 0, byond_version from DM_VERSION.
- OD marks type/vars/parent_type/verbs/loc/x/y/z/ckey/group/bound_*/mouse_*_pointer tmp, which
  changes issaved().
Nondeterministic world vars (time, timeofday, realtime, cpu, tick_usage, map_cpu, address, port,
internet_address, url, system_type, timezone, host, reachable, process, log, contents) are not printed.
"""
from gen import dm_str

DATUM = ["type", "parent_type", "tag", "vars"]
ATOM = DATUM + [
    "alpha", "appearance", "appearance_flags", "blend_mode", "color", "contents", "density", "desc",
    "dir", "filters", "gender", "icon", "icon_state", "icon_w", "icon_z", "infra_luminosity",
    "invisibility", "layer", "loc", "luminosity", "maptext", "maptext_height", "maptext_width",
    "maptext_x", "maptext_y", "mouse_drag_pointer", "mouse_drop_pointer", "mouse_drop_zone",
    "mouse_opacity", "mouse_over_pointer", "name", "opacity", "overlays", "override", "pixel_w",
    "pixel_x", "pixel_y", "pixel_z", "pixloc", "plane", "render_source", "render_target", "suffix",
    "text", "transform", "underlays", "verbs", "vis_contents", "vis_flags", "vis_locs", "x", "y", "z",
]
MOVABLE = ATOM + [
    "animate_movement", "bound_height", "bound_width", "bound_x", "bound_y", "bounds", "glide_size",
    "locs", "particles", "pixel_step_size", "screen_loc", "step_size", "step_x", "step_y",
]
MOB = MOVABLE + ["ckey", "client", "group", "key", "see_in_dark", "see_infrared", "see_invisible", "sight"]
IMAGE = DATUM + [
    "alpha", "appearance", "appearance_flags", "blend_mode", "color", "icon", "icon_state", "icon_w",
    "icon_z", "text", "dir", "filters", "loc", "maptext", "maptext_width", "maptext_height",
    "maptext_x", "maptext_y", "overlays", "override", "pixel_x", "pixel_y", "pixel_w", "pixel_z",
    "plane", "render_source", "render_target", "transform", "underlays", "vis_contents", "x", "y", "z",
    # Not in BYOND's image list, but declared by OD's /image (or atom-like)
    "layer", "name", "desc", "density", "gender", "invisibility", "luminosity", "opacity", "suffix",
    "mouse_opacity", "mouse_over_pointer", "mouse_drag_pointer", "mouse_drop_pointer", "mouse_drop_zone",
    "infra_luminosity", "glide_size", "pixel_step_size", "verbs", "contents", "vis_flags",
]
MA = IMAGE + ["animate_movement", "screen_loc"]
ICON = DATUM + ["icon"]
MATRIX = DATUM + ["a", "b", "c", "d", "e", "f"]
REGEX = DATUM + ["flags", "group", "index", "match", "name", "next", "text"]
SOUND = DATUM + [
    "file", "repeat", "wait", "channel", "volume", "frequency", "pitch", "pan", "params", "falloff",
    "atom", "transform", "x", "y", "z", "environment", "echo", "len", "offset", "priority", "status",
]
EXCEPTION = DATUM + ["name", "desc", "file", "line"]
PARTICLES = DATUM + [
    "width", "height", "count", "spawning", "bound1", "bound2", "gravity", "gradient", "transform",
    "lifespan", "fade", "fadein", "icon", "icon_state", "color", "color_change", "position",
    "velocity", "scale", "grow", "rotation", "spin", "friction", "drift",
]
SAVEFILE = ["cd", "dir", "eof", "byond_version", "byond_build", "type", "tag", "vars"]

# Location-dependent vars, read on atoms with no loc / fresh areas
LOCSET = ["loc", "x", "y", "z", "locs", "pixloc", "contents", "name", "text", "layer", "luminosity", "density",
          "vis_locs", "bound_width", "step_size"]

# key -> (typed declaration path, setup lines defining D, var names, full = also typed/initial/issaved)
CTORS = [
    ("datum", "/datum", ["var/datum/D = new /datum"], DATUM, True),
    ("obj", "/obj", ["var/obj/D = parity_track(new /obj(locate(2, 3, 1)))"], MOVABLE, True),
    ("obj_null", "/obj", ["var/obj/D = parity_track(new /obj)"], LOCSET, False),
    ("mob", "/mob", ["var/mob/D = parity_track(new /mob(locate(2, 3, 1)))"], MOB, True),
    ("mob_null", "/mob", ["var/mob/D = parity_track(new /mob)"], LOCSET, False),
    ("movable", "/atom/movable", ["var/atom/movable/D = parity_track(new /atom/movable(locate(2, 3, 1)))"], MOVABLE, False),
    ("turf", "/turf", ["var/turf/D = locate(2, 3, 1)"], ATOM, True),
    ("area", "/area", ["var/area/D = locate(/area)"], ATOM, True),
    ("area_new", "/area", ["var/area/D = parity_track(new /area)"], LOCSET, False),
    ("image", "/image", ["var/image/D = new /image"], IMAGE, True),
    ("image_proc", "/image", ["var/image/D = image('test.dmi', \"solid\")"], IMAGE, False),
    ("ma", "/mutable_appearance", ["var/mutable_appearance/D = new /mutable_appearance"], MA, True),
    ("ma_obj", "/mutable_appearance", ["var/obj/defaults_over/O = parity_track(new /obj/defaults_over(locate(2, 3, 1)))",
                                       "var/mutable_appearance/D = new /mutable_appearance(O)"], MA, False),
    ("icon", "/icon", ["var/icon/D = new /icon('test.dmi')"], ICON, True),
    ("icon_empty", "/icon", ["var/icon/D = new /icon"], ICON, False),
    ("matrix", "/matrix", ["var/matrix/D = matrix()"], MATRIX, True),
    ("matrix_new", "/matrix", ["var/matrix/D = new /matrix"], MATRIX, False),
    ("regex", "/regex", ["var/regex/D = regex(\"b+\", \"gi\")"], REGEX, True),
    ("regex_new", "/regex", ["var/regex/D = new /regex"], REGEX, False),
    ("sound", "/sound", ["var/sound/D = new /sound"], SOUND, True),
    ("exception", "/exception", ["var/exception/D = new /exception"], EXCEPTION, True),
    ("exception_arg", "/exception", ["var/exception/D = new /exception(\"boom\")"], EXCEPTION, False),
    ("particles", "/particles", ["var/particles/D = new /particles"], PARTICLES, True),
    ("savefile", "/savefile", ["var/savefile/D = new /savefile"], SAVEFILE, True),
]

# Deterministic world vars
WORLD = ["area", "turf", "mob", "name", "tick_lag", "fps", "loop_checks", "maxx", "maxy", "maxz",
         "icon_size", "view", "movement_mode", "byond_version", "byond_build", "version", "visibility",
         "status", "params", "sleep_offline", "map_format", "cache_lifespan", "executor", "hub",
         "hub_password", "game_state", "type", "parent_type", "tag"]

HELPERS = r'''
/proc/defaults_names(list/L)
	if(!islist(L))
		return L
	var/list/R = list()
	for(var/k in L)
		R += k
	return R

// Documented names missing from L, then names in L that are not documented (in L's order)
/proc/defaults_diff(list/L, list/want)
	if(!islist(L))
		return L
	var/list/missing = list()
	var/list/extra = list()
	for(var/k in want)
		if(!(k in L))
			missing += k
	for(var/k in L)
		if(!(k in want))
			extra += k
	return list("missing" = missing, "extra" = extra)

// Lists as their length and contents; vars lists (which contain themselves) as their names
/proc/defaults_show(x)
	if(islist(x))
		var/list/L = x
		if(L.len > 40)
			return "len=[L.len]"
	return x

/obj/defaults_over
	name = "over thing"
	desc = "described"
	density = 1
	opacity = 1
	layer = 7
	dir = EAST
	icon = 'test.dmi'
	icon_state = "solid"
	alpha = 100
	color = "#ff0000"
	pixel_x = 3
	invisibility = 2
	luminosity = 3
	mouse_opacity = 2
	maptext = "hi"
	plane = 5

/obj/defaults_big_thing

/obj/defaults_a__b

/obj/defaults_named
	name = "Zed"

/obj/defaults_lower
	name = "zed"

/obj/defaults_empty_name
	name = ""

/obj/defaults_custom
	var/defaults_a = 1
	var/tmp/defaults_t = 2
	var/const/defaults_c = 3
	var/global/defaults_g = 4
	var/static/defaults_s = 5
	var/defaults_n
	var/list/defaults_l = list(1, 2)

/obj/defaults_custom/sub
	defaults_a = 10

/obj/defaults_verbed/verb/defaults_poke()
	set src in view()
	return 1

/mob/defaults_m

/turf/defaults_t

/area/defaults_area

/datum/defaults_dt
	var/defaults_x = 7

/datum/defaults_dt/sub
	defaults_x = 8

/defaults_root
	var/defaults_y = 9

/sound/defaults_snd
	volume = 50

/matrix/defaults_mx

/proc/defaults_fail()
	var/list/L = null
	return L[1]

var/global/defaults_gv = 3

/defaults_pt
	parent_type = /obj

/obj/defaults_verbed2/verb/defaults_v2()
	set name = "Poke"
	set category = "X"
	set desc = "pokes"
	return 1

// One field of this proc's own /callee, read while the proc is still running
/proc/defaults_cl(n, a, b)
	var/callee/D = callee
	switch(n)
		if("names")
			return defaults_names(D.vars)
		if("len")
			return length(D.vars)
		if("name")
			return D.name
		if("desc")
			return D.desc
		if("category")
			return D.category
		if("file")
			return D.file
		if("line")
			return D.line
		if("proc")
			return D.proc
		if("src")
			return D.src
		if("usr")
			return D.usr
		if("args")
			return D.args
		if("type")
			return D.type
		if("caller_proc")
			var/callee/C = D.caller
			return C.proc
		if("initial")
			return initial(D.line)
		if("issaved")
			return issaved(D.line)
	return "?"

// The same through caller: the frame that called defaults_cl2 is defaults_clr
/proc/defaults_clr(n)
	return defaults_cl2(n)

/proc/defaults_cl2(n)
	var/callee/D = caller
	switch(n)
		if("names")
			return defaults_names(D.vars)
		if("name")
			return D.name
		if("proc")
			return D.proc
		if("args")
			return D.args
		if("type")
			return D.type
		if("src")
			return D.src
		if("file")
			return D.file
		if("line")
			return D.line
	return "?"

// Walks to the top of the call chain: depth and the top frame's proc
/proc/defaults_top()
	var/n = 0
	var/callee/D = callee
	while(D.caller)
		D = D.caller
		n++
	return list(n, D.proc, isnull(D.caller))

/obj/defaults_named/proc/defaults_cl_src()
	var/callee/D = callee
	return list(D.src, D.proc, D.name)

/obj/defaults_named/proc/defaults_init()
	return list(initial(name), initial(layer), issaved(name), initial(src.text))

/proc/defaults_exc()
	return EXCEPTION("boom")

/proc/defaults_exc_line()
	var/exception/E = EXCEPTION("boom")
	var/callee/D = callee
	return E.line - D.line
'''


def val(expr, name):
    """Wrap var values that would print huge or recurse (vars, world contents)."""
    if name == "vars":
        return f"defaults_names({expr})"
    if name in ("contents", "verbs", "params"):
        return f"defaults_show({expr})"
    return expr


def build(s):
    s.dm(HELPERS)

    for key, path, setup, names, full in CTORS:
        p = f"{key}"
        # The whole vars list: names in order, count, documented diff
        s.body(f"{p}.names", setup, "defaults_names(D.vars)")
        s.body(f"{p}.names", setup, "length(D.vars)")
        doc = {"obj_null": MOVABLE, "mob_null": MOB, "area_new": ATOM}.get(key, names)
        s.body(f"{p}.names", setup, f"defaults_diff(D.vars, list({', '.join(dm_str(n) for n in doc)}))")
        s.body(f"{p}.names", setup, "islist(D.vars)")
        s.body(f"{p}.names", setup, '"bogus" in D.vars')
        s.body(f"{p}.names", setup, 'D.vars["bogus"]')
        s.body(f"{p}.names", setup, 'D.vars[1]')
        for n in names:
            s.body(f"{p}.vars", setup, val(f'D.vars["{n}"]', n))
            if full:
                s.body(f"{p}.var", setup, val(f"D.{n}", n))
                s.body(f"{p}.initial", setup, val(f"initial(D.{n})", n))
                s.body(f"{p}.issaved", setup, f"issaved(D.{n})")
        if full and key != "savefile":
            # Every name the engine reports, valued through the vars list in one go
            s.body(f"{p}.all", setup + ["var/list/R = list()",
                                        "for(var/k in D.vars)",
                                        '\tif(k != "vars" && k != "contents" && k != "verbs")',
                                        "\t\tR[k] = D.vars[k]"], "R")

    # ---------------- /world ----------------
    s.case("world.names", "defaults_names(world.vars)")
    s.case("world.names", "islist(world.vars)")
    s.case("world.names", f"defaults_diff(world.vars, list({', '.join(dm_str(n) for n in WORLD)}))")
    s.case("world.names", '"maxx" in world.vars')
    s.case("world.names", "islist(world.contents)")
    for n in WORLD:
        s.case("world.vars", val(f'world.vars["{n}"]', n))
        if n in ("type", "parent_type", "tag"):
            continue  # both compilers reject world.type/parent_type/tag as an expression
        s.case("world.var", val(f"world.{n}", n))
        s.case("world.initial", val(f"initial(world.{n})", n))
        s.case("world.issaved", f"issaved(world.{n})")
    for n in ["time", "realtime", "timeofday", "cpu", "tick_usage", "map_cpu", "port", "address",
              "internet_address", "url", "system_type", "timezone", "host", "reachable", "process", "log",
              "contents"]:
        # Only the kind of value, never the value itself. The network vars change kind while BYOND
        # resolves the address/hub after startup, so only their issaved() is recorded.
        if n not in ("internet_address", "reachable", "address", "url"):
            s.case("world.kind", f"list(isnull(world.{n}), isnum(world.{n}), istext(world.{n}), islist(world.{n}))")
        s.case("world.issaved", f"issaved(world.{n})")
    s.case("world.var", "world.system_type == MS_WINDOWS || world.system_type == UNIX")
    s.case("world.var", "world.maxx * world.maxy * world.maxz")

    # ---------------- /list ----------------
    for setup in (["var/list/D = list()"], ["var/list/D = list(1, 2, 3)"], ["var/list/D = new /list(4)"],
                  ['var/list/D = list("a" = 1)']):
        s.body("list.var", setup, "D.len")
        s.body("list.var", setup, "initial(D.len)")
        s.body("list.var", setup, "issaved(D.len)")
        s.body("list.var", setup, "D.type")
        s.body("list.var", setup, "D.vars")
    s.body("list.var", ["var/list/D = list(1, 2, 3)", "D.len = 1"], "list(D.len, initial(D.len), D)")

    # ---------------- vector ----------------
    for setup in (["var/vector/D = vector(1, 2)"], ["var/vector/D = vector(1, 2, 3)"]):
        for n in ["x", "y", "z", "len", "size", "type"]:
            s.body("vector.var", setup, f"D.{n}")
        s.body("vector.var", setup, "D.vars")

    # ---------------- names, text and derived defaults ----------------
    for t in ["/obj", "/mob", "/turf", "/area", "/atom/movable", "/obj/defaults_big_thing", "/obj/defaults_a__b",
              "/obj/defaults_named", "/obj/defaults_lower", "/obj/defaults_empty_name", "/obj/defaults_over",
              "/mob/defaults_m", "/turf/defaults_t", "/area/defaults_area", "/obj/defaults_custom/sub"]:
        if t.startswith("/turf"):
            setup = [f"var/turf/T = locate(4, 4, 1)", f"var/old = T.type",
                     f"var/atom/D = new {t}(T)"]
            # Put the default turf back after reading
            for n in ["name", "text", "layer", "density", "luminosity", "plane", "dir", "gender"]:
                s.body("derived", setup + [f"var/r = D.{n}", "new old(T)"], "r", f"{t}: {n}")
            continue
        if t.startswith("/area"):
            setup = [f"var/atom/D = parity_track(new {t})"]
        else:
            setup = [f"var/atom/D = parity_track(new {t}(locate(4, 4, 1)))"]
        if t in ("/obj", "/mob", "/area", "/atom/movable"):
            dnames = ["name", "text"]  # the rest is covered by the per-type sweeps
        elif t == "/obj/defaults_over":
            dnames = ["name", "text", "layer", "density", "luminosity", "plane", "dir", "gender",
                      "desc", "icon", "icon_state", "opacity", "alpha", "color", "invisibility", "mouse_opacity",
                      "maptext", "pixel_x"]
        else:
            dnames = ["name", "text", "layer", "density", "luminosity", "plane", "gender"]
        for n in dnames:
            s.body("derived", setup, f"D.{n}")
            s.body("derived", setup, f"initial(D.{n})")
            if n in ("name", "text"):
                s.body("derived", setup, f'D.vars["{n}"]')
        s.body("derived", setup, "list(D.x, D.y, D.z, D.loc)")
    s.body("derived", ["var/obj/D = parity_track(new /obj)", 'D.name = "Quux"'], "D.text")
    s.body("derived", ["var/obj/D = parity_track(new /obj)", 'D.name = "Quux"'], "initial(D.text)")
    s.body("derived", ["var/obj/D = parity_track(new /obj/defaults_named)"], "D.text")
    s.body("derived", ["var/image/D = image('test.dmi', \"solid\")"], "list(D.name, D.text)")
    s.body("derived", ["var/mutable_appearance/D = new"], "list(D.name, D.text)")

    # ---------------- initial() after changes ----------------
    for n, v in [("name", '"changed"'), ("dir", "NORTH"), ("layer", "9"), ("density", "1"), ("icon_state", '"x"'),
                 ("desc", '"d"'), ("alpha", "5"), ("pixel_x", "7"), ("tag", '"defaults_tag"'), ("luminosity", "2"),
                 ("color", '"#00ff00"'), ("invisibility", "5"), ("mouse_opacity", "0"), ("plane", "3"),
                 ("maptext_width", "64"), ("step_size", "8"), ("glide_size", "4"), ("animate_movement", "0"),
                 ("screen_loc", '"1,1"'), ("suffix", '"s"'), ("gender", "MALE")]:
        for t in ["/obj", "/obj/defaults_over"]:
            setup = [f"var/obj/D = parity_track(new {t}(locate(4, 4, 1)))", f"D.{n} = {v}"]
            s.body("initial.changed", setup, f"list(D.{n}, initial(D.{n}), D.vars[\"{n}\"])")
    s.body("initial.changed", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", "D.loc = locate(5, 5, 1)"],
           "list(D.x, initial(D.x), initial(D.loc))")
    s.body("initial.changed", ["var/mob/D = parity_track(new /mob(locate(4, 4, 1)))", "D.see_in_dark = 5", "D.sight = 4"],
           "list(initial(D.see_in_dark), initial(D.sight), D.see_in_dark)")
    s.body("initial.changed", ["var/datum/defaults_dt/sub/D = new", "D.defaults_x = 1"], "list(D.defaults_x, initial(D.defaults_x))")
    s.body("initial.changed", ["var/matrix/D = matrix()", "D.a = 5"], "list(D.a, initial(D.a))")
    s.body("initial.changed", ["var/sound/defaults_snd/D = new", "D.volume = 5"], "list(D.volume, initial(D.volume))")
    s.body("initial.changed", ["var/sound/D = new", "D.volume = 5"], "list(D.volume, initial(D.volume))")
    s.body("initial.changed", ["var/regex/D = regex(\"a\")", "D.Find(\"cat\")"], "list(D.index, initial(D.index), D.match, initial(D.match))")
    s.body("initial.changed", ["var/image/D = image('test.dmi', \"solid\")", "D.layer = 9"], "list(D.layer, initial(D.layer), initial(D.icon_state))")
    s.case("initial.changed", "initial(world.view)")

    # ---------------- user-declared vars: vars order, issaved, initial ----------------
    cust = ["var/obj/defaults_custom/D = parity_track(new /obj/defaults_custom/sub(locate(4, 4, 1)))"]
    s.body("custom", cust, "defaults_names(D.vars)")
    s.body("custom", cust, "length(D.vars)")
    for n in ["defaults_a", "defaults_t", "defaults_c", "defaults_g", "defaults_s", "defaults_n", "defaults_l"]:
        s.body("custom", cust, f'D.vars["{n}"]')
        s.body("custom", cust, f'"{n}" in D.vars')
        s.body("custom", cust, f"D.{n}")
        if n == "defaults_c":
            # OD folds the const and reports the error at its declaration (whole-build failure)
            s.body("custom", cust, f"initial(D:{n})")
            s.body("custom", cust, f"issaved(D:{n})")
            continue
        s.body("custom", cust, f"initial(D.{n})")
        s.body("custom", cust, f"issaved(D.{n})")
    s.body("custom", cust + ["D.defaults_l += 3"], "list(D.defaults_l, initial(D.defaults_l))")
    s.body("custom", ["var/datum/defaults_dt/sub/D = new"], "defaults_names(D.vars)")
    s.body("custom", ["var/defaults_root/D = new"], "defaults_names(D.vars)")
    s.body("custom", ["var/defaults_root/D = new"], "list(D.type, D.parent_type, initial(D.parent_type))")
    s.body("custom", ["var/defaults_root/D = new"], 'D.vars["parent_type"]')
    s.body("custom", ["var/mob/defaults_m/D = parity_track(new /mob/defaults_m)"], "list(D.type, D.parent_type)")
    s.body("custom", ["var/matrix/defaults_mx/D = new"], "list(D.type, D.parent_type, D.a, D.e)")
    s.body("custom", ["var/sound/defaults_snd/D = new"], "list(D.type, D.parent_type, D.volume, D.vars[\"volume\"])")

    # ---------------- writing through vars ----------------
    s.body("vars.write", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", 'D.vars["name"] = "renamed"'], "list(D.name, initial(D.name))")
    s.body("vars.write", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", 'D.vars["layer"] = 8'], "D.layer")
    s.body("vars.write", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", 'D.vars["bogus"] = 8'], 'D.vars["bogus"]')
    s.body("vars.write", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", 'D.vars["type"] = /mob'], "D.type")
    s.body("vars.write", ["var/matrix/D = matrix()", 'D.vars["c"] = 4'], "D")
    s.body("vars.write", ["var/datum/D = new", 'D.vars["tag"] = "defaults_t1"'], "D.tag")

    # ---------------- verbs, mob group, exception from a runtime error ----------------
    s.body("verbs", ["var/obj/D = parity_track(new /obj/defaults_verbed(locate(4, 4, 1)))"], "D.verbs")
    s.body("verbs", ["var/obj/D = parity_track(new /obj/defaults_verbed(locate(4, 4, 1)))"], "length(D.verbs)")
    s.body("verbs", ["var/obj/D = parity_track(new /obj/defaults_verbed(locate(4, 4, 1)))"], 'D.vars["verbs"]')
    s.body("verbs", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))"], "list(islist(D.verbs), length(D.verbs))")
    s.body("verbs", ["var/mob/D = parity_track(new /mob(locate(4, 4, 1)))"], "list(islist(D.group), length(D.group))")
    for n in ["name", "desc", "file", "type"]:
        s.body("exception.caught", ["var/r", "try", "\tdefaults_fail()", "catch(var/exception/E)", f"\tr = E.{n}"], "r")
    s.body("exception.caught", ["var/r", "try", "\tdefaults_fail()", "catch(var/exception/E)", "\tr = isnum(E.line)"], "r")
    s.body("exception.caught", ["var/r", "try", "\tdefaults_fail()", "catch(var/exception/E)", "\tr = defaults_names(E.vars)"], "r")

    # ---------------- savefile with a known name ----------------
    sf = ['fdel("defaults_save.sav")', 'var/savefile/D = new("defaults_save.sav")']
    for n in SAVEFILE + ["name"]:
        s.body("savefile.named", sf + [f"var/r = {val('D.' + n, n)}", "del D", 'fdel("defaults_save.sav")'], "r",
               f"savefile named: {n}")

    build_more(s)


FILTERS = {
    "blur": ["size"],
    "outline": ["size", "color", "flags"],
    "drop_shadow": ["x", "y", "size", "offset", "color"],
    "wave": ["x", "y", "size", "offset", "flags"],
    "ripple": ["x", "y", "size", "repeat", "radius", "falloff", "flags"],
    "displace": ["x", "y", "size", "icon", "render_source", "flags"],
    "color": ["color", "space"],
    "alpha": ["x", "y", "icon", "render_source", "flags"],
    "layer": ["x", "y", "icon", "render_source", "flags", "color", "transform", "blend_mode"],
    "bloom": ["threshold", "size", "offset", "alpha"],
    "rays": ["x", "y", "size", "color", "offset", "density", "threshold", "factor", "flags"],
    "angular_blur": ["x", "y", "size", "offset"],
    "radial_blur": ["x", "y", "size", "offset"],
    "motion_blur": ["x", "y"],
}

CLIENT = ["dir", "perspective", "show_popup_menus", "show_verb_panel", "preload_rsc", "fps", "tick_lag",
          "color", "default_verb_category", "view", "lazy_eye", "edge_limit", "pixel_x", "pixel_y", "pixel_w",
          "pixel_z", "byond_version", "glide_size", "bound_width", "bound_height", "bound_x", "gender",
          "inactivity", "computer_id", "control_freak", "mouse_pointer_icon", "statpanel", "script",
          "authenticate", "type", "tag", "virtual_eye", "eye", "mob", "key", "ckey"]


def build_more(s):
    # ---------------- /client through the scope operator (no client needed) ----------------
    for n in CLIENT:
        s.case("client.scope", f"/client::{n}")

    # ---------------- A::B as an initial-value form ----------------
    for e in ["/obj::layer", "/mob::density", "/mob::layer", "/area::layer", "/area::luminosity", "/turf::layer",
              "/obj::name", "/obj::text", "/obj::dir", "/obj::plane", "/obj::alpha", "/obj::gender",
              "/obj::maptext_width", "/obj::bound_width", "/obj::step_size", "/mob::see_in_dark",
              "/obj/defaults_over::alpha", "/obj/defaults_over::name", "/obj/defaults_over::layer",
              "/obj/defaults_named::text", "/obj/defaults_big_thing::name",
              "/sound::volume", "/sound::environment", "/sound::falloff", "/sound/defaults_snd::volume",
              "/matrix::a", "/matrix::e", "/image::layer", "/image::plane", "/mutable_appearance::plane",
              "/mutable_appearance::layer", "/obj/defaults_custom/sub::defaults_a", "/obj/defaults_custom::defaults_a",
              "/obj/defaults_custom::defaults_c", "/obj/defaults_custom::defaults_l", "/datum/defaults_dt/sub::defaults_x",
              "/exception::name", "/regex::index", "/datum::type", "/obj::type", "/obj::parent_type",
              "/defaults_root::defaults_y", "/defaults_pt::layer", "/defaults_pt::name"]:
        s.case("scope.type", e)
    obj9 = ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))", "D.layer = 9"]
    s.body("scope.inst", obj9, "D::layer")
    s.body("scope.inst", obj9, "list(D.layer, D::layer, initial(D.layer))")
    s.body("scope.inst", ["var/obj/defaults_over/D = parity_track(new /obj/defaults_over(locate(4, 4, 1)))", "D.alpha = 1"],
           "list(D.alpha, D::alpha, D::name)")
    s.body("scope.inst", ["var/obj/D = parity_track(new /obj/defaults_over(locate(4, 4, 1)))"], "D::alpha")
    s.body("scope.inst", ["var/sound/D = new", "D.volume = 5"], "D::volume")
    s.body("scope.inst", ["var/obj/defaults_custom/sub/D = parity_track(new /obj/defaults_custom/sub(locate(4, 4, 1)))",
                          "D.defaults_a = 99"], "list(D.defaults_a, D::defaults_a)")

    # ---------------- /pixloc ----------------
    for setup in (["var/pixloc/D = pixloc(33, 65, 1)"], ["var/pixloc/D = pixloc(1, 1, 1)"],
                  ["var/pixloc/D = pixloc(40, 50, 1)"]):
        for n in ["loc", "step_x", "step_y", "x", "y", "z"]:
            s.body("pixloc.var", setup, f"D.{n}")
            s.body("pixloc.vars", setup, f'D.vars["{n}"]')
        s.body("pixloc.names", setup, "defaults_names(D.vars)")
        s.body("pixloc.names", setup, "length(D.vars)")
        s.body("pixloc.var", setup, "D")
        s.body("pixloc.var", setup, "D.type")
        s.body("pixloc.initial", setup, "initial(D.x)")
        s.body("pixloc.initial", setup, "initial(D.loc)")
        s.body("pixloc.issaved", setup, "issaved(D.x)")
        s.body("pixloc.issaved", setup, "issaved(D.loc)")
    po = ["var/obj/D = parity_track(new /obj(locate(2, 3, 1)))"]
    s.body("pixloc.atom", po, "D.pixloc")
    s.body("pixloc.atom", po, 'D.vars["pixloc"]')
    s.body("pixloc.atom", po, "initial(D.pixloc)")
    s.body("pixloc.atom", po, "issaved(D.pixloc)")
    s.body("pixloc.atom", ["var/turf/D = locate(2, 3, 1)"], "D.pixloc")
    s.body("pixloc.atom", ["var/mob/D = parity_track(new /mob(locate(5, 1, 1)))"], "D.pixloc")

    # ---------------- /callee ----------------
    for n in ["names", "len", "name", "desc", "category", "file", "line", "proc", "src", "usr", "args", "type",
              "caller_proc", "initial", "issaved"]:
        s.case("callee", f'defaults_cl("{n}", 1, "a")')
    for n in ["names", "name", "proc", "args", "type", "src", "file", "line"]:
        s.case("callee.caller", f'defaults_clr("{n}")')
    s.case("callee.top", "defaults_top()")
    s.body("callee.src", ["var/obj/defaults_named/O = parity_track(new /obj/defaults_named(locate(4, 4, 1)))"],
           "O.defaults_cl_src()")
    s.case("callee.kw", "callee.type")
    s.case("callee.kw", "istype(callee, /callee)")
    s.case("callee.kw", "istype(caller, /callee)")

    # ---------------- /dm_filter defaults ----------------
    for ft, fields in FILTERS.items():
        setup = [f'var/dm_filter/D = filter(type="{ft}")']
        s.body("filter.names", setup, "defaults_names(D.vars)")
        s.body("filter.names", setup, "length(D.vars)")
        s.body("filter.var", setup, "D.type")
        s.body("filter.var", setup, 'D:vars["type"]')
        for f in fields:
            s.body("filter.var", setup, f"D:{f}")
    s.body("filter.var", ['var/obj/O = parity_track(new /obj(locate(4, 4, 1)))', 'O.filters += filter(type="blur")'],
           "list(length(O.filters), O.filters[1]:size)")
    s.body("filter.var", ['var/dm_filter/D = filter(type="blur", size = 3)'], "D:size")
    s.body("filter.var", ['var/dm_filter/D = filter(type="outline", color = "red")'], "D:color")

    # ---------------- /generator, /database, /database/query ----------------
    for key, setup in [("generator", ['var/generator/D = generator("num", 0, 1)']),
                       ("database", ["var/database/D = new"]),
                       ("query", ['var/database/query/D = new("SELECT 1")'])]:
        s.body(f"{key}.names", setup, "defaults_names(D.vars)")
        s.body(f"{key}.names", setup, "length(D.vars)")
        s.body(f"{key}.names", setup, "D.type")
        s.body(f"{key}.names", setup, '"_binobj" in D.vars')

    # ---------------- /alist, /file ----------------
    for setup in (["var/alist/D = alist()"], ['var/alist/D = alist("a" = 1)']):
        s.body("alist.var", setup, "D.len")
        s.body("alist.var", setup, "D.type")
        s.body("alist.var", setup, "initial(D.len)")
        s.body("alist.var", setup, "issaved(D.len)")
        s.body("alist.var", setup, "D.vars")
    fsetup = ['var/F = file("test.dmi")']
    s.body("file.var", fsetup, "F:vars")
    s.body("file.var", fsetup, "F:name")
    s.body("file.var", fsetup, "F:hash")
    s.body("file.var", fsetup, "F:type")
    s.body("file.var", fsetup, "istype(F, /datum)")

    # ---------------- global.vars ----------------
    s.case("global.vars", '"defaults_gv" in global.vars')
    s.case("global.vars", 'global.vars["defaults_gv"]')
    s.case("global.vars", "islist(global.vars)")
    s.case("global.vars", "initial(global.defaults_gv)")
    s.case("global.vars", "issaved(global.defaults_gv)")
    s.case("global.vars", '"PINF" in global.vars')
    s.case("global.vars", 'global.vars["bogus"]')
    s.body("global.vars", ["global.defaults_gv = 4", "var/r = list(global.defaults_gv, initial(global.defaults_gv))",
                           "global.defaults_gv = 3"], "r")

    # ---------------- vars order with overridden builtins ----------------
    from_movable = ", ".join(f'"{n}"' for n in MOVABLE)
    ov = ["var/obj/defaults_over/D = parity_track(new /obj/defaults_over(locate(2, 3, 1)))"]
    s.body("over.names", ov, "defaults_names(D.vars)")
    s.body("over.names", ov, "length(D.vars)")
    s.body("over.names", ov, f"defaults_diff(D.vars, list({from_movable}))")
    s.body("over.names", ov, 'D.vars.Find("name")')
    s.body("over.names", ov, 'D.vars.Find("layer")')
    s.body("over.names", ov, 'D.vars.Find("type")')
    s.body("over.names", ["var/obj/D = parity_track(new /obj(locate(2, 3, 1)))"], 'D.vars.Find("name")')
    s.body("over.names", ["var/obj/D = parity_track(new /obj(locate(2, 3, 1)))"], 'D.vars.Find("layer")')
    s.body("over.names", ["var/obj/D = parity_track(new /obj(locate(2, 3, 1)))"], 'D.vars.Find("type")')

    # ---------------- parent_type reparenting onto /obj ----------------
    pt = ["var/defaults_pt/D = parity_track(new /defaults_pt(locate(4, 4, 1)))"]
    for e in ["D.type", "D.parent_type", "initial(D.parent_type)", "defaults_names(D.vars)", "length(D.vars)",
              "D.layer", "D.name", "D.text", "istype(D, /obj)", "isobj(D)", "ismovable(D)", "D.loc", 'D.vars["name"]']:
        s.body("parent_type", pt, e)

    # ---------------- initial()/issaved() through : and implicit src ----------------
    un = ["var/D = parity_track(new /obj/defaults_over(locate(4, 4, 1)))"]
    for e in ["initial(D:layer)", "initial(D:name)", "issaved(D:loc)", "issaved(D:name)", "initial(D:text)"]:
        s.body("initial.forms", un, e)
    s.body("initial.forms", ["var/obj/defaults_named/O = parity_track(new /obj/defaults_named(locate(4, 4, 1)))",
                             'O.name = "x"', "O.layer = 8"], "O.defaults_init()")
    s.body("initial.forms", ["var/obj/D = parity_track(new /obj(locate(4, 4, 1)))"], 'initial(D.vars["name"])')

    # ---------------- /image from an atom or a loc ----------------
    oo = ["var/obj/defaults_over/O = parity_track(new /obj/defaults_over(locate(2, 3, 1)))"]
    for ctor in ["image(O)", "new /image(O)"]:
        for n in ["name", "layer", "icon_state", "color", "alpha", "dir", "plane", "loc", "icon"]:
            s.body("image.atom", oo + [f"var/image/D = {ctor}"], f"D.{n}")
    for ctor in ["image('test.dmi', locate(2, 3, 1))", "image('test.dmi', O)"]:
        for e in ["D.loc", "D.x", "D.y", "D.z", 'D.vars["loc"]', "D.layer", "D.icon_state"]:
            s.body("image.loc", oo + [f"var/image/D = {ctor}"], e)
    pos = ["var/image/D = image('test.dmi', null, \"solid\", 5, EAST)"]
    for e in ["D.layer", "D.dir", "D.icon_state", "D.loc"]:
        s.body("image.pos", pos, e)

    # ---------------- /exception arguments and EXCEPTION ----------------
    ex3 = ['var/exception/D = new /exception("boom", "f.dm", 7)']
    for n in ["name", "desc", "file", "line"]:
        s.body("exception.args", ex3, f"D.{n}")
        s.body("exception.macro", ["var/exception/D = defaults_exc()"], f"D.{n}")
    s.case("exception.macro", "defaults_exc_line()")
    s.body("exception.throw", ["var/r", "try", '\tthrow "txt"', "catch(var/E)", "\tr = list(E, istext(E), istype(E, /exception))"], "r")
    s.body("exception.throw", ["var/r", "try", "\tthrow new /datum", "catch(var/E)", "\tr = list(E, istype(E, /exception))"], "r")
    s.body("exception.throw", ["var/r", "try", "\tthrow 5", "catch(var/E)", "\tr = list(E, isnum(E))"], "r")
    s.body("exception.throw", ["var/r", "try", "\tthrow null", "catch(var/E)", "\tr = list(E, isnull(E))"], "r")

    # ---------------- proc and verb reference vars ----------------
    for t in ["/obj/defaults_verbed", "/obj/defaults_verbed2"]:
        vb = [f"var/obj/D = parity_track(new {t}(locate(4, 4, 1)))", "var/V = D.verbs[1]"]
        for n in ["name", "desc", "category", "invisibility", "type"]:
            s.body("procref", vb, f"V:{n}")
        s.body("procref", vb, "V")
    pp = ["var/P = /proc/defaults_fail"]
    for n in ["name", "desc", "category", "type"]:
        s.body("procref", pp, f"P:{n}")

    # ---------------- mutable_appearance from an image or an appearance ----------------
    for key, setup in [("ma_image", ["var/mutable_appearance/D = new /mutable_appearance(image('test.dmi', \"solid\"))"]),
                       ("ma_app", oo + ["var/mutable_appearance/D = new /mutable_appearance(O.appearance)"])]:
        for n in ["layer", "plane", "icon_state", "name", "screen_loc", "icon", "alpha", "color", "dir"]:
            s.body(key, setup, f"D.{n}")
        s.body(key, setup, 'D.vars["appearance"]')
        s.body(key, setup, 'D.vars["vis_contents"]')
        s.body(key, setup, "D.type")

    # ---------------- /vector and /list initial/issaved/vars ----------------
    for setup in (["var/vector/D = vector(1, 2)"], ["var/vector/D = vector(1, 2, 3)"]):
        for e in ["initial(D.x)", "issaved(D.x)", 'D.vars["x"]', "defaults_names(D.vars)", "initial(D.len)"]:
            s.body("vector.more", setup, e)
    for setup in (["var/list/D = list()"], ["var/list/D = list(1, 2, 3)"]):
        s.body("list.more", setup, 'D.vars["len"]')
        s.body("list.more", setup, "defaults_names(D.vars)")
