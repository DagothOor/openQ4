#!/usr/bin/env python3
"""Title the SYSTEM confirmation panel by the attempt it reports.

The Keep/Revert question belongs to a display confirmation. An automatic
attempt, such as the next map's light-grid preload, never asks it: the panel
opens for such an attempt only when it needs recovery (a failed preparation or
restore, or a save that did not finish), and then needs a title that fits any
attempt. While the service reports RecoveryRequired the title reads the
neutral recovery heading; otherwise it keeps the Keep question.
This tool owns the title's text binding and the renderOptions extension
record. --check verifies reproducible generation without writing.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from update_system_number_fields import index_nodes, load

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('content/baseoq4/pak0/guis/menu/settings/system.q4ui')
TITLE = 'confirmation-panel-title'
KEEP_TITLE, RECOVERY_TITLE = '#str_229993', '#str_230077'
RECOVERY_REQUIRED = 3  # SettingsPhase::RecoveryRequired
# No other SYSTEM tool inserts beside the VSync bindings, so the title binding
# keeps one stable place however the passes are ordered.
ANCHOR = 'settings_vsync.opacity'


def compose(document):
    result = copy.deepcopy(document)
    title = index_nodes(result['root']).get(TITLE)
    if title is None or title['properties'].get('text') != {'type': 'text', 'value': KEEP_TITLE}:
        raise ValueError('The SYSTEM confirmation title no longer reads the Keep question; review its binding')
    binding = {'id': TITLE + '.text', 'node': TITLE, 'property': 'text', 'value': {'op': 'select', 'args': [
        {'op': '==', 'args': [{'state': 'settings.phase'}, RECOVERY_REQUIRED]}, RECOVERY_TITLE, KEEP_TITLE]}}
    bindings = [entry for entry in result.get('bindings', []) if entry['id'] != binding['id']]
    position = next((index for index, entry in enumerate(bindings) if entry['id'] == ANCHOR), None)
    if position is None:
        raise ValueError('The SYSTEM VSync opacity binding is missing; choose a new anchor for the confirmation title')
    bindings.insert(position + 1, binding)
    result['bindings'] = bindings
    result.setdefault('extensions', {}).setdefault('openq4', {})['renderOptions'] = {
        'scope': 'Automatic attempts (the next map\'s light-grid preload) apply without Keep/Revert and report '
                 'Applying, Restoring and Saving status. The confirmation panel opens for one only when it needs '
                 'recovery, under the neutral recovery title.',
        'confirmationTitle': {'recoveryPhase': RECOVERY_REQUIRED, 'recovery': RECOVERY_TITLE, 'otherwise': KEEP_TITLE},
        'localization': [KEEP_TITLE, RECOVERY_TITLE, '#str_230073', '#str_230074', '#str_230075', '#str_230076'],
        'remaining': 'The Preload Light Grids, Renderer Fallback, display device and resolution rows follow in '
                     'their own increments.'}
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
            raise SystemExit('SYSTEM confirmation title differs from its render-options definition')
    else:
        args.source.write_text(prefix + json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
