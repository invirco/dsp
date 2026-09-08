"""afb_ref — the NORMATIVE model for the ANTI-FEEDBACK notch design.

THE SAME DISEASE THE GRAPHIC EQ HAD, ON A DIFFERENT BANK. `ANTI_FB` is
a real six-stage biquad cascade with its own dual-instance crossfade,
and the 2026-09-08 family walk measured what it does with the numbers
the contract gives it: `_afb_notch_freq/_gain/_q` take the write and
land correctly (1000.0 Hz, -18.0 dB, Q 4.0, read back off the part),
`_afb_coeffs_next` never moves, both banks stay at their compiled
identity, and every anti-feedback node in the product passes its input
through untouched. `_afb_on` and `_afb_ctrl_on` take their writes and
are read by no emitted line.

`defs/products/d24/dsp.csv` spends eighteen addresses on a node's six
notches -- freq, gain and Q each -- plus `AntiFbOn` and
`AntiFbCtrlOn`. Thirty coefficient words and a swap trigger have no
address to live at, exactly as with the GEQ, so THE DESIGN BELONGS ON
THE DSP and this file is the model it is scored against.

WHAT A NOTCH IS HERE, and why it is a peaking section. A textbook RBJ
`notch` has no depth parameter -- it is infinitely deep at f0 -- and the
contract carries `AntiFbNotchGain` with the domain `0=-18/127=0/[Lin]`.
A depth of -18 dB IS the parameter, so the section that honours the
contract is RBJ PEAKING at negative gain, which is
`bq_float_ref.rbj_peak(f0, Q, g)` -- the same design the parametric EQ,
the graphic EQ and the crossover all use. Nothing new is invented here.
At g = 0 the section is the exact identity, which is what makes "the
notch is off" mean "the sample comes through word for word".

THE DOMAINS ARE THE CONTRACT'S OWN, and they are CLAMPED on the part:

    freq  40 .. 12000 Hz     Table 0=40/127=12000/[Log]
    gain  -18 .. 0 dB        Table 0=-18/127=0/[Lin]
    Q     1 .. 20            Table 0=1/127=20/[Log]

`design_notch` RAISES on an out-of-domain input where the part clamps,
so a model run cannot pass quietly where the part clamped -- geq_ref's
rule, for geq_ref's reason.

WHAT THE KERNEL EVALUATES. Unlike the GEQ, NOTHING is a per-notch
constant: frequency and Q both move, so sin(w0) and 1 - cos(w0) have to
be computed on the part over the whole audio band.

    x   = 2*pi*f0/fs                    0.00524 .. 1.5708 rad
    s   = x * Ps(x*x)                   sin x
    u   = (x*x/2) * Pu(x*x)             1 - cos x
    k2  = 2*u
    al  = s / (2Q)
    A   = 2**(g*log2(10)/40)
    aA  = al*A      ia = al/A      inv = 1/(1 + ia)
    b0  = (1 + aA)*inv
    n1  = (k2 + 2*aA)*inv
    n2  = (-2*aA)*inv
    c1  = (k2 + 2*ia)*inv
    c2  = (2*ia)*inv

which is the float arm's offset encoding (b0, b1+2b0, b2-b0, 2+a1,
1-a2) with every cancellation removed -- geq_ref's derivation, and the
same reason: at 40 Hz a1 is -1.99997 and c1 is 3.4e-5, so forming a1 in
float32 and adding 2 would throw away the quantity the pole placement
rests on.

`1 - cos x` COMES FROM ITS OWN POLYNOMIAL and never from a subtraction.
Over 40 Hz .. 12 kHz cos x runs from 0.999986 down to 0, and at the
bottom of that range a float32 `1 - cos x` keeps four significant
digits of a number the design needs all of. `Pu` is a fit of
(1 - cos x)/(x*x/2), which has no cancellation in it anywhere.

A IS 2**v WITH |v| <= 1.4949 and the exponent polynomial this tree
already carries is fitted on [-1, 1]. Rather than fit a second one,
the kernel evaluates 2**(v/2) -- |v/2| <= 0.7475, comfortably inside
the existing domain -- and SQUARES it, and gets 1/A from 2**(-v/2)
squared rather than from a second reciprocal. The relative error
roughly doubles, to about 4e-9, which is still seventeen times finer
than a float32 ulp.
"""

import math

import geq_ref as _geq

FS = 48000.0

AFB_NOTCHES = 6

AFB_FREQ_MIN = 40.0
AFB_FREQ_MAX = 12000.0
AFB_GAIN_MIN = -18.0
AFB_GAIN_MAX = 0.0
AFB_Q_MIN = 1.0
AFB_Q_MAX = 20.0

AFB_FLAT_EPS = 1.0 / 256.0        # dB — exact in binary, geq_ref's constant

LOG2_10_OVER_40 = _geq.LOG2_10_OVER_40

# The exponent polynomial is geq_ref's, by reference and not by copy:
# one literal for 2**x on [-1, 1] in this repo, emitted into the
# generated tables under each family's own symbol.
EXP2_POLY = _geq.EXP2_POLY

IDENTITY = (1.0, 2.0, -1.0, 2.0, 1.0)   # offset form of b0=1, rest 0

# x runs to 2*pi*12000/48000 = pi/2, so t = x*x runs to (pi/2)**2.
AFB_T_MAX = (math.pi / 2.0) ** 2

# Degree-5 Chebyshev fits on t in [0, (pi/2)**2], ascending powers,
# produced by _fit() below. Checked in so generation needs no numpy;
# check() re-measures both rather than trusting the comment.
SIN_POLY = (
    0.9999999999622449,
    -0.16666666602330965,
    0.008333330722010535,
    -0.00019840845563578202,
    2.752495795838452e-06,
    -2.3889347252326365e-08,
)
VERS_POLY = (
    0.9999999999945809,
    -0.083333333241003,
    0.0027777774030810225,
    -4.9602565974737885e-05,
    5.506823747390353e-07,
    -4.0087845402718825e-09,
)


def _fit(degree=5, n=400001):
    """Provenance of SIN_POLY and VERS_POLY. Needs numpy; nothing in the
    build calls it. Both are fitted in t = x*x, so the odd/even symmetry
    of sin and cos is exact by construction rather than by fit."""
    import numpy as np
    t = np.linspace(0.0, AFB_T_MAX, n)
    x = np.sqrt(t)
    xs = np.where(x == 0, 1.0, x)
    ts = np.where(t == 0, 1.0, t)
    ys = np.where(t > 0, np.sin(x) / xs, 1.0)
    yu = np.where(t > 0, (1.0 - np.cos(x)) / (ts / 2.0), 1.0)
    fit = np.polynomial.chebyshev.chebfit
    to_poly = np.polynomial.chebyshev.cheb2poly
    return (tuple(float(v) for v in to_poly(fit(t, ys, degree))),
            tuple(float(v) for v in to_poly(fit(t, yu, degree))))


def _horner(poly, t):
    acc = 0.0
    for c in reversed(poly):
        acc = acc * t + c
    return acc


def sin_poly(x):
    """sin x by the polynomial the kernel evaluates."""
    return x * _horner(SIN_POLY, x * x)


def vers_poly(x):
    """1 - cos x by the polynomial the kernel evaluates."""
    t = x * x
    return (t / 2.0) * _horner(VERS_POLY, t)


def exp2_poly(u):
    """2**u for |u| <= 1 -- geq_ref's polynomial, by reference."""
    return _geq.exp2_poly(u)


def exp2_wide(v):
    """2**v for |v| <= 2, by squaring the half-argument. The kernel's
    route: one polynomial, two evaluations, no range reduction."""
    h = exp2_poly(v / 2.0)
    return h * h


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def design_notch(freq, gain_db, q, fs=FS):
    """One notch -> direct form (b0, b1, b2, a1, a2), a0 = 1.

    The readable expression, in double, RAISING out of domain. Identical
    to bq_float_ref.rbj_peak(freq, q, gain_db); check() asserts it.
    """
    if not AFB_FREQ_MIN - 1e-9 <= freq <= AFB_FREQ_MAX + 1e-9:
        raise ValueError('ANTI_FB notch frequency %.3f Hz is outside the '
                         'contract domain %g..%g Hz (Table 0=40/127=12000)'
                         % (freq, AFB_FREQ_MIN, AFB_FREQ_MAX))
    if not AFB_GAIN_MIN - 1e-9 <= gain_db <= AFB_GAIN_MAX + 1e-9:
        raise ValueError('ANTI_FB notch gain %.3f dB is outside the contract '
                         'domain %g..%g dB (Table 0=-18/127=0)'
                         % (gain_db, AFB_GAIN_MIN, AFB_GAIN_MAX))
    if not AFB_Q_MIN - 1e-9 <= q <= AFB_Q_MAX + 1e-9:
        raise ValueError('ANTI_FB notch Q %.3f is outside the contract '
                         'domain %g..%g (Table 0=1/127=20)'
                         % (q, AFB_Q_MIN, AFB_Q_MAX))
    if abs(gain_db) < AFB_FLAT_EPS:
        return (1.0, 0.0, 0.0, 0.0, 0.0)
    w0 = 2.0 * math.pi * freq / fs
    alpha = math.sin(w0) / (2.0 * q)
    a = 10.0 ** (gain_db / 40.0)
    inv = 1.0 / (1.0 + alpha / a)
    b0 = (1.0 + alpha * a) * inv
    b1 = (-2.0 * math.cos(w0)) * inv
    b2 = (1.0 - alpha * a) * inv
    a2 = (1.0 - alpha / a) * inv
    return (b0, b1, b2, b1, a2)


def offset_form(c):
    b0, b1, b2, a1, a2 = c
    return (b0, b1 + 2.0 * b0, b2 - b0, 2.0 + a1, 1.0 - a2)


def kernel_notch(freq, gain_db, q, on=True, fs=FS):
    """One notch, offset-encoded, BY THE KERNEL'S EXPRESSION -- clamping
    where the part clamps rather than raising."""
    if not on:
        return IDENTITY
    freq = clamp(freq, AFB_FREQ_MIN, AFB_FREQ_MAX)
    gain_db = clamp(gain_db, AFB_GAIN_MIN, AFB_GAIN_MAX)
    q = clamp(q, AFB_Q_MIN, AFB_Q_MAX)
    if abs(gain_db) < AFB_FLAT_EPS:
        return IDENTITY
    x = 2.0 * math.pi * freq / fs
    s = sin_poly(x)
    u = vers_poly(x)
    k2 = 2.0 * u
    al = s / (2.0 * q)
    v = gain_db * LOG2_10_OVER_40
    a = exp2_wide(v)
    inv_a = exp2_wide(-v)
    a_a = al * a
    i_a = al * inv_a
    inv = 1.0 / (1.0 + i_a)
    return ((1.0 + a_a) * inv,
            (k2 + 2.0 * a_a) * inv,
            (-2.0 * a_a) * inv,
            (k2 + 2.0 * i_a) * inv,
            (2.0 * i_a) * inv)


def kernel_set(freqs, gains, qs, on=True, fs=FS):
    """A whole ANTI_FB node, offset-encoded, flattened -- what
    `_afb_coeffs_next` must hold after the design step has run."""
    out = []
    for f, g, q in zip(freqs, gains, qs):
        out.extend(kernel_notch(f, g, q, on, fs))
    return out


def response_db(coeffs_offset, freq, fs=FS):
    """Magnitude in dB at `freq` of a cascade given as offset-form words."""
    total = 0.0
    w = 2.0 * math.pi * freq / fs
    for k in range(0, len(coeffs_offset), 5):
        b0, n1, n2, c1, c2 = coeffs_offset[k:k + 5]
        b1 = n1 - 2.0 * b0
        b2 = n2 + b0
        a1 = c1 - 2.0
        a2 = 1.0 - c2
        num = complex(b0 + b1 * math.cos(w) + b2 * math.cos(2 * w),
                      -(b1 * math.sin(w) + b2 * math.sin(2 * w)))
        den = complex(1.0 + a1 * math.cos(w) + a2 * math.cos(2 * w),
                      -(a1 * math.sin(w) + a2 * math.sin(2 * w)))
        total += 20.0 * math.log10(abs(num / den))
    return total


def check(verbose=False):
    """The model against RBJ, and the kernel expression against the model.

    Three bars, all re-measured rather than asserted:
      * design_notch == bq_float_ref.rbj_peak over the whole domain;
      * a 0 dB notch is the compiled identity, exactly;
      * the two polynomials, and the kernel expression they feed, agree
        with the readable form to well inside a float32 ulp.
    """
    import bq_float_ref as R
    freqs = [40.0, 63.0, 100.0, 250.0, 440.0, 1000.0, 2500.0,
             5000.0, 8000.0, 12000.0]
    gains = [-18.0, -12.0, -9.0, -6.0, -3.0, -1.0, -0.25]
    qs = [1.0, 2.0, 4.0, 8.0, 14.0, 20.0]

    worst = 0.0
    for f in freqs:
        for g in gains:
            for q in qs:
                mine = design_notch(f, g, q)
                theirs = R.rbj_peak(f, q, g)
                for a, b in zip(mine, theirs):
                    worst = max(worst, abs(a - b) / max(abs(b), 1e-9))
    assert worst < 1e-12, 'afb_ref diverges from rbj_peak by %.3e' % worst

    for f in freqs:
        for q in qs:
            flat = offset_form(design_notch(f, 0.0, q))
            for a, b in zip(flat, IDENTITY):
                assert abs(a - b) < 1e-12, '0 dB at %g Hz is not identity' % f

    sworst = uworst = 0.0
    n = 4001
    for i in range(n):
        x = AFB_FREQ_MIN + (AFB_FREQ_MAX - AFB_FREQ_MIN) * i / (n - 1.0)
        w = 2.0 * math.pi * x / FS
        sworst = max(sworst, abs(sin_poly(w) - math.sin(w)) / math.sin(w))
        uworst = max(uworst,
                     abs(vers_poly(w) - (1.0 - math.cos(w)))
                     / (1.0 - math.cos(w)))
    eworst = 0.0
    for i in range(2001):
        v = -1.4949 + 2.0 * 1.4949 * i / 2000.0
        eworst = max(eworst, abs(exp2_wide(v) - 2.0 ** v) / 2.0 ** v)

    kworst = 0.0
    for f in freqs:
        for g in gains:
            for q in qs:
                mine = kernel_notch(f, g, q)
                theirs = offset_form(design_notch(f, g, q))
                for a, b in zip(mine, theirs):
                    kworst = max(kworst, abs(a - b) / max(abs(b), 1e-9))

    if verbose:
        print('afb_ref vs bq_float_ref.rbj_peak, worst relative: %.3e' % worst)
        print('sin polynomial worst relative:                    %.3e' % sworst)
        print('1-cos polynomial worst relative:                  %.3e' % uworst)
        print('2**v by half-and-square, worst relative:          %.3e' % eworst)
        print('kernel expression vs direct form, worst:          %.3e' % kworst)
        print('0 dB notch is the compiled identity:              True')
    assert sworst < 1e-9, 'SIN_POLY worse than advertised: %.3e' % sworst
    assert uworst < 1e-9, 'VERS_POLY worse than advertised: %.3e' % uworst
    assert eworst < 1e-8, 'exp2_wide worse than advertised: %.3e' % eworst
    assert kworst < 1e-7, 'kernel expression diverges: %.3e' % kworst
    return worst


if __name__ == '__main__':
    import sys
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    check(verbose=True)
    print('')
    print('%-9s %-6s %-6s  %s' % ('f0 Hz', 'gain', 'Q', 'depth at f0, dB'))
    for f in (100.0, 1000.0, 5000.0):
        for g in (-18.0, -6.0):
            for q in (2.0, 10.0):
                c = kernel_notch(f, g, q)
                print('%-9.1f %-6.1f %-6.1f  %+.4f'
                      % (f, g, q, response_db(list(c), f)))
