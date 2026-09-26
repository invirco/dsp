#!/usr/bin/env python3
"""Can the seven gain steps be read against the lane's own noise, with no lead?

The same seven chain images the station writes, on the byte that actually
drives the input (send_pos, S125), read off the measurement node at several
window lengths. The question is not whether the noise is there -- it is, 34 dB
of it -- but whether a reading of it is repeatable enough to judge a 3 dB step.
"""
import sys, time, json, statistics
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P

MIC, LANE, POS = 7, 7, 11
CODES = [0, 1, 2, 4, 8, 16, 32, 63]
EXP = {0: 0.0, 1: 12.845, 2: 19.463, 4: 26.892, 8: 34.283, 16: 41.494,
       32: 48.046, 63: 53.111}
GRID = [(2, 1, 0.0), (4, 2, 0.0), (4, 2, 0.3), (8, 4, 0.3)]

u = P.Unit()
an = P.Analog(enabled=True, log=lambda s: None)
an.up()
res = []
try:
    u.osc(on=False)
    u.meas_chan(LANE)
    for settle, windows, dwell in GRID:
        runs = []
        for rep in range(3):
            row = {}
            for code in CODES:
                an.image = None
                an.chain(an.step_image(POS, code), 'code %d' % code)
                if dwell:
                    time.sleep(dwell)
                t0 = time.time()
                m = u.measure(None, 0.0, windows=windows, settle=settle)
                row[code] = (m.get('rms'), time.time() - t0)
            runs.append(row)
        res.append(dict(settle=settle, windows=windows, dwell=dwell, runs=runs))
        per = statistics.median(runs[0][c][1] for c in CODES)
        print('settle %d win %d dwell %.1f  (%.3f s a step)' % (settle, windows, dwell, per))
        for code in CODES:
            vals = [r[code][0] for r in runs if r[code][0] is not None]
            rises = [r[code][0] - r[0][0] for r in runs
                     if r[code][0] is not None and r[0][0] is not None]
            print('   code %3d exp %+7.3f  node %s  spread %5.2f  rise %s  err %s'
                  % (code, EXP[code],
                     ' '.join('%8.2f' % v for v in vals),
                     (max(vals) - min(vals)) if vals else -1,
                     ' '.join('%+7.2f' % v for v in rises),
                     ' '.join('%+7.2f' % (v - EXP[code]) for v in rises)))
finally:
    an.down()
    u.osc(on=False)
json.dump(res, open('/home/app/selftest/s125-noise.json', 'w'), indent=1, default=str)
