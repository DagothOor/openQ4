#!/usr/bin/env python3
"""Capture the ui_retained title, pause and loading screens in the engine.

Each scenario is one hidden, windowed client with a private savepath under
.tmp, installed Quake 4 assets and host mouse/controller input disabled. Stages
are console scripts: engine `screenshot` captures, `ui_retainedStatus` reports
and semantic `openq4_retainedGui` operations; no OS input or OS screenshot is
used. With --gate 0 the title and pause scenarios (whose real map load covers
the loading route) qualify that nothing retained loads; the loading scenario
opens its document with the developer `testGUI` command, which is not gated.
The default, --gate default, leaves ui_retained unset, as a player has it.

The fallback scenarios run as a private mod (fs_game) in the savepath, whose
files take precedence over openQ4's packs as any mod's do: a retained document
that cannot load, or a main menu without a page the home screens hand off to,
as a mod's own menu might be. Each screen must then present its stock GUI, and
ui_retainedStatus lists the fallback.

    python tools/ui/capture_retained_screens.py --assets "E:/SteamLibrary/steamapps/common/Quake 4" \
        --runtime .install --output .tmp/retained-screens/gl-720 --renderer gl --size 1280x720
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DONE = 'RETAINED_SCREENS_CAPTURE_COMPLETE'

# Scenario -> (map to load or None for the title, console stages).
SCENARIOS = {
    'title': (None, [
        'waitMsec 4000', 'ui_retainedStatus', 'screenshot "screenshots/title.tga"',
        # Depth: with the pointer at the top-trailing corner the backdrop layers lean away.
        'openq4_retainedGui state pointer_x 1', 'openq4_retainedGui state pointer_y -1', 'waitMsec 300',
        'screenshot "screenshots/title-depth.tga"', 'openq4_retainedGui state pointer_x 0', 'openq4_retainedGui state pointer_y 0',
        'openq4_retainedGui focus nav_loadgame', 'waitMsec 500', 'screenshot "screenshots/title-focus.tga"',
        'openq4_retainedGui event exitModalShow', 'waitMsec 500', 'ui_retainedStatus', 'screenshot "screenshots/title-exit.tga"',
        'openq4_retainedGui event exitModalHide', 'waitMsec 400',
        'openq4_retainedGui focus nav_settings', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0',
        'waitMsec 250', 'screenshot "screenshots/title-depart.tga"', 'waitMsec 1500', 'ui_retainedStatus',
        'screenshot "screenshots/title-settings.tga"',
    ]),
    'pause': ('game/airdefense1', [
        'openq4_assertMenuActivation 10000', 'waitMsec 1200', 'ui_retainedStatus', 'screenshot "screenshots/pause.tga"',
        'openq4_retainedGui focus nav_restart', 'waitMsec 400', 'screenshot "screenshots/pause-focus.tga"',
        'openq4_retainedGui event quitModalShow', 'waitMsec 500', 'screenshot "screenshots/pause-quit.tga"',
        # The modal holds focus until its 300 ms leave completes.
        'openq4_retainedGui event quitModalHide', 'waitMsec 600',
        # RESUME closes the screen at once; the softened view releases over 250 ms.
        'openq4_retainedGui focus nav_resume', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0',
        'waitMsec 100', 'ui_retainedStatus', 'screenshot "screenshots/pause-releasing.tga"',
        'waitMsec 700', 'ui_retainedStatus', 'screenshot "screenshots/pause-resumed.tga"',
    ]),
    # The level block's open objectives: airdefense1's first two objective
    # entities fire before the pause menu opens (trigger works in single player).
    'pause-objectives': ('game/airdefense1', [
        'trigger objectiveIntro', 'waitMsec 500', 'trigger objectiveMedic', 'waitMsec 1500',
        'openq4_assertMenuActivation 10000', 'waitMsec 1200', 'ui_retainedStatus', 'screenshot "screenshots/pause-objectives.tga"',
        'openq4_retainedGui focus nav_resume', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0', 'waitMsec 500',
    ]),
    # From game/medlabs on Kane is Strogg and the pause takes the Strogg family:
    # its labels arrive in runes and translate, and focus runs the scan bar.
    'pause-strogg': ('game/recomp', [
        'openq4_assertMenuActivation 10000', 'waitMsec 300', 'screenshot "screenshots/pause-strogg-translating.tga"',
        'waitMsec 1500', 'ui_retainedStatus', 'screenshot "screenshots/pause-strogg.tga"',
        'openq4_retainedGui focus nav_restart', 'waitMsec 120', 'screenshot "screenshots/pause-strogg-focus.tga"',
        'openq4_retainedGui event objectivesShow', 'waitMsec 1200', 'screenshot "screenshots/pause-strogg-objectives.tga"',
        'openq4_retainedGui event objectivesHide', 'waitMsec 1300',
        'openq4_retainedGui event quitModalShow', 'waitMsec 500', 'screenshot "screenshots/pause-strogg-quit.tga"',
        'openq4_retainedGui event quitModalHide', 'waitMsec 600',
        'openq4_retainedGui focus nav_resume', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0',
        'waitMsec 100', 'ui_retainedStatus', 'screenshot "screenshots/pause-strogg-releasing.tga"',
        'waitMsec 700', 'ui_retainedStatus', 'screenshot "screenshots/pause-strogg-resumed.tga"',
    ]),
    # The OBJECTIVES page: airdefense1's first objective completed and two
    # more held, so the page lists two plates and one completed row.
    'pause-objectives-page': ('game/airdefense1', [
        'trigger objectiveIntro', 'waitMsec 500', 'trigger objectiveMedic', 'waitMsec 500', 'trigger completeObjectiveIntro',
        'waitMsec 500', 'trigger objectiveReturnMedic', 'waitMsec 1500',
        'openq4_assertMenuActivation 10000', 'waitMsec 1200', 'screenshot "screenshots/objectives-menu.tga"',
        'openq4_retainedGui event objectivesShow', 'waitMsec 300', 'screenshot "screenshots/objectives-docking.tga"',
        'waitMsec 900', 'ui_retainedStatus', 'screenshot "screenshots/objectives-page.tga"',
        'openq4_retainedGui menu down 1', 'openq4_retainedGui menu down 0', 'waitMsec 300', 'screenshot "screenshots/objectives-scrolled.tga"',
        'openq4_retainedGui event objectivesHide', 'waitMsec 900', 'screenshot "screenshots/objectives-closed.tga"',
        'openq4_retainedGui focus nav_resume', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0',
        'waitMsec 600', 'ui_retainedStatus',
    ]),
    'loading': (None, [
        'waitMsec 3000', 'testGUI "guis/loading/loading.q4ui"', 'waitMsec 300',
        'openq4_retainedGui pending loading_levelshot gfx/guis/loadscreens/airdefense',
        'openq4_retainedGui pending loading_levelname "Air Defense Trenches"',
        'openq4_retainedGui pending loading_objectives "Fight through the trench network to the anti-aircraft battery."',
        'openq4_retainedGui pending loading_detail Corporal', 'openq4_retainedGui pending loading_phase ASSETS',
        'openq4_retainedGui pending loading_count "412/1630"',
        'openq4_retainedGui state map_loading 0.62', 'waitMsec 600', 'screenshot "screenshots/loading.tga"',
        # Pending values commit with the next state operation.
        'openq4_retainedGui pending loading_phase "LOAD TIME"', 'openq4_retainedGui pending loading_count "12.4 s"',
        'openq4_retainedGui event FinishedLoading', 'openq4_retainedGui state map_loading 1', 'waitMsec 600',
        'screenshot "screenshots/loading-ready.tga"',
        'openq4_retainedGui state loading_controller 1', 'waitMsec 300', 'screenshot "screenshots/loading-controller.tga"',
        'openq4_retainedGui state loading_controller 0',
        'openq4_retainedGui pending server_name "openQ4 Test Server"', 'openq4_retainedGui pending server_ip "192.168.1.20:28004"',
        'openq4_retainedGui pending server_limit "Frag limit 30 - Time limit 10"', 'openq4_retainedGui pending server_gametype Deathmatch',
        'openq4_retainedGui pending loading_detail Deathmatch',
        'openq4_retainedGui pending loading_levelshot gfx/guis/loadscreens/q4dm1',
        'openq4_retainedGui pending loading_levelname "Bloodwork"', 'openq4_retainedGui pending loading_ready 0',
        'openq4_retainedGui state loading_mp 1', 'waitMsec 600', 'screenshot "screenshots/loading-mp.tga"',
        'testGUI', 'waitMsec 300',
    ]),
    # A title document that cannot load: the stock title presents.
    'fallback-document': (None, [
        'waitMsec 4000', 'ui_retainedStatus', 'screenshot "screenshots/fallback-document.tga"',
    ]),
    # A main menu without the Demos page, as a mod's own menu might be: it
    # presents its own home screen, and the pause screen does not cover it either.
    'fallback-menu': (None, [
        'waitMsec 4000', 'ui_retainedStatus', 'screenshot "screenshots/fallback-menu.tga"',
    ]),
    # The retained SYSTEM page lacks some stock settings, so by default the
    # SYSTEM button opens the stock page.
    'system-default': (None, [
        'waitMsec 4000', 'openq4_guiAction main_b_settings', 'waitMsec 1500', 'openq4_guiAction set_b_system',
        'waitMsec 1500', 'openq4_guiGet p_settings_sys::visible', 'openq4_system report', 'ui_retainedStatus',
        'screenshot "screenshots/system-default.tga"',
    ]),
    # Opted into, the retained SYSTEM page opens from the SYSTEM button.
    'system-optin': (None, [
        'waitMsec 4000', 'openq4_guiAction main_b_settings', 'waitMsec 1500', 'openq4_guiAction set_b_system',
        'waitMsec 1500', 'openq4_system report', 'ui_retainedStatus', 'screenshot "screenshots/system-optin.tga"',
        'openq4_system back', 'waitMsec 1000', 'openq4_system report',
    ]),
    # Opted into, a SYSTEM page that cannot load: the same click opens the stock page.
    'fallback-system': (None, [
        'waitMsec 4000', 'openq4_guiAction main_b_settings', 'waitMsec 1500', 'openq4_guiAction set_b_system',
        'waitMsec 1500', 'openq4_guiGet p_settings_sys::visible', 'openq4_system report', 'ui_retainedStatus',
        'screenshot "screenshots/fallback-system.tga"',
    ]),
    # A Single Player selector that cannot load: the stock selector opens.
    'fallback-campaign': (None, [
        'waitMsec 4000', 'openq4_guiAction main_b_newgame', 'waitMsec 2500', 'openq4_system report', 'ui_retainedStatus',
        'screenshot "screenshots/fallback-campaign.tga"',
    ]),
}

# Not a retained document: it fails to load with diagnostics.
BROKEN_DOCUMENT = '{ "openq4": "not a retained document" }\n'


def stock_menu_without_demos(runtime: Path) -> str:
    """The installed main menu with its Demos page renamed, as a mod's menu might lack it."""
    with zipfile.ZipFile(runtime / 'baseoq4' / 'pak0.pk4') as pack:
        menu = pack.read('guis/mainmenu.gui').decode('utf-8', errors='surrogateescape')
    assert 'windowDef main_b_demos' in menu
    return menu.replace('main_b_demos', 'main_b_records')


# CVars a scenario sets beyond the common ones.
SCENARIO_CVARS = {'system-optin': {'ui_retainedSystem': '1'}, 'fallback-system': {'ui_retainedSystem': '1'}}

# The private mod the fallback scenarios run as, and the files it provides.
FALLBACK_MOD = 'retainedfallback'
OVERRIDES = {
    'fallback-document': {'guis/menu/title.q4ui': lambda runtime: BROKEN_DOCUMENT},
    'fallback-menu': {'guis/mainmenu.gui': stock_menu_without_demos},
    'fallback-system': {'guis/menu/settings/system.q4ui': lambda runtime: BROKEN_DOCUMENT},
    'fallback-campaign': {'guis/menu/singleplayer.q4ui': lambda runtime: BROKEN_DOCUMENT},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def to_png(tga: Path) -> Path | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    png = tga.with_suffix('.png')
    Image.open(tga).convert('RGB').save(png)
    return png


def mod_manifest(runtime: Path) -> str:
    """The runtime's own manifest under a test name, so the mod matches its version."""
    manifest = json.loads((runtime / 'baseoq4' / 'mod.json').read_text(encoding='utf-8'))
    manifest['name'] = 'openQ4 retained fallback test'
    return json.dumps(manifest, indent=2) + '\n'


def run(args, scenario: str) -> dict:
    output = (args.output / scenario).resolve()
    overrides_files = OVERRIDES.get(scenario, {})
    game_dir = FALLBACK_MOD if overrides_files else 'baseoq4'
    game = output / 'save' / game_dir
    game.mkdir(parents=True)
    level, stages = SCENARIOS[scenario]
    if overrides_files:
        (game / 'mod.json').write_text(mod_manifest(args.runtime.resolve()), encoding='utf-8')
    for relative, content in overrides_files.items():
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content(args.runtime.resolve()).encode('utf-8', errors='surrogateescape'))
    lines = [f'echo RETAINED_STAGE {scenario}'] + stages + ['ui_retainedStatus', f'echo {DONE}', 'quit']
    cfg = game / f'retained-{scenario}.cfg'
    cfg.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    width, height = args.size.split('x')
    overrides = {
        'fs_basepath': str(args.assets.resolve()), 'fs_savepath': str(output / 'save'), 'fs_devpath': str(output / 'save'),
        'fs_game': game_dir, 'logFile': '2', 'logFileName': 'logs/openq4.log',
        'r_fullscreen': '0', 'r_fullscreenDesktop': '0', 'r_borderless': '0', 'r_borderlessDefaultMigrated': '1', 'r_hiddenWindow': '1',
        'r_windowWidth': width, 'r_windowHeight': height, 'r_mode': '-1', 'r_customWidth': width, 'r_customHeight': height,
        'r_renderApi': args.renderer, 'r_multiSamples': '0', 'r_swapInterval': '1',
        'in_mouse': '0', 'in_joystick': '0', 'in_joystickRumble': '0', 's_noSound': '1',
        'com_skipLogoVideos': '1', 'g_autoSkipCinematics': '1', 'com_skipLoadingContinue': '1', 'com_maxfps': '60',
        'developer': '0', 'ui_autoJoin': '0', 'sys_lang': args.language,
        'ui_retainedTrace': '1', 'ui_retainedReducedMotion': '0',
    }
    if args.gate != 'default':
        overrides['ui_retained'] = args.gate
    overrides.update(SCENARIO_CVARS.get(scenario, {}))
    command = [str(args.runtime.resolve() / ('openQ4-client_x64.exe' if os.name == 'nt' else 'openQ4-client_x64'))]
    for key, value in overrides.items():
        command += ['+set', key, value]
    if level:
        command += ['+set', 'g_autoExecAfterMapLoad', cfg.name, '+set', 'g_autoExecAfterMapLoadDelayMs', '3000', '+map', level]
    else:
        command += ['+exec', cfg.name]
    options = {'env': {**os.environ, 'TEMP': str(ROOT / '.tmp'), 'TMP': str(ROOT / '.tmp')}}
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        options.update(startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
    started = time.monotonic()
    with (output / 'process.log').open('w', encoding='utf-8') as process_log:
        process = subprocess.Popen(command, cwd=args.runtime.resolve(), stdout=process_log, stderr=subprocess.STDOUT, **options)
        try:
            returncode = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            returncode = None
    log_path = game / 'logs' / 'openq4.log'
    log = re.sub(r'\^[0-9]', '', log_path.read_text(encoding='utf-8', errors='replace')) if log_path.is_file() else ''
    shots = []
    for tga in sorted((game / 'screenshots').glob('*.tga')):
        png = to_png(tga)
        shots.append({'tga': str(tga.relative_to(ROOT)), 'png': str(png.relative_to(ROOT)) if png else None, 'sha256': digest(tga)})
    status = re.findall(r'OPENQ4_RETAINED .*', log)
    return {
        'scenario': scenario, 'gate': args.gate, 'renderer': args.renderer, 'size': args.size, 'returncode': returncode,
        'seconds': round(time.monotonic() - started, 1), 'complete': DONE in log, 'status': status,
        'retained_loaded': re.findall(r'RETAINED_GUI_LOADED (\S+)', log),
        'session_requests': re.findall(r'RETAINED_GUI_SESSION .*', log),
        'loading_phases': re.findall(r'RETAINED_LOADING_PHASE .*', log),
        'retained_warnings': [line for line in log.splitlines() if 'retained' in line.lower() and ('WARNING' in line or 'ERROR' in line)],
        'gui_values': re.findall(r'GUI_VALUE .*', log), 'system_reports': re.findall(r'OPENQ4_SYSTEM .*', log),
        'game_dir': game_dir, 'overrides': sorted(overrides_files),
        'errors': [line for line in log.splitlines() if 'ERROR:' in line or 'FATAL:' in line],
        'screenshots': shots, 'command': command, 'log': str(log_path.relative_to(ROOT)) if log_path.is_file() else None,
        'host_input_injection': False, 'windowed': True, 'hidden_window': True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.install')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--renderer', choices=('gl', 'vulkan'), default='gl')
    parser.add_argument('--size', default='1280x720')
    parser.add_argument('--gate', choices=('0', '1', 'default'), default='default',
                        help='ui_retained for the run; default leaves it unset')
    parser.add_argument('--language', default='english')
    parser.add_argument('--scenario', action='append', choices=sorted(SCENARIOS))
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a new output directory')
    if not args.output.resolve().is_relative_to((ROOT / '.tmp').resolve()):
        parser.error('captures belong under the repository .tmp directory')
    results = [run(args, scenario) for scenario in (args.scenario or list(SCENARIOS))]
    report = args.output / 'capture.json'
    report.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    for result in results:
        print(f"{result['scenario']}: exit={result['returncode']} complete={result['complete']} "
              f"loaded={result['retained_loaded']} shots={len(result['screenshots'])} errors={len(result['errors'])}")
        for line in result['status']:
            print('   ', line)
        for line in result['loading_phases']:
            print('    ~', line)
        for line in result['retained_warnings'][:10]:
            print('    !', line)
    return 0 if all(result['complete'] and result['returncode'] == 0 for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
