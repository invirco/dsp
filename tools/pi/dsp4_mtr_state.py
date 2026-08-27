#!/usr/bin/env python3
"""xp_mtr.py — settled meter state, for diffing across builds.

WHY NOT A PER-SAMPLE TRACE. The obvious idea -- point the scope at
_mtr_peak and read 32 samples -- does not work for a per-BLOCK kernel:
_scope_record runs in the gather loop, after the whole chain has already
run, so it cannot see a block kernel's internal state evolving. The first
attempt at this probe returned two plausible words followed by
uninitialised buffer, which is what that looks like.

WHAT THIS DOES INSTEAD. Inject a constant amplitude, let the meter settle,
then peek its two state words. With a constant input A the peak sits in a
two-sample limit cycle (latch A, decay A*0.9995, latch A, ...) and a block
is an even number of samples, so the end-of-block value is deterministic;
the RMS converges to A^2. Both are fixed points of the arithmetic, so two
builds that compute the same thing must report the same words -- and a
build that clobbered a hoisted constant, or took the wrong branch, or ran
the loop a different number of times, would not.

Negative control: a second amplitude must move both readings.
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

sc = S.Scope(1); sc.check_chip()
POOL = sc.sym.get('_blk_pool')
INJ = POOL if POOL else sc.sym['_rx_slot_C1_IN_01']
PEAK = sc.sym['_mtr_peak_C1_MTR_01']
RMS = sc.sym['_mtr_rms_C1_MTR_01']

def fl(v): return struct.unpack('<f', struct.pack('<I', (v or 0) & 0xFFFFFFFF))[0]
def peek(a):
    """Read until two consecutive reads agree. The diag link intermittently
    answers 0xFFFFFFFF for a peek, and a single read cannot tell that from a
    real value -- an earlier run of this probe reported the peak as NaN twice
    for exactly that reason."""
    last = None
    for _ in range(24):
        try:
            v = sc.d.peek(a)
        except Exception:
            time.sleep(0.05); last = None; continue
        if v == 0xFFFFFFFF:
            last = None; time.sleep(0.03); continue
        if v == last:
            return v
        last = v
        time.sleep(0.03)
    return None

def settle(amp, rounds=60):
    # Inject through the scope's step mode; the recorded source is irrelevant
    # here, the injection is what matters.
    for _ in range(rounds):
        sc.arm(INJ, INJ, amp, 2)
        sc.wait()
    return peek(PEAK), peek(RMS)

print('build: %s' % ('BLOCK KERNELS' if POOL else 'per-sample'))
for amp in (0x40000000, 0x40000000, 0x20000000):
    pk, rm = settle(amp)
    print('amp=0x%08X  peak=%s (%.7g)  rms=%s (%.7g)'
          % (amp, ('%08X' % pk) if pk is not None else 'UNREADABLE', fl(pk),
             ('%08X' % rm) if rm is not None else 'UNREADABLE', fl(rm)))
