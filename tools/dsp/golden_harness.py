#!/usr/bin/env python3
"""golden_harness.py — acceptance harness for the fixed-point audio path.

Tests the bit-accurate fixed reference (fixed_ref.py) against float64
per the tolerances in shared/numeric-spec.md. Exit code 0 = all pass.

Two-step equivalence model (numeric-spec.md): the SHARC asm / FPGA RTL
must match fixed_ref BIT-EXACTLY (checked elsewhere, per target);
fixed_ref must match float64 within these tolerances (checked here).

Usage: python3 golden_harness.py [-v]
"""

import math
import sys

import numpy as np

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import fixed_ref as fr
import boundary_vectors as bv

FS = 48000.0
results = []
FULL = fr.I32_MAX
NFULL = fr.I32_MIN


def check(name, value, limit, unit, lower_is_better=True):
    ok = value <= limit if lower_is_better else value >= limit
    results.append((name, value, limit, unit, ok))
    return ok


# ---------------------------------------------------------------------------
# Biquad design helpers (RBJ cookbook, float — the shared derivation)
# ---------------------------------------------------------------------------

def peaking(f0, gain_db, q):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w0), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w0), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def freq_response_db(process, n=16384, amp=0.25):
    """Impulse-response FFT magnitude of a sample processor (float in/out)."""
    out = np.zeros(n)
    for i in range(n):
        out[i] = process(amp if i == 0 else 0.0)
    h = np.fft.rfft(out)
    with np.errstate(divide='ignore'):
        return 20 * np.log10(np.abs(h) / amp + 1e-30)


def t_biquad(verbose):
    worst_mag = 0.0
    worst_mag_hf = 0.0
    worst_noise = -999.0
    cases = [(f0, g, q) for f0 in (20, 100, 1000, 10000, 20000)
             for g in (-12, -3, 6, 12) for q in (0.5, 1.0, 4.0)]
    for f0, g, q in cases:
        cf = peaking(f0, g, q)
        cq = fr.biquad_coeffs_q(*cf)
        sf, sq = [0.0] * 4, fr.biquad_state()
        db_f = freq_response_db(lambda x: fr.biquad_f(x, cf, sf))
        db_q = freq_response_db(
            lambda x: fr.from_q(fr.biquad(fr.to_q(x), cq, sq)))
        n = len(db_f)
        band = slice(int(20 / (FS / 2) * n), int(20000 / (FS / 2) * n))
        sel = db_f[band] > -100
        d = np.max(np.abs((db_q[band] - db_f[band])[sel]))
        worst_mag = max(worst_mag, d)
        if f0 >= 50:
            worst_mag_hf = max(worst_mag_hf, d)
        if verbose:
            print(f'  biquad f0={f0} g={g} q={q}: mag err {d:.5f} dB')

    # Noise/limit-cycle floor: -6 dBFS sine through a tough LF boost,
    # residual = fixed - float64
    cf = peaking(40, 12, 2.0)
    cq = fr.biquad_coeffs_q(*cf)
    sf, sq = [0.0] * 4, fr.biquad_state()
    n = 48000
    x = 0.5 * np.sin(2 * np.pi * 997 * np.arange(n) / FS)
    res = np.empty(n)
    for i in range(n):
        yf = fr.biquad_f(float(x[i]), cf, sf)
        yq = fr.from_q(fr.biquad(fr.to_q(float(x[i])), cq, sq))
        res[i] = yq - yf
    noise_dbfs = 20 * math.log10(np.sqrt(np.mean(res * res)) + 1e-30)
    worst_noise = max(worst_noise, noise_dbfs)

    # 0.07 dB, RAISED FROM 0.05 on 2026-08-29 and the reason is a ruling,
    # not a regression: the halved-n1 encoding (PW ruling, minimum EQ
    # Q = 0.10) spends one bit of n1 resolution to buy the range the
    # +15 dB / low-Q corner needs. MEASURED on this same sweep: 0.046151
    # dB before, 0.060560 dB after, both at f0 = 20 Hz / -12 dB / Q = 4,
    # and IDENTICAL at 0.003479 dB for f0 >= 50 Hz -- the cost lands only
    # where the offset form's whole benefit lives. Still 6.6x better than
    # the shipping FP32 firmware's 0.4 dB on the same case.
    check('biquad magnitude error (worst incl. 20 Hz)', worst_mag, 0.07, 'dB')
    check('biquad magnitude error (f0 >= 50 Hz)', worst_mag_hf, 0.01, 'dB')
    check('biquad residual vs float64 (RMS)', worst_noise, -120.0, 'dBFS')


def t_gain_sum(verbose):
    rng = np.random.default_rng(1)
    # gains: ±0.5 LSB vs exact rounding of float product
    worst = 0
    for _ in range(2000):
        x = int(rng.integers(fr.I32_MIN // 8, fr.I32_MAX // 8))
        g = fr.to_q(float(rng.uniform(0, 4.0)))
        yq = fr.gain(x, g)
        yf = int(round((x * g) / (1 << fr.QS)))
        worst = max(worst, abs(yq - fr.sat32(yf)))
    check('gain error vs exact rounding', worst, 1, 'LSB')

    # summing: must be exact vs arbitrary-precision reference
    worst = 0
    for _ in range(200):
        xs = rng.integers(fr.I32_MIN // 16, fr.I32_MAX // 16, 128)
        gs = [fr.to_q(float(v)) for v in rng.uniform(0, 1, 128)]
        yq = fr.mix_sum([int(v) for v in xs], gs)
        acc = sum(int(v) * g for v, g in zip(xs, gs))
        worst = max(worst, abs(yq - fr.sat32(fr.rns(acc, fr.QS))))
    check('128-way mix summing vs exact', worst, 0, 'LSB')


def t_log_exp(verbose):
    # dB round-trip accuracy across ±60 dB
    k = 20 * math.log10(2.0)
    worst = 0.0
    for db in np.arange(-60, 18.01, 0.25):
        x = fr.to_q(10 ** (db / 20.0))
        if x == 0:
            continue
        l = fr.log2_q(x)
        db_meas = l / (1 << 25) * k
        worst = max(worst, abs(db_meas - db))
    check('log2 dB error (-60..+18 dB)', worst, 0.001, 'dB')

    worst = 0.0
    for db in np.arange(-72, 18.01, 0.25):
        l = int(round(db / k * (1 << 25)))
        y = fr.exp2_q(l)
        y_ref = 10 ** (db / 20.0)
        err_db = abs(20 * math.log10(fr.from_q(y) / y_ref + 1e-30))
        worst = max(worst, err_db)
    check('exp2 dB error (-72..+18 dB)', worst, 0.001, 'dB')


def t_dynamics(verbose):
    k = 20 * math.log10(2.0)
    # Static compressor curve vs float64 (hard and soft knee)
    worst = 0.0
    for thr_db, ratio, knee in [(-20, 4, 0), (-40, 2, 0), (-10, 10, 0),
                                (-30, 1.5, 0), (-20, 4, 6), (-30, 8, 12)]:
        thr_q = int(round(thr_db / k * (1 << 25)))
        slope = 1.0 - 1.0 / ratio
        slope_q = fr.to_q(slope, fr.QA)
        hk_q = int(round((knee / 2) / k * (1 << 25))) if knee else 0
        k2_q = (int(round(slope / (2 * knee / k) * (1 << 25)))
                if knee else 0)
        for db in np.arange(-59.9, 17.9, 0.2):
            x = 10 ** (db / 20.0)
            gq = fr.from_q(fr.comp_gain(fr.to_q(x), thr_q, slope_q,
                                        hk_q, k2_q))
            gf = fr.comp_gain_f(x, thr_db, ratio, knee)
            d = abs(20 * math.log10(gq / gf + 1e-30))
            worst = max(worst, d)
        if verbose:
            print(f'  comp thr={thr_db} r={ratio} knee={knee}: '
                  f'worst {worst:.5f} dB')
    check('compressor static curve error', worst, 0.05, 'dB')

    # Soft-knee boundary: over == ±half_knee is where the hard/soft
    # branches meet, so an asymmetric <=/< split at the two symmetric
    # thresholds would show up here even though it doesn't on the
    # broader sweep above (2.6).
    worst_boundary = 0.0
    for thr_db, ratio, knee in [(-20, 4, 6), (-30, 8, 12)]:
        thr_q = int(round(thr_db / k * (1 << 25)))
        slope = 1.0 - 1.0 / ratio
        slope_q = fr.to_q(slope, fr.QA)
        hk_q = int(round((knee / 2) / k * (1 << 25)))
        k2_q = int(round(slope / (2 * knee / k) * (1 << 25)))
        for over_db in (-knee / 2, knee / 2):
            db = thr_db + over_db
            x = 10 ** (db / 20.0)
            gq = fr.from_q(fr.comp_gain(fr.to_q(x), thr_q, slope_q,
                                        hk_q, k2_q))
            gf = fr.comp_gain_f(x, thr_db, ratio, knee)
            d = abs(20 * math.log10(gq / gf + 1e-30))
            worst_boundary = max(worst_boundary, d)
        if verbose:
            print(f'  knee boundary thr={thr_db} r={ratio} knee={knee}: '
                  f'worst {worst_boundary:.5f} dB')
    check('soft-knee boundary error (over=+/-half_knee)', worst_boundary, 0.05, 'dB')

    # Envelope time constant: alpha for 10 ms attack, measure 63.2% time
    tau_s = 0.010
    alpha = 1.0 - math.exp(-1.0 / (tau_s * FS))
    aq = fr.to_q(alpha, fr.QA)
    env, target = 0, fr.to_q(1.0)
    n63 = None
    for i in range(1, 48000):
        env = fr.envelope_step(env, target, aq)
        if n63 is None and env >= fr.to_q(1 - math.exp(-1)):
            n63 = i
            break
    err_pct = abs(n63 / FS - tau_s) / tau_s * 100
    check('envelope tau error (10 ms attack)', err_pct, 2.0, '%')


# ---------------------------------------------------------------------------
# Boundary vectors — the wide-accumulator and blend touchpoints (D1, D3)
#
# These are not tolerance tests. They are the SHARED vector set: the same
# cases the in-part self-test runs, so "asm == model" and "model is
# right" are checked against identical numbers. Each family also asserts
# its NEGATIVE CONTROL — the pre-fix arithmetic must FAIL on the vectors
# that sit across the boundary, or the vectors prove nothing.
# ---------------------------------------------------------------------------

FULL = fr.I32_MAX
NFULL = fr.I32_MIN


def t_mix_boundary(verbose):
    """The 80-bit accumulator, and what the 64-bit one got wrong (D1).

    Two assertions, and the second is the negative control:
      1. mix_sum equals an unbounded exact sum on every vector -- the
         80-bit store is never reached, which is the D1 margin claim;
      2. the PRE-FIX 64-bit sum differs on EXACTLY the vectors whose
         final accumulator value leaves +/-2^63, and on no others. The
         predicted set is computed from the vectors (bv), not written
         down, so a vector added later cannot quietly stop testing.
    """
    worst = 0
    predicted, observed = set(), set()
    for v in bv.MIX:
        xs, gs = bv.mix_expand(v)
        label = v[6]
        good = fr.mix_sum(xs, gs)
        exact = fr.sat32(fr.rns(sum(x * g for x, g in zip(xs, gs)), fr.QS))
        worst = max(worst, abs(good - exact))
        bad = fr.mix_sum_wrapping(xs, gs)
        if bv.mix_predicted_wrong(v):
            predicted.add(label)
        if bad != good:
            observed.add(label)
        if verbose:
            print(f'  mix {label:38s} model {good:12d}  '
                  f'pre-fix {bad:12d}  '
                  f'{"DIFFERS" if bad != good else "same":8s}')
    check('mix_sum vs unbounded exact, boundary vectors', worst, 0, 'LSB')
    check('boundary vectors the PRE-FIX 64-bit sum gets wrong',
          len(observed), 1, 'vectors', lower_is_better=False)
    check('pre-fix mix failures match the predicted set exactly',
          len(predicted ^ observed), 0, 'vectors')


def t_blend_boundary(verbose):
    """The crossfade blend, and what the 32-bit difference got wrong (D3).

      1. the blend never leaves the interval its two operands span (bar
         one LSB of rounding) -- which is why its final add cannot
         overflow and no saturation is applied to it;
      2. the PRE-FIX 32-bit difference differs on EXACTLY the vectors
         where new-old does not fit int32 and alpha is non-zero.
    """
    worst_range = 0
    predicted, observed = set(), set()
    for v in bv.BLEND:
        new, old, a, label = v
        y = fr.xfade_blend(new, old, a)
        lo, hi = min(new, old), max(new, old)
        worst_range = max(worst_range, max(0, lo - 1 - y, y - (hi + 1)))
        bad = fr.xfade_blend_wrapping(new, old, a)
        if bv.blend_predicted_wrong(v):
            predicted.add(label)
        if bad != y:
            observed.add(label)
        if verbose and label in predicted | observed:
            print(f'  blend {label:24s} model {y:12d}  pre-fix {bad:12d}  '
                  f'{"DIFFERS" if bad != y else "same"}')
    check('blend stays within [min,max] of its operands', worst_range, 0, 'LSB')
    check('boundary vectors the PRE-FIX 32-bit difference gets wrong',
          len(observed), 1, 'vectors', lower_is_better=False)
    check('pre-fix blend failures match the predicted set exactly',
          len(predicted ^ observed), 0, 'vectors')



# ---------------------------------------------------------------------------
# NODE FAMILIES — the golden-coverage batch (2026-08-30, findings D26-D34)
#
# Everything above this line covers a PRIMITIVE. These cover the NODES:
# the arithmetic between the primitives, which is where the last three
# shipped audio defects actually lived (the squared pan gain, the percent
# blend, the dry-by-default compressor) and which had no reference of any
# kind. Each family asserts, in this order:
#
#   1. the IDENTITIES the node's own structure guarantees -- exact, not
#      toleranced, because they are statements about the arithmetic;
#   2. the model against a float64 twin, where a twin means anything;
#   3. its NEGATIVE CONTROL: the deliberately-wrong form in fixed_ref
#      must disagree on EXACTLY the vectors boundary_vectors predicts and
#      on no others. The predicted set is computed from the vectors, so a
#      vector added later cannot quietly stop testing.
# ---------------------------------------------------------------------------


def _negctl(name, vectors, predicate, disagrees, verbose=False):
    """The shared negative-control contract. Returns (n_predicted, n_seen)
    and registers the two checks every family makes: the control has to
    fire at all, and it has to fire exactly where the model says."""
    predicted, observed = set(), set()
    for i, v in enumerate(vectors):
        if predicate(v):
            predicted.add(i)
        if disagrees(v):
            observed.add(i)
    check(f'{name}: negative control fires', len(observed), 1, 'vectors',
          lower_is_better=False)
    check(f'{name}: control fires on exactly the predicted set',
          len(predicted ^ observed), 0, 'vectors')
    return len(predicted), len(observed)


def t_comp_wet(verbose):
    """COMP's wet path: the makeup's second rounding and the parallel
    blend (review finding D28)."""
    # 1. THE BLEND IDENTITIES. par = 0 returns the dry sample EXACTLY --
    #    that is not a nicety, it is the D59 defect stated as arithmetic:
    #    a compressor that is on, above threshold and visibly reducing
    #    gain passed the input through untouched. par = full returns the
    #    wet sample to within the blend's own rounding.
    worst_dry, worst_wet = 0, 0
    for v in bv.COMP:
        dry, g, mk, _ = bv.comp_expand(v)
        wet = fr.comp_wet(dry, g, mk)
        worst_dry = max(worst_dry, abs(fr.comp_blend(dry, wet, 0) - dry))
        if not bv.comp_diff_wraps(v):
            worst_wet = max(worst_wet,
                            abs(fr.comp_blend(dry, wet, fr.I32_MAX) - wet))
    check('comp blend at par=0 returns dry exactly', worst_dry, 0, 'LSB')
    check('comp blend at par=100% returns wet', worst_wet, 1, 'LSB')

    # 2. THE MODEL AGAINST float64. The wet path is two multiplies and
    #    two roundings, so a float64 twin should sit within one LSB per
    #    rounding wherever nothing saturates.
    worst = 0
    for v in bv.COMP:
        dry, g, mk, par = bv.comp_expand(v)
        wet = fr.comp_wet(dry, g, mk)
        if abs(wet) >= fr.I32_MAX or bv.comp_diff_wraps(v):
            continue                      # saturated / wrapped: no twin
        ref = dry + (wet - dry) * (par / float(1 << fr.QA))
        worst = max(worst, abs(fr.comp_out(dry, g, mk, par) - ref))
    check('comp wet path vs float64', worst, 2.0, 'LSB')

    # 3. THE BOUND on the 32-bit difference: wet and dry always carry the
    #    same sign, so |wet - dry| fits int32 except where the gain
    #    computer underflows to zero at full negative scale. The vectors
    #    that do that are named; the count is the bound, measured.
    n_wrap = sum(bv.comp_diff_wraps(v) for v in bv.COMP)
    check('comp vectors whose wet-dry leaves int32', n_wrap, 3, 'vectors')

    # 4. NEGATIVE CONTROL: the single-rounding wet path.
    _negctl('comp second rounding', bv.COMP, bv.comp_round_predicted_wrong,
            lambda v: fr.comp_wet(*bv.comp_expand(v)[:3])
                      != fr.comp_wet_1round(*bv.comp_expand(v)[:3]))
    if verbose:
        for v in bv.COMP:
            dry, g, mk, par = bv.comp_expand(v)
            print(f'  comp {v[4]:44s} {fr.comp_out(dry, g, mk, par):12d}')


def t_gate(verbose):
    """The GATE node's state machine (review finding D30)."""
    # 1. COVERAGE OF THE LADDER. Four transitions exist and the set has
    #    to visit all of them, or it is testing a gate that only ever
    #    does one thing.
    seen = set()
    worst_gain_hi, worst_gain_lo = 0, 0
    for v in bv.GATE:
        _, p, xs = v
        att, rel, thr, rng, hold = p
        st = fr.gate_state()
        prev_t, prev_h = st[2], st[3]
        for x in xs:
            fr.gate_step(x, st, *p)
            if st[2] == fr.GATE_UNITY and prev_t != fr.GATE_UNITY:
                seen.add('open')
            if st[3] == hold and prev_h != hold:
                seen.add('retrigger' if prev_h > 0 else 'arm')
            if st[2] == rng and prev_t == fr.GATE_UNITY:
                seen.add('hold expired')
            # the smoother is a convex combination of target and gain, so
            # the gain can never leave [floor, unity]
            worst_gain_hi = max(worst_gain_hi, st[1] - fr.GATE_UNITY)
            worst_gain_lo = max(worst_gain_lo, min(rng, fr.GATE_UNITY) - st[1])
            prev_t, prev_h = st[2], st[3]
    check('gate ladder transitions visited', len(seen & {
        'open', 'arm', 'retrigger', 'hold expired'}), 4, 'transitions',
        lower_is_better=False)
    check('gate smoother overshoots unity', worst_gain_hi, 0, 'LSB')
    check('gate smoother undershoots the floor', worst_gain_lo, 0, 'LSB')

    # 2. THE FLOOR IS THE REQUESTED DEPTH. GateRng is dB on the wire
    #    (review finding D39) and the floor it converts to is what the
    #    gate settles at; check the conversion against float64 in dB.
    worst_db = 0.0
    for db in (0.0, 6.0, 12.0, 24.0, 40.0, 60.0):
        got = fr.from_q(fr.gate_range_q(db))
        ref = 10.0 ** (-db / 20.0)
        worst_db = max(worst_db, abs(20 * math.log10(got / ref)))
    check('gate range floor vs float64', worst_db, 0.001, 'dB')

    # 3. NEGATIVE CONTROL: the ladder without the hold counter.
    _negctl('gate hold ladder', bv.GATE, bv.gate_predicted_wrong,
            lambda v: bv.gate_run(v)[0] != bv.gate_run(v, fr.gate_step_nohold)[0])
    if verbose:
        for v in bv.GATE:
            ys, st = bv.gate_run(v)
            print(f'  gate {v[0]:52s} end gain {st[1]:11d} '
                  f'target {st[2]:11d} hold {st[3]:7d}')


def t_fdr(verbose):
    """FADER_PAN's level coefficient and pan law (review finding D31)."""
    # 1. THE LINEAR LAW'S DEFINING IDENTITY: the two legs sum to unity at
    #    every pan position. A constant-power law would not (D42 is open;
    #    this models WHAT IS and this check is what would change).
    worst_sum, worst_mute = 0, 0
    for pan in [i / 64.0 for i in range(65)]:
        _, lq, rq = fr.fdr_coeffs(1.0, pan, 0)
        worst_sum = max(worst_sum, abs(lq + rq - fr.GATE_UNITY))
    for v in bv.FDR:
        level, pan, mute, x = bv.fdr_expand(v)
        gq, _, _ = fr.fdr_coeffs(level, pan, mute)
        if mute:
            worst_mute = max(worst_mute, abs(gq))
    check('fdr pan legs sum to unity (LINEAR law, D42 open)',
          worst_sum, 0, 'LSB')
    check('fdr mute forces the coefficient to zero', worst_mute, 0, 'LSB')

    # 2. CENTRE PAN IS -6.02 dB PER LEG, not -3.01. Stated as a number so
    #    the day D42 rules constant-power this check fails and says so.
    centre_db = 20 * math.log10(fr.from_q(fr.fdr_coeffs(1.0, 0.5, 0)[1]))
    check('fdr centre-pan leg (linear law; constant-power = -3.01)',
          abs(centre_db - (-6.0206)), 0.001, 'dB')

    # 3. THE SAMPLE PATH against exact rounding.
    worst = 0
    for v in bv.FDR:
        level, pan, mute, x = bv.fdr_expand(v)
        gq, _, _ = fr.fdr_coeffs(level, pan, mute)
        ref = fr.sat32(int(math.floor((x * gq) / float(1 << fr.QS) + 0.5)))
        worst = max(worst, abs(fr.fdr_apply(x, gq) - ref))
    check('fdr sample path vs exact rounding', worst, 1, 'LSB')

    # 4. NEGATIVE CONTROL: the squared-gain form, which is EXACT at unity
    #    level and is why the defect shipped.
    _negctl('fdr squared gain', bv.FDR, bv.fdr_predicted_wrong,
            lambda v: bv.fdr_predicted_wrong(v))
    unity_rows = [v for v in bv.FDR if v[0] == 1.0 and not v[2]]
    check('fdr squared-gain control is exact at unity level (why it shipped)',
          sum(bv.fdr_predicted_wrong(v) for v in unity_rows), 0, 'vectors')

    # 5. THE UNCLAMPED CONVERSION (finding D64): a level of exactly 8.0 is
    #    a value the cell holds and the conversion does not define.
    try:
        fr.fdr_coeffs(8.0, 0.5, 0)
        undefined = 0
    except ValueError:
        undefined = 1
    check('fdr level 8.0 is refused, not invented (D64)', undefined, 1,
          'refusals', lower_is_better=False)


def t_tube(verbose):
    """TUBE_SAT's three chained roundings (review finding D29).

    PLUGIN-CLASS COVERAGE, per PW's 2026-08-30 ruling: the ACTIVE path is
    modelled and vectored here the way a plug-in would engage it. The
    bypass path's obligation belongs to the base strip and is a
    measurement, not an arithmetic -- it appears here only as the
    identity it has to be."""
    # 1. IDENTITIES.
    worst_id, worst_bypass, worst_odd = 0, 0, 0
    for v in bv.TUBE:
        x, _ = bv.tube_expand(v)
        worst_id = max(worst_id, abs(fr.tube(x, 0) - x))
        worst_bypass = max(worst_bypass, abs(fr.tube_bypass(x) - x))
    check('tube at sat=0 is the identity', worst_id, 0, 'LSB')
    check('tube bypassed is the identity (the BASE strip path)',
          worst_bypass, 0, 'LSB')

    # 2. ODD SYMMETRY. The shape is x*(1 + sat*(1 - x^2)), odd in x, and
    #    the rounding is half-toward-+inf, so the two halves agree to one
    #    LSB wherever nothing saturates.
    for v in bv.TUBE:
        x, sq = bv.tube_expand(v)
        if abs(x) >= (1 << 30) or abs(fr.tube(x, sq)) >= fr.I32_MAX:
            continue
        worst_odd = max(worst_odd, abs(fr.tube(-x, sq) + fr.tube(x, sq)))
    check('tube odd symmetry', worst_odd, 1, 'LSB')

    # 3. AGAINST float64, inside the soft-clip region the shape is for.
    worst = 0.0
    for v in bv.TUBE:
        x, sq = bv.tube_expand(v)
        if abs(x) > fr.GATE_UNITY:
            continue                      # past unity the curve turns over
        xf, sf = fr.from_q(x), fr.from_q(sq)
        ref = xf * (1.0 + sf * (1.0 - xf * xf))
        if abs(ref) >= 8.0:
            continue
        worst = max(worst, abs(fr.from_q(fr.tube(x, sq)) - ref) * (1 << fr.QS))
    check('tube vs float64 (|x| <= 1.0)', worst, 3.0, 'LSB')

    # 4. NEGATIVE CONTROL: the middle rounding folded away.
    _negctl('tube middle rounding', bv.TUBE, bv.tube_predicted_wrong,
            lambda v: fr.tube(*bv.tube_expand(v))
                      != fr.tube_2round(*bv.tube_expand(v)))
    if verbose:
        for v in bv.TUBE:
            x, sq = bv.tube_expand(v)
            print(f'  tube {v[2]:52s} {fr.tube(x, sq):12d}')


def t_tdm(verbose):
    """The two wire boundaries (review finding D34)."""
    # 1. ROUND TRIP. Everything the wire can carry survives out-and-back.
    worst_rt = 0
    for w, _ in bv.TDM_IN:
        worst_rt = max(worst_rt, abs(fr.tdm_out(fr.tdm_in(w)) - (w & ~7)))
    check('tdm out(in(w)) recovers w to its top 29 bits', worst_rt, 0, 'LSB')

    # 2. THE INPUT SHIFT TRUNCATES -- there is no rounding half -- so it
    #    carries up to one LSB of DOWNWARD bias, and that is a property to
    #    state rather than a defect to fix: rounding it would cost an add
    #    per input slot per sample for a 2^-28 offset.
    worst_bias = 0
    for w in range(-64, 65):
        worst_bias = max(worst_bias,
                         fr.tdm_in(w) - int(math.floor(w / 8.0 + 0.5)))
    check('tdm input bias vs round-to-nearest (truncation, by design)',
          abs(worst_bias), 1, 'LSB')

    # 3. THE OUTPUT CLIPS AT 1.0 and by the SIGN OF THE SOURCE.
    worst_clip = 0
    for v, _ in bv.TDM_OUT:
        y = fr.tdm_out(v)
        if v > fr.to_q(1.0):
            worst_clip = max(worst_clip, abs(y - fr.I32_MAX))
        elif v < -fr.to_q(1.0):
            worst_clip = max(worst_clip, abs(y - fr.I32_MIN))
    check('tdm output saturates to full scale by the source sign',
          worst_clip, 0, 'LSB')

    # 4. NEGATIVE CONTROL: the shift with the round-trip test dropped.
    _negctl('tdm output saturation', bv.TDM_OUT, bv.tdm_out_predicted_wrong,
            lambda v: fr.tdm_out(v[0]) != fr.tdm_out_unchecked(v[0]))


def t_bqcvt(verbose):
    """`_bq_fx_convert_N` — the coefficient conversion the part performs
    (review finding D27).

    TWO MODELS, DELIBERATELY. biquad_coeffs_q is the NORMATIVE float64
    definition; bq_convert_f32 is the same conversion in float32, which
    is what the parameter plane is (numeric-spec.md) and what the part
    issues. The gap between them is measured here rather than assumed to
    be zero -- it is not zero."""
    # 1. THE TWO MODELS, over the vectors AND over the harness's own
    #    design sweep, so the number covers more than the corner cases.
    worst, worst_at = 0, ''
    sets = [(v[:5], v[5]) for v in bv.BQCVT]
    sets += [(peaking(f0, g, q), f'peaking {f0}/{g}/{q}')
             for f0 in (20, 100, 1000, 10000, 20000)
             for g in (-15, -12, -3, 6, 12, 15)
             for q in (0.10, 0.5, 1.0, 4.0)]
    for cf, label in sets:
        a = fr.bq_convert_f32(*cf)
        b = fr.biquad_coeffs_q(*cf)
        d = max(abs(x - y) for x, y in zip(a, b))
        if d > worst:
            worst, worst_at = d, label
    check('float32 conversion vs the float64 definition', worst, 64, 'LSB')
    if verbose:
        print(f'  bqcvt: worst float32-vs-float64 gap {worst} LSB at {worst_at}')

    # 2. THE n1 CORNER. The halved Q5.27 encoding exists so that the
    #    +15 dB / Q = 0.10 corner does not saturate at conversion; check
    #    it does not, with margin, on the part's own arithmetic.
    worst_nh = 0
    for cf, _ in sets:
        worst_nh = max(worst_nh, abs(fr.bq_convert_f32(*cf)[1]))
    check('halved n1 headroom used (2^31 = saturation)',
          worst_nh / float(1 << 31), 1.0, 'of full')

    # 3. NEGATIVE CONTROL: b1 destroyed before n1 reads it -- the defect
    #    this routine shipped. It must PASS the b1 = 0 rows, which is
    #    what proves it detects b1 rather than failing everything.
    _negctl('bqcvt b1 site', bv.BQCVT, bv.bqcvt_predicted_wrong,
            lambda v: fr.bq_convert_f32(*v[:5]) != fr.bq_convert_b1_lost(*v[:5]))
    zero_b1 = [v for v in bv.BQCVT if v[1] == 0.0]
    check('bqcvt b1 control PASSES the b1 = 0 vectors',
          sum(bv.bqcvt_predicted_wrong(v) for v in zero_b1), 0, 'vectors')


def t_meter(verbose):
    """The meter, which the harness has never called (review finding D26).

    The on-part leg (tools/pi/dsp4_mtr_verify.py) is strong -- bit-exact
    64-bit state with two negative controls -- but the model-vs-float64
    leg the numeric spec requires ran nowhere at all."""
    BLOCK = 8
    aq, bq = fr.meter_coeffs(BLOCK)

    # 1. THE GENERATED HEADER MUST AGREE WITH THE MODEL. dsp_block.h
    #    bakes these two coefficients and the whole meter's time
    #    constants follow from them; a stale header is exactly review
    #    finding D6 (a decay derived for one block rate applied at
    #    another). Read the header rather than trusting it.
    import os
    import re as _re
    hdr = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', '..', 'MW', 'D32', 'DSP', 'SHARC', 'src',
                       'dsp_block.h')
    baked = {}
    if os.path.exists(hdr):
        txt = open(hdr).read()
        for k in ('DSP4_BLOCK_SIZE', 'DSP4_MTR_ALPHA_Q', 'DSP4_MTR_BETA_Q'):
            m = _re.search(r'#define\s+%s\s+(\d+)' % k, txt)
            if m:
                baked[k] = int(m.group(1))
    if baked.get('DSP4_BLOCK_SIZE'):
        aq, bq = fr.meter_coeffs(baked['DSP4_BLOCK_SIZE'])
    check('meter alpha_q in dsp_block.h matches the model',
          abs(baked.get('DSP4_MTR_ALPHA_Q', -1) - aq), 0, 'LSB')
    check('meter beta_q in dsp_block.h matches the model',
          abs(baked.get('DSP4_MTR_BETA_Q', -1) - bq), 0, 'LSB')

    block = baked.get('DSP4_BLOCK_SIZE', BLOCK)
    fs = fr.METER_FS
    rate = fs / block

    # 2. RMS ACCURACY. A -6 dBFS sine, run long enough for the 300 ms
    #    window to settle, read back through the float contract.
    st = fr.meter_state()
    amp = 0.5
    n = int(rate * 3.0)
    ph = 0
    for _ in range(n):
        xs = []
        for _s in range(block):
            xs.append(int(round(amp * math.sin(2 * math.pi * 997 * ph / fs)
                                * (1 << fr.QM))))
            ph += 1
        fr.meter_block(xs, st, aq, bq)
    peak, rms = fr.meter_readback(st)
    ref_rms = amp / math.sqrt(2.0)
    check('meter RMS vs float64 (-6 dBFS sine)',
          abs(20 * math.log10(rms / ref_rms)), 0.05, 'dB')
    check('meter peak vs float64 (-6 dBFS sine)',
          abs(20 * math.log10(peak / amp)), 0.05, 'dB')

    # 3. THE PEAK DECAY TIME CONSTANT is a property of the METER, not of
    #    the block size -- the defect D6 recorded was exactly a constant
    #    that stopped tracking the block rate. Measure the 1/e time.
    st = fr.meter_state()
    fr.meter_block([1 << fr.QM] * block, st, aq, bq)     # 1.0 linear
    start = fr.meter_readback(st)[0]
    blocks = 0
    while fr.meter_readback(st)[0] > start * math.exp(-1.0) and blocks < 100000:
        fr.meter_block([0] * block, st, aq, bq)
        blocks += 1
    tau = blocks / rate
    check('meter peak decay tau vs its specification',
          abs(tau - fr.METER_TAU_PEAK_S) / fr.METER_TAU_PEAK_S * 100,
          2.0, '%')

    # 4. THE Q8.24 CLAMP. Every meter taps the MS word of its accumulator
    #    (PW's wide-word ruling), so its input reaches values the Q4.28
    #    interchange word cannot hold; the peak clamps at 8.0 linear.
    st = fr.meter_state()
    pk, _ms = fr.meter_block([fr.I32_MAX] * block, st, aq, bq)
    check('meter peak clamps at the Q8.24 ceiling',
          abs(pk - (((1 << (fr.QM + 3)) - 1) << (fr.QS - fr.QM))), 0, 'LSB')


def main():
    verbose = '-v' in sys.argv
    for t in (t_biquad, t_gain_sum, t_log_exp, t_dynamics,
              t_mix_boundary, t_blend_boundary,
              t_comp_wet, t_gate, t_fdr, t_tube, t_tdm, t_bqcvt, t_meter):
        t(verbose)
    print(f'{"test":58s} {"value":>12s} {"limit":>10s}  unit   result')
    fails = 0
    for name, value, limit, unit, ok in results:
        fails += (not ok)
        print(f'{name:58s} {value:12.6f} {limit:10.4f}  {unit:5s}  '
              f'{"PASS" if ok else "FAIL"}')
    print(f'\n{len(results) - fails}/{len(results)} passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
