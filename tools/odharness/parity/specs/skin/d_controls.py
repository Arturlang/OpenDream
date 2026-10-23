"""Type-specific parameters of each control type: set with winset, read back with winget, then restored."""
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

    # Label
    t = "label"
    sg(t, "lbl", "text", K.STR_FULL[:10], "text=hello")
    sg(t, "lbl", "align", ["left", "top-left", "bottom-right", "LEFT", "4", "bad"], "align=center")
    sg(t, "lbl", "text-wrap", B, "text-wrap=false")
    sg(t, "lbl", "image-mode", ["stretch", "tile", "bad"], "image-mode=center")
    sg(t, "lbl", "keep-aspect", B, "keep-aspect=false")
    sg(t, "lbl", "allow-html", B, "allow-html=false")
    sg(t, "lbl", "stretch", ["true", "false"], "stretch=false;image-mode=center", "stretch;image-mode")
    sg(t, "lbl", "image", ["'nosuch.png'"], "image=")
    sg(t, "lbl", "text", ['"<b>bold</b>"'], "text=hello")
    K.raw(s, t, "lbl", 'allow-html=true;text="<b>bold</b> x"', "text", "allow-html=false;text=hello")

    # Buttons
    t = "button"
    sg(t, "btn", "text", ['"two words"', "", '"&Amp"'], "text=Push")
    sg(t, "btn", "button-type", ["pushbox", "checkbox", "radio", "PUSHBOX", "bad"],
       "button-type=pushbutton")
    sg(t, "btn", "command", K.CMD + ['"skinxecho \\"[[lbl.text]]\\""'], "command=")
    sg(t, "btn", "group", ["g1", '"two words"'], "group=")
    sg(t, "btn", "is-checked", ["true"], "is-checked=false")
    sg(t, "btn", "is-flat", B, "is-flat=false")
    sg(t, "btn", "image", ["'nosuch.png'"], "image=")
    sg(t, "box", "is-checked", K.B, "is-checked=false")
    sg(t, "chk", "is-checked", B, "is-checked=false")
    sg(t, "chk", "button-type", ["pushbutton", "radio"], "button-type=checkbox", "button-type;is-checked")
    sg(t, "dis_btn", "is-disabled", ["false", "0"], "is-disabled=true")
    # Radio group: checking one unchecks the others in the same group
    for ctl, val in [("rad2", "true"), ("rad1", "false"), ("rad2", "1")]:
        s.body("button.radio", [f'winset({C}, {q(ctl)}, {q("is-checked=" + val)})', "sleep(1)",
                                f'var/__v = winget({C}, "rad1;rad2;rad3", "is-checked")',
                                f'winset({C}, "rad1", "is-checked=true")', "sleep(1)",
                                f'var/__w = winget({C}, "rad1;rad2;rad3", "is-checked")'], "list(__v, __w)")
    s.body("button.radio", [f'winset({C}, "rad3", "group=other;is-checked=true")', "sleep(1)",
                            f'var/__v = winget({C}, "rad1;rad2;rad3", "is-checked")',
                            f'winset({C}, "rad3", "group=grp1;is-checked=false")',
                            f'winset({C}, "rad1", "is-checked=true")', "sleep(1)",
                            f'var/__w = winget({C}, "rad1;rad2;rad3", "is-checked")'], "list(__v, __w)")
    s.body("button.radio", [f'winset({C}, null, "rad2.is-checked=true;rad3.is-checked=true")', "sleep(1)",
                            f'var/__v = winget({C}, "rad1;rad2;rad3", "is-checked")',
                            f'winset({C}, "rad1", "is-checked=true")', "sleep(1)",
                            f'var/__w = winget({C}, "rad1;rad2;rad3", "is-checked")'], "list(__v, __w)")
    s.body("button.radio", [f'winset({C}, "box", "button-type=radio;group=grp1;is-checked=true")', "sleep(1)",
                            f'var/__v = winget({C}, "rad1;rad2;rad3;box", "is-checked")',
                            f'winset({C}, "box", "button-type=pushbox;group=;is-checked=false")',
                            f'winset({C}, "rad1", "is-checked=true")', "sleep(1)",
                            f'var/__w = winget({C}, "rad1;rad2;rad3;box", "is-checked")'], "list(__v, __w)")

    # Input
    t = "input"
    sg(t, "inp", "text", ['"two words"', "none", '"esc \\"q\\""', '"line\\nbreak"'], "text=")
    sg(t, "inp", "command", K.CMD, "command=")
    sg(t, "inp", "is-password", B, "is-password=false")
    sg(t, "inp", "no-command", B, "no-command=false")
    sg(t, "inp", "multi-line", ["true", "false"], "multi-line=false")
    sg(t, "inp", "on-focus", ["say"], "on-focus=")
    sg(t, "inp", "on-blur", ["say"], "on-blur=")
    K.raw(s, t, "inp", 'is-password=true;text=secret', "text;is-password", "is-password=false;text=")

    # Output
    t = "output"
    sg(t, "out", "max-lines", ["0", "10", "-1", "abc"], "max-lines=1000")
    sg(t, "out", "link-color", COL, "link-color=#0000ff")
    sg(t, "out", "visited-color", COL, "visited-color=#ff00ff")
    sg(t, "out", "style", ['".a { font-weight: bold; }"'], "style=")
    sg(t, "out", "legacy-size", B, "legacy-size=true")
    sg(t, "out", "enable-http-images", B, "enable-http-images=false")
    sg(t, "out", "image", ["'nosuch.png'"], "image=")

    # Browser
    t = "browser"
    sg(t, "brw", "show-history", B, "show-history=false")
    sg(t, "brw", "show-url", B, "show-url=false")
    sg(t, "brw", "use-title", B, "use-title=false")
    sg(t, "brw", "auto-format", B, "auto-format=false")
    sg(t, "brw", "inner-background-color", COL + ["transparent"], "inner-background-color=#ffffff")
    sg(t, "brw", "on-show", ["say"], "on-show=")
    sg(t, "brw", "on-hide", ["say"], "on-hide=")

    # Grid
    t = "grid"
    sg(t, "grd", "cells", ["4x3", "4,3", "-1x5", "abc"], "cells=3x2")
    sg(t, "grd", "current-cell", ["2,2", "2x2", "9,9", "abc"], "current-cell=1,1")
    sg(t, "grd", "cell-span", ["2x1", "2,2", "abc"], "cell-span=1x1")
    sg(t, "grd", "is-list", B, "is-list=false")
    K.raw(s, t, "grd", "is-list=true;cells=5", "cells;is-list", "is-list=false;cells=3x2")
    K.raw(s, t, "grd", "is-list=true;current-cell=3", "current-cell;is-list", "is-list=false;current-cell=1,1")
    sg(t, "grd", "show-lines", ["none", "vertical", "bad"], "show-lines=both")
    sg(t, "grd", "show-names", B, "show-names=true")
    sg(t, "grd", "small-icons", B, "small-icons=false")
    sg(t, "grd", "style", ['"body{color:red}"', ""], "style=")
    sg(t, "grd", "highlight-color", ["#ff0000", "bad"], "highlight-color=#00ff00")
    sg(t, "grd", "line-color", ["#ff0000", "none"], "line-color=#c0c0c0")
    sg(t, "grd", "link-color", ["#ff0000", "none"], "link-color=#0000ff")
    sg(t, "grd", "visited-color", ["#ff0000", "bad"], "visited-color=#ff00ff")
    sg(t, "grd", "enable-http-images", B, "enable-http-images=false")

    # Bar and slider
    t = "bar"
    sg(t, "bar", "value", ["0", "55.5", "-10", "150", "abc"], "value=30")
    sg(t, "bar", "dir", ["north", "clockwise", "ccw", "8", "NORTH", "bad"], "dir=east")
    sg(t, "bar", "angle1", ["90", "-45", "abc"], "angle1=0")
    sg(t, "bar", "angle2", ["360", "400", "abc"], "angle2=180")
    sg(t, "bar", "width", ["0", "50", "-1"], "width=10")
    sg(t, "bar", "bar-color", COL, "bar-color=#00ff00")
    sg(t, "bar", "is-slider", B, "is-slider=false")
    sg(t, "bar", "on-change", ['"skinxnoop [[*]]"', "none"], "on-change=")
    sg(t, "sld", "value", ["75", "101", "33.3"], "value=50")
    sg(t, "sld", "is-slider", ["false", "true"], "is-slider=true")
    sg(t, "sld", "bar-color", ["#ff0000", "none"], "bar-color=#0000ff")

    # Tab
    t = "tab"
    rt = "tabs=tpane1,tpane2;current-tab=tpane1"
    for v in ["tpane2,tpane1", "tpane1,tpane2,spane", "+spane", "%2Bspane", "%2Dtpane2", "nosuch", ""]:
        K.raw(s, t, "tabs", "tabs=" + v, "tabs;current-tab", rt)
    for v in ["tpane2", "spane", "nosuch", "", "Two"]:
        K.raw(s, t, "tabs", "current-tab=" + v, "tabs;current-tab", rt)
    s.case(t, f'list(skin_x_sg("tabs", "current-tab=tpane2", "current-tab", null), '
              f'winget({C}, "tpane2;tpane1", "is-visible"), skin_x_sg("tabs", {q(rt)}, "current-tab", null))')
    sg(t, "tabs", "multi-line", B, "multi-line=true")
    sg(t, "tabs", "on-tab", ['"skinxnoop [[*]]"', ""], "on-tab=")
    sg(t, "tpane2", "title", ["Renamed", '"two words"', ""], "title=Two")

    # Child
    t = "child"
    rc = "left=lpane;right=rpane;is-vert=true;splitter=50;show-splitter=true"
    for p in ["top=spane", "bottom=spane", "left=nosuch", "right=none", "left=rpane;right=lpane",
              "left=lpane;right=lpane"]:
        K.raw(s, t, "split", p, "left;right;top;bottom", rc)
    for p in ["left=spane", "right=", "left=tpane1"]:
        s.case(t, f"list(skin_x_sg(\"split\", {q(p)}, \"left;right\", null), winget({C}, \"tabs\", \"tabs\"), "
                  f"winget({C}, \"lpane;rpane;spane\", \"is-visible\"), skin_x_sg(\"split\", {q(rc)}, \"left;right\", null), "
                  f"skin_x_sg(\"tabs\", {q(rt)}, \"tabs\", null))")
    sg(t, "split", "is-vert", B, "is-vert=true")
    sg(t, "split", "splitter", ["0", "150", "33.3", "abc"], "splitter=50")
    sg(t, "split", "show-splitter", B, "show-splitter=true")
    sg(t, "split", "lock", ["left", "right", "bad"], "lock=none")
    s.case(t, f'skin_x_kind(winget({C}, "lpane", "size"))')

    # Info
    t = "info"
    sg(t, "info", "allow-html", B, "allow-html=true")
    sg(t, "info", "has-stats", ["false", "bad"], "has-stats=true")
    sg(t, "info", "has-verbs", ["false", "bad"], "has-verbs=true")
    sg(t, "info", "multi-line", ["false", "true"], "multi-line=true")
    sg(t, "info", "highlight-color", COL, "highlight-color=#00ff00")
    sg(t, "info", "prefix-color", ["#00ff00", "none"], "prefix-color=#ff0000")
    sg(t, "info", "suffix-color", ["#00ff00", "none"], "suffix-color=#0000ff")
    sg(t, "info", "tab-background-color", ["#00ff00", "none"], "tab-background-color=#ffffff")
    sg(t, "info", "tab-text-color", ["#00ff00", "bad"], "tab-text-color=#000000")
    sg(t, "info", "tab-font-family", ['"Courier New"'], "tab-font-family=")
    sg(t, "info", "tab-font-size", ["12", "abc"], "tab-font-size=0")
    sg(t, "info", "tab-font-style", ["bold", "italic underline"], "tab-font-style=")
    sg(t, "info", "on-show", ["say"], "on-show=")
    sg(t, "info", "on-hide", ["say"], "on-hide=")
    sg(t, "info", "on-tab", ['"skinxnoop [[*]]"', ""], "on-tab=")
    sg(t, "info", "current-tab", ["Verbs", "nosuch"], "")

    # Map: only parameters that leave the map usable, each restored
    t = "map"
    sg(t, "map", "zoom", ["0.5", "-1", "abc"], "zoom=1", "zoom")
    sg(t, "map", "zoom", ["2", "0"], "zoom=1", "zoom;view-size")
    sg(t, "map", "icon-size", ["64", "16", "abc"], "icon-size=0;zoom=1", "icon-size;zoom")
    sg(t, "map", "zoom-mode", ["distort", "blur", "bad"], "zoom-mode=normal")
    sg(t, "map", "letterbox", B, "letterbox=true")
    sg(t, "map", "text-mode", B, "text-mode=false")
    sg(t, "map", "style", ['".maptext{color:red}"', ""], "style=")
    sg(t, "map", "on-show", ["say"], "on-show=")
    sg(t, "map", "on-hide", ["say"], "on-hide=")
    sg(t, "map", "view-size", ["100x100"], "", "view-size")
