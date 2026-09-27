# Quake 4: The Awakening (`q4xbase`) support plan

Status: in progress. This is the living plan for running the unreleased Raven/Ritual
expansion on openQ4. The gap analysis it works from is
[the support audit](../q4x-awakening-support-audit.md).

## Goal

Play the expansion's campaign (13 maps, `m01_stranarus_trench1` to `m09_valkaryne`) and
its multiplayer maps (`q4xctf1`-`q4xctf6`, `q4xtourney1`) on openQ4, from the
expansion's own content plus openQ4 binaries. The expansion's `gamex86.dll` is never
loaded (openQ4 does not load legacy game code), and none of its code is copied: it is
studied only as a record of how the shipped content expects to behave.

## Shape of the solution

Three repositories share the work.

| Repository | Licence | Role |
|---|---|---|
| `openQ4` | GPLv3 | Engine features the expansion's content needs; the build that stages and links the Awakening game modules |
| `openQ4-game` | Quake 4 SDK EULA | The base game libraries, plus generic extension points the expansion builds on |
| `openQ4-game-awakening` | Quake 4 SDK EULA | The expansion's own classes, as an additive *game-library layer* |

### The game-library layer

`openQ4-game-awakening` holds only new files. Its `layer.json` names the layer, its
game directory (`q4xbase`) and its source roots:

- `src/shared` compiles into both modules,
- `src/game` into single player only,
- `src/mpgame` into multiplayer only.

`tools/build/stage_gamelibs.py --layer` copies the base trees and places the layer's
files in `src/game/awakening/` and `src/mpgame/awakening/` of a separate stage, so a
layer file includes base headers exactly as a base file would (`../Game_local.h`) and
cannot collide with them. The base game compiles once, into static core libraries that
both `baseoq4` and `q4xbase` link whole; the layer adds its objects on top.
`tools/build/game_layer.py` validates `layer.json` and writes `q4xbase/mod.json`.

The Meson option `awakening` (`auto` by default) builds the layer when
`../openQ4-game-awakening` (or `OPENQ4_AWAKENING_REPO`) exists. Output lands in
`builddir/q4xbase/` for direct runs and `.install/q4xbase/` for the staged package;
`tools/build/meson_setup.ps1` re-stages whenever the layer's sources change.

CI does not build the layer: `openQ4-game-awakening` is a private repository, which the
public workflows cannot fetch. Local builds cover it instead (the `auto` option builds it
whenever the checkout sits beside openQ4), with the headless runs under Validation and a
Linux `g++ -fsyntax-only` pass over every layer source under WSL. An `openQ4-game` change
to an extension point therefore needs a local build of both modules before it is pushed.

A layer reaches the base in one of three ways, in order of preference:

1. **A new class** (most of the roster), registered like any other: base
   `CLASS_DECLARATION` now registers through a static registrar, so a class in a layer
   object is found without editing any base list.
2. **Class substitution**: `SPAWNCLASS_SUBSTITUTION( base, replacement )` makes every
   spawn of a base class produce a layer subclass, for behaviour the expansion changed
   on a stock class.
3. **A generic extension point in the base**, when neither will do (below).

### Extension points added to `openQ4-game`

Each is inert for stock content; the audit checked the retail defs for every key.

| Extension point | Used by |
|---|---|
| `idClassRegistrar`, `idClassSubstitution` | Every layer class |
| A damage def with a `spawnclass` hands its damage to an entity of that class (`idEntity::SpawnDamageEntity`); `idEntity::ApplyDamage` takes worked-out damage; `idActor::SetPainType` | `DOTEntity`, `FireDOTEntity` |
| `idActor::SetDamageScales` (damage dealt and taken) | `riMonsterRetch` |
| `resetTalkCount` script event on `idAI` | Expansion scripts |
| `idLight::GetRadius` | `riFireFX` |
| `WeaponNapalmGun` declared in a header | `WeaponGoobGun` |
| `rvVehicleWeapon`: virtual `Fire`, `UpdateCursorGUI`, `Select`, `ProjectileLaunched`; a `convergence` key | Cockpit cannons |
| `rvVehicle::SetFovOffset`, added to the driver's FOV | `riVehiclePartBoost` |
| `damage <entity> <scale> [def]` console command | Headless testing |
| Multiplayer powerups resolved by def name (`idPlayer::PowerupForContentType`), plus `POWERUP_ADRENALINE` and `POWERUP_FC_ARMOR_REGEN` | The expansion's `powerup_types` numbering |
| `idBuyItemPrice` / `BUY_ITEM_PRICE`: prices a layer sets in code, ahead of `ItemCostConstants` | `src/mpgame/BuyPrices.cpp` |
| `sq_buy` / `sq_buyMenu`, and the `canbuy_*` states on every buy-menu refresh | The expansion's `buymenu.gui` and `default.cfg` |
| `openq4_reportMPWorld` also prints armor, credits and weapons (`MP_WORLD_INVENTORY`) | Headless multiplayer testing |
| `idProjectile`: `sticky`, `passThroughActors`, `maxPinDistance` and the `STUCK` state; `canBePinned` on the corpse | The spike gun, the Pain Lord |
| Transient AF constraints (`idAFConstraint::SetTransient`), left out of saves | Corpse pins |
| `idAI`: `onlyTarget`, `onlyTarget2`, ... and `subStringOnlyTarget` | Scripted fights in m03, m04, m06, m07 and m09 |
| `openq4_launchTestProjectile <def> <name> <target> [key value ...]` | Headless testing |

### Engine work in `openQ4`

- **Mod runtime underlay.** Under any mod that is not built on `baseoq4`, the engine
  still searches `baseoq4` (between the mod and `q4base`), so openQ4's own shaders,
  GUIs and fonts come along.
- **Decl layering.** When a mod ships a decl file with the same name as one below it
  (the expansion's `player.def`, `debris.def`, `persona.def`, `music.sndshd`, ...), the
  engine now also reads the shadowed copies, with the mod's definitions winning. This
  recovers the hundreds of retail definitions those files used to hide. `decl_layerModFiles 0`
  restores the old behaviour.
- **Formats.** `CM "2"` collision models (the expansion's 157 per-model `.cm` files),
  DXT3 textures, `.jpg` names that exist only as `.tga` (the Valkaryne's nine limb
  textures), and `sound/music/` as a music path. DXT3 is decoded on the CPU and used
  only when a material names the file or nothing else by its name exists: retail keeps
  a DXT3 copy beside the `.tga` of every font atlas, and fonts must keep loading from
  the `.tga`.
- **Robustness.** Rotation bounds stay finite when a rotation axis component rounds a
  hair above 1 (ragdolls in m04 hit it on their first frames).
- **Menus.** `GetCVarValue`, `SetCVarValue` and `GetVecCVarValue` GUI commands. The
  create-server and server-browser previews show a map's mapDef `loadimage`, as its
  loading screen does: the expansion's CTF maps, `q4xctf1-5`, have no levelshot of their
  own name and name retail's there, so they previewed as the generic image.
  `openq4_mapLevelshot <map>` prints what the menus will show.
- **Input.** `_altattack` binds the zoom button, which is alternate fire.

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
  it from there, with retail content from the Steam install; `launch_entry_check.py`
  (local) runs an entry's arguments headlessly against an isolated copy.
