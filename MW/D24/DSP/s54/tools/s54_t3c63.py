#!/usr/bin/env python3
"""s54_t3c63.py — T3 at code 63, lane -3.0 dBFS pk (PW: THD+N at min and max gain, 3 dB below clipping).
Oscillator trimmed on the coherent lane peak; strip-20 block peak meter read to confirm no sample at FS."""
import sys, time
_ARGV = list(sys.argv)
import s54lib as T
X = T.X
R = T.Rig('/home/app/s54/s54_t3c63.jsonl')
P = lambda *a: print(*a, flush=True)
def mtr(n=40):
    m = 0.0
    for _ in range(n):
        m = max(m, X.from_f32(R.peek('_mtr_peak_C1_MTR_%02d' % T.LOOP))); time.sleep(0.01)
    return m
R.chain(63); R.meas(T.LOOP)
L = -3.0 - 58.717
for i in range(5):
    R.osc(1000.0, L)
    m = R.windows(2, settle_windows=8, tag='t3c63_trim')
    pk = T.summ(m, 'coh_pk_dbfs')
    P('trim %d: osc %.3f -> lane coh pk %.3f dBFS' % (i, L, pk))
    if pk < -30:
        P('LANE AT FLOOR: loop not there -- nothing measured'); R.chain(0); R.osc(1000.0, -20.0); sys.exit(3)
    if abs(pk + 3.0) <= 0.02:
        break
    L += -3.0 - pk
m = R.windows(6, settle_windows=8, tag='t3c63')
pk = mtr()
thd, nse = T.summ(m, 'thd'), T.summ(m, 'noise')
P('code 63 osc %.3f  lane coh pk %.3f dBFS  RMS %.3f  ThdResult %.2f dB = %.5f %%  NoiseResult %.2f dBFS  meter pk %.6f (%+.3f dBFS)%s'
  % (L, T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'rms'), thd, T.pct(thd), nse, pk, T.dbv(pk), '  <-- FS' if pk >= 0.9999 else '  (no sample at FS)'))
P('  windows ThdResult: %s' % ' '.join('%.2f' % r['thd'] for r in m['rows']))
T.log({'ev': 't3c63', 'osc': L, 'coh_pk': T.summ(m, 'coh_pk_dbfs'), 'thd': thd, 'noise': nse, 'meter_peak': pk})
R.chain(0); R.osc(1000.0, -20.0)
m = R.windows(3, settle_windows=6, tag='t3c63_handback')
P('handback code 0, 1 kHz -20: RMS %.2f THD+N %.2f dB' % (T.summ(m, 'rms'), T.summ(m, 'thd')))
