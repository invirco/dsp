#!/usr/bin/env python3
"""dsp4_gate_latch.py — does strip 1's GATE return to rest under DSP4_SIMD_DYN?

S21. goldnode's GATE arm declines a verdict on `shipping.config.s20` because
the gate is not closed when the state is read, and a four-way bisect puts it
on DSP4_SIMD_DYN alone: with that switch off and the other four unchanged the
same arm reads 64 of 64 bit-exact. This asks the question directly, and it
asks it of the PAIR rather than of one strip, because the paired driver runs
strips 1 and 2 in one instruction stream and takes a scalar fallback unless
BOTH channels are on.

  * writes the gate parameters goldnode writes, to strip 1 and to strip 2;
  * drives the strip through the scope's own step injection, then stops;
  * watches both strips' envelope, gain and target for twelve seconds.

An envelope that holds the driven level with nothing driving it is the
defect. An envelope that falls says the gate closes and goldnode's rest wait
was the problem.
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_conform import Part, STRIDE, GATE_ON, GATE_THR, GATE_ATT, \
    GATE_HOLD, GATE_REL, COMP_ON, TUBE_ON

GATE_RNG = 0x002D

def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]

def s32(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)

part = Part(1)
sc = part.sc
print('cfg 0x%08X  cfg2 0x%08X' % (sc.rd(0xE0EA), sc.rd(0xE0EB)))

WHICH = [int(a) for a in (sys.argv[1:] or ['1', '2'])]
for strip in WHICH:
    b = (strip - 1) * STRIDE
    for off, w in ((GATE_ON, 1), (COMP_ON, 0), (TUBE_ON, 0),
                   (GATE_THR, f32(-40.0)), (GATE_ATT, f32(0.05)),
                   (GATE_REL, f32(0.5)), (GATE_RNG, f32(40.0)),
                   (GATE_HOLD, f32(0.2))):
        part.write(b + off, w, 0)
        time.sleep(0.02)
time.sleep(1.0)

def show(tag):
    row = []
    for strip in (1, 2):
        n = 'C1_GATE_%02d' % strip
        row.append('s%d on=%s env=%12s gain=%12s tgt=%12s hold=%11s' % (
            strip,
            s32(sc.peek(sc.addr('_gate_on_' + n))),
            s32(sc.peek(sc.addr('_gate_envelope_' + n))),
            s32(sc.peek(sc.addr('_gate_gain_' + n))),
            s32(sc.peek(sc.addr('_gate_gain_target_q_' + n))),
            s32(sc.peek(sc.addr('_gate_hold_count_' + n)))))
    print('  %-9s %s' % (tag, row[0]))
    print('  %-9s %s' % ('', row[1]))

print('gates on strips %s; before driving:' % WHICH)
show('quiet')
inj = sc.sym['_rx_slot_C1_IN_01'] if '_rx_slot_C1_IN_01' in sc.sym else 0
sc.arm(sc.addr('_gate_gain_C1_GATE_01'), inj, 0x0D3A17B5, 2)
try:
    sc.wait()
except Exception as exc:
    print('  (wait: %s)' % exc)
print('immediately after the step injection stops:')
for k in range(7):
    show('t=%4.1fs' % (k * 2.0))
    if k < 6:
        time.sleep(2.0)
