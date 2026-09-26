#!/usr/bin/env python3
"""s124_haptic.py <symdir> -- S124: the S122 haptic path, proved on the part.

Every item here is judged by the part: the speaker slot's own words, the MEMS
lane's own words, and the host link's own clock. Nothing needs a hand and
nothing needs an ear.
"""
import json, math, statistics, struct, sys, threading, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _A[0]
OUT = _A[1] if len(_A) > 1 else '/tmp/s124-haptic.json'
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

def wr(addr, word, ramp=0):
    c2.d.link.write(addr, word & 0xFFFFFFFF, ramp)

def cap(sc, sym, n=1024):
    a = sc.addr(sym)
    sc.arm(a, inj=0, amp=0, mode=1)
    sc.wait(timeout=8.0)
    return [s32(w) / float(1 << 28) for w in sc.fetch(n)]

def stats(x):
    nz = sum(1 for v in x if v != 0.0)
    pk = max(abs(v) for v in x) if x else 0.0
    rms = math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0
    return {'n': len(x), 'nonzero': nz, 'peak': pk, 'rms': rms,
            'rms_dbfs': (20 * math.log10(rms) if rms > 0 else None),
            'peak_dbfs': (20 * math.log10(pk) if pk > 0 else None)}

def zero_crossing_hz(x, fs=48000.0):
    """Crude but honest: half-cycles between sign changes."""
    xs = [v for v in x if v != 0.0]
    if len(xs) < 8: return None
    idx = [i for i in range(1, len(xs)) if (xs[i - 1] < 0) != (xs[i] < 0)]
    if len(idx) < 3: return None
    per = (idx[-1] - idx[0]) / float(len(idx) - 1) * 2.0
    return fs / per

# ---------------------------------------------------------------- 1. host write time
print('=== S124-a  HOST WRITE TIME (the unmeasured half of the latency)')
t = []
for _ in range(60):
    t0 = time.perf_counter(); wr(SAMPLE, 1); t1 = time.perf_counter()
    t.append((t1 - t0) * 1000.0)
t.sort()
R['host_write_ms'] = {'n': len(t), 'min': t[0], 'median': t[len(t)//2],
                      'p95': t[int(0.95*len(t))], 'max': t[-1],
                      'mean': statistics.fmean(t)}
print('  link.write  n=%d  min %.3f  median %.3f  p95 %.3f  max %.3f ms'
      % (len(t), t[0], t[len(t)//2], t[int(0.95*len(t))], t[-1]))

# ---------------------------------------------------------------- 2. the trigger is consumed
print('=== S124-b  THE TRIGGER WORD IS CONSUMED BY THE KERNEL')
wr(SAMPLE, 1); time.sleep(0.05)
wr(LEVEL, f32(1.0)); time.sleep(0.05)
t0 = time.perf_counter(); wr(TRIG, 1); t1 = time.perf_counter()
busy_seen, trig_after = None, None
for _ in range(40):
    b = c2.rd(BUSY)
    if busy_seen is None or b: busy_seen = b
    if b: break
trig_after = c2.rd(TRIG)
time.sleep(0.2)
R['trigger'] = {'write_ms': (t1 - t0) * 1000.0, 'busy_first_read': busy_seen,
                'trig_reads_back': trig_after, 'busy_after_settle': c2.rd(BUSY)}
print('  trig write %.3f ms; busy first read %s; trig reads back %s; busy after 200 ms %s'
      % (R['trigger']['write_ms'], busy_seen, trig_after, R['trigger']['busy_after_settle']))

# ---------------------------------------------------------------- 3. the test tone
print('=== S124-c  THE TEST TONE REACHES THE SPEAKER SLOT')
wr(TEST_LEVEL, f32(0.5)); time.sleep(0.1)
wr(TEST_ON, 1); time.sleep(0.2)
tone = cap(c2, '_tx_out_slot_C2_SPKR_OUT')
R['tone_on'] = stats(tone); R['tone_on']['hz'] = zero_crossing_hz(tone)
print('  tone ON  : %(nonzero)d/%(n)d non-zero  peak %(peak).5f  rms %(rms_dbfs).2f dBFS'
      % R['tone_on'], ' hz %.1f' % (R['tone_on']['hz'] or 0))
wr(TEST_ON, 0); time.sleep(0.3)
off = cap(c2, '_tx_out_slot_C2_SPKR_OUT')
R['tone_off'] = stats(off)
print('  tone OFF : %(nonzero)d/%(n)d non-zero  peak %(peak).8f' % R['tone_off'])

# ---------------------------------------------------------------- 4. clicks, sustained
print('=== S124-d  A TRIGGERED CLICK REACHES THE SPEAKER SLOT')
stop = threading.Event()
def retrigger():
    while not stop.is_set():
        wr(TRIG, 1)
        time.sleep(0.004)
for smp, name in ((1, '2500 Hz tau 2.5 ms'), (2, '3000 Hz tau 1.8 ms'), (3, '1500 Hz tau 3.0 ms')):
    wr(SAMPLE, smp); time.sleep(0.1)
    stop.clear(); th = threading.Thread(target=retrigger, daemon=True); th.start()
    time.sleep(0.2)
    x = cap(c2, '_tx_out_slot_C2_SPKR_OUT')
    stop.set(); th.join()
    st = stats(x); st['hz'] = zero_crossing_hz(x); st['model'] = name
    R['click_%d' % smp] = st
    print('  sample %d (%s): %d/%d non-zero  peak %.5f  rms %.2f dBFS  %.0f Hz'
          % (smp, name, st['nonzero'], st['n'], st['peak'], st['rms_dbfs'] or -999,
             st['hz'] or 0))
    time.sleep(0.4)

# ---------------------------------------------------------------- 5. the slot at rest
print('=== S124-e  THE SLOT AT REST, WITH THE MIXER DRIVEN HARD')
time.sleep(0.5)
for sym in ('_tx_out_slot_C2_SPKR_OUT', '_blk_C2_SPKR_OUT', '_blk_C2_HPT_01'):
    x = cap(c2, sym)
    R['rest_' + sym] = stats(x)
    print('  %-28s %d/%d non-zero  peak %.8f' % (sym, R['rest_' + sym]['nonzero'],
                                                 R['rest_' + sym]['n'], R['rest_' + sym]['peak']))
for sym in ('_blk_C2_MON', '_blk_C2_MON_DLY', '_tx_out_slot_C2_MAIN_OUT_01'):
    x = cap(c2, sym)
    R['drive_' + sym] = stats(x)
    print('  %-28s %d/%d non-zero  peak %.5f  rms %.2f dBFS (the mixer, driven)'
          % (sym, R['drive_' + sym]['nonzero'], R['drive_' + sym]['n'],
             R['drive_' + sym]['peak'], R['drive_' + sym]['rms_dbfs'] or -999))

# ---------------------------------------------------------------- 6. the MEMS lane hears it
print('=== S124-f  THE MEMS LANE HEARS THE SPEAKER (acoustic, no hands)')
quiet = cap(c1, '_buf_C1_XIN_MEMS')
R['mems_quiet'] = stats(quiet)
print('  speaker silent : rms %.2f dBFS  peak %.6f'
      % (R['mems_quiet']['rms_dbfs'] or -999, R['mems_quiet']['peak']))
wr(TEST_LEVEL, f32(0.5)); time.sleep(0.05); wr(TEST_ON, 1); time.sleep(0.5)
tone_m = cap(c1, '_buf_C1_XIN_MEMS')
R['mems_tone'] = stats(tone_m); R['mems_tone']['hz'] = zero_crossing_hz(tone_m)
print('  test tone on   : rms %.2f dBFS  peak %.6f  %.0f Hz'
      % (R['mems_tone']['rms_dbfs'] or -999, R['mems_tone']['peak'],
         R['mems_tone']['hz'] or 0))
wr(TEST_ON, 0); time.sleep(0.4)
stop.clear(); wr(SAMPLE, 1); time.sleep(0.05)
th = threading.Thread(target=retrigger, daemon=True); th.start()
time.sleep(0.3)
click_m = cap(c1, '_buf_C1_XIN_MEMS')
stop.set(); th.join()
R['mems_click'] = stats(click_m); R['mems_click']['hz'] = zero_crossing_hz(click_m)
print('  clicks playing : rms %.2f dBFS  peak %.6f  %.0f Hz'
      % (R['mems_click']['rms_dbfs'] or -999, R['mems_click']['peak'],
         R['mems_click']['hz'] or 0))
time.sleep(0.4)
quiet2 = cap(c1, '_buf_C1_XIN_MEMS')
R['mems_quiet_after'] = stats(quiet2)
print('  silent again   : rms %.2f dBFS  peak %.6f'
      % (R['mems_quiet_after']['rms_dbfs'] or -999, R['mems_quiet_after']['peak']))

# ---------------------------------------------------------------- hand back
wr(TEST_ON, 0); time.sleep(0.05)
wr(TEST_LEVEL, f32(0.0)); time.sleep(0.05)
wr(SAMPLE, 1); time.sleep(0.05)
wr(LEVEL, f32(1.0)); time.sleep(0.2)
R['handback'] = {'trig': c2.rd(TRIG), 'test_on': c2.rd(TEST_ON),
                 'busy': c2.rd(BUSY)}
print('=== handback: trig %s test_on %s busy %s'
      % (R['handback']['trig'], R['handback']['test_on'], R['handback']['busy']))
json.dump(R, open(OUT, 'w'), indent=1)
print('written', OUT)
