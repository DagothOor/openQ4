#!/usr/bin/env python3
"""Author SYSTEM display controls using its shared editable vector artwork.

Selections only edit the existing typed draft. Apply/Keep/Revert and display
recovery remain owned by the settings service, including unsupported requests.
The pass also declares the display list keys the service publishes
(system_display_catalog.py). Display Device and Expand Across Displays read
them; the resolution and refresh rows are still to come.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from update_system_presets import allowed, length, load, nodes, renamed, typed
import system_display_catalog

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'content/baseoq4/pak0/guis/menu/settings/system.q4ui'
# id, CVar, label, source artwork, alias, option labels, exact typed values
FIELDS = (
    ('settings_fullscreen', 'r_fullscreen', '#str_200147', 'settings_shadows', 'Fullscreen', None, None),
    ('settings_borderless', 'r_borderless', '#str_229909', 'settings_shadows', 'Borderless', None, None),
    ('settings_fullscreen_policy', 'r_fullscreenDesktop', '#str_229910', 'settings_vsync', 'FullscreenPolicy', '#str_229911', (True, False)),
    ('settings_msaa', 'r_multiSamples', '#str_41093', 'settings_postaa', 'MSAA', '#str_230020', (0, 2, 4, 8, 16)),
)
# The display device: Auto, then one option per device list slot, labelled
# from the list. It picks through the list token, so a pick names the list
# the player saw. Eight rows show, as the visual specification's dropdowns do.
DEVICE, DEVICE_KEY, DEVICE_LABEL, DEVICE_SOURCE, DEVICE_ALIAS = (
    'settings_display_device', 'r_screen', '#str_229912', 'settings_postaa', 'DisplayDevice')
DEVICE_ACTION, AUTO, ROWS, ROW_HEIGHT = 'display.select', '#str_229914', 8, 36
# Expanding across displays: No or Yes, as V-Sync answers; the stock
# "Primary Display Only" and "Span All Displays" do not fit the largest text
# size in every language. A span needs the lists to allow one, and a
# borderless window or desktop fullscreen; exclusive fullscreen cannot span.
SPAN, SPAN_KEY, SPAN_LABEL, SPAN_SOURCE, SPAN_ALIAS, SPAN_OPTIONS = (
    'settings_multiscreen', 'r_multiScreen', '#str_229915', 'settings_vsync', 'MultiScreen', '#str_200059')
# Why Yes is unavailable: the window mode, or displays that cannot span.
SPAN_NEEDS_WINDOW, SPAN_UNAVAILABLE = '#str_230088', '#str_230089'


def display(name):
    return {'state': system_display_catalog.PREFIX + name}


def draft(key):
    return {'state': 'settings.draft.' + key}


def baseline(key):
    return {'state': 'settings.baseline.' + key}


def op(name, *args):
    return {'op': name, 'args': list(args)}


def options(field, ident, entries):
    """Replace a cloned choice's options and popup rows with entries of
    (option fields, row label text)."""
    control = field['control']
    parts = nodes(field)
    option_template = copy.deepcopy(control['options'][0])
    row_template = copy.deepcopy(parts[ident + '-option-0'])
    control['options'] = []
    parts[ident + '-content']['children'] = []
    for i, (fields, text) in enumerate(entries):
        option_id = ident + '-option-' + str(i)
        option = renamed(option_template, ident + '-option-0', option_id)
        option.pop('labelIndex', None)
        option.update(fields)
        control['options'].append(option)
        row = renamed(row_template, ident + '-option-0', option_id)
        nodes(row)[option_id + '-label']['properties']['text'] = typed('text', text)
        parts[ident + '-content']['children'].append(row)


def compose(document):
    result = copy.deepcopy(document)
    index = nodes(result['root'])
    controls = []
    result['state']['settings.msaaAvailable'] = {'type': 'boolean', 'initial': False}
    result['presentationVariables']['msaaAvailable'] = {
        'type': 'boolean', 'initial': False, 'value': {'state': 'settings.msaaAvailable'}}
    result['aliases']['msaaAvailable'] = {'variable': 'msaaAvailable'}
    system_display_catalog.declare(result)
    for ident, key, label, original, alias, labels, options_ in FIELDS:
        field = renamed(index[original], original, ident)
        control = field['control']
        control.update(label=label, action='edit.' + key, value={'state': 'settings.draft.' + key})
        fi = nodes(field)
        fi[ident + '-label']['properties']['text'] = typed('text', label)
        kind = 'number' if key == 'r_multiSamples' else 'boolean'
        action = {'input': kind, 'operation': 'settings.system.edit', 'arguments': {key: {'input': 'value'}}}
        if result['actions'].get('edit.' + key) != action:
            raise ValueError('Review the existing display proposal contract: ' + key)
        if options_ is not None:
            option_template = copy.deepcopy(control['options'][0])
            row_template = copy.deepcopy(fi[ident + '-option-0'])
            control['options'] = []
            fi[ident + '-content']['children'] = []
            for i, value in enumerate(options_):
                option_id = ident + '-option-' + str(i)
                option = renamed(option_template, ident + '-option-0', option_id)
                option.update(label=labels, labelIndex=i, value=value)
                control['options'].append(option)
                row = renamed(row_template, ident + '-option-0', option_id)
                nodes(row)[option_id + '-label']['properties']['text'] = typed('text', labels)
                fi[ident + '-content']['children'].append(row)
        controls.append(field)
        for phase in ('draft', 'baseline'):
            variable = phase + alias
            result['presentationVariables'][variable] = {
                'type': kind, 'initial': 0 if kind == 'number' else False,
                'value': {'state': 'settings.' + phase + '.' + key}}
            result['aliases'][variable] = {'variable': variable}
        for group in ('bindings', 'timelines'):
            result[group] = [entry for entry in result[group] if not entry['id'].startswith(ident + '.')]
            position = next(i for i, entry in enumerate(result[group]) if entry['id'].startswith('settings_ui_scale.'))
            available = ({'op': '&&', 'args': [allowed(), {'state': 'settings.msaaAvailable'}]}
                         if key == 'r_multiSamples' else allowed())
            entries = ([{'id': ident + '.enabled', 'node': ident, 'property': 'enabled', 'value': available}]
                       if group == 'bindings' else [renamed(entry, original, ident) for entry in result[group]
                                                   if entry['id'].startswith(original + '.')])
            if group == 'bindings' and key == 'r_multiSamples':
                entries.append({'id': ident + '.availabilityOpacity', 'node': ident, 'property': 'opacity',
                                'value': {'op': 'select', 'args': [{'state': 'settings.msaaAvailable'}, 1, .45]}})
            result[group][position:position] = entries

    # Display Device picks through the list token instead of editing r_screen,
    # so the unused direct edit goes.
    direct = {'input': 'number', 'operation': 'settings.system.edit', 'arguments': {DEVICE_KEY: {'input': 'value'}}}
    if result['actions'].pop('edit.' + DEVICE_KEY, direct) != direct:
        raise ValueError('Review the existing display device proposal contract')
    result['actions'][DEVICE_ACTION] = {'input': 'number', 'operation': 'settings.system.display',
                                        'arguments': {'index': {'input': 'value'}, 'catalog': display('catalog')}}
    span_action = {'input': 'number', 'operation': 'settings.system.edit', 'arguments': {SPAN_KEY: {'input': 'value'}}}
    if result['actions'].get('edit.' + SPAN_KEY) != span_action:
        raise ValueError('Review the existing span proposal contract')
    device = renamed(index[DEVICE_SOURCE], DEVICE_SOURCE, DEVICE)
    device['control'].update(label=DEVICE_LABEL, action=DEVICE_ACTION, value=draft(DEVICE_KEY),
                             visibleRows=ROWS, optionCount=display('optionCount'))
    parts = nodes(device)
    parts[DEVICE + '-label']['properties']['text'] = typed('text', DEVICE_LABEL)
    for part in (DEVICE + '-popup', DEVICE + '-viewport'):
        parts[part]['properties']['height'] = length(ROWS * ROW_HEIGHT)
    # A slot past the connected displays names a stale choice; it cannot be
    # picked. Painted slot labels replace the row text, which only has to be
    # a valid key.
    options(device, DEVICE, [({'label': AUTO, 'labelIndex': 0, 'value': -1}, AUTO)] + [
        ({'label': display(f'{slot}.label'), 'value': slot, 'enabled': op('<', slot, display('count'))}, DEVICE_LABEL)
        for slot in range(system_display_catalog.DEVICE_SLOTS)])
    span = renamed(index[SPAN_SOURCE], SPAN_SOURCE, SPAN)
    span['control'].update(label=SPAN_LABEL, action='edit.' + SPAN_KEY, value=draft(SPAN_KEY))
    nodes(span)[SPAN + '-label']['properties']['text'] = typed('text', SPAN_LABEL)
    spannable = op('&&', display('spanAvailable'), op('||', op('&&', draft('r_fullscreen'), draft('r_fullscreenDesktop')),
                                                       op('&&', op('!', draft('r_fullscreen')), draft('r_borderless'))))
    options(span, SPAN, [({'label': SPAN_OPTIONS, 'labelIndex': 0, 'value': 0}, SPAN_OPTIONS),
                         ({'label': SPAN_OPTIONS, 'labelIndex': 1, 'value': 1, 'enabled': spannable}, SPAN_OPTIONS)])
    # The reason sits inside the card under the value, as the renderer
    # notice does, so focus reveals it and the list opens below it.
    reason = renamed(copy.deepcopy(index['dimensions-hint']), 'dimensions-hint', SPAN + '-status')
    reason['properties'].update({'text': typed('text', SPAN_NEEDS_WINDOW), 'display': typed('keyword', 'none'),
                                 'width': length(100, '%'), 'margin-top': length(4), 'margin-bottom': length(0)})
    value_at = next(i for i, child in enumerate(span['children']) if child['id'] == SPAN + '-value') + 1
    span['children'][value_at:value_at] = [reason]
    # Shown on several displays, and on one while the draft still names a
    # display or a span the lists cannot offer, or holds a change not yet
    # applied: a recorded pick whose monitor changed keeps its row, so it can
    # be chosen again. Without lists, as when the topology capture failed,
    # neither row can work, so both stay hidden like the stock rows.
    shown = {DEVICE: op('&&', display('available'), op('||', op('||', op('>', display('count'), 1),
                                                                      op('>=', draft(DEVICE_KEY), display('count'))),
                                                         op('!=', draft(DEVICE_KEY), baseline(DEVICE_KEY)))),
             SPAN: op('&&', display('available'), op('||', op('||', op('>', display('count'), 1), op('!=', draft(SPAN_KEY), 0)),
                                                       op('!=', draft(SPAN_KEY), baseline(SPAN_KEY))))}
    for ident, key, alias, original in ((DEVICE, DEVICE_KEY, DEVICE_ALIAS, DEVICE_SOURCE), (SPAN, SPAN_KEY, SPAN_ALIAS, SPAN_SOURCE)):
        for phase in ('draft', 'baseline'):
            variable = phase + alias
            result['presentationVariables'][variable] = {'type': 'number', 'initial': 0,
                                                         'value': {'state': 'settings.' + phase + '.' + key}}
            result['aliases'][variable] = {'variable': variable}
        for group in ('bindings', 'timelines'):
            result[group] = [entry for entry in result[group] if not entry['id'].startswith((ident + '.', ident + '-status.'))]
            position = next(i for i, entry in enumerate(result[group]) if entry['id'].startswith('settings_ui_scale.'))
            entries = ([{'id': ident + '.enabled', 'node': ident, 'property': 'enabled', 'value': op('&&', allowed(), display('available'))},
                        {'id': ident + '.display', 'node': ident, 'property': 'display',
                         'value': op('select', shown[ident], 'block', 'none')}]
                       if group == 'bindings' else [renamed(entry, original, ident) for entry in result[group]
                                                   if entry['id'].startswith(original + '.')])
            if group == 'bindings' and ident == SPAN:
                entries += [{'id': SPAN + '-status.display', 'node': SPAN + '-status', 'property': 'display',
                             'value': op('select', op('!', spannable), 'block', 'none')},
                            {'id': SPAN + '-status.text', 'node': SPAN + '-status', 'property': 'text',
                             'value': op('select', display('spanAvailable'), SPAN_NEEDS_WINDOW, SPAN_UNAVAILABLE)}]
            result[group][position:position] = entries
    column = copy.deepcopy(index['image-column'])
    column['id'] = 'display-column'
    title = copy.deepcopy(column['children'][0]); title['id'] = 'display-title'
    title['properties']['text'] = typed('text', '#str_229900')
    column['properties'].update({'width': length(20, 'em'), 'min-width': length(0), 'max-width': length(100, '%')})
    column['children'] = [title, device, span, *controls]
    body = index['settings-body']
    body['children'] = [child for child in body['children'] if child['id'] != 'display-column']
    position = next(i for i, child in enumerate(body['children']) if child['id'] in ('dimensions-column', 'image-column'))
    body['children'].insert(position, column)
    result['extensions']['openq4']['displayControls'] = {
        'scope': 'Display Device, Expand Across Displays, fullscreen, borderless, fullscreen policy and MSAA edit the existing draft. Apply uses owned Keep/Revert recovery; unsupported device requests do not bypass validation.',
        'remaining': 'The resolution and refresh rows over the published display lists, dimension editors, full settings effects and screen acceptance remain required.',
        'displayLists': 'settings.display.* keys from system_display_catalog.py: owner-only lists the settings service builds from the display topology.',
        'deviceRow': 'Auto and the device list slots, labelled from the list; a pick sends its slot and the list token, and a display that is not connected cannot be picked. Hidden on one display unless the draft names a display the list lacks or holds a change not yet applied, and hidden without lists.',
        'spanRow': 'No or Yes over r_multiScreen, as V-Sync answers; the stock option labels do not fit the largest text size in every language. Spanning needs the list to allow it and a borderless window or desktop fullscreen; a line under the value says which is missing. Hidden on one display unless the draft spans or holds a change not yet applied, and hidden without lists.',
        'msaaAvailability': 'Read-only active-backend observation. Vulkan and unavailable renderers disable MSAA; strict Apply still checks supported GL sample counts.',
        'localization': ['#str_229900', DEVICE_LABEL, AUTO, SPAN_LABEL, SPAN_OPTIONS, SPAN_NEEDS_WINDOW, SPAN_UNAVAILABLE, '#str_200147',
                         '#str_229909', '#str_229910', '#str_229911', '#str_41093', '#str_230020']}
    nodes(result['root'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    prefix, document = load(args.source); result = compose(document)
    if args.check:
        if result != document: raise SystemExit('SYSTEM display controls differ from their authoring definition')
    else:
        args.source.write_text(prefix + json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__': main()
