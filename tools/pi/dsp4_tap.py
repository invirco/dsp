#!/usr/bin/env python3
"""dsp4_tap — capture any strip tap for a build-vs-build diff.

One probe for the whole strip: pick the capture point by symbol name or by
pool slot, drive a stimulus that actually varies, and print the samples.

The resonant HPF matters. With the default unity filters a step is
constant after sample 0, and a capture that agrees for any processing at
all -- including none -- proves nothing. Two earlier verifications on this
bench reported clean passes over windows of zeros or constants before that
was noticed.
"""
import argparse, struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

HPF0, HPF_SW = 0x0004, 0x0009
RESONANT = [1.0, -2.0, 1.0, -1.8, 0.81]


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', help='symbol to capture, e.g. _buf_C1_TUBE_01')
    ap.add_argument('--pool-src', type=int, help='capture _blk_pool + N*32')
    ap.add_argument('--pool-inj', action='store_true',
                    help='inject into _blk_pool + 0 (per-block builds: the '
                         'input kernel reads DMA directly and _rx_slot_* is '
                         'unreferenced, so injecting there does nothing)')
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--mode', type=int, default=2, help='1=impulse 2=step')
    ap.add_argument('--set', action='append', default=[],
                    metavar='ADDR=VAL', help='raw SPI write, hex addr')
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    inj = sc.sym['_blk_pool'] if a.pool_inj else sc.sym['_rx_slot_C1_IN_01']
    src = (sc.sym['_blk_pool'] + a.pool_src * 32) if a.pool_src is not None \
          else sc.sym[a.src]

    for i, c in enumerate(RESONANT):
        sc.d.write(HPF0 + i, f32(c))
    for _ in range(3):
        sc.d.write(HPF_SW, 1)
        time.sleep(S.SETTLE)
    for kv in a.set:
        addr, val = kv.split('=')
        sc.d.write(int(addr, 16), int(val, 0))
    time.sleep(0.6)

    sc.arm(src, inj, int(a.amp, 16), a.mode)
    if not sc.wait():
        raise SystemExit('scope never disarmed')
    vals = [v - (1 << 32) if v & 0x80000000 else v for v in sc.fetch(a.n)]
    distinct = len(set(vals))
    nonzero = sum(1 for v in vals if v != 0)
    if distinct < 4 or nonzero < 4:
        print('STIMULUS TOO FLAT: %d distinct, %d non-zero -- this capture '
              'could not have failed' % (distinct, nonzero))
        sys.exit(2)
    print('CAPTURE distinct=%d nonzero=%d' % (distinct, nonzero))
    for i, v in enumerate(vals):
        print('%d %d' % (i, v))


if __name__ == '__main__':
    main()
