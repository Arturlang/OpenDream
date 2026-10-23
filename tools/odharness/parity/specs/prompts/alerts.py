"""alert(): button counts, labels, title and message forms, each button."""
from gen import dm_str as q

USR = ["usr = C.mob"]


def build(s):
    s.prompts()
    p = s.prompt
    sub = [("submit",)]

    # Button counts
    p("alert no buttons submit", 'alert(C, "Sure?", "Confirm")', sub)
    p("alert message only submit", 'alert(C, "Sure?")', sub)
    p("alert 1 button press", 'alert(C, "Sure?", "Confirm", "Yes")', [("press", "Yes")])
    for b in ("Yes", "No"):
        p(f"alert 2 buttons press {b}", 'alert(C, "Sure?", "Confirm", "Yes", "No")', [("press", b)])
    p("alert 2 buttons submit", 'alert(C, "Sure?", "Confirm", "Yes", "No")', sub)
    for b in ("Yes", "No", "Maybe"):
        p(f"alert 3 buttons press {b}", 'alert(C, "Sure?", "Confirm", "Yes", "No", "Maybe")', [("press", b)])
    p("alert 3 buttons submit", 'alert(C, "Sure?", "Confirm", "Yes", "No", "Maybe")', sub)
    p("alert 3 buttons close", 'alert(C, "Sure?", "Confirm", "Yes", "No", "Maybe")', [("close",)])

    # Recipient forms
    p("alert usr form submit", 'alert("Sure?")', sub, lines=USR)
    p("alert usr form 2 buttons", 'alert("Sure?", "Confirm", "A", "B")', [("press", "B")], lines=USR)
    p("alert mob recipient", 'alert(C.mob, "Sure?", "Confirm", "A", "B")', [("press", "A")])

    # Empty, null and odd labels
    p("alert empty button1 submit", 'alert(C, "m", "t", "")', sub)
    p("alert empty button1 press B", 'alert(C, "m", "t", "", "B")', [("press", "B")])
    p("alert empty button2 press C", 'alert(C, "m", "t", "A", "", "C")', [("press", "C")])
    p("alert null button1 press B", 'alert(C, "m", "t", null, "B")', [("press", "B")])
    p("alert num buttons press 2", 'alert(C, "m", "t", 1, 2)', [("press", "2")])
    p("alert duplicate labels press", 'alert(C, "m", "t", "Yes", "Yes")', [("press", "Yes")])
    p("alert duplicate first third submit", 'alert(C, "m", "t", "A", "B", "A")', sub)
    long_label = "Long label " + "x" * 50
    p("alert long label press", f'alert(C, "m", "t", "Short", {q(long_label)})', [("press", long_label)])
    for b in ("Ja ✓", "Да", "日本"):
        p(f"alert unicode press {b}", f'alert(C, "m", "t", {q("Ja ✓")}, {q("Да")}, {q("日本")})', [("press", b)])
    p("alert OK label press", 'alert(C, "m", "t", "OK", "Cancel")', [("press", "Cancel")])

    # Title and message
    p("alert null title", 'alert(C, "Sure?", null, "A")', sub)
    p("alert empty title", 'alert(C, "Sure?", "", "A")', sub)
    p("alert empty message", 'alert(C, "", "Title", "A")', sub)
    p("alert null message", 'alert(C, null, "Title", "A")', sub)
    p("alert num message", 'alert(C, 42, 7, "A")', sub)
    p("alert multi-line message", f'alert(C, {q("line one\nline two\nline three")}, "Lines", "A")', sub)
    p("alert long message", f'alert(C, {q("word " * 80)}, "Long", "A")', sub)
    p("alert unicode title message", f'alert(C, {q("Grüße ☃ 日本語")}, {q("Tïtle ✓")}, "A")', sub)
    p("alert embedded text", 'alert(C, "Value: [1 + 2]", "Expr [3 * 2]", "B[4]")', [("press", "B4")])
