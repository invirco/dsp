#!/usr/bin/env python3
"""s91_caprows.py — the driven ladder, shipping arm against candidate-s89.

S89e fixed the DAC fold by moving chip 2's block gather to a fixed point in
the block period (`DSP4_TX_DEFER=2`) and claimed it costs "zero cycles, zero
DM". It could only test that claim SILENT: the dispatch it ran under forbade
the `driveall` CPLD flash the driven row needs. This reads the four arms S91
took with that flash authorised — control (`DSP4_TX_DEFER=0`) and candidate
(`=2`), D24 and D32, two boots each, three rows a boot — and prints the
candidate beside the control with the delta, per row, per chip.

WHY THE PER-ROW FORM AND NOT ONE NUMBER. The three rows are taken on one
boot so they subtract: A is the product's default configuration silent, B is
the loaded configuration silent (B − A is what the CONFIGURATION costs), C is
the same configuration with the `driveall` stimulus playing (C − B is what
the SIGNAL costs, which is the dynamics' expensive branch). A fix that
genuinely adds no instructions has to read zero in all three, and the row
that carries the 84.47 % bar is C on chip 2.

CHIP 1 IS THE NULL ARM AND IT IS WHAT MAKES A DELTA A MEASUREMENT.
`DSP4_TX_DEFER=2` is a per-chip mask that names chip 2 only, so chip 1's code
is byte-identical between the two arms (the images differ in one byte, chip
1's own config stamp). Chip 1's deltas are therefore the instrument reading
itself, and no chip-2 delta inside that spread is a cost.

    python3 s91_caprows.py <goldens dir>
"""
import glob
import json
import sys

ROW = {'A-sil-default': 'A', 'B-sil-load': 'B', 'C-driven': 'C'}
ROWNAME = {'A': 'A  silent, default cfg',
           'B': 'B  silent, loaded cfg',
           'C': 'C  DRIVEN, loaded cfg'}
# The arms, as capacity.sh was invoked: (prefix, product, label).
ARMS = [('s91ctl', 'd24', 'D24 control  TX_DEFER=0'),
        ('s91fix', 'd24', 'D24 candidate TX_DEFER=2'),
        ('s91ctl32', 'd32', 'D32 control  TX_DEFER=0'),
        ('s91fix32', 'd32', 'D32 candidate TX_DEFER=2')]
BAR = 84.47      # S86's D24 chip-2 driven row, the bar this arm is scored against


def read(d, prefix, product):
    """{(row, chip): [pct per boot]}, plus overruns, cfg words and frames."""
    pct, mx, over, cfg, frames = {}, {}, {}, set(), {}
    for f in sorted(glob.glob('%s/cap-%s-%s-r*.json' % (d, prefix, product))):
        key = None
        for suffix, name in ROW.items():
            if f.endswith('-%s.json' % suffix):
                key = name
        if key is None:
            continue
        for c in json.load(open(f))['chips']:
            k = (key, c['chip'])
            pct.setdefault(k, []).append(c['proc_cyc_pct'])
            # THE WORST-BLOCK PERCENTAGE HAS TO BE COMPUTED, NOT READ.
            # `proc_cyc_max_pct` is the percentage of whatever `proc_cyc_max`
            # holds, and on some rows that is still the PRE-clear latch: S86's
            # own D24 file reads 342.93 / 357.31 / 384.20 % there, which is the
            # boot transient and S21-6's diag-tick artefact and not a block the
            # part ever spent. `proc_cyc_max_after_clear` is the figure a budget
            # has to cover, so the percentage is taken from it against the
            # budget the same reading measured.
            if c.get('proc_cyc_max_after_clear') is not None and c.get('budget'):
                mx.setdefault(k, []).append(
                    100.0 * c['proc_cyc_max_after_clear'] / c['budget'])
            else:
                mx.setdefault(k, []).append(c['proc_cyc_max_pct'])
            over[k] = over.get(k, 0) + c['overruns']
            frames[k] = frames.get(k, 0) + c['frames']
            cfg.add((c.get('build_cfg'), c.get('build_cfg2')))
    return pct, mx, over, cfg, frames


def mean(v):
    return sum(v) / len(v) if v else float('nan')


def table(d, ctl_prefix, fix_prefix, product, title, field):
    c_pct, c_mx, c_over, c_cfg, c_fr = read(d, ctl_prefix, product)
    f_pct, f_mx, f_over, f_cfg, f_fr = read(d, fix_prefix, product)
    ctl = c_pct if field == 'avg' else c_mx
    fix = f_pct if field == 'avg' else f_mx
    print()
    print('%s — %s' % (title, 'mean _proc_cyc' if field == 'avg'
                       else 'worst block after clear'))
    print('%-24s %-28s %-28s' % ('row', 'chip 1  ctl -> fix (delta)',
                                 'chip 2  ctl -> fix (delta)'))
    for row in ('A', 'B', 'C'):
        cells = []
        for chip in (1, 2):
            k = (row, chip)
            if k not in ctl or k not in fix:
                cells.append('%-28s' % '(missing)')
                continue
            a, b = mean(ctl[k]), mean(fix[k])
            cells.append('%-28s' % ('%6.2f -> %6.2f  (%+5.2f)' % (a, b, b - a)))
        print('%-24s %s %s' % (ROWNAME[row], cells[0], cells[1]))
    if field == 'avg':
        # MISSED BLOCKS, PER ARM AND PER ROW, NOT AS ONE SUM. A single total
        # hides which arm and which row missed them, and on D32 that is the
        # whole content of the number: chip 2's LOADED rows sit above budget
        # on BOTH arms and miss ~2.7 % of blocks there, while every silent row
        # and every chip-1 row misses none. Summed, that reads as "29,309
        # missed blocks" against a fix that did not cause one of them.
        for label, over in (('control', c_over), ('candidate', f_over)):
            rows = ['%s chip %d: %d' % (ROWNAME[k[0]].split()[0], k[1], v)
                    for k, v in sorted(over.items()) if v]
            print('    missed blocks, %-9s %s'
                  % (label, ', '.join(rows) if rows else 'NONE in any row'))
        print('    blocks measured: control %d, candidate %d'
              % (sum(c_fr.values()), sum(f_fr.values())))
        print('    build_cfg/cfg2 read off the part during the measurement: %s'
              % '; '.join(sorted('%s %s' % x for x in (c_cfg | f_cfg) if x[0])))
    return c_pct, f_pct


def spread(pct, label):
    """The per-boot spread, so a delta is read against it and not against 0."""
    worst = 0.0
    for k, v in sorted(pct.items()):
        if len(v) > 1:
            worst = max(worst, max(v) - min(v))
    print('    %s: worst boot-to-boot spread on any row %.2f points' % (label, worst))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    for field in ('avg', 'max'):
        table(d, 's91ctl', 's91fix', 'd24', 'D24 (24 channels)', field)
        table(d, 's91ctl32', 's91fix32', 'd32', 'D32 (32 channels)', field)

    print()
    print('== the bar ==')
    for prefix, product, label in ARMS:
        pct, _, over, _, _ = read(d, prefix, product)
        k = ('C', 2)
        if k not in pct:
            print('  %-26s (no driven row)' % label)
            continue
        v = pct[k]
        print('  %-26s chip 2 driven %6.2f %%  (boots %s)  vs bar %.2f -> %+.2f'
              % (label, mean(v), '/'.join('%.2f' % x for x in v), BAR,
                 mean(v) - BAR))
    print()
    print('== the null arm: chip 1, byte-identical code between the two arms ==')
    for ctlp, fixp, product in (('s91ctl', 's91fix', 'd24'),
                                ('s91ctl32', 's91fix32', 'd32')):
        c_pct, _, _, _, _ = read(d, ctlp, product)
        f_pct, _, _, _, _ = read(d, fixp, product)
        deltas = [mean(f_pct[k]) - mean(c_pct[k])
                  for k in c_pct if k[1] == 1 and k in f_pct]
        c2 = [mean(f_pct[k]) - mean(c_pct[k])
              for k in c_pct if k[1] == 2 and k in f_pct]
        if deltas:
            print('  %s chip 1 deltas %s points (the instrument against itself)'
                  % (product, ' '.join('%+.2f' % x for x in sorted(deltas))))
        if c2:
            print('  %s chip 2 deltas %s points'
                  % (product, ' '.join('%+.2f' % x for x in sorted(c2))))
        spread(c_pct, '%s control' % product)
        spread(f_pct, '%s candidate' % product)


if __name__ == '__main__':
    main()
