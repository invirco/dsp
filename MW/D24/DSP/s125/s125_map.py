#!/usr/bin/env python3
"""Which 595 chain position drives which converter lane?

One position unmuted at full gain at a time, every other channel muted -- the
image `d24_patch.step_image()` builds -- and the lane that rises is the answer.
The lane's own preamp noise is the stimulus, so this needs no lead and no
oscillator: 53 dB of gain lifts an open input about 33 dB above the converter
floor (measured, s125_floor.py).
"""
import sys, time, json
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P
import d24_chain as CH

LANES = list(range(1, 25))
u = P.Unit()
an = P.Analog(enabled=True, log=lambda s: None)
an.up()
base = {}
out = {}
try:
    u.osc(on=False)
    an.image = None
    an.chain([0x01] * 24 + [0x00], 'all muted')
    time.sleep(0.5)
    for lane in LANES:
        u.meas_chan(lane)
        base[lane] = u.measure(None, 0.0, windows=1, settle=3).get('rms')
    print('floor: %s' % ' '.join('%d:%.0f' % (k, v) for k, v in sorted(base.items())))
    for pos in range(1, 25):
        img = [0x01] * 24 + [0x00]
        img[pos - 1] = CH.byte(mute=0, phantom=0, gain=63)
        an.image = None
        an.chain(img, 'position %d' % pos)
        time.sleep(0.3)
        rises = {}
        for lane in LANES:
            u.meas_chan(lane)
            v = u.measure(None, 0.0, windows=1, settle=3).get('rms')
            if v is not None and base[lane] is not None:
                rises[lane] = v - base[lane]
        top = sorted(rises.items(), key=lambda kv: -kv[1])[:2]
        out[pos] = dict(rises=rises, top=top)
        print('position %2d -> lane %2d  %+6.2f dB   (next %2d %+6.2f)'
              % (pos, top[0][0], top[0][1], top[1][0], top[1][1]))
finally:
    an.down()
    u.osc(on=False)
json.dump(dict(base=base, positions=out),
          open('/home/app/selftest/s125-map.json', 'w'), indent=1, default=str)
