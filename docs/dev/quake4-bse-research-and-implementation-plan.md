# openQ4 Quake 4 BSE Research And Implementation Plan (2026-02-06)

## Purpose

This document captures a deep technical review of Quake 4's BSE (Basic System for Effects) and a concrete implementation plan for openQ4.

Primary references:

- openQ4 source tree (`src/bse`, `src/game`, `src/renderer`, `src/framework`)
- Reverse-engineered BSE project: `E:\_SOURCE\_CODE\Quake4BSE-master`

Status (2026-10-02): the gap analysis and plan below are historical. The
[retail parity audit](#retail-parity-audit-2026-10-02) at the end records the
current state, measured against the retail 1.4.2 executable, and supersedes the
snapshot entries it names.

## What BSE Is

BSE is Raven's data-driven effects runtime used by Quake 4 for particles, trails, lights, decals, sounds, and camera/view effects (shake/tunnel). Compared with Doom 3 style FX, BSE is a full runtime system with:

- structured effect declarations (`.fx` under `effects/`)
- multi-segment effect graphs
- per-particle spawn/motion/death domains
- envelope/table-driven interpolation
- optional physics, impact/timeout sub-effects, and nested effect spawning

In code terms:

- `rvDeclEffect` is the parsed declaration/template (`src/bse/BSE.h`)
- `rvSegmentTemplate` defines segment behavior (`SEG_EMITTER`, `SEG_LIGHT`, `SEG_SOUND`, etc.)
- `rvParticleTemplate` defines particle type, domains, flags, and events
- `rvBSE` is the live runtime instance bound to one `renderEffect_t`
- `rvBSEManager` is the global service interface used by renderer/game

## Engine And Game Wiring (How It Is Supposed To Flow)

### Decl registration and lookup

openQ4 wires BSE effects as a dedicated decl type:

- `RegisterDeclType( "effect", DECL_EFFECT, idDeclAllocator<rvDeclEffect> )`
- `RegisterDeclFolder( "effects", ".fx", DECL_EFFECT )`
- `FindEffect()` resolves through `DECL_EFFECT`

Files:

- `src/framework/DeclManager.cpp`
- `src/framework/declManager.h`

### Game import and API boundary

BSE crosses the engine/game DLL boundary through `gameImport_t`:

- `rvBSEManager* bse` in `gameImport_t`
- `GetGameAPI` assigns `bse = import->bse`

Files:

- `src/game/Game.h`
- `src/game/Game_local.cpp`

### Runtime effect lifecycle

Normal path:

1. Game code creates `rvClientEffect` via `idGameLocal::PlayEffect` / `idEntity::PlayEffect`.
2. `rvClientEffect::Think` pushes `renderEffect_t` into renderer using `AddEffectDef`.
3. Renderer allocates `rvRenderEffectLocal` and calls `bse->PlayEffect`.
4. Per render frame, `R_AddEffectSurfaces` calls `bse->ServiceEffect`.
5. Game frame wraps logic with `bse->StartFrame()` and `bse->EndFrame()`.

Files:

- `src/game/Game_local.cpp`
- `src/game/Entity.cpp`
- `src/game/client/ClientEffect.cpp`
- `src/renderer/RenderWorld.cpp`
- `src/renderer/tr_light.cpp`

### Script, network, and savegame usage

BSE is used by gameplay systems through multiple channels:

- Script VM: `idThread::Event_PlayWorldEffect`
- Network: `GAME_UNRELIABLE_MESSAGE_EFFECT`
- Entity instance events: `EVENT_PLAYEFFECT`, `EVENT_PLAYEFFECT_JOINT`
- Save/restore: `WriteRenderEffect` and `ReadRenderEffect` serialize `renderEffect_t`, including decl name and shader parms

Files:

- `src/game/script/Script_Thread.cpp`
- `src/game/Game_network.cpp`
- `src/game/Entity.cpp`
- `src/game/gamesys/SaveGame.cpp`

## BSE Script System Intricacies

### Effect-level grammar (`rvDeclEffect::Parse`)

Top-level effect blocks allow segment declarations and global controls.

Observed segment keywords:

- `tunnel`
- `shake`
- `delay`
- `light`
- `decal`
- `sound`
- `trail`
- `spawner`
- `emitter`
- `effect` (nested effect segment)

Observed effect-level scalar keywords:

- `cutOffDistance`
- `size`

Current openQ4 parser issue:

- `rvDeclEffect::Parse` is hard-disabled via `#if 1 return true;` in `src/bse/BSE_EffectTemplate.cpp`.

Reference implementation:

- `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_EffectTemplate.cpp` has active parse logic and finish pass.

### Segment-level grammar (`rvSegmentTemplate::Parse`)

Key segment controls:

- timing and population: `start`, `duration`, `density`, `count`/`rate`, `particleCap`
- attenuation: `attenuation`, `attenuateEmitter`, `inverseAttenuateEmitter`
- transform/sort flags: `orientateIdentity`, `useMaterialColor`, `depthsort`, `scale`, `locked`, `calcDuration`, `constant`
- sound: `soundShader`, `volume`, `freqShift`, `channel`
- child effects: repeated `effect <name>`
- type selection for particle template blocks: `sprite`, `line`, `oriented`, `decal`, `model`, `light`, `electricity`, `linked`, `orientedlinked`, `debris`

Segment finish behavior in BSE is important:

- min/max ranges are normalized
- segment flags are inferred from particle/template characteristics
- effect duration bounds are expanded from segment timing
- trail segment links are resolved by name

Files:

- `src/bse/BSE_SegmentTemplate.cpp`

### Particle-level grammar (`rvParticleTemplate::Parse`)

Key particle resrc/data controls:

- resource pointers: `material`, `model`, `entityDef`
- rendering flags: `blend`, `shadows`, `specular`, `useLightningAxis`
- behavior flags: `persist`, `tiling`, `generatedLine`, `generatedNormal`, `generatedOriginNormal`, `flipNormal`, `lineHit`, `parentvelocity`
- timing/physics: `duration`, `gravity`, `windDeviationAngle`
- trails: `trailType`, `trailMaterial`, `trailTime`, `trailCount`, `trailRepeat`, `trailScale`
- events: `impact { ... }`, `timeout { ... }`
- domain blocks: `start { ... }`, `motion { ... }`, `end { ... }`

Spawn domain primitives:

- `point`
- `line`
- `box`
- `sphere`
- `cylinder`
- `spiral`
- `model`

Common spawn modifiers in domain blocks:

- `surface`
- `useEndOrigin`
- `cone`
- `relative`
- `linearSpacing`
- `attenuate`
- `inverseAttenuate`

Files:

- `src/bse/BSE_ParseParticle2.cpp`
- `src/bse/BSE_SpawnDomains.h`
- `src/bse/BSE_Envelope.h`
- `src/bse/BSE_Particle.h`

## Runtime behavior details

Important BSE runtime semantics from the recovered code paths:

- Effect-level looping and duration management (`LoopLooping`, `LoopInstant`)
- Segment-level spawn/update/check phases
- Per-segment sound update against reference emitter
- Distance attenuation evaluation per segment
- Timeout/impact spawned sub-effects
- End-origin aware behavior for linked beams and similar effects

In openQ4, much of this logic exists but is currently disabled or stubbed.

## Current openQ4 Status (Gap Analysis)

### Major missing/disabled areas

1. Decl parse is bypassed.
- `rvDeclEffect::Parse` returns early; actual parser is dead code block.
- File: `src/bse/BSE_EffectTemplate.cpp`

2. Segment runtime is effectively stubbed.
- Compiled methods at file top are empty/do-nothing for core segment lifecycle.
- Large reconstructed logic is wrapped in `#if 0`.
- File: `src/bse/BSE_Segment.cpp`

3. Owner sync and render pass are incomplete.
- `rvBSE::UpdateFromOwner` is TODO/decompile block.
- `rvBSE::Render` is disabled (`#if 0`).
- File: `src/bse/BSE_Effect.cpp`

4. Manager behavior is stubbed.
- `EffectDuration` returns `0`
- `CheckDefForSound` always returns `true`
- `Filtered` always returns `false`
- `CanPlayRateLimited` always returns `true`
- `UpdateRateTimes` empty
- File: `src/bse/BSE_Manager.cpp`

5. Renderer sound pre-check is stubbed.
- `idRenderWorldLocal::EffectDefHasSound` returns `false`.
- This blocks expected emitter allocation logic in `rvClientEffect::Think`.
- File: `src/renderer/RenderWorld.cpp`

6. Particle/template cleanup still has TODO/memory-leak placeholders.
- `PurgeTraceModel` free path commented
- `Purge()` TODO
- several parse paths still marked uncertain
- File: `src/bse/BSE_ParseParticle2.cpp`

### Behavioral concern to resolve during implementation

`rvClientEffect::Think` treats `UpdateEffectDef(...) == true` as "effect is done; remove self". openQ4 currently returns `true` unconditionally from `idRenderWorldLocal::UpdateEffectDef`, which can prematurely tear down live client effects unless compensated by other code paths.

File:

- `src/game/client/ClientEffect.cpp`
- `src/renderer/RenderWorld.cpp`

## Detailed Implementation Plan

This plan prioritizes compatibility with original Quake 4 assets and shipped-content behavior. openQ4 does not target binary compatibility with the proprietary Quake 4 game DLLs.

### Phase 0: Baseline and instrumentation

Goals:

- establish reproducible baseline before touching BSE core
- capture current warnings/errors from stock assets only

Tasks:

1. Run Procedure 1 loop against installed Quake 4 assets:
- launch default task
- close after ~3s
- inspect `fs_savepath\<gameDir>\logs\openq4.log` (commonly `${workspaceFolder}\\.home\\baseoq4\\logs\\openq4.log`)
2. Add temporary logging hooks (guarded by cvars/dev flags) for:
- effect parse success/failure
- `AddEffectDef`/`UpdateEffectDef`/`FreeEffectDef`
- manager `PlayEffect`/`ServiceEffect` decisions
3. Ensure `fs_cdpath` (locked to launch working directory) does not depend on repo `q4base/` content during validation runs.

Acceptance:

- baseline log snapshot saved in notes/task doc
- reproducible list of current BSE-related warnings/errors

### Phase 1: Restore declaration parsing

Goals:

- fully parse Quake 4 `.fx` effect declarations via `DECL_EFFECT`
- recover template-level flags/duration/cutoff/size semantics

Tasks:

1. Replace early-return parser in `rvDeclEffect::Parse`.
2. Port/align parser and `Finish()` flow using reference:
- `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_EffectTemplate.cpp`
3. Validate all top-level segment keywords and global tokens.
4. Verify `CacheFromDict` / `FindEffect` interactions still match expected decl manager behavior.

Files:

- `src/bse/BSE_EffectTemplate.cpp`
- `src/framework/DeclManager.cpp` (only if lookup behavior adjustments are needed)

Acceptance:

- effect decls parse without fallback defaults for stock content
- unknown token diagnostics include file/line context

### Phase 2: Restore segment template and particle parsing correctness

Goals:

- make segment and particle templates produce runtime-ready data
- eliminate placeholder paths that degrade behavior

Tasks:

1. Reconcile `rvSegmentTemplate::Parse` + `Finish` with reference semantics.
2. Reconcile `rvParticleTemplate::Parse*` family:
- spawn/motion/death domains
- impact/timeout effect lists
- trail/electricity/model handling
3. Fix memory ownership for:
- env parameter allocations
- trail/electricity structures
- trace model lifecycle (`PurgeTraceModel` and `Purge`)
4. Ensure `UsesEndOrigin`, duration clamps, and parameter count setup mirror expected behavior.

Files:

- `src/bse/BSE_SegmentTemplate.cpp`
- `src/bse/BSE_ParseParticle2.cpp`
- `src/bse/BSE_Particle.h`
- `src/bse/BSE_SpawnDomains.h`
- `src/bse/BSE_Envelope.h`

Acceptance:

- representative stock effects parse to non-default template data
- no growth/leaks from repeated map loads and effect replay loops

### Phase 3: Restore runtime effect state synchronization

Goals:

- correctly track owner transform, end origin, bounds, tint, velocity, and timing

Tasks:

1. Implement `rvBSE::UpdateFromOwner` based on recovered logic.
2. Verify/update:
- local/world bounds updates
- axis transpose and lightning axis derivation
- current velocity and interpolation fields
- end-origin changed flag behavior
3. Validate attenuation inputs (`UpdateAttenuation`, distance metrics) against runtime values.

Files:

- `src/bse/BSE_Effect.cpp`

Acceptance:

- moving/bound effects follow entities and joints correctly
- end-origin effects (beams/trails) update continuously without desync

### Phase 4: Restore segment runtime and rendering path

Goals:

- re-enable full segment lifecycle and particle generation/update/render

Tasks:

1. Remove stubs and re-enable compiled segment logic:
- `Init`, `ResetTime`, `Check`, `CalcCounts`, `Handle`, `UpdateParticles`, `InitParticles`, `AllocateSurface`, render helpers
2. Re-enable/implement segment render paths:
- particle draw, motion trail, decal creation
3. Re-enable/implement effect-level render model update path (`rvBSE::Render` or equivalent final architecture).
4. Reconcile any old renderer API drift with current openQ4 renderer interfaces.

Files:

- `src/bse/BSE_Segment.cpp`
- `src/bse/BSE_Effect.cpp`
- `src/renderer/Model_local.*` / related render-model interfaces if needed

Acceptance:

- visible effect content appears with expected particle/trail/decal/light behavior
- renderer surfaces/bounds remain stable across frame updates

### Phase 5: Restore manager and renderer contract behavior

Goals:

- match expected effect lifetime/sound/rate-limit behavior used by game code

Tasks:

1. Implement manager functions with real semantics:
- `EffectDuration`
- `CheckDefForSound`
- `Filtered`
- `UpdateRateTimes`
- `CanPlayRateLimited`
2. Implement `idRenderWorldLocal::EffectDefHasSound` by delegating to manager/decl metadata.
3. Correct `UpdateEffectDef` contract so `rvClientEffect::Think` lifetime logic behaves correctly.
4. Validate `StopEffectDef` and `FreeEffectDef` semantics for looped vs non-looped effects.

Files:

- `src/bse/BSE_Manager.cpp`
- `src/renderer/RenderWorld.cpp`
- `src/game/client/ClientEffect.cpp` (only if return-contract glue needs adjustment)

Acceptance:

- looping and one-shot effects end when expected
- sound emitter allocation/use/release behavior is stable
- category/rate filtering works and is externally controllable by cvars

### Phase 6: Game-lib parity validation

Goals:

- confirm behavior parity for script/network/savegame pathways

Tasks:

1. Validate script-triggered world effects (`Event_PlayWorldEffect`).
2. Validate network-triggered effects:
- unreliable message path
- entity event path
3. Validate save/restore of active effects with start/end origin, loop flag, and shader parms.
4. Validate first-person/player-local effects and attenuation with PVS constraints.

Files:

- `src/game/script/Script_Thread.cpp`
- `src/game/Game_network.cpp`
- `src/game/Entity.cpp`
- `src/game/gamesys/SaveGame.cpp`

Acceptance:

- no effect regressions across single-player + multiplayer core scenarios
- save/load restores active effects without crashes or orphaned emitters

### Phase 7: Compatibility hardening and cleanup

Goals:

- move from "works in most cases" to "stock-asset compatible"

Tasks:

1. Run repeated Procedure 1 loops with stock assets only until logs are clean of BSE parser/runtime warnings.
2. Remove temporary diagnostics and dead `#if 0` reconstruction chunks once stabilized.
3. Document final behavior and compatibility notes in `README.md` and/or dedicated BSE doc.
4. Re-check repo `q4base/` dependency footprint and avoid content-side fixes for engine/runtime issues.

Acceptance:

- clean startup/shutdown with stock Quake 4 assets
- no required custom `q4base` overrides for BSE initialization

### Recommended Execution Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7

This order minimizes hidden coupling: parse/template correctness first, then runtime state, then render/manager contracts, then gameplay-path parity.

### Progress Snapshot (2026-02-06, follow-up pass)

- Phase 4 (runtime foundation): implemented non-stub segment lifecycle plumbing (`Init`, `InitTime`, attenuation helpers, `Check`, `Handle`, `UpdateParticles`, `CalcCounts`) so effects no longer rely on pure no-op segment runtime paths.
- Phase 4 note: full particle simulation/render/decal projection parity is still pending because openQ4 currently lacks several runtime particle implementation units present in the reverse-engineered reference tree.
- Phase 5 (manager/renderer contract): implemented manager-side duration/sound/filter/rate-limit logic, wired `EffectDefHasSound`, fixed `UpdateEffectDef` return semantics to report completion via `rvRenderEffectLocal::expired`, and hardened effect handle bounds checks.
- Runtime validation loop executed after these changes; latest run logs show no BSE parser/runtime warnings.
- Current blocker for strict Procedure 1 path: startup can fatal early with `Couldn't load default.cfg` when savepath config is absent/non-writable; validation was completed using the configured writable savepath.
- Phase 6 (game-lib parity): restored network/entity event effect safety paths by removing the `EVENT_PLAYEFFECT_JOINT` assert placeholder, adding null-decl + `Filtered` + rate-limit guards on receive paths, and restoring gravity assignment for unreliable/world and entity-bound event effects.
- Phase 6 (save/restore parity): `rvClientEffect::Restore` now clears `referenceSoundHandle` so active effects rebind a valid emitter after load instead of reusing stale handles.
- Phase 7 (hardening pass): repeated Procedure 1 launch/short-run/log checks with stock assets (`fs_cdpath` launch directory set to stock assets) and confirmed zero BSE parser/runtime tokens (`BSE`, `rvBSE`, invalid segment/motion/effect parse errors, asserts/fatals) in `fs_savepath\<gameDir>\logs\openq4.log`.
- Interim visibility step: added `bse_fallbackSprite` (default `1`) to draw a temporary sprite-backed `renderEntity_t` for active client effects while full BSE particle surface generation is still being restored.
- Phase 4/5 parity continuation: restored active segment spawn scheduling in `rvSegment::Check` for `SEG_EMITTER`, `SEG_TRAIL`, and `SEG_SPAWNER`, including attenuation-driven interval/count handling and loop-safe time progression (`mLastTime`) so particle segments no longer remain effectively inert.
- Phase 4 parity correction: removed the erroneous large negative spawn offset in `rvBSE::Service` (`-10.0f * segmentIndex` equivalent), which had been delaying segment start checks by whole seconds; segment checks now run on current frame time.
- Phase 4 parity correction: trail/child spawn offsets are now propagated into particle init position in `rvParticle::FinishSpawn`, and trail segments now pass interpolated local movement offsets when spawning.
- Phase 4 parity correction: `rvParticle::EvaluatePosition` / `EvaluateVelocity` now convert between spawn-space and current effect-space for non-locked particles using stored spawn origin/axis, reducing obvious orientation/placement drift for moving/rotating emitters.
- Phase 3/4 detail parity: `rvBSE::UpdateFromOwner` now transforms owner `windVector` into effect-local wind (`mCurrentWindVector`) instead of forcing zero each frame.
- Phase 4 parity continuation: implemented `SEG_DECAL` world projection path in `rvSegment::CreateDecal` (spawn size/rotation sampling + winding projection through `idRenderWorld::ProjectDecalOntoWorld`) instead of a no-op stub.
- Phase 4/5 parity slice (spawn ordering / draw order): restored runtime spawn-list insertion behavior in `BSE_SegmentRuntime` so particles are no longer always LIFO-inserted; linked segments now preserve stable end-time ordering while complex segments keep front-insert behavior, and temporary segments are handled explicitly.
- Phase 5 draw-order refinement: segment render path now treats linked strip particles specially by disabling depth-sort for strip topology and using first-strip index budgeting rules to avoid premature render rejection.
- Phase 5 utility parity: `rvSegment::Sort` in `BSE_SegmentRuntime` is now implemented with stable depth sorting for deterministic per-segment order when invoked.
- Validation: after each of these patches, openQ4 compiles cleanly and Procedure 1 short-run log checks continue to show no BSE parser/runtime assert/fatal regressions.
- Phase 5 correctness fix: removed the `Filtered()` + `CanPlayRateLimited()` double-consumption path on network/entity receive flows (`src/game/Entity.cpp`, `src/game/Game_network.cpp`); rate-limit cost is now consumed once per event.
- Phase 2/4 correctness fix: restored `rvParticleTemplate::FixupParms` sanitization logic (previously fully disabled), re-enabling spawn-type normalization and end-origin spawn-type promotion behavior used by parsed particle domains.
- Phase 3/4 parity fix: `rvBSE::UpdateFromOwner` now derives `mLightningAxis` from current origin/end-origin direction (with stable fallback basis), instead of leaving lightning-axis state stale/default.
- Phase 4/5 parity fix: `rvSegment::AttenuateInterval` and `rvSegment::AttenuateCount` now apply `bse_scale` interpolation semantics instead of hardcoded max-range behavior.
- Phase 4/5 parity fix: `bse_maxParticles` is now enforced consistently in segment runtime allocation/count clamps (`InitParticleArray`, `AddToParticleCount`, spawner/check and precomputed count clamps), rather than silently using compile-time `MAX_PARTICLES` only.
- Phase 7 cleanup: temporary always-on BSE trace spam (`spawn/expire/generic-remove`, segment render skip, segment state print) has been removed from runtime paths, and `bse_frameCounters` default was set back to `0` in renderer init.
- Validation (2026-02-07): clean rebuild executed from `builddir/` (full clean + full rebuild) and both `openQ4.exe` and `openQ4-ded.exe` link successfully; 10-second stock-asset launch/log pass shows zero BSE parser/runtime assert/fatal tokens.
- Phase 4 physics parity: `rvParticle::FinishSpawn` now applies template-authored gravity (`gravity` decl range) in effect-space, projected into particle-local acceleration, instead of silently ignoring particle gravity.
- Phase 4 debris parity: `rvDebrisParticle::FinishSpawn` now follows the client-moveable path (`game->SpawnClientMoveable`) when `entityDef` is provided, and immediately retires CPU-side particle rendering for those debris particles.
- Phase 5 robustness: client-effect shader parm defaults (RGBA/brightness/time offset) are now initialized in `rvClientEffect::Init`, and `rvBSE::UpdateFromOwner` now applies a safe fallback to unit tint/brightness when render effects arrive with fully zeroed shader parms.
- Phase 7 hardening: implemented missing `rvParticleTemplate` utility methods declared in headers (`Compare`, `GetTraceModel`, `GetTrailCount`, `ShutdownStatic`) to remove remaining declaration/implementation gaps in the template runtime contract.
- Phase 4 timing/lifecycle parity follow-up: `rvSegment::Check` now short-circuits on expired/stopped segments (decompiled behavior), removes the global end-time rejection path that could suppress late-serviced short emitters, and marks `SEG_SOUND` as one-shot-expired after initial trigger so sounds are not restarted every service pass.
- Phase 4/5 spawn/detail parity follow-up: spawner batch fraction was aligned to decompiled semantics (`i / count`), and effect sprite-size shader overrides (`shaderParms[8]`/`[9]`) are now propagated through `rvBSE::UpdateFromOwner` and honored by `rvSpriteParticle::Render`.
- Phase 3/4 bounds parity follow-up: effect world bounds are now initialized once in `rvBSE::Init` and grown in `UpdateFromOwner` instead of being cleared each frame, matching decompiled accumulation behavior used by attenuation/local-bounds derivation.
- Validation (2026-02-08): rebuild + staged install succeeded, and long diagnostic pass (`_save/q4base/logs/bse_repro_long_1770579479.log`) shows improved frame metrics versus the prior two runs (`1770578957`, `1770579353`): average rendered effects `60.91` (up from `57.33`/`52.47`), average effect `noIndexed` `6.09` (down from `10.55`/`14.53`), and zero spawn miss/service-cap warnings.
- Phase 4 matrix parity follow-up (2026-02-08): unlocked particle bounce persistence now reprojects post-impact velocity/position through inverse `current->init` axis mapping (plus origin-delta compensation) before storing `mVelocity`/`mInitPos`, preventing frame-space double-transform drift after impacts on moving/rotating emitters.
- Phase 3 owner-kinematics parity follow-up (2026-02-08): `rvBSE::UpdateFromOwner` now preserves the last valid `mCurrentVelocity` when owner updates arrive with near-zero `dt` (same-timestamp service/update paths), matching decompiled behavior instead of forcing a zero velocity spike.
- Phase 4 render-matrix parity follow-up (2026-02-08): `rvOrientedParticle::Render` now matches decompiled oriented-quad corner sign/order (`-right`, `-up`, `+right`, `+up`) for the rotation basis, eliminating mirrored orientation in oriented particle quads.
- Runtime stability follow-up (2026-02-08): hardened startup command parsing and token append bounds (`ParseCommandLine`, `StartupVariable`, `idCmdArgs::AppendArg`) to prevent access violations under oversized `+wait` stress command lines; reproduced crash no longer occurs across `+wait` 40/120/900 validation launches.

### Implementation Reference Mapping (openQ4 <-> Quake4BSE-master)

- `src/bse/BSE_EffectTemplate.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_EffectTemplate.cpp`
- `src/bse/BSE_SegmentTemplate.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_SegmentTemplate.cpp`
- `src/bse/BSE_ParseParticle2.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_ParseParticle2.cpp`
- `src/bse/BSE_Effect.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_Effect.cpp`
- `src/bse/BSE_Segment.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_Segment.cpp`
- `src/bse/BSE_Manager.cpp` <-> `E:\_SOURCE\_CODE\Quake4BSE-master\bse\BSE_Manager.cpp`

Use this mapping as a behavior reference, not a blind copy source. Keep openQ4 interfaces and build layout intact, and preserve Quake 4 compatibility requirements first.

## Retail Parity Audit (2026-10-02)

Eight months into the reconstruction, every BSE area was compared with the
retail Quake 4 1.4.2 executable (`Quake4.exe`, BSE linked in): x87 disassembly,
RTTI vtables and the spawn function table. Neither reference tree is reliable
on its own. Quake4Decompiled comes from a pre-1.1 build and has
reconstruction errors (its segment enum and `EffectDuration` fallback are
wrong). Quake4BSE-master derives from Enemy Territory: Quake Wars, so its
`sdModelInfo`, oriented-linked particles and extra virtual arguments are not
Quake 4 behavior. Where they disagreed with the binary, the binary won.
`tools/tests/bse_retail_parity.py` pins the corrections most likely to drift
back.

### Corrections

Spawn domains (`BSE_SpawnDomains.cpp`):

- The samplers follow the retail spawn table: sphere, cylinder and cone volumes
  and surfaces, cylinder surface normals with taper, box faces in retail's
  cube-face order, rectangle outlines, spirals with zero range, and the stub
  domain as a no-op.
- Model domains pick a random surface and triangle, use the face normal, map
  model axes onto effect axes as retail does, and fit the sample into the
  domain box. They reference the model directly instead of ETQW
  `sdModelInfo` copies.
- `GetMinsMaxs` and the `SurfaceBox1` endpoint choice keep retail's literal
  behavior.

Templates and parsing (`BSE_ParseParticle2.cpp`, `BSE_SegmentTemplate.cpp`):

- Segment costs use retail's base-cost table.
- Segment bounds come from retail's per-type formula.
- Spawn volume, maximum parameter value and furthest distance (including
  gravity) are literal ports.
- The particle duration is clamped to 60 s, and trail counts truncate.
- Model particles trace as points.
- Debris entity definitions precache their media.
- The openQ4-only `drip_ring` to `drip_splash` substitution is gone: a missing
  child effect plays nothing, as in retail.

Segments (`BSE_Segment.cpp`, `BSE_SegmentRuntime.cpp`):

- `rvSegment::Check` matches retail's timing. It records the service time on
  entry, fast-forwards emitters to the segment start, stops constant emitters
  at the end of their window, truncates spawner counts, and expires trail,
  delay, decal, light and view segments after their single action.
- Sound segments set volume, frequency shift and emitter position before
  starting. One-shot sounds play once per loop; looping sounds latch with
  `SSF_LOOPING`.
- Both sound starts pass `rvRandom::flrand(0, 1)` as the diversity (retail
  calls at `0x101cc5fe` and `0x101cc643`), so multi-sample shaders pick a
  random entry. The fixed 0.0 used before played entry 0 every time. In the
  retail paks, 311 of the 502 effects with sound segments use a multi-sample
  shader. They include machinegun, shotgun, nailgun, hyperblaster, blaster and
  gauntlet impacts, ricochets, bullet whiz-bys and rocket and grenade
  explosions. Emile Belanger found the fixed value first
  ([emileb/openQ4@71af0c11](https://github.com/emileb/openQ4/commit/71af0c115f4e99fd1a9b5d49bd74d5eba6eb9413)).
- Child effect segments play only when the owner is in a connected area, and
  pass no end origin.
- The spawn look-ahead is 0.016 s. Interval attenuation interpolates in
  retail's direction, and lights initialise only when freshly spawned.
- Decals size from `size.x` and rotate from `rotate.x`.
- Electricity segments size their surface from the live bolt total every
  frame.

Effects (`BSE_Effect.cpp`):

- Loop and ambient flags are latched when the effect starts, and the
  connected-area flag is read on every owner update.
- A looping ambient effect starts with two loops of history, so map effects
  are already in full flow when first seen.
- The `bse_debug 2` cost overlay costs each segment by its own template.
- The sprite-size overrides (`shaderParms[8]`/`[9]`) and light-suppression
  hooks added in February are removed; retail never reads them.

Particles (`BSE_Particle.cpp`):

- Spawning follows retail order. Velocity, acceleration and friction are
  sampled first, then the orientation comes from the spawn normal, a generated
  normal rotates velocity and length, and acceleration and friction rotate by
  their motion normals.
- Friction is a vector with retail's exponential terms.
- End-origin particles resample their domains from a copy of the parameters.
- Line, linked and debris particles use their retail overrides. Debris hands
  off to a client moveable at birth.
- Bounces store the current frame and come to rest below retail's speed limit.
  Physics traces include render models, and impact and timeout effects respect
  the connected-area flag.
- Envelopes run at the rate fixed at spawn. Infinite segments extend `mEndTime`
  every frame, which used to slow their envelopes down.
- Vertex colours pack the retail way. Additive particles fade through RGB and
  stay opaque without reading the owner's alpha, and channel bytes wrap rather
  than clamp.
- Faded particles still draw, and generated lines collapse when they have no
  velocity.
- Electricity uses retail's bend points, ribbon winding and fork width.
- Light particles take the raw tint and an unsigned radius clamp, use the
  default light shader when no material is set, and are never re-added once
  registration fails.

Engine, renderer and game:

- `idDeclTable::TableLookup` returns 1.0 for single-value tables again, as Doom 3
  and Quake 4 do. A missing table defaults to `{ { 0 } }`, and returning
  `values[0]` had frozen envelopes and material stages that name one (the grunt
  blood burst stayed half size).
- `R_AddEffectSurfaces` submits effects farthest first, so equal-sort
  translucent effects overlap in retail order.
- `rvClientEffect` owns its reference sound emitter (SDK 1.4.2). It frees the
  emitter in its destructor, keeps it across effect restarts, and keeps the
  saved handle on restore. `rvBSE::Destroy` no longer stops or frees it.
  - Supersedes the February `Restore` reset and the July move of the free into
    BSE.
  - Now that emitter slots are stable, the reset orphaned the restored emitter,
    so each load stacked another copy of every looping effect sound.
- Manager: `bseStats` and `bseLog` are restored, `bse_showBounds` is an integer
  as in retail, and `bse_scale` is archived.

### Retail quirks kept deliberately

- Emitters and trails pass the absolute birth time as the spawn fraction; only
  spawners pass `i / count`. Retail's linear sampler uses that fraction raw, so
  `linearSpacing` domains in single-spawn segments extrapolate far along their
  line. For example, the `column_fire` emitters in
  `weapons/napalmgun/impact.fx` land well away from the impact, as in retail.
- Colour bytes wrap. `levels/waste/wastesplash.fx` authors a fade of 100.

### Deliberate divergences kept

- The time-based rate limiter, the owner/presentation clock split, per-view
  model rebuilds with portal scissors, the culling and service-budget cvars,
  soft particles and the debug counters.
- `EffectDuration`'s fallback, one-second zero-length sound segments, parser
  recovery and extra keywords, and demo state serialization.
- The white fallback for fully zero owner tints, which protects openQ4 callers
  that leave shader parameters unset.
- Defensive electricity limits:
  - a fallback bolt count;
  - point and step caps;
  - a surface clamp where retail would skip a segment beyond 1 MB of
    vertices.
- Rejection of negative burn-trail times.
- Two unverified details stay as they were:
  - The first `InitLight` places the light with the current effect transform
    rather than the spawn transform (`PresentLight` corrects it a frame later).
  - Model-particle normals and tangents are still rotated.

### Validation

- **Build and tests:** the Windows debugoptimized build is clean.
  `bse_retail_parity.py` passes, and a mutation run confirmed that it fails for
  each of nine reverted pins. The BSE, renderer, savegame and UI contract tests
  that read these files pass. The sound-diversity pin was added on 2026-10-05
  and fails when either sound start reverts to a fixed diversity.
- **Fixed-pose captures:** hangar1 captures used looping `func_fx` entities and
  no input, comparing a pre-change baseline with the candidate.
  - Electric arcs regain their bright forked look.
  - The steam jet is fully developed at 0.3 s.
  - Cylinder-domain smoke forms its intended wall.
- **Save/load:** a looping `effects_arc_loop` probe on OpenAL Soft's null
  backend counted one voice before saving.
  - Before the fix, it counted two voices after one load and three after two.
  - After the fix, it counts one after each load.
- **Multiplayer:** a 60 s six-bot `mp/q4dm1` listen-server match completed
  without failures or BSE warnings.
