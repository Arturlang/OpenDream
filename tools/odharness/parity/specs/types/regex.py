r"""/regex datum: regex() / new /regex, Find / Find_char, Replace / Replace_char, the regex vars,
REGEX_QUOTE / REGEX_QUOTE_REPLACEMENT and BYOND's regular expression syntax.

BYOND reference points targeted here (info.html /proc/regex, /regex/*, "Regular expressions"):
- regex(pattern, flags) and regex(Regex) (copy); new /regex(...) is the same thing.
- Flags: i (case-insensitive), g (global), m (multi-line ^ $).
- Find(haystack, Start=1, End=0): Start in bytes, defaults to src.next on a global pattern; End is the
  byte after the end of the search, 0 = end, and the match may extend past End. Sets text, index,
  match, group (list of capture groups) and, for "g", next.
- Replace(haystack, replacement, Start=1, End=0): first match (all with "g"); a non-global Replace
  sets index and next as a global Find would, next based on the replaced text, which goes in text.
  Replacement text: $1-$9, $` (before), $' (after), $0 / $& (whole match), $$ (literal $).
  Replacement proc: called with the match then each group; its return value replaces the match.
- name / flags hold the pattern and flags; changing them later does not change behaviour.
- Find_char / Replace_char count characters instead of bytes.
- Syntax: . ^ $ \A \Z [..] [^..] \b \B (..) (?:..) \1-\9, greedy and lazy quantifiers, {n} {n,} {n,m},
  \xNN \uNNNN \UNNNNNN, \d \D \l \L \w \W \s \S, (?=) (?!) (?<=) (?<!) (fixed byte length look-behind).
- REGEX_QUOTE escapes special regex characters; REGEX_QUOTE_REPLACEMENT doubles $.

OpenDream divergences these cases aim at (DreamObjectRegex.cs, DreamProcNativeRegex.cs, Regex.dm):
- OD hands the pattern to .NET Regex: \d \w \s are Unicode-aware, $ matches before a final \n,
  .NET-only syntax ((?<n>), \k<n>, $_, $+, ${n}, (?i), variable look-behind, \p{L}) is accepted,
  \U is not, and invalid patterns throw .NET ArgumentExceptions.
- Every position is a UTF-16 index (Find == Find_char, emoji count as 2, "." can match half an emoji).
- group is an empty list when there are no groups; empty groups become null; a miss leaves the
  previous index/match/group in place.
- Replace with End uses Substring(0, End - Start); non-global Replace sets next from the raw
  replacement length and never sets index; proc replacements are Spawn()ed with src = the regex.
- REGEX_QUOTE is regex(x, 1) = Regex.Escape, which also escapes space, # and whitespace.
- regex(R) copies name/flags/Regex/global but nothing else; non-text flags are ignored.
"""
from gen import dm_str
from pools import TEXT, TEXT_S, OTHER

q = dm_str


def mk(p, f=None):
    return f"regex({q(p)})" if f is None else f"regex({q(p)}, {f if not isinstance(f, str) else q(f)})"


ST = "regex_st(R)"
FIND_RES = "list(r, R.index, R.match, R.group, R.next)"

# Patterns for the pattern x haystack Find sweep (Python strings, unescaped)
PATTERNS = [
    "a", "A", "b+", "a|b", ".", "^a", "c$", "^", "$", r"\d+", r"\w+", r"\s", r"\l+", r"\L", r"\D",
    r"\W", r"\S", r"\bW", r"\B", "(a)(b)?", "(?:ab)+", "a*", "", "[0-3]", "[^a-z]", "x{2}", "x{2,}",
    "x{1,2}?", ".*?c", ".*c", "(?=b)", "(?<=a)b", "(?<!a)b", r"(\w)\1", r"\x41", r"é",
    r"\U01F642", "é", "🙂", "[é日]", r"\A.", r"\Z", "b(.)(.)", "(x)|(b)", r"[\d\l]+", "[-a]", "a{0}",
]
HAYS = ["", "abc", "aabbcc", "Hello World", "x1 22 333", "a\nb\nc", "é日本🙂", "a_b-c", "abc\n"]

# Patterns for flag interactions
FLAG_PATS = ["a", "^b", "c$", "^", "$", "a.c", "é", r"^\w+$"]
FLAG_HAYS = ["abc", "ABC", "a\nb\nc", "É", "z\nB\n"]
FLAGS = ["", "i", "m", "g", "im", "gim"]

# Unknown / odd flag strings and values
ODD_FLAGS = [q(f) for f in ["x", "G", "I", "M", "ig x", "s", "gg", "ii", "igmx", " i", "é", "0"]] + \
            ["null", "0", "1", "2", "3", "-1", "1.5", "list()", "list(\"i\")", "/datum", "new /datum", "PINF"]

# Odd pattern values (DM source)
ODD_PATTERNS = ["null", "5", "0", "-1.5", "list()", 'list("a")', "/datum", "new /datum", "PINF",
                '"a"', '""', "/regex", "regex_noregex()"]

# Syntax beyond the documented set; whether each is accepted, and what it matches, is the parity point
EXTENDED = [
    "(?<n>b)", "(?P<n>b)", r"(?<n>b)\k<n>", r"(b)\g1", "(?i)ABC", "(?#comment)b", "a++", "(?>a+)b",
    "(?(1)a|b)", r"\Qa.c\E", r"\p{L}+", r"\P{L}", r"\h", r"\R", r"a\Kb", r"\Gb", "(?<=a+)b",
    "(?<=a|bc)d", "(?<=é)x", r"\x{41}", r"\101", r"\0", r"\e", r"\cA", r"\t", r"\n", r"\r", r"\v",
    r"\f", r"\a", r"\_", r"\-", r"\/", r"\"", r"\z", r"\Z\n", "[[:alpha:]]+", "[a-z&&[^b]]",
    r"[\b]", r"[\l_]+", r"[^\L]+", r"[\w-]+", "(?s).+", "(?m)^b", "(?x) a b c", "a{,2}", "a{2}{3}",
    "a{3,2}", "{", "}", "a{", "x*?", "x??", "(?:)", "()", "(|a)", "[]a]", "[^]a]", "\\$", r"\.",
    r"\[", "[.]", "[$]", "^*", r"\1(a)", r"(a)\2", r"\8", r"(?=a)*", "(?!)",
]
EXT_HAYS = ["abcdab aab\tB x.c\nd", "Aé日x"]

INVALID = ["(", ")", "[", "a{2,1}", "*", "+a", "a**", "(?<", "\\", "[z-a]", r"\k<n>", "(?<=a*)b",
           "(?P<n>", "(?<n>a)(?<n>b)", r"x\u12", r"\x", r"\U1", "?", "a|*", "[a", r"(?<=\w+)x", "(?z)",
           r"\p{Nope}", "(*FAIL)", "a{99999999999}"]

# Replacement strings (unescaped)
REPLS = ["", "X", "$1", "$2", "$0", "$&", "$`", "$'", "$$", "$", "$3", "$10", "$a", "${1}", "$_",
         "$+", "${n}", r"\1", "[$1]", "$1$1", "a$$b", "$$1", "$12", "$01", "<$`|$'>", "$&$&", "é$1🙂"]
REP_PATS = ["(b)(c)", "b", "x", "", "a*", "^", "$", r"(\w)(\w)?", "(?<n>b)", "(x)?b"]


def build(s):
    s.dm(HELPERS)
    _create(s)
    _find_patterns(s)
    _flags(s)
    _find_positions(s)
    _find_global(s)
    _find_vars(s)
    _replace_text(s)
    _replace_positions(s)
    _replace_proc(s)
    _syntax(s)
    _quote(s)
    _wrong_types(s)
    _gaps(s)


HELPERS = r'''/var/regex/regex_cur

/proc/regex_st(regex/R)
	return list(R.name, R.flags, R.text, R.index, R.next, R.match, R.group)

/proc/regex_noregex()
	return new /datum

/proc/regex_rep(m, a, b)
	return "<[m]:[a]:[b]>"

/proc/regex_args()
	var/t = "[args.len]"
	for(var/a in args)
		t += "|" + (isnull(a) ? "N" : "[a]")
	return t

/proc/regex_num(m)
	return 42

/proc/regex_null(m)
	return null

/proc/regex_empty(m)
	return ""

/proc/regex_list(m)
	return list(m)

/proc/regex_dat(m)
	return new /datum

/proc/regex_upper(m)
	return uppertext(m)

/proc/regex_src(m)
	if(isnull(src))
		return "N"
	if(istype(src, /regex))
		return "R"
	return "O"

/proc/regex_err(m)
	CRASH("regex_boom")

/proc/regex_peek(m)
	if(!regex_cur)
		return "?"
	return "([regex_cur.index],[regex_cur.next],[regex_cur.match],[regex_cur.text])"

/proc/regex_none()
	return "Z"

/proc/regex_len(m)
	return "[length(m)]"

/proc/regex_nested(m)
	var/regex/I = regex("(.)")
	I.Find(m)
	return "{[I.group[1]]}"

/proc/regex_dollar1(m)
	return "$1"

/proc/regex_dollar_amp(m)
	return "$&"

/proc/regex_dollar2(m)
	return "$$"

/proc/regex_dollar_pre(m)
	return "\[$`\]"

/proc/regex_dollar_brace(m)
	return "${1}"

/proc/regex_dollar_post(m)
	return "$'"

/proc/regex_touch_find(m)
	var/r = regex_cur.Find("zzz")
	return "F[r]"

/proc/regex_touch_findm(m)
	var/r = regex_cur.Find(m)
	return "M[r]"

/proc/regex_touch_next(m)
	regex_cur.next = 1
	return "N"

/proc/regex_touch_state(m)
	return "([regex_cur.index],[regex_cur.next],[regex_cur.match],[regex_cur.text],[regex_cur.group ? regex_cur.group.len : -1])"

/proc/regex_len_x(m)
	return ""

/var/regex_log = ""

/regex/regex_sub
	var/regex_extra = 5

/regex/regex_sub/New(p, f)
	regex_log += "New([p],[f])"
	..()

/regex/regex_subf/Find(h, s, e)
	regex_log += "F([h])"
	return ..()

/regex/regex_subr/Replace(h, r, s, e)
	regex_log += "R([h])"
	return ..()

/datum/regex_holder/proc/rep(m)
	return "H[m]"

/datum/regex_holder/proc/who(m)
	return istype(src, /datum/regex_holder) ? "self" : (istype(src, /regex) ? "regex" : "other")
'''


def _create(s):
    P = "regex"
    # regex(pattern, flags) over patterns and flags; the datum prints index/next/match/group
    for pat in ["a", "", "(a)(b)", "é🙂", "\\d+", "[x]"]:
        for f in [None, "", "g", "i", "m", "gim", "mig"]:
            s.body(P, [f"var/regex/R = {mk(pat, f)}"], f"list(R, {ST})")
            if f in (None, "gim"):
                s.body(P, [f"var/regex/R = new /regex({q(pat)}{'' if f is None else ', ' + q(f)})"],
                       f"list(R, {ST})")
    # Odd flags
    for f in ODD_FLAGS:
        s.body(P, [f'var/regex/R = regex("b", {f})'], f'list({ST}, R.Find("aBcb"), R.Find("aBcb"))')
        s.body(P, [f'var/regex/R = new /regex("b", {f})'], f'list({ST}, R.Find("aBcb"))')
    # Odd patterns
    for p in ODD_PATTERNS:
        s.case(P, f"regex({p})")
        s.body(P, [f"var/regex/R = regex({p})"], f'list({ST}, R.Find("a5/regex0"))')
        s.body(P, [f"var/regex/R = new /regex({p})"], ST)
    s.case(P, "regex()")
    s.body(P, ["var/regex/R = new /regex()"], ST)
    s.body(P, ["var/regex/R = new /regex"], ST)
    s.body(P, ['var/regex/R = new("b+", "g")'], f'list({ST}, R.Find("abbcb"), R.next)')
    s.case(P, 'regex("a", "g", 1)')
    s.case(P, 'regex(pattern = "a", flags = "g")')
    s.case(P, 'regex(flags = "i", pattern = "A")')
    s.body(P, ['var/regex/R = regex(flags = "i", pattern = "A")'], f'list({ST}, R.Find("xa"))')
    s.body(P, ['var/regex/R = new /regex(flags = "i", pattern = "A")'], f'list({ST}, R.Find("xa"))')
    s.case(P, 'istype(regex("a"), /regex)')
    s.case(P, 'istype(regex("a"), /datum)')
    s.case(P, 'regex("a").type')
    s.case(P, '"[regex("a")]"')
    s.case(P, 'regex("a") == regex("a")')
    s.body(P, ['var/regex/R = regex("a")'], 'list(R.vars.len, "name" in R.vars, "flags" in R.vars, "next" in R.vars, "group" in R.vars)')
    s.body(P, ['var/regex/R = regex("a")', 'var/list/L = list()', 'for(var/v in list("name", "flags", "text", "index", "next", "match", "group"))', '\tL[v] = isnull(R.vars[v]) ? "null" : R.vars[v]'], 'L')
    s.body(P, ['var/regex/R = regex("a")'], 'list(initial(R.name), initial(R.flags), initial(R.next))')
    s.case(P, 'regex("a") ? 1 : 0')

    # Copy: regex(R) and new /regex(R) after state was set on the source
    for f in [None, "g", "i", "gi", "m"]:
        src = mk("(o)(r)?", f)
        for maker in ["regex(R)", "new /regex(R)", 'regex(R, "g")', 'regex(R, "i")', "regex(R, null)"]:
            s.body("regex copy", [f"var/regex/R = {src}", 'R.Find("Hello World")',
                                  f"var/regex/C = {maker}"],
                   f'list(C == R, regex_st(C), C.Find("hellO wOrld"), regex_st(C), C.Find("hellO wOrld"), {ST})')
    # A copy made after name/flags were changed by hand
    s.body("regex copy", ['var/regex/R = regex("a", "g")', 'R.name = "b"', 'R.flags = "i"', "var/regex/C = regex(R)"],
           'list(regex_st(C), C.Find("aBb"), C.Find("aBb"))')
    s.body("regex copy", ['var/regex/R = regex("a")', 'var/regex/C = regex(R)', 'var/regex/D = regex(C)'],
           'list(regex_st(D), D.Find("xa"))')
    # A copy does not share state with its source
    s.body("regex copy", ['var/regex/R = regex("o", "g")', 'var/regex/C = regex(R)', 'R.Find("foo")', 'R.Find("foo")'],
           'list(C.Find("foo"), C.next, R.next)')


def _find_patterns(s):
    for pat in PATTERNS:
        for h in HAYS:
            s.body("Find", [f"var/regex/R = {mk(pat)}", f"var/r = R.Find({q(h)})"], FIND_RES)
    # Find_char on the multibyte haystacks, same patterns
    for pat in PATTERNS:
        for h in ["🙂x🙂", "aé"]:
            s.body("Find_char", [f"var/regex/R = {mk(pat)}", f"var/r = R.Find_char({q(h)})"], FIND_RES)
    # Documented examples
    s.body("Find", ['var/regex/R = new("B(.)(.)(.)D")', 'var/r = R.Find("BYOND")'], FIND_RES)
    s.body("Find", ['var/regex/R = regex("1(\\\\d)(\\\\d)")', 'var/r = R.Find("123")'], FIND_RES)
    s.body("Find", ['var/regex/R = regex("B.*D")', 'var/r = R.Find("aBcDeD")'], FIND_RES)
    s.body("Find", ['var/regex/R = regex(@"[0-3]")', 'var/r = R.Find("a5b2")'], FIND_RES)
    s.body("Find", ['var/regex/R = regex("foo|bar", "i")', 'var/r = R.Find("xBAR foo")'], FIND_RES)
    s.body("Find", ['var/regex/R = regex(@"\\d+", "g")', 'var/a = R.Find("a12b345")', 'var/b = R.Find("a12b345")', 'var/c = R.Find("a12b345")'],
           'list(a, b, c, R.index, R.match, R.next)')
    s.body("Find", [f'var/regex/R = regex({q(chr(92) + "b")} + REGEX_QUOTE("a.b") + {q(chr(92) + "b")}, "i")', 'var/r = R.Find("xa.b A.B")'], FIND_RES)
    # Lazy vs greedy
    for pat in ["<.+>", "<.+?>", "<.*?>", "a{2,3}", "a{2,3}?", "a+?", "a*?b", "(a+?)(a*)", "(a*?)(a*)"]:
        s.body("Find", [f"var/regex/R = {mk(pat)}", 'var/r = R.Find("<a><b>aaaab")'], FIND_RES)
    # Group shapes: no groups, empty group, non-participating group, nested groups, many groups
    for pat in ["abc", "(a*)b", "(x)?b", "((a)(b))", "(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)", "(?:a)(b)",
                "(a)|(b)", "(a)*", "(a|b)+", "()", "(z*)"]:
        s.body("Find", [f"var/regex/R = {mk(pat)}", 'var/r = R.Find("abcdefghijk")'],
               'list(r, R.match, R.group, R.group ? R.group.len : -1, R.group ? isnull(R.group[1]) : -1)')
    # Case-insensitive non-ASCII and multiline/dotall behaviour
    for pat, f, h in [("é", "i", "É"), ("É", "i", "é"), ("ü", "i", "Ü"), ("σ", "i", "Σ"), ("k", "i", "K"),
                      ("ß", "i", "SS"), ("i", "i", "İ"), ("a.c", None, "a\nc"), ("a.c", "m", "a\nc"),
                      ("a.c", None, "a\x0dc"), ("^c", None, "ab\nc"), ("b$", None, "ab\n"), ("b$", "m", "ab\nc"),
                      (r"b\Z", None, "ab\n"), (r"\Ac", "m", "ab\nc"), ("^$", "m", "a\n\nb"), ("$", "g", "a\n"),
                      (r"\d", None, "٣"), (r"\d", None, "５"), (r"\w", None, "é"), (r"\w", None, "日"),
                      (r"\l", None, "é"), (r"\s", None, " "), (r"\s", None, " "), (r"\s", None, "\x0b"),
                      (r"\b", None, "éa"), (r"\W", None, "é!"), (r"\D", None, "\n1x"), (r"\L", None, "\nx1"),
                      (r"\S", None, "\nx"), (r"\W", None, "\n!"), ("[^a]", None, "a\nb"), (".", None, "\x00x")]:
        s.body("Find", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Find({q(h)})"], FIND_RES)


def _flags(s):
    for pat in FLAG_PATS:
        for f in FLAGS:
            for h in FLAG_HAYS:
                s.body("Find flags", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Find({q(h)})"], FIND_RES)


def _find_positions(s):
    START = ["0", "1", "2", "3", "5", "9", "10", "11", "-1", "-3", "-9", "-100", "1.5", "null", "NAN", '"2"', "PINF", "NINF", "list()"]
    END = ["0", "3", "4", "9", "10", "-1", "-3", "null"]
    for p in ["Find", "Find_char"]:
        for st in START:
            s.body(p, ['var/regex/R = regex("bc")', f'var/r = R.{p}("abcabcabc", {st})'], FIND_RES)
            s.body(p, ['var/regex/R = regex("bc", "g")', f'var/r = R.{p}("abcabcabc", {st})'], FIND_RES)
        for st in ["1", "2", "3", "5", "0", "-1", "-4"]:
            for en in END:
                s.body(p, ['var/regex/R = regex("bc")', f'var/r = R.{p}("abcabcabc", {st}, {en})'], FIND_RES)
        for st in ["1", "2", "5", "-4"]:
            for en in ["0", "3", "4", "-1"]:
                s.body(p, ['var/regex/R = regex("bc", "g")', f'var/r = R.{p}("abcabcabc", {st}, {en})'], FIND_RES)
        # Match extending past End, anchors at the End boundary, look-behind before Start
        for pat, a in [("cde", "1, 4"), ("cde", "1, 3"), ("c$", "1, 4"), ("c(?=d)", "1, 4"), ("^c", "3"),
                       ("(?<=b)c", "3"), (r"\bc", "3"), ("c(?!d)", "1, 4"), ("^", "3"), ("$", "1, 3"),
                       (r"\Ac", "3"), ("c.*", "1, 4"), ("", "4"), ("", "7"), ("", "8"), ("f", "6, 6"),
                       ("a", "1, 1"), ("a", "2, 1"), ("b", "4, 2")]:
            s.body(p, [f"var/regex/R = {mk(pat)}", f'var/r = R.{p}("abcdef", {a})'], FIND_RES)
        # Multibyte: bytes for Find, characters for Find_char
        MB = q("é日本🙂é日本🙂")
        for st in ["1", "2", "3", "4", "6", "9", "10", "13", "15", "25", "-1", "-4", "-12"]:
            s.body(p, ['var/regex/R = regex("日本")', f'var/r = R.{p}({MB}, {st})'], FIND_RES)
            s.body(p, ['var/regex/R = regex("日本", "g")', f'var/r = R.{p}({MB}, {st})'], FIND_RES)
        for a in ["1, 3", "1, 4", "1, 6", "1, 9", "5, 9", "1, -1", "2, -4"]:
            s.body(p, ['var/regex/R = regex("本")', f'var/r = R.{p}({MB}, {a})'], FIND_RES)
        s.body(p, ['var/regex/R = regex("🙂", "g")', f'var/a = R.{p}({MB})', 'var/n1 = R.next', f'var/b = R.{p}({MB})'],
               'list(a, n1, b, R.next, R.index)')
        s.body(p, ['var/regex/R = regex(".", "g")', f'var/a = R.{p}("🙂x")', 'var/m1 = R.match', f'var/b = R.{p}("🙂x")'],
               'list(a, m1, b, R.match, R.next)')
        s.body(p, ['var/regex/R = regex("x")', f'var/r = R.{p}("🙂x", 2)'], FIND_RES)
        s.body(p, ['var/regex/R = regex(".")', f'var/r = R.{p}("🙂x", 2)'], FIND_RES)
        # Named arguments: BYOND documents Start/End, OD declares start/end
        for a in ['haystack = "abcabc"', '"abcabc", Start = 3', '"abcabc", start = 3', '"abcabc", 1, End = 3',
                  '"abcabc", end = 3', 'Start = 4, haystack = "abcabc"', '"abcabc", Haystack = "x"']:
            s.body(p, ['var/regex/R = regex("c")', f'var/r = R.{p}({a})'], FIND_RES)
        # Arity
        s.body(p, ['var/regex/R = regex("c")', f'var/r = R.{p}()'], FIND_RES)
        s.body(p, ['var/regex/R = regex("c")', f'var/r = R.{p}("abc", 1, 0, 5)'], FIND_RES)
        # Long haystack
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 3000) t += "日🙂"', 't += "x"', 'var/regex/R = regex("x")', f'var/r = R.{p}(t)'],
               'list(r, R.match)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 3000) t += "ab"', 'var/regex/R = regex("b", "g")', 'var/n = 0',
                   f'while(R.{p}(t) && n < 5000)', '\tn++'], 'list(n, R.next, R.index)')


def _find_global(s):
    for p in ["Find", "Find_char"]:
        # Iterating with a global pattern, capped so a stuck next cannot loop forever
        for pat, h in [("o", "Hello World"), ("", "abc"), ("a*", "baac"), ("^", "a\nb"), ("$", "ab"),
                       ("x", "abc"), ("(.)", "é日🙂"), ("\\b", "ab cd"), ("o", "o"), ("ab|b", "abb"),
                       ("^.", "a\nb\nc")]:
            for f in ["g", "gm"] if pat in ("^", "^.") else ["g"]:
                s.body(p, [f"var/regex/R = {mk(pat, f)}", "var/list/L = list()", "for(var/i in 1 to 6)",
                           f"\tL += R.{p}({q(h)})", "\tL += R.next"], "L")
        # A non-global pattern never advances
        s.body(p, ['var/regex/R = regex("o")', "var/list/L = list()", "for(var/i in 1 to 3)",
                   f'\tL += R.{p}("Hello World")', "\tL += R.next"], "L")
        # next set by hand; text set by hand; switching haystacks; explicit Start overrides next
        for pre in ['R.next = 6', 'R.next = 100', 'R.next = 0', 'R.next = -1', 'R.next = "6"', 'R.next = null',
                    'R.next = 1.5', 'R.text = "other"', 'R.text = null', 'R.index = 5']:
            s.body(p, ['var/regex/R = regex("o", "g")', f'R.{p}("Hello World")', pre, f'var/r = R.{p}("Hello World")'],
                   FIND_RES)
            s.body(p, ['var/regex/R = regex("o", "g")', pre, f'var/r = R.{p}("Hello World")'], FIND_RES)
        for a in ["1", "5", "6", "null", "0"]:
            s.body(p, ['var/regex/R = regex("o", "g")', f'R.{p}("Hello World")', f'var/r = R.{p}("Hello World", {a})'],
                   FIND_RES)
        s.body(p, ['var/regex/R = regex("o", "g")', f'var/a = R.{p}("Hello World")', f'var/b = R.{p}("Hello")',
                   f'var/c = R.{p}("Hello")', f'var/d = R.{p}("Hello World")'], 'list(a, b, c, d, R.next, R.text)')
        s.body(p, ['var/regex/R = regex("o", "g")', f'var/a = R.{p}("Hello World")', f'var/b = R.{p}("Hello World")',
                   f'var/c = R.{p}("Hello World")', f'var/d = R.{p}("Hello World")'], 'list(a, b, c, d, R.next, R.index, R.match)')
        # Global search across a text that only looks the same (different object, same value)
        s.body(p, ['var/regex/R = regex("o", "g")', 'var/t = "Hello"', f'R.{p}(t + " World")', f'var/r = R.{p}("Hello World")'],
               FIND_RES)
        # Miss after a hit: what is left in index/match/group
        for f in [None, "g"]:
            s.body(p, [f"var/regex/R = {mk('(o)', f)}", f'var/a = R.{p}("Hello")', f'var/b = R.{p}("zzz")'],
                   f"list(a, b, {ST})")


def _find_vars(s):
    P = "regex vars"
    # State after each op
    for f in [None, "g", "i", "m"]:
        R = mk("(l+)(o)", f)
        s.body(P, [f"var/regex/R = {R}"], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Find("Hello World")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Find("zzz")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Replace("Hello World", "X")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Replace("zzz", "X")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Find("Hello World")', f'R.Replace("Hello World", {q("[$2]")})'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Replace("Hello World", "$2$1")', 'R.Find("Hello World")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Find_char("éHello")'], ST)
        s.body(P, [f"var/regex/R = {R}", 'R.Replace_char("éHello", "X")'], ST)
    # Changing name/flags does not change behaviour
    s.body(P, ['var/regex/R = regex("a")', 'R.name = "b"'], 'list(R.Find("ab"), R.name, R.match)')
    s.body(P, ['var/regex/R = regex("a")', 'R.flags = "gi"'], 'list(R.Find("AaA"), R.Find("AaA"), R.next, R.flags)')
    s.body(P, ['var/regex/R = regex("a", "g")', 'R.flags = null'], 'list(R.Find("aa"), R.Find("aa"), R.next)')
    s.body(P, ['var/regex/R = regex("a")', 'R.group = list("q")', 'R.Find("b")'], ST)
    s.body(P, ['var/regex/R = regex("(a)")', 'R.Find("a")', 'var/list/G = R.group', 'R.Find("ba")'], 'list(G, R.group, G == R.group)')
    s.body(P, ['var/regex/R = regex("(a)")', 'R.Find("a")', 'R.group += "x"'], 'list(R.group, R.Find("ba"), R.group)')
    s.body(P, ['var/regex/R = regex("a")', 'R.match = 5', 'R.index = "q"'], ST)
    s.body(P, ['var/regex/R = regex("a")'], 'list(issaved(R.name), issaved(R.next))')


def _replace_text(s):
    for p in ["Replace", "Replace_char"]:
        pats = REP_PATS if p == "Replace" else REP_PATS[:4]
        repls = REPLS if p == "Replace" else REPLS[:12]
        for pat in pats:
            for f in [None, "g"]:
                for r in (repls if f is None else repls[:12]):
                    s.body(p, [f"var/regex/R = {mk(pat, f)}", f'var/r = R.{p}("abcabc", {q(r)})'],
                           f"list(r, {ST})")
    # Documented: dollar escapes, groups $1-$9, the text before/after
    D = [("(\\w+) (\\w+)", "$2 $1", "hello world"), ("o", "$`", "foo"), ("o", "$'", "foob"), ("o", "[$0]", "foo"),
         ("(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)", "$9$10", "abcdefghij"), ("(.)", "$1$1", "é🙂"), ("x", "$$", "axb"),
         ("(a)|(b)", "<$1|$2>", "ab"), ("(a)?b", "<$1>", "b"), ("b", "$`$'", "abc")]
    for pat, r, h in D:
        for f in [None, "g"]:
            s.body("Replace", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Replace({q(h)}, {q(r)})"], f"list(r, {ST})")
    # Case-insensitive replacement keeps the replacement as given
    s.body("Replace", ['var/regex/R = regex("hello", "gi")', 'var/r = R.Replace("Hello HELLO hello", "bye")'], f"list(r, {ST})")
    # Global replacement with empty matches and zero-width assertions
    for pat in ["", "x*", "a*", "^", "$", "\\b", "(?=b)", "(?<=a)", "^", "$"]:
        for f in ["g", "gm"]:
            s.body("Replace", [f"var/regex/R = {mk(pat, f)}", 'var/r = R.Replace("ab\\nab", "-")'], f"list(r, {ST})")
    # Repeated non-global Replace: next/index/text after each
    s.body("Replace", ['var/regex/R = regex("o")', 'var/a = R.Replace("foo boo", "0")', 'var/n1 = R.next',
                       'var/b = R.Replace(a, "0")', 'var/n2 = R.next', 'var/c = R.Replace(b, "0", R.next)'],
           f"list(a, n1, b, n2, c, {ST})")
    for r in ["", "XYZ", "$0$0", "$1"]:
        s.body("Replace", ['var/regex/R = regex("(o+)")', f'var/a = R.Replace("foo boo", {q(r)})'], f"list(a, {ST})")
        s.body("Replace_char", ['var/regex/R = regex("(é+)")', f'var/a = R.Replace_char("fé🙂éé", {q(r)})'], f"list(a, {ST})")
        s.body("Replace", ['var/regex/R = regex("(é+)")', f'var/a = R.Replace("fé🙂éé", {q(r)})'], f"list(a, {ST})")
    # Global Replace leaves next as what?
    s.body("Replace", ['var/regex/R = regex("o", "g")', 'R.Find("foo")', 'var/r = R.Replace("foo boo", "0")'], f"list(r, {ST})")
    s.body("Replace", ['var/regex/R = regex("o", "g")', 'var/r = R.Replace("foo boo", "0")', 'var/f = R.Find("foo boo")'], f"list(r, f, {ST})")
    # Replace after a global Find on the same text: does Start default to next?
    s.body("Replace", ['var/regex/R = regex("o", "g")', 'R.Find("foo boo")', 'R.Find("foo boo")', 'var/r = R.Replace("foo boo", "0")'], f"list(r, {ST})")
    # Arity and named arguments
    for a in ['"abcabc"', '', '"abcabc", "X", 1, 0, 9', 'haystack = "abcabc", replacement = "X"',
              '"abcabc", "X", Start = 3', '"abcabc", "X", start = 3', '"abcabc", "X", 1, End = 3',
              '"abcabc", "X", end = 3', 'replacement = "Y", haystack = "abc"', '"abcabc", Replacement = "Z"']:
        for f in [None, "g"]:
            s.body("Replace", [f"var/regex/R = {mk('b', f)}", f"var/r = R.Replace({a})"], f"list(r, {ST})")


def _replace_positions(s):
    START = ["1", "2", "3", "5", "0", "-1", "-3", "10", "null"]
    END = ["0", "3", "5", "9", "10", "-1", "null"]
    for p in ["Replace", "Replace_char"]:
        for f in [None, "g"]:
            for st in START:
                for en in END:
                    if (f == "g" or p == "Replace_char") and st not in ("1", "3", "-3", "null"):
                        continue
                    s.body(p, [f"var/regex/R = {mk('b', f)}", f'var/r = R.{p}("abcabcabc", "<$0>", {st}, {en})'],
                           f"list(r, {ST})")
            for st in START[:8]:
                s.body(p, [f"var/regex/R = {mk('b', f)}", f'var/r = R.{p}("abcabcabc", "<$0>", {st})'], f"list(r, {ST})")
        # Multibyte positions
        MB = q("é日本🙂é日本🙂")
        for a in ["1", "3", "4", "9", "13", "-4", "1, 6", "1, 9", "3, 15", "2, -1"]:
            for f in [None, "g"]:
                s.body(p, [f"var/regex/R = {mk('日本', f)}", f'var/r = R.{p}({MB}, "_", {a})'], f"list(r, {ST})")
        # Match running past End
        for pat in ["cde", "c.*", "$", "c$", ""]:
            s.body(p, [f"var/regex/R = {mk(pat, 'g')}", f'var/r = R.{p}("abcdef", "X", 1, 4)'], f"list(r, {ST})")
        # End before Start
        s.body(p, ['var/regex/R = regex("b", "g")', f'var/r = R.{p}("abcabc", "X", 5, 2)'], f"list(r, {ST})")
        s.body(p, ['var/regex/R = regex("b")', f'var/r = R.{p}("abcabc", "X", 5, 2)'], f"list(r, {ST})")


def _replace_proc(s):
    PROCS = ["/proc/regex_rep", "/proc/regex_args", "/proc/regex_num", "/proc/regex_null", "/proc/regex_empty",
             "/proc/regex_list", "/proc/regex_dat", "/proc/regex_upper", "/proc/regex_src", "/proc/regex_err",
             "/proc/regex_none", "/proc/regex_len", "/proc/regex_nested", "/datum/regex_holder/proc/rep",
             "/datum/regex_holder/proc/who"]
    for pr in PROCS:
        for pat, h in [("(b)(c)?", "abcab"), ("x", "abc"), ("", "ab"), ("(é)", "aé🙂é")]:
            for f in [None, "g"]:
                s.body("Replace proc", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Replace({q(h)}, {pr})"],
                       f"list(r, {ST})")
        s.body("Replace_char proc", ['var/regex/R = regex("(é)", "g")', f'var/r = R.Replace_char("aé🙂é", {pr})'],
               f"list(r, {ST})")
    # Seeing the regex's own vars from inside the proc
    for f in [None, "g"]:
        s.body("Replace proc", [f"var/regex/R = {mk('o', f)}", "regex_cur = R", 'var/r = R.Replace("foo boo", /proc/regex_peek)',
                                "regex_cur = null"], f"list(r, {ST})")
    # Positions with a proc
    for a in ["3", "1, 5", "5, 9", "-3"]:
        for f in [None, "g"]:
            s.body("Replace proc", [f"var/regex/R = {mk('(b)', f)}", f'var/r = R.Replace("abcabcabc", /proc/regex_rep, {a})'],
                   f"list(r, {ST})")
    # Many groups passed as arguments
    s.body("Replace proc", ['var/regex/R = regex("(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)")', 'var/r = R.Replace("abcdefghijk", /proc/regex_args)'],
           f"list(r, {ST})")
    s.body("Replace proc", ['var/regex/R = regex("(a)(x)?(b)", "g")', 'var/r = R.Replace("abab", /proc/regex_args)'], f"list(r, {ST})")
    s.body("Replace proc", ['var/regex/R = regex("(a*)b", "g")', 'var/r = R.Replace("bab", /proc/regex_args)'], f"list(r, {ST})")
    # Things that are not procs given as the replacement
    for v in ['"regex_rep"', '"/proc/regex_rep"', "/datum", "/regex", "new /datum", "list()", "5", "null",
              "PINF", '"[1]"', "/proc/regex_missing_not_a_proc"]:
        for f in [None, "g"]:
            s.body("Replace wrong", [f"var/regex/R = {mk('b', f)}", f'var/r = R.Replace("abcb", {v})'], f"list(r, {ST})")


def _syntax(s):
    for pat in EXTENDED:
        for h in EXT_HAYS:
            s.body("syntax", [f"var/regex/R = {mk(pat)}", f"var/r = R.Find({q(h)})"], FIND_RES)
    # Escapes
    for pat, h in [(r"\x41", "zA"), (r"\x61", "zA"), (r"\xe9", "é"), (r"\xc3", "é"), (r"é", "é"),
                   (r"日", "x日"), (r"\U01F642", "x🙂"), (r"\U00e9", "é"), (r"A", "A"),
                   (r"[\x41-\x43]+", "ABCD"), (r"[à-ÿ]", "é"), (r"\x4", "\x04"), (r"\xZZ", "xZZ"),
                   ("[é-ü]", "ñ"), ("[🙂-🙃]", "🙃"), ("[^é]", "é"), ("é+", "ééé"), ("🙂+", "🙂🙂"), ("(🙂){2}", "🙂🙂"),
                   (".{2}", "🙂"), (".{2}", "é"), ("^.$", "é"), ("^.$", "🙂"), ("^..$", "🙂"), ("(?<=é)x", "éx"),
                   ("(?<=🙂)x", "🙂x"), ("(?<=.)x", "🙂x"), ("(?<=..)x", "éx"), ("(?<=....)x", "🙂x")]:
        for p in ["Find", "Find_char"]:
            s.body("syntax", [f"var/regex/R = {mk(pat)}", f"var/r = R.{p}({q(h)})"], FIND_RES)
    # Invalid patterns: error at creation, or at the first Find, or silent?
    for pat in INVALID:
        s.body("invalid", [f"var/regex/R = {mk(pat)}"], ST)
        s.body("invalid", [f"var/regex/R = {mk(pat)}", f"var/r = R.Find({q('a(b)[c]*?')})"], FIND_RES)
        s.body("invalid", [f"var/regex/R = {mk(pat, 'g')}", f"var/r = R.Replace({q('a(b)[c]*?')}, \"X\")"], f"list(r, {ST})")
    s.body("invalid", ['var/r = "ok"', 'try', '\tregex("(")', 'catch(var/exception/E)', '\tr = list(E.name, E.desc)'], "r")


def _quote(s):
    SPECIAL = ["", "a", ".", "*", "+", "?", "^", "$", "{", "}", "(", ")", "|", "[", "]", "\\", "/", "-", "#",
               " ", "\t", "\n", "a.b*c", "1+1=2", "$1 $$", "é🙂", "<>", "&", "'\"", ",", ":", "=", "!", "@", "%",
               "~", "`", "_", "\x00", "\x0d", "\x0c", "\x07", "\x1b"]
    for t in SPECIAL:
        s.case("REGEX_QUOTE", f"REGEX_QUOTE({q(t)})")
        s.case("REGEX_QUOTE_REPLACEMENT", f"REGEX_QUOTE_REPLACEMENT({q(t)})")
        # Round trip: the quoted text matches itself literally
        s.body("REGEX_QUOTE", [f"var/regex/R = regex(REGEX_QUOTE({q(t)}))", f'var/r = R.Find("x" + {q(t)})'], FIND_RES)
        s.body("REGEX_QUOTE_REPLACEMENT", ['var/regex/R = regex("b")', f'var/r = R.Replace("abc", REGEX_QUOTE_REPLACEMENT({q(t)}))'], "r")
    for t in TEXT:
        s.case("REGEX_QUOTE", f"REGEX_QUOTE({t})")
    for o in OTHER + ["5", "-1.5", "1e7"]:
        s.case("REGEX_QUOTE", f"REGEX_QUOTE({o})")
        s.case("REGEX_QUOTE_REPLACEMENT", f"REGEX_QUOTE_REPLACEMENT({o})")
    # The macros' underlying form: regex(text, number)
    for n in ["1", "2", "0", "3", "-1", "1.5", "2.5"]:
        s.case("regex numeric", f'regex("a.$b", {n})')
        s.case("regex numeric", f'regex(regex("a"), {n})')
    s.body("REGEX_QUOTE", ['var/word = "c++"', 'var/regex/R = regex("\\\\b[REGEX_QUOTE(word)]", "i")', 'var/r = R.Find("x C++ y")'], FIND_RES)
    s.body("REGEX_QUOTE", ['var/regex/R = regex(REGEX_QUOTE("a.b"), "g")', 'var/r = R.Replace("a.b axb a.b", "Q")'], "r")


def _wrong_types(s):
    VALS = ["null", "123", "1.5", "list()", 'list("abc")', "/datum", "new /datum", "PINF", '"123"', 'regex("b")']
    for v in VALS:
        for f in [None, "g"]:
            s.body("Find wrong", [f"var/regex/R = {mk('[1b]', f)}", f"var/r = R.Find({v})"], f"list(r, {ST})")
            s.body("Find wrong", [f"var/regex/R = {mk('[1b]', f)}", f"var/r = R.Find_char({v})"], f"list(r, {ST})")
            s.body("Replace wrong", [f"var/regex/R = {mk('[1b]', f)}", f'var/r = R.Replace({v}, "X")'], f"list(r, {ST})")
            s.body("Replace wrong", [f"var/regex/R = {mk('[1b]', f)}", f'var/r = R.Replace_char({v}, "X")'], f"list(r, {ST})")
        s.body("Find wrong", ['var/regex/R = regex("b")', f'var/r = R.Find("abcb", {v})'], f"list(r, {ST})")
        s.body("Find wrong", ['var/regex/R = regex("b")', f'var/r = R.Find("abcb", 1, {v})'], f"list(r, {ST})")
        s.body("Replace wrong", ['var/regex/R = regex("b", "g")', f'var/r = R.Replace("abcb", "X", {v})'], f"list(r, {ST})")
        s.body("Replace wrong", ['var/regex/R = regex("b", "g")', f'var/r = R.Replace("abcb", "X", 1, {v})'], f"list(r, {ST})")
    # Text-sweep: shared TEXT_S haystacks through a fixed global word regex and its replacement
    for t in TEXT_S:
        s.body("Find", ['var/regex/R = regex("(\\\\w)(\\\\w*)", "g")', f"var/a = R.Find({t})", f"var/b = R.Find({t})"],
               "list(a, b, R.index, R.match, R.group, R.next)")
        s.body("Replace", ['var/regex/R = regex("(\\\\w)(\\\\w*)", "g")', f'var/r = R.Replace({t}, "$2$1")'], f"list(r, {ST})")
        s.body("Replace_char", ['var/regex/R = regex(".", "g")', f'var/r = R.Replace_char({t}, "<$0>")'], "r")


def _gaps(s):
    # Replace proc whose return value holds $ tokens: inserted as-is or expanded?
    for pr in ["/proc/regex_dollar1", "/proc/regex_dollar_amp", "/proc/regex_dollar2", "/proc/regex_dollar_pre",
               "/proc/regex_dollar_brace", "/proc/regex_dollar_post"]:
        for f in [None, "g"]:
            s.body("Replace proc", [f"var/regex/R = {mk('(b)', f)}", f'var/r = R.Replace("abcb", {pr})'], f"list(r, {ST})")
        s.body("Replace_char proc", ['var/regex/R = regex("(é)", "g")', f'var/r = R.Replace_char("aé🙂é", {pr})'], f"list(r, {ST})")

    # Callback that uses the regex calling it
    for pr in ["/proc/regex_touch_find", "/proc/regex_touch_findm", "/proc/regex_touch_next", "/proc/regex_touch_state"]:
        for pat in ["(b)", "b"]:
            for f in [None, "g"]:
                s.body("Replace proc", [f"var/regex/R = {mk(pat, f)}", "regex_cur = R", f'var/r = R.Replace("abcab", {pr})',
                                        "regex_cur = null"], f"list(r, {ST})")

    # /regex subtypes
    P = "regex subtype"
    for maker in ['new /regex/regex_sub("(a)", "g")', 'new /regex/regex_sub("(a)")', 'new /regex/regex_sub']:
        s.body(P, ['regex_log = ""', f"var/regex/regex_sub/R = {maker}", "var/l = regex_log"],
               f'list(l, istype(R, /regex), R.type, R.regex_extra, {ST}, R.Find("xa"), R.next, {ST})')
    s.body(P, ['regex_log = ""', 'var/regex/regex_sub/R = new /regex/regex_sub("(a)", "g")', 'var/r = R.Replace("xaxa", "<$1>")'],
           f"list(r, regex_log, {ST})")
    s.body(P, ['regex_log = ""', 'var/regex/regex_sub/R = new /regex/regex_sub("(a)", "g")', "var/regex/C = regex(R)"],
           'list(C.type, regex_log, regex_st(C), C.Find("aa"))')
    s.body(P, ['regex_log = ""', 'var/regex/regex_sub/R = new /regex/regex_sub("(a)", "i")', 'var/regex/C = new /regex/regex_sub(R)'],
           'list(C.type, regex_log, regex_st(C), C.Find("xA"))')
    for f in [None, "g"]:
        sub = f'new /regex/regex_subf("(a)"{"" if f is None else ", " + q(f)})'
        s.body(P, ['regex_log = ""', f"var/regex/R = {sub}", 'var/a = R.Find("xaa")', 'var/b = R.Find("xaa")'],
               f"list(a, b, regex_log, R.type, {ST})")
        s.body(P, ['regex_log = ""', f"var/regex/R = {sub}", 'var/a = R.Find_char("xaa")', 'var/b = R.Replace("xaa", "Q")'],
               f"list(a, b, regex_log, {ST})")
        sub = f'new /regex/regex_subr("(a)"{"" if f is None else ", " + q(f)})'
        s.body(P, ['regex_log = ""', f"var/regex/R = {sub}", 'var/a = R.Replace("xaa", "Q")', 'var/b = R.Replace_char("xaa", "Q")'],
               f"list(a, b, regex_log, {ST})")
    s.case(P, 'istype(regex("a"), /regex/regex_sub)')

    # Back-references \10 and up, and to groups that did not take part
    P = "syntax"
    TEN = "(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)\\10"
    for h in ["abcdefghijj", "abcdefghija0", "abcdefghija"]:
        s.body(P, [f"var/regex/R = {mk(TEN)}", f"var/r = R.Find({q(h)})"], FIND_RES)
    s.body(P, [f"var/regex/R = {mk('(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)')}", f'var/r = R.Replace("abcdefghijk", {q("$10|$11|${11}")})'],
           f"list(r, {ST})")
    for pat, h in [("(x)?\\1b", "b"), ("(a)|\\1b", "b"), ("(x)*\\1b", "ab"), ("(?:(x)|y)\\1z", "yz"), ("(a)?\\1", "aa")]:
        s.body(P, [f"var/regex/R = {mk(pat)}", f"var/r = R.Find({q(h)})"], FIND_RES)

    # Case-insensitive back-references and classes
    for pat, h in [("(a)\\1", "aA"), ("(a)\\1", "Aa"), ("[a-c]+", "xABC"), ("[^a]", "Ab"), ("\\l+", "1AbC"),
                   ("\\L+", "aB1-"), ("[\\l]+", "1AbC"), ("[^\\l]", "Ab1"), ("[A-C]+", "xabc"), ("[é]", "É"), ("(é)\\1", "éÉ")]:
        for f in ["i", None]:
            s.body("Find flags", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Find({q(h)})"], FIND_RES)

    # Named groups mixed with plain groups: numbering order
    for pat in ["(?<n>a)(b)", "(a)(?<n>b)", "(?<n>a)(b)(?<m>c)"]:
        s.body(P, [f"var/regex/R = {mk(pat)}", 'var/r = R.Find("abc")'], FIND_RES)
        s.body(P, [f"var/regex/R = {mk(pat)}", 'var/r = R.Replace("abc", "$1|$2|$3")'], f"list(r, {ST})")
        s.body(P, [f"var/regex/R = {mk(pat)}", 'var/r = R.Replace("abc", /proc/regex_args)'], f"list(r, {ST})")

    # \uNNNN with valid values
    for pat, h in [(r"é", "xé"), (r"日", "x日"), (r"[à-ÿ]+", "aéü"), (r"\uD83D", "🙂"),
                   (r"\uD83D.", "🙂x"), (r"A", "zA"), (r"é", "é"), (r"é+", "éé")]:
        for p in ["Find", "Find_char"]:
            s.body(P, [f"var/regex/R = {mk(pat)}", f"var/r = R.{p}({q(h)})"], FIND_RES)

    # Look-behind with a fixed char count but a variable byte length
    for pat, h in [("(?<=[aé])x", "éx"), ("(?<=[aé])x", "ax"), ("(?<=a|é)x", "éx"), ("(?<=a|é)x", "ax"),
                   ("(?<![aé])x", "éx"), ("(?<=.)x", "éx"), ("(?<=\\w)x", "éx")]:
        for p in ["Find", "Find_char"]:
            s.body(P, [f"var/regex/R = {mk(pat)}", f"var/r = R.{p}({q(h)})"], FIND_RES)

    # OD's \l / \L rewrite when a class starts with ]
    for pat, h in [(r"[]\l]+", "x]ab"), (r"[^]\L]+", "]a1"), (r"[\]\l]+", "]a"), (r"[]\L]+", "a]1-"),
                   (r"[\l]]+", "a]]"), (r"[[\l]+", "1[a"), (r"\[\l\]", "[a]")]:
        s.body(P, [f"var/regex/R = {mk(pat)}", f"var/r = R.Find({q(h)})"], FIND_RES)

    # \r\n line endings
    CRLF = "a\r\nb"
    for pat, f, h in [("a$", "m", CRLF), ("^b", "m", CRLF), ("a$", None, "a\r\n"), ("a$", None, "a\r"),
                      ("\\S", None, "\rx"), ("\\W", None, "\r!"), ("\\s", None, "\r"), ("\\L", None, "\rx"),
                      ("\\D", None, "\rx"), ("[^a]", None, "\rx"), ("^", "gm", CRLF), ("$", "gm", CRLF)]:
        s.body("Find", [f"var/regex/R = {mk(pat, f)}", f"var/r = R.Find({q(h)})"], FIND_RES)
    s.body("Replace", ['var/regex/R = regex("$", "gm")', f'var/r = R.Replace({q("a" + chr(13) + chr(10) + "b" + chr(13) + chr(10))}, "|")'],
           f"list(r, {ST})")

    # Replace_char with a proc plus Start/End
    MB = q("é🙂éaé")
    for a in ["2, 4", "-2", "2", "1, 3", "3, -1"]:
        for f in [None, "g"]:
            s.body("Replace_char proc", [f"var/regex/R = {mk('(é)', f)}", f'var/r = R.Replace_char({MB}, /proc/regex_rep, {a})'],
                   f"list(r, {ST})")
            s.body("Replace proc", [f"var/regex/R = {mk('(é)', f)}", f'var/r = R.Replace({MB}, /proc/regex_rep, {a})'],
                   f"list(r, {ST})")

    # Global proc replacement with empty or shorter results on dense matches
    for pat, h, pr in [("aa", "aaaaaa", "/proc/regex_empty"), ("a", "aaab", "/proc/regex_len_x"),
                       ("(?<=a)a", "aaaa", "/proc/regex_upper"), ("(?<=a)a", "aaaa", "/proc/regex_empty"),
                       ("aa", "aaaaa", "/proc/regex_none"), ("ab", "ababab", "/proc/regex_none"),
                       ("(?<!b)a", "aaaa", "/proc/regex_dollar_pre"), ("a", "aaaa", "/proc/regex_null"),
                       ("aaa", "aaaaaaa", "/proc/regex_len")]:
        s.body("Replace proc", [f"var/regex/R = {mk(pat, 'g')}", f"var/r = R.Replace({q(h)}, {pr})"], f"list(r, {ST})")
    # Same with text replacements, for contrast
    for pat, h, r in [("aa", "aaaaaa", ""), ("(?<=a)a", "aaaa", "A"), ("(?<=a)a", "aaaa", "")]:
        s.body("Replace", [f"var/regex/R = {mk(pat, 'g')}", f"var/r = R.Replace({q(h)}, {q(r)})"], f"list(r, {ST})")
