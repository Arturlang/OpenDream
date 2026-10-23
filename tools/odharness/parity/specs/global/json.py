"""json_encode / json_decode.

BYOND reference points targeted here (info.html /proc/json_encode, /proc/json_decode; stddef.dm):
- json_encode(Value, flags): plain lists and matrices become arrays, associative lists objects
  (keys need not be strings), datums become "[Value]", NaN/inf become {"__number__":"NaN"} style
  objects, BYOND text macros (\\red, \\proper...) are stripped, a list that contains itself
  encodes the nested copy as null. JSON_PRETTY_PRINT (1): spaces after ':' and ',', non-empty
  arrays/objects get a line break and tabs per item, special numbers and matrices stay inline.
  stddef.dm also defines JSON_ENCODE_STRICT 2 (undocumented).
- json_decode(JSON, flags): arrays -> lists, objects -> assoc lists; non-strict mode allows
  unquoted string keys and non-string keys, numeric keys become text ({1:2} -> list("1"=2));
  NaN and Infinity are recognised (case-sensitive); true/false -> 1/0; numbers are float32.
  JSON_STRICT (1): double-quoted strings only, no NaN/Infinity (but {"__number__":"NaN"} works),
  keys must be double-quoted strings. JSON_ALLOW_COMMENTS (2): // and /* */ comments, on by
  default.

OpenDream divergences these cases aim at (DreamProcNativeRoot.cs NativeProc_json_encode/decode):
- Decode uses System.Text.Json: no comments, no NaN/Infinity literals, no unquoted keys, no
  single quotes, no trailing commas, max depth 64; numbers via TryGetSingle (1e39 may throw);
  {"__number__":X} with a non-string X throws; any single-key object named __number__ is a
  number; a non-text argument throws "Unknown value"; the flags argument is not declared.
- Decode of objects with 2+ keys re-enumerates all properties (duplicate keys / order).
- Encode uses Utf8JsonWriter: shortest round-trip float formatting (BYOND uses its own number
  text), 2-space indentation for pretty print, any flags value other than exactly 1 is
  non-pretty, control and some non-ASCII characters escaped as \\uXXXX, depth > 20 -> null
  (not self-reference detection), keys via Stringify, vars lists skip "vars".
- OD's DMStandard has no JSON_STRICT / JSON_ALLOW_COMMENTS / JSON_ENCODE_STRICT defines.
"""
from pools import TEXT, TEXT_S, NUM, NUM_S, OTHER, ANY
from gen import dm_str

q = dm_str

HELPERS = r'''
/datum/json_thing
	var/a = 1

/obj/json_named
	name = "widget"

/obj/json_proper
	name = "\proper Bob"

/obj/json_improper
	name = "\improper apple"

/proc/json_nest(n)
	var/list/L = list()
	var/list/cur = L
	for(var/i in 1 to n)
		var/list/nxt = list()
		cur += list(nxt)
		cur = nxt
	return L

/proc/json_nest_assoc(n)
	var/list/L = list()
	var/list/cur = L
	for(var/i in 1 to n)
		var/list/nxt = list()
		cur["k"] = nxt
		cur = nxt
	return L

/proc/json_rt(x)
	return json_decode(json_encode(x))

/proc/json_dummy()
	return 1

/proc/json_depth(list/L)
	var/d = 0
	while(islist(L) && length(L))
		d++
		var/k = L[1]
		if(islist(k))
			L = k
		else
			L = L[k]
	return d
'''

# Values to encode, beyond the shared pools
ENC_VALUES = [
    # numbers
    "0", "-0", "0 * -1", "1", "-1", "0.1", "0.5", "1/3", "2/3", "-1/3", "1.5", "123.456",
    "1e6", "1e7", "1e-7", "1e-5", "0.0001", "123456789", "16777216", "16777217", "1e30", "-1e30",
    "3.4e38", "1e-38", "1e-45", "2**31", "2**24", "-2**31", "PINF", "NINF", "NAN", "-NAN",
    "100000", "999999", "1000000", "12345.6789", "0.000123", "-0.5",
    # text
    '""', '"a"', '"abc"', q('say "hi"'), q("a\\b"), q("a/b"), q("</script>"), q("<b>&amp;</b>"),
    q("line1\nline2"), q("tab\there"), "ascii2text(13)", "ascii2text(1)", "ascii2text(8)",
    "ascii2text(12)", "ascii2text(31)", "ascii2text(127)", "ascii2text(0)", q("'single'"),
    q("é"), q("Ünïcödé"), q("日本語"), q("🙂"), q("x🙂y"), q("﻿"),
    # Line/paragraph separators and NEL built at runtime (raw ones would split manifest lines)
    '"[ascii2text(8232)][ascii2text(8233)]"', "ascii2text(133)", "ascii2text(173)",
    q("�"), q(" "), q("​"), q("+&="), q("`~"),
    '"\\red red text"', '"\\proper Bob"', '"\\improper apple"', '"\\the cat"', '"\\The Cat"',
    '"a\\bold b"', '"\\icon"', '"x\\ref"', '"\\a apple"', '"\\..."', '"\\black\\bold"',
    # null and paths
    "null", "/datum", "/obj/json_named", "/list", "/proc/json_dummy", "/datum/proc/New",
    "/turf", "/icon",
    # datums and atoms
    "new /datum", "new /datum/json_thing", "new /list", "new /regex(\"a\")", "new /exception(\"boom\")",
    "matrix()", "matrix(1, 2, 3, 4, 5, 6)", "matrix(0.5, 0, 0, 0, 0.5, 0)", "matrix(PINF, NAN, 0, 0, 1, 0)",
    "vector(1, 2, 3)", "vector(1.5, -2)", "icon('test.dmi')", "'test.dmi'", "file(\"test.dmi\")",
    "locate(1, 1, 1)", "locate(/area)", "world", "generator(\"num\", 1, 2)", "image('test.dmi')",
    "new /mutable_appearance", "sound('test.dmi')",
    # lists
    "list()", "list(1)", "list(1, 2, 3)", "list(null)", "list(null, null)", "list(\"a\")",
    "list(\"a\", \"b\")", "list(\"a\" = 1)", "list(\"a\" = 1, \"b\" = 2)", "list(\"a\" = null)",
    "list(\"a\" = 1, \"b\")", "list(\"b\", \"a\" = 1)", "list(1, \"a\" = 2)", "list(\"a\" = list(1, 2))",
    "list(list())", "list(list(1), list(2, list(3)))", "list(\"x\" = list(\"y\" = list(\"z\" = 1)))",
    "list(/datum = 1)", "list(/datum)", "list(new /datum = 1)", "list(list(1) = 2)",
    "list(\"a\" = PINF)", "list(PINF, NAN, NINF)", "list(\"a\" = /datum)",
    "list(\"\" = 1)", "list(\" \" = 1)", "list(\"\\\"q\\\"\" = 1)", "list(\"é\" = \"日本\")",
    "list(\"\\red k\" = \"\\red v\")", "list(matrix())", "list(\"m\" = matrix())",
    "list(null = 1)", "list(\"a\" = 1, \"a\" = 2)", "list(\"a\", \"a\")", "list(\"a\" = 1, \"A\" = 2)",
    "list(\"1\" = 1)", "list(\"null\" = 1)", "list(\"a\" = \"\")", "list(list(\"a\" = 1), list(\"b\" = 2))",
    "list(\"k\" = new /datum)", "list(new /datum)", "list(\"a\" = list())",
    "list(\"__number__\" = \"NaN\")", "list(\"__number__\" = 5)", "list(list(), list())",
]

FLAGS = ["0", "1", "2", "3", "null", "-1", "4", "0.5", "1.5", "PINF", "NAN", '"1"', "list()",
         "JSON_PRETTY_PRINT"]

# JSON documents to decode (Python strings, turned into DM literals)
DEC_DOCS = [
    # scalars
    "1", "0", "-0", "-1", "1.5", "0.1", "1e3", "1E3", "1e+3", "1e-3", "-1.5e-3", "123456789",
    "16777217", "16777216", "3.4028235e38", "3.5e38", "1e39", "-1e39", "1e-39", "1e-46", "1e400",
    "1e-400", "2147483648", "9007199254740993", "0.30000000000000004", "1.0", "100", "00", "01",
    "-01", "+1", ".5", "5.", "-", "1e", "0x10", "1_000", "--1", "1.2.3", "-.5",
    "true", "false", "null", "True", "FALSE", "Null", "nil", "undefined",
    "NaN", "Infinity", "-Infinity", "+Infinity", "nan", "infinity", "INF", "-NaN", "Infinity1",
    '""', '"a"', '"abc"', "'a'", "a", "abc", '"unterminated', '"a"b',
    # escapes
    r'"\""', r'"\\"', r'"\/"', r'"\b"', r'"\f"', r'"\n"', r'"\r"', r'"\t"', r'"\u0041"',
    r'"\u00e9"', r'"\u00E9"', r'"\u65e5\u672c"', r'"\ud83d\ude42"', r'"a\u0042c"', r'{"\u0061":1}', r'{"\ud83d\ude42":1}', r'"\ud800"', r'"\udc00"',
    r'"\ud83d"', r'"\u0000"', r'"a\u0000b"', r'"\x41"', r'"\a"', r'"\'"', r'"\u12"', r'"\U0041"',
    r'"\u004"', '"tab\there"', '"line\nbreak"', '"é日本🙂"', '"\\u2028"', '"<\\/script>"',
    # arrays
    "[]", "[ ]", "[1]", "[1,2,3]", "[1, 2, 3]", '["a","b"]', "[null]", "[null,null]", "[true,false]",
    "[[]]", "[[1],[2,[3]]]", "[1,]", "[,1]", "[1,,2]", "[1 2]", "[", "]", "[1", "[1]]",
    '[{"a":1}]', '[{"a":1},{"a":2}]', "[NaN]", "[Infinity,-Infinity]",
    # objects
    "{}", "{ }", '{"a":1}', '{"a" : 1}', '{"a":1,"b":2}', '{"b":1,"a":2}', '{"a":null}',
    '{"a":[1,2]}', '{"a":{"b":{"c":1}}}', '{"a":1,"a":2}', '{"a":1,"b":2,"a":3}',
    '{"a":1,"b":2,"c":3,"b":4}', '{"a":1,"A":2}', '{"":1}', '{" ":1}', '{"1":2}', '{"null":1}',
    "{a:1}", "{a:1,b:2}", "{1:2}", "{1.5:2}", "{-1:2}", "{null:1}", "{true:1}", "{false:1}",
    "{'a':1}", "{\"a\":'b'}", "{[1]:2}", "{{}:1}", '{"a":1,}', '{"a"}', '{"a":}', '{:1}', '{"a" 1}',
    '{"a":1 "b":2}', "{", "}", '{"a":1', '{"a":1}}', '{"a":NaN}', '{"é":"日本"}',
    '{"a":true,"b":false}', '{"__number__":"NaN"}', '{"__number__":"Infinity"}',
    '{"__number__":"-Infinity"}', '{"__number__":"inf"}', '{"__number__":"1.5"}',
    '{"__number__":"abc"}', '{"__number__":5}', '{"__number__":null}', '{"__number__":"NaN","x":1}',
    '{"x":1,"__number__":"NaN"}', '{"__NUMBER__":"NaN"}', '[{"__number__":"Infinity"}]',
    '{"a":{"__number__":"NaN"}}', '{"__number__":""}',
    # whitespace and garbage
    "", " ", "\t", "\n", " 1 ", "\t[1]\n", "\r\n{\"a\" :\r\n 1}\r\n", "1 2", "[1]x", "[1] [2]",
    "{} {}", "﻿1", " 1", "1;", "1,", "x", "/datum", "list(1)",
    # comments
    "// c\n1", "1 // c", "/* c */ 1", "[1, /* c */ 2]", '{"a": 1 // c\n}', "/* unclosed 1",
    "[1, // c\n 2]", "# c\n1", "/**/[]", '{"a"/**/:1}', '"/* not a comment */"', '"// not"',
]

DEC_FLAGS = ["0", "1", "2", "3", "null", "4", "-1", "1.5", '"1"']


def build(s):
    s.dm(HELPERS)
    s.dm(HELPERS2)
    build_gaps(s)

    # ---- json_encode: generic sweeps ------------------------------------------------------------
    s.sweep("json_encode", [ANY + TEXT + NUM], min_args=1)
    s.sweep("json_encode", [ANY, ["0", "1", "2", "3", "null", '"1"', "list()"]], min_args=2)
    for v in ENC_VALUES:
        s.call("json_encode", v)
    # Pretty print and the undocumented strict flag over the structured values
    for v in ENC_VALUES:
        if v.startswith("list(") or v.startswith("matrix") or v in ("PINF", "NINF", "NAN", '"\\red red text"',
                                                                    '"a"', "1/3", "1e7", "null"):
            s.call("json_encode", v, "JSON_PRETTY_PRINT")
            s.call("json_encode", v, "2")
            s.call("json_encode", v, "3")
    # Flag values on a fixed nested value
    for f in FLAGS:
        s.call("json_encode", 'list("a" = list(1, 2), "b" = list())', f)
        s.call("json_encode", "list(PINF, list(1))", f)
    # Strict-flag names (OD lacks the defines)
    s.call("json_encode", "list(1, PINF)", "JSON_ENCODE_STRICT")
    s.call("json_encode", "list(\"a\" = NAN)", "JSON_ENCODE_STRICT")
    s.call("json_encode", "list(/datum = 1)", "JSON_ENCODE_STRICT")
    s.body("json_encode", ["var/list/L = list()", "L[ascii2text(1)] = 2"], "json_encode(L, 2)")
    s.call("json_encode", "list(\"a\" = 1)", "JSON_PRETTY_PRINT | JSON_ENCODE_STRICT")
    # Compile-time rejections seen on BYOND, one case each
    s.case("json_encode", 'json_encode("\\an")')
    s.case("json_encode", 'json_encode("\\s s")')
    s.case("json_encode", 'json_encode("\\th")')
    s.case("json_encode", 'json_encode("1\\th")')
    s.case("json_encode", 'json_encode("\\he")')
    s.case("json_encode", 'json_encode("\\hers")')
    s.case("json_encode", "json_encode(/datum/proc/New)")
    s.case("json_encode", "json_encode(/datum/json_thing/proc/New)")
    s.case("json_encode", "json_encode(/datum/verb)")
    s.body("json_encode", ['var/O = parity_track(new /obj(locate(1, 1, 1)))', 'var/obj/P = O'],
           'json_encode("\\he [P]")')
    s.case("json_encode", "json_encode(/world)")
    s.case("json_encode", "json_encode(list(1.5 = 2))")
    s.body("json_encode", ["var/list/L = list()", "L[1.5] = 2"], "json_encode(L)")
    # Arity and named arguments
    s.case("json_encode", "json_encode()")
    s.case("json_encode", "json_encode(1, 0, 0)")
    s.case("json_encode", "json_encode(Value = list(1, 2))")
    s.case("json_encode", "json_encode(Value = list(1, 2), flags = 1)")
    s.case("json_encode", "json_encode(flags = 1, Value = list(\"a\" = 1))")
    s.case("json_encode", 'call("json_encode")(list(1, 2))')
    s.case("json_encode", 'call("json_encode")(list(1, 2), 1)')
    s.case("json_encode", "json_encode(arglist(list(list(1, 2), 1)))")

    # Atoms and datums: "[Value]"
    for t in ["/obj", "/obj/json_named", "/obj/json_proper", "/obj/json_improper", "/mob"]:
        s.body("json_encode", [f"var/O = parity_track(new {t}(locate(1, 1, 1)))"], "json_encode(O)")
        s.body("json_encode", [f"var/O = parity_track(new {t}(locate(1, 1, 1)))"], "json_encode(list(O))")
        s.body("json_encode", [f"var/O = parity_track(new {t}(locate(1, 1, 1)))", "var/list/L = list()",
                               "L[O] = 1"], "json_encode(L)")
        s.body("json_encode", [f"var/O = parity_track(new {t}(locate(1, 1, 1)))"], 'json_encode(list("k" = O))')
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))', 'O.name = "\\red Red"'],
           "json_encode(O)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))', 'O.name = ""'], "json_encode(O)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))', 'O.name = null'], "json_encode(O)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))', 'O.name = "a\\"b"'], "json_encode(O)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))'], "json_encode(O.contents)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))',
                           'var/obj/I = parity_track(new /obj/json_named(O))', 'I.name = "inner"'],
           "json_encode(O.contents)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))'], "json_encode(O.overlays)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))'], "json_encode(O.verbs)")
    s.body("json_encode", ['var/obj/O = parity_track(new /obj(locate(1, 1, 1)))', 'O.filters = filter(type = "blur", size = 1)'],
           "json_encode(O.filters)")
    s.body("json_encode", ['var/turf/T = locate(1, 1, 1)'], "json_encode(T.contents)")
    # Datum vars lists ("vars" skipped)
    s.body("json_encode", ["var/datum/json_thing/D = new"], "json_encode(D.vars)")
    s.body("json_encode", ["var/datum/json_thing/D = new"], "json_decode(json_encode(D.vars))")
    s.body("json_encode", ["var/datum/json_thing/D = new"], 'length(json_decode(json_encode(D.vars)))')
    s.body("json_encode", ["var/datum/json_thing/D = new", "var/list/L = json_decode(json_encode(D.vars))"],
           'list(L["a"], L["type"], L["parent_type"], ("vars" in L), L["tag"])')
    s.body("json_encode", ["var/datum/json_thing/D = new", 'D.tag = "json_tag_x"'], "json_encode(D)")
    # Special lists
    s.case("json_encode", "json_encode(alist(\"a\" = 1, 2 = 3))")
    s.case("json_encode", "json_encode(alist())")
    s.case("json_encode", 'json_args(1, "x")')
    s.case("json_encode", "json_args()")
    s.case("json_encode", "json_args(list(1), list(\"k\" = 2))")
    s.body("json_encode", ['var/list/L = list(1, 2, 3)', 'L.len = 5'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list("a" = 1, "b" = 2)', 'L -= "a"'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list("a" = 1, "b" = 2)', 'L["a"] = null'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list(1, 2)', 'L[1] = list("x" = 1)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list("a", "b")', 'L["b"] = 2'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list("a" = 1)', 'L += 5'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'L[new /datum/json_thing] = 2'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'L[matrix()] = 2'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'L[/proc/json_dummy] = 2'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', "L['test.dmi'] = 2"], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'L[vector(1, 2)] = 2'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'L["k"] = PINF'], "json_encode(L, 1)")
    # Self-reference vs depth
    s.body("json_encode", ['var/list/L = list(1)', 'L += list(L)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list(1)', 'L["self"] = L'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list(1)', 'var/list/M = list(L)', 'L += list(M)'], "json_encode(L)")
    s.body("json_encode", ['var/list/A = list(1)', 'var/list/L = list(A, A)'], "json_encode(L)")
    s.body("json_encode", ['var/list/A = list("x" = 1)', 'var/list/L = list("p" = A, "q" = A)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list(1)', 'L += list(L)'], "json_encode(L, 1)")
    for n in [1, 5, 15, 18, 19, 20, 21, 22, 25, 30, 64, 100]:
        s.case("json_encode", f"json_encode(json_nest({n}))")
    for n in [18, 19, 20, 21, 30]:
        s.case("json_encode", f"json_encode(json_nest_assoc({n}))")
        s.case("json_encode", f"length(json_encode(json_nest({n}), 1))")
    # Big structures
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 1 to 300) L += i'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 1 to 200) L["k[i]"] = i'],
           "length(json_encode(L))")
    s.body("json_encode", ['var/t = ""', 'for(var/i in 1 to 2000) t += "ab\\""'], "length(json_encode(t))")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 0 to 31) L += ascii2text(i)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 127 to 160) L += ascii2text(i)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 0 to 12) L += 10 ** i'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 0 to 12) L += 10 ** -i'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 1 to 12) L += 1 / (i + 2)'], "json_encode(L)")
    s.body("json_encode", ['var/list/L = list()', 'for(var/i in 20 to 26) L += 2 ** i + 1'], "json_encode(L)")
    # Argument unchanged afterwards
    s.body("json_encode", ['var/list/L = list("b" = 1, "a" = list(2))', 'var/r = json_encode(L)'], "list(r, L)")
    s.body("json_encode", ['var/t = "\\red x"', 'var/r = json_encode(t)'], "list(r, t, length(t))")

    # ---- json_decode: generic sweeps ------------------------------------------------------------
    s.sweep("json_decode", [TEXT + OTHER + NUM_S], min_args=1)
    s.sweep("json_decode", [TEXT_S + OTHER[:4] + ['"1"', '"\\[1\\]"', '"{a:1}"', '"NaN"'],
                            ["0", "1", "2", "3", "null"]], min_args=2)
    for d in DEC_DOCS:
        s.call("json_decode", q(d))
    # Flags over a set of documents that differ between strict and non-strict / comments
    FLAG_DOCS = ["1", "NaN", "Infinity", "-Infinity", "{a:1}", "{1:2}", "{null:1}", "'a'", "{'a':1}",
                 '{"__number__":"NaN"}', '{"__number__":"Infinity"}', "// c\n1", "/* c */ [1]",
                 '{"a":1 /* c */}', '"x"', "[1,2]", '{"a":1,"a":2}', "[1,]", "true", "abc",
                 '{"a":"b"}', "1e39", "[NaN]", '{"a":{b:1}}']
    for d in FLAG_DOCS:
        for f in DEC_FLAGS:
            s.call("json_decode", q(d), f)
    for d in ["NaN", "{a:1}"]:
        s.call("json_decode", q(d), "JSON_STRICT")
        s.call("json_decode", q(d), "JSON_ALLOW_COMMENTS")
        s.call("json_decode", q(d), "JSON_STRICT | JSON_ALLOW_COMMENTS")
    # Arity and named arguments
    s.case("json_decode", "json_decode()")
    s.case("json_decode", 'json_decode("1", 0, 0)')
    s.case("json_decode", 'json_decode(JSON = "\\[1\\]")')
    s.case("json_decode", 'json_decode(JSON = "{a:1}", flags = 1)')
    s.case("json_decode", 'json_decode(flags = 0, JSON = "{a:1}")')
    s.case("json_decode", 'call("json_decode")("\\[1, 2\\]")')
    s.case("json_decode", 'json_decode(arglist(list("\\[1\\]")))')
    # Wrong types
    for w in ["null", "1", "0", "list()", 'list("\\[1\\]")', "/datum", "new /datum", "PINF",
              "'test.dmi'", "file(\"test.dmi\")", "matrix()", "vector(1, 2)"]:
        s.call("json_decode", w)
    # Results are real, mutable lists
    s.body("json_decode", ['var/list/L = json_decode("\\[1, 2\\]")', "L += 3"], "L")
    s.body("json_decode", ['var/list/L = json_decode("{\\"a\\":1}")', 'L["b"] = 2'], "L")
    s.body("json_decode", ['var/list/L = json_decode("{\\"a\\":1}")'], 'list(L["a"], L[1], L.len, ("a" in L))')
    s.body("json_decode", ['var/list/L = json_decode("{\\"a\\":1,\\"b\\":2,\\"a\\":3}")'],
           'list(L.len, L[1], L[2], L["a"], L["b"])')
    s.body("json_decode", ['var/list/L = json_decode("{\\"a\\":1,\\"b\\":2,\\"c\\":3,\\"b\\":4,\\"d\\":5}")'],
           'list(L.len, L[1], L[2], L[3], L[4], L["b"])')
    s.body("json_decode", ['var/list/L = json_decode("{1:2}")'], 'list(L.len, L[1], istext(L[1]), L["1"])')
    s.body("json_decode", ['var/list/L = json_decode("{null:2}")'], 'list(L.len, L[1], isnull(L[1]), istext(L[1]))')
    s.body("json_decode", ['var/list/L = json_decode("{true:2}")'], 'list(L.len, L[1], isnum(L[1]))')
    s.body("json_decode", ['var/list/L = json_decode("\\[\\[1\\], \\[1\\]\\]")'], 'list(L.len, L[1] == L[2], L[1] ~= L[2])')
    s.body("json_decode", ['var/n = json_decode("1.5")'], 'list(n, isnum(n), n * 2)')
    s.body("json_decode", ['var/n = json_decode("-0")'], 'list(n, "[n]", num2text(n, 12))')
    s.body("json_decode", ['var/n = json_decode("{\\"__number__\\":\\"NaN\\"}")'], 'list(n != n, isnum(n))')
    s.body("json_decode", ['var/n = json_decode("NaN")'], 'list(n != n, isnum(n))')
    s.body("json_decode", ['var/n = json_decode("1e39")'], 'list(n, isnum(n), n == PINF)')
    s.body("json_decode", ['var/n = json_decode("16777217")'], 'list(n, n == 16777216, num2text(n, 12))')
    s.body("json_decode", ['var/n = json_decode("0.1")'], 'list(num2text(n, 12), n == 0.1)')
    s.body("json_decode", ['var/n = json_decode("1e-46")'], 'list(n, n == 0)')
    s.body("json_decode", ['var/t = json_decode("\\"\\\\u00e9\\"")'], 'list(t, length(t), length_char(t), text2ascii(t))')
    s.body("json_decode", ['var/t = json_decode("\\"\\\\ud83d\\\\ude42\\"")'], 'list(t, length(t), length_char(t), text2ascii_char(t))')
    s.body("json_decode", ['var/t = json_decode("\\"\\\\ud800\\"")'], 'list(length(t), length_char(t))')
    s.body("json_decode", ['var/t = json_decode("\\"a\\\\u0000b\\"")'], 'list(length(t), length_char(t), text2ascii(t, 2))')
    # Deep nesting: System.Text.Json has a max depth of 64
    for n in [10, 63, 64, 65, 100, 200]:
        s.body("json_decode", ['var/t = ""', f'for(var/i in 1 to {n}) t += "\\["', f'for(var/i in 1 to {n}) t += "\\]"'],
               "json_depth(json_decode(t))")
        s.body("json_decode", ['var/t = ""', f'for(var/i in 1 to {n}) t += "{{\\"k\\":"', 't += "1"',
                               f'for(var/i in 1 to {n}) t += "}}"'], "json_depth(json_decode(t))")
    # Big documents
    s.body("json_decode", ['var/t = "\\["', 'for(var/i in 1 to 500) t += "[i],"', 't += "0\\]"'],
           'length(json_decode(t))')
    s.body("json_decode", ['var/t = "{"', 'for(var/i in 1 to 300) t += "\\"k[i % 50]\\":[i],"', 't += "\\"z\\":0}"'],
           'json_decode(t)')
    s.body("json_decode", ['var/t = ""', 'for(var/i in 1 to 3000) t += "a"'], 'length(json_decode("\\"[t]\\""))')

    # ---- round trips --------------------------------------------------------------------------
    for v in ENC_VALUES:
        s.case("json_rt", f"json_rt({v})")
    for v in ENC_VALUES:
        if v.startswith("list("):
            s.case("json_rt", f"json_encode(json_rt({v}))")
            s.case("json_rt", f"json_decode(json_encode({v}, 1))")
    for d in ['{"a":1,"b":[1,2,{"c":null}]}', "[1.5,-2,0.1,1e-7,123456789]", '{"x":"\\u00e9\\n"}',
              '{"b":1,"a":2}', "[]", "{}", '[[],{}]', '{"a":{"__number__":"NaN"}}', "{a:1}", "[NaN]",
              '"\\ud83d\\ude42"', '"\\/"', "1e7", "0.3333333", "{1:2}", '{"k":true}']:
        s.case("json_rt", f"json_encode(json_decode({q(d)}))")
        s.case("json_rt", f"json_encode(json_decode({q(d)}), 1)")


# ---- second pass: gaps found by review --------------------------------------------------------
BS = chr(92)
U = BS + "u"   # a JSON backslash-u escape, built at runtime so no tool decodes it in this file
DQ = chr(34)

HELPERS2 = """
/datum/json_named_datum
	var/name = "nm"

/datum/json_strop
	var/a = 1

/datum/json_strop/proc/operator\"\"()
	return "custom"

/proc/json_args(a, b)
	return json_encode(args)

/proc/json_sav(flags, rt)
	fdel("json_fixed.sav")
	var/savefile/S = new("json_fixed.sav")
	if(rt)
		. = json_rt(S)
	else
		. = json_encode(S, flags)
	del S
	fdel("json_fixed.sav")

/proc/json_dec_key(t)
	var/list/L = json_decode(t)
	if(!islist(L) || !length(L))
		return L
	var/k = L[1]
	return list(L.len, k, istext(k), isnum(k), L[k])
"""


def build_gaps(s):
    # Savefile with a fixed name (an unnamed one may print a temp file name)
    for f in ["0", "1"]:
        s.case("json_encode", f"json_sav({f}, 0)")
    s.case("json_rt", "json_sav(0, 1)")

    # Lone surrogates reaching the encoder (text and key path)
    for esc in ["d800", "dc00", "d83d"]:
        lit = q(DQ + U + esc + DQ)
        s.case("json_encode", f"json_encode(json_decode({lit}))")
        s.case("json_encode", f"json_encode(json_decode({lit}), 1)")
        s.body("json_encode", [f"var/k = json_decode({lit})", "var/list/L = list()", "L[k] = 1"], "json_encode(L)")
        s.case("json_rt", f"json_rt(json_decode({lit}))")
        s.body("json_rt", [f"var/t = json_rt(json_decode({lit}))"],
               f"list(length(t), length_char(t), t == json_decode({lit}))")
        s.body("json_rt", [f"var/k = json_decode({lit})", "var/list/L = list()", "L[k] = 1"], "json_rt(L)")
    s.body("json_encode", [f"var/k = json_decode({q(DQ + U + 'd800' + DQ)})", 'var/t = "a[k]b"'], "json_encode(t)")

    # Unassigned / private use / noncharacter / recent code points
    for cp in [888, 57344, 63743, 65534, 65535, 64976, 65007, 129768, 917505, 983040, 1114109, 768, 8203, 65279]:
        s.case("json_encode", f"json_encode(ascii2text({cp}))")
        s.body("json_encode", ["var/list/L = list()", f"L[ascii2text({cp})] = {cp}"], "json_encode(L)")
        s.case("json_rt", f"text2ascii_char(json_rt(ascii2text({cp})))")

    # Datums with a name var / operator""
    for t in ["/datum/json_named_datum", "/datum/json_strop"]:
        s.body("json_encode", [f"var/D = new {t}"], "json_encode(D)")
        s.body("json_encode", [f"var/D = new {t}"], "json_encode(list(D))")
        s.body("json_encode", [f"var/D = new {t}", "var/list/L = list()", "L[D] = 1"], "json_encode(L)")
        s.body("json_encode", [f"var/D = new {t}"], 'json_encode(list("k" = D), 1)')
        s.body("json_encode", [f"var/D = new {t}"], 'list("[D]", json_rt(D))')
    s.body("json_encode", ["var/datum/json_named_datum/D = new", 'D.name = "\\proper Zed"'], "json_encode(D)")
    s.body("json_encode", ["var/datum/json_named_datum/D = new", "D.name = null"], "json_encode(D)")
    s.body("json_encode", ["var/datum/json_named_datum/D = new", "D.name = 5"], "json_encode(D)")
    s.body("json_encode", ["var/datum/json_named_datum/D = new", 'D.name = "\\red R"'], "json_encode(D)")

    # alist key kinds
    for kv in ["1.5 = 2", "-0 = 1", "1e30 = 1", "new /datum = 1", '"x" = alist(1 = 2)', '1 = 2, "1" = 3',
               "/datum = 1", "null = 1", "0.1 = 1", "16777217 = 1", "1e-7 = 1"]:
        s.case("json_encode", f"json_encode(alist({kv}))")
    for k in ["PINF", "NINF", "NAN", "1/3", "-0", "2**31"]:
        s.body("json_encode", ["var/alist/A = alist()", f"A[{k}] = 1"], "json_encode(A)")
    s.body("json_encode", ["var/alist/A = alist()", "A[matrix()] = 1"], "json_encode(A)")
    s.body("json_encode", ["var/alist/A = alist()", "A[new /datum/json_strop] = 1"], "json_encode(A)")
    for f in ["1", "2", "3"]:
        s.case("json_encode", f'json_encode(alist("a" = 1, 2 = 3), {f})')
        s.case("json_encode", f'json_encode(alist("x" = alist(1 = 2), "y" = list(1)), {f})')
    s.case("json_rt", 'json_rt(alist("a" = 1, 2 = 3))')
    s.case("json_rt", 'json_rt(alist("x" = alist(1 = 2)))')

    # Key collisions after stringifying
    s.body("json_encode", ["var/list/L = list()", "L[/datum] = 1", 'L["/datum"] = 2'], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", 'L["/datum"] = 2', "L[/datum] = 1"], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", "L[new /datum] = 1", 'L["/datum"] = 2'], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", "L[new /datum] = 1", "L[new /datum] = 2"], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", "L[new /datum] = 1", "L[/datum] = 2"], "json_rt(L)")
    s.body("json_encode", ["var/list/L = list()", "L[new /datum/json_strop] = 1", 'L["custom"] = 2'], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", "L[new /datum/json_named_datum] = 1", 'L["nm"] = 2'], "json_encode(L)")
    s.body("json_encode", ["var/list/L = list()", "L[/datum] = 1", 'L["/datum"] = 2'], "json_encode(L, 1)")

    # Unquoted keys: token shapes
    for d in ["{a_b:1}", "{a1:1}", "{_a:1}", "{1a:1}", "{a-b:1}", "{$a:1}", "{é:1}", "{a b:1}",
              '{"a":1, b:2}', '{a:1, "b":2}', "{NaN:1}", "{Infinity:1}", "{undefined:1}", "{-Infinity:1}",
              "{a.b:1}", "{日本:1}", "{a :1}", "{ a:1}", "{a\t:1}", "{TRUE:1}"]:
        for f in ["0", "1"]:
            s.call("json_decode", q(d), f)
    for d in ["{a_b:1}", "{1a:1}", "{a b:1}", "{NaN:1}", "{undefined:1}", "{é:1}"]:
        s.case("json_decode", f"json_dec_key({q(d)})")

    # Number keys: their text form
    for d in ["{1e3:2}", "{0.1:2}", "{1e30:2}", "{1e-7:2}", "{16777217:2}", "{-0:2}", "{1.0:2}", "{01:2}",
              "{1E3:2}", "{123456789:2}", "{0.30000001:2}", "{1e39:2}", "{-1.5e-3:2}", "{.5:2}"]:
        s.case("json_decode", f"json_dec_key({q(d)})")

    # Unquoted / single-quoted values
    for d in ["[abc]", '{"a":abc}', "{a:b}", "['a','b']", "'a" + BS + "'b'", "'a\"b'", "\"a'b\"", "{'a':'b'}",
              "['']", "''", "[a b]", '{"a":b c}', "'" + U + "0041'"]:
        for f in ["0", "1"]:
            s.call("json_decode", q(d), f)

    # Comment edge forms
    for d in ["// c", "/* c */", "/* /* */ */ 1", '{"a" /* c */ : 1}', "1/**/", "// c\r1", "1// c",
              "/* c */\n", "[1/**/]", "/*/ 1", "/**/1/**/", "[1,/**/]"]:
        for f in ["0", "1", "2", "3"]:
            s.call("json_decode", q(d), f)

    # {"__number__": "..."} string variants
    for v in ["nan", "+Infinity", "∞", "-∞", "1e39", "0x10", " NaN ", "1,5", "-NaN", "-0", "1e-50", " 1",
              "1.5e3", "Inf", "infinity"]:
        d = '{"__number__":"' + v + '"}'
        for f in ["0", "1"]:
            s.call("json_decode", q(d), f)
    s.body("json_decode", [f"var/n = json_decode({q('{' + DQ + '__number__' + DQ + ':' + DQ + '-0' + DQ + '}')})"],
           'list(n, "[n]", isnum(n))')

    # Non-JSON whitespace and raw control characters
    for d in ["\x0c1", "1\x0c", "[1,\x0c2]", "\x0b1", "[1,\x0b2]", "1\x00", "\x001", "[1\x00,2]", "1\x002",
              '"a\x01b"', '"a\x00b"', '"a\x1fb"', '"a\x7fb"', '{"a\x01":1}', "\x1c1", chr(133) + "1"]:
        for f in ["0", "1"]:
            s.call("json_decode", q(d), f)
    s.body("json_decode", [f"var/t = json_decode({q(DQ + 'a' + chr(1) + 'b' + DQ)})"],
           "list(length(t), text2ascii(t, 2))")

    # Number precision through containers
    s.case("json_rt", "json_rt(list(1/3, 2/3, 0.1, 1e-7, 16777217, 3.4e38, 1e-38))")
    s.case("json_rt", "json_encode(json_rt(list(1/3, 2/3, 0.1, 1e-7, 16777217, 3.4e38, 1e-38)))")
    s.case("json_encode", "json_encode(list(1/3, 2/3, 0.1, 1e-7, 16777217, 3.4e38, 1e-38))")
    s.case("json_rt", f"json_encode(json_decode({q('[0.1,0.2,0.30000001,1.17549435e-38,3.4028234e38]')}))")
    s.case("json_rt", f"json_encode(json_decode({q('[1e-45,1.4e-45,7e-46,123456.789,0.000001,1e21,1e-6,1e-5]')}))")
    s.case("json_rt", f"json_encode(json_decode({q('{' + DQ + 'a' + DQ + ':[0.1,{' + DQ + 'b' + DQ + ':2.5e-8}]}')}))")
    s.body("json_rt", ["var/list/L = json_rt(list(1/3, 0.1, 16777217))"],
           "list(L[1] == 1/3, L[2] == 0.1, L[3] == 16777217)")

    # Pretty print on nested mixed structures
    for f in ["1", "3"]:
        s.case("json_encode", f'json_encode(list("a" = list("b" = list(1, list())), "c" = list(PINF, matrix())), {f})')
        s.case("json_encode", f'json_encode(list(list("x" = 1), list()), {f})')
        s.case("json_encode", f'json_encode(list("a" = list("b" = list("c" = list("d" = list(1, 2))))), {f})')
        s.case("json_encode", f'json_encode(list(list(list(list(NAN)))), {f})')
        s.case("json_encode", f'json_encode(list("m" = list(matrix(1, 2, 3, 4, 5, 6), "s"), "e" = list("z" = list())), {f})')
