# Builtin parity suite

Compares what OpenDream's builtins return against BYOND's, case by case.

    python -I run.py <suite>                 # generate, compile, run BYOND then OD headless, diff
    python -I run.py <suite> --od-only       # reuse the saved BYOND golden (only if the cases are unchanged)
    python -I run.py <suite> --build-only    # generate + compile both engines, run nothing
    python -I diff.py <suite> [--proc NAME] [--show N] [--strict-errors]
    python -I gen.py --list                  # suites and case counts
    python -I ../odh.py parity <suite> ...   # same as run.py

Engines run one at a time on the harness's own ports (`procs.py`: OD 26420/26421, BYOND 26020). The
harness keeps its PIDs in `state.json` and stops only those, so `odh.py` work and other agents' engines
are safe. A run of a few thousand cases takes seconds. Cases that hung BYOND in the last golden are
skipped at once on later runs (BYOND does not change). OD always runs every case.

## Layout

| Path | What |
|---|---|
| `lib/parity.dm` | DM runtime: `parity_canon()` value printing, result file, skip handling |
| `gen.py` | specs -> `build/<suite>/<engine>/` DM projects + `manifest.tsv` |
| `pools.py` | shared input values (DM source strings) |
| `specs/<suite>/*.py` | case definitions; each module has `build(s)` |
| `golden/byond-<ver>/<suite>.txt` | BYOND results (+ `.hash` of the cases they came from) |
| `results/<suite>_od.txt` | latest OD results |
| `known.tsv` | accepted differences: `<glob on case id or proc>\t<reason>` |
| `../out/parity_<suite>.txt` | full diff report |

## Writing specs

```python
from pools import TEXT, NUM, POS, OTHER, ANY
from gen import dm_str

def build(s):
    # Every combination for <= 2 arguments, all-pairs beyond; each arg count from min_args up
    s.sweep("copytext", [TEXT + OTHER, POS, POS], min_args=1)
    # One hand-picked expression
    s.case("copytext", 'copytext("abc", 2, 3)')
    # Statements first, then the recorded result (side effects)
    s.body("splittext", ['var/list/L = splittext("a,b", ",")', 'L += "c"'], "L")
    # Custom call shape: fmt gets the DM source of each argument
    s.sweep("text2num", [TEXT], fmt=lambda t: f"text2num({t}, 16)")
```

Suite-level hooks:

```python
    s.define("PARITY_MAXX", 20)      # also PARITY_MAXY/MAXZ (10/10/1), PARITY_VIEW (5), PARITY_ICON_SIZE (32)
    s.dm("/obj/geo_wall\n\tdensity = 1\n\n/proc/geo_helper(x)\n\treturn x")   # helper types/procs (defs.dm)
    s.resource("data/x.json", some_path)                              # extra file in the build folder
```

- Every build gets the DMI fixtures from `fixtures/` (made by `fixtures.py`, every pixel known):
  `test.dmi` 32x32 with states `solid grad alpha half checker asym dirs4 dirs8 anim anim4 rewind moving
  "" empty`; `small.dmi` 16x16 (`solid grad`); `rect.dmi` 32x16 (`wide`). `asym` has no symmetry, so
  flips and turns show up. `dirs4`/`dirs8` are one colour per dir; `anim` is red/green/blue frames.
- Atoms a case creates must go through `parity_track(new /obj(locate(1, 1, 1)))`; they are deleted
  after the case. Don't change turfs or areas unless you change them back in the same case.
- Icons print as `i:WxH[state:hash, ...]`: the hash covers the first frame of the first dir only. For
  deeper checks use `parity_icon_hash(I, state, dir, frame)` or `parity_icon_pixels(I, state, dir, frame)`.
- Names in `s.dm()` code must start with the spec's name (`geo_`, `mov_`, ...) so specs don't clash.
- Pool entries are DM source. Build text literals with `dm_str()`, which escapes `\ " [ ]`.
- `PINF`, `NINF`, `NAN` are globals in `lib/parity.dm`.
- The case id is `proc#hash(code)`, so changing a case's code gives it a new id; the rest keep theirs.
- Keep each case independent: no shared state between cases.
- Don't call things that block or need a client (`input`, `alert`, `sleep`, `shell`, `world.Export`).

## How values are printed

`null`, `n:<display>~<12 digits>`, `t:"<escaped>"`, `p:/path`, `L(len)[item, key=value]`, `f:file`,
`i:WxH[...]` (icon), `m:[a, b, c, d, e, f]` (matrix), `r:index= next= match= group=` (regex),
`v:(x, y, z)` (vector), `px:(x, y, z)` (pixloc), `e:<name>` (exception), `a:/type@x,y,z "name"` (atoms;
areas without coordinates), `d:/type` (other datums). Control characters in text print as `\xNN`. Runtime errors print as `ERR <message>`.

Special results:
- `COMPILE_ERROR`: the case did not compile on that engine (the runner maps the compiler's line
  numbers back to cases and regenerates with them stubbed out).
- `SKIP crash|hang|abort`: the case crashed the engine, produced nothing for `HANG_SECS` (8s), or
  wrote no line at all and took the rest of its chunk with it (an error escaping try/catch). The
  runner skips it and resumes after the cases that already have results, so this costs one engine
  restart, not a full rerun.
- `WRITE_FAILED len=.. len_char=..`: OD's text2file refused the value (half a UTF-16 surrogate pair).

The golden is reused by `--od-only` only while `cases.dm` and `parity.dm` are byte-identical.

## Live suites

Live suites need a client. `live.py` builds the suite, starts both servers and both clients (OD left,
BYOND right) and sends commands with world Topic, so no suite needs keyboard focus or clicks.

| Mode | Spec calls | Runner | Output |
|---|---|---|---|
| Render pages | `s.render()`, `s.cell(name, lines, solo=False, tol=None)` | `render.py <suite>` | `../out/render/<suite>/index.html` |
| Browser probes | `s.browser()`, `s.probe(name, js)`, `s.roundtrip(name, dm_lines)`, `s.link(name, query_js)` | `browser.py <suite>` | diff, as for other suites |
| Prompts | `s.prompts()`, `s.prompt(name, call, answer)` | `prompts.py <suite>` | diff, plus `<id>:ui` (the prompt as shown) |
| Skin | `s.skin(dmf_path, window=(W, H))`, then `s.case()`/`s.body()` | `skin.py <suite>` | diff, plus screenshots |

Skin suites:
- The suite's own `.dmf` replaces the generated skin. The cases run in order while the client is connected
  (`live_client`), so `winset`, `winget`, `winclone` and `winshow` act on a real skin.
- The client applies many `winset` changes a moment later. Put `sleep(1)` or `sleep(2)` before the `winget`.
- A case that hangs (15 s with no new result) is skipped, and both worlds restart to resume after it.

Render pages:
- A page is 7x5 cells of 3x3 tiles on a grey checker. The cell code runs with `T` = the centre turf.
- Use `parity_track()` for each atom a cell makes. The page change deletes them.
- Use `solo=True` for a cell that changes the whole view (plane masters, `client.color`, `client.screen`).
  Each page change resets `client.color`, `see_invisible` and the screen objects other than the markers.
- `render.py` finds the map by the magenta corner markers and checks the page code tile. Then it compares
  each cell. A cell passes when the share of pixels with a channel difference over 24 is under `tol[0]`
  and the mean difference is under `tol[1]` (default 2% and 3.0).

Browser probes:
- `s.probe`: `js` is the body of an async function. The return value is recorded as JSON.
- `s.roundtrip`: the DM lines run with `C` = the client and call `output(..., "probe:parity_recv")`.
  The page records the arguments it gets.
- `s.link`: the page opens `byond://?parity_link=<id>&<query>`. DM records `href_list` (`<id>:dm`) and
  `href` (`<id>:href`).
- `s.js(code)` adds shared JS helpers to the page once. `parity_current` holds the id of the running probe.
- Do not `output()` to `"probe"` without a function, or `output(null, "probe")`: that replaces the page.

Prompts:
- `call` opens one prompt for `C`, for example `'input(C, "Name?", "T", "def") as text|null'`.
- `answer` is a list of actions: `("text", s)`, `("select", index)`, `("press", label)`, `("submit",)`,
  `("close",)`.
- BYOND dialogs are read and answered with Win32 messages (`win32.ps1 dlg`, `dlgdo`). OD prompts use the
  client hook `opendream.test_prompt_dir` (files in `%APPDATA%\Space Station 14\data\parity_prompts`).
- OD prompts cannot be closed without an answer, so `("close",)` gives `NO_RESULT` on OD.
- A typed answer cannot hold a newline or a tab, because the OD hook reads one tab-separated action per line.
- A BYOND dialog that stays open after a case (`STUCK` in `<id>:answer`) is cancelled or closed before the next case.
- `as color` opens the Windows colour chooser on BYOND, so colour cases can only submit or cancel.
- BYOND shows one prompt at a time and ignores a close message on alerts. A prompt that cannot be answered
  blocks every later prompt. `input() as anything` with no list and no `null` is such a prompt (an empty list,
  OK only, and it opens again on every OK), so the suite leaves it out.
- The runner closes every open BYOND prompt before it asks the next case, and gives each action the window handle
  of the case's own dialog.

Self-checks: `smoke` (headless), `rsmoke`, `bsmoke`, `psmoke`, `ssmoke`.

## Findings

`findings/<suite>.md` holds triaged root causes (what BYOND does, what OD does, the OD source
location, a fix hint and an impact guess), each checked by an independent verifier.

## Diff buckets

`pass`, `fail`, `compile` (compiles on one engine only), `known`, `err-text` (both errored with
different messages; a pass unless `--strict-errors`), `precision` (same display, different digits).
Refs (`[0x...]`) are masked. Invalid UTF-8 bytes are kept as `\xNN`.

## Engine notes found while building this

- OD's compiler rejects the `"\r"` escape; BYOND accepts it.
- BYOND checks argument counts of builtins at compile time (`copytext(x)` is an error); OD does not.
- Both engines' text2file write `\n` as CRLF and append a line break of their own; the readers ignore blank lines.