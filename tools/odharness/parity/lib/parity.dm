// Parity suite runtime: each generated case writes one "id<TAB>value" line to results_<engine>.txt.
// Values go through canon() so both engines print the same kinds of value the same way.

#ifdef OPENDREAM
#define PARITY_ENGINE "od"
#else
#define PARITY_ENGINE "byond"
#endif

#define PARITY_OUT "results_[PARITY_ENGINE].txt"

// A suite can set these with s.define() (written to pre.dm, which is included first)
#ifndef PARITY_MAXX
#define PARITY_MAXX 10
#endif
#ifndef PARITY_MAXY
#define PARITY_MAXY 10
#endif
#ifndef PARITY_MAXZ
#define PARITY_MAXZ 1
#endif
#ifndef PARITY_VIEW
#define PARITY_VIEW 5
#endif
#ifndef PARITY_ICON_SIZE
#define PARITY_ICON_SIZE 32
#endif

/world
	maxx = PARITY_MAXX
	maxy = PARITY_MAXY
	maxz = PARITY_MAXZ
	view = PARITY_VIEW
	icon_size = PARITY_ICON_SIZE
	loop_checks = 0

// Atoms a case creates go through parity_track() and are deleted after the case, so cases stay independent
var/global/list/parity_tracked = list()

/proc/parity_track(x)
	parity_tracked += x
	return x

/proc/parity_cleanup()
	// One failing del (OD can leave a deleted container's children broken) must not stop the rest
	var/list/L = parity_tracked.Copy()
	parity_tracked.Cut()
	for(var/x in L)
		if(!isnull(x))
			try
				del x
			catch

var/global/PINF
var/global/NINF
var/global/NAN
var/global/list/parity_skip = list()

/world/New()
	..()
	// Float32 overflow gives inf on both engines without needing an inf literal
	PINF = 1e30
	PINF *= 1e30
	NINF = -PINF
	NAN = PINF - PINF
	spawn(5)
		parity_main()

/proc/parity_main()
	fdel(PARITY_OUT)
	if(fexists("skip.txt"))
		for(var/line in splittext(file2text("skip.txt"), "\n"))
			var/tab = findtext(line, "\t")
			if(tab)
				parity_skip[copytext(line, 1, tab)] = copytext(line, tab + 1)
	text2file("#START\t[PARITY_ENGINE]\n", PARITY_OUT)
#ifdef PARITY_LIVE
	// Live suites stay up and are driven through world/Topic (lib/live.dm)
	return
#endif
	parity_run_chunks()
	text2file("#DONE\n", PARITY_OUT)
	shutdown()

/proc/parity_emit(id, value)
	// OD cannot write text that holds half a UTF-16 surrogate pair. Record that, so the case is not lost.
	if(!text2file("[id]\t[parity_canon(value)]\n", PARITY_OUT))
		text2file("[id]\tWRITE_FAILED len=[length(value)] len_char=[length_char(value)]\n", PARITY_OUT)

/proc/parity_emit_raw(id, text)
	text2file("[id]\t[text]\n", PARITY_OUT)

/proc/parity_emit_err(id, exception/e)
	var/msg = istype(e) ? "[e.name]" : "[e]"
	parity_emit_raw(id, "ERR [parity_escape(msg)]")

// TRUE if an earlier run of this case crashed or hung the engine
/proc/parity_skipped(id)
	var/why = parity_skip[id]
	if(!why)
		return FALSE
	// Already recorded by an earlier run that the runner is resuming after
	if(why != "=done")
		parity_emit_raw(id, "SKIP [why]")
	return TRUE

/proc/parity_escape(t)
	t = replacetext(t, "\\", "\\\\")
	t = replacetext(t, "\n", "\\n")
	t = replacetext(t, ascii2text(13), "\\r") // OD's compiler rejects the "\r" escape
	t = replacetext(t, "\t", "\\t")
	// Other control characters (text macro markers among them) would otherwise print invisibly
	for(var/c in parity_controls)
		if(findtextEx(t, c))
			t = replacetextEx(t, c, parity_controls[c])
	return t

var/global/list/parity_controls = parity_make_controls()

/proc/parity_make_controls()
	var/list/L = list()
	var/hex = "0123456789abcdef"
	// 0 is left out: ascii2text(0) may be "" and would then match everywhere
	for(var/i in 1 to 31)
		if(i == 9 || i == 10 || i == 13)
			continue
		L[ascii2text(i)] = "\\x[copytext(hex, round(i / 16) + 1, round(i / 16) + 2)][copytext(hex, i % 16 + 1, i % 16 + 2)]"
	L[ascii2text(127)] = "\\x7f"
	return L

/proc/parity_num(n)
	if(n != n)
		return "nan"
	if(n == PINF)
		return "inf"
	if(n == NINF)
		return "-inf"
	// The display form is a parity point itself. The precise form after '~' is reported separately,
	// so a format difference does not hide a value difference.
	return "[n]~[num2text(n, 12)]"

/proc/parity_canon(v, depth = 0)
	if(isnull(v))
		return "null"
	if(isnum(v))
		return "n:[parity_num(v)]"
	if(istext(v))
		return "t:\"[parity_escape(v)]\""
	if(ispath(v))
		return "p:[v]"
	if(depth > 4)
		return "..."
	if(islist(v))
		var/list/L = v
		var/list/parts = list()
		for(var/k in L)
			var/s = parity_canon(k, depth + 1)
			if(!isnum(k))
				var/assoc = L[k]
				if(!isnull(assoc))
					s += "=[parity_canon(assoc, depth + 1)]"
			parts += s
		return "L([L.len])\[[jointext(parts, ", ")]\]"
	if(isfile(v))
		return "f:[v]"
	if(istype(v, /icon))
		return parity_icon(v)
	if(istype(v, /matrix))
		var/matrix/M = v
		return "m:\[[parity_num(M.a)], [parity_num(M.b)], [parity_num(M.c)], [parity_num(M.d)], [parity_num(M.e)], [parity_num(M.f)]\]"
	if(istype(v, /regex))
		var/regex/R = v
		return "r:index=[parity_canon(R.index, depth + 1)] next=[parity_canon(R.next, depth + 1)] match=[parity_canon(R.match, depth + 1)] group=[parity_canon(R.group, depth + 1)]"
	if(istype(v, /vector))
		var/vector/V = v
		return "v:([parity_canon(V.x, depth + 1)], [parity_canon(V.y, depth + 1)], [parity_canon(V.z, depth + 1)])"
	if(istype(v, /pixloc))
		var/pixloc/P = v
		return "px:([parity_canon(P.x, depth + 1)], [parity_canon(P.y, depth + 1)], [parity_canon(P.z, depth + 1)])"
	if(istype(v, /exception))
		var/exception/E = v
		return "e:[parity_canon(E.name, depth + 1)]"
	if(isarea(v))
		var/area/A = v
		return "a:[A.type]"
	if(isturf(v))
		var/turf/T = v
		return "a:[T.type]@[T.x],[T.y],[T.z]"
	if(ismovable(v))
		var/atom/movable/M = v
		return "a:[M.type]@[M.x],[M.y],[M.z] [parity_canon(M.name, depth + 1)]"
	if(istype(v, /datum))
		var/datum/D = v
		return "d:[D.type]"
	return "?:[v]"

// Size, states in order, and a hash of every pixel of each state's first frame and dir
/proc/parity_icon(icon/I)
	var/list/states = icon_states(I)
	var/list/parts = list()
	for(var/s in states)
		parts += "[parity_escape(s)]:[parity_icon_hash(I, s)]"
	return "i:[I.Width()]x[I.Height()]\[[jointext(parts, ", ")]\]"

/proc/parity_icon_hash(icon/I, state, dir = 0, frame = 0)
	return copytext(md5(jointext(parity_icon_pixels(I, state, dir, frame), ",")), 1, 9)

// Every pixel of one image, row by row from the top, as GetPixel gives it (null for transparent)
/proc/parity_icon_pixels(icon/I, state, dir = 0, frame = 0)
	var/list/L = list()
	var/w = I.Width()
	var/h = I.Height()
	for(var/y in h to 1 step -1)
		for(var/x in 1 to w)
			L += "[I.GetPixel(x, y, state, dir, frame)]"
	return L
