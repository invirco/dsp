/*======================================================================
 * geq_design_fx.asm — the GEQ band design, on the part.
 *
 * WHY THIS EXISTS. The graphic EQ's kernel has always been a real
 * N-stage biquad cascade; what never existed was the step between the
 * contract and it. `defs/products/d24/dsp.csv` gives a GEQ node ONE
 * address per band carrying a gain in dB (`Aux001Geq001..028`, Table
 * `0=-12/127=12/[Lin]`), and 28 addresses cannot carry the 140
 * coefficient words plus a trigger that EQ_BIQUAD's arrangement --
 * the host computes the biquad, the cells alias its base -- needs.
 * Measured on the part 2026-09-08: those 28 words landed in
 * `_geq_coeffs_next[0..27]` as raw dB floats, the active bank never
 * moved off its compiled identity, and every GEQ in the product passed
 * its input through untouched.
 *
 * So the design belongs here. NORMATIVE MODEL: tools/dsp/geq_ref.py
 * (`kernel_band`), which is checked against `bq_float_ref.rbj_peak`
 * band by band across the domain -- the filter is the same RBJ peaking
 * section every other family in this tree uses, and nothing about it is
 * invented in assembly.
 *
 * THE EXPRESSION, and the one thing that must not be got wrong. With
 * f0 and Q fixed per band, only A = 10**(g/40) moves:
 *
 *     aA = alpha * A        ia = alpha / A       inv = 1 / (1 + ia)
 *     b0 = (1 + aA) * inv
 *     n1 = (k2 + 2*aA) * inv
 *     n2 = (-2*aA) * inv
 *     c1 = (k2 + 2*ia) * inv
 *     c2 = (2*ia) * inv                k2 = 2*(1 - cos w0)
 *
 * which is the float arm's offset encoding directly. THE READABLE ROUTE
 * -- design b0..a2, then c1 = 2 + a1 -- IS WRONG ON THE PART AND WOULD
 * NOT LOOK IT. At 20 Hz a1 is -1.99999 and c1 is 6.8e-6; forming a1 in
 * float32 first carries about 1.2e-7 of absolute error into a
 * subtraction of two near-equal numbers, so c1 would come out two
 * percent wrong -- exactly the error the offset encoding exists to
 * remove, thrown away in the step that computes it. k2 is a PER-BAND
 * CONSTANT computed in double at generation time, so the small number
 * is never formed by cancelling here.
 *
 * A = 2**(g * log2(10)/40). Over the contract's +/-12 dB the exponent
 * is inside +/-0.9966, so ONE degree-8 polynomial on [-1, 1] covers it
 * with no range reduction, no table lookup and no branch, and 2**-u
 * comes from the same polynomial rather than a second reciprocal. Its
 * worst relative error is 2.1e-9, seventeen times finer than a float32
 * ulp; geq_ref.check() re-measures that rather than trusting this
 * comment.
 *
 * A FLAT BAND IS THE TRIVIAL IDENTITY. At 0 dB the expression gives
 * b == a -- a true identity, but built from a pole and a zero on top of
 * each other near the unit circle, and twenty-eight of those in series
 * on seventeen nodes is recursion noise bought for nothing. |g| under
 * 1/256 dB writes (1, 2, -1, 2, 1), which is the set every GEQ bank is
 * COMPILED with, so an untouched graphic EQ still passes its input word
 * for word. The model applies the same test with the same constant.
 *
 * THE DOMAIN IS CLAMPED, not diagnosed: `CLIP` to +/-12 dB. A band
 * asked for +40 dB is a host fault and the kernel's job is to stay
 * stable; geq_ref.design_band RAISES on the same input, so a model run
 * cannot pass quietly where the part clamped.
 *
 * Infrastructure (hand-maintained). The TABLES it reads are generated:
 * src/geq_tables.asm, from tools/dsp/dsp_codegen.py.
 *======================================================================*/

#include "dsp_block.h"

#define GEQ_FLAT_EPS_F32   0x3B800000    /* 1/256 dB          */
#define GEQ_LIMIT_F32      0x41400000    /* 12.0 dB           */
#define GEQ_LOG2_10_40     0x3DAA152D    /* log2(10)/40       */
#define GEQ_ONE_F32        0x3F800000
#define GEQ_TWO_F32        0x40000000
#define GEQ_NEGONE_F32     0xBF800000
#define GEQ_EXP2_TERMS     9

.section/pm seg_pmco;

.extern _geq_exp2_poly;

/*----------------------------------------------------------------------
 * _geq_design_N — design `r4` bands into the staging buffer.
 *
 *   i0 -> gains, float32 dB, r4 words                     (read)
 *   i1 -> band constants, float32 (alpha, k2) pairs       (read)
 *   i2 -> _geq_coeffs_next, 5*r4 words, offset form       (written)
 *   r4 =  band count
 *
 * Clobbers r0-r12, f0-f12, r14, i0-i3, m3, l0-l3. Returns nothing: the
 * caller raises its own swap_pending, because only the caller knows
 * which node's crossfade this belongs to.
 *
 * Control-rate. It runs in the block loop on the block a gain changed
 * and on no other, so its cost is a transient of the same class as the
 * crossfade it starts -- and it is bounded: r4 bands, no data-dependent
 * iteration anywhere, one branch per band on the flat test.
 *--------------------------------------------------------------------*/
.global _geq_design_N;
_geq_design_N:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    l3 = 0;
    /* THE BAND COUNTER LIVES IN r14 AND THAT IS NOT A FREE CHOICE.
     * SHARC's register file is unified: r12 and f12 are the SAME
     * register, and the first version of this routine held the counter
     * in r12 while `inv` went into f12. The count then became the float
     * bits of 1/(1+ia) -- about 1.07e9 -- and the loop marched past the
     * end of _geq_coeffs_next writing designed coefficients into
     * whatever followed, until a band read out of the tables happened to
     * produce a negative `inv` and the `if gt` fell through.
     *
     * It did not look like memory corruption. The first 140 words were
     * PERFECT (1-3 ulps against the model, response inside 0.0002 dB)
     * and the part stayed up, because everything the overrun touched is
     * rewritten every block -- except _geq_active, which is not. That
     * word held n1 = 2.0f, `pass` read it as non-zero, the cascade ran
     * the bank the design had NOT gone into, and the graphic EQ went on
     * passing its input through with a correct coefficient set sitting
     * in the other bank. Measured on the part 2026-09-08.
     *
     * f13-f15 are untouched here, so r13-r15 are the safe integers. */
    r14 = r4;                        /* bands remaining */

.geqd_band:
    f0 = dm(i0, 1);                  /* g, dB, as the host wrote it */
    f8 = dm(i1, 1);                  /* alpha */
    f9 = dm(i1, 1);                  /* k2 = 2*(1 - cos w0) */

    r2 = GEQ_LIMIT_F32;
    f2 = r2;
    f0 = clip f0 by f2;              /* the contract domain, clamped */

    f1 = abs f0;
    r2 = GEQ_FLAT_EPS_F32;
    f2 = r2;
    comp(f1, f2);
    if lt jump (pc, .geqd_flat);

    /* ---- A = 2**(g * log2(10)/40), and 1/A from the same polynomial */
    r2 = GEQ_LOG2_10_40;
    f2 = r2;
    f4 = f0 * f2;                    /* u, |u| <= 0.9966 */

    i3 = _geq_exp2_poly;
    m3 = GEQ_EXP2_TERMS-1;
    modify(i3, m3);                  /* -> the highest term */
    m3 = -1;
    f5 = dm(i3, m3);
    lcntr = GEQ_EXP2_TERMS-1, do .geqd_hA until lce;
        f2 = dm(i3, m3);
        f5 = f5 * f4;
    .geqd_hA: f5 = f5 + f2;          /* f5 = A */

    r2 = GEQ_NEGONE_F32;
    f2 = r2;
    f4 = f4 * f2;                    /* -u */

    i3 = _geq_exp2_poly;
    m3 = GEQ_EXP2_TERMS-1;
    modify(i3, m3);
    m3 = -1;
    f6 = dm(i3, m3);
    lcntr = GEQ_EXP2_TERMS-1, do .geqd_hB until lce;
        f2 = dm(i3, m3);
        f6 = f6 * f4;
    .geqd_hB: f6 = f6 + f2;          /* f6 = 1/A */

    /* ---- the two products the whole set is built from ---- */
    f10 = f8 * f5;                   /* aA = alpha * A   */
    f11 = f8 * f6;                   /* ia = alpha / A   */

    /* ---- inv = 1/(1 + ia). RECIPS is an 8-bit seed; three Newton
     * steps, the same three lib/bq_headroom.asm takes. The argument
     * here is between 1.0 and about 1.3, so this is the easy case for
     * it and the iteration count is inherited rather than re-derived. */
    r2 = GEQ_ONE_F32;
    f2 = r2;
    f7 = f2 + f11;                   /* d = 1 + ia */
    r2 = GEQ_TWO_F32;
    f2 = r2;
    f12 = recips f7;
    f3 = f7 * f12;
    f3 = f2 - f3;
    f12 = f12 * f3;
    f3 = f7 * f12;
    f3 = f2 - f3;
    f12 = f12 * f3;
    f3 = f7 * f12;
    f3 = f2 - f3;
    f12 = f12 * f3;                  /* inv */

    /* ---- the five offset coefficients ---- */
    r2 = GEQ_ONE_F32;
    f2 = r2;
    f3 = f2 + f10;                   /* 1 + aA */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* b0 */

    f7 = f10 + f10;                  /* 2*aA */
    f3 = f9 + f7;                    /* k2 + 2aA */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* n1 */

    f3 = f7 * f12;
    r2 = GEQ_NEGONE_F32;
    f2 = r2;
    f3 = f3 * f2;
    dm(i2, 1) = f3;                  /* n2 = -2aA * inv */

    f7 = f11 + f11;                  /* 2*ia */
    f3 = f9 + f7;                    /* k2 + 2ia */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* c1 */

    f3 = f7 * f12;
    dm(i2, 1) = f3;                  /* c2 = 2ia * inv */

    jump (pc, .geqd_next);

.geqd_flat:
    /* (1, 2, -1, 2, 1) — the compiled identity, bit for bit */
    r2 = GEQ_ONE_F32;
    dm(i2, 1) = r2;
    r2 = GEQ_TWO_F32;
    dm(i2, 1) = r2;
    r2 = GEQ_NEGONE_F32;
    dm(i2, 1) = r2;
    r2 = GEQ_TWO_F32;
    dm(i2, 1) = r2;
    r2 = GEQ_ONE_F32;
    dm(i2, 1) = r2;

.geqd_next:
    r14 = r14 - 1;
    if gt jump (pc, .geqd_band);
    rts;
_geq_design_N.end:
