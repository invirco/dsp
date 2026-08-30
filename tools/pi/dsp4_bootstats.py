#!/usr/bin/env python3
"""dsp4_bootstats.py — score dsp4_bootchar.py CSVs into a rate with bounds.

The point of the boot characterisation is that the failure rate stops being
an anecdote, so it needs to be quoted the same way every time: a count, a
Wilson 95 % interval, and the failure modes kept APART. They are not one
failure — a part that is alive at BOOT_STAGE 5 with the commit missing and a
part whose core has stopped are different defects with different fixes, and
merging them is how "~2 in 8" survived four sessions.

    python3 dsp4_bootstats.py bootchar*.csv
    python3 dsp4_bootstats.py --by-tag bootchar_fix2.csv
"""

import argparse
import collections
import csv
import math
import sys


def wilson(x, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, c - h), min(1.0, c + h)


def report(name, rows):
    n = len(rows)
    if not n:
        return
    verdicts = collections.Counter(r['verdict'] for r in rows)
    bad = n - verdicts.get('OK', 0)
    lo, hi = wilson(bad, n)
    print(f'{name}: {n - bad}/{n} clean on one attempt '
          f'({100.0 * (n - bad) / n:.1f}%); failure rate '
          f'{100.0 * bad / n:.2f}% [{100 * lo:.2f}%, {100 * hi:.2f}%] '
          f'Wilson 95%')
    for v, c in sorted(verdicts.items()):
        if v != 'OK':
            print(f'    {v:18s} {c}')
    # The two counters that separate the failure modes, when present.
    pf = collections.Counter(r.get('post1_pfix', '') for r in rows)
    if any(k not in ('', '0') for k in pf):
        print(f'    SPI_PART_FIX over the run: {dict(sorted(pf.items()))}')
    rx = collections.Counter(r.get('post1_rx', '') for r in rows)
    if len(rx) > 1:
        print(f'    SPI_RX_COUNT at the post-config probe: '
              f'{dict(sorted(rx.items()))}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('csv', nargs='+')
    ap.add_argument('--by-tag', action='store_true')
    args = ap.parse_args()

    rows = []
    for path in args.csv:
        with open(path, newline='') as fh:
            rows += list(csv.DictReader(fh))
    if args.by_tag:
        for tag in sorted({r['tag'] for r in rows}):
            report(tag, [r for r in rows if r['tag'] == tag])
    else:
        report('pooled', rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
