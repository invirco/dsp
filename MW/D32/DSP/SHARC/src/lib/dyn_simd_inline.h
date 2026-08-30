/*======================================================================
 * dyn_simd_inline.h — the paired-dynamics helpers as MACROS.
 *
 * WHY. A `call`/`rts` pair costs 15.04 cycles of pipeline refill on this
 * part on top of its two instructions, measured 2026-08-30 by the ladder
 * in lib/call_selftest.asm and independent of the callee's body and of
 * which object it lives in (review finding D66). `_comp_pair_blk`'s
 * per-sample loop makes SEVEN such pairs — `_compgain_simd`, its nested
 * `_log2q_simd` -> `_polyq_simd` and `_exp2q_simd` -> `_polyq_simd`, and
 * `_mrf_rns28_simd` twice — and `_gate_pair_blk`'s makes three. That is
 * 105 and 45 cycles per SIMD sample of pure branch cost, which is 52.6
 * and 22.6 cycles per sample per CHANNEL, in ten call sites.
 *
 * ONE SOURCE OF TRUTH. Each routine's body lives here exactly once and
 * is used twice: the standalone `_..._simd` entry points in
 * dyn_simd_fx.asm are the macro plus an `rts`, and the pair kernels
 * expand the same macro inline. The arithmetic therefore cannot drift
 * between the called form and the inlined one, which is what makes the
 * bit-exactness bar (dynst.sh, scalar vs paired, 0 of 32) meaningful
 * after the change rather than a diff of two edits of the same text.
 *
 * LABELS. A hardware loop and a jump target need a label, and a macro
 * expanded twice in one scope would define it twice, so every macro that
 * needs one takes it as a parameter. Pass a label that is unique to the
 * expansion site.
 *
 * REGISTERS, unchanged from the called forms:
 *   POLYQ_SIMD     in r0 = t_q31, i0 = table.  out r0.  clobbers r1-r3,r5,l0
 *   LOG2Q_SIMD     in r0 = x Q4.28.            out r0 Q6.25. clobbers r1-r5,i0
 *   EXP2Q_SIMD     in r0 = l Q6.25.            out r0 Q4.28. clobbers r1-r5,i0
 *   MRF_RNS28_SIMD in MRF.                     out r0. clobbers r1-r3
 *   COMPGAIN_SIMD  in r0 = |x|, r8..r11 = par. out r0. clobbers r0-r5,r7,i0
 * Every one of them leaves r6 and r8-r15 alone, which is what the two
 * pair kernels rely on to keep their state in registers across the call
 * sites — and now across the inlined bodies.
 *====================================================================*/
#ifndef DSP4_DYN_SIMD_INLINE_H
#define DSP4_DYN_SIMD_INLINE_H

/* _polyq_fx with a DOUBLED coefficient table: identical arithmetic,
 * identical order, identical rounding; modifier 2 over doubled entries
 * so both units get C[k] instead of PEy getting C[k+1]. */
#define POLYQ_SIMD(L) \
    l0 = 0; \
    r1 = dm(i0, 2); \
    r5 = 5; \
    lcntr = r5, do L until lce; \
        mrf = r1 * r0 (ssi); \
        r2 = 0x40000000; \
        r3 = 1; \
        mrf = mrf + r2 * r3 (ssi); \
        r2 = mr0f; \
        r3 = mr1f; \
        r2 = lshift r2 by -31; \
        r3 = lshift r3 by 1; \
        r1 = r2 or r3; \
        r2 = dm(i0, 2); \
    L: \
        r1 = r1 + r2; \
    r0 = r1;

/* leftz and the variable shifts are per-unit, so the two channels may
 * have completely different exponents. e survives the poly in r4. */
#define LOG2Q_SIMD(L) \
    r1 = leftz r0; \
    r2 = 3; \
    r2 = r2 - r1; \
    r3 = ashift r0 by r1; \
    r4 = 0x7FFFFFFF; \
    r0 = r3 and r4; \
    r4 = r2; \
    i0 = _log2_poly_dup; \
    POLYQ_SIMD(L) \
    r3 = 16; \
    r0 = r0 + r3; \
    r0 = ashift r0 by -5; \
    r2 = lshift r4 by 25; \
    r0 = r0 + r2;

/* The scalar's THREE-WAY BRANCH, flattened: two channels can want
 * different arms, so both candidates are computed unconditionally and
 * selected per unit. The saturation constant is loaded BEFORE the compare
 * it is conditioned on — an ALU op between comp and the conditional move
 * overwrites the flags. */
#define EXP2Q_SIMD(L) \
    r2 = ashift r0 by -25; \
    r4 = r2; \
    r3 = lshift r2 by 25; \
    r1 = r0 - r3; \
    r0 = lshift r1 by 6; \
    i0 = _exp2_poly_dup; \
    POLYQ_SIMD(L) \
    r1 = 2; \
    r1 = r1 - r4; \
    r2 = -r1; \
    r3 = ashift r0 by r2; \
    r4 = -r2; \
    r5 = ashift r3 by r4; \
    r2 = 0x7FFFFFFF; \
    comp(r5, r0); \
    if ne r3 = pass r2; \
    r2 = r1 - 1; \
    r4 = 1; \
    r4 = lshift r4 by r2; \
    r5 = r0 + r4; \
    r2 = -r1; \
    r5 = ashift r5 by r2; \
    r2 = 0; \
    r4 = 32; \
    comp(r1, r4); \
    if ge r5 = pass r2; \
    r0 = pass r5; \
    r2 = 0; \
    comp(r1, r2); \
    if le r0 = pass r3;

/* _mrf_rns28 with its `if eq rts` replaced by a per-unit conditional
 * move: a conditional RETURN is a branch, so it would have taken PEx's
 * flags for both channels and channel B would have saturated whenever
 * channel A did. */
#define MRF_RNS28_SIMD \
    r1 = 0x08000000; \
    r3 = 1; \
    mrf = mrf + r1 * r3 (ssi); \
    r1 = mr0f; \
    r2 = mr1f; \
    r1 = lshift r1 by -28; \
    r3 = lshift r2 by 4; \
    r0 = r1 or r3; \
    r1 = ashift r2 by -31; \
    r3 = 0x7FFFFFFF; \
    r3 = r3 xor r1; \
    r1 = ashift r2 by -28; \
    r2 = ashift r0 by -31; \
    comp(r1, r2); \
    if ne r0 = pass r3;

/* The gain computer, both channels, no branches. LA and LB are the two
 * polynomial loops (log2's and exp2's) and must differ. */
#define COMPGAIN_SIMD(LA, LB) \
    r1 = 0; \
    r2 = 0; \
    r7 = 1; \
    comp(r0, r1); \
    if gt r7 = pass r2; \
    LOG2Q_SIMD(LA) \
    r1 = r0 - r8; \
    r2 = -r10; \
    r3 = 1; \
    comp(r1, r2); \
    if le r7 = pass r3; \
    mrf = r1 * r9 (ssi); \
    r2 = 0x40000000; \
    r3 = 1; \
    mrf = mrf + r2 * r3 (ssi); \
    r2 = mr0f; \
    r3 = mr1f; \
    r2 = lshift r2 by -31; \
    r3 = lshift r3 by 1; \
    r4 = r2 or r3; \
    r0 = r1 + r10; \
    mrf = r0 * r0 (ssi); \
    r2 = 0x01000000; \
    r3 = 1; \
    mrf = mrf + r2 * r3 (ssi); \
    r2 = mr0f; \
    r3 = mr1f; \
    r2 = lshift r2 by -25; \
    r3 = lshift r3 by 7; \
    r5 = r2 or r3; \
    mrf = r5 * r11 (ssi); \
    r2 = 0x01000000; \
    r3 = 1; \
    mrf = mrf + r2 * r3 (ssi); \
    r2 = mr0f; \
    r3 = mr1f; \
    r2 = lshift r2 by -25; \
    r3 = lshift r3 by 7; \
    r5 = r2 or r3; \
    r0 = pass r4; \
    comp(r1, r10); \
    if lt r0 = pass r5; \
    r2 = 0; \
    comp(r10, r2); \
    if eq r0 = pass r4; \
    r0 = -r0; \
    EXP2Q_SIMD(LB) \
    r2 = 0; \
    r3 = 0x10000000; \
    comp(r7, r2); \
    if ne r0 = pass r3;

#endif /* DSP4_DYN_SIMD_INLINE_H */
