#!/usr/bin/env python3
"""s54_txpeek.py — what chip 2's gather wrote to the AUX 1 DAC lane (TX DMA words), across the knee.
Read-only peeks of the TX buffer (link traffic only, no audio-path cost). Q4.28, 1.0 = DAC full scale."""
import sys, time, math
_ARGV = list(sys.argv)
import s54lib as T
X = T.X
R = T.Rig('/home/app/s54/s54_txpeek.jsonl')
c2 = X.Chip(2); sc2 = c2.sc
P = lambda *a: print(*a, flush=True)
ptrs, offs, strd = sc2.sym['_c2_tx_ptrs'], sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride']
want = sc2.sym['_tx_out_slot_C2_AUX_OUT_01']
idx = [i for i in range(24) if sc2.peek(ptrs + i) == want][0]
off, st = sc2.peek(offs + idx), sc2.peek(strd + idx)
P('C2_AUX_OUT_01: tx index %d off %d stride %d' % (idx, off, st))
def txwords(n=160):
    w = []
    while len(w) < n:
        try:
            b = sc2.peek(sc2.sym['_tx_active_buf'])
            w.extend(sc2.peek(b + off + k * st) for k in range(16))
        except IOError:
            pass
    return [X.s32(x) / 2.0 ** 28 for x in w]
R.chain(0); R.meas(T.LOOP)
for L in [float(a) for a in _ARGV[1:]] or [-40.0, -20.0, -19.0, -18.5, -18.0, -15.0, -12.0]:
    R.osc(1000.0, L)
    m = R.windows(2, settle_windows=4, tag='txpeek')
    v = txwords()
    pk = max(abs(x) for x in v)
    rms = math.sqrt(sum(x * x for x in v) / len(v))
    big = sum(1 for x in v if abs(x) > 0.999)
    P('osc %6.2f dBFS pk (strip 6 digital) -> AUX1 TX lane |peak| %.5f (%+.2f dBFS) rms %+.2f dBFS, %d/%d words >=0.999 | ratio pk/osc %+.2f dB | loop THD+N %.2f dB'
      % (L, pk, T.dbv(pk), T.dbv(rms), big, len(v), T.dbv(pk) - L, T.summ(m, 'thd')))
    T.log({'ev': 'txpeek', 'osc': L, 'tx_peak': pk, 'tx_rms_db': T.dbv(rms), 'n_fs': big, 'n': len(v), 'sample': v[:48]})
R.osc(1000.0, -20.0)
