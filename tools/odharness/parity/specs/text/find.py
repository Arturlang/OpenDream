"""findtext family: findtext, findtextEx, findlasttext, findlasttextEx and their _char variants.

BYOND reference points targeted here:
- Forward procs: (Haystack, Needle, Start=1, End=0); End is the byte after the last one searched,
  negative Start/End count from the end ("findtext("Banana", "na", -3)" searches the final "ana").
- Backward procs: (Haystack, Needle, Start=0, End=1); Start is where the backward search begins,
  End is the earliest position that can be a match.
- findtext/findlasttext are case-insensitive, the Ex forms case-sensitive.
- Non-_char procs count BYTES of the UTF-8 text, _char procs count characters.
- Forward procs accept a /regex Needle (its own flags decide case, the match may extend past End,
  and Find() sets the regex's index/match/group/next). Backward procs document that a regex Needle
  is NOT allowed.

OpenDream divergences these cases aim at (DreamProcNativeRoot.cs, _Standard.dm):
- OD indexes by UTF-16 code unit in every variant (no byte counting, emoji count as 2).
- OD's _Standard.dm declares findlasttextEx_char(..., Start = 1, End = 0), not 0/1.
- OD returns 1 when both Haystack and Needle are non-text, 0 for an empty Needle, and 0 whenever
  Start > length or Start == 0 on the forward procs.
- OD's findtextEx uses InvariantCulture comparison (not ordinal), findtext OrdinalIgnoreCase
  (folds non-ASCII case); findlasttextEx adds needle length to its count a second time.
"""
from pools import TEXT_S, NEEDLE, OTHER
from gen import dm_str

FWD = ["findtext", "findtextEx"]
BWD = ["findlasttext", "findlasttextEx"]
BASE = FWD + BWD
CHAR = [p + "_char" for p in BASE]
ALL = BASE + CHAR
FWD_ALL = FWD + [p + "_char" for p in FWD]

# Haystacks for the generic two-argument sweep (TEXT_S plus some extra shapes)
HAY2 = TEXT_S + [dm_str(t) for t in ["Hello World hello", "aXbXaXb", "line1\nline2"]]
# Wrong-type values plus numbers
WRONG = OTHER + ["123", "-1.5"]

# Multibyte haystacks/needles for the _char procs' two-argument sweep
MB_HAY = [dm_str(t) for t in ["", "abc", "é日本", "🙂x🙂", "Ünïcödé", "日本語テキスト", "aéaéa",
                              "ÉCOLE école", "x🙂🙂y"]]
MB_NEEDLE = [dm_str(t) for t in ["", "x", "é", "É", "ü", "本", "テキ", "🙂", "🙂🙂", "zz"]]

# Start values for three-argument sweeps on a fixed ASCII haystack (len 9)
START_A = ["0", "1", "2", "3", "5", "9", "10", "-1", "-9", "-100", "1.5", "null", "NAN", '"2"']
# Start/End grid on that haystack
GRID_A = ["0", "1", "3", "7", "10", "-1", "-3"]

# The multibyte haystack: "é日本🙂é日本🙂" is 8 characters, 24 bytes
# (é=2 bytes at 1, 日=3 at 3, 本=3 at 6, 🙂=4 at 9, é at 13, 日 at 15, 本 at 18, 🙂 at 21)
MB = dm_str("é日本🙂é日本🙂")
START_MB = ["0", "1", "2", "3", "4", "6", "9", "15", "25", "-1", "-4", "-12", "-25"]
GRID_MB = ["0", "1", "3", "9", "15", "-1", "-12"]

Q = '"'


def q(t):
    return dm_str(t)


def build(s):
    # ---- generic sweeps -------------------------------------------------------------------------
    for p in BASE:
        # findtext and findlasttextEx get the full needle pool, the other two a subset
        needles = NEEDLE if p in ("findtext", "findlasttextEx") else NEEDLE[:6] + NEEDLE[10:14]
        s.sweep(p, [HAY2 if p == "findtext" else TEXT_S, needles], min_args=2)
    for p in CHAR:
        s.sweep(p, [MB_HAY, MB_NEEDLE if "Ex" not in p else MB_NEEDLE[:3] + MB_NEEDLE[5:8]], min_args=2)
        for h in ["Hello World", "aaa"]:
            for n in ["O", "aa", ""]:
                s.call(p, q(h), q(n))

    # Wrong types in either position, and arity / argument forms
    for p in ALL:
        for w in WRONG:
            s.call(p, w, q("a"))
            s.call(p, q("abc"), w)
            if w in ("null", "list()", "123"):
                s.call(p, w, w)
        s.call(p, q("abc"), q("b"), q("2"), q("0"))
        s.call(p, q("abc"), q("b"), "list()")
        s.call(p, q("abc"), q("b"), "1", "new /datum")
        s.call(p, q("abc"))
        s.call(p)
        s.call(p, q("abc"), q("b"), "1", "0", "1")
        s.case(p, f'{p}(Haystack = "abcabc", Needle = "c")')
        s.case(p, f'{p}("abcabc", "c", End = 4)')
        s.case(p, f'{p}("abcabc", "c", Start = 4)')
        s.case(p, f'{p}(Needle = "b", Haystack = "abcb")')

    # Start sweeps (three arguments) and Start/End grids on fixed haystacks
    for p in ALL:
        s.sweep(p, [[q("abcabcabc")], [q("bc")], START_A], min_args=3)
        s.sweep(p, [[q("Banana")], [q("NA")], ["0", "1", "3", "4", "-1", "-2", "-3", "-6", "-7"]],
                min_args=3)
        s.sweep(p, [[q("abcabcabc")], [q("")], ["0", "1", "5", "9", "10", "11", "-1", "-9", "-10"]],
                min_args=3)
        # Multibyte positions: byte counting (base) vs character counting (_char)
        s.sweep(p, [[MB], [q("日本")], START_MB], min_args=3)
        s.sweep(p, [[MB], [q("🙂")], ["0", "1", "5", "9", "10", "13", "21", "-1", "-4", "-5"]], min_args=3)
        if p in ("findtext", "findlasttext", "findlasttextEx"):
            s.sweep(p, [[q("abcabcabc")], [q("bc")], GRID_A, GRID_A], min_args=4)
        if "Ex" not in p:
            s.sweep(p, [[MB], [q("日本")], GRID_MB, GRID_MB], min_args=4)

    # Generic all-pairs over the shared pools with positions (TEXT_S keeps it small)
    POS_S = ["0", "1", "2", "-1", "-3", "100", "null"]
    NEEDLE_S = [q(t) for t in ["", "a", "b", "é", "🙂", "zz"]]
    for p in ["findtext", "findlasttextEx"]:
        s.sweep(p, [TEXT_S, NEEDLE_S, POS_S], min_args=3)

    # ---- documented examples ---------------------------------------------------------------------
    s.call("findtext", q("Hi There"), q("there"))
    s.call("findtextEx", q("Hi There"), q("there"))
    s.call("findtextEx", q("Hi There"), q("There"))
    for p in ALL:
        s.call(p, q("Banana"), q("na"), "-3")
        s.call(p, q("Banana"), q("na"))
        s.call(p, q("Banana"), q("NA"))
        s.call(p, q("Banana"), q("na"), "-3", "-1")
        s.call(p, q("Banana"), q("na"), "3", "6")
        s.call(p, q("Banana"), q("na"), "3", "7")
        s.call(p, q("Banana"), q("na"), "5", "3")

    # ---- hand-picked edges, every proc -----------------------------------------------------------
    for p in ALL:
        # Overlapping matches, needle longer than haystack, needle equal to haystack
        s.call(p, q("aaaa"), q("aa"))
        s.call(p, q("aaaa"), q("aa"), "2")
        s.call(p, q("aaaa"), q("aa"), "3")
        s.call(p, q("aaaa"), q("aa"), "4")
        s.call(p, q("aaaa"), q("aa"), "0", "3")
        s.call(p, q("ab"), q("abc"))
        s.call(p, q("abc"), q("abc"))
        s.call(p, q("abc"), q("ABC"))
        # Match that would end past End / start before End (the backward End is earliest start)
        for a in [("1", "4"), ("1", "5"), ("1", "6"), ("5", "3"), ("4", "3"), ("3", "3"), ("0", "4"),
                  ("-1", "4"), ("-4", "-6")]:
            s.call(p, q("abcdef"), q("cde"), *a)
        # Empty needle against positions and empty haystack
        for a in [[q(""), q("")], [q("abc"), q(""), "2"], [q("abc"), q(""), "3"],
                  [q("abc"), q(""), "4"], [q("abc"), q(""), "5"], [q("abc"), q(""), "-1"],
                  [q("abc"), q(""), "0"], [q(""), q("a"), "1", "0"], [q(""), q(""), "1", "1"]]:
            s.call(p, *a)
        # Case: ASCII and non-ASCII case folding, which BYOND may limit to ASCII
        for h, n in [("ÉCOLE", "é"), ("école", "É"), ("Ünïcödé", "ÜNÏ"), ("STRASSE", "ß"),
                     ("ΣΑΣ", "σ"), ("Kelvin", "K"), ("@[`{", "`"), ("Z", "z")]:
            s.call(p, q(h), q(n))
        # Combining characters vs precomposed: an ordinal search must not match across forms
        s.call(p, q("café"), q("é"))
        s.call(p, q("café"), q("é"))
        # Ignorable code points (culture-aware comparison treats these as ignorable)
        s.call(p, q("a­b"), q("ab"))
        s.call(p, q("a​b"), q("ab"))
        s.call(p, q("ab"), q("­"))
        # Ligatures and width forms (culture-aware comparisons may equate these)
        s.call(p, q("æ"), q("ae"))
        s.call(p, q("ＡＢＣ"), q("ABC"))
        # Embedded escape characters
        s.call(p, q("10.5"), q("."))
        s.call(p, q("a\\b"), q("\\"))
        s.call(p, q("tab\there"), q("\t"))
        s.call(p, q("x\x00y"), q("y"))
        s.call(p, q("x\x00y"), "ascii2text(0)")
        # Regex metacharacters in a text needle are plain text
        for n in [".", "a.c", "(b)", "\\d"]:
            s.call(p, q("a.c*^a(b)[a]\\d|c$"), q(n))
        # Positions that are not whole numbers
        for st in ["1.5", "1.6", "-0.5", "-1.5"]:
            s.call(p, q("abcabc"), q("c"), st)
        s.call(p, q("abcabc"), q("c"), "1", "3.5")
        # Start inside a multibyte character
        for st in ["2", "5", "10"]:
            s.call(p, MB, q("本"), st)
        s.call(p, q("é"), q("é"), "2")
        s.call(p, q("🙂"), q("🙂"), "2")
        s.call(p, q("🙂"), q("🙂"), "1", "4")
        s.call(p, q("🙂"), q("🙂"), "1", "5")
        s.call(p, q("🙂"), q("🙂"), "1", "2")
        for st in ["-1", "-4"]:
            s.call(p, q("x🙂"), q("🙂"), st)
        # Surrogate halves: OD's UTF-16 indexing could match half an emoji
        s.call(p, q("🙂🙃"), q("🙃"))
        s.call(p, q("🙂🙃"), q("🙃"), "2")
        s.call(p, q("🙂🙃"), q("🙂"), "0", "2")

    # Long strings, built in a body so the source stays short
    for p in ALL:
        ab = ['var/t = ""', 'for(var/i in 1 to 5000) t += "ab"', 't += "c"']
        s.body(p, ab, f'{p}(t, "c")')
        mb = ['var/t = ""', 'for(var/i in 1 to 3000) t += "日🙂"', 't += "x"']
        s.body(p, mb, f'{p}(t, "🙂", -10)')
        s.body(p, mb, f'{p}(t, "日", 1000, 2000)')
        s.body(p, ['var/n = ""', 'for(var/i in 1 to 2000) n += "a"', 'var/t = n + "b" + n'],
               f'{p}(t, n + "b")')
        s.body(p, ['var/n = ""', 'for(var/i in 1 to 2000) n += "a"'], f'{p}(n, n + "a")')

    # Arguments are values: a var Haystack is unchanged afterwards
    for p in ALL:
        s.body(p, ['var/h = "AbCabc"', f'var/r = {p}(h, "c")'], 'list(r, h)')

    # ---- regex needles ---------------------------------------------------------------------------
    regex_cases = [
        ('"Hello World"', 'regex("o")'),
        ('"Hello World"', 'regex("O")'),
        ('"Hello World"', 'regex("O", "i")'),
        ('"Hello World"', 'regex("l+")'),
        ('"Hello World"', 'regex("^W")'),
        ('"Hello World"', 'regex("^H")'),
        ('"Hello World"', 'regex("d$")'),
        ('"Hello World"', 'regex("W(or)ld")'),
        ('"Hello World"', 'regex("z")'),
        ('"Hello World"', 'regex("")'),
        ('"Hello World"', 'regex("o", "g")'),
        ('""', 'regex("")'),
        ('""', 'regex("a*")'),
        ('"abc"', 'regex("x*")'),
        ('"Hello World"', 'regex(@"\\s")'),
        ('"Hello World"', 'regex(@"\\bW")'),
        ('"é日本x"', 'regex("x")'),
        ('"é日本x"', 'regex("本")'),
        ('"é日本x"', 'regex(".x")'),
        ('"🙂x🙂"', 'regex("x")'),
        ('"🙂x🙂"', 'regex("🙂", "g")'),
        ('"ÉCOLE"', 'regex("é", "i")'),
        ('null', 'regex("a")'),
        ('123', 'regex("2")'),
    ]
    for p in FWD_ALL:
        for h, r in regex_cases:
            s.call(p, h, r)
        # Positions with a regex: the match may extend past End
        for a in [('regex("cde")', "1", "4"), ('regex("cde")', "1", "3"), ('regex("cde")', "4"),
                  ('regex("c|e")', "4"), ('regex("c|e")', "-2"), ('regex("c|e")', "-5", "-3"),
                  ('regex("^c")', "3"), ('regex("c")', "0"), ('regex("c")', "10")]:
            s.call(p, '"abcdef"', *a)
        s.call(p, '"é日本x"', 'regex("x")', "4")
        s.call(p, '"é日本x"', 'regex("x")', "9")
        s.call(p, '"é日本x"', 'regex("x")', "-1")
        # The regex's vars after the search
        s.body(p, ['var/regex/R = regex("(o)(r?)")', f'var/r = {p}("Hello World", R)'],
               'list(r, R.index, R.match, R.group, R.next, R.text)')
        s.body(p, ['var/regex/R = regex("o", "g")', f'var/a = {p}("Hello World", R)',
                   f'var/b = {p}("Hello World", R)', f'var/c = {p}("Hello World", R)'],
               'list(a, b, c, R.index, R.next)')
        s.body(p, ['var/regex/R = regex("o", "g")', f'var/a = {p}("Hello World", R)',
                   f'var/b = {p}("Hello World", R, 1)'],
               'list(a, b, R.next)')
        s.body(p, ['var/regex/R = regex("z")', f'var/r = {p}("Hello World", R)'],
               'list(r, R.index, R.match, R.group, R.next)')
        s.body(p, ['var/regex/R = regex("(本)")', f'var/r = {p}("é日本x", R)'],
               'list(r, R.index, R.match, R.group, R.next)')
    # Backward procs: a regex Needle is documented as not allowed
    for p in BWD + [x + "_char" for x in BWD]:
        for h, r in regex_cases[:3] + regex_cases[17:18]:
            s.call(p, h, r)
        s.body(p, ['var/regex/R = regex("o")', f'var/r = {p}("Hello World", R)'],
               'list(r, R.index, R.match)')
    # A non-regex datum and regex-looking text are not regexes
    for p in ALL:
        s.call(p, '"Hello World"', '"l+"')
        s.call(p, '"Hello World"', 'new /regex("o")')

    _gaps(s)


def _gaps(s):
    """Cases added for gaps a review found."""
    MBX = q("é日本x本")  # é=1-2, 日=3-5, 本=6-8, x=9, 本=10-12 (bytes); 5 characters
    BWD_ALL = BWD + [x + "_char" for x in BWD]

    # End more negative than the haystack is long (forward procs)
    for p in FWD_ALL:
        for a in [("1", "-100"), ("1", "-9"), ("5", "-8"), ("1", "-8"), ("1", "-10"), ("-100", "-100")]:
            s.call(p, q("abcabcabc"), q("bc"), *a)

    # Backward Start far past the length, and End = 100 for backward procs
    for p in BWD_ALL:
        s.call(p, q("abcabcabc"), q("bc"), "100")
        s.call(p, MB, q("日本"), "100")
        s.call(p, q("abcabcabc"), q("bc"), "0", "100")
        s.call(p, q("abcabcabc"), q("bc"), "100", "100")
        s.call(p, MB, q("日本"), "0", "100")

    # Huge and infinite positions
    for p in ALL:
        for st in ["1e31", "-1e31", "PINF", "NINF", "2147483648"]:
            s.call(p, q("abcabc"), q("c"), st)
        for en in ["PINF", "-1e31", "NINF"]:
            s.call(p, q("abcabc"), q("c"), "0" if p in BWD_ALL else "1", en)
        s.call(p, q("abcabc"), q("c"), "PINF", "NINF")

    # Numeric Needle or Haystack that would match after conversion to text
    for p in ALL:
        for a in [(q("a123b"), "123"), (q("a123b"), "2"), ("1234", q("23")), ("1.5", q(".")),
                  (q("x2x2"), "2"), ("1234", "23"), (q("a1e+31b"), "1e31"), (q("a0.5b"), "0.5")]:
            s.call(p, *a)

    # Text macros that BYOND stores as special bytes
    macro_cases = [('"\\improper Apple"', q("A")), ('"\\proper Bob"', q("Bob")),
                   ('"\\red text"', q("text")), ('"\\the cat"', q("cat")),
                   ('"\\The Cat"', q("Cat")), ('"\\improper Apple"', q("apple")),
                   ('"a\\red b\\blue c"', q("c")), ('"\\proper Bob"', q("p"))]
    for p in ALL:
        for h, n in macro_cases:
            s.call(p, h, n)
        s.body(p, ['var/t = "\\proper Bob"'], f'list({p}(t, "Bob"), length(t), length_char(t))')

    # Indirect calls: call() and arglist(). BYOND's compiler rejects /proc/<builtin> paths and
    # arglist() on these builtins (one case each records that); call("name") compiles.
    for p in ALL:
        s.case(p, f'call(/proc/{p})("abcabc", "c")')
        s.case(p, f'{p}(arglist(list("abcabc", "c", 2)))')
        s.case(p, f'{p}(arglist(list("Haystack" = "abcabc", "Needle" = "c", "Start" = 4)))')
        s.case(p, f'call("{p}")("abcabc", "c")')
        s.case(p, f'call("{p}")("abcabc", "C", 4)')
        s.case(p, f'call("{p}")("abcabc", "c", 1, 4)')
        s.case(p, f'call("{p}")("abcabc")')
        s.case(p, f'call("{p}")(arglist(list("abcabc", "c", 2)))')
        s.case(p, f'call("{p}")(arglist(list("Haystack" = "abcabc", "Needle" = "c", "Start" = 4)))')
        s.body(p, [f'var/n = "{p}"'], 'call(n)("abcabc", "b")')

    # Regex anchors and lookahead at the End boundary; \b at Start
    for p in FWD_ALL:
        for a in [('regex("c$")', "1", "4"), ('regex("c(?=d)")', "1", "4"), ('regex(@"\\bc")', "3"),
                  ('regex("c$")', "1", "3"), ('regex("^c")', "3", "4"), ('regex("c(?!d)")', "1", "4"),
                  ('regex("(?<=b)c")', "3"), ('regex("cdef")', "3", "4"), ('regex(@"c\\b")', "1", "4")]:
            s.call(p, '"abcdef"', *a)

    # Global regex: repeated calls after a miss, setting next by hand, reuse on a shorter haystack
    for p in FWD_ALL:
        s.body(p, ['var/regex/R = regex("o", "g")', 'var/list/L = list()',
                   'for(var/i in 1 to 4)', f'\tL += {p}("Hello World", R)', '\tL += R.next'], 'L')
        s.body(p, ['var/regex/R = regex("o", "g")', 'R.next = 6', f'var/r = {p}("Hello World", R)'],
               'list(r, R.index, R.next)')
        s.body(p, ['var/regex/R = regex("o", "g")', 'R.next = 6', f'var/r = {p}("Hello World", R, 1)'],
               'list(r, R.index, R.next)')
        s.body(p, ['var/regex/R = regex("o", "g")', f'var/a = {p}("Hello World", R)',
                   f'var/b = {p}("Hello World", R)', f'var/c = {p}("Hello", R)', f'var/d = {p}("Hello", R)'],
               'list(a, b, c, d, R.index, R.next)')
        s.body(p, ['var/regex/R = regex("o", "g")', 'R.next = 100', f'var/r = {p}("Hello World", R)'],
               'list(r, R.index, R.next)')
        # Global regex on a multibyte haystack: is next a byte or a character index?
        s.body(p, ['var/regex/R = regex("本", "g")', f'var/a = {p}({MBX}, R)', f'var/b = {p}({MBX}, R)'],
               'list(a, b, R.index, R.next)')
        # State after a miss that follows a hit
        s.body(p, ['var/regex/R = regex("(o)")', f'var/a = {p}("Hello", R)', f'var/b = {p}("zzz", R)'],
               'list(a, b, R.index, R.match, R.group, R.text, R.next)')
        s.body(p, ['var/regex/R = regex("(o)", "g")', f'var/a = {p}("Hello", R)', f'var/b = {p}("zzz", R)'],
               'list(a, b, R.index, R.match, R.group, R.text, R.next)')
        # Empty and non-participating capture groups
        s.body(p, ['var/regex/R = regex("(a*)b")', f'var/r = {p}("b", R)'],
               'list(r, R.group, length(R.group), R.group[1], R.match)')
        s.body(p, ['var/regex/R = regex("(x)?o")', f'var/r = {p}("Hello", R)'],
               'list(r, R.group, length(R.group), R.group[1], R.match)')
        s.body(p, ['var/regex/R = regex("(x)|(o)")', f'var/r = {p}("Hello", R)'],
               'list(r, R.group, length(R.group), R.group[1], R.group[2])')
        # Regex with End on multibyte text
        s.call(p, MBX, 'regex("本")', "1", "3")
        s.call(p, MBX, 'regex("本")', "1", "6")
        s.call(p, MBX, 'regex("本")', "1", "7")
        s.call(p, MBX, 'regex("本")', "7")
        s.call(p, MBX, 'regex("本")', "3")
        s.call(p, q("🙂x🙂"), 'regex("x")', "-2", "0")
        s.call(p, q("🙂x🙂"), 'regex("x")', "-5", "0")
        s.call(p, q("🙂x🙂"), 'regex("🙂")', "2")
        # Non-integer, text, null and list Start/End with a regex needle
        for a in [("3.5",), ('"2"',), ("null",), ("list()",), ("1", "3.5"), ("1", "null"),
                  ("1", '"4"'), ("PINF",), ("NINF",), ("1", "-100")]:
            s.call(p, q("abcabc"), 'regex("c")', *a)

    # Backward Start in the middle of a longer needle's possible match
    for p in BWD_ALL:
        for st in ["8", "9", "10", "11", "12", "0", "-3", "-4"]:
            s.call(p, q("abcdefabcdef"), q("cde"), st)
        for st in ["9", "10", "11"]:
            s.call(p, q("abcdefabcdef"), q("CDE"), st)
            s.call(p, q("abcdefabcdef"), q("cdef"), st)
        s.call(p, q("abcdefabcdef"), q("cde"), "10", "4")
        s.call(p, q("abcdefabcdef"), q("cde"), "10", "3")

    # Case folding of special letters
    for p in ["findtext", "findtextEx", "findlasttext", "findtext_char"]:
        for h, n in [("İstanbul", "i"), ("istanbul", "İ"), ("ı", "I"), ("I", "ı"), ("ǅ", "ǆ"),
                     ("ǅ", "Ǆ"), ("ﬃ", "ffi"), ("ffi", "ﬃ"), ("ſ", "s"), ("Ω", "ω"),
                     ("ẞ", "ß"), ("ÿ", "Ÿ")]:
            s.call(p, q(h), q(n))
