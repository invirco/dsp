"""s57_readonly.py — READ ONLY snapshot: no cell write, no capture arm, no chain write, no GPIO write.
MIC 5 RX lane (the MIC 5 strip input) RMS/peak from point-sampled contiguous 16-word blocks; the MIC 5 strip post-fader RmsResult
(TEST_MEAS, MeasChan as found) and its meter peak; AUX 1 TX lane RMS/peak; the MIC 5 strip -> AUX 1 cells."""
import math, os, sys
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
X = T.X
P = lambda *a: print(*a, flush=True)
def db(x): return 20 * math.log10(x) if x > 0 else float('-inf')
c1 = X.Chip(1); c2 = X.Chip(2); sc1, sc2 = c1.sc, c2.sc
def blocks(sc, buf, off, st, n):
    w = []
    while len(w) < n:
        try:
            b = sc.peek(sc.sym[buf])
            w.extend(X.s32(sc.peek(b + off + k * st)) / 2.0 ** 31 for k in range(16))
        except IOError:
            pass
    return w
def rp(v): return 'RMS %.2f dBFS, peak %.6f (%.2f dBFS), %d samples' % (db(math.sqrt(sum(x * x for x in v) / len(v))), max(abs(x) for x in v), db(max(abs(x) for x in v)), len(v))
e = sc1.peek(sc1.sym['_c1_rx_node_entry'] + T.LOOP - 1)
off, st = sc1.peek(sc1.sym['_c1_rx_off'] + e), sc1.peek(sc1.sym['_c1_rx_stride'] + e)
P('MIC 5 RX lane (the MIC 5 strip input, rx24in32, 1.0 = ADC FS): ' + rp(blocks(sc1, '_rx_active_buf', off, st, 1600)))
mc = sc1.rd(T.A_MEASCHAN)
P('the MIC 5 strip post-fader: TEST_MEAS MeasChan %d RmsResult %.2f dBFS (DC-24k, 4096-sample window), meter peak _mtr_peak_C1_MTR_nn %.6f (%.2f dBFS), OscOn %d'
  % (mc, X.from_f32(sc1.rd(T.A_RMS)), X.from_f32(sc1.peek(sc1.sym['_mtr_peak_C1_MTR_%02d' % T.LOOP])), db(X.from_f32(sc1.peek(sc1.sym['_mtr_peak_C1_MTR_%02d' % T.LOOP]))), sc1.rd(T.A_OSCON)))
ptrs, offs, strd = sc2.sym['_c2_tx_ptrs'], sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride']
want = sc2.sym['_tx_out_slot_C2_AUX_OUT_01']
idx = [i for i in range(24) if sc2.peek(ptrs + i) == want][0]
P('AUX 1 TX lane (chip 2, Q1.31, 1.0 = DAC FS): ' + rp(blocks(sc2, '_tx_active_buf', sc2.peek(offs + idx), sc2.peek(strd + idx), 1600)))
f = lambda c, n: X.from_f32(c.r(n))
P('the MIC 5 strip -> AUX 1: AuxOn %d, AuxSend %.6f, AuxPick %d, Mute %d, Gain %.6f, Level %.6f, MainOn %d | AUX 1 Level %.6f, Mute %d | strips on AUX 1: %s'
  % (c1.r('Chan%03dAuxOn001' % T.LOOP), f(c1, 'Chan%03dAuxSend001' % T.LOOP), c1.r('Chan%03dAuxPick001' % T.LOOP), c1.r('Chan%03dMute001' % T.LOOP), f(c1, 'Chan%03dGain001' % T.LOOP),
     f(c1, 'Chan%03dLevel001' % T.LOOP), c1.r('Chan%03dMainOn001' % T.LOOP), f(c2, 'Aux001Level001'), c2.r('Aux001Mute001'),
     [s for s in range(1, 25) if c1.r('Chan%03dAuxOn001' % s) == 1]))
