# openQ4-game-awakening

Game code that makes **Quake 4: The Awakening**, the unreleased Quake 4 expansion, playable on the [openQ4](https://github.com/themuffinator/openQ4) engine.

## What this is

The Awakening (`q4xbase`) was an expansion pack in development at Raven Software and Ritual Entertainment that never shipped. Its content survived; its game code only exists as a leaked binary that openQ4 does not and will not load.

This repository is new game code, written for openQ4, that implements what the expansion's content expects: its new monsters and bosses, weapons, vehicles, effects and script functions. It is a *mod layer* on top of openQ4's own game code ([openQ4-game](https://github.com/themuffinator/openQ4-game)): it only adds to that code, and every build is the current openQ4 game plus the expansion's additions.

## What you need

- Quake 4 from Steam or GOG, patched to 1.4.2.
- An openQ4 build that includes the Awakening modules (see **Building**).
- The expansion content, as a `q4xbase` folder inside your Quake 4 installation, next to `q4base`. This repository does not include or distribute any game content.

## Playing

Start openQ4 with the expansion selected as the game directory:

```
openQ4-client_x64 +set fs_game q4xbase
```

openQ4 keeps its own runtime files underneath the expansion automatically, so no other settings are needed. Saves, configs and logs go to the `q4xbase` folder of your openQ4 save path.

## Building

openQ4 builds these modules itself when this repository sits next to it (`../openQ4-game-awakening`) or when `OPENQ4_AWAKENING_REPO` points at it. On Windows:

```
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 compile -C builddir
```

run from the openQ4 checkout. The modules appear in `builddir/q4xbase/` and, after installing, in `.install/q4xbase/`. Configure openQ4 with `-Dawakening=disabled` to leave them out, or `-Dawakening=enabled` to make a missing layer an error.

## Status

Work in progress. See [the integration plan](https://github.com/themuffinator/openQ4/blob/main/docs/dev/plans/q4x-awakening.md) for what is implemented and what is next.

## Credits

- Raven Software and Ritual Entertainment, who made Quake 4 and The Awakening.
- id Software.
- Justin Marshall, who recovered and published the expansion.
- openQ4 contributors.

## License

Like openQ4-game, this repository is licensed under the Quake 4 Software Development Kit Limited Use License Agreement. See `LICENSE`.
