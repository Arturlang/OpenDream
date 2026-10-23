# OpenDream vs BYOND self-test harness

Everything runs from this folder with `python -I odh.py <command>`; `python -I odh.py --help` lists all
commands. State (PIDs, logs) lives in `state.json`, output (logs, screenshots, traces) in `out/`.
Both are git-ignored.

## Setup

- Windows, Python 3, PowerShell 7 (`pwsh`), BYOND installed (`BYOND_BIN` overrides
  `C:\Program Files (x86)\BYOND\bin`). `OD_ROOT` overrides the OpenDream checkout (default: this repo).
- `trace`: `dotnet tool install -g dotnet-trace` (also handy: `dotnet-counters`, `dotnet-dump`).
- `tracysum.py`: build Tracy 0.13.1's `csvexport` into `tracy-0.13.1/` here (git-ignored).
- `alloctop/`: allocation summary from a `.nettrace`; `dotnet run --project alloctop -- <trace>`.

## Layout

| Path | What |
|---|---|
| `odh.py` | the harness CLI |
| `win32.ps1`, `threads.ps1` | window placement, screenshots, guarded input, per-thread CPU |
| `mkdmi.py`, `dmiview.py` | make solid-colour DMIs, dump a DMI's states |
| `speedscope.py`, `tracysum.py`, `alloctop/` | summarise dotnet-trace, Tracy and allocation captures |
| `scenes/<name>/` | minimal repro projects for both engines |
| `parity/` | builtin parity suite against saved BYOND results (see its README) |
| `scripts/` | one-off loops kept for reference (helmet capture, soak, jump tracking) |

## Typical loops

Full game, side by side:

    python -I odh.py od-server E:\GithubRepos\TerraGov-Marine-Corps --json tgmc.json
    python -I odh.py od-client E:\GithubRepos\TerraGov-Marine-Corps [--skin-dump] [--cvar k=v]
    python -I odh.py by-server E:\GithubRepos\TerraGov-Marine-Corps tgmc.dmb
    python -I odh.py by-client
    python -I odh.py place both 1600 900        # identical outer window size
    python -I odh.py shot lobby                 # out/lobby.png = OD left, BYOND right
    python -I odh.py click od 112 428           # client-area coords
    python -I odh.py perf 30                    # CPU/RAM of all four, OD FPS, server tick metrics
    python -I odh.py trace od-client 20         # dotnet-trace + game-thread hot path

Minimal repro scene (the fastest way to settle "is it OD or the game?"):

    python -I odh.py scene parallax 900 700 [-D DEFINE] [--cvar k=v] [--od-only]

BYOND only (no OpenDream build), and a short animated capture of a running scene:

    python -I odh.py scene fog 900 720 --by-only [-D TILE_STATIC]
    python -I odh.py burst fog_motion 30 150 by --scene      # out/scene_fog_motion.gif

`scenes/fog` is the TGMC camera-fog prototype (soft reveal disks masked by server LOS markers; see its scene.dme).

Scenes live in `scenes/<name>/scene.dme`, are compiled by both compilers, run on their own ports
(OD 26410, BYOND 26010) so a game can stay up, and land in `out/scene_<name>[_DEFINES].png`.
Add `--scene` to shot/click/perf/windows to act on the scene engines. `mkdmi.py` makes solid-colour
DMIs so scenes need no game assets.

## Things that bite

- **Clicks are real mouse input** (SDL ignores posted button messages). `click` hit-tests the target
  pixel first and refuses if another app's window covers it, so it can never click into something else.
- Popups: `windows by` lists them; `--title "<empty>"` targets BYOND's untitled tgui popups.
- A client-only reconnect to a running OD server leaves a half-initialised session; restart both.
- Git Bash rewrites `/paths` in arguments; launching through this script avoids that.
- GPU-bound numbers are meaningless while another game is using the GPU or covering the window
  (occluded windows are throttled). CPU numbers are still fine.
- `skin` reads the OD skin dump (`od-client --skin-dump`); `tree by` gives BYOND's real control
  geometry, since DreamSeeker controls are Win32 child windows.
