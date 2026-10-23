"""input() as num with text that is not a plain number. Last file: a prompt that refuses OK stays open."""


def build(s):
    s.prompts()
    p = s.prompt
    for t in ("abc", "1e3", " 42 ", "0x10", "12abc", ""):
        p(f"num typed {t!r}", 'input(C, "How many?", "Count", 3) as num', [("text", t), ("submit",)])
    p("num|null typed 'abc'", 'input(C, "How many?", "Count", 3) as num|null', [("text", "abc"), ("submit",)])
    p("as null only", 'input(C, "Nothing?", "Null", "d") as null', [("submit",)])
