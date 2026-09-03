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

import math
import os
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
    cfs, tags = [], []
    for f0 in SC_F:
        for q in SC_Q:
            for hp in (True, False):
                cf = hplp(f0, q, hp)
                cq = fr.biquad_coeffs_q(*cf)
                cfs.append(HL.dequant(cq))
                tags.append(('hp' if hp else 'lp', f0, q))
    l1, _ = SB.l1_norm(cfs)
    hs = [SB.bits_for(v) for v in l1]
    i = int(np.argmax(l1))
    print(f'   {len(cfs)} HPF/LPF sections over {SC_F[0]}-{SC_F[-1]} Hz, '
          f'Q {SC_Q[0]}-{SC_Q[-1]}')
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
    for fh in SC_F:
        for fl in SC_F:
            for q in SC_Q:
                cqs = [fr.biquad_coeffs_q(*hplp(fh, q, True)),
                       fr.biquad_coeffs_q(*hplp(fl, q, False))]
                b, _ = HL.l1_bound([HL.dequant(c) for c in cqs])
                if b > worst2:
                    worst2, tag2 = b, (fh, fl, q)
    h2 = HL.headroom_bits(worst2)
    print(f'   worst HPF+LPF CASCADE bound = {worst2:.2f} at HPF '
          f'{tag2[0]:.0f} Hz, LPF {tag2[1]:.0f} Hz, Q {tag2[2]}  -> H = {h2}')
    if h2 == 0:
        print('   H = 0 across the range, which is what the generated '
              'nodes assume: the sidechain blocks carry the guard\'s '
              'header word for shape and nothing sizes them.')
    else:
        print(f'   *** H = {h2} IS REACHABLE. The gate and talkback '
              'sidechain blocks carry the header word but NOTHING SIZES')
        print('   THEM -- they are left at H = 0. At this corner the '
              'sidechain detector can wrap under round-once. It is one')
        print('   at the extreme of parameters the DEFS file does not '
              'bound, and it is the one place in the tree where the')
        print('   guard is wired for shape and not for value.')
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
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
