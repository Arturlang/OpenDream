"""Menu items and macros: parameters set with winset and read back with winget."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C
B = K.B


def build(s):
    K.setup(s)
    sg = lambda topic, ctl, param, vals, restore, prop=None: K.sg(s, topic, ctl, param, vals, restore, prop)

    # Menu items
    t = "menu"
    sg(t, "m_cmd", "command", K.CMD + ['"skinxecho \\"[[lbl.text]]\\""', "a%20b", "none"],
       'command="skinxecho \\"menu\\""')
    sg(t, "m_chk", "is-checked", K.B, "is-checked=false")
    sg(t, "m_cmd", "is-checked", ["true", "false"], "is-checked=false")
    sg(t, "m_chk", "can-check", B, "can-check=true")
    sg(t, "m_cmd", "is-disabled", B, "is-disabled=false")
    sg(t, "m_dis", "is-disabled", ["false", "true", "0"], "is-disabled=true")
    sg(t, "m_file", "is-disabled", ["true"], "is-disabled=false")
    sg(t, "m_cmd", "name", ['"two words"', '"Tab\\tF1"', ""], "name=Command")
    sg(t, "m_chk", "group", ["g2", ""], "group=")
    for e in ["m_file", "m_chk", "m_r1", "m_cmd", "m2_item"]:
        K.get(s, t, e, "name;command;is-checked;can-check;is-disabled;group")
    # Menu radio group
    for ctl in ["m_r2", "m_r1"]:
        s.body("menu.radio", [f'winset({C}, {q(ctl)}, "is-checked=true")', "sleep(1)",
                              f'var/__v = winget({C}, "m_r1;m_r2", "is-checked")',
                              f'winset({C}, null, "m_r1.is-checked=true;m_r2.is-checked=false")'], "__v")
    s.body("menu.radio", [f'winset({C}, "m_chk", "group=mg;is-checked=true")', "sleep(1)",
                          f'var/__v = winget({C}, "m_r1;m_r2;m_chk", "is-checked")',
                          f'winset({C}, "m_chk", "group=;is-checked=false")',
                          f'winset({C}, null, "m_r1.is-checked=true;m_r2.is-checked=false")'], "__v")
    # Decorated and odd ids
    for cid in ["menu.m_chk", "menu2.m_chk", "menu.Check me"]:
        s.body("menu.id", [f'winset({C}, {q(cid)}, "is-checked=true")', "sleep(1)",
                           f'var/__v = winget({C}, {q(cid)}, "is-checked")',
                           f'var/__w = winget({C}, "m_chk", "is-checked")', f'winset({C}, "m_chk", "is-checked=false")'],
               "list(__v, __w)")
    s.body("menu.id", [f'winset({C}, null, "m_chk.is-checked=true;menu.m_cmd.is-disabled=true")', "sleep(1)",
                       f'var/__v = winget({C}, "m_chk;m_cmd", "is-checked;is-disabled")',
                       f'winset({C}, null, "m_chk.is-checked=false;m_cmd.is-disabled=false")'], "__v")
    s.case("menu.id", f'winget({C}, "menu", "type;name;command")')
    s.case("menu.id", f'winget({C}, "menu", "nosuch")')
    # Write-only index and category move the item, so they use an item no other case reads later
    sg(t, "m2_item", "index", ["1", "0", "-1", "99", "abc"], "", "index;name")
    sg(t, "m2_item", "category", ["&Other", "nosuch", ""], "", "category;name")

    # Macros
    t = "macro"
    sg(t, "mac_f5", "command", K.CMD + ['"skinxnoop [[*]]"', "a%20b", "none"], 'command="skinxecho \\"f5\\""')
    sg(t, "mac_f5", "is-disabled", B, "is-disabled=false")
    sg(t, "mac_f5", "pass-through", B, "pass-through=false")
    sg(t, "mac_f5", "map-to", ["South", "GamepadDir", "", "nosuch"], "map-to=")
    sg(t, "mac_ctrl", "name", ["CTRL+R", "Shift+Alt+F9", "F9+REP", "", "bad key"],
       "name=CTRL+E", "name")
    for p in ["macro.F6", "macro.f6", "macro.CTRL+E", "macro.E+CTRL", "F6", "macro2.F7", "macro.F7"]:
        s.body("macro.id", [f'var/__o = winget({C}, {q(p)}, "command")',
                            f'winset({C}, {q(p)}, "command=changed")', "sleep(1)",
                            f'var/__v = winget({C}, {q(p)}, "command")', f'winset({C}, {q(p)}, list("command" = __o))',
                            "sleep(1)", f'var/__w = winget({C}, {q(p)}, "command")'], "list(__o, __v, __w)")
    s.body("macro.id", [f'winset({C}, "mac_ctrl", "name=CTRL+R")', "sleep(1)",
                        f'var/__v = list(winexists({C}, "macro.CTRL+R"), winexists({C}, "macro.CTRL+E"), '
                        f'winget({C}, "macro.CTRL+R", "command"))', f'winset({C}, "mac_ctrl", "name=CTRL+E")'], "__v")
    for e in ["mac_f5", "mac_ctrl", "mac2_f7", "macro.F6"]:
        K.get(s, "macro.id", e, "name;command;map-to;pass-through;is-disabled")
    s.case("macro.id", f'winget({C}, "macro", "type;name;command")')
    s.case("macro.id", f'skin_x_sorted(winget({C}, "macro.*", "name"))')
