#!/usr/bin/env python3
"""s124_lat.py <symdir> [n] -- S124: cell write -> sound, measured.

The click is its OWN clock. Its envelope is exp(-n/tau) with tau known from
the generator, so the peak the capture opens on says how long the click had
ALREADY been running when the capture started. Subtract that from the host's
own perf_counter interval between the trigger write and the ARM write and
what is left is the whole path: SPI write -> kernel -> block -> TX slot.
"""
import json, math, statistics, struct, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _A[0]
N = int(_A[1]) if len(_A) > 1 else 20
OUT = _A[2] if len(_A) > 2 else '/tmp/s124-lat.json'
BASE = 2175
TRIG, SAMPLE, LEVEL, TEST_ON, TEST_LEVEL, BUSY = (BASE + i for i in range(6))
FS, TAU_MS, PEAK = 48000.0, 2.5, 0.94
TAU = TAU_MS / 1000.0 * FS          # 120 samples

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

c2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
c2.d.resync(); c2.check_chip()
c1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
c1.d.resync(); c1.check_chip()

def prearm(sc, sym):
    sc.d.write(S.SCOPE_ARM, 0); time.sleep(0.01)
    sc.wr(S.SCOPE_SRC, sc.addr(sym)); sc.wr(S.SCOPE_INJ, 0)
    sc.wr(S.SCOPE_AMP, 0); sc.wr(S.SCOPE_MODE, 1)

def collect(sc, n=1024):
    sc.wait(timeout=8.0)
    return [s32(w) / float(1 << 28) for w in sc.fetch(n)]

def env_offset(x):
    """Samples the click had already run when the capture opened.

    Fit log|half-cycle peaks| against -n/TAU; the intercept is the offset.
    Uses only the first 5 ms of the capture, where the model is clean.
    """
    pk = []
    win = int(0.005 * FS)
    i = 1
    while i < min(len(x) - 1, win):
        if abs(x[i]) > abs(x[i-1]) and abs(x[i]) >= abs(x[i+1]) and abs(x[i]) > 1e-3:
            pk.append((i, abs(x[i])))
            i += 4
        else:
            i += 1
    if len(pk) < 5: return None, len(pk)
    # log(a) = log(PEAK) - (i + n0)/TAU  ->  n0 = -TAU*(log(a)-log(PEAK)) - i
    ns = [-TAU * (math.log(a) - math.log(PEAK)) - i for i, a in pk]
    return statistics.median(ns), len(pk)

R = {'runs': []}
c2.d.link.write(LEVEL, f32(1.0), 0); time.sleep(0.05)
c2.d.link.write(SAMPLE, 1, 0); time.sleep(0.1)
print('=== S124-e  CELL WRITE -> SOUND, n=%d, the click as its own clock' % N)
for k in range(N):
    prearm(c2, '_tx_out_slot_C2_SPKR_OUT')
    t0 = time.perf_counter()
    c2.d.link.write(TRIG, 1, 0)
    t1 = time.perf_counter()
    c2.d.write(S.SCOPE_ARM, 1)
    t2 = time.perf_counter()
    x = collect(c2)
    n0, npk = env_offset(x)
    if n0 is None:
        print('  run %2d: no usable envelope (%d peaks)' % (k, npk)); continue
    host_ms = (t1 - t0) * 1000.0
    to_arm_ms = (t2 - t0) * 1000.0
    already_ms = n0 / FS * 1000.0
    lat_ms = to_arm_ms - already_ms
    R['runs'].append({'host_write_ms': host_ms, 'trig_to_arm_ms': to_arm_ms,
                      'click_age_at_capture_ms': already_ms,
                      'write_to_sound_ms': lat_ms, 'peaks': npk,
                      'capture_peak': max(abs(v) for v in x)})
    time.sleep(0.35)

def col(k): return sorted(r[k] for r in R['runs'])
def sm(k):
    v = col(k)
    return {'n': len(v), 'min': v[0], 'median': v[len(v)//2], 'max': v[-1],
            'mean': statistics.fmean(v),
            'sd': (statistics.stdev(v) if len(v) > 1 else 0.0)}
for k in ('host_write_ms', 'trig_to_arm_ms', 'click_age_at_capture_ms', 'write_to_sound_ms'):
    R[k] = sm(k)
    print('  %-26s n=%2d  min %6.3f  median %6.3f  mean %6.3f  sd %5.3f  max %6.3f ms'
          % (k, R[k]['n'], R[k]['min'], R[k]['median'], R[k]['mean'], R[k]['sd'], R[k]['max']))

# ---- the acoustic leg: the same trigger, read on the MEMS lane
print('=== the acoustic leg, on the MEMS lane')
prearm(c1, '_buf_C1_XIN_MEMS')
c1.d.write(S.SCOPE_ARM, 1)
q = collect(c1)
floor_pk = max(abs(v) for v in q)
thr = max(4.0 * floor_pk, 0.01)
print('  MEMS floor peak %.6f -> onset threshold %.6f' % (floor_pk, thr))
ac = []
for k in range(6):
    prearm(c1, '_buf_C1_XIN_MEMS')
    t0 = time.perf_counter()
    c2.d.link.write(TRIG, 1, 0)
    c1.d.write(S.SCOPE_ARM, 1)
    t2 = time.perf_counter()
    y = collect(c1)
    oi = next((i for i, v in enumerate(y) if abs(v) > thr), None)
    if oi is None:
        print('  run %d: nothing above threshold' % k); continue
    ac.append({'trig_to_arm_ms': (t2 - t0) * 1000.0, 'onset_idx': oi,
               'onset_ms': oi / FS * 1000.0,
               'write_to_air_ms': (t2 - t0) * 1000.0 + oi / FS * 1000.0,
               'peak': max(abs(v) for v in y)})
    print('  run %d: onset sample %3d (%.2f ms after the capture opened) peak %.5f'
          % (k, oi, oi / FS * 1000.0, ac[-1]['peak']))
    time.sleep(0.4)
R['acoustic'] = ac
if ac:
    v = sorted(a['write_to_air_ms'] for a in ac)
    R['write_to_air_ms'] = {'n': len(v), 'min': v[0], 'median': v[len(v)//2], 'max': v[-1]}
    print('  host write -> MEMS hears it: min %.2f  median %.2f  max %.2f ms'
          % (v[0], v[len(v)//2], v[-1]))
c2.d.link.write(SAMPLE, 1, 0); time.sleep(0.05)
c2.d.link.write(TEST_ON, 0, 0); time.sleep(0.05)
json.dump(R, open(OUT, 'w'), indent=1)
print('written', OUT)
