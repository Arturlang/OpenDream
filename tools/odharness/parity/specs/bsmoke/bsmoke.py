"""Browser framework self-check: one probe of each kind."""


def build(s):
    s.browser()
    s.probe("js basics", "return [typeof window.Byond, typeof window.BYOND, 1 + 1];")
    s.probe("location", "return location.protocol;")
    s.roundtrip("output with params", ['C << output(list2params(list("a", "b c", "d&e")), "probe:parity_recv")'])
    s.roundtrip("output plain text", ['C << output("hello world", "probe:parity_recv")'])
    s.roundtrip("output url-encoded", ['C << output(url_encode("x y+z"), "probe:parity_recv")'])
    s.link("link simple", '"a=1&b=two"')
    s.link("link special chars", '"t=" + encodeURIComponent("a b+c;d&e=f%") + "&u=%41"')
    s.link("link repeated key", '"k=1&k=2&k=3"')
    s.probe("winget via Byond", """
if (window.Byond && Byond.winget) { return await Byond.winget("probe", "size"); }
if (window.BYOND && BYOND.winget) { return await BYOND.winget("probe", "size"); }
return "no winget API";
""")
