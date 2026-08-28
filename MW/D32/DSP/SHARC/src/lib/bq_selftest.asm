/*======================================================================
 * bq_selftest.asm — is _bq_fx_cascade_blk the fault, or is the wrapper?
 *
 * Runs BOTH cascades on byte-identical data inside the part and diffs
 * them. That separates the routine from the node wrapper by construction:
 * a match proves the block routine and moves the fault to the wrapper; a
 * mismatch localises it inside the routine.
 *
 * Two deliberate choices, from the corrected suspect order:
 *
 *  - TWO STAGES WITH DIFFERENT COEFFICIENTS (1 kHz LPF Q0.707 then 300 Hz
 *    HPF Q2). Equal stages would hide a stage-pointer fault, and unity
 *    stages hide everything -- with unity coefficients y = x and the
 *    stored state contributes nothing at all, which is why `both_unity`
 *    passing at 0 LSB never exonerated the state handling.
 *  - TWO CONSECUTIVE BLOCKS. Block 1 is an impulse, block 2 is silence,
 *    so every sample of block 2 is pure feedback tail. Block 1 matching
 *    while block 2 diverges is block-boundary persistence; both diverging
 *    is in-block state.
 *
 * Debug only: DSP4_BQ_SELFTEST. Not built into any shipping image.
 *====================================================================*/

#include "dsp_block.h"

#if DSP4_BQ_SELFTEST

.section/dm seg_dmda;

/* [b0, n1, n2, c1, c2] per stage, Q4.28 offset form */
.global _bqst_coeffs;
.var _bqst_coeffs[10] =
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,  /* LPF 1k   */
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63;  /* HPF 300  */




.global _bqst_st_ref;   .var _bqst_st_ref[12];
.global _bqst_st_blk;   .var _bqst_st_blk[12];
/* Two consecutive blocks of stimulus and the two results. Retired once,
 * when the block cascade had been proved and the buffers were wanted for
 * the pairing test; back because DSP4_STRIP_FUSED replaces the block
 * cascade with a different routine (the error feedback stays in MRF
 * across samples instead of being taken apart and pushed back), and a
 * proof of the routine it replaced is not a proof of this one. */
.global _bqst_x;        .var _bqst_x[64];
.global _bqst_ref;      .var _bqst_ref[64];
.global _bqst_blk;      .var _bqst_blk[64];
.global _bqst_maxdiff;  .var _bqst_maxdiff = 0;
.global _bqst_ndiff;    .var _bqst_ndiff = 0;
.global _bqst_first;    .var _bqst_first = -1;
.global _bqst_done;     .var _bqst_done = 0;

/* ---- SIMD (PEy) feasibility ----------------------------------------
 * The capacity arithmetic says 32 strips cannot fit one 21564 single-issue
 * even at one instruction per cycle with no stalls, so whether the second
 * compute unit can be driven decides the whole question. This asks the
 * PART rather than the manual: enable PEYEN, do arithmetic, and see
 * whether the PEy half of each pair came back. */
.global _simdst_in;     .var _simdst_in[4] =
    0x11111111, 0x22222222, 0x33333333, 0x44444444;
.global _simdst_out;    .var _simdst_out[4] = 0, 0, 0, 0;
.global _simdst_mode1;  .var _simdst_mode1 = 0;

#if DSP4_SIMD_PROBE
/* Two strips' worth of independent data, and the interleaved copy the
 * SIMD cascade consumes. Coefficients DIFFER between the two strips --
 * identical strips would hide a PEy that was quietly reading PEx's
 * operands, which is precisely what this has to rule out. */
.global _sq_cA;   .var _sq_cA[10] =
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63;
.global _sq_cB;   .var _sq_cB[10] =
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63,
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC;
.global _sq_sA;   .var _sq_sA[12];
.global _sq_sB;   .var _sq_sB[12];
.global _sq_xA;   .var _sq_xA[32];
.global _sq_xB;   .var _sq_xB[32];
.global _sq_cyc_scalar; .var _sq_cyc_scalar = 0;
.global _sq_cyc_simd;   .var _sq_cyc_simd = 0;
.global _sq_ndiff;      .var _sq_ndiff = 0;
.global _sq_raw;        .var _sq_raw[5] = 0, 0, 0, 0, 0;  /* s0 s1 m0 m1 tperiod */
/* Copies for the PAIRING wrapper, which does its own interleave and
 * de-interleave -- proving _bq_fx_cascade_simd on pre-interleaved data is
 * not the same as proving _bq_pair_blk on the layout the graph actually
 * has. */
.global _sq_pA;   .var _sq_pA[32];
.global _sq_pB;   .var _sq_pB[32];
.global _sq_psA;  .var _sq_psA[12];
.global _sq_psB;  .var _sq_psB[12];
.global _sq_pdiff; .var _sq_pdiff = 0;
#endif

.section/pm seg_pmco;
.extern _bq_fx_cascade_N;
.extern _bq_fx_cascade_blk;

.global _bq_selftest;
_bq_selftest:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    l3 = 0;
    l4 = 0;
    l5 = 0;

    /* ---- block cascade vs the per-sample reference -------------------
     * Both routines run on byte-identical data inside the part and the
     * results are diffed, which separates the routine from every node
     * wrapper by construction. Under DSP4_STRIP_FUSED the block routine
     * is the FUSED one, so this is the acceptance for strip fusion's
     * biggest single change.
     *
     * Two stages with DIFFERENT coefficients (1 kHz LPF Q0.707 then
     * 300 Hz HPF Q2) -- equal stages would hide a stage-pointer fault,
     * and unity stages hide everything, because with unity coefficients
     * y = x and the stored state contributes nothing at all.
     *
     * Two CONSECUTIVE blocks: block 1 an impulse, block 2 silence, so
     * every sample of block 2 is pure feedback tail. Block 1 matching
     * while block 2 diverges is block-boundary persistence -- which is
     * exactly what the fused form changes, since it carries the error
     * feedback in MRF and only writes it out at the end of a stage.
     * ------------------------------------------------------------------ */
    i3 = _bqst_x;
    i4 = _bqst_ref;
    r0 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .bqst_z until lce;
        dm(i3, 1) = r0;
    .bqst_z: dm(i4, 1) = r0;
    r0 = 0x08000000;                /* impulse at sample 0, -6 dBFS */
    dm(_bqst_x) = r0;

    i3 = _bqst_st_ref;
    i4 = _bqst_st_blk;
    r0 = 0;
    lcntr = 12, do .bqst_zs until lce;
        dm(i3, 1) = r0;
    .bqst_zs: dm(i4, 1) = r0;

    /* reference: the per-sample cascade, one sample at a time */
    i3 = _bqst_x;
    i4 = _bqst_ref;
    lcntr = 2*DSP4_BLOCK_SIZE, do .bqst_rl until lce;
        r0 = dm(i3, 1);
        i0 = _bqst_coeffs;
        i1 = _bqst_st_ref;
        r4 = 2;
        call _bq_fx_cascade_N;
        /* A DO loop's last three instructions may not be a branch or a
         * call, so the call gets padded away from the loop end. Same
         * idiom as the generated dynamics kernels. */
        nop;
        nop;
    .bqst_rl: dm(i4, 1) = r0;

    /* the block form works IN PLACE, so it gets its own copy */
    i3 = _bqst_x;
    i4 = _bqst_blk;
    lcntr = 2*DSP4_BLOCK_SIZE, do .bqst_cp until lce;
        r0 = dm(i3, 1);
    .bqst_cp: dm(i4, 1) = r0;

    i0 = _bqst_coeffs;
    i1 = _bqst_st_blk;
    i2 = _bqst_blk;
    r4 = 2;
    call _bq_fx_cascade_blk;
    i0 = _bqst_coeffs;
    i1 = _bqst_st_blk;
    r0 = _bqst_blk;
    r1 = DSP4_BLOCK_SIZE;
    r0 = r0 + r1;
    i2 = r0;                        /* the second block, same state */
    r4 = 2;
    call _bq_fx_cascade_blk;

    /* Diff: count, worst magnitude, and where it FIRST goes wrong.
     *
     * Walked BACKWARDS on purpose. "First differing index" needs two
     * conditions in the forward direction (differs AND nothing recorded
     * yet), and the second one cannot be tested without a branch -- and a
     * branch inside a hardware loop, especially one landing on the loop's
     * own end instruction, is exactly the hazard that hung the first cut
     * of this test on the part. Backwards, the LAST index written is the
     * lowest differing one, which is the same answer from one
     * conditional move. */
    r0 = _bqst_ref;
    r1 = 63;
    r0 = r0 + r1;
    i3 = r0;
    r0 = _bqst_blk;
    r0 = r0 + r1;
    i4 = r0;
    r12 = 0;                        /* ndiff   */
    r13 = 0;                        /* maxdiff */
    r14 = -1;                       /* first differing index */
    r15 = 63;                       /* index, counting down  */
    r3 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .bqst_cmp until lce;
        r0 = dm(i3, -1);
        r1 = dm(i4, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
    .bqst_cmp: r15 = r15 - 1;
    dm(_bqst_ndiff) = r12;
    dm(_bqst_maxdiff) = r13;
    dm(_bqst_first) = r14;

    l0 = 0;
    l1 = 0;
    l2 = 0;
    l3 = 0;
    l4 = 0;
    l5 = 0;

#if DSP4_SIMD_PROBE
    /* ---- SIMD vs scalar: same work, measured, and checked ---- */
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;

    /* stimulus: an impulse for A, a different one for B */
    i3 = _sq_xA; i4 = _sq_xB; r0 = 0;
    lcntr = DSP4_BLOCK_SIZE, do .sq_z until lce;
        dm(i3, 1) = r0;
    .sq_z: dm(i4, 1) = r0;
    r0 = 0x08000000; dm(_sq_xA) = r0;
    r0 = 0x04000000; dm(_sq_xB) = r0;

    /* zero all state */
    i3 = _sq_sA; i4 = _sq_sB; r0 = 0;
    lcntr = 12, do .sq_zs until lce;
        dm(i3, 1) = r0;
    .sq_zs: dm(i4, 1) = r0;

    /* ---- scalar: two strips, one after the other ---- */
    /* Timed over MANY iterations against the 1 kHz diag tick. One pass is
     * a few thousand cycles, far below a tick, so a single pass cannot be
     * timed this way -- and TCOUNT read back values inconsistent with a
     * TPERIOD reload, so it is not the instrument to use here. 4000
     * iterations is about 32 ms, which the tick resolves to ~3 %. */
    .extern _diag_ticks;
    r12 = dm(_diag_ticks);
    dm(_sq_raw + 0) = r12;
    lcntr = 2, do .sq_sloop until lce;
        i0 = _sq_cA; i1 = _sq_sA; i2 = _sq_xA; r4 = 2;
        call _bq_fx_cascade_blk;
        i0 = _sq_cB; i1 = _sq_sB; i2 = _sq_xB; r4 = 2;
        call _bq_fx_cascade_blk;
    .sq_sloop: nop;
    r13 = dm(_diag_ticks);
    dm(_sq_raw + 1) = r13;

    /* ---- SIMD: the same two strips together, THROUGH THE PAIRING
     * WRAPPER, so the interleave and de-interleave are inside the timed
     * span. Timing the pre-interleaved cascade would have flattered it by
     * assuming away the very overhead that decides whether pairing is
     * worth doing. ---- */
    r12 = dm(_diag_ticks);
    dm(_sq_raw + 2) = r12;
    lcntr = 2, do .sq_mloop until lce;
        r8 = _sq_cA;  r9 = _sq_psA;  r10 = _sq_pA;
        r11 = _sq_cB; r12 = _sq_psB; r13 = _sq_pB;
        r4 = 2;
#if !DSP4_SKIP_PAIR
        call _bq_pair_blk;
#endif
    .sq_mloop: nop;
    r13 = dm(_diag_ticks);
    dm(_sq_raw + 3) = r13;

    /* ---- the PAIRING WRAPPER on the graph's own layout ---- */
    i3 = _sq_xA;   /* careful: _sq_xA now holds the SCALAR RESULT */
    l3 = 0; l4 = 0; l5 = 0;
    /* rebuild the stimulus into the pair buffers */
    i3 = _sq_pA; i4 = _sq_pB; r0 = 0;
    lcntr = DSP4_BLOCK_SIZE, do .sq_pz until lce;
        dm(i3, 1) = r0;
    .sq_pz: dm(i4, 1) = r0;
    r0 = 0x08000000; dm(_sq_pA) = r0;
    r0 = 0x04000000; dm(_sq_pB) = r0;
    i3 = _sq_psA; i4 = _sq_psB; r0 = 0;
    lcntr = 12, do .sq_pzs until lce;
        dm(i3, 1) = r0;
    .sq_pzs: dm(i4, 1) = r0;

    r8 = _sq_cA;  r9 = _sq_psA;  r10 = _sq_pA;
    r11 = _sq_cB; r12 = _sq_psB; r13 = _sq_pB;
    r4 = 2;
#if !DSP4_SKIP_PAIR
    call _bq_pair_blk;
#endif

    /* compare against the scalar results, both strips */
    i3 = _sq_pA; i4 = _sq_xA; i5 = _sq_pB; r14 = 0;
    lcntr = DSP4_BLOCK_SIZE, do .sq_pc until lce;
        r0 = dm(i3, 1);
        r1 = dm(i4, 1);
        r2 = r0 - r1;
        r2 = pass r2;
        if ne r14 = r14 + 1;
        r0 = dm(i5, 1);
        r1 = dm(_sq_xB);
    .sq_pc: nop;
    dm(_sq_pdiff) = r14;

    /* The pairing-wrapper comparison above is the real check now: it runs
     * on the layout the graph actually has and compares BOTH strips
     * against the scalar results. _sq_ndiff mirrors it. */
    dm(_sq_ndiff) = r14;
#endif

    /* ---- SIMD probe ---- */
    i3 = _simdst_in;
    i4 = _simdst_out;
    l3 = 0;
    l4 = 0;
    bit set mode1 0x00200000;   /* BITM_REGF_MODE1_PEYEN */
    nop;
    nop;
    r0 = dm(i3, 2);        /* PEx gets in[0], PEy should get in[1] */
    r1 = r0 + r0;
    dm(i4, 2) = r1;        /* should write BOTH out[0] and out[1] */
    r0 = dm(i3, 2);
    r1 = r0 + r0;
    dm(i4, 2) = r1;
    bit clr mode1 0x00200000;
    nop;
    nop;
    r0 = mode1;
    dm(_simdst_mode1) = r0;

    r0 = 1;
    dm(_bqst_done) = r0;
    rts;
_bq_selftest.end:

#endif
