"""overlays / underlays on /obj, /mob, /turf, /image and /mutable_appearance, plus vis_contents, verbs
and contents list manipulation.

Every mutating statement runs inside a local try/catch, so a case records "ok"/"ERR" for the
operation and then the state it left behind: list(op result, state). Overlay entries can't be printed
by parity_canon (they are appearances), so overlays_list() prints "len=N: {...} {...}" where each
entry shows icon (file name, or a pixel hash for dynamic icons), icon_state, layer, plane, dir, name,
pixel_x/y, alpha, color, invisibility and its own overlays/underlays (one level deep).

BYOND reference (info.html /atom/var/overlays, underlays, vis_contents, vis_locs, verbs, contents,
/image, /mutable_appearance):
- overlays accept icons, icon states (text), objects and object types; an object/image becomes a
  static snapshot: later changes to it don't change the overlay. The snapshot keeps the object's
  layer, icon-state overlays use FLOAT_LAYER (-1). An empty icon is inherited from the owner at
  render time. +=, -=, Add, Remove and Cut work normally; items "may not be directly accessed".
- underlays are the same as overlays, processed first.
- mutable_appearance.overlays is a temporary normal list that can be modified easily.
- vis_contents: only turfs and movable atoms; vis_locs is the reverse list.
- verbs: starts as the prototype's verbs; procs can be added and removed at runtime.
- contents: only movables (except areas); contents += obj moves it.

OpenDream targets (DreamList.cs DreamOverlaysList / DreamVisContentsList / VerbsList /
MovableContentsList, DreamObjectImage.cs, DreamObjectAtom.cs, AtomManager.TryCreateAppearanceFrom):
- invalid overlay values (null, numbers, datums) become MutableAppearance.Default and are still added.
- text icon states copy the owner's icon at add time (BYOND leaves icon empty), so -= after the
  owner's icon changes may miss.
- overlays.Find() throws NotImplementedException; overlays[i] = x errors; ContainsValue ('in') is the
  base list's (always false).
- reading overlays gives mutable copies of the appearances.
- vis_contents silently ignores duplicates and null, errors on anything else non-atom.
- verbs += an already present verb is a no-op; Cut/Remove behaviour.
- MovableContentsList.Cut() is a TODO (does nothing); -= a non-member is silent; += non-movable errors.
- /image declares verbs/contents in OD but not in BYOND (compile-time parity points).
"""
from pools import ANY

OV_VARS = ["icon_state", "layer", "plane", "dir", "name", "pixel_x", "pixel_y", "alpha", "color", "invisibility"]


def _helpers():
    d = []
    d.append(r'''var/global/list/overlays_events = list()

/obj/overlays_base
	name = "base"
	icon = 'test.dmi'
	icon_state = "solid"

/obj/overlays_thing
	name = "thing"
	icon = 'test.dmi'
	icon_state = "grad"
	layer = 5
	dir = EAST
	pixel_x = 3

/obj/overlays_plain
	name = "plain"

/obj/overlays_box
	name = "box"

/obj/overlays_box/Entered(atom/movable/M, atom/OldLoc)
	overlays_events += "Entered [M.name] from [OldLoc ? OldLoc.name : "null"]"

/obj/overlays_box/Exited(atom/movable/M, atom/NewLoc)
	overlays_events += "Exited [M.name] to [NewLoc ? NewLoc.name : "null"]"

/obj/overlays_box/Enter(atom/movable/M)
	overlays_events += "Enter [M.name]"
	return ..()

/obj/overlays_box/Exit(atom/movable/M)
	overlays_events += "Exit [M.name]"
	return ..()

/mob/overlays_mob
	name = "mobby"
	icon = 'test.dmi'
	icon_state = "checker"

/mob/overlays_mob/verb/overlays_mv()
	set name = "mobverb"
	return 1

/obj/overlays_vobj
	name = "vobj"

/obj/overlays_vobj/verb/overlays_v1()
	return 1

/obj/overlays_vobj/verb/overlays_v2()
	set name = "Second Verb"
	return 2

/obj/overlays_vobj/proc/overlays_p1()
	return 3

/obj/proc/overlays_op()
	return 4

/proc/overlays_gp()
	return 5

/proc/overlays_ma(state = "half", layer = 7)
	var/mutable_appearance/M = new /mutable_appearance
	M.icon = 'test.dmi'
	M.icon_state = state
	M.layer = layer
	M.name = "ma"
	return M

/proc/overlays_img(state = "alpha", layer = FLOAT_LAYER)
	var/image/I = image('test.dmi', state)
	I.layer = layer
	I.name = "img"
	return I

/proc/overlays_icon(i)
	if(isnull(i))
		return "null"
	if(istext(i) || isnum(i))
		return parity_canon(i)
	var/t = "[i]"
	if(length(t) > 4 && copytext(t, -4) == ".dmi")
		return "f:[t]"
	try
		return parity_icon(icon(i))
	catch
		return "icon?"

// Plain list of an overlays-like list, for loops that must not change the original
/proc/overlays_items(L)
	var/list/R = list()
	for(var/x in L)
		R += list(x)
	return R

/proc/overlays_list(L, depth = 0)
	if(isnull(L))
		return "null"
	if(!islist(L))
		return "notlist:[parity_canon(L)]"
	var/list/LL = L
	var/n
	try
		n = LL.len
	catch
		n = "ERR"
	var/list/parts = list()
	try
		for(var/x in LL)
			parts += overlays_d(x, depth)
	catch
		parts += "iterERR"
	return "len=[n]: [jointext(parts, " ")]"

/proc/overlays_vis(A)
	var/list/R = list()
	try
		R["len"] = A:vis_contents:len
	catch
		R["len"] = "ERR"
	try
		R["items"] = overlays_items(A:vis_contents)
	catch
		R["items"] = "ERR"
	return R

/proc/overlays_verbs(L)
	if(!islist(L))
		return parity_canon(L)
	var/list/LL = L
	var/list/R = list()
	for(var/v in LL)
		R += "[v]"
	return list("len" = LL.len, "items" = R)

/proc/overlays_locs(list/objs)
	var/list/R = list()
	for(var/atom/movable/M in objs)
		R += "[M.name]@[M.loc ? M.loc.name : "null"]"
	return R
''')
    # overlays_d: one overlay entry, var by var, each guarded so one missing var doesn't hide the rest
    lines = ["/proc/overlays_d(x, depth = 0)",
             "\tif(isnull(x) || isnum(x) || istext(x) || ispath(x) || islist(x))",
             "\t\treturn parity_canon(x)",
             "\tvar/list/p = list()",
             "\ttry",
             "\t\tp += \"icon=[overlays_icon(x:icon)]\"",
             "\tcatch",
             "\t\tp += \"icon=ERR\""]
    for v in OV_VARS:
        lines += ["\ttry",
                  f"\t\tp += \"{v}=[parity_canon(x:{v})]\"",
                  "\tcatch",
                  f"\t\tp += \"{v}=ERR\""]
    lines += ["\tif(depth < 1)",
              "\t\ttry",
              "\t\t\tp += \"ov=([overlays_list(x:overlays, depth + 1)])\"",
              "\t\tcatch",
              "\t\t\tp += \"ov=ERR\"",
              "\t\ttry",
              "\t\t\tp += \"un=([overlays_list(x:underlays, depth + 1)])\"",
              "\t\tcatch",
              "\t\t\tp += \"un=ERR\"",
              "\treturn \"{[jointext(p, \" \")]}\""]
    d.append("\n".join(lines))
    return "\n\n".join(d)


def guard(stmt, var="__op"):
    """stmt inside a try/catch that sets var to "ok" or "ERR"."""
    out = ["try"]
    for l in stmt if isinstance(stmt, list) else [stmt]:
        out.append("\t" + l)
    out += [f"\t{var} = \"ok\"", "catch", f"\t{var} = \"ERR\""]
    return out


def guarded(*stmts):
    """Each statement guarded separately; the result names list them in order."""
    lines = []
    names = []
    for i, st in enumerate(stmts):
        n = f"__op{i}"
        lines.append(f"var/{n}")
        lines += guard(st, n)
        names.append(n)
    return lines, names


# ---------- targets for overlays ----------
OV_TARGETS = {
    "obj": ["var/obj/overlays_base/A = parity_track(new /obj/overlays_base(locate(2, 2, 1)))"],
    "image": ["var/image/A = image('test.dmi', \"solid\")"],
    "ma": ["var/mutable_appearance/A = new /mutable_appearance", "A.icon = 'test.dmi'", "A.icon_state = \"solid\""],
    "obj_noicon": ["var/obj/overlays_plain/A = parity_track(new /obj/overlays_plain(locate(2, 2, 1)))"],
    "mob": ["var/mob/overlays_mob/A = parity_track(new /mob/overlays_mob(locate(2, 2, 1)))"],
    "obj_nullloc": ["var/obj/overlays_base/A = parity_track(new /obj/overlays_base)"],
}

# ---------- overlay values ----------
OV_VALUES = [
    '"solid"', '"grad"', '""', '"nonexistent"', '"Solid"',
    "'test.dmi'", "'small.dmi'", "'rect.dmi'",
    "icon('test.dmi', \"grad\")", "new /icon('small.dmi')", "icon('test.dmi', \"dirs4\", EAST)",
    "/obj/overlays_thing", "/obj", "/mob/overlays_mob", "/datum", "/image", "/turf", "/area",
    "image('test.dmi', \"half\")", "image('test.dmi', icon_state = \"alpha\", layer = 5)",
    "image(icon = 'test.dmi', icon_state = \"checker\", dir = EAST)", "image(\"anim\")", "new /image",
    "overlays_ma()", "new /mutable_appearance",
    "parity_track(new /obj/overlays_thing)", "parity_track(new /obj/overlays_plain)",
    "parity_track(new /mob/overlays_mob)", "locate(3, 3, 1)",
    'list("solid", "grad")', "list()", 'list("solid", "solid")', 'list("solid" = 1)',
    "list(list(\"grad\"))", "list(image('test.dmi', \"half\"), /obj/overlays_thing, 'small.dmi')",
    "null", "0", "1", "-1", "1.5", "PINF", "NAN", "new /datum", "matrix()",
]
OV_VALUES_S = ['"grad"', "'small.dmi'", "/obj/overlays_thing", "image('test.dmi', \"half\")", "overlays_ma()",
               "parity_track(new /obj/overlays_thing)", 'list("solid", "grad")', "null", "1", "new /datum"]

FULL_OPS = ("add", "under", "addproc", "assign", "dup", "addrem", "addrem_fresh", "remmiss", "removeproc")
TARGET_OPS = {
    "obj": FULL_OPS,
    "image": FULL_OPS,
    "ma": FULL_OPS,
    "obj_noicon": ("add", "assign", "addrem"),
    "mob": ("add", "under"),
    "obj_nullloc": ("add",),
}


def ov_case(s, proc, setup, ops, result):
    lines, names = guarded(*ops)
    s.body(proc, setup + lines, f"list({', '.join(names + [result])})")


def build_overlays(s):
    ST = "overlays_list(A.overlays)"
    BOTH = "overlays_list(A.overlays), overlays_list(A.underlays)"
    for tname, setup in OV_TARGETS.items():
        ops = TARGET_OPS[tname]
        proc = f"overlays.{tname}"
        vals = OV_VALUES if len(ops) > 3 or tname == "obj_noicon" else OV_VALUES_S
        for X in vals:
            if "add" in ops:
                ov_case(s, proc + ".add", setup, ["A.overlays += " + X], ST)
            if "under" in ops:
                ov_case(s, proc + ".under", setup, ["A.underlays += " + X], BOTH)
            if "addproc" in ops:
                ov_case(s, proc + ".Add", setup, ["A.overlays.Add(" + X + ")"], ST)
            if "assign" in ops:
                ov_case(s, proc + ".assign", setup, ["A.overlays = " + X], ST)
            if "dup" in ops:
                ov_case(s, proc + ".dup", setup + ["var/v = " + X], ["A.overlays += v", "A.overlays += v"], ST)
            if "addrem" in ops:
                ov_case(s, proc + ".addrem", setup + ["var/v = " + X], ["A.overlays += v", "A.overlays -= v"], ST)
            if "addrem_fresh" in ops:
                ov_case(s, proc + ".addrem_fresh", setup, ["A.overlays += " + X, "A.overlays -= " + X], ST)
            if "remmiss" in ops:
                ov_case(s, proc + ".remmiss", setup, ['A.overlays += "asym"', "A.overlays -= " + X], ST)
            if "removeproc" in ops:
                lines = setup + ["var/v = " + X, "A.overlays += v", "var/__rv"] + guard("__rv = A.overlays.Remove(v)", "__ro")
                s.body(proc + ".Remove", ["var/__ro"] + lines, f"list(__ro, __rv, {ST})")

    # Generic sweep of the shared pool on an obj's overlays and an image's underlays
    for X in ANY:
        ov_case(s, "overlays.pool.obj", OV_TARGETS["obj"], ["A.overlays += " + X], ST)
        ov_case(s, "overlays.pool.image_under", OV_TARGETS["image"], ["A.underlays += " + X], "overlays_list(A.underlays)")
        ov_case(s, "overlays.pool.ma", OV_TARGETS["ma"], ["A.overlays += " + X], ST)

    O = OV_TARGETS["obj"]
    I = OV_TARGETS["image"]
    M = OV_TARGETS["ma"]
    # ---- list-ness and kinds of what reading gives ----
    for tn, setup in (("obj", O), ("image", I), ("ma", M)):
        p = f"overlays.kind.{tn}"
        s.body(p, setup, "list(islist(A.overlays), istype(A.overlays, /list), length(A.overlays), A.overlays.len)")
        s.body(p, setup, "A.overlays.type")
        s.body(p, setup, "A.underlays.type")
        s.body(p, setup, "A.overlays == A.overlays")
        s.body(p, setup, "A.overlays ~= list()")
        s.body(p, setup + ['A.overlays += "grad"'], 'list(istype(A.overlays[1], /image), istype(A.overlays[1], /mutable_appearance), istype(A.overlays[1], /datum), isicon(A.overlays[1]), istext(A.overlays[1]), isnull(A.overlays[1]))')
        s.body(p, setup + ['A.overlays += "grad"'], 'overlays_d(A.overlays[1])')
        s.body(p, setup + ['A.overlays += "grad"', 'var/x = A.overlays[1]'], 'x:type')
        s.body(p, setup + ['A.overlays += image(\'test.dmi\', "half")', 'var/x = A.overlays[1]'], 'x:type')
        s.body(p, setup + ['A.overlays += overlays_ma()', 'var/x = A.overlays[1]'], 'x:type')
        s.body(p, setup + ['A.overlays += "grad"'], 'A.overlays[1] == A.overlays[1]')
        s.body(p, setup + ['A.overlays += "grad"', 'A.overlays += "grad"'], 'A.overlays[1] == A.overlays[2]')
        s.body(p, setup + ['A.overlays += "grad"'], '"[A.overlays[1]]"')
        s.body(p, setup + ['A.overlays += "grad"', 'var/x = A.overlays[1]'], 'list(isicon(x:icon), isfile(x:icon), istext(x:icon))')
        s.body(p, setup + ['A.overlays += icon(\'test.dmi\', "grad")', 'var/x = A.overlays[1]'], 'list(isicon(x:icon), isfile(x:icon), istext(x:icon))')
        s.body(p, setup + ['A.overlays += "grad"', 'var/x = A.overlays[1]'], 'x:overlays')
        s.body(p, setup + ['A.overlays += "grad"'], 'A.overlays.Copy() ~= A.overlays')
        s.body(p, setup + ['A.overlays += "grad"'], 'overlays_list(A.overlays.Copy())')
        s.body(p, setup + ['A.overlays += "grad"', 'A.overlays += "half"'], 'overlays_list(A.overlays.Copy(2))')
        s.body(p, setup + ['A.overlays += "grad"', 'var/list/__c = A.overlays.Copy()'], 'overlays_d(__c[1])')

    # ---- index / list procs on overlays ----
    for tn, setup in (("obj", O), ("image", I), ("ma", M)):
        p = f"overlays.listops.{tn}"
        pre = setup + ['A.overlays += "grad"', 'A.overlays += image(\'test.dmi\', "half")', 'A.overlays += "alpha"']
        for idx in ("0", "1", "3", "4", "-1", '"grad"', "null", "1.5"):
            ov_case(s, p + ".index", pre + ["var/__x"], [f"__x = overlays_d(A.overlays[{idx}])"], "__x")
        ov_case(s, p + ".setindex", pre, ['A.overlays[1] = "asym"'], ST)
        ov_case(s, p + ".setindex_same", pre, ['A.overlays[1] = A.overlays[2]'], ST)
        for start, end in (("1", "0"), ("2", "0"), ("1", "2"), ("2", "3"), ("3", "4"), ("4", "0"), ("0", "0"), ("-1", "0"), ("1", "100")):
            ov_case(s, p + ".Cut", pre, [f"A.overlays.Cut({start}, {end})"], ST)
        ov_case(s, p + ".Cut", pre, ["A.overlays.Cut()"], ST)
        ov_case(s, p + ".Cut", pre + ["var/__x"], ["__x = A.overlays.Cut()"], "list(__x, " + ST + ")")
        ov_case(s, p + ".lenset", pre, ["A.overlays.len = 0"], ST)
        ov_case(s, p + ".lenset", pre, ["A.overlays.len = 1"], ST)
        ov_case(s, p + ".lenset", pre, ["A.overlays.len = 5"], ST)
        ov_case(s, p + ".lenset", pre, ["A.overlays.len--"], ST)
        for v in ('"grad"', '"asym"', 'image(\'test.dmi\', "half")', 'A.overlays[1]', "null", "1"):
            ov_case(s, p + ".Find", pre + ["var/__x"], [f"__x = A.overlays.Find({v})"], "__x")
            ov_case(s, p + ".in", pre + ["var/__x"], [f"__x = (({v}) in A.overlays)"], "__x")
        ov_case(s, p + ".Insert", pre + ["var/__x"], ['__x = A.overlays.Insert(1, "asym")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Insert", pre + ["var/__x"], ['__x = A.overlays.Insert(0, "asym")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Swap", pre, ["A.overlays.Swap(1, 3)"], ST)
        ov_case(s, p + ".Splice", pre, ['A.overlays.Splice(1, 2, "asym")'], ST)
        ov_case(s, p + ".RemoveAll", pre + ['A.overlays += "grad"', "var/__x"], ['__x = A.overlays.RemoveAll("grad")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Remove", pre + ['A.overlays += "grad"', "var/__x"], ['__x = A.overlays.Remove("grad")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Remove", pre + ["var/__x"], ['__x = A.overlays.Remove("grad", "alpha")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Remove", pre + ["var/__x"], ['__x = A.overlays.Remove("zz")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Add", pre + ["var/__x"], ['__x = A.overlays.Add("asym", "checker")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".Join", pre + ["var/__x"], ['__x = A.overlays.Join(",")'], "__x")
        ov_case(s, p + ".plus", pre + ["var/__x"], ['__x = overlays_list(A.overlays + "asym")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".minus", pre + ["var/__x"], ['__x = overlays_list(A.overlays - "grad")'], "list(__x, " + ST + ")")
        ov_case(s, p + ".or", pre, ['A.overlays |= "grad"'], ST)
        ov_case(s, p + ".or", pre, ['A.overlays |= "asym"'], ST)
        ov_case(s, p + ".and", pre, ['A.overlays &= list("grad")'], ST)
        ov_case(s, p + ".xor", pre, ['A.overlays ^= list("grad")'], ST)
        ov_case(s, p + ".self", pre, ["A.overlays += A.overlays"], ST)
        ov_case(s, p + ".self", pre, ["A.overlays -= A.overlays"], ST)
        ov_case(s, p + ".self", pre, ["A.overlays = A.overlays"], ST)
        ov_case(s, p + ".self", pre, ["A.overlays = A.underlays"], BOTH)
        ov_case(s, p + ".self", pre, ["A.underlays = A.overlays"], BOTH)
        ov_case(s, p + ".self", pre, ["A.underlays += A.overlays"], BOTH)
        ov_case(s, p + ".selfatom", setup, ["A.overlays += A"], ST)
        ov_case(s, p + ".ref", pre + ["var/list/L = A.overlays"], ['L += "asym"'], ST)
        ov_case(s, p + ".ref", pre + ["var/list/L = A.overlays"], ['A.overlays += "asym"'], "overlays_list(L)")
        ov_case(s, p + ".copy", pre + ["var/list/L = A.overlays.Copy()"], ['L += "asym"'], ST)
        ov_case(s, p + ".copy", pre + ["var/list/L = A.overlays.Copy()"], ['L += "asym"'], "overlays_list(L)")
        ov_case(s, p + ".copy", pre + ["var/list/L = A.overlays.Copy()"], ["A.overlays.Cut()"], "overlays_list(L)")
        ov_case(s, p + ".copy_back", pre + ["var/list/L = A.overlays.Copy()"], ["A.overlays.Cut()", "A.overlays += L"], ST)
        ov_case(s, p + ".copy_back", pre + ["var/list/L = A.overlays.Copy()"], ["A.overlays = L"], ST)
        ov_case(s, p + ".copy_back", pre + ["var/list/L = A.overlays.Copy()"], ["A.overlays -= L"], ST)
        ov_case(s, p + ".loop", pre + ["var/n = 0"], [["for(var/x in A.overlays)", "\tn++"]], "n")
        ov_case(s, p + ".loop_cut", pre + ["var/n = 0"], [["for(var/x in A.overlays)", "\tn++", "\tA.overlays.Cut()"]], "list(n, " + ST + ")")
        ov_case(s, p + ".loop_add", pre + ["var/n = 0"], [["for(var/x in A.overlays)", "\tn++", "\tif(n < 10)", "\t\tA.overlays += \"asym\""]], "list(n, " + ST + ")")
        ov_case(s, p + ".under_cut", pre + ['A.underlays += "asym"'], ["A.overlays.Cut()"], BOTH)
        ov_case(s, p + ".under_cut", pre + ['A.underlays += "asym"'], ["A.underlays.Cut()"], BOTH)
        ov_case(s, p + ".assign_null", pre, ["A.overlays = null"], ST)
        ov_case(s, p + ".assign_list", pre, ["A.overlays = list()"], ST)
        ov_case(s, p + ".len_after", pre, ['A.overlays += list("a", "b", "a")'], "A.overlays.len")

    # ---- snapshot semantics, layers, dirs, icon inheritance ----
    for tn, setup in (("obj", O), ("image", I), ("ma", M)):
        p = f"overlays.snapshot.{tn}"
        ov_case(s, p, setup + ["var/obj/overlays_thing/T = parity_track(new /obj/overlays_thing)"],
                ["A.overlays += T", 'T.icon_state = "half"', "T.layer = 9", "T.name = \"changed\""], ST)
        ov_case(s, p, setup + ["var/obj/overlays_thing/T = parity_track(new /obj/overlays_thing)"],
                ["A.overlays += T", 'T.icon_state = "half"', "A.overlays -= T"], ST)
        ov_case(s, p, setup + ["var/obj/overlays_thing/T = parity_track(new /obj/overlays_thing)"],
                ["A.overlays += T", 'T.icon_state = "half"', 'T.icon_state = "grad"', "A.overlays -= T"], ST)
        ov_case(s, p, setup + ['var/image/T = image(\'test.dmi\', "half")'],
                ["A.overlays += T", 'T.icon_state = "asym"', "T.pixel_x = 7"], ST)
        ov_case(s, p, setup + ['var/image/T = image(\'test.dmi\', "half")'],
                ["A.overlays += T", 'T.icon_state = "asym"', "A.overlays -= T"], ST)
        ov_case(s, p, setup + ["var/mutable_appearance/T = overlays_ma()"],
                ["A.overlays += T", 'T.icon_state = "asym"'], ST)
        ov_case(s, p, setup + ["var/mutable_appearance/T = overlays_ma()"],
                ["A.overlays += T", 'T.icon_state = "asym"', "A.overlays -= T"], ST)
        ov_case(s, p, setup + ['var/icon/T = icon(\'test.dmi\', "grad")'],
                ["A.overlays += T", "T.Flip(NORTH)"], ST)
        ov_case(s, p, setup + ['var/icon/T = icon(\'test.dmi\', "grad")'],
                ["A.overlays += T", "A.overlays -= T"], ST)
        ov_case(s, p, setup + ['var/icon/T = icon(\'test.dmi\', "grad")'],
                ["A.overlays += T", "T.Flip(NORTH)", "A.overlays -= T"], ST)
        ov_case(s, p, setup + ['var/icon/T = icon(\'test.dmi\', "grad")'],
                ["A.overlays += T", 'A.overlays -= icon(\'test.dmi\', "grad")'], ST)
        # Owner changes after a text state overlay was added
        ov_case(s, p + ".owner_icon", setup, ['A.overlays += "grad"', "A.icon = 'small.dmi'"], ST)
        ov_case(s, p + ".owner_icon", setup, ['A.overlays += "grad"', "A.icon = 'small.dmi'", 'A.overlays -= "grad"'], ST)
        ov_case(s, p + ".owner_icon", setup, ["A.icon = null", 'A.overlays += "grad"'], ST)
        ov_case(s, p + ".owner_icon", setup, ["A.icon = null", 'A.overlays += "grad"', "A.icon = 'test.dmi'", 'A.overlays -= "grad"'], ST)
        ov_case(s, p + ".owner_dir", setup, ["A.dir = WEST", 'A.overlays += "dirs4"', 'A.overlays += image(\'test.dmi\', "dirs4")', 'A.overlays += image(\'test.dmi\', "dirs4", dir = NORTH)'], ST)
        ov_case(s, p + ".owner_dir", setup, ['A.overlays += "dirs4"', "A.dir = WEST"], ST)
        ov_case(s, p + ".owner_layer", setup, ["A.layer = 8", 'A.overlays += "grad"', "A.overlays += /obj/overlays_thing"], ST)
        ov_case(s, p + ".layers", setup, ['A.overlays += overlays_img("a", 5)', 'A.overlays += overlays_img("b", 1)',
                                          'A.overlays += overlays_img("c", FLOAT_LAYER - 1)', 'A.overlays += overlays_img("d", -100)',
                                          'A.overlays += overlays_img("e", 0)'], ST)
        ov_case(s, p + ".layers_rem", setup, ['A.overlays += overlays_img("a", 5)', 'A.overlays += overlays_img("a", 1)',
                                              'A.overlays -= overlays_img("a", 5)'], ST)
        ov_case(s, p + ".layers_rem", setup, ['A.overlays += overlays_img("a", 5)', 'A.overlays -= "a"'], ST)
        ov_case(s, p + ".dupremove", setup, ['A.overlays += "grad"', 'A.overlays += "half"', 'A.overlays += "grad"', 'A.overlays -= "grad"'], ST)
        ov_case(s, p + ".dupremove", setup, ['A.overlays += list("grad", "grad", "grad")', 'A.overlays -= list("grad")'], ST)
        ov_case(s, p + ".dupremove", setup, ['A.overlays += list("grad", "grad", "grad")', 'A.overlays -= list("grad", "grad")'], ST)
        ov_case(s, p + ".dupremove", setup, ['A.overlays += list("grad", "half", "grad")', 'A.overlays.Remove("grad")'], ST)
        ov_case(s, p + ".mixed_eq", setup, ['A.overlays += "grad"', "A.overlays -= icon('test.dmi', \"grad\")"], ST)
        ov_case(s, p + ".mixed_eq", setup, ['A.overlays += "grad"', 'A.overlays -= image(\'test.dmi\', "grad")'], ST)
        ov_case(s, p + ".mixed_eq", setup, ['A.overlays += image(\'test.dmi\', "grad")', 'A.overlays -= "grad"'], ST)
        ov_case(s, p + ".mixed_eq", setup, ['A.overlays += /obj/overlays_thing', 'A.overlays -= parity_track(new /obj/overlays_thing)'], ST)
        ov_case(s, p + ".mixed_eq", setup, ['A.overlays += parity_track(new /obj/overlays_thing)', 'A.overlays -= /obj/overlays_thing'], ST)
        ov_case(s, p + ".mixed_eq", setup, ["A.overlays += 'small.dmi'", "A.overlays -= icon('small.dmi')"], ST)
        ov_case(s, p + ".mixed_eq", setup, ["A.overlays += overlays_ma()", 'A.overlays -= overlays_img("half", 7)'], ST)
        # Nested overlays of overlays
        ov_case(s, p + ".nested", setup + ['var/image/T = image(\'test.dmi\', "grad")', 'T.overlays += "half"', 'T.underlays += "alpha"'],
                ["A.overlays += T"], ST)
        ov_case(s, p + ".nested", setup + ["var/obj/overlays_thing/T = parity_track(new /obj/overlays_thing)", 'T.overlays += "asym"', 'T.overlays += image(\'test.dmi\', "half")'],
                ["A.overlays += T"], ST)
        ov_case(s, p + ".nested", setup + ["var/mutable_appearance/T = overlays_ma()", 'T.overlays += "asym"'],
                ["A.overlays += T"], ST)
        ov_case(s, p + ".nested", setup + ['var/image/T = image(\'test.dmi\', "grad")', 'T.overlays += "half"'],
                ["A.overlays += T", 'T.overlays.Cut()'], ST)
        ov_case(s, p + ".nested", setup + ['var/image/T = image(\'test.dmi\', "grad")', 'T.overlays += "half"', 'var/image/U = image(\'test.dmi\', "asym")', "U.overlays += T", "var/__o1", "var/__o2"],
                ["A.overlays += U", "__o1 = A.overlays[1]", "__o2 = __o1:overlays[1]"], "overlays_list(A.overlays), overlays_d(__o2)")
        ov_case(s, p + ".nested", setup + ['var/image/T = image(\'test.dmi\', "grad")', 'T.overlays += "half"'],
                ["A.overlays += T", 'A.overlays -= image(\'test.dmi\', "grad")'], ST)

    # ---- appearance round trips ----
    for tn, setup in (("obj", O), ("image", I)):
        p = f"overlays.appearance.{tn}"
        ov_case(s, p, setup + ['var/image/T = image(\'test.dmi\', "grad")', 'T.overlays += "half"', 'T.underlays += "alpha"'],
                ["A.appearance = T"], BOTH)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                [], "overlays_list(MA.overlays), MA.overlays.type")
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                ['MA.overlays += "asym"'], "overlays_list(MA.overlays), " + ST)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                ['MA.overlays += "asym"', "A.appearance = MA"], ST)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                ["MA.overlays.Cut()", "A.appearance = MA"], ST)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                ['MA.overlays = list("asym", "checker")', "A.appearance = MA"], ST)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/mutable_appearance/MA = new /mutable_appearance(A)"],
                ['MA.overlays = "asym"', "A.appearance = MA"], "overlays_list(MA.overlays), " + ST)
        ov_case(s, p, setup + ['A.overlays += "half"', "var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"],
                ["B.appearance = A.appearance"], "overlays_list(B.overlays)")
        ov_case(s, p, setup + ['A.overlays += "half"', "var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"],
                ["B.overlays = A.overlays"], "overlays_list(B.overlays)")
        ov_case(s, p, setup + ['A.overlays += "half"', "var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"],
                ["B.overlays += A.overlays", "B.overlays += A.overlays"], "overlays_list(B.overlays)")
        ov_case(s, p, setup + ['A.overlays += "half"', "var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"],
                ["B.overlays += A", "A.overlays.Cut()"], "overlays_list(B.overlays)")
        ov_case(s, p, setup + ['A.overlays += "half"', 'var/x = A.appearance'],
                ["A.overlays.Cut()"], "overlays_list(x:overlays), " + ST)
    # The MA's overlays list itself: a normal list holding what was added?
    p = "overlays.ma_list"
    for X in ('"grad"', "'small.dmi'", "/obj/overlays_thing", "image('test.dmi', \"half\")", "overlays_ma()", "null", "1", "new /datum",
              'list("a", "b")', "parity_track(new /obj/overlays_thing)"):
        ov_case(s, p, M, ["A.overlays += " + X], "A.overlays.len, istext(A.overlays[1]), ispath(A.overlays[1]), isicon(A.overlays[1]), isfile(A.overlays[1]), istype(A.overlays[1], /image), istype(A.overlays[1], /obj)")
    ov_case(s, p, M + ['var/list/L = list("grad")'], ["A.overlays = L", 'L += "half"'], ST)
    ov_case(s, p, M + ['var/list/L = list("grad")'], ["A.overlays = L"], "A.overlays == L")
    ov_case(s, p, M, ['A.overlays += "grad"', 'A.overlays[1] = "half"'], ST)
    ov_case(s, p, M, ['A.overlays["k"] = "half"'], ST)
    ov_case(s, p, M, ['A.overlays += "grad"', 'A.overlays.len = 3'], ST)
    ov_case(s, p, M, ['A.overlays += "grad"'], '"grad" in A.overlays')
    ov_case(s, p, M, ['A.overlays += "grad"'], 'A.overlays.Find("grad")')
    ov_case(s, p, M + ["var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"], ['A.overlays += "grad"', "B.appearance = A", 'A.overlays += "half"'], "overlays_list(B.overlays)")
    ov_case(s, p, M + ["var/mutable_appearance/MB = new /mutable_appearance(A)"], ['A.overlays += "grad"'], "overlays_list(MB.overlays)")
    ov_case(s, p, M + ['A.overlays += "grad"', "var/mutable_appearance/MB = new /mutable_appearance(A)"], ['MB.overlays += "half"'], "overlays_list(A.overlays), overlays_list(MB.overlays)")

    # ---- turf overlays: change and restore within the case ----
    T = ["var/turf/A = locate(8, 8, 1)", "A.overlays.Cut()", "A.underlays.Cut()"]
    for X in OV_VALUES_S:
        s.body("overlays.turf.add", T + ["var/__op"] + guard("A.overlays += " + X) +
               ["var/__s = overlays_list(A.overlays)", "A.overlays.Cut()"], "list(__op, __s, A.overlays.len)")
        s.body("overlays.turf.under", T + ["var/__op"] + guard("A.underlays += " + X) +
               ["var/__s = overlays_list(A.underlays)", "A.underlays.Cut()"], "list(__op, __s, A.underlays.len)")

    # ---- area overlays ----
    s.body("overlays.area", ["var/area/overlays_ar = parity_track(new /area)", "var/__op"] + guard('overlays_ar.overlays += "grad"'),
           "list(__op, overlays_list(overlays_ar.overlays))")


# ---------- vis_contents ----------
VIS_TARGETS = {
    "obj": ["var/obj/overlays_base/A = parity_track(new /obj/overlays_base(locate(2, 2, 1)))"],
    "mob": ["var/mob/overlays_mob/A = parity_track(new /mob/overlays_mob(locate(2, 2, 1)))"],
    "image": ["var/image/A = image('test.dmi', \"solid\")"],
    "ma": ["var/mutable_appearance/A = new /mutable_appearance"],
}
VIS_VALUES = [
    "parity_track(new /obj/overlays_thing(locate(4, 4, 1)))", "parity_track(new /obj/overlays_thing)",
    "parity_track(new /mob/overlays_mob(locate(4, 4, 1)))", "parity_track(new /atom/movable)", "locate(5, 5, 1)",
    "locate(/area)", "null", '"grad"', "1", "0", "/obj/overlays_thing", "image('test.dmi', \"half\")",
    "overlays_ma()", "'test.dmi'", "icon('test.dmi')", "new /datum", "list()",
    "list(parity_track(new /obj/overlays_thing), parity_track(new /obj/overlays_plain))", "list(null)", 'list("x")',
]


def vis_case(s, proc, setup, ops, result):
    ov_case(s, proc, setup, ops, result)


def build_vis(s):
    for tn, setup in VIS_TARGETS.items():
        p = f"vis.{tn}"
        R = "overlays_vis(A)" if tn not in ("image", "ma") else "A.vis_contents.len, overlays_items(A.vis_contents)"
        for X in VIS_VALUES:
            vis_case(s, p + ".add", setup, ["A.vis_contents += " + X], R)
            if tn in ("obj", "image"):
                vis_case(s, p + ".Add", setup, ["A.vis_contents.Add(" + X + ")"], R)
                vis_case(s, p + ".assign", setup, ["A.vis_contents = " + X], R)
                vis_case(s, p + ".dup", setup + ["var/v = " + X], ["A.vis_contents += v", "A.vis_contents += v"], R)
                vis_case(s, p + ".addrem", setup + ["var/v = " + X], ["A.vis_contents += v", "A.vis_contents -= v"], R)
                vis_case(s, p + ".remmiss", setup + ["var/obj/overlays_plain/P = parity_track(new /obj/overlays_plain)", "A.vis_contents += P"],
                         ["A.vis_contents -= " + X], R)
    for X in ANY:
        vis_case(s, "vis.pool.obj", VIS_TARGETS["obj"], ["A.vis_contents += " + X], "overlays_vis(A)")

    O = VIS_TARGETS["obj"]
    B = ["var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing(locate(4, 4, 1)))",
         "var/obj/overlays_plain/C = parity_track(new /obj/overlays_plain)"]
    pre = O + B + ["A.vis_contents += B", "A.vis_contents += C"]
    p = "vis.ops"
    s.body(p, O, "list(islist(A.vis_contents), A.vis_contents.type, A.vis_contents.len, A.vis_locs.len, A.vis_locs.type)")
    for idx in ("1", "2", "0", "3", "-1", '"x"'):
        vis_case(s, p + ".index", pre + ["var/__x"], [f"__x = A.vis_contents[{idx}]"], "__x")
    vis_case(s, p + ".setindex", pre, ["A.vis_contents[1] = C"], "overlays_vis(A)")
    vis_case(s, p + ".setindex", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)"], ["A.vis_contents[1] = D"], "overlays_vis(A)")
    for a, b in (("1", "0"), ("2", "0"), ("1", "2"), ("0", "0"), ("3", "0"), ("2", "1")):
        vis_case(s, p + ".Cut", pre, [f"A.vis_contents.Cut({a}, {b})"], "overlays_vis(A), B.vis_locs.len, C.vis_locs.len")
    vis_case(s, p + ".Cut", pre, ["A.vis_contents.Cut()"], "overlays_vis(A), B.vis_locs.len, C.vis_locs.len")
    for v in ("B", "C", "A", "null", '"x"'):
        vis_case(s, p + ".Find", pre + ["var/__x"], [f"__x = A.vis_contents.Find({v})"], "__x")
        vis_case(s, p + ".in", pre + ["var/__x"], [f"__x = (({v}) in A.vis_contents)"], "__x")
    vis_case(s, p + ".vis_locs", pre, [], "overlays_items(B.vis_locs), overlays_items(C.vis_locs), A.vis_locs.len")
    vis_case(s, p + ".vis_locs", pre, ["A.vis_contents -= B"], "overlays_items(B.vis_locs), overlays_items(C.vis_locs)")
    vis_case(s, p + ".vis_locs", pre, ["B.vis_locs += A"], "overlays_items(B.vis_locs), overlays_vis(A)")
    vis_case(s, p + ".vis_locs", pre, ["B.vis_locs.Cut()"], "overlays_items(B.vis_locs), overlays_vis(A)")
    vis_case(s, p + ".vis_locs", pre, ["B.vis_locs = list()"], "overlays_items(B.vis_locs), overlays_vis(A)")
    vis_case(s, p + ".vis_locs", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)", "D.vis_contents += B"], [],
             "overlays_items(B.vis_locs)")
    vis_case(s, p + ".del", pre, ["del B"], "overlays_vis(A)")
    vis_case(s, p + ".del", pre, ["del C"], "overlays_vis(A)")
    vis_case(s, p + ".del", pre, ["del A"], "B.vis_locs.len, C.vis_locs.len")
    vis_case(s, p + ".self", O, ["A.vis_contents += A"], "overlays_vis(A), A.vis_locs.len")
    vis_case(s, p + ".cycle", pre, ["B.vis_contents += A"], "overlays_vis(A), overlays_vis(B)")
    vis_case(s, p + ".copy", pre + ["var/list/L = A.vis_contents.Copy()"], ["L -= B"], "overlays_vis(A), L.len, L.type")
    vis_case(s, p + ".ref", pre + ["var/list/L = A.vis_contents"], ["L -= B"], "overlays_vis(A)")
    vis_case(s, p + ".plus", pre + ["var/__x"], ["__x = A.vis_contents + B"], "__x, overlays_vis(A)")
    vis_case(s, p + ".minus", pre + ["var/__x"], ["__x = A.vis_contents - B"], "__x, overlays_vis(A)")
    vis_case(s, p + ".or", pre, ["A.vis_contents |= B"], "overlays_vis(A)")
    vis_case(s, p + ".and", pre, ["A.vis_contents &= list(B)"], "overlays_vis(A)")
    vis_case(s, p + ".lenset", pre, ["A.vis_contents.len = 0"], "overlays_vis(A)")
    vis_case(s, p + ".lenset", pre, ["A.vis_contents.len = 5"], "overlays_vis(A)")
    vis_case(s, p + ".Insert", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)", "var/__x"], ["__x = A.vis_contents.Insert(1, D)"], "__x, overlays_vis(A)")
    vis_case(s, p + ".Swap", pre, ["A.vis_contents.Swap(1, 2)"], "overlays_vis(A)")
    vis_case(s, p + ".Remove", pre + ["var/__x"], ["__x = A.vis_contents.Remove(B)"], "__x, overlays_vis(A)")
    vis_case(s, p + ".Remove", pre + ["var/__x"], ["__x = A.vis_contents.Remove(A)"], "__x, overlays_vis(A)")
    vis_case(s, p + ".contents", pre, [], "A.contents.len, B.loc, C.loc")
    vis_case(s, p + ".loop", pre + ["var/list/names = list()"], [["for(var/atom/movable/M in A.vis_contents)", "\tnames += M.name"]], "names")
    vis_case(s, p + ".overlays_unaffected", pre, [], "overlays_list(A.overlays)")
    vis_case(s, p + ".move", pre, ["B.loc = locate(6, 6, 1)"], "overlays_vis(A)")
    vis_case(s, p + ".image_then_atom", O + ['var/image/I = image(\'test.dmi\', "half")'] + B, ["I.vis_contents += B", "A.overlays += I"],
             "overlays_list(A.overlays), overlays_items(B.vis_locs)")
    vis_case(s, p + ".appearance", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)"], ["D.appearance = A.appearance"],
             "overlays_vis(D)")
    vis_case(s, p + ".ma", pre + ["var/mutable_appearance/MA = new /mutable_appearance(A)"], [], "MA.vis_contents.len, overlays_items(MA.vis_contents)")
    vis_case(s, p + ".ma", O + B + ["var/mutable_appearance/MA = new /mutable_appearance(A)"], ["MA.vis_contents += B", "A.appearance = MA"], "overlays_vis(A)")
    # Turf as the vis_contents owner: cleared before and after
    T = ["var/turf/A = locate(9, 9, 1)", "A.vis_contents.Cut()"]
    for X in ("parity_track(new /obj/overlays_thing)", "locate(5, 5, 1)", "null", '"grad"', "/obj/overlays_thing"):
        s.body("vis.turf.add", T + ["var/__op"] + guard("A.vis_contents += " + X) + ["var/__s = overlays_vis(A)", "A.vis_contents.Cut()"],
               "list(__op, __s, A.vis_contents.len)")
    s.body("vis.turf.self", T + ["var/__op"] + guard("A.vis_contents += A") + ["var/__s = overlays_vis(A)", "var/__l = A.vis_locs.len", "A.vis_contents.Cut()"],
           "list(__op, __s, __l)")
    s.body("vis.turf.vis_locs", ["var/turf/T = locate(9, 9, 1)"] + O + ["A.vis_contents += T"], "overlays_items(T.vis_locs)")
    s.body("vis.area", ["var/area/overlays_ar = parity_track(new /area)", "var/obj/overlays_plain/P = parity_track(new /obj/overlays_plain)", "var/__op"] +
           guard("overlays_ar.vis_contents += P"), "list(__op, overlays_ar.vis_contents.len)")


# ---------- verbs ----------
def build_verbs(s):
    V = ["var/obj/overlays_vobj/A = parity_track(new /obj/overlays_vobj(locate(2, 2, 1)))"]
    P = ["var/obj/overlays_plain/A = parity_track(new /obj/overlays_plain(locate(2, 2, 1)))"]
    MB = ["var/mob/overlays_mob/A = parity_track(new /mob/overlays_mob(locate(2, 2, 1)))"]
    R = "overlays_verbs(A.verbs)"
    VALS = ["/obj/overlays_vobj/verb/overlays_v1", "/obj/overlays_vobj/verb/overlays_v2", "/obj/overlays_vobj/proc/overlays_p1",
            "/obj/proc/overlays_op", "/proc/overlays_gp", "/mob/overlays_mob/verb/overlays_mv", '"overlays_v1"', '"text"', "null",
            "1", "/obj", "new /datum", "list(/obj/proc/overlays_op, /proc/overlays_gp)", "list()", "'test.dmi'"]
    for tn, setup in (("vobj", V), ("plain", P), ("mob", MB)):
        p = f"verbs.{tn}"
        s.body(p + ".initial", setup, R)
        for X in VALS:
            ov_case(s, p + ".add", setup, ["A.verbs += " + X], R)
            ov_case(s, p + ".sub", setup, ["A.verbs -= " + X], R)
            if tn == "vobj":
                ov_case(s, p + ".Add", setup, ["A.verbs.Add(" + X + ")"], R)
                ov_case(s, p + ".dup", setup, ["A.verbs += " + X, "A.verbs += " + X], R)
                ov_case(s, p + ".addrem", setup, ["A.verbs += " + X, "A.verbs -= " + X], R)
                ov_case(s, p + ".assign", setup, ["A.verbs = " + X], R)
                ov_case(s, p + ".in", setup + ["var/__x"], [f"__x = (({X}) in A.verbs)"], "__x")
    for X in ANY:
        ov_case(s, "verbs.pool", V, ["A.verbs += " + X], R)
    p = "verbs.ops"
    s.body(p, V, "list(islist(A.verbs), A.verbs.type, length(A.verbs))")
    for idx in ("1", "2", "0", "3", '"x"'):
        ov_case(s, p + ".index", V + ["var/__x"], [f"__x = \"[A.verbs[{idx}]]\""], "__x")
    ov_case(s, p + ".setindex", V, ["A.verbs[1] = /obj/proc/overlays_op"], R)
    for a, b in (("1", "0"), ("2", "0"), ("1", "2"), ("0", "0"), ("3", "0")):
        ov_case(s, p + ".Cut", V, [f"A.verbs.Cut({a}, {b})"], R)
    ov_case(s, p + ".Cut", V, ["A.verbs.Cut()"], R)
    ov_case(s, p + ".Cut_readd", V, ["A.verbs.Cut()", "A.verbs += /obj/overlays_vobj/verb/overlays_v2"], R)
    for X in ("/obj/overlays_vobj/verb/overlays_v1", "/obj/overlays_vobj/verb/overlays_v2", "/obj/proc/overlays_op", "null", '"overlays_v1"'):
        ov_case(s, p + ".Find", V + ["var/__x"], [f"__x = A.verbs.Find({X})"], "__x")
        ov_case(s, p + ".Remove", V + ["var/__x"], [f"__x = A.verbs.Remove({X})"], "list(__x, " + R + ")")
    ov_case(s, p + ".lenset", V, ["A.verbs.len = 0"], R)
    ov_case(s, p + ".lenset", V, ["A.verbs.len = 5"], R)
    ov_case(s, p + ".Insert", V, ["A.verbs.Insert(1, /obj/proc/overlays_op)"], R)
    ov_case(s, p + ".Swap", V, ["A.verbs.Swap(1, 2)"], R)
    ov_case(s, p + ".copy", V + ["var/list/L = A.verbs.Copy()"], ["L -= /obj/overlays_vobj/verb/overlays_v1"], "overlays_verbs(L), " + R)
    ov_case(s, p + ".ref", V + ["var/list/L = A.verbs"], ["L -= /obj/overlays_vobj/verb/overlays_v1"], "overlays_verbs(L), " + R)
    ov_case(s, p + ".plus", V + ["var/__x"], ["__x = overlays_verbs(A.verbs + /obj/proc/overlays_op)"], "__x, " + R)
    ov_case(s, p + ".minus", V + ["var/__x"], ["__x = overlays_verbs(A.verbs - /obj/overlays_vobj/verb/overlays_v1)"], "__x, " + R)
    ov_case(s, p + ".or", V, ["A.verbs |= /obj/overlays_vobj/verb/overlays_v1"], R)
    ov_case(s, p + ".and", V, ["A.verbs &= list(/obj/overlays_vobj/verb/overlays_v1)"], R)
    ov_case(s, p + ".kind", V + ["var/v = A.verbs[1]"], [], "list(ispath(v), istext(v), isnull(v), istype(v, /datum), v == /obj/overlays_vobj/verb/overlays_v1)")
    ov_case(s, p + ".name", V + ["var/v = A.verbs[1]", "var/__x"], ["__x = v:name"], "__x")
    ov_case(s, p + ".name", V + ["var/v = A.verbs[2]", "var/__x"], ["__x = v:name"], "__x")
    ov_case(s, p + ".name", V + ["A.verbs += /obj/proc/overlays_op", "var/v = A.verbs[A.verbs.len]", "var/__x"], ["__x = v:name"], "__x")
    ov_case(s, p + ".other_instance", V + ["var/obj/overlays_vobj/B = parity_track(new /obj/overlays_vobj)"], ["A.verbs -= /obj/overlays_vobj/verb/overlays_v1"],
            "overlays_verbs(B.verbs), " + R)
    ov_case(s, p + ".other_instance", V + ["var/obj/overlays_vobj/B = parity_track(new /obj/overlays_vobj)"], ["A.verbs += /obj/proc/overlays_op"],
            "overlays_verbs(B.verbs), " + R)
    ov_case(s, p + ".appearance", V + ["var/obj/overlays_plain/B = parity_track(new /obj/overlays_plain)"], ["B.appearance = A.appearance"],
            "overlays_verbs(B.verbs)")
    ov_case(s, p + ".loop", V + ["var/n = 0"], [["for(var/v in A.verbs)", "\tn++"]], "n")
    ov_case(s, p + ".turf", ["var/turf/A = locate(7, 7, 1)", "var/__n = A.verbs.len"], [], "__n")
    ov_case(s, p + ".image", ["var/image/A = image('test.dmi')"], ["A:verbs += /obj/proc/overlays_op"], "A:verbs")


# ---------- contents ----------
def build_contents(s):
    BOX = ["overlays_events = list()", "var/obj/overlays_box/A = parity_track(new /obj/overlays_box(locate(2, 2, 1)))",
           "var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing(locate(3, 3, 1)))",
           "var/obj/overlays_plain/C = parity_track(new /obj/overlays_plain)"]
    ST = "overlays_items(A.contents), overlays_locs(list(B, C)), overlays_events"
    p = "contents"
    VALS = ["B", "C", "list(B, C)", "list(B, B)", "list()", "null", '"grad"', "1", "/obj/overlays_thing", "new /datum",
            "locate(5, 5, 1)", "locate(/area)", "A", "image('test.dmi')", "parity_track(new /mob/overlays_mob(locate(4, 4, 1)))",
            "list(B, \"x\", C)"]
    for X in VALS:
        ov_case(s, p + ".add", BOX, ["A.contents += " + X], ST)
        ov_case(s, p + ".Add", BOX, ["A.contents.Add(" + X + ")"], ST)
        ov_case(s, p + ".addrem", BOX, ["A.contents += " + X, "A.contents -= " + X], ST)
        ov_case(s, p + ".sub_missing", BOX, ["A.contents -= " + X], ST)
        ov_case(s, p + ".assign", BOX + ["A.contents += C"], ["A.contents = " + X], ST)
        ov_case(s, p + ".in", BOX + ["A.contents += C", "var/__x"], [f"__x = (({X}) in A.contents)"], "__x")
    for X in ANY:
        ov_case(s, p + ".pool", BOX, ["A.contents += " + X], ST)
    pre = BOX + ["A.contents += B", "A.contents += C", "overlays_events = list()"]
    ov_case(s, p + ".dup", BOX, ["A.contents += B", "A.contents += B"], ST)
    for idx in ("1", "2", "0", "3", "-1", '"x"'):
        ov_case(s, p + ".index", pre + ["var/__x"], [f"__x = A.contents[{idx}]"], "__x")
    ov_case(s, p + ".setindex", pre, ["A.contents[1] = C"], ST)
    for a, b in (("1", "0"), ("2", "0"), ("1", "2"), ("0", "0"), ("3", "0")):
        ov_case(s, p + ".Cut", pre, [f"A.contents.Cut({a}, {b})"], ST)
    ov_case(s, p + ".Cut", pre, ["A.contents.Cut()"], ST)
    for X in ("B", "C", "A", "null", '"x"'):
        ov_case(s, p + ".Find", pre + ["var/__x"], [f"__x = A.contents.Find({X})"], "__x")
        ov_case(s, p + ".Remove", pre + ["var/__x"], [f"__x = A.contents.Remove({X})"], "__x, " + ST)
    ov_case(s, p + ".lenset", pre, ["A.contents.len = 0"], ST)
    ov_case(s, p + ".lenset", pre, ["A.contents.len = 5"], ST)
    ov_case(s, p + ".Insert", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)"], ["A.contents.Insert(1, D)"], ST + ", D.loc")
    ov_case(s, p + ".Swap", pre, ["A.contents.Swap(1, 2)"], ST)
    ov_case(s, p + ".copy", pre + ["var/list/L = A.contents.Copy()"], ["L -= B"], "L.len, L.type, " + ST)
    ov_case(s, p + ".ref", pre + ["var/list/L = A.contents"], ["L -= B"], ST)
    ov_case(s, p + ".plus", pre + ["var/obj/overlays_plain/D = parity_track(new /obj/overlays_plain)", "var/__x"], ["__x = A.contents + D"], "__x, D.loc, " + ST)
    ov_case(s, p + ".minus", pre + ["var/__x"], ["__x = A.contents - B"], "__x, " + ST)
    ov_case(s, p + ".or", pre, ["A.contents |= B"], ST)
    ov_case(s, p + ".and", pre, ["A.contents &= list(B)"], ST)
    ov_case(s, p + ".kind", pre, [], "islist(A.contents), A.contents.type, length(A.contents)")
    ov_case(s, p + ".move_between", pre + ["var/obj/overlays_box/D = parity_track(new /obj/overlays_box)", "D.name = \"box2\""],
            ["D.contents += B"], ST + ", overlays_items(D.contents)")
    ov_case(s, p + ".nested", pre, ["B.contents += A"], ST + ", overlays_items(B.contents), A.loc")
    ov_case(s, p + ".nested", pre, ["C.contents += A"], ST + ", overlays_items(C.contents), A.loc")
    ov_case(s, p + ".loc_assign", BOX, ["B.loc = A"], ST)
    ov_case(s, p + ".loc_assign", BOX, ["B.Move(A)"], ST)
    ov_case(s, p + ".loop", pre + ["var/list/names = list()"], [["for(var/atom/movable/M in A.contents)", "\tnames += M.name"]], "names")
    ov_case(s, p + ".loop_move", pre + ["var/n = 0"], [["for(var/atom/movable/M in A.contents)", "\tn++", "\tM.loc = null"]], "n, " + ST)
    ov_case(s, p + ".del_member", pre, ["del B"], "overlays_items(A.contents)")
    ov_case(s, p + ".del_container", pre, ["del A"], "B.loc, C.loc")
    # turf and mob containers
    TB = ["var/turf/T = locate(6, 6, 1)", "var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing)"]
    ov_case(s, p + ".turf", TB, ["T.contents += B"], "B.loc, B.x, B.y, B in T.contents")
    ov_case(s, p + ".turf", TB + ["T.contents += B"], ["T.contents -= B"], "B.loc, B in T.contents")
    ov_case(s, p + ".turf", TB, ['T.contents += "x"'], "T.contents.len")
    ov_case(s, p + ".turf", TB, ["T.contents += locate(7, 7, 1)"], "T.contents.len")
    ov_case(s, p + ".turf", TB + ["T.contents += B"], ["T.contents.Cut()"], "B.loc")
    MB = ["var/mob/overlays_mob/A = parity_track(new /mob/overlays_mob(locate(2, 2, 1)))",
          "var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing(locate(3, 3, 1)))"]
    ov_case(s, p + ".mob", MB, ["A.contents += B"], "overlays_items(A.contents), B.loc")
    ov_case(s, p + ".mob", MB, ["B.contents += A"], "overlays_items(B.contents), A.loc")
    ov_case(s, p + ".area", ["var/area/AR = locate(/area)", "var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing)"],
            ["AR.contents += B"], "B.loc")
    ov_case(s, p + ".image", ["var/image/A = image('test.dmi')", "var/obj/overlays_thing/B = parity_track(new /obj/overlays_thing)"],
            ["A:contents += B"], "B.loc")


def build(s):
    s.dm(_helpers())
    build_overlays(s)
    build_vis(s)
    build_verbs(s)
    build_contents(s)
