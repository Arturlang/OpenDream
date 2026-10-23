"""input() as text and as message: defaults, title and message forms, typed answers."""
from gen import dm_str as q

USR = ["usr = C.mob"]
UNI = "Grüße ☃ 日本語 \U0001F600"


def build(s):
    s.prompts()
    p = s.prompt
    sub = [("submit",)]

    # as text: answers
    p("text typed", 'input(C, "Name?", "Name", "def") as text', [("text", "Bob"), ("submit",)])
    p("text default untouched", 'input(C, "Name?", "Name", "def") as text', sub)
    p("text typed empty", 'input(C, "Name?", "Name", "def") as text', [("text", ""), ("submit",)])
    p("text typed unicode", 'input(C, "Name?", "Name", "def") as text', [("text", UNI), ("submit",)])
    p("text typed brackets quotes", 'input(C, "Name?", "Name") as text', [("text", '[x] "q" <b>&amp;'), ("submit",)])
    p("text typed long", 'input(C, "Name?", "Name") as text', [("text", "abcdefghij" * 30), ("submit",)])
    p("text no default submit", 'input(C, "Name?", "Name") as text', sub)
    p("text implicit type", 'input(C, "Name?", "Name", "def")', [("text", "Bob"), ("submit",)])

    # as text: defaults of other types
    p("text num default", 'input(C, "Name?", "Name", 5) as text', sub)
    p("text null default", 'input(C, "Name?", "Name", null) as text', sub)
    p("text list default", 'input(C, "Name?", "Name", list("a", "b")) as text', sub)
    p("text unicode default", f'input(C, "Name?", "Name", {q(UNI)}) as text', sub)

    # text|null
    p("text|null typed", 'input(C, "Name?", "Name", "def") as text|null', [("text", "Bob"), ("submit",)])
    p("text|null cancel", 'input(C, "Name?", "Name", "def") as text|null', [("press", "Cancel")])
    p("text|null empty", 'input(C, "Name?", "Name", "def") as text|null', [("text", ""), ("submit",)])
    p("null|text cancel", 'input(C, "Name?", "Name", "def") as null|text', [("press", "Cancel")])
    p("text|null cancel after typing", 'input(C, "Name?", "Name", "def") as text|null', [("text", "Bob"), ("press", "Cancel")])

    # as message
    p("message typed", 'input(C, "Write", "Msg", "a") as message', [("text", "hello world"), ("submit",)])
    p("message default", f'input(C, "Write", "Msg", {q("line1" + chr(10) + "line2")}) as message', sub)
    p("message empty", 'input(C, "Write", "Msg", "a") as message', [("text", ""), ("submit",)])
    p("message|null cancel", 'input(C, "Write", "Msg", "a") as message|null', [("press", "Cancel")])

    # Recipient forms
    p("text usr form", 'input("Name?", "Name", "def") as text', sub, lines=USR)
    p("text mob recipient", 'input(C.mob, "Name?", "Name", "def") as text', sub)

    # Title and message
    p("text message only", 'input(C, "Name?") as text', [("text", "x"), ("submit",)])
    p("text empty title", 'input(C, "Name?", "", "d") as text', sub)
    p("text null title", 'input(C, "Name?", null, "d") as text', sub)
    p("text empty message", 'input(C, "", "Title", "d") as text', sub)
    p("text null message", 'input(C, null, "Title", "d") as text', sub)
    p("text num title message", 'input(C, 42, 7, "d") as text', sub)
    p("text long message", f'input(C, {q("word " * 80)}, "Long", "d") as text', sub)
    p("text multi-line message", f'input(C, {q("one" + chr(10) + "two" + chr(10) + "three")}, "Lines", "d") as text', sub)
    p("text unicode title message", f'input(C, {q(UNI)}, {q("Tïtle ✓")}, "d") as text', sub)
