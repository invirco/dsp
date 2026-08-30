/*======================================================================
 * call_selftest.asm — WHAT DOES A call/rts PAIR COST ON THIS PART?
 *
 * Review finding D66. Session 9 measured TUBE's engaged body at 103.9
 * cycles/sample on the part against a ~52 c/s estimate built by counting
 * the emitted instructions at one cycle apiece, and the ~52 c/s the count
 * missed is spread over the loop's three `call`/`rts` pairs — ~17 c/s a
 * pair. AXIS 1's floor table prices COMP's ~9 pairs and GATE's ~3 with
 * the SAME one-cycle-per-instruction count, so if 17 is right, every
 * floor built that way is understated. This is the isolated measurement
 * D66 asks for, and it is a LADDER rather than a single number, because
 * "17 c/s per pair" could be generic branch overhead, or it could be
 * something specific to `_mrf_rns28` — and those two answers point the
 * efficiency queue in different directions.
 *
 * THE LADDER. Eight rungs, each an identical hardware loop over the same
 * iteration count, differing only in the payload:
 *
 *   0 NULL        empty loop            — is a hardware loop really 1
 *                                         instruction per cycle? Every
 *                                         floor in the review assumes it.
 *   1 CALL_BARE   call to a bare `rts`  — the pair with NO body at all.
 *   2 CALL_NOP8   call to `nop x8; rts` — the pair with a body, callee in
 *                                         THIS object (near).
 *   3 INLINE_NOP8 the same 8 nops inline— rung 2 minus rung 3 is the pair
 *                                         priced against its own body.
 *   4 CALL_RNS    `_mrf_rns28` called   — the real callee, in another
 *                                         object (mac64_fx.asm).
 *   5 INLINE_RNS  `_mrf_rns28` inlined  — same arithmetic, no pair. Rung
 *                                         4 minus rung 5 is what INLINING
 *                                         actually recovers, measured.
 *   6 TUBE_CALL   TUBE's per-sample body, instruction for instruction
 *                 (C1_TUBE_01.asm:70-83) — this rung must reproduce the
 *                 103.9 c/s session 9 measured through the GRAPH, or this
 *                 instrument is not measuring the same thing the graph is.
 *   7 TUBE_INLINE the same body with the three rounds inlined — the
 *                 candidate optimisation, measured before it is adopted.
 *   8 JUMP_UNCOND an unconditional taken jump and nothing else — rung 8
 *                 minus rung 3 is the branch penalty on its own, with no
 *                 call, no return and no condition in it.
 *   9 INLINE_FREE `_mrf_rns28` inlined with the saturate as a conditional
 *                 MOVE — three instructions more than rung 5 and no
 *                 branch. This is the form AXIS 1's floors already assume.
 *  10 TUBE_FREE   TUBE's body inlined branch-free with the two rounding
 *                 constants hoisted. Hoisting pays for the conditional
 *                 move exactly, so rung 10 issues the SAME 47
 *                 instructions as rung 7 with three fewer taken branches:
 *                 if the penalty measured in rungs 5 and 8 is real and
 *                 additive, rung 10 must land on its naive count. That is
 *                 the falsifiable form of the whole ladder.
 *
 * WHY THE RUNGS ARE COMPARABLE. Same loop form, same iteration count,
 * same trailing pair of nops (TUBE carries two for the loop-tail hazard
 * and every rung carries them so none is flattered), and the whole ladder
 * runs THREE times so the host can take the minimum and drop any pass a
 * diag-tick ISR landed in. The window arithmetic is main.asm's own:
 *   cycles = (ticks_end - ticks_start) * TPERIOD + (tcount_start - tcount_end)
 * which is exact per pass rather than 1 ms-quantised.
 *
 * WHAT RUNG 5 IS AND IS NOT. The inlined form ends `if eq jump` where the
 * callee ends `if eq rts` — a taken branch either way — so rung 4 minus
 * rung 5 prices the CALL instruction and the return's pipeline cost, not
 * the branch itself. A branch-free saturate would be cheaper still; this
 * ladder does not claim that number, it claims the one that follows from
 * deleting the pair and nothing else.
 *
 * Debug only: DSP4_CALL_SELFTEST. Never in a shipping image.
 *====================================================================*/

#include "dsp_block.h"
#include "diag.h"

#if DSP4_CALL_SELFTEST

#define CST_RUNGS   11
#define CST_REPS    3

.section/dm seg_dmda;

.global _cst_done;      .var _cst_done  = 0;
.global _cst_magic;     .var _cst_magic = 0xD5B4C001;
.global _cst_iters;     .var _cst_iters = 20000;
.global _cst_reps;      .var _cst_reps  = CST_REPS;
.global _cst_rungs;     .var _cst_rungs = CST_RUNGS;
.global _cst_tper;      .var _cst_tper  = DIAG_TPERIOD;
.global _cst_blk;       .var _cst_blk   = DSP4_BLOCK_SIZE;

/* (ticks,tcount) at start and again at end — 4 words per rung per rep,
 * written through a running pointer in rep-major order, so the host reads
 * rung r of rep p at _cst_tick + ((p * CST_RUNGS) + r) * 4. */
.global _cst_tick;      .var _cst_tick[CST_RUNGS * CST_REPS * 4];

/* TUBE replica working buffers. 0.5 in Q4.28: x^2 = 0.25, and with
 * sat_q = 0.25 the whole expression stays well inside the domain, so
 * `_mrf_rns28` takes its early `if eq rts` exactly as it does in the
 * graph. A saturating stimulus would measure a different path. */
.global _cst_src;       .var _cst_src[DSP4_BLOCK_SIZE] =
    0x08000000, 0x08000000, 0x08000000, 0x08000000,
    0x08000000, 0x08000000, 0x08000000, 0x08000000;
.global _cst_dst;       .var _cst_dst[DSP4_BLOCK_SIZE];

.section/pm seg_pmco;
.extern _diag_ticks;
.extern _mrf_rns28;

/* Read the window ends the way main.asm does, and store through i5.
 * I8..I15 are DAG2 and address PM only; a DM store through one is a
 * type-4 semantic error, which is how this was found. */
#define CST_T   r2 = tcount; r0 = dm(_diag_ticks); dm(i5,1) = r0; dm(i5,1) = r2;

/* ---- rung 1 and rung 2 callees, in THIS object so the call is near --- */
.global _cst_rts;
_cst_rts:
    rts;
_cst_rts.end:

.global _cst_nop8;
_cst_nop8:
    nop; nop; nop; nop; nop; nop; nop; nop;
    rts;
_cst_nop8.end:

.global _cst_selftest;
_cst_selftest:

    i5 = _cst_tick;
    l5 = 0;
    r11 = 0;                        /* rep counter — no callee touches r11/r12 */

.cst_rep:

    /* ---- rung 0: NULL ------------------------------------------------ */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r0 until lce;
        nop;
    .cst_r0: nop;
    CST_T

    /* ---- rung 1: call to a bare rts ---------------------------------- */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r1 until lce;
        call _cst_rts;
        nop;
    .cst_r1: nop;
    CST_T

    /* ---- rung 2: call to an 8-nop body ------------------------------- */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r2 until lce;
        call _cst_nop8;
        nop;
    .cst_r2: nop;
    CST_T

    /* ---- rung 3: the same 8 nops inline ------------------------------ */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r3 until lce;
        nop; nop; nop; nop; nop; nop; nop; nop;
        nop;
    .cst_r3: nop;
    CST_T

    /* ---- rung 4: the real _mrf_rns28, called -------------------------- */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r4 until lce;
        r8 = 0x08000000;
        mrf = r8 * r8 (ssi);
        call _mrf_rns28;
        nop;
    .cst_r4: nop;
    CST_T

    /* ---- rung 5: the same arithmetic inlined -------------------------- */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r5 until lce;
        r8 = 0x08000000;
        mrf = r8 * r8 (ssi);
        r1 = 0x08000000;
        r3 = 1;
        mrf = mrf + r1 * r3 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        comp(r1, r3);
        if eq jump (pc, .cst_r5_ok);
        r0 = 0x7FFFFFFF;
        r1 = ashift r2 by -31;
        r0 = r0 xor r1;
    .cst_r5_ok:
        nop;
    .cst_r5: nop;
    CST_T

    /* ---- rung 6: TUBE's per-sample body, called ----------------------- */
    /* C1_TUBE_01.asm:70-83, instruction for instruction. i3/i4 are
     * circular over the two BLOCK-long buffers so 20,000 iterations walk
     * the same 8 words the graph's kernel does. */
    b3 = _cst_src;  i3 = _cst_src;  l3 = DSP4_BLOCK_SIZE;
    b4 = _cst_dst;  i4 = _cst_dst;  l4 = DSP4_BLOCK_SIZE;
    r9 = 0x04000000;                /* sat_q, hoisted, as the kernel does */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r6 until lce;
        r8 = dm(i3, 1);
        mrf = r8 * r8 (ssi);
        call _mrf_rns28;
        r10 = 0x10000000;
        r10 = r10 - r0;
        mrf = r9 * r10 (ssi);
        call _mrf_rns28;
        r10 = 0x10000000;
        r10 = r10 + r0;
        mrf = r8 * r10 (ssi);
        call _mrf_rns28;
        nop;
        nop;
    .cst_r6: dm(i4, 1) = r0;
    CST_T

    /* ---- rung 7: the same body with all three rounds inlined ---------- */
    b3 = _cst_src;  i3 = _cst_src;  l3 = DSP4_BLOCK_SIZE;
    b4 = _cst_dst;  i4 = _cst_dst;  l4 = DSP4_BLOCK_SIZE;
    r9 = 0x04000000;
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r7 until lce;
        r8 = dm(i3, 1);
        mrf = r8 * r8 (ssi);
        r1 = 0x08000000;
        r3 = 1;
        mrf = mrf + r1 * r3 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        comp(r1, r3);
        if eq jump (pc, .cst_r7_a);
        r0 = 0x7FFFFFFF;
        r1 = ashift r2 by -31;
        r0 = r0 xor r1;
    .cst_r7_a:
        r10 = 0x10000000;
        r10 = r10 - r0;
        mrf = r9 * r10 (ssi);
        r1 = 0x08000000;
        r3 = 1;
        mrf = mrf + r1 * r3 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        comp(r1, r3);
        if eq jump (pc, .cst_r7_b);
        r0 = 0x7FFFFFFF;
        r1 = ashift r2 by -31;
        r0 = r0 xor r1;
    .cst_r7_b:
        r10 = 0x10000000;
        r10 = r10 + r0;
        mrf = r8 * r10 (ssi);
        r1 = 0x08000000;
        r3 = 1;
        mrf = mrf + r1 * r3 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        comp(r1, r3);
        if eq jump (pc, .cst_r7_c);
        r0 = 0x7FFFFFFF;
        r1 = ashift r2 by -31;
        r0 = r0 xor r1;
    .cst_r7_c:
        nop;
        nop;
    .cst_r7: dm(i4, 1) = r0;
    CST_T


    /* ---- rung 8: an UNCONDITIONAL taken jump, nothing else ----------- */
    /* Same 10 instructions as rung 3, one of them a taken jump to the
     * very next instruction. Rung 8 minus rung 3 IS the branch penalty,
     * with no call, no return and no condition in it. */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r8 until lce;
        nop; nop; nop; nop; nop; nop; nop;
        jump (pc, .cst_r8_ok);
    .cst_r8_ok:
        nop;
    .cst_r8: nop;
    CST_T

    /* ---- rung 9: _mrf_rns28 inlined AND branch-free ------------------ */
    /* The saturate becomes a conditional MOVE, which is what AXIS 1's
     * floors already assume the hardware is used for. Three instructions
     * MORE than rung 5 and no branch at all. */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r9 until lce;
        r8 = 0x08000000;
        mrf = r8 * r8 (ssi);
        r1 = 0x08000000;
        r3 = 1;
        mrf = mrf + r1 * r3 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        r4 = ashift r2 by -31;
        r5 = 0x7FFFFFFF;
        r4 = r4 xor r5;
        comp(r1, r3);
        if ne r0 = pass r4;
        nop;
    .cst_r9: nop;
    CST_T

    /* ---- rung 10: TUBE's body, inlined, branch-free, constants hoisted */
    /* The same 47 instructions as rung 7 -- hoisting the two rounding
     * constants out of the loop pays for the conditional move exactly --
     * with the three taken branches gone. If the branch penalty measured
     * in rungs 8 and 5 is real and additive, this rung must land on its
     * naive count. That is the falsifiable form of the whole ladder. */
    b3 = _cst_src;  i3 = _cst_src;  l3 = DSP4_BLOCK_SIZE;
    b4 = _cst_dst;  i4 = _cst_dst;  l4 = DSP4_BLOCK_SIZE;
    r9 = 0x04000000;
    r6 = 0x08000000;                /* 2^27 rounding half, hoisted */
    r7 = 1;
    r5 = 0x7FFFFFFF;                /* saturation magnitude, hoisted */
    CST_T
    r10 = dm(_cst_iters);
    lcntr = r10, do .cst_r10 until lce;
        r8 = dm(i3, 1);
        mrf = r8 * r8 (ssi);
        mrf = mrf + r6 * r7 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        r4 = ashift r2 by -31;
        r4 = r4 xor r5;
        comp(r1, r3);
        if ne r0 = pass r4;
        r10 = 0x10000000;
        r10 = r10 - r0;
        mrf = r9 * r10 (ssi);
        mrf = mrf + r6 * r7 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        r4 = ashift r2 by -31;
        r4 = r4 xor r5;
        comp(r1, r3);
        if ne r0 = pass r4;
        r10 = 0x10000000;
        r10 = r10 + r0;
        mrf = r8 * r10 (ssi);
        mrf = mrf + r6 * r7 (ssi);
        r1 = mr0f;
        r2 = mr1f;
        r1 = lshift r1 by -28;
        r3 = lshift r2 by 4;
        r0 = r1 or r3;
        r1 = ashift r2 by -28;
        r3 = ashift r0 by -31;
        r4 = ashift r2 by -31;
        r4 = r4 xor r5;
        comp(r1, r3);
        if ne r0 = pass r4;
        nop;
        nop;
    .cst_r10: dm(i4, 1) = r0;
    CST_T

    l3 = 0;
    l4 = 0;

    r11 = r11 + 1;
    r12 = dm(_cst_reps);
    comp(r11, r12);
    if lt jump (pc, .cst_rep);

    r0 = 1;
    dm(_cst_done) = r0;
    rts;
_cst_selftest.end:

#endif /* DSP4_CALL_SELFTEST */
