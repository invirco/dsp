#!/usr/bin/env python3
"""s60_t7.py — T7 crosstalk at 10 kHz (PW: crosstalk is measured at 10 kHz; supersedes the S54/S55 1 kHz figures).
The S54 T7 method unchanged except the frequency: MIC 5 register alone open at code 2 (as S54), TEST_OSC 10 kHz on
strip 6 -> AUX 1 -> J25 with the MIC 5 strip at -6 dBFS peak (coherent), then every other strip 1..24 brought to unity
in turn and its COHERENT 10 kHz component read against the MIC 5 strip's; control = the worst strip with the
reference running and OscChan 0. Strips put back as found after each read."""
import os, sys, time
import s60lib as S
T, X = S.T, S.X
R = T.Rig('/home/app/s60/s60_t7.jsonl')
c1 = R.c1
M5, DONOR = T.LOOP, T.DONOR
CODE, TGT, F = int(os.environ.get('CODE', '2')), -6.0, 10000.0
KEYS = ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001'] + \
       ['AuxOn%03d' % a for a in range(1, 9)] + ['Mute001']
R.chain(CODE)
time.sleep(3.0)
R.wv(S.A_SWEEPON, 0)
R.osc(F, -40.0, chan=DONOR)
R.meas(M5)
pr = R.windows(3, settle_windows=4, tag='t7probe')
g = T.summ(pr, 'H_db')
L = TGT - g
R.osc(F, L, chan=DONOR)
ref = R.windows(4, settle_windows=4, tag='t7ref')
refpk = T.summ(ref, 'coh_pk_dbfs')
S.P('T7 @ %g Hz, code %d: loop gain %.3f dB -> osc %.2f dBFS; MIC 5 strip %d coherent peak %.2f dBFS, RMS %.2f'
    % (F, CODE, g, L, M5, refpk, T.summ(ref, 'rms')))
rows = []
t0 = time.time()
for n in [s for s in range(1, 25) if s not in (DONOR, M5)]:
    pfx = 'Chan%03d' % n
    saved = {k: c1.r(pfx + k) for k in KEYS}
    X.strip_unity(c1, n)
    R.meas(n, xsrc=M5, xdst=n)
    m = R.windows(3, settle_windows=4, tag='t7_s%02d' % n)
    xt = T.summ(m, 'coh_pk_dbfs') - refpk
    rows.append((n, xt))
    S.P('strip %2d  RMS %8.2f dBFS  coh pk %8.2f dBFS  xtalk %8.2f dB  XtalkResult %8.2f dB'
        % (n, T.summ(m, 'rms'), T.summ(m, 'coh_pk_dbfs'), xt, T.summ(m, 'xtalk')))
    T.log({'ev': 't7_10k', 'strip': n, 'xt_coh_db': xt, 'saved': saved})
    for k in reversed(KEYS):
        c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))
dt = time.time() - t0
w = max(rows, key=lambda r: r[1])
S.P('WORST neighbour at 10 kHz: strip %d at %.2f dB (22 strips in %.0f s)' % (w[0], w[1], dt))
n = w[0]; pfx = 'Chan%03d' % n
saved = {k: c1.r(pfx + k) for k in KEYS}
X.strip_unity(c1, n)
R.meas(n)
R.wv(T.A_OSCCHAN, 0)
m = R.windows(3, settle_windows=4, tag='t7_ctrl')
S.P('CONTROL strip %d, reference running, OscChan 0: coh pk %.2f dBFS -> floor %.2f dB re source'
    % (n, T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'coh_pk_dbfs') - refpk))
T.log({'ev': 't7_10k_summary', 'worst': w, 'rows': rows, 'control_db': T.summ(m, 'coh_pk_dbfs') - refpk,
       'ref_pk': refpk, 'osc': L, 'gain': g, 'seconds': dt})
for k in reversed(KEYS):
    c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))
R.wv(T.A_OSCCHAN, DONOR)
R.meas(M5)
R.chain(0)
