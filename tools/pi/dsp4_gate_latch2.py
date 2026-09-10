#!/usr/bin/env python3
"""dsp4_gate_latch2.py — is the "frozen" gate state a firmware defect or an
injection that never stopped? (S22 gate 0, settling S21-7.)

S21-7 reported four FROZEN gate state words on one strip of every SIMD pair,
with the partner strip's hold counter decrementing. This runs the same
stimulus as dsp4_gate_latch.py and adds the two readings that tell the two
explanations apart:

  * `_scope_arm` / `_scope_idx` / `_scope_runs`, the scope's own state. A
    step injection (`mode 2`) drives the named slot on EVERY block for as
    long as ARM is set, and only the capture filling clears it. An armed
    scope 12 seconds after the run is a stimulus still being driven -- and
    a gate whose input is still driven is OPEN, not frozen: envelope at the
    driven level, gain and target at unity, and the hold count RELOADED
    every sample by the open branch, so constant BY DESIGN.
  * the same watch again after the host clears ARM by hand. If the four
    words move as soon as the stimulus stops, there was never a freeze.

Usage:  dsp4_gate_latch2.py [hold] [release]
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_scope import SCOPE_ARM, SCOPE_IDX, SCOPE_RUNS, SCOPE_AMP
from dsp4_conform import Part, STRIDE, GATE_ON, GATE_THR, GATE_ATT, \
    GATE_HOLD, GATE_REL, COMP_ON, TUBE_ON

GATE_RNG = 0x002D


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def s32(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


HOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
REL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

part = Part(1)
sc = part.sc
print('cfg 0x%08X  cfg2 0x%08X' % (sc.rd(0xE0EA), sc.rd(0xE0EB)))

for strip in (1, 2):
    b = (strip - 1) * STRIDE
    for off, w in ((GATE_ON, 1), (COMP_ON, 0), (TUBE_ON, 0),
                   (GATE_THR, f32(-40.0)), (GATE_ATT, f32(0.05)),
                   (GATE_REL, f32(REL)), (GATE_RNG, f32(40.0)),
                   (GATE_HOLD, f32(HOLD))):
        part.write(b + off, w, 0)
        time.sleep(0.02)
time.sleep(1.0)

NODE = {}
for strip in (1, 2):
    n = 'C1_GATE_%02d' % strip
    NODE[strip] = [sc.addr('_gate_envelope_' + n), sc.addr('_gate_gain_' + n),
                   sc.addr('_gate_gain_target_q_' + n),
                   sc.addr('_gate_hold_count_' + n)]


def show(tag):
    arm = sc.rd(SCOPE_ARM)
    idx = sc.rd(SCOPE_IDX)
    go = sc.peek(sc.addr('_scope_go')) if '_scope_go' in sc.sym else None
    runs = sc.rd(SCOPE_RUNS)
    print('  %-9s scope arm=%s idx=%s go=%s runs=%s' % (tag, arm, idx, go, runs))
    for strip in (1, 2):
        print('  %-9s   s%d [env gain tgt hold] = %s'
              % ('', strip, [s32(sc.peek(a)) for a in NODE[strip]]))


AMP = 0x0D3A17B5
print('amp = 0x%08X = %d' % (AMP, AMP))
print('quiet, before driving:')
show('quiet')
inj = sc.addr('_rx_slot_C1_IN_01')
sc.arm(sc.addr('_gate_gain_C1_GATE_01'), inj, AMP, 2)
try:
    sc.wait()
    print('  capture COMPLETED (arm cleared by the tap)')
except Exception as exc:
    print('  wait: %s' % exc)
print('after the step injection:')
for k in range(5):
    show('t=%4.1fs' % (k * 2.0))
    if k < 4:
        time.sleep(2.0)

print('now clearing _scope_arm by hand (the stimulus stops here):')
sc.d.write(SCOPE_ARM, 0)
time.sleep(0.05)
sc.d.write(SCOPE_ARM, 0)
time.sleep(0.05)
for k in range(5):
    show('t=%4.1fs' % (k * 2.0))
    if k < 4:
        time.sleep(2.0)
