# Quake 4: The Awakening (`q4xbase`) support plan

Status: in progress. This is the living plan for running the unreleased Raven/Ritual
expansion on openQ4. The gap analysis it works from is
[the support audit](../q4x-awakening-support-audit.md).

## Current architecture (1 October 2026)

Awakening is an optional **single-player campaign** built into the canonical
`src/game/` SP library in openQ4. Its independent additions are in
`src/game/awakening/`; `src/mpgame/` remains the ordinary multiplayer game.
The two companion repositories are historical import sources, not build inputs.
See [source provenance](../game-source-provenance.md),
[licensing](../../../LICENSING.md) and the
[consolidation/evidence plan](game-source-consolidation.md).

Single Player → Campaign queries loose files and PK4 indices without mounting
them. A ready installation requires the defining declarations/scripts and all
thirteen compiled campaign maps. Only selecting Awakening mounts `q4xbase`,
which keeps its saves/configuration separate from `baseoq4`. Its turret
substitution is scoped to the filesystem's active game directory. Retail,
Arena and online multiplayer unload expansion overrides through a full restart.
Both story campaigns load the trusted `baseoq4` SP module, ignoring old expansion
DLLs. Expansion menu/default configuration files cannot replace engine navigation.

The original leaked game binary and reconstructed GPL source remain behaviour
references only. No recovered implementation or proprietary art is imported.
Awakening multiplayer code, maps and pricing changes are excluded from this
integration. No expansion assets are distributed; installation is described in
the [campaign guide](../../user/campaigns.md).

The sections below retain the historical feature and content investigation.
References to separately linked layer modules describe the pre-consolidation
implementation; the architecture above governs current builds.

## Status

### Single player

| Class / feature | Maps | State |
|---|---|---|
| 10 new script events | all | Done |
| `riFireFX` (`func_fire_volume`) | m01, m01 part 2, m02, m03, m04 | Done |
| `riMonsterWalker` | m01, m01 part 2, m06 invasion | Done |
| `riMonsterRetch` (buffs allies) | m01 part 2, m02, m04, m05, m08 | Done |
| `riMonsterTank` (breakable launcher and chest) | m02, m04, m08, m09 | Done |
| `idTarget_ObjectiveBeacon` | m04, m05, m06, m06 invasion, m08 | Done (the compass that reads it is commented out of the shipped HUD) |
| `WeaponGoobGun` + `DOTEntity` / `FireDOTEntity` | m02 on | Done |
| `rvWeaponFreezeGun`, `WeaponSpikeGun` | player arsenal | Done, with freezing, sticky spikes and corpse pinning |
| `riMonsterTurret` (every turret spawn) | m01, m01 part 2, m04, m05 | Done |
| `riMonsterPainLord` | m05 | Done |
| `riMonsterValkaryne` | m08 (set piece), m09 | Done |
| `riVehicleSpeederBike`, `riVehiclePartBoost` | m06 invasion, the three m07 race maps | Done |
| `riVCWPulseCannon`, `riVCWMissileTurret`, `riProjectileSpaceRocket` | m03, m06 invasion | Done |

### Multiplayer

The drop's multiplayer maps run as listen servers with a bot in a live match: `q4xctf1-6`
in CTF, `q4xctf2` in Arena CTF, `q4xctf3` in DeadZone, `q4xctf5` and `q4xdm12` in DM, and
`q4xtourney1` in Tourney and Team DM. Only `q4xctf1-5` and `q4xdm12` are new. `q4xctf6`,
`q4xtourney1` and `q4xdm10`, `11` and `13`-`15` are Raven's post-release maps, already in
retail's `pak019.pk4`; the drop carries other builds of them, which win under `q4xbase`.
`q4xdm1-6` re-export retail's DM maps. The expansion's powerup numbering, its two new
powerups and its buy menu work (Phase 3). Its effects and materials name images that
neither it nor retail ships (`gfx/effects/fire/p_fire2a`, `gfx/mp/ctf_neutral_flagstrip*`,
`models/monsters/burn_misc_sm`); they load as the default image, as they would under
retail.

## Phases

### Phase 1 — the campaign plays (done)

Everything in the status table above, plus the engine work, the build, and the headless
harness `.tmp/awakening/run_q4x.py` (local, untracked) used to boot each map.

### Phase 2 — campaign polish (done)

- **Freezing** (done, in `openQ4-game`). Each `freezeEnemies` bolt adds 0.05 to an AI's
  freeze factor, capped at 0.9; the factor slows its animation (to a quarter at most),
  thaws at 0.3 a second and shows `common/freeze_overlay1` above 0.15. `filter_freeze`
  damage that would kill it freezes it solid instead: `common/freeze_death_overlay`,
  `snd_freezeDeathBegin`, animation stopped, and four seconds later (or when anything
  else kills it) `damage_freezegib` shatters it with `fx_freezegib`. The state is not
  saved; a restored AI has thawed.
- **Turrets** (done, `riMonsterTurret` substituted for `rvMonsterTurret`):
  `dynamicAccuracy` (spread tightens over `accuracyLerpTime` of firing),
  `delayedTracking` / `lockDelay` (turn sounds, and a pause before firing again),
  `scanAnim` (the security cameras sweep).
- **Sticky spikes and pinning** (done, in `openQ4-game`'s `idProjectile`). Retail's SDK
  declares a `sticky` flag and never reads it; the expansion's spike and Pain Lord
  projectiles set it. A sticky projectile that does not detonate on the world stays where
  it hits it (bound to a mover it hits), and one that kills an actor stays in the corpse,
  bound to the joint it hit, until its fuse runs out. `passThroughActors` spikes hurt a
  living actor once and glance off it instead of detonating; the spike has no bounce, so
  it drops away, as it did in the expansion's code. In single player a spike stuck in a
  corpse pins it once its ragdoll is up: a ball-and-socket joint from the body it hit to
  the first surface within `maxPinDistance` behind that body, free to swing 90 degrees
  about the spike's line, unless the corpse's def says `canBePinned 0` (the Tank and the
  Walker). The spike's `maxPinDistance` is 10, so a corpse is pinned only when it lands
  against a wall. The joint is a *transient* AF constraint, which `idPhysics_AF::Save`
  leaves out, so a game saved with a pinned corpse loads, with the corpse unpinned. None
  of these keys appears in retail content.
- **Scripted targets** (done, in `openQ4-game`'s `idAI`). `onlyTarget`, `onlyTarget2`, ...
  name the only actors an AI may take as an enemy (`subStringOnlyTarget` lets a name match
  by its start), and spawners pass them on as `spawn_onlyTarget*`. The set pieces rely on
  them: m03's Strogg shoot at invisible targets on the dropship rather than at the player
  inside it, m04's marine goes for one jumping grunt, m06's harvesters shoot at the
  trucks, m07's bridge duel keeps to its two marines and a gladiator, and m09's Valkaryne
  fights only the player.
- **Savegames** (done). `idAI` saves one attack offset per animation of its model. Stock
  models have at most 244 animations and openQ4's restore rejected more than 256; the
  expansion's marines have 540 (its reference marine 1015), so a game saved on m04 never
  loaded. The bound now follows the range of an animation number (32768).
- **Dead keys.** `velScale`, `iff`, `spawn_iff`, `bindOrientied`, `canTurn` and
  `ignoreAAS` have no reader in the expansion's own code either. Its only reader of
  `useMasterRoll` / `useMasterPitch` is monster physics, and the content sets them on
  movers, dropships and static models. Nothing to do for any of them.

### Phase 3 — multiplayer (done)

- `"TeamDM"` accepted as `"Team DM"` in `maps.def`, in the game and in the engine's
  create-server map list (done).
- **Powerups** (done, in `openQ4-game`'s multiplayer module). The expansion inserted
  Adrenaline at 12 in its `powerup_types` def, which pushes DeadZone and the team powerups
  one along, and added FC Armor Regen at 17. openQ4 keeps its own numbering and translates
  a content number through the def name `powerup_types` gives it
  (`idPlayer::PowerupForContentType`, `GetPowerupDefName`), so every retail number maps to
  itself and the expansion's DeadZone tokens stay DeadZone tokens. The two new powerups are
  appended (`POWERUP_ADRENALINE`, `POWERUP_FC_ARMOR_REGEN`); the powerup bits now travel as
  `POWERUP_MAX` bits instead of a short.
  - Adrenaline lends 400 health at once, less one second's share, and takes that share
    back every second while health is at max or above; it ends when health falls below max
    or the payback reaches 100. No map places it; `give adrenaline` works where its def exists.
  - FC Armor Regen, the fourth team special on the buy menu, builds armor 5 every half
    second up to 100 over max (capped at 255, the snapshot's byte) instead of letting it
    tick down. It stays with its buyer when they die.
- **The buy menu** (done). The expansion's `buymenu.gui` runs `sq_buy <item>` and reads 27
  `canbuy_*` states; its `default.cfg` binds `sq_buyMenu`. Both names are the `buy` and
  `buyMenu` commands, and the menu refresh fills retail's `buyStatus_*` states and the
  expansion's `canbuy_*` states from one table (firing retail's `update_buymenu` and the
  expansion's `redraw`). The expansion kept its prices in code, so the layer registers them
  (`BUY_ITEM_PRICE`, `src/mpgame/BuyPrices.cpp`), ahead of the content's
  `ItemCostConstants`. An item is for sale only when something prices it: that puts the
  nine weapon mods (each only with its weapon, once) and FC Armor Regen (team games) on
  sale in `q4xbase` and keeps them off it in `baseoq4`. A buy travels as impulse
  `IMPULSE_100` plus its index in one table; the Awakening's items fill the numbers retail
  left unused and the goob gun takes 128. The expansion's own check for the spike gun
  scope looked for a `weapon_scope` that does not exist, so the scope never sold there;
  openQ4 reads a mod's weapon from its def, and it does.
- Weapon groups (nothing to do). The expansion registers `g_weaponGroup0..7` (impulse
  lists a key would cycle through) and `g_weaponPickupPriority` (an auto-switch order on
  pickup), but its code never reads them: the only references to those cvars are their
  static registration and destruction. `default.cfg` sets the priority and the
  developers' own configs leave every group empty, so neither changes play there.

### Phase 4 — latent content (nothing reaches it)

Classes the expansion's code has but nothing in its content reaches:

- `WeaponGrappleHook`, with a rope mode in `idPhysics_Player`. No def gives it; the
  player def carries its beam and crosshair keys, `func_grapplenode` exists but no map
  places one, and `default.cfg` binds `g` to `_impulse27`, which openQ4 leaves unused.
- `rvWeaponConcussionGun`. No def gives it; the player def only carries its animations.
  The grenade launcher's concussion blast, which m02, m08 and m09 hand out, is unrelated:
  an ordinary weapon mod whose `def_projectile` swaps in a grenade with a wider, harder
  splash, applied by the same code as retail's mods.
- `riVehiclePartSplineTether`. The speeder bike's def comments its part out.
- `rvVehicleGravGun`. `vehicle_turret_gravgun` exists, but no map places it.

The compass (`gui::objectiveYaw`) waits on content that is commented out.

## What the expansion's code taught us

Recorded because each one changed what "support" means here.

- A damage def with a `spawnclass` does no direct damage to actors in the expansion;
  its entity does all of it (the goob gun's 35-point hit is never applied). openQ4
  keeps that. Players, who have their own damage path, take the direct damage.
- The expansion's burn looked its effect up on the *victim*, where no def sets it, so
  the first flame never showed; openQ4 takes it from the damage def.
- The speeder bike's boost set `g_fov` and left it at 90; openQ4 widens the view through
  the vehicle instead and leaves the player's FOV alone. The boost fires on *crouch*
  (the bike's HUD says so), not a new button.
- The bike's script events drive a spline tether its def leaves out, so they do nothing
  in the expansion or here.
- The expansion's rigid bodies take friction values up to 10; Quake 4 drops the whole
  friction set when one passes 1. The bike's `friction_angular` of 5 is what stops it
  turning: on the 0.6 fallback a held turn spun it up past 500 degrees a second, and
  it turned two more full circles after the stick was let go. openQ4 raises the
  ceiling for the bike alone (`riVehicleSpeederBike::GetMaxFriction`), because a
  global change would also apply convoy1's landmine friction of 5, which retail drops.
  Rigid vehicles apply the def's friction again on restore, so older saves pick it up.
- Its hoverpads take `traceRelativeDirection`: the pad probes along that direction in
  the vehicle's frame and pushes straight back. The bike's antisuspensor probes up,
  holding it off ceilings, and its six bumpers probe out, holding it off walls. Probing
  down instead, as stock pads do, the antisuspensor pressed the bike towards the ground.
- openQ4's first rebuild of the bike's grip turned its velocity by twice the bike's
  heading every tic (it multiplied by the axis instead of projecting onto it), so
  thrust could not build speed on most headings. On open track three seconds of full
  forward thrust moved the bike about 25 units; it now covers about 1100 and reaches
  about 580 units a second.
- Vehicle turrets follow only the change in the player's own aim, so a script that
  seats the player and then turns the vehicle (m07's race start turns the bike 165
  degrees) leaves the guns pointing ahead, here and in the expansion. A gun camera
  facing backwards at the race start came from VR's seat tracking, not the bike.
- The Valkaryne's `requestDocking` function is parsed and never called; the m09 script
  docks her itself. She spawns with her ranged and melee attacks switched off.
- `ai_valkaryneShots` is registered and never read, and so are the weapon-group and
  pickup-priority cvars.
- Some of its map scripts call events their target classes do not have, in its own game
  code as much as in openQ4's: `playCycle` on m04's security cameras (turrets) and
  `becomeSolid` / `becomeNonSolid` on m02's `func_static` leaper clips. The calls do
  nothing and openQ4 logs "not supported", as the SDK does. The expansion DLL's event
  tables, read statically, register those events on the same classes as retail.

## Validation

- `.tmp/awakening/run_q4x.py <map>` boots a map in a hidden client with an isolated
  savepath and runs an after-load cfg (the Awakening content comes from the drop at
  `E:\Games\Quake_4_Alpha-main`).
- `damage <entity> 1 damage_goobDirect` with `g_debugDamage 1` shows the burn ticking
  once a second on an AI.
- Every campaign map must load, spawn its entities without class errors and run to its
  after-load quit.
- `.tmp/awakening/save_sweep.py` (local) saves every campaign map a few seconds in and
  loads it in a second client. A load passes when nothing errors after the savegame
  banner and the after-load cfg, which only runs once the restored map is live, echoes
  its marker. `--game baseoq4` runs it on stock maps.
- `.tmp/awakening/pin_test.py` (local) launches a spike at the world and at a fresh
  Strogg marine on m04 with `openq4_launchTestProjectile`, and reads `g_debugDamage`'s
  stick and pin reports; it then saves and loads the game with the corpse pinned.
- `.tmp/awakening/onlytarget_test.py` (local) spawns a Strogg marine facing the player on
  m04 with `noDamage 1` (so the level's marines cannot kill it first): with
  `onlyTarget player1` it hurts the player, with `onlyTarget nobody` it never does.
- `run_q4x.py mp/q4xdm1 --mp "Team DM"` starts a listen server; with `net_allowCheats`,
  `addbot` and `serverForceReady` the match goes live, and `openq4_reportMPWorld player1`
  reads the player back. `.tmp/awakening/mp_phase3_test.py` (local) picks up a spawned
  Adrenaline, buys the spike gun, its scope and FC Armor Regen, and picks up a DeadZone
  token; `mp_stock_buy_test.py` checks that `baseoq4` buying is unchanged. Game time trails
  the real-time waits in a hidden run, so waits are generous and checks look for steps,
  not totals.
- `.tmp/awakening/script_sweep.py` (local) fires every `trigger_*` of each campaign map in
  file order, with the map's `target_endlevel` removed, god mode and `notarget`, under
  cdb so a crash reports a stack. All 13 maps run to the end without an error or a
  crash. Firing sequences out of order makes warnings of its own (scripted moves that
  cannot start, entities a sequence already removed, which a plain boot never shows);
  the rest are the script calls above, retail's harvester lacking the `turn_90_lt` its
  code asks for, and m09's ragdoll marines, which spawn with `spawn_health 0` on purpose.
- `.tmp/awakening/mp_maps_boot.py` (local) boots the expansion's multiplayer maps in the
  gametypes listed under Status, adds a bot, forces the match live and reads the player
  back.
- `.tmp/awakening/levelshot_test.py` (local) checks `openq4_mapLevelshot` for the
  expansion's maps, and that stock maps keep their levelshots.
- For interactive testing the expansion's content sits in the development savepath,
  `.home/q4xbase/`, copied from the drop without its leaked `gamex86.dll` and never
  committed. The `(SP) Awakening ...` and `(MP) Awakening ...` launch configurations run
  it from there, with retail content from the Steam install. Like the stock entries, they
  cover the menus and every map the expansion carries (13 campaign maps, 19 multiplayer
  maps), each on GL and on Vulkan, and the multiplayer ones start at the join screen
  (`ui_autoJoin 0`). `launch_entry_check.py` (local) runs a map entry's arguments headlessly
  against an isolated copy, and `launch_menu_check.py` does the same for a menu entry.
