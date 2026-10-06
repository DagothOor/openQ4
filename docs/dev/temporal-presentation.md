# Temporal Presentation

Milestone E adds a temporal presentation path shared by OpenGL and Vulkan. It
combines delayed GPU-time dynamic resolution with native-resolution temporal
accumulation, while preserving the existing SMAA/spatial path as the immediate
rollback. Since 2026-10-06 `r_temporalAA` defaults to `2` (automatic): TAAU
replaces the bilinear stretch whenever the 3D scene renders below native
resolution (`r_screenFraction < 100` with scale mode `1` or `2`, or dynamic
resolution), and stays off at native resolution. It is never automatic on the
OpenGL ES module, which has no temporal resolve, or on an OpenGL context
without GLSL 1.30. `R_MigrateLegacyTemporalAADefault` moves an archived `0`
to `2` once (`r_temporalAADefaultMigrated`).

## Ownership Contract

The renderer selects one immutable presentation state at `BeginFrame`:

- `sceneWidth` and `sceneHeight` size the game-owned 3D and authored-post chain;
- `outputWidth` and `outputHeight` size the temporal histories and final output;
- 3D rendering and authored scene effects complete before temporal resolve;
- HUD, menus, console, and other root 2D views are submitted after that resolve
  directly at native output resolution.

Renderer ABI v11 exposes this frame state and one append-only temporal-resolve
entry point to both game modules. The SP authored-post path owns two native-sized
history render targets; direct and MP paths that do not use that post chain use
an equivalent lazy backend-owned pair. Either owner swaps only after the exact
frame/generation resolve is accepted. A generation change, native extent change,
video/backend restart, map/session discontinuity, camera cut, capture, missing
current-frame depth stamp, or rejected write invalidates continuity. A dynamic
scene-size change does not: history is native-sized, so retaining it is required
for TAAU.

No loose material or shader asset is required. Backend resolve programs are
engine-owned resources, and retail Quake 4 materials remain unchanged.

## Dynamic Resolution

`r_rendererDynamicResolution 1` enables the controller and automatically enables
the backend-neutral whole-frame timing stream needed by it. OpenGL uses the
existing four-slot timestamp-query ring; Vulkan reads timestamps only after the
ordinary frame fence for that slot retires. Neither backend waits for a current
frame query.

The controller associates each delayed sample with the exact scale of its source
frame, rejects stale/out-of-order/generation-mismatched samples, drops resolution
quickly above budget, and raises it only after an under-budget streak. Dimensions
are bounded and aligned before target allocation. Unsupported timing keeps the
configured safe ceiling and reports `dynamicActive=0`.

Manual `r_screenFraction` scaling remains available when the automatic
controller is off. With temporal AA active, even mode `0` uses the scene-target
route so TAAU receives the requested low-resolution scene instead of the legacy
back-buffer crop path. Root UI-only frames never enter either scaling route.

Relevant controls:

| CVar | Default | Purpose |
|---|---:|---|
| `r_rendererDynamicResolution` | `0` | Enable automatic 3D scene scaling |
| `r_dynamicResolutionMinScale` | `50` | Minimum automatic scale, percent |
| `r_dynamicResolutionMaxScale` | `100` | Maximum automatic scale, percent |
| `r_dynamicResolutionTargetMsec` | `0` | Explicit GPU budget; `0` derives it from presentation timing |
| `r_dynamicResolutionTargetUtilization` | `90` | Share of the presentation interval available to GPU work |
| `r_dynamicResolutionDropStep` | `5` | Maximum percentage-point drop per over-budget sample |
| `r_dynamicResolutionRaiseStep` | `2` | Percentage-point increase after a recovery streak |
| `r_dynamicResolutionRaiseFrames` | `30` | Retired under-budget samples required before a raise |
| `r_dynamicResolutionAlignment` | `8` | Scene-dimension alignment |
| `r_dynamicResolutionCaptureNative` | `0` | Force known captures to native scene resolution instead of freezing scale |

`rendererTemporalPresentationStatus` prints the latched extents, delayed sample
identity and age, target budget, controller decision, image-history generation,
and capture state.

## Temporal History And Motion

An active temporal request replaces the game SMAA tail only when the renderer
accepts a validated temporal resolve command. Rejection leaves the established
SMAA or spatial final pass in place. The resolve uses an eight-sample Halton
sequence, previous camera projection, depth reprojection and per-pixel object
velocity.

### Per-pixel ownership

The velocity pass (`RB_RenderMotionVectorBuffer`, `VK_Post_RenderMotionVectors`)
owns every visible moving surface per pixel. `R_ScenePackets_TemporalSurfaceMotion`
classifies each view drawSurf for both backends:

| Domain | History treatment |
|---|---|
| Static world (no entity, or a static world area model) | Not drawn: camera/depth reprojection is exact |
| Rigid entities (static model, no callback) | Exact vector from the previous model transform |
| Posed (skinned MD5) surfaces | Exact vector from the previous transform and each vertex's previous model-space position |
| First-person weapon | As above, with the weapon's own depth-hack projection on both frames and its 0..0.5 depth range |
| Particles/BSE, in-world GUI, subview and post surfaces | Reactive coverage of the pixels they cover |
| Translucent entity surfaces, unposed dynamic models, newly visible entities, packed MD5R | Reactive coverage |

The previous positions come from the front end. `idMD5Mesh::UpdateSurface`
reuses each entity's triangle surface, so just before a new pose overwrites
`verts`, `R_TemporalPresentation_CapturePreviousPositions` copies the pose that
was drawn on the immediately preceding frame (`positionsFrame == frame - 1`;
animation-LOD frames that redraw the old pose keep the chain continuous). For a
main-view drawSurf whose geometry is still that surface, `R_AddDrawSurf`
uploads the capture as a frame-temp `idVec3` stream
(`drawSurf->previousPositionCache`). OpenGL binds it to texture coordinate 1;
Vulkan binds it at vertex binding 1 (`VK_EXTRA_VERTEX_POSITION_PREVIOUS`). A
skinned surface without a capture, a material deform's replacement geometry
and packed MD5R stay reactive.

The RGBA16F velocity target carries the vector in `rg` (scene pixels), the
reactive amount in `b` and an exact-vector flag in `a`. Reactive surfaces write
only `b` (`glColorMask`, or a Vulkan pipeline with R/G/A masked), and only where
they are not behind the finished opaque depth, so an exact vector underneath
survives. The amount is `r_temporalAAReactiveEffects` (0.85) for effects and
translucent geometry, 0.5 for in-world GUIs and 1 for subview and post surfaces.
A complete pass reports per-pixel ownership, and the shared packet policy then
adds no screen regions (`R_ScenePackets_BuildTemporalViewMotionPolicy(...,
perPixelOwnership)`). Only a pass that could not draw a surface falls back to
the two conservative regions, or to the whole view when the policy is
unavailable. Root 2D UI is never part of the temporal history or scene scaling.

`rendererTemporalPresentationStatus` prints the last pass's counts:
`Temporal ownership: rigid= posed= weapon= reactive= missed= complete=`.

### Resolve

Both resolve shaders (`draw_common.cpp` builtin, `temporal_resolve.frag`) share
one algorithm:

- a 3x3 neighbourhood in YCoCg gives a mean/variance box (1.25 sigma,
  intersected with the sample range); history is clipped toward the box centre
  rather than clamped per channel;
- when the nearest-depth texel of the 3x3 carries an exact object vector, that
  vector is used, so a moving silhouette carries its motion onto the
  background texels around it; a still occluder never pins the moving
  background beside it (each texel then keeps its own velocity);
- history is reconstructed with a five-tap Catmull-Rom filter, not bilinear;
- reactivity comes only from the per-pixel reactive channel (times
  `r_temporalAAReactiveScale`), the fallback regions, and depth disocclusion
  that only applies while the pixel moves. Colour differences are not reactive:
  they are what clipping handles, and treating them as reactive switched
  anti-aliasing off at exactly the high-contrast edges that need it;
- feedback (`r_temporalAAFeedback`, 0.9) falls by up to 30% for fast motion,
  and the blend is luminance-weighted so a single bright sample cannot flicker.

The image the player sees gets contrast-adaptive sharpening
(`r_temporalAASharpness`, 0.5, AMD CAS cross pattern). It is applied only when
the resolved history is presented (OpenGL: the scene present program; Vulkan:
flag 16 of the resolve block, with the amount in `reactiveRect1.x`, which a
history-less present does not read), never written back into the history.

Vulkan keeps TAA transform history separate from motion blur. It commits that
history only after the matching color history write, and requires the previous
backend frame, view identity, generation, model identity and scene extent to
match. Captures, cuts, resizes, missing previous geometry and failed resource
admission cannot reuse old vectors. Its single-sample RGBA16F velocity target
tests fragments against the current resolved scene depth, including MSAA scenes.
Vectors include camera motion and jitter once, use scene-pixel units, and scale
to native presentation pixels in the resolve. Unsupported geometry keeps its
explicit reactive ownership.

`rendererTemporalPresentationStatus` also reports Vulkan's eligible/drawn rigid
surfaces, whether the last vector pass was complete, and completed vector views.
The stock HDR gameplay gate checks that completed vector views increase during
each scaled/restarted interval. A single frame can correctly reject history
after a time discontinuity or newly visible entity; cumulative freshness proves
the real production draws without requiring unsafe reuse on that frame.

`r_temporalAAFeedback`, `r_temporalAAReactiveScale`, `r_temporalAAReactiveEffects`,
`r_temporalAASharpness` and `r_temporalAADebug` control maximum history weight,
rejection strength, effect coverage strength, present sharpening and the
velocity/reactive/history-weight diagnostic views.

## Cuts And Captures

Per-view identity includes the render world/map, root or subview chain, view id,
flags, and capture surface provenance. History is rejected for identity or
generation changes, native output resizes, time discontinuities, teleports,
large rotation cuts, and projection cuts. Equal simulation times remain valid
so high-refresh presentation can accumulate between game tics.

Known screenshot and save-preview frames render without temporal jitter. A
capture that begins after the game queued its scene marks the source timing
sample ineligible, advances only the image-history generation, and makes both
backends bypass history reads and writes. The current scene is spatially
presented for readback, then ordinary history starts cleanly on a later frame.

The stock renderer remains a numeric SDR pipeline: temporal targets preserve the
same UNORM/code-value contract as their source, and neither resolve shader adds
an sRGB or gamma transfer. Native UI is composed after the scene resolve.

## Validation

Dependency-light policy coverage lives in
`openq4-temporal-presentation-core-test` and
`openq4-temporal-history-core-test`. The static cross-repository/backend contract
is checked by `tools/tests/renderer_temporal_presentation.py`. Runtime acceptance
uses windowed engine-TGA captures and mode-specific SP/MP gameplay; operating-
system capture and injected user input are not part of the workflow.

`rendererVulkanTemporalMotionSelfTest` numerically reads GPU velocity and resolve
attachments for positive/negative translation, rotation, perspective interpolation, camera plus jitter,
invalid previous clip positions, asymmetric depth occlusion and scaled scissors.
Thirty-six fixtures cover two scene extents and both stored image origins;
missing geometry, new entities and
stale view/frame/generation/extent/capture state must reject exact ownership.
The required `renderer-vk-temporal-motion-selftest` matrix case repeats them
after full restart with active validation. These tests establish numerical
behavior, not moving-scene visual parity, performance or platform promotion.

The 2026-10-06 per-pixel ownership was checked in `game/airdefense1` (devmap,
1280x720 windowed, 60 fps cap), on OpenGL and on Vulkan with
`r_vkValidation 1`. History was read back with `screenshot image
_temporalHistoryAlbedo0`; a plain `screenshot` renders a capture frame that
bypasses history. Every captured frame reported complete ownership with no
missed surface: 53 rigid, 11 posed (2 of them the weapon) and 73-78 reactive
surfaces at the spawn view, and 3 rigid, 11 posed and 23 reactive in the
middle of a `benchmarkViewSweep 90 3000`. Vulkan logged no validation message.
Against the previous resolve (the same view on a065b928), the weapon outline
and the long wall-top edge lost their stair-steps. At `r_screenFraction 75`
the automatic mode engaged (960x540 into 1280x720) and replaced the bilinear
stretch's blocky edges with smooth ones; at `100` it stayed off. The mid-sweep
history showed no ghost trails around the weapon or the skyline. The
sharpened image the player sees cannot be captured by `screenshot`; its CAS
step was evaluated by applying the identical filter to the read-back history.
