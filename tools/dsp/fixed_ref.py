#!/usr/bin/env python3
"""fixed_ref.py — bit-accurate fixed-point reference models (decision D5).

THE normative definition of the DSP4 fixed-point audio path per
shared/numeric-spec.md. The SHARC assembly and the future FPGA RTL must
match these functions BIT-EXACTLY; this model in turn is
tolerance-tested against float64 by golden_harness.py.

Formats (numeric-spec.md): samples Q4.28, biquad coeffs Q2.30, linear
gains Q4.28, alphas Q0.31; ≥64-bit accumulators; round-to-nearest then
saturate on every 32-bit store; wrap forbidden.

All arithmetic uses Python ints (exact, arbitrary width) so the model
is platform-independent.
"""

import math

QS = 28              # sample fraction bits (Q4.28)
QB = 28              # biquad offset-coefficient fraction bits (Q4.28)
QC = 30              # poly coeff fraction bits (Q2.30)
QA = 31              # alpha fraction bits (Q0.31)
I32_MAX = (1 << 31) - 1
I32_MIN = -(1 << 31)


def sat32(v):
    return I32_MAX if v > I32_MAX else (I32_MIN if v < I32_MIN else v)


def rns(acc, shift):
    """Round-to-nearest, half toward +inf: (acc + half) >> shift with
    arithmetic (floor) shift. NORMATIVE (2026-07-31): this is the
    hardware-natural form — one add and one arithmetic shift on both
    SHARC and FPGA — and is what the asm kernels implement. Python's
    >> on negative ints is floor, matching exactly."""
    return (acc + (1 << (shift - 1))) >> shift


def to_q(x, frac=QS):
    """Float -> saturated 32-bit fixed (round-to-nearest)."""
    return sat32(int(round(x * (1 << frac))))


def from_q(v, frac=QS):
    return v / (1 << frac)


# ---------------------------------------------------------------------------
# Gain (Q4.28 sample × Q4.28 gain)
# ---------------------------------------------------------------------------

def gain(x, g):
    return sat32(rns(x * g, QS))


# ---------------------------------------------------------------------------
# Biquad — NORMATIVE TOPOLOGY: offset-coefficient direct-form I
# (Agarwal-Burrus style) with first-order error feedback.
#
# Plain DF1 with 32-bit coefficients fails at low frequencies (measured
# up to 12.8 dB response error at 20 Hz, and today's FP32 firmware shows
# 0.4 dB there). Storing the coefficients as OFFSETS from the LF limit
# point makes their quantization error proportional to their (small)
# magnitude:
#     y = b0*(x - 2*x1 + x2) + n1*x1 + n2*x2
#         + 2*y1 - y2 - c1*y1 + c2*y2 + efb
#     n1 = b1 + 2*b0,  n2 = b2 - b0,  c1 = 2 + a1,  c2 = 1 - a2
# All five stored coefficients fit Q4.28 (|c1| ≤ 4, |c2| ≤ 2, |n1|,|n2|
# bounded for table-reachable settings). The rounding remainder is fed
# back into the next accumulation (first-order noise shaping), which
# takes the LF noise floor from ~-107 dBFS to below -130 dBFS.
#
# state = [x1, x2, y1, y2, efb]; efb is the Q8.56 rounding remainder.
# ---------------------------------------------------------------------------

def biquad(x, coeffs, state):
    b0, n1, n2, c1, c2 = coeffs
    x1, x2, y1, y2, efb = state
    acc = (b0 * (x - 2 * x1 + x2) + n1 * x1 + n2 * x2
           - c1 * y1 + c2 * y2)             # Q8.56, exact
    acc += (2 * y1 - y2) << QB              # exact unity/two terms
    acc += efb                              # error feedback
    y = sat32(rns(acc, QB))
    state[4] = acc - (y << QB)              # rounding remainder
    state[0], state[1] = x, x1
    state[2], state[3] = y, y1
    return y


def biquad_state():
    return [0, 0, 0, 0, 0]


def biquad_coeffs_q(b0, b1, b2, a1, a2):
    """Float RBJ coefficient set -> quantized offset form (load-time)."""
    q = lambda c: sat32(int(round(c * (1 << QB))))
    return (q(b0), q(b1 + 2 * b0), q(b2 - b0), q(2 + a1), q(1 - a2))


# ---------------------------------------------------------------------------
# Mix summing: exact wide-accumulator MAC, ONE round/saturate at the end
# ---------------------------------------------------------------------------

def mix_sum(samples, gains):
    acc = 0
    for x, g in zip(samples, gains):
        acc += x * g                    # Q8.56 terms, exact
    return sat32(rns(acc, QS))


# ---------------------------------------------------------------------------
# One-pole envelope (dynamics attack/release): env += alpha*(target-env)
# ---------------------------------------------------------------------------

def envelope_step(env, target, alpha):
    return sat32(env + rns(alpha * (target - env), QA))


# ---------------------------------------------------------------------------
# log2 / exp2 polynomial approximants (normalize-then-poly, degree 5)
# Coefficients are Chebyshev-fitted then quantized to Q2.30 — these
# EXACT integer coefficient sets are part of the normative spec.
#
# Checked-in constants, not computed at import time: regenerate with
# tools/dsp/fit_log2exp2_poly.py if the fit degree, range, or QC changes.
# ---------------------------------------------------------------------------

# log2(1+t), t in [0,1)
LOG2_POLY = [46176222, -201314356, 439665385, -758584049, 1547790691, 17732]
# 2^f, f in [0,1)
EXP2_POLY = [2033403, 9609550, 59979580, 257850314, 744268966, 1073741715]


def _poly_eval_q(coeffs_q230, t_q31):
    """Horner in fixed point: t in Q0.31, coeffs Q2.30, result Q2.30."""
    acc = coeffs_q230[0]
    for c in coeffs_q230[1:]:
        acc = rns(acc * t_q31, QA) + c      # stays in Q2.30
    return acc


def log2_q(x):
    """log2 of a nonnegative Q4.28 value -> Q6.25 result (range ±32).

    Normalize: x = m * 2^e with m in [1,2); log2(x) = e + log2(m).

    x == 0 is a legitimate call (silence, comp_gain's x_abs); it returns
    the -32 sentinel rather than raising. This is provably collision-free:
    the smallest legitimate positive Q4.28 value is x=1, whose exponent
    is nbits-1-QS = 0-28 = -28, so no positive x can produce a result at
    or below -32 (verified against the encoding, not assumed). x < 0 is
    not legitimate for any current caller (comp_gain's x_abs is always
    an absolute value) and raises.
    """
    if x < 0:
        raise ValueError(f'log2_q undefined for negative x={x!r}')
    if x == 0:
        return -(32 << 25)                  # -inf sentinel (~-32 in Q6.25)
    nbits = x.bit_length()                  # Q4.28: value 1.0 has 29 bits
    e = nbits - 1 - QS                      # integer exponent
    m_q31 = (x << (31 - (nbits - 1)))       # mantissa in Q1.31, [1,2)
    t_q31 = m_q31 - (1 << 31)               # t = m-1 in Q0.31, [0,1)
    frac_q230 = _poly_eval_q(LOG2_POLY, t_q31)
    return (e << 25) + rns(frac_q230, QC - 25)


def exp2_q(l_q625):
    """2^l for l in Q6.25 (range ±32) -> Q4.28 saturated."""
    e = l_q625 >> 25                        # floor
    f_q25 = l_q625 - (e << 25)              # frac in [0,1), Q0.25
    f_q31 = f_q25 << 6
    m_q230 = _poly_eval_q(EXP2_POLY, f_q31)  # 2^f in Q2.30, [1,2)
    shift = QC - QS - e                      # to Q4.28 scaled by 2^e
    if shift <= 0:
        return sat32(m_q230 << -shift)
    if shift > 62:
        return 0
    return sat32(rns(m_q230, shift))


# Dynamics carry levels in the LOG2 DOMAIN (Q6.25) rather than dB:
# thresholds and slopes are converted from dB at parameter-load time
# (thr_log2 = thr_db / (20*log10(2))), which removes all per-sample
# dB-constant multiplies. This is a normative spec choice.

# ---------------------------------------------------------------------------
# Compressor static gain computer (hard knee), fixed path:
#   level_db = K * log2(|x|); over = level_db - thr_db (if > 0)
#   gr_db = over * (1 - 1/ratio);  gain = exp2(-gr_db / K)
# All dB values carried as LOG2-DOMAIN Q6.25 (i.e. dB/K) to avoid the
# extra constant multiplies: thresholds/ratios convert at load time.
# ---------------------------------------------------------------------------

def comp_gain(x_abs, thr_log2_q625, slope_q31, half_knee_q625=0,
              k2_q625=0):
    """Gain computer with optional soft knee (matches the float lib).

    slope = (1 - 1/ratio) in Q0.31; half_knee = knee/2 in log2-domain
    Q6.25; k2 = slope/(2*knee) in Q6.25 (block-rate precomputed; both 0
    => hard knee). Returns linear gain Q4.28.
    """
    lvl = log2_q(x_abs)
    over = lvl - thr_log2_q625
    if over <= -half_knee_q625:
        return 1 << QS
    if half_knee_q625 and over < half_knee_q625:
        t = over + half_knee_q625               # Q6.25
        t2 = rns(t * t, 25)                     # Q6.25
        gr = rns(t2 * k2_q625, 25)              # Q6.25
        return exp2_q(-gr)
    gr = rns(over * slope_q31, QA)              # Q6.25
    return exp2_q(-gr)


# ---------------------------------------------------------------------------
# float64 reference twins (the golden comparison targets)
# ---------------------------------------------------------------------------

def biquad_f(x, coeffs, state):
    b0, b1, b2, a1, a2 = coeffs
    x1, x2, y1, y2 = state
    y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
    state[0], state[1] = x, x1
    state[2], state[3] = y, y1
    return y


def comp_gain_f(x_abs, thr_db, ratio, knee_db=0.0):
    if x_abs <= 0:
        return 1.0
    lvl = 20 * math.log10(x_abs)
    over = lvl - thr_db
    slope = 1.0 - 1.0 / ratio
    if over <= -knee_db / 2:
        return 1.0
    if knee_db > 0 and over < knee_db / 2:
        gr = slope * (over + knee_db / 2) ** 2 / (2 * knee_db)
    else:
        gr = over * slope
    return 10.0 ** (-gr / 20.0)
