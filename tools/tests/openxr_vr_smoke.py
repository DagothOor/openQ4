#!/usr/bin/env python3
"""Play single player in VR against the openQ4 OpenXR test runtime (requires
Pillow, a staged client built with OpenXR, and retail assets).

The test runtime (tools/tests/openxr/OpenXRTestRuntime.cpp, built beside the
client) simulates a stereo headset with off-axis eyes and two controllers. It
is selected for this process only through XR_RUNTIME_JSON, so no system-wide
OpenXR registration is read or changed. No keyboard or mouse input is
synthesised: console commands drive the game, and the runtime's frame script
is synchronised to them through marker files the engine writes with condump.

Checks:
- the session binds the renderer's OpenGL context and presents loading as a
  quad layer before gameplay;
- gameplay submits a stereo projection layer plus the HUD quad, both eyes are
  lit and differ (parallax), and a scripted head turn changes what they see;
- a stick snap turn turns the body by vr_snapTurnAngle and a controller
  trigger press reaches the binding system;
- the controller's menu button opens the pause menu on an opaque, world-locked
  virtual screen in front of the still-rendered world, the weapon hand points
  at it (the pointer is drawn where the ray meets the screen) and the trigger
  clicks Resume there, which closes the menu even though the desktop window
  holds no focus;
- the runtime can end VR: the game carries on on the desktop, keeps
  vr_enable for the next launch and waits for vr_restart;
- the log carries no errors.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from mp_round_remote_smoke import verify_runtime_is_current

ROOT = Path(__file__).resolve().parents[2]

# Where the scripted controller points: straight ahead from this far right of
# and above the eyes, onto a screen vr_screenWidth metres wide hung straight
# ahead (the simulated head looks down -Z from 1.6 m). This is the pause
# menu's Resume row.
POINTER_RIGHT_M = -0.84
POINTER_UP_M = 0.15
SCREEN_WIDTH_M = 3.0


def read_events(path: Path) -> list[dict]:
    events = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def body_yaws(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"body yaw (-?\d+(?:\.\d+)?)", text)]


def yaw_delta(before: float, after: float) -> float:
    return (after - before + 180.0) % 360.0 - 180.0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basepath", type=Path, required=True, help="installed retail Quake 4 assets")
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "builddir",
                        help="build directory holding openq4_xr_test_runtime.json")
    parser.add_argument("--executable-name")
    parser.add_argument("--map", default="game/airdefense1")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    options = parser.parse_args(argv)
    from PIL import Image, ImageChops, ImageStat

    staged = options.runtime_dir.resolve()
    executable = options.executable_name or ("openQ4-client_x64.exe" if os.name == "nt" else "openQ4-client_x64")
    manifest = (options.build_dir / "openq4_xr_test_runtime.json").resolve()
    if not (staged / executable).is_file() or not options.basepath.is_dir():
        parser.error("a staged client and installed Quake 4 assets are required")
    if not manifest.is_file():
        parser.error(f"the OpenXR test runtime is not built: {manifest}")
    verify_runtime_is_current(staged, executable)

    output = (options.output_dir or ROOT / ".tmp/openxr-vr-smoke").resolve()
    if output == staged or staged in output.parents or output in staged.parents:
        parser.error("output and staged runtime directories must not overlap")
    profile = output / "sp"
    game = profile / "baseoq4"
    game.mkdir(parents=True, exist_ok=True)
    for stale in list(game.glob("vr_marker_*.txt")) + list(profile.glob("xr_*.tga")) + list(profile.glob("xr_*.png")):
        stale.unlink()
    xr_log = profile / "xr.jsonl"
    xr_log.unlink(missing_ok=True)

    def marker(name: str) -> str:
        return str(game / f"vr_marker_{name}.txt")

    # The runtime acts on the frame after each marker appears.
    script = [
        f"when {marker('gameplay')} capture {profile / 'xr_gameplay'}",
        f"when {marker('turn')} head 40 0 0",
        f"when {marker('turned')} capture {profile / 'xr_turned'}",
        f"when {marker('snap')} head 0 0 0",
        f"when {marker('snap')} stick right 1 0",
        f"when {marker('snapback')} stick right 0 0",
        f"when {marker('trigger')} button right trigger 1",
        f"when {marker('release')} button right trigger 0",
        f"when {marker('menu')} button left menu 1",
        f"when {marker('menu_release')} button left menu 0",
        f"when {marker('point')} hand right {POINTER_RIGHT_M} {1.6 + POINTER_UP_M} 0 0 0 0",
        f"when {marker('pointed')} capture {profile / 'xr_menu'}",
        f"when {marker('click')} button right trigger 1",
        f"when {marker('unclick')} button right trigger 0",
        f"when {marker('exit')} exit",
    ]
    (profile / "xr_script.txt").write_text("\n".join(script) + "\n", encoding="utf-8")

    # A key binding appends to the command buffer behind whatever still waits
    # there, so the trigger's binding runs the rest of the script itself.
    commands = [
        "waitMsec 3000", "echo VR_GAMEPLAY_ACTIVE", "vr_status",
        "condump vr_marker_gameplay.txt", "waitMsec 1000",
        "condump vr_marker_turn.txt", "waitMsec 700",
        "condump vr_marker_turned.txt", "waitMsec 700",
        "echo VR_SNAP_BEFORE", "vr_status",
        "condump vr_marker_snap.txt", "waitMsec 500",
        "condump vr_marker_snapback.txt", "waitMsec 500",
        "echo VR_SNAP_AFTER", "vr_status",
        'bind JOY15 "echo VR_TRIGGER_BIND_RAN; exec openxr_vr_smoke_menu.cfg"',
        "condump vr_marker_trigger.txt",
    ]
    menu_commands = [
        "unbind JOY15",
        "condump vr_marker_release.txt", "waitMsec 500",
        "condump vr_marker_menu.txt", "waitMsec 300",
        "condump vr_marker_menu_release.txt", "waitMsec 1500",
        "echo VR_MENU_OPEN",
        "condump vr_marker_point.txt", "waitMsec 700",
        "condump vr_marker_pointed.txt", "waitMsec 700",
        "condump vr_marker_click.txt", "waitMsec 300",
        # Resume dispatches on release, then the menu takes 250 ms to go; a
        # debug build draws the paused stereo world at only ~13 fps
        "condump vr_marker_unclick.txt", "waitMsec 2000",
        "condump vr_marker_exit.txt", "waitMsec 1500",
        "echo VR_AFTER_EXIT", "vr_status", "vr_enable",
        "echo VR_SMOKE_COMPLETE", "quit",
    ]
    (game / "openxr_vr_smoke.cfg").write_text("\n".join(commands) + "\n", encoding="utf-8")
    (game / "openxr_vr_smoke_menu.cfg").write_text("\n".join(menu_commands) + "\n", encoding="utf-8")

    launches = json.loads((ROOT / ".vscode/launch.json").read_text(encoding="utf-8"))
    launch = next(c for c in launches["configurations"] if c["name"] == "(SP) Main menu — GL")
    args = [a.replace("${workspaceFolder}", str(ROOT)) for a in launch["args"]]
    settings = {
        "in_mouse": "0", "in_joystick": "0",
        "r_fullscreen": "0", "r_borderless": "0", "r_borderlessDefaultMigrated": "1",
        "r_hiddenWindow": "1", "r_windowWidth": "1280", "r_windowHeight": "720",
        "r_mode": "-1", "r_customWidth": "1280", "r_customHeight": "720",
        "r_swapInterval": "0", "com_maxfps": "60",
        "win_allowMultipleInstances" if os.name == "nt" else "sys_allowMultipleInstances": "1",
        "fs_basepath": str(options.basepath.resolve()),
        "fs_savepath": str(profile), "fs_devpath": str(profile),
        "g_autoExecAfterMapLoad": "openxr_vr_smoke.cfg", "g_autoExecAfterMapLoadDelayMs": "1000",
        "g_autoSkipCinematics": "1", "com_skipLoadingContinue": "1",
        "com_loadingContinueAutoAdvance": "1", "com_allowConsole": "1",
        "vr_enable": "1", "vr_debug": "1", "vr_aimMode": "1", "vr_turnMode": "0", "vr_snapTurnAngle": "45",
        "vr_screenDistance": "2.5", "vr_screenWidth": str(SCREEN_WIDTH_M), "vr_leftHanded": "0",
    }
    for key, value in settings.items():
        args += ["+set", key, value]
    args += ["+map", options.map]
    command = [str(staged / executable), *args]
    (profile / "command.json").write_text(json.dumps(command, indent=2), encoding="utf-8")

    environment = dict(os.environ)
    environment.update({
        "XR_RUNTIME_JSON": str(manifest),
        "OPENQ4_XR_TEST_LOG": str(xr_log),
        "OPENQ4_XR_TEST_SCRIPT": str(profile / "xr_script.txt"),
        "OPENQ4_XR_TEST_EYE_SIZE": "1200x1320",
        "OPENQ4_XR_TEST_RATE": "90",
    })
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    timed_out = False
    with (profile / "process.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, cwd=staged, stdout=log, stderr=subprocess.STDOUT,
                                    env=environment, startupinfo=startup, timeout=options.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True

    text = (game / "logs/openq4.log").read_text(encoding="utf-8", errors="replace")
    events = read_events(xr_log)
    (profile / "xr_events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

    assert "VR_GAMEPLAY_ACTIVE" in text, "gameplay not reached"
    assert "OpenXR: presenting to the headset" in text, "the session never began"
    if timed_out:
        assert "VR_TRIGGER_BIND_RAN" in text, "the controller trigger never reached its binding (the script waited on it)"
        raise AssertionError(f"the client did not finish within {options.timeout} s")
    assert result.returncode == 0, result.returncode
    assert "VR_SMOKE_COMPLETE" in text, "script did not complete"
    assert not re.search(r"FATAL|ERROR:|OpenXR: .* failed|Unknown command", text), "errors in the log"

    sessions = [e for e in events if e.get("event") == "create_session"]
    assert sessions and sessions[0].get("binding", "").startswith("opengl_"), sessions
    assert any(e.get("event") == "begin_session" for e in events), "xrBeginSession never ran"
    # the runtime's binding UI shows these names: they come from the language table
    localized = sorted(e["localized"] for e in events if e.get("event") == "create_action")
    assert localized == sorted(["Aim pose", "Grip pose", "Trigger", "Grip", "Thumbstick", "Thumbstick click",
                                "Primary button", "Secondary button", "Menu", "Vibration"]), localized
    assert [e["localized"] for e in events if e.get("event") == "create_action_set"] == ["Gameplay"], \
        "the action set name is not localised"
    assert any(e.get("event") == "end_session" for e in events), "the runtime's exit request never ended the session"
    assert any(e.get("event") == "destroy_session" for e in events), "the session was not destroyed"
    assert not any(e.get("event") in ("end_frame_invalid", "create_session_rejected", "create_swapchain_rejected")
                   for e in events), "the runtime rejected a submission"
    frames = [e for e in events if e.get("event") == "end_frame"]
    assert any([layer["type"] for layer in f["layers"]] == ["quad"] for f in frames), \
        "loading never presented as a lone virtual-screen quad"
    stereo = [f for f in frames if [layer["type"] for layer in f["layers"]] == ["projection", "quad"]]
    assert stereo, "gameplay never presented a stereo projection layer with the HUD"
    assert any(f["layers"][1]["flags"] & 0x2 for f in stereo), \
        "the gameplay HUD quad must blend with source alpha"

    captures = {}
    for e in events:
        if e.get("event") == "capture":
            stage = next(s for s in ("gameplay", "turned", "menu") if f"xr_{s}_" in Path(e["path"]).name)
            captures[f"{stage}_{e['layer']}"] = e
    for name in ("gameplay_left", "gameplay_right", "gameplay_quad1", "turned_left", "turned_right", "menu_quad1"):
        assert name in captures and captures[name]["written"], f"missing capture {name}: {sorted(captures)}"
    for name in ("gameplay_left", "gameplay_right", "turned_left", "turned_right"):
        assert captures[name]["lit_fraction"] > 0.2, f"eye capture {name} is mostly black: {captures[name]}"

    def image(prefix: str, layer: str):
        return Image.open(profile / f"{prefix}_{layer}.tga").convert("RGB")

    left, right = image("xr_gameplay", "left"), image("xr_gameplay", "right")
    eye_difference = max(ImageStat.Stat(ImageChops.difference(left, right)).mean)
    assert eye_difference > 1.0, f"the eyes are identical: no parallax ({eye_difference:.3f})"
    turned = image("xr_turned", "left")
    turn_difference = max(ImageStat.Stat(ImageChops.difference(left, turned)).mean)
    assert turn_difference > 4.0, f"a 40 degree head turn barely changed the view ({turn_difference:.3f})"
    with Image.open(profile / "xr_gameplay_quad1.tga") as hud:
        alpha = hud.convert("RGBA").getchannel("A")
        covered = sum(alpha.histogram()[16:]) / float(hud.width * hud.height)
    assert 0.0 < covered < 0.9, f"the HUD layer should be a partial overlay ({covered:.3f} covered)"

    before = text.partition("VR_SNAP_BEFORE")[2].partition("VR_SNAP_AFTER")[0]
    after = text.partition("VR_SNAP_AFTER")[2]
    yaws_before, yaws_after = body_yaws(before), body_yaws(after)
    assert yaws_before and yaws_after, "vr_status did not report the body yaw"
    turn = yaw_delta(yaws_before[0], yaws_after[0])
    assert abs(turn + 45.0) < 1.0, f"a right snap turn should turn the body -45 degrees, turned {turn:.2f}"
    assert "VR_TRIGGER_BIND_RAN" in text, "the controller trigger never reached its binding"

    # the pause menu: the menu button opened it, the screen hangs opaque and
    # world-locked in front of the paused world, and the pointer sits where
    # the controller's ray meets it
    menu_log = text.partition("VR_TRIGGER_BIND_RAN")[2]
    assert "OpenXR: JOY7 down" in menu_log, "the controller's menu button never posted its key"
    assert "VR_MENU_OPEN" in menu_log, "the menu stage did not run"
    capture_frames = [e["frame"] for e in events if e.get("event") == "script_command" and e.get("command") == "capture"]
    menu_frames = [f for f in frames if f["frame"] >= capture_frames[-1]]
    assert menu_frames, "no frame followed the menu capture"
    screen_layer = menu_frames[0]["layers"][-1]
    assert screen_layer["type"] == "quad" and not screen_layer["flags"] & 0x2 and abs(screen_layer["z"] + 2.5) < 0.01, \
        f"the pause menu should hang an opaque screen 2.5 m ahead: {menu_frames[0]}"
    with Image.open(profile / "xr_menu_quad1.tga") as screen:
        screen = screen.convert("RGB")
        screen_height_m = SCREEN_WIDTH_M * screen.height / screen.width
        px = round((0.5 + POINTER_RIGHT_M / SCREEN_WIDTH_M) * screen.width)
        py = round((0.5 - POINTER_UP_M / screen_height_m) * screen.height)
        # the dot is white, ringed in black, about 16 px across at 1080 lines
        ring = max(6, round(screen.height * 12 / 1080))
        centre = min(screen.getpixel((px + dx, py + dy))[c] for dx in (-1, 0, 1) for dy in (-1, 0, 1) for c in range(3))
        border = max(max(screen.getpixel((px + dx, py + dy))) for dx, dy in ((ring, 0), (-ring, 0), (0, ring), (0, -ring)))
    assert centre > 200, f"no pointer at ({px}, {py}) on the menu screen (darkest centre channel {centre})"
    assert border < 90, f"the pointer at ({px}, {py}) lacks its dark ring (brightest ring channel {border})"
    assert "OpenXR: MOUSE1 down" in menu_log and "OpenXR: MOUSE1 up" in menu_log, \
        "the trigger did not click as a mouse button while pointing at the menu"
    # the hidden test window never has focus, as a desktop window seldom does
    # while the player wears the headset: the click must still reach the menu
    assert any([layer["type"] for layer in f["layers"]] == ["projection", "quad"] and f["layers"][1]["flags"] & 0x2
               for f in menu_frames), "clicking Resume with the pointer did not close the pause menu"

    # the runtime ends VR: the game carries on and keeps the player's setting
    before_exit, _, after_exit = menu_log.partition("VR_AFTER_EXIT")
    assert "OpenXR: the runtime ended the VR session" in before_exit, "the runtime's exit request was not honoured"
    assert "the runtime ended VR; vr_restart starts it again" in after_exit, "vr_status does not report the ended session"
    assert re.search(r'"vr_enable" is:"1"', after_exit), "ending VR from the runtime must leave vr_enable as the player set it"

    for name in ("left", "right", "quad1"):
        image("xr_gameplay", name).save(profile / f"xr_gameplay_{name}.png")
    turned.save(profile / "xr_turned_left.png")
    image("xr_menu", "quad1").save(profile / "xr_menu_quad1.png")
    print(f"OpenXR VR smoke: PASS (eye difference {eye_difference:.2f}, head turn {turn_difference:.2f}, "
          f"HUD coverage {covered:.3f}, pointer at {px},{py}); evidence={profile}")


if __name__ == "__main__":
    main()
