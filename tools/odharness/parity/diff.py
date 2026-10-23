"""Compare OD results against the BYOND golden for a suite.

    python -I diff.py <suite> [--strict-errors] [--show N] [--proc NAME]

Each case lands in one bucket:
  pass         identical (after masking refs)
  err-text     both raised a runtime error, with different messages (counted as pass unless --strict-errors)
  precision    same displayed number, different value past the '~'
  compile      compiles on one engine only (usually arity or type checks BYOND does at compile time)
  known        a mismatch matching a pattern in known.tsv (glob on the case id or proc, a tab, the reason)
  fail         anything else, including COMPILE_ERROR/SKIP on one side only
Full detail goes to out/parity_<suite>.txt; the console gets a per-proc table and the first few failures.
"""
import fnmatch, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import gen, run  # noqa: E402

REF_RX = re.compile(r"\[0x[0-9a-fA-F]+\]")


def load(path):
    out = {}
    for line in run.lines(Path(path).read_bytes().decode("utf-8", errors="backslashreplace")):
        if "\t" in line:
            k, v = line.split("\t", 1)
            out[k] = REF_RX.sub("[0x?]", v)
    return out


def load_known():
    f = HERE / "known.tsv"
    if not f.exists():
        return []
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "\t" in line:
            pat, why = line.split("\t", 1)
            rows.append((pat.strip(), why.strip()))
    return rows


def classify(by, od, strict):
    if by == od:
        return "pass"
    if by is None or od is None:
        return "fail"
    if (by == "COMPILE_ERROR") != (od == "COMPILE_ERROR"):
        return "compile"
    if by.startswith("ERR ") and od.startswith("ERR "):
        return "fail" if strict else "err-text"
    strip = lambda v: re.sub(r"~[^\],=\s]*", "", v)
    if strip(by) == strip(od):
        return "precision"
    return "fail"


def main(a):
    suite = a[0]
    strict = "--strict-errors" in a
    show = int(a[a.index("--show") + 1]) if "--show" in a else 3
    only = a[a.index("--proc") + 1] if "--proc" in a else None
    import run
    gfile = run.GOLDEN / f"byond-{run.byond_version()}" / f"{suite}.txt"
    golden, od = load(gfile), load(HERE / "results" / f"{suite}_od.txt")
    manifest = {}
    for line in run.lines((gen.BUILD / suite / "manifest.tsv").read_text(encoding="utf-8")):
        cid, proc, code = line.split("\t", 2)
        manifest[cid] = (proc, code)
    known = load_known()

    per_proc = defaultdict(Counter)
    detail = defaultdict(list)
    for cid, (proc, code) in manifest.items():
        if only and proc != only:
            continue
        by, o = golden.get(cid, "MISSING"), od.get(cid, "MISSING")
        b = classify(by, o, strict)
        if b == "fail":
            why = next((w for p, w in known if fnmatch.fnmatchcase(cid, p) or fnmatch.fnmatchcase(proc, p)), None)
            if why:
                b = "known"
        per_proc[proc][b] += 1
        if b != "pass":
            detail[proc].append((b, code, by, o))

    report = HERE.parent / "out" / f"parity_{suite}.txt"
    report.parent.mkdir(exist_ok=True)
    with open(report, "w", encoding="utf-8") as f:
        for proc in sorted(detail):
            f.write(f"== {proc}\n")
            for b, code, by, o in detail[proc]:
                f.write(f"[{b}] {code}\n    BYOND: {by}\n    OD:    {o}\n")
    total = Counter()
    for c in per_proc.values():
        total.update(c)

    cols = ["pass", "fail", "compile", "known", "err-text", "precision"]
    print(f"\n{'proc':28}" + "".join(f"{c:>10}" for c in cols))
    for proc in sorted(per_proc, key=lambda p: (-per_proc[p]["fail"], p)):
        c = per_proc[proc]
        print(f"{proc:28}" + "".join(f"{c[k]:>10}" for k in cols))
    print(f"{'TOTAL':28}" + "".join(f"{total[k]:>10}" for k in cols))
    print()
    for proc in sorted(detail, key=lambda p: -per_proc[p]["fail"]):
        fails = [d for d in detail[proc] if d[0] == "fail"][:show]
        for _, code, by, o in fails:
            print(f"{proc}: {code}\n    BYOND: {by}\n    OD:    {o}")
    print(f"\nfull report: {report}")


if __name__ == "__main__":
    main(sys.argv[1:])
