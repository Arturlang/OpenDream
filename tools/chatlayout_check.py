#!/usr/bin/env python3
"""Verify the tgui-panel chat layout in a running OpenDream client.

The chat browser (browseroutput) has repeatedly ended up mis-sized or offset
inside its pane: tgui-panel wingets the legacy output control's size and
winsets it onto browseroutput at load, and any staleness in that round-trip
gets baked into the control's anchor offsets (see "Report live control sizes
from winget"). This script asserts, from the outside, that the layout came out
right:

  1. browseroutput sits at pos 0,0 inside the output_browser pane
  2. browseroutput's size matches the output_browser pane's size
  3. the CEF page's innerWidth/innerHeight match browseroutput's size
     (i.e. the browser bitmap actually fills the control)
  4. statbrowser's page width matches its control too (control sample)

Requires the client to be running with CEF remote debugging on port 9222
(OpenDream enables this by default in dev builds) and the game to be past
interface load. Exits 0 on PASS, 1 on FAIL, 2 if the client/pages are missing.

Usage: python tools/chatlayout_check.py [--cdp-port 9222] [--tolerance 4]
"""

import argparse
import asyncio
import json
import sys
import urllib.request

try:
    import websockets
except ImportError:
    print("FAIL-SETUP: pip install websockets")
    sys.exit(2)


async def evaluate(ws, counter, expression):
    counter[0] += 1
    msg_id = counter[0]
    await ws.send(json.dumps({
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
    }))
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == msg_id:
            result = message.get("result", {}).get("result", {})
            if message.get("result", {}).get("exceptionDetails"):
                raise RuntimeError(message["result"]["exceptionDetails"].get("text", "JS exception"))
            return result.get("value")


async def winget(ws, counter, control):
    raw = await evaluate(
        ws, counter,
        f"Byond.winget('{control}').then(r => JSON.stringify(r)).catch(e => 'ERR: ' + e)")
    if raw is None or raw.startswith("ERR"):
        raise RuntimeError(f"winget {control} failed: {raw}")
    return json.loads(raw)


def parse_pair(value):
    for sep in ("x", ","):
        if sep in value:
            a, b = value.split(sep, 1)
            return int(float(a)), int(float(b))
    raise ValueError(value)


async def run(cdp_port, tolerance):
    try:
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5))
    except OSError as error:
        print(f"FAIL-SETUP: no CDP endpoint on port {cdp_port}: {error}")
        return 2

    failures = []

    async def check_page(url_part, control):
        target = next((p for p in pages if url_part in p.get("url", "")), None)
        if target is None:
            failures.append(f"{control}: page {url_part} not loaded")
            return None
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
            counter = [0]
            inner = json.loads(await evaluate(
                ws, counter, "JSON.stringify([window.innerWidth, window.innerHeight])"))
            info = await winget(ws, counter, control)
            return ws, counter, inner, info, target

    # The chat page carries the winget bridge; do all queries through it.
    target = next((p for p in pages if "browseroutput" in p.get("url", "")), None)
    if target is None:
        print("FAIL-SETUP: browseroutput page not loaded (client not in game yet?)")
        return 2

    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
        counter = [0]

        chat_inner = json.loads(await evaluate(
            ws, counter, "JSON.stringify([window.innerWidth, window.innerHeight])"))
        browser = await winget(ws, counter, "browseroutput")
        pane = await winget(ws, counter, "output_browser")

        browser_pos = parse_pair(browser["pos"])
        browser_size = parse_pair(browser["size"])
        pane_size = parse_pair(pane["size"])

        def expect(label, actual, wanted):
            if abs(actual[0] - wanted[0]) > tolerance or abs(actual[1] - wanted[1]) > tolerance:
                failures.append(f"{label}: {actual} != {wanted} (tolerance {tolerance})")

        expect("browseroutput.pos", browser_pos, (0, 0))
        expect("browseroutput.size vs pane", browser_size, pane_size)
        expect("chat page inner size vs control", tuple(chat_inner), browser_size)

        print(f"chat: pane={pane_size} control={browser_size} at {browser_pos} page={tuple(chat_inner)}")

    stat = next((p for p in pages if "statbrowser" in p.get("url", "")), None)
    if stat is not None:
        async with websockets.connect(stat["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
            counter = [0]
            stat_inner = json.loads(await evaluate(
                ws, counter, "JSON.stringify([window.innerWidth, window.innerHeight])"))
            stat_info = await winget(ws, counter, "statbrowser")
            stat_size = parse_pair(stat_info["size"])
            if abs(stat_inner[0] - stat_size[0]) > tolerance or abs(stat_inner[1] - stat_size[1]) > tolerance:
                failures.append(f"statbrowser page inner size {tuple(stat_inner)} != control {stat_size}")
            print(f"stat: control={stat_size} page={tuple(stat_inner)}")

    if failures:
        print("FAIL:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("PASS")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-port", type=int, default=9222)
    parser.add_argument("--tolerance", type=int, default=4)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(run(args.cdp_port, args.tolerance)))


if __name__ == "__main__":
    main()
