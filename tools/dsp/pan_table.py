"""pan_table.py — THE pan law, as one 127-entry table (PW ruling R5).

WHAT R5 ASKS FOR, AND WHAT THIS FILE IS

PW's R5 (amended) puts the whole mixer on ONE pan table: 127 pan
positions x (gL, gC, gR); `Sys[1-1]LcrLaw[1-1]` selects which law is
loaded; every channel's `Pan` is an INDEX into it; `Chan*LcrOn` selects
the three-column read per channel and `Chan*CtrOn` gates the centre leg.
Non-LCR channels use the same table so that "stereo and LCR panning share
one law".

This module is the LAW ITSELF -- the single place the numbers come from.
The generator emits the tables from here, the bench probe scores the part
against here, and neither has a copy of the arithmetic.

THE COLUMN CONVENTION, AND WHY IT IS NOT "IGNORE THE CENTRE"

R5-amended says a non-LCR channel "uses the same table's L/R columns
(centre column ignored)". Read literally that silences a centre-panned
channel: under hard LCR the centre position is `centre bus only`, so its
L and R legs are BOTH ZERO, and a stereo strip panned to the middle would
disappear. The same is true of the constant-power law. So "ignored"
cannot be what the columns hold.

What this table stores instead, and it satisfies R5 literally:

    column L, column R = what a NON-LCR channel reads, unmodified
    column C          = the centre leg

and an LCR channel's three legs are recovered from the same three words:

    (gL, gC, gR)_LCR = (L - C/2, C, R - C/2)

i.e. the centre bus takes what the two sides used to carry between them,
at -6 dB each -- the ordinary centre downmix, run backwards.

THIS IS AN IDENTITY FOR HARD LCR, NOT AN APPROXIMATION. Hard LCR is
"centre -> centre bus only, extremes -> one side only, linear divide
between near side and centre":

    p <= 1/2 : (1-2p, 2p,   0  )
    p >= 1/2 : (0,    2-2p, 2p-1)

Fold the centre back at half into each side and the sides become
(1-p, p) for EVERY p, on both halves -- which is exactly the linear pan
law this graph has always run. So under law 0 the L/R columns ARE the
shipping law, word for word, and a non-LCR channel's audio does not move
at all. That is what makes R5 testable against the pre-R5 image rather
than merely plausible.

For the constant-power law the fold is a choice rather than an identity,
and its consequence is measured rather than asserted: `fold_peak_db()`
reports how far the folded stereo pair rises above unity (+0.97 dB at
p ~ 0.148 for law 1, +0.00 dB everywhere for law 0). That is the ordinary
"-6 dB centre downmix is louder in the middle" bump; it is inside Q4.28's
headroom and nothing saturates. WHAT A NON-LCR CHANNEL SHOULD READ UNDER
A CONSTANT-POWER LAW IS A PRODUCT QUESTION R5 DOES NOT ANSWER -- three
columns cannot hold both a two-bus constant-power law and a three-bus one
-- and it is carried, not guessed.

Q4.28, and why the conversion is spelled this way: the pre-R5 node
computed its legs as `fix(g * 2^28)` in float32. The tables are built the
same way, through float32, so the stored word is the word the old
arithmetic produced and the bit-exact claim is a claim about the same
operation and not about two roundings that happen to agree.
"""

import math
import struct

# 127 pan positions. Index 0 = hard left, 63 = centre, 126 = hard right;
# 63 is the exact middle of 0..126, which is why the centre position is a
# table entry and not something between two.
PAN_POSITIONS = 127
PAN_CENTRE = 63

LAW_HARD_LCR = 0
LAW_CONST_POWER = 1
LAW_NAMES = {LAW_HARD_LCR: 'hard-LCR', LAW_CONST_POWER: 'constant-power'}


def _f32(x):
    """x through float32, the way the DSP holds it."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def _fix(v):
    """The core's `fix`, MEASURED (S25-2) and not assumed.

    Every comment in this tree that mentions it -- including the one this
    module was first written with, and `dsp4_s24_probe.py`'s `q28()` --
    says `fix` TRUNCATES toward zero. It does not: MODE1's truncate bit
    is set nowhere in the tree, so `fix` ROUNDS TO NEAREST, ties to even.

    That is not a reading of the manual, it is what the part answered.
    The first run of the pan probe wrote pan indices 31, 63 and 94 into a
    node that computed `fix(pan * 126 + 0.5)`, and the part came back with
    32, 64 and 94. The three products are EXACTLY 31.0, 63.0 and 94.0 in
    float32, so the sums are exactly 31.5, 63.5 and 94.5; truncation gives
    31/63/94 and round-half-away gives 32/64/95. Only ties-to-even gives
    32/64/94, and it gives it on all three.

    S24's probe could not have caught this and did not claim to: its five
    levels were 1.0, 0.5, 0.25, 0.0 and a mute, every one of which is an
    exact power of two at Q4.28, so no rounding was ever exercised.
    """
    import decimal
    return int(decimal.Decimal(v).quantize(0, decimal.ROUND_HALF_EVEN))


def _q428(g):
    """float gain -> Q4.28, the node's own conversion: a float32 multiply
    by 2^28 and one `fix`."""
    q = _fix(_f32(_f32(g) * _f32(2.0 ** 28)))
    if q < -(1 << 31) or q > (1 << 31) - 1:
        raise ValueError(f'pan gain {g} does not fit Q4.28 ({q})')
    return q


def pan_of(idx):
    """The float32 `Pan` value that lands on table index `idx`."""
    if not 0 <= idx < PAN_POSITIONS:
        raise ValueError(f'pan index {idx} outside 0..{PAN_POSITIONS - 1}')
    return _f32(idx / float(PAN_POSITIONS - 1))


def shipping_linear(idx):
    """The PRE-R5 law at this index, computed the pre-R5 node's own way:
    `fix((1 - pan) * 2^28)` and `fix(pan * 2^28)`, with the subtraction in
    float32 because that is where the node does it."""
    p = pan_of(idx)
    return (_q428(_f32(_f32(1.0) - p)), _q428(p))


def stereo_cols(law, idx):
    """The table's stored L and R columns -- what a NON-LCR channel reads
    -- as Q4.28 words."""
    l, _, r = columns(law, idx)
    return (l, r)


def columns(law, idx):
    """The three STORED words at `idx`: (L, C, R), Q4.28.

    THE PRIMARY DEFINITION IS DIFFERENT FOR THE TWO LAWS, and saying
    which is the point of this function.

    Law 0's primary definition is its L/R COLUMNS: they are the pre-R5
    node's own arithmetic, word for word, so switching R5 on cannot move
    a non-LCR channel. The centre column is then exactly twice the
    smaller side, which makes the recovered LCR legs exact integers --
    the near side becomes L - R and the far side becomes EXACTLY zero,
    which is R5's "extremes -> one side only" with no rounding anywhere.

    Law 1's primary definition is its LCR LEGS, because "three-bus
    constant-power" is a statement about the three legs and R5 gives no
    other. The columns are then whatever reproduces those legs through
    the kernel's `(L - C>>1, C, R - C>>1)` read.

    THE ONE THING R5 DOES NOT ANSWER, and it is carried rather than
    guessed: what a NON-LCR channel should read under law 1. Three
    columns cannot hold both a two-bus constant-power law and a
    three-bus one -- that is arithmetic, not preference -- so the stereo
    projection is the centre folded back at -6 dB, the ordinary downmix,
    which peaks +0.97 dB above unity at p ~ 0.148 (fold_peak_db reports
    it, and nothing saturates: Q4.28 reaches 8.0). Under law 0 the same
    fold is the IDENTITY that gives back the linear law.
    """
    if law == LAW_HARD_LCR:
        l, r = shipping_linear(idx)
        return (l, 2 * min(l, r), r)
    if law == LAW_CONST_POWER:
        p = pan_of(idx)
        if p <= 0.5:
            gl, gc, gr = math.cos(p * math.pi), math.sin(p * math.pi), 0.0
        else:
            q = _f32(p - 0.5)
            gl, gc, gr = 0.0, math.cos(q * math.pi), math.sin(q * math.pi)
        c = _q428(gc)
        half = c >> 1
        return (_q428(gl) + half, c, _q428(gr) + half)
    raise ValueError(f'unknown pan law {law} — laws are '
                     f'{sorted(LAW_NAMES)} (no-fallback policy)')


def table_q428(law):
    """The whole table for `law`, 127 x 3 Q4.28 words, row-major (L,C,R)."""
    out = []
    for i in range(PAN_POSITIONS):
        out.extend(w & 0xFFFFFFFF for w in columns(law, i))
    return out


def lcr_legs(law, idx):
    """The three legs an LCR channel gets, as the KERNEL computes them:
    (L - C>>1, C, R - C>>1), integer, no float anywhere."""
    l, c, r = columns(law, idx)
    half = c >> 1                      # `ashift by -1`, and c >= 0
    return (l - half, c, r - half)


def read_legs(law, idx, lcr_on):
    """What the NODE publishes -- the model the bench probe scores the
    part against, as unsigned Q4.28 words.

    Non-LCR: the stored L/R, used exactly as they are, and NO centre leg.
    LCR:     (L - C>>1, C, R - C>>1).
    """
    if not lcr_on:
        l, _, r = columns(law, idx)
        return (l & 0xFFFFFFFF, 0, r & 0xFFFFFFFF)
    return tuple(w & 0xFFFFFFFF for w in lcr_legs(law, idx))


def pan_to_index(pan):
    """The float `Pan` cell (0..1) -> table index, the node's own
    arithmetic: one float32 multiply and one `fix`. There is NO +0.5 --
    `fix` rounds (see _fix), and adding a half made every exact index
    land on a tie and round up to the next one."""
    i = _fix(_f32(_f32(pan) * _f32(float(PAN_POSITIONS - 1))))
    return 0 if i < 0 else (PAN_POSITIONS - 1 if i > PAN_POSITIONS - 1 else i)


def stereo_read(law, idx):
    """The (L, R) a non-LCR channel reads, as floats, for reporting."""
    l, _, r = columns(law, idx)
    return (l / 2.0 ** 28, r / 2.0 ** 28)


def fold_peak_db(law):
    """How far above unity the stored stereo pair rises, in dB.

    0.00 for hard LCR -- its columns ARE the pre-R5 linear law, whose
    peak is unity. +0.97 dB for constant power, which is the ordinary
    consequence of a law whose two-bus projection is cos/sin.
    """
    peak = max(max(stereo_read(law, i)) for i in range(PAN_POSITIONS))
    return 20.0 * math.log10(peak)


def check():
    """The law's own self-test. Returns a list of (name, ok, detail)."""
    out = []

    # 1. Hard LCR's L/R columns ARE the pre-R5 law, at every index and to
    #    the word. This is the whole basis of "R5 moves no non-LCR
    #    channel's audio", so it is checked and not argued.
    bad = [i for i in range(PAN_POSITIONS)
           if stereo_cols(LAW_HARD_LCR, i) != shipping_linear(i)]
    out.append(('hard-LCR L/R columns == the pre-R5 law, all 127 indices',
                not bad, bad[:6]))

    # 2. Centre is the exact middle and reads exactly 0.5 / 1.0 / 0.5.
    out.append(('hard-LCR centre row is 0.5 / unity / 0.5',
                columns(LAW_HARD_LCR, PAN_CENTRE)
                == (0x08000000, 0x10000000, 0x08000000),
                tuple(hex(w) for w in columns(LAW_HARD_LCR, PAN_CENTRE))))

    # 3. R5's definition of hard LCR, recovered from the stored columns
    #    by the kernel's own integer arithmetic: centre -> centre bus
    #    only, extremes -> one side only, and the far leg EXACTLY zero at
    #    every position (which is what "hard" means).
    ok3 = (lcr_legs(LAW_HARD_LCR, PAN_CENTRE) == (0, 0x10000000, 0)
           and lcr_legs(LAW_HARD_LCR, 0) == (0x10000000, 0, 0)
           and lcr_legs(LAW_HARD_LCR, PAN_POSITIONS - 1)
           == (0, 0, 0x10000000))
    far = [i for i in range(PAN_POSITIONS)
           if min(lcr_legs(LAW_HARD_LCR, i)[0],
                  lcr_legs(LAW_HARD_LCR, i)[2]) != 0]
    out.append(('hard-LCR: centre-only, extremes one-sided, far leg zero '
                'at all 127', ok3 and not far, (ok3, far[:6])))

    # 4. No leg of either law is negative or out of Q4.28 range.
    bad4 = [(law, i) for law in LAW_NAMES for i in range(PAN_POSITIONS)
            if min(lcr_legs(law, i)) < 0
            or max(lcr_legs(law, i)) > (1 << 31) - 1]
    out.append(('no law produces a negative or out-of-range leg',
                not bad4, bad4[:6]))

    # 5. Constant power really is constant power in LCR mode, to the
    #    resolution Q4.28 allows.
    worst = 0.0
    for i in range(PAN_POSITIONS):
        s2 = sum((g / 2.0 ** 28) ** 2 for g in lcr_legs(LAW_CONST_POWER, i))
        worst = max(worst, abs(s2 - 1.0))
    out.append(('constant-power law: sum of squares == 1 in LCR mode',
                worst < 2e-7, worst))

    # 6. The index arithmetic is the node's, and it round-trips: the
    #    float32 `Pan` that names an index must map back to it. This is
    #    the check the first run of the probe failed on the part.
    bad6 = [i for i in range(PAN_POSITIONS) if pan_to_index(pan_of(i)) != i]
    out.append(('Pan -> index round-trips at all 127 indices',
                not bad6, bad6[:6]))

    return out


if __name__ == '__main__':
    import sys
    bad = 0
    for name, ok, detail in check():
        print(f'{"ok  " if ok else "FAIL"}  {name}   {detail}')
        bad += not ok
    for law in sorted(LAW_NAMES):
        print(f'\n{LAW_NAMES[law]} (law {law}): fold peak '
              f'{fold_peak_db(law):+.4f} dB')
        for i in (0, 31, PAN_CENTRE, 94, 126):
            l, c, r = (f'0x{w:08X}' for w in table_q428(law)[3 * i:3 * i + 3])
            print(f'  idx {i:3d}  stored L={l} C={c} R={r}   '
                  f'LCR legs ' + ' '.join(
                      f'0x{w:08X}' for w in read_legs(law, i, True)))
    sys.exit(1 if bad else 0)
