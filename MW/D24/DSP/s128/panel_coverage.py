#!/usr/bin/env python3
"""panel_coverage.py -- every switch and indicator on the two switch boards,
against what the panel loop actually grades (S128, HUB ADDENDUM 1).

PW at the bench, 2026-09-27: "led test was only one switch board, and didn't
cover all switches."

THE LIST IS READ FROM `defs`, NOT FROM THE LOOP. `defs/products/d24/fw.csv` is
the definition of what is on each board: it is sectioned by `MCU` rows, so every
`SW`, `LED`, `ENC` and `CON` row between `MCU SW_RIGHT` and `MCU SW_LEFT`
belongs to the right board and everything after `MCU SW_LEFT` to the left one.
Reconciling against `d24_panel.py`'s own tables would only prove the loop agrees
with itself, which is how a board goes missing.

    panel_coverage.py                 the table, as markdown
    panel_coverage.py --check         exit 1 if anything is unaccounted for
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
FW = os.path.join(ROOT, 'defs', 'products', 'd24', 'fw.csv')
CATALOG = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's119', 'test-catalog.csv')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pi'))

BOARD = {'SW_RIGHT': 'right', 'SW_LEFT': 'left'}
# The `Notes` column of a SW/LED row carries the firmware's radio index, which
# is the value that lights that indicator and the value a press sends.
IDX = 2


def fw_rows():
    """Every control on the two switch boards, in fw.csv order, with its board.

    `kind` is fw.csv's own Type: SW is a switch, LED an indicator, ENC the
    encoder, CON a line that passes through the panel processor with no matrix
    cell bound to it.
    """
    out, board = [], None
    with open(FW, newline='') as fh:
        for rec in csv.reader(fh):
            if not rec or not rec[0]:
                continue
            if rec[0] == 'MCU':
                board = BOARD.get(rec[1])
                continue
            if board is None or rec[0] not in ('SW', 'LED', 'ENC', 'CON'):
                continue
            out.append(dict(kind=rec[0], name=rec[1], notes=rec[2],
                            board=board, cell=rec[6] if len(rec) > 6 else '',
                            idx=rec[2] if rec[2].isdigit() else ''))
    return out


def catalog_rows():
    rows = {}
    with open(CATALOG, newline='') as fh:
        for d in csv.DictReader(fh):
            rows[int(d['num'])] = d
    return rows


def loop_tables():
    import d24_panel as PL
    steps, always, enc, unreached = {}, {}, {}, {}
    for side, table in PL.PANELS.items():
        for pos, (idx, name, sw, led, what) in enumerate(table, start=1):
            steps[(side, name)] = dict(pos=pos, idx=idx, sw=sw, led=led,
                                       what=what)
    for side, (nums, what) in PL.ALWAYS_ON.items():
        always[side] = (nums, what)
    for side, pair in PL.ENC_ROWS.items():
        enc[side] = pair
    for side, d in PL.UNREACHED.items():
        unreached[side] = d
    return steps, always, enc, unreached


# fw.csv's name -> the loop's display name, where they differ. Kept here and
# nowhere else: the loop's names are what a worker reads off the panel and
# fw.csv's are the firmware's identifiers.
ALIAS = {
    'Phantom48': '+48', 'FxMute': 'FX MUTE', 'RecPlay': 'REC/PLY',
    'Studio': 'STUDIO CTL', 'ChanAssign': 'CH ASSIGN', 'MonoAux': 'MONO AUX',
    'StereoAux': 'STEREO AUX', 'AuxOnFaders': 'AUX ON FADERS',
    'Overview': 'OVERVIEW', 'Home': 'HOME', 'Menu': 'MENU',
    'Feedback': 'FEEDBACK', 'Mute': 'MUTE', 'Scene': 'SCENE', 'Fx': 'FX',
    'Eq': 'EQ', 'L': 'L', 'C': 'C', 'R': 'R', 'Monitor': 'MONITOR',
    'FxMuteWhite': 'FX MUTE', 'FxMuteRed': 'FX MUTE', 'RecPlayWhite': 'REC/PLY',
    'RecPlayRec': 'REC/PLY',
}

NO_CELL = ('no matrix cell is bound to it in the definitions, so nothing the '
           'host writes can light it and no press reaches the host')


def rows_for(item, steps, always, enc, unreached, cat):
    """(catalog rows, loop step, graded, why) for one fw.csv control."""
    side, name = item['board'], ALIAS.get(item['name'], item['name'].upper())
    st = steps.get((side, name))
    if item['kind'] == 'ENC':
        pair = enc.get(side)
        if pair:
            return [pair[0]], 'encoder step', True, 'a detent each way, read off the bus'
        return [], '-', False, 'the loop has no encoder step for this board'
    if item['kind'] == 'CON':
        # A pass-through: the catalog rows for these are 92, 93, 94.
        hit = [n for n, d in cat.items()
               if 'pass-through' in d['item'] and _con_match(item['name'], d['item'])]
        return hit, '-', False, NO_CELL
    # THE INDICATORS NO STEP CAN GRADE come first: they have no step, and saying
    # "no loop step exists" about them would hide the reason, which is the whole
    # point of this table.
    if item['name'].startswith('Enc') and item['kind'] == 'LED':
        pair = enc.get(side)
        return ([pair[1]] if pair else []), 'encoder ring', False, \
            'the ring is stepped round twice, but grading it needs a yes/no ' \
            'question and the factory screen has one button'
    if item['name'] == 'BootLed':
        hit = [n for n, d in cat.items() if 'BootLed' in d['item']
               and _board_of(d) == side]
        return (hit or []), '-', False, \
            'driven by the processor boot pin, not by the processor: nothing ' \
            'the host writes can light it'
    # The WHITE ring of the two two-indicator buttons is not in the radio group
    # at all: MainInit() drives it high and leaves it there, so it is lit
    # whenever the unit is on and no write can move it. One question grades
    # both, and this screen cannot ask it.
    if item['name'] in ('FxMuteWhite', 'RecPlayWhite'):
        nums = (always.get(side) or ([], ''))[0]
        num = {'FxMuteWhite': 60, 'RecPlayWhite': 86}[item['name']]
        return ([num] if num in nums else []), 'always-lit pair', False, \
            'lit whenever the unit is on and no write can move it; grading it ' \
            'needs a yes/no question and the factory screen has one button'
    if st is None:
        return [], '-', False, 'no loop step exists for this control'
    if item['kind'] == 'SW':
        return [st['sw']], 'step %d' % st['pos'], True, \
            'the key code that comes back is this button\'s'
    if item['name'] in ('FxMuteRed', 'RecPlayRec'):
        # The RED indicator of a two-indicator button IS in the radio group and
        # is the one the loop's step lights.
        return [st['led']], 'step %d' % st['pos'], True, \
            'lit by the host and confirmed by the press under it'
    return [st['led']], 'step %d' % st['pos'], True, \
        'lit by the host and confirmed by the press under it'


def _board_of(d):
    b = (d.get('board') or '').lower()
    if 'left' in b:
        return 'left'
    if 'right' in b:
        return 'right'
    return ''


def _con_match(name, item):
    key = {'Talkback': 'Talkback switch', 'TalkbackLed0': 'Talkback switch',
           'TalkbackLed1': 'Talkback switch', 'MiniJackDet': 'Mini-jack',
           'Blower': 'TEMP / BLOWER', 'Fan': 'TEMP / BLOWER'}.get(name)
    return bool(key) and item.startswith(key)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    items = fw_rows()
    cat = catalog_rows()
    steps, always, enc, unreached = loop_tables()
    out, gaps = [], []
    for it in items:
        rows, step, graded, why = rows_for(it, steps, always, enc, unreached, cat)
        out.append((it, rows, step, graded, why))
        if not graded:
            gaps.append((it, why))
    # the always-lit indicators, which are catalog rows with no fw.csv row of
    # their own beyond the button's
    print('| control | kind | board | radio index | matrix cell | catalog row | '
          'loop step | graded | why / why not |')
    print('|---|---|---|---|---|---|---|---|---|')
    for it, rows, step, graded, why in out:
        print('| %s | %s | %s | %s | %s | %s | %s | %s | %s |'
              % (it['name'], it['kind'], it['board'], it['idx'] or '-',
                 it['cell'] or '(none)',
                 ', '.join(str(n) for n in rows) or '-', step,
                 'yes' if graded else 'NO', why))
    # THE OTHER DIRECTION, and it is the half that catches a missing control:
    # every catalog row on either switch board that no fw.csv control above
    # claimed. A row nothing claims is a control the definitions and the test
    # disagree about, and it is named rather than counted.
    claimed = set()
    for _it, rows, _s, _g, _w in out:
        claimed.update(rows)
    # A row that declares an AUTOMATIC test is graded by that test and is not
    # the panel loop's to cover: row 56, the left board's MEMS microphone and
    # speaker, is AL1's -- the acoustic check -- and there is no button on it.
    orphans = [(n, d) for n, d in sorted(cat.items())
               if _board_of(d) and 'Switch PCBA' in (d.get('board') or '')
               and n not in claimed and not (d.get('tests') or '').strip()]
    auto = [(n, d) for n, d in sorted(cat.items())
            if _board_of(d) and 'Switch PCBA' in (d.get('board') or '')
            and n not in claimed and (d.get('tests') or '').strip()]
    if auto:
        print('')
        print('### Rows on the two boards the MACHINE grades, not the loop')
        print('')
        print('| catalog row | board | what it is | graded by |')
        print('|---|---|---|---|')
        for n, d in auto:
            print('| %d | %s | %s | %s |' % (n, _board_of(d), d['item'],
                                             d['tests']))
    print('')
    print('### Catalog rows on the two boards that no definition row claims')
    print('')
    if not orphans:
        print('None.')
    else:
        print('| catalog row | board | what it is | graded | why not |')
        print('|---|---|---|---|---|')
        for n, d in orphans:
            why = (unreached.get(_board_of(d)) or {}).get(n)
            print('| %d | %s | %s | %s | %s |'
                  % (n, _board_of(d), d['item'],
                     'NO', (why[0] if isinstance(why, tuple) else why)
                     or 'not accounted for anywhere -- LOOK AT THIS'))
    print('')
    n_sw = sum(1 for it, _r, _s, g, _w in out if it['kind'] == 'SW')
    n_sw_g = sum(1 for it, _r, _s, g, _w in out if it['kind'] == 'SW' and g)
    n_led = sum(1 for it, _r, _s, g, _w in out if it['kind'] == 'LED')
    n_led_g = sum(1 for it, _r, _s, g, _w in out if it['kind'] == 'LED' and g)
    print('')
    print('Switches: %d of %d graded.  Indicators: %d of %d graded.'
          % (n_sw_g, n_sw, n_led_g, n_led))
    for side in ('left', 'right'):
        sw = [it['name'] for it, _r, _s, g, _w in out
              if it['board'] == side and it['kind'] == 'SW']
        swg = [it['name'] for it, _r, _s, g, _w in out
               if it['board'] == side and it['kind'] == 'SW' and g]
        print('  %s switch board: %d switches, %d walked (%s)'
              % (side, len(sw), len(swg), ', '.join(swg) or 'none'))
    if a.check:
        bad = [it['name'] for it, why in gaps if not why]
        bad += ['catalog row %d' % n for n, d in orphans
                if not (unreached.get(_board_of(d)) or {}).get(n)]
        if bad:
            print('UNACCOUNTED: %s' % ', '.join(bad))
            return 1
        print('every control is either graded or named with its reason')
    return 0


if __name__ == '__main__':
    sys.exit(main())
