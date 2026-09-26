#!/usr/bin/env python3
"""How long does the node need to report a level DROP correctly?

A gain step that is short reads LOW, and the node's RMS settles asymmetrically
-- fast onto a rise, slowly off a fall. This sweeps the settle against the
smallest element the station has to catch (6.552 dB) and the largest (12.845),
and reports the reading, its spread and its cost.
"""
import sys, time, json, statistics
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P

STRIP = P.DONOR_DEFAULT
BASE = -12.0
GRID = [(2, 1), (3, 1), (4, 1), (4, 2), (6, 1), (6, 2), (8, 2), (12, 2)]
u = P.Unit()
u.meas_chan(STRIP)
out = []
try:
    for settle, windows in GRID:
        line = []
        for short in (6.552, 12.845):
            vals, secs = [], []
            for _ in range(5):
                u.osc(chan=STRIP, freq=1000.0, level_dbfs=BASE, on=True)
                m0 = u.measure(1000.0, BASE, windows=windows, settle=settle)
                t0 = time.time()
                u.osc(level_dbfs=BASE - short)
                m = u.measure(1000.0, BASE, windows=windows, settle=settle)
                secs.append(time.time() - t0)
                if m0.get('rms') is not None and m.get('rms') is not None:
                    vals.append(m0['rms'] - m['rms'])
            line.append((short, statistics.median(vals), max(vals) - min(vals),
                         statistics.median(secs)))
        out.append(dict(settle=settle, windows=windows, rows=line))
        print('settle %2d win %d | %.3f s | 6.552 -> %6.3f (err %+6.3f, spread %.3f)'
              ' | 12.845 -> %6.3f (err %+6.3f, spread %.3f)'
              % (settle, windows, line[0][3],
                 line[0][1], line[0][1] - 6.552, line[0][2],
                 line[1][1], line[1][1] - 12.845, line[1][2]))
finally:
    u.osc(on=False)
json.dump(out, open('/home/app/selftest/s125-sweep.json', 'w'), indent=1)
