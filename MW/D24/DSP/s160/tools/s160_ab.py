#!/usr/bin/env python3
"""s160_ab.py -- does the MIC 2/4 HF hump move with the GAIN CODE or with
TIME? Reads the ordered `seqNN_*` captures (codes alternated on one input)
and prints, per capture, the hump's peak frequency, its level and the time."""
import json
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s160_analyse as A          # noqa: E402

d = sys.argv[1]
for fn in sorted(os.listdir(d)):
    if not fn.startswith('seq'):
        continue
    r = json.load(open(os.path.join(d, fn)))
    for i, c in enumerate(r['captures']):
        f, p, _ = A.psd([c])
        k = int(200 / f[1])
        sm = np.convolve(10 * np.log10(p), np.ones(k) / k, mode='same')
        m = (f > 14000) & (f < 21500)
        j = np.argmax(np.where(m, sm, -1e9))
        hf = A.band(f, p, 14000, 21500)
        print('%-26s cap %d  t+%5.1fs  peak %6.0f Hz  %6.1f dB/bin  '
              '14-21.5k %6.1f dBFS' % (fn[:-5], i, c['t'], f[j], sm[j], hf))
