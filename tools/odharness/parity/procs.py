"""Ports and processes of the parity harness. They are separate from odh.py's scene ports and state, so a
parity run and other odh.py work (or another agent) can run at the same time. stop() kills only the
processes this harness started, by PID."""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import odh  # noqa: E402

OD_PORT, OD_TOPIC, BY_PORT = 26420, 26421, 26020
STATE = HERE / "state.json"
KEYS = ("od_server", "by_server", "od_client", "by_client")


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def remember(key, pid):
    s = load()
    s[key] = pid
    STATE.write_text(json.dumps(s, indent=2))


def pid(key):
    return load().get(key)


def stop():
    s = load()
    for k in KEYS:
        p = s.pop(k, None)
        if p and odh.alive(p):
            subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    STATE.write_text(json.dumps(s, indent=2))
    for p in orphans():
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)


def orphans():
    """Engine processes on this harness's ports that state.json lost, e.g. after a killed run. Only this harness
    uses these ports, so this never matches odh.py work or another agent's engines."""
    marks = [f"net.port={OD_PORT}", f"udp://127.0.0.1:{OD_PORT}", f" {BY_PORT} ", f"127.0.0.1:{BY_PORT}"]
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(OpenDreamClient|OpenDreamServer|dreamdaemon|dreamseeker)\\.exe$' }"
          " | ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = []
    for line in r.stdout.split("\n"):
        pid, _, cmd = line.strip().partition("\t")
        if pid.isdigit() and any(m in cmd + " " for m in marks):
            out.append(int(pid))
    return out
