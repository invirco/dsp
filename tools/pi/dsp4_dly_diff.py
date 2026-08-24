#!/usr/bin/env python3
"""dsp4_dly_diff — capture C1_DLY_01's output for a build-vs-build diff.

DLY sits behind GATE, COMP and TUBE. COMP and TUBE are NOT converted, so
in a per-block build they never write the pool and DLY is handed EQ's
output, while in a per-sample build it is handed TUBE's. Bypassing all
three makes both builds present EQ's output to DLY, so the two captures
are directly comparable and the diff is a real bit-exactness test.

A resonant HPF in C1_FILT_01 makes the signal vary sample to sample; with
the default unity filters a step is constant and a delay of any length --
including none -- would satisfy the check.
"""
import argparse, struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

HPF0, HPF_SW = 0x0004, 0x0009
GATE_ON, COMP_ON, TUBE_ON = 0x0028, 0x0038, 0x004C
DLY_OFFSET = 0x004E
RESONANT = [1.0, -2.0, 1.0, -1.8, 0.81]


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--offset', type=int, default=5)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--pool', action='store_true')
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    inj = sc.sym['_blk_pool'] if a.pool else sc.sym['_rx_slot_C1_IN_01']
    src = (sc.sym['_blk_pool'] + 32) if a.pool else sc.sym['_buf_C1_DLY_01']

    for i, c in enumerate(RESONANT):
        sc.d.write(HPF0 + i, f32(c))
    for _ in range(3):
        sc.d.write(HPF_SW, 1)
        time.sleep(S.SETTLE)
    for addr in (GATE_ON, COMP_ON, TUBE_ON):
        sc.d.write(addr, 0)
    sc.d.write(DLY_OFFSET, a.offset)
    time.sleep(0.6)

    sc.arm(src, inj, int(a.amp, 16), 2)          # STEP into the resonant HPF
    if not sc.wait():
        raise SystemExit('scope never disarmed')
    vals = [v - (1 << 32) if v & 0x80000000 else v for v in sc.fetch(a.n)]
    if len(set(vals)) < 4:
        print('STIMULUS TOO FLAT: %d distinct -- proves nothing'
              % len(set(vals)))
        sys.exit(2)
    print('OFFSET %d  distinct %d' % (a.offset, len(set(vals))))
    for i, v in enumerate(vals):
        print('%d %d' % (i, v))


if __name__ == '__main__':
    main()
