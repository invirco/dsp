#!/usr/bin/env python3
"""dsp4_gate_probe — gate open/close threshold, range floor and timing.

Chain: _rx_slot_C1_IN_01 -> GAIN -> FILT -> EQ -> GATE -> _buf_C1_GATE_01
Everything upstream is forced to unity first, so what the gate sees is the
injected step and nothing else.

The gate is: envelope -> log2 -> compare against threshold -> pick a gain
TARGET (1.0 open, `range` closed, with a hold counter) -> one-pole smooth
the gain -> multiply. A step exercises all of it: the leading edge gives
the open time, the tail gives the settled gain.
"""
import argparse, struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

GAIN = 0x0000
HPF0, HPF_SW, LPF0, LPF_SW = 0x0004, 0x0009, 0x000A, 0x000F
EQ0, EQ_SW = 0x0010, 0x0024
G_ON, G_THR, G_ATT, G_HOLD, G_REL, G_RNG = (0x0028, 0x0029, 0x002A,
                                            0x002B, 0x002C, 0x002D)
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
    ap.add_argument('--thr', type=float, default=-40.0)
    ap.add_argument('--attack', type=float, default=0.2)
    ap.add_argument('--release', type=float, default=0.2)
    ap.add_argument('--hold', type=float, default=4)
    ap.add_argument('--range', dest='rng', type=float, default=0.001)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=300)
    a = ap.parse_args()

    sc = S.Scope(1)
    inj = sc.sym['_rx_slot_C1_IN_01']
    src = sc.sym['_buf_C1_GATE_01']

    wrv(sc, GAIN, f32(1.0))
    set_bq(sc, HPF0, HPF_SW, UNITY)
    set_bq(sc, LPF0, LPF_SW, UNITY)
    for i in range(4):
        for j, c in enumerate(UNITY):
            wrv(sc, EQ0 + i * 5 + j, f32(c))
    for _ in range(3):
        sc.d.write(EQ_SW, 1)
        time.sleep(S.SETTLE)

    wrv(sc, G_ON, 1)
    wrv(sc, G_THR, f32(a.thr))
    wrv(sc, G_ATT, f32(a.attack))
    wrv(sc, G_REL, f32(a.release))
    wrv(sc, G_HOLD, f32(a.hold))
    wrv(sc, G_RNG, f32(a.rng))
    time.sleep(0.6)

    amp = int(a.amp, 16)
    sc.arm(src, inj, amp, 2)                 # STEP
    sc.wait()
    vals = sc.fetch(a.n)
    print('PARAMS thr=%g att=%g rel=%g hold=%g rng=%g amp=0x%08X'
          % (a.thr, a.attack, a.release, a.hold, a.rng, amp))
    for i, v in enumerate(vals):
        print('%d %d' % (i, v - (1 << 32) if v & 0x80000000 else v))


if __name__ == '__main__':
    main()
