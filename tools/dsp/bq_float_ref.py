"""bq_float_ref — the NORMATIVE model for the float cascade kernels.

`fixed_ref.py::biquad` is normative for `lib/biquad_fx.asm`'s fixed
kernels; this is normative for the same file's DSP4_BQ_FLOAT kernels, and
for the same reason: a kernel is only correct against a model, and a
model written after the fact from the assembly is not one.

WHAT THE PART ACTUALLY DOES, instruction for instruction:

  in     Fn = FLOAT Rx BY -28        Q4.28 word -> float, ROUNDED to the
                                     current float boundary
  stage  y   = w1 + b0*x             direct form II TRANSPOSED
         w1' = w2 + b1*x - a1*y
         w2' =      b2*x - a2*y
  out    Fn = CLIP Fx BY 7.99999952  the ONE clamp: the inter-node bus is
         Rn = FIX Fx BY 28           still Q4.28, so the word handed on
                                     must fit, whatever the cascade did
                                     internally

THE FLOAT BOUNDARY IS THE WHOLE OF THE 40-BIT QUESTION. MODE1.RND32
selects it: cleared (the arm) every result keeps the register file's
40-bit extended format, 32 significand bits; set (DSP4_BQ_FLOAT32, the
control) every result rounds to IEEE single's 24. The block kernels hold
w1/w2 in REGISTERS across all the samples of a stage, so inside a block
the recursion runs at whichever boundary is selected -- but a 40-bit
register STORED to a 32-bit DM word loses its low eight mantissa bits,
so the state crosses each BLOCK BOUNDARY at single precision even in the
40-bit arm. All three of those are modelled separately here, because the
difference between the second and the third is exactly what a PM-resident
(48-bit) state array would buy and it should be priced before it is
built.

COEFFICIENTS ARE float32 IN THE OFFSET FORM (2026-09-03, and it is the
accuracy fix, not a detail): the host writes b0, n1 = b1 + 2*b0,
n2 = b2 - b0, c1 = 2 + a1, c2 = 1 - a2 as IEEE-754 singles over SPI, the
float arm stores them unchanged (`_bq_fx_convert_N` is a copy under
DSP4_BQ_FLOAT) and the kernel reconstructs the direct words in REGISTERS
once per stage per block. Carrying a1 = -1.9948 directly costs six bits
of pole placement -- a float32 ulp there is 2.4e-7 against Q4.28's
3.7e-9, because fixed-point precision is absolute and float's is
relative -- and 2 + a1 = 0.0052 gets them back. Worst response error
over the DEFS set: 0.3715 dB on the direct wire, 0.0042 dB on the
offset one, against a fixed contract at 0.0265 and a golden bar of
0.046.

EXACT ROUNDING, NOT float64 STANDING IN FOR IT. A product of two 32-bit
significands needs 64 bits before it is rounded, and float64 has 53 --
rounding it twice is not the same as rounding it once and can differ in
the last place. numpy.longdouble on x86-64 is the 80-bit extended format
with a 64-bit significand, which holds such a product exactly, so every
40-bit operation here is computed exactly and rounded ONCE. The 24-bit
arm is computed the same way and is checked against numpy.float32
on 20,000 random values, where it agrees on every one.

    python3 tools/dsp/bq_float_ref.py            the whole report
    python3 tools/dsp/bq_float_ref.py --overflow just the overflow proof
"""
import sys, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import fixed_ref as F

FS = 48000.0
QS = 28

# Q4.28's ceiling as the largest float32 below 8.0 (0x40FFFFFF). The
# kernel clamps to this, so FIX BY 28 gives 0x7FFFFF80 and cannot wrap.
CLIPF = float(np.frombuffer(np.uint32(0x40FFFFFF).tobytes(), dtype=np.float32)[0])

LD = np.longdouble
# 64-bit significand on x86-64; anything less and the 40-bit arm is not
# exactly rounded and this model is not normative for anything.
_LD_BITS = np.finfo(np.longdouble).nmant + 1
if _LD_BITS < 64:
    print(f'WARNING: numpy.longdouble has {_LD_BITS} significand bits, not 64;'
          ' the 40-bit arm is DOUBLE-ROUNDED here and is not normative',
          file=sys.stderr)


# Veltkamp/Dekker splitting: with a q-bit significand,
#     c  = fl(x * (2**s + 1)),   hi = fl(c - fl(c - x))
# gives hi = x ROUNDED TO NEAREST at q-s bits, exactly. Three flops
# instead of a frexp/scale/round, which matters because this runs once
# per operand per sample per stage over hundreds of thousands of
# sample-stages. Valid while x * 2**s does not overflow, and the values
# here reach 1e4 against an exponent range of 1e38.
_SPLIT32 = LD(2.0) ** 32 + LD(1.0)      # 64-bit significand -> 32 bits
_SPLIT24 = LD(2.0) ** 40 + LD(1.0)      # 64-bit significand -> 24 bits


def rnd32(x):
    c = x * _SPLIT32
    return c - (c - x)


def rnd24(x):
    c = x * _SPLIT24
    return c - (c - x)


def rnd_p(x, p):
    """Round a longdouble to p significand bits, round-to-nearest -- the
    SHARC's float boundary. p = 32 is the 40-bit register format,
    p = 24 is IEEE single (MODE1.RND32 set)."""
    x = LD(x)
    if x == 0 or not np.isfinite(x):
        return x
    if p >= 64:
        return x
    c = x * (LD(2.0) ** (64 - p) + LD(1.0))
    return c - (c - x)


def trunc_p(x, p):
    """Truncate a longdouble toward zero to p significand bits -- what a
    40-bit data register loses when it is STORED to a 32-bit DM word.
    Called twice per stage per BLOCK, not per sample, so it can afford
    the exponent lookup that the round cannot."""
    x = LD(x)
    if x == 0 or not np.isfinite(x):
        return x
    hi = rnd_p(x, p)
    if abs(hi) > abs(x):
        _, e = math.frexp(float(hi))
        hi = hi - LD(math.copysign(1.0, float(hi))) * LD(2.0) ** (e - p)
    return hi


# --------------------------------------------------------------------------
# RBJ designs, the same forms the DEFS parameter path produces
# --------------------------------------------------------------------------
def rbj_peak(f0, q, gain_db, fs=FS):
    a = 10.0 ** (gain_db / 40.0)
    w = 2 * math.pi * f0 / fs
    al = math.sin(w) / (2 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def rbj_shelf(f0, q, gain_db, high, fs=FS):
    A = 10.0 ** (gain_db / 40.0)
    w = 2 * math.pi * f0 / fs
    cw, sw = math.cos(w), math.sin(w)
    al = sw / 2 * math.sqrt((A + 1 / A) * (1 / q - 1) + 2)
    tsa = 2 * math.sqrt(A) * al
    if high:
        b0 = A * ((A + 1) + (A - 1) * cw + tsa); b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) + (A - 1) * cw - tsa); a0 = (A + 1) - (A - 1) * cw + tsa
        a1 = 2 * ((A - 1) - (A + 1) * cw);       a2 = (A + 1) - (A - 1) * cw - tsa
    else:
        b0 = A * ((A + 1) - (A - 1) * cw + tsa); b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - tsa); a0 = (A + 1) + (A - 1) * cw + tsa
        a1 = -2 * ((A - 1) + (A + 1) * cw);      a2 = (A + 1) + (A - 1) * cw - tsa
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def rbj_hpf(f0, q, fs=FS):
    w = 2 * math.pi * f0 / fs
    al = math.sin(w) / (2 * q)
    cw = math.cos(w)
    b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
    a0, a1, a2 = 1 + al, -2 * cw, 1 - al
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


# --------------------------------------------------------------------------
# The kernels, modelled
# --------------------------------------------------------------------------
def wire_coeffs(designs):
    """What the host actually puts on the SPI wire and the float arm
    stores unchanged: the RBJ words as IEEE-754 singles."""
    return [tuple(LD(np.float32(v)) for v in d) for d in designs]


def _dequantised_fixed(designs):
    """The direct-form coefficients the FIXED kernel is actually running,
    recovered from its stored Q4.28 offset words -- the reference its own
    arithmetic noise must be measured against."""
    out = []
    for d in designs:
        b0, n1h, n2, c1, c2 = F.biquad_coeffs_q(*d)
        out.append((F.from_q(b0),
                    F.from_q(2 * n1h) - 2 * F.from_q(b0),
                    F.from_q(n2) + F.from_q(b0),
                    F.from_q(c1) - 2.0,
                    1.0 - F.from_q(c2)))
    return out


def exact_coeffs(designs):
    """The design's own coefficients at full longdouble precision. Not a
    thing any wire format delivers -- it is the CONTROL that separates
    what the ARITHMETIC costs from what the COEFFICIENT WORD costs."""
    return [tuple(LD(v) for v in d) for d in designs]


def offset_wire_coeffs(designs, recon_mant=32):
    """D5's OFFSET encoding carried as float32 -- THE SHIPPING WIRE since
    2026-09-03. The wire carries b0, n1 = b1 + 2*b0, n2 = b2 - b0,
    c1 = 2 + a1, c2 = 1 - a2 as float32 and the kernel reconstructs the
    direct words in REGISTERS, once per stage per block.

    The point of the offset form in Q4.28 was headroom. In FLOAT it buys
    something else and something larger: a1 sits at -1.9948 for a 20 Hz
    biquad, where a float32 ulp is 2.4e-7, while 2 + a1 = 0.0052 has an
    ulp of 3.7e-10 -- so the same 32-bit word places the pole nearly
    three decimal orders more accurately. Fixed-point precision is
    ABSOLUTE and float's is RELATIVE, and pole placement error is an
    absolute error.

    recon_mant IS THE RECONSTRUCTION, NOT AN APPROXIMATION OF IT. The
    five prologue instructions run in the register file at the float
    boundary the kernel is in -- 32 significand bits in the 40-bit arm,
    24 with DSP4_BQ_FLOAT32 -- so `c1 - 2.0` is EXACT wherever c1's
    lowest set bit is at or above 2**-31 and rounds once where it is not.
    Modelling it in longdouble would credit the wire with precision the
    part does not have; None asks for that control deliberately."""
    R = (lambda v: v) if recon_mant is None else (lambda v: rnd_p(v, recon_mant))
    out = []
    for b0, b1, b2, a1, a2 in designs:
        b0f = LD(np.float32(b0))
        n1 = LD(np.float32(b1 + 2 * b0))
        n2 = LD(np.float32(b2 - b0))
        c1 = LD(np.float32(2.0 + a1))
        c2 = LD(np.float32(1.0 - a2))
        out.append((b0f,
                    R(n1 - R(b0f + b0f)),
                    R(n2 + b0f),
                    R(c1 - LD(2.0)),
                    R(LD(1.0) - c2)))
    return out


def offset_wire_words(designs):
    """The five float32 words per stage the HOST puts on the SPI wire
    under the float arm, in the order the coefficient block holds them.
    This is the wire contract itself; offset_wire_coeffs is what the
    kernel makes of it."""
    out = []
    for b0, b1, b2, a1, a2 in designs:
        out.append((np.float32(b0), np.float32(b1 + 2 * b0),
                    np.float32(b2 - b0), np.float32(2.0 + a1),
                    np.float32(1.0 - a2)))
    return out


def q428_coeffs_as_float(designs):
    """RIG A2's comparison basis: the Q4.28 offset words the FIXED path
    stores, de-quantised back to direct form. Kept so this model can
    reproduce the shootout's isolate-the-arithmetic figure."""
    out = []
    for d in designs:
        b0, n1h, n2, c1, c2 = F.biquad_coeffs_q(*d)
        out.append((LD(np.float32(F.from_q(b0))),
                    LD(np.float32(F.from_q(2 * n1h) - 2 * F.from_q(b0))),
                    LD(np.float32(F.from_q(n2) + F.from_q(b0))),
                    LD(np.float32(F.from_q(c1) - 2.0)),
                    LD(np.float32(1.0 - F.from_q(c2)))))
    return out


def run_float_cascade(x_q, coeffs, mant=32, store_mant=24, block=16,
                      clamp=True, track=None, sig_mant=24):
    """The float cascade BLOCK kernel, exactly as the part runs it.

    x_q       int32 Q4.28 words in, int32 Q4.28 words out
    mant      significand bits of the float boundary (32 = the 40-bit arm,
              24 = DSP4_BQ_FLOAT32)
    store_mant  significand bits the state survives a BLOCK boundary with
              (24 = a 32-bit DM word, the firmware; 32 = a hypothetical
              48-bit PM-resident state; None = never stored)
    sig_mant  significand bits the signal survives ONE STAGE with (24 = the
              32-bit DM block buffer, the firmware; None = the per-sample
              kernel, which passes y to the next stage in a register)
    track     if a dict, records the largest magnitude any internal value
              reached -- the overflow proof

    THE SIGNAL CROSSES A 32-BIT DM WORD BETWEEN STAGES and it is not the
    same crossing as the state's. `_bq_fx_cascade_blk` runs stage-outer /
    sample-inner, so a stage writes its whole block of y back to the
    buffer (`dm(i2, 1) = f1`) and the next stage reads it (`f0 =
    dm(i2, 0)`): the forward path is 32-bit float even in the 40-bit arm,
    and so is the entry pass's `FLOAT Rx BY -28`, which quantises a
    32-significant-bit Q4.28 word to 24 bits on its way into the buffer.
    What stays at 40 bits is the RECURSION -- w1/w2 in registers across
    the whole block, and the full-precision y that feeds them, not the
    truncated copy handed on. That is where a high-Q LF biquad's state
    error lives, so the 40 bits keep what they were bought for; but a
    model that carried the forward path in longdouble would be claiming
    a precision the kernel does not have. Measured, both ways, on the
    response table: it is worth nothing there (0.0042 dB either way).

    sig_mant=None IS the per-sample kernel `_bq_fx_cascade_N`, which
    holds the cascade value in f0 across stages -- which is why the
    crossfade path cannot be bit-identical to steady state under float.
    """
    ns = len(coeffs)
    w1 = [LD(0)] * ns
    w2 = [LD(0)] * ns
    out = np.zeros(len(x_q), dtype=np.int64)
    R = rnd32 if mant == 32 else (rnd24 if mant == 24 else
                                 (LD if mant >= 64 else
                                  (lambda v: rnd_p(v, mant))))
    T = (lambda v: v) if sig_mant is None else (lambda v: trunc_p(v, sig_mant))
    peak = LD(0)
    for base in range(0, len(x_q), block):
        blk = x_q[base:base + block]
        # the domain crossing IN: FLOAT Rx BY -28, rounded at the boundary,
        # then STORED to the 32-bit block buffer
        v = [T(R(LD(int(w)) / LD(2) ** QS)) for w in blk]
        for k in range(ns):
            b0, b1, b2, a1, a2 = coeffs[k]
            s1, s2 = w1[k], w2[k]
            nv = []
            for xv in v:
                y = R(s1 + R(b0 * xv))
                t = R(s2 + R(b1 * xv))
                s1 = R(t - R(a1 * y))
                s2 = R(R(b2 * xv) - R(a2 * y))
                nv.append(T(y))          # the block buffer is 32-bit
                if abs(y) > peak: peak = abs(y)
                if abs(s1) > peak: peak = abs(s1)
                if abs(s2) > peak: peak = abs(s2)
            v = nv
            # the state crosses the block boundary through memory
            if store_mant is None:
                w1[k], w2[k] = s1, s2
            else:
                w1[k] = trunc_p(s1, store_mant)
                w2[k] = trunc_p(s2, store_mant)
        # the ONE clamp and the domain crossing OUT
        for i, yv in enumerate(v):
            if clamp:
                if yv > LD(CLIPF): yv = LD(CLIPF)
                elif yv < LD(-CLIPF): yv = LD(-CLIPF)
            out[base + i] = int(np.round(np.float64(yv * LD(2) ** QS)))
    if track is not None:
        track['peak'] = float(peak)
    return out


def run_fixed_cascade(x_q, designs):
    """The shipping contract, bit for bit: fixed_ref's offset form."""
    cq = [F.biquad_coeffs_q(*d) for d in designs]
    st = [F.biquad_state() for _ in designs]
    out = np.zeros(len(x_q), dtype=np.int64)
    for i, w in enumerate(x_q):
        v = int(w)
        for c, s in zip(cq, st):
            v = F.biquad(v, c, s)
        out[i] = v
    return out


def run_exact_cascade(x_q, designs):
    """The filter the design ASKED for: unquantised coefficients, float64
    direct form II transposed, no clamp. The bar both arms are scored
    against."""
    w1 = [0.0] * len(designs)
    w2 = [0.0] * len(designs)
    out = np.zeros(len(x_q), dtype=np.float64)
    for i, w in enumerate(x_q):
        v = float(w) / (1 << QS)
        for k, (b0, b1, b2, a1, a2) in enumerate(designs):
            y = w1[k] + b0 * v
            w1[k] = w2[k] + b1 * v - a1 * y
            w2[k] = b2 * v - a2 * y
            v = y
        out[i] = v
    return out


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def curve_db(y, n):
    Y = np.fft.rfft(y, n)
    return 20 * np.log10(np.maximum(np.abs(Y), 1e-30))


def response_err(y_test, y_ref, n, fs=FS, lo=20.0, hi=20000.0):
    freqs = np.fft.rfftfreq(n, 1 / fs)
    band = (freqs >= lo) & (freqs <= hi)
    d = np.abs(curve_db(y_test, n) - curve_db(y_ref, n))[band]
    i = int(np.argmax(d))
    return float(d[i]), float(freqs[band][i])


def noise_floor_db(y_test, y_ref):
    """Residual error power relative to full scale, in dBFS."""
    e = np.asarray(y_test, dtype=np.float64) - np.asarray(y_ref, dtype=np.float64)
    rms = math.sqrt(float(np.mean(e * e))) if len(e) else 0.0
    return 20 * math.log10(max(rms, 1e-30))


# --------------------------------------------------------------------------
# the design set -- the DEFS worst cases the fixed work was decided on
# --------------------------------------------------------------------------
GEQ = [rbj_peak(25 * (2 ** (i / 6.0)), 4.3, 6.0) for i in range(28)]

CASES = {
    'ordinary peak +15 dB Q3 @1k':      [rbj_peak(1000, 3.0, 15.0)],
    'peak +15 dB Q0.1 @5k':             [rbj_peak(5000, 0.1, 15.0)],
    'EXTREME +15 dB Q10 @20 Hz':        [rbj_peak(20, 10.0, 15.0)],
    'HF shelf +12 dB Q5.01 @20':        [rbj_shelf(20, 5.01, 12.0, True)],
    'LF shelf +15 dB Q3.16 @20 Hz':     [rbj_shelf(20, 3.16, 15.0, False)],
    '4-band EQ, mixed':                 [rbj_peak(80, 1.1, 8.0), rbj_peak(400, 1.5, -6.0),
                                         rbj_peak(2500, 2.0, 6.0), rbj_peak(9000, 0.8, -4.0)],
    'EQ 4-band +15/+15/-15/-15 @1k Q1': [rbj_peak(1000, 1.0, 15.0), rbj_peak(1000, 1.0, 15.0),
                                         rbj_peak(1000, 1.0, -15.0), rbj_peak(1000, 1.0, -15.0)],
    '4-band all +15 dB @1k Q1':         [rbj_peak(1000, 1.0, 15.0)] * 4,
    '28-band GEQ all +6 dB':            GEQ,
    '28-band GEQ alternating +/-6':     [rbj_peak(25 * (2 ** (i / 6.0)), 4.3, 6.0 * (-1) ** i)
                                         for i in range(28)],
    'FILT: HPF 20 Hz + LPF 20 kHz':     [rbj_hpf(20, 0.707), rbj_hpf(20, 0.707)],
}

N = 8192
BLOCK = 16


def impulse_q(amp=0.5, n=N):
    x = np.zeros(n, dtype=np.int64)
    x[0] = int(round(amp * (1 << QS)))
    return x


def l1_norm(designs, n=200000):
    """|h|_1 of the whole cascade -- what an arbitrary bounded input can
    reach at the output, which is what the fixed guard sizes on."""
    y = run_exact_cascade(impulse_q(1.0, n), designs)
    return float(np.sum(np.abs(y)))


def main():
    only_overflow = '--overflow' in sys.argv
    imp = impulse_q(0.5)
    ref_designs = {k: v for k, v in CASES.items()}

    if not only_overflow:
        print('=' * 108)
        print('RESPONSE ERROR vs THE FILTER THE DESIGN ASKED FOR '
              '(unquantised float64), 20 Hz - 20 kHz, impulse at -6 dBFS')
        print('=' * 108)
        print(f"{'design':36s} {'fixed D5':>10s} {'flt40 OFFS':>11s} "
              f"{'flt32 offs':>11s} {'flt40 raw':>11s} {'flt40 exact':>12s}")
        print('-' * 108)
        rows = []
        for name, d in ref_designs.items():
            raw = wire_coeffs(d)
            offs = offset_wire_coeffs(d)
            offs24 = offset_wire_coeffs(d, recon_mant=24)
            exct = exact_coeffs(d)
            y_ref = run_exact_cascade(imp, d)
            y_fx = run_fixed_cascade(imp, d).astype(np.float64) / (1 << QS)
            ys = [y_fx]
            for co, mant in ((offs, 32), (offs24, 24), (raw, 32), (exct, 32)):
                ys.append(run_float_cascade(imp, co, mant, 24, BLOCK).astype(np.float64)
                          / (1 << QS))
            e = [response_err(y, y_ref, N)[0] for y in ys]
            rows.append((name, e))
            print(f'{name:36s} {e[0]:10.4f} {e[1]:11.4f} {e[2]:11.4f} '
                  f'{e[3]:11.4f} {e[4]:12.4f}')
        print('-' * 108)
        w = [max(r[1][i] for r in rows) for i in range(5)]
        print(f"{'WORST OVER THE SET':36s} {w[0]:10.4f} {w[1]:11.4f} {w[2]:11.4f} "
              f"{w[3]:11.4f} {w[4]:12.4f}")
        print(f"{'golden_harness response bar':36s} {0.046:10.4f}")
        print()
        print('  fixed D5     the reference model, kept behind DSP4_BQ_FLOAT=0: Q4.28')
        print('               OFFSET words, per-stage round with ERROR FEEDBACK (fixed_ref)')
        print('  flt40 OFFS   THE SHIPPING PATH -- 40-bit arithmetic on the float32 OFFSET')
        print('               wire (b0, n1, n2, c1, c2), reconstructed in registers')
        print('  flt32 offs   DSP4_BQ_FLOAT32, the 32-bit control on the same wire')
        print('  flt40 raw    the DIRECT-form float32 wire the arm carried before')
        print('               2026-09-03: the same arithmetic, the coefficient word alone')
        print('  flt40 exact  40-bit arithmetic on unquantised coefficients: the control')
        print('               that separates the ARITHMETIC from the COEFFICIENT WORD')
        print()

        # ---- residual noise floor ----
        print('=' * 108)
        print('RESIDUAL NOISE FLOOR, ARITHMETIC ONLY: RMS error in dBFS against a float64 '
              'run of THE SAME')
        print('coefficients, on 32768 samples of -20 dBFS noise. Scoring against the '
              'ideal filter instead would')
        print('fold the coefficient word\'s deterministic response error into a figure '
              'that is supposed to be noise.')
        print('=' * 108)
        rng = np.random.default_rng(20260903)
        nn = 32768
        drive = np.clip(rng.standard_normal(nn) * 0.1, -0.999, 0.999)
        xq = np.round(drive * (1 << QS)).astype(np.int64)
        print(f"{'design':36s} {'fixed D5':>10s} {'flt40 OFFS':>11s} "
              f"{'flt32 offs':>11s} {'flt40 no-store':>15s}")
        print('-' * 108)
        for name in ('LF shelf +15 dB Q3.16 @20 Hz', 'EXTREME +15 dB Q10 @20 Hz',
                     '4-band EQ, mixed', '28-band GEQ all +6 dB'):
            d = CASES[name]
            offs = offset_wire_coeffs(d)
            offs24 = offset_wire_coeffs(d, recon_mant=24)
            offs_f = [tuple(float(c) for c in st) for st in offs]
            dq = [tuple(x) for x in _dequantised_fixed(d)]
            y_fx = run_fixed_cascade(xq, d).astype(np.float64) / (1 << QS)
            r_fx = run_exact_cascade(xq, dq)
            r_fl = run_exact_cascade(xq, offs_f)
            y_40 = run_float_cascade(xq, offs, 32, 24, BLOCK).astype(np.float64) / (1 << QS)
            y_32 = run_float_cascade(xq, offs24, 24, 24, BLOCK).astype(np.float64) / (1 << QS)
            y_4n = run_float_cascade(xq, offs, 32, None, BLOCK).astype(np.float64) / (1 << QS)
            print(f'{name:36s} '
                  f'{noise_floor_db(y_fx, r_fx):10.1f} {noise_floor_db(y_40, r_fl):11.1f} '
                  f'{noise_floor_db(y_32, r_fl):11.1f} {noise_floor_db(y_4n, r_fl):15.1f}')
        print()

    # ---- the overflow proof ----
    print('=' * 108)
    print('OVERFLOW: the largest magnitude anything inside the float cascade reaches, '
          'MATCHED-SIGN drive at 0 dBFS')
    print('=' * 108)
    print(f"{'design':36s} {'|h|_1':>12s} {'fixed H':>8s} "
          f"{'peak internal':>14s} {'headroom to 3.4e38':>20s}")
    print('-' * 108)
    worst_ratio = 0.0
    for name, d in CASES.items():
        h1 = l1_norm(d)
        H = max(0, math.ceil(math.log2(h1 / 8.0))) if h1 > 8.0 else 0
        # matched-sign drive: the input whose response IS |h|_1
        n = 4096
        hi = run_exact_cascade(impulse_q(1.0, n), d)
        drive = np.sign(hi[::-1][-1024:])
        drive[drive == 0] = 1
        xq = np.tile(np.round(drive * (1 << QS)).astype(np.int64), 4)
        tr = {}
        run_float_cascade(xq, offset_wire_coeffs(d), 32, 24, BLOCK, track=tr)
        ratio = tr['peak'] / 3.4028235e38
        worst_ratio = max(worst_ratio, ratio)
        print(f'{name:36s} {h1:12.1f} {H:8d} {tr["peak"]:14.1f} '
              f'{3.4028235e38 / max(tr["peak"], 1e-30):20.3e}x')
    print('-' * 108)
    print(f'WORST CASE USES {worst_ratio:.3e} OF THE float32 EXPONENT RANGE. '
          'Nothing in the float cascade can overflow;')
    print('the fixed path needs up to 8 mantissa bits of headroom over the '
          'same set (the |h|_1 column).')
    print()
    print('The ONE thing that still clamps is the cascade OUTPUT, because the '
          'inter-node bus is Q4.28:')
    print('a cascade whose |h|_1 exceeds 8 can hand on a word that does not fit, '
          'and both the guarded fixed')
    print('arm and the float arm clip it. Clipping is bounded and preserves sign; '
          'the wrap the guard exists')
    print('to prevent is what float removes without sizing anything.')


if __name__ == '__main__':
    main()
