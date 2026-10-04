# Virtual reality (OpenXR)

openQ4 can play Quake 4 on a PC VR headset through OpenXR, the cross-vendor
VR standard. You see the game in stereo at your headset's resolution, look
around with your head and aim with a motion controller. The HUD floats in
front of you, and menus, loading screens and cinematics appear on a floating
screen.

VR mode is **experimental**. It works with the single-player campaign and
multiplayer, and needs no extra content beyond your Quake 4 install.

## What you need

- A PC VR headset and an **OpenXR runtime that supports OpenGL**, set as the
  system's active OpenXR runtime:
  - **SteamVR** (Valve Index, HTC Vive, Pimax, Bigscreen and many others);
  - the **Meta Quest Link** PC app for Quest headsets over Link or Air Link;
  - **Monado** on Linux.

  Windows Mixed Reality's own runtime does not support OpenGL. On a WMR
  headset, run the game through SteamVR instead.
- The **OpenGL renderer**, which is the default. VR does not start while
  `r_renderApi` is `vulkan`.
- On Linux, a GLX context: on an X11 desktop this is automatic; on a Wayland
  desktop, start openQ4 with the environment variable `OPENQ4_FORCE_X11=1` so
  it runs through XWayland.

## Turning VR on

1. Start your headset and its OpenXR runtime (for example SteamVR).
2. In openQ4, open **Settings > Game Options**, pick **VR** under Section,
   and set **VR Mode** to Enabled. VR starts at once. From the console,
   `vr_enable 1` does the same.

   The setting is saved, so the next launch starts in VR on its own. You can
   also launch with `+set vr_enable 1`.

The same section sets aiming, turning, movement, the laser sight,
vibration, the two-handed grip and the comfort vignette.

When VR is on, the desktop window shows what your left eye sees. To turn VR
off again, set VR Mode back to Disabled (you can point at it in the headset),
or enter `vr_enable 0`.

The same Virtual Reality section holds the settings players change most:
aim with the controller or your head, weapon hand, snap or smooth turning,
the snap angle, walk direction, room scale, the laser sight and vibration.
The tables below list everything, including the console-only settings.

If the headset isn't connected yet, openQ4 waits for it and starts VR as soon
as it appears.

If you quit SteamVR, or the runtime closes VR some other way, the game carries
on in its desktop window. Enter `vr_restart` to go back into VR; `vr_enable`
stays on, so the next launch starts in VR as usual.

## Controls

Controllers act like a gamepad, so the default gamepad bindings apply and you
can rebind them in the controls menu like any gamepad button.

| Control | Gameplay | Menus |
| --- | --- | --- |
| Weapon-hand trigger | Fire | Click where you point |
| Off-hand trigger | Zoom | - |
| Off-hand stick | Move | Navigate |
| Weapon-hand stick left/right | Turn | Navigate |
| Weapon-hand stick up/down | Next / previous weapon | Navigate |
| A | Jump | Select |
| B | Crouch | Back |
| X | Reload | - |
| Y | Flashlight | - |
| Off-hand grip | Weapon wheel, or hold the gun in both hands | - |
| Weapon-hand grip | Last weapon | - |
| Off-hand stick click | Run / walk | - |
| Menu button | Menu | Close menu |

The weapon hand is the right hand. Set `vr_leftHanded 1` to hold the weapon
in your left hand; the triggers, grips and sticks swap with it.

Menus open on a floating screen in front of you, and the game world stays
around you while the game is paused. Point your weapon-hand controller at the
screen: a dot shows where it points, and the trigger clicks there like a
mouse. The sticks and the A and B buttons also work in menus.

You aim with the controller in your weapon hand, and the gun follows it. A
red laser dot sits where your shots will land, at the real distance of what
you're pointing at, so it stays sharp whether the target is near or far. It
dims when something between you and the target hides it. Set `vr_aimMode 0`
to aim with your head instead; the HUD crosshair only shows when you aim with
your head.

To steady a gun, hold it in both hands: put your off hand in front of your
weapon hand, where a rifle's foregrip would be, and squeeze its grip. The
off-hand controller gives a short buzz, and the gun then points from your
rear hand through your front hand until you let go. Squeezing the off-hand
grip anywhere else opens the weapon wheel: turn your weapon hand towards the
weapon you want and let go of the grip to switch to it.

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_aimLaser` | 1 | 0 no marker, 1 laser dot, 2 laser dot and a beam from the gun |
| `vr_twoHanded` | 1 | 1 the off-hand grip on the foregrip holds the gun in both hands, 0 it always opens the weapon wheel |

The off-hand trigger zooms with a scoped weapon, such as the machinegun or
the railgun: your whole view magnifies as far as the scope would, and the
laser dot is your crosshair. Keep zoom short if magnified head movement
makes you uneasy.

The controllers vibrate: your weapon hand with every shot, and both hands
when you're hit, harder for bigger hits. Set `vr_hapticStrength` between 0
(off) and 1 (full, the default).

## Comfort

openQ4 avoids moving your view in ways your body doesn't feel:

- there is no view bob, weapon kick or screen shake in VR;
- turning is done in steps (snap turn) by default;
- while the stick moves you or turns you smoothly, the edges of your view
  darken around a clear centre (the comfort vignette), because that motion is
  what your body doesn't feel; walking about your room never triggers it;
- in-game cinematics play on the floating screen instead of moving your view.

In single player you can walk around your room: step and your character
steps with you, sliding along walls and up stairs, so your view never ends
up inside a wall. Lean a little and only your head moves. Your character
won't follow you off a ledge; you can lean over it instead. In multiplayer
your character stays put and you can lean up to `vr_headOffsetLimit` from
it, because the server decides where everyone is.

You can change these settings:

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_turnMode` | 0 | 0 snap turn, 1 smooth turn |
| `vr_snapTurnAngle` | 45 | degrees per snap turn |
| `vr_smoothTurnSpeed` | 120 | smooth turn speed, degrees per second |
| `vr_moveDirection` | 0 | 0 walk where you look, 1 walk where the off-hand controller points |
| `vr_stickDeadzone` | 0.2 | thumbstick deadzone |
| `vr_comfortVignette` | 0.5 | how strongly the comfort vignette narrows your view, from 0 (off) to 1 (a black edge around a 60 degree clear centre) |
| `vr_roomScale` | 1 | 1 your character follows your steps about the room (single player), 0 it stays put |
| `vr_headOffsetLimit` | 16 | how far you can lean from your character before the view stops (game units) |

Use `vr_recenter` to make your current position and direction the front. It
helps to bind it to a key, for example `bind F12 vr_recenter`.

## Display

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_renderScale` | 1.0 | multiplies the headset's recommended resolution (0.5-2.0; apply with `vr_restart`) |
| `vr_worldScale` | 39.37 | game units per metre; lower makes the world feel bigger |
| `vr_hudDistance` | 1.4 | HUD distance in metres |
| `vr_hudWidth` | 1.2 | HUD width in metres |
| `vr_hudHeightOffset` | -0.1 | HUD height relative to your eyes, in metres, when you aim with the controller (head aiming centres the HUD so its crosshair lines up) |
| `vr_screenDistance` | 2.5 | menu and cinematic screen distance in metres |
| `vr_screenWidth` | 3.0 | menu and cinematic screen width in metres |
| `vr_mirror` | 1 | desktop window: 0 black, 1 left eye, 2 the floating screen |

The floating screen and the HUD take the shape of the game window, so menus
look the same as on your monitor.

Temporal anti-aliasing and dynamic resolution switch themselves off in VR.
Use MSAA (`r_multiSamples`) or SMAA instead.

## Weapon position

Each gun appears full size in your hand, gripped where its own model holds it,
with its barrel pointing along your controller's aim and the laser. If a gun
still doesn't sit naturally, nudge it relative to the controller:

| Setting | Default | Direction |
| --- | --- | --- |
| `vr_weaponOffsetX` | 0 | along the controller's aim, in game units |
| `vr_weaponOffsetY` | 0 | to the controller's left |
| `vr_weaponOffsetZ` | 0 | up |
| `vr_weaponPitch` | 0 | tilt in degrees; positive tilts down |

If you played an earlier VR build, its offsets of -5 and -3 would push the gun
out of your hand, so openQ4 resets that pair to 0 once at startup.

## Multiplayer

VR players can join any openQ4 server. Your aim reaches the server the same
way a mouse's does, so servers need no changes. In multiplayer, shots leave
from your eyes along your controller's aim; in single player they leave from
the gun in your hand.

## Troubleshooting

Enter `vr_status` in the console to see the runtime, headset, session state
and resolution openQ4 is using. `vr_debug 1` logs session events.

- **"no runtime is available"**: no OpenXR runtime is installed or active.
  Set one as active in its own settings, for example in SteamVR under
  Settings > OpenXR.
- **"does not support OpenGL"**: the active runtime can't render OpenGL games.
  Switch to SteamVR or Meta Quest Link.
- **"VR needs the OpenGL renderer"**: set `r_renderApi gl` and restart. On a
  Linux Wayland desktop, also start openQ4 with `OPENQ4_FORCE_X11=1`.
- **The image looks washed out**: the runtime didn't offer an sRGB image
  format. Report your headset and runtime.
