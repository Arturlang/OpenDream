# Performance notes

Findings from profiling OpenDream against BYOND 516.1686 on TerraGov-Marine-Corps (one
observer, lobby round, same commit compiled by both compilers). Each entry records what was
measured, the cause, and where the fix lives. Numbers are percent of one core on an
i9-12900KF with a 240 Hz display.

## How to measure without fooling yourself

- **Count the whole process tree.** OpenDream runs CEF helper processes; DreamSeeker's
  browser controls run in a WebView2 tree owned by `byond.exe`, not under `dreamseeker.exe`.
  Comparing the two client executables alone makes BYOND look three times cheaper than it is.
- **Child PIDs lie.** Windows keeps a dead parent's PID on its children, and PIDs get reused,
  so a long-running process can appear to be the child of a newer one. Ignore children
  created before their parent.
- **Per-thread CPU beats sampling for "what is busy".** dotnet-trace's sampled thread time
  counts managed frames of parked thread-pool workers as CPU, and on tight interpreter loops
  it can only stop threads at GC polls, so everything lands in `PollGCWorker`. OS per-thread
  CPU time with thread names (`Thread.Name` becomes the OS thread description) is exact.
- **Allocation rate explains interpreter cost.** `dotnet-counters` `total_allocated` on a
  call-heavy scene says more than any sampled profile.
- **Tracy shows DM time, inflated.** `opendream.enable_tracy` emits a zone per proc call,
  which roughly doubles init time; read rankings, not absolutes. The Tracy client takes one
  connection per process, so use `opendream.tracy_delay` to start it after world init when
  profiling steady state. Capture with a tracy-capture build of the client's version (0.13.1).
- **Machine load moves init time by 2x** (15 s alone vs 30+ s with another engine running).

## Server

### A 0.1 ms log flush timer kept the thread pool spinning
`ConsoleLogHandler` built its flush timer as `new Timer(0.1)`; `System.Timers.Timer` takes
milliseconds, so it fired about once per timer-queue tick and flushed stdout on a pool
thread each time. Around 1,300 work items a second kept pool workers spinning, which was
most of an idle server's CPU (9.8% total with the game thread at 1.1%). It also ran in the
client. Fix: 100 ms, which was the intent; warnings and errors still flush immediately.
Idle server: 9.8% -> 2.1%.

### The server console polled a closed stdin every tick
With stdin redirected from nothing, the reader task read `null` forever and handed it to the
console each tick. It now stops at end of input, and `UpdateInput` stops polling once the
reader is done and drained.

### Tools builds paid for Tracy on every proc resume
`DreamThread.ReentrantResume` built a Tracy zone's proc path string and source location on
every resume even with Tracy off (`BeginZone` returned null, so it never stuck and repeated
on the next resume). `InitDreamObject` formatted a string for every `new`. Now gated on
`Profiler.IsActivated()`. Release builds never had this.

### Lidgren woke every millisecond on idle sockets
The network loop waits with `Socket.Poll(1000)`, so each peer's thread wakes 1,000 times a
second, and Robust opens one per address family. Arriving data ends the wait immediately, so
the timeout only paces heartbeats; a peer with no connections, handshakes or queued sends now
waits 10 ms. The idle IPv6 thread went from 1.0% to 0.1%. Connected peers keep 1 ms: going
further means waking the thread when a send is queued, which changes ack and resend timing.

### Idle and soak numbers after the fixes
A 22-minute soak with one observer stayed flat: 3-7% total, game thread 1.1-2.3%, with no
growth over the lobby's repeated failed round starts. With one client the Lidgren network
thread (1.3-3%) is often the busiest thread; DreamDaemon was 0.1-1% in total.

### DM execution is not the bottleneck
Steady state, the whole DM tick (MC, subsystems, map update) is about 1.2 ms at 20 Hz even
under Tracy. World init is faster than BYOND's (15-30 s vs 44 s; Greyscale 4-7 s vs 19 s).
Per call, OpenDream's natives are mostly faster than BYOND's, while proc calls (about 3x),
datum proc calls (2x) and new/del (about 4x) were slower. The Tracy gating above brought
proc calls to 1.4x BYOND (0.158 vs 0.114 us), datum proc calls to parity, and new+del to
2.3x; a call-only loop went from 736 to 279 MB/s allocated and 113 to 28 gen0 GCs a second.
What is left: calls still allocate, and creating a datum allocates about 600 MB/s worth.

### Proc lookup by name walked the whole ancestry
`DreamObjectDefinition.TryGetProc` did two dictionary lookups per level up the type tree, and
`new` resolved `New` twice, `del` resolved `Del`, and `obj.proc()` resolves its proc this way.
Game types sit 6-8 levels deep, which a shallow benchmark type hides. Results (misses too) are
now cached per type; any proc definition change bumps a global version that clears them all.
Also per `new`/`del`: `gc_destroyed` was read by name twice on every release (its slot is now
resolved once per type), the object factory ran 19 subtype checks per call (the kind is now
cached per type), and `CreateObject` allocated a closure on every call because a lambda in a
rare branch captured the `state` parameter (moved into its own method).
new+del: 0.369 us at the start -> 0.161 us (BYOND 0.095). Inherited proc calls on an 8-level
type run at BYOND's speed. All 777 DM tests pass.

## Memory

### Type definitions copy every inherited var default
On TGMC the server's managed heap is about 2 GiB (DreamDaemon's whole process: 558 MiB).
Only about 430 MiB of it is DM data (`DMHeapAudit`). The single biggest structural cost is
type metadata: each of TGMC's 30,040 `DreamObjectDefinition`s holds a full copy of its
inherited var defaults (`Dictionary<string, DreamValue>`, 236 MiB of entries, about 7.8 KB a
type), plus a per-type slot-name map (45 MiB) and copied const/tmp sets (16 MiB). BYOND keeps
only each type's overrides. Sharing the parent's defaults, or flattening them into per-layout
arrays, is the fix; it sits on the var-lookup hot path, so it needs benchmarking.

### Other large consumers
`byte[]` 329 MiB (resource data and buffers), `DreamValue[]` 240 MiB (list contents and var
slots), `string` 157 MiB (2.2M), and 932k `DreamList`s at about 107 bytes each before their
contents. On TGMC every space turf builds its own `smoothing_groups` and `alpha_sources` list
(235k turfs, 37 MiB each); that is game code, and BYOND allocates those lists too.

## Client

### The client ignored client.fps
TGMC sets `client.fps = 60`; OpenDream rendered at the monitor's refresh rate instead, four
times the frames on a 240 Hz display. `client.fps` now travels in `MsgUpdateClientInfo` and
caps the frame rate through `IGameController.ContentMaxFps`, which sleeps to the cap even
with vsync on and never touches the user's `display.max_fps`.

### Hidden OS windows were drawn and swapped every frame
Robust rendered every secondary window's UI into its render target, fenced it, blitted it
and swapped it, visible or not. Each swap waits for a vblank, so three hidden skin windows
held the frame for several refreshes: 89 FPS at 107% of a core. Hidden windows are now
skipped in `UserInterfaceManager.Render` and `BlitSecondaryWindows`.

### Keep-together groups render to a pool that never shrank
`RenderTargetPool` kept every size it had ever handed out. Sizes idle for 600 frames are now
disposed, and keep-together sizes are rounded to 128 px so a moving group reuses targets.

### Where a client's CPU actually goes
In game with all of the above: OpenDream 62% (game thread ~14%, CEF main thread ~18%, CEF
helpers the rest) against BYOND 59% (DreamSeeker 21% + WebView2 38%). Both spend most of it
in the embedded browsers, not the map.
