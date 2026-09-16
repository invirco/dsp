"""s57_readline.py [count gap_s] — READ ONLY, one line for the hub: lane RMS/peak (MIC 5 RX), the MIC 5 strip post-fader RmsResult,
AUX 1 TX RMS/peak, the MIC 5 strip AUX 1 send / mute / on. No writes of any kind."""
import math, os, sys
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
X = T.X
def db(x): return 20 * math.log10(x) if x > 0 else float('-inf')
c1 = X.Chip(1); c2 = X.Chip(2); sc1, sc2 = c1.sc, c2.sc
def blocks(sc, buf, off, st, n):
    w = []
    while len(w) < n:
        try:
            b = sc.peek(sc.sym[buf]); w.extend(X.s32(sc.peek(b + off + k * st)) / 2.0 ** 31 for k in range(16))
        except IOError:
            pass
    return w
def rms(v): return db(math.sqrt(sum(x * x for x in v) / len(v)))
def pk(v): return db(max(abs(x) for x in v))
import time
ARGS = [a for a in os.environ.get('S57_LOOP', '1 0').split()]
N, GAP = int(ARGS[0]), float(ARGS[1])
e = sc1.peek(sc1.sym['_c1_rx_node_entry'] + T.LOOP - 1)
idx = [i for i in range(24) if sc2.peek(sc2.sym['_c2_tx_ptrs'] + i) == sc2.sym['_tx_out_slot_C2_AUX_OUT_01']][0]
t0 = time.time()
for it in range(N):
    while time.time() < t0 + it * GAP:
        time.sleep(0.2)
    lane = blocks(sc1, '_rx_active_buf', sc1.peek(sc1.sym['_c1_rx_off'] + e), sc1.peek(sc1.sym['_c1_rx_stride'] + e), 1600)
    post = X.from_f32(sc1.rd(T.A_RMS))
    tx = blocks(sc2, '_tx_active_buf', sc2.peek(sc2.sym['_c2_tx_off'] + idx), sc2.peek(sc2.sym['_c2_tx_stride'] + idx), 1600)
    print('READ lane_rms=%.2f lane_pk=%.2f post=%.2f aux1tx_rms=%.2f aux1tx_pk=%.2f send20=%.6f strip20_mute=%d strip20_on=%d'
          % (rms(lane), pk(lane), post, rms(tx), pk(tx), X.from_f32(c1.r('Chan%03dAuxSend001' % T.LOOP)), c1.r('Chan%03dMute001' % T.LOOP), c1.r('Chan%03dAuxOn001' % T.LOOP)), flush=True)
