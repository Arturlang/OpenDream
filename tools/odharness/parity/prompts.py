"""Prompt runner: opens each prompt case on both clients, records the prompt as shown, answers it the same way
on both, and diffs the results.

    python -I prompts.py <suite> [--only N,M]

BYOND prompts are Win32 dialogs, read and answered in-process with win32dlg.py. OD prompts go through the client's
prompt test hook (cvar opendream.test_prompt_dir). Neither needs keyboard focus. Both engines run each case at the
same time in two threads.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import diff, gen, procs, run, win32dlg  # noqa: E402
from live import Live  # noqa: E402

HOOK_DIR = "parity_prompts"
HOOK_PATH = Path(os.environ["APPDATA"]) / "Space Station 14" / "data" / HOOK_DIR
UI_KEYS = ("title", "message", "buttons", "default_button", "text", "items", "selected")
WAIT = 6       # seconds for a prompt to open
RESULT = 4     # seconds for the result after the answer
POLL = 0.05


def wait_for(fn, timeout, poll=POLL):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v:
            return v
        time.sleep(poll)
    return None


def ui_line(d):
    return "j:" + json.dumps({k: d.get(k) for k in UI_KEYS}, ensure_ascii=False, sort_keys=True)


def od_prompts():
    try:
        return json.loads((HOOK_PATH / "prompts.json").read_text(encoding="utf-8"))["prompts"]
    except (OSError, ValueError, KeyError):
        return []


def clear_dialog(h):
    """Cancels dialog h, or presses its default button, until it closes. A close message alone can leave it open."""
    for _ in range(3):
        d = win32dlg.describe(h)
        if not d:
            return True
        if "Cancel" in d["buttons"]:
            win32dlg.act(h, "press", "Cancel")
        else:
            # BYOND re-opens a list prompt when OK is pressed with nothing selected
            if d.get("items"):
                win32dlg.act(h, "select", 0)
            win32dlg.act(h, "submit")
        if wait_for(lambda: not win32dlg.is_open(h), 1):
            return True
    return False


def clear_all_byond():
    """Closes every open BYOND prompt. Called before a case is asked, so all of them are leftovers.
    A cleared prompt can re-open in a new window, so repeat a few times."""
    pid = procs.pid("by_client")
    for _ in range(5):
        left = win32dlg.dialogs(pid)
        if not left:
            return
        for h in left:
            clear_dialog(h)
        time.sleep(0.2)


def byond_case(L, c, seen):
    """One case on BYOND. seen holds the window handles of earlier dialogs. Every action targets this case's dialog."""
    out, pid, cid = {}, procs.pid("by_client"), c["id"]
    got = lambda: cid in L.results("byond")
    found = wait_for(lambda: ("dlg", win32dlg.find(pid, seen)) if win32dlg.find(pid, seen) else ("done", 0) if got() else None, WAIT)
    h = found[1] if found and found[0] == "dlg" else None
    d = win32dlg.describe(h)
    out[cid + ":ui"] = ui_line(d) if d else "NO_PROMPT"
    if h:
        seen.add(h)
        status = "ok"
        for a in c["answer"]:
            r = win32dlg.act(h, a[0], a[1] if len(a) > 1 else "")
            if r.startswith("failed") or r == "no dialog":
                status = f"{r} at {list(a)}"
                break
            time.sleep(POLL)
        if status != "ok":
            # The answer cannot be given here; free BYOND now (it shows one prompt at a time) and record what that gives
            clear_dialog(h)
        out[cid + ":answer"] = status
    if not wait_for(got, RESULT):
        out[cid] = "NO_RESULT"
    # A dialog that stays open (a num prompt that refused the text, an ignored close) would block the next case
    if h and not wait_for(lambda: not win32dlg.is_open(h), 1):
        out[cid + ":answer"] = out.get(cid + ":answer", "") + " STUCK"
        clear_dialog(h)
    return out


def od_case(L, c, state):
    """One case on OD. state["seen"] is the highest hook prompt id handled so far."""
    out, cid = {}, c["id"]
    got = lambda: cid in L.results("od")
    p = wait_for(lambda: [x for x in od_prompts() if x["id"] > state["seen"]] or got(), WAIT)
    if isinstance(p, list):
        p = p[0]
        state["seen"] = p["id"]
        out[cid + ":ui"] = ui_line(p)
        lines = "".join(f"{p['id']}\t{a[0]}\t{a[1] if len(a) > 1 else ''}\n" for a in c["answer"])
        (HOOK_PATH / "answer.txt").write_text(lines, encoding="utf-8")
        taken = wait_for(lambda: not (HOOK_PATH / "answer.txt").exists(), 3)
        out[cid + ":answer"] = "ok" if taken else "hook did not take the answer"
    else:
        out[cid + ":ui"] = "NO_PROMPT"
    if not wait_for(got, RESULT):
        out[cid] = "NO_RESULT"
    return out


def main(a):
    suite = a[0]
    HOOK_PATH.mkdir(parents=True, exist_ok=True)
    for f in HOOK_PATH.glob("*"):
        f.unlink()
    run.build(suite)
    cases = json.loads((gen.BUILD / suite / "prompt_cases.json").read_text(encoding="utf-8"))
    only = [int(x) for x in a[a.index("--only") + 1].split(",")] if "--only" in a else range(len(cases))
    extra = {"byond": {}, "od": {}}
    t0 = time.time()
    with Live(suite, od_client_cvars=[f"opendream.test_prompt_dir=/{HOOK_DIR}"]) as L, ThreadPoolExecutor(2) as pool:
        seen_by, od_state = set(), {"seen": 0}
        for k in only:
            c = cases[k]
            clear_all_byond()
            seen_by.update(win32dlg.dialogs(procs.pid("by_client")))
            try:
                L.cmd_all(cmd="ask", i=k)
            except OSError as ex:
                # An engine went away (crash, or another process stopped it). Keep what we have.
                print(f"{k}: engine down ({ex}); stopping with partial results", flush=True)
                for e in L.engines:
                    extra[e]["#ENGINE_DOWN"] = f"at case {k}"
                break
            tc = time.time()
            fb, fo = pool.submit(byond_case, L, c, seen_by), pool.submit(od_case, L, c, od_state)
            rb, ro = fb.result(), fo.result()
            extra["byond"].update(rb)
            extra["od"].update(ro)
            if rb.get(c["id"] + ":ui") == "NO_PROMPT" and rb.get(c["id"]) == "NO_RESULT":
                # BYOND shows one prompt at a time: a prompt with no window leaves the client blocked for good
                ok = L.restart_byond_client()
                extra["byond"][c["id"] + ":answer"] = "no window; client restarted" if ok else "no window; restart failed"
                seen_by.clear()
            flags = " ".join(f"{e}:{v[:9]}" for e, r in (("by", rb), ("od", ro)) for kk, v in r.items()
                             if v in ("NO_PROMPT", "NO_RESULT") or "STUCK" in v or v.startswith("failed") or "hook did" in v)
            print(f"{k}: {c['name']}  {time.time() - tc:.1f}s {flags}", flush=True)
        res = {e: {**L.results(e), **{k: v for k, v in extra[e].items() if k not in L.results(e)}} for e in L.engines}
    print(f"{len(only)} cases in {time.time() - t0:.0f}s", flush=True)
    gdir = run.GOLDEN / f"byond-{run.byond_version()}"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / f"{suite}.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["byond"].items()), encoding="utf-8")
    (gdir / f"{suite}.hash").write_text(run.case_hash(suite))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{suite}_od.txt").write_text("".join(f"{k}\t{v}\n" for k, v in res["od"].items()), encoding="utf-8")
    diff.main([suite])


if __name__ == "__main__":
    main(sys.argv[1:])
