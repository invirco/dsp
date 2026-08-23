/*======================================================================
 * dyn_fx.asm — fixed-point dynamics core (decision D5)
 *
 * NORMATIVE REFERENCE: tools/dsp/fixed_ref.py — these routines mirror
 * log2_q / exp2_q / envelope_step / comp_gain BIT-EXACTLY (with the
 * 2026-07-31 rns definition: (v + half) >> shift, arithmetic).
 * Dynamics levels are carried in the LOG2 DOMAIN, Q6.25.
 *
 * Poly coefficient tables (_log2_poly_fx / _exp2_poly_fx, 6 × Q2.30)
 * are GENERATED into poly_tables_fx.asm from fixed_ref's exact ints.
 *
 * Entry points (register contracts documented per routine; all clobber
 * MRF; none touch r13-r15):
 *   _polyq_fx    — r0 = poly(t): i0 -> 6 Q2.30 coeffs, r0 = t Q0.31
 *                  clobbers r1-r3, r5, i0
 *   _log2q_fx    — r0(Q4.28, must be > 0) -> r0 = log2 Q6.25
 *                  clobbers r1-r5, i0
 *   _exp2q_fx    — r0(Q6.25) -> r0 = 2^l Q4.28 (saturated)
 *                  clobbers r1-r6, i0
 *   _envq_fx     — r0 = x_abs, r1 = env, r2 = alpha_att(Q0.31),
 *                  r3 = alpha_rel -> r0 = env' (fixed_ref.envelope_step)
 *                  clobbers r4, r5
 *   _compgain_fx — r0 = x_abs(Q4.28), i0 -> [thr_q625, slope_q31,
 *                  halfk_q625, k2_q625] -> r0 = gain Q4.28
 *                  clobbers r1-r12, i0 (uses r8-r11 for params)
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

.section/dm seg_dmda;
.extern _log2_poly_fx;
.extern _exp2_poly_fx;

.section/pm seg_pmco;

.global _polyq_fx;
_polyq_fx:
#if DSP4_STUB_POLY
    r0 = 0x20000000;           /* TEMP bisect */
    rts;
#endif
    r1 = dm(i0, 1);            /* acc = C0 */
    r5 = 5;
    lcntr = r5, do .pq_lp until lce;
        mrf = r1 * r0 (ssi);
        r2 = 0x40000000;       /* 2^30 half for >>31 */
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r1 = r2 or r3;         /* rns(acc*t, 31) */
        r2 = dm(i0, 1);
    .pq_lp:
        r1 = r1 + r2;          /* + C[k] */
    r0 = r1;
    rts;
_polyq_fx.end:

.global _log2q_fx;
_log2q_fx:
#if DSP4_STUB_LOG2
    r0 = 0;                    /* TEMP bisect */
    rts;
#endif
    /* e = 3 - leftz(x); m_q31 = x << leftz; t = m & 0x7FFFFFFF */
    r1 = leftz r0;
    r2 = 3;
    r2 = r2 - r1;              /* e (can be negative) */
    r3 = ashift r0 by r1;      /* m (MSB set) */
    r4 = 0x7FFFFFFF;
    r0 = r3 and r4;            /* t_q31 */
    r4 = r2;                   /* save e across poly (r4 is clobber-safe
                                  inside _polyq_fx? it is NOT used there) */
    i0 = _log2_poly_fx;
    call _polyq_fx;            /* r0 = frac Q2.30 */
    r3 = 16;                   /* rns(frac, 5) -> Q6.25 */
    r0 = r0 + r3;
    r0 = ashift r0 by -5;
    r2 = lshift r4 by 25;      /* e << 25 */
    r0 = r0 + r2;
    rts;
_log2q_fx.end:

.global _exp2q_fx;
_exp2q_fx:
#if DSP4_STUB_EXP2
    r0 = 0x10000000;           /* TEMP bisect */
    rts;
#endif
    r2 = ashift r0 by -25;     /* e = floor(l / 2^25) */
    r6 = r2;                   /* save e (polyq spares r6) */
    r3 = lshift r2 by 25;
    r1 = r0 - r3;              /* f_q25 in [0, 2^25) */
    r0 = lshift r1 by 6;       /* t_q31 */
    i0 = _exp2_poly_fx;
    call _polyq_fx;            /* r0 = m Q2.30, in [2^30, 2^31) */
    r1 = 2;
    r1 = r1 - r6;              /* shift = 2 - e */
    r2 = 0;
    comp(r1, r2);
    if gt jump (pc, .e2_right);
    /* shift <= 0: left shift with saturation (m > 0 always) */
    r2 = -r1;
    r3 = ashift r0 by r2;      /* candidate */
    r4 = -r2;
    r5 = ashift r3 by r4;      /* back-shift check */
    comp(r5, r0);
    if eq jump (pc, .e2_lok);
    r3 = 0x7FFFFFFF;
.e2_lok:
    r0 = r3;
    rts;
.e2_right:
    r2 = 32;
    comp(r1, r2);
    if lt jump (pc, .e2_rs);
    r0 = 0;                    /* m < 2^31 -> rounds to 0 for shift>=32 */
    rts;
.e2_rs:
    /* rns(m, shift): half = 1 << (shift-1); (m + half) >> shift */
    r2 = r1 - 1;
    r3 = 1;
    r3 = lshift r3 by r2;
    r0 = r0 + r3;
    r2 = -r1;
    r0 = ashift r0 by r2;
    rts;
_exp2q_fx.end:

.global _envq_fx;
_envq_fx:
    /* env' = env + rns(alpha * (x - env), 31); alpha by delta sign */
    r4 = r0 - r1;              /* delta */
    r5 = 0;
    comp(r4, r5);
    if gt jump (pc, .env_att);
    r2 = r3;                   /* use release alpha */
.env_att:
    mrf = r2 * r4 (ssi);
    r5 = 0x40000000;
    r2 = 1;
    mrf = mrf + r5 * r2 (ssi);
    r5 = mr0f;
    r2 = mr1f;
    r5 = lshift r5 by -31;
    r2 = lshift r2 by 1;
    r5 = r5 or r2;             /* rns(alpha*delta, 31) */
    r0 = r1 + r5;
    rts;
_envq_fx.end:

.global _compgain_fx;
_compgain_fx:
#if DSP4_STUB_COMPGAIN
    r0 = 0x10000000;           /* TEMP bisect: unity Q4.28, do nothing */
    rts;
#endif
    r8 = dm(i0, 1);            /* thr_q625 */
    r9 = dm(i0, 1);            /* slope_q31 */
    r10 = dm(i0, 1);           /* halfk_q625 */
    r11 = dm(i0, 1);           /* k2_q625 */

    r1 = pass r0;
    if le jump (pc, .cg_unity);    /* x <= 0: below any threshold */
    call _log2q_fx;                /* r0 = lvl Q6.25 */
    r1 = r0 - r8;                  /* over */
    r2 = -r10;
    comp(r1, r2);
    if le jump (pc, .cg_unity);
    r2 = pass r10;
    if eq jump (pc, .cg_hard);
    comp(r1, r10);
    if ge jump (pc, .cg_hard);

    /* soft knee: t = over + halfk; t2 = rns(t*t,25); gr = rns(t2*k2,25) */
    r1 = r1 + r10;
    mrf = r1 * r1 (ssi);
    r2 = 0x01000000;               /* 2^24 half for >>25 */
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -25;
    r3 = lshift r3 by 7;
    r12 = r2 or r3;                /* t2 Q6.25 */
    mrf = r12 * r11 (ssi);
    r2 = 0x01000000;
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -25;
    r3 = lshift r3 by 7;
    r12 = r2 or r3;                /* gr Q6.25 */
    jump (pc, .cg_exp);

.cg_hard:
    mrf = r1 * r9 (ssi);           /* over * slope, rns 31 */
    r2 = 0x40000000;
    r3 = 1;
    mrf = mrf + r2 * r3 (ssi);
    r2 = mr0f;
    r3 = mr1f;
    r2 = lshift r2 by -31;
    r3 = lshift r3 by 1;
    r12 = r2 or r3;                /* gr Q6.25 */

.cg_exp:
    r0 = -r12;
    call _exp2q_fx;
    rts;

.cg_unity:
    r0 = 0x10000000;
    rts;
_compgain_fx.end:
