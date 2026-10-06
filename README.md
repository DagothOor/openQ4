<a id="top"></a>

<div align="center">

<img src="assets/docs/img/banner.png" alt="openQ4 banner">

[![Licensing: GPL engine and SDK game code](https://img.shields.io/badge/Licensing-GPL%20engine%20%7C%20SDK%20game%20code-blue.svg)](LICENSING.md)
[![Status](https://img.shields.io/badge/status-Beta%20Development-d97a1f.svg)](https://github.com/themuffinator/openQ4/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS%20preview-lightgrey.svg)](https://github.com/themuffinator/openQ4)
[![Architecture](https://img.shields.io/badge/arch-x64%20%7C%20ARM64-orange.svg)](https://github.com/themuffinator/openQ4)

**Play Quake 4 on modern systems with an open-source engine and SDK-licensed game-code replacement built around the original retail assets.**

<a href="https://github.com/themuffinator/openQ4/releases">
  <img src="https://img.shields.io/badge/Download-Latest%20Release-2d8f4e?style=for-the-badge&logo=github" alt="Download the latest openQ4 release">
</a>
<a href="https://github.com/themuffinator/openQ4/stargazers">
  <img src="https://img.shields.io/github/stars/themuffinator/openQ4?style=for-the-badge&logo=github&label=Star%20on%20GitHub" alt="Star openQ4 on GitHub">
</a>
<a href="https://github.com/themuffinator/openQ4/fork">
  <img src="https://img.shields.io/github/forks/themuffinator/openQ4?style=for-the-badge&logo=github&label=Fork%20on%20GitHub" alt="Fork openQ4 on GitHub">
</a>

<a href="https://discord.gg/T32mFejwR4">
  <img src="https://img.shields.io/badge/Join%20the-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join the openQ4 Discord server">
</a>

[Get Started](#getting-started) | [Features](#features) | [Player Guides](#player-guides) | [Build from Source](BUILDING.md) | [Technical Reference](TECHNICAL.md)

</div>

---

<p align="center">
  <img src="assets/docs/img/readme-airdefense1-cinematic.png" alt="openQ4 airdefense1 intro cinematic showing ships approaching Stroggos" width="92%">
</p>

## What is openQ4?

**openQ4** replaces the Quake 4 engine and game binaries with a GPL-covered engine and SDK-licensed, source-available game modules. It keeps the original game playable on modern PCs while improving visuals, audio, controls and everyday usability.

It is for players who want the original Quake 4 experience on today's hardware.

> [!NOTE]
> openQ4 does **not** include Quake 4 assets. You still need a legitimate Quake 4 copy from Steam or GOG.

---

## Features

- **Built for modern displays.** Widescreen, ultrawide, multi-monitor, borderless and fullscreen setups all work. On 144 Hz and 240 Hz screens the camera, weapons and moving objects are drawn smoothly between the game's 60 Hz ticks, while gameplay, networking, demos and saves keep their original timing.
- **Optional visual upgrades.** Bloom, HDR, anti-aliasing, soft particles, baked light grids, cel shading, a CRT filter and cleaner [shadow maps](docs/user/shadow-mapping.md), each one switchable.
- **A modern interface, still growing.** The title screen, pause menu and loading screens are rebuilt as sharp, scalable screens; the other menus keep the classic look for now. If a modern screen can't be shown, for example because a mod brings its own main menu, the classic one appears instead. Prefer the classic screens throughout? See [Modern and classic screens](docs/user/client-settings.md#modern-and-classic-screens).
- **Real liquids.** Wade, swim and drown in water, take damage in slime and lava, with underwater visuals and audio. Retail Quake 4 has no liquids, so they appear in maps built for them; see the [Liquids guide](docs/user/liquids.md).
- **Rich, reliable audio** through OpenAL: Quake 4's room reverb, 3D headphone audio and your device's own speaker layout. macOS packages bundle their own, so there is nothing extra to install; see [Gameplay Settings](docs/user/gameplay-settings.md#audio-quality).
- **Controller support and quality-of-life fixes**, including a better console and modern settings behaviour.
- **Play in VR** (experimental). With a PC VR headset, play the campaign or multiplayer in stereo: look around with your head, aim with a motion controller, and get menus and cinematics on a floating screen. See the [VR guide](docs/user/vr.md).
- **Play in your language.** Menus and game text in English, French, German, Italian, Spanish, Brazilian Portuguese, Czech, Hungarian, Turkish and Ukrainian, plus Polish and Russian menus. Choose one in Settings > Game Options > Language; see the [languages guide](docs/user/languages.md).
- **More single-player.** Alongside the original campaign there is an experimental [Arena Campaign](docs/user/arena-campaign.md): bot matches across five tiers of the stock maps, with boss matches and saved progress. **The Awakening** campaign is available too if you supply its content.
- **Better multiplayer** (experimental): a server browser with sorting, filters and favourites, bots with team objectives and personalities, readable chat with history, Duel queues and spectator match controls.
- **A demo library and player** with pause, speed, stepping, rewind and fast-forward, plus free-fly playback of full-match recordings.
- **Single-player and multiplayer in one install** on Windows, Linux, Steam Deck and macOS.
- **Physically based materials for mods.** Maps and mods can ship PBR materials, with metalness, roughness, ambient occlusion, normal maps and glow, that render on OpenGL and Vulkan beside the stock surfaces, lit and shadowed by every light. Stock content looks exactly as before. See the [PBR materials guide](docs/user/pbr-materials.md).
- **Renderer previews**, all off by default: a Vulkan renderer (a preview on Windows), [temporal anti-aliasing and dynamic resolution](docs/user/temporal-presentation.md), and [volumetrics, reflections and indirect light](docs/user/advanced-screen-space-lighting.md).

See the [Releases page](https://github.com/themuffinator/openQ4/releases) for what changed in each version.

---

## Screenshots

<p align="center">
  <img src="assets/docs/img/readme-bloom-hdr.png" alt="openQ4 bloom and HDR side-by-side comparison on mp q4dm2" width="92%">
</p>
<p align="center"><sub>Bloom and HDR on mp/q4dm2: normal rendering on the left, enhanced post-processing on the right.</sub></p>

<p align="center">
  <img src="assets/docs/img/readme-lightgrid.png" alt="openQ4 light-grid indirect diffuse off and on comparison" width="92%">
</p>
<p align="center"><sub>Baked light-grid lighting on mp/q4dm2, off and on.</sub></p>

<p align="center">
  <img src="assets/docs/img/readme-crt.png" alt="openQ4 CRT post-process off and on comparison on mp q4dm8" width="92%">
</p>
<p align="center"><sub>The CRT filter on mp/q4dm8, off and on.</sub></p>

> [!TIP]
> **OpenGL is the default and recommended renderer on every platform.** Vulkan is a preview on Windows and experimental on Linux and macOS: set `r_renderApi vulkan` and restart to try it. If Vulkan can't start, openQ4 switches back to OpenGL automatically. On macOS, Vulkan runs through the bundled MoltenVK translation layer. See [Display Settings → Renderer Backend](docs/user/display-settings.md#renderer-backend-opengl-default-vulkan-preview-on-windows).

---

## System requirements

You need a legitimate Quake 4 install plus the openQ4 package that matches your operating system and CPU architecture.

| Tier | Practical target |
|---|---|
| **Minimum** | 64-bit CPU, 4 GB RAM, a working OpenGL compatibility driver with ARB2-era vertex/fragment program support, and about 12 GB free for the openQ4 package plus retail Quake 4 assets. Use the `minimum` or `lowpower` performance preset on constrained systems. |
| **Recommended** | Modern quad-core CPU, 8 GB RAM, OpenGL 4.1+ compatibility-class GPU with 2 GB+ VRAM, current graphics drivers, and 15 GB+ free. For high resolutions, `quality`, or `ultra`, 16 GB RAM and 6 GB+ VRAM gives much better headroom. |

Packages are available for Windows x64, Linux x64 and Steam Deck/SteamOS, with preview Linux ARM64, preview Apple Silicon/arm64 macOS and experimental Windows ARM64 builds:

- **Linux** ships as directly executable AppImages and archives for `x86_64` and `aarch64`. Linux ARM64 needs a desktop OpenGL compatibility driver.
- **macOS** downloads are unsigned OpenGL/Metal bridge packages, and players have run them only on current macOS.
- **Windows ARM64** packages are built but have not yet been confirmed to run on real hardware.

See [Getting Started](docs/user/getting-started.md#system-requirements) for platform details.

---

## Getting started

1. Install **Quake 4** from [Steam](https://store.steampowered.com/app/2210/Quake_4/) or [GOG](https://www.gog.com/en/game/quake_4).
2. Download the latest openQ4 build from the [Releases page](https://github.com/themuffinator/openQ4/releases).
3. On Linux, make the matching `x86_64` or `aarch64` AppImage executable and launch it; for an extracted archive, launch `openQ4-client_<arch>` (or `openQ4-steamdeck` on Steam Deck).
4. If openQ4 does not find your Quake 4 install automatically, follow the path setup notes in the [Getting Started guide](docs/user/getting-started.md).

When upgrading, replace the whole openQ4 package rather than individual files.

---

## Player guides

### Start here

- [Getting Started](docs/user/getting-started.md) - system requirements, installation, first launch, and common setup questions
- [Campaigns](docs/user/campaigns.md) - choosing Quake 4 or The Awakening, installing expansion content, and separate saves
- [The Awakening](docs/user/awakening.md) - what openQ4 fixes and changes in the expansion's campaign
- [Client Settings Guide](docs/user/client-settings.md) - where to find the most useful in-game settings
- [Server Setup Guide](docs/user/server-setup.md) - dedicated server setup and common server variables
- [Server and Remote-Console Security](docs/user/server-security.md) - secure remote console and password handling

### Play and tune

- [Display Settings](docs/user/display-settings.md) - fullscreen, windowed mode, resolution scale, multi-monitor, and renderer choice
- [Input Settings](docs/user/input-settings.md) - keyboard, mouse, controller, and bindings
- [Gameplay Settings](docs/user/gameplay-settings.md) - gameplay and audio options
- [Arena Campaign](docs/user/arena-campaign.md) (experimental) - tiers, unlocks, maps, game types, and bots
- [Steam Deck](docs/user/steam-deck.md) - launcher, controls, and handheld notes
- [Virtual Reality](docs/user/vr.md) (experimental) - headsets, controller layout, comfort settings, and troubleshooting
- [Multiplayer Networking](docs/user/multiplayer-networking.md) (experimental) - connection tuning and lag compensation
- [Multiplayer Chat](docs/user/multiplayer-chat.md) - chat controls, history, and layout
- [Competitive Matches](docs/user/competitive-matches.md) (experimental) - match rules, voting, readiness, rounds, and One Flag
- [Demo Library and Multi-View Demos](docs/user/multiview-demos.md) - browsing, playback controls, and recording full matches
- [Shadow Mapping](docs/user/shadow-mapping.md) - shadow-map options, flashlight shadows, and troubleshooting
- [Light Grids](docs/user/light-grids.md) - baked indirect lighting
- [Classic Dynamic Lights](docs/user/classic-dynamic-lights.md) - Quake II/III style lights on muzzle flashes, projectiles, and explosions
- [Cel Shading](docs/user/cel-shading.md) - the cel-shaded look
- [Temporal AA and Dynamic Resolution](docs/user/temporal-presentation.md) (experimental) - temporal anti-aliasing, upscaling, and automatic resolution scaling
- [Advanced Screen-Space Lighting](docs/user/advanced-screen-space-lighting.md) (experimental) - volumetrics, reflections, and indirect light
- [PBR Materials](docs/user/pbr-materials.md) - authoring physically based materials and how they are lit
- [DDS Texture Replacements](docs/user/texture-replacements.md) - installing texture packs
- [Level-Load Cache](docs/user/level-load-cache.md) (experimental) - optional local load caches, and how to clear them

### Mapping and modding

- [Liquids](docs/user/liquids.md) - water, slime, and lava behaviour, and how to add them to maps
- [Map Entity Strings](docs/user/map-entity-strings.md) - replace or extend a map's entities without editing the map
- [Experimental Level Editor](docs/user/level-editor.md) - the new editor workspace alongside the classic Radiant

---

## Compatibility

- openQ4 targets the **official Quake 4 retail assets** and ships its **own engine and game modules**.
- It is **not** a drop-in runtime for mods built on the original proprietary Quake 4 game DLLs.
- **Quake 4: The Awakening** single-player is available from **Single Player → Campaign** once you supply its content, which is not included. It is unfinished alpha content, and its multiplayer changes are not supported. See the [campaign guide](docs/user/campaigns.md).
- The project is in **beta development**, so compatibility work is ongoing.

## Reporting problems

Please use the [issue tracker](https://github.com/themuffinator/openQ4/issues) and include crash logs or setup details when you can. For macOS crashes, follow the [macOS support-data guide](docs/user/macos-support-data.md) first. Windows ARM64 and Linux ARM64 have their own issue templates; a report that everything simply worked is as useful there as a bug.

---

## Contributing

Bug reports, compatibility reports, testing feedback, and code contributions are all welcome. To build openQ4 yourself, start with [BUILDING.md](BUILDING.md); for project conventions, see [CONTRIBUTING.md](.github/CONTRIBUTING.md).

Developers can also find advanced configuration and file layout in [TECHNICAL.md](TECHNICAL.md), experimental Android builds in [Android, GLES and SigmaTouch](docs/dev/android-build.md), and the current implemented/experimental/missing status of every subsystem in the [engine capability matrix](docs/dev/engine-capability-matrix.md).

---

## Credits

- **themuffinator** - openQ4 development and maintenance
- **[Emile Belanger (emileb)](https://github.com/emileb)** - contributor and original author of the Android port, SigmaTouch integration, OpenGL ES 3.0 renderer, GLES shader variants, ETC2/EAC compression, and associated mobile memory/loading work. This integration builds on his [Android branch](https://github.com/emileb/openQ4/tree/android) and [GLES shader-variants branch](https://github.com/emileb/openQ4/tree/gles-shader-variants); see the [contribution and adaptation record](docs/dev/android-gles-integration.md).
- **DarkMatter Productions** - project stewardship and website
- **[The RmlUi Team, CodePoint, Shift Technology and contributors](https://github.com/mikke89/RmlUi/tree/6.3)** - MIT-licensed layout library behind the new interface, with [openQ4 patches](subprojects/packagefiles/rmlui/README.openq4.md); [licence notice](docs/licenses/RmlUi.txt)
- **[Baptiste Lepilleur and the JsonCpp authors](https://github.com/open-source-parsers/jsoncpp/tree/1.9.6)** - JSON parser for the new interface's source files, used under its MIT option with an [openQ4 patch](subprojects/packagefiles/jsoncpp/subnormal-numbers.patch); [licence notice](docs/licenses/JsonCpp.txt)
- **[Mikko Mononen, Eric Veach and the libtess2 contributors](https://github.com/memononen/libtess2/tree/8dbd6483e920311a58c9af10a10beb278efebc36)** - SGI-B-2.0 polygon tessellator for the new interface's vector shapes, with an [openQ4 precision patch](subprojects/packagefiles/libtess2/double-precision.patch); [licence notice](docs/licenses/libtess2.txt)
- **[Q2REX Project Team](https://github.com/themuffinator/Q2REX)** - design reference for the [multiplayer chat panel](docs/user/multiplayer-chat.md)
- **[MuffMode](https://github.com/themuffinator/MuffMode)** and **[Q4MAX](https://www.moddb.com/mods/q4max)** - multiplayer workflow and usability references
- **[Team Beef](https://github.com/Team-Beef-Studios)** - design reference for [VR mode](docs/user/vr.md): [PreyVR](https://github.com/Team-Beef-Studios/PreyVR) (Luboš Vonásek, GLKarin, DrBeef, Baggyg, Bummser and contributors) and [Doom3Quest](https://github.com/DrBeef/Doom3Quest) (DrBeef and contributors) shaped its head-driven movement, two-handed aim, zoom, comfort options and physical crouch; ideas only, no code copied
- **Justin Marshall** - Quake4Doom and early BSE reverse engineering reference work, and recovering and publishing Quake 4: The Awakening
- **Robert Beckebans** - renderer modernization reference work, including RBDOOM-3-BFG inspiration
- **id Software's official Doom 3 and Doom 3 BFG source releases** - retained idTech 4 source lineage; see the [source provenance inventory](docs/dev/source-provenance.md)
- **id Software** and **Raven Software** - Quake 4 and the underlying technology
- **Raven Software** and **Ritual Entertainment** - Quake 4: The Awakening, the unreleased expansion whose single-player campaign openQ4 can run
- **Chris Robinson and the [OpenAL Soft](https://openal-soft.org/) contributors** - cross-platform OpenAL runtime bundled in macOS packages
- **The Khronos Group and [glslang contributors](https://github.com/KhronosGroup/glslang/tree/15.1.0)** - GLSL-to-SPIR-V compiler used by the Vulkan renderer; its complete licence ships under `licenses/`
- **[The Khronos Group, Valve Corporation and LunarG](https://github.com/KhronosGroup/OpenXR-SDK/tree/release-1.1.63)** - Apache-2.0 OpenXR loader and headers behind [VR mode](docs/user/vr.md); [licence notice](docs/licenses/openxr-sdk.txt)
- **[The Khronos Group](https://github.com/KhronosGroup/OpenGL-Registry)** - MIT-licensed OpenGL ES API headers, with their original notices retained
- **akacross** (Discord user) - Thorough playtesting on Linux and Windows, a huge help moving the project forward!

---

## License and disclaimer

openQ4 engine code is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0). See [LICENSE](LICENSE) for details. Files retaining Doom 3 or Doom 3 BFG Edition headers also retain their upstream notices and are accompanied by the corresponding published Additional Terms; the [source-provenance inventory](docs/dev/source-provenance.md) records their scope, pinned audit references, and intermediate lineage without offering a legal conclusion.

The game-library code in [`src/game`](src/game/) and [`src/mpgame`](src/mpgame/) is derived from the Quake 4 SDK and remains subject to [id Software's SDK EULA](LICENSES/QUAKE-4-SDK-EULA.rtf). [LICENSING.md](LICENSING.md) distinguishes component terms and the unresolved linked-distribution licensing question. Quake 4 assets remain the property of id Software and ZeniMax Media.

openQ4 is an independent project and is not affiliated with, endorsed by, or sponsored by id Software, Raven Software, Bethesda, or ZeniMax Media.

---

[Website](https://www.darkmatter-quake.com) | [Repository](https://github.com/themuffinator/openQ4) | [Game Sources](src/game/) | [Issues](https://github.com/themuffinator/openQ4/issues) | [Releases](https://github.com/themuffinator/openQ4/releases)

[Back to Top](#top)
