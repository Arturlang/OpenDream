"""winclone() of windows, panes, menus and macro sets, runtime control creation, and deletion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C


def clone_case(s, topic, src, cid, queries, delete="parent=none", extra=()):
    """Clone src as cid, read it, delete it, check it is gone. Each clone id is used once."""
    lines = [f'winclone({C}, {q(src)}, {q(cid)})', "sleep(2)", f'var/__a = winexists({C}, {q(cid)})']
    res = ["__a"]
    for k, (ctl, prop) in enumerate(queries):
        lines.append(f'var/__q{k} = winget({C}, {q(ctl)}, {q(prop)})')
        res.append(f"__q{k}")
    lines += list(extra)
    if delete is not None:
        lines += [f'winset({C}, {q(cid)}, {q(delete)})', "sleep(2)", f'var/__z = winexists({C}, {q(cid)})']
        res.append("__z")
    s.body(topic, lines, f"list({', '.join(res)})")


def build(s):
    K.setup(s)

    t = "winclone.window"
    clone_case(s, t, "win2", "cl_w1", [("cl_w1", "type;is-visible;is-pane;title;size")])
    clone_case(s, t, "win2", "cl_w2", [("cl_w2.win2_lbl", "text;type"), ("cl_w2.win2_btn", "text")])
    clone_case(s, t, "win2", "cl_w3", [("cl_w3", "title")], delete="parent=")
    clone_case(s, t, "win2", "cl_w4", [("cl_w4", "title")], delete="parent=nosuch")
    clone_case(s, t, "win2", "cl_w5", [("cl_w5", "title")], delete=None)
    s.case(t, f'list(winexists({C}, "cl_w5"), skin_x_sorted(winget({C}, null, "windows")))')
    s.body(t, [f'winset({C}, "cl_w5", "parent=none")', "sleep(2)", f'var/__v = winexists({C}, "cl_w5")'], "__v")
    s.body(t, [f'winclone({C}, "win2", "cl_w6")', "sleep(2)", f'var/__v = skin_x_sorted(winget({C}, null, "windows"))',
               f'var/__p = skin_x_sorted(winget({C}, null, "panes"))', f'winset({C}, "cl_w6", "parent=none")', "sleep(2)",
               f'var/__w = skin_x_sorted(winget({C}, null, "windows"))'], "list(__v, __p, __w)")
    # The clone copies the skin file, not the current state
    s.body(t, [f'winset({C}, "win2", "title=changed")', "sleep(1)", f'winclone({C}, "win2", "cl_w7")', "sleep(2)",
               f'var/__v = winget({C}, "cl_w7", "title")', f'winset({C}, "win2", "title=Second")',
               f'winset({C}, "cl_w7", "parent=none")', "sleep(1)"], "__v")
    # Clone, change, check the original is untouched
    s.body(t, [f'winclone({C}, "win2", "cl_w8")', "sleep(2)", f'winset({C}, "cl_w8", "title=Clone")', "sleep(1)",
               f'var/__v = winget({C}, "cl_w8;win2", "title")', f'winset({C}, "cl_w8", "parent=none")', "sleep(1)"],
           "__v")
    s.body(t, [f'winclone({C}, "win2", "cl_w9")', "sleep(2)", f'winset({C}, "cl_w9.win2_lbl", "text=inclone")',
               "sleep(1)", f'var/__v = list(winget({C}, "cl_w9.win2_lbl", "text"), winget({C}, "win2.win2_lbl", "text"))',
               f'winset({C}, "cl_w9", "parent=none")', "sleep(1)"], "__v")
    s.body(t, [f'winclone({C}, "win2", "cl_w10")', "sleep(2)", f'winshow({C}, "cl_w10", 1)', "sleep(2)",
               f'var/__v = winget({C}, "cl_w10", "is-visible")', f'winshow({C}, "cl_w10", 0)', "sleep(2)",
               f'var/__w = winget({C}, "cl_w10", "is-visible")', f'winset({C}, "cl_w10", "parent=none")', "sleep(1)"],
           "list(__v, __w)")
    s.body(t, [f'winclone({C}, "win2", "cl_w11")', "sleep(2)", f'var/__v = skin_x_keys("cl_w11")',
               f'winset({C}, "cl_w11", "parent=none")', "sleep(1)"], "__v")
    # Clone twice to one id, clone a clone
    s.body(t, [f'winclone({C}, "win2", "cl_w12")', f'winclone({C}, "spane", "cl_w12")', "sleep(2)",
               f'var/__v = winget({C}, "cl_w12", "is-pane;title")', f'winset({C}, "cl_w12", "parent=none")', "sleep(2)",
               f'var/__w = winexists({C}, "cl_w12")'], "list(__v, __w)")
    s.body(t, [f'winclone({C}, "win2", "cl_w13")', "sleep(2)", f'winclone({C}, "cl_w13", "cl_w14")', "sleep(2)",
               f'var/__v = list(winexists({C}, "cl_w14"), winget({C}, "cl_w14", "title"))',
               f'winset({C}, "cl_w14", "parent=none")', f'winset({C}, "cl_w13", "parent=none")', "sleep(2)"], "__v")
    for k, src in enumerate(["nosuch", "lbl", "", "mainwindow.lbl", "m_chk", "mac_f5"]):
        clone_case(s, "winclone.bad", src, f"cl_b{k}", [], delete="parent=none")
    s.body("winclone.bad", [f'winclone({C}, "win2", "")', "sleep(2)", f'var/__v = winexists({C}, "")'], "__v")
    s.body("winclone.bad", [f'winclone({C}, "win2", null)', "sleep(2)", f'var/__v = winexists({C}, "win2")'], "__v")
    s.body("winclone.bad", [f'winclone({C}.mob, "win2", "cl_mob")', "sleep(2)", f'var/__v = winexists({C}, "cl_mob")',
                            f'winset({C}, "cl_mob", "parent=none")', "sleep(1)"], "__v")

    t = "winclone.pane"
    clone_case(s, t, "lpane", "cl_p1", [("cl_p1", "type;is-pane;title"), ("cl_p1.lp_lbl", "text")])
    clone_case(s, t, "spane", "cl_p2", [("cl_p2", "is-pane")], delete="parent=")
    s.body(t, [f'winclone({C}, "spane", "cl_p3")', "sleep(2)", f'winset({C}, "split", "right=cl_p3")', "sleep(2)",
               f'var/__v = list(winget({C}, "split", "right"), winget({C}, "cl_p3", "is-visible"), '
               f'winget({C}, "cl_p3.sp_lbl", "text"))',
               f'winset({C}, "split", "right=rpane")', "sleep(1)", f'winset({C}, "cl_p3", "parent=none")', "sleep(2)",
               f'var/__w = list(winexists({C}, "cl_p3"), winget({C}, "split", "right"))'], "list(__v, __w)")
    s.body(t, [f'winclone({C}, "spane", "cl_p4")', "sleep(2)", f'winset({C}, "tabs", list("tabs" = "+cl_p4"))',
               "sleep(2)", f'var/__v = winget({C}, "tabs", "tabs")',
               f'winset({C}, "tabs", "tabs=tpane1,tpane2;current-tab=tpane1")', "sleep(1)",
               f'winset({C}, "cl_p4", "parent=none")', "sleep(1)"], "__v")

    t = "winclone.new"
    for kind, cid in [("window", "cl_n1"), ("pane", "cl_n2"), ("menu", "cl_n3"), ("macro", "cl_n4"),
                      ("WINDOW", "cl_n5"), ("label", "cl_n6")]:
        clone_case(s, t, kind, cid, [(cid, "type;is-pane;is-visible")])
    s.body(t, [f'winclone({C}, "pane", "cl_n7")', f'winset({C}, "cl_n7", "size=100x100")',
               f'winset({C}, "cl_n7_lbl", "type=label;parent=cl_n7;pos=0,0;size=100x20;anchor1=0,0;anchor2=100,0;text=made")',
               "sleep(2)", f'var/__v = list(winexists({C}, "cl_n7_lbl"), winget({C}, "cl_n7_lbl", "text;parent"), '
                           f'winget({C}, "cl_n7", "size"))',
               f'winset({C}, "cl_n7", "parent=none")', "sleep(2)",
               f'var/__w = list(winexists({C}, "cl_n7"), winexists({C}, "cl_n7_lbl"))'], "list(__v, __w)")

    t = "winclone.menu"
    clone_case(s, t, "menu", "cl_m1", [("cl_m1", "type"), ("cl_m1.m_chk", "name;is-checked")])
    clone_case(s, t, "macro", "cl_k1", [("cl_k1", "type"), ("cl_k1.mac_f5", "name;command")])
    s.body(t, [f'winclone({C}, "menu", "cl_m2")', "sleep(2)", f'var/__v = skin_x_sorted(winget({C}, null, "menus"))',
               f'winset({C}, "cl_m2", "parent=none")', "sleep(2)",
               f'var/__w = skin_x_sorted(winget({C}, null, "menus"))'], "list(__v, __w)")
    s.body(t, [f'winclone({C}, "macro", "cl_k2")', "sleep(2)", f'var/__v = skin_x_sorted(winget({C}, null, "macros"))',
               f'winset({C}, "cl_k2", "parent=none")', "sleep(2)",
               f'var/__w = skin_x_sorted(winget({C}, null, "macros"))'], "list(__v, __w)")
    s.body(t, [f'winclone({C}, "menu", "cl_m3")', f'winset({C}, "cl_m3_file", "parent=cl_m3;name=File")',
               f'winset({C}, "cl_m3_go", "parent=cl_m3_file;name=Go;command=skinxnoop")', "sleep(2)",
               f'var/__v = list(winexists({C}, "cl_m3_file"), winget({C}, "cl_m3_go", "name;command"))',
               f'winset({C}, "cl_m3", "parent=none")', "sleep(2)",
               f'var/__w = list(winexists({C}, "cl_m3"), winexists({C}, "cl_m3_go"))'], "list(__v, __w)")

    # Runtime creation with winset(type, parent) and deletion with a blank or none parent
    t = "create"
    for cid, params, dele in [
            ("cr_1", "type=label;parent=win2;pos=0,60;size=80x20;text=made", "parent="),
            ("cr_2", "type=LABEL;parent=win2;pos=0,60;size=80x20;text=made", "parent=none"),
            ("cr_3", "type=button;parent=win2;pos=0,90;size=80x20;text=btn", "parent="),
            ("cr_5", "type=bar;parent=win2;pos=0,90;size=80x20;value=40", "parent="),
            ("cr_6", "type=grid;parent=win2;pos=0,90;size=80x40;cells=2x2", "parent="),
            ("cr_9", "type=tab;parent=win2;pos=0,90;size=80x40", "parent="),
            ("cr_12", "type=map;parent=win2;pos=0,90;size=80x40", "parent="),
            ("cr_13", "type=main;parent=win2;pos=0,90;size=80x40", "parent="),
            ("cr_14", "type=nosuch;parent=win2;pos=0,90;size=80x40", "parent="),
            ("cr_15", "type=label;parent=nosuch;text=x", "parent="),
            ("cr_16", "type=label;text=noparent", "parent="),
            ("cr_17", "parent=win2;text=notype", "parent="),
            ("cr_18", "type=label;parent=lpane;pos=0,60;size=80x20;text=inpane", "parent="),
            ("cr_19", "type=label;parent=mainwindow;pos=600,600;size=80x20;text=inmain", "parent="),
            ("cr_20", "parent=menu;name=Extra;command=skinxnoop", "parent="),
            ("cr_21", "parent=m_file;name=Extra;command=skinxnoop", "parent="),
            ("cr_22", "parent=macro;name=F9;command=skinxnoop", "parent="),
            ("cr_23", "type=label;parent=win2.win2_lbl;text=x", "parent="),
            ("cr_24", "type=label;parent=win2;pos=0,60;size=80x20;text=\"two words\";is-visible=false", "parent=")]:
        s.body(t, [f'winset({C}, {q(cid)}, {q(params)})', "sleep(2)",
                   f'var/__a = winexists({C}, {q(cid)})', f'var/__b = winget({C}, {q(cid)}, "type;text;pos;size;name;command")',
                   f'winset({C}, {q(cid)}, {q(dele)})', "sleep(2)", f'var/__c = winexists({C}, {q(cid)})'],
               "list(__a, __b, __c)")
    s.body(t, [f'winset({C}, "cr_30", "type=label;parent=win2;pos=0,60;size=80x20")', "sleep(2)",
               f'var/__a = winexists({C}, "win2.cr_30")', f'var/__b = skin_x_keys("cr_30")',
               f'winset({C}, "cr_30", "parent=")', "sleep(2)"], "list(__a, __b)")
    s.body(t, [f'winset({C}, null, "cr_31.type=label;cr_31.parent=win2;cr_31.text=viaglobal")', "sleep(2)",
               f'var/__a = winexists({C}, "cr_31")', f'var/__b = winget({C}, "cr_31", "text")',
               f'winset({C}, "cr_31", "parent=")', "sleep(2)"], "list(__a, __b)")
    s.body(t, [f'winset({C}, "cr_32", list("type" = "label", "parent" = "win2", "text" = "via list"))', "sleep(2)",
               f'var/__a = winexists({C}, "cr_32")', f'var/__b = winget({C}, "cr_32", "text")',
               f'winset({C}, "cr_32", list("parent" = ""))', "sleep(2)", f'var/__c = winexists({C}, "cr_32")'],
           "list(__a, __b, __c)")
    # Deleting skin-file controls is not allowed
    s.body(t, [f'winset({C}, "win2_btn", "parent=")', "sleep(2)", f'var/__a = winexists({C}, "win2_btn")'], "__a")
    s.body(t, [f'winset({C}, "sp_lbl", "parent=none")', "sleep(2)", f'var/__a = winexists({C}, "sp_lbl")'], "__a")
    s.body(t, [f'winset({C}, "m2_top", "parent=")', "sleep(2)", f'var/__a = winexists({C}, "m2_top")'], "__a")

    # Clone onto an existing window id last: it may replace win2
    s.body("winclone.window", [f'winclone({C}, "spane", "win2")', "sleep(2)",
                               f'var/__v = winget({C}, "win2", "is-pane;title;is-visible")'], "__v")
