#!/usr/bin/env python3
"""Soften the screen behind the SYSTEM page's dialogs (visual specification 6).

The Apply/Keep/Revert confirmation and the unapplied-changes dialog keep the
screen beneath in modal.softfocus: a 5 u (7.5 dp) blur at 0.80 saturation,
never dimmed. With the opaque-backing option, or where the renderer cannot
soften the screen (ui_retainedSoftFocus is 0), their existing 0.6 backing
stands in. This tool owns those two dialogs' backdrop nodes and bindings and
the soft_focus state. --check verifies reproducible generation without
writing.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from update_system_number_fields import index_nodes, keyword, length, load, node, value

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('content/baseoq4/pak0/guis/menu/settings/system.q4ui')
DIALOGS = ('confirmation-panel', 'discard-panel')
BACKING = [0, 0, 0, 0.6]
BLUR_DP, SATURATION = 7.5, 0.8


def select(state, shown, hidden):
    return {'op': 'select', 'args': [{'state': state}, shown, hidden]}


def compose(document):
    result = copy.deepcopy(document)
    result.setdefault('state', {})['soft_focus'] = {'type': 'boolean', 'initial': False, 'cvar': 'ui_retainedSoftFocus'}
    nodes = index_nodes(result['root'])
    owned = {f'{dialog}-{part}' for dialog in DIALOGS for part in ('softfocus', 'scrim')}
    # Each dialog's backdrop bindings follow its own visibility binding; other
    # SYSTEM tools keep theirs at the end of the list.
    following = {f'{dialog}.display': [
        {'id': f'{dialog}-softfocus.display', 'node': f'{dialog}-softfocus', 'property': 'display',
         'value': select('soft_focus', 'block', 'none')},
        {'id': f'{dialog}-scrim.display', 'node': f'{dialog}-scrim', 'property': 'display',
         'value': select('soft_focus', 'none', 'block')}] for dialog in DIALOGS}
    bindings = []
    for binding in result.get('bindings', []):
        if binding['node'] in owned: continue
        bindings.append(binding)
        bindings += following.pop(binding['id'], [])
    if following: raise ValueError('A SYSTEM dialog lost its visibility binding: ' + ', '.join(following))
    for dialog in DIALOGS:
        panel = nodes[dialog]
        properties = panel['properties']
        if properties.get('position') != keyword('absolute') or properties.get('width') != length(100, '%') or \
                properties.get('height') != length(100, '%'):
            raise ValueError(f'{dialog} no longer covers the view; review its backdrop')
        # The dialog's own backing moves to a node that only the fallback shows.
        properties['background-color'] = value('color', [0, 0, 0, 0])
        cover = {'position': keyword('absolute'), 'left': length(0), 'top': length(0), 'width': length(100, '%'),
                 'height': length(100, '%'), 'pointer-events': keyword('none')}
        # Absolute layers leave the dialog's centered flex layout alone; the
        # first paints first, so its backdrop reads everything beneath.
        softened = node(f'{dialog}-softfocus', properties={**cover, 'display': keyword('none'), 'backdrop-blur': length(BLUR_DP),
                                                           'backdrop-saturate': value('number', SATURATION)})
        scrim = node(f'{dialog}-scrim', properties={**cover, 'background-color': value('color', BACKING)})
        panel['children'] = [softened, scrim] + [child for child in panel['children'] if child['id'] not in owned]
    result['bindings'] = bindings
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--source', type=Path, default=ROOT / SOURCE)
    parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    prefix, document = load(args.source); result = compose(document)
    if args.check:
        if result != document: raise SystemExit('SYSTEM dialog backdrops differ from their soft-focus definition')
    else: args.source.write_text(prefix + json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__': main()
