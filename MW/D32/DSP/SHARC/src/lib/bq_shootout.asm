/*======================================================================
 * bq_shootout.asm — RIG A2 of the biquad shootout spike (2026-09-02).
 *
 * SPIKE ONLY. Standalone rig, never in a shipping image, no graph
 * integration, no contract edit. Guarded on DSP4_BQ_SHOOTOUT.
 *
 * THE QUESTION. PW: "3 cycles/biquad is achievable on this part; round
 * once per cascade output instead of per stage." Today's fixed cascade
 * measures 12.83 cycles/band-sample paired (session 19) against a
 * current-contract floor of 5.94 (session 18), and eleven of its nineteen
 * inner-loop instructions ARE the numeric contract -- the 64-bit extract,
 * the branch-free saturate, the error-feedback MAC. A FLOAT cascade pays
 * none of those: the rounding is the format's, once per operation, and
 * there is no saturate and no error feedback at all.
 *
 * WHAT IS MEASURED AGAINST WHAT. Four rungs, same loop form, same
 * iteration count, same 28-stage bank, same block size -- so the only
 * thing that differs between rung 1 and rung 3 is the ARITHMETIC:
 *
 *   rung 1  _bq_fx_cascade_blk    today's fixed cascade, 1 channel
 *   rung 2  _bq_fx_cascade_simd   today's fixed cascade, 2 channels
 *   rung 3  _bqf_cascade_blk      float DF-II-T, 1 channel
 *   rung 4  _bqf_cascade_simd     float DF-II-T, 2 channels
 *
 * THE NUMERIC COST OF RUNG 3/4 IS NOT FREE AND IS ALREADY PRICED:
 * tools/dsp/bq_float_delta.py puts it at 0.0001 dB on ordinary EQ and
 * 0.52 dB on an LF shelf at +15 dB Q3.16 -- eleven times the 0.046 dB bar
 * golden_harness holds the current contract to. This file measures the
 * CYCLES; that script measures the price.
 *
 * DF-II-T, which is the right form for float and the wrong one for fixed:
 *   y   = b0*x + w1
 *   w1' = b1*x - a1*y + w2
 *   w2' = b2*x - a2*y
 * Two state words per stage against the fixed form's six, and no
 * error-feedback word, because in float there is no rounding remainder to
 * carry.
 *======================================================================*/

#include "dsp_block.h"
#include "diag.h"

#if DSP4_BQ_SHOOTOUT

#define BQS_STAGES  28
#define BQS_RUNGS   5
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
