"""Parameters common to all positionable controls: full value pools on the label, a sample on every other type."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C

# id, topic name, background colour, pos, size, default drop-zone
CTLS = [
    ("btn", "button", "#d0d0d0", "0,232", "100x24", "false"),
    ("inp", "input", "#ffffff", "296,166", "300x24", "false"),
    ("out", "output", "#ffffff", "296,0", "300x160", "false"),
    ("brw", "browser", "#ffffff", "604,0", "430x224", "false"),
    ("grd", "grid", "#ffffff", "416,262", "300x120", "true"),
    ("bar", "bar", "#ffffff", "0,262", "200x20", "false"),
    ("info", "info", "#ffffff", "724,262", "310x200", "true"),
    ("split", "child", "#e0e0e0", "0,390", "400x200", "false"),
    ("tabs", "tab", "#e0e0e0", "408,390", "300x200", "false"),
    ("map", "map", None, None, None, "true"),
    ("win2", "main", "#e0e0e0", None, None, "false"),
    ("lpane", "pane", "#f0f0f0", None, None, "false"),
    ("lp_lbl", "label", "#f0f0f0", "0,0", "180x20", "false"),
]


def build(s):
    K.setup(s)
    sg = lambda topic, ctl, param, vals, restore: K.sg(s, topic, ctl, param, vals, restore)

    # Label: wider pools
    t = "label.common"
    sg(t, "lbl", "is-visible", K.B, "is-visible=true")
    sg(t, "lbl", "is-disabled", ["true", "1"], "is-disabled=false")
    sg(t, "lbl", "is-transparent", ["true"], "is-transparent=false")
    sg(t, "lbl", "drop-zone", ["true"], "drop-zone=false")
    sg(t, "lbl", "right-click", ["true"], "right-click=false")
    sg(t, "lbl", "border", ["line", "sunken", "LINE", "bad"], "border=none")
    sg(t, "lbl", "on-size", ['"skinxnoop [[*]]"', '"a;b"'], "on-size=")
    sg(t, "lbl", "anchor1", ["0,0", "50,50", "bad", "0x0"], "anchor1=none")
    sg(t, "lbl", "anchor2", ["100,100", "150,-10"], "anchor2=none")
    sg(t, "lbl", "is-default", ["true", "false"], "is-default=false")
    sg(t, "lbl", "focus", ["false"], "")
    # Read-only or write-only params on a label no later case uses
    sg(t, "hid_lbl", "type", ["nosuch", "button"], "")
    s.body(t, [f'winset({C}, "hid_lbl", "id=renamed")', "sleep(1)",
               f'var/__v = list(winexists({C}, "renamed"), winexists({C}, "hid_lbl"))',
               f'winset({C}, "renamed", "id=hid_lbl")'], "__v")
    s.body(t, [f'winset({C}, "hid_lbl", "parent=win2")', "sleep(1)",
               f'var/__v = list(winexists({C}, "hid_lbl"), winexists({C}, "win2.hid_lbl"), '
               f'winexists({C}, "mainwindow.hid_lbl"), winget({C}, "hid_lbl", "parent"))'], "__v")
    for v in ['"is-checked;size"', ""]:
        s.body(t, [f'var/__o = winget({C}, "lbl", "saved-params")', f'winset({C}, "lbl", {q("saved-params=" + v)})',
                   "sleep(1)", f'var/__v = winget({C}, "lbl", "saved-params")',
                   f'winset({C}, "lbl", list("saved-params" = __o))'], "__v")
    s.case(t, f'winget({C}, "lbl", "id;type;parent")')
    # Anchored label: anchors set and read, size as a kind only (it follows the window)
    sg(t, "anc", "anchor1", ["0,0", "50,0", "none"], "anchor1=0,0")
    sg(t, "anc", "anchor2", ["100,0", "100,100", "none"], "anchor2=100,0")
    s.case(t, f'skin_x_kind(winget({C}, "anc", "size"))')

    # Every other control type: a sample of each common parameter
    for ctl, typ, bg, pos, size, dz in CTLS:
        t = f"{typ}.common"
        # Colours and font in one call, flags in one call, then visibility, geometry and on-size
        look = "background-color;text-color;font-size;font-style"
        K.raw(s, t, ctl, "background-color=#ff0000;text-color=#00ff00;font-size=14;font-style=bold italic", look,
              f"background-color={bg or '#e0e0e0'};text-color=#000000;font-size=0;font-style=")
        flip = "false" if dz == "true" else "true"
        K.raw(s, t, ctl, f"is-disabled=true;is-transparent=true;drop-zone={flip};right-click=true",
              "is-disabled;is-transparent;drop-zone;right-click",
              f"is-disabled=false;is-transparent=false;drop-zone={dz};right-click=false")
        if ctl not in ("map", "win2"):
            sg(t, ctl, "is-visible", ["false"], "is-visible=true")
        if pos:
            K.raw(s, t, ctl, "pos=12,34;size=90x20", "pos;size", f"pos={pos};size={size}")
        K.raw(s, t, ctl, 'on-size="skinxnoop [[*]]"', "on-size;saved-params", "on-size=")
