"""Number <-> text conversion: text2num, num2text, "[x]" stringification, text() formatting.

BYOND ref: text2num(T, radix=10) parses an initial numeric portion (rest ignored, null if none),
radix 2..36. num2text(N, SigFig=6) uses scientific notation beyond SigFig digits;
num2text(N, Digits, Radix) uses only the integer part (32-bit), left-pads with zeroes to Digits.
text(FormatText, Args...) substitutes [] placeholders with trailing args, and expands text macros.

OD details these cases aim at: text2num has no exponent / inf / nan parsing and trims all
whitespace; num2text uses .NET "g<N>" format; ToBase(0) is "", radix < 2 has no guard (radix 1
loops, 0 divides by zero); text() is resolved entirely in OD's parser.
"""
from pools import TEXT, TEXT_S, NUM, NUM_S, OTHER
from gen import dm_str

# Strings for text2num: numeric forms, signs, whitespace, exponents, hex, inf/nan, garbage
T2N_RAW = [
    "", " ", "0", "1", "-1", "+1", "--1", "+-1", "-+1", "- 1", "+", "-", ".", "-.", "+.5", "-.5",
    ".5", "5.", "0.5", "00012", "007.50", "1.2.3", "1..2", "123abc", "abc123", "12 34", "1,000",
    "1_000", " 42", "42 ", "  42  ", "\t42", "\n42", "42\n", " 42", "　42", "\x0b42",
    "1e3", "1E3", "1e+3", "1e-3", "1e", "1e+", "1ee3", "e3", "1.5e2", "-1.5e-2", "1e38", "1e39",
    "1e308", "1e400", "1e-45", "1e-50", "2e", "1e3.5", "1 e3", "1d3",
    "0x1F", "0X1F", "0x", "0xg", "-0x10", "+0x10", "0x1.8", "0x1e3", "0b101", "0o17", "#ff", "$ff",
    "inf", "INF", "-inf", "infinity", "Infinity", "nan", "NaN", "-nan", "1.#INF", "1.#QNAN",
    "16777216", "16777217", "16777218", "2147483647", "2147483648", "4294967296",
    "99999999999999999999", "0.1", "0.30000000000000004", "3.14159265358979",
    "0.000001", "123456789.987654321", "1/2", "½", "١٢٣", "１２３",
    "12abc", "ff", "FF", "zz", "Zz", "z", "10", "11", "777", "1010", "-ff", "a.8", "0.0", "-0",
    "-0.0", "  -  5", "5-", "$5",
]
T2N = [dm_str(t) for t in T2N_RAW]
# Short set for radix sweeps
T2N_S = [dm_str(t) for t in [
    "0", "1", "10", "-10", "+7", "777", "1010", "ff", "FF", "-ff", "zz", "Zz", "z", "a.8", "1.5",
    "0x1F", "0x", "1e3", "  12  ", "12abc", "", "inf", "19", "2", "9", "#",
]]
RADIX = ["2", "3", "7", "8", "10", "11", "16", "17", "20", "35", "36"]
RADIX_BAD = ["0", "1", "37", "-1", "-16", "100", "1.5", "16.9", "2.5", "35.99", "null",
             '"16"', '"a"', "list()", "new /datum", "PINF", "NINF", "NAN"]

# Numbers across magnitudes and precisions
MAG = [
    "0", "-0", "1", "-1", "0.1", "0.5", "-0.5", "1/3", "2/3", "0.1+0.2", "1.5", "2.5", "3.14159265",
    "10", "100", "999", "1000", "12345", "99999", "123456", "999999", "999999.4", "999999.5",
    "1000000", "-1000000", "1234567", "9999999", "1e7", "12345678", "16777215", "16777216",
    "16777217", "2**31", "2**32", "1e10", "1e15", "1e20", "1e30", "1e38", "3.4e38", "-3.4e38",
    "0.01", "0.001", "0.0001", "0.00012345", "0.00001", "1e-5", "1.5e-5", "1e-6", "1e-7",
    "1e-10", "1e-20", "1e-38", "1e-40", "1e-45", "123.456", "-123.456", "99999.95", "0.999999",
    "0.9999995", "1.0000001", "65535", "65536", "4294967295", "PINF", "NINF", "NAN",
]
MAG_S = ["0", "-0", "1", "0.5", "1/3", "123.456", "999999", "1234567", "16777217", "1e20",
         "3.4e38", "0.00001", "1e-10", "1e-45", "-123.456", "PINF", "NAN"]
SIGFIG = [str(i) for i in range(0, 21)] + ["-1", "-5", "1.5", "2.9", "25", "100", "null",
                                             '"3"', "PINF", "NAN"]
# Integers for the radix form
INTS = ["0", "1", "-1", "11", "-11", "255", "343", "1000", "65535", "65536", "16777216",
        "2147483647", "-2147483648", "2147483648", "4294967295", "4294967296", "1e10", "-1e10",
        "12.9", "-12.9", "0.5", "-0.5", "PINF", "NINF", "NAN"]
DIGITS = ["0", "1", "2", "4", "8", "16", "33", "-1", "-5", "1.5", "null"]
NRADIX = ["2", "3", "7", "8", "10", "16", "36"]
NRADIX_BAD = ["0", "-2", "37", "64", "1.5", "2.9", "null", '"16"', "NAN"]


def build(s):
    # ---------- text2num ----------
    s.sweep("text2num", [T2N + TEXT + NUM + OTHER])
    s.sweep("text2num", [T2N_S, RADIX])
    s.sweep("text2num", [T2N_S[:8], RADIX_BAD])
    s.sweep("text2num", [TEXT_S + NUM_S + OTHER, ["2", "16", "36", "null"]])
    for n in MAG:  # round trips through the display forms
        s.case("text2num", f"text2num(num2text({n}))")
        s.case("text2num", f'text2num("[{n}]")')
        s.case("text2num", f"text2num(num2text({n}, 12))")
    # Digits at the radix boundary: a digit >= radix must stop the parse
    for r in (2, 8, 10, 16, 36):
        for ch in "019azAZ":
            s.case("text2num", f"text2num({dm_str(ch + '1')}, {r})")
    for e in ['text2num("1", radix = 16)', 'text2num(T = "ff", radix = 16)', 'text2num("ff", 16) == 255',
              'text2num("0x10", 8)', 'text2num("0x10", 2)', 'text2num("0x10", 36)', 'text2num("1e3", 16)',
              'text2num("1e3", 15)', 'text2num("1.1", 2)', 'text2num("0.1", 3)', 'text2num("-z.z", 36)',
              'isnull(text2num("abc"))', 'text2num("[ascii2text(0)]5")', 'text2num("5[ascii2text(0)]6")',
              'text2num("[ascii2text(13)]5")', 'text2num("\\x35")', 'text2num(5)', 'text2num(-0.5, 16)',
              'text2num(/obj)', 'text2num(new /obj)', 'text2num(world)', 'text2num(icon())',
              'text2num(file("x.txt"))', 'text2num(list("1"))', 'text2num()', 'text2num("1", 10, 3)']:
        s.case("text2num", e)
    s.body("text2num", ['var/t = ""', 'for(var/i in 1 to 400) t += "9"'], "text2num(t)")
    s.body("text2num", ['var/t = "0."', 'for(var/i in 1 to 400) t += "0"', 't += "1"'], "text2num(t)")
    s.body("text2num", ['var/t = ""', 'for(var/i in 1 to 300) t += "0"', 't += "42"'], "text2num(t)")
    s.body("text2num", ['var/t = "1"', 'for(var/i in 1 to 40) t += "0"'], "text2num(t, 2)")
    s.body("text2num", ['var/t = ""', 'for(var/i in 1 to 2000) t += " "', 't += "7"'], "text2num(t)")
    # text2num does not modify its argument
    s.body("text2num", ['var/t = "  12  "', 'text2num(t)'], "t")

    # ---------- num2text ----------
    s.sweep("num2text", [MAG + TEXT_S + OTHER])
    s.sweep("num2text", [MAG_S, SIGFIG])
    s.sweep("num2text", [["0", "1", "1/3", "123456", "1234567", "0.0001", "1e-5"],
                         [str(i) for i in range(0, 21)]],
            fmt=lambda n, d: f"num2text(-({n}), {d})")
    s.sweep("num2text", [INTS, DIGITS, NRADIX])  # all-pairs
    s.sweep("num2text", [INTS, ["0", "8"], NRADIX], full_upto=3)
    s.sweep("num2text", [["0", "11", "-11", "255"], ["2"], NRADIX_BAD], full_upto=3)
    s.sweep("num2text", [TEXT_S + OTHER, ["0", "4"], ["10", "16"]], full_upto=3)
    s.sweep("num2text", [TEXT_S + OTHER, ["1", "6", "null"]])
    for n in ("12", "343", "11"):
        for d, r in (("1", "16"), ("2", "16"), ("0", "7"), ("4", "2")):
            s.case("num2text", f"num2text({n}, {d}, {r})")
    for e in ["num2text(12)", "num2text(12, 1)", "num2text(11, 2, 16)", "num2text(343, 0, 7)",
              "num2text(255, 0, 16)", "num2text(255, 0, 10)", "num2text(1234567, 6, 10)",
              "num2text(N = 5)", "num2text(N = 1/3, SigFig = 3)", "num2text(1/3, null)",
              "num2text(1/3, null, null)", "num2text(1/3, 3, null)", "num2text(255, null, 16)",
              "num2text(255, 3, 16, 1)", "num2text()", "length(num2text(1, 1000))",
              "length(num2text(1, 1000, 2))", "num2text(1, 50, 2)", 'num2text(1, 1e6) == "1"',
              "num2text(/datum)", "num2text(new /obj)", 'num2text("12", 3, 16)', "num2text(TRUE)"]:
        s.case("num2text", e)
    s.body("num2text", ['var/n = 1.25', 'num2text(n, 1)'], "n")

    # ---------- "[x]" stringification ----------
    for n in MAG:
        s.case("stringify", f'"[{n}]"')
        s.case("stringify", f'"[-({n})]"')
    for k in range(-12, 13):
        s.case("stringify", f'"[10 ** {k}]"')
        s.case("stringify", f'"[1.23456789 * (10 ** {k})]"')
        s.case("stringify", f'"[-7 * (10 ** {k})]"')
    for k in range(0, 33, 2):
        s.case("stringify", f'"[2 ** {k}]"')
        s.case("stringify", f'"[(2 ** {k}) - 1]"')
    for v in ("0.1", "0.15", "0.25", "0.125", "1.005", "2.675", "1234.5", "12345.5", "123456.5",
              "1234565", "1234575", "0.0000123", "0.00001234567"):
        s.case("stringify", f'"[{v}]"')
    for e in ['"[1e6 - 1]"', '"[1e6 + 1]"', '"[0 * -1]"', '"[-0.0]"', '"[1 / PINF]"', '"[-1 / PINF]"',
              '"[NAN]"', '"[-NAN]"', '"[PINF][NINF]"', '"[TRUE][FALSE][null]"', '"[1][2][3]"',
              '"<[1 ]|[ 2]>"']:
        s.case("stringify", e)
    s.body("stringify", ['var/t = 5', 't = "[t]"'], "t")
    s.body("stringify", ['var/y = 0', 'for(var/i in 1 to 10) y += 0.1'], '"[y]"')
    s.body("stringify", ['var/y = 1', 'for(var/i in 1 to 30) y *= 3'], '"[y]"')
    s.body("stringify", ['var/y = 1', 'for(var/i in 1 to 30) y /= 7'], '"[y]"')

    # ---------- text() ----------
    for e in ['text("plain")', 'text("")', 'text("a[]b", 1)', 'text("[]", 1/3)', 'text("[][]", 1, 2)',
              'text("[] and []", "x", "y")', 'text("[]-[]-[]", null, list(), /datum)',
              'text("You are [] leagues from home.", sqrt(3**2 + 4**2))', 'text("[1+1] []", 3)',
              'text("[] [1+1]", 3)', 'text("x[]", "\\[]")', 'text("\\[]", 1)', 'text("[]")',
              'text("[][]", 1)', 'text("[]", 1, 2)', 'text("plain", 1)', 'text()', 'text(5)',
              'text(null)', 'text("[]\\th place", 2)', 'text("\\roman[]", 14)', 'text("\\a []", "apple")']:
        s.case("text", e)
    s.body("text", ['var/f = "a[]b"'], 'text(f, 1)')
    s.body("text", ['var/f = "abc"'], 'text(f)')
    s.body("text", ['var/n = 0'], 'text("[]/[]/[]", ++n, ++n, ++n)')
    for v in MAG_S + ['"str"', 'null', 'list(1,2)', '/datum', '"é日\U0001F642"']:
        s.case("text", f'text("<[]>", {v})')
    # Text macros (DM source written directly; dm_str would escape the backslashes)
    for n in ("0", "1", "2", "3", "4", "11", "12", "13", "21", "22", "23", "101", "111", "112",
              "-1", "-2", "1.5", "0.5", "1000", "1e7", "null", '"x"'):
        s.case("text", f'"[{n}]\\th"')
        s.case("text", f'text("[]\\th", {n})')
    for n in ("0", "1", "4", "9", "14", "40", "49", "90", "99", "400", "1994", "2024", "3999",
              "4000", "5000", "-1", "-4", "1.5", "2.9", "null", '"x"', "PINF"):
        s.case("text", f'"\\roman[{n}]"')
        s.case("text", f'"\\Roman[{n}]"')
    for n in ("0", "1", "2", "-1", "0.5", "1.5", "null", '"x"', "list()", "list(1,2)"):
        s.case("text", f'"[{n}] apple\\s"')
    for w in ('"apple"', '"Apple"', '"egg"', '"hour"', '"unit"', '"\\proper fred"',
              '"\\improper CPU"', '"Fred"', '""', 'null', '5'):
        for m in ("a", "A", "the", "The"):
            s.case("text", f'"\\{m} [{w}]"')
    for e in ['"\\he"', '"[5] \\he \\his"', '"[\\"x\\"] \\him \\himself \\hers"', '"a\\tb"', '"a\\nb"',
              '"\\"q\\""', '"\\\\"', '"\\<b\\>"', '"a\\ b"', '"line\\..."', '"x\\...y"', '"\\x41\\x7a"',
              '"\\x4"', '"\\u00e9\\u65e5"', '"\\U01F642"', '"\\u00"', '"\\q"', '"\\1"', '"\\ref"',
              'length("\\ref[null]")', '"\\icon"', '"\\proper"', '"\\improper"', '"\\th"', '"\\s"',
              '"\\a"', 'length("\\U01F642")',
              'length("[ascii2text(128512)]")']:
        s.case("text", e)

    _build_gaps(s)


def _build_gaps(s):
    """Cases added for gaps a review found (runtime-only stringify, OD-specific text2num/num2text paths)."""
    # ---------- stringify: runtime values (no compile-time constant folding) ----------
    for k in range(-12, 13):
        s.body("stringify", ['var/x = 1.23456789', f'var/k = {k}', 'x *= 10 ** k'], '"[x]"')
        s.body("stringify", ['var/x = 10', f'var/k = {k}', 'x = x ** k'], '"[x]"')
        s.body("stringify", ['var/x = -7', f'var/k = {k}', 'x *= 10 ** k'], '"[x]"')
    for k in range(0, 33, 2):
        s.body("stringify", ['var/x = 2', f'var/k = {k}', 'x = x ** k'], '"[x]"')
        s.body("stringify", ['var/x = 2', f'var/k = {k}', 'x = (x ** k) - 1'], '"[x]"')
    for v in ("16777217", "999999.5", "999999.4", "1234567", "16777216", "1e20", "1/3", "0.00001",
              "3.4e38", "1e-45", "123.456", "-1234567", "0.999999", "0.9999995"):
        s.body("stringify", [f'var/x = {v}', 'var/z = 0', 'x += z'], '"[x]"')
    s.body("stringify", ['var/x = 0.1', 'x += 0.2'], '"[x]"')
    s.body("stringify", ['var/x = 0.1', 'var/y = 0.2'], '"[x + y]"')
    s.body("stringify", ['var/x = 3.4e38', 'x *= 10'], '"[x]"')
    s.body("stringify", ['var/x = -3.4e38', 'x *= 10'], '"[x]"')
    s.body("stringify", ['var/x = 1e-38', 'x /= 1e10'], '"[x]"')
    s.body("stringify", ['var/x = 16777216', 'x += 1'], '"[x]"')
    s.body("stringify", ['var/x = 1000000', 'x += 0.5'], '"[x]"')
    # g8 integer branch boundaries, halfway non-integers inside it, negatives that skip it
    for v in ("1234567.5", "8388607.5", "1000000.5", "1048575.75", "16777215.5", "9999999.5",
              "-1234567", "-16777215", "-9999999", "-16777216", "-1000000.5", "1000001", "999999.9"):
        s.case("stringify", f'"[{v}]"')
    # Literals that overflow / underflow float at compile time
    for v in ("1e39", "3.5e38", "-1e39", "1e-46", "1e-50", "1e300", "-1e-50"):
        s.case("stringify", f'"[{v}]"')
    # Empty interpolation outside text()
    for e in ['"x[]y"', '"[]"', '"a[][]b"', 'length("x[]y")', 'length("[]")', '"[]" == ""']:
        s.case("stringify", e)

    # ---------- text2num: whitespace .NET Trim() strips but BYOND may not ----------
    for c in (160, 12, 133, 8195, 65279, 8232, 28, 31, 32):
        s.case("text2num", f'text2num("[ascii2text({c})]42")')
        s.case("text2num", f'text2num("42[ascii2text({c})]")')
    s.case("text2num", 'text2num("[ascii2text(160)]-42[ascii2text(160)]")')
    # 0x prefix forms
    for e in ['text2num("0X1F", 16)', 'text2num("0x1F", 16)', 'text2num("0x1f", 16)', 'text2num("-0x10", 16)',
              'text2num("+0x10", 16)', 'text2num("0x-5")', 'text2num("0x 5")', 'text2num(" 0x10")',
              'text2num(" 0x10", 16)', 'text2num("0x-5", 16)', 'text2num("0X10")', 'text2num("0x10", 10)',
              'text2num("0x10", 17)', 'text2num("0x0x10", 16)', 'text2num("00x10", 16)']:
        s.case("text2num", e)
    # Signs with non-10 radix and whitespace
    for e in ['text2num("  -ff  ", 16)', 'text2num("+z", 36)', 'text2num("-.8", 16)', 'text2num(".8", 16)',
              'text2num("-", 16)', 'text2num("+", 2)', 'text2num(" +101 ", 2)', 'text2num("- ff", 16)',
              'text2num("--ff", 16)', 'text2num("-0", 16)', 'text2num("\\t-Z\\n", 36)']:
        s.case("text2num", e)
    # Long high-radix strings
    for e in ['text2num("zzzzzzzzzzzz", 36)', 'text2num("ffffffff", 16)', 'text2num("100000000", 16)',
              'text2num("7fffffff", 16)', 'text2num("80000000", 16)', 'text2num("1000001", 16)',
              'text2num("ffffff", 16)', 'text2num("1000000", 16)',
              'text2num("11111111111111111111111111111111", 2)']:
        s.case("text2num", e)
    s.body("text2num", ['var/t = ""', 'for(var/i in 1 to 200) t += "z"'], "text2num(t, 36)")
    s.body("text2num", ['var/t = ""', 'for(var/i in 1 to 200) t += "z"'], "text2num(t, 36) == PINF")
    # Fractions in non-decimal radixes
    for e in ['text2num("0.1", 16)', 'text2num("0.3", 7)', 'text2num("z.zzzzzz", 36)', 'text2num("1.", 2)',
              'text2num("1.2", 2)', 'text2num("..1", 16)', 'text2num("0.8", 16)', 'text2num("f.f", 16)',
              'text2num("0.0001", 2)', 'text2num("-0.1", 3)']:
        s.case("text2num", e)
    # Radix as whole-number float, named, null
    for e in ['text2num("ff", 16.0)', 'text2num("ff", radix = 36.0)', 'text2num("ff", radix = null)',
              'text2num(T = "10", radix = 2)', 'text2num("10", null)', 'text2num(radix = 2, T = "11")',
              'text2num("ff", 32/2)']:
        s.case("text2num", e)
    s.body("text2num", ['var/r = 4', 'r *= 4'], 'text2num("ff", r)')

    # ---------- num2text ----------
    # Radix 1, negative, above 36 (num2text(5, 1, 1) may hang OD; the runner skips hangs)
    for e in ['num2text(0, 4, 1)', 'num2text(5, 1, 1)', 'num2text(5, 1, -16)', 'num2text(0, 1, 37)',
              'num2text(1000, 1, 37)', 'num2text(0, 1, 1000)', 'num2text(1000, 1, 1000)', 'num2text(0, 1, 0)',
              'num2text(0, 1, -1)']:
        s.case("num2text", e)
    # Digits not a finite integer
    for e in ['num2text(255, "4", 16)', 'num2text(255, PINF, 16)', 'num2text(255, NINF, 16)',
              'num2text(255, NAN, 16)', 'num2text(255, list(), 16)', 'num2text(255, /datum, 16)',
              'length(num2text(5, 100000, 10))', 'length(num2text(5, 1e8, 10))', 'num2text(255, 4.9, 16)',
              'num2text(255, -4.9, 16)']:
        s.case("num2text", e)
    # BYOND's documented argument names
    for e in ['num2text(255, Digits = 4, Radix = 16)', 'num2text(255, Radix = 16)', 'num2text(255, 4, Radix = 16)',
              'num2text(N = 255, Digits = 0, Radix = 2)', 'num2text(1/3, SigFig = 2)',
              'num2text(SigFig = 2, N = 1/3)', 'num2text(255, Digits = 4)']:
        s.case("num2text", e)
    # Explicit null radix
    for e in ['num2text(1234567, 6, null)', 'num2text(255, 0, null)', 'num2text(12.5, 1, null)',
              'num2text(255, null, null, null)', 'num2text(1234567, 6)', 'num2text(12.5, 1)']:
        s.case("num2text", e)
    # SigFig form in the g8 range, compared with "[x]"
    for n in ("1000000", "16777216", "-1000000", "1234567", "9999999"):
        s.case("num2text", f"num2text({n})")
        s.case("num2text", f'num2text({n}) == "[{n}]"')
    for e in ['num2text(1000000, 8)', 'num2text(1000000, 7)', 'num2text(16777216, 8)', 'num2text(1234567, 7)']:
        s.case("num2text", e)
    # Radix form near integer limits and negative fractions
    for e in ['num2text(-0.9, 1, 16)', 'num2text(-0.9, 2, 2)', 'num2text(2147483647.5, 0, 16)',
              'num2text(-2147483649, 0, 16)', 'num2text(4294967295, 0, 16)', 'num2text(-1, 8, 16)',
              'num2text(-1, 0, 2)', 'num2text(-255, 6, 16)', 'num2text(-0.5, 3, 2)',
              'num2text(4294967296, 0, 16)']:
        s.case("num2text", e)

    # ---------- text() ----------
    # Format not a plain literal (OD resolves text() in its parser)
    s.body("text", ['var/const/F = "a\\[\\]b"'], 'text(F, 1)')
    s.body("text", ['var/const/F = "a[]b"'], 'text(F, 1)')
    for e in ['text("a" + "[]", 1)', 'text("a" + "\\[\\]", 1)', 'text(lowertext("A\\[\\]B"), 1)',
              'text(("a[]b"), 1)', 'text(arglist(list("\\[\\]", 1)))', 'text(arglist(list("[]", 1)))',
              'text("[]" + "[]", 1, 2)']:
        s.case("text", e)
    s.body("text", ['var/f = "x\\[\\]y"'], 'text(f, 7)')
    # Text macros combined with placeholders
    for e in ['text("[] apple\\s", 2)', 'text("[] apple\\s", 1)', 'text("[] apple\\s", 0)',
              'text("\\The []", "apple")', 'text("\\the []", "\\proper Fred")', 'text("\\The []", "\\improper apple")',
              'text("[] \\he", "x")', 'text("\\Roman[]", 1994)', 'text("\\roman[]", 0)', 'text("\\a []", "hour")',
              'text("\\A []", "egg")']:
        s.case("text", e)
    s.body("text", ['var/s = "\\th"'], 'text("[][]", 1, s)')
    s.body("text", ['var/s = "\\the apple"'], 'text("[]", s)')
    # Embedded expressions in arguments, nested text()
    for e in ['text("[]", "[1+1]")', 'text("[]", text("[]", 5))', 'text("[][]", "[]", 1)', 'text("[]", "a[]b")',
              'text("[]", text("[][]", "a", "b"))', 'text("[][]", "\\[\\]", 1)']:
        s.case("text", e)
