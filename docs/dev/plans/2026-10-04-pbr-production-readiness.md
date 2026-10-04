# PBR production readiness

Status: in progress (started 2026-10-04).

This plan takes the authored PBR material path from a qualified laboratory
feature to a production feature. Production means that a mod author can ship
dual-authored PBR materials, a player sees them rendered as PBR in ordinary
gameplay on the default renderer, stock content renders exactly as before, and
every material channel reaches every lighting term it should on both backends.
The earlier work and its evidence are in the
[September audit](2026-09-20-pbr-rendering-audit.md) and the
[original plan](2026-05-19-pbr-material-support.md).

## Gap audit (2026-10-04)

The audit traced every PBR input through both backends. Each row names the gap,
the decision and the stage that closes it.

| ID | Gap | Decision | Stage |
|---|---|---|---|
| G1 | Single-scattering GGX loses up to 69% of a rough white conductor's energy (1 - ln 2 at roughness 1). Rough metals rendered far too dark on both backends. | Multiple-scattering energy compensation on every specular lobe, direct and environment. | A |
| G2a | Authored ambient lights ignored material AO on both backends, although they stand in for bounced light. | Ambient-light diffuse takes the same multi-bounce AO as environment diffuse. | A |
| G2b | Environment specular was multiplied by raw AO, darkening smooth head-on reflections as much as rough ones. | Specular occlusion from AO, NoV and roughness. | A |
| G2c | Raw AO over-darkened bright occluded albedo. | Multi-bounce AO on diffuse (by albedo) and specular (by F0). | A |
| G2d | Normal maps could send reflections below the geometric surface. | Horizon occlusion against the interpolated vertex normal. | A |
| G2e | SSAO multiplies the whole lit frame, direct light included, and ignores material AO. On Vulkan it also disables the linear PBR scene and drops the environment pass of baked receivers. | SSAO attenuates PBR indirect light only, combined with material AO. | D |
| G3a | Without the filtered atlas, GL's analytic environment ignored roughness and the split-sum table. | Roughness-convolved analytic lobe and an analytic split-sum fallback. | A |
| G3b | GL's deferred `r_pbrDebug 4` showed filtered roughness, forward showed authored roughness. | Both show authored roughness. | A |
| G4 | OpenGL, the default renderer, draws PBR only when a whole frame qualifies for the modern visible path. That needs six developer cvars, and any weapon, stock specular material, ambient light or stencil shadow sends the frame back to classic. Ordinary gameplay never shows PBR on GL. | Per-surface native PBR inside the classic GL light loop, mirroring native Vulkan. | B |
| G5 | Presentation: HDR-off PBR radiance is added to the display domain without the sRGB transfer, and Vulkan's HDR scene linearizes and filmic-maps every view once `r_pbrMaterials` is on, changing stock frames. | Production composite in the classic display domain on both native backends. Stock pixels stay unchanged, and the tone curve does not depend on whether PBR is in view. | C |
| G6 | Environment lighting in real maps: without authored probes every PBR surface reflects the analytic studio sky, even in dark interiors. | To be decided after G4/G5 measurements. | E |
| G7 | Defaults and UX: `r_pbrMaterials` defaults to 0, GL needs the non-archived `r_rendererModernVisible`, and there is no menu control. | Promote after G4/G5/G6, with menu control and docs. | F |

## Stage A: complete roughness and AO shading (both backends)

The shared kernel (`src/renderer/PBRMath.h`) gains five numerically tested
functions, embedded in OpenGL's modern shaders and included by Vulkan's:

- `PBRSpecularAlbedo(NoV, r)`: the directional albedo E of the
  single-scattering lobe with F = 1, the A + B of the split-sum table. It is a
  15-term fit in r and sqrt(NoV), over NoV in [0.1, 1] and the shading
  roughness range. 1/E is within 2.5% of the integrated table.
- `PBREnergyCompensation(f0, E)`: `1 + f0 (1/E - 1)`. A compensated white
  furnace lands in [0.975, 1.023]; no F0 gains energy beyond that bound.
- `PBRSpecularOcclusion(NoV, ao, r)`: Lagarde and de Rousiers (2014).
  AO 1 is unoccluded, AO 0 fully occluded, and rough lobes follow AO.
- `PBRMultiBounceAO(v, albedo)`: Jimenez et al. (2016), bounded to [v, 1].
- `PBRHorizonOcclusion(dot(R, Ngeom))`.

Direct lights (point and projected) apply the energy compensation and stay
AO-free. The environment pass uses the split-sum table's A + B where it is
bound, and the fit elsewhere (Vulkan's per-light passes bind no table).

Evidence: `tools/tests/native/PBRMathTest.cpp` and
`tools/tests/renderer_pbr_materials.py`
(`test_pbr_energy_and_occlusion_contract`); laboratory runs below.

### Vulkan rough-reflection regression found by the audit

The paired IBL comparison failed `rough-high` and `double` on HEAD, before
any Stage A change. OpenGL's specimen values still matched the retained v7
qualification exactly (rough metal mean 4.518), while Vulkan had drifted
(4.252) and showed a crisp key-light rim on a roughness-1 metal. The cause was
c850233d (2026-09-25): explicit `TF_LINEAR` samplers now clamp to the base
level to match `GL_LINEAR`. The PBR environment atlas is `TF_LINEAR` and reads
its prefiltered levels with explicit `textureLod`, so every rough Vulkan
reflection and authored probe sampled the mirror level. The atlas now has a
sampler that keeps the chain (`VK_Image_UseExplicitMipChain`), and
`test_vulkan_environment_mip_chain_sampler` pins it. The regression never
reached a tagged release; v0.13.2 predates c850233d.

### Stage A laboratory evidence (2026-10-04)

Private build `+g632d66b1.dirty` (HEAD plus Stage A only), Windows/NVIDIA,
runtime `.tmp/wt-pbr/.tmp/lab-b` (Stage A) against `.tmp/wt-pbr/.tmp/lab-base`
(HEAD renderer modules in the same package).

| Suite | Result |
|---|---|
| Native math (`openq4-pbr-math`) | pass, including 21x19 fit/furnace grid and occlusion invariants |
| GL core (`lit,ownership,no-probes,direct,legacy,master-off`) | 6/6 |
| Vulkan direct suite, 0x | 68/68; A/B against HEAD changes only `rough-high`/`aa-rough` (max +29 bytes, 2.6% of pixels) |
| Vulkan ambient lights, 0x | 41/41; independent oracle with multi-bounce AO passes within 1.1 bytes, `ao-zero` black |
| IBL suites, 0x | Vulkan 27/27, GL 26/26; GL/Vulkan parity exact on all 26 paired controls (HEAD: 2 failures) |
| IBL suites, 4x | Vulkan 27/27, GL 26/26; parity maximum 1 byte |
| Probes, 0x | Vulkan 46/46, GL 40/40; probe proof and GL/Vulkan parity pass |
| Transparency / cutout / fog / capacity / resources | 25/25, pass, 7/7, 18/18, 44/44 |
| Geometry | 11/11 per backend; parity pass |
| Baked lighting | GL 6/6; native baked composition passes |
| Diagnostics | 62/62 per backend; paired whole-frame comparison keeps its documented mapped-normal and cutout-boundary failures, identical on HEAD |

The IBL A/B against HEAD isolates each term: the roughness-1 metal gains up to
76 bytes from energy compensation, AO-0.75 specimens up to 5 bytes from
multi-bounce and specular occlusion, normal-mapped specimens lose up to 9 bytes
at grazing reflections from horizon occlusion, and `ao-zero` stays black.
