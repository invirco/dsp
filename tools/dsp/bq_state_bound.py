#!/usr/bin/env python3
"""bq_state_bound.py — RIG C's known weak point, measured.

PW's D5 amendment (2026-09-02) moves the round and the saturate to ONCE
per cascade output. The dispatch's own words about what that leaves
open: "a high-Q filter's state can overflow regardless of I/O level --
headroom at entry does NOT fully protect it. Do NOT wave this away."

WHAT THE RECURSIVE STATE ACTUALLY IS, because it decides the whole
answer. The normative topology is offset-coefficient DIRECT FORM I
(fixed_ref.biquad), whose state is x1 x2 y1 y2 plus the error-feedback
remainder. x1/x2 are past INPUTS and y1/y2 are past OUTPUTS -- there is
no separate internal node in DF-I, so "the state overflows" and "the
stage output overflows" are the SAME event. That is good news for the
guard and bad news for the headroom, and this script quantifies both:

  * TODAY, y is saturated at every stage. The recursion therefore stays
    representable by construction: a clipped y is a WRONG y, but it is a
    bounded one, and the filter degrades into soft nonlinearity rather
    than inverting sign.
  * UNDER ROUND-ONCE there is no per-stage clamp, so the extracted y
    WRAPS. A wrap in a RECURSIVE path is not a clipped sample; it is a
    full-scale sign inversion fed back into the poles, and a high-Q
    section will ring on it.

SO THE BOUND THAT MATTERS IS THE BOUND ON y, AND IT IS NOT max|H|.
For an arbitrary input bounded by |x| <= X the reachable output bound is
X * ||h||_1, the l1 norm of the impulse response, and for a high-Q boost
||h||_1 is far above the sine-reachable max|H|. THAT is the precise
sense in which "headroom at entry does not protect the state": headroom
sized on the EQ curve (max|H|) is not headroom sized on ||h||_1.

Outputs, over the DEFS design space (bound_efb.design_space):
  1. max|H| and ||h||_1 per design, and the headroom BITS each implies
     against Q4.28's ceiling of 8.0 for a 0 dBFS (1.0) input;
  2. the (family, f0, gain, Q) corners that need the most;
  3. a WRAP DEMONSTRATION on a reachable setting: the same filter, the
     same stimulus, run through the saturating contract and through a
     round-once model, showing the sign inversion.

Usage: python3 bq_state_bound.py [--quick] [--full]
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr
from bound_efb import design_space, peaking, shelf, hplp

FS = 48000.0
NMAX = 400000          # impulse-response length for the l1 sum
QB = fr.QB
CEIL = 8.0             # Q4.28's ceiling, = +18.06 dB above 0 dBFS


def max_abs_H(cf, npts=1024, chunk=2000):
    """Peak |H(e^jw)| on a log grid plus DC and Nyquist, in chunks so the
    grid never becomes a gigabyte."""
    w = np.concatenate(([0.0],
                        2 * np.pi * np.logspace(math.log10(5.0),
                                                math.log10(FS / 2 - 1),
                                                npts) / FS,
                        [np.pi]))
    z1 = np.exp(-1j * w)[None, :]
    z2 = z1 * z1
    out = np.empty(len(cf))
    for s0 in range(0, len(cf), chunk):
        part = cf[s0:s0 + chunk]
        b0, b1, b2, a1, a2 = (np.asarray(x, dtype=np.float64)
                              for x in zip(*part))
        num = b0[:, None] + b1[:, None] * z1 + b2[:, None] * z2
        den = 1.0 + a1[:, None] * z1 + a2[:, None] * z2
        out[s0:s0 + len(part)] = np.abs(num / den).max(axis=1)
    return out


def l1_norm(cf, nmax=NMAX):
    """sum_n |h[n]|, run as the recursion itself rather than in closed
    form, so the number reported is the one the filter actually produces.

    The length is chosen PER DESIGN from the pole radius (r = sqrt|a2|),
    designs are grouped by that radius so a batch runs only as long as
    its slowest member needs, and whatever is still moving at the end is
    BOUNDED AND ADDED -- (|h[n]| + |h[n-1]|) * r / (1-r) -- so the result
    is an upper bound and never a truncation that flatters RIG C."""
    n = len(cf)
    arr = np.asarray(cf, dtype=np.float64)
    # The LARGER pole radius, not sqrt|a2|. sqrt|a2| is the GEOMETRIC MEAN
    # of the two roots and equals the radius only for a conjugate pair;
    # for REAL roots -- every low-Q design -- it under-reads the slow one,
    # which shortens the run AND shrinks the tail term. Both errors are in
    # the unsafe direction for a bound whose whole job is to be an upper
    # one (found 2026-09-03 while validating the load-time sizer against
    # this function: 1,140 of 37,105 sets came out under it).
    disc = arr[:, 3] ** 2 - 4.0 * arr[:, 4]
    r = np.where(disc <= 0.0,
                 np.sqrt(np.abs(arr[:, 4])),
                 0.5 * (np.abs(arr[:, 3]) + np.sqrt(np.maximum(disc, 0.0))))
    r = np.minimum(r, 1 - 1e-12)
    want = np.minimum(nmax, np.ceil(25.0 / (1.0 - r)) + 4).astype(np.int64)
    order = np.argsort(want)
    out = np.zeros(n)
    tfr = np.zeros(n)
    step = 4000
    for s0 in range(0, n, step):
        idx = order[s0:s0 + step]
        a = arr[idx]
        b0, b1, b2, a1, a2 = (a[:, i].copy() for i in range(5))
        N = int(want[idx].max())
        h1 = b0.copy()
        acc = np.abs(b0)
        h2 = np.zeros_like(b0)
        h = b1 - a1 * h1
        acc += np.abs(h); h2, h1 = h1, h
        h = b2 - a1 * h1 - a2 * h2
        acc += np.abs(h); h2, h1 = h1, h
        for _ in range(3, N):
            h = -a1 * h1 - a2 * h2
            acc += np.abs(h)
            h2, h1 = h1, h
        rr = r[idx]
        tail = (np.abs(h1) + np.abs(h2)) * rr / (1.0 - rr)
        out[idx] = acc + tail
        tfr[idx] = tail / np.maximum(acc, 1e-300)
    return out, tfr


def bits_for(x):
    """Headroom bits a Q4.28 word needs to hold x * (0 dBFS) without
    wrapping, given its ceiling of 8.0."""
    return np.maximum(0.0, np.ceil(np.log2(np.maximum(x, 1e-30) / CEIL)))


def sweep(quick):
    designs = list(design_space(*(41, 21, 15) if quick else (61, 31, 21)))
    cf = [d[0] for d in designs]
    tags = [d[1] for d in designs]
    print(f'design space: {len(cf)} coefficient sets '
          f'(bound_efb.design_space, the DEFS ranges)')
    mh = max_abs_H(cf)
    l1, tailfrac = l1_norm(cf)
    return tags, np.asarray(mh), np.asarray(l1), np.asarray(tailfrac)


def report(tags, mh, l1, tailfrac):
    print()
    print('  BOUND ON THE STAGE OUTPUT y (= the recursive state, in DF-I),')
    print('  for a 0 dBFS (1.0) input, against Q4.28\'s ceiling of 8.0:')
    print()
    print(f'    {"":22s} {"worst":>12s} {"as dB":>9s} {"headroom bits":>14s}')
    for name, v in (('max|H|  (sine drive)', mh),
                    ('||h||_1 (worst case)', l1)):
        i = int(np.argmax(v))
        print(f'    {name:22s} {v[i]:12.2f} {20*math.log10(v[i]):9.2f} '
              f'{int(bits_for(v[i])):14d}   at {tags[i]}')
    print()
    print(f'    l1 tail still moving at n = {NMAX}: worst '
          f'{tailfrac.max()*100:.4f}% of the sum (added, not dropped)')
    print()
    # How much of the space needs ANY headroom at all.
    for name, v in (('max|H|', mh), ('||h||_1', l1)):
        need = bits_for(v)
        tot = len(v)
        print(f'    {name:8s}: {int((need > 0).sum()):7d} of {tot} sets '
              f'({100*(need>0).mean():5.1f}%) exceed 8.0 on a 0 dBFS input; '
              f'worst needs {int(need.max())} bits')
    print()
    print('  WHERE IT BITES, by design family (worst ||h||_1 headroom bits):')
    fams = {}
    need = bits_for(l1)
    for t, n, v in zip(tags, need, l1):
        k = t[0]
        if k not in fams or v > fams[k][1]:
            fams[k] = (int(n), v, t)
    for k in sorted(fams):
        n, v, t = fams[k]
        print(f'    {k:8s} {n:2d} bits  ||h||_1 = {v:9.2f}  at '
              f'f0={t[1]:8.1f} Hz gain={t[2]} Q={t[3]:.3f}')
    print()
    print('  AND THE Q/GAIN DEPENDENCE, which is the answer to "which')
    print('  designs": peaking, at the frequency that is worst for each.')
    print(f'    {"gain dB":>8s}' + ''.join(f'{q:>9.2f}' for q in
                                           (0.1, 0.5, 1.0, 2.0, 5.0, 10.0)))
    for g in (3.0, 6.0, 9.0, 12.0, 15.0):
        row = []
        for q in (0.1, 0.5, 1.0, 2.0, 5.0, 10.0):
            best = 0.0
            for f0 in (20.0, 40.0, 80.0, 200.0, 1000.0, 5000.0, 15000.0):
                v, _ = l1_norm([peaking(f0, g, q)], nmax=200000)
                best = max(best, float(v[0]))
            row.append(best)
        print(f'    {g:8.1f}' + ''.join(f'{v:9.2f}' for v in row))


def imp_resp(cf_list, n):
    """Impulse response of a CASCADE, stage by stage, as float64."""
    x = np.zeros(n)
    x[0] = 1.0
    for (b0, b1, b2, a1, a2) in cf_list:
        y = np.empty(n)
        x1 = x2 = y1 = y2 = 0.0
        for i in range(n):
            v = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, x[i]
            y2, y1 = y1, v
            y[i] = v
        x = y
    return x


def cascades(n=60000):
    """Where the headroom actually goes: the PARTIAL cascade.

    Round-once clamps at the cascade OUTPUT, so every intermediate --
    the output of band 1, of bands 1-2, of bands 1-3 -- has to be
    representable too, and a boost cascade's intermediates are the
    growing part. What is reported per case is the WORST partial
    cascade, because that is what sizes the internal format."""
    print()
    print('  THE CASCADES, which is where the headroom actually goes.')
    print('  Round-once clamps at the cascade OUTPUT, so every PARTIAL')
    print('  cascade has to be representable as well.')
    print()
    cases = []
    # 4-band channel/aux/main PEQ, all bands coherent at one f0, +15 dB.
    for q in (0.5, 2.0, 10.0):
        for f0 in (60.0, 1000.0):
            cases.append((f'PEQ 4x +15 dB Q{q:g} @{f0:g} Hz',
                          [peaking(f0, 15.0, q)] * 4))
    # HPF 36 dB/oct (three cascaded biquads) + LPF, the FILT node.
    cases.append(('FILT HPF 20 Hz 36 dB/oct + LPF 20 kHz',
                  [hplp(20.0, q, True) for q in (0.5177, 0.7071, 1.9319)]
                  + [hplp(20000.0, 0.7071, False)]))
    # 28-band GEQ all up: the biggest cascade in the product.
    third = [24.803 * (2 ** (k / 3.0)) for k in range(28)]
    cases.append(('GEQ 28 x +12 dB (1/3 oct, Q 4.32)',
                  [peaking(f, 12.0, 4.32) for f in third]))
    cases.append(('GEQ 28 x +12 dB alternating sign',
                  [peaking(f, 12.0 if k % 2 == 0 else -12.0, 4.32)
                   for k, f in enumerate(third)]))
    print(f'    {"case":42s} {"stages":>6s} {"worst partial":>14s} '
          f'{"dB":>8s} {"bits":>5s}')
    for name, cf in cases:
        worst = 0.0
        for k in range(1, len(cf) + 1):
            h = imp_resp(cf[:k], n)
            worst = max(worst, float(np.abs(h).sum()))
        print(f'    {name:42s} {len(cf):6d} {worst:14.2f} '
              f'{20*math.log10(worst):8.2f} {int(bits_for(worst)):5d}')


def wrap_demo():
    """The wrap, on a setting the product allows, shown as samples.

    Driven by the input that ACHIEVES ||h||_1 -- x[n] = X*sign(h[N-n]),
    the matched sign pattern -- because that is the input the bound is
    about. A square wave at f0 reaches max|H| and not ||h||_1, which is
    exactly why sizing headroom off an EQ curve is the mistake this
    script exists to price.

    Round-once model: the same offset-form accumulation, the same
    round-to-nearest at 28 bits, but the extracted word WRAPS instead of
    saturating -- which is what `r0 = r0 or lshift r3 by 4` in
    _bqc_cascade_blk does. No error feedback, because there is no
    remainder to carry when nothing was clipped away."""
    print()
    print('  THE WRAP, DEMONSTRATED (not asserted).')

    def bq_round_once(x, cq, st):
        b0, n1h, n2, c1, c2 = cq
        x1, x2, y1, y2 = st
        acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
               - c1 * y1 + c2 * y2 + ((2 * y1 - y2) << QB))
        y = fr.rns(acc, QB)
        y = ((y + (1 << 31)) & 0xFFFFFFFF) - (1 << 31)     # WRAP, no clamp
        st[0], st[1] = x, x1
        st[2], st[3] = y, y1
        return y

    full = 1 << QB                        # 0 dBFS
    for cf, label in ((shelf(20.0, 12.0, 5.0119, False),
                       'HF shelf +12 dB Q5.01 @20 Hz (the worst set in '
                       'the space)'),
                      (peaking(5023.8, 15.0, 0.1, ),
                       'peak +15 dB Q0.10 @5 kHz')):
        cq = fr.biquad_coeffs_q(*cf)
        n = 40000
        h = imp_resp([cf], n)
        drive = np.sign(h[::-1])
        drive[drive == 0] = 1.0
        st_a, st_b = [0, 0, 0, 0, 0], [0, 0, 0, 0]
        worst_a = worst_b = 0
        flips = 0
        for i in range(n):
            x = int(full * drive[i])
            ya = fr.biquad(x, cq, st_a)
            yb = bq_round_once(x, cq, st_b)
            worst_a = max(worst_a, abs(ya))
            worst_b = max(worst_b, abs(yb))
            if (ya > 0) != (yb > 0) and abs(ya) > full // 4:
                flips += 1
        print(f'    {label}')
        print(f'      matched-sign drive at 0 dBFS, {n} samples')
        print(f'      contract (saturating): peak |y| = {worst_a/full:8.3f} '
              f'x 0 dBFS  (clamps at {CEIL:.3f})')
        print(f'      round-once (wrapping): peak |y| = {worst_b/full:8.3f} '
              f'x 0 dBFS, {flips} samples of OPPOSITE SIGN to the contract')


def main():
    quick = '--quick' in sys.argv
    tags, mh, l1, tf = sweep(quick)
    report(tags, mh, l1, tf)
    cascades()
    wrap_demo()
    print()
    print('  THE GUARD, and why the cheap ones do not work:')
    print('   * A per-CASCADE clamp does not help: the wrap happens INSIDE,')
    print('     in y1/y2, and is fed back before the cascade output exists.')
    print('   * A per-STAGE clamp on y IS the guard -- and it is exactly the')
    print('     six instructions round-once deletes, so it gives the cycles')
    print('     straight back (bqshoot rung 2 vs rung 6/8).')
    print('   * HEADROOM sized on ||h||_1, not on max|H|, is the guard that')
    print('     keeps the cycles. The bits above are what it costs, and')
    print('     tools/dsp/roundonce_noise.py turns them into noise floor.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
