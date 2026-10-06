# Audio Modernization (2026-10-06)

This records how openQ4's audio compares with the id Tech 5 and id Tech 6 generation, what
changed in the 2026-10-06 audio pass, the evidence behind each change, and what is
deliberately left for later. The retail parity work that came before it is in
[retail-audio-reverb.md](retail-audio-reverb.md).

## Where openQ4 starts from

openQ4's sound core is the Doom 3 BFG Edition sound system (`snd_world.cpp`,
`snd_emitter.cpp`, `SoundVoice.cpp`; the files keep the BFG GPL header). BFG carried the id
Tech 5-era design: emitter channels sorted by volume into a fixed voice budget with a
cushion fade (`s_maxEmitterChannels`, `s_cushionFade*`), sound classes and fades, and an
XAudio2 mixer that blended a voice toward every speaker inside its inner radius. Robert
Beckebans' RBDOOM-3-BFG replaced XAudio2 with OpenAL (`src/sound/OpenAL`); openQ4 runs on
OpenAL Soft 1.25 and adds Quake 4's retail behaviour on top: the per-area EFX reverb, EAX
occlusion, portal spatialization and Quake 4's volume rules.

id Tech 6 games moved audio to middleware: DOOM (2016) is listed among Audiokinetic Wwise
titles, and its shipped audio is Wwise-encoded. The comparison below is with the class of
features such a pipeline provides (distance filtering, source spread, voice virtualization,
a protected master bus, streaming), not with any one game's tuning, which is not public.

## Comparison

| Area | id Tech 5 (BFG) | id Tech 6-class middleware | openQ4 before | openQ4 now |
| --- | --- | --- | --- | --- |
| Close sources | Blend to omni inside the inner radius | Spread / focus by distance | Hard point panning; the inner radius was stored but never applied | `AL_SOURCE_RADIUS` from `minDistance` (`s_sourceRadiusScale`) |
| Unpositioned sounds | Equal to every speaker | Non-spatialized | Rendered as a point straight ahead | Full spread around the listener |
| Stereo and music | Straight to left and right | Non-diegetic bus | Virtual speakers, so through HRTF on headphones | Direct channels (`s_directStereo`) |
| Speaker layout and HRTF | XAudio2 device channels | Endpoint layout, binaural option | 5.1 forced everywhere; `s_openALHRTF 1` ignored | Device layout by default; HRTF preference honoured; reopen keeps both |
| Resampling | XAudio2 SRC | High-quality SRC | OpenAL Soft cubic spline | 11th order sinc (`s_resampler`) |
| Master bus | XAudio2 mastering voice | Limiter / HDR | No limiter on float devices | OpenAL Soft limiter (`s_outputLimiter`) |
| Distance filtering | None | Attenuation low-pass | None | Air absorption from the room preset (`s_airAbsorption`) |
| Gain headroom | Unclamped sounds above unity | Bus headroom | Clamped to 1 by `AL_MAX_GAIN` | 16x headroom |
| Device loss | n/a (console first) | Device handling | Static voices stayed stopped after a reopen | Stopped voices restart at their offset |
| Shakes and rumble | Amplitude data | Meter / RTPC | Game query returned 0; amplitude stubbed at 1 | `shakeData` envelope, else the measured sample envelope |
| Sample residency | Purged per level | Streaming banks | Every map's PCM kept for the session | Doom 3 purge rules restored |
| Sample decode | Offline-encoded, loaded per level | Asynchronous loading | Decoded on the main thread as each shader parsed | Decoded on job workers during the level load (`s_asyncSampleDecode`) |
| Per-voice update cost | One matrix per voice | Batched | Filters and sends re-sent by every setter (5-6 times a frame) | Once a frame (`CommitMix`) |

## What changed

### Spatial

- **Source size.** `idSoundChannel::UpdateHardware` passes each sound's `minDistance` as the
  voice's inner radius, which only BFG's unused `CalculateSurround` read. The OpenAL voice now
  sends `minDistance * s_sourceRadiusScale` (default 0.5) as `AL_SOURCE_RADIUS`. OpenAL Soft
  spreads a source over the arc it subtends and over the whole sphere inside it; at half of
  `minDistance` the directional part follows BFG's linear blend to omni to within about 0.12
  up to `minDistance`, and becomes a point source beyond it.
- **Sounds at the listener.** Global, omnidirectional and listener-owned voices sit at the
  origin. With no radius OpenAL Soft renders that as a point straight ahead (front-centre on
  5.1, the frontal HRTF on headphones). Such voices always get a radius, so they surround.
- **Direct stereo.** Multichannel voices set `AL_DIRECT_CHANNELS_SOFT` (with
  `AL_REMIX_UNMATCHED_SOFT` where available). Rendered through OpenAL Soft's wave backend with
  HRTF forced on, the main-menu music measured an L/R correlation of 0.95 and lost about 5 dB
  through virtual speakers, against 0.68 with direct channels, which matches the source.
  Without HRTF the two paths measure the same.

### Device

- **One attribute list.** `openQ4_BuildDeviceAttributes` carries the HRTF preference, the
  output mode and the limiter, and is used by `alcCreateContext`, `alcReopenDeviceSOFT` and the
  checked settings reset. The old HRTF reset ran before the context existed, and context
  creation rebuilt the device without it: `s_openALHRTF 1` still reported HRTF enabled on
  headphones. It now reports "disabled, basic stereo". A hot-plug reopen passed no attributes
  and dropped the layout.
- **Output limiter.** OpenAL Soft's log showed "Output limiter disabled" on a Float32
  shared-mode WASAPI device; it now asks for `ALC_OUTPUT_LIMITER_SOFT` (`s_outputLimiter`).
- **Resampler.** 4,762 of the 5,737 stock sounds are 22.05 kHz, so nearly every voice is
  upsampled about 2.2x. `s_resampler auto` picks the runtime's "11th order Sinc"; `default`
  keeps OpenAL Soft's own (cubic spline in 1.25); `listResamplers` lists them.
- **Units.** `AL_SPEED_OF_SOUND` is set in game units (343.3 / 0.0254). Stock content uses no
  Doppler, but a `useDoppler` sound faster than about 9 m/s would have run away in pitch.
- **Headroom.** `AL_MAX_GAIN` is raised to the voice's 16x ceiling. 57 stock map speakers are
  authored `s_unclamped` at +1 to +12 dB and were flattened to unity.

### Mixing and timing

- **Recycled channels.** `idBlockAlloc` hands back channels without constructing them, and
  `StartSound` did not reset the fade. After a map script faded a sound to -80 dB and removed
  it (11 stock map scripts, among them hangar1, hub1, tram1, walker and putra), the next sound to get that
  channel played silent. `AllocSoundChannel` now resets the channel.
- **Slow motion.** The weapon wheel runs the game at 0.18x and the voices pitch down with it,
  but channel completion ran on wall-clock time, so a line of dialogue stopped about a third of
  the way in. The channel clock now integrates the voice's whole playback rate, shared with the
  pitch (`SoundChannelPlaybackRate`). Music keeps its tempo through slow motion.
- **Silent dialogue.** Voice-over cannot be muted without losing its lip sync, and a silent
  unmutable channel was skipped by the update, so it kept playing at its last gain: on through
  alt-tab with `s_muteUnfocused 1`, and through a door that had just closed. Such channels now
  update at zero gain.
- **Inferred VO.** The BFG rule that marks `sound/vo/` and `sound/guis/` shaders as voice-over
  also set retail's `SSF_IS_VO`, which retail reserves for lip-synced speech and which skips
  `s_speakerFraction`. Map speakers playing VO were 3.7 dB louder than retail. Only openQ4's own
  `SSF_VO` is inferred now.
- **no_dups.** Retail's fixed channel slots kept a finished sound's sample, so `no_dups` also
  skipped the variant that had just ended. Each emitter now remembers its last eight starts.
- **Cushion fade.** `s_cushionFadeRate` is applied per second of sound time instead of per
  1/60 s update, which ran four times too fast at 240 fps.
- **Global channels at range.** An emitter beyond the `maxDistance` of its positional channels
  returned before updating its global channels too; they play at any distance.
- **One commit per frame.** The OpenAL voice's mix setters only record their value and
  `CommitMix` sends the filters and sends once a frame. It still runs every frame, so the
  sends follow the listener's reverb slot between areas.

### Shakes, rumble and sound-driven lights

`idSoundSystem::CurrentShakeAmplitudeForPosition`, which `idPlayerView::CalculateShake` and
`idEarthQuake` call, returned 0. It now returns the game world's shake sum. A channel's
amplitude comes from its shader's `shakeData` (Raven's 30 Hz letter envelope, already read for
lights) or else from a 60 Hz peak envelope measured from the PCM at upload, since no `.amp`
files ship. Shake strength uses the sound's volume before `s_volume`, as retail did. The stock
`airdefense_cannon_fire` (`shakes 1`) peaks at 0.91 and decays along its envelope;
`s_showVoices 1` prints the shake and rumble totals.

### Memory and loading

- **Level purge.** `LoadSample` marked every sample never-purge. It now follows Doom 3's sound
  cache: samples first referenced outside a level load stay resident, `BeginLevelLoad` clears
  the level marks without freeing, `EndLevelLoad` frees what the new level did not reference,
  and a purged sample reloads when referenced again. `airdefense1` then `airdefense2` held 233
  MB of PCM and now hold 121 MB after "582 sound samples from earlier levels freed (111.8 MB)".
  `s_restart` reloads only the resident set.
- **Decode on the job workers.** During a level load `LoadSample` reads and opens each Ogg on
  the main thread, which fixes the sample's length, rate and channels at once, and a
  low-priority job decodes the PCM while the rest of the level loads. Whatever reads the PCM
  first waits for it (`FinishDecode` from the upload, `FreeData` and `EnsureCpuPayload`), and
  `EndLevelLoad` uploads the rest. At most 48 decodes are outstanding; beyond that, and with
  `jobs_enable 0`, the main thread decodes as before. A failed decode takes the normal
  synchronous probe, so fallbacks to other variants and the default are unchanged.
  The main thread only reads the file and the page headers: the channels and rate from the
  identification header and the length from the end-of-stream granule
  (`SoundSample_PeekOggInfo`, which matches stb_vorbis on all 5,690 stock files); the job opens
  the stream and checks all three before decoding. In the optimized build the sound share of
  `airdefense1`'s game media precache (`com_showLevelLoadTimes 1`) fell from about 970 ms to
  270 ms of main-thread time, and an earlier cut that still parsed the headers on the main
  thread measured the whole warm load at 12.40 s against 13.10 s (medians of three).
- **Ogg decode.** `LoadOgg` opens the stream, sizes the buffer from its length and decodes
  straight into it. `stb_vorbis_decode_memory` grew a scratch buffer by doubling and copied it
  out: two to three times a sound's PCM at peak and a full copy of every sound. A stream that
  decodes short now warns. Offline, every stock Ogg (5,690 files, 1.23 GB of PCM) decodes
  byte-identical to `stb_vorbis_decode_memory` and slightly faster (10.9 s against 11.1 s on
  one core).
- **Robust loading.** A failed loader attempt frees itself instead of uploading the default
  beep, which a later language variant then found in place of its own audio. Out-of-range
  ADPCM predictors, XMA2 and more-than-stereo PCM are refused at load with a warning; they
  used to end the session (`common->Error`) or play as noise. `s_noSound 1; s_restart;
  s_noSound 0` keeps the restart pending instead of starting voices on emptied samples.

### Presets

Every performance preset keeps room reverb on (`s_useEAXReverb 1`); see
`Common_MigrateLegacyAudioDefaults` in `src/framework/Common.cpp` for the one-time step that
restores it on profiles still on the minimum, lowpower or performance preset.

## Deferred

- **Streaming music and long voice-over.** All 43 music tracks decode to 393 MB of PCM. The
  voice already queues three buffers; streaming from the compressed Ogg would hold about 33 MB.
- **Centre channel on 5.1.** `SetCenterChannel`, `SSF_CENTER` and `s_centerFractionVO` have no
  OpenAL equivalent in use; voice-over on 5.1 is spread like any listener sound.
- **Mod reverb room rolloff.** OpenAL Soft applies an effect's room rolloff with distances in
  game units. Stock presets use 0; a mod preset with a room rolloff gets far too much.
- **HDR audio, ducking, geometric obstruction.** These change the authored mix or need new
  per-sound data; they are not defaults for stock content.
- **Voice budget.** 48 voices stay (retail mixed 24 channels).

## Verifying

- `tools/tests/sound_settings.py` and `tools/tests/sound_recovery.py` (the device-layout and
  limiter paths), `tools/tests/sound_retail_reverb_contract.py`,
  `tools/tests/macos_openal_provider_policy.py`, `tools/tests/ui_performance_presets.py` and the
  in-engine `performancePresetSelfTest`.
- The log reports `OpenAL voices: source radius on, direct stereo on (remixed), resampler 11th
  order Sinc` and `OpenAL output limiter: on`.
- Audible checks without a device: point `ALSOFT_CONF` at a config with `drivers=wave` and a
  `[wave] file=` path, as in [retail-audio-reverb.md](retail-audio-reverb.md).
