"""geq_ref — the NORMATIVE model for the graphic EQ's BAND DESIGN.

The GEQ kernel has always been a real N-stage biquad cascade. What did
not exist, anywhere, was the step that turns the thing the contract
carries -- ONE number per band, a gain in dB -- into the five
coefficients a stage needs. `defs/products/d24/dsp.csv` gives
`Aux001Geq001..028` one address each with the Table domain
`0=-12/127=12/[Lin]`, and 28 addresses cannot carry the 140 coefficient
words plus a trigger that the host-computes-coefficients arrangement
(EQ_BIQUAD's) needs. The design therefore belongs ON THE DSP, and this
file is the model it is scored against.

THE BAND SET IS THE ISO R.40 THIRD-OCTAVE SERIES, base 10, anchored at
1 kHz:

    f_i = 1000 * 10 ** ((i - 17) / 10)      i = 0 .. bands-1

so 31 bands are 19.95 Hz .. 19,953 Hz -- the nominal 20 Hz .. 20 kHz
third-octave set, which is PW's market bar. A `bands` smaller than 31
takes the LOWEST `bands` of that same series and loses the top end;
the shipping 28-band graph therefore runs 19.95 Hz .. 10 kHz. That is a
consequence of the band count, it is not a separate band layout, and it
is stated here rather than left to be inferred from a table.

Q IS THE EXACT CONSTANT-Q THIRD-OCTAVE VALUE:

    Q = 1 / (2**(1/6) - 2**(-1/6)) = 4.3185...

`bq_float_ref.CASES` has carried 4.3 as the GEQ test-vector Q since the
cascade work; that is the same number rounded, and the vectors are not
affected by this file.

EACH BAND IS AN RBJ PEAKING SECTION -- `bq_float_ref.rbj_peak(f, Q, g)`,
the same design every other filter family in this tree uses. Nothing new
is invented here; what is new is only that a gain in dB now reaches it.

WHAT THE KERNEL EVALUATES, and why it is written this way. With f0 and Q
fixed per band, only A = 10**(g/40) moves, so the design reduces to two
per-band CONSTANTS and a short expression:

    alpha = sin(w0) / (2Q)              per-band constant
    k     = -2 * cos(w0)                per-band constant
    A     = 10 ** (g / 40)              the only runtime transcendental
    inv   = 1 / (1 + alpha / A)
    b0 = (1 + alpha*A) * inv    b1 = k * inv    b2 = (1 - alpha*A) * inv
    a1 = b1                     a2 = (1 - alpha/A) * inv

a1 and b1 are the SAME WORD, which the kernel exploits. The coefficients
are then written in the float arm's offset encoding -- b0, n1 = b1+2b0,
n2 = b2-b0, c1 = 2+a1, c2 = 1-a2 -- because that is what
`_bq_fx_convert_N` copies straight through under DSP4_BQ_FLOAT and what
the cascade's prologue reconstructs from.

A FLAT BAND IS THE TRIVIAL IDENTITY, NOT THE CANCELLING ONE. At 0 dB
the expression above gives b == a exactly -- a real identity, but one
built from a pole and a zero sitting on top of each other near the unit
circle. Twenty-eight of those in series, on every one of seventeen
nodes, is measurable recursion noise bought for nothing, and it would
also mean a GEQ nobody has touched no longer passes its input word for
word. So |g| below GEQ_FLAT_EPS (1/256 dB, exactly representable in
binary) designs to (1, 0, 0, 0, 0) instead. The response step that
introduces is under 0.004 dB, an order below the 0.046 dB response bar
the harness scores biquads against, and the DSP applies the SAME test
with the SAME constant.

THE DOMAIN IS +/-12 dB and it is CLAMPED, loudly at generation time and
silently on the part. The Table column says so; a GEQ band asked for
+40 dB is a host fault, and the kernel's job is to stay stable rather
than to diagnose it. `design_band` raises instead, so a model run that
would have gone out of domain cannot pass quietly.
"""

import math

FS = 48000.0
GEQ_BANDS_MAX = 31
GEQ_GAIN_LIMIT = 12.0
GEQ_FLAT_EPS = 1.0 / 256.0        # 0.00390625 dB — exact in binary

# Exact constant-Q third-octave: BW = f0 * (2**(1/6) - 2**(-1/6)).
GEQ_Q = 1.0 / (2.0 ** (1.0 / 6.0) - 2.0 ** (-1.0 / 6.0))


def centre(i):
    """ISO R.40 third-octave centre for band index i (0-based, 31 = 20k)."""
    if not 0 <= i < GEQ_BANDS_MAX:
        raise ValueError('GEQ band index %d outside 0..%d'
                         % (i, GEQ_BANDS_MAX - 1))
    return 1000.0 * 10.0 ** ((i - 17) / 10.0)


def centres(bands):
    return [centre(i) for i in range(bands)]


def band_consts(i, fs=FS):
    """(alpha, k) -- everything about band i that does not move with gain."""
    w0 = 2.0 * math.pi * centre(i) / fs
    return (math.sin(w0) / (2.0 * GEQ_Q), -2.0 * math.cos(w0))


def design_band(i, gain_db, fs=FS):
    """Band i at `gain_db` -> direct-form (b0, b1, b2, a1, a2), a0 = 1.

    Bit-for-bit the same filter as bq_float_ref.rbj_peak(centre(i),
    GEQ_Q, gain_db) up to floating-point association; `check()` asserts
    that, so the two cannot drift apart.
    """
    if abs(gain_db) > GEQ_GAIN_LIMIT + 1e-9:
        raise ValueError('GEQ band gain %.3f dB is outside the contract '
                         'domain +/-%.1f dB (Table 0=-12/127=12)'
                         % (gain_db, GEQ_GAIN_LIMIT))
    if abs(gain_db) < GEQ_FLAT_EPS:
        return (1.0, 0.0, 0.0, 0.0, 0.0)
    alpha, k = band_consts(i, fs)
    a = 10.0 ** (gain_db / 40.0)
    inv = 1.0 / (1.0 + alpha / a)
    b0 = (1.0 + alpha * a) * inv
    b1 = k * inv
    b2 = (1.0 - alpha * a) * inv
    a2 = (1.0 - alpha / a) * inv
    return (b0, b1, b2, b1, a2)


def offset_form(c):
    """Direct form -> the float arm's wire encoding (b0, n1, n2, c1, c2)."""
    b0, b1, b2, a1, a2 = c
    return (b0, b1 + 2.0 * b0, b2 - b0, 2.0 + a1, 1.0 - a2)


def design_set(gains, fs=FS):
    """A whole GEQ, offset-encoded, flattened -- what `_geq_coeffs_next`
    must hold after the design step has run."""
    out = []
    for i, g in enumerate(gains):
        out.extend(offset_form(design_band(i, g, fs)))
    return out


IDENTITY = (1.0, 2.0, -1.0, 2.0, 1.0)   # offset form of b0=1, rest 0


# ---------------------------------------------------------------------------
# WHAT THE KERNEL ACTUALLY EVALUATES
#
# `design_band` above is the readable form and it is the wrong one to put
# on the part, for one reason: c1 = 2 + a1. At 20 Hz a1 is -1.99999, so
# forming a1 first and then adding 2 is CATASTROPHIC CANCELLATION -- in
# float32 a1 carries about 1.2e-7 of absolute error and c1 is 6.8e-6, so
# the result would be wrong by two percent. That is the exact error the
# offset encoding exists to avoid, thrown away in the step that computes
# it.
#
# The five offset coefficients have a closed form that never subtracts
# two near-equal numbers. With d = 1 + alpha/A and inv = 1/d:
#
#     k2 = 2 * (1 - cos w0)          <- per-band constant, small and exact
#     aA = alpha * A     ia = alpha / A
#     b0 = (1 + aA) * inv
#     n1 = (k2 + 2*aA) * inv         since b1 + 2*b0 = (k + 2 + 2aA) * inv
#     n2 = -2*aA * inv               since b2 - b0   = -2aA * inv
#     c1 = (k2 + 2*ia) * inv         since 2 + k*inv = (k2 + 2ia) * inv
#     c2 = 2*ia * inv                since 1 - a2    = 2ia * inv
#
# k2 = k + 2 exactly, and k2 is computed here in double from 1 - cos w0
# so the small value is never formed by cancelling on the part. Two
# per-band constants (alpha, k2), one reciprocal, eight multiplies.
#
# A = 10**(g/40) = 2**(g * log2(10)/40). Over the contract's +/-12 dB
# domain the exponent is within +/-0.9966, so ONE polynomial on [-1, 1]
# covers it with no range reduction, no table and no branch -- and 2**-u
# comes from the same polynomial rather than from a second reciprocal.
# ---------------------------------------------------------------------------

LOG2_10_OVER_40 = math.log2(10.0) / 40.0

# Degree-8 Chebyshev fit of 2**x on [-1, 1], ascending powers. Produced by
# _fit_exp2() below (numpy); the literal is checked in so generation needs
# no numpy, and check() re-measures it rather than trusting the comment.
EXP2_POLY = (
    1.0000000000097173,
    0.6931471778953535,
    0.24022650642495205,
    0.055504147720470104,
    0.00961813373411475,
    0.001333203659214392,
    0.00015402143791501502,
    1.5469639709683897e-05,
    1.3383537587348823e-06,
)


def _fit_exp2(degree=8, n=200001):
    """Provenance of EXP2_POLY. Needs numpy; nothing in the build calls it."""
    import numpy as np
    x = np.linspace(-1.0, 1.0, n)
    c = np.polynomial.chebyshev.cheb2poly(
        np.polynomial.chebyshev.chebfit(x, 2.0 ** x, degree))
    return tuple(float(v) for v in c)


def exp2_poly(u):
    """2**u for |u| <= 1, by the polynomial the kernel evaluates."""
    acc = 0.0
    for c in reversed(EXP2_POLY):
        acc = acc * u + c
    return acc


def band_consts2(i, fs=FS):
    """(alpha, k2) -- the two constants the kernel holds per band."""
    w0 = 2.0 * math.pi * centre(i) / fs
    return (math.sin(w0) / (2.0 * GEQ_Q), 2.0 * (1.0 - math.cos(w0)))


def kernel_band(i, gain_db, fs=FS):
    """Band i at `gain_db`, offset-encoded, BY THE KERNEL'S EXPRESSION."""
    if abs(gain_db) < GEQ_FLAT_EPS:
        return IDENTITY
    if abs(gain_db) > GEQ_GAIN_LIMIT:
        gain_db = math.copysign(GEQ_GAIN_LIMIT, gain_db)
    alpha, k2 = band_consts2(i, fs)
    a = exp2_poly(gain_db * LOG2_10_OVER_40)
    a_a = alpha * a
    i_a = alpha / a
    inv = 1.0 / (1.0 + i_a)
    return ((1.0 + a_a) * inv,
            (k2 + 2.0 * a_a) * inv,
            (-2.0 * a_a) * inv,
            (k2 + 2.0 * i_a) * inv,
            (2.0 * i_a) * inv)


def kernel_set(gains, fs=FS):
    out = []
    for i, g in enumerate(gains):
        out.extend(kernel_band(i, g, fs))
    return out


def check(verbose=False):
    """Agreement with bq_float_ref.rbj_peak, over the whole domain.

    The two expressions are algebraically identical and associate
    differently, so this is a tolerance check on double arithmetic, not
    an equality -- 1e-12 relative is four orders tighter than anything
    the float32 wire can carry.
    """
    import bq_float_ref as R
    worst = 0.0
    for i in range(GEQ_BANDS_MAX):
        for g in (-12.0, -9.0, -6.0, -3.0, -0.5, 0.5, 3.0, 6.0, 9.0, 12.0):
            mine = design_band(i, g)
            theirs = R.rbj_peak(centre(i), GEQ_Q, g)
            for a, b in zip(mine, theirs):
                d = abs(a - b) / max(abs(b), 1e-9)
                worst = max(worst, d)
    if verbose:
        print('geq_ref vs bq_float_ref.rbj_peak: worst relative %.3e '
              '(gain != 0)' % worst)
        print('flat band is the compiled identity: %s'
              % (tuple(offset_form(design_band(0, 0.0))) == IDENTITY))
    assert worst < 1e-12, 'geq_ref diverges from rbj_peak by %.3e' % worst
    for i in range(GEQ_BANDS_MAX):
        flat = offset_form(design_band(i, 0.0))
        for a, b in zip(flat, IDENTITY):
            assert abs(a - b) < 1e-12, 'band %d at 0 dB is not identity' % i

    # The kernel expression against the readable one. This is the check
    # that matters: it is what says the cancellation-free rearrangement
    # is the SAME filter, and it holds the polynomial's error to a bound
    # the float32 wire cannot resolve.
    kworst = 0.0
    pworst = 0.0
    for u in [x / 1000.0 for x in range(-1000, 1001)]:
        pworst = max(pworst, abs(exp2_poly(u) - 2.0 ** u) / 2.0 ** u)
    for i in range(GEQ_BANDS_MAX):
        for g in (-12.0, -7.5, -3.0, -0.25, 0.25, 3.0, 7.5, 12.0):
            mine = kernel_band(i, g)
            theirs = offset_form(design_band(i, g))
            for a, b in zip(mine, theirs):
                kworst = max(kworst, abs(a - b) / max(abs(b), 1e-9))
    if verbose:
        print('exp2 polynomial worst relative:            %.3e' % pworst)
        print('kernel expression vs direct form, worst:   %.3e' % kworst)
    assert pworst < 1e-8, 'EXP2_POLY worse than advertised: %.3e' % pworst
    assert kworst < 1e-7, 'kernel expression diverges: %.3e' % kworst
    return worst


if __name__ == '__main__':
    import sys
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    check(verbose=True)
    print('%-4s %-10s %-12s %-12s' % ('band', 'f0 Hz', 'alpha', 'k'))
    for i in range(GEQ_BANDS_MAX):
        al, k = band_consts(i)
        print('%-4d %-10.3f %-12.9f %-12.9f' % (i, centre(i), al, k))
