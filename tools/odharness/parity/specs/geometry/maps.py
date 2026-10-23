"""Map geometry builtins: locate(x,y,z), block, get_step, get_step_away/towards/to, get_steps_to,
get_dist, get_dir, turn(dir), view/range/orange/oview, viewers/hearers/oviewers/ohearers, bounds,
obounds, bounds_dist, and world/area/turf contents.

The map is 20x20x2, all /turf in one /area. Every case builds its own scene from maps_* helpers
(objects go through parity_track and are deleted afterwards). Lists of atoms print through
maps_desc() ("len:item item ...", turfs as x,y,z, movables as name@x,y,z, the area as A) so the
order is visible; maps_sdesc() prints the same items sorted (set comparison independent of order);
maps_sig() prints length, first, last and an md5 of the ordered items for large lists.

BYOND reference points targeted:
- get_dist is the max of the x/y/z distances, -1 for the same object, infinite off the map.
- get_dir returns the nearest diagonal when not along an axis; across z levels.
- turn(Dir, Angle): counterclockwise; non-multiples of 45 round toward 0; an invalid Dir gives a
  random direction unless Angle is 0 (so invalid dirs are only tried with Angle 0).
- block(Start, End) and block(x1,y1,z1, x2=x1,y2=y1,z2=z1) with null End values defaulting.
- get_step_to returns null when within Min or farther than 2*world.view; get_step_away returns 0
  when Ref is farther than Max; both path around obstacles (dense Ref vs dense walls).
- view/range: Dist 0 includes Center, its contents, its loc and the loc's contents; "WxH" text sizes;
  arguments in either order; o* forms exclude Center and its contents. Opaque objs block view.
- bounds(Ref, Dist) / bounds(Ref, x, y, w, h) / bounds(x, y, w, h, z); obounds excludes Ref;
  bounds_dist: gap in pixels, 0 touching, negative overlapping.

OpenDream divergences these cases aim at:
- get_dist in _Standard.dm is round(sqrt(dx^2+dy^2)) (Euclidean, ignores z, 127 off-map).
- get_step_away/get_step_towards are DM wrappers ignoring obstacles and Max.
- get_step_to pathfinds with maxSteps from world.view; bounds/obounds are range/orange wrappers
  ignoring pixels; bounds_dist reads origin's bound_height for the target and ignores step_x.
- turn truncates angle/45; view/oview spirals ignore rectangle shapes ("TODO: Make rectangles
  work"); ViewRange(string) throws on bad text; range includes no area; viewers/hearers re-resolve
  the range per mob.
- block() returns an empty list when any coordinate is outside the map instead of clamping.
- locate(x,y,z) casts to int (truncation) with UnsafePopAsFloat.
"""

HELPERS = r'''/obj/maps_thing
	name = "thing"

/obj/maps_wall
	name = "wall"
	density = 1

/obj/maps_opaque
	name = "opaque"
	opacity = 1

/obj/maps_dense
	name = "dense"
	density = 1

/mob/maps_mob
	name = "mob"

/proc/maps_obj(x, y, z, n = "o", T = /obj/maps_thing)
	var/atom/movable/O = new T(locate(x, y, z))
	O.name = n
	parity_track(O)
	return O

/proc/maps_in(atom/movable/outer, n = "inner", T = /obj/maps_thing)
	var/atom/movable/O = new T(outer)
	O.name = n
	parity_track(O)
	return O

/proc/maps_inobj(x, y, z)
	return maps_in(maps_obj(x, y, z, "outer"))

/proc/maps_tc(x, y, z)
	var/turf/T = locate(x, y, z)
	return T.contents

/proc/maps_mob(x, y, z, n = "m")
	return maps_obj(x, y, z, n, /mob/maps_mob)

/proc/maps_walls(x1, y1, x2, y2, z = 1)
	for(var/x in x1 to x2)
		for(var/y in y1 to y2)
			maps_obj(x, y, z, "w[x]_[y]", /obj/maps_wall)

/proc/maps_d1(x)
	if(isnull(x))
		return "null"
	if(isarea(x))
		return "A"
	if(isturf(x))
		var/turf/T = x
		return "[T.x],[T.y],[T.z]"
	if(ismovable(x))
		var/atom/movable/M = x
		return "[M.name]@[M.x],[M.y],[M.z]"
	if(isnum(x))
		return "[x]"
	if(istext(x))
		return "\"[x]\""
	return "?"

/proc/maps_parts(list/L)
	var/list/parts = list()
	for(var/x in L)
		parts += maps_d1(x)
	return parts

/proc/maps_desc(L)
	if(!islist(L))
		return parity_canon(L)
	return "[length(L)]:[jointext(maps_parts(L), " ")]"

/proc/maps_sdesc(L)
	if(!islist(L))
		return parity_canon(L)
	var/list/P = maps_parts(L)
	for(var/i in 2 to P.len)
		var/j = i
		while(j > 1 && sorttextEx(P[j - 1], P[j]) < 0)
			P.Swap(j - 1, j)
			j--
	return "[length(L)]:[jointext(P, " ")]"

/proc/maps_sig(L)
	if(!islist(L))
		return parity_canon(L)
	var/list/P = maps_parts(L)
	if(!P.len)
		return "0"
	return "[P.len] first=[P[1]] last=[P[P.len]] md5=[copytext(md5(jointext(P, " ")), 1, 9)]"

// Counts of each kind in a list of atoms
/proc/maps_kinds(list/L)
	if(!islist(L))
		return parity_canon(L)
	var/a = 0
	var/t = 0
	var/o = 0
	var/m = 0
	var/other = 0
	for(var/x in L)
		if(isarea(x))
			a++
		else if(isturf(x))
			t++
		else if(isobj(x))
			o++
		else if(ismob(x))
			m++
		else
			other++
	return "len=[length(L)] area=[a] turf=[t] obj=[o] mob=[m] other=[other]"

// ---- view scenes; each returns the center ----
/proc/maps_scene_fill(cx, cy, cz)
	maps_obj(cx, cy, cz, "same")
	if(cx < world.maxx)
		maps_obj(cx + 1, cy, cz, "e1")
	if(cy < world.maxy)
		maps_obj(cx, cy + 1, cz, "n1")
	if(cx > 2 && cy > 2)
		maps_obj(cx - 2, cy - 2, cz, "sw2")
	if(cx + 2 <= world.maxx && cy + 2 <= world.maxy)
		maps_obj(cx + 2, cy + 2, cz, "ne2")
	if(cx > 3)
		maps_obj(cx - 3, cy, cz, "w3")
	if(cy + 4 <= world.maxy)
		maps_obj(cx, cy + 4, cz, "n4")
	if(cx + 1 <= world.maxx && cy > 1)
		maps_obj(cx + 1, cy - 1, cz, "se1")

/proc/maps_scene_open()
	var/obj/C = maps_obj(10, 10, 1, "ctr")
	maps_in(C, "inner")
	maps_scene_fill(10, 10, 1)
	maps_obj(15, 15, 1, "far")
	maps_obj(10, 10, 2, "z2")
	return C

/proc/maps_scene_turf()
	maps_scene_open()
	return locate(10, 10, 1)

/proc/maps_scene_corner()
	var/obj/C = maps_obj(1, 1, 1, "ctr")
	maps_in(C, "inner")
	maps_scene_fill(1, 1, 1)
	return C

/proc/maps_scene_top()
	var/obj/C = maps_obj(20, 20, 2, "ctr")
	maps_in(C, "inner")
	maps_obj(20, 20, 2, "same")
	maps_obj(19, 20, 2, "w1")
	maps_obj(20, 19, 2, "s1")
	maps_obj(18, 18, 2, "sw2")
	maps_obj(20, 20, 1, "z1")
	return C

/proc/maps_scene_inner()
	var/obj/C = maps_scene_open()
	return locate(/obj) in C

/proc/maps_scene_mobc()
	var/mob/C = maps_mob(10, 10, 1, "mctr")
	maps_in(C, "inner")
	maps_scene_fill(10, 10, 1)
	return C

/proc/maps_scene_opaque()
	var/obj/C = maps_obj(10, 10, 1, "ctr")
	maps_obj(11, 10, 1, "op1", /obj/maps_opaque)
	maps_obj(12, 10, 1, "b1")
	maps_obj(13, 10, 1, "b2")
	maps_obj(13, 11, 1, "b3")
	maps_obj(10, 12, 1, "op2", /obj/maps_opaque)
	maps_obj(10, 13, 1, "b4")
	maps_obj(10, 14, 1, "b5")
	maps_obj(8, 8, 1, "op3", /obj/maps_opaque)
	maps_obj(7, 7, 1, "b6")
	maps_obj(9, 11, 1, "v1")
	maps_obj(11, 11, 1, "v2")
	return C

/proc/maps_scene_ring()
	var/obj/C = maps_obj(10, 10, 1, "ctr")
	for(var/dx in -1 to 1)
		for(var/dy in -1 to 1)
			if(dx || dy)
				maps_obj(10 + dx, 10 + dy, 1, "r[dx + 1][dy + 1]", /obj/maps_opaque)
	maps_obj(12, 10, 1, "out1")
	maps_obj(10, 8, 1, "out2")
	return C

/proc/maps_scene_mobs()
	var/obj/C = maps_obj(10, 10, 1, "ctr")
	maps_mob(10, 10, 1, "m0")
	maps_mob(11, 10, 1, "m1")
	maps_mob(8, 10, 1, "m2")
	maps_mob(10, 13, 1, "m3")
	maps_mob(10, 7, 1, "mx")
	maps_mob(16, 10, 1, "m6")
	maps_mob(10, 10, 2, "mz")
	maps_obj(12, 10, 1, "op", /obj/maps_opaque)
	maps_mob(13, 10, 1, "mb")
	maps_mob(9, 9, 1, "md")
	maps_in(C, "inner")
	return C

/proc/maps_scene_mobs_m()
	maps_scene_mobs()
	return locate(/mob) in locate(10, 10, 1)

/proc/maps_scene_mobs_t()
	maps_scene_mobs()
	return locate(10, 10, 1)

// Number of each kind of atom in the world
/proc/maps_world()
	var/a = 0
	var/t = 0
	var/o = 0
	var/m = 0
	for(var/area/A in world)
		a++
	for(var/turf/T in world)
		t++
	for(var/obj/O in world)
		o++
	for(var/mob/M in world)
		m++
	return "contents=[length(world.contents)] area=[a] turf=[t] obj=[o] mob=[m]"
'''

# ---- pools ----
LX = ["0", "1", "20", "21", "-1", "1.5", "1.9", "0.5", "20.9", '"1"', "null", "NAN"]
LZ = ["0", "1", "2", "3", "1.5", "2.9", "-1", "null", '"1"', "NAN"]

BX = ["1", "3", "0", "21", "null", "2.5"]
BZ = ["1", "2", "0", "3", "null"]

DIRS = ["0", "NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST",
        "UP", "DOWN", "3", "12", "15", "48", "NORTH|UP", "SOUTHWEST|DOWN", "-1", "1.5",
        '"1"', "null", "NAN"]
STEP_REFS = ["locate(10, 10, 1)", 'maps_obj(10, 10, 1, "o")', "locate(1, 1, 1)", "locate(20, 20, 2)",
             "locate(20, 1, 1)", "maps_inobj(5, 5, 1)", "null", "locate(/area)", '"text"',
             'maps_obj(1, 20, 2, "o")']

# Positions relative to (10, 10, 1) for get_step_towards/away
TRG = ["locate(13, 10, 1)", "locate(10, 15, 1)", "locate(7, 10, 1)", "locate(10, 6, 1)", "locate(12, 12, 1)",
       "locate(6, 14, 1)", "locate(13, 11, 1)", "locate(11, 16, 1)", "locate(10, 10, 1)", "locate(10, 10, 2)",
       "locate(12, 11, 2)", "null", "locate(/area)", 'maps_obj(14, 7, 1, "t")', "maps_inobj(8, 12, 1)", '"text"']
MOV_REFS = ['maps_obj(10, 10, 1, "a")', "locate(10, 10, 1)", 'maps_obj(1, 1, 1, "a")', "maps_inobj(10, 10, 1)",
            "null"]

GD = ["locate(10, 10, 1)", "locate(11, 10, 1)", "locate(13, 14, 1)", "locate(4, 9, 1)",
      "locate(20, 20, 1)", "locate(12, 15, 2)", 'maps_obj(10, 10, 1, "o")',
      "maps_inobj(13, 10, 1)", "null", "locate(/area)", '"text"']

GRID = [-7, -3, -2, -1, 0, 1, 2, 3, 7]

VALID_DIRS = ["NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST"]
ANGLES = ["0", "45", "90", "135", "180", "225", "270", "315", "360", "405", "720", "-45", "-90", "-135",
          "-180", "-270", "-360", "1", "44", "46", "89", "91", "-1", "-44", "-46",
          "22.5", "67.5", "1e7", "null"]
ANGLES_X = ["NAN", "PINF", "NINF", '"90"', "list()", "0.5", "-0.5", "45.5", "-1e7"]
BAD_DIRS = ["0", "UP", "DOWN", "3", "12", "15", "17", "NORTH|UP", "1.5", "-1", "null", '"1"', "255", "1e7", "NAN"]

VIEW = ["view", "range", "orange", "oview"]
VDIST = ["0", "1", "2", '"3x3"', '"5x3"', '"3x5"', '"1x1"', '"4x4"', '"2x6"', '"0x0"', "-1", "1.5", "null"]
VDIST_ORDER = ["0", "1", '"5x3"', '"2x6"']
VDIST_S = ["0", "1", "2", '"3x5"', '"4x4"', "-1", "null"]
VCENTERS = ["maps_scene_open()", "maps_scene_turf()", "maps_scene_corner()", "maps_scene_top()",
            "maps_scene_inner()", "maps_scene_mobc()", "maps_scene_opaque()", "maps_scene_ring()"]
VBIG = ["5", "7", '"11x11"', '"21x21"', '"15x5"', "25"]
VBAD = ['"abc"', '"3x"', '"x3"', '" 3x3"', '"3X3"', '"3x3x3"', '"-3x3"', '"3.5x3"', '"3"', '""', "list()",
        "new /datum", "/obj"]

VIEWERS = ["viewers", "hearers", "oviewers", "ohearers"]
WDIST = ["0", "1", "2", "3", "5", "null", '"3x3"', '"7x3"', "-1"]
WCENTERS = ["maps_scene_mobs()", "maps_scene_mobs_m()", "maps_scene_mobs_t()"]


def build(s):
    s.define("PARITY_MAXX", 20)
    s.define("PARITY_MAXY", 20)
    s.define("PARITY_MAXZ", 2)
    s.dm(HELPERS)

    # Scene sanity: what each scene holds (makes the rest readable)
    for c in VCENTERS + WCENTERS:
        s.case("scene", f"list(maps_d1({c}), maps_world())")

    # ================= locate(x, y, z) =================
    s.sweep("locate", [LX, LX, LZ], fmt=lambda x, y, z: f"locate({x}, {y}, {z})")
    for x, y, z in [(1, 1, 1), (20, 20, 2), (20, 1, 2), (1, 20, 1), (10, 10, 2), (21, 1, 1), (1, 21, 1),
                    (1, 1, 3), (0, 0, 0), (-5, -5, 1), (1, 1, -1)]:
        s.case("locate", f"locate({x}, {y}, {z})")
    for other in ["new /datum", "/obj", '"abc"', "list(1)", "NINF", "1e7", "-0.5", "0.99", "-0.99"]:
        s.case("locate", f"locate({other}, 2, 1)")
        s.case("locate", f"locate(2, {other}, 1)")
        s.case("locate", f"locate(2, 2, {other})")
    s.case("locate", "locate(1, 1)")
    s.case("locate", "locate(1, 1, 1, 1)")
    s.case("locate", "locate(vector(2, 3, 1))")
    s.body("locate", ["var/x = 3", "var/y = 4"], "locate(x, y, x - 2)")
    s.body("locate", ["var/list/L = list(5, 6, 2)"], "locate(L[1], L[2], L[3])")
    # Other forms
    s.case("locate", "locate(/turf)")
    s.case("locate", "locate(/area)")
    s.case("locate", "locate(/obj/maps_thing)")
    s.body("locate", ['maps_obj(4, 4, 1, "x")'], "locate(/obj/maps_thing)")
    s.body("locate", ['maps_obj(4, 4, 1, "x")', 'maps_obj(3, 3, 1, "y")'], "locate(/obj/maps_thing) in locate(3, 3, 1)")
    s.body("locate", ['maps_obj(4, 4, 1, "x")'], "locate(/obj/maps_thing) in locate(3, 3, 1)")
    s.body("locate", ['var/obj/O = maps_obj(4, 4, 1, "x")', 'O.tag = "maps_tag1"'], 'locate("maps_tag1")')
    s.body("locate", ['var/obj/O = maps_obj(4, 4, 1, "x")', 'O.tag = "maps_tag2"', 'O.tag = null'], 'locate("maps_tag2")')
    s.body("locate", ['var/obj/O = maps_inobj(4, 4, 1)'], "locate(/obj/maps_thing) in O.loc")
    s.body("locate", ['var/turf/T = locate(7, 8, 2)'], "locate(T.x, T.y, T.z) == T")

    # ================= block =================
    tb = [
        ("locate(1, 1, 1)", "locate(3, 3, 1)"), ("locate(3, 3, 1)", "locate(1, 1, 1)"),
        ("locate(3, 1, 1)", "locate(1, 3, 1)"), ("locate(1, 3, 1)", "locate(3, 1, 1)"),
        ("locate(5, 5, 1)", "locate(5, 5, 1)"), ("locate(1, 1, 1)", "locate(2, 2, 2)"),
        ("locate(2, 2, 2)", "locate(1, 1, 1)"), ("locate(19, 19, 2)", "locate(20, 20, 2)"),
        ("locate(1, 1, 1)", "locate(1, 4, 1)"), ("locate(1, 1, 1)", "locate(4, 1, 1)"),
        ("locate(1, 1, 1)", "null"), ("null", "locate(2, 2, 1)"), ("locate(1, 1, 1)", '"x"'),
        ('"a"', '"b"'), ("locate(2, 2, 1)", "2"), ("2", "locate(2, 2, 1)"),
        ('maps_obj(2, 2, 1, "o")', "locate(3, 3, 1)"), ("locate(1, 1, 1)", 'maps_obj(2, 3, 1, "o")'),
        ("locate(/area)", "locate(2, 2, 1)"), ("list()", "list()"),
    ]
    for a, b in tb:
        s.case("block", f"maps_desc(block({a}, {b}))")
    s.case("block", "maps_sig(block(locate(1, 1, 1), locate(20, 20, 2)))")
    s.case("block", "maps_sig(block(locate(20, 20, 2), locate(1, 1, 1)))")
    s.case("block", "maps_sig(block(locate(1, 1, 1), locate(20, 20, 1)))")
    s.case("block", "maps_desc(block(locate(1, 1, 1)))")
    s.case("block", "maps_desc(block())")
    # Coordinate form: full printing for small ones
    for args in ["1, 1, 1", "1, 1, 1, 3", "1, 1, 1, 3, 2", "1, 1, 1, null, 3", "1, 1, 1, 2, 2, 2", "2, 2, 1, 1, 1, 1",
                 "3, 1, 1, 1, 3, 1", "1, 3, 1, 3, 1, 1", "1, 1, 2, 2, 2, 1", "19, 19, 1, 25, 25, 1", "0, 0, 1, 2, 2, 1",
                 "-1, -1, 1, 1, 1, 1", "1, 1, 0, 1, 1, 1", "1, 1, 1, 1, 1, 3", "1, 1, 3, 1, 1, 3", "21, 21, 1",
                 "1.5, 1.5, 1, 2.5, 2.5, 1", "1.9, 1, 1, 2.9, 1, 1", "null, null, null", "null, null, null, 2, 2, 1",
                 '"1", "1", "1", "2", "2", "1"', "1, 1, 1, null, null, 2", "2, 2", "2", "20, 20, 2, 19, 19, 1",
                 "1, 1, 1, 0, 0, 0", "5, 5, 1, NAN, 6, 1", "5, 5, 1, PINF, 5, 1", "5, 5, 1, 7, 5, -1",
                 "locate(1, 1, 1), 2, 2", "1, 1, 1, locate(2, 2, 1)"]:
        s.case("block", f"maps_desc(block({args}))")
    s.sweep("block", [BX, BX, BZ, BX, BX, BZ], min_args=3, fmt=lambda *a: f"maps_sig(block({', '.join(a)}))")
    s.body("block", ["var/list/L = block(1, 1, 1, 2, 2, 1)", "L += 5"], "maps_desc(L)")
    s.body("block", ["var/list/A = block(1, 1, 1, 2, 2, 1)", "var/list/B = block(1, 1, 1, 2, 2, 1)"], "list(A == B, A ~= B)")

    # ================= get_step =================
    s.sweep("get_step", [STEP_REFS, DIRS], fmt=lambda r, d: f"get_step({r}, {d})")
    s.case("get_step", "get_step(locate(10, 10, 1))")
    s.case("get_step", "get_step()")
    s.case("get_step", "get_step(locate(10, 10, 1), NORTH, 1)")
    s.body("get_step", ['var/obj/O = maps_obj(10, 10, 1, "o")', "O.step_x = 20", "O.step_y = -20"], "get_step(O, NORTH)")
    s.body("get_step", ['var/obj/O = maps_obj(10, 10, 1, "o")', "O.dir = EAST"], "get_step(O, O.dir)")
    s.body("get_step", ['var/obj/O = maps_obj(10, 10, 1, "o")', "var/turf/T = get_step(O, NORTH)"], "list(O.loc, T)")
    s.body("get_step", ['var/obj/O = maps_obj(10, 10, 1, "o")', "del O"], "get_step(O, NORTH)")
    s.body("get_step", ['var/obj/O = new /obj/maps_thing', "parity_track(O)"], "get_step(O, NORTH)")
    s.body("get_step", ['var/obj/O = maps_obj(10, 10, 1, "o")', 'maps_obj(10, 11, 1, "w", /obj/maps_wall)'], "get_step(O, NORTH)")
    s.case("get_step", "get_step(new /datum, NORTH)")
    s.case("get_step", "get_step(list(), NORTH)")
    s.case("get_step", "get_step(/turf, NORTH)")

    # ================= get_step_towards / get_step_away =================
    s.sweep("get_step_towards", [MOV_REFS, TRG], fmt=lambda r, t: f"get_step_towards({r}, {t})")
    s.sweep("get_step_away", [MOV_REFS, TRG], fmt=lambda r, t: f"get_step_away({r}, {t})")
    # Max: target distance 3 and 1
    for mx in ["0", "1", "2", "3", "4", "5", "10", "-1", "null", "1.5", "2.5", "3.5", '"9"', "PINF"]:
        s.case("get_step_away", f'get_step_away(maps_obj(10, 10, 1, "a"), locate(13, 10, 1), {mx})')
        s.case("get_step_away", f'get_step_away(maps_obj(10, 10, 1, "a"), locate(11, 11, 1), {mx})')
        s.case("get_step_away", f'get_step_away(maps_obj(10, 10, 1, "a"), locate(10, 10, 1), {mx})')
    s.case("get_step_away", 'get_step_away(maps_obj(10, 10, 1, "a"), locate(16, 10, 1))')
    s.case("get_step_away", 'get_step_away(maps_obj(10, 10, 1, "a"), locate(15, 10, 1))')
    s.case("get_step_away", 'get_step_away(maps_obj(10, 10, 1, "a"), locate(15, 13, 1))')
    s.case("get_step_away", 'get_step_away(maps_obj(1, 1, 1, "a"), locate(2, 2, 1))')
    s.case("get_step_away", 'get_step_away(maps_obj(1, 5, 1, "a"), locate(2, 5, 1))')
    s.case("get_step_away", 'get_step_away(maps_obj(20, 20, 1, "a"), locate(19, 20, 1))')
    s.case("get_step_towards", 'get_step_towards(maps_obj(1, 1, 1, "a"), locate(20, 20, 1))')
    s.case("get_step_towards", 'get_step_towards(maps_obj(10, 10, 1, "a"), locate(11, 19, 1))')
    s.case("get_step_towards", 'get_step_towards(maps_obj(10, 10, 1, "a"), locate(19, 11, 1))')
    s.case("get_step_towards", 'get_step_towards(maps_obj(10, 10, 1, "a"))')
    s.case("get_step_away", 'get_step_away(maps_obj(10, 10, 1, "a"))')

    # Obstacles: Ref plain (not dense) or dense, walls in the way
    for rt in ["/obj/maps_thing", "/obj/maps_dense"]:
        A = f'var/obj/A = maps_obj(10, 10, 1, "a", {rt})'
        tag = "dense" if "dense" in rt else "plain"
        scenes = {
            "free": [],
            "wall1": ["maps_walls(11, 10, 11, 10)"],
            "wall3": ["maps_walls(11, 9, 11, 11)"],
            "wall5": ["maps_walls(11, 8, 11, 12)"],
            "cup": ["maps_walls(11, 9, 11, 11)", "maps_walls(10, 11, 10, 11)", "maps_walls(10, 9, 10, 9)"],
            "boxed": ["maps_walls(9, 9, 11, 9)", "maps_walls(9, 11, 11, 11)", "maps_walls(9, 10, 9, 10)", "maps_walls(11, 10, 11, 10)"],
            "column": ["maps_walls(12, 1, 12, 20)"],
            "diag": ["maps_walls(11, 11, 11, 11)"],
            "behind": ["maps_walls(9, 10, 9, 10)"],
            "behind3": ["maps_walls(9, 9, 9, 11)"],
        }
        for name, lines in scenes.items():
            for trg in ["locate(14, 10, 1)", "locate(14, 14, 1)", "locate(13, 11, 1)"]:
                s.body("get_step_to", [A] + lines, f"get_step_to(A, {trg})")
                s.body("get_steps_to", [A] + lines, f"get_steps_to(A, {trg})")
                s.body("get_step_towards", [A] + lines, f"get_step_towards(A, {trg})")
            for trg in ["locate(7, 10, 1)", "locate(8, 8, 1)"]:
                s.body("get_step_away", [A] + lines, f"get_step_away(A, {trg})")
                s.body("get_step_away", [A] + lines, f"get_step_away(A, {trg}, 2)")
            # Ref stays put; the walls' presence is recorded with the result
            s.body("get_step_to", [A] + lines, "list(get_step_to(A, locate(14, 10, 1), 0), A.loc)")
    # Min and distance limits (world.view = 5, so 2*view = 10)
    for mn in ["0", "1", "2", "3", "4", "5", "-1", "null", "1.5", "3.5", '"2"', "PINF"]:
        s.case("get_step_to", f'get_step_to(maps_obj(10, 10, 1, "a"), locate(14, 10, 1), {mn})')
        s.case("get_steps_to", f'get_steps_to(maps_obj(10, 10, 1, "a"), locate(14, 12, 1), {mn})')
    for tx, ty in [(19, 10), (20, 10), (20, 20), (15, 16), (10, 10), (11, 11)]:
        s.case("get_step_to", f'get_step_to(maps_obj(10, 10, 1, "a"), locate({tx}, {ty}, 1))')
        s.case("get_steps_to", f'get_steps_to(maps_obj(10, 10, 1, "a"), locate({tx}, {ty}, 1))')
    for tx in [11, 12, 15, 21]:
        s.case("get_step_to", f'get_step_to(maps_obj(1, 1, 1, "a"), locate({tx if tx <= 20 else 20}, 1, 1))')
    s.case("get_step_to", 'get_step_to(maps_obj(1, 1, 1, "a"), locate(11, 11, 1))')
    s.case("get_step_to", 'get_step_to(maps_obj(1, 1, 1, "a"), locate(12, 1, 1))')
    s.case("get_steps_to", 'get_steps_to(maps_obj(1, 1, 1, "a"), locate(11, 1, 1))')
    s.case("get_steps_to", 'get_steps_to(maps_obj(1, 1, 1, "a"), locate(12, 1, 1))')
    # Wrong kinds of Ref/Trg, different z, target inside something, target a dense wall
    for r, t in [('maps_obj(10, 10, 1, "a")', "locate(10, 10, 2)"), ('maps_obj(10, 10, 1, "a")', "null"),
                 ("null", "locate(12, 10, 1)"), ("locate(10, 10, 1)", "locate(12, 10, 1)"),
                 ('maps_obj(10, 10, 1, "a")', "maps_inobj(12, 10, 1)"), ("maps_inobj(10, 10, 1)", "locate(12, 10, 1)"),
                 ('maps_obj(10, 10, 1, "a")', 'maps_obj(13, 10, 1, "w", /obj/maps_wall)'),
                 ('maps_obj(10, 10, 1, "a", /obj/maps_dense)', 'maps_obj(13, 10, 1, "w", /obj/maps_wall)'),
                 ('maps_obj(10, 10, 1, "a")', "locate(/area)"), ('maps_obj(10, 10, 1, "a")', '"text"'),
                 ('maps_obj(10, 10, 1, "a")', 'maps_obj(10, 10, 1, "b")'), ('maps_mob(10, 10, 1, "m")', "locate(13, 13, 1)")]:
        s.case("get_step_to", f"get_step_to({r}, {t})")
        s.case("get_steps_to", f"get_steps_to({r}, {t})")
    s.case("get_step_to", 'get_step_to(maps_obj(10, 10, 1, "a"))')

    # ================= get_dist =================
    s.sweep("get_dist", [GD, GD], fmt=lambda a, b: f"get_dist({a}, {b})")
    s.body("get_dist", ["var/turf/T = locate(3, 3, 1)"], "get_dist(T, T)")
    s.body("get_dist", ['var/obj/O = maps_obj(3, 3, 1, "o")'], "get_dist(O, O)")
    s.body("get_dist", ['var/obj/O = maps_obj(3, 3, 1, "o")'], "get_dist(O, O.loc)")
    s.body("get_dist", ['var/obj/O = maps_inobj(3, 3, 1)'], "get_dist(O, O.loc)")
    s.body("get_dist", ['var/obj/O = maps_inobj(3, 3, 1)'], "get_dist(O, locate(3, 3, 1))")
    s.body("get_dist", ['var/obj/O = maps_inobj(3, 3, 1)'], "get_dist(O, locate(5, 3, 1))")
    s.body("get_dist", ['var/area/A = locate(/area)'], "get_dist(A, A)")
    s.case("get_dist", "get_dist(null, null)")
    s.case("get_dist", "get_dist(locate(1, 1, 1))")
    for (a, b) in [((1, 1, 1), (20, 20, 1)), ((1, 1, 1), (20, 20, 2)), ((1, 1, 1), (1, 1, 2)), ((5, 5, 1), (8, 9, 1)),
                   ((5, 5, 1), (9, 8, 1)), ((5, 5, 1), (6, 6, 2)), ((5, 5, 1), (5, 5, 2)), ((1, 1, 1), (17, 1, 1)),
                   ((3, 4, 1), (6, 8, 1)), ((5, 5, 2), (5, 5, 1)), ((2, 2, 1), (3, 12, 1))]:
        s.case("get_dist", f"get_dist(locate({a[0]}, {a[1]}, {a[2]}), locate({b[0]}, {b[1]}, {b[2]}))")
    s.body("get_dist", ['var/obj/O = maps_obj(5, 5, 1, "o")', "O.step_x = 31", "O.step_y = 31"], "get_dist(O, locate(6, 6, 1))")
    s.body("get_dist", ['var/obj/O = maps_obj(5, 5, 1, "o")', "O.bound_width = 96"], "get_dist(O, locate(7, 5, 1))")

    # ================= get_dir =================
    for dx in GRID:
        for dy in GRID:
            s.case("get_dir", f"get_dir(locate(10, 10, 1), locate({10 + dx}, {10 + dy}, 1))")
    for dx, dy in [(0, 0), (1, 0), (0, 1), (-1, -1), (2, 1), (5, -1)]:
        s.case("get_dir", f"get_dir(locate(10, 10, 1), locate({10 + dx}, {10 + dy}, 2))")
        s.case("get_dir", f"get_dir(locate(10, 10, 2), locate({10 + dx}, {10 + dy}, 1))")
    for dx, dy in [(1, 5), (5, 1), (1, 9), (-1, 9), (9, -1), (2, 5), (1, 2), (3, 7), (-8, 1), (6, 5)]:
        s.case("get_dir", f"get_dir(locate(10, 10, 1), locate({10 + dx}, {10 + dy}, 1))")
    GDIR = ["locate(10, 10, 1)", 'maps_obj(10, 10, 1, "o")', "maps_inobj(12, 10, 1)", "null", "locate(/area)",
            '"text"', "5", "locate(12, 12, 1)", "locate(10, 10, 2)", 'maps_obj(9, 12, 1, "o")']
    s.sweep("get_dir", [GDIR, GDIR], fmt=lambda a, b: f"get_dir({a}, {b})")
    s.body("get_dir", ['var/obj/O = maps_obj(5, 5, 1, "o")', "O.step_x = 20"], "get_dir(O, locate(5, 6, 1))")
    s.body("get_dir", ['var/obj/O = maps_obj(5, 5, 1, "o")', "O.step_x = 20", 'var/obj/P = maps_obj(5, 5, 1, "p")'], "list(get_dir(O, P), get_dir(P, O))")
    s.body("get_dir", ['var/obj/O = maps_inobj(5, 5, 1)'], "get_dir(O, locate(5, 8, 1))")
    s.case("get_dir", "get_dir(locate(1, 1, 1))")

    # ================= turn (dirs) =================
    s.sweep("turn", [VALID_DIRS, ANGLES], fmt=lambda d, a: f"turn({d}, {a})")
    for d in ["NORTH", "NORTHEAST", "SOUTHWEST"]:
        for a in ANGLES_X:
            s.case("turn", f"turn({d}, {a})")
    for d in BAD_DIRS:
        s.case("turn", f"turn({d}, 0)")
    s.case("turn", "turn(NORTH)")
    s.case("turn", "turn()")
    s.case("turn", "turn(NORTH, 90, 1)")
    s.case("turn", 'turn("abc", 0)')
    s.case("turn", "turn(new /datum, 0)")
    s.case("turn", "turn(list(), 0)")
    s.body("turn", ["var/d = NORTH", "for(var/i in 1 to 8)", "\td = turn(d, 45)"], "d")
    s.body("turn", ["var/list/L = list()", "var/d = EAST", "for(var/i in 1 to 9)", "\tL += d", "\td = turn(d, -45)"], "L")
    s.body("turn", ["var/list/L = list()", "for(var/d in list(NORTH, SOUTH, EAST, WEST))", "\tL += turn(d, 180)"], "L")

    # ================= view / range / orange / oview =================
    for p in VIEW:
        for c in VCENTERS:
            for d in (VDIST if p in ("view", "range") else VDIST_S):
                s.case(p, f"maps_sdesc({p}({d}, {c}))")
            for d in VDIST_ORDER:
                s.case(p, f"maps_desc({p}({d}, {c}))")
            # Argument order swapped, and center only (default dist)
            s.case(p, f"maps_sdesc({p}({c}, 1))")
            s.case(p, f'maps_sdesc({p}({c}, "3x5"))')
            s.case(p, f"maps_sig({p}({c}))")
        for c in ["maps_scene_open()", "maps_scene_corner()", "maps_scene_opaque()", "maps_scene_top()"]:
            for d in VBIG:
                s.case(p, f"maps_sig({p}({d}, {c}))")
            s.case(p, f"maps_kinds({p}(7, {c}))")
        for d in VBAD:
            s.case(p, f"maps_sdesc({p}({d}, maps_scene_open()))")
        # No usr here: no center, dist only, nothing
        s.case(p, f"maps_desc({p}())")
        s.case(p, f"maps_desc({p}(2))")
        s.case(p, f"maps_desc({p}(null, null))")
        s.case(p, f"maps_sdesc({p}(1, null, maps_scene_open()))")
        s.case(p, f"maps_sdesc({p}(maps_scene_open(), maps_scene_corner()))")
        s.case(p, f"maps_sdesc({p}(1, 2, maps_scene_open()))")
        s.case(p, f"maps_sdesc({p}(1, locate(/area)))")
        s.case(p, f'maps_sdesc({p}(1, maps_obj(10, 10, 1, "x")))')
        s.case(p, f"maps_desc({p}(0, locate(5, 5, 1)))")
        s.case(p, f"maps_desc({p}(1, locate(5, 5, 1)))")
        s.case(p, f"{p}(1, new /datum)")
        s.case(p, f'maps_sdesc({p}(1, new /obj/maps_thing))')
        # Invisible and moved items
        s.body(p, ["var/C = maps_scene_open()", 'var/obj/I = maps_obj(11, 11, 1, "invis")', "I.invisibility = 1"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/C = maps_scene_open()", 'var/obj/I = maps_obj(11, 11, 1, "dark")', "I.luminosity = 0"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/obj/C = maps_scene_open()", "C.loc = locate(12, 12, 1)"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/obj/C = maps_scene_open()", "C.loc = null"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/obj/C = maps_scene_open()", "C.step_x = 20"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/obj/C = maps_scene_opaque()", "C.opacity = 1"], f"maps_sdesc({p}(2, C))")
        s.body(p, ["var/mob/C = maps_scene_mobc()", "C.see_invisible = 0", 'var/obj/I = maps_obj(11, 11, 1, "invis")', "I.invisibility = 1"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/mob/C = maps_scene_mobc()", "C.see_invisible = 5", 'var/obj/I = maps_obj(11, 11, 1, "invis")', "I.invisibility = 1"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/mob/C = maps_scene_mobc()", "C.sight = SEE_TURFS"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/mob/C = maps_scene_mobc()", "C.sight = BLIND"], f"maps_sdesc({p}(1, C))")
        s.body(p, ["var/mob/C = maps_scene_mobc()", 'maps_obj(9, 10, 1, "op", /obj/maps_opaque)', "C.sight = SEE_OBJS"], f"maps_sdesc({p}(3, C))")
        # Result is a fresh list
        s.body(p, ["var/C = maps_scene_open()", f"var/list/L = {p}(0, C)", 'L += "x"'], f"list(maps_sdesc(L), maps_sdesc({p}(0, C)))")

    # ================= viewers / hearers / oviewers / ohearers =================
    for p in VIEWERS:
        for c in WCENTERS:
            for d in WDIST:
                s.case(p, f"maps_sdesc({p}({d}, {c}))")
            for d in ["2", "5"]:
                s.case(p, f"maps_desc({p}({d}, {c}))")
            s.case(p, f"maps_sdesc({p}({c}))")
            s.case(p, f"maps_sdesc({p}({c}, 2))")
        s.case(p, f"maps_desc({p}())")
        s.case(p, f"maps_desc({p}(3))")
        s.case(p, f"maps_sdesc({p}(3, maps_scene_opaque()))")
        s.case(p, f"maps_sdesc({p}(3, locate(/area)))")
        s.case(p, f'maps_sdesc({p}(3, maps_mob(1, 1, 1, "lone")))')
        s.case(p, f'maps_sdesc({p}("abc", maps_scene_mobs()))')
        s.body(p, ['var/obj/C = maps_scene_mobs()', 'var/mob/M = locate(/mob) in locate(11, 10, 1)', "M.sight = BLIND"], f"maps_sdesc({p}(3, C))")
        s.body(p, ['var/obj/C = maps_scene_mobs()', "C.invisibility = 1"], f"maps_sdesc({p}(3, C))")
        s.body(p, ['var/obj/C = maps_scene_mobs()', 'var/mob/M = locate(/mob) in locate(11, 10, 1)', "M.see_invisible = 5", "C.invisibility = 1"], f"maps_sdesc({p}(3, C))")
        s.body(p, ['var/obj/C = maps_scene_mobs()', 'var/mob/M = maps_in(C, "inmob", /mob/maps_mob)'], f"maps_sdesc({p}(1, C))")
        s.body(p, ['var/obj/C = maps_scene_mobs()', 'maps_in(locate(/mob) in locate(8, 10, 1), "pocket", /mob/maps_mob)'], f"maps_sdesc({p}(3, C))")

    # ================= bounds / obounds =================
    for p in ["bounds", "obounds"]:
        pre = ['var/obj/A = maps_obj(5, 5, 1, "a")', 'maps_obj(5, 5, 1, "b")', 'maps_obj(6, 5, 1, "e")',
               'maps_obj(5, 6, 1, "n")', 'maps_obj(4, 4, 1, "sw")', 'maps_inobj(5, 5, 1)']
        for args in ["A", "A, 0", "A, 1", "A, -1", "A, 16", "A, 32", "A, 33", "A, -6, 0", "A, 1, 0", "A, 0, 1",
                     "A, -12, -12, 24, 24", "A, 0, 0, 32, 0", "A, 0, 0, -1, -1", "A, 31, 31", "A, 32, 0",
                     "A, -33, 0", "A, 0, 0, 1", "A, 1.5", "A, null", 'A, "x"', "A, 100"]:
            s.body(p, pre, f"maps_sdesc({p}({args}))")
        for args in ["A", "A, 1", "A, -6, 0", "A, -12, -12, 24, 24"]:
            s.body(p, pre, f"maps_desc({p}({args}))")
        # Pixel offsets on Ref
        for sx, sy in [(16, 0), (0, 16), (16, 16), (31, 0), (-1, 0), (-16, -16), (32, 0), (40, 0)]:
            s.body(p, pre + [f"A.step_x = {sx}", f"A.step_y = {sy}"], f"maps_sdesc({p}(A))")
            s.body(p, pre + [f"A.step_x = {sx}", f"A.step_y = {sy}"], f"maps_sdesc({p}(A, 1))")
        for bx, by, bw, bh in [(0, 0, 16, 16), (8, 8, 16, 16), (0, 0, 64, 32), (0, 0, 33, 33), (-8, 0, 32, 32), (16, 16, 32, 32), (0, 0, 0, 0)]:
            s.body(p, pre + [f"A.bound_x = {bx}", f"A.bound_y = {by}", f"A.bound_width = {bw}", f"A.bound_height = {bh}"],
                   f"maps_sdesc({p}(A))")
        # Other objects' pixel offsets
        s.body(p, pre + ['var/obj/B = maps_obj(7, 5, 1, "p")', "B.step_x = -1"], f"maps_sdesc({p}(A))")
        s.body(p, pre + ['var/obj/B = maps_obj(7, 5, 1, "p")', "B.step_x = -32"], f"maps_sdesc({p}(A))")
        s.body(p, pre + ['var/obj/B = maps_obj(7, 5, 1, "p")', "B.step_x = -33"], f"maps_sdesc({p}(A))")
        s.body(p, pre + ['var/obj/B = maps_obj(5, 7, 1, "p")', "B.bound_y = -40"], f"maps_sdesc({p}(A))")
        # Turf and edge refs
        for args in ["locate(5, 5, 1)", "locate(5, 5, 1), 1", "locate(5, 5, 1), 31", "locate(5, 5, 1), 32", "locate(1, 1, 1), 1",
                     "locate(20, 20, 2), 40", "locate(1, 1, 1), -10, -10", "locate(/area)", "null", "new /datum",
                     '"A"', "maps_inobj(8, 8, 1)", 'maps_obj(1, 1, 1, "c")', 'maps_obj(1, 1, 1, "c"), 5']:
            s.body(p, pre, f"maps_sdesc({p}({args}))")
        s.body(p, pre, f"maps_sdesc({p}())")
    # Absolute coordinate form and pixlocs
    pre = ['maps_obj(5, 5, 1, "a")', 'maps_obj(6, 5, 1, "e")', 'maps_obj(2, 2, 2, "z")']
    for args in ["1, 1, 32, 32, 1", "33, 1, 32, 32, 1", "1, 1, 64, 64, 1", "16, 16, 32, 32, 1", "129, 129, 32, 32, 1",
                 "129, 129, 64, 1, 1", "128, 128, 1, 1, 1", "129, 129, 0, 0, 1", "33, 33, 32, 32, 2", "0, 0, 1, 1, 1",
                 "-100, -100, 50, 50, 1", "600, 600, 100, 100, 1", "1, 1, 32, 32, 3", "1, 1, 32, 32", "1, 1, 32, 32, 0",
                 "129, 129, -32, -32, 1", "1.5, 1.5, 31.5, 31.5, 1",
                 "pixloc(129, 129, 1)", "pixloc(129, 129, 1), pixloc(200, 140, 1)", "pixloc(160, 160, 1), 1",
                 "vector(129, 129), vector(32, 32), 1"]:
        s.body("bounds", pre, f"maps_sdesc(bounds({args}))")
    s.body("obounds", pre, "maps_sdesc(obounds(129, 129, 32, 32, 1))")
    s.body("obounds", pre, "maps_sdesc(obounds(pixloc(129, 129, 1)))")

    # ================= bounds_dist =================
    bd_pos = [(5, 5, 1), (6, 5, 1), (7, 5, 1), (5, 6, 1), (6, 6, 1), (8, 9, 1), (5, 5, 2), (9, 5, 1)]
    for (x, y, z) in bd_pos:
        s.case("bounds_dist", f'bounds_dist(maps_obj(5, 5, 1, "a"), maps_obj({x}, {y}, {z}, "b"))')
        s.case("bounds_dist", f"bounds_dist(locate(5, 5, 1), locate({x}, {y}, {z}))")
    bd_obj = [
        (["A.step_x = 10"], []), (["A.step_x = 31"], []), ([], ["B.step_x = -10"]), ([], ["B.step_x = -40"]),
        (["A.step_y = 16"], ["B.step_y = 16"]), (["A.bound_width = 64"], []), ([], ["B.bound_width = 64"]),
        (["A.bound_height = 64"], []), ([], ["B.bound_height = 8"]), ([], ["B.bound_height = 96"]),
        (["A.bound_x = 8", "A.bound_width = 16"], []), ([], ["B.bound_y = 8", "B.bound_height = 8"]),
        (["A.step_x = 0.5"], []), (["A.bound_width = 0", "A.bound_height = 0"], []),
    ]
    for la, lb in bd_obj:
        for bx, by in [(6, 5), (7, 5), (6, 7), (5, 5)]:
            s.body("bounds_dist", ['var/obj/A = maps_obj(5, 5, 1, "a")', f'var/obj/B = maps_obj({bx}, {by}, 1, "b")'] + la + lb,
                   "list(bounds_dist(A, B), bounds_dist(B, A))")
    s.body("bounds_dist", ['var/obj/A = maps_obj(5, 5, 1, "a")'], "bounds_dist(A, A)")
    s.body("bounds_dist", ['var/obj/A = maps_obj(5, 5, 1, "a")'], "bounds_dist(A, A.loc)")
    s.body("bounds_dist", ['var/obj/A = maps_obj(5, 5, 1, "a")'], "bounds_dist(A, locate(8, 5, 1))")
    for a, b in [("maps_inobj(5, 5, 1)", "locate(6, 5, 1)"), ("null", "locate(6, 5, 1)"), ("locate(6, 5, 1)", "null"),
                 ("null", "null"), ("locate(/area)", "locate(6, 5, 1)"), ('"a"', "locate(6, 5, 1)"),
                 ("new /datum", "locate(6, 5, 1)"), ("locate(1, 1, 1)", "locate(20, 20, 1)"),
                 ("pixloc(160, 160, 1)", "locate(6, 5, 1)")]:
        s.case("bounds_dist", f"bounds_dist({a}, {b})")
    s.case("bounds_dist", "bounds_dist(locate(1, 1, 1))")

    # ================= world / area / turf contents =================
    s.case("contents", "maps_world()")
    s.body("contents", ['maps_obj(1, 1, 1, "a")', 'maps_obj(20, 20, 2, "b")', 'maps_mob(3, 3, 1, "m")', "maps_inobj(4, 4, 1)"], "maps_world()")
    s.body("contents", ['var/obj/O = maps_obj(1, 1, 1, "a")', "O.loc = null"], "maps_world()")
    s.case("contents", "maps_kinds(world.contents)")
    s.case("contents", "maps_sig(world.contents)")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_mob(2, 2, 1, "m")', "maps_inobj(3, 2, 1)"], "maps_kinds(world.contents)")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_mob(2, 2, 1, "m")'], "maps_sig(world.contents)")
    s.body("contents", ['var/n = 0', "for(var/turf/T in world)", "\tn++"], "n")
    s.body("contents", ['var/list/L = list()', "for(var/turf/T in world)", "\tL += T", "\tif(L.len >= 25)", "\t\tbreak"], "maps_desc(L)")
    s.body("contents", ['var/list/L = list()', "for(var/turf/T in world)", "\tL += T"], "maps_desc(L.Copy(L.len - 3))")
    s.case("contents", "maps_desc(world.contents.Copy(1, 6))")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_obj(1, 1, 1, "b")', 'maps_mob(3, 3, 2, "m")'],
           "maps_desc(world.contents.Copy(world.contents.len - 4))")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_obj(1, 1, 1, "b")', 'maps_mob(1, 1, 1, "m")',
                        "var/list/L = list()", "for(var/atom/movable/M in world)", "\tL += M"], "maps_desc(L)")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_obj(1, 1, 1, "b")', 'maps_mob(1, 1, 1, "m")',
                        "var/list/L = list()", "for(var/obj/M in world)", "\tL += M"], "maps_desc(L)")
    s.case("contents", "locate(/area) in world")
    s.case("contents", "locate(/turf) in world")
    s.body("contents", ['maps_obj(2, 2, 1, "a")'], "locate(/obj) in world")
    s.case("contents", "length(world.contents) - world.maxx * world.maxy * world.maxz")
    # area.contents
    s.body("contents", ["var/area/A = locate(/area)"], "maps_kinds(A.contents)")
    s.body("contents", ["var/area/A = locate(/area)"], "maps_sig(A.contents)")
    s.body("contents", ["var/area/A = locate(/area)"], "maps_desc(A.contents.Copy(1, 6))")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_mob(5, 5, 2, "m")', "maps_inobj(3, 3, 1)", "var/area/A = locate(/area)"], "maps_kinds(A.contents)")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_mob(5, 5, 2, "m")', "var/area/A = locate(/area)"], "maps_sig(A.contents)")
    s.body("contents", ['var/obj/O = maps_obj(2, 2, 1, "a")', "var/area/A = locate(/area)"], "O in A.contents")
    s.body("contents", ['var/obj/O = maps_inobj(2, 2, 1)', "var/area/A = locate(/area)"], "O in A.contents")
    s.body("contents", ["var/area/A = locate(/area)"], "(locate(7, 7, 2)) in A.contents")
    s.body("contents", ["var/area/A = locate(/area)"], "list(A.x, A.y, A.z, A.loc)")
    s.body("contents", ["var/turf/T = locate(4, 6, 2)"], "list(T.loc, T.x, T.y, T.z)")
    s.body("contents", ["var/area/A = locate(/area)", "var/n = 0", "for(var/turf/T in A)", "\tn++"], "n")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', "var/area/A = locate(/area)", "var/n = 0", "for(var/obj/O in A)", "\tn++"], "n")
    # turf.contents ordering
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_obj(2, 2, 1, "b")', 'maps_obj(2, 2, 1, "c")'], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['maps_obj(2, 2, 1, "a")', 'maps_mob(2, 2, 1, "m")', 'maps_obj(2, 2, 1, "c")'], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['maps_mob(2, 2, 1, "m")', 'maps_obj(2, 2, 1, "a")', 'maps_mob(2, 2, 1, "n")'], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', 'maps_obj(2, 2, 1, "b")', "A.loc = locate(3, 3, 1)", "A.loc = locate(2, 2, 1)"], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', 'maps_obj(2, 2, 1, "b")', "A.Move(locate(3, 2, 1))", "A.Move(locate(2, 2, 1))"], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', 'var/obj/B = maps_obj(2, 2, 1, "b")', "A.layer = 10", "B.layer = 1"], "maps_desc(maps_tc(2, 2, 1))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', 'maps_obj(2, 2, 1, "b")', "A.step_x = 40"], "list(maps_desc(maps_tc(2, 2, 1)), maps_desc(maps_tc(3, 2, 1)), maps_desc(A.locs))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', "A.bound_width = 64", "A.bound_height = 64"], "list(maps_desc(maps_tc(3, 3, 1)), maps_desc(A.locs))")
    s.body("contents", ['var/obj/A = maps_obj(2, 2, 1, "a")', 'maps_in(A, "i1")', 'maps_in(A, "i2")'], "list(maps_desc(maps_tc(2, 2, 1)), maps_desc(A.contents))")
    s.body("contents", ["var/turf/T = locate(2, 2, 1)", 'maps_obj(2, 2, 1, "a")', "T.contents += new /datum"], "maps_desc(T.contents)")
    s.body("contents", ["var/turf/T = locate(2, 2, 1)", 'var/obj/O = parity_track(new /obj/maps_thing)', 'O.name = "x"', "T.contents += O"], "list(maps_desc(T.contents), maps_d1(O))")
    s.body("contents", ["var/turf/T = locate(2, 2, 1)", 'maps_obj(2, 2, 1, "a")', 'maps_obj(2, 2, 1, "b")', "var/list/L = T.contents", "L.Cut(1, 2)"], "maps_desc(T.contents)")
    s.case("contents", "maps_desc(maps_tc(9, 9, 1))")
    s.body("contents", ["var/area/A = locate(/area)"], "maps_desc(A.loc)")
