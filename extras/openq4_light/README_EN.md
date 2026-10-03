# openQ4 Light — no more pitch-black shadows, and honest AO for Quake 4

A shader pack for [openQ4](https://github.com/themuffinator/openQ4) (the open-source Quake 4 engine):

- **shadows stop being pitch black**: they receive bounce light baked by the openQ4 engine, while the
  shadows cast by lamps stay where they are;
- **GTAO instead of the stock SSAO**: depth in seams, corners and niches without grey noise on flat walls.

Step-by-step guide with pictures: **`GUIDE_EN.pdf`**. Russian version: `README.md`, `GUIDE_RU.pdf`.

## Requirements

- Quake 4 (Steam or GOG) and openQ4 0.13.2 or newer.
- The default openQ4 renderer (OpenGL). The shaders have no effect under Vulkan.
- A GPU with OpenGL 4.5 (anything from roughly 2014 onward).
- Disk space for a page file if you are going to bake lighting (see below).

## What's where

| Folder | Contents | Needed by a regular player? |
|---|---|---|
| `1_PRESETS` | Three ready presets, each one is a single `.pk4` file | **Yes, pick one** |
| `2_BAKE` | Double-click scripts that bake the lighting | **Yes** |
| `3_SINGLE_SHADERS` | The same shaders individually, for experimenting | No |
| `4_SOURCE` | Shader sources and the GPL v3 licence | No |
| `5_DEV` | Depth-buffer capture tool and tests | No |

## Quick start

1. **Bake the lighting** (once, best left overnight). Copy everything from `2_BAKE` into the folder that
   contains `openQ4-client_x64.exe` and run `bake_campaign_full.bat`.
2. **Install a preset.** Copy one `.pk4` from `1_PRESETS` into the `baseoq4` folder next to
   `openQ4-client_x64.exe`.
3. **Apply the settings.** In game, open the console (`~`; if it doesn't open, Ctrl+Alt+`~`) and enter
   the preset's command from the table below once. The settings are saved.

## Presets

| Preset | File | Command | What it does |
|---|---|---|---|
| A — honest | `zz_light_honest.pk4` | `exec light_honest.cfg` | Baked bounce light; AO darkens only that light, not the lamps. The physically correct option. |
| B — full-frame AO | `zz_light_classic.pk4` | `exec light_classic.cfg` | Baked light never darker than a set minimum, plus full-frame GTAO. More depth and contrast. |
| C — simple fill | `zz_light_simple.pk4` | `exec light_simple.cfg` | Even shadow fill without baked light, plus full-frame GTAO. The quick bake is enough. |

Keep **only one** preset in `baseoq4`.

## Baking the lighting

openQ4 only fills shadows on maps that have "light grid" data. Only a few maps ship with it; the rest
have to be baked.

| File | Purpose | Time |
|---|---|---|
| `bake_campaign_full.bat` | Whole campaign, full quality (3 bounces). For presets A and B. | 15–25 min per map, about 10 hours total |
| `bake_campaign_quick.bat` | Whole campaign, minimal quality. Preset C only. | Fast |
| `bake_one_map.bat` | One map at full quality (shows a numbered map list, pick a number) | 15–25 min |

What these scripts do:
- launch the game windowed and at low priority, so you can keep using the PC;
- press a key on the **PRESS ANY KEY TO CONTINUE** screen for you (`bake_watch.ps1`): the bake does
  not start until a key is pressed. If the screen stays up for more than 15 seconds, click the game
  window and press any key;
- open a separate window with bake progress (the game window itself shows "Not Responding" while baking,
  that's normal);
- drop `zzz_bake_helper.pk4` in for the bake and remove it afterwards;
- back up your game settings before the run and restore them after;
- if a map runs out of memory (`Out of memory`), close the game and move on to the next map; at the end
  they list the maps that failed, also saved in `bake_failed.txt`;
- skip maps that are already baked, so a run can be stopped and restarted.

**Important: enlarge the page file.** In openQ4 0.13.2 memory use grows during baking, and with the
default page file the bake fails with `Out of memory`. Set the initial and maximum size **equal**, 131072 MB: Windows doesn't grow the page file
in time, so "32768–131072" doesn't help. You need ~130 GB free (see the
guide). Any drive works, an HDD is fine.

The campaign map list in the `.bat` files was written by hand. If a name doesn't exist, openQ4 prints
`skipping missing map` and moves on to the next map.

## Checking that it works

In the game console:
- `r_lightGridDebug 2` — show only the baked light (`r_lightGridDebug 0` to go back);
- `r_useLightGrid 0` / `r_useLightGrid 1` — turn the baked light off/on to compare;
- `r_ssaoDebug 1` — show only the AO (`0` to go back);
- `path` — list of loaded archives; your preset must appear above `pak0.pk4`.

## Tuning brightness

- `seta r_lightGridIrradianceGamma 0.35` — the difference between outdoors and indoors: lower = smaller
  difference, 1 = as baked. Presets A and B use 0.35.
- `seta r_lightGridIntensity 0.4` — overall bounce-light level. Presets A and B use 0.4.
- Light-coloured models (ships, debris) receive bounce light as if their texture were no brighter than
  0.4 (`kAlbedoCap` in the shader); otherwise they glow against the rest of the scene.

## Uninstalling

Delete the preset's `.pk4` from `baseoq4` and enter `seta r_ssao 0` in the console once.
The baked data can stay; without a preset it changes nothing.

## Troubleshooting

- **The bake doesn't start, the game sits on PRESS ANY KEY**: click the game window and press any key.
  This happens for every map; the `.bat` does it for you, but Windows sometimes won't let it switch to
  the game window.
- **No shadow fill on some map**: the map isn't baked. Try `r_lightGridDebug 1` — if no even grey
  haze covers the scene (black stays black), run `bake_one_map.bat` and pick that map.
- **Some models (ships, rocks) are too bright**: fixed in the presets. If you use older shader versions,
  update them.
- **The game now starts windowed**: older `.bat` versions could leave that behind. In the console:
  `seta r_fullscreen 1`, then `vid_restart`.
- **Lighting looks different after an interrupted bake**: check whether `zzz_bake_helper.pk4` was left in
  `baseoq4` and delete it.
- **Nothing changes at all**: check with `path` that the game sees the archive, and that OpenGL, not
  Vulkan, is selected in the settings.

## Licence

The shaders are modified versions of openQ4's shaders, distributed under the GNU GPL v3 (`4_SOURCE`).
The pack contains no Quake 4 game data.
