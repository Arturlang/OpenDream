"""input() as num, color, null, anything and type combinations."""


def build(s):
    s.prompts()
    p = s.prompt
    sub = [("submit",)]

    # as num
    p("num typed", 'input(C, "How many?", "Count", 3) as num', [("text", "42"), ("submit",)])
    p("num default untouched", 'input(C, "How many?", "Count", 3) as num', sub)
    p("num typed negative float", 'input(C, "How many?", "Count", 3) as num', [("text", "-2.5"), ("submit",)])
    p("num typed zero", 'input(C, "How many?", "Count", 3) as num', [("text", "0"), ("submit",)])
    p("num typed big", 'input(C, "How many?", "Count", 3) as num', [("text", "16777217"), ("submit",)])
    p("num no default submit", 'input(C, "How many?", "Count") as num', [("text", "7"), ("submit",)])
    p("num float default", 'input(C, "How many?", "Count", 0.1) as num', sub)
    p("num big default", 'input(C, "How many?", "Count", 1e7) as num', sub)
    p("num text default numeric", 'input(C, "How many?", "Count", "12") as num', sub)
    p("num null default typed", 'input(C, "How many?", "Count", null) as num', [("text", "5"), ("submit",)])
    p("num|null typed", 'input(C, "How many?", "Count", 3) as num|null', [("text", "8"), ("submit",)])
    p("num|null cancel", 'input(C, "How many?", "Count", 3) as num|null', [("press", "Cancel")])
    p("num|null cancel no default", 'input(C, "How many?", "Count") as num|null', [("press", "Cancel")])
    p("null|num cancel", 'input(C, "How many?", "Count", 3) as null|num', [("press", "Cancel")])

    # as color (no typing: BYOND shows the system colour dialog)
    p("color default submit", 'input(C, "Pick", "Colour", "#00ff00") as color', sub)
    p("color named default submit", 'input(C, "Pick", "Colour", "red") as color', sub)
    p("color no default submit", 'input(C, "Pick", "Colour") as color', sub)
    p("color|null cancel", 'input(C, "Pick", "Colour", "#123456") as color|null', [("press", "Cancel")])

    # as null, anything and combinations. "as anything" with no list and no null is left out: BYOND shows an empty
    # list with only OK and opens it again on every OK, so nothing can answer it.
    p("null|anything no list cancel", 'input(C, "Any?", "Any", "def") as null|anything', [("press", "Cancel")])
    p("text|num typed number", 'input(C, "Val?", "Mixed", "d") as text|num', [("text", "12"), ("submit",)])
    p("text|num typed text", 'input(C, "Val?", "Mixed", "d") as text|num', [("text", "abc"), ("submit",)])
    p("num|text num default", 'input(C, "Val?", "Mixed", 4) as num|text', sub)
    p("message|num typed", 'input(C, "Val?", "Mixed", "d") as message|num', [("text", "9"), ("submit",)])
    p("text|num|null cancel", 'input(C, "Val?", "Mixed", "d") as text|num|null', [("press", "Cancel")])
