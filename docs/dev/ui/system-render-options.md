# SYSTEM render options

The retained SYSTEM page's render options that take effect later than Apply.
Today that is **Preload Light Grids** (`r_lightGridPreload`), which the next
map load uses. The Renderer Fallback row follows in its own increment.

## Preload Light Grids

The row sits under Irradiance Volumes, cloned from that toggle. Its card holds
the label (`#str_42820`), the stock help text (`#str_42821`: smoother area
changes, longer loads, more video memory, applies next map load) and a status
line. Help and status sit inside the card, so focus reveals the whole
explanation, and the plate and focus frame grow around it.

- **Draft.** The toggle proposes `r_lightGridPreload` through the existing
  `edit.r_lightGridPreload` action. Nothing is written until Apply, and the
  `draftLightGridPreload`/`baselineLightGridPreload` aliases tell the draft
  from the applied choice.
- **Apply.** The change completes through the
  [deferred executor](settings-effect-execution.md#deferred-light-grid-executor)
  without a Keep/Revert question. The page reports Applying, Restoring or
  Saving settings while it runs, and a draft that also changes display or
  renderer settings is refused with a notice to apply them separately.
- **Status.** The line is hidden until a map is loaded. It then reads:

  | State | Text |
  | --- | --- |
  | A saved change waits for the next load | `#str_230078` This map keeps the previous light-grid setting until the next map loads. |
  | The loaded map preloaded | `#str_230079` This map preloads its light grids. |
  | The loaded map streams | `#str_230080` This map streams light grids as areas come into view. |
  | The map has no baked light grids | `#str_230081` This map has no baked light grids. |

## Service status

The settings service publishes five owner-only Booleans, declared by the page:
`settings.lightGrid.committed`, `.mapLoaded`, `.consumed`, `.effective` and
`.pending`. They come from the committed preload (an open attempt's baseline
until its choice is saved, as for level loads) and the renderer's latest
light-grid receipt from [render API 20](settings-effect-execution.md#renderer-settings-reports).

A receipt describes the map on screen only when it carries the latest policy
token and that token was issued after the last unload. A receipt from an
earlier load, from a load the service could not answer (token 0, as on a
dedicated server or when the setting cannot be read), or from an earlier
renderer module never counts, and a load that ran without a renderer shows no
status. Editor worlds start empty and publish no receipt. Render-demo playback
is an ordinary load: it takes a fresh token after the unload that starts it,
and its receipt describes the demo's map until the demo stops. `consumed` means the map has light grids
the load set up; `effective` means it preloaded them, including a preload that
left some areas out; `pending` means the committed choice differs from what
the loaded map used.

`tools/ui/update_system_render_options.py` owns the row, its help and status,
the five state declarations, the aliases, the bindings and the feedback
timelines, together with the confirmation title's recovery binding. The row
follows the page's shared editing rule (open, editing, not busy, no
confirmation, discard dialog or unconfirmed numeric draft) and dims to 0.4
otherwise, like Irradiance Volumes. With the row in place
`RETAINED_SYSTEM_MISSING_SETTINGS` no longer lists `r_lightGridPreload`.

## Qualification

- `tools/tests/ui_settings_service.py` drives the status through a session:
  no map, a load in progress, a streamed map, an attempt not yet saved, a saved
  preload waiting for the next map, an unload, the next load, a stale token, a
  map without baked grids, a load without a renderer, an incomplete preload and
  another owner.
- `tools/tests/native/UiSystemRenderOptionsTest.cpp` loads the production page
  with every SYSTEM test locale at normal and 40% wider glyphs. It checks the
  exact proposal with no write, the aliases, each status text and its
  visibility, the recovery title, and that the label, help, status lines and
  the deferred status messages fit at 1280x720 and 640x480, at 100% and 200%
  density, with the focused card revealed inside the body.
- SP map loads of `game/airdefense2` on OpenGL and Vulkan opened the page
  in game, toggled the row, applied, and reloaded the map with console verbs
  only. Both logged the edit and apply, the schema-2 journal going Pending then
  Confirmed, the deferred observation and the controller returning to idle,
  then `preload 1, token 2, preloaded, 29/29 areas resident` on the reload.
  The journal was removed and the configuration archived
  `seta r_lightGridPreload "1"`. Engine screenshots show the status reading
  streams, then waits for the next map, then preloads.

Evidence: `.tmp/ui/system-render-options/validation-evidence.json`, SHA-256
`092fe0eb98ffc56f6dc38fc2141b6bbe302f9620c37c1798ed9395e753f6b237`.

This evidence covers the Preload Light Grids row only. The remaining SYSTEM
rows, the editor round trip and the full platform, display and input matrix
stay open.
