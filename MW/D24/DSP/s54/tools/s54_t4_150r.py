#!/usr/bin/env python3
"""s54_t4_150r.py — T4 + T4b with 150 ohm across J25 pins 2-3 (loop cable off). Tone off, codes 63 and 0.
First a negative check that the loop is really gone: 1 kHz -20 dBFS on AUX 1 at code 0 must not reach the lane."""
import sys
_ARGV = list(sys.argv)
import s54lib as T
R = T.Rig('/home/app/s54/s54_t4_150r.jsonl')
P = lambda *a: print(*a, flush=True)
GAIN = {63: 58.717, 0: 5.578}          # loop gains from T1 (64-code sweep), measured with the loop in place
R.meas(T.LOOP)
R.chain(0); R.osc(1000.0, -20.0)
m = R.windows(4, settle_windows=8, tag='t4r_loopcheck')
P('loop check, code 0, osc -20 on AUX 1: lane coherent pk %.2f dBFS (with loop: -14.42), RMS %.2f' % (T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'rms')))
T.log({'ev': 't4r_loopcheck', 'coh_pk': T.summ(m, 'coh_pk_dbfs'), 'rms': T.summ(m, 'rms')})
R.osc(on=False)
for code in (63, 0):
    R.chain(code)
    m = R.windows(8, settle_windows=16, tag='t4r_c%d' % code)
    rms, nse = T.summ(m, 'rms'), T.summ(m, 'noise')
    P('code %2d tone OFF, 150 ohm: RmsResult %.2f dBFS  NoiseResult %.2f dBFS  (windows %s)  input-referred %.2f dBFS-eq (divisor %+.3f dB)'
      % (code, rms, nse, ' '.join('%.2f' % r['rms'] for r in m['rows']), nse - GAIN[code], GAIN[code]))
    T.log({'ev': 't4r', 'code': code, 'rms': rms, 'noise': nse, 'gain': GAIN[code], 'input_ref': nse - GAIN[code],
           'windows': [r['rms'] for r in m['rows']]})
R.chain(0); R.osc(1000.0, -20.0)
P('handback: code 0, 1 kHz -20 dBFS on strip 6 -> AUX 1 (no loop), MeasChan 20')
