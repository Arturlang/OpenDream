"""Case conversion, key canonicalisation, comparison, trimming and span procs.

lowertext uppertext ckey ckeyEx cmptext cmptextEx sorttext sorttextEx trimtext
spantext spantext_char nonspantext nonspantext_char
"""
from pools import TEXT, TEXT_S, NUM_S, POS, OTHER
from gen import dm_str

# Case mapping beyond ASCII: sharp s, ligature, Turkish i, titlecase digraph, Greek sigma,
# Cyrillic, fullwidth, and characters with no case
CASE_RAW = [
    "straße", "STRASSE", "ﬁne", "İstanbul", "ıi", "ǅǆǄ", "ΣΑΣ", "σας", "Привет", "ПРИВЕТ",
    "ＡＢＣａｂｃ", "ÀÉÎÕÜ", "àéîõü", "Ω", "µ", "ÿ", "Ÿ", "123!?", "@#$%^&*()", "a_b-c.d",
    "Mr. T-Bone_99", "a[b]\\c`d@e^f", "{curly}|~", "tab\there", "  Spaced Key  ",
]
CASE = [dm_str(t) for t in CASE_RAW]
# Text macros (raw DM source: dm_str would escape the backslash)
MACRO = ['"\\proper Bob"', '"\\improper bob"', '"\\improper Bob"', '"\\proper"']

# Whitespace of every kind for trimtext
WS_RAW = [" ", "  x  ", "\tx\t", "\nx\n", " a b ", "\t\n ", "x"] + [
    chr(c) + "x" + chr(c) for c in (0xA0, 0x2003, 0x3000, 0x200B, 0x202F, 0xFEFF, 0x1680, 0x180E, 0x2000, 0x200A)
] + [chr(0xA0), chr(0x2000) + chr(0x2001) + chr(0x2002) + "x" + chr(0x2009)]
WS = [dm_str(t) for t in WS_RAW] + [
    '"[ascii2text(13)]x[ascii2text(13)]"', '"[ascii2text(11)]x[ascii2text(12)]"',
    '"[ascii2text(28)]x[ascii2text(31)]"', '"[ascii2text(133)]x[ascii2text(133)]"',
    '"[ascii2text(8232)]x[ascii2text(8233)]"', '"[ascii2text(127)]x"',
]

# Short pools for multi-argument sweeps
CMP_S = [dm_str(t) for t in ["", "a", "A", "abc", "b", "é", "É", "🙂"]]
WRONG_S = ["null", "1", "new /datum"]
# 3-argument sweeps: case pairs, a miss, multibyte, empty
CMP3_S = [dm_str(t) for t in ["", "a", "A", "b", "é", "🙂"]]
NEEDLE_S = [dm_str(t) for t in ["", "a", "ab", "b ", "é", "🙂", ", "]] + ["null", "1"]
SPAN_HAY_S = TEXT_S + ["null", "5"]

SINGLE = ["lowertext", "uppertext", "ckey", "ckeyEx", "trimtext"]
CMP = ["cmptext", "cmptextEx"]
SORT = ["sorttext", "sorttextEx"]
SPAN = ["spantext", "spantext_char", "nonspantext", "nonspantext_char"]


def long_body(var, unit, n):
    return [f'var/{var} = ""', f"for(var/__i in 1 to {n})", f"\t{var} += {unit}"]


CMP_CASES = [
    '"a", "a", "a", "a"', '"a", "A", "a", "A", "a"', '"a", "a", "a", "b"', '"b", "a", "a", "a"',
    '"", ""', '"", null', 'null, ""', 'null, null', '1, 1', '1, "1"', '"1", 1', '0, null',
    'NAN, NAN', '/datum, "/datum"', '"/datum", /datum', 'list(), list()',
    '"\\proper Bob", "bob"', '"\\improper bob", "Bob"', '"\\proper Bob", "\\improper Bob"',
    '"Bob", "\\proper Bob"', '"é", "É"', '"ÀÉÎ", "àéî"', '"straße", "STRASSE"', '"ΣΑΣ", "σας"',
    '"ΣΑΣ", "σασ"', '"İ", "i"', '"ı", "I"', '"ǅ", "ǆ"', '"Привет", "ПРИВЕТ"',
    '"ＡＢＣ", "ａｂｃ"', '"a", "a "', '"a", "a[ascii2text(0)]"', '"🙂", "🙂"',
    '"[1]", "1"', '"x[null]", "x"', '"_", "_"', '"@", "`"', '"\\[", "{"',
]

SORT_CASES = [
    '"a", "b", "c"', '"c", "b", "a"', '"a", "c", "b"', '"b", "a", "c"', '"a", "a", "b"',
    '"b", "a", "a"', '"a", "a", "a"', '"a", "b", "c", "d"', '"d", "c", "b", "a"',
    '"a", "b", "b", "c"', '"a", "B", "c"', '"A", "b", "C"', '"C", "b", "A"',
    '"a", "a"', '"A", "a"', '"a", "A"', '"ab", "abc"', '"abc", "ab"', '"", "a"', '"a", ""',
    '"_", "a"', '"a", "_"', '"_", "A"', '"A", "_"', '"\\[", "a"', '"Z", "\\["', '"`", "a"',
    '"{", "a"', '"~", "Z"', '"0", "A"', '"9", "10"', '"10", "9"', '" ", "a"', '"a ", "a"',
    '"é", "f"', '"f", "é"', '"É", "é"', '"é", "É"', '"z", "é"', '"日", "本"', '"🙂", "日"',
    '"a[ascii2text(0)]", "a"', '"\\proper Bob", "bob"', '"\\improper Bob", "Bob"',
    '1, 2', '2, 1', '"1", 2', 'null, "a"', '"a", null', 'null, null', '"a", null, "b"',
    '"b", null, "a"', '"a", 1, "b"', '/datum, "a"', '"a", /datum', 'NAN, "a"',
    '"apple", "Banana", "cherry"', '"Apple", "banana", "Cherry"',
]

SPAN_CASES = [
    # documented examples
    '"apples, oranges", ", ", 7', '"apples, oranges", ", "', '"apples, oranges", ", ", -9',
    # case sensitivity
    '"AAa", "a"', '"AAa", "A"', '"aAa", "aA"',
    # needle order / duplicates
    '"abcabc", "cba"', '"abcabc", "aaaa"', '"   x", " "', '"x   ", " "',
    # starts
    '"aaab", "a", 0', '"aaab", "a", 1', '"aaab", "a", 2', '"aaab", "a", 4', '"aaab", "a", 5',
    '"aaab", "a", 6', '"aaab", "a", -1', '"aaab", "a", -2', '"aaab", "a", -4', '"aaab", "a", -5',
    '"aaab", "a", -50', '"aaab", "a", 1.5', '"aaab", "a", 1.9', '"aaab", "a", 2.5',
    '"aaab", "a", -0.5', '"aaab", "a", 0.5', '"aaab", "a", null', '"aaab", "a", "2"',
    '"aaab", "a", NAN', '"aaab", "a", PINF', '"aaab", "a", NINF', '"aaab", "a", list()',
    '"", "a", 1', '"", "", 1', '"", "a", -1', '"", "a", 0',
    # multibyte: byte index vs char index
    '"éé", "é"', '"éa", "é"', '"éa", "a"', '"aé", "a"', '"éé", "é", 2', '"éé", "é", 3',
    '"éé", "é", -1', '"éé", "é", -2', '"aéa", "a", 2', '"aéa", "a", 3', '"aéa", "a", 4',
    '"aéa", "é", 2', '"aéa", "é", 3', '"éè", "é"', '"èé", "é"', '"é", ascii2text(195)',
    '"日本日", "日本"', '"日本x", "日"', '"日本x", "x", 3', '"日本x", "x", 7', '"日本x", "x", -1',
    '"🙂🙂x", "🙂"', '"🙂🙂x", "🙂", 2', '"🙂🙂x", "🙂", 5', '"🙂🙂x", "x", 3', '"🙂🙂x", "x", 9',
    '"🙂🙂x", "x", -1', '"🙂🙂x", "x", -2', '"x🙂", "🙂", -1', '"x🙂", "🙂", -4',
    # combining sequences / grapheme clusters
    '"éé", "e"', '"éé", "é"', '"éx", "́"',
    '"👍🏽x", "👍"', '"👍🏽x", "👍🏽"',
    # wrong-type haystack/needles
    'null, "a"', '"a", null', 'null, null', '1, "1"', '11, "1"', '"11", 1', '"aab", list("a")',
    'list("a"), "a"', 'new /datum, "/"', '/datum, "/"', '"/datum", /datum',
    # macros and embedded expressions
    '"\\proper Bob", "B"', '"[1][2]x", "12"', '"a[ascii2text(0)]b", "a[ascii2text(0)]"',
]


def build(s):
    # ---------- single-argument procs ----------
    for p in SINGLE:
        s.sweep(p, [TEXT + CASE + MACRO + OTHER + NUM_S])
        s.case(p, f"{p}()")
        s.case(p, f'{p}("a", "b")')
        for a in ["NAN", "NINF", "1e7", "-0.5", "/obj", '"[1]"', '"x[null]y"', '"x[new /datum]y"',
                  "ascii2text(0)", '"a[ascii2text(0)]B"']:
            s.case(p, f"{p}({a})")
        # The result is a new string; the source var is untouched
        s.body(p, ['var/t = " Ab C "', f"var/u = {p}(t)"], "list(t, u)")
        # Very long input
        s.body(p, long_body("t", '" Ab-C_é "', 5000), f"length({p}(t))")
        s.body(p, long_body("t", '"aB"', 3000) + [f"var/u = {p}(t)"],
               "list(length(u), copytext(u, 1, 9), copytext(u, -8))")
    # Named arguments with the documented names
    s.case("lowertext", 'lowertext(T = "AbC")')
    s.case("uppertext", 'uppertext(T = "AbC")')
    s.case("ckey", 'ckey(Key = "A B")')
    s.case("ckeyEx", 'ckeyEx(Text = "A B")')
    s.case("trimtext", 'trimtext(Text = " a ")')

    # trimtext: every kind of whitespace
    s.sweep("trimtext", [WS])
    s.body("trimtext", long_body("t", '" "', 4000) + ['t += "x"'] + long_body("v", '" "', 4000) + ["t += v"],
           "trimtext(t)")

    # ckey/ckeyEx: which characters survive
    for p in ("ckey", "ckeyEx"):
        s.body(p, ["var/out = list()", "for(var/c in 1 to 127)",
                   f"\tif(length({p}(ascii2text(c)))) out += c"], "out")
        s.body(p, ["var/out = list()", "for(var/c in 128 to 1000)",
                   f"\tif(length({p}(ascii2text(c)))) out += c"], "out")
        for a in ["Ünïcödé Kéy", "日本 語", "🙂 Smile 🙂", "Guest-1234567", "some_key-name"]:
            s.case(p, f"{p}({dm_str(a)})")
    # Case mapping table over the first code points
    for p in ("lowertext", "uppertext"):
        s.body(p, ["var/out = list()", "for(var/c in 1 to 127)",
                   f"\tvar/r = text2ascii({p}(ascii2text(c)))",
                   '\tif(r != c) out += "[c]>[r]"'], "out")
        s.body(p, ["var/out = list()", "for(var/c in 128 to 1200)",
                   f"\tvar/r = {p}(ascii2text(c))",
                   '\tif(r != ascii2text(c)) out += "[c]>[text2ascii(r)]:[length(r)]"'], "out")

    # ---------- cmptext / cmptextEx ----------
    for p in CMP:
        s.sweep(p, [CMP_S + WRONG_S, CMP_S + WRONG_S], min_args=1)
        s.sweep(p, [CMP3_S, CMP3_S, CMP3_S], min_args=3)
        s.case(p, f"{p}()")
        for args in CMP_CASES:
            s.case(p, f"{p}({args})")
        s.body(p, long_body("t", '"aB"', 4000) + long_body("u", '"Ab"', 4000), f"{p}(t, u)")
        s.body(p, long_body("t", '"aB"', 4000) + long_body("u", '"aB"', 4000), f"{p}(t, u)")
        s.case(p, f'{p}(arglist(list("x", "X", "x")))')
        s.case(p, f'{p}(arglist(list()))')

    # ---------- sorttext / sorttextEx ----------
    for p in SORT:
        s.sweep(p, [CMP_S + WRONG_S, CMP_S + WRONG_S], min_args=1)
        s.sweep(p, [CMP3_S, CMP3_S, CMP3_S], min_args=3)
        s.case(p, f"{p}()")
        for args in SORT_CASES:
            s.case(p, f"{p}({args})")
        s.body(p, long_body("t", '"a"', 4000) + ['var/u = t + "b"'], f"list({p}(t, u), {p}(u, t))")
        s.case(p, f'{p}(arglist(list("a", "b", "c")))')
        s.case(p, f'{p}(arglist(list("a")))')
        # Order of printable ASCII: adjacent characters, and each against "A" and "a"
        s.body(p, ["var/out = list()", "for(var/c in 32 to 126)",
                   f"\tout += {p}(ascii2text(c), ascii2text(c + 1))"], "out")
        s.body(p, ["var/out = list()", "for(var/c in 32 to 126)",
                   f'\tout += {p}("A", ascii2text(c))'], "out")
        s.body(p, ["var/out = list()", "for(var/c in 32 to 126)",
                   f'\tout += {p}("a", ascii2text(c))'], "out")

    # ---------- spantext / nonspantext and _char variants ----------
    for p in SPAN:
        s.sweep(p, [SPAN_HAY_S, NEEDLE_S], min_args=2)
        s.sweep(p, [TEXT_S, NEEDLE_S[:7], POS], min_args=3)
        s.case(p, f"{p}()")
        s.case(p, f'{p}("abc")')
        s.case(p, f'{p}("abc", "a", 1, 2)')
        s.case(p, f'{p}(Haystack = "aab", Needles = "a")')
        s.case(p, f'{p}("aab", "a", Start = 2)')
        for args in SPAN_CASES:
            s.case(p, f"{p}({args})")
        s.body(p, long_body("t", '"ab"', 5000) + ['t += "c"'],
               f'list({p}(t, "ab"), {p}(t, "c"), {p}(t, "ab", -1))')
        s.body(p, long_body("t", '"é"', 3000) + ['t += "x"'],
               f'list({p}(t, "é"), {p}(t, "x"), {p}(t, "é", -2))')
        s.body(p, ['var/t = "aab"', f'var/r = {p}(t, "a")'], "list(t, r)")


# ---------- gap coverage (second pass) ----------
def U(c):
    """DM source for one code point."""
    return f"ascii2text({c})"


# Canonically equivalent / compatibility / ignorable-character pairs (DM source, two args)
EQUIV_PAIRS = [
    ('"é"', f'"e[{U(769)}]"'), (U(197), U(8491)), ('"ﬁ"', '"fi"'), (U(233), f'"e[{U(769)}]"'),
    ('"ab"', f'"a[{U(173)}]b"'), ('"ab"', f'"a[{U(8203)}]b"'), ('"ab"', f'"a[{U(8205)}]b"'),
    ('"ab"', f'"a[{U(65039)}]b"'), ('"ab"', f'"ab[{U(173)}]"'), ('"ab"', f'"[{U(8203)}]ab"'),
    ('"Ω"', U(8486)), ('"K"', U(8490)), ('"µ"', '"μ"'), ('"ｱ"', '"ア"'), ('"①"', '"1"'),
]
EQUIV_PAIRS_CI = [
    ('"É"', f'"e[{U(769)}]"'), ('"AB"', f'"a[{U(173)}]b"'), (U(197), U(8491)), (U(229), U(8491)),
    ('"AB"', f'"a[{U(8203)}]b"'), ('"AB"', f'"a[{U(8205)}]b"'), ('"AB"', f'"a[{U(65039)}]b"'),
    ('"FI"', '"ﬁ"'), ('"ω"', U(8486)), ('"k"', U(8490)), ('"SS"', '"ß"'), ('"ss"', U(7838)),
]

# Text macros stored as marker bytes in BYOND
MACRO2 = ['"\\red Hi"', '"\\bold Hi"', '"\\the Bob"', '"\\a apple"', '"\\an Apple"', '"\\The Bob"',
          '"\\A Apple"', '"[1]\\th"', '"[2]\\th"', '"[2] apple\\s"', '"[1] apple\\s"', '"\\roman[3]"',
          '"\\Roman[14]"', '"x\\icon[null]y"', '"\\he"', '"\\proper Bob \\improper Bob"',
          '"\\proper"', '"\\improper"', '"\\proper  "', '"  \\improper"', '"\\proper \\red X"']

# A sorttext result r as one character, in DM
SORT_SYM = '(r == 1 ? ">" : (r == -1 ? "<" : (r == 0 ? "=" : "?")))'


def runs_body(lo, hi, test):
    """Code points c in lo..hi for which test (DM, uses ch) is true, as compressed runs."""
    return (["var/out = list()", "var/start = 0", "var/prev = 0", f"for(var/c in {lo} to {hi})",
             "\tvar/ch = ascii2text(c)", f"\tif({test})",
             "\t\tif(!start) start = c", "\t\tprev = c",
             "\telse if(start)", '\t\tout += (start == prev ? "[start]" : "[start]-[prev]")', "\t\tstart = 0",
             'if(start) out += (start == prev ? "[start]" : "[start]-[prev]")'], "out")


def build_gaps(s):
    # cmptext / cmptextEx: canonical equivalence and ignorable characters
    for a, b in EQUIV_PAIRS:
        s.case("cmptextEx", f"cmptextEx({a}, {b})")
        s.case("cmptextEx", f"cmptextEx({b}, {a})")
        s.case("cmptext", f"cmptext({a}, {b})")
        s.case("sorttextEx", f"sorttextEx({a}, {b})")
    for a, b in EQUIV_PAIRS_CI:
        s.case("cmptext", f"cmptext({a}, {b})")
        s.case("cmptext", f"cmptext({b}, {a})")
        s.case("sorttext", f"sorttext({a}, {b})")

    # Non-text values after position 2, and late mismatches
    for args in ['"a", "a", null', '"a", "A", 1', '"a", "a", new /datum', '"1", "1", 1', '"a", "a", /datum',
                 '"a", "a", list("a")', '"a", "A", "a", "A", "b"', '"a", "A", "a", "b", "A"',
                 '"a", "a", "a", "a", null', '"", "", null', 'null, null, null', '"a", "a", ""']:
        for p in CMP:
            s.case(p, f"{p}({args})")
    # Named arguments
    for e in ['cmptext(T1 = "a", T2 = "A")', 'cmptext("a", T2 = "b")', 'cmptext("a", T2 = "A")',
              'cmptext(T2 = "A", T1 = "a")', 'cmptext(T1 = "a")',
              'cmptext(arglist(list("T1" = "a", "T2" = "A")))', 'cmptext(arglist(list("T1" = "a", "T2" = "b")))']:
        s.case("cmptext", e)
        s.case("cmptextEx", e.replace("cmptext(", "cmptextEx("))

    # Documented reference examples
    s.case("sorttext", 'sorttext("A", "B")')
    s.case("sorttextEx", 'sorttextEx("a", "B")')
    s.case("cmptext", 'cmptext("Hi", "HI")')
    s.case("cmptextEx", 'cmptextEx("Hi", "HI")')
    s.case("lowertext", 'lowertext("HI THERE")')
    s.case("uppertext", 'uppertext("hi there")')

    # cmptextEx(T1, T2) == (T1 == T2)
    pairs = [('"\\proper Bob"', '"Bob"'), ('"\\improper Bob"', '"Bob"'), ('"\\proper Bob"', '"\\improper Bob"'),
             ('"a"', f'"a[{U(0)}]"'), (f'"a[{U(0)}]"', f'"a[{U(0)}]"'), (f'"a[{U(0)}]b"', f'"a[{U(0)}]c"'),
             ('"a"', '"a"'), ('"a"', '"A"'), ('""', "null"), ("1", '"1"')] + EQUIV_PAIRS
    for a, b in pairs:
        s.case("cmptextEx", f"list(cmptextEx({a}, {b}), {a} == {b})")

    # Sort order where UTF-16 ordinal and UTF-8 byte order disagree; positions 3+
    for p in SORT:
        for a, b in [('"🙂"', '"ｚ"'), ('"ｚ"', '"🙂"'), ('"🙂"', U(57344)), (U(57344), '"🙂"'),
                     ('"🙂"', U(65533)), (U(65533), '"🙂"'), ('"𐐀"', U(65535)), ('"🙂"', U(55296)),
                     (U(0x10FFFF), U(0xFFFF)), ('"ä"', '"Ä"'), ('"Ä"', '"b"'), ('"ä"', '"B"'), ('"ÿ"', '"Ÿ"')]:
            s.case(p, f"{p}({a}, {b})")
        for args in ['"a", "b", null', '"a", "b", 1', '"a", "b", "c", "a"', '"c", "b", "a", "z"',
                     '"a", "b", "B"', '"a", "b", new /datum', '"a", "b", "c", "c"', '"a", "b", "c", "b"',
                     '"b", "a", null']:
            s.case(p, f"{p}({args})")
        for e in [f'{p}(T1 = "a", T2 = "b")', f'{p}(T2 = "a", T1 = "b")', f'{p}("b", T2 = "a")',
                  f'{p}(arglist(list("T1" = "b", "T2" = "a")))']:
            s.case(p, e)
        # Non-ASCII ordering sweep: five symbols per code point, one body per 128-code-point chunk
        ranges = [(lo, min(lo + 127, 1200)) for lo in range(128, 1201, 128)] + [(0x3000, 0x3010), (0xFF00, 0xFF60)]
        for lo, hi in ranges:
            s.body(p, ['var/out = ""', f"for(var/c in {lo} to {hi})", "\tvar/ch = ascii2text(c)",
                       f'\tvar/r = {p}("a", ch)', f"\tout += {SORT_SYM}",
                       f'\tr = {p}("z", ch)', f"\tout += {SORT_SYM}",
                       f'\tr = {p}("é", ch)', f"\tout += {SORT_SYM}",
                       f'\tr = {p}("É", ch)', f"\tout += {SORT_SYM}",
                       f"\tr = {p}(ch, ascii2text(c + 1))", f"\tout += {SORT_SYM}",
                       '\tout += " "'], "out")

    # Case mapping above U+1200 and in the supplementary planes
    hi_ranges = [(0x1E00, 0x1EFF), (0x1F00, 0x1FFF), (0x2160, 0x2188), (0x24B6, 0x24E9), (0x10A0, 0x10FF),
                 (0x1C90, 0x1CBF), (0x13A0, 0x13FF), (0xAB70, 0xABBF), (0x2C00, 0x2C7F), (0xA640, 0xA69F),
                 (0xFF21, 0xFF5A), (0x10400, 0x1044F), (0x1E900, 0x1E943), (0x1D400, 0x1D433)]
    for p in ("lowertext", "uppertext"):
        for lo, hi in hi_ranges:
            s.body(p, ["var/out = list()", f"for(var/c in {lo} to {hi})", f"\tvar/r = {p}(ascii2text(c))",
                       '\tif(r != ascii2text(c)) out += "[c]>[text2ascii(r)]:[length(r)]"'], "out")
        for ch in ["ẞ", "ᾈ", "ᾀ", "Ⅻ", "ⅻ", "Ⓐ", "ⓐ", "Ⴀ", "ⴀ", "Ა", "Ꭰ", "ꭰ", "𐐀", "𐐨", "𞤀", "𝐀", "ŉ", "ǰ", "ΐ"]:
            s.body(p, [f"var/r = {p}({dm_str(ch)})"], "list(r, length(r), length_char(r), text2ascii(r))")
    # Decomposed input
    for p, src in [("lowertext", f'"E[{U(769)}]"'), ("uppertext", f'"e[{U(769)}]"'),
                   ("lowertext", f'"A[{U(778)}]B"'), ("uppertext", f'"a[{U(778)}]b"')]:
        s.body(p, [f"var/r = {p}({src})"],
               "list(r, length(r), length_char(r), text2ascii(r, 1), text2ascii(r, 2), text2ascii(r, 3), "
               "text2ascii_char(r, 1), text2ascii_char(r, 2))")

    # Text macros other than \proper/\improper
    for p in SINGLE:
        for m in MACRO2:
            s.body(p, [f"var/r = {p}({m})"], "list(r, length(r))")
        # The ref's id differs per run and the proc may strip the brackets the diff masks on, so record only its shape
        s.body(p, ["var/datum/d = new", f'var/r = {p}("\\ref[d]")'], 'list(istext(r), findtext(r, "0x") > 0)')
    # Whitespace next to a text macro, and more Unicode whitespace
    for src in ['" \\proper Bob "', '"\\proper   Bob  "', '"\\improper  "', '"  \\improper Bob"',
                '"\\the  Bob "', '" \\red Hi "']:
        s.body("trimtext", [f"var/r = trimtext({src})"], "list(r, length(r))")
    for src in [f'"[{U(c)}]x[{U(c)}]"' for c in (0x2007, 0x2008, 0x205F, 0x2028, 0x2029, 0x85)] + \
               [f'"x[{U(0xA0)}]x"', f'"[{U(0x2028)}]"', f'"x[{U(0)}]"', f'"[{U(0)}] x "',
                f'"[{U(0)}]"', f'" [{U(0)}] "', f'"[{U(0x200B)}]"', f'"[{U(0xFEFF)}]x"']:
        s.body("trimtext", [f"var/r = trimtext({src})"], "list(r, length(r))")

    # ckey / ckeyEx above 1000
    for p in ("ckey", "ckeyEx"):
        s.body(p, *runs_body(1001, 0x3100, f"length({p}(ch))"))
        s.body(p, *runs_body(0xFF00, 0xFFFD, f"length({p}(ch))"))
        for ch in ["𐐀", "𝐀", "👨‍👩‍👧", "🙂", "a‍b", "aéb", "Ａ"]:
            s.body(p, [f"var/r = {p}({dm_str(ch)})"], "list(r, length(r))")
    for src in ['"a@b"', f'"a[{U(91)}]b"', '"a\\\\b"', '"a\\]b"', '"a^b"', '"a`b"', '"a_b"', '"a-b"', '"a.b"',
                '"a{b"', '"a|b"', '"a~b"', f'"A[{U(64)}]Z"', f'"a[{U(127)}]b"', f'"a[{U(93)}]b"']:
        s.case("ckeyEx", f"ckeyEx({src})")
        s.case("ckey", f"ckey({src})")

    # _char variants: Start just past the character count
    for args in ['"🙂🙂x", "🙂", 4', '"🙂🙂x", "x", 4', '"👍🏽x", "x", 2', '"👍🏽x", "x", 3', '"👍🏽x", "x", 4',
                 f'"e[{U(769)}]x", "x", 2', f'"e[{U(769)}]x", "x", 3', '"🙂🙂x", "x", 3', '"🙂🙂x", "x", 5',
                 '"🙂🙂x", "x", 6', '"🙂🙂x", "x", -1', '"🙂🙂x", "🙂", -3']:
        for p in ("spantext_char", "nonspantext_char"):
            s.case(p, f"{p}({args})")
    for args in ['"🙂🙂x", "x", 2', '"🙂🙂x", "x", -2', '"🙂a🙂", "🙂", 2', f'"e[{U(769)}]e", {U(769)}',
                 '"👍🏽x", "🏽"', '"👍🏽x", "x"', '"🙂a🙂", "a", 3', '"🙂a🙂", "🙂", -1']:
        for p in ("nonspantext_char", "spantext_char"):
            s.case(p, f"{p}({args})")
    # Lone surrogate needles
    for p in SPAN:
        for args in [f'"🙂", {U(55357)}', f'"🙂", {U(56898)}', f'"🙂x", {U(55357)}', f'"x🙂", {U(55357)}']:
            s.case(p, f"{p}({args})")
    # Named-argument permutations
    for p in SPAN:
        for e in [f'{p}(Needles = "a", Haystack = "aab")', f'{p}("aab", Start = 2)',
                  f'{p}("aab", Needles = "a", Start = -1)', f'{p}(Start = 2, Haystack = "abc", Needles = "c")',
                  f'{p}(arglist(list("Haystack" = "aab", "Needles" = "a")))']:
            s.case(p, e)
    # Multibyte needles that share UTF-8 lead bytes with the haystack
    for p in SPAN:
        for args in ['"è", "é"', '"日", "本"', '"è", "è"', '"èx", "é"', '"日本", "本"', '"本日", "日"',
                     '"aè", "é", 2', '"ü", "ö"', '"🙂", "🙃"', '"🙂🙃", "🙃"']:
            s.case(p, f"{p}({args})")


_build_first = build


def build(s):
    _build_first(s)
    build_gaps(s)
