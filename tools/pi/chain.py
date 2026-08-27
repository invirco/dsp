#!/usr/bin/env python3
"""chain.py — strip 1 end to end, against an EXPLICITLY CONFIGURED strip.

The previous version checked `mono == input` and assumed the strip was
transparent. That was true when only IN, GAIN, FDR and RTG were converted:
FILT, EQ, GATE, COMP, TUBE and DLY were unconverted, never touched the
pool, and the signal really did pass straight through. All six are
converted now and the gate and compressor are ON by default, so the
assumption expired silently and the probe read like a regression when
nothing had regressed. Three builds -- 786 MHz with the fabric conversion,
491 MHz with it, and 491 MHz without it -- produced identical values, which
is what proved the firmware innocent.

So this version CONFIGURES every node in the path and assumes nothing:
unity gain, unity filters, unity EQ, dynamics bypassed, no delay. Anything
it does not set, it does not trust.

RAMPED PARAMETERS GO THROUGH wrv WITH ramp_id=1. Gain, fader level, pan
and DCA are ramped, and writing them with ramp_id 0 takes the INSTANT path,
which sets only the level word -- the node's block-rate code then does
`if frames <= 0: level = target` and clobbers it from a target that was
never written. The negative control below is what caught this: halving the
gain changed nothing at all.

It also runs a NEGATIVE CONTROL. A probe that reports the input back could
pass while reading a dead buffer, so it deliberately sets a gain of 0.5 and
requires the reading to change. A check that cannot fail proves nothing --
this bench has produced two of those already (a `both_unity` biquad test
blind to state, and a delay test that ran on 27 samples of silence).
"""
import struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv

GAIN      = 0x0000
HPF0, HPF_SW = 0x0004, 0x0009
LPF0, LPF_SW = 0x000A, 0x000F
EQ0,  EQ_SW  = 0x0010, 0x0024
GATE_ON   = 0x0028
COMP_ON   = 0x0038
TUBE_ON   = 0x004C
DLY_OFF   = 0x004E
FDR_LEVEL = 0x0050
FDR_PAN   = 0x0051
FDR_MUTE  = 0x0052
FDR_DCA   = 0x0053

UNITY_BIQUAD = [1.0, 0.0, 0.0, 0.0, 0.0]      # RBJ b0,b1,b2,a1,a2
AMP = 0x08000000                               # -6 dBFS in Q4.28


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def configure(sc):
    """Put the whole strip in a known state. Never assume; always set."""
    wrv(sc, GAIN, f32(1.0), ramp_id=1, settle=0.05)

    for base, sw in ((HPF0, HPF_SW), (LPF0, LPF_SW)):
        for i, c in enumerate(UNITY_BIQUAD):
            sc.d.write(base + i, f32(c))
        for _ in range(3):                     # swap triggers are consumed
            sc.d.write(sw, 1)
            time.sleep(S.SETTLE)

    for band in range(4):
        for i, c in enumerate(UNITY_BIQUAD):
            sc.d.write(EQ0 + band * 5 + i, f32(c))
    for _ in range(3):
        sc.d.write(EQ_SW, 1)
        time.sleep(S.SETTLE)

    for addr in (GATE_ON, COMP_ON, TUBE_ON, FDR_MUTE):
        sc.d.write(addr, 0)
    sc.d.write(DLY_OFF, 0)
    wrv(sc, FDR_DCA, f32(1.0), ramp_id=1, settle=0.05)
    time.sleep(0.8)                            # let the coefficient fades finish


def main():
    sc = S.Scope(1)
    sc.check_chip()
    P = sc.sym['_blk_pool']
    BUS_L = sc.sym['_buf_C1_BUS_MAIN_L']

    def sgn(v):
        return v - (1 << 32) if v & 0x80000000 else v

    def cap(addr):
        sc.arm(addr, P, AMP, 2)
        if not sc.wait():
            raise SystemExit('scope never disarmed - sample loop not turning')
        return sgn(sc.fetch(1)[0])

    configure(sc)

    # ---- negative control: the probe must be able to see a change ----
    wrv(sc, FDR_LEVEL, f32(1.0), ramp_id=1, settle=0.05)
    wrv(sc, FDR_PAN, f32(0.5), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    base = cap(P)
    wrv(sc, GAIN, f32(0.5), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    halved = cap(P)
    wrv(sc, GAIN, f32(1.0), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    if halved == base:
        print('NEGATIVE CONTROL FAILED: halving the gain did not change the '
              'reading (%d) - this probe cannot fail, so it proves nothing' % base)
        return 2
    print('negative control ok: gain 1.0 -> %d, gain 0.5 -> %d' % (base, halved))

    bad = 0
    for lv, pn in ((1.0, 0.5), (0.5, 0.5), (0.25, 0.5),
                   (1.0, 0.0), (1.0, 0.25), (1.0, 0.75), (0.5, 0.25)):
        wrv(sc, FDR_LEVEL, f32(lv), ramp_id=1, settle=0.05)
        wrv(sc, FDR_PAN, f32(pn), ramp_id=1, settle=0.05)
        time.sleep(0.4)
        # THERE IS NO PAN-SPLIT BUFFER ANY MORE (08-25 crosspoint-coefficient
        # mandate, landed 2026-08-27). FADER_PAN used to multiply the mono by
        # the pan leg into BLK_FDR_L/R and ROUTING accumulated that with a
        # unity coefficient; the pan leg is now the main-bus CROSSPOINT
        # COEFFICIENT and ROUTING MACs the mono by it directly. The bus
        # reading is unchanged for one source -- the old form rounded the pan
        # product and then accumulated it exactly, which is the same single
        # rounding -- so this still checks the same number, one stage earlier.
        mono, bus = cap(P), cap(BUS_L)
        e_mono = int(round(AMP * lv))
        e_bus  = int(round(e_mono * (1.0 - pn)))
        ok = (mono == e_mono and bus == e_bus)
        bad += 0 if ok else 1
        print('lv=%-5g pn=%-5g mono=%10d/%-10d bus=%10d/%-10d  %s'
              % (lv, pn, mono, e_mono, bus, e_bus, 'ok' if ok else '<-- MISMATCH'))
    print('CHAIN %s (%d of 7 cases mismatched)'
          % ('BIT-EXACT' if bad == 0 else 'DIFFERS', bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
