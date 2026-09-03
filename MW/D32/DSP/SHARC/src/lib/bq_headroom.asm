/*======================================================================
 * bq_headroom.asm — the per-cascade headroom guard, sized at
 * PARAMETER-LOAD time.
 *
 * NORMATIVE REFERENCE: tools/dsp/bq_h_load.py. This file must produce
 * the H that module produces, in the same relation to it as
 * biquad_fx.asm is to fixed_ref.py.
 *
 * WHAT IT IS FOR. Round-once (D5 amendment, landed 2026-09-03) deletes
 * the per-stage saturate, so a cascade whose reachable internal
 * magnitude exceeds Q4.28's ceiling of 8.0 WRAPS -- and in a direct-form
 * I recursion a wrap is a sign inversion fed back into the poles, not a
 * clipped sample. The bound that decides it is |h|_1, the l1 norm of the
 * impulse response, because that is what an arbitrary bounded input can
 * reach; max|H| is only what a sine can. H = ceil(log2(|h|_1 / 8)) bits
 * of headroom, sized over the worst PARTIAL cascade, restores the
 * guarantee for one shift on the way in and one shift and one clamp on
 * the way out, per cascade per sample.
 *
 * WHY THE SIZING IS A BOUNDED RUN AND NOT A CONVERGED ONE. The offline
 * sizer (tools/dsp/bq_headroom_guard.py) runs the impulse response to
 * convergence, up to 60,000 samples. A 20 Hz Q10 section has a pole
 * radius of 1 - 6.5e-5, so convergence is a quarter of a million
 * samples, and a 28-band GEQ is twenty-eight of them. This runs a
 * BOUNDED N and adds a bound on everything after it:
 *
 *   N    = clamp(ceil(6 / (1 - r_max)), 128, 1024)
 *   tot  = sum of |h[n]| over the run, per PREFIX
 *   env  = max(env * r, |h[n]|) for n >= N/2   (a DECAYING peak hold)
 *   |h|_1 <= (tot + env * r/(1-r)) * 1.125
 *
 * The decaying peak-hold is what makes a peak found anywhere in the
 * second half count, correctly discounted -- a plain window max
 * under-reads by an unbounded factor when the window lands on a null of
 * a 20 Hz ring, whose period is 2400 samples. The warm-up is what keeps
 * h[0] out of it: held at r ~ 1 the impulse itself would dominate env
 * forever and size a 20 Hz Q10 peak at H = 12 instead of H = 0. The
 * 1.125 is the safety factor that makes the result an upper bound over
 * the whole DEFS space (bq_h_load.py --check is that bar) and is one
 * shift and one add.
 *
 * WHERE IT RUNS, AND WHY THAT IS THE WHOLE DESIGN. NOT in block work.
 * A 28-band GEQ is 28 x 1024 = 28,672 stage-samples; at any budget that
 * is several blocks of arithmetic, and doing it inline would drop audio
 * on a snapshot recall -- with the size of the hit a function of how
 * many nodes the operator happened to move at once, which is the shape
 * of bug that only ever appears in front of an audience. It runs from
 * the MAIN LOOP, DSP4_BQHR_BUDGET samples per pass, out of the idle
 * spin that is already there between blocks. The graph's per-block cost
 * is untouched; the only thing the sizing spends is latency, about a
 * millisecond and a half for a four-band EQ.
 *
 * ONE JOB AT A TIME, deliberately. The engine holds one job, and a node
 * that asks while it is busy is told so and asks again next block. That
 * is what bounds the cost of a whole-console recall: N nodes take N
 * times as long, not N times as much CPU at once.
 *
 * NO RACE IS POSSIBLE and it is worth saying why: the node graph runs
 * from the main loop too (main.asm .main_loop, after _block_ready), so
 * the engine and the nodes that talk to it are strictly serialised by
 * construction. Nothing here is touched from an ISR.
 *
 * THE COEFFICIENTS SIZED ARE THE QUANTISED ONES. The engine reads the
 * fixed offset words the converter just wrote and de-quantises them back
 * to direct float, so what is bounded is the filter the part RUNS and
 * not the filter that was designed.
 *
 * Entry points:
 *   _bq_hr_request_n — i0 -> a list of (block, stages) PAIRS, r4 = how
 *                    many (1..4). r0 = 1 accepted, 0 busy. A list and
 *                    not a single block because FILT and CROSSOVER call
 *                    the cascade once per SECTION, and each call is its
 *                    own cascade with its own headroom; one request per
 *                    node keeps the engine's one-job-at-a-time rule and
 *                    keeps the sequencing out of every node body.
 *                    Clobbers r0-r15, f0-f15, i0-i2, m0-m2.
 *   _bq_hr_poll    — r0 = the FIRST block of the list (the job's key).
 *                    r0 = 1 if every block in it has its H (and the
 *                    engine is released), else 0. Clobbers r0-r2.
 *   _bq_hr_service — run one budget's worth. Main-loop context only.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#include "dsp_block.h"

#if DSP4_BQ_GUARD

.extern _bq_fx_convert_N;

/* Stages the engine can size. The deepest cascade in the product is the
 * 28-band GEQ; 32 leaves room and costs 32 words of DM per array. */
#define BQHR_KMAX     32
#define BQHR_NMAX     1024
#define BQHR_NMIN     128

.section/dm seg_dmda;

.global _bqhr_state;
.var _bqhr_state = 0;          /* 0 idle, 1 running, 2 done */
.var _bqhr_blk = 0;            /* coefficient block base being sized */
.var _bqhr_key = 0;            /* the job's key: its first block */
.var _bqhr_list[8];            /* up to 4 (block, stages) pairs */
.var _bqhr_nl = 0;             /* how many pairs */
.var _bqhr_li = 0;             /* which pair is being sized */
.var _bqhr_k = 0;              /* stages */
.var _bqhr_j = 0;              /* stage being run */
.var _bqhr_n = 0;              /* sample index within the stage */
.var _bqhr_N = 0;              /* run length */
.var _bqhr_half = 0;           /* N/2, where env starts */
.global _bqhr_calls;
.var _bqhr_calls = 0;          /* service passes, for the bench */
.global _bqhr_jobs;
.var _bqhr_jobs = 0;           /* jobs completed, for the bench */
.global _bqhr_lasth;
.var _bqhr_lasth = 0;          /* last H written, for the bench */

.var _bqhr_worst = 0.0;        /* max over prefixes so far */
.var _bqhr_tot = 0.0;          /* this prefix's truncated l1 sum */
.var _bqhr_env = 0.0;          /* this prefix's decaying peak hold */
.var _bqhr_x1 = 0.0;
.var _bqhr_x2 = 0.0;
.var _bqhr_y1 = 0.0;
.var _bqhr_y2 = 0.0;
.var _bqhr_r = 0.0;            /* prefix max pole radius */
.var _bqhr_gn = 0.0;           /* r/(1-r) for the prefix */
.var _bqhr_umin = 0.0;         /* 1 - r for the prefix (the small one) */
.var _bqhr_t0 = 0.0;           /* scratch across the reciprocal/sqrt helpers */
.var _bqhr_t1 = 0.0;
.var _bqhr_t2 = 0.0;

.var _bqhr_cf[5 * BQHR_KMAX];  /* direct float b0,b1,b2,a1,a2 per stage */
.var _bqhr_u[BQHR_KMAX];       /* 1 - r, per stage, from its OWN poles */
.var _bqhr_sig[BQHR_NMAX];     /* the prefix impulse response, in place */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _bqhr_recip — f0 = 1/f0, RECIPS plus three Newton steps.
 * Clobbers f1, f2.  (Three, not two: RECIPS is an 8-bit seed and this
 * reciprocal is taken of numbers as small as 1e-4, where the tail bound
 * multiplies whatever error is left by 10,000.)
 *--------------------------------------------------------------------*/
_bqhr_recip:
    r1 = 0x40000000;           /* 2.0f */
    f1 = r1;
    f2 = recips f0;
    f3 = f0 * f2;
    f3 = f1 - f3;
    f2 = f2 * f3;
    f3 = f0 * f2;
    f3 = f1 - f3;
    f2 = f2 * f3;
    f3 = f0 * f2;
    f3 = f1 - f3;
    f2 = f2 * f3;
    f0 = pass f2;
    rts;
_bqhr_recip.end:

/*----------------------------------------------------------------------
 * _bqhr_sqrt — f0 = sqrt(f0) for f0 > 0, RSQRTS plus three Newton steps
 * (meter_fx.asm's idiom). Zero in gives zero out.
 * Clobbers f1-f5.
 *--------------------------------------------------------------------*/
_bqhr_sqrt:
    r1 = 0;
    f1 = r1;
    comp(f0, f1);
    if le rts;
    f2 = rsqrts f0;
    r3 = 0x3FC00000;           /* 1.5f */
    f3 = r3;
    r4 = 0x3F000000;           /* 0.5f */
    f4 = r4;
    f5 = f0 * f4;              /* a/2 */
    f1 = f2 * f2;
    f1 = f5 * f1;
    f1 = f3 - f1;
    f2 = f2 * f1;
    f1 = f2 * f2;
    f1 = f5 * f1;
    f1 = f3 - f1;
    f2 = f2 * f1;
    f1 = f2 * f2;
    f1 = f5 * f1;
    f1 = f3 - f1;
    f2 = f2 * f1;
    f0 = f0 * f2;              /* sqrt(a) = a * rsqrt(a) */
    rts;
_bqhr_sqrt.end:

/*----------------------------------------------------------------------
 * _bq_hr_request — take a job, if the engine is free.
 *
 * In:  i0 -> coefficient block (header, then 5 words per stage)
 *      r4 = stages (1..BQHR_KMAX)
 * Out: r0 = 1 accepted, 0 refused (busy, or too deep)
 *--------------------------------------------------------------------*/
.global _bq_hr_request_n;
_bq_hr_request_n:
    r0 = dm(_bqhr_state);
    r0 = pass r0;
    if ne jump (pc, .bqhr_busy);
    r0 = 4;
    comp(r4, r0);
    if gt jump (pc, .bqhr_busy);
    r0 = 0;
    comp(r4, r0);
    if le jump (pc, .bqhr_busy);

    l0 = 0;
    l1 = 0;
    l2 = 0;
    dm(_bqhr_nl) = r4;
    r1 = r4 + r4;              /* two words a pair */
    i1 = _bqhr_list;
    lcntr = r1, do .bqhr_cpl until lce;
        r0 = dm(i0, 1);
    .bqhr_cpl: dm(i1, 1) = r0;
    r0 = dm(_bqhr_list);
    dm(_bqhr_key) = r0;        /* the first block is the job's key */
    r0 = 0;
    dm(_bqhr_li) = r0;
    call _bqhr_job_start;
    r0 = 1;
    dm(_bqhr_state) = r0;
    rts;

.bqhr_busy:
    r0 = 0;
    rts;
_bq_hr_request_n.end:

/*----------------------------------------------------------------------
 * _bqhr_job_start — set up the list entry _bqhr_li: de-quantise its
 * stages, pick N, lay down the impulse, and start on stage 0.
 *--------------------------------------------------------------------*/
_bqhr_job_start:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    r0 = dm(_bqhr_li);
    r0 = r0 + r0;
    i0 = _bqhr_list;
    m0 = r0;
    modify(i0, m0);
    r0 = dm(i0, 1);            /* block base */
    r4 = dm(i0, 0);            /* stages */
    dm(_bqhr_blk) = r0;
    r1 = BQHR_KMAX;
    r4 = min(r4, r1);
    dm(_bqhr_k) = r4;
    i0 = r0;
    modify(i0, 1);             /* step past the header word */

    /* ---- de-quantise every stage, and take each one's 1-r ---- */
    i1 = _bqhr_cf;
    i2 = _bqhr_u;
    r12 = 0x3F800000;          /* 1.0f, kept for the whole loop */
    r14 = 0x3F800000;
    f14 = r14;                 /* umin = 1.0 (r = 0) so far */

    lcntr = r4, do .bqhr_cvt until lce;
        r0 = dm(i0, 1);        /* b0q  Q4.28 */
        r1 = dm(i0, 1);        /* nhq  = n1/2 in Q4.28 */
        r2 = dm(i0, 1);        /* n2q  Q4.28 */
        r3 = dm(i0, 1);        /* c1q  Q4.28 */
        r4 = dm(i0, 1);        /* c2q  Q4.28 */

        r15 = -28;
        f5 = float r0 by r15;  /* b0 */
        r15 = -27;
        f6 = float r1 by r15;  /* n1 = 2 * from_q(nh) */
        r15 = -28;
        f7 = float r2 by r15;  /* from_q(n2) */
        f8 = float r3 by r15;  /* from_q(c1) */
        f9 = float r4 by r15;  /* from_q(c2) */

        f10 = f5 + f5;         /* 2*b0 */
        f6 = f6 - f10;         /* b1 = n1 - 2*b0 */
        f7 = f7 + f5;          /* b2 = n2 + b0 */
        r15 = 0x40000000;      /* 2.0f */
        f10 = r15;
        f8 = f8 - f10;         /* a1 = c1 - 2 */
        f11 = r12;             /* 1.0f */
        f9 = f11 - f9;         /* a2 = 1 - c2 */

        dm(i1, 1) = f5;
        dm(i1, 1) = f6;
        dm(i1, 1) = f7;
        dm(i1, 1) = f8;
        dm(i1, 1) = f9;

        /* ---- 1 - r for THIS stage, in the cancellation-free form ----
         * Complex pair (disc <= 0):  r = sqrt(a2),
         *     1 - r = (1 - a2) / (1 + r)
         * Real roots:  1 - r_max is the SMALLER root of
         *     t^2 - (2+a1) t + (1+a1+a2), i.e.
         *     1 - r = 2(1+a1+a2) / ((2+a1) + sqrt(disc))
         * Both avoid subtracting two numbers that are nearly equal,
         * which is the whole game when r = 1 - 6.5e-5 and the tail term
         * divides by 1 - r. */
        f0 = f8 * f8;
        f1 = f9 + f9;
        f1 = f1 + f1;          /* 4*a2 */
        f0 = f0 - f1;          /* disc = a1^2 - 4*a2 */
        r1 = 0;
        f1 = r1;
        comp(f0, f1);
        if gt jump (pc, .bqhr_real);

        /* complex pair */
        f0 = abs f9;           /* |a2| */
        dm(_bqhr_t0) = f8;     /* park a1/a2 across the helper */
        dm(_bqhr_t1) = f9;
        call _bqhr_sqrt;       /* f0 = r */
        f8 = dm(_bqhr_t0);
        f9 = dm(_bqhr_t1);
        f2 = r12;              /* 1.0f */
        f1 = f2 + f0;          /* 1 + r */
        f0 = f2 - f9;          /* 1 - a2 */
        dm(_bqhr_t2) = f0;     /* numerator */
        f0 = pass f1;
        call _bqhr_recip;      /* f0 = 1/(1+r) */
        f1 = dm(_bqhr_t2);
        f0 = f0 * f1;          /* 1 - r */
        jump (pc, .bqhr_uok);

    .bqhr_real:
        dm(_bqhr_t0) = f8;
        dm(_bqhr_t1) = f9;
        call _bqhr_sqrt;       /* f0 = sqrt(disc) */
        f8 = dm(_bqhr_t0);
        f9 = dm(_bqhr_t1);
        f2 = r12;              /* 1.0f */
        f1 = f2 + f2;          /* 2.0f */
        f1 = f1 + f8;          /* 2 + a1 */
        f0 = f0 + f1;          /* (2+a1) + sqrt(disc) */
        f1 = f2 + f8;
        f1 = f1 + f9;          /* 1 + a1 + a2 */
        f1 = f1 + f1;          /* 2(1+a1+a2) */
        dm(_bqhr_t2) = f1;
        call _bqhr_recip;      /* f0 = 1/((2+a1)+sqrt(disc)) */
        f1 = dm(_bqhr_t2);
        f0 = f0 * f1;          /* 1 - r */

    .bqhr_uok:
        /* clamp 1-r into (1e-6, 1] so a marginal design cannot divide by
         * zero; 1e-6 is 20 bits of tail, far past HMAX. */
        r1 = 0x358637BD;       /* 1e-6f */
        f1 = r1;
        f0 = max(f0, f1);
        f1 = r12;              /* 1.0f */
        f0 = min(f0, f1);
        dm(i2, 1) = f0;
        f14 = min(f14, f0);    /* umin over the whole cascade */
    .bqhr_cvt:
        nop;

    /* ---- N = clamp(ceil(6/umin), NMIN, NMAX) ---- */
    f0 = pass f14;
    call _bqhr_recip;          /* 1/umin */
    r1 = 0x40C00000;           /* 6.0f */
    f1 = r1;
    f0 = f0 * f1;
    r0 = fix f0;               /* truncates; the clamp makes it moot */
    r1 = BQHR_NMIN;
    r0 = max(r0, r1);
    r1 = BQHR_NMAX;
    r0 = min(r0, r1);
    dm(_bqhr_N) = r0;
    r0 = lshift r0 by -1;
    dm(_bqhr_half) = r0;

    /* ---- the impulse: sig[0] = 1.0, the rest zero ---- */
    i1 = _bqhr_sig;
    r0 = dm(_bqhr_N);
    r1 = 0;
    lcntr = r0, do .bqhr_zs until lce;
    .bqhr_zs: dm(i1, 1) = r1;
    r1 = 0x3F800000;           /* 1.0f */
    dm(_bqhr_sig) = r1;

    /* ---- start on stage 0 ---- */
    r0 = 0;
    dm(_bqhr_j) = r0;
    dm(_bqhr_n) = r0;
    f0 = r0;
    dm(_bqhr_worst) = f0;
    r1 = 0x3F800000;
    f1 = r1;
    dm(_bqhr_umin) = f1;       /* prefix 1-r starts at 1.0 */
    call _bqhr_stage_init;
    rts;
_bqhr_job_start.end:

/*----------------------------------------------------------------------
 * _bqhr_stage_init — fold stage j's pole radius into the prefix, clear
 * the per-prefix accumulators and state.
 *--------------------------------------------------------------------*/
_bqhr_stage_init:
    l1 = 0;
    r0 = dm(_bqhr_j);
    i1 = _bqhr_u;
    m1 = r0;
    modify(i1, m1);
    f0 = dm(i1, 0);            /* this stage's 1-r */
    f1 = dm(_bqhr_umin);
    f0 = min(f0, f1);          /* the prefix is as slow as its slowest */
    dm(_bqhr_umin) = f0;
    r1 = 0x3F800000;
    f1 = r1;
    f2 = f1 - f0;              /* r = 1 - u */
    dm(_bqhr_r) = f2;
    f0 = pass f0;
    call _bqhr_recip;          /* 1/u */
    f2 = dm(_bqhr_r);
    f0 = f0 * f2;              /* gn = r/(1-r) */
    dm(_bqhr_gn) = f0;
    r0 = 0;
    f0 = r0;
    dm(_bqhr_tot) = f0;
    dm(_bqhr_env) = f0;
    dm(_bqhr_x1) = f0;
    dm(_bqhr_x2) = f0;
    dm(_bqhr_y1) = f0;
    dm(_bqhr_y2) = f0;
    dm(_bqhr_n) = r0;
    rts;
_bqhr_stage_init.end:

/*----------------------------------------------------------------------
 * _bq_hr_service — run up to DSP4_BQHR_BUDGET samples of the current
 * stage. Main-loop context; returns at once when idle or finished.
 *--------------------------------------------------------------------*/
.global _bq_hr_service;
_bq_hr_service:
    r0 = dm(_bqhr_state);
    r1 = 1;
    comp(r0, r1);
    if ne rts;

    r0 = dm(_bqhr_calls);
    r0 = r0 + 1;
    dm(_bqhr_calls) = r0;

    l0 = 0;
    l1 = 0;
    l2 = 0;

    /* Samples this pass = min(BUDGET, N - n), and NEVER ACROSS N/2.
     * The env warm-up is done by RESETTING env at the half boundary
     * rather than by testing n inside the sample loop: a conditional
     * jump three instructions from the end of a hardware loop is exactly
     * the restriction the house rules avoid, and a branch-free body is
     * four instructions shorter besides. Stopping a pass on the boundary
     * is what makes the reset land in the right place. */
    r0 = dm(_bqhr_N);
    r1 = dm(_bqhr_n);
    r2 = r0 - r1;
    r3 = DSP4_BQHR_BUDGET;
    r2 = min(r2, r3);
    r10 = dm(_bqhr_half);
    r3 = r10 - r1;             /* samples left before the boundary */
    r3 = pass r3;
    if le jump (pc, .bqhr_nohalf);
    r2 = min(r2, r3);
.bqhr_nohalf:
    r2 = pass r2;
    if le jump (pc, .bqhr_stage_end);

    /* coefficients of stage j */
    r0 = dm(_bqhr_j);
    r3 = r0 + r0;
    r3 = r3 + r3;
    r3 = r3 + r0;              /* 5*j */
    i0 = _bqhr_cf;
    m0 = r3;
    modify(i0, m0);
    f4 = dm(i0, 1);            /* b0 */
    f5 = dm(i0, 1);            /* b1 */
    f6 = dm(i0, 1);            /* b2 */
    f7 = dm(i0, 1);            /* a1 */
    f8 = dm(i0, 0);            /* a2 */

    /* state and accumulators */
    f9  = dm(_bqhr_x1);
    f10 = dm(_bqhr_x2);
    f11 = dm(_bqhr_y1);
    f12 = dm(_bqhr_y2);
    f13 = dm(_bqhr_tot);
    f14 = dm(_bqhr_env);
    f15 = dm(_bqhr_r);

    /* The run position: one pointer, read then written in place.
     * WHERE THE PASS ENDS IS WRITTEN NOW, not carried in a register --
     * the sample loop uses ALL SIXTEEN (x, y, two temporaries, five
     * coefficients, four state words, the sum, the envelope and r), so
     * there is no register to keep it in. */
    i1 = _bqhr_sig;
    m1 = r1;
    modify(i1, m1);            /* i1 -> sig[n] */
    r0 = r1 + r2;
    dm(_bqhr_n) = r0;          /* where this pass ends */

    lcntr = r2, do .bqhr_samp until lce;
        f0 = dm(i1, 0);        /* x */
        f1 = f4 * f0;
        f2 = f5 * f9;
        f1 = f1 + f2;
        f2 = f6 * f10;
        f1 = f1 + f2;
        f2 = f7 * f11;
        f1 = f1 - f2;
        f2 = f8 * f12;
        f1 = f1 - f2;          /* y */
        f10 = pass f9;         /* x2' = x1 */
        f9 = pass f0;          /* x1' = x  */
        f12 = pass f11;        /* y2' = y1 */
        f11 = pass f1;         /* y1' = y  */
        f2 = abs f1;
        f13 = f13 + f2;        /* tot += |y| */
        f3 = f14 * f15;        /* env * r, the decay */
        f14 = max(f3, f2);     /* the peak hold */
    .bqhr_samp:
        dm(i1, 1) = f1;        /* the prefix response, in place */

    dm(_bqhr_x1) = f9;
    dm(_bqhr_x2) = f10;
    dm(_bqhr_y1) = f11;
    dm(_bqhr_y2) = f12;
    dm(_bqhr_tot) = f13;

    /* env is held from N/2 on, and the way it is held from N/2 is that
     * everything before N/2 is thrown away here -- which is why a pass
     * is never allowed to run across the boundary. */
    r2 = dm(_bqhr_n);
    r0 = dm(_bqhr_half);
    comp(r2, r0);
    if ne jump (pc, .bqhr_keepenv);
    r1 = 0;
    f14 = r1;
.bqhr_keepenv:
    dm(_bqhr_env) = f14;

    r0 = dm(_bqhr_N);
    comp(r2, r0);
    if lt rts;

.bqhr_stage_end:
    /* ---- this prefix is done: fold its bound into the worst ---- */
    f0 = dm(_bqhr_env);
    f1 = dm(_bqhr_gn);
    f0 = f0 * f1;
    f1 = dm(_bqhr_tot);
    f0 = f0 + f1;              /* tot + env*r/(1-r) */
    f1 = dm(_bqhr_worst);
    f0 = max(f0, f1);
    dm(_bqhr_worst) = f0;

    r0 = dm(_bqhr_j);
    r0 = r0 + 1;
    dm(_bqhr_j) = r0;
    r1 = dm(_bqhr_k);
    comp(r0, r1);
    if lt jump (pc, .bqhr_next);

    /* ---- the whole cascade is sized: H, and the header word ----
     * H = ceil(log2(worst * 1.125 / 8)), floored at 0, capped at 12.
     * ceil(log2()) comes straight out of the IEEE fields: for
     * v = 1.m * 2^e, log2(v) is in [e, e+1), so the ceiling is e when
     * the mantissa is exactly 1 and e+1 otherwise. */
    f0 = dm(_bqhr_worst);
    r1 = 0x3E000000;           /* 0.125f */
    f1 = r1;
    f1 = f0 * f1;
    f0 = f0 + f1;              /* * 1.125, the safety factor */
    /* r0 and f0 are the same register: the IEEE fields are already there */
    r1 = lshift r0 by -23;
    r2 = 0xFF;
    r1 = r1 and r2;            /* biased exponent */
    r2 = 130;                  /* 127 bias, plus the 3 of the /8 */
    r1 = r1 - r2;              /* e - 3 */
    r2 = 0x007FFFFF;
    r0 = r0 and r2;            /* mantissa bits */
    r0 = pass r0;
    if ne r1 = r1 + 1;         /* not a power of two: round up */
    r2 = 0;
    r1 = max(r1, r2);
    r2 = 12;                   /* HMAX: 12 bits is 72 dB */
    r1 = min(r1, r2);
    dm(_bqhr_lasth) = r1;
    r0 = dm(_bqhr_blk);
    i0 = r0;
    l0 = 0;
    dm(i0, 0) = r1;            /* THE HEADER WORD */
    r0 = dm(_bqhr_jobs);
    r0 = r0 + 1;
    dm(_bqhr_jobs) = r0;

    /* next section of this node, if it has one */
    r0 = dm(_bqhr_li);
    r0 = r0 + 1;
    dm(_bqhr_li) = r0;
    r1 = dm(_bqhr_nl);
    comp(r0, r1);
    if ge jump (pc, .bqhr_alldone);
    call _bqhr_job_start;
    rts;
.bqhr_alldone:
    r0 = 2;
    dm(_bqhr_state) = r0;      /* done; the node's poll releases it */
    rts;

.bqhr_next:
    call _bqhr_stage_init;
    rts;
_bq_hr_service.end:

/*======================================================================
 * THE NODE SIDE, IN ONE PLACE.
 *
 * The sizing hand-off is the same eight steps in every node that owns a
 * cascade -- pick the dormant instance, convert into it, ask the engine,
 * come back next block, ask again if it was busy, and only then let the
 * crossfade start. Inlined per node that was forty instructions in each
 * of a hundred and sixty nodes, and it OVERFLOWED sec_swco on chip 1 in
 * the profiling build. It is a subroutine for the same reason
 * _xfade_blend_core is one expression in the generator: the nodes should
 * not each carry their own copy of a sequence that has to be identical.
 *
 * The arguments are parked in DM because everything below clobbers the
 * register file -- _bq_fx_convert_N alone writes f0-f8 -- and because
 * this runs in main-loop context where there is nothing to race with.
 *====================================================================*/

.section/dm seg_dmda;
.var _bqhr_a_hrw;      /* &hrw   : 0 idle, 1 asked, 2 converted-and-asking */
.var _bqhr_a_hrl;      /* &hrl   : the (block, stages) list */
.var _bqhr_a_act;      /* &active */
.var _bqhr_a_ca;       /* coefficients, instance A */
.var _bqhr_a_cb;       /* coefficients, instance B */
.var _bqhr_a_sa;       /* state, instance A */
.var _bqhr_a_sb;       /* state, instance B */
.var _bqhr_a_nx;       /* the float staging block */
.var _bqhr_a_st;       /* stages */
.var _bqhr_a_dc;       /* the dormant coefficient block */
.var _bqhr_a_ds;       /* the dormant state block */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _bqhr_dormant — dc/ds = the instance the node is NOT running.
 *--------------------------------------------------------------------*/
_bqhr_dormant:
    l0 = 0;
    r0 = dm(_bqhr_a_act);
    i0 = r0;
    r0 = dm(i0, 0);
    r0 = pass r0;
    r1 = dm(_bqhr_a_cb);
    r2 = dm(_bqhr_a_ca);
    if ne r1 = pass r2;
    dm(_bqhr_a_dc) = r1;
    r0 = dm(_bqhr_a_act);
    i0 = r0;
    r0 = dm(i0, 0);
    r0 = pass r0;
    r1 = dm(_bqhr_a_sb);
    r2 = dm(_bqhr_a_sa);
    if ne r1 = pass r2;
    dm(_bqhr_a_ds) = r1;
    rts;
_bqhr_dormant.end:

/*----------------------------------------------------------------------
 * _bqhr_ask_core — put the dormant block to the engine and record what
 * came back. r0 = 0 always: the caller returns and comes back next block.
 *--------------------------------------------------------------------*/
_bqhr_ask_core:
    l0 = 0;
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r0 = dm(_bqhr_a_dc);
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_st);
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r4 = 1;
    call _bq_hr_request_n;
    r4 = 2;                    /* engine busy: ask again next block */
    r0 = pass r0;
    if ne r4 = r4 - 1;         /* accepted: wait on it */
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    dm(i0, 0) = r4;
    r0 = 0;
    rts;
_bqhr_ask_core.end:

/*----------------------------------------------------------------------
 * _bq_hr_ask — the bookkeeping half, for nodes that do their own
 * conversion (FILT converts one section or two, conditionally, on top of
 * a copy of the active instance).
 *
 * In:  r0 = &hrw, r1 = &hrl, r2 = &active, r3 = coeffs A, r4 = coeffs B,
 *      r5 = stages
 * Out: r0 = 1 the headroom is written and the caller may proceed,
 *      r0 = 0 the caller must return and be called again next block.
 * Clobbers r0-r15, f0-f15, i0-i2, m0-m2.
 *--------------------------------------------------------------------*/
.global _bq_hr_ask;
_bq_hr_ask:
    dm(_bqhr_a_hrw) = r0;
    dm(_bqhr_a_hrl) = r1;
    dm(_bqhr_a_act) = r2;
    dm(_bqhr_a_ca) = r3;
    dm(_bqhr_a_cb) = r4;
    dm(_bqhr_a_st) = r5;
    call _bqhr_dormant;
    l0 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    r0 = dm(i0, 0);
    r1 = 1;
    comp(r0, r1);
    if eq jump (pc, .bqhr_apoll);
    call _bqhr_ask_core;       /* 0 or 2: ask (again) */
    rts;
.bqhr_apoll:
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r0 = dm(i0, 0);
    call _bq_hr_poll;
    r0 = pass r0;
    if eq rts;                 /* not sized yet */
    r1 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    dm(i0, 0) = r1;
    r0 = 1;
    rts;
_bq_hr_ask.end:

/*----------------------------------------------------------------------
 * _bq_hr_ask2 — the same, for a node with TWO independent cascades on
 * one swap (CROSSOVER's LP and HP paths). One job, two list entries, so
 * the node waits once and the engine still runs one cascade at a time.
 *
 * In:  r0 = &hrw, r1 = &hrl, r2 = &active,
 *      r3 = cascade 1 A, r4 = cascade 1 B, r5 = stages 1,
 *      r6 = cascade 2 A, r7 = cascade 2 B, r8 = stages 2
 * Out: as _bq_hr_ask.
 *--------------------------------------------------------------------*/
.global _bq_hr_ask2;
_bq_hr_ask2:
    dm(_bqhr_a_hrw) = r0;
    dm(_bqhr_a_hrl) = r1;
    dm(_bqhr_a_act) = r2;
    dm(_bqhr_a_ca) = r3;
    dm(_bqhr_a_cb) = r4;
    dm(_bqhr_a_st) = r5;
    dm(_bqhr_a_sa) = r6;       /* cascade 2's A, parked in the state slot */
    dm(_bqhr_a_sb) = r7;
    dm(_bqhr_a_nx) = r8;       /* cascade 2's stage count */
    call _bqhr_dormant;
    r0 = dm(_bqhr_a_dc);
    dm(_bqhr_a_ds) = r0;       /* cascade 1's dormant block */
    /* cascade 2's dormant block, same active flag */
    r0 = dm(_bqhr_a_sa);
    dm(_bqhr_a_ca) = r0;
    r0 = dm(_bqhr_a_sb);
    dm(_bqhr_a_cb) = r0;
    call _bqhr_dormant;        /* leaves cascade 2's block in _bqhr_a_dc */

    l0 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    r0 = dm(i0, 0);
    r1 = 1;
    comp(r0, r1);
    if eq jump (pc, .bqhr_a2poll);

    /* build a two-entry list and ask */
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r0 = dm(_bqhr_a_ds);       /* cascade 1 */
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_st);
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_dc);       /* cascade 2 */
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_nx);
    dm(i0, 1) = r0;
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r4 = 2;
    call _bq_hr_request_n;
    r4 = 2;
    r0 = pass r0;
    if ne r4 = r4 - 1;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    dm(i0, 0) = r4;
    r0 = 0;
    rts;

.bqhr_a2poll:
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r0 = dm(i0, 0);
    call _bq_hr_poll;
    r0 = pass r0;
    if eq rts;
    r1 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    dm(i0, 0) = r1;
    r0 = 1;
    rts;
_bq_hr_ask2.end:

/*----------------------------------------------------------------------
 * _bq_hr_node1 — the whole hand-off for a node whose cascade is ONE
 * block converted in one go, which is every EQ, GEQ and AFB.
 *
 * In:  r0 = &hrw, r1 = &hrl, r2 = &active, r3 = coeffs A, r4 = coeffs B,
 *      r5 = state A, r6 = state B, r7 = float staging, r8 = stages
 * Out: r0 = 1 the headroom is written, i2 = the dormant STATE block (the
 *          pointer the caller's zeroing loop wants), caller proceeds;
 *      r0 = 0 caller must return.
 * Clobbers r0-r15, f0-f15, i0-i2, m0-m2.
 *--------------------------------------------------------------------*/
.global _bq_hr_node1;
_bq_hr_node1:
    dm(_bqhr_a_hrw) = r0;
    dm(_bqhr_a_hrl) = r1;
    dm(_bqhr_a_act) = r2;
    dm(_bqhr_a_ca) = r3;
    dm(_bqhr_a_cb) = r4;
    dm(_bqhr_a_sa) = r5;
    dm(_bqhr_a_sb) = r6;
    dm(_bqhr_a_nx) = r7;
    dm(_bqhr_a_st) = r8;
    call _bqhr_dormant;

    l0 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    r0 = dm(i0, 0);
    r0 = pass r0;
    if ne jump (pc, .bqhr_n1w);

    /* ---- state 0: convert the staged float set into the dormant
     * instance, past its header word, then ask ---- */
    l1 = 0;
    r0 = dm(_bqhr_a_nx);
    i0 = r0;
    r0 = dm(_bqhr_a_dc);
    i1 = r0;
    modify(i1, 1);             /* past the headroom header */
    r4 = dm(_bqhr_a_st);
    call _bq_fx_convert_N;
    call _bqhr_ask_core;
    rts;

.bqhr_n1w:
    r1 = 2;
    comp(r0, r1);
    if ne jump (pc, .bqhr_n1p);
    call _bqhr_ask_core;       /* converted already; the engine was busy */
    rts;

.bqhr_n1p:
    r0 = dm(_bqhr_a_hrl);
    i0 = r0;
    r0 = dm(i0, 0);
    call _bq_hr_poll;
    r0 = pass r0;
    if eq rts;                 /* not sized yet */
    r1 = 0;
    r0 = dm(_bqhr_a_hrw);
    i0 = r0;
    dm(i0, 0) = r1;
    l2 = 0;
    r0 = dm(_bqhr_a_ds);
    i2 = r0;                   /* the caller's zeroing loop wants this */
    r0 = 1;
    rts;
_bq_hr_node1.end:

/*----------------------------------------------------------------------
 * _bq_hr_poll — has this block's H been written?
 * In: r0 = coefficient block base.  Out: r0 = 1 (and the engine is
 * released) or 0.
 *--------------------------------------------------------------------*/
.global _bq_hr_poll;
_bq_hr_poll:
    r1 = dm(_bqhr_state);
    r2 = 2;
    comp(r1, r2);
    if ne jump (pc, .bqhr_notyet);
    r1 = dm(_bqhr_key);
    comp(r0, r1);
    if ne jump (pc, .bqhr_notyet);
    r1 = 0;
    dm(_bqhr_state) = r1;
    r0 = 1;
    rts;
.bqhr_notyet:
    r0 = 0;
    rts;
_bq_hr_poll.end:

#endif /* DSP4_BQ_GUARD */
