"""/savefile and /database + /database/query.

Savefiles: every value kind through << / >>, operator[] read and write, the root buffer, reopening a
file, cd / dir navigation, eof, deleting keys, Read()/Write() overrides, ExportText's exact text,
ImportText, Flush, Lock/Unlock, name, temporary savefiles.
Most cases use a temporary savefile (new /savefile()); cases that need a real file use a unique name
in sv_tmp/ derived from the case's own code, and delete it when done (savedb_done).

Databases: sqlite files in db_tmp/ (unique per case, deleted afterwards): Execute return values,
NextRow, GetRowData, GetColumn, Columns, RowsAffected, Reset, Clear, Close, Error/ErrorMsg on query
and database, Add/New with ? parameters of every kind, and the DM types of returned values.

Divergences OD's source suggests: savefile buffers hold one value (BYOND buffers are streams that
<< appends to and >> reads in order); datum identity inside one write; New() called on read;
ExportText number/text escaping; ImportText missing; dir.Find unimplemented; new /savefile(file())
treated as temporary; Execute() returns null and ignores a filename argument; Add() replaces instead
of appending; NULL/BLOB columns throw in GetRowData; params bound instead of substituted (null and
object params left unbound); ErrorMsg wording."""
import hashlib
from pathlib import Path

from gen import dm_str

HERE = Path(__file__).resolve()

DEFS = r'''
var/global/list/savedb_log = list()
var/global/savedb_news = 0

/datum/savedb_thing
	var/a = 1
	var/b = "x"
	var/list/c
	var/tmp/t = 5
	var/datum/savedb_thing/ref
	var/global/g = 9
	var/const/k = 3

/datum/savedb_thing/sub
	a = 10

/datum/savedb_rw
	var/v = 1
	var/extra

/datum/savedb_rw/Write(savefile/F)
	savedb_log += "W"
	..()
	F["extra"] << 42

/datum/savedb_rw/Read(savefile/F)
	savedb_log += "R"
	..()
	F["extra"] >> extra

/datum/savedb_nosuper
	var/v = 1

/datum/savedb_nosuper/Write(savefile/F)
	F["custom"] << "c"

/datum/savedb_nosuper/Read(savefile/F)
	F["custom"] >> v

/datum/savedb_new
	var/v = 1

/datum/savedb_new/New()
	savedb_news++
	savedb_log += "New"

/datum/savedb_new/Read(savefile/F)
	savedb_log += "Read"
	..()

/datum/savedb_cd
	var/v = 1

/datum/savedb_cd/Write(savefile/F)
	savedb_log += F.cd
	..()

/datum/savedb_cd/Read(savefile/F)
	savedb_log += F.cd
	..()

/datum/savedb_tmpall
	var/tmp/x = 1
	var/y = 2

/obj/savedb_obj
	name = "sobj"
	var/v = 1

/proc/savedb_thing(a, b, list/c)
	var/datum/savedb_thing/T = new
	if(!isnull(a))
		T.a = a
	if(!isnull(b))
		T.b = b
	if(!isnull(c))
		T.c = c
	return T

/proc/savedb_done(value, savefile/F, name)
	if(F)
		del F
	if(name)
		fdel(name)
	return value

/proc/savedb_named(name)
	fdel(name)
	return new /savefile(name)

/proc/savedb_dir(savefile/F)
	var/list/L = list()
	for(var/k in F.dir)
		L += k
	return L

/proc/savedb_sorted(list/L)
	L = L.Copy()
	for(var/i in 1 to L.len)
		for(var/j in 1 to L.len - i)
			if(sorttext(L[j], L[j + 1]) < 0)
				L.Swap(j, j + 1)
	return L

/proc/savedb_show(x, depth = 0)
	if(depth > 4)
		return "..."
	if(istype(x, /datum/savedb_thing))
		var/datum/savedb_thing/T = x
		var/r = T.ref
		if(r == T)
			r = "self"
		else if(r)
			r = savedb_show(r, depth + 1)
		return list("thing", T.type, T.a, T.b, savedb_show(T.c, depth + 1), T.t, r)
	if(istype(x, /datum/savedb_rw))
		var/datum/savedb_rw/R = x
		return list("rw", R.v, R.extra)
	if(istype(x, /datum/savedb_nosuper))
		var/datum/savedb_nosuper/N = x
		return list("nosuper", N.v)
	if(istype(x, /obj/savedb_obj))
		var/obj/savedb_obj/O = x
		return list("obj", O.v, O.name, isnull(O.loc))
	if(islist(x))
		var/list/L = x
		var/list/out = list()
		for(var/k in L)
			var/s = savedb_show(k, depth + 1)
			if(!isnum(k) && !isnull(L[k]))
				out[++out.len] = list(s, "=", savedb_show(L[k], depth + 1))
			else
				out[++out.len] = s
		return out
	if(isfile(x) && !isicon(x))
		return list("file", md5(x))
	return x

// Runs one SQL statement on db (no parameters) and returns the query
/proc/savedb_sql(database/db, sql)
	var/database/query/q = new(sql)
	q.Execute(db)
	return q

// A typed table t(a INTEGER, b TEXT, c REAL, d BLOB, e) with three rows, made with plain SQL
/proc/savedb_table(database/db)
	savedb_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL, d BLOB, e)")
	savedb_sql(db, "INSERT INTO t VALUES (1, 'one', 1.5, NULL, NULL)")
	savedb_sql(db, "INSERT INTO t VALUES (2, 'two', 2.5, NULL, 'x')")
	savedb_sql(db, "INSERT INTO t VALUES (3, NULL, NULL, NULL, 7)")

/proc/savedb_db(name)
	fdel(name)
	return new /database(name)

/proc/savedb_dbdone(value, database/db, database/query/q, name)
	if(q)
		del q
	if(db)
		del db
	if(name)
		fdel(name)
	return value

// Every row's GetRowData() (at most 20)
/proc/savedb_rows(database/query/q)
	var/list/L = list()
	var/n = 0
	while(q.NextRow() && n < 20)
		n++
		L[++L.len] = q.GetRowData()
	return L

// The first row of a one-statement query, as list(Execute(), GetRowData(), Error(), ErrorMsg())
/proc/savedb_one(database/db, database/query/q)
	var/ex = q.Execute(db)
	var/nr = q.NextRow()
	var/row = q.GetRowData()
	return list(ex, nr, row, q.Error(), q.ErrorMsg())

/proc/savedb_types(list/L)
	var/list/out = list()
	for(var/k in L)
		var/v = L[k]
		out += "[k]:[isnull(v) ? "null" : isnum(v) ? "num" : istext(v) ? "text" : isfile(v) ? "file" : "other"]"
	return out
'''

# ---------------------------------------------------------------- value kinds for savefile round trips
VALS = [
    "null", "0", "1", "-1", "1.5", "-0.5", "0.1", "100", "123456", "1e7", "16777217", "1e-7", "1e30", "-1e30",
    "PINF", "NINF", "NAN", "1/3",
    dm_str(""), dm_str("abc"), dm_str("A B"), dm_str("é日本"), dm_str("🙂x🙂"), dm_str('q"uote'),
    dm_str("line\nbreak"), dm_str("a\\b"), dm_str("[br]"), dm_str("tab\tx"), dm_str("'single'"),
    dm_str("<b>&amp;</b>"), dm_str("a=b;c"), dm_str("{\"x\"}"), dm_str("123"), dm_str("null"),
    '"[ascii2text(1)]x"', '"\\ref"',
    "/datum", "/obj", "/datum/savedb_thing", "/datum/savedb_thing/sub", "/list", "/savefile",
    "list()", "list(1, 2, 3)", 'list("a", "b")', 'list("a" = 1, "b" = "x")', 'list(1, "a" = 2)',
    "list(list(1, 2), list())", "list(null, null)", 'list("k" = null)', "list(/datum, /obj)",
    'list(/datum = 1, /obj = "o")', 'list("a" = list(1))', "list(1.5, -0.5, PINF, NAN)",
    'list("é" = "日")', 'list(list("x" = list("y" = 1)))', 'list("a", "a", "b")', 'list("1" = 2)',
    "new /datum", "new /datum/savedb_thing", "new /datum/savedb_thing/sub", 'savedb_thing(2, "y", list(1, "z"))',
    'savedb_thing(null, null, list("k" = new /datum/savedb_thing))', "list(new /datum/savedb_thing, 5)",
    'list("o" = savedb_thing(7))', "new /datum/savedb_rw", "new /datum/savedb_nosuper", "new /datum/savedb_tmpall",
    "matrix()", "matrix(1, 2, 3, 4, 5, 6)", "icon('test.dmi')", "icon('small.dmi', \"grad\")", "'test.dmi'",
    "'small.dmi'", "vector(1, 2, 3)", 'regex("a+")', "new /exception(\"boom\")",
]
# A smaller set for the per-kind reopen / sequential cases
VALS_S = ["null", "0", "1.5", "-1", "16777217", "PINF", "NAN", dm_str(""), dm_str("abc"), dm_str("é🙂"),
          dm_str('q"\n'), "/datum/savedb_thing", "list()", 'list(1, "a" = 2)', "list(list(1))",
          'savedb_thing(2, "y", list(1))', "new /datum/savedb_rw", "'small.dmi'", "icon('small.dmi')"]

SV_PATHS = [dm_str(t) for t in ["/", ".", "..", "a", "/a", "a/b", "/a/b", "a/b/", "/a/../b", "a/./b", "../..",
                                "", " ", "A", "a b", "é", "1", "//a", "a//b", ".hidden", "/a/b/c/d/e"]]
SV_CD_BAD = ["null", "1", "0", "list()", "new /datum", "/datum"]


def _hash(lines, result):
    return hashlib.sha1(("\n".join(lines) + "\n" + result).encode()).hexdigest()[:10]


def build(s):
    s.dm(DEFS)
    # The work folders exist in the build tree (the savefile/db cases themselves never create them)
    s.resource("sv_tmp/keep.txt", HERE)
    s.resource("db_tmp/keep.txt", HERE)

    def sv(proc, lines, result):
        """A case on a temporary savefile F, deleted afterwards."""
        return s.body(proc, ["var/savefile/F = new /savefile()"] + list(lines), f"savedb_done({result}, F)")

    def svn(proc, lines, result):
        """A case on a savefile F at a fresh file N in sv_tmp/; F is deleted and N removed afterwards.
        Lines may use N (the file name as a DM literal) and reopen F."""
        name = f'"sv_tmp/{_hash(lines, result)}.sav"'
        lines = [l.replace("@N", name) for l in lines]
        result = result.replace("@N", name)
        return s.body(proc, [f"var/savefile/F = savedb_named({name})"] + lines, f"savedb_done({result}, F, {name})")

    def db(proc, lines, result, table=False):
        """A case on a database db at a fresh file in db_tmp/; q is a declared query var."""
        name = f'"db_tmp/{_hash(lines, result + str(table))}.db"'
        lines = [l.replace("@N", name) for l in lines]
        result = result.replace("@N", name)
        pre = [f"var/database/db = savedb_db({name})", "var/database/query/q"]
        if table:
            pre.append("savedb_table(db)")
        return s.body(proc, pre + lines, f"savedb_dbdone({result}, db, q, {name})")

    # ================================================================ savefile: value round trips
    for v in VALS:
        sv("savefile.<<", [f'F["k"] << {v}', "var/x", 'F["k"] >> x'], "savedb_show(x)")
        sv("savefile[]=", [f'F["k"] = {v}'], 'savedb_show(F["k"])')
        sv("savefile.ExportText", [f'F["k"] << {v}'], 'F.ExportText("/")')
        sv("savefile.<<root", [f"F << {v}", 'F.cd = "/"', "var/x", "F >> x"], "savedb_show(x)")
    # Type of what comes back
    for v in ["1", '"a"', "/datum", "list(1)", "new /datum", "'test.dmi'", "icon('test.dmi')", "null", "matrix()"]:
        sv("savefile.>>type", [f'F["k"] << {v}', "var/x", 'F["k"] >> x'],
           'list(isnum(x), istext(x), ispath(x), islist(x), isfile(x), isicon(x), istype(x, /datum), isnull(x))')
    sv("savefile.>>type", ["F[\"k\"] << 'test.dmi'", "var/x", 'F["k"] >> x'], '"[x]"')
    sv("savefile.>>type", ["F[\"k\"] << 'test.dmi'", "var/x", 'F["k"] >> x'], "md5(x) == md5('test.dmi')")
    sv("savefile.>>type", ["F[\"k\"] << icon('test.dmi', \"asym\")", "var/icon/x", 'F["k"] >> x'],
       'parity_icon_hash(x, "asym") == parity_icon_hash(icon(\'test.dmi\', "asym"), "asym")')
    sv("savefile.>>type", ['F["k"] << matrix(1, 2, 3, 4, 5, 6)', "var/x", 'F["k"] >> x'], "x")
    sv("savefile.>>type", ['F["k"] << list(1, 2)', "var/list/x", 'F["k"] >> x', "x += 3"], "x")
    # The value written and the value read back are different objects
    sv("savefile.>>identity", ["var/list/L = list(1)", 'F["k"] << L', "var/x", 'F["k"] >> x'], "list(x == L, x ~= L)")
    sv("savefile.>>identity", ["var/datum/D = new", 'F["k"] << D', "var/x", 'F["k"] >> x'], "x == D")
    sv("savefile.>>identity", ["var/list/L = list(1)", 'F["k"] << L', "L += 2", "var/x", 'F["k"] >> x'], "x")
    sv("savefile.>>identity", ["var/datum/savedb_thing/T = new", 'F["k"] << T', "T.a = 50", "var/x", 'F["k"] >> x'],
       "savedb_show(x)")
    # Two reads give two objects
    sv("savefile.>>identity", ['F["k"] << new /datum', "var/x", "var/y", 'F["k"] >> x', 'F["k"] >> y'], "x == y")
    # Datum identity inside one write: shared references stay shared, cycles terminate
    sv("savefile.<<refs", ["var/datum/D = new", 'F["k"] << list(D, D)', "var/list/x", 'F["k"] >> x'],
       "list(x.len, x[1] == x[2], isnull(x[1]))")
    sv("savefile.<<refs", ["var/datum/D = new", 'F["k"] << list(D, D)'], 'F.ExportText("/")')
    sv("savefile.<<refs", ["var/datum/savedb_thing/T = new", "T.ref = T", 'F["k"] << T', "var/datum/savedb_thing/x",
                           'F["k"] >> x'], "list(x.ref == x, savedb_show(x))")
    sv("savefile.<<refs", ["var/datum/savedb_thing/T = new", "T.ref = T", 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.<<refs", ["var/datum/savedb_thing/A = new", "var/datum/savedb_thing/B = new", "A.ref = B", "B.ref = A",
                           'F["k"] << A', "var/datum/savedb_thing/x", 'F["k"] >> x'],
       "list(x.ref.ref == x, savedb_show(x))")
    sv("savefile.<<refs", ["var/datum/savedb_thing/A = new", "var/datum/savedb_thing/B = new", "A.ref = B", "B.ref = A",
                           'F["k"] << A'], 'F.ExportText("/")')
    sv("savefile.<<refs", ["var/datum/savedb_thing/A = new", "var/datum/savedb_thing/B = new", "A.ref = B",
                           'F["k"] << list(A, B)', "var/list/x", 'F["k"] >> x', "var/datum/savedb_thing/x1 = x[1]"],
       "list(x1.ref == x[2], savedb_show(x))")
    sv("savefile.<<refs", ["var/datum/savedb_thing/A = new", "var/datum/savedb_thing/B = new", "A.ref = B",
                           'F["k"] << list(A, B)'], 'F.ExportText("/")')
    # Separate writes of the same datum are separate objects
    sv("savefile.<<refs", ["var/datum/D = new", 'F["a"] << D', 'F["b"] << D', "var/x", "var/y", 'F["a"] >> x',
                           'F["b"] >> y'], "list(x == y, istype(x, /datum), istype(y, /datum))")
    sv("savefile.<<refs", ["var/datum/D = new", 'F["a"] << D', 'F["b"] << D'], 'F.ExportText("/")')
    sv("savefile.<<refs", ["var/list/L = list(1)", 'F["k"] << list(L, L)', "var/list/x", 'F["k"] >> x'],
       "list(x, x[1] == x[2])")
    sv("savefile.<<refs", ["var/list/L = list(1)", "L += list(L)", 'F["k"] << L'], 'F.ExportText("/")')
    # Atoms: an obj is written as an object (not its location) and read back off-map
    sv("savefile.<<atom", ["var/obj/savedb_obj/O = parity_track(new /obj/savedb_obj(locate(2, 2, 1)))", "O.v = 4",
                           'F["k"] << O', "var/obj/savedb_obj/x", 'F["k"] >> x', "parity_track(x)"],
       "list(savedb_show(x), x == O, O.loc == locate(2, 2, 1))")
    sv("savefile.<<atom", ["var/obj/savedb_obj/O = parity_track(new /obj/savedb_obj(locate(2, 2, 1)))", "O.v = 4",
                           'F["k"] << O'], 'F.ExportText("/")')
    sv("savefile.<<atom", ["var/obj/O = parity_track(new /obj(locate(2, 2, 1)))", 'O.name = "named"', 'O.dir = 4',
                           'F["k"] << O'], 'F.ExportText("/")')
    sv("savefile.<<atom", ["var/obj/O = parity_track(new /obj(locate(2, 2, 1)))", 'O.name = "named"', "O.density = 1",
                           'F["k"] << O', "var/obj/x", 'F["k"] >> x', "parity_track(x)"], "list(x.name, x.density, x.loc)")
    sv("savefile.<<atom", ["var/obj/O = parity_track(new /obj(locate(2, 2, 1)))", "O.icon = 'test.dmi'",
                           'O.icon_state = "solid"', 'F["k"] << O', "var/obj/x", 'F["k"] >> x', "parity_track(x)"],
       "list(x.icon_state, isicon(x.icon) || isfile(x.icon))")
    sv("savefile.<<atom", ["F[\"k\"] << locate(3, 4, 1)"], 'F.ExportText("/")')
    sv("savefile.<<atom", ["F[\"k\"] << locate(/area)"], 'F.ExportText("/")')
    sv("savefile.<<atom", ['F["k"] << world'], 'F.ExportText("/")')
    sv("savefile.<<atom", ['F["k"] << world', "var/x", 'F["k"] >> x'], "x")
    # Datum vars: defaults, tmp, global and const are skipped
    sv("savefile.Write", ['F["k"] << new /datum/savedb_tmpall'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.t = 99", 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.t = 99", 'F["k"] << T', "var/datum/savedb_thing/x",
                          'F["k"] >> x'], "x.t")
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.a = 1", 'T.b = "x"', 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.a = null", 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.a = null", 'F["k"] << T', "var/datum/savedb_thing/x",
                          'F["k"] >> x'], "savedb_show(x)")
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.c = list()", 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", 'T.tag = "savedb_tag"', 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/sub/T = new", "T.a = 1", 'F["k"] << T'], 'F.ExportText("/")')
    sv("savefile.Write", ["var/datum/savedb_thing/sub/T = new", "T.a = 1", 'F["k"] << T', "var/datum/savedb_thing/x",
                          'F["k"] >> x'], "savedb_show(x)")
    # Write()/Read() overrides: call order, extra keys, no ..()
    sv("savefile.Write", ["savedb_log = list()", "var/datum/savedb_rw/R = new", "R.v = 3", 'F["k"] << R'],
       'list(savedb_log, F.ExportText("/"))')
    sv("savefile.Read", ["savedb_log = list()", "var/datum/savedb_rw/R = new", "R.v = 3", 'F["k"] << R', "var/x",
                         'F["k"] >> x'], "list(savedb_log, savedb_show(x))")
    sv("savefile.Write", ["var/datum/savedb_nosuper/N = new", "N.v = 3", 'F["k"] << N'], 'F.ExportText("/")')
    sv("savefile.Read", ["var/datum/savedb_nosuper/N = new", "N.v = 3", 'F["k"] << N', "var/x", 'F["k"] >> x'],
       "savedb_show(x)")
    sv("savefile.Read", ["savedb_log = list()", "savedb_news = 0", "var/datum/savedb_new/D = new", "D.v = 2",
                         'F["k"] << D', "savedb_log = list()", "var/datum/savedb_new/x", 'F["k"] >> x'],
       "list(savedb_log, savedb_news, x.v)")
    sv("savefile.Write", ["savedb_log = list()", "var/datum/savedb_cd/D = new", "D.v = 2", 'F["k"] << D'],
       "list(savedb_log, F.cd)")
    sv("savefile.Read", ["savedb_log = list()", "var/datum/savedb_cd/D = new", "D.v = 2", 'F["k"] << D',
                         "savedb_log = list()", 'F.cd = "/"', "var/x", 'F["k"] >> x'], "list(savedb_log, F.cd)")
    sv("savefile.Write", ["savedb_log = list()", "var/datum/savedb_cd/D = new", "D.v = 2", 'F["a/b"] << D'],
       "list(savedb_log, F.cd)")
    sv("savefile.Write", ["savedb_log = list()", "var/datum/savedb_cd/D = new", 'F.cd = "/x"', "F << D"],
       "list(savedb_log, F.cd)")
    sv("savefile.Write", ["savedb_log = list()", "var/datum/savedb_cd/D = new", 'F["l"] << list(D, D)'],
       "list(savedb_log, F.cd)")
    # Calling Write()/Read() directly
    sv("savefile.Write", ["var/datum/savedb_thing/T = new", "T.a = 8", 'F.cd = "/obj"', "T.Write(F)", 'F.cd = "/"'],
       'F.ExportText("/")')
    sv("savefile.Read", ['F["a"] << 8', 'F["b"] << "rb"', 'F["t"] << 1', "var/datum/savedb_thing/T = new",
                         "T.Read(F)"], "savedb_show(T)")
    sv("savefile.Read", ['F["a"] << 8', 'F["zzz"] << 1', "var/datum/savedb_thing/T = new", "T.Read(F)"],
       "savedb_show(T)")
    # Write of a type that no longer matches the stored type text
    sv("savefile.Read", ['F["k/.0/type"] << /datum/savedb_thing', 'F["k/.0/a"] << 77', 'F.cd = "/"'],
       'F.ExportText("/")')

    # ================================================================ savefile: buffers are streams
    for v in VALS_S:
        sv("savefile.stream", [f"F << {v}", "F << 2", 'F.cd = "/"', "var/x", "var/y", "F >> x", "F >> y"],
           "list(savedb_show(x), y)")
        svn("savefile.reopen", [f'F["k"] << {v}', "del F", "F = new /savefile(@N)", "var/x", 'F["k"] >> x'],
            "savedb_show(x)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", "F << 3", 'F.cd = "/a"', "var/x", "var/y", "var/z",
                           "var/w", "F >> x", "F >> y", "F >> z", "F >> w"], "list(x, y, z, w)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2"], 'F.ExportText("/")')
    sv("savefile.stream", ["F << 1", "F << \"two\"", "F << list(3)"], 'F.ExportText("/")')
    sv("savefile.stream", ['F["a"] << 1', 'F["a"] << 2', "var/x", 'F["a"] >> x'], "x")
    sv("savefile.stream", ['F["a"] << 1', 'F["a"] << 2'], 'F.ExportText("/")')
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/"', "var/x", "var/y", 'F["a"] >> x',
                           'F["a"] >> y'], "list(x, y)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", "var/x", "F >> x"], "x")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "."', "var/x", "F >> x"], "x")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/"', 'F.cd = "a"', "var/x", "var/y",
                           "F >> x", "F >> y"], "list(x, y)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/a"', "F << 9", 'F.cd = "/a"', "var/x",
                           "var/y", "F >> x", "F >> y"], "list(x, y)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/"'], 'F["a"]')
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", 'F["sub"] << 5', "F << 2", 'F.cd = "/a"', "var/x", "var/y",
                           "F >> x", "F >> y"], "list(x, y)")
    sv("savefile.stream", ['F.cd = "/a"', "F << 1", 'F["sub"] << 5', "F << 2"], 'F.ExportText("/")')
    sv("savefile.stream", ["var/x", "F >> x"], "x")
    sv("savefile.stream", ["var/x = 5", "F >> x"], "x")
    sv("savefile.stream", ["var/x = 5", 'F["nope"] >> x'], "x")
    sv("savefile.stream", ['F["a"] << 1', "var/x = 5", 'F["a/b"] >> x'], "x")
    sv("savefile.stream", ['F.cd = "/a"', "F << null", "F << 2", 'F.cd = "/a"', "var/x = 5", "var/y", "F >> x",
                           "F >> y"], "list(x, y)")
    # Writing to a directory keeps its subdirectories
    sv("savefile.stream", ['F["a/b"] << 1', 'F["a"] << 2', "var/x", "var/y", 'F["a"] >> x', 'F["a/b"] >> y'],
       "list(x, y)")
    sv("savefile.stream", ['F["a/b"] << 1', 'F["a"] << 2'], 'F.ExportText("/")')
    # Overwriting a datum with a plain value drops its object dirs
    sv("savefile.stream", ['F["a"] << new /datum/savedb_thing', 'F["a"] << 2'], 'F.ExportText("/")')
    sv("savefile.stream", ['F["a"] << savedb_thing(5)', 'F["a"] << 2'], 'F.ExportText("/")')

    # ================================================================ savefile: operator[]
    sv("savefile[]", ['F["a"] = 1'], 'F["a"]')
    sv("savefile[]", [], 'F["missing"]')
    sv("savefile[]", ['F["a"] = 1'], 'list(F["a"], F["/a"], F["./a"], F["a/"], F["A"])')
    sv("savefile[]", ['F["a/b/c"] = 3'], 'list(F["a/b/c"], F["/a/b/c"], F["a"], F["a/b"])')
    sv("savefile[]", ['F["a/b/c"] = 3'], 'savedb_dir(F)')
    sv("savefile[]", ['F["a/b/c"] = 3', 'F.cd = "a/b"'], 'list(F["c"], F[".."], F["../b/c"], F.cd)')
    sv("savefile[]", ['F["a"] = 1', 'F.cd = "/x/y"'], 'list(F["/a"], F["../../a"], F["a"])')
    sv("savefile[]", ['F["a"] = 1'], 'F.cd')
    sv("savefile[]", ['F["."] = 1'], 'list(F["."], F.ExportText("/"))')
    sv("savefile[]", ['F["."] = 1', 'var/x', 'F >> x'], 'x')
    sv("savefile[]", ['F["/"] = 1'], 'list(F["/"], F.ExportText("/"))')
    sv("savefile[]", ['F[".."] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F[""] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F[" "] = 1'], 'list(F[" "], savedb_dir(F))')
    sv("savefile[]", ['F["é日"] = "v"'], 'list(F["é日"], savedb_dir(F), F.ExportText("/"))')
    sv("savefile[]", ['F["a b"] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F["1"] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F["a=b"] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F["q\\"k"] = 1'], 'F.ExportText("/")')
    sv("savefile[]", ['F["a"] = 1', 'F["a"] = null'], 'list(F["a"], savedb_dir(F), F.ExportText("/"))')
    sv("savefile[]", ['F["a"] = list(1, 2)'], 'F["a"][2]')
    sv("savefile[]", ['F["a"] = list(1, 2)', 'F["a"] += 3'], 'F["a"]')
    sv("savefile[]", ['F["a"] = 1', 'F["a"] += 3'], 'F["a"]')
    sv("savefile[]", ['F["a"] = 1', 'F["a"]++'], 'F["a"]')
    sv("savefile[]", ['F["a"] = "x"', 'F["a"] += "y"'], 'F["a"]')
    sv("savefile[]", ['F["a"] = 5'], 'F["a"] * 2')
    for idx in ["1", "0", "null", "list()", "/datum", "new /datum", "1.5", "PINF"]:
        sv("savefile[]", [], f"F[{idx}]")
        sv("savefile[]=", [f"F[{idx}] = 1"], 'F.ExportText("/")')
        sv("savefile[]<<", [f"F[{idx}] << 1"], 'F.ExportText("/")')
    # [] reads always start at the buffer's first value; >> continues
    sv("savefile[]", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/"'], 'list(F["a"], F["a"])')
    sv("savefile[]", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/a"', "var/x", "F >> x"], 'list(x, F["."])')
    # Reading a [] key does not create it
    sv("savefile[]", ['var/x = F["ghost"]'], 'list(x, savedb_dir(F), F.ExportText("/"))')
    sv("savefile[]", ['var/x', 'F["ghost"] >> x'], 'list(x, savedb_dir(F))')
    sv("savefile[]", ['var/x', 'F["g1/g2"] >> x'], 'list(x, savedb_dir(F))')
    # Write order and many keys
    sv("savefile[]", ['for(var/i in 1 to 30)', '\tF["k[i]"] << i'], 'savedb_dir(F)')
    sv("savefile[]", ['for(var/i in 1 to 30)', '\tF["k[i]"] << i'], 'F["k17"]')
    sv("savefile[]", ['F["b"] << 1', 'F["a"] << 2', 'F["c"] << 3'], 'list(savedb_dir(F), F.ExportText("/"))')
    sv("savefile[]", ['F["b"] << 1', 'F["a"] << 2', 'F["c"] << 3'], 'F.dir[1]')
    sv("savefile[]", ['F["B"] << 1', 'F["a"] << 2', 'F["_"] << 3', 'F["1"] << 4'], 'savedb_dir(F)')
    sv("savefile[]", ['F["a"] << 1', 'F["A"] << 2'], 'list(F["a"], F["A"], savedb_dir(F))')

    # ================================================================ savefile: cd
    for p in SV_PATHS:
        sv("savefile.cd", [f"F.cd = {p}"], "F.cd")
        sv("savefile.cd", ['F.cd = "/x/y"', f"F.cd = {p}"], "F.cd")
        sv("savefile.cd", [f"F.cd = {p}", "F << 1"], 'F.ExportText("/")')
    for p in SV_CD_BAD:
        sv("savefile.cd", [f"F.cd = {p}"], "F.cd")
        sv("savefile.cd", ['F.cd = "/x"', f"F.cd = {p}"], "F.cd")
    sv("savefile.cd", [], "F.cd")
    sv("savefile.cd", ['F.cd = "/a"'], "savedb_dir(F)")
    sv("savefile.cd", ['F.cd = "/a"', 'F.cd = "/"'], "savedb_dir(F)")
    sv("savefile.cd", ['F.cd = "/a"', 'F.cd = "/"'], 'F.ExportText("/")')
    sv("savefile.cd", ['F.cd = "/a/b"', 'F.cd = "/"'], "list(savedb_dir(F), F.dir.len)")
    sv("savefile.cd", ['F.cd = "/a"', 'F["k"] << 1', 'F.cd = "/"'], 'list(F["a/k"], savedb_dir(F))')
    sv("savefile.cd", ['F.cd = "/a"', 'F.cd = "b"', 'F.cd = "../c"'], "F.cd")
    sv("savefile.cd", ['F.cd = "/a"', 'F.cd = "../../.."'], "F.cd")
    sv("savefile.cd", ['F.cd = "a"', 'F.cd = "a"'], "F.cd")
    sv("savefile.cd", ['F["d/k"] << 1', 'F.cd = "d"', "var/x", 'F["k"] >> x'], "list(x, F.cd)")
    sv("savefile.cd", ['F["d"] << 1', 'F.cd = "d"', "var/x", "F >> x"], "x")
    sv("savefile.cd", ['F.cd = "/a"', 'F["../b"] << 1', 'F.cd = "/"'], 'F.ExportText("/")')
    sv("savefile.cd", ['F.cd = "/a"', 'F["/b"] << 1', 'F.cd = "/"'], 'F.ExportText("/")')
    sv("savefile.cd", ['F.cd = "/a"', 'F["b"] << 1'], 'list(F.cd, F.ExportText("/"))')
    sv("savefile.cd", ['F["a/b"] << 1'], "F.cd")
    sv("savefile.cd", ['F.cd = "/a"', 'F.cd += "/b"'], "F.cd")

    # ================================================================ savefile: dir list
    sv("savefile.dir", [], "savedb_dir(F)")
    sv("savefile.dir", [], "F.dir.len")
    sv("savefile.dir", [], "islist(F.dir)")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], "parity_canon(F.dir)")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], "list(F.dir.len, length(F.dir))")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], 'list("a" in F.dir, "c" in F.dir, 1 in F.dir)')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], 'list(F.dir.Find("b"), F.dir.Find("c"))')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], "list(F.dir[1], F.dir[2])")
    sv("savefile.dir", ['F["a"] << 1'], "F.dir[2]")
    sv("savefile.dir", ['F["a"] << 1'], "F.dir[0]")
    sv("savefile.dir", ['F["a"] << 1'], 'F.dir["a"]')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], "F.dir.Copy()")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2'], 'jointext(F.dir, ",")')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2', "var/list/L = F.dir", 'F["c"] << 3'], "L.len")
    sv("savefile.dir", ['F["a/x"] << 1', 'F["b"] << 2', 'F.cd = "a"'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a/x"] << 1', 'F["b"] << 2', 'F.cd = "/nope"'], "savedb_dir(F)")
    sv("savefile.dir", ['F.dir.Add("n1")'], 'list(savedb_dir(F), F["n1"], F.ExportText("/"))')
    sv("savefile.dir", ['F.dir.Add("n1", "n2")'], "savedb_dir(F)")
    sv("savefile.dir", ['F.dir += "n1"'], "savedb_dir(F)")
    sv("savefile.dir", ['F.dir.Add("a/b")'], "list(savedb_dir(F), F.ExportText(\"/\"))")
    sv("savefile.dir", ['F["a"] << 1', 'F.dir.Add("a")'], 'list(savedb_dir(F), F["a"])')
    sv("savefile.dir", ["F.dir.Add(1)"], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2', 'F.dir.Remove("a")'], 'list(savedb_dir(F), F["a"])')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2', 'F.dir -= "a"'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << 1', 'F.dir.Remove("zz")'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << 1'], 'F.dir.Remove("a")')
    sv("savefile.dir", ['F["a/b"] << 1', 'F["a/c"] << 2', 'F.dir.Remove("a")'], 'list(savedb_dir(F), F["a/b"])')
    sv("savefile.dir", ['F["a/b"] << 1', 'F.dir.Remove("a/b")'], 'list(savedb_dir(F), F["a/b"])')
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2', "F.dir.Cut()"], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << 1', 'F["b"] << 2', 'F.dir[1] = "z"'], 'list(savedb_dir(F), F["z"], F["a"])')
    sv("savefile.dir", ['F["a"] << 1', 'F.dir.len = 0'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << 1', "F.dir = list()"], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << new /datum/savedb_thing'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << new /datum/savedb_thing', 'F.cd = "a"'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << savedb_thing(2)', 'F.cd = "a"'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << savedb_thing(2)', 'F.cd = "a/.0"'], "savedb_dir(F)")
    sv("savefile.dir", ['F["a"] << list(savedb_thing(2))', 'F.cd = "a"'], "savedb_dir(F)")
    sv("savefile.dir", ['for(var/i in 1 to 5)', '\tF["k[i]"] << i', "var/list/L = list()", "for(var/k in F.dir)",
                        '\tL += F[k]'], "L")

    # ================================================================ savefile: eof
    sv("savefile.eof", [], "F.eof")
    sv("savefile.eof", ['F["a"] << 1'], "F.eof")
    sv("savefile.eof", ["F << 1"], "F.eof")
    sv("savefile.eof", ["F << 1", 'F.cd = "/"'], "F.eof")
    sv("savefile.eof", ["F << 1", 'F.cd = "/"', "var/x", "F >> x"], "list(x, F.eof)")
    sv("savefile.eof", ["F << 1", "F << 2", 'F.cd = "/"', "var/x", "F >> x"], "list(x, F.eof)")
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F.cd = "/a"'], "F.eof")
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F.cd = "/a"', "F.eof = 1", "var/x = 7", "F >> x"],
       "list(x, F.eof)")
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/a"', "var/x", "F >> x", "F.eof = 0",
                        "var/y", "F >> y"], "list(x, y, F.eof)")
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F["sub"] << 2', 'F.cd = "/a"', "F.eof = -1", 'F.cd = "/"'],
       'list(F["a"], F["a/sub"], savedb_dir(F), F.ExportText("/"))')
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F.cd = "/a"', "F.eof = -1"], "F.eof")
    sv("savefile.eof", ["F << 1", 'F["k"] << 2', 'F.cd = "/"', "F.eof = -1"], 'list(F.eof, F["k"], F.ExportText("/"))')
    sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F.cd = "/a"', "F.eof = -1", "F << 5", 'F.cd = "/a"', "var/x",
                        "F >> x"], "x")
    for v in ["2", "0.5", "-2", "null", '"1"', "PINF", "NAN"]:
        sv("savefile.eof", ['F.cd = "/a"', "F << 1", 'F.cd = "/a"', f"F.eof = {v}"], 'list(F.eof, F.ExportText("/"))')
    sv("savefile.eof", ["savedb_log = list()", 'F.cd = "/a"', "F << 1", "F << 2", 'F.cd = "/a"', "while(!F.eof)", "\tvar/x", "\tF >> x",
                        "\tsavedb_log += x", "\tif(savedb_log.len > 10)", "\t\tbreak"], "savedb_log")

    # ================================================================ savefile: ExportText formats
    def export(lines, path='"/"', proc="savefile.ExportText"):
        sv(proc, lines, f"F.ExportText({path})" if path is not None else "F.ExportText()")
    export([])
    export([], None)
    export([], '"."')
    export([], "null")
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'])
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], None)
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"b"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"/b"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"/b/"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"b/d"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"a"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], '"nope"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2'], "1")
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2', 'F.cd = "b"'], None)
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2', 'F.cd = "b"'], '"/"')
    export(['F["a"] << 1', 'F["b/c"] << "x"', 'F["b/d/e"] << 2', 'F.cd = "b"'], '"d"')
    sv("savefile.ExportText", ['F["a"] << 1', 'F["b/c"] << "x"', 'F.cd = "b"', 'var/t = F.ExportText("/")'],
       "list(t, F.cd)")
    export(['F["b"] << 1', 'F["b"] << 1'])
    export(['F["x"] << 1', 'F["x/y"] << 2', 'F["x/y/z"] << 3'])
    export(['F["x/y/z"] << 3'])
    export(['F["x/y/z"] << 3'], '"x/y/z"')
    export(['F["a"] << list(1, list(2, list(3)))'])
    export(['F["a"] << list("k" = list("v" = list()))'])
    export(['F["a"] << list(savedb_thing(2), savedb_thing(3))'])
    export(['F["a"] << list("k" = savedb_thing(2))'])
    export(['F["a"] << list(savedb_thing(2) = 1)'])
    export(['F["a"] << savedb_thing(2, null, list(savedb_thing(3)))'])
    export(['F["a"] << savedb_thing(2)', 'F["b"] << savedb_thing(3)'])
    export(['F.cd = "/q"', "F << savedb_thing(2)", 'F.cd = "/"'])
    export(['F << savedb_thing(2)'])
    export(['F["a"] << new /savefile()'])
    export(['var/savefile/G = new', 'G["in"] << 5', 'F["a"] << G'])
    sv("savefile.<<savefile", ['var/savefile/G = new', 'G["in"] << 5', 'F["a"] << G', "var/x", 'F["a"] >> x'],
       "list(isfile(x), istype(x, /savefile))")
    sv("savefile.<<savefile", ['var/savefile/G = new', 'G["in"] << 5', 'F["a"] << G', "var/x", 'F["a"] >> x',
                               "var/savefile/H = new(x)"], 'H["in"]')
    for n in ["0.1", "0.2", "1/3", "2/3", "1e6", "999999", "1000000", "1e-5", "0.0001", "123.456", "-0", "1e38",
              "3.4e38", "1.17549e-38", "16777216", "8388608.5", "0.30000001", "100000.5", "-1e-10"]:
        export([f'F["n"] << {n}'])
        sv("savefile.<<num", [f'F["n"] << {n}', "var/x", 'F["n"] >> x'], "x")
    for t in ["", " ", "\n", "\t", "\\", '"', "''", "[x]", "\\[x\\]", "a\nb\n", "é", "🙂", "<>&", "{}", "\"}",
              "\\n", "a" * 300, "x\x7fy"]:
        export([f'F["t"] << {dm_str(t)}'])
    export(['F["t"] << "[ascii2text(13)]"'])
    export(['F["t"] << "[ascii2text(0)]x"'])
    export(['F["t"] << "\\ref"'])
    export(['F["t"] << "\\red bold"'])
    export(["F[\"f\"] << 'small.dmi'"])
    export(["F[\"f\"] << icon('small.dmi', \"solid\")"])
    export(['F["f"] << file("small.dmi")'])
    export(['F["p"] << /proc/savedb_named'])
    export(['F["p"] << /datum/proc/Write'])
    export(['F["p"] << /datum/savedb_thing/proc/Write'])
    sv("savefile.<<proc", ['F["p"] << /proc/savedb_named', "var/x", 'F["p"] >> x'], "x")
    export(['F["l"] << list(1 = 2)'])
    export(['F["l"] << list(-1, 1.5, "é", /datum, null, list())'])
    export(['F["l"] << list("a" = 1, "b", "c" = "d")'])
    export(["F[\"l\"] << list('small.dmi')"])
    export(['F["l"] << new /list(3)'])
    export(['var/list/L[2][2]', 'F["l"] << L'])
    export(['F["e"] << new /exception("boom")'])
    export(['F["m"] << matrix(2, 0, 0, 0, 2, 0)'])
    export(['F["v"] << vector(1, 2, 3)'])
    export(['F["v"] << vector(1.5, -2)'])
    # ExportText to a file
    for f in ['file(@N + ".txt")', '@N + ".txt"']:
        svn("savefile.ExportText", ['F["a"] << 1', 'fdel(@N + ".txt")', f'var/r = F.ExportText("/", {f})',
                                     'var/t = file2text(@N + ".txt")', 'fdel(@N + ".txt")'], "list(r, t)")
    svn("savefile.ExportText", ['F["a"] << 1', 'fdel(@N + ".txt")', 'text2file("old\\n", @N + ".txt")',
                                 'F.ExportText("/", file(@N + ".txt"))', 'var/t = file2text(@N + ".txt")',
                                 'fdel(@N + ".txt")'], "t")
    sv("savefile.ExportText", ['F["a"] << 1'], 'F.ExportText("/", null)')
    sv("savefile.ExportText", ['F["a"] << 1'], 'F.ExportText("/", 5)')
    sv("savefile.ExportText", ['F["a"] << 1'], 'F.ExportText(path = "/")')
    sv("savefile.ExportText", ['F["a"] << 1'], 'F.ExportText("/", "/", "/")')

    # ================================================================ savefile: ImportText
    IMPORTS = [
        'a = 1', 'a = 1\nb = "x"', 'a = "x"\n', 'a = 1.5', 'a = -1', 'a = 1e+07', 'a = null', 'a = /datum',
        'a = list(1,2)', 'a = list("k" = 1)', 'a = list()', 'a\n\tb = 2', 'a = 1\n\tb = 2', 'a\n\tb\n\t\tc = 3',
        'a = "q\\"x"', 'a = "line\\nbreak"', 'a = "\\[b\\]"', '', '\n', 'garbage!!', 'a =', '= 1', 'a = b',
        'a = object(".0")\n\t.0\n\t\ttype = /datum/savedb_thing\n\t\ta = 4',
        'a = object(".0")\n\t.0\n\t\ttype = /datum/savedb_rw\n\t\tv = 2\n\t\textra = 9',
        '\na = 1\n', 'a = 1 // c', 'a = 1;b = 2', '"a b" = 1', 'a = "é日本"', 'a = list(list(1), "x" = list(2))',
        'a = 1\na = 2',
    ]
    for t in IMPORTS:
        sv("savefile.ImportText", [f'F.ImportText("/", {dm_str(t)})'], 'F.ExportText("/")')
        sv("savefile.ImportText", [f'F.ImportText("/", {dm_str(t)})', "var/x", 'F["a"] >> x'],
           'list(savedb_show(x), savedb_dir(F))')
    sv("savefile.ImportText", ['F.ImportText("/", "a = 1")'], "F.ImportText(\"/\", \"b = 2\")")
    sv("savefile.ImportText", ['F["old"] << 1', 'F.ImportText("/", "a = 1")'], "savedb_dir(F)")
    sv("savefile.ImportText", ['F["a"] << 1', 'F.ImportText("/", "a = 2")'], 'F["a"]')
    sv("savefile.ImportText", ['F.ImportText("sub", "a = 1")'], 'list(F["sub/a"], F.ExportText("/"))')
    sv("savefile.ImportText", ['F.ImportText("/x/y", "a = 1")'], 'F.ExportText("/")')
    sv("savefile.ImportText", ['F.cd = "/c"', 'F.ImportText(source = "a = 1")', 'F.cd = "/"'], 'F.ExportText("/")')
    sv("savefile.ImportText", ['F.cd = "/c"', 'F.ImportText(, "a = 1")', 'F.cd = "/"'], 'F.ExportText("/")')
    sv("savefile.ImportText", ['F.ImportText("/", null)'], 'F.ExportText("/")')
    sv("savefile.ImportText", ['F.ImportText("/", 5)'], 'F.ExportText("/")')
    sv("savefile.ImportText", ['F.ImportText("/", list("a" = 1))'], 'F.ExportText("/")')
    # Round trip: export one savefile, import into another
    for v in VALS_S + ['savedb_thing(2, "y", list(1))', 'list("k" = savedb_thing(3))']:
        sv("savefile.ImportText", [f'F["k"] << {v}', 'F["d/e"] << 2', "var/savefile/G = new",
                                   'G.ImportText("/", F.ExportText("/"))', "var/x", 'G["k"] >> x'],
           'list(savedb_show(x), G["d/e"], G.ExportText("/") == F.ExportText("/"))')
    svn("savefile.ImportText", ['F["a"] << 1', 'fdel(@N + ".txt")', 'text2file("b = 2\\nc = \\"x\\"", @N + ".txt")',
                                 'F.ImportText("/", file(@N + ".txt"))', 'fdel(@N + ".txt")'], 'F.ExportText("/")')
    svn("savefile.ImportText", ['fdel(@N + ".txt")', 'text2file("b = 2", @N + ".txt")',
                                 'F.ImportText("/", @N + ".txt")', 'fdel(@N + ".txt")'], 'F.ExportText("/")')

    # ================================================================ savefile: files, name, Flush, Lock
    svn("savefile.New", [], "fexists(@N)")
    svn("savefile.New", [], "F.name")
    svn("savefile.New", [], '"[F]"')
    svn("savefile.New", ["F.Flush()"], "fexists(@N)")
    svn("savefile.New", ['F["a"] << 1', "F.Flush()"], "length(file(@N)) > 0")
    svn("savefile.New", ['F["a"] << 1'], "fexists(@N)")
    svn("savefile.New", ['F["a"] << 1', "del F"], "fexists(@N)")
    svn("savefile.New", ['F["a"] << 1', "del F", "F = new /savefile(@N)"], "list(savedb_dir(F), F[\"a\"], F.cd, F.eof)")
    svn("savefile.New", ['F["a"] << 1', "del F", "F = new /savefile(@N)"], 'F.ExportText("/")')
    svn("savefile.New", ['F["a"] << 1', "var/savefile/G = new /savefile(@N)"], 'list(G["a"], G.cd)')
    svn("savefile.New", ['F["a"] << 1', "var/savefile/G = new /savefile(@N)", 'G["b"] << 2'], 'F["b"]')
    svn("savefile.New", ['F["a"] << 1', "var/savefile/G = new /savefile(@N)", 'G.cd = "/x"'], "F.cd")
    svn("savefile.New", ['F["a"] << 1', "F.Flush()", "var/savefile/G = new /savefile(file(@N))"], 'G["a"]')
    svn("savefile.New", ['F["a"] << 1', "F.Flush()", "var/savefile/G = new /savefile(file(@N))"], "G.name")
    svn("savefile.New", ['F["a"] << 1', "del F", "fdel(@N)", "F = new /savefile(@N)"], "savedb_dir(F)")
    svn("savefile.New", ['F["a"] << 1', "F.Flush()", "fdel(@N)", "var/savefile/G = new /savefile(@N)"], "savedb_dir(G)")
    svn("savefile.New", ["F = new /savefile(@N, 0)"], "F.name")
    svn("savefile.New", ["F = new /savefile(@N, 1)"], "F.name")
    svn("savefile.New", ["F = new /savefile(@N, -1)"], "F.name")
    svn("savefile.Flush", ['F["a"] << 1'], "F.Flush()")
    svn("savefile.Flush", ['F["a"] << 1'], "F.Flush(1, 2)")
    sv("savefile.Flush", ['F["a"] << 1'], "F.Flush()")
    sv("savefile.Flush", ['F["a"] << 1', "F.Flush()"], 'F["a"]')
    svn("savefile.Lock", [], "F.Lock()")
    svn("savefile.Lock", [], "F.Lock(0)")
    svn("savefile.Lock", [], "F.Lock(-1)")
    svn("savefile.Lock", ["F.Lock(0)"], "F.Unlock()")
    svn("savefile.Lock", ["F.Lock(0)", "F.Unlock()", 'F["a"] << 1'], 'F["a"]')
    sv("savefile.Lock", [], "F.Lock(0)")
    sv("savefile.Unlock", [], "F.Unlock()")
    sv("savefile.name", [], "istext(F.name) && length(F.name) > 0")
    sv("savefile.name", [], "fexists(F.name)")
    sv("savefile.name", ["F.name = \"x\""], "F.name == \"x\"")
    sv("savefile.name", [], "F.type")
    sv("savefile.name", [], 'istype(F, /savefile)')
    sv("savefile.name", [], 'isfile(F)')
    sv("savefile.vars", [], "F.byond_version")
    sv("savefile.vars", [], "F.byond_build")
    sv("savefile.vars", ["F.byond_version = 514"], "F.byond_version")
    sv("savefile.vars", [], '"cd" in F.vars')
    sv("savefile.vars", [], 'F.vars["cd"]')
    svn("savefile.New", ["F = new /savefile(@N + \"/\")"], "1")
    sv("savefile.New", [], "1")
    s.case("savefile.New", "savedb_done(1, new /savefile(null))")
    s.case("savefile.New", 'savedb_done(1, new /savefile(""))')
    s.body("savefile.New", ["var/savefile/F = new /savefile('test.dmi')"], "savedb_done(savedb_dir(F), F)")
    s.body("savefile.New", ["var/savefile/F = new /savefile(5)"], "savedb_done(savedb_dir(F), F)")
    s.body("savefile.New", ["var/savefile/F = new /savefile(list())"], "savedb_done(savedb_dir(F), F)")
    s.body("savefile.New", ['fdel("sv_tmp/notsave.txt")', 'text2file("not a savefile", "sv_tmp/notsave.txt")',
                            'var/savefile/F = new /savefile("sv_tmp/notsave.txt")', 'var/r = savedb_dir(F)', "del F"],
           'savedb_done(r, null, "sv_tmp/notsave.txt")')
    s.body("savefile.New", ['fdel("sv_tmp/newdir/")', 'var/savefile/F = new /savefile("sv_tmp/newdir/x.sav")',
                            'F["a"] << 1', "F.Flush()", 'var/r = fexists("sv_tmp/newdir/x.sav")', "del F",
                            'fdel("sv_tmp/newdir/")'], "r")
    # Savefile in a savefile reopened from the cache file
    sv("savefile.New", ['var/savefile/G = new', 'G["in"] << 5', 'F["g"] << G', "var/c", 'F["g"] >> c',
                        "var/savefile/H = new /savefile(c)", 'H["in"] << 6', "var/savefile/J = new /savefile(c)"],
       'list(H["in"], J["in"])')
    # Deleted savefile datum
    sv("savefile.del", ["var/savefile/G = new", "del G"], "G")
    sv("savefile.del", ["var/savefile/G = new", "var/list/L = G.dir", 'G["a"] << 1', "del G"], "L.len")

    # ================================================================ database: Execute and results
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute(db)")
    db("query.Execute", ['q = new("SELEC 1")'], "q.Execute(db)")
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute()")
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute(null)")
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute(@N)")
    db("query.Execute", ['q = new("SELECT 1")', "q.Execute(@N)", "q.NextRow()"], "q.GetRowData()")
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute(5)")
    db("query.Execute", ['q = new("SELECT 1")'], "q.Execute(new /datum)")
    db("query.Execute", ["q = new"], "q.Execute(db)")
    db("query.Execute", ['q = new("")'], "list(q.Execute(db), q.NextRow(), q.Error(), q.ErrorMsg())")
    db("query.Execute", ['q = new("   ")'], "list(q.Execute(db), q.NextRow(), q.Error(), q.ErrorMsg())")
    db("query.Execute", ['q = new("CREATE TABLE x (a)")'], "q.Execute(db)")
    db("query.Execute", ['q = new("CREATE TABLE x (a)")', "q.Execute(db)"], "q.Execute(db)")
    db("query.Execute", ['q = new("CREATE TABLE x (a)")', "q.Execute(db)"], "list(q.Execute(db), q.Error(), q.ErrorMsg())")
    db("query.Execute", ['q = new("SELECT 1")', "q.Execute(db)"], "list(q.Execute(), q.NextRow(), q.GetRowData())")
    db("query.Execute", ['q = new("SELECT 1")', "q.Execute(db)", "q.NextRow()", "q.Execute(db)"],
       "list(q.NextRow(), q.GetRowData(), q.NextRow())")
    db("query.Execute", ['q = new("SELECT 1; SELECT 2")'], "list(q.Execute(db), savedb_rows(q), q.Error(), q.ErrorMsg())")
    db("query.Execute", ['q = new("CREATE TABLE x (a); INSERT INTO x VALUES (5)")', "q.Execute(db)",
                         'q = new("SELECT * FROM x")', "q.Execute(db)"], "savedb_rows(q)")
    db("query.Execute", ['q = new("SELECT 1;")'], "list(q.Execute(db), savedb_rows(q))")
    db("query.Execute", ['q = new("SELECT 1 -- comment")'], "list(q.Execute(db), savedb_rows(q))")
    db("query.Execute", ['q = new("select 1 as A")'], "list(q.Execute(db), savedb_rows(q))")
    # Result values and their types
    for sql in ["SELECT 1", "SELECT 0", "SELECT -1", "SELECT 1.5", "SELECT 0.1", "SELECT 2.0", "SELECT 1e7",
                "SELECT 16777217", "SELECT 2147483648", "SELECT 9007199254740993", "SELECT 9223372036854775807",
                "SELECT -9223372036854775808", "SELECT 1e308 * 10", "SELECT -1e308 * 10", "SELECT -0.0",
                "SELECT 1/3.0", "SELECT 1/3", "SELECT 7 % 3", "SELECT 'a'", "SELECT ''", "SELECT 'é日本'",
                "SELECT '🙂'", "SELECT 'it''s'", "SELECT '5'", "SELECT NULL", "SELECT x'4142'", "SELECT x''",
                "SELECT zeroblob(2)", "SELECT CAST(1 AS REAL)", "SELECT CAST('7' AS INTEGER)", "SELECT 1 = 1",
                "SELECT 'a' || 'b'", "SELECT 1 + '2'", "SELECT 123456789.123", "SELECT abs(-5)", "SELECT upper('a')",
                "SELECT length('é')", "SELECT typeof(1.0)", "SELECT char(65, 0, 66)", "SELECT 'a' || char(10) || 'b'",
                "SELECT 1, 'x', NULL, 2.5", "SELECT 1 AS a, 2 AS a", "SELECT 1 AS \"my col\"", "SELECT 1 AS \"\"",
                "SELECT 1 AS [b]", "SELECT 1 AS \"é\"", "SELECT 1 WHERE 0", "SELECT 3 UNION SELECT 1 UNION SELECT 2"]:
        db("query.result", [f"q = new({dm_str(sql)})"], "savedb_one(db, q)")
        db("query.GetColumn", [f"q = new({dm_str(sql)})", "q.Execute(db)", "q.NextRow()"],
           "list(q.GetColumn(0), q.GetColumn(1))")
    db("query.result", ['q = new("SELECT 1.5, 2, \'t\', NULL")', "q.Execute(db)", "q.NextRow()"],
       "savedb_types(q.GetRowData())")
    db("query.result", ['q = new("SELECT x\'4142\' AS b")', "q.Execute(db)", "q.NextRow()"],
       "savedb_types(q.GetRowData())")
    db("query.result", ['q = new("SELECT x\'4142\' AS b")', "q.Execute(db)", "q.NextRow()", "var/x = q.GetColumn(0)"],
       'list(isfile(x), istext(x), "[x]")')
    # Typed table round trip
    db("query.table", ['q = new("SELECT * FROM t")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.table", ['q = new("SELECT * FROM t ORDER BY a DESC")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.table", ['q = new("SELECT a, b FROM t WHERE a > 1")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.table", ['q = new("SELECT count(*) FROM t")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.table", ['q = new("SELECT sum(c), max(b), avg(a) FROM t")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.table", ['q = new("SELECT * FROM t WHERE a = 99")', "q.Execute(db)"],
       "list(q.NextRow(), q.GetRowData(), q.Columns())", table=True)
    db("query.table", ['q = new("SELECT a FROM t WHERE b IS NULL")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    for col in range(-1, 7):
        db("query.GetColumn", ['q = new("SELECT * FROM t")', "q.Execute(db)", "q.NextRow()", "q.NextRow()"],
           f"list(q.GetColumn({col}), q.Error(), q.ErrorMsg())", table=True)
        db("query.Columns", ['q = new("SELECT * FROM t")', "q.Execute(db)"],
           f"list(q.Columns({col}), q.Error(), q.ErrorMsg())", table=True)
    for col in ['"a"', '"b"', '"zz"', "null", "1.5", "1.9", '"1"', "list()", "PINF", "NAN"]:
        db("query.GetColumn", ['q = new("SELECT * FROM t")', "q.Execute(db)", "q.NextRow()", "q.NextRow()"],
           f"q.GetColumn({col})", table=True)
        db("query.Columns", ['q = new("SELECT * FROM t")', "q.Execute(db)"], f"q.Columns({col})", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t")', "q.Execute(db)", "q.NextRow()"], "q.GetColumn()", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t")', "q.Execute(db)"], "q.GetColumn(0)", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t")'], "q.GetColumn(0)", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t")', "q.Execute(db)", "var/cnt = 0", "while(q.NextRow() && cnt < 20)", "\tcnt++"],
       "list(q.GetColumn(0), q.GetRowData())", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t WHERE a = 3")', "q.Execute(db)", "q.NextRow()"],
       "list(q.GetColumn(1), q.GetColumn(2), q.GetColumn(3), q.GetColumn(4))", table=True)
    db("query.GetColumn", ['q = new("SELECT * FROM t WHERE a = 1")', "q.Execute(db)", "q.NextRow()"],
       "list(q.GetColumn(3), q.Error(), q.ErrorMsg())", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t WHERE a = 1")', "q.Execute(db)", "q.NextRow()"],
       "list(q.GetRowData(), q.Error())", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t WHERE a = 1")', "q.Execute(db)", "q.NextRow()"],
       "savedb_types(q.GetRowData())", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t WHERE a = 2")', "q.Execute(db)", "q.NextRow()"],
       "savedb_types(q.GetRowData())", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t")', "q.Execute(db)"], "q.GetRowData()", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t")'], "q.GetRowData()", table=True)
    db("query.GetRowData", ["q = new"], "q.GetRowData()")
    db("query.GetRowData", ['q = new("SELECT * FROM t")', "q.Execute(db)", "q.NextRow()", "var/list/L = q.GetRowData()",
                            'L["a"] = 50'], "list(L, q.GetRowData())", table=True)
    db("query.GetRowData", ['q = new("SELECT * FROM t")', "q.Execute(db)", "q.NextRow()"],
       "q.GetRowData() == q.GetRowData()", table=True)
    db("query.GetRowData", ['q = new("SELECT a, a FROM t")', "q.Execute(db)", "q.NextRow()"], "q.GetRowData()", table=True)
    db("query.GetRowData", ['q = new("SELECT a AS z, b AS y FROM t")', "q.Execute(db)", "q.NextRow()"],
       "q.GetRowData()", table=True)
    # Columns
    db("query.Columns", ['q = new("SELECT * FROM t")', "q.Execute(db)"], "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELECT * FROM t")'], "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELECT * FROM t")'], "q.Columns(0)", table=True)
    db("query.Columns", ["q = new"], "q.Columns()")
    db("query.Columns", ['q = new("SELECT a AS x, b, 1 + 1 FROM t")', "q.Execute(db)"], "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELECT * FROM t WHERE 0")', "q.Execute(db)"], "q.Columns()", table=True)
    db("query.Columns", ['q = new("INSERT INTO t VALUES (9, 9, 9, 9, 9)")', "q.Execute(db)"], "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELEC")', "q.Execute(db)"], "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELECT * FROM t")', "q.Execute(db)", "var/cnt = 0", "while(q.NextRow() && cnt < 20)", "\tcnt++"],
       "q.Columns()", table=True)
    db("query.Columns", ['q = new("SELECT * FROM t")', "q.Execute(db)", "var/list/L = q.Columns()", 'L += "x"'], "q.Columns()", table=True)
    # NextRow / Reset / Close / Clear
    db("query.NextRow", ['q = new("SELECT * FROM t")', "q.Execute(db)"],
       "list(q.NextRow(), q.NextRow(), q.NextRow(), q.NextRow(), q.NextRow())", table=True)
    db("query.NextRow", ['q = new("SELECT * FROM t")'], "q.NextRow()", table=True)
    db("query.NextRow", ["q = new"], "q.NextRow()")
    db("query.NextRow", ['q = new("CREATE TABLE y (a)")', "q.Execute(db)"], "q.NextRow()")
    db("query.NextRow", ['q = new("SELEC")', "q.Execute(db)"], "q.NextRow()")
    db("query.NextRow", ['q = new("SELECT * FROM t")', "q.Execute(db)"], "q.NextRow(1)", table=True)
    db("query.Reset", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.NextRow()", "q.NextRow()", "var/r = q.Reset()",
                       "q.NextRow()"], 'list(r, q.GetColumn(0))', table=True)
    db("query.Reset", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.NextRow()", "q.Reset()"],
       "q.GetRowData()", table=True)
    db("query.Reset", ['q = new("SELECT a FROM t")', "q.Execute(db)", "savedb_rows(q)", "q.Reset()"],
       "savedb_rows(q)", table=True)
    db("query.Reset", ['q = new("SELECT a FROM t")'], "list(q.Reset(), q.NextRow())", table=True)
    db("query.Reset", ["q = new"], "q.Reset()")
    db("query.Reset", ['q = new("INSERT INTO t (a) VALUES (10)")', "q.Execute(db)", "q.Reset()",
                       'var/database/query/c = savedb_sql(db, "SELECT count(*) FROM t")', "c.NextRow()"],
       "c.GetColumn(0)", table=True)
    db("query.Close", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.NextRow()", "var/r = q.Close()"],
       "list(r, q.NextRow(), q.GetRowData(), q.Columns())", table=True)
    db("query.Close", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.Close()", "q.Execute(db)"],
       "savedb_rows(q)", table=True)
    db("query.Close", ["q = new"], "q.Close()")
    db("query.Clear", ['q = new("SELECT a FROM t")', "var/r = q.Clear()"], "list(r, q.Execute(db), q.NextRow())",
       table=True)
    db("query.Clear", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.NextRow()", "q.Clear()"],
       "list(q.NextRow(), q.GetRowData())", table=True)
    db("query.Clear", ['q = new("SELECT a FROM t")', "q.Clear()", 'q.Add("SELECT 5")', "q.Execute(db)"],
       "savedb_rows(q)", table=True)
    # RowsAffected
    for sql in ["INSERT INTO t (a) VALUES (10)", "INSERT INTO t (a) SELECT a FROM t", "UPDATE t SET b = 'u'",
                "UPDATE t SET b = 'u' WHERE a = 1", "UPDATE t SET b = 'u' WHERE a = 99", "DELETE FROM t",
                "DELETE FROM t WHERE a < 3", "SELECT * FROM t", "CREATE TABLE z (a)", "DROP TABLE t", "SELEC"]:
        db("query.RowsAffected", [f"q = new({dm_str(sql)})", "q.Execute(db)"], "q.RowsAffected()", table=True)
    db("query.RowsAffected", ['q = new("UPDATE t SET b = 1")'], "q.RowsAffected()", table=True)
    db("query.RowsAffected", ["q = new"], "q.RowsAffected()")
    db("query.RowsAffected", ['q = new("UPDATE t SET b = 1")', "q.Execute(db)", "q.Execute(db)"], "q.RowsAffected()",
       table=True)
    db("query.RowsAffected", ['q = new("DELETE FROM t")', "q.Execute(db)", 'var/database/query/c = savedb_sql(db, "SELECT count(*) FROM t")',
                              "c.NextRow()"], "list(c.GetColumn(0), q.RowsAffected())", table=True)

    # ================================================================ database: errors
    for sql in ["SELEC 1", "SELECT * FROM nosuch", "SELECT nosuch FROM t", "INSERT INTO t VALUES (1)",
                "CREATE TABLE t (a)", "SELECT 'unterminated", "SELECT ?", "SELECT 1 +", "DROP TABLE nosuch",
                "INSERT INTO u VALUES (1, 1)", "SELECT * FROM t WHERE a = 'x' AND"]:
        db("query.Error", [f"q = new({dm_str(sql)})", "var/ex = q.Execute(db)"],
           "list(ex, q.Error(), q.ErrorMsg(), db.Error(), db.ErrorMsg())", table=True)
    db("query.Error", ['savedb_sql(db, "CREATE TABLE u (a UNIQUE, b)")', 'savedb_sql(db, "INSERT INTO u VALUES (1, 1)")',
                       'q = new("INSERT INTO u VALUES (1, 2)")', "var/ex = q.Execute(db)"],
       "list(ex, q.Error(), q.ErrorMsg(), db.Error(), db.ErrorMsg())")
    db("query.Error", ['savedb_sql(db, "CREATE TABLE u (a NOT NULL)")', 'q = new("INSERT INTO u VALUES (NULL)")',
                       "var/ex = q.Execute(db)"], "list(ex, q.Error(), q.ErrorMsg())")
    db("query.Error", ['q = new("SELECT 1")'], "list(q.Error(), q.ErrorMsg(), db.Error(), db.ErrorMsg())")
    db("query.Error", ['q = new("SELECT 1")', "q.Execute(db)"], "list(q.Error(), q.ErrorMsg(), db.Error(), db.ErrorMsg())")
    db("query.Error", ["q = new"], "list(q.Error(), q.ErrorMsg())")
    db("query.Error", [], "list(db.Error(), db.ErrorMsg())")
    # Does a later good query clear the error?
    db("query.Error", ['q = new("SELEC 1")', "q.Execute(db)", 'q.Add("SELECT 1")', "q.Execute(db)"],
       "list(q.Error(), q.ErrorMsg(), db.Error(), db.ErrorMsg())")
    db("query.Error", ['q = new("SELEC 1")', "q.Execute(db)", 'var/database/query/r = savedb_sql(db, "SELECT 1")'],
       "list(r.Error(), r.ErrorMsg(), db.Error(), db.ErrorMsg())")
    db("query.Error", ['q = new("SELEC 1")', "q.Execute(db)"], "list(q.Error(1), q.ErrorMsg(1))")
    # Closed / unopened databases
    db("database.Close", ["var/r = db.Close()"], "r")
    db("database.Close", ["db.Close()", 'q = new("SELECT 1")'], "list(q.Execute(db), q.NextRow(), q.Error(), q.ErrorMsg())")
    db("database.Close", ['q = new("SELECT a FROM t")', "q.Execute(db)", "db.Close()"],
       "list(q.NextRow(), q.GetRowData())", table=True)
    db("database.Close", ["db.Close()", "db.Close()"], "db.Error()")
    db("database.Close", ["db.Close()", "db.Open(@N)"], "savedb_one(db, new /database/query(\"SELECT count(*) FROM t\"))",
       table=True)
    db("database.Open", ["var/r = db.Open(@N)"], "r")
    db("database.Open", ["db.Open(@N)"], "savedb_one(db, new /database/query(\"SELECT count(*) FROM t\"))", table=True)
    db("database.Open", ['db.Open(@N + "2")', 'var/r = savedb_one(db, new /database/query("SELECT count(*) FROM t"))',
                         'db.Close()', 'fdel(@N + "2")'], "r", table=True)
    db("database.Open", ["db.Open()"], "list(db.Error(), db.ErrorMsg())")
    db("database.Open", ["db.Open(null)"], "list(db.Error(), db.ErrorMsg())")
    db("database.Open", ["db.Open(5)"], "list(db.Error(), db.ErrorMsg())")
    db("database.Open", ['var/r = db.Open("db_tmp/no_such_dir/x.db")'], "list(r, db.Error(), db.ErrorMsg())")
    db("database.New", ["var/database/D = new", 'q = new("SELECT 1")'],
       "list(q.Execute(D), q.NextRow(), q.Error(), q.ErrorMsg(), D.Error(), D.ErrorMsg())")
    db("database.New", ["var/database/D = new", "D.Open(@N)", 'q = new("SELECT count(*) FROM t")'],
       "savedb_one(D, q)", table=True)
    db("database.New", ["var/database/D = new(@N)", 'q = new("SELECT count(*) FROM t")'], "savedb_one(D, q)", table=True)
    db("database.New", ['var/database/D = new("db_tmp/no_such_dir/x.db")'], "list(D.Error(), D.ErrorMsg())")
    db("database.New", ['var/database/D = new(":memory:")', 'q = new("SELECT 1")'], "savedb_one(D, q)")
    db("database.New", ["var/database/D = new(5)"], "list(D.Error(), D.ErrorMsg())")
    db("database.New", ["var/database/D = new(file(@N))", 'q = new("SELECT count(*) FROM t")'], "savedb_one(D, q)",
       table=True)
    db("database.New", ['fdel("db_tmp/notdb.txt")', 'text2file("not a database at all, just text", "db_tmp/notdb.txt")',
                        'var/database/D = new("db_tmp/notdb.txt")', 'q = new("SELECT 1 FROM sqlite_master")',
                        "var/r = savedb_one(D, q)", "del q", "del D", 'fdel("db_tmp/notdb.txt")'], "r")
    db("database.New", [], "fexists(@N)")
    db("database.New", [], "db.type")
    db("database.New", [], "list(db.Error(), db.ErrorMsg())")
    # Persistence across reopen
    db("database.Open", ["del db", "db = new(@N)", 'q = new("SELECT * FROM t")', "q.Execute(db)"], "savedb_rows(q)",
       table=True)
    # Two queries at once
    db("query.Execute", ['q = new("SELECT a FROM t")', 'var/database/query/r = new("SELECT b FROM t")', "q.Execute(db)",
                         "r.Execute(db)", "q.NextRow()", "r.NextRow()", "r.NextRow()"],
       "list(q.GetColumn(0), r.GetColumn(0))", table=True)
    db("query.Execute", ['q = new("SELECT a FROM t")', "q.Execute(db)", "q.NextRow()",
                         'savedb_sql(db, "UPDATE t SET a = a + 100")', "q.NextRow()"], "q.GetColumn(0)", table=True)
    db("query.Execute", ['savedb_sql(db, "BEGIN")', 'savedb_sql(db, "INSERT INTO t (a) VALUES (50)")',
                         'savedb_sql(db, "ROLLBACK")', 'q = new("SELECT count(*) FROM t")'], "savedb_one(db, q)",
       table=True)
    db("query.Execute", ['savedb_sql(db, "BEGIN")', 'savedb_sql(db, "INSERT INTO t (a) VALUES (50)")',
                         'savedb_sql(db, "COMMIT")', 'q = new("SELECT count(*) FROM t")'], "savedb_one(db, q)",
       table=True)

    # ================================================================ database: Add and parameters
    PARAMS = ["1", "0", "-1", "1.5", "0.1", "1e7", "16777217", "1e30", "PINF", "NINF", "NAN", '"x"', '""',
              dm_str("it's"), dm_str('q"d'), dm_str("é日本"), dm_str("🙂"), dm_str("a\nb"), dm_str("?"),
              dm_str("'; DROP TABLE t; --"), dm_str("5"), "null", "list(1)", "list()", "new /datum", "/datum",
              "'small.dmi'", "icon('small.dmi')", "TRUE"]
    for p in PARAMS:
        db("query.Add", [f'q = new("SELECT ? AS v, typeof(?) AS t", {p}, {p})'], "savedb_one(db, q)")
        db("query.Add", ["q = new", f'q.Add("SELECT ? AS v", {p})'], "savedb_one(db, q)")
        db("query.Add", [f'q = new("INSERT INTO t (a, b, c, d, e) VALUES (?, ?, ?, ?, ?)", {p}, {p}, {p}, {p}, {p})',
                         "q.Execute(db)", 'q = new("SELECT a, typeof(a), b, typeof(b), c, typeof(c), typeof(d), e, typeof(e) FROM t WHERE rowid = 4")'],
           "savedb_one(db, q)", table=True)
        db("query.Add", [f'q = new("SELECT a FROM t WHERE b = ?", {p})'], "list(q.Execute(db), savedb_rows(q))",
           table=True)
    db("query.Add", ["q = new", 'var/r = q.Add("SELECT 1")'], "list(r, savedb_one(db, q))")
    db("query.Add", ["q = new", 'q.Add("SELECT ")', 'q.Add("1")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?, ", 1)', 'q.Add("?", 2)'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT 1")', 'q.Add(" + 1")'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT 1")', "q.Execute(db)", 'q.Add("SELECT 2")'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT 1")', "q.Execute(db)", 'q.Add("SELECT 2")', 'q.Add(" + 3")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", "q.Add()"], "savedb_one(db, q)")
    db("query.Add", ["q = new", "q.Add(null)"], "savedb_one(db, q)")
    db("query.Add", ["q = new", "q.Add(5)"], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?, ?", 1)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?", 1, 2)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT 1", 2)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT \'?\', ?", 1)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT \\"?\\", ?", 1)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", "q.Add(\"SELECT 'it''s', ?\", 1)"], "savedb_one(db, q)")
    db("query.Add", ["q = new", "q.Add(\"SELECT 'a\\\"b', ?\", 1)"], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?1, ?2", 1, 2)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT :a", 1)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ? || ?", "a", "b")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ? + ?", 1, 2)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ? + ?", "1", "2")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?? ", 1, 2)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT -?", -1)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?", 1/3)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?", 123456.789)'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add(text = "SELECT 7")'], "savedb_one(db, q)")
    db("query.Add", ["q = new", 'q.Add("SELECT ?", item1 = 4)'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT ? AS v", "x")', 'var/list/L = q.Columns()'], "L")
    db("query.Add", ['q = new(text = "SELECT 8")'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT ?", "a", "b", "c")'], "savedb_one(db, q)")
    db("query.Add", ['q = new(null, 1)'], "savedb_one(db, q)")
    db("query.Add", ['q = new(5)'], "savedb_one(db, q)")
    db("query.Add", ['q = new("SELECT a FROM t WHERE a = ?", 2)', "q.Execute(db)", 'q.Add("SELECT a FROM t WHERE a = ?", 3)',
                     "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.Add", ['q = new("SELECT a FROM t WHERE a IN (?, ?)", 1, 3)', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.Add", ['q = new("SELECT a FROM t WHERE b LIKE ?", "t%")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.Add", ['q = new("SELECT a FROM t WHERE c > ?", 2)', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.Add", ['q = new("SELECT a FROM t WHERE a = ?", "2")', "q.Execute(db)"], "savedb_rows(q)", table=True)
    db("query.Add", ['q = new("INSERT INTO t (b) VALUES (?)", "\'); DROP TABLE t; --")', "q.Execute(db)",
                     'q = new("SELECT count(*), max(b) FROM t")'], "savedb_one(db, q)", table=True)
    db("query.Add", ["var/icon/I = icon('small.dmi', \"solid\")", 'q = new("INSERT INTO t (a, d) VALUES (9, ?)", I)',
                     "q.Execute(db)", 'q = new("SELECT d FROM t WHERE a = 9")', "q.Execute(db)", "q.NextRow()",
                     "var/x = q.GetColumn(0)"], "list(isfile(x), isicon(x), istext(x), isnull(x))", table=True)
    db("query.Add", ["q = new(\"INSERT INTO t (a, d) VALUES (9, ?)\", 'small.dmi')", "q.Execute(db)",
                     'q = new("SELECT d, typeof(d), length(d) FROM t WHERE a = 9")', "q.Execute(db)", "q.NextRow()"],
       "list(isfile(q.GetColumn(0)), q.GetColumn(1), q.GetColumn(2))", table=True)
    db("query.Add", ["q = new(\"INSERT INTO t (a, d) VALUES (9, ?)\", 'small.dmi')", "q.Execute(db)",
                     'q = new("SELECT d FROM t WHERE a = 9")', "q.Execute(db)", "q.NextRow()", "var/x = q.GetColumn(0)"],
       "md5(x) == md5('small.dmi')", table=True)
    # Many rows in a loop
    db("query.Add", ['savedb_sql(db, "CREATE TABLE n (i INTEGER, s TEXT)")', "for(var/i in 1 to 25)",
                     '\tvar/database/query/w = new("INSERT INTO n VALUES (?, ?)", i, "s[i]")', "\tw.Execute(db)",
                     'q = new("SELECT sum(i), count(*), group_concat(s) FROM n")'], "savedb_one(db, q)")
