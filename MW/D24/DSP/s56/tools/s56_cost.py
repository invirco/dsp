"""s56_cost.py — chip-1 cycles per block pass with the capture arm idle vs copying, same signal, interleaved.
MeasChan 6, TEST_OSC 1 kHz -20 dBFS on strip 6, CompOn 0. _proc_cyc is exact per pass (TCOUNT); overruns by delta."""
import json, os, statistics as st, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
r = T.Rig(logpath='/home/app/s56/s56_cost.jsonl')
c1, sc = r.c1, r.sc
c1.wv('Chan006CompOn001', 0)
r.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
r.meas(6)
time.sleep(1)
P = sc.sym['_proc_cyc']; O = sc.sym['_diag_blk_overrun']; I = sc.sym['_meas_cap_idx_C1_TEST_MEAS']
def pk(a): return r._retry(sc.peek, a)
idle, armed, idx_seen = [], [], []
o0 = pk(O); t0 = time.time()
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
for rnd in range(ROUNDS):
    # IDLE arm: capture not armed
    te = time.time() + 0.30
    while time.time() < te:
        idle.append(pk(P))
    # ARMED arm: N = 16384 (1024 blocks, 341 ms); sample while the run is in flight, keep only
    # samples bracketed by a moving index so every armed sample is a copying pass
    sc.d.write(MC.A_CAP_READY, 0); time.sleep(0.003)
    sc.d.write(MC.A_CAP_ARM, 16384); time.sleep(0.01)
    te = time.time() + 0.28
    while time.time() < te:
        i1 = pk(I); v = pk(P); i2 = pk(I)
        if 0 < i1 < i2:
            armed.append(v); idx_seen.append(i2)
    time.sleep(0.1)
o1 = pk(O); dt = time.time() - t0
def summ(x):
    x = sorted(x)
    return {'n': len(x), 'min': x[0], 'p10': x[len(x) // 10], 'median': st.median(x), 'p90': x[9 * len(x) // 10], 'max': x[-1], 'mean': st.mean(x)}
res = {'ev': 'cost', 'idle': summ(idle), 'armed': summ(armed), 'overruns': (o1 - o0) & 0xFFFFFFFF, 'seconds': round(dt, 1),
       'budget': 327680, 'max_idx_seen': max(idx_seen) if idx_seen else None}
T.log(res)
print(json.dumps(res, indent=1))
print('median delta armed-idle: %+.0f cycles; min delta %+d' % (res['armed']['median'] - res['idle']['median'], res['armed']['min'] - res['idle']['min']))
