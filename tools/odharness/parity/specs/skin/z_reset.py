"""winset(C, null, "reset=true") last: it puts the whole skin back to the skin file state."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402

C = K.C


def build(s):
    K.setup(s)
    s.body("reset", [f'winset({C}, "lbl", "text=changed")', f'winset({C}, "cr_reset", "type=label;parent=win2;text=rt")',
                     f'winclone({C}, "win2", "cl_reset")', "sleep(2)",
                     f'var/__a = list(winget({C}, "lbl", "text"), winexists({C}, "cr_reset"), winexists({C}, "cl_reset"))',
                     f'winset({C}, null, "reset=true")', "sleep(5)",
                     f'var/__b = list(winget({C}, "lbl", "text"), winexists({C}, "cr_reset"), winexists({C}, "cl_reset"))'],
           "list(__a, __b)")
    s.case("reset", f'list(winget({C}, "win2", "is-pane;title;is-visible"), winget({C}, "tabs", "tabs;current-tab"), '
                    f'winget({C}, "split", "left;right"), winget({C}, "rad1;rad2;rad3", "is-checked"))')
    s.case("reset", f'skin_x_sorted(winget({C}, null, "windows"))')
    s.case("reset", f'skin_x_sorted(winget({C}, null, "panes"))')
    s.case("reset", f'skin_x_sorted(winget({C}, null, "menus"))')
    s.case("reset", f'skin_x_sorted(winget({C}, null, "macros"))')
    s.case("reset", f'winget({C}, "lpane.dup;rpane.dup", "text")')
    s.case("reset", f'winget({C}, "map", "zoom;view-size;is-visible")')
