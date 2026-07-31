/*======================================================================
 * mac64_fx.asm — 64-bit accumulator helpers for the fixed path (D5)
 *
 * Normative model: fixed_ref.mix_sum — bus summing accumulates EXACTLY
 * in a wide accumulator (memory pairs [lo, hi], two 32-bit words) with
 * ONE round/saturate at readout. Also the shared MRF->Q4.28 extractor
 * used by fixed summing kernels.
 *
 * Entry points:
 *   _acc64_mac      — acc64[i2] += r0 * r1 (exact)
 *       In: i2 -> pair [lo, hi], r0 = sample, r1 = gain (both Q4.28)
 *       Preserves r0, r1, i2 (net); clobbers r2, r3, MRF
 *   _acc64_rns28    — r0 = sat32(rns(acc64[i2], 28))
 *       In: i2 -> pair; Out: r0; i2 advanced +1; clobbers r1-r3, MRF
 *   _mrf_rns28      — r0 = sat32(rns(MRF, 28)) from the live MRF
 *       Clobbers r1-r3
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

.section/pm seg_pmco;

.global _acc64_mac;
_acc64_mac:
    r2 = dm(i2, 1);            /* lo (i2 -> hi) */
    r3 = dm(i2, 0);            /* hi            */
    mr0f = r2;
    mr1f = r3;
    r2 = ashift r3 by -31;
    mr2f = r2;
    mrf = mrf + r0 * r1 (ssi);
    r2 = mr1f;
    dm(i2, -1) = r2;           /* hi (i2 -> lo) */
    r2 = mr0f;
    dm(i2, 0) = r2;            /* lo            */
    rts;
_acc64_mac.end:

.global _acc64_rns28;
_acc64_rns28:
    r1 = dm(i2, 1);            /* lo */
    r2 = dm(i2, 0);            /* hi */
    mr0f = r1;
    mr1f = r2;
    r3 = ashift r2 by -31;
    mr2f = r3;
    /* fall through */
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
_acc64_rns28.end:
