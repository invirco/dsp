#!/usr/bin/env python3
"""A dead gain element does not silence the lane -- it leaves the tone SHORT
by the element's own size. Can the step's window resolve that?

The station holds the converter at about the same level at every step, so a
dead element shows up as a reading low by 6.55 dB (the smallest element) to
12.85 dB (the largest). This drives exactly that, at the window the step uses,
and asks for the reading to be right to well inside the 3 dB tolerance.
"""
import sys, time, json, statistics
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P

STRIP = P.DONOR_DEFAULT
BASE = float(sys.argv[1]) if len(sys.argv)>1 else -12.0
SHORT = [0.0, 6.552, 6.618, 7.211, 7.391, 7.429, 12.845]   # the six increments
u = P.Unit()
u.meas_chan(STRIP)
out = []
try:
    for short in SHORT:
        vals, secs = [], []
        for _ in range(5):
            u.osc(chan=STRIP, freq=1000.0, level_dbfs=BASE, on=True)
            m0 = u.measure(1000.0, BASE, windows=P.GAIN_READ_WINDOWS,
                           settle=P.GAIN_SETTLE_WINDOWS)
            t0 = time.time()
            u.osc(level_dbfs=BASE - short)
            m = u.measure(1000.0, BASE, windows=P.GAIN_READ_WINDOWS,
                          settle=P.GAIN_SETTLE_WINDOWS)
            secs.append(time.time() - t0)
            if m0.get('rms') is not None and m.get('rms') is not None:
                vals.append(m0['rms'] - m['rms'])
        out.append(dict(short=short, seen=vals, secs=secs))
        print('element short by %6.3f dB -> node reads it %6.3f dB low '
              '(spread %.3f, n %d, %.3f s a reading)   error %+.3f dB'
              % (short, statistics.median(vals), max(vals) - min(vals),
                 len(vals), statistics.median(secs),
                 statistics.median(vals) - short))
finally:
    u.osc(on=False)
json.dump(out, open('/home/app/selftest/s125-sep.json', 'w'), indent=1)
