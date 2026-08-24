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

#if DSP4_BQ_SELFTEST

.section/dm seg_dmda;

/* [b0, n1, n2, c1, c2] per stage, Q4.28 offset form */
.global _bqst_coeffs;
.var _bqst_coeffs[10] =
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,  /* LPF 1k   */
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63;  /* HPF 300  */

.global _bqst_in;       .var _bqst_in[64];
.global _bqst_ref;      .var _bqst_ref[64];
.global _bqst_blk;      .var _bqst_blk[64];
.global _bqst_st_ref;   .var _bqst_st_ref[12];
.global _bqst_st_blk;   .var _bqst_st_blk[12];
.global _bqst_maxdiff;  .var _bqst_maxdiff = 0;
.global _bqst_ndiff;    .var _bqst_ndiff = 0;
.global _bqst_first;    .var _bqst_first = -1;
.global _bqst_done;     .var _bqst_done = 0;

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

    /* ---- stimulus: impulse, then 63 samples of silence ---- */
    i3 = _bqst_in;
    r0 = 0;
    lcntr = 64, do .bqst_z until lce;
    .bqst_z: dm(i3, 1) = r0;
    r0 = 0x08000000;
    dm(_bqst_in) = r0;

    /* ---- both states start identically at zero ---- */
    i3 = _bqst_st_ref;
    r0 = 0;
    lcntr = 12, do .bqst_zr until lce;
    .bqst_zr: dm(i3, 1) = r0;
    i3 = _bqst_st_blk;
    r0 = 0;
    lcntr = 12, do .bqst_zb until lce;
    .bqst_zb: dm(i3, 1) = r0;

    /* ---- reference: the shipping per-sample routine, 64 samples ---- */
    i3 = _bqst_in;
    i4 = _bqst_ref;
    lcntr = 64, do .bqst_s until lce;
        r0 = dm(i3, 1);
        i0 = _bqst_coeffs;
        i1 = _bqst_st_ref;
        r4 = 2;
        call _bq_fx_cascade_N;
        dm(i4, 1) = r0;
    .bqst_s: nop;

    /* ---- block path: same stimulus, processed in place, two blocks ---- */
    i3 = _bqst_in;
    i4 = _bqst_blk;
    lcntr = 64, do .bqst_c until lce;
        r0 = dm(i3, 1);
    .bqst_c: dm(i4, 1) = r0;

    i0 = _bqst_coeffs;
    i1 = _bqst_st_blk;
    i2 = _bqst_blk;
    r4 = 2;
    call _bq_fx_cascade_blk;

    /* second block, SAME state -- this is the persistence half */
    i0 = _bqst_coeffs;
    i1 = _bqst_st_blk;
    i2 = _bqst_blk;
    m0 = 32;
    modify(i2, m0);
    r4 = 2;
    call _bq_fx_cascade_blk;

    /* ---- diff ---- */
    i3 = _bqst_blk;
    i4 = _bqst_ref;
    r12 = 0;                    /* max |diff|                     */
    r14 = 0;                    /* how many samples differ        */
    r13 = -1;                   /* index of the first that does   */
    r10 = 0;                    /* running index                  */
    lcntr = 64, do .bqst_d until lce;
        r0 = dm(i3, 1);
        r1 = dm(i4, 1);
        r2 = r0 - r1;
        r2 = abs r2;
        r3 = pass r2;
        if ne r14 = r14 + 1;
        r3 = pass r13;
        if ge jump (pc, .bqst_seen);   /* already recorded one */
        r3 = pass r2;
        if ne r13 = pass r10;   /* first differing index */
    .bqst_seen:
        comp(r2, r12);
        if gt r12 = pass r2;
        r10 = r10 + 1;
    .bqst_d: nop;

    dm(_bqst_maxdiff) = r12;
    dm(_bqst_ndiff) = r14;
    dm(_bqst_first) = r13;
    r0 = 1;
    dm(_bqst_done) = r0;
    rts;
_bq_selftest.end:

#endif
