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
QN1 = 27             # n1 is stored HALVED, in Q5.27 (PW ruling 2026-08-29)
Q_MIN = 0.10         # minimum EQ/filter Q the conversion accepts
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
    b0, n1h, n2, c1, c2 = coeffs
    x1, x2, y1, y2, efb = state
    # n1h is n1/2 (see biquad_coeffs_q): its product is accumulated TWICE
    # into the exact wide accumulator, which is the same value as n1*x1
    # and is written as two MACs because that is what the kernel issues.
    acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
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
    """Float RBJ coefficient set -> quantized offset form (load-time).

    n1 IS STORED HALVED, IN Q5.27, AND THAT IS NORMATIVE (PW ruling
    2026-08-29, minimum EQ Q = 0.10). Of the five offset coefficients n1
    is the only one whose design-space range escapes Q4.28: at +15 dB
    with Q <= 0.12 the peaking design gives n1 = b1 + 2*b0 up to 8.318
    against a Q4.28 ceiling of 7.999..., and before this it SATURATED at
    conversion -- the filter silently became a different filter, in 1323
    of 909,315 swept sets. Storing n1/2 in Q5.27 doubles the headroom to
    +/-16 and the kernel accumulates its product twice, which is the same
    product in the exact wide accumulator.

    The encoding is UNIFORM AND UNCONDITIONAL, not a corner case: the
    kernel's instruction stream must not vary with the loaded settings,
    or measured ceilings become setting-dependent. It costs one MAC per
    biquad stage everywhere, and one bit of n1 resolution -- the n1 grid
    goes from 2^-28 to 2^-27, which golden_harness measures against the
    same 0.046 dB response bar as before.

    Q < 0.10 is REJECTED, not clamped -- see check_q().
    """
    q = lambda c: sat32(int(round(c * (1 << QB))))
    qh = lambda c: sat32(int(round(c * (1 << QN1))))
    return (q(b0), qh(b1 + 2 * b0), q(b2 - b0), q(2 + a1), q(1 - a2))


def check_q(q):
    """Reject a filter Q below the ruled floor. Loud, per the no-fallback
    policy: a silently clamped Q is the same class of defect as the
    silently saturated n1 this floor was ruled alongside."""
    if q < Q_MIN:
        raise ValueError(
            f'Q = {q} is below the ruled minimum {Q_MIN} '
            '(PW ruling 2026-08-29; shared/numeric-spec.md)')
    return q


# ---------------------------------------------------------------------------
# Mix summing: exact wide-accumulator MAC, ONE round/saturate at the end
#
# THE ACCUMULATOR IS 80 BITS AND THAT IS NORMATIVE (2026-08-29, executing
# PW's saturate-never-wrap ruling; review finding D1). The bus
# accumulators live in memory between contributions, and what is stored
# is the WHOLE SHARC multiplier result MR2F:MR1F:MR0F -- Q8.56 in 80
# bits, range +/-2^23 = +/-8388608.0 linear.
#
# It was 64 bits until 2026-08-29: MR2F was discarded on store and
# rebuilt from the sign of the high word on load, capping the stored
# value at +/-128.0 with NOTHING saturating it, and the readout then ran
# its saturation check on a value that had already wrapped -- so a
# wrapped sum came out as a clean, full-scale, WRONG-SIGN sample rather
# than as a clip. This model could not see it: it used unbounded Python
# ints, so the model was RIGHT and the assembly was wrong, and no golden
# vector went near the boundary.
#
# ACC_BITS states the boundary so vectors can be placed at it and on
# both sides of it. It is not reachable from representable inputs: a bus
# takes at most ~64 contributions, each at most 8.0 x 8.0 = 64.0, so
# |sum| <= 4096 = 2^12 against 2^23 -- eleven bits, 2048x. Saturating
# rather than wrapping at the boundary is the ruling; the margin is what
# makes it a formality rather than a limit.
# ---------------------------------------------------------------------------

ACC_BITS = 80                            # SHARC MR2F:MR1F:MR0F
ACC_MAX = (1 << (ACC_BITS - 1)) - 1
ACC_MIN = -(1 << (ACC_BITS - 1))


def sat_acc(v):
    """Saturate a wide accumulator to the 80-bit store. Never wraps."""
    return ACC_MAX if v > ACC_MAX else (ACC_MIN if v < ACC_MIN else v)


def mix_sum(samples, gains):
    acc = 0
    for x, g in zip(samples, gains):
        acc = sat_acc(acc + x * g)      # Q8.56 terms, exact to 80 bits
    return sat32(rns(acc, QS))


def mix_sum_wrapping(samples, gains, bits=64):
    """The PRE-FIX arithmetic, kept as the negative control.

    Identical to mix_sum except that the accumulator is stored in
    `bits` bits and WRAPS, which is what discarding MR2F did. Any vector
    on which these two disagree is a vector the old assembly got wrong.
    """
    lim = 1 << bits
    half = lim >> 1
    acc = 0
    for x, g in zip(samples, gains):
        acc = (acc + x * g) & (lim - 1)
        if acc >= half:
            acc -= lim
    return sat32(rns(acc, QS))


# ---------------------------------------------------------------------------
# Dual-instance coefficient crossfade blend — NORMATIVE (2026-08-29)
#
# The EQ, GEQ, AFB, FILT and CROSSOVER nodes hold two independent
# coefficient sets (A/B). When SPI delivers a new set the dormant
# instance is loaded and both run for XFADE_SAMPLES while their outputs
# are blended. THIS is that blend, and until 2026-08-29 it had no model
# at all (review finding D33), which is why review finding D3 -- the
# 32-bit `new - old` difference wrapping mid-swap -- could not be proved
# either way.
#
#   alpha    float control-plane ramp 0.0 -> 1.0, one step per call
#   a31      = sat32(int(alpha * 2**31))     (the kernel's `fix`, which
#            saturates, so alpha == 1.0 gives 2**31 - 1, not 2**31)
#   out      = old + rns(a31 * (new - old), 31)
#
# THE DIFFERENCE IS EXACT. `new` and `old` are independently saturated
# Q4.28 outputs, so new - old spans [-2**32+1, 2**32-1] and does NOT fit
# a 32-bit word: with hot program material during a coefficient swap the
# two instances can straddle full scale and the 32-bit form wrapped,
# putting up to a block of full-scale-wrong samples into the chain (a
# click, self-clearing when the fade ends). The assembly forms the
# product as TWO MACs into the 80-bit MRF -- a31*new then minus a31*old
# -- so no 32-bit difference exists at any point. That is arithmetically
# identical to the old form everywhere the old form did not wrap, which
# is what makes this a bug fix and not a spec change.
#
# THE FINAL ADD CANNOT OVERFLOW, and this is a bound, not an assumption:
# |a31| <= 2**31 - 1 and |new - old| <= 2**32 - 1, so
# rns(a31*(new-old), 31) <= 2**32 - 2, and old >= -2**31, giving
# out <= 2**31 - 2 < I32_MAX. Symmetrically for the lower end. No
# saturation is needed on the add and none is applied.
# ---------------------------------------------------------------------------

XFADE_MS = 12.0
XFADE_SAMPLES = int(XFADE_MS / 1000.0 * 48000)      # 576 @ 48 kHz
XFADE_STEP = 1.0 / XFADE_SAMPLES


def xfade_alpha_q(alpha):
    """Control-plane float alpha -> the kernel's Q0.31 integer.

    THIS IS FLOAT32 ARITHMETIC, not float64, and getting that wrong was
    worth 15 LSB on the part: the whole parameter plane is float32
    (numeric-spec.md, "Parameter boundary"), so alpha is stored as a
    float32 and the kernel's `f4 = f4 * f5` is a float32 multiply by
    2^31 before `r4 = fix f4`. Measured 2026-08-29: modelling it in
    float64 disagreed with the part by 15 at alpha = 1 - 1/576, and
    modelling it in float32 agrees exactly on every vector.

    DOMAIN: alpha in [0, 1). The kernel's own ramp guarantees it --
    `f4 = alpha + step; comp(f4, 1.0); if lt rts;` stores the new alpha
    only when it is still below 1.0, and otherwise ENDS the crossfade
    and zeroes alpha -- so the largest alpha ever blended is one step
    short of unity. alpha == 1.0 makes the float32 product exactly 2^31,
    which is not a 32-bit integer; `fix` was measured on the part to
    return 0xFFFFFFFF for it, not a saturated 0x7FFFFFFF. That corner is
    unreachable and is left unmodelled deliberately, but any change to
    the alpha ramp has to preserve alpha < 1.0.
    """
    import struct
    f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
    return sat32(int(f32(f32(alpha) * f32(float(1 << QA)))))


def _wrap32(v):
    """Two's-complement wrap into a 32-bit register — what a SHARC Rn does
    and what the models of the PRE-FIX arithmetic have to reproduce."""
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= (1 << 31) else v


def xfade_blend(new, old, alpha):
    """One blended sample. new/old are Q4.28; alpha is the float ramp."""
    a31 = xfade_alpha_q(alpha)
    return old + rns(a31 * (new - old), QA)


def xfade_blend_wrapping(new, old, alpha):
    """The PRE-FIX arithmetic, kept as the negative control.

    Identical to xfade_blend except that the difference is formed in a
    32-bit register and wraps. Any vector on which these two disagree is
    a vector the old assembly got wrong.
    """
    a31 = xfade_alpha_q(alpha)
    d = _wrap32(new - old)                          # THE defect: 32-bit sub
    return _wrap32(old + rns(a31 * d, QA))          # the final add is 32-bit too


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


# ---------------------------------------------------------------------------
# METER — NORMATIVE (2026-08-28, PW ruling "rebuild in-kernel")
#
# The meter that this replaces had four recorded defects (see
# tools/dsp/hw-reports/mtr-2026-08-23.md): it reinterpreted a Q4.28 word
# as an IEEE float, its RMS never advanced because the new-peak branch
# returned first, its decay ran once per SAMPLE against a constant
# derived for once per BLOCK, and it had no reference model at all. This
# is that model, and the assembly is written to match it bit-exactly.
#
# SHAPE. Per sample the kernel keeps three running quantities and touches
# no memory: the maximum of x, the minimum of x, and an exact sum of x^2
# in the 80-bit multiplier accumulator. Per block it folds those into two
# 64-bit states. Nothing is decimated: every sample is in the peak and in
# the mean square.
#
#   peak of the block   pk_blk = max(max x, -min x)          Q4.28
#   mean square         ms_blk = (sum x^2) >> (QS + shift)   Q4.28
#                       where 2**shift == BLOCK, so the shift is exact
#                       and the block mean needs no divide
#
# STATE IS 64-BIT, and that is the point. Both one-poles have a
# time constant of hundreds of blocks, so their per-block correction is
# ~1e-4 of the state. Held in Q4.28 that correction rounds to zero for
# anything below about -50 dBFS and the meter simply stops moving. Held
# as Q8.56 -- which is what the multiplier produces anyway -- the
# correction is a single exact MAC and the smallest step is 2^-56.
#
#   ms64 += alpha_q * (ms_blk - (ms64 >> QS))       [Q8.56 += Q4.28*Q4.28]
#   pk64  = pk_blk << QS                     if pk_blk > (pk64 >> QS)
#   pk64 -= beta_q * (pk64 >> QS)            otherwise
#
# Readback stays FLOAT, which is the existing host contract:
#   peak = (pk64 >> QS) / 2**QS              linear amplitude
#   rms  = sqrt((ms64 >> QS) / 2**QS)        linear amplitude, TRUE rms
#
# Time constants are properties of the meter, not of the block size, so
# the coefficients are derived from the block RATE and every one of them
# moves when BLOCK moves.
# ---------------------------------------------------------------------------

METER_TAU_RMS_S = 0.300      # RMS window, 300 ms class
METER_TAU_PEAK_S = 1.333     # peak-hold decay; matches the library meter's
                             # documented ~1.33 s at any block size
METER_FS = 48000.0


def meter_coeffs(block, fs=METER_FS):
    """(alpha_q, beta_q) in Q4.28 for a given block size.

    alpha is the RMS window's one-pole coefficient, beta the peak-hold
    decay's, both per BLOCK: 1 - exp(-1 / (rate * tau)).
    """
    rate = fs / block
    alpha = 1.0 - math.exp(-1.0 / (rate * METER_TAU_RMS_S))
    beta = 1.0 - math.exp(-1.0 / (rate * METER_TAU_PEAK_S))
    return to_q(alpha, QS), to_q(beta, QS)


def meter_state():
    """[pk64, ms64] — both Q8.56, both zero at reset."""
    return [0, 0]


QM = 24              # METER sample fraction bits (Q8.24) — PW ruling
                     # 2026-08-29: every meter taps the MS 32-bit word of
                     # the accumulator at its tap point, unrounded and
                     # unsaturated, so the meter's input is the Q8.24 view
                     # of a value the Q4.28 interchange word cannot hold.


def meter_block(xs, state, alpha_q, beta_q):
    """One block of Q8.24 samples into the meter state (updated in place).

    Returns (pk_blk, ms_blk) in Q4.28 — the block's own peak and mean
    square, before the one-poles — because those are what the assembly
    holds in registers and are the useful intermediate to diff against.

    THE INPUT IS Q8.24 AND THE OUTPUT IS Q4.28, deliberately: the meter's
    64-bit state, its one-poles and its float readback are unchanged by the
    wide-word ruling; only what is fed in changed. Squares are therefore
    Q16.48 and the mean-square shift is 48 - 28 = 20 plus log2(BLOCK). The
    peak converts by a left shift of 4 and CLAMPS at 8.0 linear (+18.06
    dBFS), which is where a Q4.28 peak word runs out; a saturated Q4.28
    source could never have reported above 0 dBFS at all.
    """
    block = len(xs)
    shift = block.bit_length() - 1
    assert block == (1 << shift), 'BLOCK must be a power of two'

    hi = max(xs)
    lo = min(xs)
    pk_blk = hi if hi > -lo else -lo
    pk_blk = sat32(pk_blk)
    pk_clamp = (1 << (QM + 3)) - 1          # 0x07FFFFFF
    if pk_blk > pk_clamp:
        pk_blk = pk_clamp
    pk_blk <<= (QS - QM)

    ssq = 0
    for x in xs:
        ssq += x * x
    ms_blk = sat32(ssq >> (2 * QM - QS + shift))

    # RMS window: exact Q8.56 accumulate of a Q4.28 x Q4.28 correction.
    ms_q = state[1] >> QS
    state[1] += alpha_q * (ms_blk - ms_q)

    # Peak hold: instant attack, one-pole decay, same 64-bit domain.
    pk_q = state[0] >> QS
    if pk_blk > pk_q:
        state[0] = pk_blk << QS
    else:
        state[0] -= beta_q * pk_q

    return pk_blk, ms_blk


def meter_readback(state):
    """(peak, rms) as floats — linear amplitude, the host contract."""
    peak = (state[0] >> QS) / float(1 << QS)
    ms = (state[1] >> QS) / float(1 << QS)
    return peak, math.sqrt(ms) if ms > 0.0 else 0.0


# ===========================================================================
# THE PARAMETER BOUNDARY: float32 and the SHARC `fix`
#
# Everything below this line models a NODE rather than a primitive, and a
# node has two halves: a float32 control plane that converts host
# parameters once per block, and a fixed sample path. numeric-spec.md
# already rules the first half float32 ("Parameter boundary"), and
# xfade_alpha_q was the first model to have to say so -- modelling its
# alpha in float64 disagreed with the part by 15 LSB. Every conversion
# below is therefore float32, single operation at a time, in the order
# the emitted instructions perform it.
# ===========================================================================

def f32(x):
    """Round to IEEE-754 single, which is what every register in the
    control plane holds."""
    import struct
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


F32_2P28 = f32(268435456.0)      # 0x4D800000, the Q4.28 scale
F32_2P27 = f32(134217728.0)      # 0x4D000000, the Q5.27 scale (halved n1)
F32_2P31 = f32(2147483648.0)     # 0x4F000000, the Q0.31 scale
F32_2P25 = f32(33554432.0)       # 0x4C000000, the Q6.25 scale
F32_DB_LOG2 = f32(5573270.5)     # 0x4AAA152D, dB -> Q6.25 log2 domain
F32_2P31_100 = f32(21474836.0)   # 0x4BA3D70A, 2^31 / 100 (percent cells)


def fix32(x):
    """SHARC `Rn = FIX Fx`, in its DEFINED DOMAIN ONLY.

    Round-to-nearest-even (the RND mode every one of these conversions
    runs under; Python's round() is the same rule) of a float32, into a
    32-bit signed word.

    OUT OF RANGE IT RAISES, and that is the no-fallback policy rather
    than laziness. `fix` on this part does NOT saturate and does NOT
    two's-complement wrap: at exactly 2^31 it was MEASURED to return
    0xFFFFFFFF, i.e. -1 (see the CLAMP note in the COMPRESSOR node and
    xfade_alpha_q's docstring -- two independent measurements, both on
    the part, both 2026-08-23/29). One measured point is not a model of
    the overflow behaviour, so this refuses to invent the rest of it.

    The consequence is a REQUIREMENT on the kernel, not a limitation of
    the model: every host parameter that reaches a `fix` must be clamped
    into range before it gets there. CompPar (review finding D40) and
    GateRng (D39) are; FADER level and pan are not (finding D64)."""
    v = f32(x)
    if not (I32_MIN <= v <= I32_MAX):
        raise ValueError(
            f'fix32({v!r}) is outside the 32-bit domain. `fix` neither '
            f'saturates nor wraps here -- at 2^31 the part returns '
            f'0xFFFFFFFF -- so the conversion is undefined and the '
            f'parameter must be clamped before it reaches this point '
            f'(review finding D64).')
    return int(round(v))


def wrap32(v):
    """Two's-complement wrap into a 32-bit register. THE ALU WRAPS: MODE1
    ALUSAT is never set anywhere in this firmware (audited 2026-08-30),
    so every `r0 = r1 + r2`, `r0 = r1 - r2` and `r0 = abs r1` in the
    emitted nodes wraps rather than saturating. Only the explicit
    round-and-saturate sequences (_mrf_rns28, _acc64_rns28) saturate."""
    return _wrap32(v)


def alu_abs(v):
    """SHARC `Rn = ABS Rx` with ALUSAT clear: abs(I32_MIN) is I32_MIN."""
    return _wrap32(abs(v))


# ---------------------------------------------------------------------------
# COMPRESSOR wet path — NORMATIVE (2026-08-30, review finding D28)
#
# comp_gain() above stops at the gain computer. What the node does with
# that gain had no model at all, and it is where the two most recent
# cell-semantics defects lived (D40's percent scaling, D59's fully-dry
# default). Three things happen after the gain computer, in this order:
#
#   wet  = rns28(rns28(dry * gain) * makeup)     TWO roundings
#   d    = wet - dry                             32-BIT register subtract
#   out  = dry + rns(d * par, 31)                32-bit add
#
# THE SECOND ROUNDING IS THE POINT OF THE MODEL. The kernel cannot form
# dry*gain*makeup in one accumulator -- both are Q4.28, so the triple
# product is Q12.84 and the multiplier is 80 bits -- so it rounds and
# saturates to Q4.28 between them. That is a half-LSB of extra error and
# a saturation point that a single-rounding model does not have, and
# comp_wet_1round() below is exactly that single-rounding model, kept as
# the negative control: any vector on which the two disagree is a vector
# that can tell the implemented arithmetic from the obvious one.
#
# THE 32-BIT DIFFERENCE IS BOUNDED, NOT SAFE BY ACCIDENT. gain is in
# [0, 1] and makeup is non-negative, so wet and dry ALWAYS CARRY THE SAME
# SIGN and |wet - dry| <= max(|wet|, |dry|) <= 2^31. That fits int32
# everywhere except the single corner dry = I32_MIN with wet = 0, which
# needs the gain computer's exp2 to underflow to zero -- reachable only
# at extreme threshold/ratio settings. The bound depends on makeup being
# non-negative, which nothing in the kernel enforces (review finding D4),
# so it is a bound on the DOCUMENTED domain and the vector set sits on
# its edge.
# ---------------------------------------------------------------------------

def comp_wet(dry, gain_q, mk_q):
    """dry -> wet, both roundings. gain_q and mk_q are Q4.28."""
    w = sat32(rns(dry * gain_q, QS))
    return sat32(rns(w * mk_q, QS))


def comp_wet_1round(dry, gain_q, mk_q):
    """The single-rounding wet path — THE NEGATIVE CONTROL for the second
    round. Arithmetically what a model that ignored the intermediate
    store would say; not what the kernel can issue."""
    return sat32(rns(dry * gain_q * mk_q, 2 * QS))


def comp_blend(dry, wet, par_q31):
    """out = dry + rns((wet - dry) * par, 31), with the kernel's exact
    register widths. par is Q0.31.

    The rns product itself cannot overflow: |wet-dry| <= 2^31 and
    par <= 2^31 - 1, so |product| < 2^62 and the (mr1f<<1 | mr0f>>31)
    extraction the kernel uses is exact. The two ALU operations either
    side of it are the ones that wrap."""
    d = _wrap32(wet - dry)
    return _wrap32(dry + rns(d * par_q31, QA))


def comp_out(dry, gain_q, mk_q, par_q31):
    """The whole wet path: what `_buf_<COMP>` holds for a sample the
    compressor did not bypass."""
    return comp_blend(dry, comp_wet(dry, gain_q, mk_q), par_q31)


def comp_par_q(percent):
    """CompPar (PERCENT on the wire, review finding D40) -> Q0.31, as the
    node converts it: clamp to the masters' documented 0..100, scale by
    the float32 constant 2^31/100, `fix`, then the explicit negative
    clamp that catches 100 % landing on exactly 2^31."""
    p = f32(percent)
    if p < 0.0:
        p = 0.0
    if p > f32(100.0):
        p = f32(100.0)
    scaled = f32(p * F32_2P31_100)
    # The kernel's `fix` here CAN be handed 2^31 (at exactly 100 %) and
    # the node repairs it afterwards with `if lt r1 = 0x7FFFFFFF`. Model
    # the repair rather than the undefined conversion.
    if scaled >= F32_2P31:
        return I32_MAX
    v = int(round(scaled))
    return I32_MAX if v < 0 else v


def comp_makeup_q(makeup):
    """CompMkUp (linear gain, float) -> Q4.28."""
    return fix32(f32(f32(makeup) * F32_2P28))


# ---------------------------------------------------------------------------
# One-pole with attack/release selection — the emitted `_envq_fx`
#
# envelope_step() above is the SPEC primitive: one alpha, saturating add.
# _envq_fx is what every dynamics node actually calls, and it differs in
# two ways that no vector had ever separated:
#   * it picks the alpha from the SIGN of (target - env) -- attack when
#     the target is above the state, release otherwise;
#   * its final add is a plain ALU add, so it WRAPS where the spec
#     primitive saturates.
# The wrap is unreachable for legitimate inputs (the result is a convex
# combination of two int32s and is bounded by them, the same bound the
# crossfade blend carries), which is why the two forms have never been
# seen to differ. It is modelled exactly anyway, because "unreachable"
# is a claim a vector should be able to test.
# ---------------------------------------------------------------------------

def env_step(target, env, att_q, rel_q):
    """_envq_fx, bit-exact. att_q/rel_q are Q0.31."""
    d = _wrap32(target - env)
    a = att_q if d > 0 else rel_q
    return _wrap32(env + rns(a * d, QA))


# ---------------------------------------------------------------------------
# GATE node state machine — NORMATIVE (2026-08-30, review finding D30)
#
# The primitives had models; the LADDER did not, and the ladder is where
# the behaviour is. Per sample, in the emitted order:
#
#   env    = envq(|x|, env, att, rel)              sidechain follower
#   open   = env > 0 and log2(env) >= thr          (env == 0 is BELOW)
#   open :   target = 1.0 ; hold_count = hold
#   below:   hold_count -= 1 ; if hold_count <= 0: target = range
#   gain   = envq(target, gain, att, rel)          one-pole smoother
#   y      = sat32(rns(x * gain, 28))
#
# THREE THINGS THE LADDER DOES THAT A DESCRIPTION OF A GATE DOES NOT:
#   * the hold counter is decremented UNCONDITIONALLY while below and is
#     never floored, so a gate that stays shut runs it negative for as
#     long as it stays shut. Only its sign is ever read, so nothing
#     audible follows -- until 2^31 samples (12.4 hours at 48 kHz) take
#     it through the wrap, after which it is briefly positive again while
#     the target it would have set is already the range floor. Modelled
#     with the wrap so the claim is testable rather than asserted.
#   * the SAME alpha pair drives the sidechain follower and the gain
#     smoother, so "attack" is the attack of both.
#   * `|x|` is the ALU's ABS with ALUSAT clear, so |I32_MIN| is I32_MIN
#     -- a full-negative sample presents a NEGATIVE level to the
#     follower, and env then goes to it on the RELEASE alpha.
#
# The linear-threshold variant (DSP4_GATE_LINTHR) is a different
# arithmetic and is NOT modelled here: it is unshipped, needs a
# numeric-spec amendment, and its own note says so.
# ---------------------------------------------------------------------------

GATE_UNITY = 1 << QS


def gate_state(env=0, gain=GATE_UNITY, target=GATE_UNITY, hold_count=0):
    """[env, gain, target, hold_count] — the four words the node keeps."""
    return [env, gain, target, hold_count]


def gate_step(x, st, att_q, rel_q, thr_q625, rng_q, hold):
    """One sample through the gate. st is updated in place; returns y."""
    st[0] = env_step(alu_abs(x), st[0], att_q, rel_q)
    if st[0] > 0 and log2_q(st[0]) >= thr_q625:
        st[2] = GATE_UNITY
        st[3] = hold
    else:
        st[3] = _wrap32(st[3] - 1)
        if st[3] <= 0:
            st[2] = rng_q
    st[1] = env_step(st[2], st[1], att_q, rel_q)
    return sat32(rns(x * st[1], QS))


def gate_step_nohold(x, st, att_q, rel_q, thr_q625, rng_q, hold):
    """THE NEGATIVE CONTROL for the hold ladder: identical except that
    the gate closes the instant the level falls below threshold. Any
    vector on which this and gate_step disagree is a vector that can see
    the hold counter."""
    st[0] = env_step(alu_abs(x), st[0], att_q, rel_q)
    if st[0] > 0 and log2_q(st[0]) >= thr_q625:
        st[2] = GATE_UNITY
    else:
        st[2] = rng_q
    st[1] = env_step(st[2], st[1], att_q, rel_q)
    return sat32(rns(x * st[1], QS))


def gate_range_q(range_db):
    """GateRng (DECIBELS on the wire, review finding D39) -> Q4.28 linear
    floor: clamp to the documented 0..60 dB, then 2^(-dB * log2(10)/20)
    through the SAME exp2 the kernel calls."""
    d = f32(range_db)
    if d < 0.0:
        d = 0.0
    if d > f32(60.0):
        d = f32(60.0)
    l = f32(f32(d * f32(-0.16609640419483185)) * F32_2P25)
    return exp2_q(fix32(l))


def gate_thr_q(thr_db):
    """GateThr (dB) -> Q6.25 log2 domain."""
    return fix32(f32(f32(thr_db) * F32_DB_LOG2))


def dyn_alpha_q(alpha):
    """A dynamics attack/release coefficient (float) -> Q0.31."""
    return fix32(f32(f32(alpha) * F32_2P31))


# ---------------------------------------------------------------------------
# FADER_PAN — NORMATIVE (2026-08-30, review finding D31)
#
# The site of the 2026-08-23 squared-gain bug, and still the only strip
# node whose float parameters reach a `fix` with NO CLAMP between them
# (finding D64). Three coefficients, all block rate, all float32:
#
#   gq = fix(level * 2^28), forced to 0 when mute is set   (the 08-25
#        crosspoint-coefficient fold: mute is a linear gain term, so it
#        belongs in the coefficient and the sample path stays one MAC)
#   lq = fix((1 - pan) * 2^28)        LINEAR pan law
#   rq = fix(pan * 2^28)
#
# lq/rq are ROUTING's main-bus crosspoint coefficients, not sample-path
# multipliers: the node's own MAC applies gq only. Folding the level into
# the pan legs as well is precisely the shipped defect -- x * level^2 *
# (1-pan), 6.02 dB low at level 0.5 and exact at unity, which is why it
# shipped. fdr_pan_squared() keeps that arithmetic as the negative
# control.
#
# THE PAN LAW IS LINEAR AND THAT IS AN OPEN DECISION, NOT A RULING. The
# masters document a constant-power law; linear is what is implemented,
# and the difference is a ~3 dB dip at centre (review finding D42, PW's
# to decide). This models WHAT IS. If D42 rules constant-power, this
# function and the emitted node change together and this comment is the
# marker for it.
# ---------------------------------------------------------------------------

def fdr_coeffs(level, pan, mute=0):
    """(gq, lq, rq) — the three Q4.28 coefficients, as the node builds
    them. Raises through fix32 if level or pan is out of range, which is
    finding D64: nothing in the kernel clamps them."""
    gq = 0 if mute else fix32(f32(f32(level) * F32_2P28))
    lq = fix32(f32(f32(f32(1.0) - f32(pan)) * F32_2P28))
    rq = fix32(f32(f32(pan) * F32_2P28))
    return gq, lq, rq


def fdr_apply(x, gq):
    """The whole sample path: one MAC, one round-and-saturate."""
    return sat32(rns(x * gq, QS))


def fdr_pan_squared(x, gq, leg_q):
    """THE PRE-2026-08-23 ARITHMETIC, kept as the negative control: the
    pan leg with the level folded in a second time, so the bus feed came
    out as x * level^2 * leg. Bit-identical to the correct form at
    level = 1.0, which is how it shipped."""
    return sat32(rns(sat32(rns(x * gq, QS)) * sat32(rns(gq * leg_q, QS)), QS))


# ---------------------------------------------------------------------------
# TUBE_SAT — NORMATIVE (2026-08-30, review finding D29)
#
# THREE CHAINED ROUNDINGS and, until now, no coverage of any kind:
#
#   x2 = rns28(x * x)                    saturates at 7.999 (|x| > 2.83)
#   t  = 1.0 - x2                        32-bit ALU, wraps
#   s  = rns28(sat_q * t)
#   g  = 1.0 + s                         32-bit ALU, wraps
#   y  = rns28(x * g)
#
# A soft-clip shape only for |x| <= 1: above that x2 > 1, so g < 1 and
# the transfer curve TURNS OVER -- at |x| = 2 with sat = 1.0 the gain
# factor is 1 + (1 - 4) = -2 and the output has the WRONG SIGN. That is
# what the arithmetic is, it is reachable from a Q4.28 sample (full scale
# is 8.0), and it is why the vectors walk past unity rather than stopping
# at it.
#
# PLUGIN-CLASS COVERAGE (PW ruling 2026-08-30). TUBE is a plug-in option,
# not a fixed strip feature: the base strip's floors and ceilings are
# computed with it bypassed, its ACTIVE cost bills to plugin headroom,
# and this model covers the ACTIVE path -- engaged the way a plugin would
# engage it. The bypass path's obligation is different and belongs to the
# base strip: it must cost nothing, which is a MEASUREMENT (the node's
# `_tube_on == 0` arm), not an arithmetic.
# ---------------------------------------------------------------------------

def tube(x, sat_q):
    """One sample through an ENGAGED tube stage. sat_q is Q4.28."""
    x2 = sat32(rns(x * x, QS))
    t = _wrap32(GATE_UNITY - x2)
    s = sat32(rns(sat_q * t, QS))
    g = _wrap32(GATE_UNITY + s)
    return sat32(rns(x * g, QS))


def tube_2round(x, sat_q):
    """THE NEGATIVE CONTROL: the same shape with the middle rounding
    folded away (sat*(1-x^2) carried at full width into the last MAC).
    Any vector on which this and tube() disagree is a vector that can see
    the second of the three roundings."""
    x2 = sat32(rns(x * x, QS))
    t = _wrap32(GATE_UNITY - x2)
    g = (GATE_UNITY << QS) + sat_q * t
    return sat32(rns(x * g, 2 * QS))


def tube_bypass(x):
    """The bypassed path, which is the BASE strip's version of this node:
    the sample is passed through untouched."""
    return x


def tube_sat_q(sat):
    """TubeSat (float) -> Q4.28."""
    return fix32(f32(f32(sat) * F32_2P28))


# ---------------------------------------------------------------------------
# TDM BOUNDARY — NORMATIVE (2026-08-30, review finding D34)
#
# The two places the fixed audio path meets the wire. Both are three-bit
# shifts and neither had any test surface at all.
#
#   IN   (chip 1 `_scatter_chip1`)  Q1.31 -> Q4.28: an ARITHMETIC right
#        shift by 3. It TRUNCATES TOWARD -INFINITY -- there is no
#        rounding half added -- so every input sample carries up to one
#        LSB of downward bias. Three bits of the wire word are discarded
#        by construction: the interchange format has four integer bits
#        the codec's does not.
#   OUT  (chip 2 `_gather_chip2`)   Q4.28 -> Q1.31: a left shift by 3
#        with a round-trip test, saturating to +/-full scale by the SIGN
#        OF THE SOURCE when the value does not fit. Everything above
#        1.0 linear clips here, which is the only place in the graph
#        where the extra headroom of Q4.28 is finally spent.
# ---------------------------------------------------------------------------

TDM_SHIFT = 3


def tdm_in(w):
    """One wire word (Q1.31) -> one sample (Q4.28). Truncating."""
    return w >> TDM_SHIFT


def tdm_out(v):
    """One sample (Q4.28) -> one wire word (Q1.31), saturating."""
    y = _wrap32(v << TDM_SHIFT)
    if (y >> TDM_SHIFT) == v:
        return y
    return I32_MAX if v >= 0 else I32_MIN


def tdm_out_unchecked(v):
    """THE NEGATIVE CONTROL: the shift without the round-trip test, i.e.
    what the conversion would be if the saturation arm were dropped.
    Differs on exactly the samples above 1.0 linear."""
    return _wrap32(v << TDM_SHIFT)


# ---------------------------------------------------------------------------
# BIQUAD COEFFICIENT CONVERSION ON THE PART — `_bq_fx_convert_N`
# (2026-08-30, review finding D27)
#
# biquad_coeffs_q() above is the NORMATIVE float64 definition. This is
# the same conversion as the PART performs it: float32, one operation per
# emitted instruction, `fix` instead of a saturating round. It is a
# parameter-boundary function, so float32 is the spec (numeric-spec.md),
# not a deviation -- but the two are not identical word for word and the
# harness measures the gap rather than assuming it away.
#
# THE b1 SITE. This routine shipped a defect in which the b0 conversion's
# `fix` destination was r1 -- the same register as f1, which held b1 --
# so b1 was destroyed before `n1 = b1 + 2*b0` ever read it and EVERY
# biquad in the product ran with b1 = 0. bq_convert_b1_lost() is that
# arithmetic, kept as the negative control: it differs on every
# coefficient set with a non-zero b1 and on none without one, which is
# what makes a b1 = 0 vector worth having in the set.
# ---------------------------------------------------------------------------

def bq_convert_f32(b0, b1, b2, a1, a2):
    """(b0q, nh, n2, c1, c2) exactly as `_bq_fx_convert_N` computes them."""
    b0, b1, b2, a1, a2 = (f32(v) for v in (b0, b1, b2, a1, a2))
    b0q = fix32(f32(b0 * F32_2P28))
    nh = fix32(f32(f32(b1 + f32(b0 * f32(2.0))) * F32_2P27))
    n2 = fix32(f32(f32(b2 - b0) * F32_2P28))
    c1 = fix32(f32(f32(a1 + f32(2.0)) * F32_2P28))
    c2 = fix32(f32(f32(f32(1.0) - a2) * F32_2P28))
    return (b0q, nh, n2, c1, c2)


def bq_convert_b1_lost(b0, b1, b2, a1, a2):
    """THE NEGATIVE CONTROL: b1 destroyed by the b0 conversion, so
    n1 comes out as exactly 2*b0 (`biquad_fx.asm`'s own header)."""
    b0, b1, b2, a1, a2 = (f32(v) for v in (b0, b1, b2, a1, a2))
    b0q = fix32(f32(b0 * F32_2P28))
    nh = fix32(f32(f32(b0 * f32(2.0)) * F32_2P27))
    n2 = fix32(f32(f32(b2 - b0) * F32_2P28))
    c1 = fix32(f32(f32(a1 + f32(2.0)) * F32_2P28))
    c2 = fix32(f32(f32(f32(1.0) - a2) * F32_2P28))
    return (b0q, nh, n2, c1, c2)
