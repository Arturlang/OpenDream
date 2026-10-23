"""Browser suite: output() from DM into a JavaScript function of the page."""
from gen import dm_str

HELPERS = """/proc/browser_x_repeat(t, n)
	var/r = ""
	for(var/i in 1 to n)
		r += t
	return r

/client/verb/browser_x_big(n as num)
	set name = "browserxbig"
	set hidden = 1
	src << output(list2params(list(browser_x_repeat("ab&c=d;e+f% é", n))), "probe:browser_x_measure")

/client/verb/browser_x_bigraw(n as num)
	set name = "browserxbigraw"
	set hidden = 1
	src << output(browser_x_repeat("0123456789", n), "probe:browser_x_measure")

/client/verb/browser_x_to(f as text)
	set name = "browserxto"
	set hidden = 1
	src << output("a&b%20c", "probe:[f]")"""

# Waits for window.browser_x_got, which a receiver sets. The command runs through byond://winset?command=.
WAIT = r"""async function runAndWait(cmd) {
  window.browser_x_got = undefined;
  location.href = "byond://winset?command=" + encodeURIComponent(cmd);
  for (var i = 0; i < 30 && window.browser_x_got === undefined; i++) await sleep(50);
  var g = window.browser_x_got; delete window.browser_x_got; return g === undefined ? "<not called>" : g;
}"""

MEASURE = r"""window.browser_x_measure = function (s) {
  var h = 0; s = String(s);
  for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  window.browser_x_got = [arguments.length, s.length, h, s.slice(0, 24), s.slice(-24)];
};"""

SPECIALS = ["a&b", "a;b", "a=b", "a+b", "100%", "%41", "%zz", "a%20b", "it's", 'say "hi"', "<b>x</b>",
            "é", "\U0001F600", "line1\nline2", "back\\slash", "[x]", "\x01"]


def build(s):
    s.browser()
    s.dm(HELPERS)
    R = lambda name, *lines, settle=300: s.roundtrip(name, list(lines), settle)
    O = lambda expr, ctl="probe:parity_recv": f"C << output({expr}, {dm_str(ctl)})"

    R("plain text", O('"hello world"'))
    R("twelve args", O('list2params(list("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"))'))
    R("forty args", "var/list/L = list()", "for(var/i in 1 to 40)", '\tL += "v[i]"', O("list2params(L)"))
    R("keyed params", O('list2params(list("a" = 1, "b" = "x y", "c" = null))'))
    R("url_encode", O('url_encode("x y+z&w=v;u%")'))
    R("url_encode unicode", O('url_encode("é \U0001F600")'))
    R("double url_encode", O('url_encode(url_encode("a b&c"))'))
    for t in SPECIALS:
        R(f"raw {t!r}", O(dm_str(t)))
        R(f"list2params {t!r}", O(f"list2params(list({dm_str(t)}))"))
    for t in ["a b", "é"]:
        R(f"url_encode {t!r}", O(f"url_encode({dm_str(t)})"))
    for e in ['""', 'list2params(list(""))', 'list2params(list("", ""))', '"&"', '"&&"', '";"']:
        R(f"empty-ish {e}", O(e))
    for e in ["5", "-1.5", "1e10", "1/3", "list2params(list(1, 2.5))"]:
        R(f"number {e}", O(e))
    R("json url_encoded", O('url_encode(json_encode(list("name" = "fridge", "power" = 12)))'))
    R("json raw", O('json_encode(list("name" = "fridge", "power" = 12))'))
    R("json specials", O('url_encode(json_encode(list("t" = "a&b;c=d+e%", "u" = "é")))'))
    R("json list2params", O('list2params(list(json_encode(list(1, "two", list(3)))))'))
    R("payload 5000", O('list2params(list(browser_x_repeat("ab&c ", 1000)))'))

    R("missing function then recv", O('"x"', "probe:browser_x_missing"), O('"after"'))
    R("wrong case function then recv", O('"x"', "probe:PARITY_RECV"), O('"after"'))
    for f in ["window.parity_recv", "parity_recv.call",
              'window["parity_recv"]', "parity_recv()"]:
        R(f"name {f}", O('"a&b"', f"probe:{f}"), O('"end"'))
    R("decorated control", O('"a&b"', "mainwindow.probe:parity_recv"))
    R("default browser control", O('"a&b"', ":browser:parity_recv"), O('"end"'))

    R("order five", *[O(dm_str(str(i))) for i in range(1, 6)])
    R("order loop twenty", "for(var/i in 1 to 20)", "\t" + O('"[i]"'))
    R("order with missing between", O('"1"'), O('"x"', "probe:browser_x_missing"), O('"2"'),
      O('"x"', "probe:browser_x_missing.m"), O('"3"'))
    R("order mixed forms", O('"a b"'), O('list2params(list("a b"))'), O('url_encode("a b")'))

    # Large payloads go to a measuring receiver, so the result stays small
    s.probe("payload 50 KB encoded", "\n".join([WAIT, MEASURE, 'var g = await runAndWait("browserxbig 3125");',
                                                 "delete window.browser_x_measure; return g;"]))
    s.probe("payload 50 KB raw digits", "\n".join([WAIT, MEASURE, 'var g = await runAndWait("browserxbigraw 5000");',
                                                    "delete window.browser_x_measure; return g;"]))
    s.probe("nested receiver obj.inner.m", "\n".join([WAIT, r"""
window.browser_x_obj = {inner: {m: function () {
  window.browser_x_got = [Array.prototype.slice.call(arguments), this === window.browser_x_obj.inner];
}}};
var g = await runAndWait("browserxto browser_x_obj.inner.m");
delete window.browser_x_obj; return g;"""]))
    s.probe("receiver this", "\n".join([WAIT, r"""
window.browser_x_fn = function () { window.browser_x_got = [this === window, typeof this, arguments.length]; };
var g = await runAndWait("browserxto browser_x_fn");
delete window.browser_x_fn; return g;"""]))
    s.probe("receiver return value ignored", "\n".join([WAIT, r"""
window.browser_x_fn = function (a) { window.browser_x_got = a; return "ret"; };
var g = await runAndWait("browserxto browser_x_fn");
delete window.browser_x_fn; return g;"""]))
    s.probe("receiver throws", "\n".join([WAIT, r"""
window.browser_x_fn = function (a) { window.browser_x_got = a; throw new Error("browser_x_boom"); };
var g = await runAndWait("browserxto browser_x_fn");
delete window.browser_x_fn; return g;"""]))
