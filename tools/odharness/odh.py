"""OpenDream vs BYOND self-test harness.

Run with `python -I odh.py <command> ...`. State (PIDs, ports, log paths) lives in state.json
next to this file, so commands can be issued one at a time from any shell.

  od-server  <game_dir> [--json X.json] [--wait REGEX] [--cvar k=v] [--env K=V]  boot OpenDreamServer (metrics on :44880) and wait
  od-client  <game_dir> [--uncapped] [--skin-dump] [--cvar k=v]...boot OpenDreamClient, wait for first frame
  by-server  <game_dir> <x.dmb>                        boot DreamDaemon on the BYOND port
  by-client                                            boot DreamSeeker against it
  compile-od <game_dir> <x.dme> [-D DEF ...]           DMCompiler, prints phase timings
  compile-by <game_dir> <x.dme> [-D DEF ...]           BYOND dm.exe with defines
  place      <od|by|both> [W H]                        same outer window size for both clients (default 1600x900)
  shot       <name> [od|by|both]                       PrintWindow capture; both -> side-by-side <name>.png
  click      <od|by|both> X Y [--right] [--double]      click at client-area coords
  hold       <od|by|both> <KEY> [ms]                  hold a key with auto-repeat, then release
  key        <od|by|both> KEYS                         SendKeys-syntax keys to the window
  windows    [od|by|both]                              list visible top-level windows (popups included)
  (any command) --title SUBSTR                         act on a popup window instead of the main one
  tree       <by|od>                                   Win32 child-window geometry (BYOND controls are real HWNDs)
  skin                                                 OD skin dump geometry (needs od-client --skin-dump)
  perf       [seconds]                                 server CPU/RAM + metrics deltas, client FPS/CPU
  threads    <od-server|od-client|...> [seconds]       exact per-thread CPU with names
  trace      <od-client|od-server> [seconds]           dotnet-trace sample + main-thread hot path summary
  scene      <name> [W H] [-D DEF ...] [--wait S] [--od-only]  run scenes/<name>/scene.dme on both engines, side-by-side shot
  bench      [scene]                                   headless per-operation timings, BYOND vs OD (one engine at a time)
  (any command) --scene                                act on the scene engines (shot/click/key/windows/tree)
  parity     <suite> [--od-only] [--build-only]         builtin proc parity vs BYOND golden (parity/README.md)
  stop       [scene|od|by|od-client|od-server|by-client|by-server|all]  kill harness-started processes by PID
  status                                               what is running
"""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
OUT = HERE / "out"
OD = Path(os.environ.get("OD_ROOT", HERE.parents[1]))
BYOND = Path(os.environ.get("BYOND_BIN", r"C:\Program Files (x86)\BYOND\bin"))
OD_PORT, OD_TOPIC, BY_PORT, METRICS = 26400, 26401, 25999, 44880
WIN32 = HERE / "win32.ps1"


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(s):
    STATE.write_text(json.dumps(s, indent=2))


def alive(pid):
    if not pid:
        return False
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in r.stdout


def spawn(args, log, cwd, env=None):
    OUT.mkdir(exist_ok=True)
    if env:
        env = {**os.environ, **env}
    f = open(log, "w", encoding="utf-8", errors="replace")
    # Fully detached, so a calling shell never waits on the child's inherited handles
    p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    return p.pid


def wait_log(log, pattern, timeout, pid=None):
    rx = re.compile(pattern)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
                if rx.search(line):
                    return line, time.time() - t0
        except FileNotFoundError:
            pass
        if pid and not alive(pid):
            raise SystemExit(f"process {pid} exited; see {log}")
        time.sleep(1)
    raise SystemExit(f"timed out after {timeout}s waiting for /{pattern}/ in {log}")


TITLE = None  # --title X on any command targets a popup window by title substring
PREFIX = ""   # --scene on any command acts on the scene engines instead of the game ones
SCENE_OD_PORT, SCENE_OD_TOPIC, SCENE_BY_PORT = 26410, 26411, 26010
SCENES = HERE / "scenes"


def ps(cmd, pid, *extra):
    if TITLE:
        extra = (*extra, "-Title", TITLE)
    # win32.ps1 prints UTF-8, so dialog text with non-Latin characters decodes
    r = subprocess.run(["pwsh", "-NoProfile", "-File", str(WIN32), cmd, "-ProcessId", str(pid), *map(str, extra)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).strip()
    if r.returncode:
        raise SystemExit(out)
    return out


def engines(which):
    s = load()
    pids = {"od": s.get(PREFIX + "od_client"), "by": s.get(PREFIX + "by_client")}
    sel = ["od", "by"] if which == "both" else [which]
    res = [(e, pids[e]) for e in sel if pids[e] and alive(pids[e])]
    if not res:
        raise SystemExit(f"no running client for {which}")
    return res


def envs(a):
    """--env K=V (repeatable) for engine launches"""
    return dict(a[i + 1].split("=", 1) for i, x in enumerate(a) if x == "--env") or None


def cvars(a):
    """--cvar k=v (repeatable) passthrough for engine launches"""
    return sum((["--cvar", a[i + 1]] for i, x in enumerate(a) if x == "--cvar"), [])


def cmd_od_server(a):
    game = Path(a[0]).resolve()
    js = game / (a[a.index("--json") + 1] if "--json" in a else next(game.glob("*.json")).name)
    wait = a[a.index("--wait") + 1] if "--wait" in a else r"Initializations complete"
    log = OUT / "od_server.log"
    pid = spawn([str(OD / "bin/Content.Server/OpenDreamServer.exe"),
                 "--cvar", f"net.port={OD_PORT}", "--cvar", f"opendream.topic_port={OD_TOPIC}",
                 "--cvar", f"opendream.json_path={js}", "--cvar", "metrics.enabled=true",
                 "--cvar", f"metrics.port={METRICS}", *cvars(a)], log, game, envs(a))
    s = load(); s.update(od_server=pid, od_server_log=str(log), game=str(game)); save(s)
    line, dt = wait_log(log, wait, 900, pid)
    print(f"od-server pid={pid} ready in {dt:.1f}s: {line.strip()}")


def cmd_od_client(a):
    game = Path(a[0]).resolve()
    log = OUT / "od_client.log"
    args = [str(OD / "bin/Content.Client/OpenDreamClient.exe"), "--connect", "--connect-address",
            f"udp://127.0.0.1:{OD_PORT}", "--cvar", "opendream.debug_renderperf=true"]
    if "--uncapped" in a:
        args += ["--cvar", "display.vsync=false"]
    args += cvars(a)
    if "--skin-dump" in a:
        args += ["--cvar", "opendream.skin_dump_path=/odh_skin_dump.json", "--cvar", "opendream.skin_dump_delay=20"]
    pid = spawn(args, log, game)
    s = load(); s.update(od_client=pid, od_client_log=str(log)); save(s)
    _, dt = wait_log(log, "RENDERPERF", 300, pid)
    print(f"od-client pid={pid} rendering after {dt:.1f}s")


def cmd_by_server(a):
    game, dmb = Path(a[0]).resolve(), a[1]
    pid = spawn([str(BYOND / "dreamdaemon.exe"), dmb, str(BY_PORT), "-trusted", "-invisible"], OUT / "by_server.log", game)
    s = load(); s.update(by_server=pid); save(s)
    print(f"by-server pid={pid} port={BY_PORT} (world.log goes to its own window; DreamSeeker can connect once it is up)")


def cmd_by_client(a):
    pid = spawn([str(BYOND / "dreamseeker.exe"), f"byond://127.0.0.1:{BY_PORT}"], OUT / "by_client.log", HERE)
    s = load(); s.update(by_client=pid); save(s)
    # DreamSeeker's window appears once the connection lands.
    for _ in range(120):
        try:
            ps("tree", pid)
            print(f"by-client pid={pid} has a window")
            return
        except SystemExit:
            time.sleep(1)
    raise SystemExit("DreamSeeker never opened a window")


def cmd_compile_od(a):
    game, dme = Path(a[0]).resolve(), a[1]
    defs = [x for i, x in enumerate(a) if i > 0 and a[i - 1] == "-D"]
    args = [str(OD / "bin/DMCompiler/DMCompiler.exe"), "--suppress-unimplemented", *sum((["--define", d] for d in defs), []), dme]
    t0 = time.time()
    r = subprocess.run(args, cwd=game, capture_output=True, text=True)
    out = r.stdout + r.stderr
    keep = [l for l in out.splitlines() if re.search(r"error|Compiling|succeeded|failed|^\s+\S.*\d+%|Total time|Peak memory", l, re.I)]
    print("\n".join(keep[-40:]))
    print(f"exit={r.returncode} wall={time.time() - t0:.1f}s")


def cmd_compile_by(a):
    """compile-by <game_dir> <x.dme> [-D DEF ...]: BYOND dm.exe with defines (no edits to the game's files)"""
    game, dme = Path(a[0]).resolve(), a[1]
    defs = [x for i, x in enumerate(a) if i > 0 and a[i - 1] == "-D"]
    t0 = time.time()
    r = subprocess.run([str(BYOND / "dm.exe"), *[f"-D{d}" for d in defs], dme], cwd=game, capture_output=True, text=True)
    print(chr(10).join(l for l in r.stdout.splitlines() if re.search(r"error|warning|Total time|dmb", l))[-3000:])
    print(f"exit={r.returncode} wall={time.time() - t0:.1f}s")


def cmd_place(a):
    which = a[0] if a else "both"
    w, h = (int(a[1]), int(a[2])) if len(a) >= 3 else (1600, 900)
    # Side by side, OD left and DreamSeeker right, so whoever is watching sees both
    for e, pid in engines(which):
        print(e, ps("place", pid, "-W", w, "-H", h, "-X", 0 if e == "od" else w, "-Y", 0))


def cmd_shot(a):
    name, which = a[0], (a[1] if len(a) > 1 else "both")
    OUT.mkdir(exist_ok=True)
    files = []
    for e, pid in engines(which):
        f = OUT / f"{PREFIX}{name}_{e}.png"
        print(ps("shot", pid, "-Out", f))
        files.append(f)
    if len(files) == 2:
        combo = OUT / f"{PREFIX}{name}.png"
        script = (
            "Add-Type -AssemblyName System.Drawing;"
            f"$a=[Drawing.Image]::FromFile('{files[0]}');$b=[Drawing.Image]::FromFile('{files[1]}');"
            "$w=$a.Width+$b.Width+8;$h=[Math]::Max($a.Height,$b.Height);"
            "$c=New-Object Drawing.Bitmap $w,$h;$g=[Drawing.Graphics]::FromImage($c);$g.Clear([Drawing.Color]::Magenta);"
            "$g.DrawImage($a,0,0,$a.Width,$a.Height);$g.DrawImage($b,$a.Width+8,0,$b.Width,$b.Height);"
            f"$c.Save('{combo}');$a.Dispose();$b.Dispose()")
        subprocess.run(["pwsh", "-NoProfile", "-Command", script], check=True)
        print(f"side-by-side (OD left, BYOND right): {combo}")


def cmd_burst(a):
    """burst <name> <frames> <interval_ms> [od|by]: capture a run of screenshots and save them as <name>.gif"""
    from PIL import Image
    name, frames, interval = a[0], int(a[1]), int(a[2])
    which = a[3] if len(a) > 3 else "by"
    OUT.mkdir(exist_ok=True)
    images = []
    for i in range(frames):
        start = time.time()
        for e, pid in engines(which):
            f = OUT / f"{PREFIX}{name}_{i:03d}_{e}.png"
            ps("shot", pid, "-Out", f)
            images.append(Image.open(f).convert("RGB"))
        time.sleep(max(0, interval / 1000 - (time.time() - start)))
    gif = OUT / f"{PREFIX}{name}.gif"
    images[0].save(gif, save_all=True, append_images=images[1:], duration=interval, loop=0)
    print(f"{len(images)} frames -> {gif}")


def cmd_click(a):
    which, x, y = a[0], int(a[1]), int(a[2])
    extra = (["-Button", "right"] if "--right" in a else []) + (["-Double"] if "--double" in a else [])
    for e, pid in engines(which):
        print(e, ps("click", pid, "-X", x, "-Y", y, *extra))
        time.sleep(0.3)


def cmd_key(a):
    for e, pid in engines(a[0]):
        print(e, ps("key", pid, "-Keys", a[1]))


def cmd_hold(a):
    """hold <od|by|both> <key letter or vk number> [ms]: hold a key down (with auto-repeat), then release"""
    which, key = a[0], a[1]
    vk = ord(key.upper()) if len(key) == 1 else int(key, 0)
    ms = a[2] if len(a) > 2 else "1000"
    for e, pid in engines(which):
        print(e, ps("hold", pid, "-Vk", vk, "-Ms", ms))
        time.sleep(0.5)


def cmd_seq(a):
    """seq <od|by|both> 'D+ 300 W+ 200 D- 300 W-': play overlapping presses; held keys auto-repeat"""
    for e, pid in engines(a[0]):
        print(e, ps("seq", pid, "-Seq", a[1]))
        time.sleep(0.5)


def cmd_windows(a):
    for e, pid in engines(a[0] if a else "both"):
        print(f"[{e}]")
        print(ps("windows", pid))


def cmd_tree(a):
    for e, pid in engines(a[0] if a else "by"):
        print(ps("tree", pid))


def cmd_skin(a):
    p = Path(os.environ["APPDATA"]) / "Space Station 14" / "data" / "odh_skin_dump.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print("reference window", d["reference_window_size"])
    for k, v in d["elements"].items():
        if v.get("is-visible", "1") in ("1", "true"):
            extra = " ".join(f"{x}={v[x]}" for x in ("splitter", "left", "right", "is-vert") if x in v)
            print(f"{k:45} pos={v.get('pos', ''):>10} size={v.get('size', ''):>10} {extra}")


def metrics():
    out = {}
    try:
        text = urllib.request.urlopen(f"http://localhost:{METRICS}/metrics", timeout=10).read().decode()
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^(\S+?)(\{.*\})?\s+(\S+)$", line)
        if m and not line.startswith("#") and re.search(r"_(sum|count|total)$", m.group(1)):
            try:
                out[m.group(1) + (m.group(2) or "")] = float(m.group(3))
            except ValueError:
                pass
    return out


def tree_stats(pids):
    """CPU seconds and private memory summed over each pid and all its descendants (browser helpers etc.)"""
    cmd = r"""
$all = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name, KernelModeTime, UserModeTime, PrivatePageCount, CreationDate
$kids = @{}; foreach ($p in $all) { $kids[[int]$p.ParentProcessId] += ,$p }
$byId = @{}; foreach ($p in $all) { $byId[[int]$p.ProcessId] = $p }
foreach ($root in @(%s)) {
  $stack = @($root); $cpu = 0; $mem = 0; $n = 0
  while ($stack.Count) { $id = $stack[0]; $stack = @($stack | Select-Object -Skip 1)
    $p = $byId[$id]; if (-not $p) { continue }
    $cpu += ($p.KernelModeTime + $p.UserModeTime) / 1e7; $mem += $p.PrivatePageCount; $n++
    # A child older than its parent is an orphan whose real parent died and whose PID got reused
    foreach ($k in $kids[$id]) { if ($k.ProcessId -ne $id -and $k.CreationDate -ge $p.CreationDate) { $stack += [int]$k.ProcessId } } }
  "$root $cpu $mem $n"
}""" % ",".join(map(str, pids))
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    res = {}
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) == 4:
            res[int(p[0])] = (float(p[1]), int(float(p[2])), int(p[3]))
    return res


def proc_stats(pids):
    pids = [p for p in pids if p]
    if not pids:
        return {}
    cmd = ("Get-Process -Id " + ",".join(map(str, pids)) + " -ErrorAction SilentlyContinue | ForEach-Object {"
           " \"$($_.Id) $($_.ProcessName) $($_.TotalProcessorTime.TotalSeconds) $($_.WorkingSet64)\" }")
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    res = {}
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) == 4:
            res[int(p[0])] = (p[1], float(p[2]), int(p[3]))
    return res


def byond_webview_root():
    """DreamSeeker's browser controls run in a WebView2 tree owned by byond.exe, not under dreamseeker.exe"""
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" | Where-Object { "
           "$_.CommandLine -notmatch '--type=' -and $_.CommandLine -like '*BYOND*cache*WebView2*' } | "
           "Select-Object -First 1 -ExpandProperty ProcessId")
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return int(r.stdout.strip()) if r.stdout.strip().isdigit() else None


def cmd_perf(a):
    secs = float(a[0]) if a else 30
    s = load()
    pids = [s.get(PREFIX + k) for k in ("od_server", "od_client", "by_server", "by_client") if alive(s.get(PREFIX + k))]
    log = str(OUT / "scene_od_client.log") if PREFIX else s.get("od_client_log")
    log_start = Path(log).stat().st_size if log and Path(log).exists() else 0
    wv = byond_webview_root() if alive(s.get(PREFIX + "by_client")) else None
    tree_pids = pids + ([wv] if wv else [])
    m0, p0, tr0, t0 = metrics(), proc_stats(pids), tree_stats(tree_pids), time.time()
    time.sleep(secs)
    m1, p1, tr1, dt = metrics(), proc_stats(pids), tree_stats(tree_pids), time.time() - t0
    print(f"window {dt:.1f}s")
    for pid, (n, cpu, ws) in p1.items():
        if pid in p0:
            line = f"  {n:16} pid={pid:6} cpu={100 * (cpu - p0[pid][1]) / dt:6.1f}% of a core  ram={ws / 2**20:7.0f} MiB"
            if pid in tr0 and pid in tr1 and tr1[pid][2] > 1:
                line += (f"   | with {tr1[pid][2] - 1} child procs: cpu={100 * (tr1[pid][0] - tr0[pid][0]) / dt:6.1f}%"
                         f"  private={tr1[pid][1] / 2**20:7.0f} MiB")
            print(line)
    if wv and wv in tr0 and wv in tr1:
        print(f"  BYOND WebView2 tree (DreamSeeker's browsers, {tr1[wv][2]} procs): "
              f"cpu={100 * (tr1[wv][0] - tr0[wv][0]) / dt:6.1f}%  private={tr1[wv][1] / 2**20:7.0f} MiB")
    if log and log_start:
        with open(log, encoding="utf-8", errors="replace") as f:
            f.seek(log_start)
            perf = [l for l in f.read().splitlines() if "RENDERPERF" in l]
        if perf:
            print("  od-client last RENDERPERF:", perf[-1].split("RENDERPERF", 1)[1].strip(), f"({len(perf)} samples)")
    rows = []
    for k, v in m1.items():
        if k.split("{")[0].endswith("_sum") and v - m0.get(k, 0) > 0:
            ck = k.replace("_sum", "_count", 1)
            rows.append((v - m0.get(k, 0), m1.get(ck, 0) - m0.get(ck, 0), k))
    for d, c, k in sorted(rows, reverse=True)[:15]:
        print(f"  {d / dt * 100:6.2f}% n={int(c):7d} mean={1000 * d / max(c, 1):8.3f}ms {k}")
    for k in ("dotnet_gc_allocated_bytes_total", "system_runtime_total_pause_time_by_gc_total"):
        if k in m1:
            print(f"  {k}: {(m1[k] - m0.get(k, 0)) / dt:,.0f}/s")


def cmd_threads(a):
    """threads <od-server|od-client|by-server|by-client> [seconds]: exact per-thread CPU with thread names"""
    which, secs = a[0], (a[1] if len(a) > 1 else "20")
    pid = load().get(PREFIX + which.replace("-", "_"))
    if not alive(pid):
        raise SystemExit(f"{which} not running")
    r = subprocess.run(["pwsh", "-NoProfile", "-File", str(HERE / "threads.ps1"), "-ProcessId", str(pid), "-Seconds", secs],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())


def cmd_trace(a):
    which, secs = a[0], int(a[1]) if len(a) > 1 else 20
    pid = load().get(which.replace("-", "_"))
    if not alive(pid):
        raise SystemExit(f"{which} not running")
    OUT.mkdir(exist_ok=True)
    base = OUT / f"{which}_{int(time.time())}.nettrace"
    subprocess.run(["dotnet-trace", "collect", "-p", str(pid), "--profile", "dotnet-sampled-thread-time",
                    "--duration", f"00:00:00:{secs:02d}", "--format", "speedscope", "-o", str(base)],
                   check=True, capture_output=True)
    ss = base.with_suffix(".speedscope.json")
    subprocess.run([sys.executable, "-I", str(HERE / "speedscope.py"), str(ss), "auto", "40"])


def cmd_scene(a):
    """scene <name> [W H] [--wait SECS] [--od-only]: compile scenes/<name>/scene.dme with both compilers,
    boot both engines on the scene ports, size both windows the same and capture them side by side."""
    global PREFIX
    PREFIX = "scene_"
    a = list(a)
    name = a[0]
    rest = [x for x in a[1:] if not x.startswith("--")]
    w, h = (int(rest[0]), int(rest[1])) if len(rest) >= 2 else (900, 700)
    settle = int(a[a.index("--wait") + 1]) if "--wait" in a else 6
    od_only = "--od-only" in a
    by_only = "--by-only" in a
    defs = [x for i, x in enumerate(a) if i > 0 and a[i - 1] == "-D"]
    cv = [a[i + 1] for i, x in enumerate(a) if x == "--cvar"]
    rest = [x for x in rest if x not in defs and x != "-D" and x not in cv]
    w, h = (int(rest[0]), int(rest[1])) if len(rest) >= 2 else (900, 700)
    d = SCENES / name
    dme = d / "scene.dme"
    if not dme.exists():
        raise SystemExit(f"no {dme}")
    cmd_stop(["scene"])
    OUT.mkdir(exist_ok=True)

    if not by_only:
        r = subprocess.run([str(OD / "bin/DMCompiler/DMCompiler.exe"), "--suppress-unimplemented",
                            *sum((["--define", x] for x in defs), []), "scene.dme"],
                           cwd=d, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("OD compile failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])
    if not od_only:
        r = subprocess.run([str(BYOND / "dm.exe"), *[f"-D{x}" for x in defs], "scene.dme"], cwd=d, capture_output=True, text=True)
        if r.returncode or not re.search(r"\b0 errors", r.stdout):
            raise SystemExit("BYOND compile failed:\n" + r.stdout[-3000:])

    s = load()
    if by_only:
        s["scene_by_server"] = spawn([str(BYOND / "dreamdaemon.exe"), "scene.dmb", str(SCENE_BY_PORT), "-trusted", "-invisible"],
                                     OUT / "scene_by_server.log", d)
        save(s)
        time.sleep(3)
        s["scene_by_client"] = spawn([str(BYOND / "dreamseeker.exe"), f"byond://127.0.0.1:{SCENE_BY_PORT}"], OUT / "scene_by_client.log", d)
        save(s)
        for e, pid in engines("by"):
            for _ in range(60):
                try:
                    print(e, ps("place", pid, "-W", w, "-H", h, "-X", 0, "-Y", 0))
                    break
                except SystemExit:
                    time.sleep(1)
        time.sleep(settle)
        cmd_shot([name + "".join("_" + x for x in defs), "by"])
        return
    s["scene_od_server"] = spawn([str(OD / "bin/Content.Server/OpenDreamServer.exe"),
                                  "--cvar", f"net.port={SCENE_OD_PORT}", "--cvar", f"opendream.topic_port={SCENE_OD_TOPIC}",
                                  "--cvar", f"opendream.json_path={d / 'scene.json'}"], OUT / "scene_od_server.log", d)
    if not od_only:
        s["scene_by_server"] = spawn([str(BYOND / "dreamdaemon.exe"), "scene.dmb", str(SCENE_BY_PORT), "-trusted", "-invisible"],
                                     OUT / "scene_by_server.log", d)
    save(s)
    wait_log(OUT / "scene_od_server.log", r"-> Ready", 120, s["scene_od_server"])

    s["scene_od_client"] = spawn([str(OD / "bin/Content.Client/OpenDreamClient.exe"), "--connect", "--connect-address",
                                  f"udp://127.0.0.1:{SCENE_OD_PORT}", "--cvar", "opendream.debug_renderperf=true", *cvars(a)],
                                 OUT / "scene_od_client.log", d)
    if not od_only:
        s["scene_by_client"] = spawn([str(BYOND / "dreamseeker.exe"), f"byond://127.0.0.1:{SCENE_BY_PORT}"], OUT / "scene_by_client.log", d)
    save(s)
    wait_log(OUT / "scene_od_client.log", "RENDERPERF", 180, s["scene_od_client"])
    for e, pid in engines("od" if od_only else "both"):
        for _ in range(60):
            try:
                print(e, ps("place", pid, "-W", w, "-H", h, "-X", 0 if e == "od" else w, "-Y", 0))
                break
            except SystemExit:
                time.sleep(1)
    time.sleep(settle)
    cmd_shot([name + "".join("_" + x for x in defs), "od" if od_only else "both"])
    errs = [l for l in (OUT / "scene_od_client.log").read_text(encoding="utf-8", errors="replace").splitlines() if "[ERRO]" in l]
    errs += [l for l in (OUT / "scene_od_server.log").read_text(encoding="utf-8", errors="replace").splitlines() if "[ERRO]" in l or "Exception" in l]
    if errs:
        print("OD errors:\n  " + "\n  ".join(errs[:15]))


def cmd_bench(a):
    """bench [scene=bench]: run a results-writing scene headless on each engine in turn (never both at once,
    so neither steals CPU from the other) and print per-operation costs side by side."""
    name = a[0] if a else "bench"
    d = SCENES / name
    cmd_stop(["scene"])
    for f in d.glob("results_*.txt"):
        f.unlink()
    r = subprocess.run([str(OD / "bin/DMCompiler/DMCompiler.exe"), "--suppress-unimplemented", "scene.dme"], cwd=d, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("OD compile failed:\n" + r.stdout[-3000:])
    r = subprocess.run([str(BYOND / "dm.exe"), "scene.dme"], cwd=d, capture_output=True, text=True)
    if not re.search(r"\b0 errors", r.stdout):
        raise SystemExit("BYOND compile failed:\n" + r.stdout[-3000:])

    runs = {
        "byond": ([str(BYOND / "dreamdaemon.exe"), "scene.dmb", str(SCENE_BY_PORT), "-trusted", "-invisible"], "scene_by_server"),
        "od": ([str(OD / "bin/Content.Server/OpenDreamServer.exe"), "--cvar", f"net.port={SCENE_OD_PORT}",
                "--cvar", f"opendream.topic_port={SCENE_OD_TOPIC}", "--cvar", f"opendream.json_path={d / 'scene.json'}"], "scene_od_server"),
    }
    for engine, (args, key) in runs.items():
        pid = spawn(args, OUT / f"bench_{engine}.log", d)
        s = load(); s[key] = pid; save(s)
        t0 = time.time()
        while not (d / f"results_{engine}.txt").exists():
            if time.time() - t0 > 600 or not alive(pid):
                raise SystemExit(f"{engine} produced no results; see {OUT / f'bench_{engine}.log'}")
            time.sleep(1)
        time.sleep(1)
        cmd_stop(["scene"])
        print(f"{engine}: done in {time.time() - t0:.0f}s")

    res = {e: dict(l.split("\t") for l in (d / f"results_{e}.txt").read_text().splitlines() if "\t" in l) for e in runs}
    print(f"\n{'operation':28} {'BYOND us':>10} {'OD us':>10} {'OD/BYOND':>9}")
    for op, by in res["byond"].items():
        od = res["od"].get(op)
        b, o = float(by), float(od) if od else float("nan")
        ratio = o / b if b else float("inf")
        flag = "  <-- slower" if ratio > 2 else ""
        print(f"{op:28} {b:10.3f} {o:10.3f} {ratio:9.2f}{flag}")


def cmd_parity(a):
    """parity <suite> [--od-only] [--build-only] ...: builtin parity suite, see parity/README.md"""
    subprocess.run([sys.executable, "-I", str(HERE / "parity" / "run.py"), *a])


def cmd_stop(a):
    which = a[0] if a else "all"
    s = load()
    keys = {"od": ["od_client", "od_server"], "by": ["by_client", "by_server"],
            "scene": ["scene_od_client", "scene_od_server", "scene_by_client", "scene_by_server"],
            "od-client": ["od_client"], "od-server": ["od_server"], "by-client": ["by_client"], "by-server": ["by_server"]}
    for k in keys.get(which, keys["od"] + keys["by"]):
        if alive(s.get(k)):
            subprocess.run(["taskkill", "/PID", str(s[k]), "/F"], capture_output=True)
            print(f"killed {k} {s[k]}")
        s.pop(k, None)
    save(s)


def cmd_status(a):
    for k, v in load().items():
        print(f"{k:16} {v}  {'(alive)' if isinstance(v, int) and alive(v) else ''}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    argv = sys.argv[2:]
    if "--scene" in argv:
        argv.remove("--scene")
        PREFIX = "scene_"
    if "--title" in argv:
        i = argv.index("--title")
        TITLE = argv[i + 1]
        del argv[i:i + 2]
    fn = globals().get("cmd_" + sys.argv[1].replace("-", "_"))
    if not fn:
        raise SystemExit(f"unknown command {sys.argv[1]}\n{__doc__}")
    fn(argv)
