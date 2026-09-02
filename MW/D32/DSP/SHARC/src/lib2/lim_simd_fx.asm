/*======================================================================
 * lim_simd_fx.asm — the paired LIMITER kernel. CHIP 2 ONLY.
 *
 * WHY IT IS NOT IN lib/dyn_simd_fx.asm WITH ITS TWO SIBLINGS. Because
 * src/lib is assembled ONCE and linked into BOTH chips, and chip 1's
 * program memory has no room: with this kernel in the shared library,
 * chip 1's link fails with "Out of memory in output section 'sec_swco'"
 * on any build that also carries DSP4_PROFILE_SIGNAL. Chip 1 has no
 * limiters to pair -- its limiting is per strip and per bus, not a class
 * with sixteen pairable instances -- so it should not be paying for this
 * code at all.
 *
 * src/lib2 is therefore the CHIP-2-ONLY library, assembled alongside
 * src/lib and linked into chip 2 alone. Anything that lands here must be
 * something chip 1 genuinely cannot use; a kernel both chips call belongs
 * in src/lib.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#include "dsp_block.h"
#include "lib/dyn_simd_inline.h"

#if DSP4_SIMD_DYN

.extern _dsim_n;
.extern _dsim_mode1;
.extern _compgain_simd;
.extern _mrf_rns28_simd;

.section/dm seg_dmda;

/* ---- LIMITER pair park ----------------------------------------------
 * PARAMETER ORDER IS THE INTERFACE: attq, relq, thr, slope, halfk, k2 --
 * the two converted alphas followed by the four words _compgain_fx
 * already reads as a block (_lim_cgp_<nid>). That is the COMPRESSOR's
 * eight minus mkq and parq, which the limiter does not have, and it is
 * exactly the node's own declaration order (_lim_attq_, _lim_relq_,
 * _lim_cgp_[4]).
 */
.global _lim_par;   .var _lim_par[12];
.global _lim_st;    .var _lim_st[2];    /* envelope */
.global _lim_sig;   .var _lim_sig[2*DSP4_BLOCK_SIZE];
.var _lim_ptr[6];                       /* parA parB stA stB sigA sigB */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _lim_pair_blk — one block of LIMITER for two channels.
 *
 * In (scalar registers, PEYEN still off):
 *   r4 = &paramsA[6]  r5 = &paramsB[6]   attq relq thr slope halfk k2
 *   r6 = &envA        r7 = &envB         Q4.28, updated in place
 *   r8 = &sigA[BLOCK] r9 = &sigB[BLOCK]  Q4.28, processed in place
 *
 * THE LIMITER IS THE COMPRESSOR WITHOUT THE MAKEUP AND THE PARALLEL MIX,
 * and this kernel is _comp_pair_blk with exactly those two stages
 * removed. The scalar limiter body calls _envq_fx, then _compgain_fx,
 * then one _mrf_rns28 on dry*gain -- three routines whose SIMD twins are
 * the same three this kernel inlines, and which _comp_pair_blk has been
 * bit-exact against in the graph since session 3. Nothing new is
 * computed here; two stages are not computed.
 *
 * WHY IT IS NOT _comp_pair_blk WITH mkq = 1.0 AND parq = FULL. Because
 * that is not the same arithmetic: the makeup stage is a MAC and a
 * ROUND, and rns28(rns28(dry*gain) * 1.0) is not identically
 * rns28(dry*gain) -- it is a second rounding of an already-rounded
 * value. The parallel stage adds a third. Reusing the compressor would
 * have cost three rounds where the limiter's contract has one, on every
 * sample of eighteen instances.
 *
 * r7 belongs to COMPGAIN_SIMD (it carries the per-unit unity flag), which
 * is why the release alpha is reloaded from the park through i3 every
 * sample rather than held -- the same arrangement, and the same reason,
 * as the COMP loop above.
 *--------------------------------------------------------------------*/
.global _lim_pair_blk;
_lim_pair_blk:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;

    i0 = _lim_ptr;
    dm(i0, 1) = r4;
    dm(i0, 1) = r5;
    dm(i0, 1) = r6;
    dm(i0, 1) = r7;
    dm(i0, 1) = r8;
    dm(i0, 1) = r9;

#if DSP4_SIMD_NEGCTL
    r5 = r4;
    r7 = r6;
    r9 = r8;
#endif

    i0 = r4; i1 = r5; i2 = _lim_par;
    lcntr = 6, do .lpb_gp until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .lpb_gp: dm(i2, 1) = r0;

    i0 = r6; i1 = r7; i2 = _lim_st;
    r0 = dm(i0, 0);
    dm(i2, 1) = r0;
    r0 = dm(i1, 0);
    dm(i2, 1) = r0;

    i0 = r8; i1 = r9; i2 = _lim_sig;
    r1 = dm(_dsim_n);
    lcntr = r1, do .lpb_gx until lce;
        r0 = dm(i0, 1);
        dm(i2, 1) = r0;
        r0 = dm(i1, 1);
    .lpb_gx: dm(i2, 1) = r0;

    /* &_lim_par[2] -- the release alpha pair, reloaded per sample */
    r0 = _lim_par;
    r1 = 2;
    r0 = r0 + r1;
    i3 = r0;

    /* ---- widen the datapath ---- */
    r0 = mode1;
    dm(_dsim_mode1) = r0;
    bit set mode1 0x00200000;      /* PEYEN */
    nop;
    nop;

    i1 = _lim_par;
    r6  = dm(i1, 2);               /* attq  */
    r0  = dm(i1, 2);               /* relq  -- read per sample via i3 */
    r8  = dm(i1, 2);               /* thr   */
    r9  = dm(i1, 2);               /* slope */
    r10 = dm(i1, 2);               /* halfk */
    r11 = dm(i1, 2);               /* k2    */
    i1 = _lim_st;
    r14 = dm(i1, 2);               /* envelope */

    i2 = _lim_sig;
    i4 = _lim_sig;
    r5 = dm(_dsim_n);              /* PEYEN is set: reads both words */
    lcntr = r5, do .lpb_lp until lce;
        r13 = dm(i2, 2);           /* dry */

        /* envelope: env += rns(alpha * (|x| - env), 31) */
        r0 = abs r13;
        r4 = r0 - r14;
        r5 = 0;
        r2 = r6;
        r3 = dm(i3, 0);
        comp(r4, r5);
        if le r2 = pass r3;        /* delta <= 0 -> release */
        mrf = r2 * r4 (ssi);
        r2 = 0x40000000;
        r3 = 1;
        mrf = mrf + r2 * r3 (ssi);
        r2 = mr0f;
        r3 = mr1f;
        r2 = lshift r2 by -31;
        r3 = lshift r3 by 1;
        r5 = r2 or r3;
        r14 = r14 + r5;

        /* gain computer -- INLINED, review finding D66's reason */
        r0 = r14;
#if DSP4_DYN_INLINE >= 2
        COMPGAIN_SIMD(.lpb_pq1, .lpb_pq2)
#else
        call _compgain_simd;
#endif

        /* out = rns28(dry * gain). ONE round: the limiter has no makeup
         * and no parallel mix, which is the whole difference from COMP. */
        r1 = r0;
        r0 = r13;
        mrf = r0 * r1 (ssi);
#if DSP4_DYN_INLINE >= 1
        MRF_RNS28_SIMD
#else
        call _mrf_rns28_simd;
#endif
        nop;
        nop;
    .lpb_lp: dm(i4, 2) = r0;

    i1 = _lim_st;
    dm(i1, 2) = r14;               /* envelope back to the park */

    r0 = dm(_dsim_mode1);
    mode1 = r0;                    /* PEYEN down, IRPTEN as the caller had it */
    nop;
    nop;

    /* ---- scatter ---- */
    i2 = _lim_sig;
    i0 = _lim_ptr;
    r0 = dm(i0, 1);
    r1 = dm(i0, 1);
    r2 = dm(i0, 1);
    r3 = dm(i0, 1);
    r4 = dm(i0, 1);
    r5 = dm(i0, 1);
    i0 = r4; i1 = r5;
    r6 = dm(_dsim_n);
    lcntr = r6, do .lpb_sx until lce;
        r0 = dm(i2, 1);
        dm(i0, 1) = r0;
        r0 = dm(i2, 1);
    .lpb_sx: dm(i1, 1) = r0;

    i2 = _lim_st;
    i0 = r2; i1 = r3;
    r0 = dm(i2, 1);
    dm(i0, 0) = r0;
    r0 = dm(i2, 1);
    dm(i1, 0) = r0;
    rts;
_lim_pair_blk.end:

#endif /* DSP4_SIMD_DYN */
