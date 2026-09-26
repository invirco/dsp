#!/usr/bin/env python3
"""Does an open mic input's own noise reach the converter at all?

The seven gain steps are judged on a LEVEL, and the dispatch asked for them to
be read 'against the lane's own noise'. This asks whether there is any such
noise to read: the whole chain at gain 0, then at gain 63 (53 dB), with the
rails up and nothing plugged into anything, read off the measurement node.
"""
import sys, time, json
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P
import d24_chain as CH

LANES = [2, 5, 7, 11, 17, 23]
u = P.Unit()
an = P.Analog(enabled=True, log=lambda s: print('   %s' % s))
an.up()
out = {}
try:
    u.osc(on=False)
    for label, img in (('gain 0', P.CHAIN_TONE), ('gain 63', P.CHAIN_NOISE)):
        an.image = None
        an.chain(img, label)
        time.sleep(0.5)
        row = {}
        for lane in LANES:
            u.meas_chan(lane)
            m = u.measure(None, 0.0, windows=2, settle=4)
            mt = u.meter_peak(lane)
            row[lane] = dict(node=m.get('rms'), noise=m.get('noise'),
                             meter=P.dbv(mt) if mt else None)
        out[label] = row
        print('%-8s %s' % (label, '  '.join(
            '%d:%.1f' % (k, v['node']) for k, v in sorted(row.items())
            if v['node'] is not None)))
finally:
    an.down()
    u.osc(on=False)
json.dump(out, open('/home/app/selftest/s125-floor.json', 'w'), indent=1)
for lane in LANES:
    a = out.get('gain 0', {}).get(lane, {}).get('node')
    b = out.get('gain 63', {}).get(lane, {}).get('node')
    if a is not None and b is not None:
        print('lane %2d: %8.2f -> %8.2f dBFS   rise %+6.2f dB (53.1 dB of gain)'
              % (lane, a, b, b - a))
