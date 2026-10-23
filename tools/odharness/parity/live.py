"""Live suite driver: boots BYOND and OD with a client each, side by side (OD left), and drives the worlds
through world Topic. Used by the render pages and the browser/prompt suites.

    with Live("render") as L:          # builds, boots, waits for both clients
        L.cmd("byond", cmd="page", n=3)
        L.shot("od", "page3")           # PNG of the OD client window
"""
import subprocess, sys, time, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import gen, odh, procs, run  # noqa: E402
from topic import topic  # noqa: E402

ENGINES = ("od", "byond")
SHOTS = HERE.parent / "out" / "live"


class Live:
    def __init__(self, suite, engines=ENGINES, window=None, od_client_cvars=()):
        self.suite = suite
        self.engines = tuple(engines)
        self.window = window  # outer (W, H); default fits the skin
        self.od_client_cvars = list(od_client_cvars)

    # --- lifecycle -------------------------------------------------------------------------------------
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        procs.stop()
        run.build(self.suite)
        s = gen.load_suite(self.suite)
        ts = s.defines.get("PARITY_ICON_SIZE", 32)
        vw, vh = s.live_view
        self.map_px = (vw * ts, vh * ts)
        # Matches gen.live_skin(): browser suites put a 640x480 browser to the right of the map
        skin = (self.map_px[0] + 640, max(self.map_px[1], 480)) if s.browser_mode else self.map_px
        if not self.window:
            self.window = s.skin_window or (skin[0] + 60, skin[1] + 100)
        for e in self.engines:
            out = self.dir(e) / f"results_{e}.txt"
            if out.exists():
                out.unlink()
        for e in self.engines:
            d = self.dir(e)
            if e == "od":
                args = [str(odh.OD / "bin/Content.Server/OpenDreamServer.exe"), "--cvar", f"net.port={procs.OD_PORT}",
                        "--cvar", f"opendream.topic_port={procs.OD_TOPIC}", "--cvar", f"opendream.json_path={d / 'scene.json'}"]
                procs.remember("od_server", odh.spawn(args, odh.OUT / f"live_{self.suite}_od_server.log", d))
            else:
                args = [str(odh.BYOND / "dreamdaemon.exe"), "scene.dmb", str(procs.BY_PORT), "-trusted", "-invisible"]
                procs.remember("by_server", odh.spawn(args, odh.OUT / f"live_{self.suite}_by_server.log", d))
        for e in self.engines:
            self.wait_line(e, "#START", 120)
        for e in self.engines:
            d = self.dir(e)
            if e == "od":
                args = [str(odh.OD / "bin/Content.Client/OpenDreamClient.exe"), "--connect", "--connect-address",
                        f"udp://127.0.0.1:{procs.OD_PORT}"]
                for cv in self.od_client_cvars:
                    args += ["--cvar", cv]
                procs.remember("od_client", odh.spawn(args, odh.OUT / f"live_{self.suite}_od_client.log", d))
            else:
                procs.remember("by_client", odh.spawn([str(odh.BYOND / "dreamseeker.exe"), f"byond://127.0.0.1:{procs.BY_PORT}"],
                                                       odh.OUT / f"live_{self.suite}_by_client.log", d))
        for e in self.engines:
            self.wait_line(e, "#CLIENT", 180)
        self.place()

    def stop(self):
        for e in self.engines:
            try:
                self.cmd(e, cmd="quit")
            except Exception:
                pass
        time.sleep(1)
        procs.stop()

    def place(self):
        w, h = self.window
        for e in self.engines:
            pid = self.client_pid(e)
            for _ in range(60):
                try:
                    odh.ps("place", pid, "-W", w, "-H", h, "-X", 0 if e == "od" else w, "-Y", 0)
                    break
                except SystemExit:
                    time.sleep(1)

    def client_pid(self, engine):
        return procs.pid("od_client" if engine == "od" else "by_client")

    def restart_byond_client(self, timeout=60):
        """Starts a new DreamSeeker in place of the current one, for a client that a prompt left blocked."""
        f = self.dir("byond") / "results_byond.txt"
        count = lambda: f.read_bytes().decode("utf-8", "replace").count("#CLIENT") if f.exists() else 0
        before = count()
        old = self.client_pid("byond")
        if old and odh.alive(old):
            subprocess.run(["taskkill", "/PID", str(old), "/F"], capture_output=True)
        procs.remember("by_client", odh.spawn([str(odh.BYOND / "dreamseeker.exe"), f"byond://127.0.0.1:{procs.BY_PORT}"],
                                               odh.OUT / f"live_{self.suite}_by_client.log", self.dir("byond")))
        t0 = time.time()
        while count() <= before and time.time() - t0 < timeout:
            time.sleep(0.25)
        w, h = self.window
        for _ in range(20):
            try:
                odh.ps("place", self.client_pid("byond"), "-W", w, "-H", h, "-X", w, "-Y", 0)
                break
            except SystemExit:
                time.sleep(0.5)
        return count() > before

    # --- talking to the worlds -------------------------------------------------------------------------
    def dir(self, engine):
        return gen.BUILD / self.suite / engine

    def port(self, engine):
        return procs.OD_TOPIC if engine == "od" else procs.BY_PORT

    def cmd(self, engine, **params):
        return topic(self.port(engine), urllib.parse.urlencode({k: str(v) for k, v in params.items()}))

    def cmd_all(self, **params):
        return {e: self.cmd(e, **params) for e in self.engines}

    def results(self, engine):
        res, _ = run.read_results(self.dir(engine) / f"results_{engine}.txt")
        return res

    def wait_line(self, engine, prefix, timeout):
        f = self.dir(engine) / f"results_{engine}.txt"
        t0 = time.time()
        while time.time() - t0 < timeout:
            if f.exists() and any(l.startswith(prefix) for l in f.read_bytes().decode("utf-8", "replace").splitlines()):
                return
            time.sleep(0.5)
        raise SystemExit(f"{engine}: no {prefix} line after {timeout}s (see out/live_{self.suite}_*.log)")

    # --- screenshots -----------------------------------------------------------------------------------
    def shot(self, engine, name):
        SHOTS.mkdir(parents=True, exist_ok=True)
        pid = self.client_pid(engine)
        f = SHOTS / f"{self.suite}_{name}_{engine}.png"
        odh.ps("shot", pid, "-Out", f)
        return f
