# Fast iteration builds

Lessons from long debugging sessions against Bubberstation; the goal is cutting the
edit-build-test loop from minutes to seconds.

## What needs no build at all

Everything under `Resources/` is mounted from source and picked up by a client/server
**restart** with zero compilation:

- `Resources/Shaders/*.swsl` and `Resources/Prototypes/**` (shader prototypes)
- interface skins (`.dmf` content served to the client)

`tools/*.py` scripts likewise run from source. Only `.cs` changes need `dotnet build`,
and only `.dm`/`.dmi` changes need a DMCompiler run.

## Build only what changed

- `OpenDreamClient` changes: build only the client; a running server keeps working.
- `OpenDreamRuntime`/`OpenDreamServer` changes: build only the server.
- `OpenDreamShared` changes: build **both** - the serializer hash must match or clients
  fail to connect ("Failed to deserialize packet").
- `RobustToolbox` (engine) changes: build whichever side the change touches; the
  submodule's projects are rebuilt automatically by project references.

## build.ps1

`./build.ps1 [-Target client|server|both] [-KeepServer] [-Full]` at the repo root:

- **Frees build locks first.** MSBuild retries locked output copies for ~10 seconds per
  file (MSB3021/MSB3027) when a client or server is still running; killing them first
  turns a stalling-then-failing build into a clean fast one. `-KeepServer` protects a
  server you're still using (e.g. a long-lived play server) during client-only builds.
- **Skips restore and Robust analyzers** for speed. The analyzers catch real mistakes
  (readonly `[Dependency]` fields and friends), so run `-Full` before committing or
  after changing packages/csproj files.

## The VS Code extension builds on its own

The OpenDream extension's launch configurations build the C# projects themselves
(`dotnet build` for the client, `dotnet run` for the server) - a `preLaunchTask`
should only free file locks and compile the DM side, or everything gets built twice.
Keep `dotnet build-server shutdown` out of that path too, so the extension's builds
stay warm.

## Other time sinks

- The full Bubberstation world takes ~65s to init; the TESTING + LOWMEMORYMODE +
  ABSOLUTE_MINIMUM defines with runtimestation_minimal cut that to ~11-16s for test
  loops.
- Tiny parity `.dme` scenes (see docs/byond-parity-notes.md) compile in under a second
  on both engines - reach for those before booting the full game.
- Reconnecting a same-ckey client to a running OpenDream server can leave the session
  with no mob (black screen); restart the test server instead of reconnecting.
