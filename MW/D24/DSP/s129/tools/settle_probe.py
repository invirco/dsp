#!/usr/bin/env python3
"""settle_probe.py -- how long the measurement node takes to follow a DRIVE step.

S129 item 1. PW has ruled option (a): a gain step's settle is counted from the
DRIVE change, as the code-0 reference already counts its own. Before that is
implemented, this measures the thing the ruling is about, ON THE PART and with
NO analog: how many windows after `Test001OscLevel001` moves does the node's own
RmsResult read the new level?

The oscillator is pointed at the DONOR strip and the measurement node is pointed
at the SAME strip, so nothing leaves the DSP -- no rails, no lead, no preamp.
What is left out is the preamp's own ~10 ms after the CS_M latch (S82), which is
a fifth of one window and cannot explain a 6.9 dB error.

  settle_probe.py --steps           the seven gain-step drive levels, in order
  settle_probe.py --pair -30 -78.05 one step, sampled window by window
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, '/home/app/selftest')
import d24_patch as P                                          # noqa: E402

STEPS = [(-30.00, 0, 0.000), (-42.84, 1, 12.845), (-49.46, 2, 19.463),
         (-56.89, 4, 26.892), (-64.28, 8, 34.283), (-71.49, 16, 41.494),
         (-78.05, 32, 48.046)]


def sample(u, strip, freq, secs, t_change):
    """Every window the node publishes for `secs`, with its own seq number."""
    sc = u.chip(1)
    out, seen = [], None
    t0 = time.time()
    while time.time() - t0 < secs:
        s = u._seq()
        if s == seen:
            time.sleep(P.WIN_S / 6)
            continue
        seen = s
        rms = u.readf('Test001RmsResult001')
        out.append(dict(seq=s, t=time.time() - t_change, rms=rms))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strip', type=int, default=24)
    ap.add_argument('--freq', type=float, default=1000.0)
    ap.add_argument('--secs', type=float, default=1.6)
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--pair', nargs=2, type=float, metavar=('FROM', 'TO'))
    ap.add_argument('--steps', action='store_true')
    ap.add_argument('--symdir', default=P.FACTORY_TEST_PAIR_DIR)
    ap.add_argument('--out')
    a = ap.parse_args()

    u = P.Unit(symdir=a.symdir)
    u.osc(chan=a.strip, freq=a.freq, level_dbfs=-30.0, on=True)
    u.meas_chan(a.strip)
    time.sleep(1.0)

    runs = []
    if a.pair:
        pairs = [(a.pair[0], a.pair[1])]
    else:
        pairs = [(STEPS[i][0], STEPS[i + 1][0]) for i in range(len(STEPS) - 1)]
        pairs += [(STEPS[0][0], STEPS[-1][0])]

    for frm, to in pairs:
        for rep in range(a.reps):
            u.osc(level_dbfs=frm)
            time.sleep(1.2)                      # fully settled at the start
            base = u.readf('Test001RmsResult001')
            u.osc(level_dbfs=to)
            t_change = time.time()
            rows = sample(u, a.strip, a.freq, a.secs, t_change)
            final = rows[-1]['rms']
            # how many windows after the change before the reading is within
            # 0.1 dB and stays there
            n_ok = None
            for i, r in enumerate(rows):
                if all(abs(x['rms'] - final) <= 0.1 for x in rows[i:]):
                    n_ok = i
                    break
            runs.append(dict(frm=frm, to=to, rep=rep, base=base, final=final,
                             delta=to - frm, windows_to_settle=n_ok,
                             ms_to_settle=(rows[n_ok]['t'] * 1e3
                                           if n_ok is not None else None),
                             rows=rows))
            print('%7.2f -> %7.2f dBFS  (step %+6.2f)  rep %d  base %8.2f '
                  'final %8.2f  settled after %s windows (%s ms), '
                  'first window read %8.2f'
                  % (frm, to, to - frm, rep, base, final,
                     n_ok, ('%.0f' % (rows[n_ok]['t'] * 1e3)
                            if n_ok is not None else '-'),
                     rows[0]['rms']))
            sys.stdout.flush()

    u.osc(on=False)
    if a.out:
        json.dump(dict(win_s=P.WIN_S, runs=runs), open(a.out, 'w'), indent=1)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
