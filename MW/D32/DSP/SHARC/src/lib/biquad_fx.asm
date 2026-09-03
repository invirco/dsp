/*======================================================================
 * biquad_fx.asm — fixed-point biquad core (decision D5)
 *
 * NORMATIVE REFERENCE: tools/dsp/fixed_ref.py::biquad — this code must
 * match it BIT-EXACTLY (offset-coefficient direct-form I with
 * first-order error feedback, shared/numeric-spec.md):
 *
 *   acc  = efb + b0*x + b0*x2 - b0*x1 - b0*x1        (x - 2x1 + x2)
 *        + nh*x1 + nh*x1 + n2*x2 - c1*y1 + c2*y2      (nh = n1/2)
 *        + y1*2^29 - y2*2^28                          (2*y1 - y2) << 28
 *   y    = sat32(rns(acc, 28))
 *   efb' = acc - (y << 28)
 *
 * ROUND ONCE PER CASCADE (PW ruling 2026-09-02, D5 amendment; landed
 * 2026-09-03, DSP4_BQ_ROUNDONCE, default on). The per-stage SATURATE is
 * DELETED: y is the plain 32-bit extract of rns(acc, 28) and wraps
 * instead of clamping. The per-stage ERROR FEEDBACK is KEPT, and that
 * distinction is the whole of the ruling -- RIG C measured the two
 * deletions separately and they price nothing alike. The saturate is six
 * instructions and, while nothing overflows, is the IDENTITY, so
 * fixed_ref stays the reference and nothing in the numeric spec moves;
 * the error feedback is one instruction and is worth 16 dB of LF
 * response on the shelf D5 was decided on.
 *
 * WHERE IT IS NOT THE IDENTITY. |h|_1 -- not max|H| -- is what an
 * arbitrary bounded input can reach, and 4.0% of the DEFS design space
 * exceeds Q4.28's ceiling of 8.0 on worst-case drive. There the extract
 * WRAPS, and in a recursive path a wrap is a sign inversion fed back
 * into the poles, not a clipped sample.
 *
 * THE GUARD IS WIRED (DSP4_BQ_GUARD, default on with round-once,
 * 2026-09-03). Headroom H is sized per CASCADE on |h|_1 at
 * PARAMETER-LOAD time by lib/bq_headroom.asm (model:
 * tools/dsp/bq_h_load.py) and is carried as the FIRST WORD of the
 * cascade's coefficient block -- one header word per block, two
 * interleaved for a SIMD pair. The kernels shift the cascade INPUT down
 * H bits on entry and the cascade OUTPUT back up and saturate ONCE on
 * exit; y stays UNSCALED in the history registers, so the recursion runs
 * at the level where |h|_1 * x fits Q4.28 and only the word handed to
 * the next node comes back up. That is why a per-cascade CLAMP does not
 * work and a per-cascade SCALE does.
 *
 * H = 0 IS THE 94% CASE AND IT COSTS A LOAD AND A TEST. Both scaling
 * passes are jumped over whole, so the sample loop is byte for byte the
 * unguarded one -- which is also why the scaling is a PASS OVER THE
 * BLOCK and not two instructions inside the loop. The in-loop form was
 * measured first (bq_shootout rungs 16/17) and cost eight instructions
 * on the exit, because three loop invariants met exactly one free
 * register under round-once and two were re-read every sample. A
 * dedicated pass has the whole register file.
 *
 * DSP4_BQ_ROUNDONCE=0 rebuilds the per-stage-saturating contract kernel
 * byte for byte and is the control every bar is run against.
 * SHARC/bqeverify.sh is the acceptance: both arms over the DEFS curve
 * set, on the part, hashed against fixed_ref.
 *
 * Formats: samples/coeffs Q4.28; acc exact in the 80-bit MRF; efb kept
 * as a 64-bit pair. rns() = add 2^27 then arithmetic >>28 (matches
 * fixed_ref.rns for the value ranges reachable here).
 *
 * Coefficient block: one HEADER word H (DSP4_BQ_GUARD only), then per
 * stage (5 words):  [b0, nh, n2, c1, c2]
 *   n1 = b1 + 2*b0,  n2 = b2 - b0,  c1 = 2 + a1,  c2 = 1 - a2
 *   b0/n2/c1/c2 are Q4.28; nh is n1 HALVED, stored Q5.27.
 *
 * WHY n1 IS HALVED (PW ruling 2026-08-29, minimum EQ Q = 0.10). n1 is
 * the only offset coefficient whose design-space range escapes Q4.28:
 * at +15 dB with Q <= 0.12 the peaking design gives n1 up to 8.318
 * against a ceiling of 7.999..., and it used to SATURATE at conversion,
 * so the filter silently became a different filter (1323 of 909,315
 * swept sets). Q5.27 doubles the headroom to +/-16 and the kernel
 * accumulates nh's product TWICE into the exact 80-bit MRF, which is
 * arithmetically n1*x1 with no intermediate rounding.
 *
 * UNIFORM AND UNCONDITIONAL. Every cascade form pays the extra MAC on
 * every stage of every sample whatever the loaded coefficients are: the
 * instruction stream must not vary with settings, or a measured ceiling
 * becomes a function of what happened to be loaded when it was measured.
 * ~+6 cycles/sample on a scalar strip, ~+3 per channel paired.
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

#include "dsp_block.h"

#if DSP4_BQ_GUARD
.section/dm seg_dmda;
/* H parked across the stage loop. The loop clobbers r1-r12 and PRESERVES
 * r13-r15 for the node crossfade bodies, so there is no register to hold
 * it in -- and this is the per-SAMPLE path, which is already the slow
 * one. */
.var _bqfx_h;
#endif

.section/pm seg_pmco;

#if !DSP4_BQ_FLOAT   /* the FIXED kernel; the float arm is at the foot of this file */
.global _bq_fx_cascade_N;
_bq_fx_cascade_N:
#if DSP4_BQ_GUARD
    r11 = dm(i0, 1);       /* H, and i0 steps past the header */
#if DSP4_BQ_GUARD_FORCE
    r11 = DSP4_BQ_GUARD_FORCE;      /* the measurement override */
#endif
    dm(_bqfx_h) = r11;
    r11 = pass r11;
    if eq jump (pc, .bqfx_noent);
    r12 = -r11;
    r0 = ashift r0 by r12;          /* x >> H, the entry scale */
.bqfx_noent:
#endif
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
        r1 = dm(i0, 1);        /* nh = n1/2, Q5.27 */
        mrf = mrf + r1 * r5 (ssi);      /* + nh*x1 */
        mrf = mrf + r1 * r5 (ssi);      /*   twice  = n1*x1 */
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
#if !DSP4_BQ_ROUNDONCE
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
#endif

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

#if DSP4_BQ_GUARD
    /* ---- the exit scale and the SINGLE clamp: y_out = sat32(y << H).
     * The saturated value is built BEFORE the compare, because the ALU
     * ops that build it would otherwise overwrite the flags it is
     * conditioned on. The test is "did the shift lose bits", i.e. does
     * shifting back down give what went in. ---- */
    r11 = dm(_bqfx_h);
    r11 = pass r11;
    if eq rts;
    r1 = 0x7FFFFFFF;
    r2 = ashift r0 by -31;          /* sign of y                    */
    r1 = r1 xor r2;                 /* MAX, or MIN                  */
    r2 = ashift r0 by r11;          /* candidate = y << H           */
    r12 = -r11;
    r3 = ashift r2 by r12;          /* candidate >> H               */
    comp(r3, r0);
    if ne r2 = pass r1;
    r0 = r2;
#endif
    rts;
_bq_fx_cascade_N.end:
#endif  /* !DSP4_BQ_FLOAT */

#if !DSP4_BQ_FLOAT   /* the FIXED kernel; the float arm is at the foot of this file */
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
 * feedback IS. So instead of extracting it, y*2^28 is subtracted with a
 * MAC and MRF carries the residue straight into the next sample
 * untouched. This is BIT-EXACT, not an approximation: the old code stored
 * efb as two 32-bit words plus a sign extension into MR2F, which is the
 * same 80-bit value MRF already holds.
 *
 * PACKED 2026-08-29 (review finding D21): branch-free saturation, the
 * rounding half kept out of MRF, and the x history shifted before the
 * extraction so two register moves stand between the last MAC and the
 * first `Rn = MR0F`.
 *
 * REGROUPED 2026-09-01 -- TWELVE MACs TO SIX, AND IT IS AN IDENTITY.
 *
 * The normative offset form (fixed_ref.biquad) is written out term by
 * term, and the kernel issued one MAC per term:
 *
 *     acc = efb + b0*x + b0*x2 - b0*x1 - b0*x1
 *               + nh*x1 + nh*x1 + n2*x2 - c1*y1 + c2*y2
 *               + y1*2^29 - y2*2^28
 *
 * Twelve MACs to express five products, because the offset encoding
 * spends the extra ones expressing b1, b2, a1 and a2 as offsets from the
 * low-frequency limit point. The 80-bit MAC accumulator is EXACT, so
 * collecting the terms by the variable they multiply cannot change the
 * sum by one bit:
 *
 *     g1h = nh - b0            (MACed TWICE, exactly as nh is)
 *     g2  = n2 + b0
 *     g3  = 2^29 - c1
 *     g4  = c2 - 2^28
 *     acc = efb + b0*x + g1h*x1 + g1h*x1 + g2*x2 + g3*y1 + g4*y2
 *
 * SIX MACs, and the offset form's whole benefit survives intact: the four
 * derived words are computed FROM THE STORED OFFSET WORDS with plain
 * 32-bit integer adds, so the coefficient QUANTISATION is byte for byte
 * what the offset encoding produced and only the grouping of the
 * arithmetic changes. Nothing about the stored coefficient block, the
 * conversion (`_bq_fx_convert_N`), the parameter path or fixed_ref moves.
 *
 * WHY g1h IS THE HALVED WORD AND NOT g1 = 2*(nh - b0). Because g1 is b1
 * in Q4.28 and b1 IS NOT BOUNDED BY 8: the worst set in the product's own
 * design space is a 20 Hz high shelf at +15 dB and Q = 3.16, where
 * |b1| = 11.2 and a Q4.28 word would wrap. Derived halved, it is
 * 0.7025 of int32 full scale -- the same reason n1 is stored halved, one
 * step further down the same road. tools/dsp/bound_direct.py sweeps all
 * 869,627 coefficient sets the DEFS ranges reach and reports the worst
 * magnitude of each derived word; it also checks the regrouping identity
 * itself against the normative expression on 20,000 random
 * coefficient/state sets. Both are conditions of this kernel being
 * correct, so they are a script and not a paragraph.
 *
 * THE ROUNDING HALF RIDES IN THE ACCUMULATOR (2026-09-01). y is
 * rns(acc,28) = (acc + 2^27) >> 28, and efb is acc - (y<<28) -- so the
 * old form had to add 2^27 to the EXTRACTED pair every sample (two more
 * instructions) to keep MRF unrounded. Carry ACC = acc + 2^27 in MRF
 * instead: y is then a plain arithmetic shift of ACC, and
 *     ACC' = acc' + 2^27 = (ACC - 2^27 - y*2^28) + products + 2^27
 *          = ACC - y*2^28 + products
 * so the half CANCELS from sample to sample. It is added once when the
 * stage loads efb and removed once when it stores it, and the two
 * per-sample adds disappear.
 *
 * THE SAMPLE LOOP IS UNROLLED BY TWO AND THE HISTORY REGISTERS ROTATE
 * (2026-09-01). x1/x2 and y1/y2 exchange roles on every sample, so a
 * two-sample body needs NO history moves at all: the four
 * `r10 = r9` / `r9 = r2` / `r12 = r11` / `r11 = r1` shuffles are gone,
 * and the incoming sample is loaded straight into the register whose x2
 * the MAC on the same instruction is consuming. After an even number of
 * samples the roles are back where the epilogue expects them, which is
 * why BLOCK must be even (checked below).
 *
 * Nineteen instructions per sample per stage against the thirty-two this
 * kernel issued on 2026-08-31, when it measured 37.2 cycles per
 * band-sample on the graph.
 *
 * Registers, all sixteen used:
 *   r0,r2,r3 scratch                                          r1 y
 *   r4 b0  r5 g1h  r6 g2  r7 g3  r8 g4
 *   r9/r10 x1,x2 (roles alternate)  r11/r12 y1,y2 (likewise)
 *   r13 = 2^28   r14 = 2^27 (stage prologue/epilogue only)
 *   r15 = 0x7FFFFFFF
 *
 * In:  i0 = coeffs, i1 = state, i2 = signal block (BLOCK words, in place),
 *      r4 = number of stages.
 *----------------------------------------------------------------------*/

#if (DSP4_BLOCK_SIZE & 1)
#error "_bq_fx_cascade_blk unrolls the sample loop by two and rotates the history registers; DSP4_BLOCK_SIZE must be even."
#endif

.global _bq_fx_cascade_blk;
_bq_fx_cascade_blk:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;                  /* rewind the signal block per stage */
#if DSP4_BQ_GUARD
    /* ---- THE ENTRY SCALE, as a pass over the block. H is a
     * control-rate word and the pass is jumped over whole when it is
     * zero, so the 94% case pays one load, one test and one branch for
     * the whole cascade. ---- */
    r13 = dm(i0, 1);           /* H, and i0 steps past the header */
#if DSP4_BQ_GUARD_FORCE
    r13 = DSP4_BQ_GUARD_FORCE;      /* the measurement override */
#endif
    dm(_bqfx_h) = r13;
    r13 = pass r13;
    if eq jump (pc, .bqf_noent);
    r14 = -r13;
    lcntr = DSP4_BLOCK_SIZE, do .bqf_ent until lce;
        r0 = dm(i2, 0);
        r0 = ashift r0 by r14;
    .bqf_ent: dm(i2, 1) = r0;
    modify(i2, m2);            /* rewind: the stage loop starts at the top */
.bqf_noent:
#endif
    r15 = 5;
    m3 = r15;                  /* state base+1 -> next stage's base   */

    lcntr = r4, do .bqf_stage until lce;

        r4 = dm(i0, 1);        /* b0 */
        r5 = dm(i0, 1);        /* nh */
        r6 = dm(i0, 1);        /* n2 */
        r7 = dm(i0, 1);        /* c1 */
        r8 = dm(i0, 1);        /* c2, i0 -> next stage                */

        r9  = dm(i1, 1);       /* x1     */
        r10 = dm(i1, 1);       /* x2     */
        r11 = dm(i1, 1);       /* y1     */
        r12 = dm(i1, 1);       /* y2     */
        r2  = dm(i1, 1);       /* efb_lo */
        r3  = dm(i1, 0);       /* efb_hi -- i1 parked at base+5       */

        r13 = 0x10000000;      /* 2^28 */
#if !DSP4_BQ_ROUNDONCE
        r15 = 0x7FFFFFFF;      /* the positive saturation pattern */
#endif

        /* ---- the DIRECT words, from the STORED OFFSET words ---- */
        r5 = r5 - r4;          /* g1h = nh - b0, MACed twice like nh */
        r6 = r6 + r4;          /* g2  = n2 + b0                      */
        r14 = r13 + r13;       /* 2^29                               */
        r7 = r14 - r7;         /* g3  = 2^29 - c1                    */
        r8 = r8 - r13;         /* g4  = c2 - 2^28                    */

        /* ---- MRF = efb + 2^27, sign extended 64 -> 80 ---- */
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;      /* the rounding half, added ONCE */
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);

        lcntr = DSP4_BLOCK_HALF, do .bqf_samp until lce;

            /* ---- sample A: x1 r9, x2 r10, y1 r11, y2 r12 ---- */
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
                                            /* g2*x2, and x lands in the
                                             * register the MAC has just
                                             * finished with -- it is the
                                             * next x1 */
            mrf = mrf + r4 * r10 (ssi);     /* b0*x    */
            mrf = mrf + r5 * r9  (ssi);     /* g1h*x1  */
            mrf = mrf + r5 * r9  (ssi);     /*   twice = n1*x1 - 2*b0*x1 */
            mrf = mrf + r7 * r11 (ssi);     /* g3*y1   */
            mrf = mrf + r8 * r12 (ssi);     /* g4*y2   */
            r2 = mr0f;
            r3 = mr1f;
#if DSP4_BQ_ROUNDONCE
            /* ROUND ONCE: the extract, and nothing after it. The combine
             * carries y in r0 and not r1 because
             * `Rn = Rn OR LSHIFT Rx BY <data8>` needs its destination to
             * be the shifted-LOW operand -- `r1 = r0 or lshift r3 by 4`
             * is rejected by the assembler. Four instructions instead of
             * five, and the six that clamped are gone. */
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);     /* ACC' = ACC - (y << 28) */
            r12 = pass r0, dm(i2, 1) = r0;  /* y is the next y1 */
#else
            r0 = lshift r2 by -28;
            r1 = lshift r3 by 4;
            r1 = r1 or r0;                  /* candidate y */
            r0 = ashift r3 by -28;          /* the bits above y */
            r2 = ashift r0 by -31;          /* sign of the accumulator */
            r2 = r15 xor r2;                /* MAX, or MIN if negative */
            r3 = ashift r1 by -31;          /* sign of the candidate */
            comp(r0, r3);
            if ne r1 = r2;                  /* saturate, WITHOUT branching */
            mrf = mrf - r1 * r13 (ssi);     /* ACC' = ACC - (y << 28) */
            r12 = pass r1, dm(i2, 1) = r1;  /* y is the next y1 */
#endif

            /* ---- sample B: x1 r10, x2 r9, y1 r12, y2 r11 ---- */
            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
#if DSP4_BQ_ROUNDONCE
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
        .bqf_samp: r11 = pass r0, dm(i2, 1) = r0;
#else
            r0 = lshift r2 by -28;
            r1 = lshift r3 by 4;
            r1 = r1 or r0;
            r0 = ashift r3 by -28;
            r2 = ashift r0 by -31;
            r2 = r15 xor r2;
            r3 = ashift r1 by -31;
            comp(r0, r3);
            if ne r1 = r2;
            mrf = mrf - r1 * r13 (ssi);
        .bqf_samp: r11 = pass r1, dm(i2, 1) = r1;
#endif

        /* ---- state back to memory, ONCE for this stage ---- */
        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);   /* take the rounding half back out */
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

#if DSP4_BQ_GUARD
    /* ---- THE EXIT SCALE AND THE SINGLE CLAMP, once per cascade, over
     * the block the last stage just wrote. i2 was rewound by the stage
     * epilogue, so it is already at the top. ---- */
    r13 = dm(_bqfx_h);
    r13 = pass r13;
    if eq rts;
    r14 = -r13;
    r15 = 0x7FFFFFFF;
    lcntr = DSP4_BLOCK_SIZE, do .bqf_exi until lce;
        r0 = dm(i2, 0);
        r1 = ashift r0 by -31;      /* sign of y            */
        r1 = r15 xor r1;            /* MAX, or MIN          */
        r2 = ashift r0 by r13;      /* candidate = y << H   */
        r3 = ashift r2 by r14;      /* candidate >> H       */
        comp(r3, r0);
        if ne r2 = pass r1;
    .bqf_exi: dm(i2, 1) = r2;
#endif
    rts;
_bq_fx_cascade_blk.end:

#else
/*----------------------------------------------------------------------
 * _bq_fx_cascade_blk — cascade a whole BLOCK, state resident in registers.
 *
 * In:  i0 = coeffs, i1 = state, i2 = signal block (BLOCK words, in place),
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
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;                  /* rewind the signal block per stage    */
#if DSP4_BQ_GUARD
    r13 = dm(i0, 1);           /* H, and i0 steps past the header */
#if DSP4_BQ_GUARD_FORCE
    r13 = DSP4_BQ_GUARD_FORCE;      /* the measurement override */
#endif
    dm(_bqfx_h) = r13;
    r13 = pass r13;
    if eq jump (pc, .bqb_noent);
    r14 = -r13;
    lcntr = DSP4_BLOCK_SIZE, do .bqb_ent until lce;
        r0 = dm(i2, 0);
        r0 = ashift r0 by r14;
    .bqb_ent: dm(i2, 1) = r0;
    modify(i2, m2);
.bqb_noent:
#endif
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

        r4 = DSP4_BLOCK_SIZE;
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
            r1 = dm(i0, 1);                 /* nh = n1/2, Q5.27 */
            mrf = mrf + r1 * r5 (ssi);
            mrf = mrf + r1 * r5 (ssi);      /* twice = n1*x1 */
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
#if !DSP4_BQ_ROUNDONCE
            r1 = ashift r12 by -28;
            r12 = ashift r11 by -31;
            comp(r1, r12);
            if eq jump (pc, .bqb_nosat);
            r11 = 0x7FFFFFFF;
            r1 = ashift r3 by -31;
            r11 = r11 xor r1;
        .bqb_nosat:
#endif
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

#if DSP4_BQ_GUARD
    r13 = dm(_bqfx_h);
    r13 = pass r13;
    if eq rts;
    r14 = -r13;
    r15 = 0x7FFFFFFF;
    lcntr = DSP4_BLOCK_SIZE, do .bqb_exi until lce;
        r0 = dm(i2, 0);
        r1 = ashift r0 by -31;
        r1 = r15 xor r1;
        r2 = ashift r0 by r13;
        r3 = ashift r2 by r14;
        comp(r3, r0);
        if ne r2 = pass r1;
    .bqb_exi: dm(i2, 1) = r2;
#endif
    rts;
_bq_fx_cascade_blk.end:
#endif
#endif
#endif  /* !DSP4_BQ_FLOAT */

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
#if !DSP4_BQ_FLOAT   /* the FIXED kernel; the float arm is at the foot of this file */
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
        /* nh = (b1 + 2*b0) / 2, stored Q5.27 -- the halved n1. Scaling
         * by 2^27 instead of 2^28 IS the halving: one multiply, no extra
         * instruction, and the ceiling moves from 7.999 to 15.999.
         *
         * The 2^27 constant goes in f1, NOT in a fresh register, and the
         * reason is the one this routine's header already learned the
         * hard way: the register file is unified, so a hoisted f9 would
         * be destroyed by the `r9 = fix f5` of the b0 conversion one
         * line earlier and n1 would quantise against garbage. f1 held
         * b1, which the add above has just consumed and which the next
         * iteration reloads, and r1 is inside this routine's documented
         * clobber set. */
        f5 = f0 * f6;
        f5 = f1 + f5;
        r1 = 0x4D000000;       /* 134217728.0f = 2^27 */
        f5 = f5 * f1;
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
#endif  /* !DSP4_BQ_FLOAT */

#if DSP4_BQ_PAIRED
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
.section/dm seg_dmda;
/* Two words: the reload at the bottom happens with PEYEN still set, so
 * PEy reads the word after. Same reason dyn_simd_fx.asm's _dsim_mode1 is
 * a pair. */
.var _simd_mode1_save[2];

#if DSP4_BQ_GUARD
/* THE GUARD'S THREE PAIRS. Every one is TWO words and read with PEYEN
 * SET, which is what makes them per-PE: a direct-address access in SIMD
 * mode gives PEx the word at the address and PEy the word after. That is
 * the same mechanism _simd_mode1_save is a pair for, and it is why the
 * two strips of a pair can carry DIFFERENT headroom -- the shift amount
 * is a register, and each unit shifts by its own.
 *
 * _bqs_gd holds the OR of the two, twice, so the skip decision is one
 * branch on PEx's flags that is right for both units. */
.var _bqs_hp[2] = 0, 0;        /* +H per strip */
.var _bqs_hm[2] = 0, 0;        /* -H per strip */
.var _bqs_gd[2] = 0, 0;        /* (Ha | Hb), in both halves */
#endif

#if DSP4_BQ_TRACE
/* EXACT ITERATION COUNTING (2026-08-30). Every counter is TWO words and
 * only the first is read: these are written from inside the PEYEN region,
 * where a direct-address store writes the word after the address too.
 *
 *   _bqs_phase   1 entered  2 PEYEN set  3 stage loop done
 *                4 MODE1 restored  5 about to rts
 *   _bqs_stages  outer (per-stage) loop iterations, expect r4
 *   _bqs_samps   inner (per-sample) loop iterations, expect r4*BLOCK
 *
 * "The self-test never finished" is compatible with a hundred mechanisms.
 * A counter that stops at a known iteration is compatible with one. */
.var _bqs_phase[2] = 0, 0;
.var _bqs_stages[2] = 0, 0;
.var _bqs_samps[2] = 0, 0;
.global _bqs_phase; .global _bqs_stages; .global _bqs_samps;
#endif

.section/pm seg_pmco;
#if !DSP4_BQ_FLOAT   /* the FIXED kernel; the float arm is at the foot of this file */
.global _bq_fx_cascade_simd;
_bq_fx_cascade_simd:
#if DSP4_BQ_TRACE
    r0 = 1; dm(_bqs_phase) = r0;
    r0 = 0; dm(_bqs_stages) = r0; dm(_bqs_samps) = r0;
#endif
    l0 = 0;
    l1 = 0;
    l2 = 0;
    /* -2 * BLOCK: the block is INTERLEAVED, so one stage walks i2 by two
     * words per sample. This was a literal -64, right for BLOCK=32 and
     * wrong for every other block size -- at BLOCK=8 it rewound i2 to 48
     * words BEFORE _bqp_sig and the second stage then read and WROTE
     * there, which is what hung the part. */
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;                  /* rewind the interleaved block per stage */
    r15 = 10;
    m3 = r15;                  /* state base+2 -> next stage's base      */

#if DSP4_BQ_GUARD
    /* ---- the header pair, read SCALAR, before PEYEN goes up ---- */
    r0 = dm(i0, 1);            /* Ha */
    r1 = dm(i0, 1);            /* Hb; i0 -> stage 0 */
#if DSP4_BQ_GUARD_FORCE
    r0 = DSP4_BQ_GUARD_FORCE;       /* the measurement override */
    r1 = DSP4_BQ_GUARD_FORCE;
#endif
    dm(_bqs_hp) = r0;
    dm(_bqs_hp + 1) = r1;
    r2 = -r0;
    r3 = -r1;
    dm(_bqs_hm) = r2;
    dm(_bqs_hm + 1) = r3;
    r0 = r0 or r1;
    dm(_bqs_gd) = r0;
    dm(_bqs_gd + 1) = r0;
#endif

    /* PEYEN ONLY -- INTERRUPTS ARE **NOT** MASKED HERE ANY MORE.
     *
     * The hazard is real: an interrupt taken while PEYEN is set runs the
     * HANDLER in SIMD mode, and every register it writes becomes a pair
     * write that clobbers the PEy shadow of state the ISR knows nothing
     * about. The fix for it is systemic and already in the tree -- _sec_isr
     * and _diag_timer_isr clear PEYEN after `push sts`, and `pop sts` puts
     * it back -- which is what the PAIRED DYNAMICS kernels rely on. They
     * mask nothing and they run, in the self-test and in the graph.
     *
     * THIS ROUTINE MASKED IRPTEN AS WELL, AND THAT IS WHY IT HUNG THE PART.
     * The masked span is one cascade, which sounds harmless against a block
     * period -- but the self-test calls it in a hardware loop thousands of
     * times with a handful of instructions between calls, so the block ISR
     * is starved for the whole run and the audio DMA never gets serviced.
     * The part is not crashed; it is running with interrupts off. It looks
     * identical from the bench: BOOT_STAGE stops advancing, frames stop,
     * "never reached stage 6". Bisected 2026-08-28: DSP4_SKIP_SIMDCALL=1
     * boots, one stage hangs exactly as four do (so it is not the per-stage
     * rewind), and the paired dynamics -- same PEYEN, no IRPTEN mask -- have
     * never hung.
     *
     * MODE1 is still saved and restored WHOLE rather than bit-toggled, so a
     * caller that had already masked interrupts stays masked. */
    r0 = mode1;
    dm(_simd_mode1_save) = r0;
    bit set mode1 0x00200000;  /* PEYEN */
    nop;
    nop;
#if DSP4_BQ_TRACE
    r0 = 2; dm(_bqs_phase) = r0;
#endif

#if DSP4_BQ_GUARD
    /* ---- THE ENTRY SCALE, one pass over the interleaved block, both
     * strips at once. Jumped over whole when neither strip carries
     * headroom, which is the 94% case. ---- */
    r0 = dm(_bqs_gd);
    r0 = pass r0;
    if eq jump (pc, .bqs_noent);
    r15 = dm(_bqs_hm);         /* -H, per PE */
    lcntr = DSP4_BLOCK_SIZE, do .bqs_ent until lce;
        r0 = dm(i2, 0);
        r0 = ashift r0 by r15;
    .bqs_ent: dm(i2, 2) = r0;
    modify(i2, m2);            /* rewind: the stage loop starts at the top */
.bqs_noent:
#endif

    lcntr = r4, do .bqs_stage until lce;
#if DSP4_BQ_TRACE
        /* r4 is the stage count and is dead here -- lcntr latched it -- so
         * it is the one register free before the coefficients load. */
        r4 = dm(_bqs_stages);
        r4 = r4 + 1;
        dm(_bqs_stages) = r4;
#endif
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

        r13 = 0x10000000;      /* 2^28 */
#if !DSP4_BQ_ROUNDONCE
        r15 = 0x7FFFFFFF;      /* the positive saturation pattern */
#endif

        /* ---- the DIRECT words, from the STORED OFFSET words ----
         * Six MACs per sample instead of twelve; see the scalar twin's
         * header for why this is an identity and why g1 is carried
         * halved. Both units derive their own channel's words from their
         * own channel's coefficients, which is what SIMD already gives. */
        r5 = r5 - r4;          /* g1h = nh - b0, MACed twice like nh */
        r6 = r6 + r4;          /* g2  = n2 + b0                      */
        r14 = r13 + r13;       /* 2^29                               */
        r7 = r14 - r7;         /* g3  = 2^29 - c1                    */
        r8 = r8 - r13;         /* g4  = c2 - 2^28                    */

        /* ---- MRF = efb + 2^27: the rounding half rides in the
         * accumulator and cancels from sample to sample ---- */
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        r14 = 0x08000000;
        r0 = 1;
        mrf = mrf + r14 * r0 (ssi);

        lcntr = DSP4_BLOCK_HALF, do .bqs_samp until lce;
#if DSP4_BQ_TRACE
            /* r1 is written by the saturation later in the body and holds
             * nothing on entry. TWO per iteration: the loop is unrolled
             * by two, so a counter of iterations is not a counter of
             * samples and the expected value would silently halve. */
            r1 = dm(_bqs_samps);
            r1 = r1 + 2;
            dm(_bqs_samps) = r1;
#endif
            /* ---- sample A: x1 r9, x2 r10, y1 r11, y2 r12 ---- */
            mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);
            mrf = mrf + r4 * r10 (ssi);     /* b0*x   */
            mrf = mrf + r5 * r9  (ssi);     /* g1h*x1 */
            mrf = mrf + r5 * r9  (ssi);     /*   twice */
            mrf = mrf + r7 * r11 (ssi);     /* g3*y1  */
            mrf = mrf + r8 * r12 (ssi);     /* g4*y2  */
            r2 = mr0f;
            r3 = mr1f;
#if DSP4_BQ_ROUNDONCE
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
            r12 = pass r0, dm(i2, 2) = r0;
#else
            r0 = lshift r2 by -28;
            r1 = lshift r3 by 4;
            r1 = r1 or r0;                  /* candidate y */
            r0 = ashift r3 by -28;          /* the bits above y */
            r2 = ashift r3 by -31;          /* sign of acc */
            r2 = r15 xor r2;                /* saturated value, built FIRST */
            r3 = ashift r1 by -31;
            comp(r0, r3);
            if ne r1 = pass r2;             /* per-PE, not a branch */
            mrf = mrf - r1 * r13 (ssi);
            r12 = pass r1, dm(i2, 2) = r1;
#endif

            /* ---- sample B: x1 r10, x2 r9, y1 r12, y2 r11 ---- */
            mrf = mrf + r6 * r9  (ssi), r9 = dm(i2, 0);
            mrf = mrf + r4 * r9  (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r5 * r10 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            mrf = mrf + r8 * r11 (ssi);
            r2 = mr0f;
            r3 = mr1f;
#if DSP4_BQ_ROUNDONCE
            r0 = lshift r2 by -28;
            r0 = r0 or lshift r3 by 4;
            mrf = mrf - r0 * r13 (ssi);
        .bqs_samp: r11 = pass r0, dm(i2, 2) = r0;
#else
            r0 = lshift r2 by -28;
            r1 = lshift r3 by 4;
            r1 = r1 or r0;
            r0 = ashift r3 by -28;
            r2 = ashift r3 by -31;
            r2 = r15 xor r2;
            r3 = ashift r1 by -31;
            comp(r0, r3);
            if ne r1 = pass r2;
            mrf = mrf - r1 * r13 (ssi);
        .bqs_samp: r11 = pass r1, dm(i2, 2) = r1;
#endif

        r0 = 1;
        mrf = mrf - r14 * r0 (ssi);   /* take the rounding half back out */
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

#if DSP4_BQ_GUARD
    /* ---- THE EXIT SCALE AND THE SINGLE CLAMP, still in SIMD, over the
     * block the last stage wrote. The saturated value is built BEFORE
     * the compare -- the ALU ops that build it would overwrite the flags
     * it is conditioned on -- and the move is a per-PE CONDITIONAL
     * COMPUTE, not a branch, because a branch would take PEx's condition
     * for both strips. ---- */
    r0 = dm(_bqs_gd);
    r0 = pass r0;
    if eq jump (pc, .bqs_noexi);
    r13 = dm(_bqs_hp);         /* +H, per PE */
    r14 = dm(_bqs_hm);         /* -H, per PE */
    r15 = 0x7FFFFFFF;
    lcntr = DSP4_BLOCK_SIZE, do .bqs_exi until lce;
        r0 = dm(i2, 0);
        r1 = ashift r0 by -31;      /* sign of y            */
        r1 = r15 xor r1;            /* MAX, or MIN          */
        r2 = ashift r0 by r13;      /* candidate = y << H   */
        r3 = ashift r2 by r14;      /* candidate >> H       */
        comp(r3, r0);
        if ne r2 = pass r1;
    .bqs_exi: dm(i2, 2) = r2;
.bqs_noexi:
#endif

#if DSP4_BQ_TRACE
    r0 = 3; dm(_bqs_phase) = r0;
#endif
    r0 = dm(_simd_mode1_save);
    mode1 = r0;                /* restores PEYEN and IRPTEN together */
    nop;
    nop;
#if DSP4_BQ_TRACE
    r0 = 4; dm(_bqs_phase) = r0;
#endif
    rts;
_bq_fx_cascade_simd.end:
#endif  /* !DSP4_BQ_FLOAT */
#endif

#if DSP4_BQ_PAIRED
/*----------------------------------------------------------------------
 * _bq_pair_blk — run TWO strips' cascades as one SIMD instruction stream.
 *
 * SIMD needs its operands interleaved, and the obvious way to get that is
 * to restructure the whole block pool from 32 independent strips into 16
 * pairs. This does not: it gathers the two strips into an interleaved
 * scratch, runs the paired cascade, and scatters back. The overhead is
 * 196 memory ops per pair per block for FILT (2 stages) -- about 4
 * cycles/sample/strip at the measured 1.3 cycles per memory op -- against
 * a saving of 51 cycles/sample/strip. It pays roughly twelve times over,
 * and it leaves the pool, the node buffers and every other kernel alone.
 *
 * In:  r8 = strip A coeffs   r9  = strip A state   r10 = strip A block
 *      r11 = strip B coeffs  r12 = strip B state   r13 = strip B block
 *      r4  = stages (1..4)
 * Clobbers freely -- callers treat this as a block-rate call.
 *--------------------------------------------------------------------*/
.section/dm seg_dmda;
#if DSP4_BQ_GUARD
.var _bqp_coeff[42];        /* 2 strips x (1 header + 4 stages x 5)   */
#else
.var _bqp_coeff[40];        /* 2 strips x 4 stages x 5                */
#endif
.var _bqp_state[48];        /* 2 strips x 4 stages x 6                */
.var _bqp_sig[2*DSP4_BLOCK_SIZE];  /* 2 strips x BLOCK samples        */
/* THE SCATTER-BACK POINTERS, PARKED ACROSS THE SIMD CALL. See the note
 * on the save below -- this is what the paired-cascade hang was. */
.var _bqp_save[5];          /* r9, r10, r12, r13, r14                 */
#if DSP4_BQ_TRACE
/* 1 entered  2 coeffs interleaved  3 state interleaved  4 signal
 * interleaved  5 cascade returned  6 pointers reloaded  7 signal
 * scattered  8 state scattered (about to rts).  Two words: PEYEN is
 * down here, but the wrapper shares its buffers with a routine that
 * sets it, and a padded counter cannot be wrong. */
.var _bqp_phase[2] = 0, 0;
.global _bqp_phase;
#endif

.section/pm seg_pmco;
.global _bq_pair_blk;
_bq_pair_blk:
#if DSP4_BQ_TRACE
    r0 = 1; dm(_bqp_phase) = r0;
#endif
    l0 = 0;
    l1 = 0;
    l2 = 0;
    l3 = 0;
    l4 = 0;
    l5 = 0;
    r14 = r4;                   /* keep the stage count */

    /* ---- PARK THE POINTERS AND THE STAGE COUNT IN MEMORY ------------
     * THIS IS THE PAIRED-CASCADE HANG (2026-08-29), and it is not a
     * hazard, a loop tail or an interrupt mask: it is a clobbered
     * register.
     *
     * _bq_fx_cascade_simd writes r0-r15 -- r4-r8 are the stage's five
     * coefficients, r9-r12 its four state words, r13/r14/r15 its
     * constants -- so NOTHING this routine holds in a register survives
     * the call. The code after it then did `i0 = r10; i1 = r13;` for the
     * signal scatter and rebuilt the state length from r14, reading the
     * cascade's leftovers: r13 comes back as 0x10000000 and r14 as
     * 0x08000000, so the scatter wrote a block to address 0x10000000 and
     * then entered a hardware loop with lcntr = 0x10000000 -- 268 million
     * iterations, scribbling as it went.
     *
     * That is exactly the symptom the bench saw and could not explain:
     * the part never crashed and the diag ISR kept answering the link,
     * but BOOT_STAGE stopped at 5 and the self-test never set done. It
     * was not hung; it was inside a quarter-billion-iteration loop, and
     * it did that on EVERY call.
     *
     * It also explains the two eliminations already on record. Removing
     * the call (DSP4_SKIP_SIMDCALL=1) boots, because the registers then
     * survive. One stage hangs exactly as four do, because the corrupt
     * lcntr does not depend on the stage count. And the paired DYNAMICS,
     * which have the same PEYEN and no interrupt mask, never hung --
     * their drivers do not carry pointers across the paired kernel.
     *
     * Five words of DM at block rate. r8 and r11 are the coefficient
     * pointers and are not needed again. */
    i2 = _bqp_save;
    dm(i2, 1) = r9;
    dm(i2, 1) = r10;
    dm(i2, 1) = r12;
    dm(i2, 1) = r13;
    dm(i2, 1) = r14;

    /* ---- interleave coefficients: 5 per stage from each strip, plus
     * the one HEADER word each carries in front of them ---- */
    r0 = lshift r14 by 2;
    r0 = r0 + r14;              /* 5 coefficients per stage */
#if DSP4_BQ_GUARD
    r0 = r0 + 1;                /* + the headroom header */
#endif
    i0 = r8;
    i1 = r11;
    i2 = _bqp_coeff;
    lcntr = r0, do .bqp_c until lce;
        r1 = dm(i0, 1);
        dm(i2, 1) = r1;
        r1 = dm(i1, 1);
    .bqp_c: dm(i2, 1) = r1;
#if DSP4_BQ_TRACE
    r0 = 2; dm(_bqp_phase) = r0;
#endif

    /* ---- interleave state: 6 per stage from each strip ---- */
    r0 = lshift r14 by 1;
    r1 = lshift r14 by 2;
    r0 = r0 + r1;               /* 6 state words per stage */
    i0 = r9;
    i1 = r12;
    i2 = _bqp_state;
    lcntr = r0, do .bqp_s until lce;
        r1 = dm(i0, 1);
        dm(i2, 1) = r1;
        r1 = dm(i1, 1);
    .bqp_s: dm(i2, 1) = r1;
#if DSP4_BQ_TRACE
    r0 = 3; dm(_bqp_phase) = r0;
#endif

    /* ---- interleave the two signal blocks ---- */
    i0 = r10;
    i1 = r13;
    i2 = _bqp_sig;
    lcntr = DSP4_BLOCK_SIZE, do .bqp_x until lce;
        r1 = dm(i0, 1);
        dm(i2, 1) = r1;
        r1 = dm(i1, 1);
    .bqp_x: dm(i2, 1) = r1;
#if DSP4_BQ_TRACE
    r0 = 4; dm(_bqp_phase) = r0;
#endif

    /* ---- one instruction stream, both strips ---- */
    i0 = _bqp_coeff;
    i1 = _bqp_state;
    i2 = _bqp_sig;
    r4 = r14;
#if !DSP4_SKIP_SIMDCALL
    call _bq_fx_cascade_simd;
#if DSP4_BQ_TRACE
    r0 = 5; dm(_bqp_phase) = r0;
#endif
    /* Belt and braces: force PEYEN down here regardless of what the MODE1
     * restore did. Kept after the hang was found elsewhere -- it costs
     * three instructions at block rate and a stray PEYEN is a whole class
     * of fault that is very hard to see from the bench. */
    bit clr mode1 0x00200000;
    nop;
    nop;
#endif

    /* ---- everything the cascade clobbered, back from memory ---- */
#if !DSP4_BQP_NOSAVE
    i2 = _bqp_save;
    r9  = dm(i2, 1);
    r10 = dm(i2, 1);
    r12 = dm(i2, 1);
    r13 = dm(i2, 1);
    r14 = dm(i2, 1);
#endif
#if DSP4_BQ_TRACE
    r0 = 6; dm(_bqp_phase) = r0;
#endif

    /* ---- scatter the signal back ---- */
    i2 = _bqp_sig;
    i0 = r10;
    i1 = r13;
    lcntr = DSP4_BLOCK_SIZE, do .bqp_xb until lce;
        r1 = dm(i2, 1);
        dm(i0, 1) = r1;
        r1 = dm(i2, 1);
    .bqp_xb: dm(i1, 1) = r1;
#if DSP4_BQ_TRACE
    r0 = 7; dm(_bqp_phase) = r0;
#endif

    /* ---- and the state, which must persist per strip ---- */
    r0 = lshift r14 by 1;
    r1 = lshift r14 by 2;
    r0 = r0 + r1;               /* 6 state words per stage */
    i2 = _bqp_state;
    i0 = r9;
    i1 = r12;
    lcntr = r0, do .bqp_sb until lce;
        r1 = dm(i2, 1);
        dm(i0, 1) = r1;
        r1 = dm(i2, 1);
    .bqp_sb: dm(i1, 1) = r1;
#if DSP4_BQ_TRACE
    r0 = 8; dm(_bqp_phase) = r0;
#endif
    rts;
_bq_pair_blk.end:
#endif

/*======================================================================
 * THE FLOAT ARM (DSP4_BQ_FLOAT, 2026-09-03) — MEASUREMENT ONLY.
 *
 * PW's fixed-vs-float mandate call is open and this is the input to it:
 * the shootout's RIG A2 arithmetic, wired into the SHIPPING graph
 * cascade path so the answer is a whole-graph capacity number on both
 * parts and not a rig extrapolation. The D5 contract does not move, the
 * fixed/round-once/guard path does not move, and DSP4_BQ_FLOAT=0 is
 * every existing build byte for byte -- every line below is inside the
 * macro and the fixed kernels above are inside its negation.
 *
 * THE ARITHMETIC is DIRECT FORM II TRANSPOSED, which is the right form
 * for float the way the offset DF-I form is right for Q4.28:
 *
 *     y   = w1 + b0*x
 *     w1' = w2 + b1*x - a1*y
 *     w2' =      b2*x - a2*y
 *
 * Five products, no 64-bit extract, no per-stage round, no per-stage
 * saturate, no error-feedback word -- in float the rounding IS the
 * format and there is no remainder to carry.
 *
 * WHAT IT DOES NOT NEED, AND THIS IS THE MEASUREMENT'S POINT. No |h|_1
 * headroom guard: no H sized at parameter-load, no load-time impulse
 * run, no header word in the coefficient block, no entry scale and no
 * exit rescale. The fixed path needs eight bits of mantissa headroom on
 * the 4-band-all-+15 dB cascade because |h|_1 = 1313 (+62 dB) does not
 * fit Q4.28's ceiling of 8; an 8-bit exponent absorbs it with 30 orders
 * of magnitude to spare, so nothing in the cascade can overflow and
 * DSP4_BQ_GUARD is FORCED off (dsp_block.h), not merely defaulted off.
 *
 * WHAT IT DOES STILL NEED IS ONE CLAMP, and the distinction matters to
 * the decision. The INTER-NODE BUS IS STILL Q4.28: the word a cascade
 * hands the next node has to fit +/-8 whatever the cascade did
 * internally. That is ONE `Fn = CLIP Fx BY Fy` per sample on the way
 * out -- a single instruction on the cascade OUTPUT, not a sizing, not a
 * scale, and not a per-stage anything. Symmetric at +/-7.99999952, the
 * largest float32 below Q4.28's ceiling, so the fix cannot wrap.
 *
 * THE DOMAIN CROSSING IS TWO INSTRUCTIONS PER SAMPLE PER CASCADE, and it
 * is a cost of float-inside-a-fixed-graph rather than a cost of float:
 * `Fn = FLOAT Rx BY -28` in, `Rn = FIX Fx BY 28` out, as passes over the
 * block in the block kernels for the same reason the guard's scaling was
 * a pass -- a dedicated pass has the whole register file. A graph that
 * carried float on the bus would not pay it.
 *
 * THE STATE IS 40-BIT. MODE1.RND32 is cleared, so the register file
 * keeps the SHARC's extended-precision float -- 32 mantissa bits against
 * IEEE single's 24 -- through the whole recursion, and the block kernels
 * hold w1/w2 in REGISTERS across all DSP4_BLOCK_SIZE samples of a stage.
 * That is where a high-Q low-frequency biquad's state error accumulates
 * and it is what the 40 bits are for. DSP4_BQ_FLOAT32=1 sets RND32 and
 * makes the arm IEEE single throughout -- RIG A2 exactly -- and is the
 * control the 40 bits are measured against.
 *
 * MODE1 IS SAVED AND RESTORED PER CALL rather than set once at boot. The
 * float boundary mode is global and the image is full of other float
 * code (the coefficient ramps, the legacy meter, the crossfade control
 * plane); an arm that silently re-rounded all of it would not be a
 * measurement of the biquads.
 *
 * FORMATS. Coefficients are the RBJ float words the host already writes
 * over SPI, five per stage [b0, b1, b2, a1, a2], a0 normalised to 1 --
 * so `_bq_fx_convert_N` becomes a COPY and the Q4.28 quantisation step
 * disappears with it. State is w1, w2 in the first two words of the
 * node's existing 6-word-per-stage state block; the other four are left
 * zero, so no generated array changes size and no node's state layout
 * moves.
 *
 * Model: tools/dsp/bq_float_ref.py, normative for these kernels the way
 * fixed_ref.py is for the fixed ones.
 *======================================================================*/
#if DSP4_BQ_FLOAT

.section/dm seg_dmda;
/* MODE1 across a cascade. TWO WORDS: the SIMD kernel restores it with
 * PEYEN still set, where a direct-address read gives PEy the word after
 * -- the same reason _simd_mode1_save is a pair. */
.var _bqfl_m1[2];
/* The Q4.28 ceiling as a float: 0x40FFFFFF is the largest float32 below
 * 8.0, so FIX BY 28 of it is 0x7FFFFF80 and cannot wrap. Two words for
 * the SIMD read. */
.var _bqfl_clip[2] = 0x40FFFFFF, 0x40FFFFFF;

#define BQFL_RND32 0x00010000       /* MODE1.RND32, bit 16 */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _bq_fx_cascade_N — float DF-II-T, N stages, ONE sample.
 *
 * Same contract as the fixed twin: r0 = x in Q4.28 on the way in and
 * y in Q4.28 on the way out, i0/i1 advanced past the stages used (5
 * coefficient and 6 state words each), r13-r15 PRESERVED because the
 * node crossfade bodies hold the input and ya in them.
 *
 * The per-sample path is the slow one by construction and it is not what
 * the graph measurement runs (the block kernels are), but it is what the
 * crossfade bodies and the unconverted node classes call, so it is the
 * same arithmetic and not an approximation of it.
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_N;
_bq_fx_cascade_N:
    r12 = mode1;
    dm(_bqfl_m1) = r12;
#if DSP4_BQ_FLOAT32
    bit set mode1 BQFL_RND32;       /* IEEE single: the 32-bit control */
#else
    bit clr mode1 BQFL_RND32;       /* 40-bit extended: the arm itself */
#endif
    nop;
    r11 = 6;
    m1 = r11;                       /* state stride, set once */
    r11 = -28;
    f0 = float r0 by r11;           /* the domain crossing, in */

    lcntr = r4, do .bqfl_stage until lce;
        f4 = dm(i0, 1);             /* b0 */
        f5 = dm(i0, 1);             /* b1 */
        f6 = dm(i0, 1);             /* b2 */
        f7 = dm(i0, 1);             /* a1 */
        f8 = dm(i0, 1);             /* a2, i0 -> next stage */
        f9  = dm(i1, 1);            /* w1, i1 -> base+1 */
        f10 = dm(i1, 0);            /* w2, i1 parked at base+1 */

        f1 = f4 * f0;
        f1 = f9 + f1;               /* y   = w1 + b0*x  */
        f2 = f5 * f0;
        f2 = f10 + f2;              /* t   = w2 + b1*x  */
        f3 = f7 * f1;
        f9 = f2 - f3;               /* w1' = t - a1*y   */
        f2 = f6 * f0;
        f3 = f8 * f1;
        f10 = f2 - f3;              /* w2' = b2*x - a2*y */

        dm(i1, -1) = f10;           /* w2' at base+1, i1 -> base+0 */
        dm(i1, 0)  = f9;            /* w1' at base+0, i1 PARKED     */
        modify(i1, m1);             /* -> next stage's state base   */
    .bqfl_stage:
        f0 = pass f1;               /* the cascade: y feeds the next stage */

    /* ---- the ONE clamp, and the domain crossing out ---- */
    f1 = dm(_bqfl_clip);
    f0 = clip f0 by f1;
    r11 = 28;
    r0 = fix f0 by r11;
    r12 = dm(_bqfl_m1);
    mode1 = r12;
    nop;
    rts;
_bq_fx_cascade_N.end:

#if DSP4_BLOCK_KERNELS
/*----------------------------------------------------------------------
 * _bq_fx_cascade_blk — float DF-II-T, N stages, a whole BLOCK.
 *
 * Stage outer, sample inner, coefficients and state in registers across
 * the block -- the same loop SHAPE the fixed block kernel has, so the
 * whole-graph difference between the two arms is the arithmetic and not
 * the structure. There is ONE float block kernel and it serves both the
 * fused and the unfused fixed build: fusion is about keeping the fixed
 * error feedback in the 80-bit accumulator, and float has no error
 * feedback to keep anywhere.
 *
 * REGISTER ALLOCATION IS THE WHOLE DESIGN and the rule was established
 * against the assembler, not from memory: a multifunction multiply reads
 * Fx from F0-F3 and Fy from F4-F7 IN THAT ORDER, and the parallel ALU op
 * reads Fz from F8-F11 and Fw from F12-F15 IN THAT ORDER. Destinations
 * are unrestricted. `f12 = f4 * f0, ...` is rejected; the operand order
 * is not commutative to the encoder even where the arithmetic is.
 *
 *   F0 x   F1 y   F2 a2   F4 b0  F5 b1  F6 b2  F7 a1
 *   F8 w1  F10 w2  F11 t   F9 b2x  F12 b0x  F13 b1x  F14 a1y  F15 a2y
 *
 * Five coefficients and four Fy registers, so exactly one product --
 * a2*y -- is a plain multiply with no ALU partner. EIGHT instructions
 * per sample per stage.
 *
 * In: i0 = coeffs (5/stage), i1 = state (6/stage), i2 = the block in
 *     place (Q4.28 in, Q4.28 out), r4 = stages.
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_blk;
_bq_fx_cascade_blk:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = mode1;
    dm(_bqfl_m1) = r15;
#if DSP4_BQ_FLOAT32
    bit set mode1 BQFL_RND32;
#else
    bit clr mode1 BQFL_RND32;
#endif
    nop;
    r15 = -DSP4_BLOCK_SIZE;
    m2 = r15;                       /* rewind the block per stage */
    r15 = 5;
    m3 = r15;                       /* state base+1 -> next stage's base */

    /* ---- the domain crossing IN, one pass over the block ---- */
    r14 = -28;
    lcntr = DSP4_BLOCK_SIZE, do .bqfl_ent until lce;
        r0 = dm(i2, 0);
        f0 = float r0 by r14;
    .bqfl_ent: dm(i2, 1) = f0;
    modify(i2, m2);

    lcntr = r4, do .bqfl_bstage until lce;
        f4 = dm(i0, 1);             /* b0 */
        f5 = dm(i0, 1);             /* b1 */
        f6 = dm(i0, 1);             /* b2 */
        f7 = dm(i0, 1);             /* a1 */
        f2 = dm(i0, 1);             /* a2 -- the plain-multiply operand */
        f8  = dm(i1, 1);            /* w1, i1 -> base+1 */
        f10 = dm(i1, 0);            /* w2, i1 parked at base+1 */

        lcntr = DSP4_BLOCK_SIZE, do .bqfl_bsamp until lce;
            f0 = dm(i2, 0);                 /* x */
            f12 = f0 * f4;                  /* b0*x */
            f13 = f0 * f5, f1 = f8 + f12;   /* b1*x || y = w1 + b0x */
            f9  = f0 * f6, f11 = f10 + f13; /* b2*x || t = w2 + b1x */
            f14 = f1 * f7;                  /* a1*y */
            f15 = f2 * f1;                  /* a2*y -- a2 cannot sit in the
                                             * Fy quadrant, which is full  */
            f8 = f11 - f14;                 /* w1' = t - a1y */
        .bqfl_bsamp: f10 = f9 - f15, dm(i2, 1) = f1;   /* w2' || store y */

        dm(i1, -1) = f10;           /* w2' at base+1, i1 -> base+0 */
        dm(i1, 1)  = f8;            /* w1' at base+0, i1 -> base+1 */
        modify(i1, m3);
        modify(i2, m2);
    .bqfl_bstage:
        nop;

    /* ---- the ONE clamp and the domain crossing OUT, one pass. i2 was
     * rewound by the stage epilogue, so it is already at the top. ---- */
    f3 = dm(_bqfl_clip);
    r14 = 28;
    lcntr = DSP4_BLOCK_SIZE, do .bqfl_exi until lce;
        f0 = dm(i2, 0);
        f0 = clip f0 by f3;
        r0 = fix f0 by r14;
    .bqfl_exi: dm(i2, 1) = r0;

    r15 = dm(_bqfl_m1);
    mode1 = r15;
    nop;
    rts;
_bq_fx_cascade_blk.end:
#endif  /* DSP4_BLOCK_KERNELS */

/*----------------------------------------------------------------------
 * _bq_fx_convert_N — under the float arm this is a COPY.
 *
 * The host writes RBJ float words over SPI and the float cascade eats
 * RBJ float words, so the whole Q4.28 offset conversion -- five
 * multiplies, five FIXes and the halved-n1 encoding that exists because
 * b1 escapes Q4.28 at Q <= 0.12 -- has nothing left to do. That
 * disappearance is part of what float costs and is reported with the
 * rest of it: it is control-rate work, so it moves no per-block cycles,
 * but it removes the coefficient quantisation from the numeric chain and
 * that IS visible in the response error.
 *
 * In: i0 -> staged float [b0,b1,b2,a1,a2] per stage, i1 -> destination,
 *     r4 = stages. Clobbers r0-r2, r9.
 *----------------------------------------------------------------------*/
.global _bq_fx_convert_N;
_bq_fx_convert_N:
    r0 = r4 + r4;              /* 2n */
    r1 = r0 + r0;              /* 4n */
    r1 = r1 + r4;              /* 5n words */
    lcntr = r1, do .bqfl_cvt until lce;
        r9 = dm(i0, 1);
    .bqfl_cvt: dm(i1, 1) = r9;
    rts;
_bq_fx_convert_N.end:

#if DSP4_BQ_PAIRED
/*----------------------------------------------------------------------
 * _bq_fx_cascade_simd — the same, two strips per instruction stream on
 * the PEx/PEy pair. Coefficients, state and signal INTERLEAVED by strip,
 * the layout the fixed SIMD kernel already uses, so nothing about the
 * pair latch, the gather or the chip-2 interleaved arrays moves.
 *
 * There is no saturation inside the loop here, so unlike the fixed twin
 * there is no per-PE conditional move to get right; the one clamp is in
 * the exit pass and `CLIP` is a compute, evaluated independently in each
 * unit, not a branch on PEx's flags.
 *
 * MODE1 is saved and restored WHOLE and interrupts are NOT masked: the
 * systemic per-ISR PEYEN clear is what makes that safe, and it is the
 * same discipline the fixed SIMD cascade relies on. Masking IRPTEN here
 * is what hung the part on 2026-08-28.
 *----------------------------------------------------------------------*/
.global _bq_fx_cascade_simd;
_bq_fx_cascade_simd:
    l0 = 0; l1 = 0; l2 = 0;
    r15 = -2*DSP4_BLOCK_SIZE;
    m2 = r15;                       /* rewind the interleaved block */
    r15 = 10;
    m3 = r15;                       /* state base+2 -> next stage's base */

    r15 = mode1;
    dm(_bqfl_m1) = r15;
    dm(_bqfl_m1 + 1) = r15;
#if DSP4_BQ_FLOAT32
    bit set mode1 BQFL_RND32;
#else
    bit clr mode1 BQFL_RND32;
#endif
    bit set mode1 0x00200000;       /* PEYEN */
    nop;
    nop;

    /* ---- the domain crossing IN, both strips at once ---- */
    r14 = -28;
    lcntr = DSP4_BLOCK_SIZE, do .bqfl_sent until lce;
        r0 = dm(i2, 0);
        f0 = float r0 by r14;
    .bqfl_sent: dm(i2, 2) = f0;
    modify(i2, m2);

    lcntr = r4, do .bqfl_sstage until lce;
        f4 = dm(i0, 2);
        f5 = dm(i0, 2);
        f6 = dm(i0, 2);
        f7 = dm(i0, 2);
        f2 = dm(i0, 2);
        f8  = dm(i1, 2);            /* w1 pair, i1 -> base+2 */
        f10 = dm(i1, 0);            /* w2 pair, i1 parked    */

        lcntr = DSP4_BLOCK_SIZE, do .bqfl_ssamp until lce;
            f0 = dm(i2, 0);
            f12 = f0 * f4;
            f13 = f0 * f5, f1 = f8 + f12;
            f9  = f0 * f6, f11 = f10 + f13;
            f14 = f1 * f7;
            f15 = f2 * f1;
            f8 = f11 - f14;
        .bqfl_ssamp: f10 = f9 - f15, dm(i2, 2) = f1;

        dm(i1, -2) = f10;           /* w2' pair, i1 -> base+0 */
        dm(i1, 2)  = f8;            /* w1' pair, i1 -> base+2 */
        modify(i1, m3);
        modify(i2, m2);
    .bqfl_sstage:
        nop;

    /* ---- the clamp and the crossing OUT, still in SIMD ---- */
    f3 = dm(_bqfl_clip);
    r14 = 28;
    lcntr = DSP4_BLOCK_SIZE, do .bqfl_sexi until lce;
        f0 = dm(i2, 0);
        f0 = clip f0 by f3;
        r0 = fix f0 by r14;
    .bqfl_sexi: dm(i2, 2) = r0;

    r15 = dm(_bqfl_m1);
    mode1 = r15;                    /* PEYEN and RND32 down together */
    nop;
    nop;
    rts;
_bq_fx_cascade_simd.end:
#endif  /* DSP4_BQ_PAIRED */

#endif  /* DSP4_BQ_FLOAT */
