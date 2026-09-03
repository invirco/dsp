/*======================================================================
 * bq_shootout.asm — the biquad/gain round-once shootout rig.
 *
 * SPIKE ONLY. Standalone rig, never in a shipping image, no graph
 * integration, no contract edit. Guarded on DSP4_BQ_SHOOTOUT.
 *
 * THE QUESTION. PW's D5 amendment of 2026-09-02: "round once per strip
 * (gain path) and once per cascade output (biquads), not per stage."
 * Today's fixed cascade measures 12.58 c/band-sample paired at block 8,
 * and eleven of its nineteen inner-loop instructions ARE the numeric
 * contract -- the 64-bit extract, the branch-free saturate, the
 * error-feedback MAC.
 *
 * SIXTEEN RUNGS, same loop form, same iteration count, same 28-stage
 * bank, same block size, so what differs between them is ARITHMETIC:
 *
 *   0        NULL, the loop's own cost, subtracted
 *   1  2     _bq_fx_cascade_blk / _simd     today, per-stage    19 instr
 *   3  4     _bqf_cascade_blk   / _simd     RIG A2, float        8
 *  14 15     _bqe_cascade_blk   / _simd     RIG C, SATURATE     12
 *                                           deleted, FEEDBACK KEPT
 *   5  6     _bqc_cascade_blk   / _simd     RIG C, both deleted,12
 *                                           rounded
 *   7  8     _bqt_cascade_blk   / _simd     RIG C, both deleted,11
 *                                           truncating
 *   9 10 11  _gsh_gain_now / _r1 / _r1t     GAIN, today / round-once /
 *                                           round-once with the D20 tap
 *  12 13     _gsh_gain_now_nm / _r1_nm      the same, meter removed
 *
 * THE TWO DELETIONS ARE NOT ONE DELETION, and separating them is what
 * this rig is for. Rungs 14/15 delete only the per-stage SATURATE and
 * are bit-identical to the contract while nothing overflows; rungs 5-8
 * delete the ERROR FEEDBACK as well and cost 16 dB of LF response on the
 * shelf D5 was decided on. Both are twelve instructions.
 *
 * THE CYCLE NUMBER IS HALF THE ANSWER, and the other half is three
 * scripts: tools/dsp/bq_float_delta.py prices the float arm (0.52 dB on
 * an LF shelf), tools/dsp/bq_state_bound.py prices RIG C's wrap risk in
 * headroom bits, and tools/dsp/roundonce_noise.py turns those bits into
 * noise floor and response error. Write-up:
 * MW/D32/DSP/dsp4-roundonce-rigc-20260902.md.
 *
 * DF-II-T for the float arm, which is the right form for float and the
 * wrong one for fixed:
 *   y   = b0*x + w1
 *   w1' = b1*x - a1*y + w2
 *   w2' = b2*x - a2*y
 * Two state words per stage against the fixed form's six, and no
 * error-feedback word, because in float there is no rounding remainder
 * to carry.
 *======================================================================*/

#include "dsp_block.h"
#include "diag.h"

#if DSP4_BQ_SHOOTOUT

#define BQS_STAGES  28
#define BQS_RUNGS   18
#define BQS_REPS    3
#define BQS_ITERS   400

.section/dm seg_dmda;

.global _bqsh_done;    .var _bqsh_done  = 0;
.global _bqsh_magic;   .var _bqsh_magic = 0xD5B4B001;
.global _bqsh_iters;   .var _bqsh_iters = BQS_ITERS;
.global _bqsh_reps;    .var _bqsh_reps  = BQS_REPS;
.global _bqsh_rungs;   .var _bqsh_rungs = BQS_RUNGS;
.global _bqsh_stages;  .var _bqsh_stages = BQS_STAGES;
.global _bqsh_tper;    .var _bqsh_tper  = DIAG_TPERIOD;
.global _bqsh_blk;     .var _bqsh_blk   = DSP4_BLOCK_SIZE;
.global _bqsh_tick;    .var _bqsh_tick[BQS_RUNGS * BQS_REPS * 4];

/* THE LADDER'S OWN LOOP STATE LIVES IN DM, AND THAT IS NOT PARANOIA.
 * call_selftest.asm can hold its rep counter in r11 because its callees
 * are `nop`s and a bare `rts`. THESE callees are the cascades, and
 * _bq_fx_cascade_blk's header lists all sixteen registers as used --
 * r11 and r12 are its y1 and y2. A counter left in r11 is destroyed on
 * every rung, the rep loop never terminates, the ladder never sets
 * _bqsh_done and the parameter link starves behind it. That is exactly
 * what this rig did on its first run: BOOT_STAGE 5 clean, MAGIC clean,
 * and "cannot phase the parameter link" the moment CONFIG_COMMIT let the
 * main loop run. Same shape as the 2026-08-29 paired-cascade hang, which
 * was also a register the callee owned. */
.var _bqsh_rep;
.var _bqsh_tp;

/* ---- fixed-point arm -------------------------------------------------
 * The cascade's cost is coefficient-independent by construction -- the
 * instruction stream does not vary with the loaded words -- so a zeroed
 * bank measures the same path a configured filter would. */
.global _bqsh_fxc;   .var _bqsh_fxc[BQS_STAGES * 5];
.global _bqsh_fxs;   .var _bqsh_fxs[BQS_STAGES * 6];
.global _bqsh_fxsig; .var _bqsh_fxsig[DSP4_BLOCK_SIZE];
.global _bqsh_fxci;  .var _bqsh_fxci[BQS_STAGES * 10];
.global _bqsh_fxsi;  .var _bqsh_fxsi[BQS_STAGES * 12];
.global _bqsh_fxsigi;.var _bqsh_fxsigi[2 * DSP4_BLOCK_SIZE];

/* ---- float arm ------------------------------------------------------ */
.global _bqsh_flc;   .var _bqsh_flc[BQS_STAGES * 5];
.global _bqsh_fls;   .var _bqsh_fls[BQS_STAGES * 2];
.global _bqsh_flsig; .var _bqsh_flsig[DSP4_BLOCK_SIZE];
.global _bqsh_flci;  .var _bqsh_flci[BQS_STAGES * 10];
.global _bqsh_flsi;  .var _bqsh_flsi[BQS_STAGES * 4];
.global _bqsh_flsigi;.var _bqsh_flsigi[2 * DSP4_BLOCK_SIZE];

.var _bqf_mode1_save[2];

/* ---- RIG C arm: fixed-point round-once. FOUR state words per stage,
 * not six -- there is no error-feedback pair when the remainder is not
 * carried. ---- */
.global _bqsh_cfc;   .var _bqsh_cfc[BQS_STAGES * 5];
.global _bqsh_cfs;   .var _bqsh_cfs[BQS_STAGES * 4];
.global _bqsh_cfsig; .var _bqsh_cfsig[DSP4_BLOCK_SIZE];
.global _bqsh_cfci;  .var _bqsh_cfci[BQS_STAGES * 10];
.global _bqsh_cfsi;  .var _bqsh_cfsi[BQS_STAGES * 8];
.global _bqsh_cfsigi;.var _bqsh_cfsigi[2 * DSP4_BLOCK_SIZE];

.var _bqc_mode1_save[2];

/* ---- RIG C, THE GUARD: per-cascade headroom sized on |h|_1 ----
 * H is a CONTROL-RATE word -- computed once per coefficient swap from
 * the l1 norm of the cascade actually loaded (tools/dsp/bq_headroom_guard.py)
 * -- so nothing here is per-sample arithmetic. Both signs and the
 * saturation pattern are stored because under round-once exactly ONE
 * register (r15) is free in the sample loop, and the exit body needs
 * three invariants. Each is a PAIR: they are read from inside the PEYEN
 * region, where a direct-address access takes the word after the address
 * for PEy. */
.global _bqh_hm;    .var _bqh_hm[2]  = -2, -2;         /* -H */
.global _bqh_hp;    .var _bqh_hp[2]  =  2,  2;         /* +H */
.global _bqh_sat;   .var _bqh_sat[2] = 0x7FFFFFFF, 0x7FFFFFFF;

/* ---- RIG C gain arm. Every _gsh_* scratch word is a PAIR: it is
 * written from inside the PEYEN region, where a direct-address store
 * writes the word after the address as well. ---- */
.var _gsh_save[2];
.var _gsh_g[2];
.var _gsh_sq0[2];
.var _gsh_sq1[2];
.var _gsh_sq2[2];
.var _gsh_max[2];
.var _gsh_min[2];
.global _gsh_src;   .var _gsh_src[DSP4_BLOCK_SIZE];
.global _gsh_chain; .var _gsh_chain[DSP4_BLOCK_SIZE];
.global _gsh_tap;   .var _gsh_tap[DSP4_BLOCK_SIZE];

.section/pm seg_pmco;
.extern _diag_ticks;
.extern _bq_fx_cascade_blk;
.extern _bq_fx_cascade_simd;

/* The tick pointer is reloaded from DM on every stamp for the same reason
 * the rep counter lives there: a cascade owns the register file across the
 * call and nothing the ladder holds survives it. */
#define BQS_T   r3 = dm(_bqsh_tp); i5 = r3; l5 = 0; \
                r2 = tcount; r0 = dm(_diag_ticks); \
                dm(i5,1) = r0; dm(i5,1) = r2; \
                r3 = i5; dm(_bqsh_tp) = r3;

/*----------------------------------------------------------------------
 * _bqf_cascade_blk — float DF-II-T cascade, one channel, whole block.
 *
 * Same loop SHAPE as _bq_fx_cascade_blk -- stage outer, sample inner,
 * coefficients and state held in registers across the block -- so the
 * comparison is of arithmetic and not of structure.
 *
 * REGISTER ALLOCATION IS THE WHOLE DESIGN, and the rule was established
 * against the assembler rather than from memory: a multifunction
 * multiply must read Fx from F0-F3 and Fy from F4-F7 IN THAT ORDER, and
 * the parallel ALU op must read Fz from F8-F11 and Fw from F12-F15 IN
 * THAT ORDER. Destinations are unrestricted. `f12 = f4 * f0, ...` and
 * `... f8 = f13 + f9` are both rejected; the operand ORDER is not
 * commutative to the encoder even where the arithmetic is.
 *
 *   F0 x     F1 y     F2 a2        F4 b0  F5 b1  F6 b2  F7 a1
 *   F8 w1    F10 w2   F11 t        F9 b2x F12 b0x F13 b1x F14 a1y F15 a2y
 *
 * There are five coefficients and only four Fy registers, so exactly one
 * product -- a2*y -- must be a plain multiply with no ALU partner. That
 * is the one instruction of the eight that a wider quadrant would buy
 * back.
 *
 * In: i0 = coeffs (5/stage: b0 b1 b2 a1 a2), i1 = state (2/stage: w1 w2),
 *     i2 = signal block, r4 = stages.
 *----------------------------------------------------------------------*/
.global _bqf_cascade_blk;
_bqf_cascade_blk:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 1;
    m3 = r15;

    lcntr = r4, do .bqf_stage until lce;
        f4 = dm(i0, 1);        /* b0 */
        f5 = dm(i0, 1);        /* b1 */
        f6 = dm(i0, 1);        /* b2 */
        f7 = dm(i0, 1);        /* a1 */
        f2 = dm(i0, 1);        /* a2 -- plain-multiply operand */
        f8  = dm(i1, 1);       /* w1 */
        f10 = dm(i1, 0);       /* w2, i1 parked at base+1 */

        lcntr = DSP4_BLOCK_SIZE, do .bqf_samp until lce;
            f0 = dm(i2, 0);                 /* x */
            f12 = f0 * f4;                  /* b0*x */
            f13 = f0 * f5, f1 = f8 + f12;   /* b1*x  ||  y = w1 + b0x */
            f9  = f0 * f6, f11 = f10 + f13; /* b2*x  ||  t = w2 + b1x */
            f14 = f1 * f7;                  /* a1*y */
            f15 = f2 * f1;                  /* a2*y -- PLAIN: a2 cannot sit
                                             * in the Fy quadrant, which is
                                             * full of b0/b1/b2/a1 */
            f8 = f11 - f14;                 /* w1' = t - a1y */
        .bqf_samp: f10 = f9 - f15, dm(i2, 1) = f1;   /* w2' || store y */

        dm(i1, -1) = f10;
        dm(i1, 1) = f8;
        modify(i1, m3);
        modify(i2, m2);
    .bqf_stage:
        nop;
    rts;
_bqf_cascade_blk.end:

/*----------------------------------------------------------------------
 * _bqf_cascade_simd — the same, two channels on the PEx/PEy pair.
 *
 * Coefficients, state and signal INTERLEAVED by channel, the same layout
 * _bq_fx_cascade_simd uses. There is no saturation here, so unlike the
 * fixed twin there is no per-PE conditional move to get right.
 *
 * MODE1 is saved and restored WHOLE and interrupts are NOT masked -- the
 * systemic per-ISR PEYEN clear is what makes that safe, and it is the same
 * discipline the fixed SIMD cascade relies on.
 *----------------------------------------------------------------------*/
.global _bqf_cascade_simd;
_bqf_cascade_simd:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 2;
    m3 = r15;

    r0 = mode1;
    dm(_bqf_mode1_save) = r0;
    bit set mode1 0x00200000;  /* PEYEN */
    nop;
    nop;

    lcntr = r4, do .bqfs_stage until lce;
        f4 = dm(i0, 2);
        f5 = dm(i0, 2);
        f6 = dm(i0, 2);
        f7 = dm(i0, 2);
        f2 = dm(i0, 2);
        f8  = dm(i1, 2);
        f10 = dm(i1, 0);

        lcntr = DSP4_BLOCK_SIZE, do .bqfs_samp until lce;
            f0 = dm(i2, 0);
            f12 = f0 * f4;
            f13 = f0 * f5, f1 = f8 + f12;
            f9  = f0 * f6, f11 = f10 + f13;
            f14 = f1 * f7;
            f15 = f2 * f1;
            f8 = f11 - f14;
        .bqfs_samp: f10 = f9 - f15, dm(i2, 2) = f1;

        dm(i1, -2) = f10;
        dm(i1, 2) = f8;
        modify(i1, m3);
        modify(i2, m2);
    .bqfs_stage:
        nop;

    r0 = dm(_bqf_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqf_cascade_simd.end:


/*======================================================================
 * RIG C — FIXED-POINT ROUND-ONCE (2026-09-02).
 *
 * PW's D5 amendment of the same day: round and saturate ONCE per strip
 * (gain path) and once per CASCADE OUTPUT (biquads), not per stage. RIG
 * A2 above answers that with float. RIG C answers it while KEEPING THE
 * FIXED CONTRACT -- same integer arithmetic, same coefficient words,
 * same offset encoding, same six MACs -- by deleting from the per-stage
 * body exactly the three things the ruling makes per-cascade:
 *
 *   the branch-free SATURATE   6 instructions
 *   the error-feedback MAC     1 instruction
 *   (and with it the efb state pair, two words per stage)
 *
 * WHAT IS *NOT* DELETABLE, AND IT IS THE WHOLE RESULT. A stage's output
 * feeds the NEXT stage's multiplier and its own y1/y2, so it must exist
 * as a 32-bit register every sample: the 64-bit accumulator has to be
 * EXTRACTED once per stage per sample whatever the rounding policy is.
 * That extract is four instructions on this part --
 *
 *      r2 = mr0f;  r3 = mr1f;
 *      r0 = lshift r2 by -28;  r0 = r0 or lshift r3 by 4;
 *
 * -- and a one-instruction extract (`Rn = MR1F`) exists only when the
 * shift is exactly 32, i.e. when the COEFFICIENTS are Q0.32 and bounded
 * by one. They are not: g1h is b1/2 and |b1| reaches 11.2 in the
 * product's own design space (see biquad_fx.asm and bound_direct.py).
 * So the float arm's advantage is not only the saturate -- it is that
 * float has NO extract at all, its rounding being the format's.
 *
 * HEADROOM IS BOUGHT AT CASCADE ENTRY, NOT IN THIS LOOP. With the
 * internal signal carried as Q(4+H).(28-H) and the coefficients left at
 * Q4.28, the product is Q(8+H).(56-H) and the output word wants
 * (28-H) fraction bits, so the extract shift is 28 FOR EVERY H. The
 * kernel below is therefore the same instruction stream at every
 * headroom setting; H costs low bits (tools/dsp/roundonce_noise.py) and
 * costs nothing here.
 *
 * TWO ARMS, because the per-stage extract is still a rounding point and
 * the cheap thing to do there is nothing:
 *   _bqc_*   round to nearest -- one extra MAC per sample to seed MRF
 *            with 2^27 (it cannot ride in the accumulator the way the
 *            fused kernel's does, because there is no efb chain left to
 *            carry it from sample to sample)
 *   _bqt_*   truncate -- the floor, one instruction cheaper and one
 *            half-LSB of DC bias per stage
 *
 * State is FOUR words per stage, not six: x1 x2 y1 y2, no efb pair.
 *======================================================================*/

/*----------------------------------------------------------------------
 * _bqc_cascade_blk — RIG C, round to nearest, one channel.
 * In: i0 = coeffs (5/stage), i1 = state (4/stage), i2 = signal, r4 = stages.
 *----------------------------------------------------------------------*/
.global _bqc_cascade_blk;
_bqc_cascade_blk:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 3;
    m3 = r15;                  /* state base+1 -> next stage's base */

    lcntr = r4, do .bqc_stage until lce;
        r4 = dm(i0, 1);        /* b0 */
        r5 = dm(i0, 1);        /* nh */
        r6 = dm(i0, 1);        /* n2 */
        r7 = dm(i0, 1);        /* c1 */
        r8 = dm(i0, 1);        /* c2 */

        r9  = dm(i1, 1);       /* x1 */
        r10 = dm(i1, 1);       /* x2 */
        r11 = dm(i1, 1);       /* y1 */
        r12 = dm(i1, 0);       /* y2 -- i1 parked at base+3 */

        r13 = 0x10000000;
        r5 = r5 - r4;          /* g1h */
        r6 = r6 + r4;          /* g2  */
        r14 = r13 + r13;
        r7 = r14 - r7;         /* g3  */
        r8 = r8 - r13;         /* g4  */
        r14 = 0x08000000;      /* the rounding half */
        r13 = 1;

        lcntr = DSP4_BLOCK_HALF, do .bqc_samp until lce;
            /* ---- sample A: x1 r9, x2 r10, y1 r11, y2 r12 ---- */
            mrf = r14 * r13 (ssi);          /* MRF = 2^27, fresh each sample */
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;      /* y in r0, WRAPPING -- no saturate */
            r12 = pass r0, dm(i2, 1) = r0;

            /* ---- sample B: x1 r10, x2 r9, y1 r12, y2 r11 ---- */
            mrf = r14 * r13 (ssi);
            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
        .bqc_samp: r11 = pass r0, dm(i2, 1) = r0;

        dm(i1, -1) = r12;      /* y2 at +3 */
        dm(i1, -1) = r11;      /* y1 at +2 */
        dm(i1, -1) = r10;      /* x2 at +1 */
        dm(i1, 1) = r9;        /* x1 at +0 -> i1 = base+1 */
        modify(i1, m3);
        modify(i2, m2);
    .bqc_stage:
        nop;
    rts;
_bqc_cascade_blk.end:

/*----------------------------------------------------------------------
 * _bqt_cascade_blk — RIG C floor, TRUNCATING, one channel.
 * The seeding MAC is gone and the first product clears MRF itself.
 *----------------------------------------------------------------------*/
.global _bqt_cascade_blk;
_bqt_cascade_blk:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 3;
    m3 = r15;

    lcntr = r4, do .bqt_stage until lce;
        r4 = dm(i0, 1);
        r5 = dm(i0, 1);
        r6 = dm(i0, 1);
        r7 = dm(i0, 1);
        r8 = dm(i0, 1);
        r9  = dm(i1, 1);
        r10 = dm(i1, 1);
        r11 = dm(i1, 1);
        r12 = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;

        lcntr = DSP4_BLOCK_HALF, do .bqt_samp until lce;
            mrf = r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            r12 = pass r0, dm(i2, 1) = r0;

            mrf = r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
        .bqt_samp: r11 = pass r0, dm(i2, 1) = r0;

        dm(i1, -1) = r12;
        dm(i1, -1) = r11;
        dm(i1, -1) = r10;
        dm(i1, 1) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqt_stage:
        nop;
    rts;
_bqt_cascade_blk.end:

/*----------------------------------------------------------------------
 * _bqc_cascade_simd / _bqt_cascade_simd — the same two, paired.
 * Coefficients, state (4/stage) and signal INTERLEAVED by channel.
 * MODE1 saved and restored WHOLE, interrupts NOT masked -- the systemic
 * per-ISR PEYEN clear is what makes that safe.
 *----------------------------------------------------------------------*/
.global _bqc_cascade_simd;
_bqc_cascade_simd:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 6;
    m3 = r15;                  /* state base+2 -> next stage's base */

    r0 = mode1;
    dm(_bqc_mode1_save) = r0;
    bit set mode1 0x00200000;
    nop;
    nop;

    lcntr = r4, do .bqcs_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);
        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 0);       /* i1 parked at base+6 */
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;
        r14 = 0x08000000;
        r13 = 1;

        lcntr = DSP4_BLOCK_HALF, do .bqcs_samp until lce;
            mrf = r14 * r13 (ssi);
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            r12 = pass r0, dm(i2, 2) = r0;

            mrf = r14 * r13 (ssi);
            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
        .bqcs_samp: r11 = pass r0, dm(i2, 2) = r0;

        dm(i1, -2) = r12;
        dm(i1, -2) = r11;
        dm(i1, -2) = r10;
        dm(i1, 2) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqcs_stage:
        nop;

    r0 = dm(_bqc_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqc_cascade_simd.end:

.global _bqt_cascade_simd;
_bqt_cascade_simd:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 6;
    m3 = r15;

    r0 = mode1;
    dm(_bqc_mode1_save) = r0;
    bit set mode1 0x00200000;
    nop;
    nop;

    lcntr = r4, do .bqts_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);
        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;

        lcntr = DSP4_BLOCK_HALF, do .bqts_samp until lce;
            mrf = r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            r12 = pass r0, dm(i2, 2) = r0;

            mrf = r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
        .bqts_samp: r11 = pass r0, dm(i2, 2) = r0;

        dm(i1, -2) = r12;
        dm(i1, -2) = r11;
        dm(i1, -2) = r10;
        dm(i1, 2) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqts_stage:
        nop;

    r0 = dm(_bqc_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqt_cascade_simd.end:


/*----------------------------------------------------------------------
 * _bqe_cascade_blk / _bqe_cascade_simd — RIG C, ERROR FEEDBACK KEPT.
 *
 * The measurement that changes the answer. Deleting the per-stage
 * saturate and deleting the error feedback are two SEPARATE deletions,
 * and roundonce_noise.py shows they cost wildly different things: the
 * saturate costs SIX instructions and buys nothing back numerically
 * while no stage overflows, and the error feedback costs ONE and is
 * worth 16 dB of LF response on the shelf D5 was decided on.
 *
 * So this arm deletes only the saturate. What is left is today's kernel
 * with the branch-free clamp taken out and the extract folded from five
 * instructions into four (`Rn = Rn OR LSHIFT Rx BY 4` needs its
 * destination to be the shifted-low operand, which is why the fused
 * kernel's three-instruction combine becomes two here):
 *
 *     6 MACs + 4 extract + 1 error-feedback MAC + 1 store  =  12
 *
 * against the fused kernel's nineteen, and identical in count to the
 * no-feedback arm above -- the seeding MAC that arm pays every sample to
 * put 2^27 into a cleared MRF is exactly the instruction this arm spends
 * on the feedback, and the rounding half rides in the accumulator here
 * the way it does in the shipping kernel.
 *
 * WHEN NOTHING OVERFLOWS THIS IS BIT-IDENTICAL TO THE CONTRACT, because
 * a saturate that never fires is the identity. What it gives up is what
 * happens when something DOES: the extract wraps, and in a recursive
 * path a wrap is a sign inversion fed back into the poles. That is the
 * whole of RIG C's risk, isolated in one arm.
 *
 * State is SIX words per stage again -- x1 x2 y1 y2 efb_lo efb_hi.
 *
 * MEASURED 8.51 c/band-sample paired against the no-feedback arm's 7.70
 * on the SAME twelve instructions, and the 0.81 is NOT the adjacency of
 * the feedback MAC to the ALU op that produces its operand: moving the
 * MAC after the store, so an instruction stands between them, measured
 * 8.51 as well. It is the MRF chain. The no-feedback arm SEEDS a cleared
 * accumulator every sample, which breaks the dependency; this arm carries
 * MRF from sample to sample, so seven dependent MACs run back to back.
 *----------------------------------------------------------------------*/
.global _bqe_cascade_blk;
_bqe_cascade_blk:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 5;
    m3 = r15;

    lcntr = r4, do .bqe_stage until lce;
        r4 = dm(i0, 1);
        r5 = dm(i0, 1);
        r6 = dm(i0, 1);
        r7 = dm(i0, 1);
        r8 = dm(i0, 1);
        r9  = dm(i1, 1);
        r10 = dm(i1, 1);
        r11 = dm(i1, 1);
        r12 = dm(i1, 1);
        r2  = dm(i1, 1);
        r3  = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);

        lcntr = DSP4_BLOCK_HALF, do .bqe_samp until lce;
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            r12 = pass r0, dm(i2, 1) = r0;

            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
        .bqe_samp: r11 = pass r0, dm(i2, 1) = r0;

        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        dm(i1, -1) = r3;
        dm(i1, -1) = r2;
        dm(i1, -1) = r12;
        dm(i1, -1) = r11;
        dm(i1, -1) = r10;
        dm(i1, 1) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqe_stage:
        nop;
    rts;
_bqe_cascade_blk.end:

.global _bqe_cascade_simd;
_bqe_cascade_simd:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 10;
    m3 = r15;

    r0 = mode1;
    dm(_bqc_mode1_save) = r0;
    bit set mode1 0x00200000;
    nop;
    nop;

    lcntr = r4, do .bqes_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);
        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 2);
        r2  = dm(i1, 2);
        r3  = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);

        lcntr = DSP4_BLOCK_HALF, do .bqes_samp until lce;
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            r12 = pass r0, dm(i2, 2) = r0;

            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
        .bqes_samp: r11 = pass r0, dm(i2, 2) = r0;

        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        dm(i1, -2) = r3;
        dm(i1, -2) = r2;
        dm(i1, -2) = r12;
        dm(i1, -2) = r11;
        dm(i1, -2) = r10;
        dm(i1, 2) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqes_stage:
        nop;

    r0 = dm(_bqc_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqe_cascade_simd.end:

/*----------------------------------------------------------------------
 * _bqh_cascade_ent — RIG C's GUARD, the ENTRY half, measured with the
 * scale on EVERY stage.
 *
 * The real guard shifts the cascade INPUT down H bits once and the
 * cascade OUTPUT back up once -- two instructions per sample per
 * CASCADE, not per stage. On a 28-stage bank that is 1/28 of a cycle and
 * the rig cannot see it. So the cost is measured AMPLIFIED: every stage
 * pays the entry scale, the delta against rung 15 is the cost of ONE
 * entry scale times 28, and the guard's real per-band-sample cost for an
 * n-stage cascade is that delta divided by 28 and again by n.
 *
 * Measuring the amplified form and dividing is the only way to resolve a
 * one-instruction change against an instrument whose spread is a few
 * hundredths of a cycle -- and it is the same reason the ladder times
 * 400 iterations of a 28-stage cascade instead of one biquad.
 *
 * -H is a CONTROL-RATE word, loaded once per stage. Under round-once r15
 * is free -- it used to hold the saturation pattern -- so the entry
 * scale needs no spill and no extra load in the sample loop.
 *--------------------------------------------------------------------*/
.global _bqh_cascade_ent;
_bqh_cascade_ent:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 10;
    m3 = r15;

    r0 = mode1;
    dm(_bqc_mode1_save) = r0;
    bit set mode1 0x00200000;
    nop;
    nop;

    lcntr = r4, do .bqhe_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);
        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 2);
        r2  = dm(i1, 2);
        r3  = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);
        r15 = dm(_bqh_hm);     /* -H, control-rate, once per stage */

        lcntr = DSP4_BLOCK_HALF, do .bqhe_samp until lce;
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            r10 = ashift r10 by r15;        /* THE ENTRY SCALE */
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            r12 = pass r0, dm(i2, 2) = r0;

            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            r9 = ashift r9 by r15;          /* THE ENTRY SCALE */
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
        .bqhe_samp: r11 = pass r0, dm(i2, 2) = r0;

        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        dm(i1, -2) = r3;
        dm(i1, -2) = r2;
        dm(i1, -2) = r12;
        dm(i1, -2) = r11;
        dm(i1, -2) = r10;
        dm(i1, 2) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqhe_stage:
        nop;

    r0 = dm(_bqc_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqh_cascade_ent.end:

/*----------------------------------------------------------------------
 * _bqh_cascade_exi — RIG C's GUARD, the EXIT half, measured with the
 * clamp on EVERY stage, for _bqh_cascade_ent's reason.
 *
 * This is the SINGLE round-and-saturate the D5 amendment rules for --
 * once per cascade output, not once per stage -- with the exit scale
 * folded into it. It is EIGHT instructions where the entry is one, and
 * the reason is register pressure: three loop invariants (+H, -H and the
 * saturation pattern) and exactly one free register, so two of them are
 * re-read from memory every sample. A kernel that could hold all three
 * would be six.
 *
 * y stays UNSCALED in r12/r11. That is the whole design: the recursion
 * lives at the scaled level where |h|_1 * x fits Q4.28, and only the
 * word handed to the next node comes back up -- which is why a
 * per-cascade CLAMP alone does not work and a per-cascade SCALE does.
 *--------------------------------------------------------------------*/
.global _bqh_cascade_exi;
_bqh_cascade_exi:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;
    r15 = 10;
    m3 = r15;

    r0 = mode1;
    dm(_bqc_mode1_save) = r0;
    bit set mode1 0x00200000;
    nop;
    nop;

    lcntr = r4, do .bqhx_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);
        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 2);
        r2  = dm(i1, 2);
        r3  = dm(i1, 0);
        r13 = 0x10000000;
        r5 = r5 - r4;
        r6 = r6 + r4;
        r14 = r13 + r13;
        r7 = r14 - r7;
        r8 = r8 - r13;
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);
        r15 = dm(_bqh_hp);     /* +H, control-rate, once per stage */

        lcntr = DSP4_BLOCK_HALF, do .bqhx_samp until lce;
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r5 * r9  (ssi);
            mrf = mrf + r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            /* ---- THE EXIT SCALE AND THE SINGLE CLAMP ----
             * y_out = sat32(y << H), and y itself stays UNSCALED in the
             * history register: the recursion runs at the scaled level
             * that keeps it representable, and only the word handed on
             * comes back up. The saturated value is built BEFORE the
             * compare, because the ALU ops that build it would otherwise
             * overwrite the flags it is conditioned on -- the shipping
             * kernel's own idiom. */
            r2 = dm(_bqh_sat);
            r3 = ashift r0 by -31;          /* sign of y            */
            r2 = r2 xor r3;                 /* MAX, or MIN          */
            r1 = ashift r0 by r15;          /* candidate = y << H   */
            r3 = dm(_bqh_hm);
            r3 = ashift r1 by r3;           /* candidate >> H       */
            comp(r3, r0);                   /* did the shift lose bits? */
            if ne r1 = pass r2;             /* per-PE, not a branch */
            dm(i2, 2) = r1;
            r12 = pass r0;

            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            r2 = dm(_bqh_sat);
            r3 = ashift r0 by -31;
            r2 = r2 xor r3;
            r1 = ashift r0 by r15;
            r3 = dm(_bqh_hm);
            r3 = ashift r1 by r3;
            comp(r3, r0);
            if ne r1 = pass r2;
            dm(i2, 2) = r1;
        .bqhx_samp: r11 = pass r0;

        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        dm(i1, -2) = r3;
        dm(i1, -2) = r2;
        dm(i1, -2) = r12;
        dm(i1, -2) = r11;
        dm(i1, -2) = r10;
        dm(i1, 2) = r9;
        modify(i1, m3);
        modify(i2, m2);
    .bqhx_stage:
        nop;

    r0 = dm(_bqc_mode1_save);
    mode1 = r0;
    nop;
    nop;
    rts;
_bqh_cascade_exi.end:

/*======================================================================
 * RIG C — GAIN, ROUND ONCE PER STRIP (2026-09-02).
 *
 * The shipping SIMD gain kernel (_gsimd_gain_blk, lib/meter_fx.asm)
 * runs EIGHTEEN instructions per two samples -- two samples because the
 * pairing is across ADJACENT SAMPLES of one channel, not across
 * channels. Of those eighteen, ONE is the gain multiply. Eleven are the
 * Q4.28 numeric contract: the rounding MAC, the 64-bit extract, and the
 * branch-free saturate.
 *
 * Under the round-once ruling the strip's clamp moves to strip OUTPUT,
 * so the gain node hands the chain a WIDE word. On this part that word
 * is free: the product of two Q4.28 words is Q8.56 in MRB, and MR1B is
 * its top 32 bits -- exactly Q8.24, four bits of headroom and four
 * fewer fraction bits, in ONE instruction and no shifter at all. It is
 * also the word the METER already reads (`r12 = mr1b`, "WIDE post-trim,
 * Q8.24"), so the round-once arm's sample body is the metered arm's
 * body with the arithmetic deleted and nothing added.
 *
 * OTHER HEADROOMS ARE ALSO FREE HERE, unlike in the cascade: scaling the
 * one effective gain word by 2^(4-H) at CONTROL rate moves the binary
 * point without touching the sample loop. H = 4 is simply the setting
 * that needs no scaling at all.
 *
 * THE MIC-PRE TAP (D20) IS THE CONSTRAINT AND IT IS MEASURED BOTH WAYS.
 * The tap is the product's clean recording pickoff and its bit pattern
 * is ruled bit-identical to today's, which is a Q4.28 rounded and
 * saturated word. A wide chain slot does NOT give that: MR1B has
 * already dropped the four bits the Q4.28 rounding would have seen, so
 * rounding Q8.24 down to Q4.28 later is not the same word. So:
 *
 *   _gsh_gain_now   today, both stores Q4.28 rounded+saturated
 *   _gsh_gain_r1    round-once, BOTH stores wide -- the floor, and the
 *                   arm that gives up the tap's bit pattern
 *   _gsh_gain_r1t   round-once chain slot, tap STILL Q4.28 rounded and
 *                   saturated -- what D20 as written actually costs
 *
 * and the same three without the meter, to separate the gain from the
 * metering the 2026-08-29 wide-word ruling puts in the same loop.
 *======================================================================*/

#define GSH_PROLOGUE \
    l0 = 0; l1 = 0; l4 = 0; \
    dm(_gsh_g) = r1; \
    dm(_gsh_g + 1) = r1; \
    r2 = mode1; \
    dm(_gsh_save) = r2; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r1 = dm(_gsh_g); \
    r6 = 0x08000000; \
    r7 = 1; \
    r10 = 0x7FFFFFFF; \
    r13 = 0x80000000; \
    r15 = 0x7FFFFFFF; \
    mrf = 0; \
    r12 = 0;

#define GSH_EPILOGUE \
    r13 = max(r13, r12); \
    mrf = mrf + r12 * r12 (ssi); \
    r15 = min(r15, r12); \
    r1 = mr0f; dm(_gsh_sq0) = r1; \
    r1 = mr1f; dm(_gsh_sq1) = r1; \
    r1 = mr2f; dm(_gsh_sq2) = r1; \
    dm(_gsh_max) = r13; \
    dm(_gsh_min) = r15; \
    r1 = dm(_gsh_save); \
    mode1 = r1; \
    nop; \
    nop; \
    rts;

/* ---- today: rounded, saturated, both stores ---- */
.global _gsh_gain_now;
_gsh_gain_now:
    GSH_PROLOGUE
    lcntr = DSP4_BLOCK_HALF, do .gshn_lp until lce;
        mrf = mrf + r12 * r12 (ssi), r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);
        r13 = max(r13, r12);
        r15 = min(r15, r12);
        r12 = mr1b;
        mrb = mrb + r6 * r7 (ssi);
        r8 = mr0b;
        r2 = mr1b;
        r0 = lshift r8 by -28;
        r0 = r0 or lshift r2 by 4;
        r8 = ashift r2 by -28;
        r9 = ashift r0 by -31;
        r11 = ashift r2 by -31;
        r11 = r10 xor r11;
        comp(r8, r9);
        if ne r0 = pass r11;
        dm(i1, 2) = r0;
.gshn_lp:
        dm(i4, 2) = r0;
    GSH_EPILOGUE
_gsh_gain_now.end:

/* ---- round-once, BOTH stores wide Q8.24 ---- */
.global _gsh_gain_r1;
_gsh_gain_r1:
    GSH_PROLOGUE
    lcntr = DSP4_BLOCK_HALF, do .gshr_lp until lce;
        mrf = mrf + r12 * r12 (ssi), r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);
        r13 = max(r13, r12);
        r15 = min(r15, r12);
        r12 = mr1b;
        dm(i1, 2) = r12;
.gshr_lp:
        dm(i4, 2) = r12;
    GSH_EPILOGUE
_gsh_gain_r1.end:

/* ---- round-once chain slot, D20 tap still Q4.28 rounded+saturated ---- */
.global _gsh_gain_r1t;
_gsh_gain_r1t:
    GSH_PROLOGUE
    lcntr = DSP4_BLOCK_HALF, do .gshrt_lp until lce;
        mrf = mrf + r12 * r12 (ssi), r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);
        r13 = max(r13, r12);
        r15 = min(r15, r12);
        r12 = mr1b;
        dm(i1, 2) = r12;                /* chain slot: WIDE */
        mrb = mrb + r6 * r7 (ssi);
        r8 = mr0b;
        r2 = mr1b;
        r0 = lshift r8 by -28;
        r0 = r0 or lshift r2 by 4;
        r8 = ashift r2 by -28;
        r9 = ashift r0 by -31;
        r11 = ashift r2 by -31;
        r11 = r10 xor r11;
        comp(r8, r9);
        if ne r0 = pass r11;
.gshrt_lp:
        dm(i4, 2) = r0;                 /* tap: Q4.28, bit-identical */
    GSH_EPILOGUE
_gsh_gain_r1t.end:

/* ---- the same three with NO meter ---- */
.global _gsh_gain_now_nm;
_gsh_gain_now_nm:
    GSH_PROLOGUE
    lcntr = DSP4_BLOCK_HALF, do .gshnm_lp until lce;
        r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);
        mrb = mrb + r6 * r7 (ssi);
        r8 = mr0b;
        r2 = mr1b;
        r0 = lshift r8 by -28;
        r0 = r0 or lshift r2 by 4;
        r8 = ashift r2 by -28;
        r9 = ashift r0 by -31;
        r11 = ashift r2 by -31;
        r11 = r10 xor r11;
        comp(r8, r9);
        if ne r0 = pass r11;
        dm(i1, 2) = r0;
.gshnm_lp:
        dm(i4, 2) = r0;
    GSH_EPILOGUE
_gsh_gain_now_nm.end:

.global _gsh_gain_r1_nm;
_gsh_gain_r1_nm:
    GSH_PROLOGUE
    lcntr = DSP4_BLOCK_HALF, do .gshrm_lp until lce;
        r0 = dm(i0, 2);
        mrb = r0 * r1 (ssi);
        r12 = mr1b;
        dm(i1, 2) = r12;
.gshrm_lp:
        dm(i4, 2) = r12;
    GSH_EPILOGUE
_gsh_gain_r1_nm.end:

/*----------------------------------------------------------------------
 * _bqsh_selftest — the ladder. Same shape as call_selftest.asm's: one
 * timestamp pair either side of each rung, the whole ladder run REPS
 * times so the host can take the minimum and drop any pass a diag-tick
 * ISR landed in.
 *----------------------------------------------------------------------*/
.global _bqsh_selftest;
_bqsh_selftest:
    r0 = _bqsh_tick;
    dm(_bqsh_tp) = r0;              /* tick write pointer, in DM */
    r0 = 0;
    dm(_bqsh_rep) = r0;             /* rep counter, in DM */

.bqsh_rep:

    /* ---- rung 0: NULL, the loop's own cost ---------------------------- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r0 until lce;
        nop;
    .bqsh_r0: nop;
    BQS_T

    /* ---- rung 1: today's FIXED cascade, 1 channel --------------------- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r1 until lce;
        i0 = _bqsh_fxc; i1 = _bqsh_fxs; i2 = _bqsh_fxsig;
        r4 = BQS_STAGES;
        call _bq_fx_cascade_blk;
        nop;
    .bqsh_r1: nop;
    BQS_T

    /* ---- rung 2: today's FIXED cascade, 2 channels (SIMD) ------------- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r2 until lce;
        i0 = _bqsh_fxci; i1 = _bqsh_fxsi; i2 = _bqsh_fxsigi;
        r4 = BQS_STAGES;
        call _bq_fx_cascade_simd;
        nop;
    .bqsh_r2: nop;
    BQS_T

    /* ---- rung 3: FLOAT DF-II-T, 1 channel ----------------------------- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r3 until lce;
        i0 = _bqsh_flc; i1 = _bqsh_fls; i2 = _bqsh_flsig;
        r4 = BQS_STAGES;
        call _bqf_cascade_blk;
        nop;
    .bqsh_r3: nop;
    BQS_T

    /* ---- rung 4: FLOAT DF-II-T, 2 channels (SIMD) --------------------- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r4 until lce;
        i0 = _bqsh_flci; i1 = _bqsh_flsi; i2 = _bqsh_flsigi;
        r4 = BQS_STAGES;
        call _bqf_cascade_simd;
        nop;
    .bqsh_r4: nop;
    BQS_T


    /* ---- rung 5: bqc_cascade_blk ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r5 until lce;
        i0 = _bqsh_cfc; i1 = _bqsh_cfs; i2 = _bqsh_cfsig;
        r4 = BQS_STAGES;
        call _bqc_cascade_blk;
        nop;
    .bqsh_r5: nop;
    BQS_T

    /* ---- rung 6: bqc_cascade_simd ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r6 until lce;
        i0 = _bqsh_cfci; i1 = _bqsh_cfsi; i2 = _bqsh_cfsigi;
        r4 = BQS_STAGES;
        call _bqc_cascade_simd;
        nop;
    .bqsh_r6: nop;
    BQS_T

    /* ---- rung 7: bqt_cascade_blk ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r7 until lce;
        i0 = _bqsh_cfc; i1 = _bqsh_cfs; i2 = _bqsh_cfsig;
        r4 = BQS_STAGES;
        call _bqt_cascade_blk;
        nop;
    .bqsh_r7: nop;
    BQS_T

    /* ---- rung 8: bqt_cascade_simd ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r8 until lce;
        i0 = _bqsh_cfci; i1 = _bqsh_cfsi; i2 = _bqsh_cfsigi;
        r4 = BQS_STAGES;
        call _bqt_cascade_simd;
        nop;
    .bqsh_r8: nop;
    BQS_T

    /* ---- rung 9: gsh_gain_now ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r9 until lce;
        i0 = _gsh_src; i1 = _gsh_chain; i4 = _gsh_tap;
        r1 = 0x0B504F33;           /* a NON-ROUND gain, 0.70710678 */
        call _gsh_gain_now;
        nop;
    .bqsh_r9: nop;
    BQS_T

    /* ---- rung 10: gsh_gain_r1 ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r10 until lce;
        i0 = _gsh_src; i1 = _gsh_chain; i4 = _gsh_tap;
        r1 = 0x0B504F33;           /* a NON-ROUND gain, 0.70710678 */
        call _gsh_gain_r1;
        nop;
    .bqsh_r10: nop;
    BQS_T

    /* ---- rung 11: gsh_gain_r1t ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r11 until lce;
        i0 = _gsh_src; i1 = _gsh_chain; i4 = _gsh_tap;
        r1 = 0x0B504F33;           /* a NON-ROUND gain, 0.70710678 */
        call _gsh_gain_r1t;
        nop;
    .bqsh_r11: nop;
    BQS_T

    /* ---- rung 12: gsh_gain_now_nm ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r12 until lce;
        i0 = _gsh_src; i1 = _gsh_chain; i4 = _gsh_tap;
        r1 = 0x0B504F33;           /* a NON-ROUND gain, 0.70710678 */
        call _gsh_gain_now_nm;
        nop;
    .bqsh_r12: nop;
    BQS_T

    /* ---- rung 13: gsh_gain_r1_nm ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r13 until lce;
        i0 = _gsh_src; i1 = _gsh_chain; i4 = _gsh_tap;
        r1 = 0x0B504F33;           /* a NON-ROUND gain, 0.70710678 */
        call _gsh_gain_r1_nm;
        nop;
    .bqsh_r13: nop;
    BQS_T


    /* ---- rung 14: bqe_cascade_blk ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r14 until lce;
        i0 = _bqsh_fxc; i1 = _bqsh_fxs; i2 = _bqsh_fxsig;
        r4 = BQS_STAGES;
        call _bqe_cascade_blk;
        nop;
    .bqsh_r14: nop;
    BQS_T

    /* ---- rung 15: bqe_cascade_simd ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r15 until lce;
        i0 = _bqsh_fxci; i1 = _bqsh_fxsi; i2 = _bqsh_fxsigi;
        r4 = BQS_STAGES;
        call _bqe_cascade_simd;
        nop;
    .bqsh_r15: nop;
    BQS_T

    /* ---- rung 16: the GUARD's entry scale, on every stage ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r16 until lce;
        i0 = _bqsh_fxci; i1 = _bqsh_fxsi; i2 = _bqsh_fxsigi;
        r4 = BQS_STAGES;
        call _bqh_cascade_ent;
        nop;
    .bqsh_r16: nop;
    BQS_T

    /* ---- rung 17: the GUARD's exit scale + single clamp, every stage ---- */
    BQS_T
    r10 = dm(_bqsh_iters);
    lcntr = r10, do .bqsh_r17 until lce;
        i0 = _bqsh_fxci; i1 = _bqsh_fxsi; i2 = _bqsh_fxsigi;
        r4 = BQS_STAGES;
        call _bqh_cascade_exi;
        nop;
    .bqsh_r17: nop;
    BQS_T

    r0 = dm(_bqsh_rep);
    r1 = 1;
    r0 = r0 + r1;
    dm(_bqsh_rep) = r0;
    r1 = BQS_REPS;
    comp(r0, r1);
    if lt jump (pc, .bqsh_rep);

    r0 = 1;
    dm(_bqsh_done) = r0;
    rts;
_bqsh_selftest.end:

#endif /* DSP4_BQ_SHOOTOUT */
