"""Parity suite generator. It makes one DM project per engine from specs/<suite>/*.py.

    python -I gen.py <suite> [--exclude-od FILE] [--exclude-byond FILE]
    python -I gen.py --list                 suites and case counts

Each spec module defines build(s). build(s) calls s.sweep(), s.case() or s.body() on a Suite.
A case id is "<proc>#<hash of the DM code>". A case keeps its id and its saved BYOND result while
its code does not change, also when other cases are added.

Output: build/<suite>/<engine>/{scene.dme, parity.dm, cases.dm, spans.json} and build/<suite>/manifest.tsv
(id, proc, code). spans.json gives the first and last line of each case in cases.dm.
"""
import hashlib, importlib.util, itertools, json, random, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
SPECS = HERE / "specs"
BUILD = HERE / "build"
CHUNK = 150  # cases per generated proc


def dm_str(s):
    """Returns a DM text literal for s. Each character that DM interprets is escaped."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "[":
            out.append("\\[")
        elif ch == "]":
            out.append("\\]")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 32:
            out.append(f'[ascii2text({ord(ch)})]')
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def pairwise(pools, seed=1):
    """Greedy all-pairs covering array. Each value pair of each two argument positions is in one row or more.
    The rows are deterministic for a given input."""
    rng = random.Random(seed)
    n = len(pools)
    uncovered = {(i, a, j, b) for i in range(n) for j in range(i + 1, n)
                 for a in range(len(pools[i])) for b in range(len(pools[j]))}
    rows = []
    while uncovered:
        best, best_gain = None, -1
        # Each candidate starts with one uncovered pair. The other positions are filled greedily.
        seeds = rng.sample(sorted(uncovered), min(30, len(uncovered)))
        for (i, a, j, b) in seeds:
            row = [None] * n
            row[i], row[j] = a, b
            for k in range(n):
                if row[k] is not None:
                    continue
                gains = []
                for v in range(len(pools[k])):
                    g = sum(1 for m in range(n) if row[m] is not None and
                            ((min(k, m), v if k < m else row[m], max(k, m), row[m] if k < m else v) in uncovered))
                    gains.append((g, -v))
                row[k] = -max(gains)[1]
            gain = sum(1 for x in range(n) for y in range(x + 1, n) if (x, row[x], y, row[y]) in uncovered)
            if gain > best_gain:
                best, best_gain = row, gain
        for x in range(n):
            for y in range(x + 1, n):
                uncovered.discard((x, best[x], y, best[y]))
        rows.append(best)
    return rows


class Suite:
    def __init__(self, name):
        self.name = name
        self.cases = {}   # id -> (proc, code lines, result expr, display)
        self.order = []
        self.defines = {}    # PARITY_MAXX and others, written to pre.dm, which is included before parity.dm
        self.extra_dm = []   # top-level DM (helper procs, types) written to defs.dm
        self.resources = {}  # build file name -> source path

    def define(self, name, value):
        """Adds a #define that comes before parity.dm, for example s.define("PARITY_MAXX", 20)."""
        if self.defines.get(name, value) != value:
            raise SystemExit(f"{name} defined twice with different values")
        self.defines[name] = value

    def dm(self, code):
        """Adds top-level DM for helper procs and types. Start each name with the spec name to prevent name clashes."""
        if code not in self.extra_dm:
            self.extra_dm.append(code)

    def resource(self, name, path):
        """Copies path into the build folder as name. Cases can then use 'name' or file("name")."""
        self.resources[name] = Path(path)

    live_view = None  # (tiles wide, tiles high) when this is a live suite
    render_mode = False

    def render(self):
        """Makes this a render-page suite (lib/render.dm). Cells are drawn on pages and compared as pixels."""
        self.render_mode = True
        self.live((25, 17))
        self.define("PARITY_MAXX", 25)
        self.define("PARITY_MAXY", 17)
        self.define("PARITY_MAXZ", 1)
        self.cells = getattr(self, "cells", [])

    browser_mode = False

    def browser(self):
        """Makes this a browser probe suite (lib/browser.dm). Probes run in order in the "probe" browser control of the skin."""
        self.browser_mode = True
        self.live((9, 7))
        self.probes = getattr(self, "probes", [])
        self.js_prelude = getattr(self, "js_prelude", [])

    def js(self, code):
        """JS added once to the probe page before the probes, for helpers that several probes use."""
        if code not in self.js_prelude:
            self.js_prelude.append(code)

    def _probe(self, kind, name, payload):
        cid = f"{kind}#{hashlib.sha1((kind + repr(payload)).encode()).hexdigest()[:10]}"
        if not any(p["id"] == cid for p in self.probes):
            self.probes.append({"id": cid, "kind": kind, "name": name, "payload": payload})
        return cid

    def probe(self, name, js):
        """A JS probe. js is the body of an async function. The page records its return value as JSON."""
        return self._probe("js", name, js)

    def roundtrip(self, name, dm_lines, settle_ms=300):
        """A DM -> page probe. dm_lines run with C = the client and usually call output(..., "probe:parity_recv").
        The page records the argument lists that parity_recv() got in settle_ms, as JSON."""
        return self._probe("rt", name, {"dm": list(dm_lines), "settle": settle_ms})

    def link(self, name, query):
        """A page -> DM probe. The page opens byond://?parity_link=<id>&<query>.
        DM records the parsed href_list as <id>:dm and the raw href as <id>:href.
        query is JS source for a string expression."""
        return self._probe("link", name, query)

    skin_mode = False
    skin_window = None

    def skin(self, dmf, window=(1100, 850)):
        """Makes this a skin suite (lib/skin.dm). dmf is the path of the test skin, used instead of the generated
        one. The cases are ordinary s.case()/s.body() cases that run while a client is connected (live_client).
        window is the outer client window size."""
        self.skin_mode = True
        self.skin_dmf = Path(dmf)
        self.skin_window = window
        self.live((9, 7))

    prompt_mode = False

    def prompts(self):
        """Makes this a prompt suite (lib/prompt.dm)."""
        self.prompt_mode = True
        self.live((9, 7))
        self.prompt_cases = getattr(self, "prompt_cases", [])

    def prompt(self, name, call, answer, lines=()):
        """One prompt case. lines run first. call is a DM expression that opens a prompt for C (the client),
        for example 'input(C, "msg", "title") as text'. answer is a list of harness actions: ("text", s),
        ("select", index), ("press", label), ("submit",) or ("close",)."""
        key = repr((list(lines), call, answer))
        cid = f"prompt#{hashlib.sha1(key.encode()).hexdigest()[:10]}"
        if not any(c["id"] == cid for c in self.prompt_cases):
            self.prompt_cases.append({"id": cid, "name": name, "call": call, "lines": list(lines), "answer": answer})
        return cid

    def cell(self, name, lines, solo=False, tol=None):
        """One render cell. lines are DM statements that run with T = the centre turf of the cell.
        A cell is 3x3 tiles, so effects can spill one tile in each direction.
        solo=True gives the cell its own page. Use it for anything that changes the whole view
        (plane masters, client.color, client.screen).
        tol is (max share of differing pixels, max mean channel difference) for this cell.
        The default comes from render_cmp.py."""
        lines = list(lines)
        cid = f"cell#{hashlib.sha1(('\n'.join(lines) + str(solo)).encode()).hexdigest()[:10]}"
        if any(c["id"] == cid for c in self.cells):
            return cid
        self.cells.append({"id": cid, "name": name, "lines": lines, "solo": solo, "tol": tol})
        return cid

    def live(self, view=(25, 17)):
        """Makes this a live suite (lib/live.dm). The world stays up for a client, and world Topic drives it.
        The skin is one window with only a map at 1x zoom, sized exactly to the view."""
        self.live_view = view
        self.define("PARITY_LIVE", 1)
        self.define("LIVE_VIEW", f'"{view[0]}x{view[1]}"')


    def _add(self, proc, lines, expr, display):
        key = "\n".join(lines) + "\n" + expr
        cid = f"{proc}#{hashlib.sha1(key.encode()).hexdigest()[:10]}"
        if cid in self.cases:
            return cid
        self.cases[cid] = (proc, lines, expr, display)
        self.order.append(cid)
        return cid

    def case(self, proc, expr):
        """One case whose result is the DM expression expr."""
        return self._add(proc, [], expr, expr)

    def body(self, proc, lines, result, display=None):
        """Statements run first, then result is recorded. Use for side effects (the list after Cut())."""
        return self._add(proc, list(lines), result, display or ("; ".join(lines) + " => " + result))

    def call(self, proc, *args):
        return self.case(proc, f"{proc}({', '.join(args)})")

    def sweep(self, proc, pools, min_args=None, full_upto=2, fmt=None):
        """Call proc with every combination of values for up to full_upto arguments and an all-pairs
        selection beyond that, for each argument count from min_args to len(pools)."""
        min_args = len(pools) if min_args is None else min_args
        n = 0
        for count in range(min_args, len(pools) + 1):
            ps = pools[:count]
            if count <= full_upto:
                rows = itertools.product(*ps)
            else:
                rows = ([ps[i][v] for i, v in enumerate(r)] for r in pairwise(ps))
            for args in rows:
                expr = fmt(*args) if fmt else f"{proc}({', '.join(args)})"
                self.case(proc, expr)
                n += 1
        return n


def live_skin(w_px, h_px, browser=None):
    """A skin with a map control of exactly w_px x h_px at zoom 1, with no stretch and no smoothing.
    A browser suite also gets a browser control "probe" of browser=(w, h) to the right of the map."""
    total_w = w_px + (browser[0] if browser else 0)
    total_h = max(h_px, browser[1] if browser else 0)
    extra = f"""	elem "probe"
		type = BROWSER
		pos = {w_px},0
		size = {browser[0]}x{browser[1]}
		anchor1 = none
		anchor2 = none
""" if browser else ""
    return f"""window "mainwindow"
	elem "mainwindow"
		type = MAIN
		pos = 0,0
		size = {total_w}x{total_h}
		is-default = true
		title = "parity"
		statusbar = false
		can-resize = false
	elem "map"
		type = MAP
		pos = 0,0
		size = {w_px}x{h_px}
		anchor1 = none
		anchor2 = none
		is-default = true
		zoom = 1
		zoom-mode = distort
		text-mode = false
""" + extra


PROBE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>parity probes</title></head>
<body style="font:12px sans-serif"><div id="status">starting</div>
<script>
// Generated by gen.py. Runs every probe in order and reports each one through a byond:// link;
// DM acknowledges with output("1", "probe:parity_ack") before the next message is sent.
var ackResolve = null, recvLog = null;
function send(q) { location.href = "byond://?" + q; }
window.parity_ack = function () { if (ackResolve) { var r = ackResolve; ackResolve = null; r(); } };
window.parity_recv = function () { if (recvLog) recvLog.push(Array.prototype.slice.call(arguments)); };
function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function timeout(p, ms) { return Promise.race([p, sleep(ms).then(function () { throw new Error("timeout"); })]); }
function waitAck(q) { return new Promise(function (res) { ackResolve = res; send(q); }); }
function canon(v) { try { return JSON.stringify(v === undefined ? "<undefined>" : v); } catch (e) { return JSON.stringify("<unserialisable " + e + ">"); } }
function report(id, v) { return waitAck("parity_probe=" + encodeURIComponent(id) + "&v=" + encodeURIComponent(canon(v))); }
var parity_current = null;
/*PRELUDE*/
var PROBES = [
/*PROBES*/
];
async function run() {
  for (var i = 0; i < PROBES.length; i++) {
    var p = PROBES[i];
    parity_current = p.id;
    document.getElementById("status").textContent = (i + 1) + "/" + PROBES.length + " " + p.id;
    var v;
    try { v = await timeout(p.fn(), 8000); } catch (e) { v = { error: String(e && e.message || e) }; }
    if (v !== "__no_report__") {
      try { await timeout(report(p.id, v), 8000); } catch (e) { }
    }
  }
  document.getElementById("status").textContent = "done";
  send("parity_done=1");
}
setTimeout(run, 500);
</script></body></html>
"""


def emit_probes(probes, prelude=()):
    """probe.html text and the DM browser_request() proc for the suite's probes."""
    js, dm = [], ["", "/proc/browser_request(id, client/C)", "\tswitch(id)"]
    for p in probes:
        pid = json.dumps(p["id"])
        if p["kind"] == "js":
            js.append(f"{{id: {pid}, fn: async function () {{\n{p['payload']}\n}}}},")
        elif p["kind"] == "rt":
            js.append(f"{{id: {pid}, fn: async function () {{ recvLog = []; send('parity_req=' + encodeURIComponent({pid}));"
                      f" await sleep({p['payload']['settle']}); var got = recvLog; recvLog = null; return got; }}}},")
            dm.append(f'\t\tif({dm_str(p["id"])})')
            for l in p["payload"]["dm"] or ["return"]:
                dm.append("\t\t\t" + l)
        elif p["kind"] == "link":
            js.append(f"{{id: {pid}, fn: async function () {{ await waitAck('parity_link=' + encodeURIComponent({pid}) + '&' + ({p['payload']}));"
                      f" return '__no_report__'; }}}},")
    if len(dm) == 3:
        dm.append('\t\tif("")')
        dm.append("\t\t\treturn")
    page = PROBE_PAGE.replace("/*PRELUDE*/", "\n".join(prelude)).replace("/*PROBES*/", "\n".join(js))
    return page, "\n".join(dm) + "\n"


PAGE_SLOTS = 35   # 7 x 5 cells per page
SOLO_SLOT = 17    # the middle cell


def layout_cells(cells):
    """Assigns (page, slot) to every cell: shared pages packed in order, then one page per solo cell."""
    placed, page, slot = [], 0, 0
    for c in cells:
        if c["solo"]:
            continue
        placed.append({**c, "page": page, "slot": slot})
        slot += 1
        if slot == PAGE_SLOTS:
            page, slot = page + 1, 0
    if slot:
        page += 1
    for c in cells:
        if c["solo"]:
            placed.append({**c, "page": page, "slot": SOLO_SLOT})
            page += 1
    return placed


def emit_cells(cells, excluded):
    """DM for the render cells: one proc per cell plus render_build_page(n). Returns text, line spans, layout."""
    placed = layout_cells(cells)
    out = ["", "// Render cells, generated by gen.py", ""]
    spans = {}
    for k, c in enumerate(placed):
        start = len(out) + 1
        out.append(f"/proc/render_cell_{k}(turf/T)")
        if c["id"] in excluded:
            out.append(f'\tparity_emit_raw({dm_str(c["id"])}, "COMPILE_ERROR")')
        else:
            for l in c["lines"] or ["return"]:
                out.append("\t" + l)
        spans[c["id"]] = (start, len(out))
        out.append("")
    out.append("/proc/render_build_page(n)")
    out.append("\tvar/count = 0")
    out.append("\tswitch(n)")
    for page in sorted({c["page"] for c in placed}):
        out.append(f"\t\tif({page})")
        for k, c in enumerate(placed):
            if c["page"] != page:
                continue
            out.append("\t\t\ttry")
            out.append(f"\t\t\t\trender_cell_{k}(render_cell_turf({c['slot']}))")
            # BYOND rejects a repeated catch variable name within one block
            out.append(f"\t\t\tcatch(var/exception/__e{k})")
            out.append(f'\t\t\t\tparity_emit_err({dm_str(c["id"])}, __e{k})')
            out.append("\t\t\tcount++")
    out.append("\treturn count")
    out.append("")
    return "\n".join(out), spans, placed


def split_defs(code):
    """Splits DM code at top-level definitions, so one bad proc or type does not remove its neighbours."""
    parts, cur = [], []
    for line in code.split("\n"):
        if cur and line[:1] not in ("", "\t", " ") and not line.startswith("//"):
            parts.append(cur)
            cur = []
        cur.append(line)
    if cur:
        parts.append(cur)
    return parts


def emit_defs(blocks, excluded):
    """defs.dm text and the line span of each top-level definition. The ids are "defs#<block>.<part>"."""
    out = ["// Generated by gen.py from s.dm() calls", ""]
    spans = {}
    for k, code in enumerate(blocks):
        for j, part in enumerate(split_defs(code)):
            bid = f"defs#{k}.{j}"
            start = len(out) + 1
            if bid in excluded:
                out.append(f"// {bid} did not compile on this engine")
            else:
                out.extend(part)
            spans[bid] = (start, len(out))
        out.append("")
    return "\n".join(out) + "\n", spans


def emit_prompts(cases, excluded):
    """DM prompt_run(i, C): case i runs its lines and call, then writes the result."""
    out = ["", "/proc/prompt_run(i, client/C)", "\tvar/__r", "\tswitch(i)"]
    spans = {}
    for k, c in enumerate(cases):
        start = len(out) + 1
        out.append(f"\t\tif({k})")
        if c["id"] in excluded:
            out.append(f'\t\t\tparity_emit_raw({dm_str(c["id"])}, "COMPILE_ERROR")')
            spans[c["id"]] = (start, len(out))
            continue
        out.append("\t\t\ttry")
        for l in c["lines"]:
            out.append("\t\t\t\t" + l)
        out.append(f"\t\t\t\t__r = {c['call']}")
        out.append(f'\t\t\t\tparity_emit({dm_str(c["id"])}, __r)')
        out.append(f"\t\t\tcatch(var/exception/__e{k})")
        out.append(f'\t\t\t\tparity_emit_err({dm_str(c["id"])}, __e{k})')
        spans[c["id"]] = (start, len(out))
    if not cases:
        out.append("\t\tif(-1)")
        out.append("\t\t\treturn")
    return "\n".join(out) + "\n", spans


def load_suite(name):
    s = Suite(name)
    d = SPECS / name
    if not d.is_dir():
        raise SystemExit(f"no spec folder {d}")
    for f in sorted(d.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"spec_{name}_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(HERE))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.pop(0)
        mod.build(s)
    return s


def emit_timed_cases(s, excluded):
    """Skin suites: one proc per case, started with spawn. parity_timed() waits a limited time for it and records
    TIMEOUT for a case that never returns (a winget the client does not answer), so one case cannot stop the run."""
    out = ["// Generated by gen.py; do not edit", ""]
    spans = {}
    for k, cid in enumerate(s.order):
        proc, lines, expr, _ = s.cases[cid]
        start = len(out) + 1
        out.append(f"/proc/parity_case_{k}()")
        if cid in excluded:
            out.append(f'\tparity_results[{dm_str(cid)}] = "COMPILE_ERROR"')
        else:
            out.append("\tvar/__r")
            out.append("\ttry")
            for l in lines:
                out.append("\t\t" + l)
            out.append(f"\t\t__r = {expr}")
            out.append(f'\t\tparity_results[{dm_str(cid)}] = parity_canon(__r)')
            out.append("\tcatch(var/exception/__e)")
            out.append(f'\t\tparity_results[{dm_str(cid)}] = parity_err_text(__e)')
            out.append("\tif(parity_tracked.len)")
            out.append("\t\tparity_cleanup()")
        spans[cid] = (start, len(out))
        out.append("")
    out.append("/proc/parity_run_chunks()")
    for k, cid in enumerate(s.order):
        out.append(f'\tparity_timed(/proc/parity_case_{k}, {dm_str(cid)})')
    if not s.order:
        out.append("\treturn")
    out.append("")
    return "\n".join(out), spans


def emit_cases(s, excluded):
    """cases.dm text plus each case's line span."""
    if s.skin_mode:
        return emit_timed_cases(s, excluded)
    out = ["// Generated by gen.py; do not edit", ""]
    spans = {}
    chunks = [s.order[i:i + CHUNK] for i in range(0, len(s.order), CHUNK)]
    for ci, chunk in enumerate(chunks):
        out.append(f"/proc/parity_chunk_{ci}()")
        out.append("\tvar/__r")
        for cid in chunk:
            proc, lines, expr, _ = s.cases[cid]
            start = len(out) + 1
            if cid in excluded:
                out.append(f'\tparity_emit_raw({dm_str(cid)}, "COMPILE_ERROR")')
            else:
                out.append(f'\tif(!parity_skipped({dm_str(cid)}))')
                out.append("\t\ttry")
                for l in lines:
                    out.append("\t\t\t" + l)
                out.append(f"\t\t\t__r = {expr}")
                out.append(f'\t\t\tparity_emit({dm_str(cid)}, __r)')
                out.append("\t\tcatch(var/exception/__e)")
                out.append(f'\t\t\tparity_emit_err({dm_str(cid)}, __e)')
                out.append("\t\tif(parity_tracked.len)")
                out.append("\t\t\tparity_cleanup()")
            spans[cid] = (start, len(out))
        out.append("")
    out.append("/proc/parity_run_chunks()")
    for ci in range(len(chunks)):
        out.append(f"\tparity_chunk_{ci}()")
    if not chunks:
        out.append("\treturn")
    out.append("")
    return "\n".join(out), spans


def generate(name, excludes=None):
    """Writes build/<name>/<engine>/ for both engines. excludes: {engine: set(case ids)}."""
    excludes = excludes or {}
    s = load_suite(name)
    root = BUILD / name
    spans = None
    for engine in ("byond", "od"):
        d = root / engine
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / "lib" / "parity.dm", d / "parity.dm")
        for f in (HERE / "fixtures").glob("*.dmi"):
            shutil.copy(f, d / f.name)
        for rname, src in s.resources.items():
            (d / rname).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, d / rname)
        pre = "".join(f"#define {k} {v}\n" for k, v in s.defines.items())
        (d / "pre.dm").write_text("// Generated by gen.py\n" + pre, encoding="utf-8")
        dtext, dspans = emit_defs(s.extra_dm, excludes.get(engine, set()))
        (d / "defs.dm").write_text(dtext, encoding="utf-8")
        (d / "defs_spans.json").write_text(json.dumps(dspans))
        text, spans_e = emit_cases(s, excludes.get(engine, set()))
        if s.render_mode:
            # Cell procs come after the case chunks, so their line numbers are offset by the chunk text
            offset = text.count("\n") + 1
            ctext, cspans, placed = emit_cells(s.cells, excludes.get(engine, set()))
            text += ctext
            spans_e.update({k: (a + offset - 1, b + offset - 1) for k, (a, b) in cspans.items()})
            (root / "render_layout.json").write_text(json.dumps(
                [{k: c[k] for k in ("id", "name", "page", "slot", "solo", "tol")} for c in placed], indent=1), encoding="utf-8")
        if s.browser_mode:
            page, req = emit_probes(s.probes, s.js_prelude)
            (d / "probe.html").write_text(page, encoding="utf-8")
            text += req
        if s.prompt_mode:
            offset = text.count("\n") + 1
            ptext, pspans = emit_prompts(s.prompt_cases, excludes.get(engine, set()))
            text += ptext
            spans_e.update({k: (a + offset - 1, b + offset - 1) for k, (a, b) in pspans.items()})
            (root / "prompt_cases.json").write_text(json.dumps(s.prompt_cases, indent=1), encoding="utf-8")
        (d / "cases.dm").write_text(text, encoding="utf-8")
        includes = ["pre.dm", "parity.dm"]
        if s.live_view:
            shutil.copy(HERE / "lib" / "live.dm", d / "live.dm")
            ts = s.defines.get("PARITY_ICON_SIZE", 32)
            browser = (640, 480) if s.browser_mode else None
            if s.skin_mode:
                shutil.copy(s.skin_dmf, d / "skin.dmf")
            else:
                (d / "skin.dmf").write_text(live_skin(s.live_view[0] * ts, s.live_view[1] * ts, browser), encoding="utf-8")
            includes = ["skin.dmf"] + includes + ["live.dm"]
            for mode, lib in ((s.render_mode, "render.dm"), (s.browser_mode, "browser.dm"), (s.prompt_mode, "prompt.dm"),
                              (s.skin_mode, "skin.dm")):
                if mode:
                    shutil.copy(HERE / "lib" / lib, d / lib)
                    includes.append(lib)
        includes += ["defs.dm", "cases.dm"]
        (d / "scene.dme").write_text("".join(f'#include "{i}"\n' for i in includes), encoding="utf-8")
        # The files this build is made from. Cases also write files here, so run.case_hash() uses only this list.
        inputs = includes + ["scene.dme"] + sorted(f.name for f in (HERE / "fixtures").glob("*.dmi")) + sorted(s.resources)
        if s.browser_mode:
            inputs.append("probe.html")
        (d / "inputs.json").write_text(json.dumps(inputs))
        if engine == "byond":
            spans = spans_e
        (d / "spans.json").write_text(json.dumps(spans_e))
    flat = lambda t: str(t).replace(chr(9), " ").replace(chr(10), " ")
    with open(root / "manifest.tsv", "w", encoding="utf-8") as f:
        for cid in s.order:
            proc, _, _, display = s.cases[cid]
            f.write(f"{cid}\t{proc}\t{flat(display)}\n")
        # Browser probes report under their id (page side) and <id>:dm / <id>:href (server side)
        for p in getattr(s, "probes", []) if s.browser_mode else []:
            if p["kind"] in ("js", "rt"):
                f.write(f"{p['id']}\t{p['name']}\t{flat(p['payload'] if p['kind'] == 'js' else p['payload']['dm'])}\n")
            if p["kind"] in ("rt", "link"):
                f.write(f"{p['id']}:dm\t{p['name']}\t{flat(p['payload'] if p['kind'] == 'link' else 'server side')}\n")
            if p["kind"] == "link":
                f.write(f"{p['id']}:href\t{p['name']}\t{flat(p['payload'])} (raw href)\n")
        for c in getattr(s, "prompt_cases", []) if s.prompt_mode else []:
            f.write(f"{c['id']}\t{c['name']}\t{flat(c['call'])} answered {flat(c['answer'])}\n")
            f.write(f"{c['id']}:ui\t{c['name']}\t{flat(c['call'])} (prompt as shown)\n")
            f.write(f"{c['id']}:answer\t{c['name']}\t{flat(c['answer'])} (harness could apply the answer)\n")
    return s


def main(a):
    if not a or a[0] == "--list":
        for d in sorted(p for p in SPECS.iterdir() if p.is_dir()):
            print(f"{d.name:16} {len(load_suite(d.name).order):7} cases")
        return
    s = generate(a[0])
    print(f"{a[0]}: {len(s.order)} cases -> {BUILD / a[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
