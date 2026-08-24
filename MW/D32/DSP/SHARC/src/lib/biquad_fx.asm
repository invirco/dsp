/*======================================================================
 * biquad_fx.asm — fixed-point biquad core (decision D5)
 *
 * NORMATIVE REFERENCE: tools/dsp/fixed_ref.py::biquad — this code must
 * match it BIT-EXACTLY (offset-coefficient direct-form I with
 * first-order error feedback, shared/numeric-spec.md):
 *
 *   acc  = efb + b0*x + b0*x2 - b0*x1 - b0*x1        (x - 2x1 + x2)
 *        + n1*x1 + n2*x2 - c1*y1 + c2*y2
 *        + y1*2^29 - y2*2^28                          (2*y1 - y2) << 28
 *   y    = sat32(rns(acc, 28))
 *   efb' = acc - (y << 28)
 *
 * Formats: samples/coeffs Q4.28; acc exact in the 80-bit MRF; efb kept
 * as a 64-bit pair. rns() = add 2^27 then arithmetic >>28 (matches
 * fixed_ref.rns for the value ranges reachable here).
 *
 * Coefficient block per stage (5 words, Q4.28):  [b0, n1, n2, c1, c2]
 *   n1 = b1 + 2*b0,  n2 = b2 - b0,  c1 = 2 + a1,  c2 = 1 - a2
 * State block per stage (6 words): [x1, x2, y1, y2, efb_lo, efb_hi]
 *
 * Entry points:
 *   _bq_fx_cascade_N — N-stage cascade, one sample
 *       In:  r0 = x (Q4.28), i0 -> coeffs (5/stage), i1 -> state
 *            (6/stage), r4 = stage count
 *       Out: r0 = y (Q4.28); i0/i1 advanced past the used stages
 *       Clobbers: r1-r3, r5-r12, m1, MRF; PRESERVES r13-r15
 *       (node crossfade bodies rely on r13/r14 surviving)
 *   _bq_fx_convert_N — float staged coeffs -> fixed offset coeffs
 *       In:  i0 -> float [b0,b1,b2,a1,a2] per stage (RBJ, from SPI),
 *            i1 -> fixed [b0,n1,n2,c1,c2] per stage, r4 = stage count
 *       Clobbers: f0-f8, r0-r2
 *
 * First cut favours correctness over cycles (~40 cycles/stage);
 * optimize with parallel dual-loads after bring-up parity is proven.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

.section/pm seg_pmco;

.global _bq_fx_cascade_N;
_bq_fx_cascade_N:
    lcntr = r4, do .bqfx_stage until lce;

        /* ---- load state ---- */
        r5 = dm(i1, 1);        /* x1                  (i1 -> x2)      */
        r6 = dm(i1, 1);        /* x2                  (i1 -> y1)      */
        r7 = dm(i1, 1);        /* y1                  (i1 -> y2)      */
        r8 = dm(i1, 1);        /* y2                  (i1 -> efb_lo)  */
        r9 = dm(i1, 1);        /* efb_lo              (i1 -> efb_hi)  */
        r10 = dm(i1, 0);       /* efb_hi (no advance; rewind later)   */

        /* ---- MRF = efb (sign-extended 64 -> 80) ---- */
        mr0f = r9;
        mr1f = r10;
        r11 = ashift r10 by -31;
        mr2f = r11;

        /* ---- numerator: b0*(x - 2*x1 + x2) via b0-only MACs ---- */
        r1 = dm(i0, 1);        /* b0                  (i0 -> n1)      */
        mrf = mrf + r1 * r0 (ssi);      /* + b0*x  */
        mrf = mrf + r1 * r6 (ssi);      /* + b0*x2 */
        mrf = mrf - r1 * r5 (ssi);      /* - b0*x1 */
        mrf = mrf - r1 * r5 (ssi);      /* - b0*x1 */

        /* ---- offset terms ---- */
        r1 = dm(i0, 1);        /* n1 */
        mrf = mrf + r1 * r5 (ssi);      /* + n1*x1 */
        r1 = dm(i0, 1);        /* n2 */
        mrf = mrf + r1 * r6 (ssi);      /* + n2*x2 */
        r1 = dm(i0, 1);        /* c1 */
        mrf = mrf - r1 * r7 (ssi);      /* - c1*y1 */
        r1 = dm(i0, 1);        /* c2                  (i0 -> next stage) */
        mrf = mrf + r1 * r8 (ssi);      /* + c2*y2 */

        /* ---- unity terms: + y1*2^29 - y2*2^28 (exact) ---- */
        r1 = 0x20000000;
        mrf = mrf + r1 * r7 (ssi);
        r1 = 0x10000000;
        mrf = mrf - r1 * r8 (ssi);

        /* ---- snapshot acc (64-bit) for the remainder ---- */
        r2 = mr0f;             /* acc_lo */
        r3 = mr1f;             /* acc_hi */

        /* ---- y = sat32(rns(acc, 28)) ---- */
        r1 = 0x08000000;       /* 2^27 rounding half */
        r11 = 1;
        mrf = mrf + r1 * r11 (ssi);
        r11 = mr0f;
        r12 = mr1f;
        r11 = lshift r11 by -28;        /* logical: low 4 bits of y   */
        r1 = lshift r12 by 4;           /* high 28 bits of y          */
        r11 = r11 or r1;                /* candidate y                */
        /* saturation check: acc>>28 must fit in 32 bits:
         * ashift(acc_hi, -28) must equal ashift(y, -31) */
        r1 = ashift r12 by -28;
        r12 = ashift r11 by -31;
        comp(r1, r12);
        if eq jump (pc, .bqfx_nosat);
        /* saturate by sign of acc (mr2f snapshot not needed: use r3) */
        r11 = 0x7FFFFFFF;
        r1 = ashift r3 by -31;          /* -1 if negative              */
        r11 = r11 xor r1;               /* MAX or MIN pattern          */
    .bqfx_nosat:

        /* ---- efb' = acc - (y << 28) (64-bit subtract) ---- */
        r1 = lshift r11 by 28;          /* (y<<28) low word            */
        r12 = ashift r11 by -4;         /* (y<<28) high word           */
        r2 = r2 - r1;                   /* low, sets borrow            */
        r3 = r3 - r12 + ci - 1;         /* high with borrow            */

        /* ---- store state: [x1', x2', y1', y2', efb'] ---- */
        dm(i1, -1) = r3;       /* efb_hi   (i1 -> efb_lo)  */
        dm(i1, -1) = r2;       /* efb_lo   (i1 -> y2)      */
        dm(i1, -1) = r7;       /* y2' = y1 (i1 -> y1)      */
        dm(i1, -1) = r11;      /* y1' = y  (i1 -> x2)      */
        dm(i1, -1) = r5;       /* x2' = x1 (i1 -> x1)      */
        dm(i1, 0) = r0;        /* x1' = x                  */
        r1 = 6;
        m1 = r1;
        modify(i1, m1);        /* advance to next stage's state */

        /* ---- cascade: y feeds the next stage ---- */
    .bqfx_stage:
        r0 = r11;

    rts;
_bq_fx_cascade_N.end:

#if DSP4_BLOCK_KERNELS
#if DSP4_STRIP_FUSED
/*----------------------------------------------------------------------
 * _bq_fx_cascade_blk — FUSED form. Same arithmetic, same result, but the
 * error feedback never leaves the MAC accumulator.
 *
 * The block form already kept state in registers. What it still did every
 * sample was take the 64-bit accumulator apart to form the error
 * feedback, store it in two registers, and push it back into MR0F/MR1F/
 * MR2F on the next sample -- about ten instructions of pure plumbing per
 * sample per stage.
 *
 * MRF is 80 bits and already holds exactly the accumulator that the error
 * feedback IS. So instead of extracting it, the rounding half is
 * subtracted back out and y*2^28 is subtracted with a MAC:
 *
 *     mrf = mrf - r14 * r15   (remove the 2^27 rounding half)
 *     mrf = mrf - y   * r13   (r13 = 2^28, so this is y << 28)
 *
 * and MRF carries the residue straight into the next sample untouched.
 * This is BIT-EXACT, not an approximation: the old code stored efb as two
 * 32-bit words plus a sign extension into MR2F, which is the same 80-bit
 * value MRF already holds.
 *
 * Registers, all sixteen used:
 *   r0 x   r1 y   r2,r3 scratch
 *   r4 b0  r5 n1  r6 n2  r7 c1  r8 c2
 *   r9 x1  r10 x2 r11 y1 r12 y2
 *   r13 = 2^28   r14 = 2^27   r15 = 1
 * There is no register left for the 2^29 unity term, so it is applied as
 * two MACs of 2^28 -- one instruction more, one register less, and the
 * register is what was scarce.
 *
 * In:  i0 = coeffs, i1 = state, i2 = signal block (32 words, in place),
 *      r4 = number of stages.
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_blk;
_bq_fx_cascade_blk:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    r15 = -32;
    m2 = r15;                  /* rewind the signal block per stage */
    r15 = 5;
    m3 = r15;                  /* state base+1 -> next stage's base   */

    lcntr = r4, do .bqf_stage until lce;

        r4 = dm(i0, 1);        /* b0 */
        r5 = dm(i0, 1);        /* n1 */
        r6 = dm(i0, 1);        /* n2 */
        r7 = dm(i0, 1);        /* c1 */
        r8 = dm(i0, 1);        /* c2, i0 -> next stage                */

        r9  = dm(i1, 1);       /* x1     */
        r10 = dm(i1, 1);       /* x2     */
        r11 = dm(i1, 1);       /* y1     */
        r12 = dm(i1, 1);       /* y2     */
        r2  = dm(i1, 1);       /* efb_lo */
        r3  = dm(i1, 0);       /* efb_hi -- i1 parked at base+5       */

        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;             /* MRF = efb, sign extended 64 -> 80   */

        r13 = 0x10000000;      /* 2^28 */
        r14 = 0x08000000;      /* 2^27, the rounding half */
        r15 = 1;

        lcntr = 32, do .bqf_samp until lce;
            r0 = dm(i2, 0);
            mrf = mrf + r4 * r0 (ssi);      /* + b0*x   */
            mrf = mrf + r4 * r10 (ssi);     /* + b0*x2  */
            mrf = mrf - r4 * r9 (ssi);      /* - b0*x1  */
            mrf = mrf - r4 * r9 (ssi);      /* - b0*x1  */
            mrf = mrf + r5 * r9 (ssi);      /* + n1*x1  */
            mrf = mrf + r6 * r10 (ssi);     /* + n2*x2  */
            mrf = mrf - r7 * r11 (ssi);     /* - c1*y1  */
            mrf = mrf + r8 * r12 (ssi);     /* + c2*y2  */
            mrf = mrf + r13 * r11 (ssi);    /* + y1*2^28 */
            mrf = mrf + r13 * r11 (ssi);    /*   twice = y1*2^29 */
            mrf = mrf - r13 * r12 (ssi);    /* - y2*2^28 */

            mrf = mrf + r14 * r15 (ssi);    /* round: + 2^27 */
            r2 = mr0f;
            r3 = mr1f;
            r1 = lshift r2 by -28;
            r2 = lshift r3 by 4;
            r1 = r1 or r2;                  /* candidate y */
            r2 = ashift r3 by -28;
            r3 = ashift r1 by -31;
            comp(r2, r3);
            if eq jump (pc, .bqf_nosat);
                r1 = 0x7FFFFFFF;
                r2 = mr1f;
                r2 = ashift r2 by -31;
                r1 = r1 xor r2;
        .bqf_nosat:
            mrf = mrf - r14 * r15 (ssi);    /* take the rounding half back out */
            mrf = mrf - r1 * r13 (ssi);     /* efb = acc - (y << 28), stays in MRF */

            r10 = r9;                       /* x2' = x1 */
            r9 = r0;                        /* x1' = x  */
            r12 = r11;                      /* y2' = y1 */
            r11 = r1;                       /* y1' = y  */
        .bqf_samp: dm(i2, 1) = r1;

        /* ---- state back to memory, ONCE for this stage ---- */
        r2 = mr0f;
        r3 = mr1f;
        dm(i1, -1) = r3;       /* efb_hi at +5 */
        dm(i1, -1) = r2;       /* efb_lo at +4 */
        dm(i1, -1) = r12;      /* y2     at +3 */
        dm(i1, -1) = r11;      /* y1     at +2 */
        dm(i1, -1) = r10;      /* x2     at +1 */
        dm(i1, 1) = r9;        /* x1     at +0, i1 -> base+1 */
        modify(i1, m3);        /* -> next stage's state base */
        modify(i2, m2);        /* rewind the block for the next stage */
    .bqf_stage:
        nop;
    rts;
_bq_fx_cascade_blk.end:

#else
/*----------------------------------------------------------------------
 * _bq_fx_cascade_blk — cascade a whole BLOCK, state resident in registers.
 *
 * In:  i0 = coeffs, i1 = state, i2 = signal block (32 words, in place),
 *      r4 = number of stages.
 *
 * Identical arithmetic to _bq_fx_cascade_N, reordered stage-at-a-time
 * instead of sample-at-a-time. That is safe for a CASCADE: each stage is
 * causal with its own state, so running stage k over the whole block
 * before stage k+1 produces the same samples in the same order. The
 * per-sample maths below is a line-for-line copy of the routine above.
 *
 * The win is the state: six loads and six stores PER SAMPLE become six
 * loads and six stores per STAGE. Coefficients are still re-read per
 * sample (one instruction each, and hoisting all five would not fit
 * alongside the six state registers).
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_blk;
_bq_fx_cascade_blk:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    r15 = -5;
    m1 = r15;                  /* rewind coeffs by one sample's worth */
    r15 = -32;
    m2 = r15;                  /* rewind the signal block per stage    */
    r15 = 5;
    m3 = r15;                  /* state base+1 -> next stage's base    */

    lcntr = r4, do .bqb_stage until lce;

        /* ---- state into registers, ONCE for this stage ---- */
        r5 = dm(i1, 1);        /* x1     */
        r6 = dm(i1, 1);        /* x2     */
        r7 = dm(i1, 1);        /* y1     */
        r8 = dm(i1, 1);        /* y2     */
        r9 = dm(i1, 1);        /* efb_lo */
        r10 = dm(i1, 0);       /* efb_hi -- i1 parked at base+5 */

        r4 = 32;
        lcntr = r4, do .bqb_samp until lce;
            r0 = dm(i2, 0);                 /* x */
            mr0f = r9;
            mr1f = r10;
            r11 = ashift r10 by -31;
            mr2f = r11;
            r1 = dm(i0, 1);                 /* b0 */
            mrf = mrf + r1 * r0 (ssi);
            mrf = mrf + r1 * r6 (ssi);
            mrf = mrf - r1 * r5 (ssi);
            mrf = mrf - r1 * r5 (ssi);
            r1 = dm(i0, 1);                 /* n1 */
            mrf = mrf + r1 * r5 (ssi);
            r1 = dm(i0, 1);                 /* n2 */
            mrf = mrf + r1 * r6 (ssi);
            r1 = dm(i0, 1);                 /* c1 */
            mrf = mrf - r1 * r7 (ssi);
            r1 = dm(i0, 1);                 /* c2 */
            mrf = mrf + r1 * r8 (ssi);
            modify(i0, m1);                 /* rewind for the next sample */
            r1 = 0x20000000;
            mrf = mrf + r1 * r7 (ssi);
            r1 = 0x10000000;
            mrf = mrf - r1 * r8 (ssi);
            r2 = mr0f;                      /* acc_lo */
            r3 = mr1f;                      /* acc_hi */
            r1 = 0x08000000;
            r11 = 1;
            mrf = mrf + r1 * r11 (ssi);
            r11 = mr0f;
            r12 = mr1f;
            r11 = lshift r11 by -28;
            r1 = lshift r12 by 4;
            r11 = r11 or r1;
            r1 = ashift r12 by -28;
            r12 = ashift r11 by -31;
            comp(r1, r12);
            if eq jump (pc, .bqb_nosat);
            r11 = 0x7FFFFFFF;
            r1 = ashift r3 by -31;
            r11 = r11 xor r1;
        .bqb_nosat:
            r1 = lshift r11 by 28;
            r12 = ashift r11 by -4;
            r2 = r2 - r1;
            r3 = r3 - r12 + ci - 1;
            /* state update stays in registers */
            r6 = r5;                        /* x2' = x1 */
            r5 = r0;                        /* x1' = x  */
            r8 = r7;                        /* y2' = y1 */
            r7 = r11;                       /* y1' = y  */
            r9 = r2;                        /* efb_lo   */
            r10 = r3;                       /* efb_hi   */
            dm(i2, 1) = r11;                /* y, advance */
        .bqb_samp:
            nop;

        /* ---- state back to memory, ONCE for this stage ---- */
        dm(i1, -1) = r10;      /* efb_hi at +5 */
        dm(i1, -1) = r9;       /* efb_lo at +4 */
        dm(i1, -1) = r8;       /* y2     at +3 */
        dm(i1, -1) = r7;       /* y1     at +2 */
        dm(i1, -1) = r6;       /* x2     at +1 */
        dm(i1, 1) = r5;        /* x1     at +0, i1 -> base+1 */
        modify(i1, m3);        /* -> next stage's state base */
        modify(i2, m2);        /* rewind the block for the next stage */
        /* i0 is rewound per SAMPLE, so after the inner loop it is still on
         * this stage's coefficients -- advance it by five for the next.
         * Without this the routine is only correct for r4 = 1, which is
         * how FILT calls it (once per section); EQ uses r4 = 4 and would
         * have run every band with band 0's coefficients. */
        r15 = 5;
        m1 = r15;
        modify(i0, m1);
        r15 = -5;
        m1 = r15;              /* restore the per-sample rewind */
    .bqb_stage:
        nop;
    rts;
_bq_fx_cascade_blk.end:
#endif
#endif

/*----------------------------------------------------------------------
 * _bq_fx_convert_N — RBJ float coeffs -> Q4.28 offset coeffs
 *
 * THE FIX RESULT GOES IN r9, NOT r1. On SHARC the register file is
 * unified: r1 and f1 are the SAME register. This routine holds b1 in f1
 * across the b0 conversion, so `r1 = fix f5` for b0q DESTROYED b1 before
 * `n1 = b1 + 2*b0` ever read it. The wreckage did not look like wreckage:
 * b0q = 0x10000000 reinterpreted as a float is 2.6e-29, which adds as
 * zero, so n1 came out as exactly 2*b0 and every biquad in the product
 * silently ran with b1 = 0 -- EQ and HPF/LPF alike. Bench 2026-08-23:
 * b1 = +1 and b1 = -1 gave the IDENTICAL impulse response, and a mixed
 * set was wrong by exactly (b1 + 2b0 - 2b0) * x1. b2/a1/a2 live in
 * f2/f3/f4 and were never touched, which is why ONLY the b1 term failed
 * and why unity coefficients looked perfect. Keep the fix destination
 * clear of f0-f8 here.
 *
 * Mirrors fixed_ref.biquad_coeffs_q: each output word is
 * round-to-nearest of (value * 2^28), saturated. Uses the float unit
 * (dual-format core); FIX rounds per the current RND mode
 * (round-to-nearest matches the model's Python round()).
 *----------------------------------------------------------------------*/
.global _bq_fx_convert_N;
_bq_fx_convert_N:
    /* f8 = 2^28 scale constant */
    r0 = 0x4D800000;           /* 268435456.0f = 2^28 */
    f8 = r0;
    r0 = 0x40000000;           /* 2.0f  */
    f6 = r0;
    r0 = 0x3F800000;           /* 1.0f  */
    f7 = r0;

    lcntr = r4, do .bqcvt_stage until lce;
        f0 = dm(i0, 1);        /* b0 */
        f1 = dm(i0, 1);        /* b1 */
        f2 = dm(i0, 1);        /* b2 */
        f3 = dm(i0, 1);        /* a1 */
        f4 = dm(i0, 1);        /* a2 */

        /* b0q */
        f5 = f0 * f8;
        r9 = fix f5;
        dm(i1, 1) = r9;
        /* n1 = b1 + 2*b0 */
        f5 = f0 * f6;
        f5 = f1 + f5;
        f5 = f5 * f8;
        r9 = fix f5;
        dm(i1, 1) = r9;
        /* n2 = b2 - b0 */
        f5 = f2 - f0;
        f5 = f5 * f8;
        r9 = fix f5;
        dm(i1, 1) = r9;
        /* c1 = 2 + a1 */
        f5 = f3 + f6;
        f5 = f5 * f8;
        r9 = fix f5;
        dm(i1, 1) = r9;
        /* c2 = 1 - a2 */
        f5 = f7 - f4;
        f5 = f5 * f8;
        r9 = fix f5;
    .bqcvt_stage:
        dm(i1, 1) = r9;

    rts;
_bq_fx_convert_N.end:

#if DSP4_SIMD_PROBE
/*----------------------------------------------------------------------
 * _bq_fx_cascade_simd — the fused cascade, two strips per instruction
 * stream on the PEx/PEy pair.
 *
 * Strips are per-channel and independent, which is exactly the shape SIMD
 * wants. Coefficients, state and signal are INTERLEAVED by strip: A's word
 * then B's word, so a single access with modifier 2 feeds both compute
 * units. Every register below is really a pair.
 *
 * The one structural change from the fused scalar version is the
 * saturation. A jump uses PEx's condition for BOTH units, so a branch here
 * would saturate strip B whenever strip A clipped. It is a per-PE
 * CONDITIONAL MOVE instead -- conditional COMPUTE is evaluated
 * independently in each unit, which is the whole SIMD idiom. The saturated
 * value is built before the compare, because the ALU ops that build it
 * would otherwise overwrite the flags it is conditioned on.
 *
 * x is folded into the state update early, before the rounding, purely to
 * free r0 as the third temporary the branch-free saturation needs.
 *
 * In:  i0 = interleaved coeffs, i1 = interleaved state,
 *      i2 = interleaved signal (64 words), r4 = stages.
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_simd;
_bq_fx_cascade_simd:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    r15 = -64;
    m2 = r15;                  /* rewind the interleaved block per stage */
    r15 = 10;
    m3 = r15;                  /* state base+2 -> next stage's base      */

    bit set mode1 0x00200000;  /* PEYEN */
    nop;
    nop;

    lcntr = r4, do .bqs_stage until lce;
        r4 = dm(i0, 2);
        r5 = dm(i0, 2);
        r6 = dm(i0, 2);
        r7 = dm(i0, 2);
        r8 = dm(i0, 2);

        r9  = dm(i1, 2);
        r10 = dm(i1, 2);
        r11 = dm(i1, 2);
        r12 = dm(i1, 2);
        r2  = dm(i1, 2);       /* efb_lo */
        r3  = dm(i1, 0);       /* efb_hi */
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;

        r13 = 0x10000000;
        r14 = 0x08000000;
        r15 = 1;

        lcntr = 32, do .bqs_samp until lce;
            r0 = dm(i2, 0);
            mrf = mrf + r4 * r0 (ssi);
            mrf = mrf + r4 * r10 (ssi);
            mrf = mrf - r4 * r9 (ssi);
            mrf = mrf - r4 * r9 (ssi);
            mrf = mrf + r5 * r9 (ssi);
            mrf = mrf + r6 * r10 (ssi);
            mrf = mrf - r7 * r11 (ssi);
            mrf = mrf + r8 * r12 (ssi);
            mrf = mrf + r13 * r11 (ssi);
            mrf = mrf + r13 * r11 (ssi);
            mrf = mrf - r13 * r12 (ssi);

            r10 = r9;                       /* x2' = x1, frees r0 */
            r9 = r0;

            mrf = mrf + r14 * r15 (ssi);    /* round */
            r2 = mr0f;
            r3 = mr1f;
            r1 = lshift r2 by -28;
            r2 = lshift r3 by 4;
            r1 = r1 or r2;                  /* candidate y */
            r0 = ashift r3 by -31;          /* sign of acc */
            r2 = 0x7FFFFFFF;
            r0 = r2 xor r0;                 /* saturated value, built FIRST */
            r2 = ashift r3 by -28;
            r3 = ashift r1 by -31;
            comp(r2, r3);
            if ne r1 = pass r0;             /* per-PE, not a branch */

            mrf = mrf - r14 * r15 (ssi);
            mrf = mrf - r1 * r13 (ssi);
            r12 = r11;
            r11 = r1;
        .bqs_samp: dm(i2, 2) = r1;

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
    .bqs_stage:
        nop;

    bit clr mode1 0x00200000;
    nop;
    nop;
    rts;
_bq_fx_cascade_simd.end:
#endif
