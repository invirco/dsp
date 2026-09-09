/*======================================================================
 * bq_probe.asm — THE PER-INSTRUCTION CYCLE PROBE (S14, 2026-09-09).
 *
 * SPIKE ONLY. Standalone rig, never in a shipping image, no graph
 * integration, no contract edit. Guarded on DSP4_BQ_PROBE.
 *
 * THE QUESTION. S13-6 pipelined the float SIMD biquad inner loop from
 * eight instructions per sample per stage to five, proved it bit-exact
 * (bqeverify 0 ULP, same hash), and the GEQ pair moved 5,983 -> 5,655
 * cycles/block: 5.5 % where the instruction count predicted 25 %. Both
 * loops run at about 1.4-1.5 cycles per instruction. The floor the 3.75
 * target was built on -- max(multiplies, ALU ops, memory moves) -- is
 * therefore WRONG, and S13's own conclusion was that the next step is to
 * MEASURE where the cycles go rather than schedule against an unmeasured
 * floor again.
 *
 * THERE IS NO DOCUMENT TO READ INSTEAD. The ADSP-2156x SHARC+ Hardware
 * Reference (Rev 1.0, Dec 2020) has no core-architecture chapter at all:
 * zero occurrences of "pipeline stage" or "Instruction Pipeline", and
 * every "stall" in its 101,300 lines is peripheral flow control (SPI
 * RDY, CRC, PKA, DMA FIFO). It states neither the core's pipeline depth
 * nor the number of cycles a compute result takes before a dependent
 * instruction may read it. The measurement below IS the stall rule for
 * this tree.
 *
 * THE METHOD is the shootout's: one timestamp pair either side of each
 * rung, the whole ladder run REPS times, the host takes the MINIMUM so a
 * pass a diag-tick ISR landed in is dropped, and rung 0 -- the loop with
 * a single nop in it -- is subtracted from nothing, because what this rig
 * reports is the DIFFERENCE between adjacent rungs and the loop nest is
 * identical in every one of them.
 *
 * EVERY RUNG RUNS THE SAME LOOP NEST as the kernel under test:
 *
 *     lcntr = PRB_STAGES, do outer until lce;
 *         <rung-specific outer body, usually just the pointer reset>
 *         lcntr = PRB_INNER, do inner until lce;
 *             <THE RUNG'S BODY -- the only thing that differs>
 *         inner: <last instruction of the body>
 *     outer: nop;
 *
 * PRB_INNER is DSP4_BLOCK_SIZE-1 = 15, which is exactly the pipelined
 * kernel's inner trip count, and PRB_STAGES is 28, the shootout's bank
 * depth. So a rung is 420 inner iterations per call and the ladder runs
 * each rung PRB_ITERS times, minimum of PRB_REPS passes.
 *
 * THE RUNGS, in four groups:
 *
 *   ISSUE RATE AND LOOP COST
 *     0  loop + 1 nop        1  loop + 3 nops
 *     2  loop + 5 nops       3  loop + 8 nops
 *   -> the slope names the nop issue rate; the intercept names what a
 *      15-trip hardware loop costs per iteration on top of its body.
 *
 *   THE PIPELINED BODY, ONE INSTRUCTION AT A TIME, IN SCHEDULE ORDER
 *     4  I1        5  I1-I2      6  I1-I3      7  I1-I4    8  I1-I5
 *   -> rung 8 IS the shipping pipelined loop's body. Each delta is the
 *      marginal cost of adding that instruction to the schedule in front
 *      of it, which is the thing S13 could not see.
 *
 *   WHAT THE COST IS MADE OF
 *     9  the same five instruction FORMS with EVERY data dependence
 *        broken -- same multiplier/ALU operand quadrants, same two
 *        memory moves, sources all loop-invariant. This is the pure
 *        issue cost of five instructions of this shape.
 *    10  rung 9 with the two memory moves deleted -> the DM cost.
 *    11  rung 9 with the store moved to PM        -> the DM-bus cost.
 *    12  four DEPENDENT float multiplies  13  four INDEPENDENT ditto
 *    14  four DEPENDENT float ALU ops     15  four INDEPENDENT ditto
 *    16  four alternating mul->ALU->mul->ALU dependences
 *   -> 12-16 name the result latency of each unit directly, in cycles,
 *      which is what the HRM does not say.
 *    17  rung 8 with PEYEN OFF -> what the SIMD pair costs.
 *
 *   THE OLD LOOP, AND THE STRUCTURE AROUND BOTH
 *    18  the OLD eight-instruction body, real dependences
 *    19  the OLD eight-instruction body, dependences broken
 *   -> S13 says the old loop runs at ~1.4 c/instruction too; 18 and 19
 *      check that it is the SAME cause and not a different one.
 *    20  rung 8's body in a 60-trip loop, 7 stages: identical total
 *        iterations, a quarter of the loop-backs -> short-loop cost.
 *    21  rung 8 plus the kernel's REAL per-stage prologue and epilogue
 *        -> the per-stage overhead term, so the probe reconciles against
 *        the 5,655 cycles/block the graph ladder measured.
 *
 * REGISTER SEEDS. Every float register is seeded to a value that keeps
 * the arithmetic bounded and OUT OF THE DENORMAL RANGE for the whole run
 * -- a probe that drifted into denormals would be measuring the denormal
 * path, not the loop. The coefficient seeds are a stable filter and the
 * dependent chains are algebraically closed (x*1.0, x+1.0-1.0).
 *
 * WAW IS NOT A DEPENDENCE. Rung 9 needs seven loop-invariant registers
 * and ten scratch destinations against the sixteen a PE has, so exactly
 * one destination (f1) is written twice and read never. That is a
 * write-after-write on an in-order machine that retires in order: it
 * cannot stall, and it is the only one in the rig.
 *======================================================================*/

#include "dsp_block.h"
#include "diag.h"

#if DSP4_BQ_PROBE

#define PRB_STAGES  28
#define PRB_INNER   (DSP4_BLOCK_SIZE - 1)
#define PRB_LSTAGES 7
#define PRB_LINNER  60
#define PRB_RUNGS   22
#define PRB_REPS    5
#define PRB_ITERS   32
#define PRB_BUF     128

.section/dm seg_dmda;

.global _prb_done;    .var _prb_done   = 0;
.global _prb_magic;   .var _prb_magic  = 0xD5B4C002;
.global _prb_iters;   .var _prb_iters  = PRB_ITERS;
.global _prb_reps;    .var _prb_reps   = PRB_REPS;
.global _prb_rungs;   .var _prb_rungs  = PRB_RUNGS;
.global _prb_stages;  .var _prb_stages = PRB_STAGES;
.global _prb_inner;   .var _prb_inner  = PRB_INNER;
.global _prb_tper;    .var _prb_tper   = DIAG_TPERIOD;
.global _prb_blk;     .var _prb_blk    = DSP4_BLOCK_SIZE;
.global _prb_tick;    .var _prb_tick[PRB_RUNGS * PRB_REPS * 4];

/* The ladder's own loop state lives in DM for bq_shootout.asm's measured
 * reason: a rung body owns the whole register file. */
.var _prb_rep;
.var _prb_tp;
.var _prb_m1[2];

.global _prb_src;   .var _prb_src[PRB_BUF];
.global _prb_dst;   .var _prb_dst[PRB_BUF];
.global _prb_coef;  .var _prb_coef[PRB_STAGES * 10];
.global _prb_st;    .var _prb_st[PRB_STAGES * 10];

/* Read as PAIRS: a direct-address DM access inside a PEYEN region takes
 * the word after the address for PEy. Same rule and same reason as
 * biquad_fx.asm's _bqfl_two / _bqfl_one. */
.var _prb_one[2] = 1.0, 1.0;
.var _prb_two[2] = 2.0, 2.0;
.var _prb_zero[2] = 0.0, 0.0;

/* The seeded filter: poles of z^2 + 0.5z + 0.25, modulus 0.5, so the
 * recursion in rungs 4-8 settles to y = x(b0+b1+b2)/(1+a1+a2) = 0.5 and
 * stays there for all 13,440 iterations -- bounded, and nowhere near the
 * denormal range. A probe that drifted into denormals would be timing
 * the denormal path instead of the loop. */
.var _prb_b0[2] = 0.5,   0.5;
.var _prb_b1[2] = 0.25,  0.25;
.var _prb_b2[2] = 0.125, 0.125;
.var _prb_a1[2] = 0.5,   0.5;
.var _prb_a2[2] = 0.25,  0.25;

.section/dm seg_pmda;
/* The PM-resident store target for rung 11. seg_pmda maps into
 * mem_block2_bw, a DIFFERENT block from seg_dmda's block 0/1 -- which is
 * the whole point of the rung. */
.global _prb_pdst;  .var _prb_pdst[PRB_BUF];

.section/pm seg_pmco;
.extern _diag_ticks;

#define PRB_T   r3 = dm(_prb_tp); i5 = r3; l5 = 0; \
                r2 = tcount; r0 = dm(_diag_ticks); \
                dm(i5,1) = r0; dm(i5,1) = r2; \
                r3 = i5; dm(_prb_tp) = r3;

/*----------------------------------------------------------------------
 * PRB_SEED — every register the rungs read, set to a bounded value.
 *
 *   f0  x        = 1.0        f4  b0 = 0.5    f5  b1 = 0.25
 *   f1  y                     f6  b2 = 0.125  f7  a1 = 0.5
 *   f2  a2 = 0.25             f3  = 1.0 (spare invariant)
 *   f8  w1 = 0.0   f9 = 0.0   f10 w2 = 0.0    f11 = 1.0
 *   f12 = 1.0      f13 = 0.0  f14 = 0.0       f15 = 0.0
 *
 * a1 = 0.5 and a2 = 0.25 give poles well inside the unit circle, so the
 * recursion in rungs 4-8 converges to a bounded DC value instead of
 * ringing up into infinity or decaying into denormals over 13,440
 * iterations. f11 and f12 are the ALU quadrant invariants rung 9 needs
 * (ALU X from R8-R11, ALU Y from R12-R15).
 *--------------------------------------------------------------------*/
#define PRB_SEED \
    f0  = dm(_prb_one);   f3 = pass f0;  f11 = pass f0;  f12 = pass f0; \
    f4  = dm(_prb_b0);    f5 = dm(_prb_b1);   f6  = dm(_prb_b2); \
    f7  = dm(_prb_a1);    f2 = dm(_prb_a2); \
    f8  = dm(_prb_zero);  f9 = pass f8;  f10 = pass f8;  f13 = pass f8; \
    f14 = pass f8;        f15 = pass f8; f1  = pass f8;

/*----------------------------------------------------------------------
 * _prb_selftest — the ladder.
 *--------------------------------------------------------------------*/
.global _prb_selftest;
_prb_selftest:
    r0 = _prb_tick;
    dm(_prb_tp) = r0;
    r0 = 0;
    dm(_prb_rep) = r0;

.prb_rep:

    /*==== GROUP 1: issue rate and the cost of the loop nest ==========*/

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r0 until lce;
        call _prb_nop2;
        nop;
    .prb_r0: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r1 until lce;
        call _prb_nop3;
        nop;
    .prb_r1: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r2 until lce;
        call _prb_nop5;
        nop;
    .prb_r2: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r3 until lce;
        call _prb_nop8;
        nop;
    .prb_r3: nop;
    PRB_T

    /*==== GROUP 2: the pipelined body, one instruction at a time =====*/

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r4 until lce;
        call _prb_p1;
        nop;
    .prb_r4: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r5 until lce;
        call _prb_p2;
        nop;
    .prb_r5: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r6 until lce;
        call _prb_p3;
        nop;
    .prb_r6: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r7 until lce;
        call _prb_p4;
        nop;
    .prb_r7: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r8 until lce;
        call _prb_p5;
        nop;
    .prb_r8: nop;
    PRB_T

    /*==== GROUP 3: what the cost is made of ==========================*/

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r9 until lce;
        call _prb_free;
        nop;
    .prb_r9: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r10 until lce;
        call _prb_free_nomem;
        nop;
    .prb_r10: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r11 until lce;
        call _prb_free_pm;
        nop;
    .prb_r11: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r12 until lce;
        call _prb_mul_dep;
        nop;
    .prb_r12: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r13 until lce;
        call _prb_mul_ind;
        nop;
    .prb_r13: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r14 until lce;
        call _prb_alu_dep;
        nop;
    .prb_r14: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r15 until lce;
        call _prb_alu_ind;
        nop;
    .prb_r15: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r16 until lce;
        call _prb_mix_dep;
        nop;
    .prb_r16: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r17 until lce;
        call _prb_p5_scalar;
        nop;
    .prb_r17: nop;
    PRB_T

    /*==== GROUP 4: the old loop, and the structure around both =======*/

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r18 until lce;
        call _prb_old8;
        nop;
    .prb_r18: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r19 until lce;
        call _prb_old8_free;
        nop;
    .prb_r19: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r20 until lce;
        call _prb_p5_long;
        nop;
    .prb_r20: nop;
    PRB_T

    PRB_T
    r10 = dm(_prb_iters);
    lcntr = r10, do .prb_r21 until lce;
        call _prb_p5_stage;
        nop;
    .prb_r21: nop;
    PRB_T

    r0 = dm(_prb_rep);
    r1 = 1;
    r0 = r0 + r1;
    dm(_prb_rep) = r0;
    r1 = PRB_REPS;
    comp(r0, r1);
    if lt jump (pc, .prb_rep);

    r0 = 1;
    dm(_prb_done) = r0;
    rts;
_prb_selftest.end:

/*======================================================================
 * THE RUNG BODIES.
 *
 * Every one of them: seed the registers, raise PEYEN (except rung 17),
 * run the nest, drop PEYEN. MODE1 is saved and restored WHOLE and
 * interrupts are NOT masked -- the systemic per-ISR PEYEN clear is what
 * makes that safe, and it is the same discipline every SIMD kernel in
 * this tree relies on. Masking IRPTEN here is what hung the part on
 * 2026-08-28.
 *====================================================================*/

#define PRB_PROLOGUE \
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; \
    r15 = mode1; \
    dm(_prb_m1) = r15; \
    dm(_prb_m1 + 1) = r15; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    PRB_SEED

#define PRB_PROLOGUE_SCALAR \
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; \
    r15 = mode1; \
    dm(_prb_m1) = r15; \
    dm(_prb_m1 + 1) = r15; \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    PRB_SEED

#define PRB_EPILOGUE \
    r15 = dm(_prb_m1); \
    mode1 = r15; \
    nop; \
    nop; \
    rts;

/* The pointer reset that opens every outer iteration. Two instructions,
 * present in EVERY rung including the nop rungs' equivalents, so it
 * cancels in the deltas that matter. */
#define PRB_PTRS \
    i2 = _prb_src; \
    i3 = _prb_dst;

/* ---- rungs 0-3: the nest itself, with 2, 3, 5 and 8 nops in the inner
 * body. Same subroutine shape, same prologue, same PRB_PTRS in the outer
 * body as every compute rung, so rung 8 - rung 0 is as clean a delta as
 * rung 8 - rung 7. The slope over (2,3,5,8) names the issue rate of an
 * instruction that cannot stall; the intercept names the loop nest. ---- */

.global _prb_nop2;
_prb_nop2:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_n2o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_n2i until lce;
            nop;
        .prb_n2i: nop;
    .prb_n2o: nop;
    PRB_EPILOGUE
_prb_nop2.end:

.global _prb_nop3;
_prb_nop3:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_n3o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_n3i until lce;
            nop; nop;
        .prb_n3i: nop;
    .prb_n3o: nop;
    PRB_EPILOGUE
_prb_nop3.end:

.global _prb_nop5;
_prb_nop5:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_n5o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_n5i until lce;
            nop; nop; nop; nop;
        .prb_n5i: nop;
    .prb_n5o: nop;
    PRB_EPILOGUE
_prb_nop5.end:

.global _prb_nop8;
_prb_nop8:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_n8o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_n8i until lce;
            nop; nop; nop; nop; nop; nop; nop;
        .prb_n8i: nop;
    .prb_n8o: nop;
    PRB_EPILOGUE
_prb_nop8.end:

/* ---- rungs 4-8: the pipelined body, built up one instruction at a
 * time, in schedule order. Rung 8 is biquad_fx.asm's .bqfl_psamp body
 * verbatim. ---- */

.global _prb_p1;
_prb_p1:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_p1o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_p1i until lce;
        .prb_p1i: f12 = f0 * f4, f10 = f9 - f15;
    .prb_p1o: nop;
    PRB_EPILOGUE
_prb_p1.end:

.global _prb_p2;
_prb_p2:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_p2o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_p2i until lce;
            f12 = f0 * f4, f10 = f9 - f15;
        .prb_p2i: f13 = f0 * f5, f1 = f8 + f12;
    .prb_p2o: nop;
    PRB_EPILOGUE
_prb_p2.end:

.global _prb_p3;
_prb_p3:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_p3o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_p3i until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
        .prb_p3i: f14 = f1 * f7, f11 = f10 + f13;
    .prb_p3o: nop;
    PRB_EPILOGUE
_prb_p3.end:

.global _prb_p4;
_prb_p4:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_p4o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_p4i until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
            f14 = f1 * f7, f11 = f10 + f13;
        .prb_p4i: f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
    .prb_p4o: nop;
    PRB_EPILOGUE
_prb_p4.end:

.global _prb_p5;
_prb_p5:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_p5o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_p5i until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
            f14 = f1 * f7, f11 = f10 + f13;
            f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
        .prb_p5i: f15 = f2 * f1, f0 = dm(i2, 2);
    .prb_p5o: nop;
    PRB_EPILOGUE
_prb_p5.end:

/* ---- rung 17: the same body with PEYEN DOWN. One PE, same five
 * instructions, same two memory moves at half the width. ---- */
.global _prb_p5_scalar;
_prb_p5_scalar:
    PRB_PROLOGUE_SCALAR
    lcntr = PRB_STAGES, do .prb_pso until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_psi until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
            f14 = f1 * f7, f11 = f10 + f13;
            f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
        .prb_psi: f15 = f2 * f1, f0 = dm(i2, 2);
    .prb_pso: nop;
    PRB_EPILOGUE
_prb_p5_scalar.end:

/* ---- rung 20: the same body, 7 outer x 60 inner = the same 420 inner
 * iterations, a quarter of the loop-backs and a quarter of the outer
 * bodies. Whatever a short hardware loop costs shows up here. ---- */
.global _prb_p5_long;
_prb_p5_long:
    PRB_PROLOGUE
    lcntr = PRB_LSTAGES, do .prb_plo until lce;
        PRB_PTRS
        lcntr = PRB_LINNER, do .prb_pli until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
            f14 = f1 * f7, f11 = f10 + f13;
            f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
        .prb_pli: f15 = f2 * f1, f0 = dm(i2, 2);
    .prb_plo: nop;
    PRB_EPILOGUE
_prb_p5_long.end:

/* ---- rung 21: the body PLUS the kernel's real per-stage prologue,
 * pipeline preamble, peeled last sample and state write-back. This is
 * biquad_fx.asm's whole .bqfl_sstage body, so rung 21 - rung 8 is the
 * per-stage overhead the graph ladder's 5,655 c/blk contains and the
 * inner loop does not. ---- */
.global _prb_p5_stage;
_prb_p5_stage:
    PRB_PROLOGUE
    r15 = 10;
    m3 = r15;
    i0 = _prb_coef;
    i1 = _prb_st;
    lcntr = PRB_STAGES, do .prb_pgo until lce;
        PRB_PTRS
        /* the real coefficient load and offset reconstruction */
        f4 = dm(i0, 2);
        f5 = dm(i0, 2);
        f6 = dm(i0, 2);
        f7 = dm(i0, 2);
        f2 = dm(i0, 2);
        f3 = f4 + f4;
        f5 = f5 - f3;
        f6 = f6 + f4;
        f3 = dm(_prb_two);
        f7 = f7 - f3;
        f3 = dm(_prb_one);
        f2 = f3 - f2;
        f8  = dm(i1, 2);
        f10 = dm(i1, 0);
        /* the pipeline preamble */
        i3 = i2;
        f0 = dm(i2, 2);
        f9 = pass f10;
        r15 = 0;
        lcntr = PRB_INNER, do .prb_pgi until lce;
            f12 = f0 * f4, f10 = f9 - f15;
            f13 = f0 * f5, f1 = f8 + f12;
            f14 = f1 * f7, f11 = f10 + f13;
            f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
        .prb_pgi: f15 = f2 * f1, f0 = dm(i2, 2);
        /* the peeled last sample */
        f12 = f0 * f4, f10 = f9 - f15;
        f13 = f0 * f5, f1 = f8 + f12;
        f14 = f1 * f7, f11 = f10 + f13;
        f9 = f0 * f6, f8 = f11 - f14, dm(i3, 2) = f1;
        f15 = f2 * f1;
        f10 = f9 - f15;
        /* the state write-back and the stage advance */
        dm(i1, -2) = f10;
        dm(i1, 2)  = f8;
        modify(i1, m3);
    .prb_pgo: nop;
    PRB_EPILOGUE
_prb_p5_stage.end:

/* ---- rung 9: THE SAME FIVE INSTRUCTION FORMS, EVERY DEPENDENCE
 * BROKEN. Multiplier X from R0-R3 and Y from R4-R7, ALU X from R8-R11
 * and Y from R12-R15, exactly as above; both memory moves kept. Sources
 * are the invariants f0, f4-f7, f11, f12 only. f1 is written by I2 and
 * by I5 and read by nothing: write-after-write, which an in-order
 * machine cannot stall on, and it is the only one in the rig. ---- */
.global _prb_free;
_prb_free:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_fro until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_fri until lce;
            f8  = f0 * f4, f13 = f11 - f12;
            f9  = f0 * f5, f2  = f11 + f12;
            f10 = f0 * f7, f3  = f11 + f12;
            f13 = f0 * f6, f14 = f11 - f12, dm(i3, 2) = f11;
        .prb_fri: f15 = f0 * f0, f1 = dm(i2, 2);
    .prb_fro: nop;
    PRB_EPILOGUE
_prb_free.end:

/* ---- rung 10: rung 9 with the two memory moves deleted. ---- */
.global _prb_free_nomem;
_prb_free_nomem:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_fno until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_fni until lce;
            f8  = f0 * f4, f13 = f11 - f12;
            f9  = f0 * f5, f2  = f11 + f12;
            f10 = f0 * f7, f3  = f11 + f12;
            f13 = f0 * f6, f14 = f11 - f12;
        .prb_fni: f15 = f0 * f0;
    .prb_fno: nop;
    PRB_EPILOGUE
_prb_free_nomem.end:

/* ---- rung 11: rung 9 with the STORE moved to PM. seg_pmda lives in
 * memory block 2 and seg_dmda in blocks 0/1, so this rung reads and
 * writes two different blocks where rung 9 reads and writes one. ---- */
.global _prb_free_pm;
_prb_free_pm:
    PRB_PROLOGUE
    i8 = _prb_pdst;
    l8 = 0;
    lcntr = PRB_STAGES, do .prb_fpo until lce;
        PRB_PTRS
        i8 = _prb_pdst;
        lcntr = PRB_INNER, do .prb_fpi until lce;
            f8  = f0 * f4, f13 = f11 - f12;
            f9  = f0 * f5, f2  = f11 + f12;
            f10 = f0 * f7, f3  = f11 + f12;
            f13 = f0 * f6, f14 = f11 - f12, pm(i8, 2) = f11;
        .prb_fpi: f15 = f0 * f0, f1 = dm(i2, 2);
    .prb_fpo: nop;
    PRB_EPILOGUE
_prb_free_pm.end:

/* ---- rungs 12-16: the raw result latencies. Four operations per
 * iteration in every one of them, so the four are directly comparable;
 * the dependent versions carry their chain across the loop back-edge as
 * well, which is what the biquad's recurrence does. Every chain is
 * algebraically closed at 1.0 so nothing drifts. ---- */

.global _prb_mul_dep;
_prb_mul_dep:
    PRB_PROLOGUE
    f4 = dm(_prb_one);              /* the chain multiplies by 1.0 */
    lcntr = PRB_STAGES, do .prb_mdo until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_mdi until lce;
            f1 = f0 * f4;
            f2 = f1 * f4;
            f3 = f2 * f4;
        .prb_mdi: f0 = f3 * f4;
    .prb_mdo: nop;
    PRB_EPILOGUE
_prb_mul_dep.end:

.global _prb_mul_ind;
_prb_mul_ind:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_mio until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_mii until lce;
            f1 = f0 * f4;
            f2 = f0 * f5;
            f3 = f0 * f6;
        .prb_mii: f13 = f0 * f7;
    .prb_mio: nop;
    PRB_EPILOGUE
_prb_mul_ind.end:

.global _prb_alu_dep;
_prb_alu_dep:
    PRB_PROLOGUE
    f4 = dm(_prb_one);
    lcntr = PRB_STAGES, do .prb_ado until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_adi until lce;
            f1 = f0 + f4;
            f2 = f1 - f4;
            f3 = f2 + f4;
        .prb_adi: f0 = f3 - f4;
    .prb_ado: nop;
    PRB_EPILOGUE
_prb_alu_dep.end:

.global _prb_alu_ind;
_prb_alu_ind:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_aio until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_aii until lce;
            f1 = f0 + f4;
            f2 = f0 - f5;
            f3 = f0 + f6;
        .prb_aii: f13 = f0 - f7;
    .prb_aio: nop;
    PRB_EPILOGUE
_prb_alu_ind.end:

/* multiply -> ALU -> multiply -> ALU, every edge a real dependence. */
.global _prb_mix_dep;
_prb_mix_dep:
    PRB_PROLOGUE
    f4 = dm(_prb_one);
    lcntr = PRB_STAGES, do .prb_xdo until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_xdi until lce;
            f1 = f0 * f4;
            f2 = f1 + f4;
            f3 = f2 * f4;
        .prb_xdi: f0 = f3 - f4;
    .prb_xdo: nop;
    PRB_EPILOGUE
_prb_mix_dep.end:

/* ---- rungs 18-19: the OLD eight-instruction loop, biquad_fx.asm's
 * .bqfl_ssamp body verbatim, and the same eight instruction forms with
 * every dependence broken. If the old loop's cost has the same cause,
 * rung 18 - rung 19 and rung 8 - rung 9 tell the same story. ---- */
.global _prb_old8;
_prb_old8:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_o8o until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_o8i until lce;
            f0 = dm(i2, 0);
            f12 = f0 * f4;
            f13 = f0 * f5, f1 = f8 + f12;
            f9  = f0 * f6, f11 = f10 + f13;
            f14 = f1 * f7;
            f15 = f2 * f1;
            f8 = f11 - f14;
        .prb_o8i: f10 = f9 - f15, dm(i2, 2) = f1;
    .prb_o8o: nop;
    PRB_EPILOGUE
_prb_old8.end:

.global _prb_old8_free;
_prb_old8_free:
    PRB_PROLOGUE
    lcntr = PRB_STAGES, do .prb_ofo until lce;
        PRB_PTRS
        lcntr = PRB_INNER, do .prb_ofi until lce;
            f1 = dm(i2, 0);
            f8  = f0 * f4;
            f9  = f0 * f5, f13 = f11 + f12;
            f10 = f0 * f6, f14 = f11 + f12;
            f13 = f0 * f7;
            f14 = f0 * f0;
            f15 = f11 - f12;
        .prb_ofi: f3 = f11 - f12, dm(i2, 2) = f11;
    .prb_ofo: nop;
    PRB_EPILOGUE
_prb_old8_free.end:

#endif /* DSP4_BQ_PROBE */
