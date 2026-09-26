#!/usr/bin/env python3
"""s124_cap.py <symdir> -- what the HAPTIC node costs chip 2, measured, as a
WITHIN-BOOT difference: the same image, the same graph, the same boot, with the
node idle / sounding a test tone / sounding clicks back to back.

A cross-boot capacity row cannot see this: the cross-boot spread on code that
did not change at all is about 2,000 cycles a block and the static count for a
sounding block is 265. A within-boot difference can.
"""
import json, statistics, struct, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _A[0]
OUT = _A[1] if len(_A) > 1 else '/tmp/s124-cap.json'
BASE = 2175
TRIG, SAMPLE, LEVEL, TEST_ON, TEST_LEVEL, BUSY = (BASE + i for i in range(6))
PROC, PROCMAX, PROCPASS = '_proc_cyc', '_proc_cyc_max', '_proc_passes'

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]

sc = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc.d.resync(); sc.check_chip()
A = {k: sc.addr(k) for k in (PROC, PROCMAX, PROCPASS)}
print('  symbols: ' + '  '.join('%s 0x%06X' % (k, v) for k, v in A.items()))
BUDGET = 327680

def cyc(n=25):
    v = []
    for _ in range(n):
        try:
            v.append(sc.peek(A[PROC]))
        except IOError:
            pass
        time.sleep(0.01)
    return v

def row(label, n=25):
    v = cyc(n)
    med = statistics.median(v)
    print('  %-22s n=%2d  median %7d  mean %8.1f  min %7d  max %7d  = %6.3f %% of budget'
          % (label, len(v), med, statistics.fmean(v), min(v), max(v),
             100.0 * med / BUDGET))
    return {'label': label, 'n': len(v), 'median': med, 'mean': statistics.fmean(v),
            'min': min(v), 'max': max(v), 'pct': 100.0 * med / BUDGET,
            'samples': v}

R = {'budget_cycles': BUDGET}
print('=== S124-g  THE HAPTIC NODE\'S COST, WITHIN ONE BOOT')
sc.d.link.write(TEST_ON, 0, 0); time.sleep(0.3)
R['idle'] = row('idle (digital zero)')
sc.d.link.write(TEST_LEVEL, f32(0.5), 0); time.sleep(0.05)
sc.d.link.write(TEST_ON, 1, 0); time.sleep(0.3)
R['tone'] = row('test tone sounding')
sc.d.link.write(TEST_ON, 0, 0); time.sleep(0.5)
R['idle2'] = row('idle again')
# clicks: retrigger between reads, in ONE process, so the node is sounding
sc.d.link.write(SAMPLE, 3, 0); time.sleep(0.1)   # 995 words = 20.7 ms, the longest
v = []
for _ in range(25):
    sc.d.link.write(TRIG, 1, 0)
    try:
        v.append(sc.peek(A[PROC]))
    except IOError:
        pass
    time.sleep(0.008)
sc.d.link.write(SAMPLE, 1, 0)
med = statistics.median(v)
R['click'] = {'label': 'clicks sounding', 'n': len(v), 'median': med,
              'mean': statistics.fmean(v), 'min': min(v), 'max': max(v),
              'pct': 100.0 * med / BUDGET, 'samples': v}
print('  %-22s n=%2d  median %7d  mean %8.1f  min %7d  max %7d  = %6.3f %% of budget'
      % ('clicks sounding', len(v), med, statistics.fmean(v), min(v), max(v),
         100.0 * med / BUDGET))
time.sleep(0.5)
R['idle3'] = row('idle, third reading')

base = statistics.median(R['idle']['samples'] + R['idle2']['samples'] + R['idle3']['samples'])
R['idle_pooled_median'] = base
for k, static in (('tone', 265), ('click', 265)):
    d = R[k]['median'] - base
    R[k]['delta_vs_idle'] = d
    R[k]['static_count'] = static
    print('  %-22s sounding minus idle = %+d cycles/block  (static count %d, %+.3f %% of budget)'
          % (k, d, static, 100.0 * d / BUDGET))
print('  pooled idle median %d cycles/block = %.3f %% of a %d-cycle budget'
      % (base, 100.0 * base / BUDGET, BUDGET))
try:
    R['proc_cyc_max'] = sc.peek(A[PROCMAX])
    R['proc_passes'] = sc.peek(A[PROCPASS])
    print('  _proc_cyc_max %d (%.3f %%)  over %s passes'
          % (R['proc_cyc_max'], 100.0 * R['proc_cyc_max'] / BUDGET, R['proc_passes']))
except IOError as e:
    print('  proc_cyc_max unread:', e)
for k in ('DIAG_BLK_OVERRUN', 'DIAG_FRAME_COUNT'):
    pass
sc.d.link.write(TEST_ON, 0, 0); time.sleep(0.05)
sc.d.link.write(TEST_LEVEL, f32(0.0), 0); time.sleep(0.05)
json.dump(R, open(OUT, 'w'), indent=1)
print('written', OUT)
