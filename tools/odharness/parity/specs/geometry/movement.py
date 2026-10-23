"""Movement: Move() return values and hook order, loc/x/y/z assignment, contents moves, density and
opacity, step/step_to/step_away/step_towards/step_rand, and pixel movement (step_size, step_x/y,
bound_x/y/width/height, locs, Move with step offsets, partial slides, Bump).

Every hook (Enter/Exit/Cross/Uncross/Entered/Exited/Crossed/Uncrossed, Bump on movables) of the
/obj/movement_o, /mob/movement_m, /turf/movement_t and /area/movement_a helper types appends to
movement_log ("<who>.<hook>(<args>)" on entry, "<who>.<hook>=<result>" after ..() for the four
permission hooks). A per-atom movement_force list (e.g. list("Cross" = 1)) overrides a permission
hook's result after ..() ran. Cases record list(return value, log, "name:loc s<step_x>,<step_y>
d<dir>" for each mover). Turf type/density/area changes go through movement_turf()/movement_area()
and are undone by a tracked /datum/movement_restorer when the case is cleaned up, even after an error.

BYOND reference points (info.html Move, Enter, Exit, Cross, Uncross, *ed, Bump, step*, pixel movement):
- Move(NewLoc, Dir=0, step_x=0, step_y=0): 1 for a jump, pixels moved for a slide, 0 on failure.
  Exit()/Uncross() on what is vacated, then Enter()/Cross() on what is entered; failures call Bump()
  for each obstacle; on success Exited/Uncrossed/Entered/Crossed. Same turf without a step change is a
  jump; z changes and moves to/from non-turfs are jumps.
- Legacy movement mode: turf.Enter() = turf.Cross() + Cross() of contents covering the whole tile;
  turf.Exit() = turf.Uncross() + Uncross() of full-tile contents. Areas, objs, mobs permit by default.
- Turfs' Entered/Exited call Crossed/Uncrossed. Setting loc/step_x/step_y, new and del fire no hooks.
- step(Ref, Dir, Speed=0), step(Ref, Vector); step_to(Ref, Trg, Min=0, Speed=0) pathfinds and gives
  up beyond 2*world.view; step_away(Ref, Trg, Max=5, Speed=0); step_towards(Ref, Trg, Speed);
  step_rand(Ref, Speed=0). All return 1 on success, 0 otherwise.
- step_size/bound_width/bound_height default 32 (icon_size), step_x/y and bound_x/y 0, locs =
  list(loc), covered turfs list the atom in their contents. Out-of-range step_x/y get normalised.

OpenDream divergences targeted (DMStandard/Types/Atoms/Movable.dm, Turf.dm, _Standard.dm,
DreamObjectMovable.cs):
- Move() is soft code with only (NewLoc, Dir): returns FALSE for same loc / null, TRUE otherwise, ignores
  step_x/step_y, sets dir only when Dir != 0, Bumps every atom in NewLoc.contents (not the turf, dense
  or not), calls Uncross on everything in the old loc, no pixel slides or multi-turf Enter/Exit.
- step() ignores Speed; step_to() does not path around obstacles; step_away/step_towards always Move.
- step_x/step_y declared null on /atom, step_size null; locs computed from bound_* only; loc = area
  puts the atom on the area's first turf internally.
- turf density reads back as a boolean.
"""
import itertools, re
from gen import dm_str, pairwise

ASSIGN = re.compile(r"^\((\S.*?) (=|\+=|-=) (.*)\)$")

HOOKS_PERMIT = [("Enter", "atom/movable/O, atom/oldloc", "[movement_n(O)],[movement_n(oldloc)]"),
                ("Exit", "atom/movable/O, atom/newloc", "[movement_n(O)],[movement_n(newloc)]"),
                ("Cross", "atom/movable/O", "[movement_n(O)]"),
                ("Uncross", "atom/movable/O", "[movement_n(O)]")]
HOOKS_NOTIFY = [("Entered", "atom/movable/O, atom/oldloc", "[movement_n(O)],[movement_n(oldloc)]"),
                ("Exited", "atom/movable/O, atom/newloc", "[movement_n(O)],[movement_n(newloc)]"),
                ("Crossed", "atom/movable/O", "[movement_n(O)]"),
                ("Uncrossed", "atom/movable/O", "[movement_n(O)]")]


def hook_type(path, movable):
    out = [path, "\tvar/list/movement_force = null"]
    for name, params, args in HOOKS_PERMIT:
        out += [f"\t{name}({params})",
                f'\t\tmovement_L("[movement_n(src)].{name}({args})")',
                "\t\t. = ..()",
                f'\t\tif(movement_force && ("{name}" in movement_force))',
                f'\t\t\t. = movement_force["{name}"]',
                f'\t\tmovement_L("[movement_n(src)].{name}=[movement_n(.)]")']
    for name, params, args in HOOKS_NOTIFY:
        out += [f"\t{name}({params})",
                f'\t\tmovement_L("[movement_n(src)].{name}({args})")',
                "\t\t..()"]
    if movable:
        out += ["\tBump(atom/Obstacle)",
                '\t\tmovement_L("[movement_n(src)].Bump([movement_n(Obstacle)])")',
                "\t\t..()"]
    return "\n".join(out)


HELPERS = r'''var/global/list/movement_log = list()
var/global/movement_on = 0
var/global/datum/movement_restorer/movement_cur
var/global/area/movement_a/movement_the_area

/proc/movement_L(t)
	if(movement_on)
		movement_log += t

// Short deterministic name for anything a hook sees
/proc/movement_n(x)
	if(isnull(x))
		return "null"
	if(isturf(x))
		var/turf/T = x
		return "[T.name]@[T.x],[T.y],[T.z]"
	if(isarea(x))
		var/area/A = x
		return "area:[A.name]"
	if(ismovable(x))
		var/atom/movable/M = x
		return "[M.name]"
	if(istext(x))
		return "\"[x]\""
	if(isnum(x))
		return "[x]"
	if(ispath(x))
		return "[x]"
	if(istype(x, /datum))
		var/datum/D = x
		return "d:[D.type]"
	return "?"

// Undoes turf type/density/opacity/area changes when parity_cleanup() deletes it
/datum/movement_restorer
	var/list/turfs = list()

/datum/movement_restorer/Del()
	movement_on = 0
	movement_log = list()
	for(var/i = turfs.len, i >= 1, i--)
		var/list/e = turfs[i]
		var/turf/T = locate(e[1], e[2], e[3])
		var/area/A = e[4]
		if(T.loc != A)
			A.contents += T
		if(T.type != /turf)
			T = new /turf(T)
		T.density = 0
		T.opacity = 0
		T.name = "turf"
	turfs = list()
	if(movement_the_area)
		movement_the_area.movement_force = null
		movement_the_area.density = 0
		movement_the_area.opacity = 0
	if(movement_cur == src)
		movement_cur = null
	..()

/proc/movement_begin()
	movement_on = 0
	movement_log = list()
	movement_cur = parity_track(new /datum/movement_restorer)
	movement_on = 1

/proc/movement_go()
	movement_log.Cut()
	movement_on = 1

// x is a number (with y, z) for a turf, or a container atom, or null for nullspace
/proc/movement_new(type, x, y, name, density = null, list/force = null, z = 1)
	var/atom/where = isnum(x) ? locate(x, y, z) : x
	var/atom/movable/M = new type(where)
	parity_track(M)
	M.name = name
	if(!isnull(density))
		M.density = density
	if(force)
		M:movement_force = force
	return M

/proc/movement_turf(x, y, density = 0, list/force = null, type = /turf/movement_t, z = 1)
	var/turf/T = locate(x, y, z)
	movement_cur.turfs += list(list(x, y, z, T.loc))
	if(T.type != type)
		T = new type(T)
	T.name = (type == /turf) ? "turf" : "t"
	T.density = density
	if(force)
		T:movement_force = force
	return T

/proc/movement_area(x, y, list/force = null, z = 1)
	var/turf/T = locate(x, y, z)
	movement_cur.turfs += list(list(x, y, z, T.loc))
	if(!movement_the_area)
		movement_the_area = new /area/movement_a
	movement_the_area.name = "ar"
	movement_the_area.movement_force = force
	movement_the_area.contents += T
	return movement_the_area

/proc/movement_pos(atom/movable/M)
	if(isnull(M))
		return "gone"
	return "[movement_n(M)]:[movement_n(M.loc)] s[M.step_x],[M.step_y] d[M.dir]"

/proc/movement_out(r, A, B = null, C = null)
	var/list/L = list(r, movement_log.Copy(), movement_pos(A))
	if(B)
		L += movement_pos(B)
	if(C)
		L += movement_pos(C)
	return L

// Names of the movables a turf lists in its contents (overhangers included)
/proc/movement_c(x, y, z = 1)
	var/list/L = list()
	var/turf/T = locate(x, y, z)
	for(var/atom/movable/M in T)
		L += M.name
	return L

/proc/movement_xyz(atom/A)
	if(isnull(A))
		return "null"
	return "[A.x],[A.y],[A.z]"'''


# ---------- DM source builders ----------
def O(n, x=5, y=5, d=0, kind="/obj/movement_o", force=None, z=1):
    return f'var/atom/movable/{n} = movement_new({kind}, {x}, {y}, "{n}", {d}, {force or "null"}, {z})'


def P(n, x=5, y=5, d=0, kind="/obj", z=1):
    """A plain (non-logging) movable."""
    return O(n, x, y, d, kind, None, z)


def T(x, y, d=0, force=None, kind="/turf/movement_t", z=1):
    return f"movement_turf({x}, {y}, {d}, {force or 'null'}, {kind}, {z})"


def F(**kw):
    return "list(" + ", ".join(f'"{k}" = {v}' for k, v in kw.items()) + ")"


L65 = "locate(6, 5, 1)"
L55 = "locate(5, 5, 1)"
TT = [T(5, 5), T(6, 5)]

DIRS = ["0", "NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST", "3", "12",
        "15", "UP", "DOWN", "-1", "0.5", "4.5", "255", "null", '"x"', "list()", "new /datum", "/obj"]
DIR8 = ["NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST"]
SPEED = ["0", "1", "4", "8", "16", "31", "32", "33", "64", "640", "-16", "0.5", "null", '"8"']
REFS = ["null", '"x"', "5", "list()", "/obj", "new /datum", L55, "locate(/area)", "PINF"]


def build(s):
    s.define("PARITY_MAXX", 20)
    s.define("PARITY_MAXY", 20)
    s.define("PARITY_MAXZ", 2)
    s.dm(HELPERS)
    s.dm(hook_type("/obj/movement_o", True))
    s.dm(hook_type("/mob/movement_m", True))
    s.dm(hook_type("/turf/movement_t", False))
    s.dm(hook_type("/area/movement_a", False))
    s.dm(EXTRA_DM)

    def mv(proc, setup, action, out="movement_out(r, A)"):
        m = ASSIGN.match(action)
        act = [m.group(1) + " " + m.group(2) + " " + m.group(3), f"var/r = {m.group(1)}"] if m else [f"var/r = {action}"]
        s.body(proc, ["movement_begin()"] + list(setup) + ["movement_go()"] + act, out)

    move_hooks(mv)
    move_dir(mv)
    move_sweep(s, mv)
    loc_assign(mv)
    contents(mv)
    density(s, mv)
    step(mv)
    step_to(mv)
    step_towards(mv)
    step_away(mv)
    step_rand(mv)
    pixel(s, mv)
    gaps(mv)


def move_hooks(mv):
    A = O("A")
    Ad = O("A", d=1)
    go = f"A.Move({L65})"
    # Plain tile move between logging turfs: the full hook order
    mv("Move", TT + [A], go)
    mv("Move", TT + [Ad], go)
    mv("Move", [Ad], go)
    mv("Move", [P("A", d=1)], go)
    # Dense destination turf
    mv("Move", [T(5, 5), T(6, 5, 1), Ad], go)
    mv("Move", [T(5, 5), T(6, 5, 1), A], go)
    mv("Move", [T(6, 5, 1), P("A", d=1)], go)
    # Objs on the destination
    mv("Move", TT + [Ad, O("B", 6, 5, 1)], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, 1)], go, "movement_out(r, A, B)")
    mv("Move", TT + [Ad, O("B", 6, 5, 0)], go, "movement_out(r, A, B)")
    mv("Move", TT + [Ad, O("B", 6, 5, 1, force=F(Cross=1))], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, 0, force=F(Cross=0))], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, 0, force=F(Cross="null"))], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, 0, force=F(Cross='"yes"'))], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5), O("C", 6, 5)], go, "movement_out(r, A, B, C)")
    mv("Move", TT + [Ad, O("B", 6, 5), O("C", 6, 5, 1)], go, "movement_out(r, A, B, C)")
    mv("Move", TT + [Ad, O("B", 6, 5, 1), O("C", 6, 5, 1)], go, "movement_out(r, A, B, C)")
    mv("Move", TT + [A, O("B", 6, 5, force=F(Cross=0)), O("C", 6, 5)], go, "movement_out(r, A, B, C)")
    # Bump targets: dense turf holding a non-dense obj; plain dense obj on a plain turf
    mv("Move", [T(5, 5), T(6, 5, 1), Ad, O("B", 6, 5, 0)], go, "movement_out(r, A, B)")
    mv("Move", [Ad, P("B", 6, 5, 1)], go, "movement_out(r, A, B)")
    mv("Move", [Ad, P("B", 6, 5, 0), P("C", 6, 5, 1)], go, "movement_out(r, A, B, C)")
    mv("Move", [Ad, P("B", 6, 5, 1, "/mob")], go, "movement_out(r, A, B)")
    # Objs left behind on the source
    mv("Move", TT + [A, O("B", 5, 5)], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 5, 5, force=F(Uncross=0))], go, "movement_out(r, A, B)")
    mv("Move", TT + [Ad, O("B", 5, 5, 1)], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 5, 5), O("C", 6, 5)], go, "movement_out(r, A, B, C)")
    # Permission overrides on the turfs
    for src_f, dst_f in [(None, F(Enter=0)), (None, F(Cross=0)), (F(Exit=0), None), (F(Uncross=0), None),
                         (None, F(Enter=1)), (F(Exit=1), None)]:
        mv("Move", [T(5, 5, force=src_f), T(6, 5, force=dst_f), A], go)
    mv("Move", [T(5, 5), T(6, 5, 1, F(Cross=1)), Ad], go)
    mv("Move", [T(5, 5), T(6, 5, 1, F(Enter=1)), Ad], go)
    mv("Move", [T(5, 5), T(6, 5, 0, F(Cross=0)), Ad, O("B", 6, 5)], go, "movement_out(r, A, B)")
    mv("Move", [T(5, 5, 1), T(6, 5), Ad], go)  # leaving a dense turf is fine
    mv("Move", [T(5, 5, 0, F(Uncross=0)), T(6, 5), A, O("B", 5, 5)], go, "movement_out(r, A, B)")
    # Mobs
    M = O("A", kind="/mob/movement_m", d="null")
    mv("Move", TT + [M], go)
    mv("Move", TT + [M, O("B", 6, 5, "null", "/mob/movement_m")], go, "movement_out(r, A, B)")
    mv("Move", TT + [M, O("B", 6, 5, 0, "/mob/movement_m")], go, "movement_out(r, A, B)")
    mv("Move", TT + [M, O("B", 6, 5, 1)], go, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, "null", "/mob/movement_m")], go, "movement_out(r, A, B)")
    mv("Move", TT + [O("A", kind="/mob/movement_m", d=0), O("B", 6, 5, "null", "/mob/movement_m")], go,
       "movement_out(r, A, B)")
    # Diagonals past dense orthogonal turfs
    diag = f"A.Move(locate(6, 6, 1))"
    mv("Move", [T(5, 5), T(6, 6), Ad], diag)
    mv("Move", [T(5, 5), T(6, 6), T(6, 5, 1), Ad], diag)
    mv("Move", [T(5, 5), T(6, 6), T(6, 5, 1), T(5, 6, 1), Ad], diag)
    mv("Move", [T(5, 5), T(6, 6, 1), T(6, 5), T(5, 6), Ad], diag)
    mv("Move", [T(5, 5), T(6, 6), O("B", 6, 5, 1), O("C", 5, 6, 1), Ad], diag, "movement_out(r, A, B, C)")
    # Same loc, null, jumps, z changes, nullspace
    mv("Move", TT + [A], f"A.Move({L55})")
    mv("Move", TT + [A, O("B", 5, 5)], f"A.Move({L55})", "movement_out(r, A, B)")
    mv("Move", TT + [A], "A.Move(A.loc, NORTH)")
    mv("Move", TT + [A], "A.Move(null)")
    mv("Move", TT + [A], "A.Move(null, NORTH)")
    mv("Move", TT + [A], "A.Move()")
    mv("Move", [T(5, 5), T(9, 9), A], "A.Move(locate(9, 9, 1))")
    mv("Move", [T(5, 5), T(9, 9, 1), Ad], "A.Move(locate(9, 9, 1))")
    mv("Move", [T(5, 5), T(9, 9), A, O("B", 9, 9, 1)], "A.Move(locate(9, 9, 1))", "movement_out(r, A, B)")
    mv("Move", [T(5, 5), T(5, 5, z=2), A], "A.Move(locate(5, 5, 2))")
    mv("Move", [T(5, 5), T(6, 5, z=2), A], "A.Move(locate(6, 5, 2))")
    mv("Move", [T(5, 5), T(5, 5, 1, z=2), Ad], "A.Move(locate(5, 5, 2))")
    mv("Move", [T(5, 5), A], "A.Move(locate(20, 20, 1))")
    mv("Move", [T(5, 5), A], "A.Move(locate(0, 0, 1))")
    mv("Move", [T(6, 5), O("A", "null")], go)
    mv("Move", [T(6, 5, 1), O("A", "null", d=1)], go)
    mv("Move", [T(6, 5), O("A", "null")], "A.Move(null)")
    mv("Move", [T(6, 5), O("A", "null")], f"A.Move({L65}, NORTH)")
    # Containers
    into = "A.Move(B)"
    mv("Move", TT + [A, O("B", 5, 5)], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5)], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 9, 9)], into, "movement_out(r, A, B)")
    mv("Move", TT + [Ad, O("B", 6, 5, 1)], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, force=F(Enter=0))], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, force=F(Cross=0))], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", 6, 5, kind="/mob/movement_m", d="null")], into, "movement_out(r, A, B)")
    mv("Move", TT + [A, O("B", "null")], into, "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5), O("A", "B")], go, "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5, force=F(Exit=0)), O("A", "B")], go, "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5, force=F(Uncross=0)), O("A", "B")], go, "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5), O("A", "B"), O("C", 5, 5)], "A.Move(C)", "movement_out(r, A, B, C)")
    mv("Move", TT + [O("B", 5, 5), O("A", "B")], "A.Move(B)", "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5), O("A", "B")], "A.Move(null)", "movement_out(r, A, B)")
    mv("Move", TT + [O("B", 5, 5), O("A", "B", d=1)], f"A.Move({L55})", "movement_out(r, A, B)")
    mv("Move", TT + [A], "A.Move(A)")
    mv("Move", TT + [A, O("B", "A")], "A.Move(B)", "movement_out(r, A, B)")
    # The container moves; the contained atom's coordinates follow
    mv("Move", TT + [O("B", 5, 5), O("A", "B")], f"B.Move({L65})", "list(r, movement_log.Copy(), movement_xyz(A), A.locs)")
    # Areas
    mv("Move", TT + [A, "movement_area(6, 5)"], go)
    mv("Move", TT + [A, "movement_area(5, 5)"], go)
    mv("Move", TT + [A, "movement_area(5, 5)", "movement_area(6, 5)"], go)
    mv("Move", TT + [A, f"movement_area(6, 5, {F(Enter=0)})"], go)
    mv("Move", TT + [A, f"movement_area(6, 5, {F(Cross=0)})"], go)
    mv("Move", TT + [A, f"movement_area(5, 5, {F(Exit=0)})"], go)
    mv("Move", TT + [A, f"movement_area(5, 5, {F(Uncross=0)})"], go)
    mv("Move", TT + [Ad, "movement_area(6, 5)", T(6, 5, 1)], go)
    mv("Move", [T(5, 5), T(9, 9), A, "movement_area(9, 9)"], "A.Move(locate(9, 9, 1))")
    mv("Move", TT + [A, "var/area/R = movement_area(9, 9)"], "A.Move(R)")
    mv("Move", TT + [A], "A.Move(locate(/area))")
    mv("Move", TT + [A, "movement_area(6, 5)", O("B", 6, 5)], into, "movement_out(r, A, B)")
    # Multi-tile mover: only newly covered turfs are entered, only fully vacated ones exited
    big = [T(5, 5), T(6, 5), T(7, 5), O("A"), "A.bound_width = 64"]
    mv("Move", big, go, "movement_out(r, A) + list(A.locs)")
    mv("Move", big + [T(7, 5, 1), "A.density = 1"], go, "movement_out(r, A) + list(A.locs)")
    mv("Move", big + [O("B", 7, 5)], go, "movement_out(r, A, B)")
    mv("Move", big + [O("B", 6, 5)], go, "movement_out(r, A, B)")
    # Return values of three Moves in a row
    mv("Move", TT + [A], f"list(A.Move({L65}), A.Move({L55}), A.Move({L55}))")


def move_dir(mv):
    A = O("A")
    for d in DIRS:
        mv("Move.dir", [A], f"A.Move({L65}, {d})")
        mv("Move.dir", [T(6, 5, 1), O("A", d=1)], f"A.Move({L65}, {d})")
    for d in ["0", "NORTH", "EAST", "3", "null"]:
        mv("Move.dir", [A], f"A.Move({L55}, {d})")
        mv("Move.dir", [A], f"A.Move(null, {d})")
        mv("Move.dir", [A], f"A.Move(locate(9, 7, 1), {d})")
        mv("Move.dir", [A], f"A.Move(locate(5, 5, 2), {d})")
        mv("Move.dir", [A, O("B", 9, 9)], f"A.Move(B, {d})")
    # Dir=0: does the mover face where it went?
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            mv("Move.dir", [A, "A.dir = WEST"], f"A.Move(locate({5 + dx}, {5 + dy}, 1))")
    mv("Move.dir", [A, "A.dir = WEST"], "A.Move(locate(8, 6, 1))")
    mv("Move.dir", [A, "A.dir = WEST"], "A.Move(locate(5, 9, 1))")
    mv("Move.dir", [T(6, 5, 1), O("A", d=1), "A.dir = WEST"], f"A.Move({L65})")
    # Named arguments
    mv("Move.named", [A], f"A.Move(NewLoc = {L65}, Dir = NORTH)")
    mv("Move.named", [A], f"A.Move(Dir = NORTH, NewLoc = {L65})")
    mv("Move.named", [A], f"A.Move({L65}, step_x = 8)")
    mv("Move.named", [A], f"A.Move({L55}, step_y = 8, step_x = 4)")
    mv("Move.named", [A], f"A.Move(NewLoc = {L65})")


def move_sweep(s, mv):
    """All-pairs over Move's four arguments, on logging source and destination turfs."""
    newloc = [L65, L55, "locate(5, 6, 1)", "locate(9, 9, 1)", "locate(6, 5, 2)", "null", "locate(/area)",
              '"x"', "5", "list()", "/turf", "new /datum"]
    dirs = ["0", "NORTH", "EAST", "SOUTHWEST", "3", "-1", "null", '"x"']
    sxy = ["0", "8", "-8", "31", "32", "40", "-40", "2.5", "null", '"4"']
    pools = [newloc, dirs, sxy, sxy]
    setup = TT + [O("A")]
    for count in range(1, 5):
        ps = pools[:count]
        if count <= 2:
            rows = itertools.product(*ps)
        else:
            rows = ([ps[i][v] for i, v in enumerate(r)] for r in pairwise(ps))
        for args in rows:
            mv("Move.sweep", setup, f"A.Move({', '.join(args)})")


def loc_assign(mv):
    A = O("A")
    base = TT + [A, O("B", 6, 5)]
    out_ab = "movement_out(r, A, B)"
    for v in [L65, "B", "null", L55, "locate(9, 9, 2)", "locate(/area)", '"x"', "5", "list()", "/turf",
              "new /datum", "A", "locate(0, 0, 0)"]:
        mv("loc=", base, f"(A.loc = {v})", f"list(r, movement_log.Copy(), movement_pos(A), movement_xyz(A), A.locs)")
    mv("loc=", base + ["var/area/R = movement_area(9, 9)"], "(A.loc = R)",
       "list(r, movement_log.Copy(), movement_pos(A), movement_xyz(A), A.locs, R.contents.Find(A) > 0)")
    mv("loc=", [T(5, 5), T(6, 5, 1), O("A", d=1), O("B", 6, 5, 1)], f"(A.loc = {L65})", out_ab)
    mv("loc=", base + ["A.dir = NORTH"], f"(A.loc = {L65})", out_ab)
    mv("loc=", base + ["var/atom/movable/C = movement_new(/obj/movement_o, A, 0, \"C\")"], "(A.loc = B)",
       "list(r, movement_log.Copy(), movement_xyz(C), C.loc == A)")
    mv("loc=", [O("B", 5, 5), O("A", "B")], "(B.loc = A)", "list(r, A.loc == B, B.loc == A)")
    # x/y/z assignment
    for var, vals in [("x", ["7", "0", "20", "21", "-1", "2.5", '"3"', "null", "NAN"]),
                      ("y", ["7", "0", "21", "1"]),
                      ("z", ["2", "0", "3", "1.5"])]:
        for v in vals:
            mv("xyz=", TT + [A], f"(A.{var} = {v})", "list(r, movement_log.Copy(), movement_pos(A), movement_xyz(A))")
    mv("xyz=", [O("A", "null")], "(A.x = 3)", "list(r, movement_pos(A), movement_xyz(A))")
    mv("xyz=", [O("A", "null")], "(A.z = 1)", "list(r, movement_pos(A), movement_xyz(A))")
    mv("xyz=", [O("B", 7, 7), O("A", "B")], "(A.x = 3)", "list(r, movement_pos(A), movement_xyz(A))")
    # Reading coordinates of contained / unplaced atoms
    mv("xyz", [O("B", 7, 8), O("A", "B")], "movement_xyz(A)", "list(r, A.locs)")
    mv("xyz", [O("B", 7, 8, kind="/mob/movement_m"), O("C", "B"), O("A", "C")], "movement_xyz(A)", "list(r, A.locs)")
    mv("xyz", [O("A", "null")], "movement_xyz(A)", "list(r, A.locs, A.loc)")
    mv("xyz", ["var/turf/X = locate(4, 6, 2)"], "movement_xyz(X)", "list(r, X.loc)")
    mv("xyz", ["var/area/R = locate(/area)"], "movement_xyz(R)", "list(r, R.loc)")
    # new / del fire no hooks
    mv("new", TT + [O("B", 5, 5)], 'movement_new(/obj/movement_o, 5, 5, "A")',
       "list(movement_log.Copy(), movement_c(5, 5))")
    mv("new", TT + [O("B", 5, 5)], 'movement_new(/obj/movement_o, B, 0, "A")',
       "list(movement_log.Copy(), B.contents.len)")
    mv("new", TT + [O("B", 5, 5, 1)], 'movement_new(/obj/movement_o, 5, 5, "A", 1)',
       "list(movement_log.Copy(), movement_c(5, 5))")
    mv("new", [T(5, 5, 1)], 'movement_new(/obj/movement_o, 5, 5, "A", 1)',
       "list(movement_log.Copy(), movement_c(5, 5))")
    mv("del", TT + [A, O("B", 5, 5)], "1", "list(movement_log.Copy(), movement_c(5, 5))")
    s_del = TT + [A, O("B", 5, 5)]
    mv("del", s_del + ["movement_go()", "del A"], "1", "list(movement_log.Copy(), movement_c(5, 5))")
    mv("del", [O("B", 5, 5), O("A", "B"), "movement_go()", "del A"], "1", "list(movement_log.Copy(), B.contents.len)")


def contents(mv):
    A = O("A")
    res = "list(r, movement_log.Copy(), movement_pos(A), movement_c(5, 5), movement_c(6, 5))"
    base = TT + [A, O("B", 6, 5), "var/turf/S = locate(5, 5, 1)", "var/turf/D = locate(6, 5, 1)"]
    mv("contents", base, "(B.contents += A)", "list(movement_log.Copy(), movement_pos(A), B.contents.len)")
    mv("contents", base, f"(D.contents += A)", res)
    mv("contents", base, f"(S.contents -= A)", res)
    mv("contents", base, f"(D.contents -= A)", res)
    mv("contents", base, f"S.contents.Cut()", res)
    mv("contents", base + [O("C", 5, 5)], f"S.contents.Cut(1, 2)", res)
    mv("contents", base, f"S.contents.Add(B)", res)
    mv("contents", base, f"S.contents.Remove(A)", res)
    mv("contents", base, f"D.contents.Insert(1, A)", res)
    mv("contents", base, f"(S.contents += \"x\")", res)
    mv("contents", base, f"(S.contents += locate(1, 1, 1))", res)
    mv("contents", base, f"(S.contents += new /datum)", res)
    mv("contents", base, f"(S.contents += list(B))", res)
    mv("contents", base, f"(S.contents = list())", res)
    mv("contents", base, f"(S.contents[1] = B)", res)
    mv("contents", base, f"S.contents[1]", res)
    mv("contents", base, f"S.contents.len", res)
    mv("contents", base, f"(S.contents.len = 0)", res)
    mv("contents", base, f"S.contents.Copy()", res)
    mv("contents", base, "(A.contents += B)", "list(movement_log.Copy(), movement_pos(B), A.contents.len)")
    mv("contents", base + ["A.contents += B"], "(A.contents -= B)", "list(movement_log.Copy(), movement_pos(B), A.contents.len)")
    mv("contents", base + ["A.contents += B"], "A.contents.Cut()", "list(movement_log.Copy(), movement_pos(B), A.contents.len)")
    mv("contents", base, "(A.contents += A)", res)
    mv("contents", base + ["A.contents += B"], "(B.contents += A)", "list(movement_log.Copy(), A.loc == B, B.loc == A)")
    mv("contents", base + ["var/area/R = locate(/area)"], "(R.contents += A)", "list(movement_log.Copy(), movement_pos(A), movement_xyz(A))")
    mv("contents", base + ["var/area/R = locate(/area)"], "(A in R)", res)
    mv("contents", base, f"(A in S)", res)
    mv("contents", base, f"(A in S.contents)", res)


def density(s, mv):
    vals = ["0", "1", "2", "-1", "0.5", '"x"', '""', "null", "list()", "PINF", "NAN", "/obj"]
    for v in vals:
        for var in ("density", "opacity"):
            mv(f"{var}=", [P("A")], f"(A.{var} = {v})", f"list(r, A.{var})")
            mv(f"{var}=", [f"var/turf/X = {T(5, 5, kind='/turf')}"], f"(X.{var} = {v})", f"list(r, X.{var})")
            mv(f"{var}=", [f"var/area/R = movement_area(5, 5)"], f"(R.{var} = {v})", f"list(r, R.{var})")
            mv(f"{var}=", [P("A", kind="/mob")], f"(A.{var} = {v})", f"list(r, A.{var})")
    # Defaults
    s.body("density", ['var/obj/A = parity_track(new /obj)', 'var/mob/B = parity_track(new /mob)',
                       'var/turf/X = locate(3, 3, 1)', 'var/area/R = locate(/area)'],
           "list(A.density, A.opacity, B.density, B.opacity, X.density, X.opacity, R.density, R.opacity)")
    # Which densities block: the mover's density, then the turf's
    go = f"A.Move({L65})"
    for v in vals:
        mv("density.move", [T(5, 5), T(6, 5, 1), O("A"), f"A.density = {v}"], go)
        mv("density.move", [T(5, 5), T(6, 5), O("A", d=1), "var/turf/D = locate(6, 5, 1)", f"D.density = {v}"], go)
        mv("density.move", [T(5, 5), T(6, 5), O("A", d=1), O("B", 6, 5), f"B.density = {v}"], go, "movement_out(r, A, B)")
    # Opacity does not block movement
    mv("opacity.move", [T(5, 5), T(6, 5), O("A", d=1), "var/turf/D = locate(6, 5, 1)", "D.opacity = 1"], go)
    mv("opacity.move", [T(5, 5), T(6, 5), O("A", d=1), O("B", 6, 5), "B.opacity = 1"], go, "movement_out(r, A, B)")
    mv("opacity.move", [T(5, 5), T(6, 5), O("A", d=1), "A.opacity = 1"], go)
    mv("opacity.move", [T(5, 5), T(6, 5), O("A", d=1), O("B", 6, 5, 1), "B.opacity = 1"], go, "movement_out(r, A, B)")
    # Density changed during the move is seen by the later hooks
    mv("density.move", [T(5, 5), T(6, 5, 1), O("A", d=1), "A.density = 0"], go)


def step(mv):
    A = O("A")
    for d in DIRS:
        mv("step", [T(5, 5), A], f"step(A, {d})")
    for d in DIR8 + ["0", "3"]:
        for sp in SPEED:
            mv("step.speed", [A], f"step(A, {d}, {sp})")
    for d in DIR8:
        mv("step", [O("A", 1, 1)], f"step(A, {d})")
        mv("step", [O("A", 20, 20)], f"step(A, {d})")
        mv("step", [O("A", 1, 20)], f"step(A, {d}, 8)")
        mv("step", [T(5, 5), T(6, 5, 1), T(5, 6, 1), O("A", d=1)], f"step(A, {d})")
    mv("step", [O("A", 5, 5, z=2)], "step(A, UP)")
    mv("step", [O("A", 5, 5, z=2)], "step(A, DOWN)")
    mv("step", [T(5, 5), T(6, 5), A, O("B", 6, 5)], "step(A, EAST)", "movement_out(r, A, B)")
    mv("step", [T(5, 5), T(6, 5), O("A", d=1), O("B", 6, 5, 1)], "step(A, EAST)", "movement_out(r, A, B)")
    mv("step", [T(5, 5), T(6, 5, 1), O("A", d=1)], "step(A, EAST)")
    mv("step", [T(5, 5), T(6, 5, 1), O("A", d=1), "A.dir = WEST"], "step(A, EAST, 4)")
    mv("step", [O("A", 5, 5, kind="/mob/movement_m", d="null"), O("B", 6, 5, "null", "/mob/movement_m")],
       "step(A, EAST)", "movement_out(r, A, B)")
    # step_size decides the default speed
    for ss in ["8", "16", "0", "-8", "64", "0.5", "null", '"8"']:
        mv("step.step_size", [A, f"A.step_size = {ss}"], "step(A, EAST)", "movement_out(r, A) + list(A.step_size)")
        mv("step.step_size", [A, f"A.step_size = {ss}"], "step(A, EAST, 4)", "movement_out(r, A) + list(A.step_size)")
    # Not on a turf
    mv("step", [O("B", 5, 5), O("A", "B")], "step(A, EAST)", "movement_out(r, A, B)")
    mv("step", [O("A", "null")], "step(A, EAST)")
    # Wrong Ref kinds
    for r in REFS:
        mv("step.ref", [], f"step({r}, EAST)", "r")
    mv("step.ref", [A], "step(A)")
    # Vector form
    for v in ["vector(8, 0)", "vector(32, 32)", "vector(0, 0)", "vector(-40, 0)", "vector(0.5, 0)", "vector(64, 0)",
              "vector(1, 2, 3)"]:
        mv("step.vector", [A], f"step(A, {v})")
    mv("step.vector", [T(6, 5, 1), O("A", d=1)], "step(A, vector(16, 0))")


def targets():
    """(label, DM setup line for target B) at different spots relative to A at (5, 5)."""
    out = []
    for x, y in [(5, 5), (6, 5), (7, 5), (8, 8), (4, 6), (5, 10), (5, 15), (5, 16), (16, 5), (15, 15), (1, 1)]:
        out.append(P("B", x, y))
    return out


def step_to(mv):
    A = O("A")
    mins = ["0", "1", "2", "3", "5", "-1", "null", "0.5", '"2"']
    speeds = ["0", "8", "32", "null"]
    tg = targets()
    for t in tg:
        for m in mins:
            mv("step_to", [A, t], f"step_to(A, B, {m})")
        mv("step_to", [A, t], "step_to(A, B)")
    rows = pairwise([list(range(len(tg))), mins, speeds])
    for r in rows:
        mv("step_to.speed", [A, tg[r[0]]], f"step_to(A, B, {mins[r[1]]}, {speeds[r[2]]})")
    # Obstacles: BYOND paths around them
    wall = [T(6, y, 1) for y in range(3, 8)]
    Ad = O("A", d=1)
    mv("step_to.wall", wall + [Ad, P("B", 7, 5)], "step_to(A, B)")
    mv("step_to.wall", wall + [O("A"), P("B", 7, 5)], "step_to(A, B)")
    mv("step_to.wall", [T(6, y, 1) for y in range(1, 21)] + [Ad, P("B", 7, 5)], "step_to(A, B)")
    mv("step_to.wall", [T(6, 5, 1), Ad, P("B", 8, 5)], "step_to(A, B)")
    mv("step_to.wall", [Ad, P("B", 6, 5, 1)], "step_to(A, B)", "movement_out(r, A, B)")
    mv("step_to.wall", [Ad, P("B", 6, 5, 1)], "step_to(A, B, 1)", "movement_out(r, A, B)")
    mv("step_to.wall", [Ad, P("C", 6, 5, 1), P("B", 7, 5)], "step_to(A, B)", "movement_out(r, A, C)")
    # Target kinds
    for t in ["null", "A", L55, "locate(8, 5, 1)", "locate(8, 5, 2)", '"x"', "locate(/area)", "new /datum"]:
        mv("step_to.trg", [A], f"step_to(A, {t})")
    mv("step_to.trg", [A, O("C", 8, 5), O("B", "C")], "step_to(A, B)")
    mv("step_to.trg", [O("C", 5, 5), O("A", "C"), P("B", 8, 5)], "step_to(A, B)")
    for r in REFS:
        mv("step_to.ref", [P("B", 7, 5)], f"step_to({r}, B)", "r")
    # Repeated steps reach the target and stop
    mv("step_to", [A, P("B", 8, 7)], "list(step_to(A, B), step_to(A, B), step_to(A, B), step_to(A, B))")
    mv("step_to", [A, P("B", 8, 7)], "list(step_to(A, B, 1), step_to(A, B, 1), step_to(A, B, 1))")


def step_towards(mv):
    A = O("A")
    for t in targets():
        mv("step_towards", [A, t], "step_towards(A, B)")
        mv("step_towards", [A, t], "step_towards(A, B, 8)")
    for sp in SPEED:
        mv("step_towards.speed", [A, P("B", 8, 5)], f"step_towards(A, B, {sp})")
    Ad = O("A", d=1)
    mv("step_towards.wall", [T(5, 5), T(6, 5, 1), Ad, P("B", 8, 5)], "step_towards(A, B)")
    mv("step_towards.wall", [T(5, 5), T(6, 6, 1), Ad, P("B", 8, 8)], "step_towards(A, B)")
    mv("step_towards.wall", [T(5, 5), T(6, 6, 1), T(6, 5, 1), T(5, 6, 1), Ad, P("B", 8, 8)], "step_towards(A, B)")
    mv("step_towards.wall", [Ad, O("B", 6, 5, 1)], "step_towards(A, B)", "movement_out(r, A, B)")
    for t in ["null", "A", L55, "locate(8, 6, 1)", "locate(8, 5, 2)", '"x"', "locate(/area)", "new /datum"]:
        mv("step_towards.trg", [A], f"step_towards(A, {t})")
    mv("step_towards.trg", [A, O("C", 8, 5), O("B", "C")], "step_towards(A, B)")
    for r in REFS:
        mv("step_towards.ref", [P("B", 7, 5)], f"step_towards({r}, B)", "r")


def step_away(mv):
    A = O("A")
    maxes = ["0", "1", "2", "5", "6", "10", "-1", "null", '"3"']
    for t in targets():
        for m in maxes:
            mv("step_away", [A, t], f"step_away(A, B, {m})")
        mv("step_away", [A, t], "step_away(A, B)")
        mv("step_away", [A, t], "step_away(A, B, 5, 8)")
    Ad = O("A", d=1)
    mv("step_away.wall", [T(5, 5), T(4, 5, 1), Ad, P("B", 6, 5)], "step_away(A, B)")
    mv("step_away.wall", [T(5, 5), T(4, 5, 1), T(4, 4, 1), T(4, 6, 1), Ad, P("B", 6, 5)], "step_away(A, B)")
    mv("step_away.wall", [O("A", 1, 1), P("B", 2, 2)], "step_away(A, B)")
    mv("step_away.wall", [O("A", 1, 5), P("B", 2, 5)], "step_away(A, B)")
    mv("step_away.wall", [Ad, O("C", 4, 5, 1), P("B", 6, 5)], "step_away(A, B)", "movement_out(r, A, C)")
    for t in ["null", "A", L55, "locate(6, 6, 1)", "locate(6, 5, 2)", '"x"', "locate(/area)", "new /datum"]:
        mv("step_away.trg", [A], f"step_away(A, {t})")
    for r in REFS:
        mv("step_away.ref", [P("B", 7, 5)], f"step_away({r}, B)", "r")
    mv("step_away", [A, P("B", 6, 5)], "list(step_away(A, B, 3), step_away(A, B, 3), step_away(A, B, 3), step_away(A, B, 3))")


def step_rand(mv):
    # Only cases where randomness can't show: nowhere to go, or no valid Ref
    box = [T(5 + dx, 5 + dy, 1) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    # The failed Move's Bump/Enter log and dir depend on the random pick: record r and loc only
    mv("step_rand", box + [O("A", d=1)], "step_rand(A)", "list(r, movement_n(A.loc))")
    mv("step_rand", box + [O("A", d=1)], "step_rand(A, 8)", "list(r, movement_n(A.loc))")
    mv("step_rand", [O("A", "null")], "step_rand(A)")
    mv("step_rand", [O("B", 5, 5), O("A", "B")], "step_rand(A)", "movement_out(r, A, B)")
    for r in REFS:
        mv("step_rand.ref", [], f"step_rand({r})", "r")


def pixel(s, mv):
    A = O("A")
    rd = "list(A.step_size, A.step_x, A.step_y, A.bound_x, A.bound_y, A.bound_width, A.bound_height, A.locs, A.bounds)"
    mv("pixel.defaults", [P("A")], "1", rd)
    mv("pixel.defaults", [P("A", kind="/mob")], "1", rd)
    mv("pixel.defaults", [P("A", "null")], "1", rd)
    mv("pixel.defaults", [P("B"), P("A", "B")], "1", rd)
    mv("pixel.defaults", [P("A")], "1", "list(initial(A.step_size), initial(A.step_x), initial(A.bound_width), initial(A.bound_height))")
    after = "list(r, movement_log.Copy(), movement_pos(A), movement_xyz(A), A.locs, movement_c(5, 5), movement_c(6, 5), movement_c(4, 5))"
    after_y = "list(r, movement_log.Copy(), movement_pos(A), movement_xyz(A), A.locs, movement_c(5, 5), movement_c(5, 6), movement_c(5, 4))"
    sv = ["0", "5", "16", "31", "32", "40", "64", "-1", "-32", "-40", "2.5", "null", '"x"', "-0.5"]
    for v in sv:
        mv("step_x=", TT + [A], f"(A.step_x = {v})", after)
        mv("step_y=", TT + [A], f"(A.step_y = {v})", after_y)
    mv("step_x=", [O("A", 20, 5)], "(A.step_x = 16)", after)
    mv("step_x=", [O("A", 1, 5)], "(A.step_x = -16)", after)
    mv("step_x=", [O("B", 5, 5), O("A", "B")], "(A.step_x = 16)", "list(r, A.step_x, A.locs)")
    mv("step_x=", [A, "A.bound_width = 16"], "(A.step_x = 16)", after)
    mv("step_x=", [A, "A.bound_width = 16"], "(A.step_x = 17)", after)
    for var in ("bound_width", "bound_height", "bound_x", "bound_y"):
        for v in ["0", "1", "16", "32", "33", "64", "100", "-1", "-16", "2.5", "null", '"x"']:
            mv(f"{var}=", [A], f"(A.{var} = {v})",
               f"list(r, A.{var}, A.locs, movement_c(5, 5), movement_c(6, 5), movement_c(5, 6), movement_c(4, 5), movement_c(5, 4), movement_c(6, 6))")
    for v in ["0", "1", "8", "16", "32", "64", "-8", "0.5", "null", '"x"']:
        mv("step_size=", [A], f"(A.step_size = {v})", "list(r, A.step_size)")
    mv("bounds", [A, "A.bound_width = 64", "A.bound_height = 48"], "A.bounds", "list(r, A.locs)")
    mv("bounds", [A, "A.step_x = 8", "A.bound_x = 4"], "A.bounds", "list(r, A.locs)")
    # Slides inside one turf: no Enter/Exit at all
    small = [T(5, 5), T(6, 5), O("A"), "A.bound_width = 16", "A.bound_height = 16"]
    mv("Move.slide", small, f"A.Move({L55}, 0, 8, 0)")
    mv("Move.slide", small, f"A.Move({L55}, 0, 16, 16)")
    mv("Move.slide", small, f"A.Move({L55}, EAST, 8, 0)")
    mv("Move.slide", small, f"A.Move({L55}, 0, 0, 0)")
    mv("Move.slide", small, f"A.Move({L55}, 0, 20, 0)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small, "step(A, EAST, 8)")
    mv("Move.slide", small + ["A.step_x = 8"], "step(A, EAST, 16)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small + ["A.step_x = 8"], "step(A, EAST, 32)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small + ["A.step_x = 8"], "step(A, WEST, 16)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small + ["A.step_size = 4"], "list(step(A, EAST), step(A, EAST), step(A, NORTH))")
    mv("Move.slide", small, f"A.Move({L65}, 0, 0, 0)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small, f"A.Move({L65}, 0, -8, 0)", "movement_out(r, A) + list(A.locs)")
    mv("Move.slide", small, f"A.Move({L65}, 0, 40, 0)", "movement_out(r, A) + list(A.locs)")
    # Partial slides stopped by a dense turf
    dsmall = [T(5, 5), T(6, 5, 1), O("A", d=1), "A.bound_width = 16", "A.bound_height = 16", "A.step_x = 8"]
    mv("Move.partial", dsmall, "step(A, EAST, 16)")
    mv("Move.partial", dsmall, "step(A, EAST, 4)")
    mv("Move.partial", dsmall, "step(A, EAST, 8)")
    mv("Move.partial", dsmall, f"A.Move({L55}, 0, 16, 0)")
    mv("Move.partial", dsmall, f"A.Move({L55}, 0, 12, 4)")
    mv("Move.partial", dsmall, f"A.Move({L65}, 0, 0, 0)")
    mv("Move.partial", dsmall, "step(A, NORTHEAST, 16)")
    mv("Move.partial", [T(5, 5), T(6, 5, 1), O("A", d=1)], f"A.Move({L55}, 0, 16, 0)")
    mv("Move.partial", [T(5, 5), T(6, 5, 1), O("A", d=1)], "step(A, EAST, 8)")
    # Crossing small objs
    smallB = [O("B", 6, 5), "B.bound_width = 8", "B.bound_height = 8", "B.step_x = 4", "B.step_y = 4"]
    mv("Move.cross", small + ["A.step_x = 8"] + smallB, "step(A, EAST, 16)", "movement_out(r, A, B)")
    mv("Move.cross", small + ["A.step_x = 8"] + smallB, "list(step(A, EAST, 16), step(A, EAST, 16))", "movement_out(r, A, B)")
    mv("Move.cross", small + ["A.step_x = 8", "A.density = 1"] + smallB + ["B.density = 1"], "step(A, EAST, 16)",
       "movement_out(r, A, B)")
    mv("Move.cross", small + ["A.step_x = 8", "A.density = 1"] + smallB + ["B.density = 1"], f"A.Move({L65}, 0, 4, 4)",
       "movement_out(r, A, B)")
    mv("Move.cross", small + ["A.step_x = 8"] + [O("B", 6, 5)], "step(A, EAST, 16)", "movement_out(r, A, B)")
    mv("Move.cross", small + ["A.step_x = 8", "A.density = 1"] + [O("B", 6, 5, 1)], "step(A, EAST, 16)",
       "movement_out(r, A, B)")
    mv("Move.cross", small + [O("B", 5, 5), "B.bound_width = 8", "B.step_x = 20"], f"A.Move({L55}, 0, 12, 0)",
       "movement_out(r, A, B)")
    mv("Move.cross", small + [O("B", 5, 5), "B.bound_width = 8", "B.step_x = 20", "A.step_x = 12"], f"A.Move({L55}, 0, 0, 0)",
       "movement_out(r, A, B)")
    # Dense small obj ahead on the same turf: Bump, partial move
    mv("Move.bump", small + ["A.density = 1", O("B", 5, 5, 1), "B.bound_width = 8", "B.step_x = 24"], "step(A, EAST, 16)",
       "movement_out(r, A, B)")
    # Overhanging dense obj from the next turf blocks a full-tile mover
    mv("Move.bump", TT + [O("A", d=1), O("B", 7, 5, 1), "B.step_x = -16"], f"A.Move({L65})", "movement_out(r, A, B) + list(B.locs)")
    # Multi-tile movers entering several turfs
    nine = [T(x, y) for x in (5, 6, 7) for y in (5, 6, 7)]
    mv("Move.big", nine + [O("A"), "A.bound_width = 64", "A.bound_height = 64"], "A.Move(locate(6, 6, 1))",
       "movement_out(r, A) + list(A.locs)")
    mv("Move.big", nine + [O("A"), "A.bound_width = 64", "A.bound_height = 64"], "step(A, NORTHEAST)",
       "movement_out(r, A) + list(A.locs)")
    mv("Move.big", nine + [O("A"), "A.bound_width = 64", "A.bound_height = 64"], "step(A, EAST, 8)",
       "movement_out(r, A) + list(A.locs)")
    mv("Move.big", nine + [O("A", d=1), "A.bound_width = 64", "A.bound_height = 64", T(7, 6, 1)], "step(A, EAST)",
       "movement_out(r, A) + list(A.locs)")
    mv("Move.big", [O("A", 19, 5), "A.bound_width = 64"], "A.locs", "list(r, movement_c(20, 5))")
    mv("Move.big", [O("A", 19, 5), "A.bound_width = 64"], "step(A, EAST)", "movement_out(r, A) + list(A.locs)")
    mv("Move.big", [O("A", 20, 5)], "(A.bound_width = 64)", "list(r, A.locs, movement_pos(A))")
    # pixel_x is visual only
    mv("pixel_x", [A], "(A.pixel_x = 40)", "list(r, A.locs, movement_c(6, 5), A.step_x)")
    mv("pixel_x", [A], "(A.pixel_w = 40)", "list(r, A.locs, movement_c(6, 5), A.step_x)")
    # step_x read back through vars and after a slide into the next turf
    mv("step_x", small + ["A.step_x = 8"], "step(A, EAST, 24)", "list(r, A.vars[\"step_x\"], A.x, A.locs)")
    mv("world.movement_mode", [], "world.movement_mode", "r")


EXTRA_DM = r'''// Logs the arguments the step procs pass to Move()
/obj/movement_o/movement_margs
	Move(NewLoc, Dir, sx, sy)
		movement_L("Move([movement_n(NewLoc)],[movement_n(Dir)],[movement_n(sx)],[movement_n(sy)])")
		return ..()

// Move() that never moves and returns movement_ret
/obj/movement_o/movement_mret
	var/movement_ret = null
	Move(NewLoc, Dir)
		movement_L("Move([movement_n(NewLoc)],[movement_n(Dir)])")
		return movement_ret

// Re-entrant movement from inside hooks
/turf/movement_t/movement_reenter
	Entered(atom/movable/O, atom/oldloc)
		..()
		if(O.name == "A")
			movement_L("nested=[O.Move(locate(7, 5, 1))]")

/turf/movement_t/movement_enterdel
	Entered(atom/movable/O, atom/oldloc)
		..()
		if(O.name == "A")
			del O

/turf/movement_t/movement_crossdel
	Crossed(atom/movable/O)
		..()
		if(O.name == "A")
			del O

/obj/movement_o/movement_crossdel
	Crossed(atom/movable/O)
		..()
		if(O.name == "A")
			del O

/obj/movement_o/movement_crossmove
	Crossed(atom/movable/O)
		..()
		if(O.name == "A")
			movement_L("nested=[O.Move(locate(7, 5, 1))]")'''


def gaps(mv):
    L75 = "locate(7, 5, 1)"
    go = f"A.Move({L65})"
    A = O("A")
    Ad = O("A", d=1)
    big = "movement_out(r, A) + list(A.locs)"

    # step_to gives up beyond 2 * world.view steps
    for x, y in [(5, 19), (5, 20), (20, 20), (15, 5), (16, 5), (5, 14)]:
        mv("step_to.far", [A, P("B", x, y)], "step_to(A, B)", "movement_out(r, A) + list(world.view)")
        mv("step_towards.far", [A, P("B", x, y)], "step_towards(A, B)", "movement_out(r, A) + list(world.view)")
        mv("step_away.far", [A, P("B", x, y)], "step_away(A, B, 30)", "movement_out(r, A) + list(world.view)")

    # Bump default action: swap with a mob whose group holds src (full-tile movers only)
    MA = O("A", kind="/mob/movement_m", d=1)
    MB = O("B", 6, 5, 1, "/mob/movement_m")
    ab = "movement_out(r, A, B)"
    mv("Bump.group", TT + [MA, MB, "A:group += B"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A"], go, ab)
    mv("Bump.group", TT + [MA, MB, "A:group += B", "B:group += A"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A"], "step(A, EAST)", ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", "A.step_size = 8"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", "A.step_size = 8"], "step(A, EAST)", ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", "B.step_size = 8"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", "A.step_x = 8"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", "A.bound_width = 16"], go, ab)
    mv("Bump.group", TT + [MA, O("B", 6, 5, 0, "/mob/movement_m"), "B:group += A"], go, ab)
    mv("Bump.group", TT + [MA, O("B", 6, 5, 1, "/obj/movement_o")], go, ab)
    mv("Bump.group", TT + [O("A", d=1), MB, "B:group += A"], go, ab)
    mv("Bump.group", [T(5, 5), T(6, 5, 1), MA, MB, "B:group += A"], go, ab)
    mv("Bump.group", TT + [MA, MB, "B:group += A", O("C", 5, 5, 1)], go, "movement_out(r, A, B, C)")
    mv("Bump.group", TT + [MA, MB, "B:group += A"], "A.Bump(B)", ab)
    mv("Bump.group", TT + [MA, O("B", 7, 5, 1, "/mob/movement_m"), "B:group += A"], "A.Bump(B)", ab)

    # What the step procs pass to Move()
    MG = O("A", kind="/obj/movement_o/movement_margs")
    for call in ["step(A, EAST)", "step(A, EAST, 8)", "step(A, EAST, 0)", "step(A, vector(8, 0))",
                 "step(A, vector(32, 0))", "step(A, 0)"]:
        mv("step.args", [MG], call)
    mv("step.args", [MG, "A.step_size = 8"], "step(A, EAST)")
    mv("step.args", [MG, "A.bound_width = 16", "A.bound_height = 16"], "step(A, EAST, 8)")
    for call in ["step_to(A, B)", "step_to(A, B, 0, 8)", "step_towards(A, B)", "step_towards(A, B, 8)",
                 "step_away(A, B)", "step_away(A, B, 5, 8)"]:
        mv("step.args", [MG, P("B", 8, 6)], call)
    mv("step.args", [O("A", 5, 5, 1, "/obj/movement_o/movement_margs"), T(6, 5, 1), P("B", 8, 5)], "step_to(A, B)")

    # Do the step procs return Move()'s raw return value?
    MR = O("A", kind="/obj/movement_o/movement_mret")
    for ret in ["5", '"x"', "null", "0", "-3", "2.5", "list()"]:
        for call in ["step(A, EAST)", "step_to(A, B)", "step_towards(A, B)", "step_away(A, B)", "step(A, vector(8, 0))"]:
            mv("step.ret", [MR, f"A:movement_ret = {ret}", P("B", 8, 5)], call, "list(r, movement_log.Copy())")
    small = [T(5, 5), T(6, 5), O("A"), "A.bound_width = 16", "A.bound_height = 16"]
    mv("step.ret", small, "list(step(A, EAST, 8), A.Move(locate(5, 5, 1), 0, 16, 0))", "list(r, A.step_x)")
    mv("step.ret", small, "step(A, EAST, 8)", "list(r, A.step_x)")
    mv("step.ret", small, "step(A, EAST, 3)", "list(r, A.step_x)")
    mv("step.ret", small + ["A.step_x = 8"], "step(A, EAST, 16)", "list(r, A.step_x, A.x)")
    mv("step.ret", small + ["A.step_size = 8"], "step_towards(A, locate(9, 5, 1))", "list(r, A.step_x)")
    mv("step.ret", small + ["A.step_size = 8"], "step_to(A, locate(9, 5, 1))", "list(r, A.step_x)")
    mv("step.ret", small + ["A.step_size = 8"], "step_away(A, locate(1, 5, 1))", "list(r, A.step_x)")

    # Slide vs jump with step_size above a tile
    three = [T(5, 5), T(6, 5), T(7, 5), T(8, 5)]
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], f"A.Move({L75})", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], "A.Move(locate(8, 5, 1))", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], "A.Move(locate(7, 6, 1))", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], "step(A, EAST)", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], "step(A, EAST, 64)", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 48"], f"A.Move({L75})", big)
    mv("Move.slide64", three + [O("A"), "A.step_size = 64"], f"A.Move({L75}, 0, 8, 0)", big)
    mv("Move.slide64", [T(5, 5), T(6, 5, 1), T(7, 5), O("A", d=1), "A.step_size = 64"], f"A.Move({L75})", big)
    mv("Move.slide64", [T(5, 5), T(6, 5), T(7, 5, 1), O("A", d=1), "A.step_size = 64"], f"A.Move({L75})", big)
    mv("Move.slide64", three + [O("A", d=1), "A.step_size = 64", O("B", 7, 5, 1)], f"A.Move({L75})",
       "movement_out(r, A, B) + list(A.locs)")

    # Re-entrant movement from inside hooks
    RE = "/turf/movement_t/movement_reenter"
    mv("Move.reenter", [T(5, 5), T(6, 5, kind=RE), T(7, 5), A], go)
    mv("Move.reenter", [T(5, 5), T(6, 5, kind=RE), T(7, 5), A, O("B", 6, 5)], go, "movement_out(r, A, B)")
    mv("Move.reenter", [T(5, 5), T(6, 5, kind=RE), T(7, 5, 1), Ad], go)
    mv("Move.reenter", [T(5, 5), T(6, 5, kind=RE), T(7, 5), A], "step(A, EAST)")
    mv("Move.reenter", [T(5, 5), T(6, 5), T(7, 5), A, O("B", 6, 5, kind="/obj/movement_o/movement_crossmove"),
                        O("C", 6, 5)], go, "movement_out(r, A, B, C)")
    mv("Move.reenter", [T(5, 5), T(6, 5, kind="/turf/movement_t/movement_enterdel"), A, O("B", 6, 5)], go,
       "movement_out(r, A, B)")
    mv("Move.reenter", [T(5, 5), T(6, 5, kind="/turf/movement_t/movement_crossdel"), A, O("B", 6, 5)], go,
       "movement_out(r, A, B)")
    mv("Move.reenter", [T(5, 5), T(6, 5), A, O("B", 6, 5, kind="/obj/movement_o/movement_crossdel"), O("C", 6, 5)],
       go, "movement_out(r, A, B, C)")
    mv("Move.reenter", [T(5, 5), T(6, 5, kind="/turf/movement_t/movement_enterdel"), A], "step(A, EAST)")
    mv("Move.reenter", [T(5, 5), T(6, 5, kind=RE), T(7, 5), A, "A.loc = locate(6, 5, 1)"], go)

    # Siblings inside a container are not Uncrossed
    inB = TT + [O("B", 5, 5), O("A", "B")]
    abc = "movement_out(r, A, B, C)"
    mv("Move.container", inB + [O("C", "B")], go, abc)
    mv("Move.container", inB + [O("C", "B", force=F(Uncross=0))], go, abc)
    mv("Move.container", inB + [O("C", "B", 1, force=F(Uncross=0))], go, abc)
    mv("Move.container", inB + [O("C", "B", force=F(Cross=0))], "A.Move(B)", abc)
    mv("Move.container", TT + [A, O("B", 5, 5), O("C", "B", 1)], "A.Move(B)", abc)
    mv("Move.container", TT + [O("B", 5, 5), O("A", "B", 1), O("C", "B", 1)], go, abc)

    # Container <-> turf with a logging area
    mv("Move.container", inB + ["movement_area(6, 5)", "movement_area(5, 5)"], go, ab)
    mv("Move.container", inB + ["movement_area(6, 5)"], go, ab)
    mv("Move.container", inB + ["movement_area(5, 5)"], go, ab)
    mv("Move.container", inB + [f"movement_area(6, 5, {F(Enter=0)})"], go, ab)
    mv("Move.container", TT + [A, O("B", 5, 5), "movement_area(5, 5)"], "A.Move(B)", ab)
    mv("Move.container", TT + [A, O("B", 5, 5), f"movement_area(5, 5, {F(Exit=0)})"], "A.Move(B)", ab)
    mv("Move.container", TT + [A, O("B", 6, 5), "movement_area(5, 5)", "movement_area(6, 5)"], "A.Move(B)", ab)

    # Area density
    for ad in ("1", "0"):
        mv("Move.area_density", TT + [O("A"), f"A.density = {ad}", "var/area/R = movement_area(6, 5)", "R.density = 1"],
           go, "movement_out(r, A) + list(R.density)")
    mv("Move.area_density", TT + [Ad, f"var/area/R = movement_area(6, 5, {F(Enter=1)})", "R.density = 1"], go)
    mv("Move.area_density", TT + [Ad, "var/area/R = movement_area(5, 5)", "R.density = 1"], go)
    mv("Move.area_density", TT + [Ad, "var/area/R = movement_area(6, 5)", "R.density = 1"], "step(A, EAST)")

    # x/y/z assignment onto blocked turfs bypasses density
    mv("xyz=", [T(5, 5), T(6, 5, 1), Ad, O("B", 6, 5, 1)], "(A.x = 6)",
       "list(r, movement_log.Copy(), movement_pos(A), movement_pos(B), movement_xyz(A))")
    mv("xyz=", [T(5, 5), T(6, 5), A, "A.bound_width = 64"], "(A.x = 6)",
       "list(r, movement_log.Copy(), movement_pos(A), A.locs, movement_c(5, 5), movement_c(6, 5), movement_c(7, 5))")
    mv("xyz=", TT + [A, "A.step_x = 8", "A.step_y = 4"], "(A.x = 6)",
       "list(r, movement_log.Copy(), movement_pos(A), A.locs)")
    mv("xyz=", TT + [A, "A.step_x = 8"], "(A.z = 2)", "list(r, movement_log.Copy(), movement_pos(A), A.locs)")
    mv("xyz=", TT + [A, "A.step_x = 8"], f"(A.loc = {L65})", "list(r, movement_log.Copy(), movement_pos(A), A.locs)")

    # locs is read-only
    lo = "list(r, A.locs, movement_c(6, 5), movement_pos(A))"
    mv("locs=", TT + [A], f"(A.locs = list({L65}))", lo)
    mv("locs=", TT + [A], f"(A.locs += {L65})", lo)
    mv("locs=", TT + [A], "(A.locs = null)", lo)
    mv("locs=", TT + [A], f"A.locs.Add({L65})", lo)
    mv("locs=", TT + [A], "A.locs.Cut()", lo)

    # TILE_MOVER keeps the atom on the grid
    tm = [T(5, 5), T(6, 5), O("A"), "A.appearance_flags = TILE_MOVER"]
    for call in ["step(A, EAST, 8)", f"A.Move({L55}, 0, 8, 0)", "(A.step_x = 8)", "step(A, EAST)",
                 f"A.Move({L65}, 0, 8, 0)", "(A.step_y = -8)", "step(A, vector(8, 0))"]:
        mv("TILE_MOVER", tm, call, big)
    mv("TILE_MOVER", tm + ["A.step_size = 8"], "step(A, EAST)", big)
    mv("TILE_MOVER", [T(5, 5), T(6, 5), O("A"), "A.step_x = 8"], "(A.appearance_flags = TILE_MOVER)", big)
    mv("TILE_MOVER", [T(5, 5), T(6, 5), O("A"), "A.bound_width = 16"], "(A.appearance_flags = TILE_MOVER)",
       "list(r, A.bound_width, A.bound_height, A.locs)")

    # Move with step offsets to non-turf / cross-z destinations
    mv("Move.offsets", TT + [A, O("B", 9, 9)], "A.Move(B, 0, 8, 8)", ab)
    mv("Move.offsets", TT + [A, O("B", 9, 9), "A.step_x = 8"], "A.Move(B)", ab)
    mv("Move.offsets", TT + [A, T(6, 5, z=2)], "A.Move(locate(6, 5, 2), 0, 8, 0)", big)
    mv("Move.offsets", TT + [A, T(5, 5, z=2)], "A.Move(locate(5, 5, 2), 0, 0, 12)", big)
    mv("Move.offsets", inB, f"A.Move({L55}, 0, 8, 0)", "movement_out(r, A, B) + list(A.locs)")
    mv("Move.offsets", inB, "A.Move(locate(6, 5, 2), 0, 8, 0)", "movement_out(r, A, B) + list(A.locs)")
    mv("Move.offsets", inB, f"A.Move({L65}, 0, -8, 4)", "movement_out(r, A, B) + list(A.locs)")
    mv("Move.offsets", TT + [O("A", "null")], f"A.Move({L65}, 0, 8, 0)", big)

    # Failed Move with a Dir argument: is dir changed?
    mv("Move.dir", [T(5, 5, force=F(Exit=0)), T(6, 5), A, "A.dir = WEST"], f"A.Move({L65}, NORTH)")
    mv("Move.dir", [T(5, 5, force=F(Uncross=0)), T(6, 5), A, "A.dir = WEST"], f"A.Move({L65}, NORTH)")
    mv("Move.dir", TT + [A, O("B", 5, 5, force=F(Uncross=0)), "A.dir = WEST"], f"A.Move({L65}, NORTH)", ab)
    mv("Move.dir", [T(5, 5), T(6, 5, force=F(Enter=0)), A, "A.dir = WEST"], f"A.Move({L65}, NORTH)")
    mv("Move.dir", [T(5, 5, force=F(Exit=0)), T(6, 5), A, "A.dir = WEST"], f"A.Move({L65})")
    mv("Move.dir", [T(5, 5, force=F(Exit=0)), T(6, 5), A, "A.dir = WEST"], "step(A, NORTH)")
    mv("Move.dir", [A, f"movement_area(5, 5, {F(Exit=0)})", "A.dir = WEST"], f"A.Move({L65}, NORTH)")
    mv("Move.dir", TT + [O("B", 5, 5, force=F(Exit=0)), O("A", "B"), "A.dir = WEST"], f"A.Move({L65}, NORTH)", ab)
