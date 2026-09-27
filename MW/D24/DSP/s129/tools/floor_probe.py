#!/usr/bin/env python3
"""floor_probe.py -- every lane's own noise floor, and the instrument's spread.

S129 items 7 and (addendum 5) the measurement quality, both answerable with NO
lead in the unit.

WHY THIS ANSWERS MIC 7. PW's pass 3 reported MIC 7 as "no tone reached MIC 7:
the lane sat -21.8 dB over its own floor" -- a NEGATIVE rise, i.e. the tone read
21.8 dB BELOW the floor the same pass measured for that lane. A tone cannot be
quieter than the noise it sits in, so the FLOOR is the suspect reading, and the
pass only ever logged the range over all lanes (-114.7 to -88.1 dBFS) and never
which lane was which. This prints them one lane at a time.

WHY IT ANSWERS THE 0.25 dB WINDOW. PW has ruled a gain step passes within
+/-0.25 dB, which is 12x tighter than the window it replaces. The first question
is not the preamp but the instrument: read the same thing five times and see the
spread. Done here on the internal path (oscillator into the donor strip, the
measurement node on the same strip), so it is the node's own repeatability with
no analog in it -- the floor under everything the station measures.

The rails go UP for the floors (a preamp with no supply has no noise to read)
and DOWN again, and the chain is written back SAFE, by Analog.down().
"""
import argparse
import json
import sys
import time

sys.path.insert(0, '/home/app/selftest')
import d24_patch as P                                          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lanes', default='1-24')
    ap.add_argument('--reps', type=int, default=5)
    ap.add_argument('--rails', action='store_true',
                    help='raise AN_EN for the floor pass and lower it after')
    ap.add_argument('--out')
    a = ap.parse_args()

    lo, _, hi = a.lanes.partition('-')
    lanes = list(range(int(lo), int(hi or lo) + 1))

    u = P.Unit()
    an = P.Analog(enabled=a.rails, log=lambda s: print('   .. %s' % s),
                  own_rails=a.rails)
    out = dict(floors={}, repeat={}, chain=None)
    try:
        if a.rails:
            an.up()
            an.chain(P.CHAIN_TONE, 'tone image: unmuted, gain 0, phantom off')
            out['chain'] = 'tone'
            time.sleep(1.0)
        u.osc(on=False)
        print('%-6s %10s %10s %10s %8s' % ('lane', 'floor', 'min', 'max',
                                           'spread'))
        for lane in lanes:
            u.meas_chan(lane)
            vals = []
            for _ in range(a.reps):
                m = u.measure(None, 0.0)
                v = m.get('rms')
                if v is not None:
                    vals.append(v)
            if not vals:
                print('%-6d %10s' % (lane, 'no reading'))
                continue
            out['floors'][lane] = vals
            print('%-6d %10.2f %10.2f %10.2f %8.2f'
                  % (lane, sum(vals) / len(vals), min(vals), max(vals),
                     max(vals) - min(vals)))
            sys.stdout.flush()

        # the instrument's own repeatability, internal path, no analog
        print('\nthe measurement node against the oscillator, internal path:')
        u.osc(chan=24, freq=1000.0, level_dbfs=-30.0, on=True)
        u.meas_chan(24)
        time.sleep(1.0)
        for windows in (1, 2, 3, 6):
            vals = []
            for _ in range(8):
                m = u.measure(1000.0, -30.0, windows=windows,
                              settle=P.SETTLE_WINDOWS)
                vals.append(m['rms'])
            out['repeat'][windows] = vals
            print('  %d read window(s): mean %.3f  spread %.3f dB  (8 reads)'
                  % (windows, sum(vals) / len(vals), max(vals) - min(vals)))
        u.osc(on=False)
    finally:
        an.down()
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
