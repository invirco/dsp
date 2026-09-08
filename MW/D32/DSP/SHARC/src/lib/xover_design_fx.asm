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
 * LINKWITZ-RILEY 4th ORDER is what the node's shape already committed
 * to: two LP stages and two HP stages, no more and no fewer. LR4 is two
 * cascaded 2nd-order Butterworth sections (Q = 1/sqrt2) at the same
 * corner, so BOTH STAGES OF A PATH ARE THE SAME FIVE WORDS and this
 * routine designs two sets, not four.
 *
 * WHAT IT EVALUATES:
 *
 *     x   = 2*pi*f0/fs                 (0.0065 .. 0.065 rad over 50-500 Hz)
 *     s   = sin x                      x*(1 - x2/6*(1 - x2/20))
 *     u   = 1 - cos x                  x2/2*(1 - x2/12*(1 - x2/30))
 *     al  = s / (2Q) = s / sqrt2
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
 * A WORD OUTSIDE 50-500 Hz IS IGNORED, NOT CLAMPED, AND THAT IS A
 * DELIBERATE READING OF A CONTRACT DEFECT. In
 * defs/products/d24/dsp.csv, MainCtr/MainL/MainR/MainSub each carry a
 * `CrossoverFreq` AND a `CrossoverSlope`, and ALL EIGHT resolve to
 * address 0x0575 -- eight cells, one word, marked "shared crossover
 * word". A slope is a small number however it is encoded; clamping it
 * into the frequency would move the crossover to 50 Hz every time the
 * host set a slope. Ignoring it leaves the split where the last legal
 * frequency put it. UNTIL THAT ROW IS SPLIT IN `defs` THE SLOPE IS NOT
 * SETTABLE and the crossover is LR4 -- 24 dB/octave, which is the top
 * of the cell's own table.
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
#define XO_INV2Q       0x3F3504F3    /* 1/(2Q), Q = 1/sqrt2 */
#define XO_FMIN        0x42480000    /* 50.0 Hz  — Table 0=50   */
#define XO_FMAX        0x43FA0000    /* 500.0 Hz — Table 127=500 */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _xover_design_LR4 — design one crossover into a staging array.
 *
 *   f0 =  corner frequency in Hz, as the host wrote it
 *   i2 -> _xover_coeffs_next, 20 words: LP, LP, HP, HP
 *
 * Returns r0 = 1 if the array was written, 0 if the word was outside
 * the contract's domain and nothing was touched. The caller raises its
 * own swap only on 1, so an out-of-domain write is a no-op end to end
 * rather than a crossfade to the same coefficients.
 *
 * Clobbers r0-r12, f0-f12, i2. r13-r15 and f13-f15 are untouched: on
 * SHARC rN and fN are the SAME register, and holding a loop count or a
 * return value in one of the low sixteen while a float lands in its
 * twin is how the GEQ design walked off the end of its array (see
 * lib/geq_design_fx.asm).
 *--------------------------------------------------------------------*/
.global _xover_design_LR4;
_xover_design_LR4:
    l2 = 0;                      /* i2 is a plain pointer, not a ring */
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
    r12 = XO_INV2Q;
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

    /* ---- LP stage, written twice: LR4 is two identical sections ---- */
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
    dm(i2, 1) = f2;
    dm(i2, 1) = f11;
    dm(i2, 1) = r0;
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;

    /* ---- HP stage, written twice ---- */
    r12 = XO_TWO;
    f12 = r12;
    f2 = f12 - f5;               /* 2 - u */
    r12 = XO_HALF;
    f12 = r12;
    f2 = f2 * f12;
    f2 = f2 * f8;                /* b0 = ((2-u)/2)*inv */
    dm(i2, 1) = f2;
    dm(i2, 1) = r0;              /* n1 = 0, exactly */
    dm(i2, 1) = r0;              /* n2 = 0, exactly */
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;
    dm(i2, 1) = f2;
    dm(i2, 1) = r0;
    dm(i2, 1) = r0;
    dm(i2, 1) = f9;
    dm(i2, 1) = f10;

    r0 = 1;
    rts;

.xod_reject:
    r0 = 0;
    rts;
_xover_design_LR4.end:
