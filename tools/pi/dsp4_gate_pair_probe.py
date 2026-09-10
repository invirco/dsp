#!/usr/bin/env python3
"""dsp4_gate_pair_probe.py — the SIMD gate pair, watched at both ends (S22 gate 0).

S21-7 reported that under DSP4_SIMD_DYN one strip of every gate pair has four
FROZEN state words while the partner's hold counter decrements. This asks the
question with a stimulus slow enough to see:

  * gate parameters with a LONG hold and release, so an envelope that was
    driven is still visibly above rest seconds later and a frozen one is not
    confused with one that has already decayed;
  * strip 1 driven by the scope's step injection, strip 2 never driven;
  * BOTH strips' four state words AND the pair kernel's own shared gather
    buffer _gat_st[8] read on every pass.

_gat_st is the discriminator. It is written by _gate_pair_blk's SIMD store
(PEx -> even words, PEy -> odd) and read back by the scatter that gives each
node its state. If _gat_st moves and the node words do not, the scatter is
the defect; if the odd words of _gat_st never move, PEy is; if both move,
there is no freeze on this image.
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


HOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
REL = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0

part = Part(1)
sc = part.sc
print('cfg 0x%08X  cfg2 0x%08X' % (sc.rd(0xE0EA), sc.rd(0xE0EB)))
print('hold=%.1f s  release=%.1f s' % (HOLD, REL))

for strip in (1, 2):
    b = (strip - 1) * STRIDE
    for off, w in ((GATE_ON, 1), (COMP_ON, 0), (TUBE_ON, 0),
                   (GATE_THR, f32(-60.0)), (GATE_ATT, f32(0.001)),
                   (GATE_REL, f32(REL)), (GATE_RNG, f32(40.0)),
                   (GATE_HOLD, f32(HOLD))):
        part.write(b + off, w, 0)
        time.sleep(0.02)
time.sleep(1.0)

ST = sc.addr('_gat_st')
NODE = {}
for strip in (1, 2):
    n = 'C1_GATE_%02d' % strip
    NODE[strip] = [sc.addr('_gate_envelope_' + n), sc.addr('_gate_gain_' + n),
                   sc.addr('_gate_gain_target_q_' + n),
                   sc.addr('_gate_hold_count_' + n)]


def show(tag):
    gat = [s32(sc.peek(ST + k)) for k in range(8)]
    print('  %-9s _gat_st  A[env gain tgt hold] = %s' % (tag, gat[0::2]))
    print('  %-9s          B[env gain tgt hold] = %s' % ('', gat[1::2]))
    for strip in (1, 2):
        print('  %-9s   s%d node                = %s'
              % ('', strip, [s32(sc.peek(a)) for a in NODE[strip]]))


print('quiet, before driving:')
show('quiet')
inj = sc.addr('_rx_slot_C1_IN_01')
sc.arm(sc.addr('_gate_gain_C1_GATE_01'), inj, 0x0D3A17B5, 2)
try:
    sc.wait()
except Exception as exc:
    print('  (wait: %s)' % exc)
print('after the step injection on strip 1 only:')
for k in range(8):
    show('t=%4.1fs' % (k * 1.5))
    if k < 7:
        time.sleep(1.5)
