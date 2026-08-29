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


def meter_block(xs, state, alpha_q, beta_q):
    """One block of Q4.28 samples into the meter state (updated in place).

    Returns (pk_blk, ms_blk) in Q4.28 — the block's own peak and mean
    square, before the one-poles — because those are what the assembly
    holds in registers and are the useful intermediate to diff against.
    """
    block = len(xs)
    shift = block.bit_length() - 1
    assert block == (1 << shift), 'BLOCK must be a power of two'

    hi = max(xs)
    lo = min(xs)
    pk_blk = hi if hi > -lo else -lo
    pk_blk = sat32(pk_blk)

    ssq = 0
    for x in xs:
        ssq += x * x
    ms_blk = sat32(ssq >> (QS + shift))

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
