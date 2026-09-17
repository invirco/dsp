#!/usr/bin/env python3
"""s67_click.py <tag> — S67-6 on real signal: strip 5 = the MIC 5 lane (analog, code 0, OSC OFF, the converter and
loop-source noise only), fader unity, pan centre, on MAIN; capture 16,384 samples of MAIN L (MeasChan 33) and of
strip 5 post-fader, count MAIN L samples at -8.0 (0x80000000) and samples whose |value| > 1000x the strip's peak."""
import sys
_ARGV = list(sys.argv)
import s67lib as L
import dsp4_meascap as MC
T, X = L.T, L.X
tag = _ARGV[1] if len(_ARGV) > 1 else 'x'
LEVEL = float(_ARGV[2]) if len(_ARGV) > 2 else 1.0
R = L.Rig('/home/app/s67/s67_click.jsonl')
R.chain(0)
R.base('analog')
R.cw('Chan006AuxOn001', 0)          # the donor silent too: nothing on AUX 1
R.osc(on=False)
R.level(LEVEL)
out = {'level': LEVEL}
for ch in (5, 33, 34):
    R.wv(T.A_MEASCHAN, ch)
    cap = MC.capture(16384, L.os.environ['SYMDIR'], sc=R.sc, log=lambda *a: None)
    v = [X.s32(w) for w in cap['samples']]
    pk = max(abs(x) for x in v)
    neg8 = sum(1 for x in v if x == -2 ** 31)
    out[ch] = {'n': len(v), 'peak_word': pk, 'n_minus8': neg8, 'overruns': cap.get('overruns')}
    L.P('ch %d: %d samples, |peak| %d (%.1f dBFS), -8.0 samples %d' % (ch, len(v), pk, L.db(pk / 2.0 ** 28) if pk else -999, neg8))
    L.save('click_%s_cap%d' % (tag, ch), cap)
R.level(1.0)
L.save('click_%s' % tag, out)
