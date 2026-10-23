"""Builtin datum-like types: /vector, /pixloc, /exception (+ throw/catch), /datum builtin vars
(type, parent_type, tag, vars), /callee (callee/caller), /sound, /generator.

Likely OD divergences aimed at (from the OD source):
- /vector: OD's Turn() returns a NEW 2D vector instead of rotating the source (docs: modifies A, and
  turns clockwise; turn() is counter-clockwise); V.z = n always throws; V[i] = n throws; += / *= mutate
  the shared object (BYOND documents vectors as primitive values); vector(Pixloc) is unimplemented;
  vector("1, 2") parsing via float.Parse; 2D/3D promotion rules for * and /; division-by-zero checks.
- /pixloc: OD implements it in DM (DMStandard/Types/PixLoc.dm): no pixloc(Atom), pixloc(Atom, x, y),
  pixloc(Pixloc, Vector) forms, no operators, setting x/y does not update loc/step_x.
- /exception: OD's default line is 0 (False) rather than null.
- /sound: OD's environment/echo/x/y/z/len/offset defaults are null; sound(S) copies only 5 vars.
- /callee: OD throws on expired callees; name is the verb name.
- /generator: argument validation.
"""
import struct
import wave
from pathlib import Path

from pools import NUM_S, OTHER, TEXT_S
from gen import dm_str

HERE = Path(__file__).resolve().parent
WAV = HERE / "datums_beep.wav"


def make_wav():
    if WAV.exists():
        return
    with wave.open(str(WAV), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", (i % 40) * 500 - 10000) for i in range(800)))


DEFS = r'''
// ---------- helpers: printing ----------
/proc/datums_v(v)
	if(istype(v, /vector))
		var/vector/V = v
		return list(V, V.len)
	return v

/proc/datums_px(p)
	if(istype(p, /pixloc))
		var/pixloc/P = p
		return list(P, P.loc, P.step_x, P.step_y)
	return p

/proc/datums_names(datum/D)
	var/list/L = list()
	for(var/k in D.vars)
		L += k
	return L

/proc/datums_sound(sound/S)
	if(!istype(S, /sound))
		return S
	return list("file" = S.file, "repeat" = S.repeat, "wait" = S.wait, "channel" = S.channel, "volume" = S.volume, "frequency" = S.frequency, "pitch" = S.pitch, "pan" = S.pan, "params" = S.params, "falloff" = S.falloff, "atom" = S.atom, "transform" = S.transform, "x" = S.x, "y" = S.y, "z" = S.z, "environment" = S.environment, "echo" = S.echo, "len" = S.len, "offset" = S.offset, "priority" = S.priority, "status" = S.status)

// ---------- datum types ----------
/datum/datums_thing
	var/a = 1
	var/b = "bee"
	var/list/c = list(1, 2)
	var/tmp/t = 3
	var/const/k = 5
	var/static/st = 7
	var/global/gl = 8
	var/nul
	var/datum/datums_thing/other

/datum/datums_thing/child
	a = 2
	var/d = "dee"

/datum/datums_thing/proc/whoami(x)
	var/callee/c = callee
	return list(c:name, c:src == src, c:type, c:args, c:proc)

/datum/datums_thing/proc/callme()
	return datums_inner(1, 2)

/datums_root
	var/r = 1

/datums_objish
	parent_type = /obj
	name = "objish"

/obj/datums_verbobj
	name = "verbobj"

/obj/datums_verbobj/verb/datums_verb()
	set name = "Nice Verb"
	set desc = "Verb desc"
	set category = "Cat"
	var/callee/c = callee
	return list(c:name, c:desc, c:category, c:proc)

/exception/datums_ex
	var/extra = "more"

// ---------- callee helpers ----------
/proc/datums_self(a, b)
	var/callee/c = callee
	return list(c:name, c:type, c:proc, c:src, c:usr, c:args, c:desc, c:category)

/proc/datums_outer(x)
	return datums_inner(x, x + 1)

/proc/datums_inner(p, q)
	var/callee/c = caller
	return list(c:name, c:proc, c:args, c:src, c:type)

/proc/datums_chain()
	return datums_chain2(1)

/proc/datums_chain2(n)
	return datums_chain3(n, 2)

/proc/datums_chain3(n, m)
	var/list/L = list()
	for(var/callee/p = callee, p, p = p:caller)
		L += p:name
		L[p:name] = p:args.Copy()
		if(p:name == "datums_chain")
			break
	return L

/proc/datums_get_callee()
	return callee

/proc/datums_mutargs(a, b)
	var/callee/c = callee
	c:args[1] = "changed"
	return list(a, b, args)

/proc/datums_addargs(a)
	var/callee/c = callee
	c:args += 5
	return list(args.len, a, args)

/proc/datums_callee_eq()
	var/callee/c1 = callee
	var/callee/c2 = callee
	return list(c1 == c2, c1:caller == caller)

/proc/datums_file_line()
	var/callee/c = callee
	return list(c:file, c:line)

/proc/datums_callee_vars()
	var/callee/c = callee
	return datums_names(c)

/proc/datums_named(a = 1, b = 2)
	var/callee/c = callee
	return c:args

/proc/datums_callee_text()
	var/callee/c = callee
	return "[c:name]"

// ---------- exception helpers ----------
/proc/datums_throw(v)
	throw v

/proc/datums_catch(v)
	try
		throw v
	catch(var/e)
		return list(e)
	return "not caught"

/proc/datums_catch_typed(v)
	try
		throw v
	catch(var/exception/e)
		return list(e, istype(e, /exception))
	return "not caught"

/proc/datums_catch_call(v)
	try
		datums_throw(v)
	catch(var/e)
		return list("caught", e)
	return "not caught"

/proc/datums_rethrow(v)
	try
		try
			throw v
		catch(var/e)
			throw list("wrapped", e)
	catch(var/e2)
		return e2

/proc/datums_rt(kind)
	try
		switch(kind)
			if(1)
				var/datum/d = null
				return d.type
			if(2)
				var/z = 0
				return 1 / z
			if(3)
				var/a = 2
				a += "Hello"
				return a
			if(4)
				var/list/L = list(1)
				return L[5]
			if(5)
				var/datum/d = new
				return call(d, "datums_nope")()
			if(6)
				var/datum/d = new
				return d.vars["datums_nope_var"]
			if(7)
				return text2num(list()) + list()
		return "no error"
	catch(var/exception/e)
		return e
	return "fell through"

/proc/datums_rt_shape(kind)
	var/exception/e = datums_rt(kind)
	if(!istype(e, /exception))
		return list("not exception", e)
	return list(e.type, istext(e.name), isnull(e.desc), isnull(e.file) || istext(e.file), isnull(e.line) || isnum(e.line))

/proc/datums_after_catch()
	var/out = "a"
	try
		out += "b"
		throw "x"
		out += "never"
	catch
		out += "c"
	out += "d"
	return out

/proc/datums_try_return()
	try
		return "from try"
	catch(var/e)
		return list("caught", e)
	return "after"

/proc/datums_catch_noname()
	try
		throw 5
	catch
		return "bare catch"
	return "after"
'''


def build(s):
    make_wav()
    s.resource("datums_beep.wav", WAV)
    s.dm(DEFS)
    vectors(s)
    pixlocs(s)
    exceptions(s)
    datum_vars(s)
    callees(s)
    sounds(s)
    generators(s)


# =====================================================================================================
# /vector
# =====================================================================================================
VECS = ["vector(1, 2)", "vector(1, 2, 3)", "vector(0, 0)", "vector(-1.5, 4, 0.25)", "vector(3, -4)"]
RHS_NONVEC = ["0", "1", "-1", "2", "0.5", "null", '"a"', "list(1, 2)", "new /datum", "PINF"]


def vectors(s):
    P = "vector"
    v = lambda e: f"datums_v({e})"
    # ---- constructor: one argument of every kind ----
    ONE = TEXT_S + NUM_S + OTHER + [
        '"1,2"', '"1x2"', '"1,2,3"', '"1x2x3"', '"1, 2"', '" 1,2 "', '"1,2,3,4"', '"1"', '"a,b"',
        '"1.5,-2e3"', '"1,,2"', '"1,2,"', '"1X2"', '"1;2"', '"-1x-2"', '"1e2x3"', '"0x10,2"', '"NAN,1"',
        '"inf,1"', '",1,2"', '"1 2"',
        "list(1, 2)", "list(1, 2, 3)", "list(1, 2, 3, 4)", "list(1)", 'list("1", "2")', "list(null, 2)",
        'list("x" = 1, "y" = 2)', "list(1.5, -2.5)", "list(list(1), 2)",
        "vector(1, 2)", "vector(1, 2, 3)", "pixloc(33, 65, 1)", "pixloc(1, 1, 1)", "locate(2, 3, 1)",
        "matrix()", "NAN", "NINF"]
    s.sweep(P, [ONE], fmt=lambda a: v(f"vector({a})"))
    # ---- two and three numeric arguments ----
    N2 = ["0", "1", "-1", "0.5", "100", "null", '"3"', "PINF", "NAN", "list(1)"]
    s.sweep(P, [N2, N2], fmt=lambda a, b: v(f"vector({a}, {b})"))
    N3 = ["0", "1", "-2", "0.5", "null", '"3"', "PINF", "NAN"]
    s.sweep(P, [N3, N3, N3], full_upto=0, fmt=lambda a, b, c: v(f"vector({a}, {b}, {c})"))
    for e in ["vector()", "vector(1, 2, 3, 4)", "vector(x = 1, y = 2)", "vector(y = 2, x = 1)",
              "vector(x = 1, y = 2, z = 3)", "vector(1, 2, z = 3)", "vector(z = 3)", "new /vector(1, 2)",
              "new /vector(1, 2, 3)", "new /vector()", 'new /vector("4x5")', "new /vector(list(7, 8, 9))",
              "vector(1, 2, null)", "vector(1, null, 3)", "vector(vector(1, 2), 5)", "vector(1, vector(1, 2))",
              "vector(0.1, 0.2, 0.3)", "vector(16777217, 1)", "vector(-0, 0)", "vector(1e-7, -1e-7, 1e38)"]:
        s.case(P, v(e))
    # ---- vars, type, identity ----
    for e in VECS + ["vector(1.5, -2.5, 3.49)"]:
        for var in ("x", "y", "z", "len", "size", "type"):
            s.body(P, [f"var/vector/V = {e}"], f"V.{var}")
        if e not in VECS[:2]:
            continue
        s.body(P, [f"var/vector/V = {e}"], 'V.vars')
        s.body(P, [f"var/vector/V = {e}"], 'V.tag')
        s.body(P, [f"var/vector/V = {e}"], 'V.parent_type')
        s.body(P, [f"var/vector/V = {e}"], 'V:size')
        s.body(P, [f"var/vector/V = {e}"], 'V["x"]')
        s.case(P, f'"[{e}]"')
        s.case(P, f"json_encode({e})")
        s.case(P, f"length({e})")
        s.body(P, [f"var/vector/V = {e}", "var/out = list()", "for(var/c in V)", "\tout += c"], "out")
        for i in ["1", "2", "3", "4", "0", "-1", "1.5", '"x"', "null"]:
            s.body(P, [f"var/vector/V = {e}"], f"V[{i}]")
    for e in ["istype(vector(1, 2), /vector)", "istype(vector(1, 2), /datum)", "isnum(vector(1, 2))",
              "islist(vector(1, 2))", "istext(vector(1, 2))", "isnull(vector(0, 0))", "ispath(vector(1, 2))",
              "isicon(vector(1, 2))", "ismovable(vector(1, 2))", "isloc(vector(1, 2))",
              "vector(1, 2) ? 1 : 0", "vector(0, 0) ? 1 : 0", "!vector(0, 0)", "!vector(1, 2)",
              "vector(1, 2) in list(vector(1, 2))", "list(vector(1, 2)).Find(vector(1, 2))",
              "list(1, 2) ~= vector(1, 2)", "vector(1, 2) ~= vector(1, 2)", "vector(1, 2) ~! vector(1, 2)",
              "vector(1, 2) ~= vector(1, 2, 0)", "num2text(vector(1, 2))", "text2num(vector(1, 2))",
              "\"[vector(0.1, 1e7, 16777217)]\"", "\"[vector(PINF, NAN)]\"", "\"[vector(1, 2, 0)]\"",
              "\"x\" + vector(1, 2)", "length(\"[vector(1, 2)]\")"]:
        s.case(P, e)
    # Assoc key use
    s.body(P, ["var/list/L = list()", "L[vector(1, 2)] = 5"], "list(L.len, L[vector(1, 2)])")
    s.body(P, ["var/list/L = list(vector(1, 2), vector(1, 2))", "L -= vector(1, 2)"], "L")
    # ---- setting vars ----
    for e in ["vector(1, 2)", "vector(1, 2, 3)"]:
        for val in ["2", "3", "1", "4", "2.5", "null", '"3"', "0", "-3", "3.0000001"]:
            s.body(P, [f"var/vector/V = {e}", f"V.len = {val}"], "list(V, V.len)")
        for var in ("x", "y", "z"):
            for val in ["5", "-1.5", "null", '"a"', "NAN", "list()"]:
                s.body(P, [f"var/vector/V = {e}", f"V.{var} = {val}"], "list(V, V.len)")
        s.body(P, [f"var/vector/V = {e}", "V.z = 9", "V.len = 3"], "V")
        s.body(P, [f"var/vector/V = {e}", "V.len = 3", "V.z = 9", "V.len = 2", "V.len = 3"], "V")
        for i, val in [("1", "7"), ("2", "8"), ("3", "9"), ("4", "0"), ("0", "1"), ('"x"', "1")]:
            s.body(P, [f"var/vector/V = {e}", f"V[{i}] = {val}"], "list(V, V.len)")
        s.body(P, [f"var/vector/V = {e}", "V.type = /datum"], "V")
        s.body(P, [f"var/vector/V = {e}", 'V.vars["x"] = 4'], "V")
        s.body(P, [f"var/vector/V = {e}", 'V.tag = "datums_vtag"', "var/r = locate(\"datums_vtag\")",
                   "V.tag = null"], "list(r, V)")
        s.body(P, [f"var/vector/V = {e}", "V.foo = 1"], "V")
    for e in VECS + ["vector(0, 0, 0)", "vector(1e-20, 0)", "vector(PINF, 1)", "vector(NAN, 1)"]:
        for val in ["1", "10", "0", "-1", "0.5", "NAN", "null", '"2"']:
            s.body(P, [f"var/vector/V = {e}", f"V.size = {val}"], "list(V, V.size)")
    # ---- value vs reference semantics ----
    for op in ["A.x = 5", "A.len = 3", "A.size = 10", "A += vector(1, 1)", "A -= vector(1, 1)", "A *= 2",
               "A /= 2", "A *= vector(2, 3)", "A /= vector(2, 4)", "A.Normalize()", "A.Turn(90)", "A++",
               "A--", "A = vector(9, 9)", "A |= vector(1, 1)", "A &= vector(1, 1)", "A %= 2", "A **= 2",
               "A[1] = 5", "A.Turn(vector(0, 0, 90))"]:
        s.body(P, ["var/vector/A = vector(3, 4)", "var/vector/B = A", op], "list(A, B, A == B)")
    s.body(P, ["var/vector/A = vector(3, 4)", "var/list/L = list(A)", "A.x = 7"], "L")
    s.body(P, ["var/datum/datums_thing/T = new", "T.other = null", "var/vector/A = vector(3, 4)",
               "T.c = list(A)", "A += vector(1, 1)"], "T.c")
    # ---- arithmetic with vectors and numbers ----
    for a in VECS:
        for b in VECS + RHS_NONVEC:
            for op in "+-*/":
                s.case(P, v(f"{a} {op} {b}"))
        for b in ["2", "0", "null", '"a"', "list(1, 2)"]:
            for op in "+-*/":
                s.case(P, v(f"{b} {op} {a}"))
        for b in ["2", "0", "vector(2, 2)"]:
            for op in ["%", "**", "%%"]:
                s.case(P, v(f"{a} {op} {b}"))
        for op in ["-", "~", "!"]:
            s.case(P, v(f"{op}{a}"))
        s.body(P, [f"var/vector/V = {a}", "V++"], v("V"))
        s.body(P, [f"var/vector/V = {a}", "V--"], v("V"))
        for b in VECS[:3] + ["list(1, 2)", "null"]:
            for op in ["==", "!=", "<", ">="]:
                s.case(P, f"{a} {op} {b}")
    for e in ["vector(1, 2) == vector(1, 2, 0)", "vector(1, 2, 0) == vector(1, 2)", "vector(0, 0) == 0",
              "vector(0, 0) == null", "vector(NAN, 1) == vector(NAN, 1)", "vector(1, 2) / vector(0, 2)",
              "vector(1, 2) / vector(2, 0)", "vector(1, 2, 3) / vector(1, 2)", "vector(1, 2) / vector(1, 2, 0)",
              "vector(1, 2, 3) / vector(1, 2, 0)", "vector(1, 2) / 0", "vector(0, 0) / 0",
              "vector(1, 2) * vector(1, 2, 3)", "vector(1, 2, 3) * vector(1, 2)", "vector(1, 2) - vector(0, 0, 5)",
              "vector(1, 2) + pixloc(1, 1, 1)", "vector(1, 2) - pixloc(1, 1, 1)", "vector(1, 2) * matrix()",
              "matrix() * vector(1, 2)", "vector(1e30, 1e30) * 1e30", "vector(16777216, 1) + vector(1, 0)",
              "vector(0.1, 0.2) + vector(0.2, 0.1)"]:
        s.case(P, v(e))
    # Augmented assignment, result and the type the variable ends up holding
    for a in ["vector(1, 2)", "vector(1, 2, 3)"]:
        for b in ["vector(1, 1)", "vector(1, 1, 1)", "2", "0", "null", '"a"', "list(1, 2)"]:
            for op in ["+=", "-=", "*=", "/="]:
                s.body(P, [f"var/vector/V = {a}", f"V {op} {b}"], v("V"))
    for b in ["vector(1, 1)", "vector(1, 1, 1)"]:
        for op in ["+=", "-=", "*=", "/="]:
            s.body(P, ["var/n = 2", f"n {op} {b}"], v("n"))
    # ---- builtin math procs ----
    MV = VECS + ["vector(1.5, -2.5, 3.49)", "vector(-0.5, 0.5)", "vector(NAN, PINF)"]
    for f in ["round", "floor", "ceil", "trunc", "fract", "abs", "sign", "sqrt", "min", "max", "isnan"]:
        for a in MV:
            s.case(P, v(f"{f}({a})"))
    for a in ["vector(1, 2)", "vector(1, 2, 3)", "vector(1.5, -2.5, 3.49)", "vector(NAN, PINF)"]:
        for b in ["0.5", "2", "0", "-1", "vector(0.5, 2)", "vector(0.5, 2, 3)", "null"]:
            s.case(P, v(f"round({a}, {b})"))
    MM = ["vector(1, 5)", "vector(3, 2)", "vector(3, 2, 7)", "vector(-1, -1, -1)", "2", "null"]
    for f in ["min", "max"]:
        s.sweep(P, [MM, MM], fmt=lambda a, b, f=f: v(f"{f}({a}, {b})"))
        s.case(P, v(f"{f}(vector(1, 5), vector(3, 2), vector(2, 9))"))
        s.case(P, v(f"{f}(list(vector(1, 5), vector(3, 2)))"))
    CL = ["0", "1", "vector(0, 0)", "vector(1, 1)", "vector(2, 2, 2)", "null"]
    for a in ["vector(-2, 0.5)", "vector(3, -4, 0.5)"]:
        s.sweep(P, [[a], CL, CL], fmt=lambda x, lo, hi: v(f"clamp({x}, {lo}, {hi})"))
    # ---- Normalize ----
    for a in MV + ["vector(0, 0, 0)", "vector(1e-20, 0)", "vector(0, -7)", "vector(1, 1, 1)"]:
        s.body(P, [f"var/vector/V = {a}", "var/R = V.Normalize()"], "list(datums_v(R), datums_v(V), R == V)")
        s.body(P, [f"var/vector/V = {a}", "V.Normalize()"], "V.size")
    s.case(P, "vector(3, 4).Normalize(5)")
    # ---- Turn(angle) / Turn(vector) / turn() ----
    ANG = ["0", "90", "-90", "180", "45", "360", "30", "1e7", "NAN", "null", '"90"']
    for a in ["vector(0, 1)", "vector(3, 4)", "vector(1, 2, 3)"]:
        for ang in ANG:
            s.body(P, [f"var/vector/V = {a}", f"var/R = V.Turn({ang})"], "list(datums_v(R), datums_v(V), R == V)")
            s.body(P, [f"var/vector/V = {a}", f"var/R = turn(V, {ang})"], "list(datums_v(R), datums_v(V))")
    AXES = ["vector(0, 0, 90)", "vector(0, 0, -90)", "vector(90, 0, 0)", "vector(0, 90, 0)", "vector(0, 0, 0)",
            "vector(0, 0, 360)", "vector(0, 90)", "vector(0, 0, 45)", "vector(90, 90, 0)", "list(0, 0, 90)"]
    for a in ["vector(1, 0, 0)", "vector(1, 2, 3)", "vector(1, 0)"]:
        for ax in AXES:
            s.body(P, [f"var/vector/V = {a}", f"var/R = V.Turn({ax})"], "list(datums_v(R), datums_v(V), R == V)")
            s.body(P, [f"var/vector/V = {a}", f"var/R = turn(V, {ax})"], "list(datums_v(R), datums_v(V))")
    for e in ["vector(1, 2).Turn()", "turn(vector(1, 2))", "turn(vector(1, 2), vector(1, 2), 3)",
              "vector(1, 2).Turn(90, 90)", "vector(1, 2).Turn(new /datum)"]:
        s.case(P, v(e))
    # ---- Cross / Dot ----
    CD = VECS + ["vector(0, 0, 1)", "list(1, 2, 3)", "null", "5", "pixloc(1, 1, 1)"]
    for a in ["vector(1, 2)", "vector(1, 2, 3)", "vector(1, 0, 0)"]:
        for b in CD:
            s.body(P, [f"var/vector/A = {a}", f"var/R = A.Cross({b})"], "list(datums_v(R), datums_v(A))")
            s.case(P, v(f"{a}.Dot({b})"))
    for e in ["vector(1, 2).Cross()", "vector(1, 2).Dot()", "vector(1, 0, 0).Cross(vector(0, 1, 0))",
              "vector(0, 1, 0).Cross(vector(1, 0, 0))", "vector(1, 0).Cross(vector(0, 1))",
              "vector(1, 2).Dot(vector(3, 4, 5))", "vector(1, 2, 5).Dot(vector(3, 4))", "vector(1, 2).Cross(B = vector(0, 0, 1))",
              "vector(0.1, 0.2, 0.3).Dot(vector(0.3, 0.2, 0.1))", "vector(PINF, 0).Dot(vector(0, 1))",
              "vector(0.6, 0.8).Dot(vector(0.6, 0.8))"]:
        s.case(P, v(e))
    # ---- Interpolate ----
    TS = ["0", "1", "0.5", "2", "-1", "0.1", "0.25", "NAN", "null", '"0.5"', "PINF", "vector(0.5, 0.5)"]
    for a, b in [("vector(0, 0)", "vector(10, 20)"), ("vector(1, 2, 3)", "vector(3, 2, 1)"),
                 ("vector(1, 2)", "vector(5, 5, 5)"), ("vector(0.1, 0.3)", "vector(0.7, 0.9)")]:
        for t in TS:
            s.body(P, [f"var/vector/A = {a}", f"var/vector/B = {b}", f"var/R = A.Interpolate(B, {t})"],
                   "list(datums_v(R), A, B)")
    for e in ["vector(1, 2).Interpolate(vector(3, 4))", "vector(1, 2).Interpolate(null, 0.5)",
              "vector(1, 2).Interpolate(list(3, 4), 0.5)", "vector(1, 2).Interpolate(5, 0.5)",
              "vector(1, 2).Interpolate()", "vector(1, 2).Interpolate(t = 0.5, B = vector(3, 4))",
              "vector(1, 2).Interpolate(vector(3, 4), 1) == vector(3, 4)",
              "vector(0.1, 0.7).Interpolate(vector(0.3, 0.9), 1) == vector(0.3, 0.9)"]:
        s.case(P, v(e))
    for e in ["vector(1, 2).Nope()", "vector(1, 2).New(5, 6)", "vector(1, 2).Del()"]:
        s.case(P, v(e))


# =====================================================================================================
# /pixloc  (map 10x10x1, 32 px tiles: world pixels 1..320)
# =====================================================================================================
def pixlocs(s):
    P = "pixloc"
    px = lambda e: f"datums_px({e})"
    C = ["1", "32", "33", "320", "321", "0", "-5", "16.75", "null", '"33"']
    s.sweep(P, [C, C], fmt=lambda x, y: px(f"pixloc({x}, {y}, 1)"))
    for z in ["0", "1", "2", "-1", "1.5", "null", '"1"']:
        for xy in ["1, 1", "33, 65", "550, 907"]:
            s.case(P, px(f"pixloc({xy}, {z})"))
    for e in ["pixloc()", "pixloc(1)", "pixloc(1, 1)", "pixloc(1, 1, 1, 1)", "pixloc(null, null, null)",
              "pixloc(locate(1, 1, 1))", "pixloc(locate(2, 3, 1))", "pixloc(locate(10, 10, 1))",
              "pixloc(locate(2, 3, 1), 5, 6)", "pixloc(locate(2, 3, 1), -5, 40)",
              "pixloc(locate(2, 3, 1), vector(5, 6))", "pixloc(locate(2, 3, 1), vector(5.5, 6, 7))",
              "pixloc(locate(2, 3, 1), 5)", "pixloc(pixloc(40, 70, 1))", "pixloc(pixloc(40, 70, 1), 3, 4)",
              "pixloc(pixloc(40, 70, 1), vector(-50, 0))", "pixloc(locate(/area))", "pixloc(world)",
              "pixloc(new /datum)", "pixloc(\"a\", 1, 1)", "pixloc(list(1, 2, 3))", "pixloc(vector(1, 2, 1))",
              "new /pixloc(33, 65, 1)", "new /pixloc()", "new /pixloc(locate(2, 2, 1))",
              "pixloc(x = 33, y = 65, z = 1)", "pixloc(1, 1, 1).type", "pixloc(1, 1, 1).parent_type",
              "istype(pixloc(1, 1, 1), /pixloc)", "istype(pixloc(1, 1, 1), /datum)", "isloc(pixloc(1, 1, 1))",
              "\"[pixloc(33, 65, 1)]\"", "json_encode(pixloc(33, 65, 1))", "length(pixloc(1, 1, 1))",
              "pixloc(33, 65, 1) == pixloc(33, 65, 1)", "pixloc(33, 65, 1) != pixloc(34, 65, 1)",
              "pixloc(33, 65, 1) == locate(2, 3, 1)", "pixloc(1, 1, 1) ? 1 : 0",
              "pixloc(33, 65, 1) in list(pixloc(33, 65, 1))", "get_dir(pixloc(1, 1, 1), pixloc(100, 100, 1))",
              "get_dist(pixloc(1, 1, 1), pixloc(100, 100, 1))", "vector(pixloc(33, 65, 1))"]:
        s.case(P, px(e))
    for e in ["pixloc(33, 65, 1)", "pixloc(1, 1, 1)", "pixloc(550, 907, 1)", "pixloc(16.5, 40, 1)"]:
        for var in ("x", "y", "z", "loc", "step_x", "step_y", "type", "vars", "tag"):
            s.body(P, [f"var/pixloc/L = {e}"], f"L.{var}")
        s.body(P, [f"var/pixloc/L = {e}"], "L[1]")
    # Setting vars
    SETS = [("x", ["100", "1", "0", "-40", "1000", "50.5", "null", '"5"']),
            ("y", ["100", "1", "0", "-40", "1000", "50.5", "null"]),
            ("z", ["1", "2", "0", "null"]),
            ("step_x", ["5", "31", "32", "40", "-1", "-40", "1.5", "null"]),
            ("step_y", ["5", "32", "-33", "100", "null"]),
            ("loc", ["locate(5, 5, 1)", "null", "locate(/area)", "new /datum", '"a"', "locate(1, 1, 1)"])]
    for var, vals in SETS:
        for val in vals:
            s.body(P, ["var/pixloc/L = pixloc(40, 70, 1)", f"L.{var} = {val}"], px("L"))
    s.body(P, ["var/pixloc/L = pixloc(40, 70, 1)", "L.foo = 1"], px("L"))
    s.body(P, ["var/pixloc/L = pixloc(40, 70, 1)", "L.type = /datum"], px("L"))
    s.body(P, ["var/pixloc/A = pixloc(40, 70, 1)", "var/pixloc/B = A", "A.x = 200"], "list(A, B, A == B)")
    s.body(P, ["var/pixloc/A = pixloc(40, 70, 1)", "var/pixloc/B = A", "A += vector(10, 10)"], "list(A, B, A == B)")
    # Operators
    PL = ["pixloc(40, 70, 1)", "pixloc(1, 1, 1)", "pixloc(300, 300, 1)"]
    PR = ["vector(10, 5)", "vector(-50, -100)", "vector(1.5, 0.5)", "vector(1, 1, 1)", "pixloc(10, 10, 1)",
          "5", "null"]
    for a in PL:
        for b in PR:
            for op in ["+", "-", "*", "%"]:
                s.case(P, px(f"datums_v({a} {op} {b})"))
        for b in ["vector(10, 5)", "5", "pixloc(10, 10, 1)"]:
            s.case(P, px(f"datums_v({b} + {a})"))
            s.case(P, px(f"datums_v({b} - {a})"))
        for op in ["+=", "-="]:
            s.body(P, [f"var/pixloc/L = {a}", f"L {op} vector(10, 5)"], px("L"))
        s.case(P, px(f"-{a}"))
        for f in ["round", "floor", "ceil", "trunc", "fract", "abs"]:
            s.case(P, px(f"datums_v({f}({a}))"))
        for b in ["vector(32, 32)", "10", "pixloc(10, 10, 1)"]:
            s.case(P, px(f"datums_v(round({a}, {b}))"))
            s.case(P, px(f"datums_v(min({a}, {b}))"))
            s.case(P, px(f"datums_v(max({a}, {b}))"))
        s.case(P, px(f"datums_v(clamp({a}, pixloc(50, 50, 1), pixloc(100, 100, 1)))"))
    s.case(P, px("pixloc(16.6, 40.4, 1) - pixloc(1, 1, 1)"))
    s.case(P, px("datums_v(fract(pixloc(16.6, 40.4, 1)))"))
    s.case(P, px("datums_v(round(pixloc(16.6, 40.4, 1)))"))
    # Atom pixloc
    for st in ["0", "5", "31", "-3", "40"]:
        s.body(P, [f"var/obj/O = parity_track(new /obj(locate(2, 3, 1)))", f"O.step_x = {st}", "O.step_y = 7"],
               px("O.pixloc"))
    s.body(P, ["var/obj/O = parity_track(new /obj(locate(2, 3, 1)))", "O.bound_x = 4", "O.bound_y = 6"], px("O.pixloc"))
    s.body(P, ["var/obj/O = parity_track(new /obj)"], px("O.pixloc"))
    s.body(P, ["var/obj/A = parity_track(new /obj(locate(2, 3, 1)))", "var/obj/O = parity_track(new /obj(A))"],
           px("O.pixloc"))
    s.case(P, px("locate(4, 5, 1).pixloc"))
    s.case(P, px("locate(/area).pixloc"))
    for val in ["pixloc(100, 200, 1)", "pixloc(1, 1, 1)", "pixloc(5000, 5000, 1)", "null", "vector(100, 100)",
                "locate(5, 5, 1)", "pixloc(100.5, 200.5, 1)"]:
        s.body(P, ["var/obj/O = parity_track(new /obj(locate(2, 3, 1)))", f"O.pixloc = {val}"],
               "list(O.loc, O.step_x, O.step_y, datums_px(O.pixloc))")
    s.body(P, ["var/turf/T = locate(4, 5, 1)", "T.pixloc = pixloc(1, 1, 1)"], "list(T, datums_px(T.pixloc))")
    s.body(P, ["var/obj/O = parity_track(new /obj(locate(2, 3, 1)))", "O.pixloc += vector(40, 0)"],
           "list(O.loc, O.step_x, O.step_y)")
    s.body(P, ["var/obj/O = parity_track(new /obj(locate(2, 3, 1)))", "var/pixloc/L = O.pixloc", "L.x += 40"],
           "list(O.loc, O.step_x, datums_px(L))")


# =====================================================================================================
# /exception, throw / try / catch
# =====================================================================================================
def exceptions(s):
    P = "exception"
    THROWN = TEXT_S[:4] + NUM_S[:4] + OTHER + ["NAN", "vector(1, 2)", "new /exception(\"boom\")",
                                               "new /exception/datums_ex(\"sub\")", "EXCEPTION(\"macro\")",
                                               "pixloc(1, 1, 1)", "locate(2, 2, 1)", "/obj", "world", "list(null)",
                                               "matrix()", "\"\"", "FALSE"]
    for t in THROWN:
        s.case(P, f"datums_catch({t})")
        s.case(P, f"datums_catch_typed({t})")
        s.case(P, f"datums_catch_call({t})")
        s.case(P, f"datums_rethrow({t})")
        # Uncaught in the case itself: the harness's catch(var/exception/e) receives it
        s.case(P, f"datums_throw({t})")
    for k in range(1, 8):
        s.case(P, f"datums_rt({k})")
        s.case(P, f"datums_rt_shape({k})")
        s.body(P, [f"var/exception/E = datums_rt({k})"], "istype(E) ? E.name : E")
    for e in ["datums_after_catch()", "datums_try_return()", "datums_catch_noname()", "datums_rt(0)"]:
        s.case(P, e)
    # Constructor forms and vars
    CTOR = ["", '"msg"', '"msg", "f.dm"', '"msg", "f.dm", 12', '"msg", "f.dm", 12, "extra"', "5", "null",
            "list(1)", 'name = "n"', 'line = 3', '"m", null, "7"', "new /datum"]
    for c in CTOR:
        s.body(P, [f"var/exception/E = new /exception({c})"], "list(E.name, E.desc, E.file, E.line)")
    s.body(P, ["var/exception/E = new"], "list(E.name, E.desc, E.file, E.line, E.type, E.parent_type, E.tag)")
    s.body(P, ["var/exception/E = new(\"x\")"], "datums_names(E)")
    s.body(P, ["var/exception/E = new(\"x\")"], "E.vars.len")
    s.body(P, ['var/exception/E = EXCEPTION("mac")'], "list(E.name, E.file, isnum(E.line), E.line > 0, E.desc)")
    s.body(P, ['var/exception/datums_ex/E = new("sub", "s.dm", 4)'], "list(E.name, E.file, E.line, E.extra, E.type, E.parent_type)")
    s.body(P, ['var/exception/E = new("a")', 'E.name = "b"', 'E.desc = "d"', "E.line = 99", 'E.file = 5'],
           "list(E.name, E.desc, E.file, E.line)")
    s.body(P, ['var/exception/E = new("a")', 'E.vars["name"] = "viavars"'], "E.name")
    s.case(P, '"[new /exception("shown")]"')
    s.case(P, '"[new /exception()]"')
    s.case(P, '"[new /exception(5)]"')
    s.case(P, 'istype(new /exception("x"), /datum)')
    # throw inside a proc called in a try in the case body
    s.body(P, ["var/r", "try", "\tdatums_throw(\"deep\")", "\tr = \"no\"", "catch(var/x)", "\tr = list(\"got\", x)"], "r")
    s.body(P, ["var/r = 1", "try", "\tr = 2", "catch", "\tr = 3"], "r")
    s.body(P, ["var/r = list()", "for(var/i in 1 to 3)", "\ttry", "\t\tif(i == 2) throw i", "\t\tr += i",
               "\tcatch(var/x)", "\t\tr += \"c[x]\""], "r")
    s.body(P, ["var/r", "try", "\tthrow new /exception(\"e\", \"file.dm\", 7)", "catch(var/exception/x)",
               "\tr = list(x.name, x.file, x.line)"], "r")
    s.body(P, ["var/r", "try", "\tvar/list/L = list()", "\tL[3] = 1", "catch(var/exception/x)",
               "\tr = list(x.type, istext(x.name))"], "r")


# =====================================================================================================
# /datum builtin vars: type, parent_type, tag, vars
# =====================================================================================================
def datum_vars(s):
    P = "datum"
    TYPES = ["/datum", "/datum/datums_thing", "/datum/datums_thing/child", "/datums_root", "/datums_objish",
             "/obj", "/mob", "/atom/movable", "/exception", "/sound", "/icon", "/matrix", "/image",
             "/mutable_appearance", "/savefile", "/exception/datums_ex", "/obj/datums_verbobj"]
    for t in TYPES:
        s.body(P, [f"var/datum/D = new {t}"], "list(D.type, D.parent_type, D.tag)")
        s.body(P, [f"var/datum/D = new {t}"], "ispath(D.type)")
        s.body(P, [f"var/datum/D = new {t}"], "ispath(D.parent_type)")
        s.body(P, [f"var/datum/D = new {t}"], "D.vars.len")
        s.body(P, [f"var/datum/D = new {t}"], '"type" in D.vars')
    for e in ["locate(2, 2, 1)", "locate(/area)", "world", "regex(\"a\")", "generator(\"num\", 1, 1)",
              "matrix()", "icon('test.dmi')", "sound('datums_beep.wav')"]:
        s.body(P, [f"var/datum/D = {e}"], "list(D.type, D.parent_type)")
    for t in ["/datum", "/datum/datums_thing", "/datum/datums_thing/child", "/datums_root", "/exception",
              "/sound", "/exception/datums_ex", "/regex", "/generator"]:
        s.body(P, [f"var/datum/D = new {t}"], "datums_names(D)")
        s.body(P, [f"var/datum/D = new {t}"], "D.vars")
    s.body(P, ["var/datum/D = new /datums_objish"], "datums_names(D)")
    s.body(P, ["var/datum/D = new /mob"], "datums_names(D)")
    s.body(P, ["var/datum/D = locate(2, 2, 1)"], "datums_names(D)")
    s.body(P, ["var/datum/D = locate(/area)"], "datums_names(D)")
    s.body(P, ["var/datum/D = regex(\"a\")"], "datums_names(D)")
    s.body(P, ["var/datum/D = matrix()"], "datums_names(D)")
    s.body(P, ["var/datum/D = icon('test.dmi')"], "datums_names(D)")
    s.body(P, ["var/datum/D = new /image"], "datums_names(D)")
    s.body(P, ["var/datum/D = new /mutable_appearance"], "datums_names(D)")
    s.case(P, "datums_names(world)")
    # vars[] reads
    T = "var/datum/datums_thing/child/D = new"
    for k in ['"a"', '"b"', '"c"', '"d"', '"t"', '"k"', '"st"', '"gl"', '"nul"', '"type"', '"parent_type"',
              '"tag"', '"vars"', '"nope"', '""', "1", "2", "0", "100", "null", "/datum", '"A"']:
        s.body(P, [T], f"D.vars[{k}]")
        s.body(P, [T], f"{k} in D.vars")
    # vars[] writes
    for k, val in [('"a"', "9"), ('"b"', "list(1)"), ('"d"', "null"), ('"t"', '"tmp"'), ('"k"', "6"), ('"st"', "70"),
                   ('"gl"', "80"), ('"type"', "/obj"), ('"parent_type"', "/obj"), ('"vars"', "list()"),
                   ('"nope"', "1"), ('"tag"', '"datums_vtag2"'), ("1", "5"), ('"A"', "3")]:
        s.body(P, [T, f"D.vars[{k}] = {val}", "var/r = list(D.a, D.b, D.d, D.t, D.st, D.gl, D.type, D.parent_type, D.tag)",
                   "D.tag = null"], "r")
    s.body(P, [T, "D.vars[\"st\"] = 71", "var/datum/datums_thing/E = new"], "E.st")
    s.body(P, [T, "D.st = 72", "var/datum/datums_thing/E = new"], "list(E.st, E.vars[\"st\"])")
    s.body(P, [T, "D.vars[\"a\"] += 5"], "D.a")
    s.body(P, [T, "D.vars[\"c\"] += 3"], "D.c")
    s.body(P, [T, "D.vars += \"zz\""], "D.vars.len")
    s.body(P, [T, "D.vars -= \"a\""], "list(D.vars.len, D.a)")
    s.body(P, [T, "D.vars.Cut()"], "D.vars.len")
    s.body(P, [T, "D.vars.Add(\"x\")"], "D.vars.len")
    s.body(P, [T, "D.vars.len = 2"], "D.vars.len")
    s.body(P, [T, "D.vars = list()"], "D.vars.len")
    s.body(P, [T], "D.vars.Find(\"a\") > 0")
    s.body(P, [T], "D.vars.Find(\"nope\")")
    s.body(P, [T], "D.vars.Copy().len == D.vars.len")
    s.body(P, [T], "islist(D.vars)")
    s.body(P, [T], "D.vars == D.vars")
    s.body(P, [T, "var/list/V = D.vars", "D.a = 42"], "V[\"a\"]")
    s.body(P, [T, "D.a = 42"], "list(initial(D.a), initial(D.vars[\"a\"]), D.a)")
    s.body(P, [T], "list(issaved(D.a), issaved(D.t), issaved(D.type), issaved(D.vars), issaved(D.tag))")
    s.body(P, [T], "list(initial(D.type), initial(D.parent_type), initial(D.tag), initial(D.d))")
    s.body(P, [T, "var/out = list()", "for(var/k in D.vars)", "\tif(k in list(\"a\", \"b\", \"c\", \"d\", \"t\", \"nul\", \"other\"))", "\t\tout[k] = D.vars[k]"], "out")
    # type / parent_type assignment
    s.body(P, [T, "D.parent_type = /obj"], "list(D.parent_type, D.type, istype(D, /obj))")
    s.body(P, ["var/datum/D = new", "D:type = /obj"], "D.type")
    # tag
    for val in ['"datums_t1"', '""', "null", "5", "list(1)", '"datums t 2"', '"[0x1]"']:
        s.body(P, ["var/datum/D = new", f"D.tag = {val}", "var/r = list(D.tag, locate(D.tag) == D)", "D.tag = null"], "r")
    s.body(P, ["var/datum/D = new", 'D.tag = "datums_t3"', 'D.tag = ""', 'var/r = list(D.tag, locate("datums_t3"))'], "r")
    s.body(P, ["var/datum/D = new", 'D.tag = "datums_t4"', 'D.tag = null', 'var/r = list(D.tag, locate("datums_t4"))'], "r")
    s.body(P, ["var/datum/D = new", 'D.tag = "datums_t5"', 'var/r = locate("datums_t5") == D', 'D.tag = null'], "list(r, locate(\"datums_t5\"))")
    s.body(P, ["var/obj/O = parity_track(new /obj(locate(2, 2, 1)))", 'O.tag = "datums_t6"',
               'var/r = list(locate("datums_t6"), O.tag)', 'O.tag = null'], "r")
    s.body(P, ["var/datum/A = new", "var/datum/B = new", 'A.tag = "datums_t7"', 'B.tag = "datums_t7"',
               'var/r = list(A.tag, B.tag, locate("datums_t7") == A, locate("datums_t7") == B)', 'A.tag = null', 'B.tag = null'], "r")
    s.body(P, ["var/datum/D = new", 'D.tag = "datums_t8"', 'var/r = D.vars["tag"]', 'D.tag = null'], "r")
    s.case(P, 'locate("datums_never_tagged")')
    # type comparisons
    for e in ["new /datum/datums_thing/child().type == /datum/datums_thing/child",
              "istype(new /datums_root, /datum)", "istype(new /datums_objish, /obj)",
              "new /datums_objish().name", "new /datums_root().r", "(new /datum/datums_thing/child).a",
              "new /datum/datums_thing().k", "new /datum/datums_thing().gl", "new /datum/datums_thing().st",
              "\"[new /datum]\"", "\"[new /datum/datums_thing]\"", "\"[new /datums_objish]\""]:
        s.case(P, e)


# =====================================================================================================
# /callee: callee / caller
# =====================================================================================================
def callees(s):
    P = "callee"
    for args in ["", "1", "1, 2", '"a", list(1)', "null, null", "1, 2, 3", "b = 5", "a = 1, b = 2", "list(\"x\" = 1)"]:
        s.case(P, f"datums_self({args})")
        s.case(P, f"datums_named({args})")
    for x in ["1", "5", "-2"]:
        s.case(P, f"datums_outer({x})")
    s.case(P, "datums_chain()")
    s.case(P, "datums_mutargs(1, 2)")
    s.case(P, "datums_mutargs()")
    s.case(P, "datums_addargs(1)")
    s.case(P, "datums_callee_eq()")
    s.case(P, "datums_file_line()")
    s.case(P, "datums_callee_vars()")
    s.case(P, "datums_callee_text()")
    s.body(P, ["var/datum/datums_thing/T = new"], "T.whoami(4)")
    s.body(P, ["var/datum/datums_thing/T = new"], "T.callme()")
    s.body(P, ["var/datum/datums_thing/T = new", "var/list/L = T.callme()"], "L[4] == T")
    s.body(P, ["var/obj/datums_verbobj/O = new"], "O.datums_verb()")
    s.body(P, ["var/callee/C = datums_get_callee()"], "C.type")
    s.body(P, ["var/callee/C = datums_get_callee()"], "C.name")
    s.body(P, ["var/callee/C = datums_get_callee()"], "C.proc")
    s.body(P, ["var/callee/C = callee"], 'list(ispath(C.proc), findtext("[C.proc]", "/proc/parity_chunk_") == 1, C.proc == C.proc)')
    s.body(P, ["var/callee/C = callee"], 'C.proc:name == C.name')
    s.body(P, ["var/callee/C = callee"], 'findtext("[C.proc:type]", "/proc") == 1')
    s.body(P, ["var/callee/C = callee"], 'C.proc == caller')
    s.body(P, ["var/callee/C = datums_get_callee()"], "C.args")
    s.body(P, ["var/callee/C = datums_get_callee()"], "istype(C, /callee)")
    s.body(P, ["var/callee/C = datums_get_callee()"], "isnull(C)")
    s.case(P, "istype(datums_get_callee(), /datum)")
    s.case(P, "callee.type")
    s.case(P, "istype(callee, /callee)")
    s.case(P, "callee.usr")
    s.case(P, "callee.src")
    s.case(P, "isnull(caller)")
    s.case(P, "callee.caller == caller")
    s.case(P, "callee.args.len")
    s.body(P, ["var/callee/C = callee", 'C.name = "x"'], "C.name")
    s.body(P, ["var/callee/C = callee", "C.args = list()"], "C.args.len")
    s.body(P, ["var/callee/C = callee", "C.foo = 1"], "1")
    s.body(P, ["var/callee/C = callee"], "C.nope")
    s.case(P, "new /callee")
    s.case(P, "datums_inner(1, 2)[5]")
    s.body(P, ["var/callee/C = callee"], "C:args")
    s.body(P, ["var/callee/C = callee"], "C.args")


# =====================================================================================================
# /sound
# =====================================================================================================
def sounds(s):
    P = "sound"
    ds = lambda e: f"datums_sound({e})"
    F = ["'datums_beep.wav'", "null", '"datums_beep.wav"', "'test.dmi'", "5", '"nofile.ogg"']
    REP = ["0", "1", "2", "-1", "null"]
    WAIT = ["0", "1", "null"]
    CH = ["0", "1", "1024", "1025", "-1", "null"]
    VOL = ["0", "50", "100", "150", "-10", "null"]
    s.sweep(P, [F, REP, WAIT, CH, VOL], min_args=1, fmt=lambda *a: ds(f"sound({', '.join(a)})"))
    s.sweep(P, [F, REP], min_args=1, fmt=lambda *a: ds(f"new /sound({', '.join(a)})"))
    for a in ["'datums_beep.wav', 1, 1, 5, 50", "'datums_beep.wav', 0, null, 1025, 150", "null, 2, 1, -1, 0"]:
        s.case(P, ds(f"new /sound({a})"))
    for e in ["sound()", "new /sound", "sound(file = 'datums_beep.wav')", "sound('datums_beep.wav', volume = 50)",
              "sound(volume = 0)", "sound(repeat = 1)", "sound('datums_beep.wav', channel = 3, wait = 1)",
              "sound(list('datums_beep.wav', \"x.ogg\"))", "sound(list())", "sound(new /datum)",
              "sound('datums_beep.wav', 1, 0, 1, 1, 1)", "sound('datums_beep.wav', 1.5, 0.5, 2.5, 33.3)",
              "sound('datums_beep.wav', \"1\", \"1\", \"2\", \"50\")", "sound('datums_beep.wav', NAN, NAN, NAN, NAN)",
              "sound('datums_beep.wav', PINF, PINF, PINF, PINF)", "sound(file('datums_beep.wav'))",
              "sound(sound('datums_beep.wav', 1, 1, 7, 33))", "new /sound(sound('datums_beep.wav', 1, 1, 7, 33))",
              "sound(sound('datums_beep.wav'), 0, 0, 2, 10)", "sound(Volume = 10)",
              "sound('datums_beep.wav', volume = 1, channel = 2, wait = 3, repeat = 4)"]:
        s.case(P, ds(e))
    # Copy of a sound with every var changed
    s.body(P, ["var/sound/A = sound('datums_beep.wav', 1, 1, 7, 33)", "A.frequency = 2", "A.pitch = 0.5", "A.pan = -50",
               "A.priority = 9", "A.status = SOUND_MUTE", "A.falloff = 3", "A.x = 1", "A.environment = 4",
               'A.params = "on-end=.x"', "var/sound/B = sound(A)"], ds("B"))
    s.body(P, ["var/sound/A = sound('datums_beep.wav', 1, 1, 7, 33)", "var/sound/B = sound(A)"], "A == B")
    s.body(P, ["var/sound/A = sound('datums_beep.wav')", "var/sound/B = sound(A, 1)"], ds("B"))
    for e in ["sound('datums_beep.wav')", "new /sound"]:
        s.body(P, [f"var/sound/S = {e}"], "datums_names(S)")
        s.body(P, [f"var/sound/S = {e}"], "list(S.type, S.parent_type, S.tag)")
        s.case(P, f'"[{e}]"')
    s.case(P, "list(SOUND_MUTE, SOUND_PAUSED, SOUND_STREAM, SOUND_UPDATE)")
    # Var assignment: stored as given, or clamped/converted?
    SETS = [("volume", ["200", "-5", "50.5", "null", '"50"']), ("channel", ["2000", "-3", "1.5", "null"]),
            ("repeat", ["2", "3", "-1", "0.5"]), ("wait", ["5", "-1"]), ("frequency", ["-1", "44100", "1e7", "null"]),
            ("pitch", ["2", "0.1", "-1", "10"]), ("pan", ["-200", "200", "50"]), ("priority", ["255", "256", "-1", "1.5"]),
            ("status", ["SOUND_MUTE | SOUND_UPDATE", "SOUND_PAUSED", "SOUND_STREAM", "255", "-1"]),
            ("falloff", ["0", "-1", "10.5"]), ("environment", ["5", "25", "26", "-2", "list(1, 2)", "null", '"x"']),
            ("echo", ["list(1, 2, 3)", "5", "null"]), ("params", ['"on-end=.x"', 'list("on-end" = ".x")', "5"]),
            ("transform", ["matrix()", "matrix(2, 0, 0, 0, 2, 0)", "5", "null"]), ("x", ["5", "-5", "1.5"]),
            ("y", ["5"]), ("z", ["5"]), ("offset", ["2.5", "-1"]), ("len", ["3"]),
            ("file", ["'datums_beep.wav'", "\"x.ogg\"", "null", "5", "list('datums_beep.wav')"])]
    for var, vals in SETS:
        for val in vals:
            s.body(P, ["var/sound/S = new", f"S.{var} = {val}"], ds("S"))
    s.body(P, ["var/sound/S = new", "var/obj/O = parity_track(new /obj(locate(2, 2, 1)))", "S.atom = O"],
           "S.atom == O")
    s.body(P, ["var/sound/S = new", "S.atom = 5"], ds("S"))
    s.body(P, ["var/sound/S = new", "S.nope = 5"], ds("S"))
    s.body(P, ["var/sound/S = new", 'S.vars["volume"] = 12'], "S.volume")
    s.body(P, ["var/sound/S = new"], "list(initial(S.volume), initial(S.falloff), initial(S.environment), initial(S.file))")
    s.body(P, ["var/sound/S = sound('datums_beep.wav')"], "isfile(S.file)")
    s.body(P, ["var/sound/S = sound(\"datums_beep.wav\")"], "list(isfile(S.file), istext(S.file))")
    s.body(P, ["var/sound/S = sound('datums_beep.wav')"], "length(S.file)")


# =====================================================================================================
# /generator (deterministic: degenerate ranges, result kinds, range predicates)
# =====================================================================================================
def generators(s):
    P = "generator"
    for e in ['generator("num", 5, 5)', 'generator("num", 5, 5, NORMAL_RAND)', 'generator("num", 5, 5, LINEAR_RAND)',
              'generator("num", 5, 5, SQUARE_RAND)', 'generator("num", -2.5, -2.5)', 'generator("num", 0, 0)',
              'generator("vector", vector(1, 2), vector(1, 2))', 'generator("vector", vector(1, 2, 3), vector(1, 2, 3))',
              'generator("box", vector(1, 2), vector(1, 2))', 'generator("box", vector(1, 2, 3), vector(1, 2, 3))',
              'generator("circle", 0, 0)', 'generator("sphere", 0, 0)', 'generator("square", 0, 0)',
              'generator("cube", 0, 0)', 'generator("square", vector(0, 0), vector(0, 0))',
              'generator("color", "#ff0000", "#ff0000")', 'generator("color", "red", "red")',
              'generator("color", rgb(1, 2, 3), rgb(1, 2, 3))',
              'generator("vector", list(1, 2), list(1, 2))', 'generator("box", list(1, 2, 3), list(1, 2, 3))',
              'generator("num", "5", "5")',
              'generator("vector", 1, 1)', 'generator("vector", vector(1, 2), vector(1, 2, 0))']:
        s.body(P, [f"var/generator/G = {e}"], "datums_v(G.Rand())")
        s.body(P, [f"var/generator/G = {e}"], "list(G.type, G.parent_type, istype(G, /generator))")
    # Only degenerate (A == B) forms here, so an engine that accepts one still prints a fixed value
    for e in ['generator()', 'generator("num")', 'generator("bogus", 1, 1)', 'generator(5, 1, 1)', 'generator("NUM", 1, 1)',
              'generator("num", 1, 1, 7)', 'generator("num", 1, 1, -1)', 'generator("num", list(1), list(1))',
              'generator("num", vector(1, 2), vector(1, 2))', 'generator("color", 1, 1)', 'generator("circle", vector(1, 1), vector(1, 1))',
              'generator(type = "num", A = 3, B = 3)']:
        s.case(P, f"datums_v({e})")
        s.body(P, [f"var/generator/G = {e}"], "datums_v(G.Rand())")
    for e in ['"[generator("num", 1, 2)]"', 'istype(generator("num", 1, 2), /datum)', 'generator("num", 1, 2).type',
              'list(UNIFORM_RAND, NORMAL_RAND, LINEAR_RAND, SQUARE_RAND)', 'new /generator',
              'new /generator("num", 4, 4)']:
        s.case(P, e)
    s.body(P, ["var/generator/G = new /generator(\"num\", 4, 4)"], "G.Rand()")
    s.body(P, ["var/generator/G = generator(\"num\", 1, 1)"], "datums_names(G)")
    s.body(P, ["var/generator/G = generator(\"num\", 1, 1)"], "G.Rand(5)")
    # Range predicates over many draws: deterministic regardless of the random source
    PRED = [('generator("num", 0, 10)', "!isnum(r) || r < 0 || r > 10"),
            ('generator("num", 10, 0)', "!isnum(r) || r < 0 || r > 10"),
            ('generator("num", -1, 1, NORMAL_RAND)', "!isnum(r) || r < -1 || r > 1"),
            ('generator("num", 1, 2, SQUARE_RAND)', "!isnum(r) || r < 1 || r > 2"),
            ('generator("vector", vector(0, 0), vector(2, 4))', "!istype(r, /vector) || r:len != 2 || abs(r:y - 2 * r:x) > 0.001 || r:x < 0 || r:x > 2"),
            ('generator("vector", vector(0, 0, 0), vector(1, 1, 1))', "!istype(r, /vector) || r:len != 3 || abs(r:x - r:z) > 0.001"),
            ('generator("box", vector(0, 0), vector(2, 4))', "!istype(r, /vector) || r:len != 2 || r:x < 0 || r:x > 2 || r:y < 0 || r:y > 4"),
            ('generator("box", vector(0, 0, 0), vector(1, 2, 3))', "!istype(r, /vector) || r:len != 3 || r:z < 0 || r:z > 3"),
            ('generator("circle", 1, 2)', "!istype(r, /vector) || r:size < 0.999 || r:size > 2.001 || r:z != 0"),
            ('generator("sphere", 1, 2)', "!istype(r, /vector) || r:size < 0.999 || r:size > 2.001"),
            ('generator("square", 1, 2)', "!istype(r, /vector) || max(abs(r:x), abs(r:y)) < 0.999 || max(abs(r:x), abs(r:y)) > 2.001"),
            ('generator("cube", 1, 2)', "!istype(r, /vector) || max(abs(r:x), abs(r:y), abs(r:z)) < 0.999 || max(abs(r:x), abs(r:y), abs(r:z)) > 2.001"),
            ('generator("color", "#000000", "#ffffff")', "!istext(r) || length(r) != 7 || copytext(r, 2, 4) != copytext(r, 4, 6)"),
            ('generator("color", "#ff0000", "#0000ff")', "!istext(r) || copytext(r, 1, 2) != \"#\""),
            ]
    for g, bad in PRED:
        s.body(P, [f"var/generator/G = {g}", "var/badn = 0", "var/kind", "for(var/i in 1 to 40)", "\tvar/r = G.Rand()",
                   "\tif(i == 1)", "\t\tkind = istype(r, /vector) ? \"vector\" : (isnum(r) ? \"num\" : (istext(r) ? \"text\" : \"other\"))",
                   f"\tif({bad})", "\t\tbadn++"], "list(kind, badn)")
