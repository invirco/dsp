/*======================================================================
 * afb_design_fx.asm — the anti-feedback notch design, on the part.
 *
 * WHY THIS EXISTS. It is the graphic EQ's story on a different bank.
 * `ANTI_FB` is a real six-stage biquad cascade with its own
 * dual-instance crossfade, and the 2026-09-08 family walk measured what
 * it did with the numbers the contract gives it: `_afb_notch_freq`,
 * `_afb_notch_gain` and `_afb_notch_q` take their writes and land
 * correctly (1000.0 Hz, -18.0 dB, Q 4.0, read back off the part),
 * `_afb_coeffs_next` never moved, both banks stayed at the compiled
 * identity, and every anti-feedback node in the product passed its
 * input through untouched. `_afb_on` took its write and was read by no
 * emitted line. Nothing converted a parameter into a coefficient
 * because nothing existed to do it.
 *
 * Eighteen addresses per node cannot also carry thirty coefficient
 * words and a swap trigger, so the design belongs here.
 *
 * NORMATIVE MODEL: tools/dsp/afb_ref.py, which checks itself against
 * `bq_float_ref.rbj_peak` over the whole contract domain.
 *
 * WHAT A NOTCH IS, AND WHY IT IS A PEAKING SECTION. A textbook RBJ
 * `notch` has no depth parameter -- it is infinitely deep at f0 -- and
 * the contract carries `AntiFbNotchGain` with the domain
 * `0=-18/127=0/[Lin]`. The depth IS the parameter, so the section that
 * honours the contract is RBJ peaking at negative gain, which is the
 * same design the parametric EQ, the graphic EQ and the crossover all
 * use. At 0 dB it is the EXACT identity, and that is what makes "the
 * notch is off" mean "the sample comes through word for word".
 *
 * NOTHING IS A PER-NOTCH CONSTANT, and that is the difference from the
 * GEQ. A graphic EQ band has a fixed centre and Q, so alpha and
 * k2 = 2*(1 - cos w0) are generated constants and only A moves. Here
 * frequency AND Q are both host-settable across the whole audio band,
 * so sin(w0) and 1 - cos(w0) are computed on the part:
 *
 *     x   = 2*pi*f0/fs                 0.00524 .. 1.5708 rad
 *     s   = x * Ps(x*x)                sin x
 *     u   = (x*x/2) * Pu(x*x)          1 - cos x
 *     k2  = 2*u
 *     al  = s / (2Q)
 *     A   = 2**(g*log2(10)/40)
 *     aA  = al*A     ia = al/A     inv = 1/(1 + ia)
 *     b0  = (1 + aA)*inv
 *     n1  = (k2 + 2*aA)*inv
 *     n2  = (-2*aA)*inv
 *     c1  = (k2 + 2*ia)*inv
 *     c2  = (2*ia)*inv
 *
 * `1 - cos x` COMES FROM ITS OWN POLYNOMIAL AND NEVER FROM A
 * SUBTRACTION -- xover_design_fx.asm's argument, over a much wider
 * domain. At 40 Hz cos x is 0.9999863 and 1 - cos x is 1.37e-5; formed
 * in float32 by subtracting, four significant digits of the quantity
 * the entire pole placement rests on would be gone. `Pu` is a fit of
 * (1 - cos x)/(x*x/2), which has no cancellation in it anywhere. The
 * same holds for c1 = 2 + a1: at 40 Hz a1 is -1.99997, so the readable
 * route would throw away exactly what the offset encoding exists to
 * keep. Both polynomials are degree 5 IN x*x, so the odd/even symmetry
 * of sin and cos is exact by construction; worst relative error 5.9e-11
 * and 8.9e-12, measured by afb_ref.check().
 *
 * A = 2**v WITH |v| UP TO 1.4949, AND THE TREE'S EXPONENT POLYNOMIAL IS
 * FITTED ON [-1, 1]. Rather than carry a second fit, this evaluates
 * 2**(v/2) -- inside +/-0.7475, comfortably in domain -- and SQUARES
 * it, and takes 1/A from 2**(-v/2) squared rather than from a second
 * reciprocal. Worst relative error 1.1e-9, still eighteen times finer
 * than a float32 ulp.
 *
 * THE DOMAINS ARE CLAMPED, NOT DIAGNOSED: 40..12000 Hz, -18..0 dB,
 * Q 1..20, which is what the contract's own Table columns say. A host
 * that asks for 30 kHz is a host fault and the kernel's job is to stay
 * stable; afb_ref.design_notch RAISES on the same input, so a model run
 * cannot pass quietly where the part clamped.
 *
 * `_afb_on` IS READ HERE AND IT IS THE ONLY PLACE IT IS READ. Off
 * designs the compiled identity into every stage, so an anti-feedback
 * node that the host has not switched on passes its input word for
 * word -- the negative control the verification runs. It is not a
 * cheap branch in the audio path: the cascade issues the same
 * instruction stream either way, which is why turning every notch on
 * costs nothing measurable at the block rate.
 *
 * `_afb_ctrl_on` IS STILL READ BY NOTHING, DELIBERATELY. It enables an
 * AUTOMATIC feedback detector -- the thing that finds a ringing
 * frequency and sets a notch itself -- and no detector exists in this
 * firmware. Wiring it to this design step would make an empty switch
 * look implemented. It is left landing at its address, unread, and
 * said so here and in the write-up.
 *
 * Infrastructure (hand-maintained). The TABLES it reads are generated:
 * src/afb_tables.asm, from tools/dsp/dsp_codegen.py via afb_ref.py.
 *======================================================================*/

#include "dsp_block.h"

#define AFB_2PI_FS         0x3909421E    /* 2*pi/48000        */
#define AFB_FMIN           0x42200000    /* 40.0 Hz    — Table 0=40      */
#define AFB_FMAX           0x463B8000    /* 12000.0 Hz — Table 127=12000 */
#define AFB_GMIN           0xC1900000    /* -18.0 dB   — Table 0=-18     */
#define AFB_GMAX           0x00000000    /* 0.0 dB     — Table 127=0     */
#define AFB_QMIN           0x3F800000    /* 1.0        — Table 0=1       */
#define AFB_QMAX           0x41A00000    /* 20.0       — Table 127=20    */
#define AFB_FLAT_EPS       0x3B800000    /* 1/256 dB                     */
#define AFB_LOG2_10_80     0x3D2A152D    /* log2(10)/80 = (log2(10)/40)/2 */
#define AFB_ONE            0x3F800000
#define AFB_TWO            0x40000000
#define AFB_HALF           0x3F000000
#define AFB_NEGONE         0xBF800000
#define AFB_SIN_TERMS      6
#define AFB_VERS_TERMS     6
#define AFB_EXP2_TERMS     9

.section/pm seg_pmco;

.extern _afb_sin_poly;
.extern _afb_vers_poly;
.extern _afb_exp2_poly;

/*----------------------------------------------------------------------
 * _afb_design_N — design `r4` notches into the staging buffer.
 *
 *   i0 -> notch frequencies, float32 Hz, r4 words          (read)
 *   i1 -> notch gains, float32 dB, r4 words                (read)
 *   i4 -> notch Qs, float32, r4 words                      (read)
 *   i2 -> _afb_coeffs_next, 5*r4 words, offset form        (written)
 *   r4 =  notch count
 *   r13 = the node's _afb_on: 0 designs the identity into every stage
 *
 * Clobbers r0-r12, f0-f12, i0-i4, m3, l0-l4. r13 is preserved; r14 is
 * the band counter and IS clobbered; r15 and f13-f15 are untouched.
 *
 * THE COUNTER LIVES IN r14 AND THAT IS NOT A FREE CHOICE. SHARC's
 * register file is unified -- rN and fN are the SAME register -- and
 * holding a count in one of the low sixteen while a float lands in its
 * twin is how the GEQ design walked off the end of its array
 * (lib/geq_design_fx.asm carries that measurement).
 *
 * Control-rate. It runs in the block loop on the block a parameter
 * changed and on no other, so its cost is a transient of the same class
 * as the crossfade it starts. Bounded: r4 notches, four fixed-length
 * polynomial evaluations and two three-step reciprocals each, no
 * data-dependent iteration anywhere, one branch per notch.
 *--------------------------------------------------------------------*/
.global _afb_design_N;
_afb_design_N:
    l0 = 0;
    l1 = 0;
    l2 = 0;
    l3 = 0;
    l4 = 0;
    r14 = r4;                        /* notches remaining */

.afbd_notch:
    f0 = dm(i0, 1);                  /* f0, Hz, as the host wrote it */
    f1 = dm(i1, 1);                  /* gain, dB */
    f8 = dm(i4, 1);                  /* Q */

    /* ---- the On switch, read HERE and nowhere else ---- */
    r2 = pass r13;
    if eq jump (pc, .afbd_flat);

    /* ---- the contract domains, clamped ---- */
    r2 = AFB_FMIN;  f2 = r2;  f0 = max(f0, f2);
    r2 = AFB_FMAX;  f2 = r2;  f0 = min(f0, f2);
    r2 = AFB_GMIN;  f2 = r2;  f1 = max(f1, f2);
    r2 = AFB_GMAX;  f2 = r2;  f1 = min(f1, f2);
    r2 = AFB_QMIN;  f2 = r2;  f8 = max(f8, f2);
    r2 = AFB_QMAX;  f2 = r2;  f8 = min(f8, f2);

    /* ---- a flat notch is the TRIVIAL identity, not the cancelling
     * one: at 0 dB the expression below gives b == a, but built from a
     * pole and a zero on top of each other. Six of those in series on
     * seventeen nodes is recursion noise bought for nothing, and it
     * would mean an anti-feedback node nobody has touched no longer
     * passes its input word for word. */
    f3 = abs f1;
    r2 = AFB_FLAT_EPS;  f2 = r2;
    comp(f3, f2);
    if lt jump (pc, .afbd_flat);

    r2 = AFB_2PI_FS;  f2 = r2;
    f3 = f0 * f2;                    /* x  */
    f4 = f3 * f3;                    /* t = x*x */

    /* ---- s = x * Ps(t) ---- */
    i3 = _afb_sin_poly;
    m3 = AFB_SIN_TERMS-1;
    modify(i3, m3);                  /* -> the highest term */
    m3 = -1;
    f5 = dm(i3, m3);
    lcntr = AFB_SIN_TERMS-1, do .afbd_hs until lce;
        f2 = dm(i3, m3);
        f5 = f5 * f4;
    .afbd_hs: f5 = f5 + f2;
    f5 = f5 * f3;                    /* sin x */

    /* ---- u = (t/2) * Pu(t) ---- */
    i3 = _afb_vers_poly;
    m3 = AFB_VERS_TERMS-1;
    modify(i3, m3);
    m3 = -1;
    f6 = dm(i3, m3);
    lcntr = AFB_VERS_TERMS-1, do .afbd_hu until lce;
        f2 = dm(i3, m3);
        f6 = f6 * f4;
    .afbd_hu: f6 = f6 + f2;
    f6 = f6 * f4;
    r2 = AFB_HALF;  f2 = r2;
    f6 = f6 * f2;                    /* 1 - cos x */
    f9 = f6 + f6;                    /* k2 = 2*(1 - cos x) */

    /* ---- al = s / (2Q). RECIPS is an 8-bit seed; three Newton steps,
     * the same three lib/bq_headroom.asm and the GEQ design take. The
     * argument is 2..40, well conditioned. x is dead from here, so f3
     * is the iteration's scratch. */
    f7 = f8 + f8;                    /* 2Q */
    r2 = AFB_TWO;  f2 = r2;
    f12 = recips f7;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;
    f8 = f5 * f12;                   /* alpha */

    /* ---- A = 2**v, v = g*log2(10)/40, by squaring 2**(v/2) ---- */
    r2 = AFB_LOG2_10_80;  f2 = r2;
    f7 = f1 * f2;                    /* v/2, |v/2| <= 0.7475 */

    i3 = _afb_exp2_poly;
    m3 = AFB_EXP2_TERMS-1;
    modify(i3, m3);
    m3 = -1;
    f10 = dm(i3, m3);
    lcntr = AFB_EXP2_TERMS-1, do .afbd_hA until lce;
        f2 = dm(i3, m3);
        f10 = f10 * f7;
    .afbd_hA: f10 = f10 + f2;
    f10 = f10 * f10;                 /* A */

    r2 = AFB_NEGONE;  f2 = r2;
    f7 = f7 * f2;                    /* -v/2 */

    i3 = _afb_exp2_poly;
    m3 = AFB_EXP2_TERMS-1;
    modify(i3, m3);
    m3 = -1;
    f11 = dm(i3, m3);
    lcntr = AFB_EXP2_TERMS-1, do .afbd_hB until lce;
        f2 = dm(i3, m3);
        f11 = f11 * f7;
    .afbd_hB: f11 = f11 + f2;
    f11 = f11 * f11;                 /* 1/A */

    f10 = f8 * f10;                  /* aA = alpha * A */
    f11 = f8 * f11;                  /* ia = alpha / A */

    /* ---- inv = 1/(1 + ia), three Newton steps ---- */
    r2 = AFB_ONE;  f2 = r2;
    f7 = f2 + f11;
    r2 = AFB_TWO;  f2 = r2;
    f12 = recips f7;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;
    f3 = f7 * f12;  f3 = f2 - f3;  f12 = f12 * f3;

    /* ---- the five offset coefficients ---- */
    r2 = AFB_ONE;  f2 = r2;
    f3 = f2 + f10;                   /* 1 + aA */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* b0 */

    f7 = f10 + f10;                  /* 2*aA */
    f3 = f9 + f7;                    /* k2 + 2aA */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* n1 */

    f3 = f7 * f12;
    r2 = AFB_NEGONE;  f2 = r2;
    f3 = f3 * f2;
    dm(i2, 1) = f3;                  /* n2 = -2aA * inv */

    f7 = f11 + f11;                  /* 2*ia */
    f3 = f9 + f7;                    /* k2 + 2ia */
    f3 = f3 * f12;
    dm(i2, 1) = f3;                  /* c1 */

    f3 = f7 * f12;
    dm(i2, 1) = f3;                  /* c2 = 2ia * inv */

    jump (pc, .afbd_next);

.afbd_flat:
    /* (1, 2, -1, 2, 1) — the compiled identity, bit for bit */
    r2 = AFB_ONE;
    dm(i2, 1) = r2;
    r2 = AFB_TWO;
    dm(i2, 1) = r2;
    r2 = AFB_NEGONE;
    dm(i2, 1) = r2;
    r2 = AFB_TWO;
    dm(i2, 1) = r2;
    r2 = AFB_ONE;
    dm(i2, 1) = r2;

.afbd_next:
    r14 = r14 - 1;
    if gt jump (pc, .afbd_notch);
    rts;
_afb_design_N.end:
