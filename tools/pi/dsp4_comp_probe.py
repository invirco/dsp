#!/usr/bin/env python3
"""dsp4_comp_probe — compressor static curve and attack/release timing.

Chain (chip 1, strip 1):
    _rx_slot_C1_IN_01 -> GAIN -> FILT -> EQ -> GATE -> COMP -> _buf_C1_COMP_01

Everything upstream is forced to unity and the GATE is switched OFF, so
what reaches the compressor is exactly the injected step. Leaving an
upstream node holding a previous test's coefficients is how a measurement
ends up describing somebody else's filter (bench 2026-08-23).

A STEP is the right stimulus here: its settled tail gives the static gain
reduction, and its leading edge gives the attack envelope, from one
capture.
"""
import argparse, struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

GAIN = 0x0000
HPF0, HPF_SW, LPF0, LPF_SW = 0x0004, 0x0009, 0x000A, 0x000F
EQ0, EQ_SW = 0x0010, 0x0024
GATE_ON = 0x0028
COMP_ON, COMP_THR, COMP_RAT = 0x0038, 0x0039, 0x003A
COMP_ATT, COMP_REL, COMP_MAKE, COMP_KNEE = 0x003B, 0x003C, 0x003D, 0x003E
COMP_PAR = 0x003F
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


def set_bq(sc, base, swap, band):
    for i, c in enumerate(band):
        wrv(sc, base + i, f32(c))
    for _ in range(3):
        sc.d.write(swap, 1)
        time.sleep(S.SETTLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thr', type=float, default=-20.0)
    ap.add_argument('--ratio', type=float, default=4.0)
    ap.add_argument('--attack', type=float, default=0.001)
    ap.add_argument('--release', type=float, default=0.05)
    ap.add_argument('--knee', type=float, default=0.0)
    ap.add_argument('--parallel', type=float, default=1.0)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--gate-off', action='store_true', default=True)
    a = ap.parse_args()

    sc = S.Scope(1)
    inj = sc.sym['_rx_slot_C1_IN_01']
    src = sc.sym['_buf_C1_COMP_01']

    wrv(sc, GAIN, f32(1.0))
    set_bq(sc, HPF0, HPF_SW, UNITY)
    set_bq(sc, LPF0, LPF_SW, UNITY)
    for i in range(4):
        for j, c in enumerate(UNITY):
            wrv(sc, EQ0 + i * 5 + j, f32(c))
    for _ in range(3):
        sc.d.write(EQ_SW, 1)
        time.sleep(S.SETTLE)
    wrv(sc, GATE_ON, 0)                      # gate open, out of the way

    wrv(sc, COMP_ON, 1)
    wrv(sc, COMP_THR, f32(a.thr))
    wrv(sc, COMP_RAT, f32(a.ratio))
    wrv(sc, COMP_ATT, f32(a.attack))
    wrv(sc, COMP_REL, f32(a.release))
    wrv(sc, COMP_MAKE, f32(1.0))
    wrv(sc, COMP_KNEE, f32(a.knee))
    wrv(sc, COMP_PAR, f32(a.parallel))
    time.sleep(0.6)

    amp = int(a.amp, 16)
    sc.arm(src, inj, amp, 2)                 # STEP
    sc.wait()
    vals = sc.fetch(a.n)
    print('PARAMS thr=%g ratio=%g att=%g rel=%g knee=%g par=%g amp=0x%08X'
          % (a.thr, a.ratio, a.attack, a.release, a.knee, a.parallel, amp))
    for i, v in enumerate(vals):
        print('%d %d' % (i, v - (1 << 32) if v & 0x80000000 else v))


if __name__ == '__main__':
    main()
