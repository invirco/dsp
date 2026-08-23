#!/usr/bin/env python3
"""dsp4_tubedly_probe — tube saturation curve and delay-line offset.

Chain: IN -> GAIN -> FILT -> EQ -> GATE -> COMP -> TUBE -> DLY

Everything ahead of the node under test is forced transparent: GAIN and
all biquads to unity, GATE off, COMP off. TUBE is switched off for the
DLY test so the delay sees a clean impulse.

TUBE is y = x*(1 + sat*(1 - x^2)) in Q4.28, so a step at several
amplitudes traces the curve. DLY is a read offset into a delay line, so
an impulse should reappear exactly `offset` samples later -- which is a
sharper test than any level measurement.
"""
import argparse, struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

GAIN = 0x0000
HPF0, HPF_SW, LPF0, LPF_SW = 0x0004, 0x0009, 0x000A, 0x000F
EQ0, EQ_SW = 0x0010, 0x0024
GATE_ON, COMP_ON = 0x0028, 0x0038
TUBE_ON, TUBE_SAT, DLY_OFF = 0x004C, 0x004D, 0x004E
UNITY = [1.0, 0.0, 0.0, 0.0, 0.0]


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def wrv(sc, addr, val, tries=12):
    val &= 0xFFFFFFFF
    for _ in range(tries):
        sc.d.write(addr, val)
        time.sleep(S.SETTLE)
        try:
            if sc.rd(addr) == val:
                return
        except IOError:
            pass
    raise IOError('SPI 0x%04X would not take 0x%08X' % (addr, val))


def transparent_chain(sc):
    wrv(sc, GAIN, f32(1.0))
    for base, swap in ((HPF0, HPF_SW), (LPF0, LPF_SW)):
        for i, c in enumerate(UNITY):
            wrv(sc, base + i, f32(c))
        for _ in range(3):
            sc.d.write(swap, 1)
            time.sleep(S.SETTLE)
    for i in range(4):
        for j, c in enumerate(UNITY):
            wrv(sc, EQ0 + i * 5 + j, f32(c))
    for _ in range(3):
        sc.d.write(EQ_SW, 1)
        time.sleep(S.SETTLE)
    wrv(sc, GATE_ON, 0)
    wrv(sc, COMP_ON, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('tube', 'dly'))
    ap.add_argument('--sat', type=float, default=0.5)
    ap.add_argument('--offset', type=int, default=17)
    ap.add_argument('--n', type=int, default=64)
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    inj = sc.sym['_rx_slot_C1_IN_01']
    transparent_chain(sc)

    if a.mode == 'tube':
        wrv(sc, TUBE_ON, 1)
        wrv(sc, TUBE_SAT, f32(a.sat))
        time.sleep(0.4)
        src = sc.sym['_buf_C1_TUBE_01']
        for amp in (0x02000000, 0x04000000, 0x08000000,
                    0x0C000000, 0x10000000):
            sc.arm(src, inj, amp, 2)           # step
            sc.wait()
            v = sc.fetch(8)[7]
            print('TUBE sat=%g in=%d out=%d'
                  % (a.sat, amp, v - (1 << 32) if v & 0x80000000 else v))
    else:
        wrv(sc, TUBE_ON, 0)
        wrv(sc, DLY_OFF, a.offset)
        time.sleep(0.4)
        src = sc.sym['_buf_C1_DLY_01']
        sc.arm(src, inj, 0x08000000, 1)        # impulse
        sc.wait()
        vals = sc.fetch(a.n)
        nz = [(i, v) for i, v in enumerate(vals) if v]
        print('DLY offset=%d nonzero=%s' % (a.offset, nz[:4]))


if __name__ == '__main__':
    main()
