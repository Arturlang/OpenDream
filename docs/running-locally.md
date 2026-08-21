# Running Bubberstation on OpenDream locally

A practical guide to the edit-build-test loop, optimised so you rebuild only
what changed. The VS Code extension works, but it needs an SS14 account and
does its own builds; everything below runs from a terminal with neither.

Paths assume `OpenDream/` and `Bubberstation/` are sibling checkouts.

## One-time prerequisites

- **`rust_g64.dll`** in the Bubberstation root. It is gitignored and must be the
  **64-bit** build — a 32-bit or mismatched one fails later as a mapgen runtime
  rather than a load error, so it looks like a content bug.
- **tgui built** (`bin/tgui-build.cmd`). Only needed again when you touch
  `tgui/`.
- **BYOND** (for side-by-side comparison only) at
  `C:\Program Files (x86)\BYOND\bin`.

## Rebuild only what you changed

This is where the time goes. Nothing here needs a full rebuild.

| Changed | Rebuild | Command |
|---|---|---|
| `Resources/**` — shaders, prototypes, skins | nothing, just restart the client | — |
| `.dm` / `.dmi` | DM only | DMCompiler, below |
| `OpenDreamClient` | client only, a running server keeps working | `./build.ps1 -Target client -KeepServer` |
| `OpenDreamRuntime` / `OpenDreamServer` | server only | `./build.ps1 -Target server` |
| `OpenDreamShared` | **both** — the serializer hash must match or clients fail to connect | `./build.ps1` |
| `RobustToolbox` | whichever side uses it (project references handle the rest) | `./build.ps1` |

`./build.ps1` skips restore and the Robust analyzers for speed, and frees build
locks first — a client or server still holding `bin/Content.*` is what turns a
build into a stalling MSB3021/MSB3027 or CS2012 failure. Run `./build.ps1 -Full`
before committing or after touching packages/csproj, so the analyzers actually
run.

`-KeepServer` protects a running server during a client-only build. Note that a
plain `-Target client` build **kills the running client** to free its locks, so
expect to relaunch it.

## Compile the DM side

Use the minimal defines. The full station takes ~65s to initialise;
`LOWMEMORYMODE` + `ABSOLUTE_MINIMUM` force `runtimestation_minimal` and cut that
to ~11-16s, which is the single biggest win in the loop.

```bash
cd Bubberstation
../OpenDream/bin/DMCompiler/DMCompiler.exe --suppress-unimplemented --define TESTING --define LOWMEMORYMODE --define ABSOLUTE_MINIMUM tgstation.dme
```

Drop `LOWMEMORYMODE`/`ABSOLUTE_MINIMUM` when you specifically need the real map.
Add `--define AUTO_OBSERVE` to skip the lobby entirely (see below).

## Run it

Two processes. No account, no auth prompt.

```bash
# server — from the Bubberstation directory
../OpenDream/bin/Content.Server/OpenDreamServer.exe --cvar net.port=26400 --cvar opendream.topic_port=26401 --cvar opendream.json_path="$PWD/tgstation.json"

# client — once the server logs "Runlevel changed from 2 to 4"
../OpenDream/bin/Content.Client/OpenDreamClient.exe --connect --connect-address "udp://127.0.0.1:26400"
```

The client lands in the **lobby**; nothing renders until you pick Observe or
join. Compiling with `--define AUTO_OBSERVE` makes it drop straight into the
world as an observer, which is what makes unattended screenshots possible. It
also dumps the server's per-turf lighting matrices to `lightdump-{od,by}.txt` -
useful for settling whether a discrepancy is the server's data or the renderer.

Add `--define AUTO_WALK` on top of that to have the observer pace north and
south forever. Motion artifacts are otherwise very hard to reproduce, and note
that **PrintWindow cannot capture them**: consecutive grabs return
byte-identical frames and then a partial one, so per-frame flicker measured from
screenshots is a capture artifact. Judge motion by eye, or instrument the
renderer.

## Gotchas that cost real time

- **Restarting only the client reconnects on the same ckey** and leaves a
  half-initialised session — the chat says "Reconnected" and lighting comes back
  wrong. It looks exactly like a rendering regression. Restart the server too.
- **Kill engines by PID, never by name.** `Get-Process dreamseeker | Stop-Process`
  also kills unrelated DreamSeeker instances you have open for other codebases.
- **Pick ports deliberately.** If a scene harness and a manually booted station
  share a port, DreamSeeker silently connects to the wrong server and you spend
  a while analysing the wrong game.
- **`icons/map_icons/` gets dirtied** by a server launch. Revert it before
  committing.

## Comparing against BYOND

For the same world under DreamSeeker:

```bash
cd Bubberstation
"/c/Program Files (x86)/BYOND/bin/dm.exe" -DTESTING -DLOWMEMORYMODE -DABSOLUTE_MINIMUM tgstation.dme
"/c/Program Files (x86)/BYOND/bin/dreamdaemon.exe" tgstation.dmb 25999 -trusted -invisible
"/c/Program Files (x86)/BYOND/bin/dreamseeker.exe" "byond://127.0.0.1:25999"
```

Note DreamDaemon's `world.log` goes to its own window, not stdout — write to a
`file()` from DM if you need machine-readable output from the BYOND side.

The `scratchpad/lightparity` harness automates all of this:
`./parity.sh <scene>` for a minimal `.dme` scene and `./game.sh [--compile]` for
the full station. Both compile with each compiler, boot both engines, wait until
each is really rendering, capture both windows and print a comparison. Prefer a
tiny scene over the full game — they compile in under a second on both engines.

## Inspecting the renderer

- `--cvar opendream.debug_plane=<n>` renders that plane's render target straight
  to the viewport, and `opendream.debug_plane_alpha=true` shows its alpha as
  greyscale. SS13's lighting plate is 22, turf lighting 10, the specular plate
  24, its mask 17.
- See `docs/byond-parity-notes.md` for verified BYOND behaviours and the
  reasoning patterns that have actually located bugs.
