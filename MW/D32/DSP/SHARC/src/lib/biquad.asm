/*======================================================================
 * biquad.asm — Reusable biquad filter core for ADSP-21564 (D32)
 *
 * Implements Direct Form II Transposed (DF-II-T) biquad:
 *
 *   w1' = b1*x + a1*y + w2
 *   w2' = b2*x + a2*y
 *   y   = b0*x + w1
 *
 * This form is preferred on SHARC because:
 *   1. Only 2 state variables per stage (vs 4 for DF-I)
 *   2. Better numerical behaviour for narrow-band filters in float32
 *   3. Natural for cascading: output feeds input of next stage
 *
 * Public entry points:
 *   _biquad_mono         — single biquad, 1 sample
 *   _biquad_cascade_N    — N-stage cascade, 1 sample
 *
 * FLOAT-ERA CODE. The fixed-point path (decision D5) does not call any
 * of it; the archived `--format float` kernels are the only callers.
 *
 * 2026-08-29 (review findings D8/D13):
 *   - `_biquad_block_32` and `_biquad_cascade_block` REMOVED. Dead
 *     everywhere, generator included: nothing emitted a call to either.
 *     ~90 instructions of PM in every shipping image for nothing.
 *   - `_biquad_cascade_N` REWRITTEN, not removed. D8 read it as dead,
 *     but the float generator emits 22 calls to it, so deleting the
 *     symbol would only move the failure to the link. What D8 found is
 *     real and worse than a loop-hazard: `rts` was the loop-END
 *     instruction, so `do .cascade_loop until lce` executed the return
 *     on the FIRST iteration. An N-stage float cascade ran ONE stage,
 *     and returned from inside a live hardware loop. The rewrite puts
 *     the `rts` outside the loop and gives the call the two-nop tail
 *     the house mitigation for hazard (a) uses.
 *
 * Register conventions (callee uses, caller saves if needed):
 *   Inputs:
 *     f0 = input sample
 *     i0 = coefficients base: [b0, b1, b2, a1, a2] per stage
 *     i1 = state base: [w1, w2] per stage
 *   Output:
 *     f0 = output sample (mono)
 *   Clobbered: f1–f12, r4–r5, i0–i1 advanced past used stages
 *
 * Hand-maintained infrastructure (NOT generated, despite what this
 * header claimed until 2026-08-29).
 *======================================================================*/

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _biquad_mono — Single-stage DF-II-T biquad, one sample
 *
 * In:  f0 = x, i0 → coeffs[5], i1 → state[2]
 * Out: f0 = y, i0 advanced +5, i1 advanced +2
 *----------------------------------------------------------------------*/
.global _biquad_mono;
_biquad_mono:
    /* Load coefficients */
    f1 = dm(i0, 1);       /* b0 */
    f2 = dm(i0, 1);       /* b1 */
    f3 = dm(i0, 1);       /* b2 */
    f4 = dm(i0, 1);       /* a1 */
    f5 = dm(i0, 1);       /* a2 */

    /* Load state */
    f6 = dm(i1, 0);       /* w1 (don't advance yet) */
    f7 = dm(i1, 1);       /* w1 — now advance; i1 → w2 */
    f8 = dm(i1, 0);       /* w2 */

    /* y = b0 * x + w1 */
    f9 = f1 * f0;         /* b0 * x */
    f9 = f9 + f7;         /* + w1 → y */

    /* w1' = b1 * x + a1 * y + w2 */
    f10 = f2 * f0;        /* b1 * x */
    f11 = f4 * f9;        /* a1 * y */
    f10 = f10 + f11;      /* b1*x + a1*y */
    f10 = f10 + f8;       /* + w2 → new w1 */

    /* w2' = b2 * x + a2 * y */
    f11 = f3 * f0;        /* b2 * x */
    f12 = f5 * f9;        /* a2 * y */
    f11 = f11 + f12;      /* → new w2 */

    /* Store state — rewind i1 by 1, write w1, advance, write w2 */
    modify(i1, -1);        /* back to w1 position */
    dm(i1, 1) = f10;      /* w1' */
    dm(i1, 1) = f11;      /* w2' — i1 now past this stage */

    /* Output */
    f0 = f9;              /* y */
    rts;
_biquad_mono.end:


/*----------------------------------------------------------------------
 * _biquad_cascade_N — N-stage cascaded biquad, one sample
 *
 * In:  f0 = x, i0 → coeffs[N*5], i1 → state[N*2], r4 = N
 * Out: f0 = y (output of last stage)
 *      i0 advanced by N*5, i1 advanced by N*2
 *
 * The loop-end instruction is a `nop`, never the `rts` — see the header.
 * The two trailing nops keep the `call` clear of the last three
 * instructions of the loop (recorded SHARC hazard (a)).
 *----------------------------------------------------------------------*/
.global _biquad_cascade_N;
_biquad_cascade_N:
    lcntr = r4, do .cascade_loop until lce;
        call _biquad_mono;    /* f0 = this stage out, feeds the next */
        nop;
    .cascade_loop:
        nop;
    rts;
_biquad_cascade_N.end:
