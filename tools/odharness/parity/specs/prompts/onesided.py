"""Cases that compile on one engine only. The build stubs them as COMPILE_ERROR on the engine that rejects them."""


def build(s):
    s.prompts()
    # OD rejects a text or num filter on "in list"
    s.prompt("in list as text", 'input(C, "Pick", "T") as text in list("a", "b")', [("select", 1), ("submit",)])
    s.prompt("in list as num", 'input(C, "Pick", "T") as num in list(1, 2, 3)', [("select", 2), ("submit",)])
    s.prompt("in list as num with text items", 'input(C, "Pick", "T") as num in list("a", 2, "c")', [("submit",)])
    s.prompt("in list as text with num items", 'input(C, "Pick", "T") as text in list(1, "b", 3)', [("submit",)])
    s.prompt("in empty list as text", 'input(C, "Pick", "T") as text in list()', [])
    # BYOND rejects named arguments to alert() and input()
    s.prompt("alert named args", 'alert(C, Message = "Sure?", Title = "T", Button1 = "Yes", Button2 = "No")', [("press", "No")])
    s.prompt("input named args", 'input(C, Message = "Name?", Title = "T", Default = "d") as text', [("submit",)])
