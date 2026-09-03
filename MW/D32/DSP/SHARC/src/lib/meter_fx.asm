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

#if DSP4_BLOCK_KERNELS && DSP4_GAIN_SIMD
/*----------------------------------------------------------------------
 * _gsimd_enter — open GAIN's SIMD block.
 *
 * SHARED ON PW'S RULING (2026-09-02): the eleven instructions below were
 * inlined in each of the 32 gain nodes and that is about 1.4 KB of a chip 1
 * whose code section had 1,842 bytes left. One call/rts per node per block
 * buys all of it back. THE CALL IS NOT FREE -- 15.04 cycles at the price
 * D66 measured, 0.94 c/s at block 16 -- and it is paid for out of three
 * savings taken in the same change: the block load folded into the meter's
 * MAC (-8 cycles/block), the loop counter as an immediate (-1), and
 * _gsimd_flush falling through into _mtr_flush instead of jumping (-6.02).
 * Net at block 16 is within a cycle of zero, and the program memory is
 * real. Both halves of that trade are recorded because neither is obvious.
 *
 * In:  r1 = the ONE effective gain word (polarity as sign, mute as 0.0),
 *      i0/i1/i4 and l0/l1/l4 already set by the caller -- untouched here.
 * Out: PEYEN set, MODE1 parked in _gsimd_save, r1 = the gain word IN BOTH
 *      COMPUTE UNITS, r6/r7 = the rounding half, r10 = the saturation mask.
 * Clobbers r1, r2, r6, r7, r10.
 *----------------------------------------------------------------------*/
.extern _gsimd_g;
.global _gsimd_enter;
_gsimd_enter:
    /* The gain word, once per compute unit, written with PEYEN still DOWN:
     * a direct store inside the region writes the PEy shadow to the next
     * word, and these two must differ from each other's shadow rather than
     * agree with it. */
    dm(_gsimd_g) = r1;
#if DSP4_GAIN_SIMD_NEGCTL
    /* NEGATIVE CONTROL. PEy's gain word is ZERO, so every ODD sample of
     * every block comes out silent. It must move the bus; if it does not,
     * PEYEN was never up and the "SIMD" kernel has been running one unit
     * all along -- which from outside is indistinguishable from a bit-exact
     * result, and is the silent fallback c2dyngold was caught by. */
    r2 = 0;
    dm(_gsimd_g + 1) = r2;
#else
    dm(_gsimd_g + 1) = r1;
#endif
    /* MODE1 saved and restored WHOLE, not bit-toggled, so a caller that had
     * already masked interrupts stays masked. INTERRUPTS ARE NOT MASKED
     * HERE: _sec_isr and _diag_timer_isr clear PEYEN after `push sts` and
     * `pop sts` puts it back, which is what the paired dynamics and the
     * paired cascade already rely on. Masking a whole block loop is what
     * hung the part on 2026-08-28. */
    r2 = mode1;
    dm(_gsimd_save) = r2;
    bit set mode1 0x00200000;          /* PEYEN */
    nop;
    nop;
    r1 = dm(_gsimd_g);                 /* g into BOTH units */
    /* THE CONSTANTS ARE LOADED HERE, INSIDE THE REGION, and the first cut
     * of this kernel got it wrong. Loaded with PEYEN down they reach PEx
     * only and PEy keeps whatever it held -- zero out of reset -- so PEy
     * would TRUNCATE its samples instead of rounding them and saturate
     * them against a mask of 0. busgold cannot see either fault: its
     * stimulus is a +/-0.5 square at UNITY gain, whose Q4.28 word is 2^28
     * exactly, so every product's low 28 bits are already zero and
     * truncation equals rounding on every sample -- and |x| = 0.5 against
     * a gain under 8 can never saturate. It returned 0 of 256 with this
     * wrong. gainsimd.sh is the bar that can see it. */
    r6 = 0x08000000;                   /* 2^27, the rounding half */
    r7 = 1;
    r10 = 0x7FFFFFFF;
    rts;                               /* returns with PEYEN up */
_gsimd_enter.end:

/*----------------------------------------------------------------------
 * _gsimd_gain_blk — THE WHOLE METERED GAIN BLOCK, for every gain node.
 *
 * WHY THE KERNEL ITSELF IS SHARED, and it is the block-rate half that made
 * it worth doing. A two-point fit across blocks 8 and 16 (2026-09-02,
 * gainprof.sh) splits this node into a PER-SAMPLE rate and a FIXED
 * per-block cost, and the split is not what the sample loop's prominence
 * suggests:
 *
 *     scalar   18.88 cycles/sample   252 cycles/block fixed
 *     SIMD      8.62 cycles/sample   296 cycles/block fixed
 *
 * The SIMD loop is a FACTOR OF 2.19 on the per-sample path -- better than
 * the 2x the pairing is worth, because the two extraction shifts fold into
 * one instruction and the block load rides on the meter's MAC. But at
 * block 16 the fixed half is 18.5 c/s against the loop's 8.6, so it
 * DOMINATES TWO TO ONE -- and the node was paying TWO call/rts pairs into
 * this file per block, one to open the PEYEN region and one to close it,
 * at 15.04 cycles each.
 *
 * Nothing in the sample loop is per-node: the pool addresses arrive in
 * i0/i1/i4 and the meter's accumulator base in r0, and the loop touches no
 * node symbol at all. So the whole body moves here and the node makes ONE
 * call instead of two. That is -15.04 cycles/block on its own, and it also
 * takes about 2.5 KB of chip 1's code section back, because the loop was
 * being emitted 32 times.
 *
 * Each compute unit carries HALF of the block's meter -- PEx the even
 * samples, PEy the odd -- so the two halves are added back together at the
 * end, PEYEN drops, and this falls into _mtr_flush.
 *
 * THE ADDITION IS EXACT, WHICH IS WHY THE SPLIT COSTS NOTHING NUMERICALLY.
 * MRF is an 80-bit integer accumulator with no rounding and no
 * saturation; a block of 16 samples of x*x tops out around 2^66, so
 * nothing here can overflow, and integer addition is associative. The
 * peak and trough are max and min, which are associative too. So the
 * accumulators this leaves are BIT-IDENTICAL to the ones the scalar loop
 * would have left, not merely close.
 *
 * SHARED for _mtr_flush's reason, restated by measurement: the first cut
 * of this had the whole sequence inlined in all 32 gain nodes and chip 1's
 * sec_swco OVERFLOWED at link. Two instructions and a call per node
 * against thirty inlined.
 *
 * ENTERED WITH PEYEN STILL SET. The five stores below are what needs it:
 * a direct store inside the region writes the PEx copy at the address and
 * the PEy copy at address+1, which is exactly how the second half gets
 * out. Every _gsimd_* variable is two words for that reason.
 *
 * In:  PEYEN DOWN. i0 = the block to read, i1 = the chain slot to write,
 *      i4 = the post-trim tap block; r1 = the ONE effective gain word
 *      (polarity as sign, mute as 0.0); r0 = base of the meter's
 *      _mtr_acc_<meter>[5].
 * Out: the block gained, rounded, saturated and stored to BOTH slots; the
 *      meter accumulators written; PEYEN back as the caller had it; i1 one
 *      past the end of the block it wrote, which is where the caller reads
 *      the last sample back from.
 * Clobbers r0-r15, i4, l0, l1, l4, MRF, MRB.
 *----------------------------------------------------------------------*/
.extern _gsimd_save;
.extern _gsimd_g;
.extern _gsimd_acc;
.extern _gsimd_sq0;
.extern _gsimd_sq1;
.extern _gsimd_sq2;
.extern _gsimd_max;
.extern _gsimd_min;
#if DSP4_GAIN_FLOAT
.extern _gsimd_clipf;
#define GSGF_RND32 DSP4_RND32_BIT
#endif
.global _gsimd_gain_blk;
_gsimd_gain_blk:
    /* The meter's accumulator base has to survive the sample loop, and the
     * loop uses r0 as its sample register. One word of DM at block rate. */
    dm(_gsimd_acc) = r0;
    l0 = 0;
    l1 = 0;
    l4 = 0;
    /* ---- open the region: the gain word into both units, the constants
     * where both units see them. See _gsimd_enter for why the constants
     * CANNOT be loaded before PEYEN goes up. */
    dm(_gsimd_g) = r1;
#if DSP4_GAIN_SIMD_NEGCTL
    r2 = 0;
    dm(_gsimd_g + 1) = r2;
#else
    dm(_gsimd_g + 1) = r1;
#endif
    r2 = mode1;
    dm(_gsimd_save) = r2;
    bit set mode1 0x00200000;          /* PEYEN */
#if DSP4_GAIN_FLOAT
#if DSP4_BQ_FLOAT32
    bit set mode1 GSGF_RND32;          /* IEEE single: the 32-bit control */
#else
    bit clr mode1 GSGF_RND32;          /* 40-bit extended: the arm itself */
#endif
#endif
    nop;
    nop;
    r1 = dm(_gsimd_g);                 /* g into BOTH units */
#if DSP4_GAIN_FLOAT
    /* THE AUDIO GAIN IS FLOATED FROM THE METER'S OWN WORD, not read
     * separately from _gain_coeff. r1 already has polarity and mute
     * folded in at control rate (the crosspoint-coefficient fold), and a
     * 32-bit integer is exact in a 40-bit float, so the two paths cannot
     * disagree about what gain was applied -- which they would if the
     * audio took the unquantised float and the meter kept the Q4.28
     * word. One instruction, at block rate. */
    r14 = -28;
    f4 = float r1 by r14;              /* g, both units */
    r9 = 28;
    f3 = dm(_gsimd_clipf);             /* the ONE clamp, both units */
#else
    r6 = 0x08000000;                   /* 2^27, the rounding half */
    r7 = 1;
    r10 = 0x7FFFFFFF;
#endif
    /* ---- the block ---- */
    r13 = 0x80000000;                  /* block max: most negative */
    r15 = 0x7FFFFFFF;                  /* block min: most positive */
    mrf = 0;                           /* exact sum of squares     */
    r12 = 0;                           /* exactly neutral: zero adds nothing
                                        * to a sum of squares and cannot move
                                        * a non-negative peak */
    /* The meter runs ONE SAMPLE BEHIND and that is what makes it free:
     * reading mr1b in the instruction after the MAC that produced it
     * stalls on the multiplier, and the first cut of the scalar loop
     * measured +25.5 c/s/strip for exactly that. The block load rides on
     * the meter's MAC, which has no dependence on the word being loaded. */
#if DSP4_GAIN_FLOAT
    /* THE FLOAT AUDIO PATH, AND THE FIXED METER BESIDE IT. The wide MAC
     * stays exactly where it was -- same instruction, same two-instruction
     * gap before mr1b is read, same 80-bit MRF sum of squares -- because
     * a meter wants the PRE-CLIP over-range word and an exact,
     * order-independent accumulation, and float gives neither. What goes
     * is the ten instructions of extract-and-saturate on the AUDIO word:
     * one FLOAT, one multiply, one CLIP and one FIX replace them.
     * ELEVEN instructions per two samples against eighteen. */
    /* THE METER'S OPS ARE INTERLEAVED INTO THE FLOAT CHAIN, and that is
     * not tidiness. FLOAT -> multiply -> CLIP -> FIX is a four-deep
     * SERIAL dependency and each link waits on the last: written as four
     * consecutive instructions the loop gave back only 1.49 of the 3.5
     * cycles/sample/strip its instruction count had deleted. The meter's
     * max, min and mr1b read have no dependence on the audio word, so
     * they are the cover. `r12 = mr1b` moves from two instructions after
     * its MAC to three, which is further away and therefore still safe. */
    lcntr = DSP4_BLOCK_HALF, do .gsg_lp until lce;
        mrf = mrf + r12 * r12 (ssi), r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);           /* the METER's wide MAC, unchanged */
        f2 = float r0 by r14;          /* x[n] -> PEx, x[n+1] -> PEy */
        r13 = max(r13, r12);           /* meter, one sample behind */
        f0 = f2 * f4;
        r15 = min(r15, r12);
        r12 = mr1b;                    /* WIDE post-trim, Q8.24 */
        f0 = clip f0 by f3;            /* per-PE compute, NOT a branch */
        r0 = fix f0 by r9;
        dm(i1, 2) = r0;
.gsg_lp:
        dm(i4, 2) = r0;                /* post-trim tap block */
#else
    lcntr = DSP4_BLOCK_HALF, do .gsg_lp until lce;
        mrf = mrf + r12 * r12 (ssi), r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);           /* x[n] -> PEx, x[n+1] -> PEy */
        r13 = max(r13, r12);           /* meter, one sample behind */
        r15 = min(r15, r12);
        r12 = mr1b;                    /* WIDE post-trim, Q8.24 */
        mrb = mrb + r6 * r7 (ssi);
        r8 = mr0b;
        r2 = mr1b;
        r0 = lshift r8 by -28;
        r0 = r0 or lshift r2 by 4;     /* two shifts and an OR, in two */
        r8 = ashift r2 by -28;
        r9 = ashift r0 by -31;
        r11 = ashift r2 by -31;
        r11 = r10 xor r11;
        comp(r8, r9);
        if ne r0 = pass r11;           /* per-PE, NOT a branch */
        dm(i1, 2) = r0;
.gsg_lp:
        dm(i4, 2) = r0;                /* post-trim tap block */
#endif
    /* the last sample's meter ops, outside the loop -- one per unit */
    r13 = max(r13, r12);
    mrf = mrf + r12 * r12 (ssi);
    r15 = min(r15, r12);
    r1 = mr0f;
    dm(_gsimd_sq0) = r1;               /* PEx word, then PEy word */
    r1 = mr1f;
    dm(_gsimd_sq1) = r1;
    r1 = mr2f;
    dm(_gsimd_sq2) = r1;
    dm(_gsimd_max) = r13;
    dm(_gsimd_min) = r15;
    r1 = dm(_gsimd_save);
    mode1 = r1;                        /* PEYEN down, MODE1 restored whole */
    nop;
    nop;
    /* The two halves, added exactly: 96 bits, carry-propagated. Every
     * load is taken FIRST so that nothing sets AC between the add that
     * produces a carry and the add that consumes it. */
    r1 = dm(_gsimd_sq0);
    r2 = dm(_gsimd_sq0 + 1);
    r3 = dm(_gsimd_sq1);
    r4 = dm(_gsimd_sq1 + 1);
    r5 = dm(_gsimd_sq2);
    r6 = dm(_gsimd_sq2 + 1);
    r1 = r1 + r2;
    r3 = r3 + r4 + ci;
    r5 = r5 + r6 + ci;
    mr0f = r1;
    mr1f = r3;
    mr2f = r5;                         /* MRF = the whole block again */
    r13 = dm(_gsimd_max);
    r1 = dm(_gsimd_max + 1);
    r13 = max(r13, r1);
    r15 = dm(_gsimd_min);
    r1 = dm(_gsimd_min + 1);
    r15 = min(r15, r1);
    r0 = dm(_gsimd_acc);               /* the meter's base, back again */
    /* AND NOW IT FALLS THROUGH INTO _mtr_flush, WHICH MUST STAY THE NEXT
     * THING IN THIS FILE. That adjacency is load-bearing: it used to be
     * `jump _mtr_flush`, which is a taken unconditional branch and cost
     * 6.02 cycles a block per node at the price D66 measured. Falling
     * through costs nothing and _mtr_flush's `rts` returns to the GAIN
     * NODE, which is the only caller. Do not insert anything between
     * these two routines. */
_gsimd_gain_blk.end:
#endif

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
/* REACHED BY FALL-THROUGH from _gsimd_flush as well as by call --
 * see the note at the end of that routine. Nothing goes between them. */
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
