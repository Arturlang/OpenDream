"""Parity runner: generate, compile, run each engine headless (one at a time), then diff.

    python -I run.py <suite> [--build-only] [--od-only] [--byond-only] [--resume] [--timeout S] [--strict-errors]

--od-only reuses the saved BYOND golden (golden/byond-<version>/<suite>.txt) when it was made from
identical cases. A case that compiles on one engine only is recorded as COMPILE_ERROR there; a case
that crashes or hangs an engine is skipped (SKIP crash/hang) and the run is repeated without it.
"""
import hashlib, json, re, subprocess, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import gen  # noqa: E402
import odh  # noqa: E402
import procs  # noqa: E402

GOLDEN = HERE / "golden"
HANG_SECS = 8  # no new result for this long = the next case hangs
# BYOND: "cases.dm:123:error: ..."   OD: "Error OD0000 at cases.dm:123:4: ..."
# defs.dm holds the s.dm() blocks. A block that does not compile is stubbed out like a case.
LINE_RX = {
    "byond": re.compile(r"(cases|defs)\.dm:(\d+):error"),
    "od": re.compile(r"Error\b.*?(cases|defs)\.dm:(\d+)"),
}


def byond_version():
    r = subprocess.run([str(odh.BYOND / "dm.exe")], capture_output=True, text=True)
    m = re.search(r"version (\d+\.\d+)", r.stdout + r.stderr)
    return m.group(1) if m else "unknown"


def compile_engine(engine, d):
    if engine == "od":
        r = subprocess.run([str(odh.OD / "bin/DMCompiler/DMCompiler.exe"), "--suppress-unimplemented", "scene.dme"],
                           cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 0
    else:
        r = subprocess.run([str(odh.BYOND / "dm.exe"), "scene.dme"], cwd=d, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = re.search(r"\b0 errors", r.stdout) is not None
    return ok, r.stdout + r.stderr


def lines_to_cases(engine, output, d):
    spans = {"cases": json.loads((d / "spans.json").read_text()), "defs": json.loads((d / "defs_spans.json").read_text())}
    bad = set()
    for m in LINE_RX[engine].finditer(output):
        ln = int(m.group(2))
        for cid, (a, b) in spans[m.group(1)].items():
            if a <= ln <= b:
                bad.add(cid)
    return bad


def build(suite):
    """Generate and compile both engines, excluding cases that don't compile on an engine."""
    excludes = {"byond": set(), "od": set()}
    for _ in range(6):
        gen.generate(suite, excludes)
        retry = False
        for engine in ("byond", "od"):
            d = gen.BUILD / suite / engine
            ok, out = compile_engine(engine, d)
            if ok:
                continue
            bad = lines_to_cases(engine, out, d) - excludes[engine]
            if not bad:
                raise SystemExit(f"{engine} compile failed outside generated cases:\n{out[-4000:]}")
            print(f"{engine}: {len(bad)} case(s) don't compile, recording them as COMPILE_ERROR", flush=True)
            excludes[engine] |= bad
            retry = True
        if not retry:
            return excludes
    raise SystemExit("compile exclusions did not converge")


def lines(text):
    """Split on \\n only. str.splitlines() also splits on U+2028, U+0085 and others that cases contain."""
    return [l[:-1] if l.endswith("\r") else l for l in text.split("\n") if l not in ("", "\r")]


def read_results(path):
    res = {}
    if not path.exists():
        return res, False
    done = False
    for line in lines(path.read_bytes().decode("utf-8", errors="backslashreplace")):
        if line == "#DONE":
            done = True
        elif "\t" in line and not line.startswith("#"):
            k, v = line.split("\t", 1)
            res[k] = v
    return res, done


def known_byond_skips(suite):
    """Cases that hung or crashed BYOND in the last golden. BYOND does not change, so skip them at once."""
    f = GOLDEN / f"byond-{byond_version()}" / f"{suite}.txt"
    if not f.exists():
        return {}
    res, _ = read_results(f)
    return {k: v[5:] for k, v in res.items() if v.startswith("SKIP ")}


def run_engine(engine, suite, timeout, resume=False):
    """Runs one engine until every case has a result. After a crash or hang the next run resumes after
    the cases that already have results (they are skipped silently) and skips the culprit.
    resume=True also skips the crashes and hangs that an interrupted run of the same build saved."""
    d = gen.BUILD / suite / engine
    order = [l.split("\t", 1)[0] for l in lines((gen.BUILD / suite / "manifest.tsv").read_text(encoding="utf-8"))]
    known = set(order)
    skip, acc = {}, {}
    saved = d / "skips.json"
    if engine == "byond":
        skip = {k: v for k, v in known_byond_skips(suite).items() if k in known}
    if resume and saved.exists():
        skip.update({k: v for k, v in json.loads(saved.read_text()).items() if k in known})
    elif saved.exists():
        saved.unlink()
    out = d / f"results_{engine}.txt"
    t_all = time.time()
    for attempt in range(200):
        skip_lines = [f"{k}\t=done\n" for k in acc] + [f"{k}\t{v}\n" for k, v in skip.items()]
        (d / "skip.txt").write_text("".join(skip_lines), encoding="utf-8")
        if out.exists():
            out.unlink()
        if engine == "od":
            args = [str(odh.OD / "bin/Content.Server/OpenDreamServer.exe"), "--cvar", f"net.port={procs.OD_PORT}",
                    "--cvar", f"opendream.topic_port={procs.OD_TOPIC}", "--cvar", f"opendream.json_path={d / 'scene.json'}"]
        else:
            args = [str(odh.BYOND / "dreamdaemon.exe"), "scene.dmb", str(procs.BY_PORT), "-trusted", "-invisible"]
        log = odh.OUT / f"parity_{suite}_{engine}.log"
        pid = odh.spawn(args, log, d)
        procs.remember("od_server" if engine == "od" else "by_server", pid)
        t0, last_size, last_change = time.time(), -1, time.time()
        status = "hang"
        while time.time() - t0 < timeout:
            res, done = read_results(out)
            if done:
                status = "done"
                break
            size = out.stat().st_size if out.exists() else 0
            if size != last_size:
                last_size, last_change = size, time.time()
            if not odh.alive(pid):
                status = "crash"
                break
            # No new output for a while once started: treat as a hang on the next case
            if size and time.time() - last_change > HANG_SECS:
                break
            time.sleep(0.5)
        procs.stop()
        res, done = read_results(out)
        acc.update((k, v) for k, v in res.items() if not v.startswith("SKIP "))
        if status == "done":
            # A case that wrote nothing (not even ERR) can take the rest of its chunk with it, as when an
            # error escapes try/catch; skip it as "abort" and resume so the cases after it still run
            first_missing = next((c for c in order if c not in acc and c not in skip), None)
            if first_missing:
                print(f"{engine}: no result for {first_missing}, skipping it as abort and resuming", flush=True)
                skip[first_missing] = "abort"
                continue
            res = {c: acc.get(c) or f"SKIP {skip[c]}" for c in order if c in acc or c in skip}
            print(f"{engine}: {len(res)} results in {time.time() - t_all:.1f}s" + (f", {len(skip)} skipped" if skip else ""), flush=True)
            return res
        # The first case without a result is the culprit
        nxt = next((c for c in order if c not in acc and c not in skip), None)
        if nxt is None:
            # Every case has a result, but the engine died before #DONE: a delayed crash from a proc an earlier case started
            print(f"{engine}: {status} after the last case (delayed crash); keeping the results", flush=True)
            return {c: acc.get(c) or f"SKIP {skip[c]}" for c in order if c in acc or c in skip}
        print(f"{engine}: {status} at {nxt}, skipping it and resuming", flush=True)
        skip[nxt] = status
        saved.write_text(json.dumps(skip))
        # The log is overwritten on restart, so keep its tail for each crash
        if status == "crash":
            tail = lines(log.read_bytes().decode("utf-8", "replace"))[-40:]
            with open(odh.OUT / f"parity_{suite}_{engine}_crashes.log", "a", encoding="utf-8") as f:
                f.write(f"=== {nxt}\n" + "\n".join(tail) + "\n")
    raise SystemExit(f"{engine}: too many crashes")


def case_hash(suite):
    """Everything the BYOND build is made from: generated DM, the library, fixtures and resources."""
    d = gen.BUILD / suite / "byond"
    h = hashlib.sha1()
    for name in sorted(set(json.loads((d / "inputs.json").read_text()))):
        h.update(name.encode() + b"\0" + (d / name).read_bytes())
    return h.hexdigest()


def main(a):
    suite = a[0]
    timeout = float(a[a.index("--timeout") + 1]) if "--timeout" in a else 180
    if "--build-only" in a:
        ex = build(suite)
        n = sum(1 for _ in open(gen.BUILD / suite / "manifest.tsv", encoding="utf-8"))
        layout = gen.BUILD / suite / "render_layout.json"
        if layout.exists():
            n += len(json.loads(layout.read_text(encoding="utf-8")))
        print(f"{suite}: {n} cases compile; COMPILE_ERROR on byond: {len(ex['byond'])}, od: {len(ex['od'])}")
        code = dict(l.split("\t")[0::2] for l in lines((gen.BUILD / suite / "manifest.tsv").read_text(encoding="utf-8")))
        for e in ("byond", "od"):
            for cid in sorted(ex[e])[:15]:
                print(f"  {e} rejects {code.get(cid, cid)}")
        return
    procs.stop()
    build(suite)
    gdir = GOLDEN / f"byond-{byond_version()}"
    gdir.mkdir(parents=True, exist_ok=True)
    gfile, ghash = gdir / f"{suite}.txt", gdir / f"{suite}.hash"
    h = case_hash(suite)

    if "--od-only" in a and ghash.exists() and ghash.read_text().strip() == h:
        print(f"byond: using saved golden {gfile}")
    elif "--od-only" not in a:
        res = run_engine("byond", suite, timeout, resume="--resume" in a)
        gfile.write_text("".join(f"{k}\t{v}\n" for k, v in res.items()), encoding="utf-8")
        ghash.write_text(h)
    else:
        raise SystemExit("no matching golden; run without --od-only once")
    if "--byond-only" in a:
        return
    res = run_engine("od", suite, timeout, resume="--resume" in a)
    odfile = HERE / "results" / f"{suite}_od.txt"
    odfile.parent.mkdir(exist_ok=True)
    odfile.write_text("".join(f"{k}\t{v}\n" for k, v in res.items()), encoding="utf-8")

    import diff
    diff.main([suite] + [x for x in a if x == "--strict-errors"])


if __name__ == "__main__":
    main(sys.argv[1:])
