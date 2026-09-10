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


def rows(paths):
    for p in paths:
        try:
            d = json.load(open(p))
        except (OSError, ValueError):
            continue
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
                worst = fmt([r['worst'] for r in drv])
                ov = ' / '.join(
                    ('%s (%s%%)' % (r['overruns'], r['overrun_pct']))
                    for r in drv) or '—'
                clk = ' / '.join(sorted(set(
                    '%.2f' % (r['cclk'] / 1e6) for r in drv if r['cclk']))) or '—'
                print('| %s | %d | %s | %s |'
                      % (arm, chip, ' | '.join(cells),
                         ' | '.join([worst, ov, clk])))

    bad = [r for r in got if r['error']]
    if bad:
        print('\nUNREADABLE rows:')
        for r in bad:
            print('  %s chip %d: %s' % (r['file'], r['chip'], r['error']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
