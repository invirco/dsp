"""xover_ref — the NORMATIVE model for the main crossover's design.

The CROSSOVER node is a real pair of two-stage cascades -- an LP path and
an HP path, each with its own state and its own dual-instance crossfade
-- and like the graphic EQ it had never been given coefficients. Measured
on the part 2026-09-08: the landed cell wrote into
`_xover_coeffs_next[0]`, one word of a twenty-word staging array, nothing
raised the swap, and both banks stayed at their compiled identity while
the node copied its input to all four outputs.

THE FILTER IS LINKWITZ-RILEY 4th ORDER, which is two cascaded
2nd-order BUTTERWORTH sections (Q = 1/sqrt(2)) at the same corner, on
each path. That is what the node's shape already committed to: two
stages of LP and two of HP, no more and no fewer. LR4 is the standard
choice for a main/sub split -- the two paths sum flat in magnitude and
both are 6 dB down at the corner, so the acoustic sum has no bump.

WHAT THE KERNEL EVALUATES. RBJ lowpass and highpass share a denominator,
and in the offset encoding almost everything falls out exactly:

    x  = 2*pi*f0/fs
    s  = sin x
    u  = 1 - cos x                  <- computed from its OWN series
    al = s / (2Q) = s / sqrt(2)
    inv = 1/(1 + al)

    LP:  b0 = (u/2)*inv     n1 = 2u*inv     n2 = 0
    HP:  b0 = ((2-u)/2)*inv n1 = 0          n2 = 0
    both: c1 = (2u + 2al)*inv       c2 = 2al*inv

n2 is EXACTLY ZERO on both paths and n1 is exactly zero on the highpass;
those are identities of the RBJ forms, not approximations, and the
kernel writes the zeros rather than computing them.

u IS COMPUTED FROM ITS OWN SERIES AND THAT IS THE POINT. Over the
contract's 50-500 Hz the corner is 0.0065-0.065 radians, so cos x is
between 0.9979 and 0.99998 and forming `1 - cos x` in float32 would keep
about four significant digits of a quantity the whole pole placement
depends on. u = x^2/2 - x^4/24 + x^6/720 has no cancellation in it at
all. Same reason `geq_ref` carries k2 as a constant rather than k + 2.

THE DOMAIN IS THE CONTRACT'S, 50-500 Hz (Table `0=50/127=500/[Log]`),
AND A WORD OUTSIDE IT IS IGNORED RATHER THAN CLAMPED -- and so is a
slope that is not 12 or 24. Ignoring leaves the split where the last
legal pair put it.

That rule was written for a defect and outlived it. Until 2026-09-09
`MainL001CrossoverFreq001` and `MainL001CrossoverSlope001` -- and the
Ctr, R and Sub pairs with them -- ALL RESOLVED TO ONE ADDRESS: eight
cells, one word. A slope is a small number whatever its encoding, so
clamping it into the frequency would have moved the crossover to 50 Hz
every time the host set a slope, and THE SLOPE WAS NOT SETTABLE AT ALL.
The slope now has its own word (the node's second), proposed with the
31-band GEQ re-layout; the ignore-don't-clamp rule stays because it is
the right answer for 6 and 18 dB/oct too.
"""

import math

FS = 48000.0
XOVER_Q = 1.0 / math.sqrt(2.0)        # Butterworth; LR4 = two of them
XOVER_F_MIN = 50.0                    # Table 0=50/127=500/[Log]
XOVER_F_MAX = 500.0
XOVER_STAGES = 2                      # per path

# THE SLOPE, a real word since 2026-09-09 -- the crossover node's second
# word, which the 31-band re-layout puts at 0x059D
# (MW/D32/DSP/dsp4-geq31-relayout-20260909.md; the design argument is in
# MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md §A). Two of the four values in
# the cell's table are HONOURED and two are IGNORED, and the split is not
# arbitrary: 24 and 12 are the even-order Linkwitz-Riley alignments a
# node with two stages per path can hold, each path 6 dB down at the
# corner and the two summing flat. 6 dB/oct is a 1st-order pair -- it
# sums flat but each path is 3 dB down, a different acoustic contract --
# and 18 dB/oct is 3rd-order, not a Linkwitz-Riley alignment at all.
# An unsupported slope leaves the split where it was, which is the rule
# an out-of-domain FREQUENCY already gets.
XOVER_SLOPES = {24: (1.0 / math.sqrt(2.0), True),   # LR4: Q, second stage is a copy
                12: (0.5, False)}                   # LR2: Q, second stage is the identity


def sin_series(x):
    """sin x on |x| <= 0.3, the kernel's polynomial."""
    x2 = x * x
    return x * (1.0 - x2 / 6.0 * (1.0 - x2 / 20.0))


def vercos_series(x):
    """1 - cos x, computed WITHOUT forming cos x. The kernel's."""
    x2 = x * x
    return x2 / 2.0 * (1.0 - x2 / 12.0 * (1.0 - x2 / 30.0))


def in_domain(f0):
    return XOVER_F_MIN <= f0 <= XOVER_F_MAX


def design(f0, fs=FS, series=True, slope=24):
    """(lp5, hp5) in the float arm's offset encoding, one stage each.

    At 24 dB/oct both stages of a path are identical -- that IS
    Linkwitz-Riley 4 -- so the staging array is lp5 twice then hp5
    twice. At 12 the second stage of each path is the compiled identity;
    `design_set` is what assembles either.
    """
    if not in_domain(f0):
        raise ValueError('crossover %.3f Hz is outside the contract domain '
                         '%.0f..%.0f Hz' % (f0, XOVER_F_MIN, XOVER_F_MAX))
    if slope not in XOVER_SLOPES:
        raise ValueError('crossover slope %r is not a Linkwitz-Riley '
                         'alignment this node can hold (12 or 24)' % (slope,))
    q, _ = XOVER_SLOPES[slope]
    x = 2.0 * math.pi * f0 / fs
    if series:
        s = sin_series(x)
        u = vercos_series(x)
    else:
        s = math.sin(x)
        u = 1.0 - math.cos(x)
    al = s / (2.0 * q)
    inv = 1.0 / (1.0 + al)
    c1 = (2.0 * u + 2.0 * al) * inv
    c2 = (2.0 * al) * inv
    lp = ((u / 2.0) * inv, (2.0 * u) * inv, 0.0, c1, c2)
    hp = (((2.0 - u) / 2.0) * inv, 0.0, 0.0, c1, c2)
    return lp, hp


IDENTITY = (1.0, 2.0, -1.0, 2.0, 1.0)


def design_set(f0, fs=FS, series=True, slope=24):
    """The 20 words `_xover_coeffs_next` must hold: LP, LP, HP, HP."""
    lp, hp = design(f0, fs, series, slope)
    _, two = XOVER_SLOPES[slope]
    second_lp = list(lp) if two else list(IDENTITY)
    second_hp = list(hp) if two else list(IDENTITY)
    return list(lp) + second_lp + list(hp) + second_hp


def direct(c):
    """Offset -> direct (b0, b1, b2, a1, a2), for a response check."""
    b0, n1, n2, c1, c2 = c
    return (b0, n1 - 2.0 * b0, n2 + b0, c1 - 2.0, 1.0 - c2)


def check(verbose=False):
    """The series against libm, and the design against RBJ, over the
    domain -- plus the two properties that say it is really LR4."""
    import cmath
    worst_s = worst_d = 0.0
    for i in range(0, 91):
        f0 = XOVER_F_MIN * (XOVER_F_MAX / XOVER_F_MIN) ** (i / 90.0)
        x = 2.0 * math.pi * f0 / FS
        worst_s = max(worst_s,
                      abs(sin_series(x) - math.sin(x)) / abs(math.sin(x)),
                      abs(vercos_series(x) - (1.0 - math.cos(x)))
                      / abs(1.0 - math.cos(x)))
        a = design_set(f0, series=True)
        b = design_set(f0, series=False)
        for p, q in zip(a, b):
            worst_d = max(worst_d, abs(p - q) / max(abs(q), 1e-12))

    # RBJ, written out plainly, must give the same filter.
    worst_r = 0.0
    for f0 in (50.0, 80.0, 120.0, 250.0, 500.0):
        w = 2.0 * math.pi * f0 / FS
        al = math.sin(w) / (2.0 * XOVER_Q)
        cw = math.cos(w)
        a0 = 1.0 + al
        lp_d = ((1 - cw) / 2 / a0, (1 - cw) / a0, (1 - cw) / 2 / a0,
                -2 * cw / a0, (1 - al) / a0)
        hp_d = ((1 + cw) / 2 / a0, -(1 + cw) / a0, (1 + cw) / 2 / a0,
                -2 * cw / a0, (1 - al) / a0)
        lp, hp = design(f0, series=False)
        for got, want in ((direct(lp), lp_d), (direct(hp), hp_d)):
            for p, q in zip(got, want):
                worst_r = max(worst_r, abs(p - q) / max(abs(q), 1e-12))

    # LR4: each path is 6 dB down at the corner, and the two sum flat.
    worst_c = worst_sum = 0.0
    for f0 in (50.0, 120.0, 500.0):
        cs = design_set(f0)
        lp = _resp(cs[:10], f0)
        hp = _resp(cs[10:], f0)
        worst_c = max(worst_c, abs(20 * math.log10(abs(lp)) + 6.0206),
                      abs(20 * math.log10(abs(hp)) + 6.0206))
        for k in range(-24, 25):
            f = f0 * 2.0 ** (k / 4.0)
            if not 10.0 < f < FS / 2:
                continue
            tot = abs(_resp(cs[:10], f) + _resp(cs[10:], f))
            worst_sum = max(worst_sum, abs(20 * math.log10(tot)))
    if verbose:
        print('sin/vercos series vs libm, worst relative:   %.3e' % worst_s)
        print('series design vs libm design, worst:         %.3e' % worst_d)
        print('design vs RBJ written out, worst:            %.3e' % worst_r)
        print('each path at the corner, worst |dB + 6.02|:  %.3e' % worst_c)
        print('LP + HP magnitude sum, worst |dB|:           %.3e' % worst_sum)
    assert worst_s < 1e-10 and worst_d < 1e-9, 'series too coarse'
    assert worst_r < 1e-12, 'not the RBJ filter'
    assert worst_c < 1e-6, 'not 6 dB down at the corner'
    assert worst_sum < 1e-6, 'the two paths do not sum flat'
    return worst_d


def _resp(coeffs_offset, f, fs=FS):
    import cmath
    z = cmath.exp(-2j * math.pi * f / fs)
    h = 1.0 + 0j
    for i in range(0, len(coeffs_offset), 5):
        b0, b1, b2, a1, a2 = direct(coeffs_offset[i:i + 5])
        h *= (b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)
    return h


if __name__ == '__main__':
    check(verbose=True)
    print('')
    print('%-8s %-12s %-12s %-12s' % ('f0 Hz', 'LP b0', 'c1', 'c2'))
    for f0 in (50.0, 80.0, 120.0, 250.0, 500.0):
        lp, hp = design(f0)
        print('%-8.1f %-12.9f %-12.9f %-12.9f' % (f0, lp[0], lp[3], lp[4]))
