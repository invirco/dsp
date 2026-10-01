#!/usr/bin/env python3
"""s160_hf.py -- the 8-24 kHz detail of the S160 open-input captures: 1 kHz
bands, lane dBFS and input-referred dBu, the hump's peak bin, and how the
MIC 2 excess moves with gain code (input-referred constant = it enters before
the gain; lane-constant = after)."""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s160_analyse as A          # noqa: E402

d = sys.argv[1]
dac, steps = A.units_dac_fs(), A.gain_steps()
R = {}
for fn in sorted(os.listdir(d)):
    if fn.startswith('MIC') and fn.endswith('.json'):
        r = A.json.load(open(os.path.join(d, fn)))
        f, p, _ = A.psd(r['captures'])
        g = A.G0[r['input']] + steps[r['code']]
        R[fn[:-10]] = (f, p, 3.0103 + dac - g, r['code'])
edges = list(range(8000, 24001, 1000))
print('1 kHz bands, LANE dBFS (mean-square)')
print('%-9s ' % '' + ' '.join('%6d' % (e // 1000) for e in edges[:-1]) + '  kHz')
for k, (f, p, off, c) in R.items():
    print('%-9s ' % k + ' '.join('%6.1f' % A.band(f, p, lo, hi)
                                 for lo, hi in zip(edges, edges[1:])))
print('\nhump peak (smoothed 300 Hz, 6-24 kHz), lane dB/bin over MIC 5 c63:')
f5, p5 = R['MIC5_c63'][0], R['MIC5_c63'][1]
k = int(300 / f5[1])
sm = lambda p: np.convolve(10 * np.log10(p), np.ones(k) / k, mode='same')
for key in ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63', 'MIC2_c48',
            'MIC2_c32', 'MIC2_c00'):
    f, p, off, c = R[key]
    m = (f > 6000) & (f < 23500)
    diff = sm(p) - sm(p5)
    i = np.argmax(np.where(m, diff, -1e9))
    print('  %-9s peak excess %+5.1f dB at %5.0f Hz' % (key, diff[i], f[i]))
print('\nMIC 2 by code, 10-20 kHz and 1-5 kHz, lane dBFS / input-referred dBu:')
for key in ('MIC2_c00', 'MIC2_c32', 'MIC2_c48', 'MIC2_c63', 'MIC1_c63',
            'MIC5_c63'):
    f, p, off, c = R[key]
    hf, mf = A.band(f, p, 10000, 20000), A.band(f, p, 1000, 5000)
    print('  %-9s code %2d  10-20k %7.1f / %7.1f   1-5k %7.1f / %7.1f   '
          'HF-MF %+5.1f dB' % (key, c, hf, hf + off, mf, mf + off, hf - mf))
