"""Browser suite: the JavaScript bridge a browse() page gets (BYOND object, winget, winset, command, topic)."""
import re

# JS helpers. A probe gets only the helpers it calls.
H = {
    # BYOND.winget with a marker when the API is missing
    "W": r"""async function W(id, props) {
  if (!window.BYOND || typeof BYOND.winget !== "function") return "<no BYOND.winget>";
  try { var r = await timeout(Promise.resolve(BYOND.winget(id, props)), 1500); return r === undefined ? "<undefined>" : r; }
  catch (e) { return {error: String(e && e.message || e)}; }
}""",
    # byond://winget?callback= form. query is the rest of the URL after the callback.
    "U": r"""function U(query, ms) {
  return new Promise(function (res) {
    var n = "browser_x_cb" + Math.floor(Math.random() * 1e9);
    var t = setTimeout(function () { delete window[n]; res("<no callback>"); }, ms || 1500);
    window[n] = function (v) { clearTimeout(t); delete window[n]; res(v === undefined ? "<undefined>" : v); };
    location.href = "byond://winget?callback=" + n + "&" + query;
  });
}""",
    # byond://winset? form, then a short wait so the next navigation does not replace it
    "S": r"""async function S(query) { location.href = "byond://winset?" + query; await sleep(150); }""",
    # Runs a command through byond://winset?command= and returns what the verbs sent to parity_recv
    "CU": r"""async function CU(cmd, ms) {
  recvLog = []; location.href = "byond://winset?command=" + encodeURIComponent(cmd);
  await sleep(ms || 500); var g = recvLog; recvLog = null; return g;
}""",
    # Same through BYOND.command
    "CB": r"""async function CB(cmd, ms) {
  if (!window.BYOND || typeof BYOND.command !== "function") return "<no BYOND.command>";
  recvLog = []; try { BYOND.command(cmd); } catch (e) { recvLog = null; return {error: String(e && e.message || e)}; }
  await sleep(ms || 500); var g = recvLog; recvLog = null; return g;
}""",
    "K": r"""function K(o) { return o && typeof o === "object" ? Object.keys(o).sort() : o; }""",
    # The id of the running probe, read from the status line of the page
    "ME": r"""function ME() { return document.getElementById("status").textContent.split(" ")[1]; }""",
}


def js(body):
    pre = [v for k, v in H.items() if re.search(r"\b" + k + r"\(", body)]
    return "\n".join(pre + [body.strip()])


VERBS = """/client/verb/browser_x_ping()
	set name = "browserxping"
	set hidden = 1
	src << output(list2params(list("ping")), "probe:parity_recv")

/client/verb/browser_x_echo(t as text)
	set name = "browserxecho"
	set hidden = 1
	src << output(list2params(list("echo", t)), "probe:parity_recv")

/client/verb/browser_x_num(n as num)
	set name = "browserxnum"
	set hidden = 1
	src << output(list2params(list("num", "[n]", "[isnum(n)]")), "probe:parity_recv")

/client/verb/browser_x_two(a as text, b as num)
	set name = "browserxtwo"
	set hidden = 1
	src << output(list2params(list("two", a, "[b]")), "probe:parity_recv")"""


def build(s):
    s.browser()
    s.dm(VERBS)
    P = lambda name, body: s.probe(name, js(body))

    # Presence and types
    P("typeof BYOND Byond byond", 'return [typeof window.BYOND, typeof window.Byond, typeof window.byond];')
    P("BYOND own keys", 'return window.BYOND ? Object.keys(BYOND).sort() : "<no BYOND>";')
    P("BYOND method types", """
if (!window.BYOND) return "<no BYOND>";
var o = {};
["winset", "winget", "command", "topic", "output", "callback"].forEach(function (k) { o[k] = typeof BYOND[k]; });
return o;""")
    P("Byond method types", """
if (!window.Byond) return "<no Byond>";
var o = {};
["winset", "winget", "command", "topic", "sendMessage", "subscribe"].forEach(function (k) { o[k] = typeof Byond[k]; });
return o;""")
    P("BYOND.winget returns thenable", """
if (!window.BYOND || typeof BYOND.winget !== "function") return "<no BYOND.winget>";
var r = BYOND.winget("probe", "type");
var t = r && typeof r.then;
try { await timeout(Promise.resolve(r), 1500); } catch (e) { }
return [Object.prototype.toString.call(r), t];""")
    P("storage objects", """
var o = {};
["byondStorage", "hubStorage", "serverStorage", "domainStorage", "localStorage", "sessionStorage"].forEach(function (k) {
  try { o[k] = typeof window[k]; } catch (e) { o[k] = "<throws>"; }
});
return o;""")
    P("localStorage roundtrip", """
try { localStorage.setItem("browser_x_k", "v1"); var v = localStorage.getItem("browser_x_k"); localStorage.removeItem("browser_x_k"); return [v, localStorage.getItem("browser_x_k")]; }
catch (e) { return {error: String(e && e.message || e)}; }""")
    P("chrome webview external", """
var o = {chrome: typeof window.chrome, external: typeof window.external};
try { o.webview = window.chrome ? typeof window.chrome.webview : "<no chrome>"; } catch (e) { o.webview = "<throws>"; }
return o;""")
    P("location protocol host", 'return [location.protocol, location.hostname, location.search, location.hash];')
    P("document basics", 'return [document.characterSet, document.compatMode, document.title, document.readyState];')
    P("window name", 'return window.name;')
    P("inner size", 'return [window.innerWidth, window.innerHeight];')
    P("page globals", 'return [typeof window.parity_recv, typeof window.parity_ack, window === window.top, window.frames.length];')

    # BYOND.winget
    for cid, props in [("probe", "size"), ("probe", "type"), ("probe", "is-visible"), ("probe", "background-color"),
                       ("probe", ["size", "type", "is-visible"]), ("probe", "isVisible"),
                       ("probe", "browser-x-bogus"), ("probe", []),
                       ("mainwindow", "title"), ("mainwindow", "size"), ("mainwindow", ["can-resize", "statusbar", "is-default"]),
                       ("map", "zoom"), ("map", ["type", "zoom-mode", "text-mode"]), ("map", "viewSize"),
                       ("mainwindow.map", "type"), (":map", "type"), ("mainwindow.*", "type"),
                       ("browser_x_none", "size"), ("browser_x_none", ["size", "type"]),
                       (None, "windows"), (None, ["windows", "panes", "menus", "macros"]), ("", "windows")]:
        P(f"BYOND.winget {cid} {props}", f"return await W({repr_js(cid)}, {repr_js(props)});")
    P("BYOND.winget probe * keys", 'return K(await W("probe", "*"));')
    P("BYOND.winget map * keys", 'return K(await W("map", "*"));')

    # BYOND.winset, read back, restore
    for name, cid, key, val, read, restore in [
            ("title", "mainwindow", "title", '"parity x"', "title", '"parity"'),
            ("map zoom number", "map", "zoom", "2", "zoom", "1"),
            ("map zoom text", "map", "zoom", '"2"', "zoom", '"1"'),
            ("map background", "map", "backgroundColor", '"#123456"', "background-color", None),
            ("map is-disabled bool", "map", "isDisabled", "true", "is-disabled", "false"),
            ("map text-color hyphen", "map", "text-color", '"#00ff00"', "text-color", None)]:
        rest = restore if restore is not None else f'(typeof b0 === "object" && b0["{read}"] && b0["{read}"].value) || "none"'
        P(f"BYOND.winset {name}", f"""
if (!window.BYOND || typeof BYOND.winset !== "function") return "<no BYOND.winset>";
var b0 = await W("{cid}", "{read}");
var o = {{}}; o["{key}"] = {val}; BYOND.winset("{cid}", o);
await sleep(150);
var a = await W("{cid}", "{read}");
var r = {{}}; r["{key}"] = {rest}; BYOND.winset("{cid}", r);
await sleep(150);
return {{before: b0, after: a, restored: await W("{cid}", "{read}")}};""")
    P("BYOND.winset null id decorated", """
if (!window.BYOND || typeof BYOND.winset !== "function") return "<no BYOND.winset>";
BYOND.winset(null, {"mainwindow.title": "parity null"});
await sleep(150);
var a = await W("mainwindow", "title");
BYOND.winset(null, {"mainwindow.title": "parity"});
await sleep(150);
return [a, await W("mainwindow", "title")];""")
    P("BYOND.winset missing control", """
if (!window.BYOND || typeof BYOND.winset !== "function") return "<no BYOND.winset>";
try { BYOND.winset("browser_x_none", {size: "10x10"}); } catch (e) { return {error: String(e && e.message || e)}; }
await sleep(150);
return await W("probe", "size");""")

    # BYOND.command and the byond://winset?command= form, both run the verbs above
    for cmd in ["browserxping", 'browserxecho "hello world"', "browserxnum 42",
                'browserxtwo "a b" 3', "browserxecho é\U0001F600", 'browserxecho "a&b;c=d+e%"', "browser_x_nosuchverb 1"]:
        P(f"BYOND.command {cmd}", f"return await CB({repr_js(cmd)});")
        P(f"winset command {cmd}", f"return await CU({repr_js(cmd)});")
    P("BYOND.command .winset", """
if (!window.BYOND || typeof BYOND.command !== "function") return "<no BYOND.command>";
BYOND.command('.winset "mainwindow.title=parity cmd"');
await sleep(200);
var a = await W("mainwindow", "title");
BYOND.command('.winset "mainwindow.title=parity"');
await sleep(200);
return [a, await W("mainwindow", "title")];""")

    # BYOND.topic: the page sends parity_probe=<this id>, so DM records v as this probe's result
    for name, v in [("plain", '"abc"'), ("specials", '"a b&c=d;e+f%25 %"'), ("unicode", '"é\U0001F600"'),
                    ("number", "12.5"), ("array", "[1, 2]")]:
        P(f"BYOND.topic {name}", f"""
if (!window.BYOND || typeof BYOND.topic !== "function") return "<no BYOND.topic>";
var id = ME();
await timeout(new Promise(function (res) {{ ackResolve = res; BYOND.topic({{parity_probe: id, v: {v}}}); }}), 1500);
return "__no_report__";""")

    # byond://winget?callback=
    for q in ["id=probe&property=size", "id=probe&property=type", "id=probe&property=is-visible",
              "id=probe&property=is-disabled", "id=probe&property=background-color",
              "id=probe&property=size,type,is-visible", "id=probe&property=isVisible", "id=probe&property=browser-x-bogus",
              "id=mainwindow&property=type", "id=mainwindow&property=title", "id=mainwindow&property=size",
              "id=mainwindow&property=can-resize", "id=mainwindow&property=statusbar", "id=mainwindow&property=titlebar",
              "id=mainwindow&property=can-close", "id=mainwindow&property=is-default", "id=mainwindow&property=is-visible",
              "id=map&property=type", "id=map&property=zoom", "id=map&property=icon-size", "id=map&property=size",
              "id=map&property=view-size", "id=probe,map&property=type", "id=probe,map&property=size,type", "id=mainwindow.map&property=type",
              "id=:map&property=type", "id=mainwindow.*&property=type", "id=browser_x_none&property=size",
              "property=windows", "id=&property=windows,panes,menus,macros"]:
        P(f"winget url {q}", f"return await U({repr_js(q)});")
    P("winget url probe * keys", 'return K(await U("id=probe&property=*"));')
    P("winget url callback args", """
return await new Promise(function (res) {
  var t = setTimeout(function () { delete window.browser_x_cba; res("<no callback>"); }, 1500);
  window.browser_x_cba = function () { clearTimeout(t); delete window.browser_x_cba; res([arguments.length, typeof arguments[0]]); };
  location.href = "byond://winget?callback=browser_x_cba&id=probe&property=size";
});""")
    P("winget url nested callback", """
return await new Promise(function (res) {
  var t = setTimeout(function () { delete window.browser_x_ns; res("<no callback>"); }, 1500);
  window.browser_x_ns = {cb: function (v) { clearTimeout(t); delete window.browser_x_ns; res(v); }};
  location.href = "byond://winget?callback=browser_x_ns.cb&id=probe&property=type";
});""")

    # byond://winset?, read back with the URL winget, restore
    for name, set_q, read_q, restore_q in [
            ("id title", "id=mainwindow&title=parity%20url", "id=mainwindow&property=title", "id=mainwindow&title=parity"),
            ("decorated title", "mainwindow.title=parity%20dec", "id=mainwindow&property=title", "mainwindow.title=parity"),
            ("two controls", "mainwindow.title=parity%20two&map.zoom=2", "id=mainwindow,map&property=title,zoom",
             "mainwindow.title=parity&map.zoom=1"),
            ("encoded title", "id=mainwindow&title=" + "a%20b%26c%3Dd%3Be%2Bf", "id=mainwindow&property=title",
             "id=mainwindow&title=parity"),
            ("unicode title", "id=mainwindow&title=%C3%A9%F0%9F%98%80", "id=mainwindow&property=title",
             "id=mainwindow&title=parity"),
            ("element key", "element=mainwindow&title=parity%20el", "id=mainwindow&property=title",
             "id=mainwindow&title=parity"),
            ("command winset", "command=" + "%2Ewinset%20%22mainwindow.title%3Dparity%20c%22", "id=mainwindow&property=title",
             "id=mainwindow&title=parity"),
            ("missing control", "id=browser_x_none&size=10x10", "id=probe&property=size", None)]:
        P(f"winset url {name}", f"""
await S({repr_js(set_q)});
var a = await U({repr_js(read_q)});
{f"await S({repr_js(restore_q)});" if restore_q else ""}
await sleep(100);
return {{after: a, restored: await U({repr_js(read_q)})}};""")


def repr_js(v):
    """JS literal for a str, list or None."""
    import json
    return "null" if v is None else json.dumps(v, ensure_ascii=False)
