#!/usr/bin/env python3
"""dsp4_dly_probe — verify the delay line by its own definition.

DLY sits behind COMP and TUBE, which are not converted, so a block build
and a per-sample build do NOT present the same signal to DLY and an
end-to-end diff would be comparing two different stimuli. Instead this
captures DLY's INPUT and its OUTPUT in the same build and checks the only
thing the node claims to do:

    out[i] == in[i - offset]

Samples before `offset` come from whatever was already in the delay line,
so they are not checked.
"""
import argparse, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

DLY_OFFSET = 0x004E          # C1_DLY_01 delay offset, in samples
HPF0, HPF_SW = 0x0004, 0x0009   # C1_FILT_01 HPF: 5 float words + swap
GATE_ON = 0x0028                # C1_GATE_01 GateOn


def f32(x):
    import struct
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


# A resonant HPF so the signal reaching DLY actually VARIES sample to
# sample. With the default unity filters and a step, in[] is constant and
# out[i] == in[i-offset] holds for any delay at all, including none -- the
# test would prove nothing.
RESONANT = [1.0, -2.0, 1.0, -1.8, 0.81]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--offset', type=int, default=5)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--pool', action='store_true',
                    help='per-block build: in = _blk_pool+0, out = _blk_pool+32')
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    # Under per-block kernels the input kernel reads the DMA buffer
    # directly and _rx_slot_* is unreferenced, so injecting there does
    # nothing at all -- the stimulus has to go into the pool from inside
    # the chain.
    inj = (sc.sym['_blk_pool'] if a.pool else sc.sym['_rx_slot_C1_IN_01'])
    if a.pool:
        a_in, a_out = sc.sym['_blk_pool'], sc.sym['_blk_pool'] + 32
    else:
        a_in, a_out = sc.sym['_buf_C1_TUBE_01'], sc.sym['_buf_C1_DLY_01']

    for i, c in enumerate(RESONANT):
        sc.d.write(HPF0 + i, f32(c))
    for _ in range(3):
        sc.d.write(HPF_SW, 1)
        time.sleep(S.SETTLE)
    # The gate sits between the filter and the delay and is STATEFUL and
    # level dependent, so its ramp state is not identical on two separate
    # captures -- with it live, in[] and out[] came from runs that differed
    # by 1 LSB and the check reported mismatches that were nothing to do
    # with the delay. Bypass it so the signal reaching DLY is deterministic.
    sc.d.write(GATE_ON, 0)
    sc.d.write(DLY_OFFSET, a.offset)
    time.sleep(0.6)                    # let the coefficient crossfade finish
    amp = int(a.amp, 16)

    def cap(addr):
        sc.arm(addr, inj, amp, 2)          # STEP into a resonant HPF
        if not sc.wait():
            raise SystemExit('scope never disarmed')
        return [v - (1 << 32) if v & 0x80000000 else v for v in sc.fetch(a.n)]

    xs = cap(a_in)
    time.sleep(0.3)
    ys = cap(a_out)

    print('OFFSET %d' % a.offset)

    # A pass is only meaningful if the stimulus could have failed. A
    # constant or silent input satisfies out[i] == in[i-offset] for ANY
    # delay, including none -- an impulse died here because the gate stays
    # shut, and the run reported 0 mismatches over 27 samples of zeros.
    window = xs[:a.n - a.offset]
    distinct = len(set(window))
    nonzero = sum(1 for v in window if v != 0)
    if distinct < 4 or nonzero < 4:
        print('STIMULUS TOO FLAT: %d distinct values, %d non-zero -- this '
              'test cannot fail and proves nothing' % (distinct, nonzero))
        sys.exit(2)
    print('STIMULUS ok: %d distinct values, %d non-zero' % (distinct, nonzero))
    bad = 0
    for i in range(a.offset, a.n):
        ok = (ys[i] == xs[i - a.offset])
        if not ok:
            bad += 1
        print('%2d in=%12d out=%12d expect=%12d %s'
              % (i, xs[i], ys[i], xs[i - a.offset], '' if ok else '<-- MISMATCH'))
    print('CHECKED %d  MISMATCHES %d' % (a.n - a.offset, bad))


if __name__ == '__main__':
    main()
