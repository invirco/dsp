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
