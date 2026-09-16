#!/usr/bin/env python3
"""s60_digital.py — the chirp through the DIGITAL path only: TEST_OSC chirp -20 dBFS on strip 6, capture strip 6's
post-fader twice. Proves (a) the capture starts on a period boundary (sample 0 = sweep sample 0, lag 0 against
the host model), (b) every period is the same samples (capture 1 == capture 2), (c) the host model's distance from
the part's 40-bit arithmetic, (d) the deconvolution of the digital path: latency 0, gain 0 dB, flat, (e) chip-1
cycles per pass with the chirp running vs the tone (interleaved, exact TCOUNT), overruns. Then the loop check:
tone 1 kHz -20 dBFS, MeasChan = MIC 5 strip: is the cable on J25?"""
import math, statistics as st, subprocess, sys, time
import s60lib as S
T, X, CH = S.T, S.X, S.CH
R = T.Rig('/home/app/s60/s60_digital.jsonl')
c1, sc = R.c1, R.sc
S.P('an_en', subprocess.run(['pinctrl', 'get', '26'], capture_output=True, text=True).stdout.strip())
for k in ('_osc_ch_pos_C1_TEST_OSC', '_osc_ch_rtab_C1_TEST_OSC'):
    assert k in sc.sym, k
S.chirp(R, -20.0, 0, chan=6)
caps = [S.capture(R, 16384, 6, 'dig_strip6_chirp_m20_%d' % i) for i in (1, 2)]
a, b = S.fs_samples(caps[0]), S.fs_samples(caps[1])
ndiff = sum(1 for u, v in zip(caps[0]['samples'], caps[1]['samples']) if u != v)
S.P('capture 1 vs 2: %d of %d samples differ; overruns %d / %d' % (ndiff, len(a), caps[0]['overruns'], caps[1]['overruns']))
lvl = R.chirp_level
m = CH.model(0, lvl)
best = None
for lag in range(-40, 41):
    e = sum((a[i] - m[(i + lag) % len(m)]) ** 2 for i in range(0, len(a)))
    if best is None or e < best[1]:
        best = (lag, e)
sig = sum(v * v for v in a)
err_db, maxd = CH.compare_model(a, 0, lvl)
S.P('alignment: best lag vs host model %d samples; model error at lag 0 %.1f dB re signal, max |diff| %.3g FS'
    % (best[0], err_db, maxd))
# the model's error by position in the period (does it grow along the sweep?)
seg = []
for k in range(8):
    lo, hi = k * 2048, (k + 1) * 2048
    e = sum((a[i] - m[i]) ** 2 for i in range(lo, hi)); s_ = sum(a[i] ** 2 for i in range(lo, hi))
    seg.append(round(10 * math.log10(e / s_), 1) if e > 0 else None)
S.P('model error by eighth of the period, dB: %s' % seg)
res = CH.analyse(a, m, 0, y2=b)
CH.report(res, 'DIGITAL strip 6 post-fader vs host model')
T.log({'ev': 'digital', 'ndiff': ndiff, 'lag': best[0], 'model_err_db': err_db, 'model_maxdiff': maxd, 'seg_err': seg,
       'latency_peak': res['latency_peak'], 'gd': res['latency_gd_1k_10k'], 'gain': res['gain_1k_db'],
       'response': res['response'], 'thd_db': res['thd_db']})

# cost: exact per-pass cycles, chirp vs tone, interleaved
Pc = sc.sym['_proc_cyc']; O = sc.sym['_diag_blk_overrun']
pk = lambda adr: R._retry(sc.peek, adr)
o0 = pk(O); ch, tn = [], []
for rnd in range(8):
    S.chirp(R, -20.0, 0, chan=6); time.sleep(0.2)
    te = time.time() + 0.4
    while time.time() < te:
        ch.append(pk(Pc))
    S.tone(R, 1000.0, -20.0, chan=6); time.sleep(0.2)
    te = time.time() + 0.4
    while time.time() < te:
        tn.append(pk(Pc))
o1 = pk(O)
S.P('cycles/pass: chirp median %d (n %d, max %d), tone median %d (n %d, max %d); delta %+d; overruns +%d; budget 327680'
    % (st.median(ch), len(ch), max(ch), st.median(tn), len(tn), max(tn), st.median(ch) - st.median(tn), (o1 - o0) & 0xFFFFFFFF))
T.log({'ev': 'cost', 'chirp_med': st.median(ch), 'tone_med': st.median(tn), 'chirp_max': max(ch), 'tone_max': max(tn),
       'n': [len(ch), len(tn)], 'overruns': (o1 - o0) & 0xFFFFFFFF})

# the loop check
M5 = T.LOOP
R.meas(M5)
mm = R.windows(3, settle_windows=3, tag='loopcheck')
S.P('LOOP CHECK: tone 1 kHz -20 dBFS on strip 6, strip %d RMS %.2f dBFS, coherent gain %s dB'
    % (M5, T.summ(mm, 'rms'), '%.3f' % T.summ(mm, 'H_db') if T.summ(mm, 'H_db') is not None else '-'))
