#!/usr/bin/env python3
"""xp_chain0.py — strip 1 end to end on a PER-SAMPLE build, checking the
crosspoint-coefficient fold.

Same explicitly-configured strip and same negative control as chain.py,
but this build has no _blk_pool: the taps are scalars. The pan leg is no
longer a buffer either -- it is the main-bus crosspoint COEFFICIENT -- so
the check is mono at the fader and the bus after _acc64_rns28.

Expected, with one source on the bus:
    mono = sat(rns(x * gq, 28))
    bus  = sat(rns(mono * lq, 28))        lq = fix((1 - pan) * 2^28)
which is bit-identical to what the pre-fold path produced (it rounded the
pan product into _buf_L and then accumulated it with a unity coefficient,
and a unity 64-bit MAC read back through _acc64_rns28 is the identity).
The two forms only diverge with MORE THAN ONE source on the bus, where the
folded form rounds once at the bus instead of once per source.

Also exercises the two folds this build introduced: FDR mute and GAIN
polarity now live in the coefficient, not in a per-sample test.
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv

GAIN, POLARITY = 0x0000, 0x0001   # _mute_C1_GAIN_01 has no dispatch entry — mute lives on the fader
MAIN_ON, SUB_ON, GRP_ON_1 = 0x0054, 0x0055, 0x0056
HPF0, HPF_SW = 0x0004, 0x0009
LPF0, LPF_SW = 0x000A, 0x000F
EQ0,  EQ_SW  = 0x0010, 0x0024
GATE_ON, COMP_ON, TUBE_ON, DLY_OFF = 0x0028, 0x0038, 0x004C, 0x004E
FDR_LEVEL, FDR_PAN, FDR_MUTE, FDR_DCA = 0x0050, 0x0051, 0x0052, 0x0053
UNITY = [1.0, 0.0, 0.0, 0.0, 0.0]
AMP = 0x08000000

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def sgn(v): return v - (1 << 32) if v & 0x80000000 else v

def rns(acc, sh=28):
    v = (acc + (1 << (sh - 1))) >> sh
    return max(-(1 << 31), min((1 << 31) - 1, v))

def configure(sc):
    wrv(sc, GAIN, f32(1.0), ramp_id=1, settle=0.05)
    for base, sw in ((HPF0, HPF_SW), (LPF0, LPF_SW)):
        for i, c in enumerate(UNITY): sc.d.write(base + i, f32(c))
        for _ in range(3): sc.d.write(sw, 1); time.sleep(S.SETTLE)
    for band in range(4):
        for i, c in enumerate(UNITY): sc.d.write(EQ0 + band * 5 + i, f32(c))
    for _ in range(3): sc.d.write(EQ_SW, 1); time.sleep(S.SETTLE)
    for a in (GATE_ON, COMP_ON, TUBE_ON, FDR_MUTE, POLARITY):
        sc.d.write(a, 0)
    sc.d.write(DLY_OFF, 0)
    wrv(sc, FDR_DCA, f32(1.0), ramp_id=1, settle=0.05)
    time.sleep(0.8)

def main():
    sc = S.Scope(1)
    sc.check_chip()
    INJ = sc.sym['_rx_slot_C1_IN_01']
    MONO = sc.sym['_buf_C1_FDR_01']
    BUS  = sc.sym['_buf_C1_BUS_MAIN_L']
    def cap(addr):
        sc.arm(addr, INJ, AMP, 2)
        if not sc.wait(): raise SystemExit('scope never disarmed')
        return sgn(sc.fetch(8)[7])

    configure(sc)
    wrv(sc, FDR_LEVEL, f32(1.0), ramp_id=1, settle=0.05)
    wrv(sc, FDR_PAN, f32(0.5), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    base = cap(MONO)
    wrv(sc, GAIN, f32(0.5), ramp_id=1, settle=0.05); time.sleep(0.4)
    halved = cap(MONO)
    wrv(sc, GAIN, f32(1.0), ramp_id=1, settle=0.05); time.sleep(0.4)
    if halved == base:
        print('NEGATIVE CONTROL FAILED: halving the gain changed nothing (%d)' % base)
        return 2
    print('negative control ok: gain 1.0 -> %d, gain 0.5 -> %d' % (base, halved))

    bad = 0
    # pan 0.0 and 1.0 matter beyond covering the ends of the law: they drive
    # one main-bus crosspoint coefficient to EXACTLY ZERO, which is how the
    # doctrine spells "not assigned". With the compacted active-crosspoint
    # list that crosspoint is absent from the list entirely, so these two
    # rows are what prove the list is built from the coefficients and not
    # from a fixed walk.
    for lv, pn in ((1.0, 0.5), (0.5, 0.5), (0.25, 0.5),
                   (1.0, 0.0), (1.0, 1.0), (1.0, 0.25), (1.0, 0.75),
                   (0.5, 0.25)):
        wrv(sc, FDR_LEVEL, f32(lv), ramp_id=1, settle=0.05)
        wrv(sc, FDR_PAN, f32(pn), ramp_id=1, settle=0.05)
        time.sleep(0.4)
        mono, bus = cap(MONO), cap(BUS)
        e_mono = rns(AMP * int(round(lv * (1 << 28))))
        e_bus  = rns(e_mono * int(round((1.0 - pn) * (1 << 28))))
        ok = (mono == e_mono and bus == e_bus)
        bad += 0 if ok else 1
        print('lv=%-5g pn=%-5g mono=%10d/%-10d bus=%10d/%-10d  %s'
              % (lv, pn, mono, e_mono, bus, e_bus, 'ok' if ok else '<-- MISMATCH'))

    # ---- the list must GROW and SHRINK with the assignment ----
    wrv(sc, FDR_LEVEL, f32(1.0), ramp_id=1, settle=0.05)
    wrv(sc, FDR_PAN, f32(0.5), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    N = sc.sym.get('_rtg_n_C1_RTG_01')
    if N is not None:
        def n_live():
            for _ in range(8):
                try: return sc.d.peek(N)
                except Exception: time.sleep(0.05)
            return None
        seq = []
        for main, sub, grp in ((1, 0, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1), (1, 0, 0)):
            sc.d.write(MAIN_ON, main); sc.d.write(SUB_ON, sub)
            sc.d.write(GRP_ON_1, grp)
            time.sleep(0.4)
            seq.append((main, sub, grp, n_live()))
        want = [2, 3, 4, 2, 2]        # main is TWO crosspoints, L and R
        got = [s[3] for s in seq]
        ok = got == want
        bad += 0 if ok else 1
        print('live-crosspoint count main/sub/grp %s -> %s (expect %s)  %s'
              % ([s[:3] for s in seq], got, want, 'ok' if ok else '<-- MISMATCH'))
        sc.d.write(MAIN_ON, 1); sc.d.write(SUB_ON, 0); sc.d.write(GRP_ON_1, 0)
        time.sleep(0.4)
    else:
        print('live-crosspoint count: _rtg_n absent — build predates the '
              'compacted list, skipping')

    # ---- the folds themselves ----
    wrv(sc, FDR_LEVEL, f32(1.0), ramp_id=1, settle=0.05)
    wrv(sc, FDR_PAN, f32(0.5), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    ref_mono, ref_bus = cap(MONO), cap(BUS)
    sc.d.write(FDR_MUTE, 1); time.sleep(0.4)
    m_mono, m_bus = cap(MONO), cap(BUS)
    sc.d.write(FDR_MUTE, 0); time.sleep(0.4)
    u_mono, u_bus = cap(MONO), cap(BUS)
    mute_ok = (m_mono == 0 and m_bus == 0 and u_mono == ref_mono and u_bus == ref_bus)
    print('FDR mute fold: on -> mono=%d bus=%d, off -> mono=%d bus=%d  %s'
          % (m_mono, m_bus, u_mono, u_bus, 'ok' if mute_ok else '<-- MISMATCH'))
    bad += 0 if mute_ok else 1

    sc.d.write(POLARITY, 1); time.sleep(0.4)
    p_mono = cap(MONO)
    sc.d.write(POLARITY, 0); time.sleep(0.4)
    n_mono = cap(MONO)
    pol_ok = (p_mono == -ref_mono and n_mono == ref_mono)
    print('GAIN polarity fold: inv -> mono=%d (expect %d), back -> %d  %s'
          % (p_mono, -ref_mono, n_mono, 'ok' if pol_ok else '<-- MISMATCH'))
    bad += 0 if pol_ok else 1

    print('CHAIN %s (%d checks mismatched)'
          % ('BIT-EXACT' if bad == 0 else 'DIFFERS', bad))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
