#!/usr/bin/env python3
"""s54_t2c63.py — T2 at code 63 (PW: response at MIN and MAX gain). Lane ~-20 dBFS pk at 1 kHz: osc = -20 - 58.717.
Loop presence is checked first at 1 kHz; a lane at the floor means the loop cable is gone and nothing is measured."""
import sys
_ARGV = list(sys.argv)
import s54lib as T
R = T.Rig('/home/app/s54/s54_t2c63.jsonl')
P = lambda *a: print(*a, flush=True)
FREQS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000]
L = -20.0 - 58.717
R.chain(63); R.meas(T.LOOP)
R.osc(1000.0, L)
m = R.windows(4, settle_windows=16, tag='t2c63_presence')
pk = T.summ(m, 'coh_pk_dbfs')
P('presence: code 63 osc %.2f -> lane coh pk %.2f dBFS, RMS %.2f, gain %+.3f dB' % (L, pk, T.summ(m, 'rms'), T.summ(m, 'H_db')))
if pk < -30.0:
    P('LANE AT FLOOR: the loop is not there (cable pulled?) -- nothing measured')
    R.chain(0); R.osc(1000.0, -20.0)
    sys.exit(3)
ref = None
res = []
for f in FREQS:
    R.osc(float(f), L)
    m = R.windows(6 if f <= 50 else 4, settle_windows=16 if f <= 50 else 6, tag='t2c63')
    res.append((f, T.summ(m, 'H_db'), T.phase_avg(m), T.summ(m, 'rms'), T.summ(m, 'thd'), T.spread(m, 'H_db')))
g1k = [r for r in res if r[0] == 1000][0][1]
for f, g, ph, rms, thd, sp in res:
    P('code 63 f %6d  coh %+.3f dB  re 1k %+.3f dB  phase %7.1f  RMS %.2f  THD+N %.2f dB = %.4f %%  spread %.3f'
      % (f, g, g - g1k, ph, rms, thd, T.pct(thd), sp))
    T.log({'ev': 't2c63', 'f': f, 'gain': g, 're1k': g - g1k, 'phase': ph})
R.chain(0); R.osc(1000.0, -20.0)
m = R.windows(3, settle_windows=4, tag='t2c63_handback')
P('handback code 0, 1 kHz -20: RMS %.2f THD+N %.2f dB' % (T.summ(m, 'rms'), T.summ(m, 'thd')))
