/*======================================================================
 * xover_design_fx.asm — the main crossover's design, on the part.
 *
 * WHY THIS EXISTS, and it is the graphic EQ's story again with a
 * different ending. The CROSSOVER node is a real pair of two-stage
 * cascades with their own state and their own dual-instance crossfade,
 * and it had never been given coefficients: the landed cell wrote into
 * `_xover_coeffs_next[0]` -- ONE word of a twenty-word staging array --
 * nothing raised the swap, and both banks held their compiled identity
 * while the node copied its input to all four main outputs. Measured on
 * the part 2026-09-08 alongside the GEQ.
 *
 * NORMATIVE MODEL: tools/dsp/xover_ref.py, which checks itself against
 * RBJ written out plainly and against the two properties that say the
 * result is really Linkwitz-Riley 4 -- each path 6.02 dB down at the
 * corner, and the two paths summing flat.
 *
 * LINKWITZ-RILEY is what the node's shape already committed to: two LP
 * stages and two HP stages, no more and no fewer. LR4 is two cascaded
 * 2nd-order Butterworth sections (Q = 1/sqrt2) at the same corner, so
 * BOTH STAGES OF A PATH ARE THE SAME FIVE WORDS; LR2 is one such
 * section at Q = 0.5 with the second stage passing through. Either way
 * this routine designs two sets, not four.
 *
 * WHAT IT EVALUATES:
 *
 *     x   = 2*pi*f0/fs                 (0.0065 .. 0.065 rad over 50-500 Hz)
 *     s   = sin x                      x*(1 - x2/6*(1 - x2/20))
 *     u   = 1 - cos x                  x2/2*(1 - x2/12*(1 - x2/30))
 *     al  = s / (2Q)                  1/(2Q) = 0.7071 (LR4), 1.0 (LR2)
 *     inv = 1/(1 + al)
 *     LP: b0 = (u/2)*inv    n1 = 2u*inv       n2 = 0
 *     HP: b0 = (2-u)/2*inv  n1 = 0            n2 = 0
 *     both: c1 = (2u + 2al)*inv         c2 = 2al*inv
 *
 * The zeros are IDENTITIES of the RBJ forms, not approximations, and
 * they are written rather than computed.
 *
 * u COMES FROM ITS OWN SERIES AND THAT IS THE WHOLE ACCURACY ARGUMENT.
 * Over the domain cos x is between 0.9979 and 0.99998, so forming
 * `1 - cos x` in float32 would keep about four significant digits of the
 * quantity the entire pole placement rests on. The series has no
 * cancellation in it. Worst error against libm over the domain: 1.6e-11,
 * measured by xover_ref.check() rather than asserted here.
 *
 * THE SLOPE IS A REAL WORD SINCE 2026-09-09, and until then it was
 * not settable at all. MainCtr/MainL/MainR/MainSub each carry a
 * `CrossoverFreq` AND a `CrossoverSlope`, and ALL EIGHT used to resolve
 * to the node's first word -- eight cells, one address, marked "shared
 * crossover word". Measured on the part 2026-09-08: writing 500 Hz and
 * then a slope left `0x00000018`, the integer 24, sitting where a
 * frequency belongs. The slope now takes the node's SECOND word, still
 * one word for all four sections because there is one crossover node
 * and one split.
 *
 * TWO OF THE CELL TABLE'S FOUR VALUES ARE HONOURED AND TWO ARE
 * IGNORED, and the division is the filter's, not a convenience:
 *
 *   24  LR4 -- two cascaded Butterworth sections, Q = 1/sqrt2. Both
 *       stages of a path are the same five words. Shipping behaviour.
 *   12  LR2 -- ONE 2nd-order section at Q = 0.5, the second stage of
 *       each path written as the compiled identity, AND THE HIGHPASS
 *       INVERTED (see .xod_hp). Same five offset formulas with 1/(2Q)
 *       at 1.0 instead of 0.7071.
 *    6  1st-order. Expressible, but each path is then 3 dB down at the
 *       corner rather than 6 -- not a Linkwitz-Riley alignment, and a
 *       different acoustic contract from the one the product ships.
 *   18  3rd-order. Not an LR alignment at any order; LP + HP does not
 *       sum flat.
 *
 * A WORD OUTSIDE 50-500 Hz, OR A SLOPE THAT IS NOT 12 OR 24, IS
 * IGNORED, NOT CLAMPED. Clamping a slope into the frequency word is
 * what the collided address used to do by accident, and clamping 18 to
 * 24 would answer a question the host asked with a filter it did not
 * ask for. Ignoring leaves the split where the last legal pair put it.
 *
 * Infrastructure (hand-maintained). Called at control rate from the
 * node, on the block a frequency arrived and on no other.
 *======================================================================*/

#include "dsp_block.h"

#define XO_2PI_FS      0x3909421E    /* 2*pi/48000        */
#define XO_INV6        0x3E2AAAAB
#define XO_INV20       0x3D4CCCCD
#define XO_INV12       0x3DAAAAAB
#define XO_INV30       0x3D088889
#define XO_HALF        0x3F000000
#define XO_ONE         0x3F800000
#define XO_TWO         0x40000000
#define XO_INV2Q_LR4   0x3F3504F3    /* 1/(2Q), Q = 1/sqrt2 — LR4 */
#define XO_INV2Q_LR2   0x3F800000    /* 1/(2Q), Q = 0.5      — LR2 */
#define XO_MONE        0xBF800000
#define XO_FMIN        0x42480000    /* 50.0 Hz  — Table 0=50   */
#define XO_FMAX        0x43FA0000    /* 500.0 Hz — Table 127=500 */
#define XO_SLOPE_LR4   24
#define XO_SLOPE_LR2   12

/* THE SLOPE DECISION, RESOLVED AT ENTRY AND HELD IN MEMORY, and the
 * reason is the register file. On SHARC rN and fN are the SAME
 * register; the design needs f0-f12 for the arithmetic and r13-r15 are
 * the caller's, so there is nowhere to keep the slope alive across the
 * body. Holding a loop count in one of the low sixteen while a float
 * landed in its twin is precisely how the GEQ design walked off the end
 * of its array (lib/geq_design_fx.asm), so this does not repeat the
 * trick with a spare register. Both words are written before any float
 * lands, and read after all of them have. One crossover node, one
 * caller, control rate: no reentrancy to protect. */
.section/dm seg_dmda;
.var _xod_inv2q = 0;         /* 1/(2Q) for the slope in force */
.var _xod_second = 0;        /* 1 = stage 2 is a copy (LR4), 0 = identity */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _xover_design_LR — design one crossover into a staging array.
 *
 *   f0 =  corner frequency in Hz, as the host wrote it
 *   r8 =  slope in dB/octave, as the host wrote it (12 or 24)
 *   i2 -> _xover_coeffs_next, 20 words: LP, LP, HP, HP
 *
 * Returns r0 = 1 if the array was written, 0 if the frequency or the
 * slope was outside the contract's domain and nothing was touched. The
 * caller raises its own swap only on 1, so an out-of-domain write is a
 * no-op end to end rather than a crossfade to the same coefficients.
 *
 * THE SLOPE IS CONSUMED FIRST, before any float is placed, because r8
 * and f8 are one register and f8 is where `inv` lives.
 *
 * Clobbers r0-r12, f0-f12, i2. r13-r15 and f13-f15 are untouched: on
 * SHARC rN and fN are the SAME register, and holding a loop count or a
 * return value in one of the low sixteen while a float lands in its
 * twin is how the GEQ design walked off the end of its array (see
 * lib/geq_design_fx.asm).
 *--------------------------------------------------------------------*/
.global _xover_design_LR;
_xover_design_LR:
    l2 = 0;                      /* i2 is a plain pointer, not a ring */
    /* ---- slope: 24 or 12, or nothing happens ---- */
    r1 = XO_SLOPE_LR4;
    r1 = r8 - r1;
    if eq jump (pc, .xod_lr4);
    r1 = XO_SLOPE_LR2;
    r1 = r8 - r1;
    if ne jump (pc, .xod_reject);   /* 6 and 18: ignored, not clamped */
    r1 = XO_INV2Q_LR2;
    dm(_xod_inv2q) = r1;
    r1 = 0;
    dm(_xod_second) = r1;
    jump (pc, .xod_slope_done);
.xod_lr4:
    r1 = XO_INV2Q_LR4;
    dm(_xod_inv2q) = r1;
    r1 = 1;
    dm(_xod_second) = r1;
.xod_slope_done:
    /* ---- domain: 50 .. 500 Hz, or nothing happens ---- */
    r1 = XO_FMIN;
    f1 = r1;
    comp(f0, f1);
    if lt jump (pc, .xod_reject);
    r1 = XO_FMAX;
    f1 = r1;
    comp(f0, f1);
    if gt jump (pc, .xod_reject);

    r1 = XO_2PI_FS;
    f1 = r1;
    f1 = f0 * f1;                /* x */
    f3 = f1 * f1;                /* x2 */

    /* ---- s = x*(1 - x2/6*(1 - x2/20)) ---- */
    r2 = XO_INV20;
    f2 = r2;
    f11 = f3 * f2;               /* x2/20 */
    r2 = XO_ONE;
    f2 = r2;
    f11 = f2 - f11;
    r12 = XO_INV6;
    f12 = r12;
    f11 = f11 * f12;             /* (1 - x2/20)/6 */
    f11 = f3 * f11;              /* x2/6*(1 - x2/20) */
    f11 = f2 - f11;
    f4 = f1 * f11;               /* s = sin x */

    /* ---- u = x2/2*(1 - x2/12*(1 - x2/30)) ---- */
    r12 = XO_INV30;
    f12 = r12;
    f11 = f3 * f12;              /* x2/30 */
    f11 = f2 - f11;
    r12 = XO_INV12;
    f12 = r12;
    f11 = f11 * f12;
    f11 = f3 * f11;
    f11 = f2 - f11;
    r12 = XO_HALF;
    f12 = r12;
    f11 = f3 * f11;
    f5 = f11 * f12;              /* u = 1 - cos x */

    /* ---- al = s/(2Q), inv = 1/(1 + al) ---- */
    r12 = dm(_xod_inv2q);
    f12 = r12;
    f6 = f4 * f12;               /* al */
    f7 = f2 + f6;                /* d = 1 + al */
    r12 = XO_TWO;
    f12 = r12;
    f8 = recips f7;
    f11 = f7 * f8;
    f11 = f12 - f11;
    f8 = f8 * f11;
    f11 = f7 * f8;
    f11 = f12 - f11;
    f8 = f8 * f11;
    f11 = f7 * f8;
    f11 = f12 - f11;
    f8 = f8 * f11;               /* inv */

    /* ---- the shared denominator, offset-encoded ---- */
    f11 = f5 + f5;               /* 2u */
    f10 = f6 + f6;               /* 2al */
    f9 = f11 + f10;
    f9 = f9 * f8;                /* c1 = (2u + 2al)*inv */
    f10 = f10 * f8;              /* c2 = 2al*inv */

    /* ---- LP stage 1 ---- */
    r12 = XO_HALF;
    f12 = r12;
    f2 = f5 * f12;
    f2 = f2 * f8;                /* b0 = (u/2)*inv */
    f11 = f11 * f8;              /* n1 = 2u*inv    */
    r0 = 0;                      /* n2 = 0, exactly */
    dm(i2, 1) = f2;
    dm(i2, 1) = f11;
    dm(i2, 1) = r0;
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;

    /* ---- LP stage 2: the SAME section at LR4, the identity at LR2 ----
     * r7/f7 held `d = 1 + al`, dead since `inv`; r6/f6 held `al`, dead
     * since c1 and c2. */
    r7 = dm(_xod_second);
    r7 = pass r7;
    if eq jump (pc, .xod_lp_identity);
    dm(i2, 1) = f2;
    dm(i2, 1) = f11;
    dm(i2, 1) = r0;
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;
    jump (pc, .xod_hp);
.xod_lp_identity:
    /* THE COMPILED IDENTITY IN THE OFFSET ENCODING: b0 = 1,
     * n1 = b1 + 2b0 = 2, n2 = b2 - b0 = -1, c1 = 2 + a1 = 2,
     * c2 = 1 - a2 = 1 -- the same five words `_xover_coeffs_next`
     * boots with, so an LR2 second stage is bit-identical to a stage
     * that was never designed. Written out at both sites rather than
     * called: a call here would be the only nested call in the design
     * path, for ten instructions. */
    r6 = XO_ONE;
    dm(i2, 1) = r6;
    r6 = XO_TWO;
    dm(i2, 1) = r6;
    r6 = XO_MONE;
    dm(i2, 1) = r6;
    r6 = XO_TWO;
    dm(i2, 1) = r6;
    r6 = XO_ONE;
    dm(i2, 1) = r6;
.xod_hp:
    /* ---- HP stage 1 ---- */
    r12 = XO_TWO;
    f12 = r12;
    f2 = f12 - f5;               /* 2 - u */
    r12 = XO_HALF;
    f12 = r12;
    f2 = f2 * f12;
    f2 = f2 * f8;                /* b0 = ((2-u)/2)*inv */

    /* THE LR2 HIGHPASS IS INVERTED, and without that this is not a
     * crossover. At 4th order the paths are 360 degrees apart at the
     * corner and sum flat as designed; at 2nd order they are 180 apart
     * and LP + HP NULLS at the corner -- -242 dB on the model before
     * this branch existed. Every 2nd-order Linkwitz-Riley is specified
     * with one path reversed. It costs one negation: the HP numerator
     * is (b0, -2*b0, b0), so in the offset encoding n1 = b1 + 2*b0 and
     * n2 = b2 - b0 are zero and STAY zero under a sign flip, and only
     * b0 changes. Done here rather than left to an output polarity
     * switch, because a split that sums flat only when a host remembers
     * to flip something is not one the product can ship. */
    r7 = dm(_xod_second);
    r7 = pass r7;
    if ne jump (pc, .xod_hp_b0);
    f2 = -f2;
.xod_hp_b0:
    dm(i2, 1) = f2;
    dm(i2, 1) = r0;              /* n1 = 0, exactly */
    dm(i2, 1) = r0;              /* n2 = 0, exactly */
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;

    /* ---- HP stage 2 ---- */
    r7 = dm(_xod_second);
    r7 = pass r7;
    if eq jump (pc, .xod_hp_identity);
    dm(i2, 1) = f2;
    dm(i2, 1) = r0;
    dm(i2, 1) = r0;
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;
    jump (pc, .xod_done);
.xod_hp_identity:
    r6 = XO_ONE;
    dm(i2, 1) = r6;
    r6 = XO_TWO;
    dm(i2, 1) = r6;
    r6 = XO_MONE;
    dm(i2, 1) = r6;
    r6 = XO_TWO;
    dm(i2, 1) = r6;
    r6 = XO_ONE;
    dm(i2, 1) = r6;
.xod_done:
    r0 = 1;
    rts;

.xod_reject:
    r0 = 0;
    rts;
_xover_design_LR.end:
