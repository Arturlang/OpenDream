"""Summarise a Tracy capture: top zones by self time and by total time.

  python -I tracysum.py <trace.tracy> [topN] [--filter TEXT]

Runs tracy-csvexport twice (inclusive and self) and joins them per zone (name + source location).
Zone names for DM procs are the proc path; the source column is the .dm file and line.
"""
import csv, io, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPORT = HERE / "tracy-0.13.1/csvexport/build/Release/tracy-csvexport.exe"

trace = sys.argv[1]
top = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 40
flt = sys.argv[sys.argv.index("--filter") + 1] if "--filter" in sys.argv else None


def export(self_time):
    args = [str(EXPORT), *(["-e"] if self_time else []), *(["-f", flt] if flt else []), trace]
    out = subprocess.run(args, capture_output=True, text=True, errors="replace").stdout
    rows = {}
    for r in csv.DictReader(io.StringIO(out)):
        key = (r["name"], r["src_file"], r["src_line"])
        rows[key] = r
    return rows


inc, slf = export(False), export(True)
span_ns = max(float(r["total_ns"]) for r in inc.values()) if inc else 1


def fmt(ns):
    return f"{ns / 1e6:10.1f}ms"


def label(key):
    name, f, line = key
    where = f"{Path(f).name}:{line}" if f and f not in ("Native Proc",) else f
    return f"{name[:70]:70} {where[:40]}"


for title, rows, col in (("SELF time", slf, "total_ns"), ("TOTAL (inclusive) time", inc, "total_ns")):
    print(f"\n== {title} (top {top}); % of longest zone {fmt(span_ns).strip()}")
    print(f"{'time':>12} {'%':>6} {'calls':>10} {'mean':>10}  zone")
    for key, r in sorted(rows.items(), key=lambda kv: -float(kv[1][col]))[:top]:
        ns, n = float(r[col]), int(r["counts"])
        print(f"{fmt(ns)} {100 * ns / span_ns:6.2f} {n:10d} {float(r['mean_ns']) / 1e3:8.1f}us  {label(key)}")
