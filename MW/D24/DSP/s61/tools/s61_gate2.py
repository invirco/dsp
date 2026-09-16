#!/usr/bin/env python3
"""s61_gate2.py — the bulk read's error check on real data (S61 gate 2).

TEST_OSC chirp -20 dBFS on strip 6, one 16,384-word capture of strip 6 post-fader (static afterwards: the arm
is one-shot). Reference = the same buffer read by PEEK (the S56 path). Then N bulk reads of the SAME buffer at
each clock in HZ, every one compared word for word with the reference and checked by the part's two sums.
Env: N (100), HZ (comma list), LEN (16384). Log: /home/app/s61/s61_gate2.jsonl"""
import json, os, sys, time
import s61lib as S
T, MC = S.T, S.MC
import dsp4_bulk as B
R = T.Rig('/home/app/s61/s61_gate2.jsonl')
sc = R.sc
N = int(os.environ.get('N', '100'))
HZ = [int(float(h)) for h in os.environ.get('HZ', '8e6').split(',')]
LEN = int(os.environ.get('LEN', '16384'))
base = sc.sym[MC.BUF]
refp = S.DATA + '/ref_peek_%d.json' % LEN
if os.path.exists(refp) and os.environ.get('NEWREF') != '1':
    ref = json.load(open(refp))['samples']
    S.P('reference from %s' % refp)
else:
    S.chirp(R, -20.0, 0, chan=6)
    os.environ['DSP4_BULK'] = '0'
    cap = S.capture(R, LEN, 6, 'ref_peek_%d' % LEN)
    os.environ['DSP4_BULK'] = '1'
    ref = cap['samples']
    R.wv(4979, 0); R.wv(4975, 0)        # chirp off, osc off: the buffer is now static regardless
    S.P('reference by peek: %d words in %.1f s, nonzero %d, overruns %d' % (
        len(ref), cap['read_s'], sum(1 for v in ref if v), cap['overruns']))
T.log({'ev': 'ref', 'len': len(ref), 'nonzero': sum(1 for v in ref if v), 'sum': '%08x/%08x' % B.sums(ref)})
for hz in HZ:
    bad = retr = 0
    ts = []
    for i in range(N):
        t0 = time.time()
        try:
            w, info = B.read(sc, base, LEN, hz=hz, tries=3)
        except IOError as e:
            bad += 1
            T.log({'ev': 'bulk_fail', 'hz': hz, 'i': i, 'err': str(e)[:400]})
            continue
        dt = time.time() - t0
        ts.append(dt)
        nd = sum(1 for u, v in zip(w, ref) if u != v)
        att = len(info['attempts'])
        retr += att - 1
        if nd or att > 1:
            T.log({'ev': 'bulk_odd', 'hz': hz, 'i': i, 'ndiff_vs_peek': nd, 'attempts': info['attempts']})
        if nd:
            bad += 1
    ts.sort()
    rec = {'ev': 'bulk_hz', 'hz': hz, 'n': N, 'len': LEN, 'wrong': bad, 'retries': retr,
           's_min': round(ts[0], 3) if ts else None, 's_med': round(ts[len(ts) // 2], 3) if ts else None,
           's_max': round(ts[-1], 3) if ts else None,
           'words_per_s_med': round(LEN / ts[len(ts) // 2]) if ts else None,
           'runs': R.rd(B.A_RUNS), 'aborts': R.rd(B.A_ABORT), 'errs': R.rd(B.A_ERR)}
    T.log(rec)
    S.P(json.dumps(rec))
