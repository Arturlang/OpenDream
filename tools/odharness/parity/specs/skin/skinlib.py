"""Shared helpers and value pools for the skin suite. build() adds the DM helpers once and no cases."""
from pathlib import Path

from gen import dm_str as q

HERE = Path(__file__).resolve().parent
C = "live_client"


def setup(s):
    s.skin(HERE / "skin.dmf", window=(1100, 850))
    s.dm(DM)


def build(s):
    setup(s)


DM = r'''var/global/skin_x_got

// Set, wait, read back, then restore. The result is the read value.
/proc/skin_x_sg(id, params, prop, restore)
	winset(live_client, id, params)
	sleep(1)
	. = winget(live_client, id, prop)
	if(restore)
		winset(live_client, id, restore)

// Same, but the winset has a null id (decorated params).
/proc/skin_x_sgn(params, id, prop, restore)
	winset(live_client, null, params)
	sleep(1)
	. = winget(live_client, id, prop)
	if(restore)
		winset(live_client, null, restore)

/proc/skin_x_sort(list/L)
	var/list/R = L.Copy()
	for(var/i in 2 to R.len)
		var/j = i
		while(j > 1 && sorttextEx(R[j - 1], R[j]) < 0)
			R.Swap(j - 1, j)
			j--
	return R

// Sorted key list of a params string
/proc/skin_x_keys_of(t)
	if(!istext(t))
		return t
	var/list/P = params2list(t)
	var/list/K = list()
	for(var/k in P)
		K += "[k]"
	return jointext(skin_x_sort(K), ";")

/proc/skin_x_keys(id)
	return skin_x_keys_of(winget(live_client, id, "*"))

/proc/skin_x_sorted(t)
	if(!istext(t))
		return t
	return jointext(skin_x_sort(splittext(t, ";")), ";")

// Runs a client command and waits up to 2 s for a skinxecho verb to report
/proc/skin_x_cmd(cmd)
	skin_x_got = null
	winset(live_client, null, list("command" = cmd))
	for(var/i in 1 to 20)
		if(!isnull(skin_x_got))
			break
		sleep(1)
	return skin_x_got

/proc/skin_x_cmd_raw(params)
	skin_x_got = null
	winset(live_client, null, params)
	for(var/i in 1 to 20)
		if(!isnull(skin_x_got))
			break
		sleep(1)
	return skin_x_got

/proc/skin_x_kind(v)
	if(isnull(v))
		return "null"
	if(!istext(v))
		return "other"
	if(v == "")
		return "empty"
	if(v == "true" || v == "false")
		return "bool"
	return "text"

// Commands always pass one non-empty argument, so no verb prompts for a missing one
/client/verb/skin_x_echo(t as text)
	set name = "skinxecho"
	set hidden = 1
	skin_x_got = t

/client/verb/skin_x_echo2(t as command_text)
	set name = "skinxecho2"
	set hidden = 1
	skin_x_got = t
'''

# Raw param values, placed after "name=" in a winset string
B_FULL = ["true", "false", "1", "0", "yes", "no", "on", "off", "TRUE", "False", "2", "-1", "", "maybe", '"true"']
B = ["true", "false", "bad"]
C_FULL = ["#ff0000", "#00ff00", "#0f0", "#00F", "#ABCDEF", "red", "Blue", "white", "black", "none", "",
          "#12345", "#1234567", "#ff000080", "#gg0000", "rgb(1,2,3)", "transparent", '"#123456"', "123456", "%23ff0000"]
COL = ["#ff0000", "none", "bad"]
N_FONT = ["12", "0", "-3", "7.5", "1e1", "abc", "", "12pt", "9999"]
SIZE_FULL = ["100x50", "100,50", "100 50", "0x0", "-5x10", "1x", "x", "abc", "", "100", "100x50x3", '"80x40"',
             "50.7x20.2", "0x20"]
POS_FULL = ["10,20", "10x20", "-5,-5", "0,0", "abc", "", "10", '"12,34"', "10.6,20.4", "10 20"]
STR_FULL = ["hello", '"two words"', '"esc \\"q\\" in"', "a%20b", "a+b", "", '""', '"semi;colon"', '"amp&er"', "none",
            '"x=y"', "héllo", '"héllo"', '"tab\\tnl\\nend"', "'single quoted'", '"back\\\\slash"',
            '"[[lbl2.text]]"', "two words", "%22pct%22"]
STR = ['"two words"', ""]
CMD = ['"say \\"hi\\""', "", '"!prompt text"']
FONT_STYLE = ["bold", "italic", "underline", "strike", "bold italic", "bold,italic", '"bold italic underline"',
              "BOLD", "none", "", "bad"]
BORDER = ["line", "sunken", "none", "LINE", "bad", ""]
ANCHOR = ["0,0", "100,100", "50,50", "none", "bad", "", "0x0", "150,-10"]


def sg(s, topic, ctl, param, values, restore, prop=None):
    """One case per value: winset ctl param=value, winget prop (default param), restore.
    For the B pool the values are the opposite of the restored default and an invalid word."""
    if values is B:
        values = ["false" if restore.endswith("=true") else "true", "bad"]
    for v in values:
        s.case(topic, f"skin_x_sg({q(ctl)}, {q(param + '=' + v)}, {q(prop or param)}, {q(restore)})")


def raw(s, topic, ctl, params, prop, restore):
    """One case with a full params string."""
    s.case(topic, f"skin_x_sg({q(ctl)}, {q(params)}, {q(prop)}, {q(restore)})")


def get(s, topic, ctl, prop):
    s.case(topic, f"winget({C}, {q(ctl)}, {q(prop)})")
