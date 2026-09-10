#!/usr/bin/env python3
"""cap_table.py — the capacity table, built from the rows and not by hand.

Reads the JSON `dsp4_capacity.py` writes and prints one markdown table per
product: arm x chip x regime, average and worst block and the arbiter, with
the measured clock carried through so a row that ran on a different clock
cannot be averaged into one that did not.

THE REGIMES ARE COLUMNS, NOT SEPARATE TABLES (S19). Every capacity figure
in the tree before 2026-09-10 was the silent one and none of them said so,
which is how the record came to hold a decision table that did not describe
a working desk. Here a row that has no driven column is visibly missing it.

    python3 tools/dsp/cap_table.py MW/D32/DSP/SHARC/goldens/cap-s19*.json
"""
import argparse
import collections
import glob
import json
import os
import sys

REGIMES = ['sil-default', 'sil-load', 'driven']
LABEL = {'sil-default': 'silent, default cfg',
         'sil-load': 'silent, loaded cfg',
         'driven': 'DRIVEN, loaded cfg'}

# THE FX LADDER'S RUNGS (S21). Not extra regimes -- they are all the DRIVEN
# regime with one cell rewritten -- so they get a table of their own, keyed
# by the tag `capacity_run.sh` gives each rung. Only the rungs that were
# actually taken appear, in this order.
FX_RUNGS = ['fx-off', 'fx-4', 'fx-3', 'fx-0', 'fx-2', 'fx-1', 'fx-5', 'fx-6']
FX_LABEL = {'fx-off': 'Fx On = 0 (PARKED since S23; was INERT)',
            'fx-4': 'Type 4 — parked in the bypass (the baseline)',
            'fx-3': 'Type 3 — Reverb (Freeverb)',
            'fx-0': 'Type 0 — Echo',
            'fx-2': 'Type 2 — Doubling',
            'fx-1': 'Type 1 — PingPong (not implemented: bypass)',
            'fx-5': 'Type 5 — Flanger (not implemented: bypass)',
            'fx-6': 'Type 6 — Phaser (not implemented: bypass)'}


def rows(paths):
    for p in paths:
        try:
            d = json.load(open(p))
        except (OSError, ValueError):
            continue
        # S21-6, for rows taken BEFORE dsp4_capacity.py learned to say it.
        # The three conditions are the tool's, verbatim: over 150 % of
        # budget, zero missed blocks, and still at or above the average once
        # one TPERIOD comes off. A row that fails any of them keeps its raw
        # figure and no asterisk.
        for c in d.get('chips', []):
            if c.get('proc_cyc_max_detick_pct') is not None:
                continue
            tp, bud = c.get('tperiod'), c.get('budget')
            mx, av, ov = (c.get('proc_cyc_max'), c.get('proc_cyc'),
                          c.get('overruns'))
            if not (tp and bud and mx and av) or ov != 0:
                continue
            if mx > 1.5 * bud and abs((mx - tp) - av) <= 0.03 * bud:
                dt = max(mx - tp, av)
                c['proc_cyc_max_detick'] = dt
                c['proc_cyc_max_detick_pct'] = round(100.0 * dt / bud, 2)
        base = os.path.basename(p)
        # cap-<arm>-<product>-r<n>-<letter>-<regime>.json
        parts = base[:-5].split('-')
        if len(parts) < 4 or parts[0] != 'cap':
            continue
        arm, product, rep = parts[1], parts[2], parts[3]
        for c in d.get('chips', []):
            yield {
                'arm': arm, 'product': product, 'rep': rep,
                'regime': c.get('tag') or d.get('tag') or '?',
                'chip': c.get('chip'),
                'avg': c.get('proc_cyc_pct'),
                'worst': c.get('proc_cyc_max_pct'),
                # S21-6: the de-ticked worst block where the row qualifies.
                # Computed by dsp4_capacity.py on the part, not here, and
                # only where the arbiter counted zero missed blocks.
                'worst_dt': c.get('proc_cyc_max_detick_pct'),
                'overruns': c.get('overruns'),
                'overrun_pct': c.get('overrun_pct'),
                'cclk': c.get('cclk_measured_hz'),
                'frames': c.get('frames'),
                'cfg': c.get('build_cfg'), 'cfg2': c.get('build_cfg2'),
                'error': c.get('error'),
                'file': base,
            }


def fmt(vals):
    """One cell from N boots: the values, not their average."""
    vals = [v for v in vals if v is not None]
    if not vals:
        return '—'
    if len(set('%.2f' % v for v in vals)) == 1:
        return '%.2f' % vals[0]
    return ' / '.join('%.2f' % v for v in vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--order', default='blk,s16,s16f,s18')
    a = ap.parse_args()

    paths = []
    for p in a.paths:
        paths += sorted(glob.glob(p)) if any(c in p for c in '*?[') else [p]

    got = list(rows(paths))
    if not got:
        print('no capacity rows in %d path(s)' % len(paths))
        return 1

    order = [x.strip() for x in a.order.split(',')]

    def armkey(arm):
        bare = arm[3:] if arm.startswith('s19') else arm
        return (order.index(bare) if bare in order else 99, arm)

    by = collections.defaultdict(list)
    for r in got:
        by[(r['product'], r['arm'], r['chip'], r['regime'])].append(r)

    products = sorted(set(r['product'] for r in got))
    for prod in products:
        arms = sorted(set(r['arm'] for r in got if r['product'] == prod),
                      key=armkey)
        print('\n### %s' % prod)
        print('| arm | chip | ' + ' | '.join(LABEL[g] for g in REGIMES)
              + ' | driven worst | overruns (driven) | CCLK |')
        print('|---|---|' + '---|' * (len(REGIMES) + 3))
        for arm in arms:
            for chip in (1, 2):
                cells = []
                for g in REGIMES:
                    rs = by.get((prod, arm, chip, g), [])
                    cells.append(fmt([r['avg'] for r in rs]))
                drv = by.get((prod, arm, chip, 'driven'), [])
                worst = fmt([(r['worst_dt'] if r['worst_dt'] is not None
                              else r['worst']) for r in drv])
                if any(r['worst_dt'] is not None for r in drv):
                    worst += ' *'
                ov = ' / '.join(
                    ('%s (%s%%)' % (r['overruns'], r['overrun_pct']))
                    for r in drv) or '—'
                clk = ' / '.join(sorted(set(
                    '%.2f' % (r['cclk'] / 1e6) for r in drv if r['cclk']))) or '—'
                print('| %s | %d | %s | %s |'
                      % (arm, chip, ' | '.join(cells),
                         ' | '.join([worst, ov, clk])))

    # ---- the FX ladder, one table, differences taken against Type 4 ----
    ladder = [r for r in got if r['regime'] in FX_RUNGS]
    if ladder:
        for prod in sorted(set(r['product'] for r in ladder)):
            arms = sorted(set(r['arm'] for r in ladder
                              if r['product'] == prod), key=armkey)
            print('\n### %s — the FX ladder (all rungs DRIVEN, same boot, '
                  'same measured clock; only the six engines\' cells move)'
                  % prod)
            print('| arm | chip | rung | avg % | worst % | overruns | '
                  'delta vs Type 4 |')
            print('|---|---|---|--:|--:|---|--:|')
            for arm in arms:
                for chip in (1, 2):
                    base = by.get((prod, arm, chip, 'fx-4'), [])
                    basev = [r['avg'] for r in base if r['avg'] is not None]
                    basev = sum(basev) / len(basev) if basev else None
                    for g in FX_RUNGS:
                        rs = by.get((prod, arm, chip, g), [])
                        if not rs:
                            continue
                        av = [r['avg'] for r in rs if r['avg'] is not None]
                        wdt = [(r['worst_dt'] if r['worst_dt'] is not None
                                else r['worst']) for r in rs]
                        d = ('%+.2f' % (sum(av) / len(av) - basev)
                             if av and basev is not None else '—')
                        ov = ' / '.join(
                            ('%s (%s%%)' % (r['overruns'], r['overrun_pct']))
                            for r in rs) or '—'
                        print('| %s | %d | %s | %s | %s%s | %s | %s |'
                              % (arm, chip, FX_LABEL.get(g, g),
                                 fmt([r['avg'] for r in rs]), fmt(wdt),
                                 (' *' if any(r['worst_dt'] is not None
                                              for r in rs) else ''), ov, d))

    if any(r['worst_dt'] is not None for r in got):
        print('\n`*` on a worst-block figure: the part\'s own latch was ONE '
              'DIAG TICK (TPERIOD, 983,040 cycles) too big on that row and '
              'the figure shown has it subtracted — see S21-6. Only rows '
              'where the arbiter counted ZERO missed blocks and the '
              'corrected value lands within 3 points of that row\'s last '
              'pass qualify, and the figure is a FLOOR on the true worst '
              'block (a corrupted pass destroys the latch\'s information '
              'about the passes after it). The raw latch is in the JSON.')

    bad = [r for r in got if r['error']]
    if bad:
        print('\nUNREADABLE rows:')
        for r in bad:
            print('  %s chip %d: %s' % (r['file'], r['chip'], r['error']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
