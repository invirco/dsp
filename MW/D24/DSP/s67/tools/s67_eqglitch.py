#!/usr/bin/env python3
"""s67_eqglitch.py — does an EQ coefficient swap on strip 5 put anything on MAIN L that strip 5's post-fader does not
carry? osc mode, strip 5 alone on MAIN, MeasChan 33 (MAIN L) with XtalkSrc 5 / XtalkDst 33 so every window gives
MAIN L's RMS/THD+N AND the energy ratio MAIN L : strip 5 (expected -6.02 dB). EQ toggled unity <-> +6 dB peak."""
import json, sys, time
import s67lib as L
T, X = L.T, L.X
F = float(sys.argv[1]) if len(sys.argv) > 1 else 250.0
R = L.Rig('/home/app/s67/s67_eqglitch.jsonl')
R.chain(0)
R.base('osc')
R.osc(F, -26.0, on=True, chan=5)
R.wv(T.A_MEASCHAN, 33); R.wv(T.A_XSRC, 5); R.wv(T.A_XDST, 33)
pk = L.rbj_peaking(1000.0, 1.0, 6.0)
seen = None
t0 = time.time()
events = [(1.0, 'peak'), (3.0, 'unity'), (5.0, 'peak'), (7.0, 'unity'), (9.0, None)]
k = 0
rows = []
while True:
    t = time.time() - t0
    if k < len(events) and t >= events[k][0]:
        what = events[k][1]
        if what is None:
            break
        if what == 'peak' and k == 0:
            # the state before the first swap: capture MAIN L (MeasChan 33) and strip 5, and peek the bus block
            import dsp4_meascap as MC
            for ch in (33, 5):
                R.wv(T.A_MEASCHAN, ch)
                cap = MC.capture(4096, L.os.environ['SYMDIR'], sc=R.sc, log=lambda *a: None)
                L.save('eqglitch_cap%d_%d' % (ch, int(F)), cap)
                v = [X.s32(w) / 2.0 ** 28 for w in cap['samples'][:4096]]
                L.P('capture ch %d: first 12 %s  max|x| %.4f' % (ch, ['%.4f' % x for x in v[:12]], max(abs(x) for x in v)))
            R.wv(T.A_MEASCHAN, 33)
            L.P('bus MAIN L peek', ['%.4f' % (X.s32(w) / 2.0 ** 28) for w in R.busword('_buf_C1_BUS_MAIN_L')])
            L.P('osc freq word %.4f k %.6f' % (X.from_f32(R.rd(T.A_OSCFREQ)), X.from_f32(R._retry(R.sc.peek, R.sc.sym['_osc_k_C1_TEST_OSC']))))
        R.eq_bands([pk if what == 'peak' else L.UNITY_BQ] + [L.UNITY_BQ] * 3)
        L.P('EQ ->', what)
        rows.append({'t': t, 'ev': what})
        k += 1
    s = R.rd(T.A_SEQ)
    if s == seen:
        time.sleep(0.02); continue
    rms = X.from_f32(R.rd(T.A_RMS)); thd = X.from_f32(R.rd(T.A_THD)); xt = X.from_f32(R.rd(T.A_XTALK))
    if R.rd(T.A_SEQ) != s:
        continue
    seen = s
    rows.append({'t': round(t, 3), 'seq': s, 'rms': rms, 'thd': thd, 'x33_5': xt})
    L.P('seq %d  MAIN L rms %8.3f dBFS  THD+N %8.3f dB  MAIN L:strip5 %8.3f dB' % (s, rms, thd, xt))
R.wv(T.A_XSRC, 0); R.wv(T.A_XDST, 0)
R.osc(on=False)
L.save('eqglitch_%d' % int(F), rows)
