#!/usr/bin/env python3
"""dyn_state_bound.py — the DYNAMICS path's state, bounded.

RIG C's still-open list ends on it: "dynamics envelopes carry the same
wrap argument and were not priced at all." This is that pricing, and the
answer is that they DO NOT carry the same argument -- not because the
dynamics are gentler, but because of a structural property their
recursion has and a biquad's does not, and the property is provable
rather than measured.

THE BIQUAD'S HAZARD, in one line: a resonant pole pair whose numerator
does not cancel it has |h|_1 far above 1 -- worst 378 over the DEFS
space -- so a bounded input reaches an unbounded-looking state, and
under round-once that state WRAPS and the wrap is fed back into the
poles. Headroom sized on |h|_1 is what buys the guarantee back.

THE ENVELOPE'S RECURSION IS A CONVEX COMBINATION:

    env' = env + alpha * (x - env) = (1 - alpha) * env + alpha * x

with alpha a Q0.31 word, so 0 <= alpha < 1 BY FORMAT. Therefore
|env'| <= max(|env|, |x|) for every sample, whatever alpha is, and by
induction |env| <= max|x| over the whole history. It cannot exceed its
input; there is nothing to guard and no headroom to spend. Equivalently:
the smoother's impulse response is alpha*(1-alpha)^n, which is
NON-NEGATIVE, so |h|_1 = sum h[n] = H(1) = 1 EXACTLY -- the l1 norm the
whole guard is sized on is one, for every attack and every release time
in the product's range.

THE ATTACK/RELEASE SWITCH DOES NOT BREAK IT, which is the part worth
saying out loud, because a switched system usually does break bounds
proved for a fixed one. Here the bound holds per SAMPLE for whichever
alpha was chosen, and both are in [0,1); the max is over both, so the
induction goes through unchanged.

WHAT THIS SCRIPT REPORTS.

  1. The envelope, numerically, over the attack/release range and four
     adversarial inputs -- the bound above, exercised rather than
     asserted, including the switched case.
  2. The GAIN COMPUTER's log-domain intermediates over the parameter
     space and the whole input range, each against its own format's
     ceiling: lvl, over, the knee's t and t*t, gr, and exp2's output.
  3. The dynamics SIDECHAIN filters, which ARE biquads and so ARE the
     other argument: their |h|_1 over the parameter range, and the H the
     guard would size for them.
  4. What round-once would delete in the dynamics path if it were
     applied there, and what would wrap if it were.

Usage: python3 dyn_state_bound.py [--quick]
"""

import csv
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr
import bq_state_bound as SB
import bq_h_load as HL

FS = 48000.0
QS = fr.QS if hasattr(fr, 'QS') else 28
UNITY = 1 << 28
CEIL_Q428 = 8.0                 # Q4.28's ceiling
CEIL_Q625 = 64.0                # Q6.25's ceiling, the log2 domain

# The parameter ranges. THE DEFS FILE DOES NOT BOUND THESE -- the
# dynamics parameters arrive as floats in the node's param string
# (dsp.csv: threshold_db, ratio, attack_ms, release_ms, knee_db,
# range_db, filter_hpf, filter_lpf, filter_q) and no range table
# constrains them, so what is swept here is a generous superset of what
# a console surface can send and is stated rather than assumed.
ATT_MS = [0.05, 0.1, 0.5, 1.0, 5.0, 20.0, 100.0, 500.0]
REL_MS = [1.0, 5.0, 20.0, 100.0, 500.0, 2000.0, 5000.0]
THR_DB = [-60.0, -40.0, -20.0, -10.0, 0.0]
RATIO = [1.0, 1.5, 2.0, 4.0, 8.0, 20.0, 100.0]
KNEE_DB = [0.0, 3.0, 6.0, 12.0, 24.0]
SC_F = [20.0, 80.0, 400.0, 2000.0, 8000.0, 18000.0]
SC_Q = [0.1, 0.5, 0.707, 1.0, 2.0, 5.0, 10.0]

# ---------------------------------------------------------------------------
# THE SIDECHAIN'S RANGES COME FROM THE CONTRACT (S16-6, 2026-09-10).
#
# Section 3 used to sweep the HPF and the LPF over the SAME grid, SC_F, up
# to 18 kHz, and reported H = 5 -- a FAIL -- with its worst corner at an
# HPF of 8 kHz. The defs do not allow an HPF of 8 kHz. `Chan001GateFilterHpf001`
# is `0=20/64=1000/[Log]` and `Chan001GateFilterLpf001` is
# `0=500/127=20000/[Log]`: two DIFFERENT ranges that overlap only between
# 500 Hz and 1 kHz. A bound taken over settings the wire cannot carry is
# not a bound on the product, and this one was over-stating by a whole
# headroom bit.
#
# Read from the landed CSV rather than transcribed, for the same reason
# every other number here is: a transcription is a second source of truth.
# If the defs submodule is not present the fallback grid is used and the
# section SAYS it is running unbounded, rather than quietly reverting to
# the number that was wrong.
# ---------------------------------------------------------------------------
# GateThr's own contract range, `0=-80/127=0/[Lin]` (Chan001GateThr001),
# and the shift S15 documented for the linear-threshold arm.
THR_LO, THR_HI = -80.0, 0.0
LINTHR_BAR = 0.0002

SC_CELLS = {'hp': 'Chan001GateFilterHpf001', 'lp': 'Chan001GateFilterLpf001',
            'q': 'Chan001GateFilterQ001'}
_LAW_RE = re.compile(
    r'^\s*(-?[\d.]+)=(-?[\d.]+)/(-?[\d.]+)=(-?[\d.]+)/\[(\w+)\]\s*$')


def _log_grid(lo, hi, n):
    return [lo * (hi / lo) ** (i / (n - 1.0)) for i in range(n)]


def sidechain_ranges(n=13, nq=11):
    """{'hp': [...], 'lp': [...], 'q': [...]}, or None if defs is absent."""
    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, '..', '..', 'defs', 'products', 'd24',
                            'dsp.csv')
    if not os.path.exists(csv_path):
        return None
    want = {v: k for k, v in SC_CELLS.items()}
    out = {}
    with open(csv_path, newline='') as fh:
        for row in csv.reader(fh):
            if not row or row[0] not in want:
                continue
            for field in row:
                m = _LAW_RE.match(field or '')
                if m:
                    lo, hi = float(m.group(2)), float(m.group(4))
                    key = want[row[0]]
                    out[key] = _log_grid(lo, hi, nq if key == 'q' else n)
                    out[key + '_span'] = (lo, hi)
                    break
    return out if len(SC_CELLS) == len({k for k in out if '_span' not in k}) \
        else None


def alpha_q(tau_ms):
    """The Q0.31 smoothing coefficient for a time constant, as the
    firmware computes it."""
    tau = max(tau_ms, 1e-6) * 1e-3
    a = 1.0 - math.exp(-1.0 / (FS * tau))
    return max(1, min((1 << 31) - 1, int(round(a * (1 << 31)))))


def env_sweep(quick):
    print('1. THE ENVELOPE: env\' = (1-alpha)*env + alpha*x, alpha in '
          'Q0.31\n')
    worst = 0.0
    worst_tag = None
    amin, amax = 1 << 31, 0
    n = 2000 if quick else 20000
    # Four adversarial inputs. The smoother's impulse response is
    # non-negative, so the input that ACHIEVES |h|_1 is a full-scale STEP
    # -- there is no sign pattern to match, which is itself the
    # difference from the biquad case.
    drives = {
        'full-scale step': lambda i: UNITY - 1,
        'full-scale square, 1 sample': lambda i: (UNITY - 1) * (1 - 2 * (i & 1)),
        'full-scale square, 64 samples': lambda i:
            (UNITY - 1) * (1 - 2 * ((i >> 6) & 1)),
        'alternating rails, worst switch': lambda i:
            (UNITY - 1) if (i % 97) < 48 else -(UNITY - 1),
    }
    for att in ATT_MS:
        for rel in (REL_MS if not quick else REL_MS[::3]):
            aa, ar = alpha_q(att), alpha_q(rel)
            amin, amax = min(amin, aa, ar), max(amax, aa, ar)
            for name, f in drives.items():
                env = 0
                peak = 0
                for i in range(n):
                    x = abs(f(i))
                    a = aa if x > env else ar
                    env = fr.envelope_step(env, x, a)
                    peak = max(peak, abs(env))
                r = peak / (UNITY - 1)
                if r > worst:
                    worst, worst_tag = r, (att, rel, name)
    print(f'   attack {min(ATT_MS)}-{max(ATT_MS)} ms, release '
          f'{min(REL_MS)}-{max(REL_MS)} ms')
    print(f'   alpha spans {amin} .. {amax} in Q0.31 '
          f'({amin / 2**31:.3e} .. {amax / 2**31:.6f}) -- all inside [0,1)')
    print(f'   worst |env| / max|x| over every (attack, release, drive): '
          f'{worst:.6f}')
    print(f'      at attack {worst_tag[0]} ms, release {worst_tag[1]} ms, '
          f'{worst_tag[2]}')
    print(f'   |h|_1 of the smoother, analytically: 1.000000 exactly '
          f'(h[n] = alpha*(1-alpha)^n >= 0, so |h|_1 = H(1) = 1)')
    ok = worst <= 1.0 + 1e-12
    print(f'   headroom bits the guard would size: '
          f'{HL.headroom_bits(1.0)}   -> {"NONE NEEDED" if ok else "FAIL"}')
    return ok


def gaincomp_sweep(quick):
    print('\n2. THE GAIN COMPUTER: every log-domain intermediate against '
          'its format\n')
    lv = [1, 2, 16, 1 << 10, 1 << 20, UNITY // 2, UNITY, 4 * UNITY,
          8 * UNITY - 1]
    if not quick:
        lv += [int(UNITY * (10 ** (d / 20.0))) for d in range(-100, 19)]
    lv = sorted({max(1, v) for v in lv})
    worst = {k: (0.0, None) for k in
             ('lvl', 'over', 't', 't2', 'gr', 'gain')}

    def note(k, v, tag):
        if abs(v) > worst[k][0]:
            worst[k] = (abs(v), tag)

    for thr_db in THR_DB:
        thr = int(round((thr_db / (20 * math.log10(2))) * (1 << 25)))
        for ratio in RATIO:
            slope = int(round((1.0 - 1.0 / ratio) * ((1 << 31) - 1)))
            for knee_db in KNEE_DB:
                hk = int(round((knee_db / 2 / (20 * math.log10(2)))
                               * (1 << 25)))
                k2 = 0 if knee_db == 0 else int(round(
                    (1.0 - 1.0 / ratio) / (2 * (knee_db /
                                                (20 * math.log10(2))))
                    * (1 << 25)))
                for x in lv:
                    tag = (thr_db, ratio, knee_db, x)
                    lvl = fr.log2_q(x)
                    note('lvl', lvl / (1 << 25), tag)
                    over = lvl - thr
                    note('over', over / (1 << 25), tag)
                    if over <= -hk:
                        continue
                    if hk and over < hk:
                        t = over + hk
                        note('t', t / (1 << 25), tag)
                        t2 = fr.rns(t * t, 25)
                        note('t2', t2 / (1 << 25), tag)
                        gr = fr.rns(t2 * k2, 25)
                    else:
                        gr = fr.rns(over * slope, 31)
                    note('gr', gr / (1 << 25), tag)
                    g = fr.comp_gain(x, thr, slope, hk, k2)
                    note('gain', g / UNITY, tag)

    print(f'   {"quantity":8s} {"format":8s} {"ceiling":>8s} {"worst":>10s} '
          f'{"headroom":>9s}   at (thr dB, ratio, knee dB, x)')
    rows = [('lvl', 'Q6.25', CEIL_Q625), ('over', 'Q6.25', CEIL_Q625),
            ('t', 'Q6.25', CEIL_Q625), ('t2', 'Q6.25', CEIL_Q625),
            ('gr', 'Q6.25', CEIL_Q625), ('gain', 'Q4.28', CEIL_Q428)]
    ok = True
    for k, fmt, ceil in rows:
        v, tag = worst[k]
        hd = ceil / max(v, 1e-30)
        if v >= ceil:
            ok = False
        print(f'   {k:8s} {fmt:8s} {ceil:8.1f} {v:10.4f} {hd:8.1f}x   {tag}')
    print('   the gain is the EXP2 output and is saturated by '
          '_exp2q_fx by construction')
    return ok


def sidechain_sweep(quick):
    print('\n3. THE SIDECHAIN FILTERS, which ARE biquads and DO carry the '
          'other argument\n')
    from bq_headroom_guard import hplp
    rng = sidechain_ranges(5 if quick else 13, 5 if quick else 11)
    if rng:
        hps, lps, qs = rng['hp'], rng['lp'], rng['q']
        print(f'   sweep bounded BY THE CONTRACT: HPF '
              f'{rng["hp_span"][0]:.0f}-{rng["hp_span"][1]:.0f} Hz, LPF '
              f'{rng["lp_span"][0]:.0f}-{rng["lp_span"][1]:.0f} Hz, Q '
              f'{rng["q_span"][0]}-{rng["q_span"][1]}  '
              f'(defs/products/d24/dsp.csv)')
    else:
        hps, lps, qs = SC_F, SC_F, SC_Q
        print('   *** defs is not checked out: sweeping the FALLBACK grid, '
              'which runs the HPF to 18 kHz where the contract stops it at '
              '1 kHz. The numbers below bound settings the wire cannot '
              'carry -- which is how this section read H = 5 until '
              '2026-09-10. ***')
    cfs, tags = [], []
    for hp, band in ((True, hps), (False, lps)):
        for f0 in band:
            for q in qs:
                cq = fr.biquad_coeffs_q(*hplp(f0, q, hp))
                cfs.append(HL.dequant(cq))
                tags.append(('hp' if hp else 'lp', f0, q))
    l1, _ = SB.l1_norm(cfs)
    hs = [SB.bits_for(v) for v in l1]
    i = int(np.argmax(l1))
    print(f'   {len(cfs)} HPF/LPF sections, HPF {hps[0]:.0f}-{hps[-1]:.0f} Hz '
          f'and LPF {lps[0]:.0f}-{lps[-1]:.0f} Hz, Q {qs[0]:.3g}-{qs[-1]:.3g}')
    print(f'   worst single-section |h|_1 = {l1[i]:.2f} '
          f'(+{20 * math.log10(l1[i]):.1f} dB) at {tags[i]}')
    print(f'   worst headroom bits: {int(max(hs))}')
    # the gate runs HPF then LPF as ONE two-stage cascade
    # HPF and LPF are INDEPENDENT parameters (filter_hpf, filter_lpf,
    # filter_q in the node's param string), so the cascade is swept over
    # both, including the settings where the HPF sits above the LPF --
    # which no one would dial deliberately and a recalled preset can
    # nevertheless contain.
    worst2, tag2 = 0.0, None
    for fh in hps:
        for fl in lps:
            for q in qs:
                cqs = [fr.biquad_coeffs_q(*hplp(fh, q, True)),
                       fr.biquad_coeffs_q(*hplp(fl, q, False))]
                b, _ = HL.l1_bound([HL.dequant(c) for c in cqs])
                if b > worst2:
                    worst2, tag2 = b, (fh, fl, q)
    h2 = HL.headroom_bits(worst2)
    print(f'   worst HPF+LPF CASCADE bound = {worst2:.2f} at HPF '
          f'{tag2[0]:.0f} Hz, LPF {tag2[1]:.0f} Hz, Q {tag2[2]:.3g}  '
          f'-> H = {h2}')
    if tag2[0] > tag2[1]:
        print('   (the worst corner has the HPF ABOVE the LPF -- a setting '
              'nobody dials and a recalled preset can carry)')
    if h2 == 0:
        print('   H = 0 across the range, which is what the generated '
              'nodes assume: the sidechain blocks carry the guard\'s '
              'header word for shape and nothing sizes them.')
    else:
        print(f'   *** H = {h2} IS REACHABLE WITHIN THE CONTRACT. The '
              'gate and talkback sidechain blocks carry the header word '
              'but NOTHING SIZES')
        print('   THEM -- they are left at H = 0. At this corner the '
              'sidechain detector can wrap under round-once. It is one')
        print('   at the extreme of parameters the DEFS file DOES bound '
              '-- HPF 20-1000 Hz, LPF 500-20000 Hz, Q 0.1-10 -- so it is')
        print('   a corner the wire can carry, and it is the one place in '
              'the tree where the guard is wired for shape and not')
        print('   for value.')
        print('   THE REASON IS NOT THE GUARD, IT IS THE CONVERSION: the '
              'gate and talkback nodes call _bq_fx_convert_N on EVERY')
        print('   invocation while their filter is on, not once per '
              'parameter change. There is no parameter-LOAD moment to')
        print('   hang a control-rate sizing off, and a per-sample sizer '
              'is not a thing. Converting those two sections when the')
        print('   parameters change -- which is also several hundred '
              'cycles a sample of pure waste -- is the fix, and it makes')
        print('   them the same shape as every other cascade. ***')
    return h2 == 0



def lut_form(quick):
    """5. THE LEVEL -> GAIN TABLE FORM (DSP4_DYN_LUT, S15).

    The dispatch asked for this analysis re-run "for the table form
    (ceilings, saturation once)", and the answer is that the table form
    is the EASIER of the two, for a reason that can be stated as a bound
    rather than as a sweep.

    WHAT THE PER-SAMPLE PATH BECOMES.  Today it is log2 -> knee -> exp2,
    and exp2 carries the one saturate in the gain computer.  Under the
    table it is: an index (shifts and a mask, no arithmetic on the
    value), two table reads, one multiply-and-round, one add.

    THE CEILING IS STRUCTURAL.  Every word in the table is the output of
    _compgain_fx, whose range is [0, 1<<QS]: comp_gain returns exactly
    unity below the knee and exp2_q(-gr) with gr >= 0 above it, and
    makeup is applied separately and afterwards.  So T[i] and T[i+1] are
    both in [0, 2^28], and the interpolation

        g = T[i] + rns((T[i+1] - T[i]) * frac, 31),   0 <= frac < 1

    is a CONVEX COMBINATION of two values in that interval and is
    therefore in that interval.  It cannot overflow, for the same kind
    of reason the envelope one-pole cannot: not because the inputs are
    gentle, but because the operator is an average.

    THE INTERMEDIATE CANNOT OVERFLOW EITHER.  |T[i+1] - T[i]| <= 2^28
    and frac < 2^31, so the product is under 2^59 in an 80-bit MR --
    two orders of magnitude of headroom -- and rns(.,31) brings it back
    to at most 2^28.

    SO THE TABLE FORM DELETES A SATURATE AND ADDS NONE.  _exp2q_fx's
    saturate still runs, once per table point, in the DESIGN step, where
    it is a block-rate cost on a value that is about to be stored rather
    than a per-sample cost on a value that is about to be heard.  That
    is the "saturation once" the dispatch asks about, and it is once per
    DESIGN rather than once per sample.

    The only new numeric question the table raises is INTERPOLATION
    ERROR, which is not a state bound and is not this tool's instrument:
    tools/dsp/dyn_lut_design.py measures it against fixed_ref directly.
    """
    print('5. THE LEVEL -> GAIN TABLE FORM (DSP4_DYN_LUT), ceilings and')
    print('   saturation')
    print()
    qs = 28
    unity = 1 << qs
    # The bound, checked rather than asserted, over the corners of the
    # documented parameter space and the whole of the table's index range.
    worst = 0
    for thr in (-60.0, -20.0, -0.5):
        for ratio in (1.5, 4.0, 100.0):
            for knee in (0.0, 6.0, 18.0):
                thrq, slope, halfk, k2 = _lut_params(thr, ratio, knee)
                for e in _lut_grid(quick):
                    g = fr.comp_gain(e, thrq, slope, halfk, k2)
                    if g < 0 or g > unity:
                        print('   *** a table word is OUTSIDE [0, 1] in '
                              'Q4.28: %d at thr %.1f ratio %.1f knee %.1f'
                              % (g, thr, ratio, knee))
                        return False
                    worst = max(worst, g)
    # THE LIMITER'S CORNERS, WITH THE NODE'S OWN WORDS (S16).
    #
    # The limiter is not a compressor at "ratio = infinity": the node's
    # block-rate conversion writes the four words directly --
    # `_lim_cgp_[1] = 0x7FFFFFFF`, halfk = 0, k2 = 0 -- and 0x7FFFFFFF
    # in Q0.31 is 1 - 2^-31, not 1. Sweeping a large float ratio would
    # model a slope word this product never writes, so the corners below
    # use the CONVERTED words, and the threshold spans the contract's
    # own range for `Aux001LimiterThr001` (0=-30/127=0/[Lin]).
    #
    # It is the sharpest curve the table carries -- an infinite ratio
    # with a hard knee is a corner -- which is why K = 4 was chosen
    # against it (dyn_lut_fx.asm's ladder) and why the bound is worth
    # checking here rather than assuming the compressor's covers it.
    lim_worst = 0
    for thr in (-30.0, -20.0, -10.0, -3.0, -0.5, 0.0):
        thrq = _lut_params(thr, 1.0, 0.0)[0]
        for e in _lut_grid(quick):
            g = fr.comp_gain(e, thrq, 0x7FFFFFFF, 0, 0)
            if g < 0 or g > unity:
                print('   *** a LIMITER table word is OUTSIDE [0, 1] in '
                      'Q4.28: %d at thr %.1f' % (g, thr))
                return False
            lim_worst = max(lim_worst, g)
    print('   the LIMITER (slope 0x7FFFFFFF, hard knee) over its contract')
    print('   threshold range -30..0 dB: every word inside [0, 1] in')
    print('   Q4.28, largest %d = %.6f' % (lim_worst, lim_worst / float(unity)))
    print('   every table word over the documented parameter corners is')
    print('   inside [0, 1] in Q4.28; the largest seen is %d = %.6f'
          % (worst, worst / float(unity)))
    print('   the per-sample interpolation is a CONVEX COMBINATION of two')
    print('   such words, so its output is inside the same interval and')
    print('   cannot wrap. No guard word, no saturate, nothing to size.')
    print('   the multiply-and-round intermediate is under 2^59 in an')
    print('   80-bit MR, so it cannot overflow either.')
    print('   _exp2q_fx\'s saturate still runs -- ONCE PER TABLE POINT in')
    print('   the DESIGN step, not once per sample in the audio path.')
    print('   THE TABLE FORM DELETES A SATURATE FROM THE PER-SAMPLE PATH')
    print('   AND ADDS NONE.')
    print()
    print('   Interpolation ERROR is a different instrument and is not')
    print('   here: tools/dsp/dyn_lut_design.py measures it against')
    print('   fixed_ref directly (0.0950 dB worst over the documented')
    print('   sweep at K = 4, against PW\'s 0.1 dB bar; the LIMITER\'s own')
    print('   worst over its six contract thresholds is 0.0604 dB).')
    print()
    return True


_LUT_K = 4
_LUT_OCTLO = 10
_LUT_OCTHI = 30


def _lut_params(thr_db, ratio, knee_db):
    kdb = 20.0 * math.log10(2.0)
    thrq = int(round(thr_db / kdb * (1 << 25)))
    slope = int(round((1.0 - 1.0 / ratio) * (1 << 31)))
    halfk = int(round((knee_db / 2.0) / kdb * (1 << 25)))
    k2 = (int(round((1.0 - 1.0 / ratio) / (2.0 * knee_db / kdb) * (1 << 25)))
          if knee_db > 0 else 0)
    return thrq, slope, halfk, k2


def _lut_grid(quick):
    """Every grid point the design step will ever write, computed the
    way dyn_lut_fx.asm computes it."""
    step = 4 if quick else 1
    n = ((_LUT_OCTHI - _LUT_OCTLO + 1) << _LUT_K) + 1
    for i in range(0, n, step):
        oct_ = (i >> _LUT_K) + _LUT_OCTLO
        sub = i & ((1 << _LUT_K) - 1)
        yield (((1 << _LUT_K) + sub) << oct_) >> _LUT_K


def linthr_shift(quick):
    """6. THE LINEAR-DOMAIN GATE THRESHOLD (DSP4_GATE_LINTHR, S15).

    `log2(env) >= thr` and `env >= 2^thr` decide the same thing, so the
    kernel converts the THRESHOLD once per block instead of the ENVELOPE
    once per sample. S15 documented the price as "at most 0.0002 dB of
    shift in the gate's effective threshold" from the two polynomials'
    error, and asserted it from their individual bounds.

    It is measurable rather than assertable, and this measures it: for
    each threshold the wire can carry, find the SMALLEST envelope each arm
    opens on -- the log arm by search over `log2_q`, the linear arm from
    `gate_thr_lin_q` directly -- and take the distance between them in dB.
    Both use the polynomials the part runs, so the answer is the part's.

    The range swept is the CONTRACT's, `0=-80/127=0/[Lin]`, not a
    convenient one.
    """
    print('\n6. THE LINEAR-DOMAIN GATE THRESHOLD (DSP4_GATE_LINTHR)\n')

    def open_env_log(thr_db):
        t = fr.gate_thr_q(thr_db)
        lo, hi = 1, (1 << 31) - 1
        while lo < hi:
            m = (lo + hi) // 2
            if fr.log2_q(m) >= t:
                hi = m
            else:
                lo = m + 1
        return lo

    n = 81 if quick else 801
    worst = (0.0, 0.0, 0, 0)
    over, lowest_ok = 0, None
    practical = 0.0
    for i in range(n):
        db = THR_LO + i * (THR_HI - THR_LO) / (n - 1.0)
        a, b = open_env_log(db), fr.gate_thr_lin_q(db)
        d = 20.0 * math.log10(a / b)
        if abs(d) > abs(worst[0]):
            worst = (d, db, a, b)
        if abs(d) > LINTHR_BAR:
            over += 1
            lowest_ok = db if lowest_ok is None else max(lowest_ok, db)
        if db >= -60.0 and abs(d) > abs(practical):
            practical = d
    print(f'   GateThr over the contract range {THR_LO:.0f} to {THR_HI:.0f} '
          f'dB (0={THR_LO:.0f}/127={THR_HI:.0f}/[Lin]), {n} points')
    print(f'   worst effective-threshold shift = {worst[0]:+.6f} dB at a '
          f'threshold of {worst[1]:.3f} dB')
    print(f'   (the log arm opens at envelope {worst[2]}, the linear arm at '
          f'{worst[3]} -- '
          f'{"ONE Q4.28 LSB apart" if abs(worst[2] - worst[3]) == 1 else "%d LSBs apart" % abs(worst[2] - worst[3])})')
    print(f'   over any threshold at or above -60 dB: {practical:+.6f} dB')
    if over:
        print(f'   {over} of {n} points exceed the documented '
              f'{LINTHR_BAR} dB, ALL of them at thresholds at or below '
              f'{lowest_ok:.1f} dB.')
        print('   The mechanism there is NOT the polynomials: at those '
              'thresholds the linear word itself is only a few tens of')
        print('   Q4.28 LSBs, so ONE LSB of quantisation is already worth '
              'more than the bar. The two arms are still one LSB apart.')
    else:
        print(f'   every point is inside the documented {LINTHR_BAR} dB.')
    # THE BAR IS THE PRACTICAL RANGE, and the reason is above: below
    # -77 dB the Q4.28 threshold word cannot represent the bar, so a
    # section that failed there would be measuring the word size and
    # calling it the arm.
    return abs(practical) <= LINTHR_BAR


def main():
    quick = '--quick' in sys.argv
    print('dyn_state_bound — the dynamics path\'s state under round-once\n')
    ok = env_sweep(quick)
    ok = gaincomp_sweep(quick) and ok
    ok = sidechain_sweep(quick) and ok
    print('\n4. WHAT ROUND-ONCE WOULD DELETE HERE, AND WHAT WOULD WRAP\n')
    print('   The dynamics path has no per-stage saturate of the biquad')
    print('   kind to delete. What it has is:')
    print('     _envq_fx        NO saturate at all, and correctly so --')
    print('                     fixed_ref.envelope_step\'s sat32 provably')
    print('                     never fires (section 1), so the asm')
    print('                     omitting it is an identity, not a')
    print('                     shortcut.')
    print('     _exp2q_fx       ONE saturate on the log2 -> linear')
    print('                     conversion, FEED-FORWARD. Deleting it')
    print('                     would wrap a large positive gain to a')
    print('                     NEGATIVE one -- a polarity inversion of')
    print('                     the whole strip -- and it is one')
    print('                     instruction on a branch that is already')
    print('                     there. There is nothing to win.')
    print('     _mrf_rns28[_simd]  the Q4.28 extract-and-saturate where')
    print('                     the gain is APPLIED. This is the GAIN')
    print('                     path\'s round-once question, priced')
    print('                     already (RIG C: 9.03 -> 3.55 c/sample/')
    print('                     strip, and the D20 mic-pre tap returns')
    print('                     the whole saving). It is feed-forward:')
    print('                     the wrap it would allow is a clipped')
    print('                     sample, not a state that rings on it.')
    print()
    print('   So the dynamics envelopes need NO guard, and the reason is')
    print('   not that they are gentle: it is that |h|_1 = 1 exactly for')
    print('   a one-pole smoother with a non-negative impulse response,')
    print('   against 378 for the worst biquad in the same design space.')
    print('   The per-cascade headroom pattern does not transfer because')
    print('   the hazard does not.')
    print()
    ok = lut_form(quick) and ok
    ok = linthr_shift(quick) and ok
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
