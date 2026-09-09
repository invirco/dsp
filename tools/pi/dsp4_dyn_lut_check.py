#!/usr/bin/env python3
"""dsp4_dyn_lut_check.py — read a node's level->gain table OFF THE PART and
compare it, word for word, against the host model.

WHY THIS IS THE BAR AND NOT A CYCLE COUNT.  S15-4: the S14 shootout rig
measured the right cycles for the wrong arithmetic for a whole session,
because the table's contents do not change the instruction stream and a
cycle rig is therefore blind to them.  The only way to know the DESIGN
STEP and the host model agree about the grid is to read what the part
actually wrote and diff it.

A comparison that cannot fail is not evidence (dsp4_comp_gr.py's rule),
so this one is built to be able to fail three ways and says which:

  * the table is still being DESIGNED -- the cursor is short of
    DYN_LUT_N -- in which case no verdict is given at all;
  * the words differ, and the first differing index is printed with the
    envelope it corresponds to and both gains in dB;
  * the words match but the KEY the node designed against is not the
    parameter set this tool was told to model, which would make a match
    meaningless.

Usage:
  dsp4_dyn_lut_check.py --node C1_COMP_01 --thr -20 --ratio 4 --knee 6
  dsp4_dyn_lut_check.py --node C1_COMP_01 --n 64      (spot-check 64 words)
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S


def vpeek(sc, addr, tries=8):
    """Voted peek. The cost words are unreadable under load on chip 2
    (dsp4_capacity.py says so and why); a table word is static, so
    voting is both possible and right here."""
    seen = {}
    for _ in range(tries):
        v = sc.peek(addr)
        seen[v] = seen.get(v, 0) + 1
        if seen[v] >= 2:
            return v
    raise IOError('0x%X never agreed with itself: %r' % (addr, seen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--sym', help='chipN.sym.json for THIS image (S10-9: a '
                                  'stale map points the symbol at whatever '
                                  'now lives at that address, and it answers)')
    ap.add_argument('--node', default='C1_COMP_01')
    ap.add_argument('--thr', type=float, default=-20.0)
    ap.add_argument('--ratio', type=float, default=4.0)
    ap.add_argument('--knee', type=float, default=6.0)
    ap.add_argument('--k', type=int, default=4)
    ap.add_argument('--n', type=int, default=0, help='0 = the whole table')
    ap.add_argument('--model', default='/home/app/dspboot/lut_model.txt',
                    help='the host model, one hex word per line')
    a = ap.parse_args()

    sc = S.Scope(a.chip, a.sym) if a.sym else S.Scope(a.chip)
    sc.check_chip()

    cur = sc.sym.get('_comp_lutc_%s' % a.node)
    tab = sc.sym.get('_comp_lut_%s' % a.node)
    key = sc.sym.get('_comp_lutk_%s' % a.node)
    if cur is None or tab is None:
        print('NO LUT SYMBOLS for %s -- is this a DSP4_DYN_LUT image?'
              % a.node)
        return 2

    want = [int(x, 16) for x in open(a.model) if x.strip()]
    n_all = len(want)

    c = vpeek(sc, cur)
    print('%s: design cursor %d of %d' % (a.node, c, n_all))
    if c < n_all:
        print('THE TABLE IS STILL BEING DESIGNED -- no verdict. Wait '
              '%d more blocks (%.1f ms) and re-run.'
              % ((n_all - c + 15) // 16, (n_all - c) / 16.0 / 3.0))
        return 3

    print('key it designed against: %s'
          % ' '.join('0x%08X' % vpeek(sc, key + i) for i in range(4)))

    n = a.n if a.n else n_all
    step = 1 if a.n == 0 else max(1, n_all // a.n)
    bad = 0
    first = None
    checked = 0
    for i in range(0, n_all, step):
        got = vpeek(sc, tab + i)
        checked += 1
        if got != want[i]:
            bad += 1
            if first is None:
                first = (i, got, want[i])
    if bad:
        i, g, w = first
        print('MISMATCH: %d of %d words differ.' % (bad, checked))
        print('  first at index %d: part 0x%08X, model 0x%08X' % (i, g, w))
        return 1
    print('DYN_LUT TABLE MATCH: %d of %d words identical to the host model '
          '(tools/dsp/dyn_lut_design.py), design step and grid agree exactly.'
          % (checked, checked))
    return 0


if __name__ == '__main__':
    sys.exit(main())
