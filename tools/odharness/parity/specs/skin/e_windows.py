"""Window and pane parameters, winshow() and output() to controls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C
B, COL, STR = K.B, K.COL, K.STR


def build(s):
    K.setup(s)
    sg = lambda topic, ctl, param, vals, restore, prop=None: K.sg(s, topic, ctl, param, vals, restore, prop)

    # Hidden second window: window-only parameters
    t = "main.window"
    sg(t, "win2", "title", STR, "title=Second")
    sg(t, "win2", "alpha", ["128", "300", "abc"], "alpha=255")
    sg(t, "win2", "can-close", ["false", "0"], "can-close=true")
    sg(t, "win2", "can-minimize", ["false"], "can-minimize=true")
    sg(t, "win2", "can-resize", ["false"], "can-resize=true")
    sg(t, "win2", "statusbar", ["true", "bad"], "statusbar=false")
    sg(t, "win2", "titlebar", ["false"], "titlebar=true")
    sg(t, "win2", "transparent-color", COL, "transparent-color=none")
    sg(t, "win2", "icon", ["'nosuch.png'"], "icon=")
    sg(t, "win2", "image", ["'nosuch.png'"], "image=")
    sg(t, "win2", "image-mode", ["stretch", "tile", "bad"], "image-mode=center")
    sg(t, "win2", "keep-aspect", ["true"], "keep-aspect=false")
    sg(t, "win2", "macro", ["macro2", "", "nosuch"], "macro=macro")
    sg(t, "win2", "menu", ["menu2", "nosuch"], "menu=")
    sg(t, "win2", "on-close", ['"skinxnoop closed"', ""], "on-close=")
    sg(t, "win2", "on-status", ['"skinxnoop [[*]]"', ""], "on-status=")
    sg(t, "win2", "flash", ["2", "abc"], "flash=0")
    sg(t, "win2", "size", ["320x240", "bad"], "size=300x200")
    sg(t, "win2", "can-scroll", ["both"], "can-scroll=none")
    for p in ["inner-size", "outer-size", "screen-size"]:
        s.case(t, f"skin_x_kind(winget({C}, \"win2\", {q(p)}))")
    s.case(t, f'winget({C}, "win2", "is-visible;is-maximized;is-minimized;is-fullscreen;can-close;titlebar")')

    # Main window: only parameters that keep it on screen and usable
    t = "main.mainwindow"
    sg(t, "mainwindow", "title", ["Renamed", '"two words"', ""], 'title="parity skin"')
    sg(t, "mainwindow", "menu", ["menu2", "", "nosuch"], "menu=menu")
    sg(t, "mainwindow", "macro", ["macro2", "", "nosuch"], "macro=macro")
    sg(t, "mainwindow", "can-resize", ["false"], "can-resize=true")
    sg(t, "mainwindow", "can-minimize", ["false"], "can-minimize=true")
    sg(t, "mainwindow", "background-color", ["#ff0000", "none"], "background-color=#e0e0e0")
    sg(t, "mainwindow", "on-close", ["say", ""], "on-close=")
    sg(t, "mainwindow", "on-status", ['"skinxnoop [[*]]"', ""], "on-status=")
    sg(t, "mainwindow", "is-default", ["true"], "is-default=true")
    s.case(t, f'winget({C}, "mainwindow", "is-visible;is-pane;is-default;is-minimized;is-fullscreen;titlebar;can-close")')

    # Panes
    t = "main.pane"
    for p in ["lpane", "rpane", "tpane1", "spane"]:
        K.get(s, t, p, "is-pane;is-visible;title")
    sg(t, "lpane", "can-scroll", ["horizontal", "vertical", "both", "bad"], "can-scroll=none")
    sg(t, "lpane", "title", ["Renamed", ""], "title=Left")
    sg(t, "lpane", "image-mode", ["tile", "bad"], "image-mode=center")
    sg(t, "spane", "size", ["150x100", "bad"], "size=200x150")
    sg(t, "lpane", "on-status", ['"skinxnoop [[*]]"'], "on-status=")
    sg(t, "lpane", "alpha", ["128"], "alpha=255")
    sg(t, "lpane", "statusbar", ["true"], "statusbar=false")

    # winshow() and is-visible on windows
    t = "winshow"
    for call in ['winshow({C}, "win2", 1)', 'winshow({C}, "win2")', 'winshow({C}, "win2", 2)',
                 'winshow({C}, "win2", "yes")', 'winshow({C}, "win2", 0)', 'winshow({C}, "win2", null)',
                 'winshow({C}, "win2", "")', 'winshow({C}.mob, "win2", 1)']:
        s.body(t, [call.format(C=C), "sleep(2)", f'var/__v = winget({C}, "win2", "is-visible")',
                   f'winset({C}, "win2", "is-visible=false")', "sleep(2)",
                   f'var/__w = winget({C}, "win2", "is-visible")'], "list(__v, __w)")
    for ctl in ["lbl", "lpane", "map", "nosuch", "m_chk"]:
        s.body(t, [f'winshow({C}, {q(ctl)}, 0)', "sleep(2)", f'var/__v = winget({C}, {q(ctl)}, "is-visible")',
                   f'winshow({C}, {q(ctl)}, 1)', "sleep(2)", f'var/__w = winget({C}, {q(ctl)}, "is-visible")',
                   f'var/__x = winexists({C}, {q(ctl)})'], "list(__v, __w, __x)")
    s.body(t, [f'winshow({C}, "hid_lbl", 1)', "sleep(2)", f'var/__v = winget({C}, "hid_lbl", "is-visible")',
               f'winshow({C}, "hid_lbl", 0)', "sleep(2)", f'var/__w = winget({C}, "hid_lbl", "is-visible")'],
           "list(__v, __w)")
    for p in ["is-visible=1"]:
        s.body(t, [f'winset({C}, "win2", {q(p)})', "sleep(2)",
                   f'var/__v = winget({C}, "win2", "is-visible;is-minimized;is-maximized")',
                   f'winset({C}, "win2", "is-visible=false")', "sleep(2)"], "__v")
    # Visible window: child control state while shown
    s.body(t, [f'winshow({C}, "win2", 1)', "sleep(2)", f'winset({C}, "win2_lbl", "text=shown")', "sleep(1)",
               f'var/__v = winget({C}, "win2_lbl;win2_btn", "text;is-visible")', f'winset({C}, "win2_lbl", "text=second")',
               f'winshow({C}, "win2", 0)', "sleep(2)"], "__v")

    # output() to controls, checked through winget
    t = "output"
    for ctl, prop, rest in [("lbl", "text", "text=hello"), ("btn", "text", "text=Push"), ("inp", "text", "text="),
                            ("bar", "value", "value=30"), ("mainwindow.lbl", "text", None),
                            ("grd", "current-cell", "current-cell=1,1"), ("tabs", "current-tab", "current-tab=tpane1"),
                            ("nosuch", "text", None)]:
        target = "lbl" if ctl == "mainwindow.lbl" else ctl
        msgs = ['"out text"', '"<b>html</b> x"', "null"] if ctl == "lbl" else ['"75"']
        for msg in msgs:
            lines = [f'{C} << output({msg}, {q(ctl)})', "sleep(2)", f'var/__v = winget({C}, {q(target)}, {q(prop)})']
            if ctl == "mainwindow.lbl":
                lines.append(f'winset({C}, "lbl", "text=hello")')
            elif rest:
                lines.append(f'winset({C}, {q(target)}, {q(rest)})')
            s.body(t, lines, "__v")
    for dest in ["grd:2,1", "grd:1", "grd:9,9"]:
        s.body(t, [f'{C} << output("cell", {q(dest)})', "sleep(2)",
                   f'var/__v = winget({C}, "grd", "current-cell;cells")', f'winset({C}, "grd", "current-cell=1,1;cells=3x2")'],
               "__v")
    s.body(t, [f'{C} << output("x", "lbl:nosuchfn")', "sleep(2)", f'var/__v = winget({C}, "lbl", "text")',
               f'winset({C}, "lbl", "text=hello")'], "__v")
    s.body(t, [f'{C} << output("a", "lbl;lbl2")', "sleep(2)", f'var/__v = winget({C}, "lbl;lbl2", "text")',
               f'winset({C}, null, "lbl.text=hello;lbl2.text=world")'], "__v")
    s.body(t, [f'{C} << output("x", ":label")', "sleep(2)", f'var/__v = winget({C}, "lbl;lbl2", "text")',
               f'winset({C}, null, "lbl.text=hello;lbl2.text=world")'], "__v")
    s.body(t, [f'winset({C}, "lbl", "is-default=true")', "sleep(1)", f'{C} << output("dflt", ":label")', "sleep(2)",
               f'var/__v = winget({C}, "lbl", "text")', f'winset({C}, "lbl", "is-default=false;text=hello")'], "__v")
