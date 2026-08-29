#!/usr/bin/env python3
"""bound_efb.py — bound the biquad error-feedback store-back (review D2).

The SHARC cascade keeps the stage remainder efb = acc - (y<<28) exactly
in the 80-bit MRF but STORES it as a 64-bit pair, discarding MR2F
(lib/biquad_fx.asm). This script produces the numbers recorded in
shared/numeric-spec.md under "Wide-accumulator bounds":

  1. the pessimistic bound  |acc| <= 8 * S * 2^56, S = 4|b0|+|n1|+|n2|
     +|c1|+|c2|+3, maximised over the product's design space;
  2. the REACHABLE bound, by driving the worst coefficient sets with
     full-scale adversarial input through fixed_ref.biquad (which is
     unbounded, so it shows what the 64-bit store would have to hold);
  3. the design-space corner where a Q4.28 coefficient saturates at
     conversion.

Usage: python3 bound_efb.py [--quick]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr

FS = 48000.0
FULL = fr.I32_MAX

# DEFS ranges (ghost_cells.c): EqFreq 20..20000 Log, EqGain -15..+15 Lin,
# EqQ 0.1..10 Log, Hpf 20..1000, Lpf 1000..20000.
F_LO, F_HI = 20.0, 20000.0
G_LO, G_HI = -15.0, 15.0
Q_LO, Q_HI = 0.1, 10.0


def peaking(f0, g, q):
    a = 10 ** (g / 40.0)
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    a0 = 1 + al / a
    return ((1 + al * a) / a0, (-2 * math.cos(w0)) / a0, (1 - al * a) / a0,
            (-2 * math.cos(w0)) / a0, (1 - al / a) / a0)


def shelf(f0, g, q, low=True):
    a = 10 ** (g / 40.0)
    w0 = 2 * math.pi * f0 / FS
    t = (a + 1 / a) * (1 / q - 1) + 2
    if t <= 0:
        return None
    al = math.sin(w0) / 2 * math.sqrt(t)
    c, s = math.cos(w0), 2 * math.sqrt(a) * al
    if low:
        b = (a * ((a + 1) - (a - 1) * c + s), 2 * a * ((a - 1) - (a + 1) * c),
             a * ((a + 1) - (a - 1) * c - s))
        d = ((a + 1) + (a - 1) * c + s, -2 * ((a - 1) + (a + 1) * c),
             (a + 1) + (a - 1) * c - s)
    else:
        b = (a * ((a + 1) + (a - 1) * c + s), -2 * a * ((a - 1) + (a + 1) * c),
             a * ((a + 1) + (a - 1) * c - s))
        d = ((a + 1) - (a - 1) * c + s, 2 * ((a - 1) - (a + 1) * c),
             (a + 1) - (a - 1) * c - s)
    return (b[0] / d[0], b[1] / d[0], b[2] / d[0], d[1] / d[0], d[2] / d[0])


def hplp(f0, q, hp):
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    b = ((1 + c) / 2, -(1 + c), (1 + c) / 2) if hp else \
        ((1 - c) / 2, (1 - c), (1 - c) / 2)
    a0 = 1 + al
    return (b[0] / a0, b[1] / a0, b[2] / a0, -2 * c / a0, (1 - al) / a0)


def s_metric(cq):
    """Sum of coefficient magnitudes, weighted by how often each is MACed."""
    q = lambda v: v / (1 << fr.QB)
    b0, n1, n2, c1, c2 = cq
    return 4 * abs(q(b0)) + abs(q(n1)) + abs(q(n2)) + abs(q(c1)) + abs(q(c2)) + 3


def design_space(nf=121, ng=61, nq=41):
    """Every quantised coefficient set the DEFS ranges allow."""
    freqs = [F_LO * (F_HI / F_LO) ** (i / (nf - 1)) for i in range(nf)]
    qs = [Q_LO * (Q_HI / Q_LO) ** (i / (nq - 1)) for i in range(nq)]
    gains = [G_LO + (G_HI - G_LO) * i / (ng - 1) for i in range(ng)]
    for f0 in freqs:
        for g in gains:
            for q in qs:
                for cf, tag in ((peaking(f0, g, q), 'peak'),
                                (shelf(f0, g, q, True), 'lshelf'),
                                (shelf(f0, g, q, False), 'hshelf')):
                    if cf is not None:
                        yield cf, (tag, f0, g, q)
        for q in (0.5, 0.707, 1.0, 2.0, 4.0, 10.0):
            yield hplp(f0, q, True), ('hp', f0, None, q)
            yield hplp(f0, q, False), ('lp', f0, None, q)


def main():
    quick = '--quick' in sys.argv
    worst_s = (0.0, None, None)
    saturating = 0
    total = 0
    for cf, tag in design_space(*(61, 31, 21) if quick else (121, 61, 41)):
        cq = fr.biquad_coeffs_q(*cf)
        total += 1
        if any(v in (fr.I32_MAX, fr.I32_MIN) for v in cq):
            saturating += 1
        s = s_metric(cq)
        if s > worst_s[0]:
            worst_s = (s, tag, cq)
    s, tag, cq = worst_s
    print(f'design space: {total} quantised coefficient sets')
    print(f'  {saturating} of them SATURATE a Q4.28 coefficient at conversion')
    print(f'  worst S = {s:.3f} at {tag}')
    print(f'  pessimistic |acc| <= 8*S*2^56 = 2^{math.log2(8 * s) + 56:.3f} '
          f'(store range 2^63)')

    # Reachable bound: full-scale adversarial drive on the worst sets.
    random.seed(7)
    n = 20000 if quick else 200000
    best = (0, None, None)
    cands = [(f0, 15.0, q)
             for f0 in (8933.7, 10023.7, 11246.8, 12619.1, 14158.9, 15886.6)
             for q in (0.1, 0.12, 0.15)]
    for f0, g, q in cands:
        cq = fr.biquad_coeffs_q(*peaking(f0, g, q))
        per = max(2, int(round(FS / f0)))
        for mode in ('rand', 'sq', 'dc'):
            st = fr.biquad_state()
            mx = 0
            for i in range(n):
                if mode == 'rand':
                    x = FULL if random.getrandbits(1) else -FULL
                elif mode == 'sq':
                    x = FULL if (i // (per // 2)) % 2 == 0 else -FULL
                else:
                    x = FULL
                fr.biquad(x, cq, st)
                mx = max(mx, abs(st[4]))
            if mx > best[0]:
                best = (mx, (f0, g, q), mode)
    mx, tag, mode = best
    print(f'reachable worst |efb| = 2^{math.log2(mx):.3f} '
          f'({tag}, {mode} drive, {n} samples)')
    print(f'  margin to the 64-bit store: {2 ** 63 / mx:.3f}x '
          f'= {math.log2(2 ** 63 / mx):.3f} bits')
    print(f'  non-saturating bound is 2^27, so {math.log2(mx) - 27:.1f} bits '
          f'of the growth is attributable to output saturation')
    return 0 if mx < (1 << 63) else 1


if __name__ == '__main__':
    sys.exit(main())
