"""Shared input pools for specs. Every entry is DM source for one value."""
from gen import dm_str

# Text: empty, case, whitespace, separators, html/url specials, numeric-looking, multibyte
TEXT_RAW = [
    "", "a", "A", "abc", "ABC", "aBc", "Hello World", "hello world", " padded  ", "\t tab\n",
    "a,b,,c", "a b  c", "aaa", "abcabc", "The Cat", "<b>bold</b> & 'q' \"dq\"",
    "&amp;&lt;&gt;&quot;&#39;&nbsp;&#x41;", "a+b%20c%2", "50%", "123", "-0.5", "1e3", "0x1F", "  42  ",
    "é", "Ünïcödé", "日本語テキスト", "🙂x🙂", "a\\b", "[brackets]", "line1\nline2",
]
TEXT = [dm_str(t) for t in TEXT_RAW]
# A shorter set for 3+ argument sweeps so all-pairs stays small
TEXT_S = [dm_str(t) for t in ["", "a", "abc", "ABC", "Hello World", "a,b,,c", "é日本", "🙂x🙂", "aaa"]]
# Needles: things the TEXT haystacks contain, plus misses
NEEDLE = [dm_str(t) for t in ["", "a", "A", "b", "abc", "c", ",", " ", "o", "l", "é", "本", "🙂", "zz", "\n"]]

NUM = ["0", "1", "-1", "2", "3", "5", "10", "-5", "0.5", "-0.5", "1.5", "2.9", "100", "1e7",
       "16777217", "1e-7", "PINF", "NINF", "NAN"]
NUM_S = ["0", "1", "-1", "2", "4", "0.5", "-3", "100"]
# Positions for 1-based text indexing, including 0 (= end) and negatives (from the end)
POS = ["0", "1", "2", "3", "4", "-1", "-2", "-100", "100", "1.5", "null"]

# Values of other kinds, to check how each proc treats arguments of the wrong type
OTHER = ["null", "list()", "list(1, \"a\")", "list(\"a\" = 1)", "/datum", "new /datum", "PINF"]

ANY = TEXT_S + NUM_S + OTHER
