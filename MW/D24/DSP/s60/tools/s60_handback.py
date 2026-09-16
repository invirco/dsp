#!/usr/bin/env python3
"""s60_handback.py — the unit as S60 found it (s60_found.jsonl 'found'): TEST_OSC off (1 kHz, 0.1, OscChan 6,
SweepOn 0, SweepStep 1), MeasChan 5, strip 6 off AUX 1, strips 5/6/20 unmuted and the rest muted, MIC 5 code 0.
AN_EN read, never written."""
import subprocess
import s60lib as S
T, X = S.T, S.X
R = T.Rig('/home/app/s60/s60_handback.jsonl')
c1 = R.c1
R.wv(S.A_SWEEPON, 0)
R.osc(1000.0, -20.0, on=False, chan=6)
R.wv(S.A_SWEEPSTEP, 1)
R.chain(0)
c1.wv('Chan006AuxOn001', 0)
for s in range(1, 25):
    want = 0 if s in (5, 6, 20) else 1
    if c1.r('Chan%03dMute001' % s) != want:
        c1.wv('Chan%03dMute001' % s, want)
R.wv(T.A_MEASCHAN, 5)
S.P('handback done; AN_EN', subprocess.run(['pinctrl', 'get', '26'], capture_output=True, text=True).stdout.strip())
