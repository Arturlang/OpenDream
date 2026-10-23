"""replacetext / replacetextEx / replacetext_char / replacetextEx_char, splittext / splittext_char, jointext.

BYOND reference notes targeted here:
- replacetext is case-insensitive and adapts the replacement's case to the found text (lowercase needle,
  found text Capitalised or ALL CAPS -> replacement Capitalised / ALL CAPS). replacetextEx is case-sensitive.
- Replacement may be a proc (called with the found text, no case correction). A regex needle behaves
  like regex.Replace(): case/global come from the regex flags.
- Start/End are BYTE positions for the non-_char procs, character positions for _char.
- splittext: "a,,b,c" gives 4 items, "" gives an empty list, regex capture groups go in the list (whole
  match first when include_delimiters), unmatched groups are null, negative Start/End count from the end,
  Start/End do not trim the text.
- jointext: non-text items converted to text, glue only between items, negative Start/End count from
  the end, List.Join is the same thing.
"""
from pools import TEXT, TEXT_S, NUM_S, OTHER
import re
from gen import dm_str

REPLACE = ["replacetext", "replacetextEx", "replacetext_char", "replacetextEx_char"]
SPLIT = ["splittext", "splittext_char"]

D = dm_str

NEEDLE_S = [D(t) for t in ["", "a", "A", "b", "abc", ",", "é", "🙂", "zz"]]
REPL_S = [D(t) for t in ["", "X", "xy", "aa", "é", "🙂"]] + ["null", "1"]
POS_S = ["0", "1", "2", "3", "-1", "-2", "100", "null"]
DELIM_S = [D(t) for t in ["", ",", "a", "b", "é", "🙂", "zz"]] + ['regex(",")']
INCL = ["0", "1", "2", "-1", "0.5", "null", D("1")]

LISTS = [
    "list()", 'list("a")', 'list("a", "b", "c")', 'list(1, 2.5, null, "x")', 'list("a" = 1, "b" = 2)',
    'list(list(1, 2), "x")', "list(/datum, new /datum)", "list(PINF, NINF, NAN)", "list(1e7, 16777217, 0.1, -0)",
    'list("é", "日本", "🙂")', 'list("", "", "")', "list(null, null)", 'list("a" = list(1), "b")',
    D("plain text"), "null", "5", "new /datum",
]
GLUE = [D(t) for t in ["", ",", ", ", "é", "[x]"]] + ["null", "1", "list()"]

RE_W = '"(\\\\w)(\\\\w*)"'      # DM source "(\\w)(\\w*)" -> pattern (\w)(\w*)


def build(s):
    # ---------------------------------------------------------------- replacetext family
    for p in REPLACE:
        # Arity (BYOND checks builtin argument counts at compile time)
        s.case(p, f'{p}()')
        s.case(p, f'{p}("abc")')
        s.case(p, f'{p}("abc", "b")')
        s.case(p, f'{p}("abc", "b", "X", 1, 0, 1)')
        if p in ("replacetext", "replacetextEx"):
            # Every haystack x needle, fixed replacement; all-pairs over haystack/needle/replacement
            # (the _char variants only differ from these once positions are given)
            hays = TEXT_S + [D(t) for t in ["Hello World", "The Cat", "Ünïcödé", "a.b", "A,B,,C", "aBc", "🙂A🙂a"]]
            s.sweep(p, [hays if p == "replacetext" else TEXT_S, NEEDLE_S], fmt=lambda h, n, p=p: f'{p}({h}, {n}, "<X>")')
            s.sweep(p, [TEXT_S + ["null", "5"], NEEDLE_S, REPL_S])
        # All-pairs with Start/End
        s.sweep(p, [TEXT_S, NEEDLE_S, REPL_S, POS_S, POS_S])
        # Wrong-type arguments in every position
        for o in OTHER + NUM_S[:3]:
            s.case(p, f'{p}({o}, "a", "X")')
            s.case(p, f'{p}("banana", {o}, "X")')
            s.case(p, f'{p}("banana", "a", {o})')
            s.case(p, f'{p}("banana", "a", "X", {o})')
            s.case(p, f'{p}("banana", "a", "X", 1, {o})')
        for c in [
            # Case adaptation
            '"One on one", "one", "two"', '"ONE on one", "one", "two"', '"oNe ONe onE", "one", "two"',
            '"One on one", "One", "two"', '"One on one", "ONE", "two"', '"One on one", "one", "TWO"',
            '"One on one", "one", "tWo"', '"One", "one", "2wo"', '"One", "one", "two words"',
            '"HELLO WORLD", "hello world", "goodbye moon"', '"Hello World", "hello world", "goodbye moon"',
            '"Hello world", "hello world", "goodbye moon"', '"A", "a", "bc"', '"AB", "ab", "cd"',
            '"Ab", "ab", "cd"', '"aB", "ab", "cd"', '"1A", "1a", "bc"', '"1AB", "1ab", "cd"',
            '"Éa", "éa", "xy"', '"ÉA", "éa", "xy"', '"Straße", "STRASSE", "x"', '"I", "i", "you"',
            # Replacement containing / overlapping the needle
            '"aaa", "a", "aa"', '"abab", "ab", "b"', '"aaaa", "aa", "b"', '"aaa", "aa", "a"',
            '"abc", "abc", ""', '"abc", "abcd", "X"', '"", "a", "X"', '"", "", "X"', '"", "", ""',
            # Empty needle
            '"abc", "", "-"', '"abc", "", ""', '"é日", "", "-"', '"🙂🙂", "", "-"',
            '"abc", "", "-", 2', '"abc", "", "-", 1, 3', '"abc", "", "-", 2, 2', '"abc", "", "-", -1',
            '"abc", "", "-", 0', '"abc", "", "-", 4', '"abc", "", "-", 1, -1',
            # Start / End
            '"aaaaa", "a", "b", 2', '"aaaaa", "a", "b", 2, 4', '"aaaaa", "a", "b", 4, 2',
            '"aaaaa", "a", "b", 0', '"aaaaa", "a", "b", -2', '"aaaaa", "a", "b", -100',
            '"aaaaa", "a", "b", 1, -1', '"aaaaa", "a", "b", 1, -100', '"aaaaa", "a", "b", 6',
            '"aaaaa", "a", "b", 7', '"aaaaa", "a", "b", 1, 6', '"aaaaa", "a", "b", 1, 100',
            '"aaaaa", "a", "b", 2.5, 3.5', '"aaaaa", "a", "b", 3, 3', '"abcabc", "abc", "X", 2',
            '"abcabc", "abc", "X", 1, 6', '"abcabc", "abc", "X", 1, 7', '"abcabc", "abc", "X", 4, 7',
            '"abcabc", "abc", "X", 1, 3', '"abcabc", "abc", "X", 1, 4', '"abcabc", "abc", "X", null, null',
            # Multibyte: byte vs character positions
            '"éaéa", "a", "X", 2', '"éaéa", "a", "X", 3', '"éaéa", "a", "X", 4', '"éaéa", "a", "X", 1, 3',
            '"éaéa", "a", "X", 1, 4', '"éaéa", "é", "X", 2', '"éaéa", "é", "X", 4', '"éaéa", "é", "X", -2',
            '"日本日本", "本", "X", 2', '"日本日本", "本", "X", 4', '"日本日本", "本", "X", 1, -3',
            '"🙂a🙂a", "a", "X", 2', '"🙂a🙂a", "a", "X", 5', '"🙂a🙂a", "🙂", "X", 3', '"🙂a🙂a", "🙂", "X", -3',
            '"ÉÉé", "é", "x"', '"日本語", "本", "🙂"',
            # Specials that must not be interpreted
            '"a.b.c", ".", "-"', '"a*b", "*", "x"', '"a$b", "$", "$$"', '"a\\\\b", "\\\\", "/"',
            '"a\\[b\\]", "\\[", "("', '"x\\ny", "\\n", " "', '"a%b", "%", "%25"',
        ]:
            s.case(p, f"{p}({c})")
        # Regex needle (behaves as regex.Replace)
        for c in [
            'regex("o", "g"), "0"', 'regex("o"), "0"', 'regex("O", "gi"), "0"', 'regex("O", "g"), "0"',
            f'regex({RE_W}, "g"), "$2$1"', 'regex("o+", "g"), "<$0>"', 'regex("o+", "g"), "<$&>"',
            'regex("w", "g"), "\\[$`|$\'\\]"', 'regex("o", "g"), "$$"', 'regex("(x)?o", "g"), "<$1>"',
            'regex("x*", "g"), "-"', 'regex("", "g"), "-"', 'regex("^", "g"), ">"', 'regex("$"), "<"',
            'regex("o", "g"), "$9"', 'regex("o", "g"), null', 'regex("o", "g"), 7',
            'regex("o", "g"), /proc/parity_canon', 'regex("o", "g"), "X", 6', 'regex("o", "g"), "X", 1, 6',
            'regex("o", "g"), "X", -4', 'regex("o", "g"), "X", 0',
        ]:
            s.case(p, f'{p}("foo bar wood", {c})')
        s.case(p, f'{p}("é日本é", regex("é", "g"), "e", 2)')
        s.case(p, f'{p}("é日本é", regex("."), "X")')
        s.case(p, f'{p}("é日本é", regex(".", "g"), "X", 3)')
        s.case(p, f'{p}("🙂x🙂", regex("x"), "🙃")')
        s.case(p, f'{p}(null, regex("o"), "X")')
        s.case(p, f'{p}(5, regex("5"), "X")')
        # Proc replacement: found text passed in, no case correction
        for c in ['"One on one", "one"', '"ONE", "one"', '"abc", ""', '"aXa", "x"', '"é日é", "é"']:
            s.case(p, f"{p}({c}, /proc/parity_canon)")
        s.case(p, f'{p}("abc", "b", /proc/parity_canon, 3)')
        # Side effects: the haystack variable is not changed
        s.body(p, ['var/t = "abcabc"', f'var/r = {p}(t, "b", "X")'], "list(t, r)")
        # Very long strings
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "ab"', f'var/r = {p}(t, "b", "xyz")'],
               'list(length(r), copytext(r, 1, 13), copytext(r, -12), findtext(r, "b"))')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 500) t += "é日"', f'var/r = {p}(t, "日", "", 100, -100)'],
               "list(length(r), length_char(r), copytext_char(r, 1, 60), copytext_char(r, -60))")
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 300) t += "Aa"', f'var/r = {p}(t, "", "-")'],
               "list(length(r), copytext(r, 1, 20), copytext(r, -20))")

    # ---------------------------------------------------------------- splittext family
    for p in SPLIT:
        s.case(p, f'{p}()')
        s.case(p, f'{p}("a,b")')
        s.case(p, f'{p}("a,b", ",", 1, 0, 1, 1)')
        if p == "splittext":
            s.sweep(p, [TEXT_S + [D("a b  c"), D("line1\nline2"), D(" padded  "), D("abcabc")], DELIM_S])
        s.sweep(p, [TEXT_S, DELIM_S, POS_S, POS_S, INCL])
        s.sweep(p, [[D("a,b,,c"), D("é,日,🙂"), D(",")], DELIM_S, INCL],
                fmt=lambda t, d, i, p=p: f"{p}({t}, {d}, 1, 0, {i})")
        for o in OTHER + NUM_S[:3]:
            s.case(p, f'{p}("a,b,c", {o})')
            s.case(p, f'{p}("a,b,c", ",", {o})')
            s.case(p, f'{p}("a,b,c", ",", 1, {o})')
            s.case(p, f'{p}("a,b,c", ",", 1, 0, {o})')
        for c in [
            '"apples,oranges,bananas", ","', '"a,,b,c", ","', '",a,", ","', '",", ","', '",,", ","',
            '"", ","', '"", ""', '"abc", ""', '"abc", "abcd"', '"abc", "abc"', '"a::b::c", "::"',
            '"a:::b", "::"', '"aXbxc", "x"', '"aXbxc", "X"', '"aaa", "aa"', '"a b  c", " "',
            '"line1\\nline2\\n", "\\n"', '"é日本é", "日"', '"é日本é", "é"', '"🙂x🙂", "🙂"', '"🙂x🙂", "x"',
            # include_delimiters with string delimiters
            '"a,b,c", ",", 1, 0, 1', '",a,", ",", 1, 0, 1', '"a,,b", ",", 1, 0, 1', '"abc", "", 1, 0, 1',
            '"", ",", 1, 0, 1', '"a::b", "::", 1, 0, TRUE',
            # Start / End: no trimming
            '"a,b,c,d", ",", 3', '"a,b,c,d", ",", 4', '"a,b,c,d", ",", 1, 4', '"a,b,c,d", ",", 1, 5',
            '"a,b,c,d", ",", 3, 6', '"a,b,c,d", ",", 6, 3', '"a,b,c,d", ",", -3', '"a,b,c,d", ",", -100',
            '"a,b,c,d", ",", 1, -2', '"a,b,c,d", ",", 1, -100', '"a,b,c,d", ",", 0', '"a,b,c,d", ",", 8',
            '"a,b,c,d", ",", 9', '"a,b,c,d", ",", 100', '"a,b,c,d", ",", 1, 8', '"a,b,c,d", ",", 1, 100',
            '"a,b,c,d", ",", 2.5, 5.5', '"a,b,c,d", ",", 3, 3', '"a,b,c,d", ",", 3, 6, 1',
            '"a,b,c,d", ",", -3, 0, 1', '"a,b,c,d", ",", null, null', '"abcabc", "bc", 3',
            '"abcabc", "bc", 1, 3', '"abcabc", "bc", 1, 4',
            # Multibyte positions
            '"é,é,é", ",", 2', '"é,é,é", ",", 3', '"é,é,é", ",", 4', '"é,é,é", ",", 1, 3',
            '"é,é,é", ",", 1, 4', '"é,é,é", ",", -2', '"日,本,語", ",", 4', '"日,本,語", ",", 5',
            '"日,本,語", ",", 1, -4', '"🙂,🙂,🙂", ",", 5', '"🙂,🙂,🙂", ",", 6', '"🙂,🙂,🙂", ",", 2, -1',
            # Regex delimiter
            '"a,b,c", regex(",")', '"a,b,c", regex("(,)")', '"a,b;c", regex("(,)|(;)")',
            '"a,b;c", regex("(,)|(;)"), 1, 0, 1', '"a,b,c", regex("(,)"), 1, 0, 1', '"a,b,c", regex(","), 1, 0, 1',
            '"a  b \\t c", regex("\\\\s+")', '"abc", regex("")', '"abc", regex("x*")', '"aXbxc", regex("x", "i")',
            '"aXbxc", regex("x")', '"a,b,c", regex(",", "g")', '"a1b22c333", regex("\\\\d+")',
            '"a1b22c333", regex("(\\\\d)(\\\\d)?")', '"a1b22c333", regex("(\\\\d)(\\\\d)?"), 1, 0, 1',
            '",a,", regex(",")', '"", regex(",")', '"a,b,c,d", regex(","), 3', '"a,b,c,d", regex(","), 1, 5',
            '"a,b,c,d", regex(","), -3, 0, 1', '"é,日,🙂", regex(",")', '"é,日,🙂", regex(","), 3',
            '"é日🙂", regex(".")', '"é日🙂", regex("(.)")',
        ]:
            s.case(p, f"{p}({c})")
        s.case(p, f'{p}(null, regex(","))')
        s.case(p, f'{p}(123, "2")')
        # Result is a fresh list
        s.body(p, [f'var/list/L = {p}("a,b", ",")', 'L += "c"', 'L[1] = "z"'], "L")
        s.body(p, [f'var/list/A = {p}("a,b", ",")', f'var/list/B = {p}("a,b", ",")'], "list(A == B, A ~= B, A.len)")
        # Long input
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 1500) t += "x[i],"', f'var/list/L = {p}(t, ",")'],
               "list(L.len, L[1], L[1500], L[1501])")
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 400) t += "日é"', f'var/list/L = {p}(t, "é", 50, -50)'],
               "list(L.len, length(L[1]), length(L[L.len]), L[2])")
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 500) t += "ab"', f'var/list/L = {p}(t, "")'],
               "list(L.len, L[1], L[L.len])")

    # ---------------------------------------------------------------- jointext
    p = "jointext"
    s.case(p, "jointext()")
    s.case(p, 'jointext(list("a", "b"))')
    s.case(p, 'jointext(list("a", "b"), ",", 1, 0, 1)')
    s.sweep(p, [LISTS, GLUE])
    s.sweep(p, [LISTS[:13], GLUE[:4], POS_S, POS_S])
    L5 = 'list("a", "b", "c", "d", "e")'
    for c in [
        "1", "2", "5", "6", "7", "0", "-1", "-5", "-6", "-100", "100", "1.5", "2.9", "null", '"2"',
        "1, 3", "2, 2", "3, 2", "1, 6", "1, 7", "1, -1", "1, -4", "1, -5", "1, -6", "-2, 0", "-2, -1",
        "2, 100", "null, null", "0, 0", "6, 6", "1, 0.5", "1, 5.9",
    ]:
        s.case(p, f'jointext({L5}, "-", {c})')
        s.body("list.Join", [f'var/list/L = {L5}'], f'L.Join("-", {c})')
    for c in [
        'list("a"), ","', 'list(), ","', 'list(""), ","', 'list("a", ""), ","', 'list(1, 2, 3), 0',
        'list(1, 2, 3), 2.5', 'list(0.1 + 0.2, 1/3, 1e-7, 123456789, -1.5), ","', 'list(1e38, 1e39, -1e39), ","',
        'list(/datum, /obj, /list), ","', 'list(new /datum, new /list, list()), ","',
        'list("a" = "x", "b" = null), ","', 'list(list(list("deep"))), ","', 'list("<b>", "&amp;", "\\[x\\]"), ","',
        'list("a\\nb", "\\t"), ","', 'alist(1 = "a", 2 = "b"), ","', 'alist("k" = 1, 5 = 2), "|"',
        'list("é", "日", "🙂"), "🙂"', '"é", ","', '"", ","', '"abc", ",", 2', '"abc", ",", 1, 2',
    ]:
        s.case(p, f"jointext({c})")
    # Wrong-type list argument / glue
    for o in OTHER + NUM_S[:3]:
        s.case(p, f'jointext({o}, ",")')
        s.case(p, f'jointext(list("a", "b"), {o})')
        s.case(p, f'jointext(list("a", "b"), ",", {o})')
        s.case(p, f'jointext(list("a", "b"), ",", 1, {o})')
    # Typed vars / side effects
    s.body(p, ['var/list/L = list("a", "b")', 'var/r = jointext(L, ",")', 'L += "c"'], "list(r, L.len)")
    s.body(p, ['var/datum/D = new', 'var/list/L = list(D, D)'], 'jointext(L, "|")')
    s.body(p, ['var/list/L = list()', 'L.len = 3'], 'jointext(L, ",")')
    s.body(p, ['var/list/L = list("a", "b", "c")', 'L.Cut(2, 3)'], 'jointext(L, ",")')
    s.body(p, ['var/list/L = list()', 'L["k"] = "v"', 'L[1] = "k2"'], 'jointext(L, ",")')
    s.body(p, ['var/list/L = list()', 'for(var/i in 1 to 3000) L += i'],
           'list(length(jointext(L, ",")), copytext(jointext(L, ","), -14), length(jointext(L, "", 100, -100)))')
    s.body(p, ['var/list/L = list()', 'for(var/i in 1 to 500) L += "日é"', 'var/r = jointext(L, "🙂")'],
           "list(length(r), length_char(r), copytext_char(r, 1, 8))")
    # Round trips
    s.case(p, 'jointext(splittext("a,,b,c", ","), ",")')
    s.case(p, 'jointext(splittext("é,日,🙂", ","), "|")')
    s.case(p, 'jointext(splittext("a1b2c", regex("(\\\\d)")), "")')

    build_gaps(s)


_CALLED = re.compile(r"(replacetextEx_char|replacetext_char|replacetextEx|replacetext|splittext_char|splittext|jointext)")


def build_gaps(s):
    """Cases added for gaps a review found. User procs can't be declared from a spec, so replacement
    procs are the lib's: parity_canon(v, depth) (text "t:..."; a group lands in depth), parity_num(n)
    (text "n~n") and parity_skipped(id) (returns the number 0).
    BYOND rejects builtin procs (/proc/uppertext, /datum/proc/Topic) as values at compile time.
    No lib proc returns null, a list or a datum, or reports its args/src (needs a framework hook for top-level DM)."""
    HAY = '"foo bar wood"'
    # ---- regex needle + proc replacement: capture groups as arguments
    for p in REPLACE:
        for rx in ['regex("(o)(x)?", "g")', 'regex("(o)(x)?")', 'regex("(x)?(o)", "g")', 'regex("(o)(o)", "g")',
                   'regex("o", "g")', 'regex("(?<n>o)", "g")']:
            for pr in ["/proc/parity_canon", "/proc/parity_num"]:
                s.case(p, f'{p}("foo bar", {rx}, {pr})')
    # Replacement procs that return non-text: null, number, list, datum; string and regex needles
    for pq in ["replacetext", "replacetextEx"]:
        for pr in ["/proc/parity_skipped", "/proc/parity_num"]:
            for n in ['"o"', '"O"', 'regex("o", "g")', 'regex("o")', 'regex("O", "gi")']:
                s.case(pq, f'{pq}({HAY}, {n}, {pr})')
    # String needle + proc: called ("b~b", 0, "") or stringified ("/proc/parity_num")?
    for pq in REPLACE:
        s.case(pq, f'{pq}("abc", "b", /proc/parity_skipped)')
        s.case(pq, f'{pq}("abc", "b", /proc/parity_num)')
        s.case(pq, f'{pq}("One on one", "one", /proc/parity_num)')
        s.case(pq, f'{pq}("abc", "", /proc/parity_num)')
        s.case(pq, f'{pq}("abcb", "b", /proc/parity_skipped, 3)')

    # ---- regex datum state after replacetext
    for pq in REPLACE:
        for flags in ['', ', "g"', ', "i"', ', "gi"']:
            s.body(pq, [f'var/regex/R = regex("o"{flags})', f'var/r = {pq}({HAY}, R, "0")'],
                   "list(r, R.next, R.index, R.text, R.match, R.group)")
            s.body(pq, [f'var/regex/R = regex("(o)(x)?"{flags})', f'var/r = {pq}({HAY}, R, "0", 3)'],
                   "list(r, R.next, R.index, R.text, R.match, R.group)")
            s.body(pq, [f'var/regex/R = regex("z"{flags})', f'var/r = {pq}({HAY}, R, "0")'],
                   "list(r, R.next, R.index, R.text, R.match)")
        # Global regex: Start defaults to src.next
        s.body(pq, ['var/regex/R = regex("o", "g")', f'R.Find({HAY})', f'var/r = {pq}({HAY}, R, "0")'],
               "list(r, R.next, R.index)")
        s.body(pq, ['var/regex/R = regex("o", "g")', f'R.Find({HAY})', f'R.Find({HAY})', f'var/r = {pq}({HAY}, R, "0")'],
               "list(r, R.next, R.index)")
        s.body(pq, ['var/regex/R = regex("o", "g")', f'R.Find({HAY})', f'var/r = {pq}({HAY}, R, "0", 1)'],
               "list(r, R.next, R.index)")
        s.body(pq, ['var/regex/R = regex("o")', f'R.Find({HAY})', f'var/r = {pq}({HAY}, R, "0")'],
               "list(r, R.next, R.index)")
        # Twice in a row with the same regex
        for flags in ['', ', "g"']:
            s.body(pq, [f'var/regex/R = regex("o"{flags})', f'var/a = {pq}({HAY}, R, "0")', f'var/b = {pq}({HAY}, R, "0")'],
                   "list(a, b, R.next, R.index)")
            s.body(pq, [f'var/regex/R = regex("o"{flags})', f'var/a = {pq}({HAY}, R, "0")', f'var/b = R.Replace({HAY}, "1")'],
                   "list(a, b, R.next, R.index)")
    # regex.Replace directly, for comparison
    for flags in ['', ', "g"']:
        s.body("regex.Replace", [f'var/regex/R = regex("o"{flags})', f'var/r = R.Replace({HAY}, "0")'],
               "list(r, R.next, R.index, R.text, R.match)")
        s.body("regex.Replace", [f'var/regex/R = regex("o"{flags})', f'var/r = R.Replace({HAY}, "0", 3, 10)'],
               "list(r, R.next, R.index, R.text, R.match)")

    # ---- regex needle + End (match may extend past End), Start>1 with End, negative End
    for pq in REPLACE:
        for rx in ['regex("o+", "g")', 'regex("o+")']:
            for se in ["1, 3", "1, 4", "2, 3", "3, 0"]:
                s.case(pq, f'{pq}("foooo bar", {rx}, "X", {se})')
        for rx in ['regex("o", "g")', 'regex("o")', 'regex("o+", "g")']:
            for se in ["3, 10", "5, 9", "3, 3", "10, 3", "1, -3", "-6, -2", "-6, 0", "-1, -1", "2, -100", "1, 100"]:
                s.case(pq, f'{pq}({HAY}, {rx}, "X", {se})')
        # Anchors relative to Start/End
        for rx in ['regex("^.", "g")', 'regex(".$", "g")', 'regex("\\\\b\\\\w", "g")']:
            for se in ["5, 0", "5, 8"]:
                s.case(pq, f'{pq}({HAY}, {rx}, "X", {se})')

    # ---- .NET-only substitution tokens (BYOND documents $0-$9, $&, $`, $', $$)
    for pq in REPLACE:
        for rep in ["${1}", "$_", "$+", "$10", "$1$2", "$2$1", "$3", "${n}", "$<n>", "$", "a$", "\\1", "$$1",
                    "$0$0", "$11", "$01", "${0}", "$ 1", "$a"]:
            s.case(pq, f'{pq}("foo boo", regex("(o)(o)", "g"), {D(rep)})')
        for rep in ["${n}", "$<n>", "$1", "$+"]:
            s.case(pq, f'{pq}("foo boo", regex("(?<n>o)(o)", "g"), {D(rep)})')

    # ---- splittext: regex delimiter state, negative End, End cutting a match, groups
    for pq in SPLIT:
        for rx in ['regex("(,)")', 'regex("(,)", "g")', 'regex(",")', 'regex("z")', 'regex("(,)(x)?")']:
            for extra in ["", ", 1, 0, 1", ", 3"]:
                s.body(pq, [f'var/regex/R = {rx}', f'var/list/L = {pq}("a,b,c", R{extra})'],
                       "list(L, R.index, R.next, R.match, R.group, R.text)")
        for c in ['"a,b,c,d", regex(","), 1, -2', '"a,b,c,d", regex(","), 2, -1, 1', '"a,b,c,d", regex(","), -4, -2',
                  '"a,b,c,d", regex(","), 1, -100', '"a,b,c,d", regex(","), 4, 2',
                  '"a::b::c", regex("::"), 1, 3', '"a::b::c", regex("::"), 1, 2', '"a::b::c", regex("::"), 1, 4',
                  '"a::b::c", regex("::"), 1, 3, 1', '"a::b::c", regex(":+"), 1, 3',
                  '"a::b::c", "::", 1, 3', '"a::b::c", "::", 1, 2', '"a::b::c", "::", 1, 4', '"a::b::c", "::", 1, 3, 1',
                  '"a::b::c", "::", 3, 5', '"a::b::c", "::", 3, -3',
                  '"a1b2c", regex("(\\\\d)(?=c)")', '"a1b2c", regex("(?<=b)(\\\\d)")', '"a-b_c", regex("((-)|(_))")',
                  '"a-b_c", regex("((-)|(_))"), 1, 0, 1', '"a-b_c", regex("(-)|_")', '"a12b", regex("((\\\\d)(\\\\d))")',
                  '"abab", regex("(?=b)")', '"abab", regex("(?=a)")', '"abab", regex("(?=b)"), 1, 0, 1',
                  '"abab", regex("\\\\b")', '"abab", regex("^")', '"abab", regex("$")',
                  '"a1x2b", regex("(\\\\d)x(\\\\d)"), 1, 0, 1', '"a1x2b", regex("(\\\\d)x(\\\\d)")',
                  '"a1x2b3x4c", regex("(\\\\d)x(?:\\\\d)"), 1, 0, 1', '"a1x2b", regex("(?<l>\\\\d)x(?<r>\\\\d)")',
                  '"a,b", regex("(,)", "i"), 1, 0, 1',
                  '"é,日,🙂", regex(","), 1, -5', '"é::日::🙂", regex("::"), 1, 5', '"é::日::🙂", "::", 2, 4']:
            s.case(pq, f"{pq}({c})")

    # ---- named arguments (spelling and case of the parameter names)
    named = [
        'replacetext(Haystack = "abc", Needle = "b", Replacement = "X")', 'replacetext("aaaaa", "a", "b", End = 3)',
        'replacetext("aaaaa", "a", "b", start = 3)', 'replacetext_char("ééé", "é", "e", Start = 2)',
        'splittext("a,b", ",", include_delimiters = 1)', 'splittext(Text = "a,b", Delimiter = ",")',
        'splittext_char("é,é", ",", Start = 2)',
        'jointext(List = list(1, 2), Glue = "-")', 'jointext(list(1, 2, 3), "-", End = 3)',
        'jointext(list(1, 2, 3), "-", start = 2)',
    ]
    # ---- call()() indirect calls, with missing / extra args (arity is otherwise only compile-time)
    calls = [
        # BYOND rejects call(/proc/<builtin>) at compile time; call("name") compiles
        'call(/proc/replacetext)("abc", "b", "X")', 'call(/proc/jointext)(list(1, 2), ",")',
        'call("replacetext")("abc", "b", "X")', 'call("replacetext")("abc", "b")', 'call("replacetext")("abc")',
        'call("replacetext")()', 'call("replacetext")("abc", "b", "X", 1, 0, 1, 2)', 'call("replacetext")("abc", "b", "X", 2, 3)',
        'call("replacetextEx")("aBc", "B", "X")', 'call("replacetext_char")("ééé", "é", "e", 2)',
        'call("replacetextEx_char")("ééé", "é", "e", 1, 3)', 'call("replacetext")("foo", regex("o", "g"), "0")',
        'call("replacetext")(Haystack = "abc", Needle = "b", Replacement = "X")',
        'call("replacetext")("One on one", "one", /proc/parity_num)',
        'call("splittext")("a,b", ",")', 'call("splittext")("a,b")', 'call("splittext")()',
        'call("splittext")("a,b", ",", 1, 0, 1, 9)', 'call("splittext_char")("é,é", ",", 2)',
        'call("splittext")("a,b", regex("(,)"), 1, 0, 1)', 'call("splittext")(Text = "a,b", Delimiter = ",")',
        'call("jointext")(list(1, 2), ",")', 'call("jointext")(list(1, 2))', 'call("jointext")()',
        'call("jointext")(list(1, 2, 3), ",", 2, 0, 9)', 'call("jointext")("abc", ",")',
        'call("jointext")(List = list(1, 2), Glue = "-")', 'call("JoinText")(list(1, 2), ",")',
    ]
    for c in named + calls:
        s.case((_CALLED.search(c) or _CALLED.search(c.lower())).group(1), c)
    s.body("list.Join", ['var/list/L = list(1, 2, 3)'], 'L.Join(Glue = "-", Start = 2)')
    s.body("list.Join", ['var/list/L = list(1, 2, 3)'], 'L.Join("-", End = 3)')

    # ---- jointext: named objects, text macros
    p = "jointext"
    s.body(p, ['var/obj/O = new', 'O.name = "Bob"', 'var/mob/M = new', 'var/obj/O2 = new', 'O2.name = "rock"'],
           'jointext(list(O, M, O2), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "\\improper rock"', 'var/obj/O2 = new', 'O2.name = "\\proper Bob"'],
           'jointext(list(O, O2), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "\\the rock"'], 'jointext(list(O, "x"), ",")')
    s.case(p, 'jointext(list("\\improper rock", "\\proper Bob"), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "rock"'], 'jointext(list("\\the [O]", "\\a [O]", "[O]"), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "Bob"'], 'jointext(list("a" = O, O = "b"), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = null'], 'jointext(list(O, "x"), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = 5'], 'jointext(list(O, "x"), ",")')
    s.case(p, 'jointext(list(new /obj, new /mob, new /image, new /regex, new /exception), ",")')
    s.body(p, ['var/turf/T = locate(1, 1, 1)'], 'jointext(list(T, T.loc), ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "rock"'], 'jointext(list(O, O), O)')
    s.body(p, ['var/obj/O = new', 'var/datum/D = new'], 'jointext(list(D, D.type, O.type), "|")')

    # ---- jointext / Join on special lists
    s.body(p, ['var/turf/T = locate(1, 1, 1)', 'var/obj/A = new(T)', 'A.name = "a1"', 'var/obj/B = new(T)', 'B.name = "b1"'],
           'jointext(T.contents, ",")')
    s.body("list.Join", ['var/turf/T = locate(1, 1, 1)', 'var/obj/A = new(T)', 'A.name = "a1"'], 'T.contents.Join("|")')
    s.body("list.Join", ['var/obj/O = new', 'O.overlays += "x"', 'O.overlays += "y"'],
           'list(length(O.overlays.Join(",")), O.overlays.len)')
    s.body(p, ['var/obj/O = new', 'O.overlays += "x"'], 'length(jointext(O.overlays, ","))')
    s.body(p, ['var/datum/D = new', 'var/j = jointext(D.vars, ",")'],
           'list(findtext(j, "type") > 0, findtext(j, "vars") > 0, length(splittext(j, ",")) == D.vars.len)')
    s.body("list.Join", ['var/datum/D = new', 'var/list/V = D.vars', 'var/j = V.Join(",")'],
           'list(findtext(j, "type") > 0, length(splittext(j, ",")) == V.len)')
    # args of the generated chunk proc (called with no arguments), then a copy with mixed items
    s.body(p, [], 'jointext(args, ",")')
    s.body("list.Join", [], 'args.Join(",")')
    s.body(p, ['var/list/A = args.Copy()', 'A += 1', 'A += "a"', 'A += null'], 'jointext(A, ",")')

    # ---- jointext: alist / number- and object-keyed assoc lists, Start/End on every list-arg kind
    for L in ['alist(1 = "a", 2 = "b", 3 = "c")', 'alist("x" = 1, "y" = 2, "z" = 3)', 'list("x" = 1, "y" = 2, "z" = 3)',
              'list(1, 2, 3)', D("abc"), D("é日🙂"), "null", "5", "new /datum"]:
        for se in ["2", "1, -1", "-2, 0", "3, 2", "4"]:
            s.case(p, f'jointext({L}, ",", {se})')
    for se in ['"-", 1, -1', '"-", 2', '"-"', '"-", 2, 3']:
        s.body("list.Join", ['var/alist/A = alist(1 = "a", 2 = "b", 3 = "c")'], f'A.Join({se})')
    s.body(p, ['var/datum/D = new', 'var/list/L = list()', 'L[D] = "v"', 'L[/datum] = "w"'], 'jointext(L, ",")')
    s.body(p, ['var/obj/O = new', 'O.name = "k"', 'var/list/L = list()', 'L[O] = "v"'], 'jointext(L, ",")')

    # ---- case adaptation with Start/End and non-letters
    for pq in ["replacetext", "replacetextEx"]:
        for c in ['"One ONE one", "one", "two", 2', '"One ONE one", "one", "two", 5, 8', '"One ONE one", "one", "two", 5',
                  '"One ONE one", "one", "two", 1, 4', '"One ONE one", "one", "two", -3', '"One ONE one", "ONE", "two", 2',
                  '" HELLO", " hello", " bye"', '" Hello", " hello", " bye"', '"1HELLO", "1hello", "bye"',
                  '"-Hello-", "-hello-", "x"', '"ONE", "one", "x"', '"One", "one", "x"', '"ONE", "one", ""',
                  '"ONE", "one", "1x"', '"O", "o", "xyz"', '"oO", "o", "x"', '"A.B", "a.b", "c.d"', '"A", "a", "é"',
                  '"É", "é", "x"', '"ÉCOLE", "école", "school"']:
            s.case(pq, f"{pq}({c})")

    # ---- regex needle + End on multibyte text: character vs byte End on the regex path
    for pq in REPLACE:
        for c in ['"é日本é", regex(".", "g"), "X", 2, 4', '"é日本é", regex("."), "X", 2, 4', '"é日本é", regex(".", "g"), "X", 2, -1',
                  '"é日本é", regex(".", "g"), "X", -2', '"é日本é", regex(".", "g"), "X", -3, -1',
                  '"🙂a🙂a", regex("a", "g"), "X", 1, -1', '"🙂a🙂a", regex("a", "g"), "X", 2, 3', '"🙂a🙂a", regex("a", "g"), "X", 3',
                  '"🙂a🙂a", regex("🙂", "g"), "X", 2', '"🙂a🙂a", regex(".", "g"), "X", 2, 4', '"🙂a🙂a", regex("a"), "X", 3, 0']:
            s.case(pq, f"{pq}({c})")
