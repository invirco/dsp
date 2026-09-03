/*======================================================================
 * bq_guard_test.asm — the HEADROOM GUARD, on the part.
 *
 * Two claims, one instrument, and both of them could fail.
 *
 *   1. THE SIZER IS THE MODEL. For each cascade the part runs
 *      lib/bq_headroom.asm end to end -- request, service to completion,
 *      poll -- and reports the H it wrote into the block's header word.
 *      The host compares it with tools/dsp/bq_h_load.py's H for the same
 *      quantised coefficients. A sizer that agreed with nothing would be
 *      a guard sized on nothing.
 *
 *   2. THE GUARD PREVENTS THE SIGN INVERSION. Each cascade is then run
 *      TWICE over the matched-sign drive that achieves |h|_1: once with
 *      the header the sizer wrote, and once with the header forced to 0,
 *      which is the kernel that landed on 2026-09-03. Both arms count
 *      the samples whose SIGN differs from a float64 run of the same
 *      de-quantised coefficients. Unguarded that count is non-zero on
 *      the hot cascades and the host knows which; guarded it must be
 *      zero on every one.
 *
 * BOTH ARMS ARE IN ONE IMAGE and neither is a rebuild, because the
 * header word is data: forcing it to zero is the whole of "turn the
 * guard off for this cascade". That also means the two arms cannot
 * differ in any way except the one being measured.
 *
 * THE REFERENCE IS FLOAT, NOT THE CONTRACT, and that matters here more
 * than anywhere else in this tree. On a cascade whose partial gain is
 * +33 dB the per-stage-saturating contract CLIPS internally: it stays
 * bounded, which is what it is for, but it is not correct, and scoring
 * the guard against it would penalise the guard for being the more
 * correct of the two. Against float the three arms separate the way the
 * argument says they should -- clipping preserves SIGN, wrapping
 * inverts it.
 *
 * Debug instrument. DSP4_BQG_VERIFY defaults 0 and it is never in a
 * shipping image.
 *
 * Infrastructure (hand-maintained); the vector table is generated.
 *======================================================================*/

#include "dsp_block.h"

#if DSP4_BQG_VERIFY

.section/dm seg_dmda;
#include "bqg_vectors.h"

.global _bqg_ncas;    .var _bqg_ncas  = BQG_NCAS;
.global _bqg_nsamp;   .var _bqg_nsamp = BQG_NSAMP;
.global _bqg_maxst;   .var _bqg_maxst = BQG_MAXST;
.global _bqg_done;    .var _bqg_done  = 0;
.global _bqg_fail;    .var _bqg_fail  = 0;   /* engine never finished */
.global _bqg_hgot;    .var _bqg_hgot[BQG_NCAS];  /* H the PART sized */
.global _bqg_fgd;     .var _bqg_fgd[BQG_NCAS];   /* inversions, guarded */
.global _bqg_fun;     .var _bqg_fun[BQG_NCAS];   /* inversions, unguarded */
/* ORDER-SENSITIVE HASHES of both arms' whole output streams, bqe_verify's
 * h = rot(h,1) xor w with a plain sum beside it. Counting sign inversions
 * proves the guard stops the wrap; it does not prove the guarded kernel
 * computes the RIGHT WORDS. The host recomputes these from the same model
 * that sized H, so 896 words of arithmetic come off the link as four. */
.global _bqg_hgd;     .var _bqg_hgd = 0;
.global _bqg_sgd;     .var _bqg_sgd = 0;
.global _bqg_hun;     .var _bqg_hun = 0;
.global _bqg_sun;     .var _bqg_sun = 0;
.var _bqg_hp;         /* &hash for this arm */
.var _bqg_sp;         /* &sum  for this arm */

.var _bqg_state[BQG_MAXST * 6];
.var _bqg_list[2];
.var _bqg_c;          /* cascade index */
.var _bqg_cf_p;       /* this cascade's coefficient block */
.var _bqg_stg_n;      /* this cascade's stage count */
.var _bqg_wct;        /* service passes, bounded -- _bq_hr_service
                       * clobbers the register file, so the loop counter
                       * cannot live in one */

.section/pm seg_pmco;
.extern _bq_hr_request_n;
.extern _bq_hr_service;
.extern _bq_hr_poll;
.extern _bq_fx_cascade_N;

/*----------------------------------------------------------------------
 * _bqg_run — one pass over the drive; r0 = sign inversions.
 *
 * The cascade kernel is the PER-SAMPLE one, and it advances i0/i1 past
 * the stages it used, so both are reloaded every sample. That is the
 * slow way to run a cascade and exactly the right way to run a bar: it
 * is the kernel a node body calls, unrolled by nothing, with no block
 * machinery between the vectors and the arithmetic.
 *--------------------------------------------------------------------*/
_bqg_run:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0;
    /* zero the state */
    i1 = _bqg_state;
    r0 = dm(_bqg_stg_n);
    r1 = r0 + r0;
    r2 = r1 + r1;
    r1 = r1 + r2;              /* 6 * stages */
    r0 = 0;
    lcntr = r1, do .bqg_zs until lce;
    .bqg_zs: dm(i1, 1) = r0;

    /* drive and sign vectors for this cascade. The offset is built by
     * ADDING, not by the multiplier: there is no Rn = Rx * Ry form
     * anywhere else in this tree and a bar is the wrong place to be the
     * first user of an instruction encoding. */
    r0 = dm(_bqg_c);
    r1 = BQG_NSAMP;
    r2 = 0;
    r0 = pass r0;
    if eq jump (pc, .bqg_o1);
    lcntr = r0, do .bqg_m1 until lce;
    .bqg_m1: r2 = r2 + r1;
.bqg_o1:
    i2 = _bqg_drv;
    m2 = r2;
    modify(i2, m2);
    i3 = _bqg_sgn;
    m3 = r2;
    modify(i3, m3);

    r14 = 0;                   /* the inversion count */
    lcntr = BQG_NSAMP, do .bqg_samp until lce;
        r15 = dm(i2, 1);       /* x */
        r13 = dm(i3, 1);       /* the float reference's sign bit */
        r0 = dm(_bqg_cf_p);
        i0 = r0;
        i1 = _bqg_state;
        r4 = dm(_bqg_stg_n);
        r0 = r15;
        call _bq_fx_cascade_N;
        /* hash and sum BEFORE the sign test, which consumes r0 */
        r1 = dm(_bqg_hp);
        i1 = r1;
        r2 = dm(i1, 0);
        r3 = lshift r2 by 1;
        r2 = lshift r2 by -31;
        r3 = r3 or r2;
        r3 = r3 xor r0;
        dm(i1, 0) = r3;
        r1 = dm(_bqg_sp);
        i1 = r1;
        r2 = dm(i1, 0);
        r2 = r2 + r0;
        dm(i1, 0) = r2;

        r0 = r0 xor r13;       /* sign bits differ -> negative */
        r0 = pass r0;
        if lt r14 = r14 + 1;
    .bqg_samp:
        nop;

    r0 = r14;
    rts;
_bqg_run.end:

/*----------------------------------------------------------------------
 * _bqg_selftest — the whole bar. Main-loop context, runs once.
 *--------------------------------------------------------------------*/
.global _bqg_selftest;
_bqg_selftest:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;
    r0 = 0;
    dm(_bqg_c) = r0;

.bqg_case:
    /* ---- this cascade's coefficient block and stage count ---- */
    r0 = dm(_bqg_c);
    r1 = BQG_MAXST * 5 + 1;
    r2 = 0;
    r0 = pass r0;
    if eq jump (pc, .bqg_o0);
    lcntr = r0, do .bqg_m0 until lce;
    .bqg_m0: r2 = r2 + r1;
.bqg_o0:
    i0 = _bqg_cf;
    m0 = r2;
    modify(i0, m0);
    r1 = i0;
    dm(_bqg_cf_p) = r1;
    i1 = _bqg_stg;
    m1 = r0;
    modify(i1, m1);
    r2 = dm(i1, 0);
    dm(_bqg_stg_n) = r2;

    /* ---- 1. SIZE IT. Header to zero first, so a stale value cannot be
     * mistaken for a computed one. ---- */
    r3 = 0;
    dm(i0, 0) = r3;
    i2 = _bqg_list;
    dm(i2, 1) = r1;            /* the block */
    dm(i2, 1) = r2;            /* stages   */
    i0 = _bqg_list;
    r4 = 1;
    call _bq_hr_request_n;
    r0 = pass r0;
    if eq jump (pc, .bqg_engfail);   /* the engine must be idle here */

    r0 = 0;
    dm(_bqg_wct) = r0;
.bqg_wait:
    call _bq_hr_service;
    r0 = dm(_bqg_cf_p);
    call _bq_hr_poll;
    r0 = pass r0;
    if ne jump (pc, .bqg_sized);
    r0 = dm(_bqg_wct);
    r0 = r0 + 1;
    dm(_bqg_wct) = r0;
    r1 = 100000;               /* far past 1024 samples x 32 stages */
    comp(r0, r1);
    if lt jump (pc, .bqg_wait);
    jump (pc, .bqg_engfail);

.bqg_sized:
    r0 = dm(_bqg_cf_p);
    i0 = r0;
    r13 = dm(i0, 0);           /* H, as the part sized it */
    i1 = _bqg_hgot;
    r0 = dm(_bqg_c);
    m1 = r0;
    modify(i1, m1);
    dm(i1, 0) = r13;

    /* ---- 2. GUARDED: the header the sizer wrote ---- */
    r0 = _bqg_hgd;
    dm(_bqg_hp) = r0;
    r0 = _bqg_sgd;
    dm(_bqg_sp) = r0;
    call _bqg_run;
    i1 = _bqg_fgd;
    r1 = dm(_bqg_c);
    m1 = r1;
    modify(i1, m1);
    dm(i1, 0) = r0;

    /* ---- 3. UNGUARDED: the same kernel with H forced to 0, which is
     * the cascade that landed on 2026-09-03 ---- */
    r0 = dm(_bqg_cf_p);
    i0 = r0;
    r1 = 0;
    dm(i0, 0) = r1;
    r0 = _bqg_hun;
    dm(_bqg_hp) = r0;
    r0 = _bqg_sun;
    dm(_bqg_sp) = r0;
    call _bqg_run;
    i1 = _bqg_fun;
    r1 = dm(_bqg_c);
    m1 = r1;
    modify(i1, m1);
    dm(i1, 0) = r0;

    /* leave the header as the sizer left it, so a reader of the image
     * sees what the part decided rather than what the last arm forced */
    r0 = dm(_bqg_cf_p);
    i0 = r0;
    i1 = _bqg_hgot;
    r1 = dm(_bqg_c);
    m1 = r1;
    modify(i1, m1);
    r2 = dm(i1, 0);
    dm(i0, 0) = r2;

    r0 = dm(_bqg_c);
    r0 = r0 + 1;
    dm(_bqg_c) = r0;
    r1 = BQG_NCAS;
    comp(r0, r1);
    if lt jump (pc, .bqg_case);

    r0 = 1;
    dm(_bqg_done) = r0;
    rts;

.bqg_engfail:
    r0 = dm(_bqg_c);
    r0 = r0 + 1;
    dm(_bqg_fail) = r0;        /* 1-based: which cascade stalled */
    r0 = 1;
    dm(_bqg_done) = r0;
    rts;
_bqg_selftest.end:

#endif /* DSP4_BQG_VERIFY */
