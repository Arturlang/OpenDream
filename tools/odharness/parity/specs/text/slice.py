"""Slicing / length / code-point procs: copytext(_char), splicetext(_char), length(_char), lentext,
text2ascii(_char), ascii2text.

Non-_char procs index by UTF-8 BYTE in BYOND (OD indexes UTF-16 code units, a likely divergence);
_char procs index by character. Cutting inside a multibyte character is documented to produce
U+FFFD for the broken part."""
from pools import TEXT, TEXT_S, NUM, NUM_S, POS, OTHER
from gen import dm_str

# Multibyte strings; the last one has a combining mark (two code points, one grapheme)
MB_RAW = ["é", "aé", "é日本", "🙂x🙂", "a🙂b", "日本語", "Ünïcödé", "x́y"]
MB = [dm_str(t) for t in MB_RAW]

# Positions: POS plus multibyte-relevant byte offsets and odd values
POS_X = POS + ["5", "6", "7", "-3", "-4", "2.5", "-1.5", "NAN", "1e30", "-1e30", '"2"']
# Text to insert into splicetext
INS = [dm_str(t) for t in ["", "X", "é🙂"]] + ["null", "5"]

TEXT_SM = TEXT_S + OTHER
# Small pools for 3+ argument sweeps
TEXT_3 = TEXT_S + ["null", "list()", "new /datum"]
MB_WALK = [dm_str(t) for t in ["aé", "é日本", "🙂x🙂", "x́y"]]
MB_WALK_RAW = ["aé", "é日本", "🙂x🙂", "x́y"]
TEXT_ALL = TEXT + [m for m in MB if m not in TEXT] + OTHER


def blen(t):
    return len(t.encode("utf-8"))


def walk_len(p, t):
    return blen(t) if not p.endswith("_char") else len(t)


def build(s):
    # ---------------- copytext / copytext_char ----------------
    for p in ("copytext", "copytext_char"):
        # BYOND rejects 1-argument copytext at compile time; a few 1-arg cases stay below as parity points
        s.sweep(p, [TEXT_SM + MB[:4], POS], min_args=2)
        s.sweep(p, [TEXT_3, POS, POS], min_args=3)
        # Every start (default end) and every end (start 1) across each multibyte string, incl. mid-character
        for t, src in zip(MB_WALK_RAW, MB_WALK):
            n = walk_len(p, t)
            for i in range(-n - 1, n + 3):
                s.call(p, src, str(i))
                s.call(p, src, "1", str(i))
            # One-unit cuts at every position
            for a in range(2, n + 1):
                s.call(p, src, str(a), str(a + 1))
        for e in ['"Hi there", 1, 3', '"Hi there", 4', '"Hi there", -5', '"abcdef", 4, 2', '"abcdef", 5, -3',
                  '"abcdef", -2, -4', '"abcdef", 3, 3', '"abcdef", 7', '"abcdef", 8', '"abcdef", 7, 7',
                  '"abcdef", -6', '"abcdef", -7', '"abcdef", 1, 7', '"abcdef", 1, 8', '"abcdef", 1, -6',
                  '"abcdef", 1, -7', '"abcdef", 0, 3', '"abcdef", null, 3', '"abcdef", 2, null',
                  '123, 1', '1.5, 2', '-7, 1, 2', '123', 'PINF, 2', '"abc", "2", "3"', '"abc", list(), 2',
                  '"abc", 1, list()', 'null, 0', 'null, 1, 0', 'null, 1, 2', 'null', '"", 1, 1', '""',
                  '"abcdef", NAN', '"abcdef", 1, NAN', '"abcdef", 1e30', '"abcdef", -1e30', '"abcdef", 1, 1e30',
                  '"abcdef", 1, -1e30', '"abcdef", 2.5, 4.5', '"abcdef", -2.5', '"abcdef", 1, 3.9']:
            s.case(p, f"{p}({e})")
        s.case(p, f'{p}(T = "abcdef", Start = 3)')
        s.case(p, f'{p}("abcdef", End = 3)')
        s.case(p, f'{p}(End = 3, T = "abcdef")')
        s.case(p, f'length({p}("é日本", 2))')
        s.case(p, f'istext({p}(null, 1))')
        s.case(p, f'isnull({p}(null, 1, 2))')
        s.case(p, f'{p}("aé日🙂", 2) == "é日🙂"')
        # The source variable is not mutated
        s.body(p, ['var/t = "hello"', f'var/c = {p}(t, 2, 4)'], 't + "|" + c')
        # Long strings
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "ab"'], f'{p}(t, 3999)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'length({p}(t, 1001, 1010))')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'{p}(t, -7)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'{p}(t, 3001, 3005)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 20000) t += "x"'], f'length({p}(t, 2, -2))')

    # ---------------- splicetext / splicetext_char ----------------
    for p in ("splicetext", "splicetext_char"):
        # BYOND rejects 1-argument splicetext at compile time
        s.sweep(p, [TEXT_3, POS], min_args=2)
        s.sweep(p, [TEXT_S + ["null"], POS, POS, INS], min_args=3)
        for t, src in zip(MB_WALK_RAW, MB_WALK):
            n = walk_len(p, t)
            for i in range(-n - 1, n + 3):
                s.call(p, src, str(i), "0", '"|"')
                s.call(p, src, str(i), str(i + 1), '"|"')
        for e in ['"banana", 3, 6, "laclav"', '"banana", 6, 3, "laclav"', '"banana", -4, -1, "X"',
                  '"banana", -1, -4, "X"', '"banana", 0, 0, "X"', '"banana", 0, 3, "X"', '"banana", 3, 0, "X"',
                  '"banana", 10, 20, "X"', '"banana", -10, 2, "X"', '"banana", -100, 100, "X"',
                  '"banana", 7, 7, "X"', '"banana", 8, 8, "X"', '"banana", 6, 6, "X"', '"banana", 1, 1, "X"',
                  '"banana", 2.5, 4.5, "X"', '"banana", "2", "4", "X"', '"banana", 2, 4, list("a")',
                  '"banana", 2, 4, new /datum', '"banana", 2, 4, 1.5', '"banana", 2, 4, null', '"banana", 2, 4',
                  '"banana", 2', '"banana"', '"", 1, 0, "X"', '"", 5, 9, "X"', '"", 0, 0, ""', 'null, 1, 0, "X"',
                  'null, 2, 3, "X"', 'null, 1, 0, ""', 'null', '5, 1, 0, "X"', '123, 2, 3, "X"',
                  'list(1,2), 1, 2, "X"', '"abc", NAN, 2, "X"', '"abc", 1, NAN, "X"', '"abc", PINF, 0, "X"',
                  '"abc", NINF, 0, "X"', '"abc", 2, 3, "a\\[b\\]"']:
            s.case(p, f"{p}({e})")
        s.case(p, f'{p}(Text = "banana", Insert = "Q")')
        s.case(p, f'{p}("banana", End = 3, Insert = "Q")')
        s.case(p, f'{p}("banana", Start = 4, Insert = "Q")')
        s.body(p, ['var/t = "banana"', f'var/r = {p}(t, 2, 4, "X")'], 't + "|" + r')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'length({p}(t, 100, 3000, "Z"))')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'copytext_char({p}(t, -3, 0, "Z"), -4)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 5000) t += "ab"'], f'length({p}(t, 2, -2, t))')

    # ---------------- length / length_char / lentext ----------------
    LEN_POOL = TEXT + [m for m in MB if m not in TEXT] + OTHER + NUM_S + [
        "list(1, 2, 3)", "list(null)", "list(list())", 'list("a" = 1, "b" = 2)', "new /list(5)",
        "ascii2text(0)", '"a[ascii2text(0)]b"', "ascii2text(65533)", "ascii2text(1114111)", "NAN", "NINF",
        "/obj", "new /obj", dm_str("\\")]
    for p in ("length", "length_char", "lentext"):
        s.sweep(p, [LEN_POOL])
        s.case(p, f'{p}("Hi")')
        s.case(p, f'{p}(vector(1, 2))')
        s.case(p, f'{p}(vector(1, 2, 3))')
        s.case(p, f'{p}(E = "abc")')
        s.case(p, f'{p}(T = "abc")')
        s.case(p, f'{p}("abc", 2)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 3000) t += "é🙂x"'], f'{p}(t)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 30000) t += "x"'], f'{p}(t)')
        s.body(p, ['var/list/L = list()', 'for(var/i in 1 to 100) L += i'], f'{p}(L)')
        s.body(p, ['var/n = 5', f'var/l = {p}(n)'], 'list(n, l)')
        s.body(p, ['var/t = "abc"', 't += "é"'], f'{p}(t)')
        # One code point of each UTF-8 length class
        for cp in (0x41, 0x7F, 0x80, 0x7FF, 0x800, 0xFFFF, 0x10000, 0x10FFFF):
            s.case(p, f'{p}(ascii2text({cp}) + "z")')

    # ---------------- text2ascii / text2ascii_char ----------------
    for p in ("text2ascii", "text2ascii_char"):
        s.sweep(p, [TEXT_ALL], min_args=1)
        s.sweep(p, [TEXT_SM + MB[:4], POS], min_args=2)
        s.sweep(p, [[dm_str("HAPPY"), dm_str("é日本")], POS_X[len(POS):]], min_args=2)
        for t, src in zip(MB_WALK_RAW + ["Ünïcödé"], MB_WALK + [dm_str("Ünïcödé")]):
            n = walk_len(p, t)
            for i in range(-n - 2, n + 3):
                s.call(p, src, str(i))
        for e in ['"A"', '"HAPPY", 2', '"HAPPY", 0', '"HAPPY", -1', '"HAPPY", 6', '"HAPPY", -5', '"HAPPY", -6',
                  '"HAPPY", 2.5', '"HAPPY", 2.9', '"HAPPY", "2"', '"HAPPY", null', '"HAPPY", list()', '""',
                  '"", 1', '"", 0', 'null', '65', '65, 1', 'list("A")', 'new /datum', '/datum', '"HAPPY", NAN',
                  '"HAPPY", PINF', '"HAPPY", NINF', '"\\n"', '"\\t"', 'ascii2text(0)', 'ascii2text(127)',
                  'ascii2text(128)', 'ascii2text(255)', 'ascii2text(1114111)', 'ascii2text(65533)', '"\\\\"',
                  '"\\""', '"\\["']:
            s.case(p, f"{p}({e})")
        s.case(p, f'{p}(T = "HAPPY", pos = 3)')
        s.case(p, f'{p}("HAPPY", pos = 4)')
        s.case(p, f'{p}("HAPPY", 2, 3)')
        s.body(p, ['var/t = "aé日🙂z"', 'var/out = ""', 'for(var/i in 1 to 12)', f'\tout += "[{p}(t, i)],"'], 'out')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'{p}(t, 3000)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'{p}(t, -1)')
        s.body(p, ['var/t = ""', 'for(var/i in 1 to 2000) t += "é🙂"'], f'{p}(t, -2)')
    # Walk a string with pos + length(ascii2text(result)), as the reference suggests
    s.body("text2ascii", ['var/t = "aé日🙂z"', 'var/out = ""', 'var/i = 1',
                          'while(i <= length(t))', '\tvar/c = text2ascii(t, i)', '\tout += "[c],"',
                          '\ti += length(ascii2text(c))'], 'out')
    s.body("text2ascii_char", ['var/t = "aé日🙂zx́"', 'var/out = ""',
                               'for(var/i in 1 to length_char(t))', '\tout += "[text2ascii_char(t, i)],"'], 'out')

    # ---------------- ascii2text ----------------
    CPS = ["0", "1", "9", "10", "13", "31", "32", "34", "38", "60", "65", "91", "92", "93", "97", "126", "127",
           "128", "159", "160", "169", "233", "255", "256", "383", "1024", "2047", "2048", "4096", "8364",
           "0xD7FF", "0xD800", "0xDBFF", "0xDC00", "0xDFFF", "0xE000", "0xFDD0", "0xFEFF", "0xFFFD", "0xFFFE",
           "0xFFFF", "0x10000", "0x1F642", "0x1F600", "0xE0001", "0x10FFFF", "0x110000", "0x1FFFFF",
           "0x7FFFFFFF", "16777215", "16777216", "-1", "-65", "-0.5", "65.5", "65.9", "64.99", "97.1", "0.5",
           "1e30", "-1e30"]
    s.sweep("ascii2text", [CPS + NUM + OTHER + ['"65"', '"A"', '""', '"abc"']])
    for v in CPS:
        s.case("ascii2text", f"length(ascii2text({v}))")
        s.case("ascii2text", f"length_char(ascii2text({v}))")
        s.case("ascii2text", f"text2ascii(ascii2text({v}))")
    s.case("ascii2text", "ascii2text(N = 66)")
    s.case("ascii2text", "ascii2text(65, 66)")
    s.case("ascii2text", 'ascii2text(65) + ascii2text(0) + ascii2text(66)')
    s.case("ascii2text", 'length(ascii2text(65) + ascii2text(0) + ascii2text(66))')
    s.case("ascii2text", 'ascii2text(0xD83D) + ascii2text(0xDE42)')
    s.case("ascii2text", 'length(ascii2text(0xD83D) + ascii2text(0xDE42))')
    s.case("ascii2text", 'ascii2text(0x1F642) == "🙂"')
    s.case("ascii2text", 'ascii2text(233) == "é"')
    s.body("ascii2text", ['var/out = ""', 'for(var/i in 32 to 126) out += ascii2text(i)'], 'out')
    s.body("ascii2text", ['var/out = ""', 'for(var/i in 0 to 31) out += ascii2text(i)'], 'length(out)')
    s.body("ascii2text", ['var/out = ""', 'for(var/i in 0 to 31) out += ascii2text(i)'], 'out')
    s.body("ascii2text", ['var/bad = 0', 'for(var/i in 1 to 2000)',
                          '\tif(text2ascii(ascii2text(i * 37)) != i * 37) bad++'], 'bad')
    build_gaps(s)


# ---------------- gap coverage (second pass) ----------------
# Grapheme clusters that are several code points: OD's _char procs (except length_char) step by .NET
# text elements, length_char by runes. Python len() gives code points, the BYOND _char unit.
GC_RAW = ["a\r\nb", "\U0001F468‍\U0001F469‍\U0001F467", "\U0001F1EB\U0001F1EE", "❤️",
          "가", "éé", "a\U0001F468‍\U0001F469‍\U0001F467b"]
GC = [dm_str(t) for t in GC_RAW]
FAM = dm_str("a\U0001F468‍\U0001F469‍\U0001F467b")
NUL = '"a[ascii2text(0)]b"'
# DM text macros kept in the string as marker bytes by BYOND
MACROS = ['"\\improper apple"', '"\\proper Bob"', '"\\red hi"', '"\\the apple"', '"a\\icon b"']


def build_gaps(s):
    # ---- grapheme-cluster walks for every _char proc ----
    for t, src in zip(GC_RAW, GC):
        n = len(t)
        # Positive positions all the way past the end; negatives only -1, -2 and the far end
        walk = sorted(set(range(0, n + 3)) | {-1, -2, -n, -n - 1})
        for i in walk:
            s.call("copytext_char", src, str(i))
            s.call("splicetext_char", src, str(i), str(i + 1), '"|"')
            if i <= n + 1:
                s.call("text2ascii_char", src, str(i))
        for a in range(1, n + 1):
            s.call("copytext_char", src, str(a), str(a + 1))
        for p in ("length", "length_char", "lentext"):
            s.call(p, src)
        s.body("text2ascii_char", [f'var/t = {src}', 'var/out = ""', 'for(var/i in 1 to length_char(t))',
                                   '\tout += "[text2ascii_char(t, i)],"'], 'out')
    s.case("length_char", f'length_char({dm_str("e" + chr(0x301))}) == length_char({dm_str(chr(0xe9))})')
    s.case("copytext_char", f'{dm_str("e" + chr(0x301))} == {dm_str(chr(0xe9))}')

    # ---- _char consistency on ZWJ / CRLF / combining ----
    for src in (FAM, dm_str("a\r\nb"), dm_str("x́y")):
        s.body("copytext_char", [f'var/t = {src}'], 'copytext_char(t, length_char(t))')
        s.body("copytext_char", [f'var/t = {src}'], 'copytext_char(t, 2, 3)')
        s.body("copytext_char", [f'var/t = {src}'], 'length_char(copytext_char(t, 2, 3))')
        s.body("copytext_char", [f'var/t = {src}'], 'copytext_char(t, 1, length_char(t))')
        s.body("splicetext_char", [f'var/t = {src}'], 'splicetext_char(t, length_char(t), 0, "X")')
        s.body("text2ascii_char", [f'var/t = {src}'], 'text2ascii_char(t, length_char(t))')
        s.body("copytext_char", [f'var/t = {src}', 'var/out = ""', 'for(var/i in 1 to length_char(t))',
                                 '\tout += copytext_char(t, i, i + 1) + "|"'], 'out')

    # ---- text2ascii(_char) on astral / ZWJ, explicit expected values ----
    for ch, cp in (("\U0001F642", 0x1F642), ("\U0001F468", 0x1F468), ("\U0001F1EB", 0x1F1EB),
                   ("\U00010000", 0x10000), ("\U0010FFFF", 0x10FFFF)):
        s.case("text2ascii_char", f'text2ascii_char({dm_str(ch)}) == {cp}')
        s.case("text2ascii", f'text2ascii({dm_str(ch)}) == {cp}')
        s.case("text2ascii_char", f'text2ascii_char({dm_str("a" + ch + "b")}, 2) == {cp}')
    for i in (2, 3, 4, 7):
        s.call("text2ascii_char", FAM, str(i))

    # ---- mid-character fragments, inspected ----
    for e in ['length(copytext("é", 1, 2))', 'text2ascii(copytext("é", 1, 2))', 'copytext("é", 1, 2)',
              'length(copytext("é", 2))', 'text2ascii(copytext("é", 2))',
              'length(copytext("🙂", 2))', 'text2ascii(copytext("🙂", 2))', 'text2ascii(copytext("🙂", 3))',
              'length(copytext("🙂", 3))', 'length(copytext("🙂", 1, 3))', 'text2ascii(copytext("🙂", 1, 3))',
              'copytext("é", 1, 2) + copytext("é", 2) == "é"', 'length(copytext("é", 1, 2) + copytext("é", 2))',
              'copytext("é", 1, 2) + copytext("é", 2)', 'copytext("🙂", 1, 3) + copytext("🙂", 3) == "🙂"',
              'length(copytext("🙂", 1, 3) + copytext("🙂", 3))', 'length_char(copytext("é", 1, 2))',
              'copytext("é", 1, 2) == ascii2text(65533)', 'findtext(copytext("日本", 2), "本")']:
        s.case("copytext", e)
    for e in ['length(splicetext("é日本", 2, 0, ""))', 'splicetext("é日本", 2, 0, "")',
              'text2ascii(splicetext("🙂x", 3, 4, "X"), 1)', 'splicetext("🙂x", 3, 4, "X")',
              'length(splicetext("🙂x", 3, 4, "X"))', 'splicetext("é", 2, 2, "") == "é"',
              'splicetext("é", 2, 2, "")', 'length(splicetext("é", 2, 2, ""))', 'splicetext("é", 2, 2, "X")',
              'length(splicetext("é", 2, 3, ""))', 'text2ascii(splicetext("é", 2, 3, "Z"))']:
        s.case("splicetext", e)

    # ---- fractional positions near zero ----
    for p in ("copytext", "copytext_char"):
        for e in ['0.5', '0.9', '-0.5', '-0.9', '0.1', '-0.1', '1, 0.5', '1, -0.5', '1, 0.9', '2, -0.9',
                  '0.5, 3', '-0.5, 3', '1.1', '6.9', '-5.5', '-6.5']:
            s.case(p, f'{p}("abcdef", {e})')
        s.case(p, f'{p}("é日本", 0.5)')
        s.case(p, f'{p}("é日本", -0.5)')
    for p in ("splicetext", "splicetext_char"):
        for e in ['0.5, 3', '-0.5, 0', '2, 0.9', '2, -0.9', '0.9, 0.9', '-0.5, -0.5', '0.1, 1', '6.5, 0',
                  '7.5, 0']:
            s.case(p, f'{p}("banana", {e}, "X")')
    for p in ("text2ascii", "text2ascii_char"):
        for e in ['0.5', '-0.5', '-1.5', '5.9', '0.9', '-0.9', '1.9', '-4.5', '-5.5', '6.1']:
            s.case(p, f'{p}("HAPPY", {e})')

    # ---- splicetext: End still negative after adjustment, Start past the end ----
    for p, t in (("splicetext", '"banana"'), ("splicetext_char", '"banana"'), ("splicetext", '"é日本"'),
                 ("splicetext_char", '"é日本"')):
        for e in ['4, -100', '7, 2', '7, 0', '100, 0', '100, 2', '2, -100', '-100, -100', '8, 0', '5, 3',
                  '4, 0', '4, 4', '5, 5', '-1, 0']:
            s.case(p, f'{p}({t}, {e}, "X")')
    for e in ['"é日本", 4, 0, "X"', '"é日本", 4, 4, "X"', '"é日本", 4, 5, "X"', '"x́y", 3, 3, "X"',
              '"x́y", 4, 4, "X"', '"x́y", 4, 0, "X"', '"🙂x🙂", 4, 0, "X"', '"🙂x🙂", 4, 4, "X"']:
        s.case("splicetext_char", f'splicetext_char({e})')

    # ---- 4-byte character with ASCII on both sides, byte walk ----
    t = dm_str("a\U0001F642b")
    for i in range(-8, 10):
        s.call("text2ascii", t, str(i))
        s.call("copytext", t, str(i))
        s.call("splicetext", t, str(i), str(i + 1), '"|"')
    for i in range(2, 7):
        s.call("copytext", t, str(i), str(i + 1))
    for i in (3, 4, 5, 6):
        s.case("text2ascii", f'text2ascii({t}, {i}) == 65533')

    # ---- embedded NUL ----
    for e in [f'copytext({NUL}, 2)', f'copytext({NUL}, 3)', f'copytext({NUL}, 1, 3)', f'length(copytext({NUL}, 2))',
              f'text2ascii({NUL}, 3)', f'text2ascii({NUL}, 2)', f'splicetext({NUL}, 2, 3, "X")',
              f'splicetext({NUL}, 3, 4, "X")', f'length(splicetext({NUL}, 1, 2, "X"))', f'copytext_char({NUL}, 3)',
              f'text2ascii_char({NUL}, 3)', f'splicetext_char({NUL}, 2, 3, "X")', f'length_char({NUL})',
              f'{NUL} == "a"', f'findtext({NUL}, "b")']:
        proc = e.split("(")[0]
        s.case(proc if proc in ("copytext", "text2ascii", "splicetext", "copytext_char", "text2ascii_char",
                                "splicetext_char", "length", "length_char") else "copytext", e)

    # ---- text macros ----
    for m in MACROS:
        for p in ("length", "length_char", "lentext"):
            s.call(p, m)
        for p in ("text2ascii", "text2ascii_char"):
            s.call(p, m)
            s.call(p, m, "2")
            s.call(p, m, "-1")
        for p in ("copytext", "copytext_char"):
            s.call(p, m, "1", "3")
            s.call(p, m, "2")
            s.call(p, m, "-3")
        for p in ("splicetext", "splicetext_char"):
            s.call(p, m, "1", "2", '"X"')

    # ---- ascii2text: past 32 bits, wrong shapes ----
    for v in ["4294967296 + 65", "4294967295", "-4294967231", "2147483648", "2147483647", "-2147483648",
              "4294967361", "1099511627841", "16777281", "TRUE", "FALSE", '"0x41"', '"1e2"', '"65.5"', '" 65"',
              "list(65)", "new /datum", "/datum"]:
        s.call("ascii2text", v)
        s.case("ascii2text", f"length(ascii2text({v}))")
    # Zero-argument calls: compile-time parity points
    for p in ("ascii2text", "text2ascii", "text2ascii_char", "length", "length_char", "lentext",
              "copytext", "copytext_char", "splicetext", "splicetext_char"):
        s.case(p, f"{p}()")

    # ---- text [] indexing (byte positions per the Unicode reference) ----
    for i in ["1", "2", "3", "4", "5", "6", "-1", "-2", "0", "100", "1.5", '"2"']:
        s.body("copytext", ['var/t = "aé日"'], f't[{i}]')
    for i in ["1", "2", "3", "4", "-1"]:
        s.body("copytext", [f'var/t = {FAM}'], f't[{i}]')
    s.body("copytext", ['var/t = "aé日"'], 'length(t[3])')
    s.body("copytext", ['var/t = "aé日"', 't[1] = "z"'], 't')

    # ---- length on files / resources ----
    for p in ("length", "length_char", "lentext"):
        s.body(p, ['fdel("parity_len.txt")', 'text2file("abcé", "parity_len.txt")'], f'{p}(file("parity_len.txt"))')
        s.body(p, ['fdel("parity_len_missing.txt")'], f'{p}(file("parity_len_missing.txt"))')
        s.body(p, ['fdel("parity_len0.txt")', 'text2file("", "parity_len0.txt")'], f'{p}(file("parity_len0.txt"))')
        s.body(p, ['fdel("parity_len.txt")', 'text2file("abcé", "parity_len.txt")'],
               f'{p}(file2text(file("parity_len.txt")))')

    # ---- length on special lists and other object kinds ----
    for p in ("length", "length_char", "lentext"):
        s.case(p, f"{p}(args)")
        s.case(p, f"{p}(new /datum().vars)")
        s.body(p, ['var/datum/d = new'], f'{p}(d.vars) == d.vars.len')
        s.body(p, ['var/obj/o = new'], f'{p}(o.vars) == o.vars.len')
        s.body(p, ['var/a = length(world.contents)', 'var/obj/o = new', 'var/b = length(world.contents)'],
               'list(b - a, isnum(a), istype(o))')
        s.body(p, ['var/obj/o = new'], f'{p}(o.overlays)')
        s.body(p, ['var/obj/o = new', 'o.overlays += "x"'], f'{p}(o.overlays)')
        s.body(p, ['var/obj/o = new', 'o.overlays += "x"', 'o.overlays += "y"', 'o.underlays += "z"'],
               f'list({p}(o.overlays), {p}(o.underlays))')
        s.body(p, ['var/obj/o = new'], f'{p}(o.verbs)')
        s.body(p, ['var/obj/o = new', 'var/obj/i = new(o)'], f'list({p}(o.contents), istype(i))')
        s.body(p, ['var/obj/o = new'], f'{p}(o.filters)')
        s.case(p, f'{p}(alist("a" = 1, "b" = 2))')
        s.case(p, f'{p}(alist())')
        for e in ["matrix()", "matrix(1, 2, 3, 4, 5, 6)", "new /icon()", "new /sound()", "new /savefile()",
                  "new /image()", 'new /regex("a")', "new /mutable_appearance()", "world",
                  'filter(type = "blur", size = 1)']:
            s.case(p, f"{p}({e})")
        s.case(p, f"{p}(global.vars) > 0")
