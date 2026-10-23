"""winset() parameter string parsing: separators, quoting, escapes, url encoding, value formats, ids, lists."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C
R_LBL = "text=hello;align=center;font-size=0;text-color=#000000;background-color=#e0e0e0"
R_TWO = "lbl.text=hello;lbl2.text=world"


def build(s):
    K.setup(s)
    t = "winset.parse"

    def lbl(params, prop="text"):
        K.raw(s, t, "lbl", params, prop, R_LBL)

    # Separators
    for p in ["text=a;align=left", "text=a&align=left", "text=a; align=left", "text=a;;align=left",
              "text=a;align=left&font-size=12", "text=a\nalign=left", "text=a align=left", "text=a,align=left"]:
        lbl(p, "text;align;font-size")

    # Quoting and escapes
    for v in ['"quoted value"', '"a \\"b\\" c"', '"a;b"', '"a&b"', '"back\\\\slash"', '"line\\nbreak"',
              "'single'", '""', '"a" "b"', '"[[lbl2.text]]"', "[[lbl2.text]]", "semi\\;colon", 'two words']:
        lbl("text=" + v)

    # URL encoding
    for v in ["a%20b", "a+b", "%3B", "%26", "%22q%22", "%25", "%zz", "%", "%C3%A9", "%0A", "%2B"]:
        lbl("text=" + v)
    lbl("text%3Dx")
    lbl("te%78t=x")
    lbl("text=a%3Balign%3Dleft", "text;align")

    # Non-ASCII and control characters
    for v in ["héllo", '"héllo"', '"日本"', '"emoji \U0001F600"']:
        lbl("text=" + v)

    # Names, spacing and repeats
    for p in ["TEXT=a", "text = a", "text==a", "text=a=b", "text", "=a", "text=a;text=b", "nosuch=1;text=a",
              "text=", "lbl.text=a", "lbl2.text=a"]:
        lbl(p, "text")

    # Boolean spellings on a harmless bool (text-wrap)
    for v in K.B_FULL:
        K.raw(s, "winset.bool", "lbl", "text-wrap=" + v, "text-wrap", "text-wrap=false")
    for v in ["0", ""]:
        K.raw(s, "winset.bool", "lbl", "text-wrap=true;text-wrap=" + v, "text-wrap", "text-wrap=false")

    # Size and position spellings on lbl
    for v in ["100x50", "100,50", "100 50", "-5x10", "abc", "", "100", '"80x40"', "50.7x20.2"]:
        K.raw(s, "winset.size", "lbl", "size=" + v, "size", "size=200x24")
    for v in ["10,20", "10x20", "-5,-5", "abc", "", '"12,34"', "10.6,20.4"]:
        K.raw(s, "winset.pos", "lbl", "pos=" + v, "pos", "pos=540,232")
    K.raw(s, "winset.pos", "lbl", "pos=600,240;size=150x20", "pos;size", "pos=540,232;size=200x24")

    # Colour spellings
    for v in ["#00ff00", "#0f0", "#00F", "red", "Blue", "none", "", "#12345", "#ff000080", "#gg0000",
              "rgb(1,2,3)", "transparent", '"#123456"', "123456", "%23ff0000"]:
        K.raw(s, "winset.color", "lbl", "text-color=" + v, "text-color", "text-color=#000000")
    for v in ["none", "red"]:
        K.raw(s, "winset.color", "lbl", "background-color=" + v, "background-color", "background-color=#e0e0e0")

    # Font specs
    for p in ['font-family="Courier New"', "font-family=Arial,Helvetica", 'font-family="nosuch font"',
              "font-size=7.5", "font-size=-3", "font-size=abc", "font-size=12pt", "font-style=bold italic",
              "font-style=bold,italic", "font-style=BOLD", "font-style=none", "font-style=bad",
              "font-family=Arial;font-size=14;font-style=bold"]:
        K.raw(s, "winset.font", "lbl", p, "font-family;font-size;font-style",
              "font-family=;font-size=0;font-style=")

    # Several controls in one call (null id), decorated ids
    def two(params):
        s.case("winset.multi", f"skin_x_sgn({q(params)}, \"lbl;lbl2\", \"text\", {q(R_TWO)})")

    for p in ["lbl.text=a;lbl2.text=b", "lbl.text=a&lbl2.text=b", "mainwindow.lbl.text=a;mainwindow.lbl2.text=b",
              'lbl.text="a b";lbl2.text="c d"', "nosuch.text=a;lbl2.text=b", "lbl.text=a;text=b", "text=a",
              "id=lbl;text=a", "lbl.text=a;id=lbl2;text=b", ":label.text=a", "LBL.text=a"]:
        two(p)

    # Control id forms for winset
    for cid in ["mainwindow.lbl", "LBL", ".lbl", "lbl.", "mainwindow", ":label", "lbl;lbl2", "", "nosuch",
                "mainwindow.nosuch"]:
        s.body("winset.id", [f'winset({C}, {q(cid)}, "text=viaid")', "sleep(1)",
                             f'var/__v = winget({C}, "lbl;lbl2;mainwindow", "text")', f'winset({C}, null, "{R_TWO}")',
                             f'winset({C}, "mainwindow", "title=\\"parity skin\\"")'], "__v")
    s.body("winset.id", [f'winset({C}, null, "lbl.text=viaid")', "sleep(1)",
                         f'var/__v = winget({C}, "lbl;lbl2", "text")', f'winset({C}, null, "{R_TWO}")'], "__v")
    for cid, prop in [(":output", "max-lines"), (":map", "text-mode"), (":input", "is-password"),
                      (":info", "prefix-color")]:
        val = {"max-lines": "max-lines=77", "text-mode": "text-mode=true", "is-password": "is-password=true",
               "prefix-color": "prefix-color=#123456"}[prop]
        rest = {"max-lines": "max-lines=1000", "text-mode": "text-mode=false", "is-password": "is-password=false",
                "prefix-color": "prefix-color=#ff0000"}[prop]
        real = {":output": "out", ":map": "map", ":input": "inp", ":info": "info"}[cid]
        s.case("winset.id", f"list(skin_x_sg({q(cid)}, {q(val)}, {q(prop)}, null), "
                            f"skin_x_sg({q(real)}, {q(rest)}, {q(prop)}, null))")
    # Duplicate id in two panes
    for cid in ["dup", "lpane.dup", "rpane.dup"]:
        s.case("winset.id", f"list(skin_x_sg({q(cid)}, \"text=X\", \"text\", null), "
                            f"winget({C}, \"lpane.dup\", \"text\"), winget({C}, \"rpane.dup\", \"text\"), "
                            f"skin_x_sgn(\"lpane.dup.text=dupL;rpane.dup.text=dupR\", \"lpane.dup\", \"text\", null))")

    # List argument
    for lst in ['list("text" = "a b")', 'list("text" = "a;b", "align" = "left")', 'list("text" = "q\\"t")',
                'list("text" = 12)', 'list("text" = null)', 'list("text")', 'list("font-size" = 14)',
                'list("text-wrap" = 1)', 'list("size" = "90x20")', r'list("text" = "\[\[lbl2.text\]\]")',
                "list()"]:
        s.body("winset.list", [f'winset({C}, "lbl", {lst})', "sleep(1)",
                               f'var/__v = winget({C}, "lbl", "text;align;font-size;text-wrap;size")',
                               f'winset({C}, "lbl", "{R_LBL};text-wrap=false;size=200x24")'], "__v")
    s.body("winset.list", [f'winset({C}, null, list("lbl.text" = "x y", "lbl2.text" = "z"))', "sleep(1)",
                           f'var/__v = winget({C}, "lbl;lbl2", "text")', f'winset({C}, null, "{R_TWO}")'], "__v")
    s.body("winset.list", [f'winset({C}, null, list2params(list("lbl.text" = "p&q")))', "sleep(1)",
                           f'var/__v = winget({C}, "lbl", "text")', f'winset({C}, null, "{R_TWO}")'], "__v")

    # Odd argument types
    for arg in ["null", "1", '""', "list2params(list(\"text\" = \"x\"))", "\"text=[1+1]\""]:
        s.body("winset.args", [f'winset({C}, "lbl", {arg})', "sleep(1)", f'var/__v = winget({C}, "lbl", "text")',
                               f'winset({C}, "lbl", "{R_LBL}")'], "__v")
    s.body("winset.args", [f'winset({C}.mob, "lbl", "text=bymob")', "sleep(1)", f'var/__v = winget({C}, "lbl", "text")',
                           f'winset({C}, "lbl", "{R_LBL}")'], "__v")
    s.body("winset.args", ['winset(null, "lbl", "text=nobody")', "sleep(1)", f'var/__v = winget({C}, "lbl", "text")'],
           "__v")

    # Parse errors last: these may throw in a client parser
    for v in ['"unterminated', '"bad \\q"', "[[unclosed", "[single]", "a?b:c", "a:b"]:
        lbl("text=" + v)
