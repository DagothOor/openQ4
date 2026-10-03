#!/usr/bin/env python3
"""Author the SYSTEM page's deferred render options and their status.

Preload Light Grids edits r_lightGridPreload in the ordinary draft. Apply
completes it automatically, and the next map load uses it; a status line
under the row says what the loaded map does with its light grids and when a
saved change waits for the next load. Renderer Fallback edits r_renderer;
Apply restarts the device on the same display and completes once the
renderer reports the request. It is available only where the renderer can
report its selection, and a notice appears while it reports a fallback.

The Keep/Revert question belongs to a display confirmation. An automatic
attempt never asks it: the panel opens for such an attempt only when it needs
recovery (a failed preparation or restore, or a save that did not finish),
and then needs a title that fits any attempt. While the service reports
RecoveryRequired the title reads the neutral recovery heading; otherwise it
keeps the Keep question.

This tool owns the preload and renderer rows, their help, status and notice
lines, their states,
aliases, bindings and timelines, the confirmation title's text binding and the
renderOptions extension record. --check verifies reproducible generation
without writing.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from update_system_presets import allowed, length, load, nodes, renamed, typed

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('content/baseoq4/pak0/guis/menu/settings/system.q4ui')
TITLE = 'confirmation-panel-title'
KEEP_TITLE, RECOVERY_TITLE = '#str_229993', '#str_230077'
RECOVERY_REQUIRED = 3  # SettingsPhase::RecoveryRequired
# No other SYSTEM tool inserts beside the VSync bindings, so the title binding
# keeps one stable place however the passes are ordered.
ANCHOR = 'settings_vsync.opacity'

ROW, SOURCE_ROW, KEY = 'settings_lightgrid_preload', 'settings_irradiance', 'r_lightGridPreload'
LABEL, HELP = '#str_42820', '#str_42821'
# The loaded map keeps the previous choice, preloads, streams, or has none.
PENDING, PRELOADS, STREAMS, NO_GRIDS = '#str_230078', '#str_230079', '#str_230080', '#str_230081'
STATUS_KEYS = ('committed', 'mapLoaded', 'consumed', 'effective', 'pending')
# The renderer fallback: a two-option choice cloned from V-Sync, last in the
# column, with a notice while the running renderer reports a fallback.
RENDERER_ROW, CHOICE_SOURCE, RENDERER_KEY = 'settings_renderer', 'settings_vsync', 'r_renderer'
RENDERER_LABEL, RENDERER_OPTIONS, FALLBACK = '#str_41103', '#str_41104', '#str_230082'
RENDERER_VALUES = ('best', 'arb2')


def state(name):
    return {'state': 'settings.lightGrid.' + name}


def select(condition, shown, hidden):
    return {'op': 'select', 'args': [condition, shown, hidden]}


def compose(document):
    result = copy.deepcopy(document)
    index = nodes(result['root'])
    title = index.get(TITLE)
    if title is None or title['properties'].get('text') != {'type': 'text', 'value': KEEP_TITLE}:
        raise ValueError('The SYSTEM confirmation title no longer reads the Keep question; review its binding')
    action = {'input': 'boolean', 'operation': 'settings.system.edit', 'arguments': {KEY: {'input': 'value'}}}
    if result['actions'].get('edit.' + KEY) != action:
        raise ValueError('Review the existing light-grid preload proposal contract')
    source = index.get(SOURCE_ROW)
    if source is None or source.get('control', {}).get('role') != 'toggle':
        raise ValueError('The Irradiance Volumes toggle the preload row is cloned from changed')

    # The row: a toggle cloned from Irradiance Volumes, placed after it. Its
    # help and status lines sit inside the card under the label, so focus
    # reveals the whole explanation and the plate and frame grow around it.
    row = renamed(source, SOURCE_ROW, ROW)
    row['control'].update(label=LABEL, action='edit.' + KEY, value={'state': 'settings.draft.' + KEY})
    nodes(row)[ROW + '-label']['properties']['text'] = typed('text', LABEL)
    hint = index['dimensions-hint']
    helper = renamed(copy.deepcopy(hint), 'dimensions-hint', ROW + '-help')
    helper['properties'].update({'text': typed('text', HELP), 'white-space': typed('keyword', 'pre-line'),
                                 'width': length(100, '%'), 'margin-top': length(4), 'margin-bottom': length(0)})
    status = renamed(copy.deepcopy(hint), 'dimensions-hint', ROW + '-status')
    # Hidden until a map is loaded; its static text is the binding's last case.
    status['properties'].update({'text': typed('text', NO_GRIDS), 'display': typed('keyword', 'none'),
                                 'width': length(100, '%'), 'margin-top': length(4), 'margin-bottom': length(0)})
    label_at = next(i for i, child in enumerate(row['children']) if child['id'] == ROW + '-label') + 1
    row['children'][label_at:label_at] = [helper, status]
    owned = {ROW, ROW + '-help', ROW + '-status'}
    column = next(node for node in index.values() if any(child['id'] == SOURCE_ROW for child in node.get('children', [])))
    children = [child for child in column['children'] if child['id'] not in owned]
    position = next(i for i, child in enumerate(children) if child['id'] == SOURCE_ROW) + 1
    column['children'] = children[:position] + [row] + children[position:]

    # Service status keys and the row's draft/applied readback.
    for name in STATUS_KEYS:
        result['state']['settings.lightGrid.' + name] = {'type': 'boolean', 'initial': False}
    for phase in ('draft', 'baseline'):
        variable = phase + 'LightGridPreload'
        result['presentationVariables'][variable] = {'type': 'boolean', 'initial': False,
                                                     'value': {'state': 'settings.' + phase + '.' + KEY}}
        result['aliases'][variable] = {'variable': variable}

    # Bindings: the row follows the shared editing rule; the status line shows
    # only while a map is loaded. The confirmation title names recovery.
    bindings = [entry for entry in result.get('bindings', [])
                if entry['node'] not in owned and entry['id'] != TITLE + '.text']
    added = [
        {'id': ROW + '.enabled', 'node': ROW, 'property': 'enabled', 'value': allowed()},
        {'id': ROW + '.opacity', 'node': ROW, 'property': 'opacity', 'value': select(allowed(), 1, 0.4)},
        {'id': ROW + '-status.display', 'node': ROW + '-status', 'property': 'display',
         'value': select(state('mapLoaded'), 'block', 'none')},
        {'id': ROW + '-status.text', 'node': ROW + '-status', 'property': 'text',
         'value': select(state('pending'), PENDING, select(state('consumed'), select(state('effective'), PRELOADS, STREAMS), NO_GRIDS))},
    ]
    anchor = next((i for i, entry in enumerate(bindings) if entry['id'] == SOURCE_ROW + '.opacity'), None)
    if anchor is None:
        raise ValueError('The Irradiance Volumes opacity binding is missing; choose a new anchor for the preload row')
    bindings[anchor + 1:anchor + 1] = added
    title_binding = {'id': TITLE + '.text', 'node': TITLE, 'property': 'text', 'value': select(
        {'op': '==', 'args': [{'state': 'settings.phase'}, RECOVERY_REQUIRED]}, RECOVERY_TITLE, KEEP_TITLE)}
    position = next((i for i, entry in enumerate(bindings) if entry['id'] == ANCHOR), None)
    if position is None:
        raise ValueError('The SYSTEM VSync opacity binding is missing; choose a new anchor for the confirmation title')
    bindings.insert(position + 1, title_binding)
    result['bindings'] = bindings

    # Feedback timelines cloned from the source row's states.
    timelines = [entry for entry in result['timelines'] if not entry['id'].startswith(ROW + '.')]
    cloned = [renamed(entry, SOURCE_ROW, ROW) for entry in timelines if entry['id'].startswith(SOURCE_ROW + '.')]
    if {entry['id'] for entry in cloned} != {ROW + '.' + s for s in ('default', 'hover', 'focus', 'pressed', 'disabled')}:
        raise ValueError('The Irradiance Volumes feedback timelines changed')
    last = max(i for i, entry in enumerate(timelines) if entry['id'].startswith(SOURCE_ROW + '.'))
    result['timelines'] = timelines[:last + 1] + cloned + timelines[last + 1:]

    # The renderer row: available only where the renderer can prove the change.
    action = {'input': 'string', 'operation': 'settings.system.edit', 'arguments': {RENDERER_KEY: {'input': 'value'}}}
    if result['actions'].get('edit.' + RENDERER_KEY) != action:
        raise ValueError('Review the existing renderer fallback proposal contract')
    index = nodes(result['root'])
    choice_source = index.get(CHOICE_SOURCE)
    if choice_source is None or choice_source['control'].get('role') != 'choice' or len(choice_source['control']['options']) != 2:
        raise ValueError('The V-Sync choice the renderer row is cloned from changed')
    choice = renamed(choice_source, CHOICE_SOURCE, RENDERER_ROW)
    choice['control'].update(label=RENDERER_LABEL, action='edit.' + RENDERER_KEY, value={'state': 'settings.draft.' + RENDERER_KEY})
    parts = nodes(choice)
    parts[RENDERER_ROW + '-label']['properties']['text'] = typed('text', RENDERER_LABEL)
    for index_, value in enumerate(RENDERER_VALUES):
        option = choice['control']['options'][index_]
        option.update(label=RENDERER_OPTIONS, labelIndex=index_, value=value)
        parts[option['parts']['label']]['properties']['text'] = typed('text', RENDERER_OPTIONS)
    # The fallback notice sits inside the card under the value, so focus
    # reveals it, the plate grows around it and the popup opens below it.
    notice = renamed(copy.deepcopy(index['dimensions-hint']), 'dimensions-hint', RENDERER_ROW + '-status')
    notice['properties'].update({'text': typed('text', FALLBACK), 'display': typed('keyword', 'none'),
                                 'width': length(100, '%'), 'margin-top': length(4), 'margin-bottom': length(0)})
    value_at = next(i for i, child in enumerate(choice['children']) if child['id'] == RENDERER_ROW + '-value') + 1
    choice['children'][value_at:value_at] = [notice]
    renderer_owned = {RENDERER_ROW, RENDERER_ROW + '-status'}
    column = next(node for node in index.values() if any(child['id'] == CHOICE_SOURCE for child in node.get('children', [])))
    children = [child for child in column['children'] if child['id'] not in renderer_owned]
    position = next(i for i, child in enumerate(children) if child['id'] == CHOICE_SOURCE) + 1
    column['children'] = children[:position] + [choice] + children[position:]
    for name in ('available', 'fallback'):
        result['state']['settings.renderer.' + name] = {'type': 'boolean', 'initial': False}
    for phase in ('draft', 'baseline'):
        variable = phase + 'Renderer'
        result['presentationVariables'][variable] = {'type': 'string', 'initial': '',
                                                     'value': {'state': 'settings.' + phase + '.' + RENDERER_KEY}}
        result['aliases'][variable] = {'variable': variable}
    available = {'state': 'settings.renderer.available'}
    bindings = [entry for entry in result['bindings'] if entry['node'] not in renderer_owned]
    position = next(i for i, entry in enumerate(bindings) if entry['id'] == TITLE + '.text') + 1
    bindings[position:position] = [
        {'id': RENDERER_ROW + '.enabled', 'node': RENDERER_ROW, 'property': 'enabled', 'value': {'op': '&&', 'args': [allowed(), available]}},
        # Dims like its column while the page is busy, and like MSAA while the
        # renderer cannot apply it.
        {'id': RENDERER_ROW + '.opacity', 'node': RENDERER_ROW, 'property': 'opacity',
         'value': select(available, select(allowed(), 1, 0.4), 0.45)},
        # The notice describes the applied renderer, so a different pick hides it.
        {'id': RENDERER_ROW + '-status.display', 'node': RENDERER_ROW + '-status', 'property': 'display',
         'value': select({'op': '&&', 'args': [{'state': 'settings.renderer.fallback'},
                                               {'op': '==', 'args': [{'state': 'settings.draft.' + RENDERER_KEY},
                                                                     {'state': 'settings.baseline.' + RENDERER_KEY}]}]},
                         'block', 'none')}]
    result['bindings'] = bindings
    timelines = [entry for entry in result['timelines'] if not entry['id'].startswith(RENDERER_ROW + '.')]
    cloned = [renamed(entry, CHOICE_SOURCE, RENDERER_ROW) for entry in timelines if entry['id'].startswith(CHOICE_SOURCE + '.')]
    if {entry['id'] for entry in cloned} != {RENDERER_ROW + '.' + s for s in ('default', 'hover', 'focus', 'pressed', 'disabled')}:
        raise ValueError('The V-Sync feedback timelines changed')
    last = max(i for i, entry in enumerate(timelines) if entry['id'].startswith(CHOICE_SOURCE + '.'))
    result['timelines'] = timelines[:last + 1] + cloned + timelines[last + 1:]

    result.setdefault('extensions', {}).setdefault('openq4', {})['renderOptions'] = {
        'scope': 'Preload Light Grids edits the draft; Apply completes it automatically without Keep/Revert, reporting '
                 'Applying, Restoring and Saving status, and the next map load uses it. The status line names what the '
                 'loaded map does with its light grids and when a saved change waits for the next load. The confirmation '
                 'panel opens for an automatic attempt only when it needs recovery, under the neutral recovery title.',
        'confirmationTitle': {'recoveryPhase': RECOVERY_REQUIRED, 'recovery': RECOVERY_TITLE, 'otherwise': KEEP_TITLE},
        'preloadRow': {'control': ROW, 'clonedFrom': SOURCE_ROW, 'setting': KEY,
                       'status': {'pending': PENDING, 'preloads': PRELOADS, 'streams': STREAMS, 'noGrids': NO_GRIDS}},
        'rendererRow': {'control': RENDERER_ROW, 'clonedFrom': CHOICE_SOURCE, 'setting': RENDERER_KEY,
                        'values': list(RENDERER_VALUES), 'fallbackNotice': FALLBACK,
                        'availability': 'A presenting OpenGL renderer that reports its selection; Vulkan has one back end.'},
        'localization': [KEEP_TITLE, RECOVERY_TITLE, '#str_230073', '#str_230074', '#str_230075', '#str_230076',
                         LABEL, HELP, PENDING, PRELOADS, STREAMS, NO_GRIDS, RENDERER_LABEL, RENDERER_OPTIONS, FALLBACK],
        'remaining': 'The display device and resolution rows follow in their own increments.'}
    nodes(result['root'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / SOURCE)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    prefix, document = load(args.source)
    result = compose(document)
    if args.check:
        if result != document:
            raise SystemExit('SYSTEM render options differ from their authoring definition')
    else:
        args.source.write_text(prefix + json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
