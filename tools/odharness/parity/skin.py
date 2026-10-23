"""Skin suite runner: boots both clients with the suite's test skin, runs the cases (winset, winget, winclone,
winshow, ...) while the clients are connected, and diffs the results.

    python -I skin.py <suite> [--timeout S]

A case that hangs an engine (no new result for HANG_SECS) is skipped, and the run restarts both worlds and
resumes after the cases that already have results. Screenshots of both clients go to out/live/.
"""
import sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import diff, gen, run  # noqa: E402
from live import Live  # noqa: E402

HANG_SECS = 15


def main(a):
    suite = a[0]
    timeout = float(a[a.index("--timeout") + 1]) if "--timeout" in a else 300
    run.build(suite)
    order = [l.split("\t", 1)[0] for l in run.lines((gen.BUILD / suite / "manifest.tsv").read_text(encoding="utf-8"))]
    acc = {"byond": {}, "od": {}}
    skip = {"byond": {}, "od": {}}
    t_all = time.time()
    for attempt in range(30):
        for e in acc:
            lines = [f"{k}\t=done\n" for k in acc[e]] + [f"{k}\t{v}\n" for k, v in skip[e].items()]
            (gen.BUILD / suite / e / "skip.txt").write_text("".join(lines), encoding="utf-8")
        with Live(suite) as L:
            L.cmd_all(cmd="run")
            pending, last, sizes = set(L.engines), time.time(), {}
            t0 = time.time()
            while pending and time.time() - t0 < timeout:
                for e in list(pending):
                    f = L.dir(e) / f"results_{e}.txt"
                    data = f.read_bytes() if f.exists() else b""
                    if b"#DONE" in data:
                        pending.discard(e)
                    if sizes.get(e) != len(data):
                        sizes[e], last = len(data), time.time()
                if time.time() - last > HANG_SECS:
                    break
                time.sleep(0.25)
            for e in L.engines:
                acc[e].update((k, v) for k, v in L.results(e).items() if not v.startswith("SKIP "))
            if not pending:
                L.shot("od", "skin_end")
                L.shot("byond", "skin_end")
        if not pending:
            break
        for e in pending:
            nxt = next((c for c in order if c not in acc[e] and c not in skip[e]), None)
            if nxt is None:
                pending = set()
                break
            print(f"{e}: hang at {nxt}, skipping it and restarting", flush=True)
            skip[e][nxt] = "hang"
        if not pending:
            break
    print(f"skin: done in {time.time() - t_all:.0f}s", flush=True)
    res = {e: {c: acc[e].get(c) or f"SKIP {skip[e][c]}" for c in order if c in acc[e] or c in skip[e]} for e in acc}
    gdir = run.GOLDEN / f"byond-{run.byond_version()}"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / f"{suite}.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["byond"].items()), encoding="utf-8")
    (gdir / f"{suite}.hash").write_text(run.case_hash(suite))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{suite}_od.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["od"].items()), encoding="utf-8")
    diff.main([suite])


if __name__ == "__main__":
    main(sys.argv[1:])
