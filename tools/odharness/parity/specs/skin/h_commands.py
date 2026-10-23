"""Client commands sent with winset(C, null, "command=..."): verbs, embedded wingets, .winset and .output.
Every verb command passes one non-empty argument: a missing argument opens a prompt on both engines.
skinxecho takes one text argument, skinxecho2 takes the rest of the line (command_text)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skinlib as K  # noqa: E402
from gen import dm_str as q  # noqa: E402

C = K.C
R_TWO = "lbl.text=hello;lbl2.text=world"


def build(s):
    K.setup(s)

    # Plain verb commands
    t = "command.verb"
    for cmd in ['skinxecho "hi"', "skinxecho hi", 'skinxecho "two words"', 'skinxecho "q\\"t"',
                'skinxecho2 "a" "b"', "skinxecho2 a b", "skinxecho2 one", 'SKINXECHO "case"',
                'skinxecho "semi;colon"', 'skinxecho "héllo"', 'nosuchverb "x"',
                'skinxecho "a"\nskinxecho "b"', 'skinxecho2   spaced   out  ']:
        s.case(t, f"skin_x_cmd({q(cmd)})")
    # String form of the command parameter
    for params in ['command=skinxecho+"plus"', 'command=skinxecho%20%22enc%22', 'command="skinxecho \\"quoted\\""',
                   'command=skinxecho+"s";lbl.text=x', 'command=skinxecho "raw"']:
        s.case(t, f"list(skin_x_cmd_raw({q(params)}), winget({C}, \"lbl\", \"text\"), "
                  f"skin_x_sgn({q(R_TWO)}, \"lbl\", \"text\", null))")
    s.case(t, 'skin_x_cmd_raw(list2params(list("command" = "skinxecho \\"listed\\"")))')

    # Embedded wingets inside a quoted argument, with markers so the argument is never empty
    t = "command.embed"
    for expr in ["[[lbl.text]]", "[[lbl.size]]", "[[lbl.pos]]", "[[lbl.size.x]]", "[[lbl.is-visible]]",
                 "[[lbl.background-color]]", "[[lbl.font-size]]", "[[lbl.nosuch]]", "[[nosuch.text]]",
                 "[[lbl.text as escaped]]", "[[lbl.text as params]]", "[[lbl.text as json-dm]]", "[[lbl.size as json-dm]]",
                 "[[lbl.is-visible as json-dm]]", "[[lbl.background-color as json-dm]]", "[[lbl.size as raw]]",
                 "[[lbl.text as nosuch]]", "[[mainwindow.lbl.text]]", "[[map.view-size]]", "[[m_chk.is-checked]]",
                 "[[windows]]", "[[*]]", "[[lbl.text]] [[lbl2.text]]"]:
        s.case(t, f"skin_x_cmd({q('skinxecho \"<' + expr + '>\"')})")
    # Quotes on both sides: the default format is escaped
    for expr in ["[[lbl.text]]", "[[lbl.size]]", "[[lbl.is-visible]]", "[[lbl.nosuch]]"]:
        s.case(t, f"skin_x_cmd({q('skinxecho \"' + expr + '\"')})")
    # Unquoted, through command_text: arg, string and json formats add their own quotes
    for expr in ["[[lbl.text]]", "[[lbl.size]]", "[[lbl.is-visible]]", "[[lbl.text as string]]",
                 "[[lbl.text as json]]", "[[lbl.size as arg]]", "[[lbl.size as json]]", "[[lbl.is-visible as json]]",
                 "[[lbl.background-color as json]]"]:
        s.case(t, f"skin_x_cmd({q('skinxecho2 < ' + expr + ' >')})")
    # Awkward text through the formats
    for val in ['"say \\"hi\\""', '"back\\\\slash"']:
        for expr in ['skinxecho "<[[lbl.text as escaped]]>"', 'skinxecho "<[[lbl.text as json-dm]]>"',
                     "skinxecho2 < [[lbl.text as arg]] >"]:
            s.body(t, [f'winset({C}, "lbl", {q("text=" + val)})', "sleep(1)",
                       f"var/__v = skin_x_cmd({q(expr)})", f'winset({C}, "lbl", "text=hello")'], "__v")

    # .winset client command, with conditions
    t = "command.winset"
    for cmd in ['.winset "lbl.text=fromcmd"', ".winset lbl.text=bare", '.winset "lbl.text=a;lbl2.text=b"',
                '.winset "lbl.text=\\"q x\\""', '.winset "lbl.text=hello ? lbl2.text=yes : lbl2.text=no"',
                '.winset "lbl.text=nope ? lbl2.text=yes : lbl2.text=no"',
                '.winset "lbl.text=nope ? lbl2.text=yes"', '.winset "lbl.text!=nope ? lbl2.text=ne"',
                '.winset "lbl.text!=hello ? lbl2.text=ne : lbl2.text=eq"',
                '.winset "lbl.is-visible=true ? lbl2.text=v lbl.text=w : lbl2.text=x"',
                '.winset "lbl.is-visible=1 ? lbl2.text=one"', '.winset "lbl.text=HELLO ? lbl2.text=ci"',
                '.winset "nosuch.text=x ? lbl2.text=y : lbl2.text=z"',
                '.winset "lbl.text=hello ? lbl2.text=[[lbl.size]]"', '.winset "lbl2.text=[[lbl.text]]"',
                '.winset "lbl.text=hello ? lbl2.text=t1 : lbl2.text=f1;lbl.text=after"',
                '.winset "lbl.size=200x24 ? lbl2.text=sz"', '.winset ""', ".WINSET lbl.text=up"]:
        s.body(t, [f'winset({C}, null, list("command" = {q(cmd)}))', "sleep(3)",
                   f'var/__v = winget({C}, "lbl;lbl2", "text")', f'winset({C}, null, {q(R_TWO)})'], "__v")

    # .output client command
    t = "command.output"
    for cmd in [".output lbl from output", ".output lbl", ".output lbl a\\nb", ".output mainwindow.lbl dec",
                ".output nosuch x", '.output lbl "quoted"', ".output lbl [[lbl2.text]]", ".output :label x"]:
        s.body(t, [f'winset({C}, null, list("command" = {q(cmd)}))', "sleep(3)",
                   f'var/__v = winget({C}, "lbl;lbl2", "text")', f'winset({C}, null, {q(R_TWO)})'], "__v")

    # Global params other than command
    t = "command.global"
    for params in ["nosuch=1", "browser-options=find", "browser-options=-find", "lbl.text=x;nosuch=1"]:
        s.body(t, [f'winset({C}, null, {q(params)})', "sleep(1)", f'var/__v = winget({C}, "lbl", "text")',
                   f'winset({C}, null, {q(R_TWO)})'], "__v")
