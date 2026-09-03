/*======================================================================
 * bqe_verify.asm — the ROUND-ONCE cascade kernel against fixed_ref, ON
 * THE PART, over the DEFS curve set.
 *
 * RIG C (2026-09-02) measured the round-once arm on ZEROED coefficient
 * banks. That is sound for timing and proves nothing about the
 * arithmetic, and its bit-identity claim was measured on the PYTHON
 * model (tools/dsp/roundonce_noise.py), not on the asm. This is the bar
 * that closes that gap, and it is the gate for landing the deletion.
 *
 * WHAT IT RUNS. tools/dsp/gen_bqe_vectors.py emits BQEV_NCAS four-stage
 * cascades -- the named worst cases from the state-bound work plus a
 * stratified sample of the DEFS design space -- and BQEV_NLVL drive
 * levels of BQEV_NBLK consecutive blocks. For every SIMD PAIR of
 * cascades, at every level, over every block, BOTH kernels run over
 * byte-identical words with their own state:
 *
 *   arm A   _bq_fx_cascade_simd   the graph's kernel
 *   arm B   _bqe_cascade_simd     round-once: per-stage SATURATE deleted,
 *                                 error feedback KEPT
 *
 * and the two output blocks are diffed on-chip.
 *
 * THREE VERDICTS, AND THE THIRD IS WHY THIS IS NOT AN ASM-VS-ASM BAR.
 * Two asm arms agreeing proves they agree; it does not prove either one
 * is the ruled arithmetic -- the same gap dsp4_bq_verify.py was written
 * to close for the fused cascade. So each arm's whole output stream is
 * reduced to an ORDER-SENSITIVE hash and a running sum, and the host
 * recomputes both from fixed_ref over the same vectors. Full coverage
 * for two words off the link instead of eighteen thousand.
 *
 *   hash/sum A   vs fixed_ref.biquad          (the contract)
 *   hash/sum B   vs the round-once model      (saturate deleted)
 *   ndiff        vs the model's own A-vs-B prediction
 *
 * THE DIVERGENCE BITMAP IS THE TWO-SIDED CONTROL. A bar that only
 * asserted "zero differences" would pass on a rig that never drove
 * anything hard enough to saturate -- which is exactly the trap the
 * zeroed-bank ladder fell into. The host predicts WHICH (cascade, level)
 * cells diverge; the part sets a bit for each cell it saw diverge, and
 * the two bitmaps must match exactly. On this set 29 of 576 cells
 * diverge, all of them hot cascades at 0 dBFS, so a kernel that silently
 * saturated anyway would fail as loudly as one that wrapped everywhere.
 *
 * Registers: every loop counter lives in DM. The callees are the
 * cascades and biquad_fx.asm's header lists all sixteen registers as
 * used -- the same reason bq_shootout.asm keeps its rep counter in
 * memory, and the same failure (a counter destroyed by the callee, a
 * loop that never ends, the parameter link starved behind it) if it did
 * not. The outer three loops are counter-and-jump rather than hardware
 * loops for the loop STACK's sake: the cascades nest two of their own,
 * and six is all there is.
 *
 * Debug only: DSP4_BQE_VERIFY. Never in a shipping image.
 *====================================================================*/

#include "dsp_block.h"

#if DSP4_BQE_VERIFY

.section/dm seg_dmda;

#include "bqe_vectors.h"

.global _bqev_magic;    .var _bqev_magic  = 0xD5B4E001;
.global _bqev_done;     .var _bqev_done   = 0;
.global _bqev_ncas;     .var _bqev_ncas   = BQEV_NCAS;
.global _bqev_nstage;   .var _bqev_nstage = BQEV_NSTAGE;
.global _bqev_nlvl;     .var _bqev_nlvl   = BQEV_NLVL;
.global _bqev_nblk;     .var _bqev_nblk   = BQEV_NBLK;
.global _bqev_blk;      .var _bqev_blk    = DSP4_BLOCK_SIZE;
.global _bqev_bmw;      .var _bqev_bmw    = BQEV_BMWORDS;
/* Which arithmetic arm A actually IS in this image -- read back, not
 * assumed, so a bar run against the wrong build cannot be scored as the
 * right one. */
.global _bqev_ro;       .var _bqev_ro     = DSP4_BQ_ROUNDONCE;

.global _bqev_nwords;   .var _bqev_nwords = 0;
.global _bqev_ndiff;    .var _bqev_ndiff  = 0;
.global _bqev_maxdiff;  .var _bqev_maxdiff = 0;
.global _bqev_first;    .var _bqev_first  = -1;
.global _bqev_hash_a;   .var _bqev_hash_a = 0;
.global _bqev_sum_a;    .var _bqev_sum_a  = 0;
.global _bqev_hash_b;   .var _bqev_hash_b = 0;
.global _bqev_sum_b;    .var _bqev_sum_b  = 0;
.global _bqev_bmap;     .var _bqev_bmap[BQEV_BMWORDS];

/* Working buffers. The coefficients are gathered into an INTERLEAVED
 * pair copy because that is the layout both SIMD kernels consume; the
 * two arms share it and hold their own state and their own signal. */
/* + 2 with the guard: one header word per strip, in front of the
 * interleaved coefficients. Both arms consume it -- the graph's kernel
 * because that is its contract, _bqe_cascade_simd because the rig skips
 * it -- so the two arms still read byte-identical coefficients, which is
 * the whole point of a shared buffer. H is zero here: the bar's job is
 * the ARITHMETIC, and the guard's own numbers are bq_h_load.py's. */
.var _bqev_ci[BQEV_NSTAGE * 10 + 2 * DSP4_BQ_HDR];
.var _bqev_sa[BQEV_NSTAGE * 12];
.var _bqev_sb[BQEV_NSTAGE * 12];
.var _bqev_ga[2 * DSP4_BLOCK_SIZE];
.var _bqev_gb[2 * DSP4_BLOCK_SIZE];

.var _bqev_p;        /* pair index                                    */
.var _bqev_l;        /* level index                                   */
.var _bqev_k;        /* block index                                   */
.var _bqev_idx;      /* running linear output-word index              */
.var _bqev_ctp;      /* -> cascade 2p's coefficients in _bqev_ctab    */
.var _bqev_stp;      /* -> this level's stimulus                      */
.var _bqev_da;       /* channel A diverged in this (pair, level)?     */
.var _bqev_db;       /* channel B ditto                               */
.var _bqev_bfirst;   /* lowest differing index within one block       */

.section/pm seg_pmco;
.extern _bq_fx_cascade_simd;
.extern _bqe_cascade_simd;

.global _bqev_selftest;
_bqev_selftest:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0; l6 = 0; l7 = 0;

    r0 = 0;
    dm(_bqev_ndiff)   = r0;
    dm(_bqev_maxdiff) = r0;
    dm(_bqev_hash_a)  = r0;
    dm(_bqev_sum_a)   = r0;
    dm(_bqev_hash_b)  = r0;
    dm(_bqev_sum_b)   = r0;
    dm(_bqev_nwords)  = r0;
    dm(_bqev_idx)     = r0;
    dm(_bqev_p)       = r0;
    r1 = -1;
    dm(_bqev_first)   = r1;
    i4 = _bqev_bmap;
    lcntr = BQEV_BMWORDS, do .bqev_cbm until lce;
    .bqev_cbm: dm(i4, 1) = r0;
    r0 = _bqev_ctab;
    dm(_bqev_ctp) = r0;

/*----------------------------------------------------------------------
 * for each SIMD pair of cascades
 *--------------------------------------------------------------------*/
.bqev_pair:
    /* ---- gather the pair's coefficients into the interleaved copy ---- */
    r0 = dm(_bqev_ctp);
    i4 = r0;                                /* cascade 2p   */
    r1 = BQEV_NSTAGE * 5;
    r0 = r0 + r1;
    i5 = r0;                                /* cascade 2p+1 */
    i6 = _bqev_ci;
#if DSP4_BQ_GUARD
    r0 = 0;
    dm(i6, 1) = r0;                         /* H, strip A */
    dm(i6, 1) = r0;                         /* H, strip B */
#endif
    lcntr = BQEV_NSTAGE * 5, do .bqev_gc until lce;
        r0 = dm(i4, 1);
        dm(i6, 1) = r0;
        r0 = dm(i5, 1);
    .bqev_gc: dm(i6, 1) = r0;

    r0 = 0;
    dm(_bqev_l) = r0;

/*----------------------------------------------------------------------
 * for each drive level: fresh state on BOTH arms, then the blocks
 *--------------------------------------------------------------------*/
.bqev_level:
    i4 = _bqev_sa;
    i5 = _bqev_sb;
    r0 = 0;
    lcntr = BQEV_NSTAGE * 12, do .bqev_zs until lce;
        dm(i4, 1) = r0;
    .bqev_zs: dm(i5, 1) = r0;
    dm(_bqev_da) = r0;
    dm(_bqev_db) = r0;
    dm(_bqev_k)  = r0;

    /* this level's stimulus base */
    r0 = dm(_bqev_l);
    r1 = BQEV_NBLK * DSP4_BLOCK_SIZE;
    r0 = r0 * r1 (ssi);
    r1 = _bqev_stim;
    r0 = r0 + r1;
    dm(_bqev_stp) = r0;

/*----------------------------------------------------------------------
 * for each block
 *--------------------------------------------------------------------*/
.bqev_block:
    /* ---- both arms get the same stimulus, in both channels ---- */
    r0 = dm(_bqev_stp);
    i4 = r0;
    i5 = _bqev_ga;
    i6 = _bqev_gb;
    lcntr = DSP4_BLOCK_SIZE, do .bqev_fill until lce;
        r0 = dm(i4, 1);
        dm(i5, 1) = r0;
        dm(i6, 1) = r0;
        dm(i5, 1) = r0;
    .bqev_fill: dm(i6, 1) = r0;
    r0 = dm(_bqev_stp);
    r1 = DSP4_BLOCK_SIZE;
    r0 = r0 + r1;
    dm(_bqev_stp) = r0;

    /* ---- arm A: the graph's kernel ---- */
    i0 = _bqev_ci;
    i1 = _bqev_sa;
    i2 = _bqev_ga;
    r4 = BQEV_NSTAGE;
    call _bq_fx_cascade_simd;

    /* ---- arm B: round-once, saturate deleted, feedback kept ---- */
    i0 = _bqev_ci;
    i1 = _bqev_sb;
    i2 = _bqev_gb;
    r4 = BQEV_NSTAGE;
    call _bqe_cascade_simd;

    /*------------------------------------------------------------------
     * diff, BACKWARDS. bq_selftest.asm's reason: a conditional move that
     * fires on every difference leaves the LAST index it saw, so scanned
     * downwards it leaves the LOWEST -- the first differing word -- and
     * no branch is needed inside the loop. The block is interleaved, so
     * descending the pair means the ODD word (channel B of the pair,
     * i.e. cascade 2p+1) then the EVEN one.
     *----------------------------------------------------------------*/
    r0 = _bqev_ga;
    r1 = 2 * DSP4_BLOCK_SIZE - 1;
    r0 = r0 + r1;
    i4 = r0;
    r0 = _bqev_gb;
    r0 = r0 + r1;
    i5 = r0;
    r12 = dm(_bqev_ndiff);
    r13 = dm(_bqev_maxdiff);
    r14 = -1;                       /* lowest differing index THIS block */
    r15 = dm(_bqev_idx);
    r15 = r15 + r1;                 /* absolute index of the last word   */
    r10 = dm(_bqev_da);
    r11 = dm(_bqev_db);
    r3 = 0;
    lcntr = DSP4_BLOCK_SIZE, do .bqev_cmp until lce;
        /* odd word: cascade 2p+1 */
        r0 = dm(i4, -1);
        r1 = dm(i5, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r3);
        if ne r11 = r11 + 1;
        comp(r2, r13);
        if gt r13 = r2;
        r15 = r15 - 1;
        /* even word: cascade 2p */
        r0 = dm(i4, -1);
        r1 = dm(i5, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r3);
        if ne r10 = r10 + 1;
        comp(r2, r13);
        if gt r13 = r2;
    .bqev_cmp: r15 = r15 - 1;
    dm(_bqev_ndiff)   = r12;
    dm(_bqev_maxdiff) = r13;
    dm(_bqev_da)      = r10;
    dm(_bqev_db)      = r11;
    dm(_bqev_bfirst)  = r14;

    /* first differing index over the WHOLE run: keep the earliest */
    r0 = dm(_bqev_first);
    r1 = -1;
    comp(r0, r1);
    if ne jump (pc, .bqev_havefirst);
    r0 = dm(_bqev_bfirst);
    dm(_bqev_first) = r0;
.bqev_havefirst:

    /*------------------------------------------------------------------
     * hash both arms, ASCENDING, in the order the host reproduces:
     * (pair, level, block, word) with the pair interleaved.
     * h = rot(h, 1) xor w, and a plain 32-bit sum beside it -- the
     * rotate is what makes it order-sensitive, and the sum is what
     * catches a rotate that is quietly a shift.
     *----------------------------------------------------------------*/
    i4 = _bqev_ga;
    r4 = dm(_bqev_hash_a);
    r5 = dm(_bqev_sum_a);
    lcntr = 2 * DSP4_BLOCK_SIZE, do .bqev_ha until lce;
        r0 = dm(i4, 1);
        r1 = lshift r4 by 1;
        r2 = lshift r4 by -31;
        r1 = r1 or r2;
        r4 = r1 xor r0;
    .bqev_ha: r5 = r5 + r0;
    dm(_bqev_hash_a) = r4;
    dm(_bqev_sum_a)  = r5;

    i4 = _bqev_gb;
    r4 = dm(_bqev_hash_b);
    r5 = dm(_bqev_sum_b);
    lcntr = 2 * DSP4_BLOCK_SIZE, do .bqev_hb until lce;
        r0 = dm(i4, 1);
        r1 = lshift r4 by 1;
        r2 = lshift r4 by -31;
        r1 = r1 or r2;
        r4 = r1 xor r0;
    .bqev_hb: r5 = r5 + r0;
    dm(_bqev_hash_b) = r4;
    dm(_bqev_sum_b)  = r5;

    r0 = dm(_bqev_idx);
    r1 = 2 * DSP4_BLOCK_SIZE;
    r0 = r0 + r1;
    dm(_bqev_idx)    = r0;
    dm(_bqev_nwords) = r0;

    /* ---- next block ---- */
    r0 = dm(_bqev_k);
    r1 = 1;
    r0 = r0 + r1;
    dm(_bqev_k) = r0;
    r1 = BQEV_NBLK;
    comp(r0, r1);
    if lt jump (pc, .bqev_block);

    /*------------------------------------------------------------------
     * end of level: post the two divergence bits for this (pair, level).
     * Cell index is cascade * NLVL + level, cascade = 2p and 2p+1.
     *----------------------------------------------------------------*/
    r0 = dm(_bqev_p);
    r1 = 2;
    r0 = r0 * r1 (ssi);             /* cascade 2p */
    r1 = BQEV_NLVL;
    r0 = r0 * r1 (ssi);
    r1 = dm(_bqev_l);
    r0 = r0 + r1;                   /* cell index for channel A */
    r6 = dm(_bqev_da);
    call .bqev_setbit;
    r1 = BQEV_NLVL;
    r0 = r0 + r1;                   /* cell index for channel B */
    r6 = dm(_bqev_db);
    call .bqev_setbit;

    /* ---- next level ---- */
    r0 = dm(_bqev_l);
    r1 = 1;
    r0 = r0 + r1;
    dm(_bqev_l) = r0;
    r1 = BQEV_NLVL;
    comp(r0, r1);
    if lt jump (pc, .bqev_level);

    /* ---- next pair ---- */
    r0 = dm(_bqev_ctp);
    r1 = 2 * BQEV_NSTAGE * 5;
    r0 = r0 + r1;
    dm(_bqev_ctp) = r0;
    r0 = dm(_bqev_p);
    r1 = 1;
    r0 = r0 + r1;
    dm(_bqev_p) = r0;
    r1 = BQEV_NCAS / 2;
    comp(r0, r1);
    if lt jump (pc, .bqev_pair);

    r0 = 1;
    dm(_bqev_done) = r0;
    rts;

/* set bitmap bit r0 if r6 != 0; clobbers r1, r2, r7, i4 */
.bqev_setbit:
    r1 = 0;
    comp(r6, r1);
    if eq rts;
    r1 = lshift r0 by -5;           /* word index  */
    r2 = _bqev_bmap;
    r1 = r1 + r2;
    i4 = r1;
    r2 = 31;
    r7 = r0 and r2;                 /* bit index   */
    r2 = 1;
    r2 = lshift r2 by r7;
    r1 = dm(i4, 0);
    r1 = r1 or r2;
    dm(i4, 0) = r1;
    rts;
_bqev_selftest.end:

#endif /* DSP4_BQE_VERIFY */
