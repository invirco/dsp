#!/usr/bin/env python3
"""dsp4_icrecv.py — IS THE INTER-CHIP MIX FABRIC A WIRE?

The fabric carries chip 1's bus sums to chip 2 unchanged: chip 1 puts a Q4.28
word in its IC TX half, the DDE clocks it across MIX_0..2 and chip 2's scatter
lifts it out at the same slot. There is no gain, no conversion and no state in
between, so ONE invariant holds at every instant, whatever the graph is doing:

    what chip 2 RECEIVES on MAIN L/R == what chip 1 SENDS on MAIN L/R.

S115-2 measured that broken on MW-D24-2 and nothing in the self-test saw it:
`_buf_C2_RECV_MAIN_L` pinned at Q4.28 saturation (+18.06 dBFS peak, words at
`0x7FFFFEE0`) with chip 1's own `_buf_C1_BUS_MAIN_L` at -117.8 dBFS and every
strip's `MainOn` at 0. In the product that is a full-scale signal on the main
outputs; on the bench it made S115's and S117's acoustic loop unmeasurable and
a later RUN ALL pass carried the fictional verdict through (S117-3), because a
pass whose link is alive does not boot the pair.

THE READING IS A COMPARISON, NOT A THRESHOLD, and that is deliberate. A bare
"MAIN must be quiet" would be wrong the moment a test legitimately opens a
strip, and would have to own a setup of its own. Comparing the two ends owns
none: it is true at digital silence, true under a tone, and false only when
the fabric stops being a wire.

Peeks are NOT coherent -- a 16-word walk spans ~15 audio blocks (S115) -- so
this reads MAGNITUDE, never a waveform, and asks for the same verdict TWICE
before calling a fault, so a transient between the two ends is not one.

  python3 dsp4_icrecv.py --symdir /home/app/loopthd/s109
  python3 dsp4_icrecv.py --symdir . --json ic1.json --reps 3
"""
import argparse
import json
import math
import os
import sys
import time

_argv = list(sys.argv)
sys.argv = ['s']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                              # noqa: E402

FRAME_COUNT = 0xE004
BLOCK = 16

# The fabric is a wire, so the two ends agree. 12 dB is far wider than any
# real difference (the healthy part measured 0.8-1.2 dB under a tone, S118)
# and far narrower than the fault (a 133 dB step, S115-2).
GAIN_TOL_DB = 12.0
# Below this the two ends are both in the dither and a dB difference means
# nothing; the fault is +15 to +18 dBFS, so no real fault hides under it.
FLOOR_DBFS = -40.0
# A main mix bus above full scale is a fault whatever chip 1 is doing.
CEILING_DBFS = 0.0

PAIRS = (('MAIN_L', '_buf_C1_BUS_MAIN_L', '_blk_C2_RECV_MAIN_L'),
         ('MAIN_R', '_buf_C1_BUS_MAIN_R', '_blk_C2_RECV_MAIN_R'))


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def peak_db(words):
    pk = max(abs(s32(w)) for w in words) / float(1 << 28)
    return -300.0 if pk <= 0 else 20.0 * math.log10(pk)


def block(sc, sym):
    a = sc.addr(sym)
    return [sc.peek(a + i) for i in range(BLOCK)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symdir', default='.')
    ap.add_argument('--reps', type=int, default=2,
                    help='read sets that must AGREE before a fault is called')
    ap.add_argument('--json')
    # The three limits, overridable so the bench can re-calibrate them --
    # and so the verdict logic can be PROVEN on a healthy part by moving a
    # limit onto a real reading instead of faking a fault (S118 §4).
    ap.add_argument('--gain-tol', type=float, default=GAIN_TOL_DB)
    ap.add_argument('--floor', type=float, default=FLOOR_DBFS)
    ap.add_argument('--ceiling', type=float, default=CEILING_DBFS)
    a = ap.parse_args(_argv[1:])

    # A PAIR THAT DOES NOT ANSWER IS `NO DATA`, NOT A CRASH AND NEVER A PASS.
    # This gate runs FIRST in a RUN ALL pass, before the pair has been proven
    # by DR2, so "the link is down" is an ordinary outcome of running it and
    # has to come back as a verdict the caller can read.
    try:
        s1 = S.Scope(1, symfile=os.path.join(a.symdir, 'chip1.sym.json'))
        s1.d.resync(); s1.check_chip()
        s2 = S.Scope(2, symfile=os.path.join(a.symdir, 'chip2.sym.json'))
        s2.d.resync(); s2.check_chip()

        f1a, f2a = s1.rd_counter(FRAME_COUNT), s2.rd_counter(FRAME_COUNT)
        sets = []
        for rep in range(a.reps):
            if rep:
                time.sleep(0.3)
            one = {}
            for name, sym1, sym2 in PAIRS:
                w1, w2 = block(s1, sym1), block(s2, sym2)
                one[name] = {'c1_db': peak_db(w1), 'c2_db': peak_db(w2),
                             'c1': ['%08X' % (w & 0xFFFFFFFF) for w in w1],
                             'c2': ['%08X' % (w & 0xFFFFFFFF) for w in w2]}
            sets.append(one)
        f1b, f2b = s1.rd_counter(FRAME_COUNT), s2.rd_counter(FRAME_COUNT)
    except (IOError, OSError, SystemExit) as e:
        print('IC1 NO DATA  the pair did not answer: %s' % e)
        if a.json:
            json.dump({'verdict': 'NO DATA', 'measured':
                       'the pair did not answer: %s' % e, 'live': False},
                      open(a.json, 'w'), indent=1)
        return 0

    live = (f1a is not None and f1b is not None and f1b != f1a
            and f2a is not None and f2b is not None and f2b != f2a)

    faults = {}
    for name, _, _ in PAIRS:
        hit = []
        for one in sets:
            d = one[name]
            over = (d['c2_db'] > a.floor
                    and d['c2_db'] - d['c1_db'] > a.gain_tol)
            hot = d['c2_db'] > a.ceiling
            hit.append(over or hot)
        if hit and all(hit):
            faults[name] = sets[-1][name]

    last = sets[-1]
    measured = ', '.join(
        '%s c1 %+.1f -> c2 %+.1f dBFS' % (n, last[n]['c1_db'], last[n]['c2_db'])
        for n, _, _ in PAIRS)
    if not live:
        verdict = 'NO DATA'
        measured = ('the block clock is not turning: chip1 FRAME_COUNT %s->%s, '
                    'chip2 %s->%s' % (f1a, f1b, f2a, f2b))
    elif faults:
        verdict = 'FAIL'
    else:
        verdict = 'PASS'

    print('IC1 %s  %s  [tol %+.1f dB over %.1f dBFS, ceiling %.1f dBFS]'
          % (verdict, measured, a.gain_tol, a.floor, a.ceiling))
    print('chip1 FRAME_COUNT %s -> %s   chip2 %s -> %s' % (f1a, f1b, f2a, f2b))
    for name, _, _ in PAIRS:
        for i, one in enumerate(sets):
            d = one[name]
            print('  set %d %-7s c1 %+8.2f dBFS  c2 %+8.2f dBFS  delta %+7.2f'
                  % (i, name, d['c1_db'], d['c2_db'], d['c2_db'] - d['c1_db']))
        print('    c1 words %s' % ' '.join(sets[-1][name]['c1'][:8]))
        print('    c2 words %s' % ' '.join(sets[-1][name]['c2'][:8]))
    if faults:
        print('FAULT: chip 2 receives what chip 1 never sent on %s -- the '
              'fabric is not a wire (S115-2).' % ', '.join(sorted(faults)))

    out = {'verdict': verdict, 'measured': measured, 'live': live,
           'frame1': [f1a, f1b], 'frame2': [f2a, f2b], 'sets': sets,
           'limits': {'gain_tol_db': a.gain_tol, 'floor_dbfs': a.floor,
                      'ceiling_dbfs': a.ceiling}}
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
