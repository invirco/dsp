/*======================================================================
 * dyn_simd_fx.asm — the DYNAMICS, two channels per instruction stream.
 *
 * WHY THIS FILE EXISTS. After strip fusion (2026-08-28) GATE + COMP is
 * 61 % of a signal-present strip -- 668.7 of 1,098.8 cycles/sample --
 * and SIMD that pairs only the biquads caps at ~11 % of a strip. Pairing
 * has to reach the dynamics or it does not matter.
 *
 * NORMATIVE REFERENCE is unchanged: tools/dsp/fixed_ref.py, through the
 * scalar routines in dyn_fx.asm. Every routine here computes the SAME
 * operations in the SAME order on the SAME operands as its scalar twin;
 * only the plumbing differs. Where that was not achievable the deviation
 * is stated at the point it occurs and nowhere else.
 *
 * THE THREE THINGS SIMD ON THIS CORE CANNOT DO, and what is done instead:
 *
 *  1. A BRANCH USES PEx's CONDITION FOR BOTH UNITS. Every data-dependent
 *     branch in the scalar dynamics -- the envelope's attack/release
 *     select, the compressor's unity/hard/soft knee split, exp2's shift
 *     direction, the gate's open/hold/close ladder -- is rewritten as
 *     CONDITIONAL COMPUTE, which each unit evaluates on its own flags.
 *     The idiom (and its trap: build the alternative value BEFORE the
 *     compare, because the ALU op that builds it overwrites the flags)
 *     is the one proved on the biquad pair.
 *
 *  2. A DATA ACCESS READS TWO CONSECUTIVE WORDS -- PEx the addressed one,
 *     PEy the next. So every per-channel operand must be INTERLEAVED
 *     (A's word then B's word), and every SHARED constant must be
 *     DOUBLED. That is why the polynomial coefficients are walked from
 *     _log2_poly_dup / _exp2_poly_dup (generated, same integers, each
 *     entry twice) with modifier 2 rather than from the scalar tables.
 *
 *  3. THE TABLE FORMS OF log2/exp2 CANNOT BE PAIRED AT ALL. A table
 *     lookup is a GATHER at two different indices, and the DAGs are
 *     shared -- one address per access, whatever PEYEN says. Only the
 *     POLYNOMIAL forms pair, which is what DSP4_DYN_TABLES=0 (the
 *     default) already selects. A build with DSP4_DYN_TABLES=1 must not
 *     enable DSP4_SIMD_DYN; the guard at the bottom of this file is the
 *     enforcement.
 *
 * INTERRUPTS. PEYEN is NOT masked around these regions. The systemic fix
 * is already in the tree: _sec_isr and _diag_timer_isr clear PEYEN after
 * `push sts` and `pop sts` restores it, so a handler taken mid-kernel
 * runs scalar and cannot pair-write the registers it saves. Masking
 * interrupts around a kernel this long (a whole block of dynamics, not
 * two biquad stages) would be a ~40 us blackout against a 667 us block.
 *
 * Entry points:
 *   _polyq_simd      r0 = poly(t) pair; i0 -> DOUBLED 6-coeff table
 *   _log2q_simd      r0(Q4.28 > 0) -> log2 Q6.25            clobbers r0-r5,i0
 *   _exp2q_simd      r0(Q6.25) -> 2^l Q4.28 saturated       clobbers r0-r5,i0
 *   _mrf_rns28_simd  r0 = sat32(rns(MRF,28))                clobbers r1-r3
 *   _compgain_simd   r0 = gain Q4.28; r8-r11 = thr/slope/halfk/k2
 *                                                           clobbers r0-r5,r7,i0
 *   _comp_pair_blk   one block of COMPRESSOR for two channels
 *   _gate_pair_blk   one block of GATE for two channels
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#include "dsp_block.h"

#if DSP4_SIMD_DYN

.section/dm seg_dmda;
.extern _log2_poly_dup;
.extern _exp2_poly_dup;

/* MODE1 is saved and restored WHOLE rather than bit-toggled, so a caller
 * that had already masked interrupts stays masked. Two words because the
 * reload happens with PEYEN still set and PEy reads the word after. */
.var _dsim_mode1[2];

/* SAMPLES PER CALL. Both pair kernels used to run exactly
 * DSP4_BLOCK_SIZE samples, which is what the self-test drives them with.
 * The GRAPH cannot: the block-rate PARAMETER CONVERSION lives inside each
 * node's per-sample body behind its `_sample_idx == 0` guard, so the pair
 * driver runs sample 0 of each channel through that scalar body -- which
 * converts, and is bit-identical to the scalar path by construction --
 * and hands the pair the remaining BLOCK-1. Two words because the count
 * is read with PEYEN set in the sample loop. The .var initialiser is the
 * full block, so a caller that does not set it (the self-test) behaves
 * exactly as before. */
.global _dsim_n;
.var _dsim_n[2] = DSP4_BLOCK_SIZE, DSP4_BLOCK_SIZE;

/* ---- COMPRESSOR pair park -------------------------------------------
 * Interleaved by channel: A's word then B's. 8 parameters, 1 state word
 * and 32 samples per channel.
 *
 * THE LAYOUT DECISION, and its cost. The alternative was to repartition
 * the whole block pool into 16 channel PAIRS so the dynamics could read
 * the graph's own buffers directly. This does not: it gathers into a
 * private interleaved park, runs, and scatters back, exactly as
 * _bq_pair_blk does for the cascade. The gather/scatter is 64+64 signal
 * words plus 18 parameter/state words per pair per block -- about 4.6
 * cycles/sample/channel at the measured 1.3 cycles per memory op --
 * against the several hundred a paired dynamics stage saves, and it
 * leaves the pool, the node buffers and every other kernel untouched.
 * DM cost: 82 words for COMP, 74 for GATE, 156 total, one park shared by
 * all sixteen pairs because pairs run one after another.
 *
 * PARAMETER ORDER IS THE INTERFACE: attq, relq, mkq, parq, thr, slope,
 * halfk, k2 -- the four converted alphas/scalars followed by the four
 * words _compgain_fx already reads as a block (_comp_cgp_<nid>).
 */
.global _cmp_par;   .var _cmp_par[16];
.global _cmp_st;    .var _cmp_st[2];    /* envelope */
.global _cmp_gn;    .var _cmp_gn[2];    /* last gain, for the display/witness */
.global _cmp_sig;   .var _cmp_sig[2*DSP4_BLOCK_SIZE];
.var _cmp_ptr[6];                       /* parA parB stA stB sigA sigB */

/* ---- GATE pair park -------------------------------------------------
 * Parameters: attq, relq, thrq, rngq, hold. State: env, gain, target,
 * hold count.
 */
.global _gat_par;   .var _gat_par[10];
.global _gat_st;    .var _gat_st[8];
.global _gat_sig;   .var _gat_sig[2*DSP4_BLOCK_SIZE];
.var _gat_ptr[6];

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _polyq_simd — _polyq_fx with a DOUBLED coefficient table.
 *
 * Identical arithmetic, identical order, identical rounding. The only
 * change is the walk: modifier 2 over a table whose entries are doubled,
 * so both units get C[k] instead of PEy getting C[k+1].
 *--------------------------------------------------------------------*/
.global _polyq_simd;
_polyq_simd:
    l0 = 0;
    r1 = dm(i0, 2);            /* acc = C0, broadcast */
    r5 = 5;
    lcntr = r5, do .pqs_lp until lce;
        mrf = r1 * r0 (ssi);
        r2 = 0x40000000;       /* 2^30 half for >>31 */
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r1 = r2 or r3;         /* rns(acc*t, 31) */
        r2 = dm(i0, 2);
    .pqs_lp:
        r1 = r1 + r2;          /* + C[k] */
    r0 = r1;
    rts;
_polyq_simd.end:

/*----------------------------------------------------------------------
 * _log2q_simd — branch-free already in the scalar; only the table walk
 * changes. leftz and the variable shifts are per-unit operations, so the
 * two channels may have completely different exponents.
 *--------------------------------------------------------------------*/
.global _log2q_simd;
_log2q_simd:
    r1 = leftz r0;
    r2 = 3;
    r2 = r2 - r1;              /* e (can be negative) */
    r3 = ashift r0 by r1;      /* m (MSB set) */
    r4 = 0x7FFFFFFF;
    r0 = r3 and r4;            /* t_q31 */
    r4 = r2;                   /* e survives _polyq_simd (r1,r2,r3,r5) */
    i0 = _log2_poly_dup;
    call _polyq_simd;          /* r0 = frac Q2.30 */
    r3 = 16;                   /* rns(frac, 5) -> Q6.25 */
    r0 = r0 + r3;
    r0 = ashift r0 by -5;
    r2 = lshift r4 by 25;      /* e << 25 */
    r0 = r0 + r2;
    rts;
_log2q_simd.end:

/*----------------------------------------------------------------------
 * _exp2q_simd — the scalar's THREE-WAY BRANCH, flattened.
 *
 * The scalar picks one of: left-shift with saturation (shift <= 0), zero
 * (shift >= 32), or round-and-shift-right. Two channels can want
 * different arms of that, so both candidates are computed unconditionally
 * and selected per unit. The discarded arm's arithmetic is harmless: with
 * the wrong sign the shifts run the other way and the result is thrown
 * away.
 *
 * The saturation constant is loaded BEFORE the compare it is conditioned
 * on -- an ALU op between comp and the conditional move overwrites the
 * flags, which is the whole reason the biquad pair builds its saturated
 * value first.
 *--------------------------------------------------------------------*/
.global _exp2q_simd;
_exp2q_simd:
    r2 = ashift r0 by -25;     /* e = floor(l / 2^25) */
    r4 = r2;                   /* save e across the poly */
    r3 = lshift r2 by 25;
    r1 = r0 - r3;              /* f_q25 in [0, 2^25) */
    r0 = lshift r1 by 6;       /* t_q31 */
    i0 = _exp2_poly_dup;
    call _polyq_simd;          /* r0 = m Q2.30, in [2^30, 2^31) */
    r1 = 2;
    r1 = r1 - r4;              /* shift = 2 - e */

    /* candidate A: shift <= 0, left shift with the back-shift check */
    r2 = -r1;
    r3 = ashift r0 by r2;
    r4 = -r2;
    r5 = ashift r3 by r4;
    r2 = 0x7FFFFFFF;           /* built FIRST: see above */
    comp(r5, r0);
    if ne r3 = pass r2;

    /* candidate B: 0 < shift < 32, rns(m, shift); shift >= 32 -> 0 */
    r2 = r1 - 1;
    r4 = 1;
    r4 = lshift r4 by r2;      /* half */
    r5 = r0 + r4;
    r2 = -r1;
    r5 = ashift r5 by r2;
    r2 = 0;
    r4 = 32;
    comp(r1, r4);
    if ge r5 = pass r2;

    /* select */
    r0 = pass r5;
    r2 = 0;
    comp(r1, r2);
    if le r0 = pass r3;
    rts;
_exp2q_simd.end:

/*----------------------------------------------------------------------
 * _mrf_rns28_simd — _mrf_rns28 with its `if eq rts` replaced by a
 * per-unit conditional move. A conditional RETURN is a branch, so it
 * would have taken PEx's flags for both channels: channel B would have
 * saturated whenever channel A did.
 *--------------------------------------------------------------------*/
.global _mrf_rns28_simd;
_mrf_rns28_simd:
    r1 = 0x08000000;           /* 2^27 rounding half */
    r3 = 1;
    mrf = mrf + r1 * r3 (ssi);
    r1 = mr0f;
    r2 = mr1f;
    r1 = lshift r1 by -28;
    r3 = lshift r2 by 4;
    r0 = r1 or r3;             /* candidate y */
    r1 = ashift r2 by -31;
    r3 = 0x7FFFFFFF;
    r3 = r3 xor r1;            /* saturated value, built FIRST */
    r1 = ashift r2 by -28;
    r2 = ashift r0 by -31;
    comp(r1, r2);
    if ne r0 = pass r3;
    rts;
_mrf_rns28_simd.end:

/*----------------------------------------------------------------------
 * _compgain_simd — the gain computer, both channels, no branches.
 *
 * The scalar's control flow:
 *     x <= 0                    -> unity
 *     over <= -halfk            -> unity
 *     halfk == 0 or over >= halfk -> hard knee
 *     otherwise                 -> soft knee
 *
 * Here BOTH knee candidates are computed every sample and selected per
 * unit, and the unity cases are carried as a per-unit flag in r7 and
 * applied AFTER exp2. They cannot be applied before it: exp2q(0) is
 * 0x0FFFFFE5, not the 0x10000000 the scalar's unity path returns, so
 * folding unity into the exponent would be a one-LSB deviation on every
 * silent sample. r7 is the only register the caller has to give up; it is
 * why the COMP block loop reloads the release alpha from the park each
 * sample instead of holding it.
 *
 * In:  r0 = x_abs Q4.28, r8 = thr, r9 = slope, r10 = halfk, r11 = k2
 * Out: r0 = gain Q4.28.  Clobbers r0-r5, r7, i0, MRF.
 *--------------------------------------------------------------------*/
.global _compgain_simd;
_compgain_simd:
    r1 = 0;
    r2 = 0;
    r7 = 1;                    /* assume unity */
    comp(r0, r1);
    if gt r7 = pass r2;        /* x > 0: not unity on this test */

    call _log2q_simd;          /* r0 = lvl Q6.25 */
    r1 = r0 - r8;              /* over */
    r2 = -r10;
    r3 = 1;
    comp(r1, r2);
    if le r7 = pass r3;        /* over <= -halfk -> unity */

    /* hard-knee candidate: gr = rns(over * slope, 31) */
    mrf = r1 * r9 (ssi);
    r2 = 0x40000000;
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -31;
    r3 = lshift r3 by 1;
    r4 = r2 or r3;             /* gr_hard */

    /* soft-knee candidate: t = over + halfk, t2 = rns(t*t,25),
     * gr = rns(t2*k2,25) */
    r0 = r1 + r10;
    mrf = r0 * r0 (ssi);
    r2 = 0x01000000;           /* 2^24 half for >>25 */
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -25;
    r3 = lshift r3 by 7;
    r5 = r2 or r3;             /* t2 Q6.25 */
    mrf = r5 * r11 (ssi);
    r2 = 0x01000000;
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -25;
    r3 = lshift r3 by 7;
    r5 = r2 or r3;             /* gr_soft Q6.25 */

    /* select: soft iff halfk != 0 AND over < halfk */
    r0 = pass r4;
    comp(r1, r10);
    if lt r0 = pass r5;
    r2 = 0;
    comp(r10, r2);
    if eq r0 = pass r4;

    r0 = -r0;
    call _exp2q_simd;          /* clobbers r0-r5, keeps r7 */
    r2 = 0;
    r3 = 0x10000000;
    comp(r7, r2);
    if ne r0 = pass r3;        /* unity override */
    rts;
_compgain_simd.end:

/*----------------------------------------------------------------------
 * _comp_pair_blk — one block of COMPRESSOR for two channels.
 *
 * In (scalar registers, PEYEN still off):
 *   r4 = &paramsA[8]  r5 = &paramsB[8]   attq relq mkq parq thr slope halfk k2
 *   r6 = &envA        r7 = &envB         Q4.28, updated in place
 *   r8 = &sigA[32]    r9 = &sigB[32]     Q4.28, processed in place
 *
 * The sample body is instruction-for-instruction the scalar block
 * kernel's, with the release alpha reloaded from the park (r7 is spent on
 * the unity flag) and the gain display written through a fixed pointer so
 * the bench witness that proves the compressor ACTIVE still has something
 * to read.
 *--------------------------------------------------------------------*/
.global _comp_pair_blk;
_comp_pair_blk:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;

    i0 = _cmp_ptr;
    dm(i0, 1) = r4;
    dm(i0, 1) = r5;
    dm(i0, 1) = r6;
    dm(i0, 1) = r7;
    dm(i0, 1) = r8;
    dm(i0, 1) = r9;

#if DSP4_SIMD_NEGCTL
    /* NEGATIVE CONTROL. Channel B is gathered from channel A's pointers,
     * so the pair computes channel A TWICE -- which is precisely the fault
     * the self-test exists to catch and the one an identical-data test
     * cannot see. A build with this set must FAIL the diff, or the diff
     * proves nothing. */
    r5 = r4;
    r7 = r6;
    r9 = r8;
#endif

    /* ---- gather: parameters, envelope, signal ---- */
    i0 = r4; i1 = r5; i2 = _cmp_par;
    lcntr = 8, do .cpb_gp until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .cpb_gp: dm(i2, 1) = r0;

    i0 = r6; i1 = r7; i2 = _cmp_st;
    r0 = dm(i0, 0);
    dm(i2, 1) = r0;
    r0 = dm(i1, 0);
    dm(i2, 1) = r0;

    i0 = r8; i1 = r9; i2 = _cmp_sig;
    r1 = dm(_dsim_n);
    lcntr = r1, do .cpb_gx until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .cpb_gx: dm(i2, 1) = r0;

    /* &_cmp_par[2] -- the release alpha pair, reloaded per sample */
    r0 = _cmp_par;
    r1 = 2;
    r0 = r0 + r1;
    i3 = r0;
    i5 = _cmp_gn;

    /* ---- widen the datapath ---- */
    r0 = mode1;
    dm(_dsim_mode1) = r0;
    bit set mode1 0x00200000;      /* PEYEN */
    nop;
    nop;

    i1 = _cmp_par;
    r6  = dm(i1, 2);               /* attq  */
    r0  = dm(i1, 2);               /* relq  -- read per sample via i3 */
    r12 = dm(i1, 2);               /* mkq   */
    r15 = dm(i1, 2);               /* parq  */
    r8  = dm(i1, 2);               /* thr   */
    r9  = dm(i1, 2);               /* slope */
    r10 = dm(i1, 2);               /* halfk */
    r11 = dm(i1, 2);               /* k2    */
    i1 = _cmp_st;
    r14 = dm(i1, 2);               /* envelope */

    i2 = _cmp_sig;
    i4 = _cmp_sig;
    r5 = dm(_dsim_n);              /* PEYEN is set: reads both words */
    lcntr = r5, do .cpb_lp until lce;
        r13 = dm(i2, 2);           /* dry */

        /* envelope: env += rns(alpha * (|x| - env), 31) */
        r0 = abs r13;
        r4 = r0 - r14;
        r5 = 0;
        r2 = r6;
        r3 = dm(i3, 0);
        comp(r4, r5);
        if le r2 = pass r3;        /* delta <= 0 -> release */
        mrf = r2 * r4 (ssi);
        r2 = 0x40000000;
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r5 = r2 or r3;
        r14 = r14 + r5;

        /* gain computer */
        r0 = r14;
        call _compgain_simd;
        dm(i5, 0) = r0;            /* display/witness */

        /* wet = dry * gain * makeup */
        r1 = r0;
        r0 = r13;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28_simd;
        r1 = r12;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28_simd;

        /* parallel: out = dry + par*(wet - dry) */
        r5 = r0 - r13;
        r4 = r15;
        mrf = r5 * r4 (ssi);
        r1 = 0x40000000;
        r2 = 1;
        mrf = mrf + r1 * r2 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -31;
        r2 = lshift r2 by 1;
        r1 = r1 or r2;
        r0 = r13 + r1;
        nop;
        nop;
    .cpb_lp: dm(i4, 2) = r0;

    i1 = _cmp_st;
    dm(i1, 2) = r14;               /* envelope back to the park */

    r0 = dm(_dsim_mode1);
    mode1 = r0;                    /* PEYEN down, IRPTEN as the caller had it */
    nop;
    nop;

    /* ---- scatter ---- */
    i2 = _cmp_sig;
    i0 = _cmp_ptr;
    r0 = dm(i0, 1);
    r1 = dm(i0, 1);
    r2 = dm(i0, 1);
    r3 = dm(i0, 1);
    r4 = dm(i0, 1);
    r5 = dm(i0, 1);
    i0 = r4; i1 = r5;
    r6 = dm(_dsim_n);
    lcntr = r6, do .cpb_sx until lce;
        r0 = dm(i2, 1);
        dm(i0, 1) = r0;
        r0 = dm(i2, 1);
    .cpb_sx: dm(i1, 1) = r0;

    i2 = _cmp_st;
    i0 = r2; i1 = r3;
    r0 = dm(i2, 1);
    dm(i0, 0) = r0;
    r0 = dm(i2, 1);
    dm(i1, 0) = r0;
    rts;
_comp_pair_blk.end:

/*----------------------------------------------------------------------
 * _gate_pair_blk — one block of GATE for two channels.
 *
 * In:
 *   r4 = &paramsA[5]  r5 = &paramsB[5]   attq relq thrq rngq hold
 *   r6 = &stateA[4]   r7 = &stateB[4]    env, gain, target, hold count
 *   r8 = &sigA[32]    r9 = &sigB[32]
 *
 * ONE STATED DEVIATION, and it is bounded. The scalar tests `env <= 0`
 * with a branch and skips log2 entirely; branch-free, log2 runs on both
 * channels and the result is forced to INT_MIN where the envelope is
 * zero, so the comparison against the threshold gives the same answer for
 * every threshold above INT_MIN in Q6.25 -- which is every threshold the
 * control surface can express, and every threshold above -1.02e9/2^25 *
 * 6.0206 = -183 dB. It is not a numeric change to any sample; it is a
 * guard against log2(0), and log2(0) is never allowed to reach the
 * comparison.
 *--------------------------------------------------------------------*/
.global _gate_pair_blk;
_gate_pair_blk:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;

    i0 = _gat_ptr;
    dm(i0, 1) = r4;
    dm(i0, 1) = r5;
    dm(i0, 1) = r6;
    dm(i0, 1) = r7;
    dm(i0, 1) = r8;
    dm(i0, 1) = r9;

#if DSP4_SIMD_NEGCTL
    r5 = r4;
    r7 = r6;
    r9 = r8;
#endif

    i0 = r4; i1 = r5; i2 = _gat_par;
    lcntr = 5, do .gpb_gp until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .gpb_gp: dm(i2, 1) = r0;

    i0 = r6; i1 = r7; i2 = _gat_st;
    lcntr = 4, do .gpb_gs until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .gpb_gs: dm(i2, 1) = r0;

    i0 = r8; i1 = r9; i2 = _gat_sig;
    r1 = dm(_dsim_n);
    lcntr = r1, do .gpb_gx until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .gpb_gx: dm(i2, 1) = r0;

    r0 = mode1;
    dm(_dsim_mode1) = r0;
    bit set mode1 0x00200000;      /* PEYEN */
    nop;
    nop;

    i1 = _gat_par;
    r6  = dm(i1, 2);               /* attq  */
    r7  = dm(i1, 2);               /* relq  */
    r8  = dm(i1, 2);               /* thrq  */
    r9  = dm(i1, 2);               /* rngq  */
    r15 = dm(i1, 2);               /* hold  */
    i1 = _gat_st;
    r10 = dm(i1, 2);               /* envelope   */
    r11 = dm(i1, 2);               /* gain       */
    r12 = dm(i1, 2);               /* gain target */
    r14 = dm(i1, 2);               /* hold count */

    i2 = _gat_sig;
    i4 = _gat_sig;
    r5 = dm(_dsim_n);              /* PEYEN is set: reads both words */
    lcntr = r5, do .gpb_lp until lce;
        r13 = dm(i2, 2);

        /* detector envelope */
        r0 = abs r13;
        r4 = r0 - r10;
        r5 = 0;
        r2 = r6;
        r3 = r7;
        comp(r4, r5);
        if le r2 = pass r3;
        mrf = r2 * r4 (ssi);
        r2 = 0x40000000;
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r5 = r2 or r3;
        r10 = r10 + r5;

        /* level, guarded against log2(0) */
        r0 = r10;
        call _log2q_simd;
        r1 = 0x80000000;
        r2 = 0;
        comp(r10, r2);
        if le r0 = pass r1;

        /* open / hold / close, all three arms predicated */
        r1 = r14 - 1;
        r2 = 0;
        comp(r1, r2);
        if le r12 = pass r9;       /* hold expired -> target = range */
        r2 = 0x10000000;
        comp(r0, r8);
        if ge r12 = pass r2;       /* open -> target = unity */
        comp(r0, r8);              /* re-issued: the conditional above
                                    * writes flags when it executes */
        if ge r1 = pass r15;       /* open -> reload the hold count */
        r14 = r1;

        /* one-pole gain smoother, same alphas */
        r4 = r12 - r11;
        r5 = 0;
        r2 = r6;
        r3 = r7;
        comp(r4, r5);
        if le r2 = pass r3;
        mrf = r2 * r4 (ssi);
        r2 = 0x40000000;
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r5 = r2 or r3;
        r11 = r11 + r5;

        r1 = r11;
        r0 = r13;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28_simd;
        nop;
        nop;
    .gpb_lp: dm(i4, 2) = r0;

    i1 = _gat_st;
    dm(i1, 2) = r10;
    dm(i1, 2) = r11;
    dm(i1, 2) = r12;
    dm(i1, 2) = r14;

    r0 = dm(_dsim_mode1);
    mode1 = r0;
    nop;
    nop;

    i2 = _gat_sig;
    i0 = _gat_ptr;
    r0 = dm(i0, 1);
    r1 = dm(i0, 1);
    r2 = dm(i0, 1);
    r3 = dm(i0, 1);
    r4 = dm(i0, 1);
    r5 = dm(i0, 1);
    i0 = r4; i1 = r5;
    r6 = dm(_dsim_n);
    lcntr = r6, do .gpb_sx until lce;
        r0 = dm(i2, 1);
        dm(i0, 1) = r0;
        r0 = dm(i2, 1);
    .gpb_sx: dm(i1, 1) = r0;

    i2 = _gat_st;
    i0 = r2; i1 = r3;
    lcntr = 4, do .gpb_ss until lce;
        r0 = dm(i2, 1);
        dm(i0, 1) = r0;
        r0 = dm(i2, 1);
    .gpb_ss: dm(i1, 1) = r0;
    rts;
_gate_pair_blk.end:

#if DSP4_DYN_TABLES
#error "DSP4_SIMD_DYN needs the POLYNOMIAL log2/exp2: a table lookup is a gather at two indices and the DAGs are shared. Build with DSP4_DYN_TABLES=0."
#endif

#endif /* DSP4_SIMD_DYN */
