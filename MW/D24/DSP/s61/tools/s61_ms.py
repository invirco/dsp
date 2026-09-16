#!/usr/bin/env python3
"""s61_ms.py — per-stream DSP-side live time (BULK_MS) and host timings, N reads at HZ. Env N, HZ, DSP4_BULK_POST_S."""
import json, os, time
import s61lib as S
T, MC = S.T, S.MC
import dsp4_bulk as B
R = T.Rig('/home/app/s61/s61_ms.jsonl')
sc = R.sc
ref = json.load(open(S.DATA + '/ref_peek_16384.json'))['samples']
N = int(os.environ.get('N', '30')); hz = int(float(os.environ.get('HZ', '10e6')))
ms = []
for i in range(N):
    w, info = B.read(sc, sc.sym[MC.BUF], 16384, hz=hz)
    a = info['attempts'][-1]
    ms.append(a['ms'])
    T.log({'ev': 'ms', 'hz': hz, 'post_s': B.POST_S, 'i': i, 'ok': w == ref, 'attempts': info['attempts']})
S.P('hz %d post %.3f ms: %s' % (hz, B.POST_S, sorted(ms)))
