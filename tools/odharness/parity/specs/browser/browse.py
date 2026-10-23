"""Browser suite: browse() popups and their options, browse_rsc() files that the page loads."""
from gen import dm_str

HELPERS = """/proc/browser_x_rep(client/C, list/L)
	C << output(list2params(L), "probe:parity_recv")

/proc/browser_x_state(client/C, win)
	return list("exists:[winexists(C, win)]", "browser:[winexists(C, "[win].browser")]", "visible:[winget(C, win, "is-visible")]")

/proc/browser_x_props(client/C, win, list/props)
	var/list/L = list()
	for(var/p in props)
		L += "[p]:[winget(C, win, p)]"
	return L

/client/verb/browser_x_note(t as text)
	set name = "browserxnote"
	set hidden = 1
	src << output(list2params(list("note", url_decode(t))), "probe:parity_recv")

/client/verb/browser_x_rsc(f as text, n as text)
	set name = "browserxrsc"
	set hidden = 1
	var/F
	switch(f)
		if("small")
			F = 'small.dmi'
		if("rect")
			F = 'rect.dmi'
		if("test")
			F = 'test.dmi'
	src << browse_rsc(F, n)
	src << output(list2params(list("rsc", n)), "probe:parity_recv")"""

PAGE = "<html><body>browser_x popup</body></html>"
WINPROPS = '"size", "inner-size", "type", "can-close", "can-resize", "can-minimize", "titlebar", "is-pane"'

# Asks DM for browse_rsc() of a fixture, then loads it in an Image
RSC = r"""async function rsc(cmd, src) {
  recvLog = [];
  location.href = "byond://winset?command=" + encodeURIComponent(cmd);
  await sleep(400);
  var ack = recvLog; recvLog = null;
  var img = await new Promise(function (res) {
    var im = new Image();
    var t = setTimeout(function () { res("<timeout>"); }, 1200);
    im.onload = function () { clearTimeout(t); res([im.naturalWidth, im.naturalHeight]); };
    im.onerror = function () { clearTimeout(t); res("<error>"); };
    im.src = src;
  });
  return {ack: ack, img: img};
}"""


def report_script(js_expr):
    """A popup page whose script sends js_expr (JSON) back through the browserxnote verb."""
    return ("<html><body>r<script>location.href='byond://winset?command='+encodeURIComponent('browserxnote '"
            f"+encodeURIComponent(JSON.stringify({js_expr})))</script></body></html>")


def build(s):
    s.browser()
    s.dm(HELPERS)
    R = lambda name, *lines, settle=1000: s.roundtrip(name, list(lines), settle)
    rep = lambda expr: f"browser_x_rep(C, {expr})"
    br = lambda body, opts: f"C << browse({body}, {dm_str(opts)})"
    close = lambda win: f'C << browse(null, "window={win}")'

    def popup(name, win, opts, extra=()):
        R(name, br(dm_str(PAGE), f"window={win};{opts}" if opts else f"window={win}"),
          rep(f'browser_x_state(C, "{win}")'), rep(f'browser_x_props(C, "{win}", list({WINPROPS}))'), *extra,
          close(win), rep(f'browser_x_state(C, "{win}")'))

    popup("popup basic", "browser_x_p1", "size=200x150")
    popup("popup default size", "browser_x_p2", "")
    popup("popup can_close=0", "browser_x_p3", "size=200x150;can_close=0")
    popup("popup can_resize=0", "browser_x_p4", "size=200x150;can_resize=0")
    popup("popup titlebar=0", "browser_x_p6", "size=200x150;titlebar=0")
    popup("popup all off", "browser_x_p7", "size=200x150;can_close=0;can_resize=0;can_minimize=0;titlebar=0")
    popup("popup border=4", "browser_x_p8", "size=200x150;border=4")
    popup("popup comma options", "browser_x_p9", "size=210x120,can_resize=0")
    R("popup ampersand options", br(dm_str(PAGE), "window=browser_x_pa&size=220x130&can_close=0"),
      rep('browser_x_props(C, "browser_x_pa", list("size", "can-close"))'), close("browser_x_pa"),
      rep('browser_x_state(C, "browser_x_pa")'))
    R("popup winset title", br(dm_str(PAGE), "window=browser_x_pt;size=200x150"),
      'winset(C, "browser_x_pt", "title=\\"browser x t\\"")', rep('browser_x_props(C, "browser_x_pt", list("title"))'),
      close("browser_x_pt"))
    R("popup browser control props", br(dm_str(PAGE), "window=browser_x_pb;size=200x150"),
      rep('browser_x_props(C, "browser_x_pb.browser", list("type", "parent", "is-default", "anchor1", "anchor2"))'),
      close("browser_x_pb"))
    R("popup wildcard type", br(dm_str(PAGE), "window=browser_x_pw;size=200x150"),
      rep('list(winget(C, "browser_x_pw.*", "type"))'), close("browser_x_pw"))
    R("popup in windows list", br(dm_str(PAGE), "window=browser_x_pl;size=200x150"),
      rep('list(findtext(winget(C, null, "windows"), "browser_x_pl") ? "listed" : "not listed")'),
      close("browser_x_pl"),
      rep('list(findtext(winget(C, null, "windows"), "browser_x_pl") ? "listed" : "not listed")'))

    R("reuse id keeps size", br('"<html><body>a</body></html>"', "window=browser_x_r1;size=200x150"),
      br('"<html><body>b</body></html>"', "window=browser_x_r1;size=300x250;can_close=0"),
      rep('browser_x_props(C, "browser_x_r1", list("size", "can-close"))'), close("browser_x_r1"),
      rep('browser_x_state(C, "browser_x_r1")'))
    R("reuse id after close", br(dm_str(PAGE), "window=browser_x_r2;size=200x150"), close("browser_x_r2"),
      br(dm_str(PAGE), "window=browser_x_r2;size=260x180"), rep('browser_x_props(C, "browser_x_r2", list("size"))'),
      rep('browser_x_state(C, "browser_x_r2")'), close("browser_x_r2"))
    R("close never opened", close("browser_x_never"), rep('browser_x_state(C, "browser_x_never")'))
    R("close twice", br(dm_str(PAGE), "window=browser_x_c2;size=200x150"), close("browser_x_c2"), close("browser_x_c2"),
      rep('browser_x_state(C, "browser_x_c2")'))
    R("display=0 makes no window", br(dm_str(PAGE), "window=browser_x_d0;display=0;file=browser_x_d0.html"),
      rep('browser_x_state(C, "browser_x_d0")'), close("browser_x_d0"))
    R("winexists missing names", rep('list("a:[winexists(C, "browser_x_none")]", "b:[winexists(C, "browser_x_none.browser")]", '
                                     '"c:[winexists(C, "probe")]", "d:[winexists(C, "mainwindow.probe")]")'))

    # Popup pages that report through the browserxnote verb
    R("popup page js environment",
      br(dm_str(report_script('[typeof window.BYOND, location.protocol, document.body.textContent]')),
         "window=browser_x_j1;size=200x150"),
      "sleep(14)", close("browser_x_j1"), settle=1900)
    R("output html to popup browser",
      br(dm_str(PAGE), "window=browser_x_j2;size=200x150"),
      f'C << output({dm_str(report_script("[document.body.textContent]"))}, "browser_x_j2.browser")',
      "sleep(14)", close("browser_x_j2"), settle=1900)

    # browse_rsc of fixture images, loaded by the probe page
    for name, cmd, src in [("small.dmi", "browserxrsc small browser_x_small.png", "browser_x_small.png"),
                           ("rect.dmi", "browserxrsc rect browser_x_rect.png", "browser_x_rect.png"),
                           ("test.dmi", "browserxrsc test browser_x_test.png", "browser_x_test.png"),
                           ("dir dropped", "browserxrsc small browser_x_dir/browser_x_s2.png", "browser_x_s2.png"),
                           ("dir kept", "browserxrsc small browser_x_dir/browser_x_s3.png", "browser_x_dir/browser_x_s3.png"),
                           ("dmi extension", "browserxrsc small browser_x_s4.dmi", "browser_x_s4.dmi"),
                           ("never sent", "browserxrsc small browser_x_s5.png", "browser_x_never_sent.png")]:
        s.probe(f"browse_rsc {name}", f"{RSC}\nreturn await rsc({dm_js(cmd)}, {dm_js(src)});")


def dm_js(t):
    import json
    return json.dumps(t)
