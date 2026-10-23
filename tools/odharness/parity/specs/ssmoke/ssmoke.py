"""Skin framework self-check: a few winset/winget cases on a small skin."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(s):
    s.skin(HERE / "ssmoke.dmf", window=(860, 700))
    C = "live_client"
    s.case("winget", f'winget({C}, "lbl", "text")')
    s.case("winget", f'winget({C}, "btn", "size")')
    s.case("winget", f'winget({C}, "mainwindow", "title")')
    s.body("winset", [f'winset({C}, "lbl", "text=changed")', "sleep(2)"], f'winget({C}, "lbl", "text")')
    s.body("winset", [f'winset({C}, "lbl", "text=\\"quoted value\\";font-size=12")', "sleep(2)"], f'winget({C}, "lbl", "text;font-size")')
    s.case("winexists", f'winexists({C}, "btn")')
    s.case("winexists", f'winexists({C}, "nosuch")')
