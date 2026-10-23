"""Browser probe runner: boots both clients, runs the suite's probe page in each, and diffs the results.

    python -I browser.py <suite> [--timeout S]

Results go where run.py puts them (golden/byond-<ver>/<suite>.txt, results/<suite>_od.txt), so diff.py and
the findings tools work the same. BYOND is rerun every time: live suites have no headless shortcut.
"""
import sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import diff, run  # noqa: E402
from live import Live  # noqa: E402


def main(a):
    suite = a[0]
    timeout = float(a[a.index("--timeout") + 1]) if "--timeout" in a else 300
    with Live(suite) as L:
        print(L.cmd_all(cmd="start"), flush=True)
        t0 = time.time()
        pending = set(L.engines)
        while pending and time.time() - t0 < timeout:
            for e in list(pending):
                f = L.dir(e) / f"results_{e}.txt"
                if f.exists() and "#PROBES_DONE" in f.read_bytes().decode("utf-8", "replace"):
                    print(f"{e}: probes done in {time.time() - t0:.0f}s", flush=True)
                    pending.discard(e)
            time.sleep(1)
        for e in pending:
            print(f"{e}: probes did not finish in {timeout:.0f}s; recording what arrived", flush=True)
        res = {e: L.results(e) for e in L.engines}
        L.shot("od", "browser")
        L.shot("byond", "browser")
    gdir = run.GOLDEN / f"byond-{run.byond_version()}"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / f"{suite}.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["byond"].items()), encoding="utf-8")
    (gdir / f"{suite}.hash").write_text(run.case_hash(suite))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{suite}_od.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["od"].items()), encoding="utf-8")
    diff.main([suite])


if __name__ == "__main__":
    main(sys.argv[1:])
