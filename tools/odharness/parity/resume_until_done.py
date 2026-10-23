"""Reruns `run.py <suite> --od-only --resume` until the OD half finishes. For suites where OD crashes
on many cases, which needs more time than one shell command gets.

    python -I resume_until_done.py <suite> [max_passes]
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
suite = sys.argv[1]
passes = int(sys.argv[2]) if len(sys.argv) > 2 else 20
log = HERE.parent / "out" / f"parity_{suite}_resume.log"
with open(log, "a", encoding="utf-8") as f:
    for i in range(passes):
        r = subprocess.run([sys.executable, "-I", "-u", str(HERE / "run.py"), suite, "--od-only", "--resume"],
                           stdout=f, stderr=subprocess.STDOUT)
        f.write(f"#PASS {i} exit {r.returncode}\n")
        f.flush()
        if r.returncode == 0:
            f.write("#FINISHED\n")
            break
