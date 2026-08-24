#!/usr/bin/env python3
"""dsp4_comp_gr — capture COMP output, having PROVED it is reducing gain.

An earlier comparison of the table and polynomial log2/exp2 forms returned
"0 of 200 samples differ" and meant nothing: the captured peak equalled the
injected amplitude, so the compressor was passing signal through. With the
stock attack of 0.001 the envelope only reaches about -20.8 dBFS after 200
samples -- right at the default -20 dB threshold -- so the gain computer
never leaves unity inside the window.

This uses a fast attack and a threshold well under the signal, and REFUSES
to print samples unless the output is measurably below the input. A
comparison that cannot fail is not evidence.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thr', type=float, default=-30.0)
    ap.add_argument('--ratio', type=float, default=8.0)
    ap.add_argument('--attack', type=float, default=0.5)
    ap.add_argument('--release', type=float, default=0.05)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--pool-inj', type=int, default=0)
    ap.add_argument('--pool-src', type=int, default=1)
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    inj = sc.sym['_blk_pool'] + a.pool_inj * 32
    src = sc.sym['_blk_pool'] + a.pool_src * 32

    def w(addr, val):
        sc.d.write(addr, val)
        time.sleep(S.SETTLE)

    w(GAIN, f32(1.0))
    for base, sw in ((HPF0, HPF_SW), (LPF0, LPF_SW)):
        for i, c in enumerate(UNITY):
            w(base + i, f32(c))
        for _ in range(3):
            w(sw, 1)
    for band in range(4):
        for i, c in enumerate(UNITY):
            w(EQ0 + band * 5 + i, f32(c))
    for _ in range(3):
        w(EQ_SW, 1)
    w(GATE_ON, 0)

    w(COMP_ON, 1)
    w(COMP_THR, f32(a.thr))
    w(COMP_RAT, f32(a.ratio))
    w(COMP_ATT, f32(a.attack))
    w(COMP_REL, f32(a.release))
    w(COMP_MAKE, f32(1.0))
    w(COMP_KNEE, f32(0.0))
    w(COMP_PAR, f32(1.0))          # fully wet, or the dry path hides everything
    time.sleep(0.8)

    amp = int(a.amp, 16)
    sc.arm(src, inj, amp, 2)       # STEP
    if not sc.wait():
        raise SystemExit('scope never disarmed')
    vals = [v - (1 << 32) if v & 0x80000000 else v for v in sc.fetch(a.n)]

    tail = vals[max(0, len(vals) - 32):]
    settled = max(abs(v) for v in tail) if tail else 0
    gr_db = 20 * (0 if settled <= 0 else __import__('math').log10(settled / amp))
    print('PARAMS thr=%g ratio=%g att=%g amp=0x%08X' % (a.thr, a.ratio, a.attack, amp))
    print('GAIN REDUCTION at the tail: %.2f dB (settled %d vs injected %d)'
          % (gr_db, settled, amp))
    if gr_db > -1.0:
        print('NOT COMPRESSING (< 1 dB of reduction) - this capture proves '
              'nothing about the gain computer')
        sys.exit(2)
    for i, v in enumerate(vals):
        print('%d %d' % (i, v))


if __name__ == '__main__':
    main()
