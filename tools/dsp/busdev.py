#!/usr/bin/env python3
"""busdev.py — how FAR two bus captures differ, in dB, not how many words.

`dsp4_pairgraph.py --compare` answers "how many words differ and what is the
largest difference in LSBs". That is the right question when a change is
bit-exact by construction and the answer must be zero. It is the wrong
question the moment a change is a declared numeric deviation with a dB bound
on it -- a maxdiff of 303,276 LSBs reads exactly the same for a table
interpolating the compressor's gain curve to 0.04 dB and for a node that has
stopped working, which is the criticism S16-4 made of counting instead of
measuring and is why `dsp4_node_verify.py` reports dB now.

So: the two captures, word for word, as a level difference.

  busdev.py A.json B.json
  busdev.py A.json B.json --bound 0.0950     # exit 1 if anything exceeds it
"""
import argparse
import json
import math
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--bound', type=float, default=None,
                    help='dB bound; exit 1 if any word exceeds it')
    args = ap.parse_args()

    A, B = json.load(open(args.a)), json.load(open(args.b))
    wa, wb = A['words'], B['words']
    if len(wa) != len(wb):
        print('captures are different lengths: %d vs %d' % (len(wa), len(wb)))
        return 2

    print('%s (%s) vs %s (%s)' % (args.a, A.get('tag'), args.b, B.get('tag')))
    for tag, C in (('A', A), ('B', B)):
        print('  %s: paired_build=%s bq_paired_build=%s gain=%s block=%s'
              % (tag, C.get('paired_build'), C.get('bq_paired_build'),
                 C.get('gain'), C.get('block')))

    diff = worst_db = 0
    worst_i = worst_pair = None
    zeroed = 0
    for i, (x, y) in enumerate(zip(wa, wb)):
        if x == y:
            continue
        diff += 1
        # Both captures are Q4.28 samples of the same bus. A word that is
        # zero in one and not the other is not a level difference at all, so
        # it is counted separately rather than folded into a dB figure.
        if x == 0 or y == 0:
            zeroed += 1
            continue
        d = abs(20.0 * math.log10(abs(y) / abs(x)))
        if d > worst_db:
            worst_db, worst_i, worst_pair = d, i, (x, y)

    print('  %d of %d words differ' % (diff, len(wa)))
    if zeroed:
        print('  %d of them are zero in one capture and not the other — NOT a '
              'level difference, look at those first' % zeroed)
    if worst_i is None:
        print('  no word carries a measurable level difference')
    else:
        print('  worst level difference %.5f dB at word %d (%d vs %d, '
              'delta %+d LSB)'
              % (worst_db, worst_i, worst_pair[0], worst_pair[1],
                 worst_pair[1] - worst_pair[0]))
    if args.bound is not None:
        ok = worst_db <= args.bound and zeroed == 0
        print('  bound %.4f dB: %s' % (args.bound, 'PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
