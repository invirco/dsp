#!/usr/bin/env python3
"""dsp4_d80.py — is D80 arithmetic, or a point on a convergence curve?

Takes the two ladders d80.sh captured (one boot per arm, the chip-2 meters
read at a series of elapsed times with DIAG_FRAME_COUNT and
DIAG_BLK_OVERRUN bracketing every read) and answers three questions in
order:

  1. IS THE METER STILL MOVING at the dwell the comparison uses? A meter is
     a per-BLOCK IIR; under DSP4_BLOCK_DECIMATE its constants stretch by the
     decimation factor in wall clock. If the last two captures of one arm
     differ by more than the cross-arm delta, that delta was never a
     measurement of the conversion.

  2. DO THE TWO ARMS RUN AT DIFFERENT SPEEDS? Graph passes per second, from
     FRAME_COUNT and the decimation. This is not a defect -- it is what the
     two arms are for -- but it is the mechanism, because a meter's value is
     a function of how many folds have happened.

  3. DO THEY LIE ON THE SAME CURVE against PASSES rather than seconds? Each
     arm's trajectory is interpolated onto the other's pass counts and the
     residual is reported per meter. A residual at the noise floor says D80
     is the curve and nothing else; a residual that holds at the recorded
     0.4-0.9 % says it is arithmetic, and the number to chase is the
     residual and not the raw delta.

Usage: dsp4_d80.py arm0.json arm1.json [--dec 32] [--block 16]
"""
import argparse
import json
import struct
import sys


def f32(u):
    """The meters are IEEE float32 words on the wire."""
    if u is None:
        return None
    return struct.unpack('<f', struct.pack('<I', u & 0xFFFFFFFF))[0]


def passes(cap, dec):
    """Graph passes at this capture, from the bracketing frame counters.

    The MIDPOINT of the bracket, because a meter capture takes seconds over
    this link and FRAME_COUNT advances throughout; the spread is reported
    beside it rather than hidden.
    """
    f0, f1 = cap.get('frame0'), cap.get('frame1')
    if f0 is None or f1 is None:
        return None, None
    mid = 0.5 * (f0 + f1)
    return mid / dec, (f1 - f0) / dec


def interp(xs, ys, x):
    """Linear interpolation, refusing to extrapolate.

    Extrapolating a convergence curve is how a comparison invents the
    agreement it was looking for, so a point outside the other arm's range
    returns None and is reported as UNCOVERED rather than scored.
    """
    if x < xs[0] or x > xs[-1]:
        return None
    for i in range(1, len(xs)):
        if x <= xs[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return ys[-1]


def pct(a, b):
    """b relative to a, in per cent; None when a is zero."""
    if a is None or b is None or a == 0.0:
        return None
    return 100.0 * (b - a) / abs(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('arm0')
    ap.add_argument('arm1')
    ap.add_argument('--dec', type=int, default=32)
    ap.add_argument('--block', type=int, default=16)
    args = ap.parse_args()

    A = json.load(open(args.arm0))
    B = json.load(open(args.arm1))
    ca, cb = A['caps'], B['caps']
    if not ca or not cb:
        print('no captures'); return 3

    print(f'=== D80: chip-2 meters against GRAPH PASSES  '
          f'(block {args.block}, decimation {args.dec}) ===')
    print()
    print('  A meter folds once per graph pass. Its RMS window is 300 ms and '
          'its peak decay')
    print(f'  1.333 s AT BLOCK RATE; at block {args.block} and decimation '
          f'{args.dec} that is '
          f'{0.300 * args.dec * 48000.0 / args.block / (48000.0 / args.block):.1f} s '
          f'and {1.333 * args.dec:.1f} s of WALL CLOCK.')
    print()

    # ---- 1. the trajectory, per arm -------------------------------------
    for name, caps in (('arm0 per-sample', ca), ('arm1 block-kernel', cb)):
        print(f'  {name}: {len(caps)} captures')
        print('    t (s)   passes   pass/s   overrun   probes')
        prev = None
        for c in caps:
            p, spread = passes(c, args.dec)
            rate = ''
            if prev is not None and p is not None and c['t'] > prev[1]:
                rate = f'{(p - prev[0]) / (c["t"] - prev[1]):8.1f}'
            print(f'    {c["t"]:6.1f}  {p if p is None else round(p):>8}  '
                  f'{rate:>8}  {c.get("ovr1")!s:>7}   {len(c["m"])}')
            if p is not None:
                prev = (p, c['t'])
        print()

    # ---- 2. is it still moving? -----------------------------------------
    names = sorted(set(ca[-1]['m']) & set(cb[-1]['m']))
    if not names:
        print('  the two arms share no readable probe'); return 3

    print('  STILL MOVING? last two captures of each arm, worst probe:')
    for label, caps in (('arm0', ca), ('arm1', cb)):
        if len(caps) < 2:
            print(f'    {label}: one capture only'); continue
        worst, wn = 0.0, None
        for n in names:
            d = pct(f32(caps[-2]['m'].get(n)), f32(caps[-1]['m'].get(n)))
            if d is not None and abs(d) > abs(worst):
                worst, wn = d, n
        print(f'    {label}: {worst:+.3f} %% on {wn}  '
              f'(t {caps[-2]["t"]:.0f} -> {caps[-1]["t"]:.0f} s)'
              .replace('%%', '%'))
    print()

    # ---- 3. the same curve, against passes? ------------------------------
    xa = [passes(c, args.dec)[0] for c in ca]
    xb = [passes(c, args.dec)[0] for c in cb]
    if any(x is None for x in xa + xb):
        print('  FRAME_COUNT unreadable in at least one capture; '
              'the pass axis is not available'); return 2

    print('  RAW cross-arm delta at EQUAL WALL CLOCK, and the RESIDUAL at '
          'EQUAL PASSES:')
    print('    probe                              raw %     residual %   '
          'passes')
    raw_worst, res_worst, uncovered = 0.0, 0.0, 0
    for n in names:
        # raw: the comparison as c2gold makes it -- both arms at the same
        # dwell, which is the last capture they have in common by index.
        k = min(len(ca), len(cb)) - 1
        raw = pct(f32(ca[k]['m'].get(n)), f32(cb[k]['m'].get(n)))
        # residual: arm1's value at arm1's pass count against arm0's
        # trajectory interpolated to THAT pass count.
        ya = [f32(c['m'].get(n)) for c in ca]
        if any(v is None for v in ya):
            continue
        xq = xb[-1]
        ref = interp(xa, ya, xq)
        got = f32(cb[-1]['m'].get(n))
        res = pct(ref, got) if ref is not None else None
        if res is None:
            uncovered += 1
        if raw is not None and abs(raw) > abs(raw_worst):
            raw_worst = raw
        if res is not None and abs(res) > abs(res_worst):
            res_worst = res
        print(f'    {n:34s} {raw if raw is None else f"{raw:+8.3f}"}   '
              f'{"UNCOVERED" if res is None else f"{res:+8.3f}"}   '
              f'{round(xq)}')
    print()
    print(f'  worst RAW delta at equal wall clock: {raw_worst:+.3f} %')
    print(f'  worst RESIDUAL at equal passes:      {res_worst:+.3f} %'
          + (f'   ({uncovered} probes UNCOVERED: arm1 ran past arm0\'s '
             f'last pass count -- lengthen TIMES for arm0)' if uncovered
             else ''))
    print()
    if uncovered:
        print('  VERDICT WITHHELD: the pass ranges do not overlap at the '
              'top, so the residual is not computed for every probe.')
        return 1
    if abs(res_worst) < 0.05 <= abs(raw_worst):
        print('  VERDICT: D80 IS THE CONVERGENCE CURVE. At equal wall clock '
              'the arms differ; at equal')
        print('  GRAPH PASSES they lie on the same curve. The meters were '
              'never settled at the dwell')
        print('  the comparison used, and the two arms are built to run at '
              'different speeds.')
        return 0
    print('  VERDICT: A RESIDUAL SURVIVES the pass alignment. D80 is not '
          'only the curve; the')
    print(f'  quantity to chase is {res_worst:+.3f} %, not the raw '
          f'{raw_worst:+.3f} %.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
