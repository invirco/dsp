#!/usr/bin/env python3
"""s65_hookcheck.py — the cue hook on a PAIRED chain (shipping.config.s26: SIMD_DYN): strips 5 (odd, pool1 slots) and 6
(even) each alone as the tone's strip and the only cued strip; PFL -> L and R, AFL pan L -> L only. -20 dBFS pk 1 kHz
-> the 1 kHz band reads -23.01 wherever the tone should be."""
import json, time
import s65lib as L
T, X = L.T, L.X
R = T.Rig(__import__('os').environ['SYMDIR'] + '/s65_hookcheck.jsonl'); C = L.Cue(R); c1 = R.c1
i = L.nearest(1000.0)
C.clear(); C.wr(L.RTA_MODE, 0); C.wr(L.RTA_ON, 1)
out = []
for s in (5, 6):
    pan0 = c1.r('Chan%03dPan001' % s)
    R.osc(freq=1000.0, level_db=-20.0, on=True, chan=s)
    C.clear(); C.wr(L.SEL(s), 1)
    for mode in (0, 1):
        C.wr(L.MODE, mode); c1.wv('Chan%03dPan001' % s, X.f32(0.0)); time.sleep(1.0)
        l, r = C.bands()
        rec = {'strip': s, 'mode': 'PFL' if mode == 0 else 'AFL panL', 'L_1k': round(l[i], 3), 'R_1k': round(r[i], 3),
               'L_oct': [round(l[i] - l[i - 3], 1), round(l[i] - l[i + 3], 1)], 'active': C.rd(L.ACTIVE)}
        out.append(rec); T.log(dict(ev='hook', **rec)); print(json.dumps(rec))
    c1.wv('Chan%03dPan001' % s, pan0)
C.clear(); C.wr(L.MODE, 0); C.wr(L.RTA_ON, 0)
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
