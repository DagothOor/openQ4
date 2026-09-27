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
- **Menus.** `GetCVarValue`, `SetCVarValue` and `GetVecCVarValue` GUI commands.
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
| `rvWeaponFreezeGun`, `WeaponSpikeGun` | player arsenal | Done, with freezing; corpse pinning is Phase 2 |
| `riMonsterTurret` (every turret spawn) | m01, m01 part 2, m04, m05 | Done |
| `riMonsterPainLord` | m05 | Done |
| `riMonsterValkaryne` | m08 (set piece), m09 | Done |
| `riVehicleSpeederBike`, `riVehiclePartBoost` | m06 invasion, the three m07 race maps | Done |
| `riVCWPulseCannon`, `riVCWMissileTurret`, `riProjectileSpaceRocket` | m03, m06 invasion | Done |

### Multiplayer

Boots and loads with the SP-shared classes. The items in Phase 3 remain.

## Phases

### Phase 1 — the campaign plays (this change)

Everything in the status table above, plus the engine work, the build, and the headless
harness `.tmp/awakening/run_q4x.py` (local, untracked) used to boot each map.

### Phase 2 — campaign polish

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
- **Pinning** (to do). A spike that kills an AI pins its ragdoll: a ball-and-socket
  constraint from the hit body to the surface within `maxPinDistance` behind it, with a
  90 degree cone around the spike's line, unless the AI's def says `canBePinned 0`. It
  needs the constraint to survive save and load, which a constraint added to the AF at
  run time does not today.
- **Dead keys.** `velScale`, `iff`, `spawn_iff`, `bindOrientied`, `canTurn` and
  `ignoreAAS` have no reader in the expansion's own code either: nothing to do.
  `onlyTarget` (an actor's allowed targets) and `useMasterRoll` / `useMasterPitch` (bind
  orientation) do, and remain.

### Phase 3 — multiplayer

- `"TeamDM"` accepted as `"Team DM"` in `maps.def`, in the game and in the engine's
  create-server map list.
- Powerups: the expansion inserted Adrenaline at type 12, which pushes DeadZone and the
  team powerups one along, and added FC Armor Regen at 17. openQ4 should resolve a
  powerup by its def name and append the two it lacks, keeping every existing index.
- The buy menu. The expansion's `buymenu.gui` issues `sq_buy <item>` and reads 27
  `canbuy_*` states (1 or 0), which its code fills from: `weapon_shotgun`,
  `weapon_hyperblaster`, `weapon_grenadelauncher`, `weapon_nailgun`,
  `weapon_rocketlauncher`, `weapon_railgun`, `weapon_lightninggun`, `weapon_spikegun`
  (`canbuy_corecannon`), `weapon_goobgun` (`canbuy_firecannon`), `weapon_dmg`,
  `weapon_freezegun`, the nine `wpmod_*` (a mod only with its weapon), the two armors,
  `ammorefill`, and the team specials `ammo_regen`, `health_regen`, `damage_boost`,
  `fc_armor_regen` (`canbuy_special0-3`, not in DM). Buys travel as usercmd impulses,
  so the new items need free impulse numbers.
- Weapon groups (`g_weaponGroup0..7`, `g_weaponPickupPriority`).

### Phase 4 — latent content

Classes the expansion's code has but no shipped map or def reaches:
`WeaponGrappleHook` (with a rope mode in `idPhysics_Player` and `_impulse27`),
`rvWeaponConcussionGun`, `riVehiclePartSplineTether`, `rvVehicleGravGun`. The compass
(`gui::objectiveYaw`) waits on content that is commented out.

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
- `ai_valkaryneShots` is registered and never read.

## Validation

- `.tmp/awakening/run_q4x.py <map>` boots a map in a hidden client with an isolated
  savepath and runs an after-load cfg (the Awakening content comes from the drop at
  `E:\Games\Quake_4_Alpha-main`).
- `damage <entity> 1 damage_goobDirect` with `g_debugDamage 1` shows the burn ticking
  once a second on an AI.
- Every campaign map must load, spawn its entities without class errors and run to its
  after-load quit.
