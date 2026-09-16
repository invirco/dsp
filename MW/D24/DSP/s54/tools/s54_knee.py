#!/usr/bin/env python3
"""s54_knee.py — is the T3 knee digital or analog, input-level or lane-level?
(a) code 0: osc across the knee; chip-2 AUX 1 meter peak + limiter envelope peeked (read-only), strip-6
    digital THD+N, strip-20 loop THD+N.  (b) code 2: the lane-level sweep again with 19.5 dB less drive."""
import sys, time
_ARGV = list(sys.argv)
import s54lib as T
X = T.X
R = T.Rig('/home/app/s54/s54_knee.jsonl')
c2 = X.Chip(2)
P = lambda *a: print(*a, flush=True)
def c2peak(n=16):
    m = 0.0
    for _ in range(n):
        m = max(m, X.from_f32(c2.sc.peek(c2.sc.sym['_mtr_peak_C2_MTR_AUX_01']))); time.sleep(0.01)
    return m
def c1peak(n=16):
    m = 0.0
    for _ in range(n):
        m = max(m, X.from_f32(R.peek('_mtr_peak_C1_MTR_20'))); time.sleep(0.01)
    return m
R.chain(0)
for L in (-25.0, -20.0, -19.0, -18.5, -18.0, -17.0, -10.0):
    R.osc(1000.0, L)
    R.meas(6); d = R.windows(2, settle_windows=4, tag='knee_dig')
    R.meas(20); m = R.windows(3, settle_windows=5, tag='knee_loop')
    env = c2.sc.peek(c2.sc.sym['_lim_envelope_C2_AUX_LIM_01'])
    P('code 0 osc %6.2f | strip6 THD+N %8.2f coh %+6.3f | C2 AUX1 meter pk %+7.2f dBFS lim_env 0x%08X | loop coh pk %7.2f THD+N %7.2f dB (%.4f %%) C1 mtr pk %+7.2f'
      % (L, T.summ(d, 'thd'), T.summ(d, 'H_db'), T.dbv(c2peak()), env, T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'thd'), T.pct(T.summ(m, 'thd')), T.dbv(c1peak())))
    T.log({'ev': 'knee_c2', 'osc': L, 'c2_aux1_peak_db': T.dbv(c2peak()), 'lim_env': env})
R.chain(2); R.meas(20)
g2 = 25.041
for tgt in (-20, -14, -13, -12, -10, -6, -3, -1, 0, 1):
    L = tgt - g2
    R.osc(1000.0, L)
    m = R.windows(4, settle_windows=6, tag='knee_c2code2')
    pk = c1peak(24)
    P('code 2 lane target %+5.1f osc %7.2f | coh pk %7.2f RMS %7.2f THD+N %8.2f dB = %.5f %% noise %7.2f | C1 mtr pk %.6f (%+.3f dBFS)%s'
      % (tgt, L, T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'rms'), T.summ(m, 'thd'), T.pct(T.summ(m, 'thd')), T.summ(m, 'noise'), pk, T.dbv(pk), '  <-- FS' if pk >= 0.9999 else ''))
    T.log({'ev': 'knee_code2', 'target': tgt, 'osc': L, 'meter_peak': pk})
R.chain(0); R.osc(1000.0, -20.0)
