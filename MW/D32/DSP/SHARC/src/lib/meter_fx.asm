/*======================================================================
 * meter_fx.asm — the block-rate half of the rebuilt meter (D5, Q4.28)
 *
 * NORMATIVE REFERENCE: tools/dsp/fixed_ref.py::meter_block — this code
 * must match it BIT-EXACTLY. That reference did not exist before
 * 2026-08-28; the meter it replaces had four recorded defects and
 * nothing to test against (tools/dsp/hw-reports/mtr-2026-08-23.md).
 *
 * WHAT THE CALLER DOES, and it is deliberately almost nothing. Per
 * sample, touching no memory at all:
 *
 *     r8 = max(r8, x);            running maximum
 *     mrf = mrf + x * x (ssi);    exact sum of squares, 80-bit
 *     r9 = min(r9, x);            running minimum
 *
 * Three instructions. The old meter was a call, an rts, two constant
 * reloads and a branch per sample -- ~20 cycles/sample/channel, 37.5 %
 * of the fabric when it was last measured. Peak comes from max and min
 * rather than from abs(x) because MAX and MIN are one ALU op each while
 * an abs would be a third op on top of a max; the sign fold happens once
 * per block, here.
 *
 * WHO THE CALLER IS, since 2026-08-29 (PW ruling, wide-word metering).
 * Not the meter node: the SOURCE node, inside its own sample loop, with
 *
 *     x = mr1b     the MS 32-bit word of the product it just formed
 *
 * -- the Q8.24 view of the signal at the tap point, before the rounding
 * half goes in and before the saturation fix-up runs. That is the whole
 * change: sign, the full over-range a 32-bit Q4.28 store cannot hold, and
 * 24 fractional bits (-144 dB). Truncation is fine for metering; the
 * absence of saturation is the FEATURE. The source hands the finished
 * accumulators over in _mtr_acc_<meter>, five words once per block, and
 * the meter node does nothing per sample at all.
 *
 * A source with no accumulator at its tap point -- chip 2's OUTPUT_TDM is
 * a copy, its bus COMPRESSOR finishes in the ALU -- publishes the same
 * value in the same format instead (_mtr_wide_<src>, ashift by -4), so
 * this fold has ONE input format and no variants.
 *
 * WHY THE STATE IS 64-BIT. Both one-poles have time constants of
 * hundreds of blocks, so each per-block correction is ~1e-4 of the
 * state. Held in Q4.28 that correction rounds to zero for anything
 * below about -50 dBFS and the meter stops moving -- a dead zone right
 * in the middle of the useful range. Held as Q8.56, which is what the
 * multiplier produces anyway, the correction is a single exact MAC and
 * the smallest representable step is 2^-56.
 *
 *     ms64 += alpha * (ms_blk - (ms64 >> 28))
 *     pk64  = pk_blk << 28                   if pk_blk > (pk64 >> 28)
 *     pk64 -= beta  * (pk64 >> 28)           otherwise
 *
 * alpha and beta come from dsp_block.h and are functions of the BLOCK
 * RATE: the time constants are properties of the meter, so the
 * coefficients move when the block size moves. That is the bug this
 * whole file is downstream of -- the old constant was derived for 1500
 * blocks/s and applied per SAMPLE.
 *
 * READBACK stays FLOAT (the host contract) and is the only part that is
 * rate-limited: the measurement is full block rate, the presentation is
 * every DSP4_MTR_CVT_DIV blocks. A square root and two float converts
 * per meter per block is real money at BLOCK=8 and no display needs
 * 6 kHz. _mtr_block_tick sets the flag once per block.
 *======================================================================*/

#include "dsp_block.h"

/* THE METER'S INPUT IS Q8.24 (PW ruling 2026-08-29): the MS 32-bit word of
 * the accumulator that produced the signal at the tap point, unrounded and
 * unsaturated. Squares are therefore Q16.48, and the right shift that turns
 * the exact sum of BLOCK of them into a Q4.28 mean square is 48 - 28 = 20
 * fraction bits plus log2(BLOCK) for the mean. The mean still costs no
 * divide. It was (28 + shift) while the meter read a stored Q4.28 block. */
#define MTR_SQSH   (20 + DSP4_BLOCK_SHIFT)

.section/dm seg_dmda;

/* 1 on the blocks whose fold also converts to float for the host. */
.global _mtr_cvt;
.var _mtr_cvt = 1;
.var _mtr_cvt_cnt = 1;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _mtr_block_tick — once per block, before the node chain.
 * Clobbers r0, r1, r2.
 *----------------------------------------------------------------------*/
.global _mtr_block_tick;
_mtr_block_tick:
    r1 = 0;
    dm(_mtr_cvt) = r1;
    r0 = dm(_mtr_cvt_cnt);
    r0 = r0 - 1;
    comp(r0, r1);
    if gt jump (pc, .mtk_done);
    r2 = DSP4_MTR_CVT_DIV;
    r0 = r2;
    r2 = 1;
    dm(_mtr_cvt) = r2;
.mtk_done:
    dm(_mtr_cvt_cnt) = r0;
    rts;
_mtr_block_tick.end:

/*----------------------------------------------------------------------
 * _mtr_flush — hand a block's meter accumulators to the meter node.
 *
 * SHARED, and for one reason: chip 1 has under two thousand bytes of
 * program memory left. Eight instructions inlined in each of the 38
 * metered source nodes is 1,368 bytes; two instructions and a call is
 * 304 plus this routine.
 *
 * In:  r0 = base of the meter's _mtr_acc_<meter>[5]
 *      r13 = block max, r15 = block min (Q8.24)
 *      MRF = exact sum of squares (Q16.48)
 * Clobbers r0, i4, l4.
 *----------------------------------------------------------------------*/
.global _mtr_flush;
_mtr_flush:
    l4 = 0;
    i4 = r0;
    dm(i4, 1) = r13;
    dm(i4, 1) = r15;
    r0 = mr0f;
    dm(i4, 1) = r0;
    r0 = mr1f;
    dm(i4, 1) = r0;
    r0 = mr2f;
    dm(i4, 0) = r0;
    rts;
_mtr_flush.end:

/*----------------------------------------------------------------------
 * _mtr_load_fold — the other half of the same trade: load what the
 * source left and fold it. The meter node is then three instructions.
 *
 * In:  r0 = address of _mtr_peak_<meter>  (the fold's variable base)
 *      r1 = base of _mtr_acc_<meter>[5]
 *----------------------------------------------------------------------*/
.global _mtr_load_fold;
_mtr_load_fold:
    l3 = 0;
    i3 = r1;
    r8 = dm(i3, 1);                /* block max, Q8.24 */
    r9 = dm(i3, 1);                /* block min, Q8.24 */
    r1 = dm(i3, 1);
    mr0f = r1;
    r1 = dm(i3, 1);
    mr1f = r1;
    r1 = dm(i3, 0);
    mr2f = r1;                     /* MRF = sum of squares, Q16.48 */
#if !DSP4_MTR_NOFOLD
    call _mtr_fold;
#endif
    rts;
_mtr_load_fold.end:

/*----------------------------------------------------------------------
 * _mtr_fold — fold one block's accumulators into the meter state.
 *
 * In:  r0  = meter variable base:
 *              +0 peak (float)   +1 rms (float)   +2 gr (float)
 *              +3 pk_lo  +4 pk_hi  +5 ms_lo  +6 ms_hi   (Q8.56)
 *      r8  = block maximum of x   (Q4.28)
 *      r9  = block minimum of x   (Q4.28)
 *      MRF = exact sum of x*x over the block (Q8.56)
 * Out: state updated; peak/rms rewritten on conversion blocks.
 * Clobbers: r0-r15, f0-f15, i3, m3, l3, MRF.
 *----------------------------------------------------------------------*/
.global _mtr_fold;
_mtr_fold:
    l3 = 0;
    i3 = r0;
    r7 = r0;                       /* keep the base for the float stores */

    /* ---- block peak = max(max, -min), saturating ---------------------
     * -min overflows only at exactly -2^31, which the saturated sample
     * path cannot produce, but the guard is two instructions and a peak
     * meter that reads negative is not a small wrong answer. */
    r6 = 0x7FFFFFFF;
    r5 = 0;
    r9 = -r9;
    comp(r9, r5);
    if lt r9 = r6;
    r8 = max(r8, r9);              /* r8 = pk_blk, Q8.24, >= 0 */

    /* ---- pk_blk into the state's Q4.28 domain ------------------------
     * The 64-bit peak state and the float readback are Q4.28 views and
     * they do not move; only the INPUT format changed. Q8.24 -> Q4.28 is a
     * left shift of 4, and the shift is where the meter's over-range
     * finally runs out: it holds up to 8.0 linear, +18.06 dBFS, against a
     * saturated Q4.28 store that could never report more than 0 dBFS at
     * all. Anything above that clamps here rather than wrapping into a
     * negative peak. */
    r4 = 0x07FFFFFF;               /* the largest Q8.24 that fits Q4.28 */
    comp(r8, r4);
    if gt r8 = pass r4;
    r8 = lshift r8 by 4;           /* r8 = pk_blk, Q4.28, >= 0 */

    /* ---- block mean square = sat(MRF >> MTR_SQSH) --------------------
     * MRF is a sum of squares, so it is non-negative and the only
     * overflow direction is upward. */
    r0 = mr0f;
    r2 = mr1f;
    r3 = mr2f;
#if MTR_SQSH < 32
    r0 = lshift r0 by -MTR_SQSH;
    r4 = lshift r2 by (32 - MTR_SQSH);
    r0 = r0 or r4;
    /* bit 31 and above of the result live at bit MTR_SQSH-1 and above of
     * the high word: anything there means the mean square does not fit
     * Q4.28 (|x| would have to exceed 2.83 full scale). */
    r4 = lshift r2 by -(MTR_SQSH - 1);
#else
    r0 = lshift r2 by -(MTR_SQSH - 32);
    r4 = lshift r2 by -31;
#endif
    r4 = r4 or r3;
    comp(r4, r5);
    if ne r0 = r6;                 /* r0 = ms_blk, Q4.28 */

    /* ---- load the 64-bit state -------------------------------------- */
    m3 = 3;
    modify(i3, m3);                /* i3 -> pk_lo */
    r10 = dm(i3, 1);               /* pk_lo */
    r11 = dm(i3, 1);               /* pk_hi */
    r12 = dm(i3, 1);               /* ms_lo */
    r13 = dm(i3, 0);               /* ms_hi */

    /* ---- RMS window: ms64 += alpha * (ms_blk - (ms64 >> 28)) --------- */
    r14 = lshift r12 by -28;
    r15 = lshift r13 by 4;
    r14 = r14 or r15;              /* ms_q, the Q4.28 view of the state */
    r14 = r0 - r14;                /* diff */
    mr0f = r12;
    mr1f = r13;
    r15 = ashift r13 by -31;
    mr2f = r15;                    /* MRF = ms64, sign extended 64 -> 80 */
    r15 = DSP4_MTR_ALPHA_Q;
    mrf = mrf + r14 * r15 (ssi);
    r12 = mr0f;
    r13 = mr1f;

    /* ---- peak hold: instant attack, one-pole decay ------------------- */
    r14 = lshift r10 by -28;
    r15 = lshift r11 by 4;
    r14 = r14 or r15;              /* pk_q */
    comp(r8, r14);
    if le jump (pc, .mtf_decay);
    r10 = lshift r8 by 28;         /* pk64 = pk_blk << 28 */
    r11 = ashift r8 by -4;
    jump (pc, .mtf_stored);
.mtf_decay:
    mr0f = r10;
    mr1f = r11;
    r15 = ashift r11 by -31;
    mr2f = r15;
    r15 = DSP4_MTR_BETA_Q;
    mrf = mrf - r14 * r15 (ssi);
    r10 = mr0f;
    r11 = mr1f;
.mtf_stored:
    i3 = r7;
    modify(i3, m3);
    dm(i3, 1) = r10;
    dm(i3, 1) = r11;
    dm(i3, 1) = r12;
    dm(i3, 0) = r13;

    /* ---- host readback, on conversion blocks only -------------------- */
    r0 = dm(_mtr_cvt);
    r1 = 0;
    comp(r0, r1);
    if eq rts;

    i3 = r7;
#if DSP4_MTR_NOCVT
    rts;
#endif
    r15 = -28;

    /* peak: linear amplitude */
    r14 = lshift r10 by -28;
    r0 = lshift r11 by 4;
    r14 = r14 or r0;
    f2 = float r14 by r15;
    dm(i3, 1) = f2;

    /* rms: sqrt of the windowed mean square, by RSQRTS + two Newton
     * steps. sqrt(a) = a * rsqrt(a), and rsqrt(0) is not finite, so zero
     * is answered directly rather than nursed through the iteration. */
    r14 = lshift r12 by -28;
    r0 = lshift r13 by 4;
    r14 = r14 or r0;
    r0 = 0;
    comp(r14, r0);
    if le jump (pc, .mtf_zero);
    f1 = float r14 by r15;         /* a, linear mean square */
#if DSP4_MTR_NOSQRT
    dm(i3, 0) = f1;
    rts;
#endif
    f2 = rsqrts f1;                /* x0 ~ 1/sqrt(a), 4-bit seed */
    r3 = 0x3FC00000;               /* 1.5f */
    f3 = r3;
    r4 = 0x3F000000;               /* 0.5f */
    f4 = r4;
    f5 = f1 * f4;                  /* a/2 */
    f6 = f2 * f2;
    f6 = f5 * f6;
    f6 = f3 - f6;
    f2 = f2 * f6;                  /* one Newton step */
    f6 = f2 * f2;
    f6 = f5 * f6;
    f6 = f3 - f6;
    f2 = f2 * f6;                  /* two */
    f6 = f2 * f2;
    f6 = f5 * f6;
    f6 = f3 - f6;
    f2 = f2 * f6;                  /* three -- RSQRTS is a 4-bit seed */
    f2 = f1 * f2;                  /* sqrt(a) */
    dm(i3, 0) = f2;
    rts;
.mtf_zero:
    r0 = 0;
    dm(i3, 0) = r0;
    rts;
_mtr_fold.end:
