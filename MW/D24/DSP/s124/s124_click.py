#!/usr/bin/env python3
"""s124_click.py <symdir> -- S124: catch a SINGLE triggered click in the
speaker slot, and in the MEMS lane, and time it.

The scope's own arm() cannot be used for this: it takes tens of milliseconds
and a click is 17.3, so by the time arm() returns the click is over. Here the
scope's source/mode registers are set up ONCE and verified, and then the only
two writes between the trigger and the start of the capture are the trigger
itself and ARM=1 -- about 0.7 ms of host link, measured. So the capture starts
at the top of the click and the sample index where sound appears is the whole
path from the host's write to the word on the TX slot.
"""
import json, math, statistics, struct, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _A[0]
OUT = _A[1] if len(_A) > 1 else '/tmp/s124-click.json'
BASE = 2175
TRIG, SAMPLE, LEVEL, TEST_ON, TEST_LEVEL, BUSY = (BASE + i for i in range(6))

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

c2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
c2.d.resync(); c2.check_chip()
c1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
c1.d.resync(); c1.check_chip()
R = {}

def prearm(sc, sym):
    sc.d.write(S.SCOPE_ARM, 0); time.sleep(0.01)
    sc.wr(S.SCOPE_SRC, sc.addr(sym)); sc.wr(S.SCOPE_INJ, 0)
    sc.wr(S.SCOPE_AMP, 0); sc.wr(S.SCOPE_MODE, 1)
    return sc.rd(S.SCOPE_RUNS)

def collect(sc, n=1024):
    sc.wait(timeout=8.0)
    return [s32(w) / float(1 << 28) for w in sc.fetch(n)]

def onset(x, thr=1e-4):
    for i, v in enumerate(x):
        if abs(v) > thr: return i
    return None

def tail_zero(x, thr=1e-9):
    last = None
    for i, v in enumerate(x):
        if abs(v) > thr: last = i
    return last

def stats(x):
    nz = sum(1 for v in x if v != 0.0)
    pk = max(abs(v) for v in x) if x else 0.0
    rms = math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0
    return {'n': len(x), 'nonzero': nz, 'peak': pk,
            'rms_dbfs': (20 * math.log10(rms) if rms > 0 else None)}

def half_cycle_hz(x, fs=48000.0):
    xs, i0 = x, onset(x)
    if i0 is None: return None
    seg = [v for v in xs[i0:i0 + 400] if True]
    idx = [i for i in range(1, len(seg)) if (seg[i-1] < 0) != (seg[i] < 0)]
    if len(idx) < 4: return None
    return fs / ((idx[-1] - idx[0]) / float(len(idx) - 1) * 2.0)

# ---------------------------------------------------------------- single click in the slot
print('=== S124-d  A SINGLE TRIGGERED CLICK, CAUGHT IN THE SPEAKER SLOT')
c2.d.link.write(LEVEL, f32(1.0), 0); time.sleep(0.05)
for smp, name, words in ((1, '2500 Hz tau 2.5 ms', 829),
                         (2, '3000 Hz tau 1.8 ms', 597),
                         (3, '1500 Hz tau 3.0 ms', 995)):
    c2.d.link.write(SAMPLE, smp, 0); time.sleep(0.1)
    runs = prearm(c2, '_tx_out_slot_C2_SPKR_OUT')
    t0 = time.perf_counter()
    c2.d.link.write(TRIG, 1, 0)
    c2.d.write(S.SCOPE_ARM, 1)
    t1 = time.perf_counter()
    x = collect(c2)
    st = stats(x)
    st.update({'model': name, 'expect_words': words, 'sample': smp,
               'onset_idx': onset(x), 'last_nonzero_idx': tail_zero(x),
               'hz': half_cycle_hz(x), 'arm_pair_ms': (t1 - t0) * 1000.0})
    if st['onset_idx'] is not None and st['last_nonzero_idx'] is not None:
        st['length_samples'] = st['last_nonzero_idx'] - st['onset_idx'] + 1
        st['length_ms'] = st['length_samples'] / 48.0
    R['click_%d' % smp] = st
    print('  sample %d (%s)' % (smp, name))
    print('     trig+arm %.3f ms   onset at sample %s (%.2f ms)   last non-zero %s'
          % (st['arm_pair_ms'], st['onset_idx'],
             (st['onset_idx'] or 0) / 48.0, st['last_nonzero_idx']))
    print('     length %s samples (%s ms, stored %d = %.2f ms)  peak %.5f  %.0f Hz'
          % (st.get('length_samples'), ('%.2f' % st['length_ms']) if 'length_ms' in st else '?',
             words, words / 48.0, st['peak'], st['hz'] or 0))
    time.sleep(0.4)

# ---------------------------------------------------------------- the same click in the air
print('=== S124-f  THE SAME CLICK, IN THE AIR, ON THE MEMS LANE')
c2.d.link.write(SAMPLE, 1, 0); time.sleep(0.1)
runs = prearm(c1, '_buf_C1_XIN_MEMS')
c1.d.write(S.SCOPE_ARM, 1)
quiet = collect(c1)
R['mems_quiet'] = stats(quiet)
print('  silent  : rms %.2f dBFS peak %.6f' % (R['mems_quiet']['rms_dbfs'] or -999,
                                               R['mems_quiet']['peak']))
runs = prearm(c1, '_buf_C1_XIN_MEMS')
t0 = time.perf_counter()
c2.d.link.write(TRIG, 1, 0)
c1.d.write(S.SCOPE_ARM, 1)
t1 = time.perf_counter()
y = collect(c1)
R['mems_click'] = stats(y)
R['mems_click'].update({'onset_idx': onset(y, 3e-4), 'hz': half_cycle_hz(y),
                        'trig_to_arm_ms': (t1 - t0) * 1000.0})
print('  clicked : rms %.2f dBFS peak %.6f  onset sample %s (%.2f ms)  %.0f Hz'
      % (R['mems_click']['rms_dbfs'] or -999, R['mems_click']['peak'],
         R['mems_click']['onset_idx'],
         (R['mems_click']['onset_idx'] or 0) / 48.0, R['mems_click']['hz'] or 0))
time.sleep(0.5)
runs = prearm(c1, '_buf_C1_XIN_MEMS')
c1.d.write(S.SCOPE_ARM, 1)
q2 = collect(c1)
R['mems_quiet_after'] = stats(q2)
print('  silent again: rms %.2f dBFS peak %.6f'
      % (R['mems_quiet_after']['rms_dbfs'] or -999, R['mems_quiet_after']['peak']))

# hand the node back at rest
c2.d.link.write(TEST_ON, 0, 0); time.sleep(0.05)
c2.d.link.write(TEST_LEVEL, f32(0.0), 0); time.sleep(0.05)
c2.d.link.write(SAMPLE, 1, 0); time.sleep(0.05)
c2.d.link.write(LEVEL, f32(1.0), 0); time.sleep(0.2)
R['handback'] = {'trig': c2.rd(TRIG), 'test_on': c2.rd(TEST_ON), 'busy': c2.rd(BUSY)}
print('=== handback: trig %s test_on %s busy %s' % (R['handback']['trig'],
      R['handback']['test_on'], R['handback']['busy']))
json.dump(R, open(OUT, 'w'), indent=1)
print('written', OUT)
