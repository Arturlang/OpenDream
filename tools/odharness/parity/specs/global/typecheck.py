"""Type-check and type-reflection builtins: isnum, istext, islist, ispath, isnull, isfile, isicon,
isloc, isarea, isturf, isobj, ismob, ismovable, istype (1/2 args), astype, typesof, text2path,
hascall, locate (type/tag/ref, with and without a container), initial, issaved, nameof.

BYOND reference points targeted here:
- isloc/isarea/isturf/isobj/ismob/ismovable take any number of args and return 1 only if ALL are
  of that kind; isloc(x) == ismob||isobj||isturf||isarea (so a bare /atom/movable is NOT a loc).
- ispath(Val) is 1 for a type path; ispath(Val, Type) - Type may be a path or an INSTANCE.
- istype(Val, Type) - Type may be a prototype or an instance; istype(Val) uses the declared type
  of the variable passed. Use ispath() for path-vs-path checks (istype on a path is false).
- isfile: file() objects and resource-cache files; isicon: /icon objects and cached icon files.
- typesof(T1, T2, ...): every type derived from the bases, bases included; also lists procs/verbs
  for "/type/proc" and "/type/verb".
- text2path: null when there is no such type.
- hascall(Object, ProcName): 1 if the object has a proc or verb of that name.
- locate(Type) in Container (default world), locate(Tag), locate(TextRef); types match like istype.
- initial(Var): compile-time value; issaved(Var): 0 for global/const/tmp vars, else 1.
- nameof(): compile-time name of a var, proc or last path element.

OpenDream divergences these cases aim at (DreamProcNativeRoot.cs, DMOpcodeHandlers.cs):
- isloc accepts any atom (bare /atom/movable included); multi-arg loc procs with zero args
  return 1 (empty foreach).
- ispath(path, instance|null|text) returns 1 because a non-type Type is treated as absent.
- isicon uses ResourceManager.TryLoadIcon, which may accept text file names and file() objects.
- hascall on a type path returns 0 (only DreamObjects); procs are looked up by HasProc.
- typesof("text") throws for unknown text; procs come from Procs.Values (order, overrides).
- text2path special-cases "/proc/" and "/verb/" substrings and ignores overrides.
- locate(x) in world only handles type paths (no datums, no instances); locate(text) strips [].
- initial() on a null owner returns null silently; initial(L[1]) does list access; issaved() of
  a number key is 0; issaved/initial via a path-typed variable.
"""
from pools import TEXT_S, NUM_S, OTHER, ANY
from gen import dm_str

HELPERS = r'''
/obj/typecheck_thing
	name = "thing"
	icon = 'test.dmi'
	icon_state = "solid"
	var/plain = 5
	var/tmp/tmpvar = 3
	var/const/constvar = 7
	var/global/globvar = 9
	var/static/statvar = 11
	var/list/listvar = list(1, 2)
	var/list/emptylist
	var/list/typedlist = new
	var/textvar = "hi"
	var/pathvar = /obj
	var/numexpr = 2 + 3
	var/fracvar = 1.5
	var/nullvar = null
	var/datumvar = new /datum

/obj/typecheck_thing/proc/typecheck_p()
	return 1

/obj/typecheck_thing/verb/typecheck_v()
	set name = "typecheck verb"

/obj/typecheck_thing/child
	name = "child"
	plain = 6
	tmpvar = 4

/obj/typecheck_thing/child/typecheck_p()
	return 2

/obj/typecheck_thing/child/proc/typecheck_childp()
	return 3

/obj/typecheck_thing/child/grand
	name = "grand"

/obj/typecheck_thing/other

/obj/typecheck_lone

/mob/typecheck_mob

/atom/movable/typecheck_am

/datum/typecheck_d
	var/x = 1
	var/tmp/y = 2
	var/z

/datum/typecheck_d/proc/typecheck_dp()
	return 1

/datum/typecheck_d/sub
	x = 10

/datum/typecheck_d/sub/deeper

/datum/typecheck_loc

/datum/typecheck_loc/sub

/proc/typecheck_global()
	return 1

var/global/typecheck_g = 3

/obj/typecheck_thing/proc/typecheck_selfq()
	return list(initial(plain), initial(src.plain), issaved(tmpvar), issaved(src.plain), nameof(plain), nameof(src.tmpvar))

/obj/typecheck_thing/proc/typecheck_selfist()
	return istype(src)

/proc/typecheck_argq(obj/typecheck_thing/A)
	return istype(A)

/proc/typecheck_usrq()
	return istype(usr)

/proc/typecheck_turf()
	return locate(1, 1, 1)

/proc/typecheck_area()
	return locate(/area)

/proc/typecheck_obj(type = /obj/typecheck_thing)
	return parity_track(new type(locate(1, 1, 1)))

/proc/typecheck_nullobj()
	return parity_track(new /obj/typecheck_thing)

/proc/typecheck_mob()
	return parity_track(new /mob/typecheck_mob(locate(1, 1, 1)))

/proc/typecheck_am()
	return parity_track(new /atom/movable/typecheck_am(locate(1, 1, 1)))

/proc/typecheck_datum(type = /datum/typecheck_d)
	return parity_track(new type)

/proc/typecheck_vars()
	var/datum/typecheck_d/D = typecheck_datum()
	return D.vars

/proc/typecheck_contents()
	var/turf/T = locate(1, 1, 1)
	return T.contents

/proc/typecheck_overlays()
	var/obj/O = typecheck_obj()
	return O.overlays

/proc/typecheck_verbs()
	var/obj/O = typecheck_obj()
	return O.verbs

/proc/typecheck_deleted()
	var/datum/D = new /datum/typecheck_d
	del D
	return D

/proc/typecheck_args(...)
	return args

// Sorted copy (by text form) so list order differences don't hide content differences
/proc/typecheck_sorted(list/L)
	if(!islist(L))
		return L
	var/list/out = list()
	for(var/x in L)
		var/i = 1
		while(i <= out.len && sorttextEx("[out[i]]", "[x]") == 1)
			i++
		out.Insert(i, x)
	return out
'''

Q = dm_str

# Values of every kind, for the one-argument predicates
KINDS = [
    "NINF", "NAN", "1e30", Q("0"), Q("/obj"), Q("test.dmi"), "'test.dmi'", "'small.dmi'",
    'file("test.dmi")', 'file("typecheck_none.txt")', "icon('test.dmi')", "new /icon",
    "image('test.dmi')", "new /mutable_appearance", "matrix()", 'regex("a")', 'new /exception("x")',
    "new /sound", "alist()", "list(list())", "world", "typecheck_turf()", "typecheck_area()",
    "typecheck_obj()", "typecheck_obj(/obj/typecheck_thing/child)", "typecheck_nullobj()",
    "typecheck_mob()", "typecheck_am()", "typecheck_datum()", "typecheck_vars()", "typecheck_contents()",
    "world.contents", "typecheck_overlays()", "typecheck_verbs()", "args", "typecheck_args(1, 2)",
    "global.vars", "typecheck_deleted()", "vector(1, 2)",
    "/obj", "/obj/typecheck_thing", "/obj/typecheck_thing/child", "/turf", "/area", "/mob", "/atom",
    "/atom/movable", "/icon", "/list", "/image", "/proc/typecheck_global",
    "/obj/typecheck_thing/proc/typecheck_p", "/obj/typecheck_thing/verb/typecheck_v",
]
VAL1 = list(dict.fromkeys(TEXT_S[:3] + [TEXT_S[6]] + NUM_S[:3] + ["0.5", "100"] + OTHER + KINDS))

PRED1 = ["isnum", "istext", "islist", "ispath", "isnull", "isfile", "isicon"]
LOCP = ["isloc", "isarea", "isturf", "isobj", "ismob", "ismovable"]

# Small pools for multi-argument loc predicates
LOCV = ["typecheck_turf()", "typecheck_area()", "typecheck_obj()", "typecheck_mob()",
        "null", "typecheck_datum()"]
LOCV3 = ["typecheck_turf()", "typecheck_obj()", "typecheck_mob()", "null", "typecheck_area()"]

# istype(Val, Type)
IST_VAL = [
    "null", Q("a"), Q("/obj"), "/obj", "/obj/typecheck_thing/child", "list()", "world", "typecheck_turf()", "typecheck_area()", "typecheck_obj()",
    "typecheck_obj(/obj/typecheck_thing/child/grand)", "typecheck_mob()", "typecheck_am()",
    "typecheck_nullobj()", "new /datum", "typecheck_datum(/datum/typecheck_d/sub)", "icon('test.dmi')",
    "image('test.dmi')", "new /mutable_appearance", "matrix()", 'regex("a")', "'test.dmi'",
]
IST_TYPE = [
    "/datum", "/atom/movable", "/obj", "/mob", "/turf", "/area", "/list", "/icon",
    "/image", "/mutable_appearance", "/matrix", "/regex",
    "/obj/typecheck_thing", "/obj/typecheck_thing/child", "/datum/typecheck_d",
    "null", Q("/obj"), "1", "list()",
    "typecheck_obj(/obj/typecheck_thing/child)", "typecheck_datum()", "/proc/typecheck_global",
]

# ispath(Val, Type)
ISP_VAL = [
    "/obj", "/obj/typecheck_thing", "/obj/typecheck_thing/child/grand", "/datum", "/atom", "/mob",
    "/list", "/icon", "/proc/typecheck_global", "/obj/typecheck_thing/proc/typecheck_p",
    "/obj/typecheck_thing/verb/typecheck_v", "null", Q("/obj"), "1", "typecheck_obj()", "list()",
]
ISP_TYPE = [
    "/obj", "/obj/typecheck_thing", "/obj/typecheck_thing/child", "/datum", "/atom", "/atom/movable",
    "/datum/typecheck_d", "/proc/typecheck_global", "null", Q("/obj"), "1", "list()",
    "typecheck_obj()", "typecheck_datum()",
]

# hascall(Object, ProcName)
HC_OBJ = ["typecheck_obj()", "typecheck_obj(/obj/typecheck_thing/child)", "typecheck_datum()",
          "new /datum", "/obj/typecheck_thing", "null", Q("a"),
          "world", "typecheck_turf()", "typecheck_mob()"]
HC_NAME = [Q(n) for n in ["typecheck_p", "typecheck_v", "typecheck verb", "typecheck_childp", "typecheck_dp",
                          "New", "Del", "Move", "Click", "Topic", "Write", "Copy",
                          "Find", "nonexistent", "TYPECHECK_P", "", "typecheck_global",
                          "proc/typecheck_p", "/obj/typecheck_thing/proc/typecheck_p"]] + ["null", "1"]

T2P = [Q(t) for t in [
    "/obj", "/obj/typecheck_thing", "/obj/typecheck_thing/child/grand", "obj", "obj/typecheck_thing",
    "/obj/", "/obj/typecheck_thing/", "/datum", "/datum/", "/", "", " ", "/nonexistent", "/obj/nonexistent",
    "/OBJ", " /obj", "/obj ", "//obj", "/obj//typecheck_thing", ".obj", "/datum/typecheck_d/sub",
    "/list", "/alist", "/icon", "/image", "/client", "/world", "/savefile", "/atom", "/atom/movable",
    "/mob/typecheck_mob", "/turf", "/area", "/matrix", "/regex", "/exception", "/mutable_appearance",
    "/proc", "/verb", "/proc/typecheck_global", "/proc/nonexistent", "/verb/typecheck_global",
    "/proc/abs", "/proc/text2path", "/obj/typecheck_thing/proc", "/obj/typecheck_thing/proc/typecheck_p",
    "/obj/typecheck_thing/verb/typecheck_v", "/obj/typecheck_thing/proc/typecheck_v",
    "/obj/typecheck_thing/verb/typecheck_p", "/obj/typecheck_thing/child/proc/typecheck_p",
    "/obj/typecheck_thing/child/typecheck_p", "/obj/typecheck_thing/child/proc/typecheck_childp",
    "/obj/typecheck_thing/typecheck_p", "/obj/typecheck_thing/child/grand/proc/typecheck_childp",
    "/datum/proc/New", "/atom/movable/proc/Move", "/obj/proc/Move", "/obj/typecheck_thing/var/plain",
    "/obj/typecheck_thing/plain", "/obj/typecheck_thing/proc/typecheck_p/", "/obj/typecheck_thing.child",
    "/obj/typecheck_thing:child",
]] + ["null", "1", "/obj", "list()", "typecheck_obj()"]


def build(s):
    s.dm(HELPERS)

    # ---------------- one-argument predicates ----------------------------------------------------
    for p in PRED1 + LOCP:
        s.sweep(p, [VAL1])
        # argument-count edges (BYOND checks some at compile time)
        s.case(p, f"{p}()")
        s.case(p, f"{p}(1, 2)")
        s.case(p, f'{p}("a", "b")')
        s.case(p, f"{p}(null, null)")
        s.case(p, f"{p}(Val = 1)")
    # extra text/number spread for the primitive checks
    for p in ["isnum", "istext", "isnull"]:
        for v in NUM_S + ["PINF", "-0", "1e-30", "16777217", "TRUE", "FALSE"] + TEXT_S:
            s.call(p, v)
    s.case("isnum", 'isnum(text2num("5"))')
    s.case("isnum", 'isnum(text2num("abc"))')
    s.case("isnum", 'isnum("[1]")')
    s.case("isnum", "isnum(1 + 1)")
    s.case("isnum", 'isnum(length("ab"))')
    s.case("istext", "istext(\"[1]\")")
    s.case("istext", "istext(num2text(5))")
    s.case("istext", "istext(\"\\ref[world]\")")
    s.case("istext", "istext(ascii2text(0))")
    s.case("istext", "istext(file2text(\"typecheck_none.txt\"))")
    s.case("istext", "istext(typecheck_obj():name)")
    s.case("isnull", "isnull(list(null)[1])")
    s.case("isnull", "isnull(typecheck_deleted())")
    s.case("isnull", 'isnull("")')
    s.case("isnull", "isnull(0)")
    s.case("isnull", "isnull(typecheck_nullobj():loc)")
    s.body("isnull", ["var/list/L = list(1)", "L.len = 3"], "list(isnull(L[2]), isnull(L[3]), L.len)")
    s.body("isnull", ["var/datum/D = new /datum/typecheck_d", "var/datum/E = D", "del D"],
           "list(isnull(D), isnull(E))")
    s.body("islist", ["var/obj/typecheck_thing/O = typecheck_obj()"],
           "list(islist(O.contents), islist(O.vars), islist(O.overlays), islist(O.underlays), "
           "islist(O.verbs), islist(O.filters), islist(O.vis_contents), islist(O.vis_locs), "
           "islist(O.listvar), islist(O.emptylist), islist(O.typedlist), islist(O.locs))")
    s.body("islist", ["var/turf/T = locate(1, 1, 1)"],
           "list(islist(T.contents), islist(T.vars), islist(T.loc.contents), islist(world.vars), "
           "islist(T.overlays), islist(T.vis_contents))")
    s.body("islist", ["var/regex/R = regex(\"(a)(b)\")", "R.Find(\"ab\")"], "islist(R.group)")
    s.body("islist", ["var/list/L = list(list(1))"], "list(islist(L[1]), islist(L), islist(L.Copy()))")
    s.case("islist", "islist(splittext(\"a,b\", \",\"))")
    s.case("islist", "islist(params2list(\"a=1\"))")
    s.case("islist", "islist(typesof(/datum/typecheck_d))")
    s.case("islist", "islist(icon_states('test.dmi'))")
    s.case("islist", "islist(world.contents)")
    s.case("islist", "islist(newlist(/datum))")
    s.case("islist", "islist(matrix())")
    s.case("islist", "islist(vector(1, 2))")
    s.case("ispath", "ispath(typecheck_obj():type)")
    s.case("ispath", "ispath(typecheck_obj():parent_type)")
    s.case("ispath", 'ispath(text2path("/obj"))')
    s.case("ispath", "ispath(/obj/typecheck_thing::pathvar)")
    s.case("ispath", "ispath(__TYPE__)")
    s.case("ispath", "ispath(/datum/typecheck_d/proc/typecheck_dp)")
    s.case("ispath", "ispath(/obj/typecheck_thing/child/typecheck_p)")
    s.case("ispath", "ispath(world.mob)")
    s.case("ispath", "ispath(world.turf)")
    s.case("ispath", "ispath(world.area)")
    s.case("ispath", "ispath(/client)")
    s.case("ispath", "ispath(/savefile)")
    s.case("isfile", 'isfile(file("typecheck_none.txt"))')
    s.case("isfile", 'isfile(fcopy_rsc("test.dmi"))')
    s.case("isfile", 'isfile(fcopy_rsc(\'small.dmi\'))')
    s.case("isfile", "isfile(typecheck_obj():icon)")
    s.case("isfile", "isfile(icon('test.dmi'))")
    s.case("isfile", "isfile(new /icon('test.dmi'))")
    s.case("isicon", "isicon(typecheck_obj():icon)")
    s.case("isicon", 'isicon(fcopy_rsc("test.dmi"))')
    s.case("isicon", 'isicon(new /icon(\'test.dmi\', "solid"))')
    s.case("isicon", "isicon('rect.dmi')")
    s.case("isicon", 'isicon("small.dmi")')
    s.case("isicon", 'isicon(file("small.dmi"))')
    s.case("isicon", 'isicon(file("typecheck_none.dmi"))')
    s.case("isicon", "isicon(image('test.dmi'))")
    s.case("isicon", "isicon(/icon)")

    # ---------------- multi-argument loc predicates ----------------------------------------------
    for p in LOCP:
        s.sweep(p, [LOCV, LOCV], min_args=2)
        s.sweep(p, [LOCV3, LOCV3, LOCV3], min_args=3)
        s.case(p, f"{p}(typecheck_obj(), typecheck_obj(), typecheck_obj(), typecheck_obj())")
        s.case(p, f"{p}(typecheck_turf(), typecheck_turf(), typecheck_turf(), null)")
        s.case(p, f"{p}(list(typecheck_obj()))")
        s.case(p, f"{p}(world.contents)")
        s.case(p, f"{p}(arglist(list(typecheck_obj(), typecheck_mob())))")
        s.case(p, f"{p}(arglist(list()))")
        s.case(p, f"{p}(Loc1 = typecheck_obj())")
        s.case(p, f"{p}(typecheck_obj(/obj/typecheck_thing/child/grand))")
        s.case(p, f"{p}(typecheck_obj(/obj/typecheck_lone))")
        s.case(p, f"{p}(typecheck_turf():loc)")
        s.case(p, f"{p}(typecheck_obj():loc)")
        s.case(p, f"{p}(typecheck_nullobj():loc)")

    # ---------------- istype -----------------------------------------------------------------------
    s.sweep("istype", [IST_VAL, IST_TYPE])
    s.case("istype", "istype(typecheck_obj(), typecheck_obj():type)")
    s.case("istype", "istype(typecheck_obj(/obj/typecheck_thing/child), typecheck_obj():type)")
    s.case("istype", "istype(typecheck_obj(), typecheck_obj(/obj/typecheck_thing/child):type)")
    s.case("istype", "istype(typecheck_obj(/obj/typecheck_thing/child), typecheck_obj())")
    s.case("istype", "istype(typecheck_obj(), typecheck_obj(/obj/typecheck_thing/child))")
    s.case("istype", "istype(typecheck_obj(), typecheck_mob())")
    s.case("istype", "istype(typecheck_turf(), typecheck_turf())")
    s.case("istype", "istype(typecheck_area(), typecheck_area())")
    s.case("istype", "istype(world, world)")
    s.case("istype", "istype(list(), list())")
    s.case("istype", "istype(typecheck_obj(), /obj/typecheck_thing/child/grand)")
    s.case("istype", 'istype(typecheck_obj(), text2path("/obj"))')
    s.case("istype", "istype(typecheck_obj(), /obj/typecheck_thing::pathvar)")
    s.case("istype", "istype(typecheck_obj())")
    s.case("istype", "istype()")
    s.case("istype", "istype(typecheck_obj(), /obj, /mob)")
    s.case("istype", "istype(Val = typecheck_obj(), Type = /obj)")
    s.case("istype", "istype(typecheck_deleted(), /datum)")
    s.case("istype", "istype(typecheck_overlays(), /list)")
    s.case("istype", "istype(world.contents, /list)")
    s.case("istype", "istype(args, /list)")
    s.case("istype", "istype(global.vars, /list)")
    s.case("istype", "istype(vector(1, 2), /vector)")
    s.case("istype", "istype(vector(1, 2), /datum)")
    s.case("istype", "istype(new /generator(\"num\", 0, 1), /generator)")
    s.case("istype", "istype(typecheck_obj(), /obj/typecheck_thing/proc/typecheck_p)")
    s.case("istype", "istype(PINF, /datum)")
    s.case("istype", "istype(1, 1)")
    s.case("istype", "istype(null, null)")
    # one-argument istype: declared type of the variable
    implicit = [
        ("obj/typecheck_thing", "typecheck_obj()"),
        ("obj/typecheck_thing", "typecheck_obj(/obj/typecheck_thing/child)"),
        ("obj/typecheck_thing/child", "typecheck_obj()"),
        ("obj/typecheck_thing", "typecheck_mob()"),
        ("obj/typecheck_thing", "null"),
        ("obj/typecheck_thing", "/obj/typecheck_thing"),
        ("obj/typecheck_thing", '"a"'),
        ("obj", "typecheck_obj()"),
        ("mob", "typecheck_mob()"),
        ("atom", "typecheck_turf()"),
        ("atom/movable", "typecheck_am()"),
        ("area", "typecheck_area()"),
        ("turf", "typecheck_area()"),
        ("datum", "new /datum"),
        ("datum", "list()"),
        ("datum", "typecheck_obj()"),
        ("datum/typecheck_d", "typecheck_datum(/datum/typecheck_d/sub/deeper)"),
        ("datum/typecheck_d/sub", "typecheck_datum()"),
        ("list", "list()"),
        ("list", "alist()"),
        ("list", "typecheck_vars()"),
        ("list", "new /datum"),
        ("icon", "icon('test.dmi')"),
        ("icon", "'test.dmi'"),
        ("image", "image('test.dmi')"),
        ("image", "new /mutable_appearance"),
        ("matrix", "matrix()"),
        ("regex", 'regex("a")'),
        ("exception", 'new /exception("x")'),
        ("sound", "new /sound"),
        ("savefile", "null"),
    ]
    for t, v in implicit:
        s.body("istype", [f"var/{t}/X = {v}"], "istype(X)")
    s.body("istype", ["var/X = typecheck_obj()"], "istype(X)")
    s.body("istype", ["var/obj/typecheck_thing/O = typecheck_obj()"], "istype(O.loc)")
    s.body("istype", ["var/obj/typecheck_thing/O = typecheck_obj()"], "istype(O.datumvar)")
    s.body("istype", ["var/obj/typecheck_thing/O = typecheck_obj()"], "istype(O.listvar)")
    s.body("istype", ["var/obj/typecheck_thing/O = typecheck_obj()"], "istype(O.emptylist)")
    s.body("istype", ["var/list/obj/L = list(typecheck_obj())"], "istype(L)")
    s.body("istype", ["var/obj/typecheck_thing/O = typecheck_obj()", "var/obj/typecheck_thing/P = O"],
           "list(istype(O), istype(P), istype(O, P), istype(P, /obj/typecheck_thing/child))")

    # ---------------- astype (closely related to istype) ------------------------------------------
    for v, t in [("typecheck_obj()", "/obj"), ("typecheck_obj()", "/mob"), ("typecheck_obj()", "/datum"),
                 ("null", "/obj"), ('"a"', "/datum"), ("list()", "/list"), ("1", "/datum"),
                 ("/obj", "/obj"), ("typecheck_obj(/obj/typecheck_thing/child)", "typecheck_obj()"),
                 ("typecheck_obj()", "typecheck_obj(/obj/typecheck_thing/child)"), ("typecheck_obj()", "null"),
                 ("image('test.dmi')", "/image"), ("new /mutable_appearance", "/image"),
                 ("typecheck_turf()", "/atom"), ("typecheck_area()", "/turf"), ("world", "/world"),
                 ("matrix()", "/matrix"), ("typecheck_datum()", '"/datum"')]:
        s.case("astype", f"astype({v}, {t})")
    for t, v in [("obj/typecheck_thing", "typecheck_obj()"), ("obj/typecheck_thing", "typecheck_mob()"),
                 ("mob", "typecheck_mob()"), ("list", "list(1)"), ("datum", '"a"')]:
        s.body("astype", [f"var/{t}/X = {v}"], "astype(X)")

    # ---------------- ispath ----------------------------------------------------------------------
    s.sweep("ispath", [ISP_VAL, ISP_TYPE], min_args=2)
    s.case("ispath", "ispath(/obj, /obj, /obj)")
    s.case("ispath", "ispath(/obj/typecheck_thing, /obj, /mob)")
    s.case("ispath", "ispath(Val = /obj, Type = /atom)")
    s.case("ispath", "ispath(/obj/typecheck_thing/child, typecheck_obj():type)")
    s.case("ispath", "ispath(typecheck_obj(/obj/typecheck_thing/child):type, /obj/typecheck_thing)")
    s.case("ispath", "ispath(/obj/typecheck_thing/proc/typecheck_p, /obj/typecheck_thing/proc/typecheck_p)")
    s.case("ispath", "ispath(/obj/typecheck_thing/proc/typecheck_p, /proc)")
    s.case("ispath", "ispath(/proc/typecheck_global, /proc)")
    s.case("ispath", "ispath(/obj/typecheck_thing/verb/typecheck_v, /verb)")
    s.case("ispath", "ispath(/mob/typecheck_mob, world.mob)")
    s.case("ispath", "ispath(/turf, world.turf)")
    s.case("ispath", "ispath(/area, world.area)")
    s.case("ispath", "ispath(/list, /datum)")
    s.case("ispath", "ispath(/icon, /datum)")
    s.case("ispath", "ispath(/image, /datum)")
    s.case("ispath", "ispath(/mutable_appearance, /image)")
    s.case("ispath", "ispath(/alist, /list)")
    s.case("ispath", "ispath(/world, /datum)")
    s.case("ispath", "ispath(/world)")
    s.case("istype", "istype(world, /world)")
    s.case("ispath", "ispath(/client, /datum)")
    s.case("ispath", "ispath(/area, /atom)")
    s.case("ispath", "ispath(/turf, /atom/movable)")
    s.case("ispath", "ispath(/regex, /datum)")
    s.case("ispath", "ispath(/savefile, /datum)")
    s.case("ispath", "ispath(/exception, /datum)")
    s.case("ispath", "ispath(/sound, /datum)")
    s.case("ispath", "ispath(/matrix, /datum)")

    # ---------------- typesof ---------------------------------------------------------------------
    TS = ["/obj/typecheck_thing", "/obj/typecheck_thing/child", "/obj/typecheck_thing/child/grand",
          "/datum/typecheck_d", "/datum/typecheck_d/sub", "/mob/typecheck_mob", "/atom/movable/typecheck_am",
          '"/obj/typecheck_thing"', '"/datum/typecheck_d/sub"', "typecheck_obj()",
          "typecheck_obj(/obj/typecheck_thing/child)", "typecheck_datum()",
          "/obj/typecheck_thing/proc", "/obj/typecheck_thing/child/proc", "/obj/typecheck_thing/child/grand/proc",
          "/obj/typecheck_thing/verb", "/obj/typecheck_thing/child/verb", "/datum/typecheck_d/proc",
          "/datum/typecheck_d/sub/proc", '"/obj/typecheck_thing/proc"', '"/obj/typecheck_thing/verb"',
          '"/obj/typecheck_thing/child/proc"',
          "null", "1", '"a"', '""', '"/typecheck_none"', "list()", "list(/obj/typecheck_thing)",
          "/obj/typecheck_thing/proc/typecheck_p", "/proc/typecheck_global"]
    for t in TS:
        s.case("typesof", f"typesof({t})")
        s.case("typesof", f"typecheck_sorted(typesof({t}))")
    for args in ["/obj/typecheck_thing, /datum/typecheck_d", "/obj/typecheck_thing/child, /obj/typecheck_thing",
                 "/obj/typecheck_thing, /obj/typecheck_thing", "/datum/typecheck_d, null, /datum/typecheck_d/sub",
                 "/datum/typecheck_d/sub, /obj/typecheck_thing/child/grand, /mob/typecheck_mob",
                 "/obj/typecheck_thing/proc, /obj/typecheck_thing", "/datum/typecheck_d/proc, /datum/typecheck_d/proc",
                 '"/datum/typecheck_d", /datum/typecheck_d/sub', "1, /datum/typecheck_d/sub", "null, null",
                 "/datum/typecheck_d/sub/deeper, /datum/typecheck_d/sub, /datum/typecheck_d"]:
        s.case("typesof", f"typesof({args})")
        s.case("typesof", f"typecheck_sorted(typesof({args}))")
    s.case("typesof", "typesof()")
    s.case("typesof", "length(typesof(/obj/typecheck_thing))")
    s.case("typesof", "(/proc/typecheck_global in typesof(/proc))")
    s.case("typesof", "(/obj/typecheck_thing/proc/typecheck_p in typesof(/proc))")
    s.case("typesof", "(/datum/typecheck_d in typesof(/datum))")
    s.case("typesof", "(/obj/typecheck_thing in typesof(/atom/movable))")
    s.case("typesof", "(/obj/typecheck_thing in typesof(/mob))")
    s.case("typesof", "(/list in typesof(/datum))")
    s.case("typesof", "(/image in typesof(/datum))")
    s.case("typesof", "(/mutable_appearance in typesof(/image))")
    s.case("typesof", "(/alist in typesof(/list))")
    s.case("typesof", "(/area in typesof(/atom))")
    s.case("typesof", "(/world in typesof(/datum))")
    s.case("typesof", "(/client in typesof(/datum))")
    s.case("typesof", "typesof(/area)")
    s.case("typesof", "typesof(/turf)")
    s.case("typesof", "typecheck_sorted(typesof(/mob))")
    s.case("typesof", "typecheck_sorted(typesof(/atom/movable))")
    s.case("typesof", "typesof(/list)")
    s.case("typesof", "typesof(/icon)")
    s.case("typesof", "typesof(/world)")
    s.case("typesof", "typesof(/client)")
    s.case("typesof", "typesof(/image)")
    s.case("typesof", "typesof(/regex)")
    s.case("typesof", "typesof(typecheck_obj():type)")
    s.case("typesof", "typesof(typecheck_turf())")
    s.case("typesof", "typesof(world)")
    s.body("typesof", ["var/list/L = typesof(/datum/typecheck_d)", "L += 1"], "L")
    s.body("typesof", ["var/list/A = typesof(/datum/typecheck_d)", "var/list/B = typesof(/datum/typecheck_d)"],
           "list(A == B, A ~= B)")
    s.body("typesof", ["var/list/L = list()", "for(var/T in typesof(/obj/typecheck_thing/proc))",
                       "\tL += \"[T]\""], "typecheck_sorted(L)")
    s.body("typesof", ["var/list/L = list()", "for(var/T in typesof(/obj/typecheck_thing/child/proc))",
                       "\tL += istext(T) ? T : ispath(T)"], "L")

    # ---------------- text2path -------------------------------------------------------------------
    for t in T2P:
        s.call("text2path", t)
    s.case("text2path", "text2path()")
    s.case("text2path", 'text2path("/obj", "/mob")')
    s.case("text2path", 'text2path(T = "/obj")')
    s.case("text2path", 'text2path("[/obj/typecheck_thing]")')
    s.case("text2path", 'text2path("[typecheck_obj():type]")')
    s.case("text2path", 'ispath(text2path("/obj/typecheck_thing/proc/typecheck_p"))')
    s.case("text2path", 'text2path("/obj/typecheck_thing") == /obj/typecheck_thing')
    s.case("text2path", 'text2path("/proc/typecheck_global") == /proc/typecheck_global')
    s.case("text2path", 'text2path("/obj/typecheck_thing/proc/typecheck_p") == /obj/typecheck_thing/proc/typecheck_p')
    s.case("text2path", 'istype(typecheck_obj(), text2path("/obj/typecheck_thing"))')
    s.body("text2path", ['var/T = text2path("/datum/typecheck_d/sub")', "var/datum/typecheck_d/D = new T"],
           "list(D.type, D.x)")

    # ---------------- hascall ---------------------------------------------------------------------
    s.sweep("hascall", [HC_OBJ, HC_NAME], min_args=2)
    s.case("hascall", "hascall()")
    s.case("hascall", "hascall(typecheck_obj())")
    s.case("hascall", 'hascall(typecheck_obj(), "typecheck_p", 1)')
    s.case("hascall", 'hascall(Object = typecheck_obj(), ProcName = "typecheck_p")')
    s.case("hascall", "hascall(typecheck_obj(), /obj/typecheck_thing/proc/typecheck_p)")
    s.body("hascall", ["var/obj/typecheck_thing/O = typecheck_obj()",
                       "O.verbs -= /obj/typecheck_thing/verb/typecheck_v"],
           'list(hascall(O, "typecheck_v"), O.verbs.len)')
    s.body("hascall", ["var/obj/typecheck_thing/O = typecheck_obj()",
                       "O.verbs += /obj/typecheck_thing/child/proc/typecheck_childp"],
           'list(hascall(O, "typecheck_childp"), O.verbs.len)')

    # ---------------- locate (type / tag / ref, no coordinates) -----------------------------------
    s.case("locate", "locate(/obj/typecheck_thing)")
    s.case("locate", "locate(/obj/typecheck_lone)")
    s.case("locate", "locate(/turf)")
    s.case("locate", "locate(/area)")
    s.case("locate", "locate(/atom)")
    s.case("locate", "locate(/mob)")
    s.case("locate", "locate(/turf) in world")
    s.case("locate", "locate(/datum/typecheck_loc)")
    s.case("locate", "locate(null)")
    s.case("locate", "locate(1)")
    s.case("locate", "locate(list())")
    s.case("locate", 'locate("")')
    s.case("locate", 'locate("typecheck_no_such_tag")')
    s.case("locate", 'locate("\\[0x0\\]")')
    s.case("locate", 'locate("\\[0xffffffff\\]")')
    s.case("locate", 'locate("\\[zz\\]")')
    s.case("locate", 'locate("0x0")')
    s.case("locate", "locate(/obj) in null")
    s.case("locate", "locate(/obj) in list()")
    s.case("locate", 'locate(/obj) in "a"')
    s.case("locate", "locate(/obj) in 5")
    s.case("locate", "locate(/turf) in typecheck_area()")
    s.case("locate", "locate(/area) in typecheck_turf()")
    s.case("locate", "locate(/list) in list(list(1))")
    s.case("locate", "locate(/obj) in list(/obj/typecheck_thing)")
    s.case("locate", "locate(/obj/typecheck_thing) in list(1, \"a\", null, /obj/typecheck_thing/child)")
    s.case("locate", 'locate("a") in list("a", "b")')
    s.case("locate", 'locate("c") in list("a", "b")')
    s.case("locate", "locate(1) in list(1, 2)")
    s.case("locate", 'locate(/datum) in list("a" = new /datum)')
    s.case("locate", "locate()")
    s.case("locate", "locate(/obj, /mob)")
    # world / container type searches with live objects
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)"], "locate(/obj/typecheck_thing)")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)"], "locate(/obj/typecheck_thing/child/grand)")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)"], "locate(/obj/typecheck_thing) in world")
    s.body("locate", ["typecheck_nullobj()"], "locate(/obj/typecheck_thing)")
    s.body("locate", ["typecheck_mob()"], "locate(/mob)")
    s.body("locate", ["typecheck_am()"], "locate(/atom/movable/typecheck_am)")
    s.body("locate", ["typecheck_datum(/datum/typecheck_loc/sub)"], "locate(/datum/typecheck_loc)")
    s.body("locate", ["typecheck_datum(/datum/typecheck_loc/sub)"], "locate(/datum/typecheck_loc) in world")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(/obj/typecheck_thing) in O.loc")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(/obj/typecheck_thing) in typecheck_turf()")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(/obj/typecheck_thing) in typecheck_area()")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)",
                      "P.loc = O"], "list(locate(/obj/typecheck_thing/child) in O, locate(/obj/typecheck_thing/child) in typecheck_turf())")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)"],
           "locate(/obj/typecheck_thing/child) in list(O, P)")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)"],
           "locate(P) in list(O, P)")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)"],
           "locate(P) in list(O)")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)"],
           "locate(P) in typecheck_turf()")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(O)")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(O) in world")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)"],
           "locate(/obj/typecheck_thing) in list(\"x\" = P, \"y\" = O)")
    s.body("locate", ["var/obj/O = typecheck_obj()"], "locate(/obj/typecheck_thing) in O.vars")
    # inferred type
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)", "var/obj/typecheck_thing/X = locate()"], "X")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)", "var/obj/typecheck_thing/child/grand/X = locate()"], "X")
    s.body("locate", ["var/obj/O = typecheck_obj()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)",
                      "P.loc = O", "var/obj/typecheck_thing/child/X = locate() in O"], "X")
    s.body("locate", ["var/turf/T = locate()"], "T")
    # tags
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("TYPECHECK_TAG1")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("\\[typecheck_tag1\\]")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate(" typecheck_tag1")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"', "O.tag = null"],
           'locate("typecheck_tag1")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"', 'O.tag = "typecheck_tag2"'],
           'list(locate("typecheck_tag1"), locate("typecheck_tag2"))')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1") in list(O)')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1") in list()')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1") in typecheck_turf()')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1") in typecheck_area()')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1") in world')
    s.body("locate", ["var/obj/O = typecheck_nullobj()", 'O.tag = "typecheck_tag1"'], 'locate("typecheck_tag1")')
    s.body("locate", ["var/datum/typecheck_loc/D = typecheck_datum(/datum/typecheck_loc)", 'D.tag = "typecheck_tag3"'],
           'locate("typecheck_tag3")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_tag1"', "del O"], 'locate("typecheck_tag1")')
    s.body("locate", ["var/obj/O = typecheck_obj()", "O.tag = 5"], "list(O.tag, locate(5), locate(\"5\"))")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = ""'], 'locate("")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "\\[0x0\\]"'], 'locate("\\[0x0\\]")')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'O.tag = "typecheck_dup"',
                      "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)", 'P.tag = "typecheck_dup"'],
           'list(locate("typecheck_dup"), O.tag, P.tag)')
    s.body("locate", ["var/turf/T = locate(1, 1, 1)", "var/old = T.tag", 'T.tag = "typecheck_turftag"',
                      'var/r = locate("typecheck_turftag")', "T.tag = old"], "r")
    # text refs
    s.body("locate", ["var/obj/O = typecheck_obj()"], 'locate("\\ref[O]")')
    s.body("locate", ["var/obj/O = typecheck_obj()"], 'locate("\\ref[O]") == O')
    s.body("locate", ["var/obj/O = typecheck_obj()"], 'locate(ref(O)) == O')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(copytext(r, 2, -1)) == O")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(uppertext(r)) == O")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], 'locate(" [r]") == O')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], 'locate("[r] ") == O')
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"', "del O"], "locate(r)")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(r) in list(O)")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(r) in list()")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(r) in typecheck_turf()")
    s.body("locate", ["var/obj/O = typecheck_obj()", 'var/r = "\\ref[O]"'], "locate(r) in world")
    s.body("locate", ["var/obj/O = typecheck_nullobj()"], 'locate("\\ref[O]") == O')
    s.body("locate", ["var/datum/D = typecheck_datum()"], 'locate("\\ref[D]") == D')
    s.body("locate", ["var/list/L = list(1, 2)"], 'locate("\\ref[L]")')
    s.body("locate", ["var/list/L = list(1, 2)"], 'locate("\\ref[L]") == L')
    s.body("locate", ["var/T = locate(1, 1, 1)"], 'locate("\\ref[T]") == T')
    s.body("locate", ["var/A = locate(/area)"], 'locate("\\ref[A]") == A')
    s.case("locate", 'locate("\\ref[world]") == world')
    s.case("locate", 'locate("\\ref[/obj/typecheck_thing]")')
    s.case("locate", 'locate("\\ref[\"typecheck_str\"]")')
    s.case("locate", 'locate("\\ref[5]")')
    s.case("locate", 'locate("\\ref[null]")')
    s.body("locate", ["var/icon/I = icon('test.dmi')"], 'locate("\\ref[I]") == I')
    s.body("locate", ["var/datum/D = typecheck_datum()", 'var/r = "\\ref[D]"'], 'istext(r) && length(r) > 4')

    # ---------------- initial ---------------------------------------------------------------------
    O = ["var/obj/typecheck_thing/O = typecheck_obj()"]
    C = ["var/obj/typecheck_thing/O = typecheck_obj(/obj/typecheck_thing/child)"]
    for v in ["plain", "name", "icon", "icon_state", "textvar", "pathvar", "numexpr", "fracvar", "nullvar",
              "tmpvar", "listvar", "emptylist", "typedlist", "datumvar", "type", "parent_type",
              "loc", "x", "y", "z", "density", "layer", "dir", "contents", "vars", "verbs", "overlays", "tag",
              "desc", "suffix", "text", "invisibility", "mouse_opacity", "appearance_flags", "plane",
              "color", "alpha", "transform", "pixel_x", "bound_width", "step_size", "glide_size"]:
        s.body("initial", O, f"initial(O.{v})")
    for v in ["plain", "name", "tmpvar", "type", "parent_type", "icon_state"]:
        s.body("initial", C, f"initial(O.{v})")
    s.body("initial", O + ["O.plain = 50", 'O.name = "renamed"', "O.dir = 4"],
           "list(O.plain, initial(O.plain), O.name, initial(O.name), O.dir, initial(O.dir))")
    s.body("initial", O + ["O.globvar = 99", "var/r = initial(O.globvar)", "O.globvar = 9"], "r")
    s.body("initial", O + ["O.statvar = 98", "var/r = initial(O.statvar)", "O.statvar = 11"], "r")
    s.body("initial", O, "list(!!initial(O.listvar), isnull(initial(O.listvar)), islist(initial(O.listvar)), "
                         "istext(initial(O.listvar)), isnum(initial(O.listvar)))")
    s.body("initial", O, "list(!!initial(O.typedlist), isnull(initial(O.typedlist)), islist(initial(O.typedlist)))")
    s.body("initial", O, "list(!!initial(O.datumvar), isnull(initial(O.datumvar)), istype(initial(O.datumvar), /datum))")
    s.body("initial", O, 'initial(O.vars["plain"])')
    s.body("initial", O + ["O.plain = 50"], 'initial(O.vars["plain"])')
    s.body("initial", O + ['var/V = "plain"', "O.plain = 50"], "initial(O.vars[V])")
    s.body("initial", O, 'initial(O.vars["typecheck_nonexistent"])')
    s.body("initial", O, "initial(O.vars[1])")
    s.body("initial", O + ["var/list/L = list(7, 8)", "L[1] = 70"], "initial(L[1])")
    s.body("initial", O + ['var/list/L = list("k" = 7)', 'L["k"] = 70'], 'initial(L["k"])')
    s.body("initial", O + ["O.listvar[1] = 100"], "initial(O.listvar[1])")
    s.body("initial", ["var/obj/typecheck_thing/P = /obj/typecheck_thing/child"], "initial(P.plain)")
    s.body("initial", ["var/obj/typecheck_thing/P = /obj/typecheck_thing/child"], "initial(P.name)")
    s.body("initial", ["var/obj/typecheck_thing/P = /obj/typecheck_thing"], "initial(P.listvar)")
    s.body("initial", ["var/obj/typecheck_thing/P = null"], "initial(P.plain)")
    s.body("initial", ['var/obj/typecheck_thing/P = "a"'], "initial(P.plain)")
    s.body("initial", ["var/obj/typecheck_thing/P = 5"], "initial(P.plain)")
    s.body("initial", ["var/obj/typecheck_thing/P = list()"], "initial(P.plain)")
    s.body("initial", ["var/obj/typecheck_thing/P = typecheck_mob()"], "initial(P.plain)")
    s.body("initial", ["var/obj/typecheck_thing/P = typecheck_mob()"], "initial(P.name)")
    s.body("initial", ["var/datum/typecheck_d/D = typecheck_datum(/datum/typecheck_d/sub)", "D.x = 77"],
           "list(D.x, initial(D.x), initial(D.y), initial(D.z), initial(D.type))")
    s.body("initial", ["var/turf/T = locate(1, 1, 1)"], "list(initial(T.x), initial(T.y), initial(T.name), initial(T.loc))")
    s.body("initial", [], "initial(world.name)")
    s.body("initial", ["var/x = 5", "x = 6"], "initial(x)")
    s.body("initial", O, "initial(O)")
    s.body("initial", O, "initial(O.typecheck_p())")
    s.case("initial", "/obj/typecheck_thing::plain")
    s.case("initial", "/obj/typecheck_thing/child::plain")
    s.case("initial", "/obj/typecheck_thing/child::name")
    s.case("initial", "/datum/typecheck_d/sub::x")
    s.case("initial", "/obj/typecheck_thing::globvar")
    s.case("initial", "/obj/typecheck_thing::constvar")
    s.case("initial", "/obj/typecheck_thing::listvar")
    s.case("initial", "initial(/obj/typecheck_thing::plain)")
    s.case("initial", "initial(/obj/typecheck_thing/child::tmpvar)")
    s.case("initial", "initial(typecheck_obj():plain)")
    s.case("initial", "initial()")
    s.case("initial", "initial(1)")

    # ---------------- issaved ---------------------------------------------------------------------
    for v in ["plain", "tmpvar", "globvar", "statvar", "listvar", "emptylist", "textvar", "name",
              "type", "parent_type", "loc", "x", "y", "z", "contents", "vars", "verbs", "overlays", "underlays",
              "icon", "icon_state", "tag", "density", "dir", "layer", "desc", "locs", "vis_contents",
              "appearance", "transform", "key", "screen_loc", "filters", "gender"]:
        s.body("issaved", O, f"issaved(O.{v})")
    for v in ["plain", "tmpvar", "name"]:
        s.body("issaved", C, f"issaved(O.{v})")
    s.body("issaved", ["var/datum/typecheck_d/D = typecheck_datum()"],
           "list(issaved(D.x), issaved(D.y), issaved(D.z), issaved(D.type), issaved(D.vars), issaved(D.tag))")
    s.body("issaved", ["var/mob/typecheck_mob/M = typecheck_mob()"],
           "list(issaved(M.key), issaved(M.ckey), issaved(M.client), issaved(M.sight), issaved(M.see_invisible))")
    s.body("issaved", ["var/turf/T = locate(1, 1, 1)"], "list(issaved(T.x), issaved(T.loc), issaved(T.name))")
    s.body("issaved", O, 'issaved(O.vars["plain"])')
    s.body("issaved", O, 'issaved(O.vars["tmpvar"])')
    s.body("issaved", O, 'issaved(O.vars["globvar"])')
    s.body("issaved", O + ['var/V = "tmpvar"'], "issaved(O.vars[V])")
    s.body("issaved", O, 'issaved(O.vars["typecheck_nonexistent"])')
    s.body("issaved", O, "issaved(O.vars[1])")
    s.body("issaved", O + ["var/list/L = list(1, 2)"], "issaved(L[1])")
    s.body("issaved", O, "issaved(O.listvar[1])")
    s.body("issaved", ["var/obj/typecheck_thing/P = /obj/typecheck_thing"], "list(issaved(P.plain), issaved(P.tmpvar))")
    s.body("issaved", ["var/obj/typecheck_thing/P = null"], "issaved(P.plain)")
    s.body("issaved", ['var/obj/typecheck_thing/P = "a"'], "issaved(P.plain)")
    s.body("issaved", [], "list(issaved(world.maxx), issaved(world.name))")
    s.body("issaved", ["var/x = 5"], "issaved(x)")
    s.case("issaved", "issaved(/obj/typecheck_thing::plain)")
    s.case("issaved", "issaved(/obj/typecheck_thing::tmpvar)")
    s.case("issaved", "issaved(typecheck_obj():tmpvar)")
    s.case("issaved", "issaved()")
    s.case("issaved", "issaved(1)")

    # ---------------- nameof (compile-time) -------------------------------------------------------
    s.body("nameof", O, "nameof(O.plain)")
    s.body("nameof", O, "nameof(O.tmpvar)")
    s.body("nameof", O, "nameof(O.name)")
    s.body("nameof", O, "nameof(O.vars)")
    s.body("nameof", O, "nameof(O)")
    s.body("nameof", O, "nameof(O.typecheck_p)")
    s.body("nameof", ["var/typecheck_local = 1"], "nameof(typecheck_local)")
    for e in ["/obj/typecheck_thing", "/obj/typecheck_thing/child/grand", "/datum", "/obj/typecheck_thing::plain",
              "/obj/typecheck_thing::globvar", "/obj/typecheck_thing::typecheck_p()",
              "/obj/typecheck_thing/child::typecheck_childp()", "/obj/typecheck_thing::typecheck_v()",
              "/proc/typecheck_global", "/obj/typecheck_thing/proc/typecheck_p",
              "/obj/typecheck_thing/verb/typecheck_v", "world.maxx", "global.PINF", "PINF",
              "/datum/typecheck_d::x", "__TYPE__", "__PROC__", "1", '"a"', "/obj/typecheck_thing/proc",
              "/list", "/icon"]:
        s.case("nameof", f"nameof({e})")
    s.case("nameof", "nameof()")
    s.case("nameof", "nameof(/obj, /mob)")

    build_extra(s)


def build_extra(s):
    O = ["var/obj/typecheck_thing/O = typecheck_obj()"]
    C = ["var/obj/typecheck_thing/O = typecheck_obj(/obj/typecheck_thing/child)"]

    # ---------------- ispointer -------------------------------------------------------------------
    s.body("ispointer", ["var/x = 1"], "ispointer(&x)")
    s.body("ispointer", ["var/x = 1", "var/p = &x"], "list(ispointer(p), *p)")
    s.body("ispointer", O, "ispointer(&O.plain)")
    s.body("ispointer", ["var/list/L = list(1, 2)"], "ispointer(&L[1])")
    s.body("ispointer", ["var/list/L = list(1, 2)", "var/p = &L[2]", "L.len = 1"], "ispointer(p)")
    s.body("ispointer", ["var/datum/typecheck_d/D = new", "var/p = &D.x", "del D"], "ispointer(p)")
    s.body("ispointer", ["var/x = 1", "var/list/L = list(&x)"], "ispointer(L[1])")
    for v in ["null", "1", "0", '"a"', "typecheck_obj()", "list()", "/obj", "world", "typecheck_datum()"]:
        s.case("ispointer", f"ispointer({v})")
    s.case("ispointer", "ispointer()")
    s.case("ispointer", "ispointer(1, 2)")

    # ---------------- issaved: const / datum / typed list / builtin via vars ------------------------
    s.body("issaved", O, "issaved(O.constvar)")
    s.case("issaved", "issaved(/obj/typecheck_thing::constvar)")
    s.body("issaved", O, 'issaved(O.vars["constvar"])')
    s.body("issaved", O, "issaved(O.datumvar)")
    s.body("issaved", O, "issaved(O.typedlist)")
    s.body("issaved", O, 'issaved(O.vars["name"])')
    s.body("issaved", O, 'issaved(O.vars["statvar"])')
    s.body("issaved", O, "issaved(O.statvar)")

    # ---------------- implicit src inside a type proc ------------------------------------------------
    s.body("initial", O + ["O.plain = 50"], "O.typecheck_selfq()")
    s.body("initial", C + ["O.plain = 50"], "O.typecheck_selfq()")
    s.body("initial", O, "O.typecheck_selfq()")

    # ---------------- instance :: operator ----------------------------------------------------------
    s.body("initial", O + ["O.plain = 50"], "initial(O::plain)")
    s.body("initial", O + ["O.plain = 50"], "O::plain")
    s.body("initial", C + ["O.plain = 50"], "list(O::plain, initial(O::plain))")
    s.body("nameof", O, "nameof(O::plain)")
    s.case("nameof", "nameof(/obj/typecheck_thing::name)")
    s.case("nameof", "nameof(/obj/typecheck_thing/child::typecheck_p())")
    s.case("nameof", "nameof(/obj/typecheck_thing::statvar)")
    s.case("nameof", "nameof(world)")
    s.body("nameof", ["var/list/L = list(1)"], "nameof(L[1])")

    # ---------------- initial of a top-level global ---------------------------------------------------
    s.body("initial", ["typecheck_g = 4", "var/r = list(typecheck_g, initial(typecheck_g))", "typecheck_g = 3"], "r")
    s.body("initial", ["typecheck_g = 4", "var/r = list(global.typecheck_g, initial(global.typecheck_g))",
                       "typecheck_g = 3"], "r")
    s.body("issaved", [], "issaved(typecheck_g)")
    s.body("nameof", [], "nameof(typecheck_g)")
    s.body("nameof", [], "nameof(global.typecheck_g)")
    s.body("initial", ["var/list/L = list(1, 2)", "L.len = 5"], "list(L.len, initial(L.len))")

    # ---------------- __IMPLIED_TYPE__ ---------------------------------------------------------------
    s.body("istype", ["var/obj/typecheck_thing/X = typecheck_obj(/obj/typecheck_thing/child)"],
           "istype(X, __IMPLIED_TYPE__)")
    s.body("istype", ["var/obj/typecheck_thing/X = typecheck_mob()"], "istype(X, __IMPLIED_TYPE__)")
    s.body("istype", ["var/obj/typecheck_thing/child/X = typecheck_obj()"], "istype(X, __IMPLIED_TYPE__)")
    s.body("istype", ["var/obj/typecheck_thing/X = __IMPLIED_TYPE__"], "X")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)",
                      "var/obj/typecheck_thing/X = locate(__IMPLIED_TYPE__)"], "X")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)",
                      "var/obj/typecheck_thing/child/grand/X = locate(__IMPLIED_TYPE__)"], "X")
    s.body("locate", ["typecheck_mob()", "var/mob/typecheck_mob/X = locate(__IMPLIED_TYPE__)"], "X")

    # ---------------- istype(Val) on proc args, src and usr -------------------------------------------
    for v in ["typecheck_obj()", "typecheck_obj(/obj/typecheck_thing/child)", "typecheck_mob()", "null", '"a"',
              "/obj/typecheck_thing"]:
        s.case("istype", f"typecheck_argq({v})")
    s.body("istype", O, "O.typecheck_selfist()")
    s.body("istype", C, "O.typecheck_selfist()")
    s.case("istype", "typecheck_usrq()")

    # ---------------- istype with more builtin types --------------------------------------------------
    for v, t in [("alist()", "/list"), ("list()", "/alist"), ("alist()", "/alist"), ("alist()", "/datum"),
                 ("new /savefile", "/datum"), ("new /savefile", "/savefile"), ("new /sound", "/datum"),
                 ("new /sound", "/sound"), ('new /exception("x")', "/datum"), ('new /exception("x")', "/exception"),
                 ('file("test.dmi")', "/datum"), ("'test.dmi'", "/datum"), ("world", "/client"),
                 ("world", "/datum"), ('regex("a")', "/datum"), ("vector(1, 2)", "/list"),
                 ('new /generator("num", 0, 1)', "/datum"), ("typecheck_obj()", "/world"),
                 ("typecheck_obj()", "/client"), ("typecheck_obj()", "/vector"), ("typecheck_obj()", "/generator"),
                 ("typecheck_obj()", "/alist"), ("typecheck_obj()", "/savefile"), ("typecheck_obj()", "/sound"),
                 ("typecheck_obj()", "/exception"), ("matrix()", "/datum"), ("icon('test.dmi')", "/datum"),
                 ("image('test.dmi')", "/datum"), ("new /mutable_appearance", "/datum")]:
        s.case("istype", f"istype({v}, {t})")

    # ---------------- locate: text path / runtime type / non-atom instances / containers --------------
    s.body("locate", ["typecheck_obj()"], 'locate("/obj/typecheck_thing")')
    s.body("locate", O, 'locate("/obj/typecheck_thing") in list(O)')
    s.body("locate", O, 'locate("/obj/typecheck_thing") in typecheck_turf()')
    s.body("locate", O + ["var/T = /obj/typecheck_thing"], "locate(T)")
    s.body("locate", O + ["var/T = /obj/typecheck_thing"], "locate(T) in typecheck_turf()")
    s.body("locate", O, 'locate(text2path("/obj/typecheck_thing"))')
    s.body("locate", O, "locate(typecheck_obj(/obj/typecheck_thing/child):type) in list(O)")
    s.body("locate", O, "locate(O.type) in list(O)")
    s.body("locate", ["var/datum/D = typecheck_datum()"], "locate(D) == D")
    s.body("locate", ["var/datum/D = typecheck_datum()"], "(locate(D) in world) == D")
    s.case("locate", "locate(/obj) in new /datum")
    s.body("locate", ["typecheck_obj(/obj/typecheck_thing/child)"], "locate(/obj/typecheck_thing) in world.contents")
    s.body("locate", O, "locate(/obj/typecheck_thing) in O.contents")
    s.body("locate", O + ["var/obj/P = typecheck_obj(/obj/typecheck_thing/child)", "P.loc = O"],
           "locate(/obj/typecheck_thing) in O.contents")
    s.body("locate", ["var/mob/M = typecheck_mob()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)",
                      "P.loc = M"], "locate(/obj/typecheck_thing) in M")
    s.body("locate", ["var/mob/M = typecheck_mob()", "var/obj/P = typecheck_obj(/obj/typecheck_thing/child)",
                      "P.loc = M"], "locate(/obj/typecheck_thing) in M.contents")

    # ---------------- locate(TextRef) for more value kinds ----------------------------------------------
    s.body("locate", ["var/image/I = image('test.dmi')"], 'locate("\\ref[I]") == I')
    s.body("locate", ["var/mutable_appearance/I = new /mutable_appearance"], 'locate("\\ref[I]") == I')
    s.body("locate", ['var/regex/R = regex("a")'], 'locate("\\ref[R]") == R')
    s.body("locate", ["var/matrix/M = matrix()"], 'locate("\\ref[M]") == M')
    s.body("locate", ["var/list/L = list(1, 2)"], "locate(ref(L)) == L")
    s.body("locate", ["var/list/L = alist(a = 1)"], 'locate("\\ref[L]") == L')
    s.body("locate", ['var/exception/E = new /exception("x")'], 'locate("\\ref[E]") == E')
    s.body("locate", ["var/datum/D = vector(1, 2)"], 'locate("\\ref[D]") == D')

    # ---------------- hascall on builtin non-atom objects -----------------------------------------------
    for o, n in [("list(1)", "Find"), ("list(1)", "Add"), ("list(1)", "New"), ("list(1)", "typecheck_dp"),
                 ("icon('test.dmi')", "Blend"), ("icon('test.dmi')", "Find"), ('regex("a")', "Find"),
                 ('regex("a")', "Replace"), ("matrix()", "Turn"), ("matrix()", "Find"),
                 ("image('test.dmi')", "New"), ("image('test.dmi')", "Blend"), ("world", "Reboot"),
                 ("world", "Export"), ("world", "New"), ("new /savefile", "ExportText"),
                 ("new /savefile", "Lock"), ("alist()", "Find"), ('new /exception("x")', "New"),
                 ("new /sound", "New"), ("vector(1, 2)", "Normalize")]:
        s.case("hascall", f"hascall({o}, {Q(n)})")
    s.body("hascall", O + ["O.verbs += /datum/typecheck_d/proc/typecheck_dp"],
           'list(hascall(O, "typecheck_dp"), O.verbs.len)')
    s.body("hascall", O + ["O.verbs -= /obj/typecheck_thing/verb/typecheck_v"],
           'list(hascall(O, "typecheck verb"), hascall(O, "typecheck_v"))')
    s.body("hascall", O, 'list(hascall(O, "typecheck verb"), hascall(O, "typecheck_v"))')

    # ---------------- text2path inherited verb / proc paths ---------------------------------------------
    for t in ["/obj/typecheck_thing/child/verb/typecheck_v", "/obj/typecheck_thing/child/grand/verb/typecheck_v",
              "/datum/typecheck_d/sub/proc/typecheck_dp", "/datum/typecheck_d/sub/deeper/proc/typecheck_dp",
              "/obj/typecheck_thing/child/grand/proc/typecheck_p", "/datum/typecheck_d/sub/verb/typecheck_dp"]:
        s.call("text2path", Q(t))
    s.case("text2path", 'text2path("/obj/typecheck_thing/child/verb/typecheck_v") == /obj/typecheck_thing/verb/typecheck_v')

    # ---------------- typesof text forms ----------------------------------------------------------------
    for t in ["obj/typecheck_thing", "/obj/typecheck_thing/", "/obj/typecheck_thing/proc/",
              "/obj/typecheck_thing/verb/", " /obj/typecheck_thing", "datum/typecheck_d/proc"]:
        s.case("typesof", f"typecheck_sorted(typesof({Q(t)}))")
    s.case("typesof", "typecheck_sorted(typesof(/verb))")
    s.case("typesof", "(/obj/typecheck_thing/verb/typecheck_v in typesof(/verb))")
    s.case("typesof", "(/proc/typecheck_global in typesof(/obj/typecheck_thing/proc))")
    s.case("typesof", "(/proc/typecheck_global in typesof(/datum/proc))")
    s.case("typesof", "(/datum/typecheck_d/proc/typecheck_dp in typesof(/proc))")

    # ---------------- isfile / isicon on assigned icons and other resources -----------------------------
    s.body("isfile", O + ["O.icon = icon('test.dmi', \"solid\")"], "list(isfile(O.icon), isicon(O.icon))")
    s.body("isfile", O + ["O.icon = 'small.dmi'"], "list(isfile(O.icon), isicon(O.icon))")
    s.body("isfile", O + ["O.icon = null"], "list(isfile(O.icon), isicon(O.icon))")
    s.case("isfile", "isfile(new /savefile)")
    s.case("isicon", "isicon(new /savefile)")
    s.case("isfile", 'isfile(new /sound("typecheck_none.ogg"))')
    s.case("isfile", 'isfile(fcopy_rsc(file("test.dmi")))')
    s.case("isicon", 'isicon(fcopy_rsc(file("test.dmi")))')

    # ---------------- ispath newer builtin types --------------------------------------------------------
    for e in ["/alist", "/vector", "/generator", "/vector, /datum", "/generator, /datum", "/alist, /datum",
              "/mutable_appearance, /datum", "/pixloc", "/pixloc, /datum", "/database", "/database/query, /datum"]:
        s.case("ispath", f"ispath({e})")
