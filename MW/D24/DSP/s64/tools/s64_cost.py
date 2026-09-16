#!/usr/bin/env python3
"""s64_cost.py [rounds] [tag] — chip-2 cycles per block pass with the RTA off vs on, interleaved on one boot, same signal
(whatever the unit is carrying). `_proc_cyc` is exact per pass (TCOUNT); `_diag_blk_overrun` by delta per arm; the
budget is 327,680 cycles (block 16 at 983.04 MHz). Each arm: write RTA_ON, settle 0.2 s, sample for 0.4 s."""
import json, statistics as st, sys, time
import s64lib as L
T = L.T
R = T.Rig(__import__('os').environ['SYMDIR'] + '/s64_cost.jsonl')
A = L.Rta(R)
sc = A.sc
P, O = sc.sym['_proc_cyc'], sc.sym['_diag_blk_overrun']
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
TAG = sys.argv[2] if len(sys.argv) > 2 else ''
arms = {0: [], 1: []}
ovr = {0: 0, 1: 0}
secs = {0: 0.0, 1: 0.0}
for rnd in range(ROUNDS):
    for on in (0, 1):
        A.wr(L.RTA_ON, on)
        time.sleep(0.2)
        o0 = A.peek(O); t0 = time.time()
        while time.time() - t0 < 0.4:
            arms[on].append(A.peek(P))
        secs[on] += time.time() - t0
        ovr[on] += (A.peek(O) - o0) & 0xFFFFFFFF


def summ(x):
    x = sorted(x)
    return {'n': len(x), 'min': x[0], 'p10': x[len(x) // 10], 'median': st.median(x), 'p90': x[9 * len(x) // 10],
            'max': x[-1], 'mean': round(st.mean(x), 1)}


B = 327680
res = {'ev': 'cost', 'tag': TAG, 'off': summ(arms[0]), 'on': summ(arms[1]), 'overruns_off': ovr[0], 'overruns_on': ovr[1],
       'seconds_off': round(secs[0], 1), 'seconds_on': round(secs[1], 1), 'budget': B}
res['delta_median'] = res['on']['median'] - res['off']['median']
res['pct_off'] = round(100.0 * res['off']['median'] / B, 2)
res['pct_on'] = round(100.0 * res['on']['median'] / B, 2)
res['delta_pct'] = round(100.0 * res['delta_median'] / B, 2)
T.log(res)
print(json.dumps(res, indent=1))
