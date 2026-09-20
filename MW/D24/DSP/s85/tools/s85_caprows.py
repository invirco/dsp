#!/usr/bin/env python3
"""s85_caprows.py — the S82 D24 capacity rows, re-taken, beside S82's own.

Gate 4 asks whether adopting the new shipping label moved the 84.34 % driven
row. The comparison is only worth making if it is the SAME question: same
product, same config file, same overrides, both boots, mean of the two --
which is how S82 quoted it and how capacity.sh takes it. So this reads the
per-boot row files and prints the two-boot mean beside S82's number and the
delta, and it prints `build_cfg2` from the rows themselves, because a capacity
number and the configuration it was taken on have to be one reading (S11-1).
"""
import glob
import json
import sys

S82 = {'A': (43.22, 77.41), 'B': (57.50, 84.27), 'C': (57.54, 84.34)}
ROW = {'A-sil-default': 'A', 'B-sil-load': 'B', 'C-driven': 'C'}

d = sys.argv[1] if len(sys.argv) > 1 else '.'
rows, cfg2, missed = {}, set(), {}
for f in sorted(glob.glob('%s/cap-*.json' % d)):
    j = json.load(open(f))
    key = None
    for suffix, name in ROW.items():
        if f.endswith('-%s.json' % suffix):
            key = name
    if key is None:
        continue
    for c in j['chips']:
        rows.setdefault((key, c['chip']), []).append(c['proc_cyc_pct'])
        missed[(key, c['chip'])] = missed.get((key, c['chip']), 0) + c['overruns']
        cfg2.add(c.get('build_cfg2'))

print('build_cfg2 read off the part during the measurement: %s'
      % ', '.join(sorted(x for x in cfg2 if x)))
print()
print('%-4s %-24s %-24s %s' % ('row', 'chip 1 (S85 / S82)', 'chip 2 (S85 / S82)',
                               'missed blocks'))
for key in ('A', 'B', 'C'):
    out = ['%-4s' % key]
    for chip in (1, 2):
        v = rows.get((key, chip))
        if not v:
            out.append('%-24s' % '-- no row --')
            continue
        mean = sum(v) / len(v)
        out.append('%-24s' % ('%.2f / %.2f  (%+.2f, %d boot%s)'
                              % (mean, S82[key][chip - 1], mean - S82[key][chip - 1],
                                 len(v), '' if len(v) == 1 else 's')))
    out.append('%d / %d' % (missed.get((key, 1), 0), missed.get((key, 2), 0)))
    print(' '.join(out))
