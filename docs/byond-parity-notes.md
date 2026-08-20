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
and render-source relays). `blendmultiply` premultiplies straight sources
like the others - the (DstColor, 1-srcAlpha) blend only lerps correctly with
premultiplied RGB - and color matrices are applied in straight-alpha space
(`colormatrix.swsl` un-premultiplies flagged sources and re-premultiplies after);
baking a matrix from premultiplied content drew a dark ring around overlay lights in
lit areas.

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
Known remaining delta - blend colorspace: BYOND blends translucency in sRGB space
(a KT ghost body over the floor measures the exact byte-space 50% mix, verified to
the digit), while Robust blends in linear space, so every partial-alpha composite
lands on slightly different colors (linear mixes read lighter in the midtones).
Changing this means non-sRGB framebuffer blending or gamma compensation throughout
the pipeline. A first implementation lives on the `srgb-blending-wip` branch: raw
(non-sRGB) DMI textures and world render targets with the shader conversion pairs
stripped. Opaque content round-trips byte-exact, but a lone 50%-alpha sprite still
measures the linear mix - the surviving conversion (suspect: color-modulated draws)
needs per-hop render-target readback to locate before the branch can land.

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


### Plane composites: alpha squared through render-target hops
User report: ghosts still don't match BYOND after the byte-space work. Root cause
found and verified with the `ghostplane` parity scene (scratchpad/lightparity):
a translucent atom on its OWN plane (real ghosts: GHOST_PLANE + plane master, as
all SS13 atoms are on planes) is drawn into the plane's transparent render target
with the default (SrcAlpha, 1-SrcAlpha) blend - leaving PREMULTIPLIED bytes
(Cs*a, a) - and the plane's composite onto the base target then applied SrcAlpha
again: alpha squared. BYOND applies alpha once no matter how many plane hops.
Measured: BYOND all cases (134,138,146); OpenDream own-plane case (83,87,95) =
exact 204*a^2 + bg*(1-a) signature. The earlier scenes missed this because their
opaque turf sat in the same plane RT as the test sprite.

The fix (verified digit-exact on ghostplane; all regression scenes re-run):
- RobustToolbox fork ShaderParser: new `blend_mode premultiplied;` keyword
  ((One, 1-SrcAlpha) - the enum value already existed for the viewport path).
- New `Resources/Shaders/blendoverlay_premult.swsl` (+ `blend_overlay_premult`
  prototype): Overlay/Default compositing for premultiplied sources (plane
  masters, render-source relays, KT groups). Group alpha scales all four
  channels in-shader (`COLOR *= premultAlpha`); blendoverlay.swsl is now
  straight-sources-only and applies no alpha itself.
- DreamViewOverlay.GetBlendAndColorShader routes premultiplied sources with
  Default/Overlay blend to the premult shader; `premultAlpha` now carries
  AlphaToApply for ALL premultiplied sources (plane masters and render sources
  included, not just KT) because a modulate would only scale the alpha channel
  (base-default.frag does COLOR * MODULATE component-wise) which breaks
  premultiplied content under the (One, 1-SrcAlpha) blend. DrawIconNow skips the
  modulate-alpha for those sources correspondingly.
- DrawPlanes' masterless-plane composite uses the premult shader instead of the
  default one (same double-alpha bug).
- blendadd/blendsubtract/blendmultiply already follow this convention
  (`COLOR *= premultAlpha` under (One,One)/(DstColor,1-SrcAlpha) gives the right
  master-alpha fade semantics - for multiply it's lerp(Cd, Cs*Cd, g)).

A premultiplied composite makes a render target's CLEAR COLOR visible. Under
(One, 1-SrcAlpha) a texel contributes its color regardless of alpha, so padding
that is transparent-but-not-black is added straight onto the destination.
`Color.Transparent` in RobustToolbox is `(255,255,255,0)` - WHITE with zero
alpha - and ProcessKeepTogether cleared its two targets with it. The ktalpha
rerun caught this: the KT group's whole 288x288 render-target quad washed out
everything behind it, by exactly white * the parent's color * the group alpha
(bg 64 + 255*0.8*0.5 = 166 for the alpha-128 group, and 64 + 255*0.8 = 268 ->
saturated 255 for the alpha-255 one). KT now clears to `Color.Black.WithAlpha(0)`
like every other target here (DreamPlane uses `new Color()`, DreamIcon and the
bilinear-smoothing path already used Black.WithAlpha(0)). Rule for this renderer:
a target that will be composited as a premultiplied source must be cleared to the
premultiplied identity (0,0,0,0), never to `Color.Transparent`.

Regression results on the fixed build, all against BYOND captures:
- ghostplane: all three cases (134,138,146) - BYOND-identical.
- alphaone: square (134,138,146) - exact.
- ktalpha: overlay bands (114,74,63)/(107,76,82) and body strips
  (134,138,146)/(134,138,146)/(204,204,204) - all exact (pre-fix they were
  (97,63,65) and (117,119,124)/(155,157,160), i.e. wrong).
- lightrelay: glow peak (58,66,82) now matches BYOND exactly (the pre-fix build
  plateaued at (44,51,63), too dim - this is the `*` render-target plane-master
  alpha that used to be silently dropped). Radius scales exactly with the
  viewport (303 BYOND px vs 150 OD px at 2.02x), falloff monotonic, cones
  visible, no dark rings. BYOND's plateau is slightly narrower than OpenDream's,
  leaving a mid-radius band up to 6/255 brighter in OpenDream; the inner and
  outer ends of the curve agree exactly.

Separate pre-existing issue found while measuring ktalpha (NOT caused by this
work - the pre-fix capture has the same geometry): in SIDE_MAP, BYOND sorts
overlays by their pixel_y offset, so the `pixel_y = 8` overlays render BEHIND the
atom's own icon; OpenDream draws them on top. Confirmed numerically - every
OpenDream color in the overlap region is exactly what the same blend math gives
with the draw order reversed, which is itself a check that the alpha math is now
right. Bubberstation sets `map_format = SIDE_MAP` (code/world.dm:21), so this
affects the real game and is worth its own fix.

Remaining: user retests ghosts/MODsuit/PDA lights in game. Scene runner +
measurement scripts: see capture.ps1 and measure_runs.py in
scratchpad/lightparity; launch pattern is documented in docs/fast-builds.md.

### Colour matrices must run on straight colour in premultiplied composites
Symptom: on Bubberstation every lit floor blew out to white, while space read
slightly too dark. Lit-room percentiles against BYOND on the same map, same
observer landmark: BYOND p75 (98,82,67) / p90 (104,86,70); OpenDream p75
(217,170,125) / p90 (255,239,180).

The decisive observation is that OpenDream's own unlit game plate reads
(104,103,105) - the floor's albedo - and BYOND's final lit floor is (104,86,70),
exactly albedo x the lighting value (1, 0.844, 0.672) the server computed. A
BLEND_MULTIPLY can only darken, so a final image ABOVE the albedo proves an
additive term. The only additive relay onto the game plane is the specular
plate.

Root cause: BYOND colour matrices are defined over straight RGBA and their
constant row often sets RGB while leaving alpha at zero.
blendoverlay_premult.swsl added that constant onto already-premultiplied
render-target content, breaking rgb <= a, and the (One, 1-SrcAlpha) blend then
painted solid colour where alpha was zero. SS13 builds the specular mask that
way - the emissive plate relays with constant (1,1,1,0), mapping blue onto alpha
for an alpha_mask_filter - so the mask read as fully open (alpha 255 over 40% of
the screen, >25 over 72%) and the specular plate was added everywhere. Fix:
un-premultiply, apply the matrix, re-premultiply. Identity round-trips, so the
alpha-once behaviour for ghosts and plane masters is untouched.

Method worth reusing: every mechanism passed in isolation - multiply plate,
per-turf darkness, the two set_light_cutoff matrices, render_target + multiply
relay, the inverse emissive mask, the lighting objects' corner-weight icon, even
colour-channel-into-alpha. The bug only appeared when a matrix with a constant
row met a premultiplied source. Two tools found it:
- `opendream.debug_plane` / `opendream.debug_plane_alpha` render one plane's
  render target (or its alpha) to the viewport. Use blend_mode none: blending
  the plane over the finished world makes an empty plane look full, which sent
  this investigation down a false path once already.
- an AUTO_OBSERVE build of the game dumps the server's lighting values, which
  showed both engines computing byte-identical lighting for all 81 sampled
  turfs and so ruled out the server entirely.

Scenes and harness live in scratchpad/lightparity: `./parity.sh <scene>` for a
scene, `./game.sh [--compile]` for the full station. Both boot BYOND and
OpenDream, wait until each is really rendering, capture and compare. They kill
only the PIDs they spawn - never by process name, or unrelated DreamSeeker
instances die too - and use ports 26777/26800 so they cannot capture a manually
booted station by mistake.
