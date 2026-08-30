#!/usr/bin/env python3
"""boundary_vectors.py — THE boundary vector set, defined once.

Three consumers, one definition:
  golden_harness.py      model vs unbounded exact, plus the negative
                         control (the pre-fix arithmetic must fail
                         exactly the vectors that cross a boundary)
  dsp_codegen.py         emits them into lib/num_selftest.asm as .var
                         tables, so the part runs the same numbers
  tools/pi/dsp4_num_verify.py
                         reads the part's results back and diffs them
                         against fixed_ref

They exist because review findings D1 and D3 are both WRAP findings: the
arithmetic is correct everywhere except across a boundary that no
existing golden vector went near. A vector set that does not straddle
the boundary cannot tell the fixed code from the broken code.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr

FULL = fr.I32_MAX
NFULL = fr.I32_MIN
UNITY = fr.to_q(1.0)
HALF = fr.to_q(0.5)


# ---------------------------------------------------------------------------
# MIX — the 64-bit bus accumulator boundary (D1)
#
# Compact form (n1, x1, g1, n2, x2, g2): n1 contributions of x1*g1 then
# n2 of x2*g2. Unity x unity is exactly 2^56 in Q8.56 = 1.0 linear, so a
# count of 128 lands the sum EXACTLY on the old +/-128.0 boundary and
# 127/129 sit one contribution either side of it.
# ---------------------------------------------------------------------------

MIX = [
    (1,   FULL,  UNITY, 0, 0, 0,     'one x unity'),
    (1,   FULL,  NFULL, 0, 0, 0,     'one x -8.0'),
    (32,  FULL,  HALF,  0, 0, 0,     '32 x 0.5 = 16.0'),
    (1,   FULL,  FULL,  0, 0, 0,     'one x 7.999 = 64.0'),
    (2,   FULL,  FULL,  0, 0, 0,     'two x 64.0 = 127.99, just UNDER'),
    (127, UNITY, UNITY, 0, 0, 0,     '127 x 1.0 = 127.0, UNDER by one'),
    (128, UNITY, UNITY, 0, 0, 0,     '128 x 1.0 = 128.0, exactly AT'),
    (129, UNITY, UNITY, 0, 0, 0,     '129 x 1.0 = 129.0, ACROSS by one'),
    (128, -UNITY, UNITY, 0, 0, 0,    '128 x -1.0 = -128.0, AT, negative'),
    (129, -UNITY, UNITY, 0, 0, 0,    '129 x -1.0, ACROSS, negative'),
    (3,   FULL,  FULL,  0, 0, 0,     'three x 64.0, ACROSS'),
    (3,   NFULL, FULL,  0, 0, 0,     'three x -64.0, ACROSS negative'),
    (32,  FULL,  UNITY, 0, 0, 0,     '32 coherent at full scale'),
    (32,  FULL,  FULL,  0, 0, 0,     '32 x 64.0, 16x over'),
    (3,   FULL,  FULL,  3, NFULL, FULL,
                                     '+3 then -3 x 64.0, excursion cancels'),
]


def mix_expand(v):
    """A compact MIX row -> (samples, gains) as mix_sum takes them."""
    n1, x1, g1, n2, x2, g2 = v[:6]
    return ([x1] * n1 + [x2] * n2, [g1] * n1 + [g2] * n2)


def mix_predicted_wrong(v):
    """Does the PRE-FIX 64-bit accumulator get this vector wrong?

    The 64-bit store is MODULAR, so an intermediate excursion that comes
    back still lands on the right answer -- what makes it wrong is the
    FINAL accumulator value leaving +/-2^63. The cancelling row is in the
    set to say so.
    """
    xs, gs = mix_expand(v)
    acc = sum(x * g for x, g in zip(xs, gs))
    return not (-(1 << 63) <= acc < (1 << 63))


# ---------------------------------------------------------------------------
# BLEND — the 32-bit new-old difference (D3)
#
# (new, old, alpha). alpha is the float control ramp; the kernel forms
# alpha_q31 with a saturating `fix`.
# ---------------------------------------------------------------------------

# alpha in [0, 1): the kernel's ramp cannot present 1.0 (see
# fixed_ref.xfade_alpha_q), so the largest here is one step short of it.
ALPHAS = (0.0, fr.XFADE_STEP, 0.25, 0.5, 0.75,
          1.0 - 2 * fr.XFADE_STEP, 1.0 - fr.XFADE_STEP)

BLEND = []
for _a in ALPHAS:
    BLEND += [
        # WITHIN 32 bits: both forms agree.
        (fr.to_q(1.0), fr.to_q(-1.0), _a, f'+1.0/-1.0 a={_a:.4f}'),
        # AT the edge: |new-old| == 2^31 - 1, the last value it holds.
        (FULL, 0, _a, f'+FS/0 a={_a:.4f}'),
        (0, NFULL, _a, f'0/-FS a={_a:.4f}'),
        # ACROSS: straddling full scale, |new-old| up to 2^32-1.
        (FULL, NFULL, _a, f'+FS/-FS a={_a:.4f}'),
        (NFULL, FULL, _a, f'-FS/+FS a={_a:.4f}'),
        (FULL, NFULL + 1, _a, f'+FS/-FS+1 a={_a:.4f}'),
    ]


def blend_predicted_wrong(v):
    """Does the PRE-FIX 32-bit difference get this vector wrong?"""
    new, old, alpha = v[0], v[1], v[2]
    d = new - old
    return (not (fr.I32_MIN <= d <= fr.I32_MAX)) and fr.xfade_alpha_q(alpha) != 0


def f32_bits(x):
    """IEEE-754 single bit pattern, for the alpha words in the ASM table."""
    import struct
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def expected():
    """(mix_results, blend_results) from the model — what the part must
    return, in table order."""
    mix = [fr.mix_sum(*mix_expand(v)) for v in MIX]
    bl = [fr.xfade_blend(v[0], v[1], v[2]) for v in BLEND]
    return mix, bl


def expected_prefix():
    """The same, through the PRE-FIX arithmetic — what the negative
    control build must return."""
    mix = [fr.mix_sum_wrapping(*mix_expand(v)) for v in MIX]
    bl = [fr.xfade_blend_wrapping(v[0], v[1], v[2]) for v in BLEND]
    return mix, bl


if __name__ == '__main__':
    m, b = expected()
    mp, bp = expected_prefix()
    print(f'{len(MIX)} mix vectors, '
          f'{sum(mix_predicted_wrong(v) for v in MIX)} across the boundary')
    for v, a, c in zip(MIX, m, mp):
        print(f'  {v[6]:38s} {a:12d} {c:12d} '
              f'{"DIFFERS" if a != c else "":8s}'
              f'{"<- predicted" if mix_predicted_wrong(v) else ""}')
    print(f'{len(BLEND)} blend vectors, '
          f'{sum(blend_predicted_wrong(v) for v in BLEND)} across the boundary')


# ===========================================================================
# THE NODE FAMILIES (2026-08-30, review findings D27-D31, D34)
#
# The families above are BOUNDARY sets: they exist because D1 and D3 were
# wrap findings and the question was where the wrap is. The families
# below are COVERAGE sets: their findings are "this arithmetic has no
# reference at all", so each one walks its node's whole shape -- every
# branch of the ladder, both sides of every saturation, and the defect
# the node has already shipped once.
#
# Every family carries its own NEGATIVE CONTROL PREDICATE, the same
# contract the two boundary families use: a function that says, from the
# vector alone, whether the deliberately-wrong twin in fixed_ref should
# disagree on it. A predicate computed from the vectors cannot quietly
# stop testing when a vector is added.
# ===========================================================================

UNITY = fr.to_q(1.0)                     # (already defined above; re-stated
                                         #  here because these families read
                                         #  as one block)

# ---------------------------------------------------------------------------
# COMP — the wet path (D28): (dry, gain_q, mk_q, par_q31, label)
#
# gain_q is what the gain computer returned (Q4.28, always <= unity);
# mk_q is the makeup (Q4.28); par_q31 is the parallel blend (Q0.31).
# THE D59 DEFAULT IS IN THE SET AS ITS OWN ROW and so is the value it
# replaced: par = 2^31-1 (100 %, fully wet, the power-on value since
# 2026-08-30) and par = 0 (fully dry, which is what shipped and what made
# a working compressor inaudible).
# ---------------------------------------------------------------------------

PAR_FULL = fr.I32_MAX                    # 100 %, the D59 default
PAR_ZERO = 0                             # 0 %, the defect it replaced
PAR_HALF = 1 << 30                       # 50 %
MK_UNITY = UNITY
MK_4X = fr.to_q(4.0)
G_HALF = fr.to_q(0.5)
G_TINY = 1                               # one LSB of gain: 60 dB+ of GR

COMP = [
    # --- the default, and the defect it replaced -------------------------
    (fr.to_q(0.5), G_HALF, MK_UNITY, PAR_FULL, 'wet 100% (the D59 default)'),
    (fr.to_q(0.5), G_HALF, MK_UNITY, PAR_ZERO, 'wet 0% (the D59 defect)'),
    (fr.to_q(0.5), G_HALF, MK_UNITY, PAR_HALF, 'wet 50%'),
    # --- unity paths: the identities the blend has to preserve -----------
    (fr.to_q(0.5), UNITY, MK_UNITY, PAR_FULL, 'unity gain, unity makeup'),
    (FULL, UNITY, MK_UNITY, PAR_FULL, '+FS through unity'),
    (NFULL, UNITY, MK_UNITY, PAR_FULL, '-FS through unity'),
    (0, UNITY, MK_UNITY, PAR_FULL, 'silence'),
    # --- the SECOND ROUNDING: makeup that pushes the intermediate over ---
    (FULL, G_HALF, MK_4X, PAR_FULL, '+FS x 0.5 x 4.0, intermediate rounds'),
    (NFULL, G_HALF, MK_4X, PAR_FULL, '-FS x 0.5 x 4.0'),
    (fr.to_q(1.0), G_HALF, MK_4X, PAR_FULL, '1.0 x 0.5 x 4.0 = 2.0'),
    (3, G_HALF, MK_4X, PAR_FULL, 'three LSB: both roundings visible'),
    (1, G_HALF, MK_4X, PAR_FULL, 'one LSB x 0.5 -> rounds to 1, x4 -> 4'),
    (1, G_HALF, MK_UNITY, PAR_FULL, 'one LSB x 0.5, no makeup'),
    (-1, G_HALF, MK_4X, PAR_FULL, 'minus one LSB: rounding is toward +inf'),
    (-3, G_HALF, MK_4X, PAR_FULL, 'minus three LSB'),
    # --- SATURATION of the intermediate store ----------------------------
    (FULL, UNITY, MK_4X, PAR_FULL, '+FS x 4.0 makeup: wet saturates'),
    (NFULL, UNITY, MK_4X, PAR_FULL, '-FS x 4.0 makeup: wet saturates low'),
    # --- the blend's own edges -------------------------------------------
    (FULL, G_TINY, MK_UNITY, PAR_FULL, '+FS crushed to ~0, fully wet'),
    (NFULL, G_TINY, MK_UNITY, PAR_FULL, '-FS crushed to ~0, fully wet'),
    (NFULL, 0, MK_UNITY, PAR_FULL, '-FS with gain 0: |wet-dry| = 2^31'),
    (NFULL, 0, MK_UNITY, PAR_ZERO, 'the same, fully dry: par masks it'),
    (FULL, 0, MK_UNITY, PAR_FULL, '+FS with gain 0'),
    (NFULL, 0, MK_UNITY, 1, 'the same, one LSB of blend'),
]


def comp_expand(v):
    return v[0], v[1], v[2], v[3]


def comp_round_predicted_wrong(v):
    """Does the SINGLE-ROUNDING wet path get this vector wrong? That is
    the negative control for the makeup's second rounding."""
    dry, g, mk, _ = comp_expand(v)
    return fr.comp_wet(dry, g, mk) != fr.comp_wet_1round(dry, g, mk)


def comp_diff_wraps(v):
    """Does `wet - dry` leave int32 on this vector? The bound says it
    cannot unless the gain computer underflows to zero with the sample at
    full negative scale -- which is what the two `gain 0` rows are."""
    dry, g, mk, _ = comp_expand(v)
    d = fr.comp_wet(dry, g, mk) - dry
    return not (fr.I32_MIN <= d <= fr.I32_MAX)


# ---------------------------------------------------------------------------
# GATE — the state machine (D30)
#
# A gate vector is a SCENARIO, not a sample: the finding is about a
# ladder with a counter in it, and a counter needs a sequence to be seen
# at all. Each scenario is (label, params, samples) where params is
# (att_q, rel_q, thr_q625, rng_q, hold) -- the five converted words the
# node holds -- and the expected output is the whole sequence.
#
# BETWEEN THEM THE SCENARIOS WALK EVERY TRANSITION: closed to open, open
# to hold, hold to closed, and hold RE-ARMED before it expires. The
# retrigger scenario is the one that separates gate_step from
# gate_step_nohold, which is what makes the hold counter observable.
# ---------------------------------------------------------------------------

def _gate_p(att=0.05, rel=0.005, thr_db=-40.0, rng_db=60.0, hold=64):
    """The five converted words, from CELL VALUES, through the same
    conversions the node performs at block rate.

    att/rel ARE ONE-POLE COEFFICIENTS, NOT TIMES. `GateAtt`/`GateRel`
    reach the node as a raw alpha in [0, 1) -- the node's own defaults
    are 0.05 and 0.005 and it multiplies them straight by 2^31 -- so a
    scenario written in milliseconds converts to an alpha a thousand
    times too small and the envelope never moves. That is how the first
    version of this set produced a gate whose gain sat at unity for all
    512 samples of every scenario.
    """
    return (fr.dyn_alpha_q(att), fr.dyn_alpha_q(rel),
            fr.gate_thr_q(thr_db), fr.gate_range_q(rng_db), hold)


def _quiet(n):
    """n samples of the below-threshold level, as a square so the
    envelope follower sees a constant magnitude."""
    return _burst(n, _COLD)


def _burst(n, amp):
    """n samples of a full-rate square at +/-amp: an envelope follower
    sees a constant |x|, so the level is exactly amp with no ripple."""
    return [amp if i % 2 == 0 else -amp for i in range(n)]


_HOT = fr.to_q(0.25)                     # -12 dBFS, well above threshold
# THE "CLOSED" LEVEL IS NOT DIGITAL SILENCE, and that is not a detail. A
# gate's output is x * gain, so at x = 0 the output is 0 whatever the
# gain is doing -- the hold counter, the range floor and the smoother
# are all INVISIBLE through a silent input. Measured while building this
# set: with the gaps at zero, gate_step and gate_step_nohold agreed word
# for word on every scenario, i.e. the negative control could not fail.
# -66 dBFS is below the -40 dB threshold by 26 dB and still carries the
# gain into the output.
_COLD = fr.to_q(0.0005)                  # -66 dBFS, below threshold

# THE RELEASE HAS TO REACH THE THRESHOLD INSIDE THE HOLD or the hold
# counter changes nothing and the scenario cannot see it: measured while
# building this set, a release slow enough to keep the level above the
# threshold for longer than the hold makes gate_step and
# gate_step_nohold agree word for word. The fast-release scenarios below
# collapse the envelope in a handful of samples, which is what puts the
# counter on the critical path. A scenario that cannot separate the two
# ladders is not coverage.
GATE = [
    ('open from closed',
     _gate_p(), _burst(256, _HOT)),
    ('open, hold, close',
     _gate_p(rel=0.5, hold=64), _burst(128, _HOT) + _quiet(384)),
    ('hold RE-ARMED before it expires',
     _gate_p(rel=0.5, hold=256),
     _burst(96, _HOT) + _quiet(128) + _burst(96, _HOT) + _quiet(256)),
    ('hold = 0: closes the sample the level drops',
     _gate_p(rel=0.5, hold=0), _burst(64, _HOT) + _quiet(256)),
    ('range 0 dB: the floor IS unity, the gate cannot attenuate',
     _gate_p(rel=0.5, rng_db=0.0), _burst(64, _HOT) + _quiet(256)),
    ('range 60 dB: the deepest the protocol can ask for',
     _gate_p(rel=0.5, rng_db=60.0, hold=8), _burst(64, _HOT) + _quiet(384)),
    ('at the threshold: level sits ON the compare',
     _gate_p(thr_db=-12.041199826559248), _burst(384, _HOT)),
    ('full-scale negative: |I32_MIN| is I32_MIN',
     _gate_p(rel=0.5), [NFULL] * 8 + _burst(120, _HOT) + _quiet(200)),
    ('silence only: the counter runs negative and stays there',
     _gate_p(hold=4), _quiet(256)),
]


def gate_run(v, step=None):
    """Run a scenario and return (outputs, state). step lets the caller
    substitute the negative-control ladder."""
    _, p, xs = v
    st = fr.gate_state()
    f = step or fr.gate_step
    return [f(x, st, *p) for x in xs], st


def gate_predicted_wrong(v):
    """Does the NO-HOLD ladder get this scenario wrong? True exactly when
    the hold counter changes an output word."""
    return gate_run(v)[0] != gate_run(v, fr.gate_step_nohold)[0]


# ---------------------------------------------------------------------------
# FDR — the pan law and the level coefficient (D31)
#
# (level, pan, mute, x, label). The vectors are the SITE OF THE 2026-08-23
# SQUARED-GAIN BUG: level 1.0 is where the defect was invisible and 0.5
# and 0.25 are where it read 6.02 dB and 12.04 dB low, so all three are
# here and the negative control (fdr_pan_squared) has to fail the last
# two and pass the first.
#
# THE PAN LAW IS LINEAR AND D42 IS STILL OPEN. Centre pan on a linear law
# puts BOTH legs at 0.5, which is -6.02 dB per leg where a constant-power
# law would put -3.01 dB. The 'centre' row is that number, so the day D42
# rules, this vector changes and says so.
# ---------------------------------------------------------------------------

FDR = [
    (1.0, 0.5, 0, fr.to_q(0.5), 'unity level, centre pan'),
    (0.5, 0.5, 0, fr.to_q(0.5), 'level 0.5 (the squared-gain site: -6.02 dB)'),
    (0.25, 0.5, 0, fr.to_q(0.5), 'level 0.25 (-12.04 dB)'),
    (1.0, 0.0, 0, fr.to_q(0.5), 'hard left'),
    (1.0, 1.0, 0, fr.to_q(0.5), 'hard right'),
    (1.0, 0.5, 1, fr.to_q(0.5), 'MUTED: the coefficient itself is zero'),
    (0.5, 0.5, 1, fr.to_q(0.5), 'muted at half level'),
    (0.0, 0.5, 0, fr.to_q(0.5), 'level 0.0'),
    (1.0, 0.5, 0, FULL, '+FS at unity'),
    (1.0, 0.5, 0, NFULL, '-FS at unity'),
    (2.0, 0.5, 0, FULL, '+6.02 dB of level: the MAC saturates'),
    (2.0, 0.5, 0, NFULL, 'the same, negative'),
    (7.999999523162842, 0.5, 0, fr.to_q(0.5),
     'the largest level the conversion is DEFINED for'),
    (1.0, 0.5, 0, 1, 'one LSB'),
    (1.0, 0.5, 0, -1, 'minus one LSB'),
    (0.5, 0.25, 0, fr.to_q(0.5), 'off-centre pan at half level'),
]


def fdr_expand(v):
    return v[0], v[1], v[2], v[3]


def fdr_predicted_wrong(v):
    """Does the SQUARED-GAIN form get this vector wrong? It is exact at
    unity level, which is how it shipped."""
    level, pan, mute, x = fdr_expand(v)
    gq, lq, _ = fr.fdr_coeffs(level, pan, mute)
    good = fr.sat32(fr.rns(fr.fdr_apply(x, gq) * lq, fr.QS))
    return good != fr.fdr_pan_squared(x, gq, lq)


# ---------------------------------------------------------------------------
# TUBE — the three chained roundings (D29), PLUGIN-CLASS
#
# (x, sat, label), sat as the cell's float. The set walks past unity on
# purpose: the shape is a soft clip only for |x| <= 1, and above that the
# 1 - x^2 term turns the transfer curve over. A Q4.28 sample reaches 8.0,
# so that region is not hypothetical.
# ---------------------------------------------------------------------------

TUBE = [
    (0, 1.0, 'silence, fully saturated'),
    (fr.to_q(0.25), 0.0, 'sat 0: the identity'),
    (fr.to_q(0.25), 1.0, '-12 dBFS, sat 1.0'),
    (fr.to_q(0.5), 1.0, '-6 dBFS, sat 1.0'),
    (fr.to_q(0.5), 0.5, '-6 dBFS, sat 0.5'),
    (fr.to_q(-0.5), 1.0, '-6 dBFS negative'),
    (fr.to_q(1.0), 1.0, 'exactly 1.0: 1 - x^2 is exactly zero'),
    (fr.to_q(-1.0), 1.0, 'exactly -1.0'),
    (fr.to_q(1.5), 1.0, 'past unity: the curve turns over'),
    (fr.to_q(2.0), 1.0, 'x = 2: gain factor is -2, the output flips sign'),
    (fr.to_q(2.828427), 1.0, 'x^2 at the Q4.28 ceiling (7.999)'),
    (fr.to_q(3.0), 1.0, 'x^2 SATURATES'),
    (FULL, 1.0, '+FS: x^2 saturates, the last MAC saturates'),
    (NFULL, 1.0, '-FS'),
    (1, 1.0, 'one LSB'),
    (-1, 1.0, 'minus one LSB'),
    (fr.to_q(0.5), 7.999999523162842,
     'the largest sat the conversion is DEFINED for'),
    # --- THE MIDDLE ROUNDING, and it is only visible off the round
    # numbers. Every tidy setting above has an EXACT intermediate:
    # sat = 1.0 with x = 0.5 gives sat*(1-x^2) on the Q4.28 grid, so
    # rounding it changes nothing and the two-rounding control agrees
    # word for word. A 400k-point search over (x, sat_q) found the
    # disagreement at 1-2 LSB and only where neither operand is tidy.
    # These six are that search's hits, carried as RAW Q4.28 sat words
    # because that is what they are. Without them the negative control
    # for the second of the three roundings cannot fire at all.
    (355571805, 230530419, 'x 1.3246, sat 0.8588: the middle round, +1 LSB'),
    (-347295166, 126478448, 'x -1.2938, sat 0.4712: -1 LSB'),
    (1921781853, 66423868, 'x 7.1592, sat 0.2474: +2 LSB'),
    (1201859104, 87891151, 'x 4.4773, sat 0.3274'),
    (-1499591369, 51847156, 'x -5.5864, sat 0.1931'),
    (-233471120, 414240403, 'x -0.8697, sat 1.5432'),
]


def tube_expand(v):
    """(x, sat_q). A row's sat is either a CELL VALUE (float, converted
    the way the node converts it) or a RAW Q4.28 word (int), because the
    rows that separate the three-rounding form from the two-rounding one
    do not sit on values a tidy cell produces."""
    return v[0], (v[1] if isinstance(v[1], int) else fr.tube_sat_q(v[1]))


def tube_predicted_wrong(v):
    """Does the TWO-ROUNDING form get this vector wrong? That is the
    negative control for the middle of the three roundings."""
    x, sq = tube_expand(v)
    return fr.tube(x, sq) != fr.tube_2round(x, sq)


# ---------------------------------------------------------------------------
# TDM — the two wire boundaries (D34): (word, label)
#
# IN vectors are Q1.31 wire words; OUT vectors are Q4.28 samples. The OUT
# set straddles 1.0 linear, which is the only clip in the whole graph
# that Q4.28's four integer bits have been deferring.
# ---------------------------------------------------------------------------

TDM_IN = [
    (0, 'silence'),
    (FULL, '+full scale on the wire'),
    (NFULL, '-full scale on the wire'),
    (1 << 30, '+0.5'),
    (-(1 << 30), '-0.5'),
    (7, 'seven LSB: all three bits are DISCARDED, not rounded'),
    (-7, 'minus seven LSB: the shift floors, so this is -1 not 0'),
    (-1, 'minus one LSB -> -1, a whole LSB of downward bias'),
    (1, 'one LSB -> 0'),
]

TDM_OUT = [
    (0, 'silence'),
    (fr.to_q(1.0), 'exactly 1.0: the last value that fits'),
    (fr.to_q(-1.0), 'exactly -1.0'),
    (fr.to_q(1.0) - 1, 'one LSB under 1.0'),
    (fr.to_q(1.0) + 1, 'one LSB OVER 1.0: SATURATES'),
    (fr.to_q(-1.0) - 1, 'one LSB under -1.0: saturates low'),
    (fr.to_q(2.0), '+6 dBFS of headroom, clipped here'),
    (FULL, '+FS in Q4.28 = 7.999 linear'),
    (NFULL, '-FS in Q4.28 = -8.0 linear'),
    (1, 'one LSB'),
    (-1, 'minus one LSB'),
]


def tdm_out_predicted_wrong(v):
    """Does dropping the saturation arm get this vector wrong?"""
    return fr.tdm_out(v[0]) != fr.tdm_out_unchecked(v[0])


# ---------------------------------------------------------------------------
# BQCVT — `_bq_fx_convert_N` (D27): (b0, b1, b2, a1, a2, label)
#
# THE SET IS BUILT AROUND THE b1 SITE AND THE Q = 0.10 CORNER.
#
# b1: the routine shipped with b1 destroyed before n1 read it, so every
# filter ran with n1 = 2*b0. The vectors carry non-zero b1 of both signs
# AND a b1 = 0 set, because the negative control has to PASS the b1 = 0
# row -- that is what proves it is detecting b1 rather than failing
# everything.
#
# Q = 0.10: the ruled minimum (PW 2026-08-29). At +15 dB and Q at the
# floor the peaking design gives n1 = b1 + 2*b0 well past the Q4.28
# ceiling of 7.999, which is what the halved Q5.27 encoding exists for.
# Those sets are here at the floor and just above it.
# ---------------------------------------------------------------------------

def _peaking(f0, gain_db, q, fs=48000.0):
    """RBJ peaking, the same derivation golden_harness uses."""
    import math
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / fs
    al = math.sin(w0) / (2 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w0), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w0), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


BQCVT = [
    (1.0, 0.0, 0.0, 0.0, 0.0, 'unity passthrough (b1 = 0: the control must PASS)'),
    (1.0, 0.5, 0.25, -1.5, 0.7, 'plain set, b1 positive'),
    (1.0, -0.5, 0.25, -1.5, 0.7, 'plain set, b1 NEGATIVE'),
    (0.5, 1.0, 0.5, -1.0, 0.5, 'b1 larger than b0'),
    (1.0, -2.0, 1.0, -1.9, 0.9, 'HPF-shaped: b1 = -2*b0, n1 lands on ZERO'),
    (1.0, 2.0, 1.0, -1.9, 0.9, 'LPF-shaped: b1 = +2*b0'),
    _peaking(20, 15, 0.10) + ('Q = 0.10 at +15 dB, 20 Hz: the n1 CORNER',),
    _peaking(20, 15, 0.12) + ('Q = 0.12 at +15 dB, 20 Hz',),
    _peaking(20, -15, 0.10) + ('Q = 0.10 at -15 dB, 20 Hz',),
    _peaking(1000, 15, 0.10) + ('Q = 0.10 at +15 dB, 1 kHz',),
    _peaking(20000, 15, 0.10) + ('Q = 0.10 at +15 dB, 20 kHz',),
    _peaking(20, 12, 4.0) + ('the harness sweep worst case (20 Hz, -12, Q 4)',),
    (0.0, 0.0, 0.0, 0.0, 0.0, 'all zero'),
    (1.9999999, 0.0, 0.0, 0.0, 0.0, 'b0 near the Q4.28 ceiling'),
]


def bqcvt_expand(v):
    return v[:5]


def bqcvt_predicted_wrong(v):
    """Does the b1-destroying form get this vector wrong? Exactly the
    sets whose b1 is not zero to the model's resolution."""
    return fr.bq_convert_f32(*v[:5]) != fr.bq_convert_b1_lost(*v[:5])
