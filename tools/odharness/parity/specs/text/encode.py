"""html_encode, html_decode, url_encode, url_decode, md5, sha1, list2params, params2list."""
from pools import TEXT, TEXT_S, NUM_S, OTHER
from gen import dm_str

S = dm_str

# html_encode inputs: every special, URLs (documented: & inside a URL is left alone), old-style codes
HTML_PLAIN = [S(t) for t in [
    "<", ">", "&", "\"", "'", "<>&\"'", "a&b", "&amp;", "&lt;", "&#39;", "&nbsp;", "a & b", "&&",
    "<script>alert('x')</script>", "<a href=\"x?a=1&b=2\">l</a>", "\u00a0", "\u00a9", "\u00ff", "\u2014",
    "line1\nline2", "a\tb", "/", "=", "`", "\u0080", "\u200b", "\ufeff", "\U0001F642&\U0001F642",
    "see http://a.com/?a=1&b=2 now", "http://a.com/?a=1&b=2", "https://x.y/<z>&q", "www.foo.com?a=1&b=2",
    "byond://?src=1&b=2", "mailto:a@b.c?x=1&y=2", "ftp://h/a&b", "http://", "x http:/a&b",
    "(http://a.b/?c&d)", "\"http://a.b/?c&d\"", "<http://a.b/?c&d>", "HTTP://A.B/?C&D", "file:///c:/a&b",
]]
# Raw DM source: old-style text macros and control characters
HTML_RAW = [
    '"\\red red text"', '"\\blue x"', '"a\\improper b"', '"\\the cat"', '"\\proper x"', '"\\black <b>"',
    '"x[ascii2text(0)]y"', '"[ascii2text(1)]"', '"[ascii2text(127)]"', '"[ascii2text(255)]"',
    '"[ascii2text(13)][ascii2text(10)]"', '"\\n"', '"\\..."',
]

# html_decode inputs: named, numeric, hex, malformed, nested, case
HTML_ENC = [S(t) for t in [
    "&amp;", "&lt;", "&gt;", "&quot;", "&#39;", "&apos;", "&nbsp;", "&#65;", "&#x41;", "&#X41;",
    "&#065;", "&#x1F642;", "&#128578;", "&copy;", "&eacute;", "&Eacute;", "&euro;", "&hellip;", "&mdash;",
    "&amp", "&lt", "&#;", "&#x;", "&#xZZ;", "&#abc;", "&unknown;", "&;", "&", "&&", "&amp;amp;",
    "&amp;lt;", "&#0;", "&#1114112;", "&#xD800;", "&#9999999999;", "&LT;", "&Amp;", "&AMP;", "&lt;b&gt;",
    "<br>", "<b>x</b>", "a&ltb", "&#x41&#x42", "&#65&#66;", "&nbsp", "&lt;&lt;&gt;&gt;", "&#10;",
    "&#13;&#10;", "&#9;", "&#38;", "&#x26;amp;", "x&y;z", "&lt;é&gt;", "&#233;", "&#xe9;",
]]

# url_encode inputs: every reserved / unreserved class, multibyte, already-encoded, full URLs
URL_PLAIN = [S(t) for t in [
    " ", "+", "%", "&", "=", "?", "/", ":", "#", "~", "-", "_", ".", "!", "*", "'", "(", ")", "@",
    "$", ",", ";", "[", "]", "{", "}", "|", "^", "`", "\\", "<", ">", "\"", "a b", "a+b", "100%",
    "%20", "%2", "%zz", "a%20b c", "é", "日", "\U0001F642", "\u00a0", "\u00ff", "\n", "\t", "\r\n",
    "http://a.b/c d?e=f g&h=i#frag", "http://x.com/%zz", "http://x.com/a%20b", "http://user:pw@h:80/p;q?r=s",
    "https://h/ü?ü=ü", "byond://?src=[0x1]&a=b", "/rel/path?x=<y>", "?a=1&b=2", "already%20encoded+x",
    "javascript:alert(\"x\")", "AZaz09",
]] + ['"x[ascii2text(0)]y"', '"[ascii2text(1)]"', '"[ascii2text(127)]"', '"[ascii2text(128)]"']
URL_FMT = ["0", "1", "2", "-1", "0.5", "null", S("1"), S(""), "PINF", "NAN", "list()"]

# url_decode inputs
URL_ENC = [S(t) for t in [
    "%20", "+", "%2B", "%2b", "%", "%2", "%zz", "%%", "%%20", "%2%20", "%C3%A9", "%c3%a9", "%C3",
    "%C3%28", "%FF", "%F0%9F%99%82", "%F0%9F", "%00", "a%00b", "%E6%97%A5", "%u0041", "%u00e9",
    "%0D%0A", "%0a", "%41%42", "a+b+c", "a%2Bb+c", "100%", "%3d%26%3b", "%25", "%2525", "%7E",
    "%G1", "%1G", "% 20", "é%20日", "%E9", "%80", "%EF%BB%BF", "+%20+", "a=b&c=d",
    "http%3A%2F%2Fa.b%2F%3Fc%3Dd", "%5B0x1%5D", "%22%27%3C%3E",
]]

# params2list inputs
PARAMS = [S(t) for t in [
    "a=1&b=2", "a=1;b=2", "a=1;b=2&c=3", "a", "a&b", "a;b", "a=", "a=&b=", "=1", "=", "==", "&", ";",
    "&&", ";;", "&a", "a&", "a=1&&b=2", "a=1;;b=2", "a=1&a=2", "a=1;a=2;a=3", "a&a", "a;a;a", "a=1&a",
    "a&a=1", "a=1&b=2&a=3", "a=&a=", "a=b=c", "a==b", "a%3db=c%26d", "a%3Db=c%3Bd", "a+b=c+d",
    "a%20b=c%20d", "a%2bb=c%2Bd", "%41=%42", "1=2", "1", "1&2", "1.5=-0.5", "a=1e3", "A=1&a=2",
    "key=value1;key=value2", " a = b ", "é=日本", "%C3%A9=%F0%9F%99%82", "?a=1", "a=1#x", "a=%",
    "a=%zz", "a=%0d%0a", "a=[0x2000000]", "a=%5b0x2000000%5d", "src=\\ref", "a=1&b", "b=2&a=1",
    "x=1&y=2&z=3&x=4&y=5", "list=a&list=b&list=c", "a=1;a=1", "a=%00", "a=+", "+=+",
]]

# list2params inputs (lists), as DM source
LISTS = [
    'list()', 'list("a")', 'list("a", "b")', 'list("a" = 1)', 'list("a" = "b", "c" = "d")',
    'list(1, 2, 3)', 'list(1.5, -0.5, 1e7)', 'list("a" = null)', 'list(null)', 'list("a" = list(1, 2))',
    'list("a" = list("x" = 1))', 'list(list(1))', 'list("a" = /datum)', 'list(/datum)',
    'list(/datum = 1)', 'list("a b" = "c d")', 'list("a&b" = "c=d")', 'list("a;b" = "c+d")',
    'list("%" = "%20")', 'list("é" = "🙂")', 'list("x" = 1.5)', 'list("x" = 1e7)',
    'list("x" = 16777217)', 'list("x" = -0.0001)', 'list("x" = PINF)', 'list("x" = NAN)',
    'list("x" = "")', 'list("" = "x")', 'list("")', 'list("x" = list())', 'list("a" = 1, "a" = 2)',
    'list("a", "a")', 'list("a", "b" = 2, "c")', 'list("k" = "<v>&\\"q\\"")',
    'list("line" = "a\\nb")', 'list("t" = "a\\tb")', 'list("a" = 0)', 'list("a" = -1)',
    'list("/" = "?")', 'list("~-_.!*\'()" = "@$,:")', 'list("a" = "x" + "y")',
    'list("\\[x\\]" = "\\[y\\]")',
    'alist("a" = 1, "b" = "c")', 'alist(1 = "a")',
]

NONLIST = TEXT_S + NUM_S + ["null", "/datum", "new /datum", "PINF", "NAN"]

# Long input strings built in a body; result trimmed so the printed line stays small
LONG_SEED = ["a b&", "<&>", "é日🙂", "%20+", "x=1&", "a"]


def long_case(s, proc, seed, n, call, tag=""):
    lines = ['var/t = ""', f'for(var/i in 1 to {n})', f'\tt += {S(seed)}', f'var/r = {call}',
             'var/rr = istext(r) ? "[length(r)]:[copytext(r, 1, 41)]|[copytext(r, -40)]" : r']
    s.body(proc, lines, "rr", f"{proc} long {seed!r} x{n} {tag}")


def ref_masked(s, proc, setup, call):
    """A case whose result contains a datum ref: replace the ref (raw or %-encoded) with REF."""
    s.body(proc, setup + [
        f"var/r = {call}",
        'var/rf = "\\ref[D]"',
        "if(istext(r))",
        '\tr = replacetext(r, rf, "REF")',
        '\tr = replacetext(r, "%5b" + copytext(rf, 2, -1) + "%5d", "REF")',
        '\tr = replacetext(r, copytext(rf, 2, -1), "REF")',
    ], "r", f"{proc}: {call} (ref masked)")


def build(s):
    WRONG = OTHER + NUM_S

    # ---------------- html_encode ----------------
    s.sweep("html_encode", [TEXT + HTML_PLAIN + HTML_RAW + WRONG], min_args=1)
    s.case("html_encode", "html_encode()")
    s.case("html_encode", 'html_encode("<a>", "<b>")')
    s.case("html_encode", 'html_encode(PlainText = "<a>&")')
    s.case("html_encode", 'html_encode(html_encode("<&>"))')
    s.case("html_encode", 'html_decode(html_encode("<b>&amp;\'\\"</b>"))')
    s.case("html_encode", 'html_encode("x" + "<" + "y")')
    s.case("html_encode", 'html_encode(1e7)')
    s.case("html_encode", 'html_encode(-0.5)')
    for seed in LONG_SEED:
        long_case(s, "html_encode", seed, 3000, "html_encode(t)")
    s.body("html_encode", ['var/out = ""', "for(var/i in 1 to 300)",
                           '\tvar/e = html_encode(ascii2text(i))', "\tif(e != ascii2text(i))",
                           '\t\tout += "[i]=[e],"'],
           "out", "html_encode of chars 1..300 that change")

    # ---------------- html_decode ----------------
    s.sweep("html_decode", [TEXT + HTML_ENC + WRONG], min_args=1)
    s.case("html_decode", "html_decode()")
    s.case("html_decode", 'html_decode("&lt;", "&gt;")')
    s.case("html_decode", 'html_decode(HtmlText = "&lt;&amp;")')
    s.case("html_decode", 'html_decode(html_decode("&amp;lt;"))')
    for e in ["&lt;", "&#65;", "&amp;amp;", "&#x1F642;"]:
        long_case(s, "html_decode", e, 2000, "html_decode(t)")
    # Each code point 1..300 through &#N;
    s.body("html_decode", ['var/out = ""', "for(var/i in 1 to 300)",
                           '\tvar/d = html_decode("&#[i];")', '\tout += "[i]:[length(d)]:[text2ascii(d)],"'],
           "out", "html_decode &#1..300; lengths and codes")

    # ---------------- url_encode ----------------
    s.sweep("url_encode", [TEXT + URL_PLAIN + WRONG], min_args=1)
    s.sweep("url_encode", [TEXT_S + URL_PLAIN, URL_FMT], min_args=2)
    s.sweep("url_encode", [OTHER, ["0", "1"]], min_args=2)
    s.case("url_encode", "url_encode()")
    s.case("url_encode", 'url_encode("a b", 0, 1)')
    s.case("url_encode", 'url_encode(PlainText = "a b&c")')
    s.case("url_encode", 'url_encode("a b&c", format = 1)')
    s.case("url_encode", 'url_encode(format = 1, PlainText = "a b&c")')
    s.case("url_encode", 'url_encode("a b&c", format = 0)')
    s.case("url_encode", 'url_decode(url_encode("a b+c%d&e=f é🙂"))')
    s.case("url_encode", 'url_decode(url_encode("a b+c%d&e=f é🙂", 1))')
    s.case("url_encode", 'url_encode(url_encode("a b"))')
    s.case("url_encode", 'url_encode(url_encode("a b", 1), 1)')
    for seed in LONG_SEED:
        long_case(s, "url_encode", seed, 3000, "url_encode(t)")
        long_case(s, "url_encode", seed, 3000, "url_encode(t, 1)", "fmt1")
    # What each format does to ASCII 1..255
    for fmt in ["0", "1"]:
        s.body("url_encode", ['var/out = ""', "for(var/i in 1 to 255)",
                              f"\tvar/e = url_encode(ascii2text(i), {fmt})", '\tout += "[i]=[e] "'],
               "out", f"url_encode chars 1..255 format {fmt}")

    # ---------------- url_decode ----------------
    s.sweep("url_decode", [TEXT + URL_ENC + WRONG], min_args=1)
    s.case("url_decode", "url_decode()")
    s.case("url_decode", 'url_decode("%20", "%20")')
    s.case("url_decode", 'url_decode(UrlText = "a%20b+c")')
    s.case("url_decode", 'url_decode(url_decode("%2520"))')
    for e in ["%20", "+", "%C3%A9", "%zz", "%"]:
        long_case(s, "url_decode", e, 2000, "url_decode(t)")
    s.body("url_decode", ['var/out = ""', "for(var/i in 1 to 127)",
                          '\tvar/h = num2text(i, 2, 16)', "\tif(length(h) < 2)", '\t\th = "0[h]"',
                          '\tvar/d = url_decode("%[h]")', '\tout += "[i]:[length(d)]:[text2ascii(d)],"'],
           "out", "url_decode %01..%7F")

    # ---------------- md5 / sha1 ----------------
    for p in ("md5", "sha1"):
        s.sweep(p, [TEXT + HTML_RAW + WRONG + ['"[ascii2text(128)]"', '"[ascii2text(65535)]"']], min_args=1)
        s.case(p, f"{p}()")
        s.case(p, f'{p}("a", "b")')
        s.case(p, f'{p}(T = "abc")')
        s.case(p, f'{p}(input = "abc")')
        s.case(p, f'{p}({p}("abc"))')
        s.case(p, f'{p}("abc") == {p}("ab" + "c")')
        s.case(p, f'{p}("abc") == {p}("ABC")')
        s.case(p, f'{p}(file("parity_does_not_exist.txt"))')
        s.case(p, f'{p}("parity_does_not_exist.txt")')
        s.case(p, f'{p}(file("scene.dme"))')
        s.case(p, f'{p}(file("scene.dme")) == {p}(file2text("scene.dme"))')
        s.case(p, f'{p}(icon())')
        s.body(p, [f'fdel("parity_{p}.txt")', f'text2file("abc", "parity_{p}.txt")',
                   f'var/r = {p}(file("parity_{p}.txt")) == {p}(file2text("parity_{p}.txt"))',
                   f'fdel("parity_{p}.txt")'], "r", f"{p}(file) equals {p}(file2text)")
        s.body(p, [f'fdel("parity_{p}e.txt")', f'text2file("", "parity_{p}e.txt")',
                   f'var/r = fexists("parity_{p}e.txt") ? {p}(file("parity_{p}e.txt")) : "nofile"',
                   f'fdel("parity_{p}e.txt")'], "r", f"{p}(empty file)")
        for seed in LONG_SEED:
            long_case(s, p, seed, 5000, f"{p}(t)")
        # Lengths 0..70 around the 55/56/64-byte block boundaries
        s.body(p, ['var/out = ""', 'var/t = ""', "for(var/i in 0 to 70)",
                   f'\tout += "[i]:[{p}(t)] "', '\tt += "x"'], "out", f"{p} lengths 0..70")

    # ---------------- params2list ----------------
    s.sweep("params2list", [TEXT + PARAMS + OTHER + NUM_S], min_args=1)
    s.case("params2list", "params2list()")
    s.case("params2list", 'params2list("a=1", "b=2")')
    s.case("params2list", 'params2list(Params = "a=1&b=2")')
    for t in ["a=1&a=2", "a=1;a=2;a=3", "a;a;a", "a&a", "a=1&a", "a&a=1", "x=1&y=2&z=3&x=4&y=5", "a=&a="]:
        for key in ["a", "x"]:
            if key not in t:
                continue
            s.body("params2list", [f"var/list/L = params2list({S(t)})", f"var/v = L[{S(key)}]",
                                   'var/r = islist(v) ? "list:[jointext(v, "|")]" : v'],
                   "r", f"params2list({t!r})[{key!r}]")
    for t in ["a=1&b=2", "1=2", "a=1e3", "a", "a=", "=1", "b=2&a=1&c=3", "a=1&a=2"]:
        s.body("params2list", [f"var/list/L = params2list({S(t)})", 'var/out = ""', "for(var/k in L)",
                               '\tvar/v = L[k]',
                               '\tout += "[istext(k) ? "t" : "o"]:[k]=[istext(v) ? "t" : (isnull(v) ? "null" : (islist(v) ? "L" : "o"))];"'],
               "out", f"params2list({t!r}) key/value types and order")
    s.body("params2list", ['var/list/L = params2list("a=1")', 'L["b"] = 2', 'L += "c"'], "L",
           "params2list result is a normal mutable list")
    s.body("params2list", ['var/list/L = params2list("a=1&b=2")'], "L.len", "params2list len")
    s.body("params2list", ['var/list/L = params2list("a=1&b=2")'], 'L[1]', "params2list L[1]")
    s.body("params2list", ['var/list/L = params2list("a=1&b=2")'], 'L["c"]', "params2list missing key")
    for seed in ["x=1&", "a&", "k\\[i\\]=v&", "k[i]=v&"]:
        s.body("params2list", ['var/t = ""', "for(var/i in 1 to 2000)", f'\tt += "{seed}"',
                               "var/list/L = params2list(t)", 'var/r = "[L.len]:[L[1]]:[L[L.len]]"'],
               "r", f"params2list long {seed!r}")

    # ---------------- list2params ----------------
    s.sweep("list2params", [LISTS + NONLIST], min_args=1)
    s.case("list2params", "list2params()")
    s.case("list2params", 'list2params(list("a"=1), list("b"=2))')
    s.case("list2params", 'list2params(List = list("a" = 1))')
    s.body("list2params", ['var/list/L = list()', 'L["offense"] = "jwalk"', 'L["time"] = "10:00"'],
           "list2params(L)", "documented example")
    s.body("list2params", ['var/list/L = list("a", "b")', 'L["a"] = "x"', 'L.Cut(2, 3)', 'L += "c"'],
           "list2params(L)", "list2params after edits")
    s.body("list2params", ['var/list/L = list("a" = 1)', 'var/r = list2params(L)'],
           "L", "list2params does not change its list")
    s.body("list2params", ['var/list/L = new /list(3)'], "list2params(L)", "list2params(new /list(3))")
    s.body("list2params", ['var/list/L = list("a" = 1, "b" = 2)', 'L["a"] = null'],
           "list2params(L)", "list2params key set to null")
    ref_masked(s, "list2params", ["var/datum/D = new"], 'list2params(list("a" = D))')
    ref_masked(s, "list2params", ["var/datum/D = new"], "list2params(list(D))")
    ref_masked(s, "list2params", ["var/datum/D = new"], 'list2params(list("a" = D, "b" = 2))')
    ref_masked(s, "list2params", ["var/datum/D = new", 'var/list/P = params2list(list2params(list("a" = D)))'],
               'P["a"]')
    s.body("list2params", ["var/datum/D = new", 'var/list/P = params2list(list2params(list("a" = D)))'],
           'locate(P["a"]) == D', "list2params datum ref round-trips through locate()")
    # Round trips
    for l in ['list("a" = "1", "b" = "2")', 'list("a b" = "c&d=e;f", "é" = "🙂")', 'list("x" = 5)',
              'list("a", "b")', 'list("%" = "+")', 'list("k" = list("v1", "v2"))', 'list("a" = "")']:
        s.case("list2params", f"params2list(list2params({l}))")
    for t in ["a=1&b=2", "a=1;b=2", "a+b=c+d", "a%20b=c%2Bd", "a&b", "a=1&a=2", "%C3%A9=%F0%9F%99%82"]:
        s.case("params2list", f"list2params(params2list({S(t)}))")
    s.body("list2params", ['var/list/L = list()', "for(var/i in 1 to 2000)", '\tL["k[i]"] = "v [i]&"',
                           "var/r = list2params(L)", 'var/rr = "[length(r)]:[copytext(r, 1, 41)]|[copytext(r, -40)]"'],
           "rr", "list2params 2000 entries")

    build_gaps(s)


# ---------------- gap coverage (second pass) ----------------
# Mask raw and %-encoded refs of any object in a result string
MASK_ALL = [
    "if(istext(r))",
    '\tvar/regex/RX = new("(%5b|\\\\\\[)0x\\[0-9a-f\\]+(%5d|\\\\\\])", "gi")',
    '\tr = RX.Replace(r, "REF")',
]


def masked_all(s, proc, setup, call, display):
    s.body(proc, setup + [f"var/r = {call}"] + MASK_ALL, "r", display)


def kv_types(s, t, tag="key/value types"):
    s.body("params2list", [f"var/list/L = params2list({S(t)})", 'var/out = "[L.len]|"', "for(var/k in L)",
                           '\tvar/v = L[k]',
                           '\tout += "[istext(k) ? "t" : (isnull(k) ? "null" : "o")]:[k]=[istext(v) ? "t:[v]" : (isnull(v) ? "null" : (islist(v) ? "L:[jointext(v, "|")]" : "o"))];"'],
           "out", f"params2list({t!r}) {tag}")


def build_gaps(s):
    # md5 / sha1: cache-file (single-quoted rsc) form. parity.dm is the only file present at compile time
    # in the scene folder, so it is the resource used (no .dmi is shipped with the scene).
    for p in ("md5", "sha1"):
        s.case(p, f"{p}('parity.dm')")
        s.case(p, f"{p}('parity.dm') == {p}(file(\"parity.dm\"))")
        s.case(p, f"{p}('parity.dm') == {p}(file2text('parity.dm'))")
        s.case(p, f"{p}('parity.dm') == {p}(file2text(\"parity.dm\"))")
        s.case(p, f"{p}(file('parity.dm')) == {p}('parity.dm')")
        s.case(p, f"isnull({p}(icon('parity.dm')))")
        # Runtime-generated .dmi: an icon written out, then hashed as a file and as an icon
        s.body(p, ['fdel("parity_h.dmi")', 'var/icon/I = new', 'fcopy(I, "parity_h.dmi")',
                   'var/a = fexists("parity_h.dmi") ? ' + p + '(file("parity_h.dmi")) : "nofile"',
                   'var/b = ' + p + '(icon("parity_h.dmi"))', 'var/r = "[istext(a)]:[a == b]:[a == ' + p + '(I)]"',
                   'fdel("parity_h.dmi")'], "r", f"{p}(file(dmi)) vs {p}(icon(dmi)) vs {p}(icon)")
        # Newlines through text2file / file2text
        for lit, tag in [('"a\\nb"', "LF"), ('"a[ascii2text(13)][ascii2text(10)]b"', "CRLF"),
                         ('"a[ascii2text(13)]b"', "CR"), ('"é日🙂\\n"', "utf8")]:
            s.body(p, ['fdel("parity_nl.txt")', f'var/sv = {lit}', 'text2file(sv, "parity_nl.txt")',
                       f'var/hf = {p}(file("parity_nl.txt"))', f'var/ht = {p}(file2text("parity_nl.txt"))',
                       f'var/r = "[hf == ht]:[hf == {p}(sv)]:[ht == {p}(sv)]:[length(file2text("parity_nl.txt"))]"',
                       'fdel("parity_nl.txt")'], "r", f"{p} file vs file2text vs literal ({tag})")
        # Binary: copy a resource and a savefile out, hash file vs file2text
        s.body(p, ['fdel("parity_cp.dm")', "fcopy('parity.dm', \"parity_cp.dm\")",
                   f'var/r = {p}(file("parity_cp.dm")) == {p}(\'parity.dm\')', 'fdel("parity_cp.dm")'],
               "r", f"{p}(fcopy of rsc) == {p}(rsc)")
        s.body(p, ['fdel("parity_b.sav")', 'var/savefile/F = new("parity_b.sav")', 'F["x"] << 1.5',
                   'F["y"] << "é"', 'del F',
                   f'var/hf = {p}(file("parity_b.sav"))', f'var/ht = {p}(file2text("parity_b.sav"))',
                   'var/r = "[istext(hf)]:[hf == ht]"', 'fdel("parity_b.sav")'], "r",
               f"{p}(binary savefile) vs file2text")
        s.body(p, ['fdel("parity_h2.dmi")', 'fcopy(new /icon, "parity_h2.dmi")', 'fdel("parity_h2c.dmi")',
                   'fcopy(file("parity_h2.dmi"), "parity_h2c.dmi")',
                   f'var/r = "[{p}(file("parity_h2.dmi")) == {p}(file("parity_h2c.dmi"))]:[{p}(file("parity_h2c.dmi")) == {p}(file2text("parity_h2c.dmi"))]"',
                   'fdel("parity_h2.dmi")', 'fdel("parity_h2c.dmi")'], "r", f"{p}(fcopy of binary dmi)")
        # Directory and empty path
        s.body(p, ['fdel("parity_dir/")', 'text2file("x", "parity_dir/x.txt")',
                   f'var/r = {p}(file("parity_dir/"))', 'fdel("parity_dir/")'], "r", f"{p}(file(directory))")
        s.body(p, ['fdel("parity_dir2/")', 'text2file("x", "parity_dir2/x.txt")',
                   f'var/r = {p}(file("parity_dir2"))', 'fdel("parity_dir2/")'], "r", f"{p}(file(dir no slash))")
        s.case(p, f'{p}(file(""))')
        s.case(p, f'{p}(file("./"))')
        s.case(p, f'{p}(file(null))')

    # list2params: atoms (named) as values, keys, mixed
    for typ, nm in [("/obj", "x"), ("/mob", "m"), ("/turf", "t"), ("/area", "ar"), ("/obj", "")]:
        setup = [f"var{typ}/D = new", f'D.name = {S(nm)}']
        ref_masked(s, "list2params", setup, 'list2params(list("a" = D))')
        ref_masked(s, "list2params", setup, "list2params(list(D))")
        ref_masked(s, "list2params", setup, "list2params(list(D = 1))")
    ref_masked(s, "list2params", ["var/datum/D = new"], "list2params(list(D = 1))")
    ref_masked(s, "list2params", ["var/datum/D = new"], 'list2params(list(D, "b" = 2))')
    ref_masked(s, "list2params", ["var/datum/D = new"], 'list2params(list("b" = 2, D = "v"))')
    ref_masked(s, "list2params", ["var/datum/D = new"], 'list2params(list(D = D))')
    ref_masked(s, "list2params", ["var/obj/D = new", 'D.name = "x y&z"'], 'list2params(list("a" = D))')
    ref_masked(s, "list2params", ["var/obj/D = new", 'D.name = "x"'],
               'params2list(list2params(list("a" = D)))["a"]')
    s.body("list2params", ["var/obj/D = new", 'D.name = "x"', 'var/list/P = params2list(list2params(list("a" = D)))'],
           'locate(P["a"]) == D', "list2params obj value round-trips through locate()")
    # Non-datum object values
    for v in ["'parity.dm'", 'file("scene.dme")', 'file("parity.dm")', "icon()", "new /icon", "world",
              "/proc/parity_escape", "/datum/proc/New", "/obj", "new /list", "new /matrix",
              "rgb(1,2,3)", "image(icon())", "new /image", "new /sound", "sound()", 'generator("num", 1, 2)',
              'new /regex("a")', "new /exception"]:
        masked_all(s, "list2params", [], f'list2params(list("a" = {v}))', f"list2params value {v} (refs masked)")
        masked_all(s, "list2params", [], f"list2params(list({v}))", f"list2params item {v} (refs masked)")
    # Special / builtin lists
    masked_all(s, "list2params", ["var/datum/D = new"], "list2params(D.vars)", "list2params(datum.vars)")
    masked_all(s, "list2params", ["var/datum/D = new"], "length(list2params(D.vars)) > 0",
               "list2params(datum.vars) nonempty")
    masked_all(s, "list2params", ["var/obj/O = new", 'O.name = "o"'],
               'params2list(list2params(O.vars))["name"]', "list2params(obj.vars) name entry")
    masked_all(s, "list2params", ["var/obj/O = new", "var/obj/A = new(O)", 'A.name = "a"', "var/obj/B = new(O)",
                                  'B.name = "b"'], "list2params(O.contents)", "list2params(atom.contents)")
    masked_all(s, "list2params", ["var/obj/O = new"], "list2params(O.verbs)", "list2params(atom.verbs)")
    masked_all(s, "list2params", ["var/obj/O = new"], "list2params(O.overlays)", "list2params(empty overlays)")
    masked_all(s, "list2params", ["var/obj/O = new", 'O.overlays += "x"'], "list2params(O.overlays)",
               "list2params(overlays)")
    masked_all(s, "list2params", [], "list2params(world.contents)", "list2params(world.contents)")
    masked_all(s, "list2params", [], "list2params(args)", "list2params(args) of the case proc")
    masked_all(s, "list2params", [], "list2params(global.vars) != null", "list2params(global.vars) works")
    masked_all(s, "list2params", ["var/obj/O = new"], "list2params(O.filters)", "list2params(filters)")
    masked_all(s, "list2params", ["var/obj/O = new"], 'list2params(O.vars["vis_contents"])',
               "list2params(vis_contents)")
    masked_all(s, "list2params", [], "list2params(world.vars) != null", "list2params(world.vars) works")

    # params2list: keys that collide only after decoding, case variants, empty keys
    for t in ["a%20b=1&a+b=2", "a=1&%61=2", "%41=1&A=2", "a%20b=1&a b=2", "%61&a", "a+b&a%20b",
              "A=1&a=2", "A=1&a=2&A=3", "A&a", "A;a;a", "a&A=1", "Ab=1&aB=2&AB=3",
              "=1&=2", "=1&=", "&=1", "=&=", "=1&a&=2", "&&=x",
              "a&a&a=1", "a=1&a&a", "a=1&a=&a=2", "a&a=1&a", "a=&a&a=",
              "a=1;b", "a=1%3Bb", "a=1\\;b", "a=;b=2", "a=x%3By", "a=x%3By;b=2", "a=%26&b=%3D", "a%3Bb=1",
              "a%26b=1", "a=1%26b=2"]:
        kv_types(s, t)
    for t, keys in [("A=1&a=2", ["A", "a"]), ("A=1&a=2&A=3", ["A", "a"]), ("A&a", ["A", "a"]),
                    ("A;a;a", ["A", "a"]), ("a%20b=1&a+b=2", ["a b"]), ("a=1&%61=2", ["a"]),
                    ("%41=1&A=2", ["A"]), ("=1&=2", [""]), ("=1&=", [""]), ("&=1", [""]), ("=&=", [""]),
                    ("a&a&a=1", ["a"]), ("a=1&a&a", ["a"]), ("a=1&a=&a=2", ["a"]), ("a=;b=2", ["a", "b"]),
                    ("a=1;b", ["a", "b"]), ("a=1%3Bb", ["a"]), ("a=1\\;b", ["a", "b", "1\\"])]:
        for k in keys:
            s.body("params2list", [f"var/list/L = params2list({S(t)})", f"var/v = L[{S(k)}]",
                                   'var/r = "[L.len]|" + (islist(v) ? "list:[jointext(v, "|")]" : (isnull(v) ? "null" : "t:[v]"))'],
                   "r", f"params2list({t!r})[{k!r}]")

    # html_encode: where a URL's skipped span ends
    for t in ["http://a.b/?c&d\ne&f", "http://a.b/?c&d\te&f", "http://a.b/c&d. x&y", "http://a.b/?q='x'&r",
              "http://a/?b&c x&y http://d/?e&f", "http://a.b/c&d, x&y", "http://a.b/c&d) x&y",
              "http://a.b/c&d! x&y", "http://a.b/?q=\"x\"&r", "http://a.b/?q=<x>&r", "http://a.b/c&d;e&f",
              "x&y http://a/?b&c", "http://a/?b&c&amp;d", "http://a/?b&c x&y", "http://a/?b&\U0001F642&c x&y"]:
        s.case("html_encode", f"html_encode({S(t)})")
    for src in ['"\\green x"', '"\\white x"', '"a \\red b \\blue c"', '"\\red http://a/?b&c"',
                '"\\yellow x"', '"\\font x"', '"\\bold x"', '"\\italic x"', '"\\red\\blue x"', '"\\red<b>&"',
                '"\\Red x"', '"\\red"', '"x\\red"']:
        s.case("html_encode", f"html_encode({src})")

    # html_decode: HTML5-only names and zero-padded numerics
    for t in ["&check;", "&NewLine;", "&Tab;", "&rarr;", "&nbsp;&ensp;", "&ensp;", "&emsp;", "&thinsp;",
              "&#0000065;", "&#x00000041;", "&#00000000065;", "&#x0000000041;", "&lbrace;", "&bigstar;",
              "&nbsp;x", "&NBSP;", "&apos;&quot;", "&rArr;", "&hearts;", "&trade;", "&dollar;", "&excl;"]:
        s.case("html_decode", f"html_decode({S(t)})")
    for t in ["&check;", "&NewLine;", "&Tab;", "&nbsp;&ensp;", "&#0000065;", "&#x00000041;", "&rarr;"]:
        s.case("html_decode", f"text2ascii(html_decode({S(t)}))")
        s.case("html_decode", f"length(html_decode({S(t)}))")
