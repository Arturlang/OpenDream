"""Prompt framework self-check: one case per prompt kind."""


def build(s):
    s.prompts()
    s.prompt("text typed", 'input(C, "Your name?", "Name", "def") as text', [("text", "Bob"), ("submit",)])
    s.prompt("text cancel", 'input(C, "Your name?", "Name", "def") as text|null', [("press", "Cancel")])
    s.prompt("num typed", 'input(C, "How many?", "Count", 3) as num', [("text", "42"), ("submit",)])
    s.prompt("message", 'input(C, "Write", "Msg", "a") as message', [("text", "line1"), ("submit",)])
    s.prompt("list pick 2", 'input(C, "Pick", "List") in list("alpha", "beta", "gamma")', [("select", 1), ("submit",)])
    s.prompt("list default", 'input(C, "Pick", "List", "gamma") in list("alpha", "beta", "gamma")', [("submit",)])
    s.prompt("alert 3 buttons", 'alert(C, "Sure?", "Confirm", "Yes", "No", "Maybe")', [("press", "No")])
