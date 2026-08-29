/*======================================================================
 * mac64_fx.asm — wide accumulator helpers for the fixed path (D5)
 *
 * Normative model: fixed_ref.mix_sum — bus summing accumulates EXACTLY
 * in a wide accumulator held in memory, with ONE round/saturate at
 * readout. Also the shared MRF->Q4.28 extractor used by fixed summing
 * kernels.
 *
 * THE ACCUMULATOR IS THREE WORDS, [lo, hi, ex] = MR0F, MR1F, MR2F —
 * the WHOLE 80-bit multiplier result, not the low 64 of it.
 *
 * It was two words until 2026-08-29 (review finding D1, the review's
 * one SEVERE). MR2F was discarded on every store and reconstructed on
 * every load by sign-extending `hi`, which makes the stored value a
 * 64-bit Q8.56: range +/-128.0 linear. Nothing saturated it. The
 * readout's saturation check ran on a value that had ALREADY wrapped,
 * so a wrapped sum passed as a clean, full-scale, WRONG-SIGN sample --
 * not as a clip. That boundary is reachable: a strip exit saturates at
 * +/-7.999 and one crosspoint coefficient is Q4.28 up to 7.999
 * (numeric-spec.md), so a single contribution reaches 64.0 and THREE
 * such channels wrap the bus. 32 channels can exceed it by 16x.
 *
 * WHY THREE WORDS RATHER THAN A SATURATING 64-BIT ACCUMULATE (the
 * trade, recorded because the dispatch asked for it):
 *   - Correctness. Saturating at +/-128.0 clips a PARTIAL SUM. A bus
 *     whose contributions cancel -- +100 and -100 -- has a legitimate
 *     small answer, and a saturating accumulate returns the wrong one,
 *     order-dependently. Keeping all 80 bits sums exactly and leaves
 *     the single ruled round/saturate at readout where the spec puts
 *     it. Exactness and order-independence are what the wide
 *     accumulator is FOR (numeric-spec.md, "Accumulators and rounding").
 *   - Reach. 80 bits is +/-2^23 = +/-8388608.0 in Q8.56. A bus takes at
 *     most ~64 contributions, each at most 8.0 x 8.0 = 64.0, so
 *     |sum| <= 4096 = 2^12: eleven bits of margin, 2048x. Wrap is not
 *     merely unlikely, it is unreachable from representable inputs.
 *   - Cost, MEASURED on the part (2026-08-29, numverify.sh timing arm,
 *     200,000 iterations against TCOUNT+tick, 491.52 MHz):
 *         _acc64_mac      27.073 -> 29.076 cycles/MAC   +2.003
 *         _acc64_mac_blk  15.290 -> 17.296 cycles/MAC   +2.005
 *     +2 for BOTH, although the block form costs three more
 *     instructions -- the extra load and store pipeline against each
 *     other. Against ~5-6 for a saturating 64-bit accumulate (the MV
 *     test plus a conditional clamp): cheaper AND stronger. Memory is
 *     +1 word per accumulator slot: 25 words per-sample, 25 x BLOCK in
 *     block builds (200 at BLOCK=8).
 *   - Recovery. Review finding D23 deletes the memory round-trip from
 *     the block form entirely (it reloads the accumulator every
 *     sample); when that lands, this +2 goes with it.
 *
 * Entry points:
 *   _acc64_mac      — acc[i2] += r0 * r1 (exact, 80-bit)
 *       In: i2 -> triple [lo, hi, ex], r0 = sample, r1 = gain (Q4.28)
 *       Preserves r0, r1, i2 (net); clobbers r2, r3, MRF. Needs l2 = 0.
 *   _acc64_rns28    — r0 = sat32(rns(acc[i2], 28)), saturating over
 *       all 80 bits. In: i2 -> triple; Out: r0; i2 advanced +3;
 *       clobbers r1-r3, MRF
 *   _mrf_rns28      — r0 = sat32(rns(MRF, 28)) from the live MRF,
 *       UNCHANGED by D1 (see its own note). Clobbers r1-r3
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

.section/pm seg_pmco;

.global _acc64_mac;
_acc64_mac:
    r2 = dm(i2, 1);            /* lo (i2 -> hi) */
    r3 = dm(i2, 1);            /* hi (i2 -> ex) */
    mr0f = r2;
    mr1f = r3;
    r2 = dm(i2, -2);           /* ex (i2 -> lo) */
    mr2f = r2;
    mrf = mrf + r0 * r1 (ssi);
    r2 = mr0f;
    dm(i2, 1) = r2;            /* lo (i2 -> hi) */
    r2 = mr1f;
    dm(i2, 1) = r2;            /* hi (i2 -> ex) */
    r2 = mr2f;
    dm(i2, -2) = r2;           /* ex (i2 -> lo) */
    rts;
_acc64_mac.end:

.global _acc64_rns28;
_acc64_rns28:
    r1 = dm(i2, 1);            /* lo */
    r2 = dm(i2, 1);            /* hi */
    mr0f = r1;
    mr1f = r2;
    r3 = dm(i2, 1);            /* ex (i2 -> next triple) */
    mr2f = r3;
    r1 = 0x08000000;           /* 2^27 rounding half */
    r3 = 1;
    mrf = mrf + r1 * r3 (ssi);
    r1 = mr0f;
    r2 = mr1f;
    r1 = lshift r1 by -28;
    r3 = lshift r2 by 4;
    r0 = r1 or r3;             /* candidate y = acc >> 28 */
    /* SATURATION over the FULL 80 bits. Two conditions, both required
     * for y to be the true value:
     *   (a) bits 63..59 are the sign of y:  ashift(hi,-28) == ashift(y,-31)
     *   (b) ex is the sign extension of hi.
     * (b) is the one the two-word accumulator could not ask, because it
     * MANUFACTURED ex from hi on every load -- which is why a wrapped
     * sum passed this check as a clean sample. It is tested on the low
     * 16 bits only: MR2F holds bits 79..64 and this core's read-back
     * representation of the unused upper half is not relied on, so the
     * xor is shifted left by 16 to discard whatever is up there. */
    r1 = ashift r2 by -28;
    r3 = ashift r0 by -31;
    comp(r1, r3);
    if ne jump (pc, .acc_sat);
    r1 = ashift r2 by -31;     /* 0 or -1: the sign hi implies */
    r3 = mr2f;
    r3 = r3 xor r1;
    r3 = lshift r3 by 16;      /* keep only the significant half */
    r3 = pass r3;
    if eq rts;
.acc_sat:
    /* saturate to the sign of the TRUE top word (bit 79 = bit 15 of ex) */
    r1 = mr2f;
    r1 = lshift r1 by 16;
    r1 = ashift r1 by -31;     /* 0 or -1 */
    r0 = 0x7FFFFFFF;
    r0 = r0 xor r1;
    rts;
_acc64_rns28.end:

/*----------------------------------------------------------------------
 * _mrf_rns28 — r0 = sat32(rns(MRF, 28)) from the LIVE MRF.
 *
 * UNCHANGED by D1, deliberately. Its callers MAC a single Q4.28 x Q4.28
 * product, |x*g| <= 64.0 = 2^62 in Q8.56, so the value is inside the
 * 64-bit domain by construction and the extra 80-bit test would be
 * four instructions per sample buying nothing. The bus accumulators are
 * the touchpoint that needed it and they have it above.
 *----------------------------------------------------------------------*/
.global _mrf_rns28;
_mrf_rns28:
    r1 = 0x08000000;           /* 2^27 rounding half */
    r3 = 1;
    mrf = mrf + r1 * r3 (ssi);
    r1 = mr0f;
    r2 = mr1f;
    r1 = lshift r1 by -28;
    r3 = lshift r2 by 4;
    r0 = r1 or r3;
    /* saturation: ashift(hi,-28) must equal ashift(y,-31) */
    r1 = ashift r2 by -28;
    r3 = ashift r0 by -31;
    comp(r1, r3);
    if eq rts;
    r0 = 0x7FFFFFFF;
    r1 = ashift r2 by -31;
    r0 = r0 xor r1;
    rts;
_mrf_rns28.end:
