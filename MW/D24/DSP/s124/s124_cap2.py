#!/usr/bin/env python3
"""s124_cap2.py <symdir> [pairs] -- the haptic node's cost as a PAIRED
difference, tone off / tone on interleaved, so the ~300 cycle drift between
one reading block and the next cancels instead of swamping the 265 the static
count predicts."""
import json, statistics, struct, sys, time
_A = sys.argv[1:]; sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
SYMDIR = _A[0]; PAIRS = int(_A[1]) if len(_A) > 1 else 40
OUT = _A[2] if len(_A) > 2 else '/tmp/s124-cap2.json'
BASE = 2175; TRIG, SAMPLE, LEVEL, TEST_ON, TEST_LEVEL = (BASE + i for i in range(5))
def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
sc = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc.d.resync(); sc.check_chip()
A = sc.addr('_proc_cyc'); BUDGET = 327680
sc.d.link.write(TEST_LEVEL, f32(0.5), 0); time.sleep(0.1)
def read(n=3):
    v = []
    for _ in range(n):
        try: v.append(sc.peek(A))
        except IOError: pass
        time.sleep(0.004)
    return statistics.median(v) if v else None
d = []
for k in range(PAIRS):
    sc.d.link.write(TEST_ON, 0, 0); time.sleep(0.06); off = read()
    sc.d.link.write(TEST_ON, 1, 0); time.sleep(0.06); on = read()
    if off is not None and on is not None: d.append(on - off)
sc.d.link.write(TEST_ON, 0, 0); time.sleep(0.05)
sc.d.link.write(TEST_LEVEL, f32(0.0), 0)
d.sort()
R = {'pairs': len(d), 'median': statistics.median(d), 'mean': statistics.fmean(d),
     'sd': statistics.stdev(d) if len(d) > 1 else 0.0, 'min': d[0], 'max': d[-1],
     'p25': d[len(d)//4], 'p75': d[3*len(d)//4], 'budget': BUDGET, 'deltas': d}
print('  PAIRED tone-on minus tone-off, n=%d pairs' % len(d))
print('    median %+d   mean %+.1f   sd %.1f   IQR %+d..%+d   min %+d  max %+d cycles/block'
      % (R['median'], R['mean'], R['sd'], R['p25'], R['p75'], R['min'], R['max']))
print('    median = %.4f %% of a %d-cycle budget   (static count 265 = %.4f %%)'
      % (100.0 * R['median'] / BUDGET, BUDGET, 100.0 * 265 / BUDGET))
json.dump(R, open(OUT, 'w'), indent=1)
print('written', OUT)
