#!/usr/bin/env python3
"""s65_cost.py TAG [rounds] — chip-1 cycles per block pass in named arms, interleaved on one boot. `_proc_cyc` is exact
per pass (TCOUNT); `_diag_blk_overrun` by delta per arm; the budget is 327,680 cycles (block 16). Each arm: set the
cells, settle 0.3 s, sample for 0.5 s.
Arms on the S65 pair: none_off (nothing cued, RTA off: the cue bus costs its hooks + the source copy), none_on (RTA on),
pfl1 (strip 6 PFL, RTA on), afl_all (every strip of the product AFL, RTA on).
On a pair without the cue (the base pair, BASE=1 in env) only the 'base' arm runs."""
import json, os, statistics as st, sys, time
TAG = sys.argv[1] if len(sys.argv) > 1 else ''
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
import s65lib as L
T = L.T
R = T.Rig(os.environ['SYMDIR'] + '/s65_cost.jsonl')
sc = R.sc
P, O = sc.sym['_proc_cyc'], sc.sym['_diag_blk_overrun']
BASE_ONLY = os.environ.get('BASE') == '1'
NSTRIPS = int(os.environ.get('NSTRIPS', '24'))
if not BASE_ONLY:
    C = L.Cue(R)


def arm(name):
    if BASE_ONLY:
        return
    C.clear()
    C.wr(L.MODE, 0)
    if name == 'none_off':
        C.wr(L.RTA_ON, 0)
    elif name == 'none_on':
        C.wr(L.RTA_ON, 1)
    elif name == 'pfl1':
        C.wr(L.RTA_ON, 1); C.wr(L.SEL(6), 1)
    elif name == 'afl_all':
        C.wr(L.RTA_ON, 1); C.wr(L.MODE, 1)
        for s in range(1, NSTRIPS + 1):
            C.wr(L.SEL(s), 1)


ARMS = ['base'] if BASE_ONLY else ['none_off', 'none_on', 'pfl1', 'afl_all']
data = {a: [] for a in ARMS}
ovr = {a: 0 for a in ARMS}
secs = {a: 0.0 for a in ARMS}
active = {a: [] for a in ARMS}
for rnd in range(ROUNDS):
    for a in ARMS:
        arm(a)
        time.sleep(0.3)
        o0 = R._retry(sc.peek, O); t0 = time.time()
        while time.time() - t0 < 0.5:
            data[a].append(R._retry(sc.peek, P))
        secs[a] += time.time() - t0
        ovr[a] += (R._retry(sc.peek, O) - o0) & 0xFFFFFFFF
        if not BASE_ONLY:
            active[a].append(C.rd(L.ACTIVE))
if not BASE_ONLY:
    C.clear(); C.wr(L.RTA_ON, 0); C.wr(L.MODE, 0)
B = 327680


def summ(x):
    x = sorted(x)
    return {'n': len(x), 'min': x[0], 'p10': x[len(x) // 10], 'median': st.median(x), 'p90': x[9 * len(x) // 10],
            'max': x[-1]}


res = {'ev': 'cost', 'tag': TAG, 'budget': B, 'arms': {}}
for a in ARMS:
    s = summ(data[a])
    res['arms'][a] = dict(s, pct=round(100.0 * s['median'] / B, 2), pct_max=round(100.0 * s['max'] / B, 2),
                          overruns=ovr[a], seconds=round(secs[a], 1), active=sorted(set(active[a])))
T.log(res)
print(json.dumps(res, indent=1))
