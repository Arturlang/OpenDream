# BYOND parity notes

Findings from side-by-side testing of OpenDream against DreamSeeker (BYOND 516) while
stabilizing a full tgstation-derived codebase (Bubberstation). Each entry records the
BYOND behavior that was verified empirically, what OpenDream did instead, and where the
fix lives. The test worlds used for verification are minimal `.dme` scenes compiled for
both engines and screenshotted side by side; `tools/chatlayout_check.py` covers the
chat-layout case.

## Rendering

### Transform translation is a post-scale pixel offset
`matrix.Scale(2.5); matrix.Translate(-32, -32)` in BYOND scales about the icon's
center and then offsets by exactly (-32, -32) pixels - the translation is never
multiplied by the scale. OpenDream ran the translation through the scale factor,
displacing scaled icons (light overlays) by tens of pixels.
Fix: `DreamViewOverlay.CalculateDrawingMatrix` extracts the translation and applies it
after scaling.

### Transformed icons are filtered
BYOND draws atoms with a scaling/rotating transform using bilinear filtering; unscaled
pixel art stays nearest-sampled. OpenDream sampled everything nearest, making scaled
gradients (lighting overlays) jagged. DMI atlas textures cannot simply be
linear-sampled (neighboring states would bleed), so icons with a non-identity linear
part are blitted through a bilinearly-filtered render target first. The blit uses an
edge-bleed shader (`edgebleed.swsl`, blend_mode none): alpha-blending the copy would
premultiply twice, and filtering toward the black stored in transparent texels darkens
soft edges into an outline.

### Additive/subtractive blending composites premultiplied content exactly once
Robust mapped `blend_mode add` to `(SrcAlpha, DstAlpha)`. Content relayed across render
targets (tg's lighting plate graph) is premultiplied by its first draw; re-scaling by
alpha on every hop faded it exponentially - a 43%-alpha cone (directional light)
compounded to ~8% and vanished, and the DstAlpha destination factor erased accumulated
content wherever the target's alpha was under 1. Now Add/Subtract use a One destination
factor with no source alpha factor; `blendadd`/`blendsubtract` premultiply straight
sources in-shader and pass render-target sources through (the `isPlaneMaster` uniform
doubles as "source is premultiplied", set by `GetBlendAndColorShader` for plane masters
and render-source relays). `blendmultiply` un-premultiplies render-target sources
before multiplying, or soft edges over-darken the destination (the dark ring around
overlay lights in lit areas).

### SIDE_MAP draw order
Verified with a walker over floor-layer objects: BYOND keeps a gliding mob above lower
layers in every direction. The rules that reproduce this:
- Sprites sort into tile rows from north to south; southern rows draw in front.
- The row comes from the sprite's *visual* position (glide-interpolated), quantized by
  the sprite's bottom edge (`floor(y - 0.5)` with tile-center positions), so a mover
  stays in its departure row until it has visually arrived.
- Within a row, layer decides. X position never participates in depth sorting -
  OpenDream's X tie-break drew the departed tile's floor content over westward-gliding
  mobs, and its use of the glide-logical (destination) position broke northward glides.
Fix: `RendererMetaData.CompareTo` + the sort position fed in `DreamViewOverlay`.
Note: BYOND's special layer ranges (`TOPDOWN_LAYER` 10000, `BACKGROUND_LAYER`, etc.),
which exempt flat content from the side-map depth sort, are still unimplemented; tg
mostly confines such content to the floor plane, which hides this.

### KEEP_TOGETHER groups
Float planes resolve relative to the parent, so an overlay on FLOAT_PLANE (the
default - nearly every overlay) belongs to its parent's plane. The keep-apart check
compared raw appearance planes, which exiled effectively all overlays from their
KEEP_TOGETHER groups - KT mobs (ghosts, humans with translucency effects) rendered
piecewise like non-KT mobs. The group's internal render-target copy also needed a
no-blend shader, the finished group texture is premultiplied content, and the group's
own alpha must scale all four channels in-shader (an alpha-only modulate breaks
premultiplication).
Known remaining delta: final alpha-blend intensities still differ slightly from
DreamSeeker (BYOND's KT ghost body measures an exact sRGB-space 50% mix; ours lands
elsewhere), pointing at blend colorspace rather than compositing structure.

## Interface

### winget reports live control geometry
BYOND's `winget size/pos` reflects the control's current laid-out geometry. OpenDream
returned the last anchor-computed `SetSize`, which goes stale as the layout changes;
tgui-panel wingets the legacy output's size and winsets it onto the chat browser, so a
stale read permanently mis-sized the chat. `InterfaceControl.TryGetProperty` now
reports the arranged size.

### Manual size winsets cannot fight full anchoring
A control anchored 0,0-100,100 has its geometry fully dictated by its anchors. During
boot the window is still resizing, and tgui-panel's winget-then-winset round trip races
it; whatever momentary size the winset delivered was baked into the anchor offsets
(BYOND has the same offset-baking semantics - it survives only because its window
settles before page JS runs). OpenDream now drops manual size winsets on fully-anchored
controls; engine plumbing (BrowsePopup) sets sizes through the non-manual path.
Regression test: `tools/chatlayout_check.py` against a running client.

### CEF browser scale/size
CEF caches the DeviceScaleFactor from `GetScreenInfo` at browser creation; the WebView
control now calls `NotifyScreenInfoChanged` on resize/UI-scale change or the browser
keeps painting at a stale scale into a texture sized for the new one.

## Networking / entities

### /image objects don't get entities until shown
Every non-mutable `/image` used to spawn a networked nullspace entity at construction;
a tg codebase holds tens of thousands (hud_list entries and friends), flooding the
entity tables. Entities are created lazily when the image actually needs one
(`client.images`); overlay/underlay usage reads the appearance directly.

### PVS budgets are sized for DM worlds
DM clients expect to know about everything BYOND would send. Large codebases keep tens
of thousands of PVS-overridden entities (one `lighting_object` per turf shown through
vis_contents = 114k on Bubberstation); at the engine default of 50 new entities per
tick that backlog drains for tens of minutes, during which in-view objects are starved
out of the game state entirely. The client requests large budgets in
`OpenDreamClient.EntryPoint`.

## Content sandbox gotchas
Code that compiles fine can fail the client's assembly type-check at *runtime* (the
whole client dies at module load). Notable trap: `string + char` concatenation - the
compiler lowers it through `new ReadOnlySpan<char>(ref char)`, which the whitelist
rejects; use `c.ToString()` or per-character comparison.
