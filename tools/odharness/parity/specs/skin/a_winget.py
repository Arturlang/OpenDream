"""winget() forms, special wingets and winexists() against the test skin."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C

WINDOWS = ["mainwindow", "win2"]
PANES = ["lpane", "rpane", "tpane1", "tpane2", "spane"]
CONTROLS = ["map", "out", "inp", "brw", "btn", "box", "chk", "rad1", "rad2", "rad3", "lbl", "lbl2", "bar", "sld",
            "grd", "info", "split", "tabs", "anc", "dis_btn", "hid_lbl", "lp_lbl", "rp_btn", "tp1_lbl", "tp2_lbl",
            "sp_lbl", "win2_lbl", "win2_btn"]
MENUS = ["menu", "menu2"]
MENU_ITEMS = ["m_file", "m_chk", "m_r1", "m_r2", "m_dis", "m_cmd", "m2_top", "m2_item"]
MACROS = ["macro", "macro2"]
MACRO_ITEMS = ["mac_f5", "mac_ctrl", "mac2_f7", "macro.F6", "macro.mac_f5", "macro.CTRL+E"]
ALL = WINDOWS + PANES + CONTROLS + MENUS + MENU_ITEMS + MACROS + MACRO_ITEMS


def build(s):
    K.setup(s)
    g = lambda ctl, prop: K.get(s, "winget.form", ctl, prop)

    # Per element: type and existence, plus flags and focus kind for windows, panes and controls
    multi = set(WINDOWS + PANES + CONTROLS)
    for e in ALL:
        if e in multi:
            s.case("winget.type", f"list(winget({C}, {q(e)}, \"type\"), winexists({C}, {q(e)}), "
                                  f"winget({C}, {q(e)}, \"id;is-visible;is-disabled;is-default\"), "
                                  f"skin_x_kind(winget({C}, {q(e)}, \"focus\")))")
        else:
            s.case("winget.type", f"list(winget({C}, {q(e)}, \"type\"), winexists({C}, {q(e)}))")
    # One element of each kind: parent and the "*" key list
    for e in ["mainwindow", "win2", "lpane", "map", "out", "inp", "brw", "btn", "box", "chk", "rad1", "lbl", "bar",
              "sld", "grd", "info", "split", "tabs", "lp_lbl", "menu", "m_chk", "m_file", "macro", "mac_f5", "macro.F6"]:
        s.case("winget.keys", f"list(winget({C}, {q(e)}, \"parent\"), skin_x_keys({q(e)}))")
    for e in PANES + ["win2"]:
        K.get(s, "winget.pane", e, "is-pane;title;can-scroll")
    for e in ["lbl", "map", "grd", "split", "tabs", "lp_lbl", "tp1_lbl", "win2_lbl"]:
        K.get(s, "winget.geom", e, "pos;size;anchor1;anchor2")

    # Single and multiple properties, odd property strings
    for prop in ["text", "text;align", "text;align;", "text;text", "TEXT", " text", "", "nosuch", "text;nosuch",
                 "text as arg", "size.x", "pos;size;is-visible", "background-color;text-color",
                 "font-size;font-family;font-style", "border;is-transparent;drop-zone;right-click",
                 "on-size;saved-params", "*;text", "text&align"]:
        g("lbl", prop)
    s.case("winget.form", f'winget({C}, "lbl", null)')
    s.case("winget.form", f'winget({C}, "lbl", 1)')
    s.case("winget.form", f'skin_x_kind(winget({C}, "lbl", "*"))')

    # Control id forms
    for cid in ["mainwindow.lbl", "lpane.lp_lbl", "mainwindow.lp_lbl", "lpane.dup", "dup", "split.lpane.lp_lbl",
                "lbl;lbl2", "lbl;nosuch", "LBL", " lbl", "nosuch.lbl", "win2.lbl", ".lbl", ":label"]:
        g(cid, "text")
    for cid in [":map", ":output", ":input", ":info", ":browser", ":main", ":MAP", ":map;:output"]:
        g(cid, "type")
    for cid in ["nosuch", "mainwindow.", "menu.m_chk"]:
        g(cid, "type")
    s.case("winget.form", f'winget({C}, null, "text")')
    s.case("winget.form", f'winget({C}, "", "type")')

    # Wildcards
    for cid, prop in [("lpane.*", "type"), ("rpane.*", "text"), ("win2.*", "is-visible"), ("mainwindow.*", "type"),
                      ("tpane1.*", "type;text"), ("menu.*", "is-checked"), ("menu.*", "name"),
                      ("macro.*", "command"), ("macro2.*", "name"), ("nosuch.*", "type"), ("lpane.*", "nosuch"),
                      ("*", "type"), ("lbl.*", "text")]:
        s.case("winget.wild", f"skin_x_sorted(winget({C}, {q(cid)}, {q(prop)}))")
    s.case("winget.wild", f'skin_x_keys_of(winget({C}, "lpane.*", "*"))')
    s.case("winget.wild", f'skin_x_keys_of(winget({C}, "lbl;lbl2", "*"))')

    # Special wingets: ids lists sorted and as given, machine values as kinds only
    for prop in ["windows", "panes", "menus", "macros"]:
        s.case("winget.special", f"skin_x_sorted(winget({C}, null, {q(prop)}))")
        s.case("winget.special", f"winget({C}, null, {q(prop)})")
    for prop in ["focus", "sound", "hwmode", "url", "dpi", "screen-size", "nosuch", "", "windows;menus", "reset"]:
        s.case("winget.special", f"skin_x_kind(winget({C}, null, {q(prop)}))")

    # Values of read-only or unlisted params, one multi-property winget per element
    for ctl, props in [
            ("mainwindow", "is-pane;is-default;is-maximized;is-minimized;is-fullscreen;menu;macro;statusbar;titlebar;can-close;alpha"),
            ("win2", "is-visible;is-maximized;size;title;macro;menu"),
            ("map", "view-size;zoom;icon-size"), ("inp", "multi-line"), ("info", "multi-line"),
            ("tabs", "multi-line;tabs;current-tab"), ("split", "left;right;top;bottom;splitter"),
            ("grd", "cells;current-cell;cell-span"), ("bar", "value"), ("sld", "value;is-slider"),
            ("dis_btn", "is-disabled"), ("hid_lbl", "is-visible"), ("rad1", "is-checked;group"),
            ("box", "button-type"), ("chk", "button-type"), ("lbl", "dpi;is-default;parent"),
            ("mainwindow", "dpi"), ("out", "is-default"), ("anc", "anchor1;anchor2"),
            ("m_chk", "can-check;category;index"), ("m_dis", "is-disabled"), ("m_r1", "group"), ("m_cmd", "command"),
            ("m_file", "name"), ("mac_f5", "name;command;map-to;pass-through;is-disabled"), ("macro.F6", "command"),
            ("lp_lbl", "parent")]:
        K.get(s, "winget.value", ctl, props)
    for ctl, prop in [("mainwindow", "pos"), ("mainwindow", "size"), ("mainwindow", "inner-size"),
                      ("mainwindow", "outer-pos")]:
        s.case("winget.value", f"skin_x_kind(winget({C}, {q(ctl)}, {q(prop)}))")

    # Player argument forms
    s.case("winget.player", f'winget({C}.mob, "lbl", "text")')
    s.case("winget.player", 'winget(null, "lbl", "text")')
    s.case("winget.player", f'winexists({C}.mob, "lbl")')
    s.case("winget.player", 'winexists(null, "lbl")')
    s.case("winget.player", 'winget("live_client", "lbl", "text")')

    # winexists edge forms
    for cid in ["nosuch", "", ":map", ":label", "mainwindow.lbl", "lpane.dup", "dup", "LBL", "lbl;lbl2",
                "menu.m_file", "window"]:
        s.case("winexists", f"winexists({C}, {q(cid)})")
    s.case("winexists", f"winexists({C}, null)")
