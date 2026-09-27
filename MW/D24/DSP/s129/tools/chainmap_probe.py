#!/usr/bin/env python3
"""chainmap_probe.py -- which 595 byte drives which lane's preamp, on the part.

S129 item 7. MIC 7 passes every tone patch in the loop block and then fails its
own gain-step patch three attempts running, in both of PW's completed passes,
with "nothing reached MIC 7". The loop block runs the whole chain UNMUTED at
gain 0; a gain step writes an image that mutes every preamp EXCEPT the one under
test, at that input's `send_pos`. So the first question is whether byte 11 --
MIC 7's send_pos, `24 - chain_index` -- actually drives MIC 7's preamp on this
unit.

It is answerable with no lead and no tone, which is why it is worth doing before
asking for hands: a preamp at gain 63 with an open input is 33 dB noisier than
the same preamp at gain 0 (S125 measured it), so walking one byte at a time and
watching which lane's OWN NOISE rises names the mapping outright.

Rails up for the walk, down again at the end, chain back to SAFE.
"""
import argparse
import json
import sys
import time

sys.path.insert(0, '/home/app/selftest')
import d24_patch as P                                          # noqa: E402
sys.path.insert(0, '/home/app/dspboot')
import d24_chain as CH                                         # noqa: E402

# defs/products/d24/inputs.csv, send_pos column
SEND_POS = {1: 23, 2: 21, 3: 19, 4: 17, 5: 15, 6: 13, 7: 11, 8: 9,
            9: 7, 10: 5, 11: 3, 12: 1, 13: 22, 14: 20, 15: 18, 16: 16,
            17: 14, 18: 12, 19: 10, 20: 8, 21: 6, 22: 4, 23: 2, 24: 0}


def floors(u, lanes, reps=2):
    out = {}
    for lane in lanes:
        u.meas_chan(lane)
        vals = [u.measure(None, 0.0).get('rms') for _ in range(reps)]
        vals = [v for v in vals if v is not None]
        out[lane] = max(vals) if vals else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--positions', default='',
                    help='comma list of send positions to walk (default: the '
                         'twelve this unit has a front end for)')
    ap.add_argument('--out')
    a = ap.parse_args()

    lanes = list(range(5, 13)) + list(range(17, 25))
    if a.positions:
        walk = [int(x) for x in a.positions.split(',')]
    else:
        walk = [SEND_POS[s] for s in lanes]

    u = P.Unit()
    an = P.Analog(enabled=True, log=lambda s: print('   .. %s' % s),
                  own_rails=True)
    result = {}
    try:
        an.up()
        u.osc(on=False)
        an.chain([0x01] * 24 + [0x00], 'every preamp MUTED at gain 0')
        time.sleep(0.8)
        base = floors(u, lanes)
        print('baseline (all muted): %s'
              % ' '.join('%d=%.1f' % (k, v) for k, v in sorted(base.items())))
        inv = {v: k for k, v in SEND_POS.items()}
        print('\n%-5s %-10s %-10s %s' % ('byte', 'expects', 'rose', 'rise dB'))
        for pos in walk:
            img = [0x01] * 24 + [0x00]
            img[pos] = CH.byte(mute=0, phantom=0, gain=63)
            an.image = None
            an.chain(img, 'byte %d at gain 63, the rest muted' % pos)
            time.sleep(0.8)
            now = floors(u, lanes)
            rise = {k: (now[k] - base[k]) for k in lanes
                    if now.get(k) is not None and base.get(k) is not None}
            top = max(rise, key=lambda k: rise[k])
            result[pos] = dict(expect=inv.get(pos), rose=top,
                               rise=rise[top], all=rise)
            print('%-5d %-10s %-10s %+.1f   %s'
                  % (pos, 'MIC %s' % inv.get(pos), 'MIC %d' % top, rise[top],
                     'OK' if inv.get(pos) == top else '*** MISMATCH ***'))
            sys.stdout.flush()
    finally:
        an.down()
    bad = [p for p, d in result.items() if d['expect'] != d['rose']]
    print('\n%d of %d positions drove the lane they are supposed to; '
          'mismatches: %s' % (len(result) - len(bad), len(result),
                              bad or 'none'))
    if a.out:
        json.dump(result, open(a.out, 'w'), indent=1)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
