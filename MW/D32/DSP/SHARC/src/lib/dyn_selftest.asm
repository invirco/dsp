/*======================================================================
 * dyn_selftest.asm — is the PAIRED dynamics the same arithmetic?
 *
 * Runs the SCALAR dynamics and the SIMD PAIR on byte-identical data
 * inside the part and diffs them, then times both over the same work.
 *
 * THE BAR THIS HAS TO CLEAR, from the fusion session: a pair that quietly
 * computed channel N twice would pass any test whose two channels carry
 * the same data. So every channel-dependent quantity here DIFFERS between
 * A and B -- stimulus, attack, release, threshold, ratio, makeup,
 * parallel blend, knee, range and hold -- and the second block is chosen
 * so the two lanes sit in DIFFERENT ARMS of every branch this pairing
 * predicates:
 *
 *   block 1  A: full-rate +/-0.5 square      B: ramp through both thresholds
 *   block 2  A: silence                      B: steady -24 dBFS
 *
 * In block 2 channel A is on the compressor's UNITY path with its gate
 * closing into hold, while channel B is above both thresholds on the SOFT
 * KNEE with its gate held open -- and A's knee is HARD where B's is soft,
 * so the knee select is exercised in opposite directions in the same
 * instruction. Two consecutive blocks, so envelope, gain, target and hold
 * count have to survive the park's gather and scatter; a block-boundary
 * persistence fault cannot hide.
 *
 * The reference is the scalar dynamics itself -- _envq_fx, _log2q_fx,
 * _compgain_fx, _mrf_rns28 -- driven by a loop that is instruction-for-
 * instruction the generated block kernel. Proving the pair against a
 * model would prove the model.
 *
 * ITERATION COUNT is 2048 and that is a ceiling, not a preference. The
 * self-test owns the main loop while it runs, and the main loop is what
 * drains the SPI2 request FIFO -- at 8192 the arms total ~700 ms of link
 * silence and the response stream comes back permanently out of phase
 * (the same failure mode that made the selftest's first placement
 * unusable). At 2048 the whole test is ~180 ms and the link survives it.
 * The cost is tick quantisation: the shortest arm is ~13 ticks, so a
 * single reading carries about +/-4 %, which is why the numbers below are
 * quoted from repeated runs rather than one.
 *
 * TIMING is against the 1 kHz diag tick over many iterations, the same
 * instrument the biquad pair used (TCOUNT read back values inconsistent
 * with its TPERIOD reload and is not trusted here). The scalar arm is
 * also the CALIBRATION: it should land near the 426.1 and 248.3
 * cycles/sample that sigprofile.sh measured for COMP and GATE on the
 * graph. If it does not, the harness is wrong and the paired number is
 * not quotable either.
 *
 * Debug only: DSP4_SIMD_DYN. Not built into any shipping image.
 *====================================================================*/

#include "dsp_block.h"

#if DSP4_SIMD_DYN

.section/dm seg_dmda;

/* ---- stimulus: two blocks per channel, deliberately unequal ----
 *
 * FILLED AT RUN TIME by _dst_fillx, from DSP4_BLOCK_SIZE. It used to be
 * these initialisers, laid out as 32 samples of block 1 followed by 32 of
 * block 2 -- and the whole point of block 2 is that it puts the two
 * channels in OPPOSITE arms of every predicated branch (A silent on the
 * compressor's unity path with its gate closing into hold, B still above
 * both thresholds). At BLOCK=8 the second block came out of words 8..15,
 * which are still block 1's square wave, and the test quietly lost the
 * branch coverage it exists for. The initialisers below are left as
 * documentation of the intended shape; the array is 64 words so any block
 * size up to 32 fits.
 */
.global _dst_xA;
.var _dst_xA[64] =
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x08000000, 0xF8000000, 0x08000000, 0xF8000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000;

.global _dst_xB;
.var _dst_xB[64] =
    0x00000000, 0x00800000, 0x01000000, 0x01800000,
    0x02000000, 0x02800000, 0x03000000, 0x03800000,
    0x04000000, 0x04800000, 0x05000000, 0x05800000,
    0x06000000, 0x06800000, 0x07000000, 0x07800000,
    0x08000000, 0x08800000, 0x09000000, 0x09800000,
    0x0A000000, 0x0A800000, 0x0B000000, 0x0B800000,
    0x0C000000, 0x0C800000, 0x0D000000, 0x0D800000,
    0x0E000000, 0x0E800000, 0x0F000000, 0x0F800000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000,
    0x01000000, 0x01000000, 0x01000000, 0x01000000;

/* ---- parameters, per channel, in the pair kernels' interface order ----
 * COMP: attq relq mkq parq thr slope halfk k2
 *   A  att 0.25  rel 0.01   makeup 1.0  parallel 0     thr -20 dB  ratio 4  HARD knee
 *   B  att 0.5   rel 0.002  makeup 1.5  parallel 0.25  thr -30 dB  ratio 2  12 dB knee
 * GATE: attq relq thrq rngq hold
 *   A  att 0.25  rel 0.01   thr -30 dB  range 0.001  hold 8
 *   B  att 0.5   rel 0.005  thr -45 dB  range 0.05   hold 3
 * Converted with the same formulas _fx_dyn_block_cvt emits at block rate.
 */
.global _dst_cpA;  .var _dst_cpA[8] = 0x20000000, 0x0147AE14, 0x10000000, 0x00000000, 0xF95B2C3E, 0x60000000, 0x00000000, 0x00000000;
.global _dst_cpB;  .var _dst_cpB[8] = 0x40000000, 0x00418937, 0x18000000, 0x20000000, 0xF608C25D, 0x40000000, 0x01FE3F87, 0x00403840;
.global _dst_gpA;  .var _dst_gpA[5] = 0x20000000, 0x0147AE14, 0xF608C25D, 0x00041893, 0x00000008;
.global _dst_gpB;  .var _dst_gpB[5] = 0x40000000, 0x00A3D70A, 0xF10D238B, 0x00CCCCCD, 0x00000003;

/* working buffers: reference results, paired results */
.global _dst_rA;   .var _dst_rA[64];
.global _dst_rB;   .var _dst_rB[64];
.global _dst_pA;   .var _dst_pA[64];
.global _dst_pB;   .var _dst_pB[64];

/* verdicts */
.global _dst_done;      .var _dst_done = 0;
.global _dst_cndiff;    .var _dst_cndiff = 0;
.global _dst_cmaxdiff;  .var _dst_cmaxdiff = 0;
.global _dst_cfirst;    .var _dst_cfirst = -1;
.global _dst_gndiff;    .var _dst_gndiff = 0;
.global _dst_gmaxdiff;  .var _dst_gmaxdiff = 0;
.global _dst_gfirst;    .var _dst_gfirst = -1;

/* tick counts: [comp scalar, comp pair, gate scalar, gate pair, null] */
.global _dst_tick;      .var _dst_tick[20] =
    0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0;
/* ITERATIONS, SCALED BY THE BLOCK. The cap exists because the self-test
 * owns the main loop while it runs and the main loop is what drains the
 * SPI2 request FIFO: much past ~180 ms of link silence and the response
 * stream comes back permanently out of phase. 2048 iterations was that
 * budget at BLOCK=32; at BLOCK=8 each iteration is a quarter of the work,
 * so the same wall clock buys four times as many -- and the timing is read
 * in whole milliseconds, so at 2048 a paired arm came back as ONE tick and
 * every ratio was quantised into uselessness. */
.global _dst_iters;     .var _dst_iters = 65536/DSP4_BLOCK_SIZE;

#if DSP4_SIMD_PROBE
/* ---- biquad pairing arm ------------------------------------------
 * The 2.39x on record for the biquad pair was measured against the OLD
 * block cascade. Strip fusion then took 32 % out of that baseline, so the
 * pairing FACTOR on the cascade the graph now runs is an open number, not
 * the one on record. Both arms here run the CURRENT routines:
 * _bq_fx_cascade_blk (the fused form under DSP4_STRIP_FUSED) against
 * _bq_pair_blk, which interleaves, runs _bq_fx_cascade_simd and scatters
 * back -- so the pairing overhead is inside the timed span, as it must be.
 *
 * Coefficients DIFFER between the two channels and between the stages:
 * equal stages hide a stage-pointer fault and unity stages hide
 * everything. Stage 1/3 are a 1 kHz LPF Q0.707, stage 2/4 a 300 Hz HPF
 * Q2, swapped between the channels.
 */
.global _dst_bcA;  .var _dst_bcA[20] =
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63,
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63;
.global _dst_bcB;  .var _dst_bcB[20] =
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63,
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC,
    0x0FD6A007, 0x00000000, 0x00000000, 0x0055E080, 0x004F9F63,
    0x00100A4E, 0x00402937, 0x00000000, 0x02F47534, 0x02B44BFC;
.var _dst_bsA[24];
.var _dst_bsB[24];
.global _dst_bndiff;    .var _dst_bndiff = 0;
.global _dst_bmaxdiff;  .var _dst_bmaxdiff = 0;
.global _dst_bfirst;    .var _dst_bfirst = -1;
#endif

/* scalar-reference scratch (one channel at a time) */
.var _cref_att;
.var _cref_rel;
.var _cref_mk;
.var _cref_par;
.var _cref_cgp[4];          /* thr slope halfk k2 -- _compgain_fx reads these */
.var _cref_env;
.var _gref_att;
.var _gref_rel;
.var _gref_thr;
.var _gref_rng;
.var _gref_hold;
.var _gref_env;
.var _gref_gain;
.var _gref_tgt;
.var _gref_hc;

/* paired state, in the pair kernels' interface order */
.var _dst_ceA;  .var _dst_ceB;          /* COMP envelope per channel */
.var _dst_gsA[4]; .var _dst_gsB[4];     /* GATE env, gain, target, hold count */

.section/pm seg_pmco;
.extern _envq_fx;
.extern _log2q_fx;
.extern _compgain_fx;
.extern _mrf_rns28;
.extern _comp_pair_blk;
.extern _gate_pair_blk;
/* The pair kernels take their sample count from _dsim_n so the graph
 * driver can hand them BLOCK-1 (sample 0 goes through the scalar body
 * for its block-rate conversion). This test always wants a FULL block,
 * and it shares the image with the drivers, so it sets the count itself
 * rather than trusting whatever ran last. */
.extern _dsim_n;
#if DSP4_SIMD_PROBE
.extern _bq_fx_cascade_blk;
.extern _bq_pair_blk;
#endif
.extern _diag_ticks;

/*----------------------------------------------------------------------
 * _cref_blk — ONE block of the scalar compressor.
 * i3 -> BLOCK input samples, i4 -> BLOCK output samples. State in _cref_env.
 * This IS the generated COMP block kernel's hoisted loop; only the
 * parameter fetches are re-pointed at the scratch above.
 *--------------------------------------------------------------------*/
_cref_blk:
    l3 = 0;
    l4 = 0;
    r7  = dm(_cref_att);
    r14 = dm(_cref_env);
    r15 = dm(_cref_mk);
    lcntr = DSP4_BLOCK_SIZE, do .crb_lp until lce;
        r13 = dm(i3, 1);
        r0 = abs r13;
        r1 = r14;
        r2 = r7;
        r3 = dm(_cref_rel);
        call _envq_fx;
        r14 = r0;
        i0 = _cref_cgp;
        call _compgain_fx;
        r1 = r0;
        r0 = r13;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28;
        r1 = r15;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28;
        r5 = r0 - r13;
        r4 = dm(_cref_par);
        mrf = r5 * r4 (ssi);
        r1 = 0x40000000;
        r12 = 1;
        mrf = mrf + r1 * r12 (ssi);
        r1 = mr0f;
        r12 = mr1f;
        r1 = lshift r1 by -31;
        r12 = lshift r12 by 1;
        r1 = r1 or r12;
        r0 = r13 + r1;
        nop;
        nop;
    .crb_lp: dm(i4, 1) = r0;
    dm(_cref_env) = r14;
    rts;
_cref_blk.end:

/*----------------------------------------------------------------------
 * _gref_blk — ONE block of the scalar gate, likewise the generated
 * kernel's loop with its branches intact.
 *--------------------------------------------------------------------*/
_gref_blk:
    l3 = 0;
    l4 = 0;
    r6  = dm(_gref_att);
    r7  = dm(_gref_rel);
    r8  = dm(_gref_thr);
    r9  = dm(_gref_rng);
    r15 = dm(_gref_hold);
    r10 = dm(_gref_env);
    r11 = dm(_gref_gain);
    r12 = dm(_gref_tgt);
    r14 = dm(_gref_hc);
    lcntr = DSP4_BLOCK_SIZE, do .grb_lp until lce;
        r13 = dm(i3, 1);
        r0 = abs r13;
        r1 = r10;
        r2 = r6;
        r3 = r7;
        call _envq_fx;
        r10 = r0;
        r1 = pass r0;
        if le jump (pc, .grb_below);
        call _log2q_fx;
        comp(r0, r8);
        if ge jump (pc, .grb_open);
    .grb_below:
        r14 = r14 - 1;
        if gt jump (pc, .grb_ramp);
        r12 = r9;
        jump (pc, .grb_ramp);
    .grb_open:
        r12 = 0x10000000;
        r14 = r15;
    .grb_ramp:
        r0 = r12;
        r1 = r11;
        r2 = r6;
        r3 = r7;
        call _envq_fx;
        r11 = r0;
        r1 = r0;
        r0 = r13;
        mrf = r0 * r1 (ssi);
        call _mrf_rns28;
        nop;
        nop;
    .grb_lp: dm(i4, 1) = r0;
    dm(_gref_env)  = r10;
    dm(_gref_gain) = r11;
    dm(_gref_tgt)  = r12;
    dm(_gref_hc)   = r14;
    rts;
_gref_blk.end:

/* copy 8 COMP params from i0 into the scalar scratch */
_cref_load:
    l0 = 0;
    r0 = dm(i0, 1); dm(_cref_att) = r0;
    r0 = dm(i0, 1); dm(_cref_rel) = r0;
    r0 = dm(i0, 1); dm(_cref_mk)  = r0;
    r0 = dm(i0, 1); dm(_cref_par) = r0;
    i1 = _cref_cgp;
    l1 = 0;
    r0 = dm(i0, 1); dm(i1, 1) = r0;
    r0 = dm(i0, 1); dm(i1, 1) = r0;
    r0 = dm(i0, 1); dm(i1, 1) = r0;
    r0 = dm(i0, 1); dm(i1, 1) = r0;
    r0 = 0;
    dm(_cref_env) = r0;
    rts;
_cref_load.end:

/* copy 5 GATE params from i0 into the scalar scratch, state zeroed the
 * way the node's .var initialisers leave it */
_gref_load:
    l0 = 0;
    r0 = dm(i0, 1); dm(_gref_att)  = r0;
    r0 = dm(i0, 1); dm(_gref_rel)  = r0;
    r0 = dm(i0, 1); dm(_gref_thr)  = r0;
    r0 = dm(i0, 1); dm(_gref_rng)  = r0;
    r0 = dm(i0, 1); dm(_gref_hold) = r0;
    r0 = 0;
    dm(_gref_env)  = r0;
    dm(_gref_gain) = r0;
    dm(_gref_tgt)  = r0;
    dm(_gref_hc)   = r0;
    rts;
_gref_load.end:

#if DSP4_SIMD_PROBE
/* zero both channels' cascade state and copy the stimulus into the two
 * working blocks (the cascades work IN PLACE) */
_dst_bprep:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;
    i0 = _dst_bsA;
    i1 = _dst_bsB;
    r0 = 0;
    lcntr = 24, do .dbp_z until lce;
        dm(i0, 1) = r0;
    .dbp_z: dm(i1, 1) = r0;
    i3 = _dst_xA;
    i4 = _dst_pA;
    i5 = _dst_xB;
    i0 = _dst_pB;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dbp_c until lce;
        r0 = dm(i3, 1);
        dm(i4, 1) = r0;
        r0 = dm(i5, 1);
    .dbp_c: dm(i0, 1) = r0;
    rts;
_dst_bprep.end:
#endif

/*----------------------------------------------------------------------
 * _dyn_selftest
 *--------------------------------------------------------------------*/
/*----------------------------------------------------------------------
 * _dst_fillx — lay the stimulus out ONE BLOCK APART, whatever the block.
 *
 *   A  block 1: +/-0.5 square (-6 dBFS)      block 2: silence
 *   B  block 1: ramp, 1/32 FS per sample     block 2: constant 1/16 FS
 *
 * Same two shapes the initialisers describe, but indexed from BLOCK, so
 * block 2 is always block 2.
 *--------------------------------------------------------------------*/
_dst_fillx:
    l0 = 0;
    i0 = _dst_xA;
    r0 = 0x08000000;
    r1 = 0xF8000000;
    lcntr = DSP4_BLOCK_HALF, do .dfx_a1 until lce;
        dm(i0, 1) = r0;
    .dfx_a1: dm(i0, 1) = r1;
    r2 = 0;
    lcntr = DSP4_BLOCK_SIZE, do .dfx_a2 until lce;
    .dfx_a2: dm(i0, 1) = r2;

    i0 = _dst_xB;
    r0 = 0;
    r1 = 0x00800000;
    lcntr = DSP4_BLOCK_SIZE, do .dfx_b1 until lce;
        dm(i0, 1) = r0;
    .dfx_b1: r0 = r0 + r1;
    r2 = 0x01000000;
    lcntr = DSP4_BLOCK_SIZE, do .dfx_b2 until lce;
    .dfx_b2: dm(i0, 1) = r2;
    rts;
_dst_fillx.end:

.global _dyn_selftest;
_dyn_selftest:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;
    call _dst_fillx;

    /* ================= COMPRESSOR: reference ================= */
    i0 = _dst_cpA;
    call _cref_load;
    i3 = _dst_xA;
    i4 = _dst_rA;
    call _cref_blk;
    call _cref_blk;                 /* i3/i4 walked on into block 2 */

    i0 = _dst_cpB;
    call _cref_load;
    i3 = _dst_xB;
    i4 = _dst_rB;
    call _cref_blk;
    call _cref_blk;

    /* ================= COMPRESSOR: paired ==================== */
    i3 = _dst_xA;
    i4 = _dst_pA;
    i5 = _dst_xB;
    i0 = _dst_pB;
    l5 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_ccp until lce;
        r0 = dm(i3, 1);
        dm(i4, 1) = r0;
        r0 = dm(i5, 1);
    .dst_ccp: dm(i0, 1) = r0;
    r0 = 0;
    dm(_dst_ceA) = r0;
    dm(_dst_ceB) = r0;

    r4 = _dst_cpA;  r5 = _dst_cpB;
    r6 = _dst_ceA;  r7 = _dst_ceB;
    r8 = _dst_pA;   r9 = _dst_pB;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    call _comp_pair_blk;
    r4 = _dst_cpA;  r5 = _dst_cpB;
    r6 = _dst_ceA;  r7 = _dst_ceB;
    r0 = _dst_pA;   r1 = DSP4_BLOCK_SIZE;  r8 = r0 + r1;
    r0 = _dst_pB;   r9 = r0 + r1;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    call _comp_pair_blk;

    /* diff, both channels, 2 blocks x 2 channels. Walked BACKWARDS so "first
     * differing index" needs one conditional move and no branch inside a
     * hardware loop -- the hazard that hung the first cut of the biquad
     * self-test on the part. */
    r0 = _dst_rA;  r1 = 2*DSP4_BLOCK_SIZE-1;  r0 = r0 + r1;  i3 = r0;
    r0 = _dst_pA;  r0 = r0 + r1;  i4 = r0;
    r0 = _dst_rB;  r0 = r0 + r1;  i5 = r0;
    r0 = _dst_pB;  r0 = r0 + r1;  i0 = r0;
    r12 = 0; r13 = 0; r14 = -1; r15 = 2*DSP4_BLOCK_SIZE-1;
    r3 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_cd until lce;
        r0 = dm(i3, -1);
        r1 = dm(i4, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
        r0 = dm(i5, -1);
        r1 = dm(i0, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
    .dst_cd: r15 = r15 - 1;
    dm(_dst_cndiff)   = r12;
    dm(_dst_cmaxdiff) = r13;
    dm(_dst_cfirst)   = r14;

    /* ================= GATE: reference ======================= */
    l0 = 0; l3 = 0; l4 = 0; l5 = 0;
    i0 = _dst_gpA;
    call _gref_load;
    i3 = _dst_xA;
    i4 = _dst_rA;
    call _gref_blk;
    call _gref_blk;

    i0 = _dst_gpB;
    call _gref_load;
    i3 = _dst_xB;
    i4 = _dst_rB;
    call _gref_blk;
    call _gref_blk;

    /* ================= GATE: paired ========================== */
    i3 = _dst_xA;
    i4 = _dst_pA;
    i5 = _dst_xB;
    i0 = _dst_pB;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_gcp until lce;
        r0 = dm(i3, 1);
        dm(i4, 1) = r0;
        r0 = dm(i5, 1);
    .dst_gcp: dm(i0, 1) = r0;
    i0 = _dst_gsA;
    i1 = _dst_gsB;
    r0 = 0;
    lcntr = 4, do .dst_gz until lce;
        dm(i0, 1) = r0;
    .dst_gz: dm(i1, 1) = r0;

    r4 = _dst_gpA;  r5 = _dst_gpB;
    r6 = _dst_gsA;  r7 = _dst_gsB;
    r8 = _dst_pA;   r9 = _dst_pB;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    call _gate_pair_blk;
    r4 = _dst_gpA;  r5 = _dst_gpB;
    r6 = _dst_gsA;  r7 = _dst_gsB;
    r0 = _dst_pA;   r1 = DSP4_BLOCK_SIZE;  r8 = r0 + r1;
    r0 = _dst_pB;   r9 = r0 + r1;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    call _gate_pair_blk;

    r0 = _dst_rA;  r1 = 2*DSP4_BLOCK_SIZE-1;  r0 = r0 + r1;  i3 = r0;
    r0 = _dst_pA;  r0 = r0 + r1;  i4 = r0;
    r0 = _dst_rB;  r0 = r0 + r1;  i5 = r0;
    r0 = _dst_pB;  r0 = r0 + r1;  i0 = r0;
    r12 = 0; r13 = 0; r14 = -1; r15 = 2*DSP4_BLOCK_SIZE-1;
    r3 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_gd until lce;
        r0 = dm(i3, -1);
        r1 = dm(i4, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
        r0 = dm(i5, -1);
        r1 = dm(i0, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
    .dst_gd: r15 = r15 - 1;
    dm(_dst_gndiff)   = r12;
    dm(_dst_gmaxdiff) = r13;
    dm(_dst_gfirst)   = r14;

#if DSP4_SIMD_PROBE
    /* ================= BIQUAD PAIR: reference vs pair =========
     * Four stages, two consecutive blocks, both channels. The reference
     * is the same _bq_fx_cascade_blk the graph calls. */
    call _dst_bprep;
    i0 = _dst_bcA; i1 = _dst_bsA; i2 = _dst_pA; r4 = 4;
    call _bq_fx_cascade_blk;
    r0 = _dst_pA; r1 = DSP4_BLOCK_SIZE; r0 = r0 + r1;
    i0 = _dst_bcA; i1 = _dst_bsA; i2 = r0; r4 = 4;
    call _bq_fx_cascade_blk;
    i0 = _dst_bcB; i1 = _dst_bsB; i2 = _dst_pB; r4 = 4;
    call _bq_fx_cascade_blk;
    r0 = _dst_pB; r1 = DSP4_BLOCK_SIZE; r0 = r0 + r1;
    i0 = _dst_bcB; i1 = _dst_bsB; i2 = r0; r4 = 4;
    call _bq_fx_cascade_blk;
    /* park the scalar results */
    i3 = _dst_pA; i4 = _dst_rA; i5 = _dst_pB; i0 = _dst_rB;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_bpk until lce;
        r0 = dm(i3, 1);
        dm(i4, 1) = r0;
        r0 = dm(i5, 1);
    .dst_bpk: dm(i0, 1) = r0;

    call _dst_bprep;
    r8 = _dst_bcA;  r9 = _dst_bsA;  r10 = _dst_pA;
    r11 = _dst_bcB; r12 = _dst_bsB; r13 = _dst_pB;
    /* DSP4_BQ_PAIR_STAGES exists to bisect the paired-cascade hang: the
     * fault is inside _bq_fx_cascade_simd (DSP4_SKIP_SIMDCALL=1 boots and
     * runs), and one stage versus four separates its per-stage rewind and
     * state advance from its sample loop. */
    r4 = DSP4_BQ_PAIR_STAGES;
#if !DSP4_SKIP_PAIR
    call _bq_pair_blk;
#endif
    r8 = _dst_bcA;  r9 = _dst_bsA;
    r0 = _dst_pA; r1 = DSP4_BLOCK_SIZE; r10 = r0 + r1;
    r11 = _dst_bcB; r12 = _dst_bsB;
    r0 = _dst_pB; r13 = r0 + r1;
    r4 = DSP4_BQ_PAIR_STAGES;
#if !DSP4_SKIP_PAIR
    call _bq_pair_blk;
#endif

    r0 = _dst_rA;  r1 = 2*DSP4_BLOCK_SIZE-1;  r0 = r0 + r1;  i3 = r0;
    r0 = _dst_pA;  r0 = r0 + r1;  i4 = r0;
    r0 = _dst_rB;  r0 = r0 + r1;  i5 = r0;
    r0 = _dst_pB;  r0 = r0 + r1;  i0 = r0;
    r12 = 0; r13 = 0; r14 = -1; r15 = 2*DSP4_BLOCK_SIZE-1;
    r3 = 0;
    lcntr = 2*DSP4_BLOCK_SIZE, do .dst_bd until lce;
        r0 = dm(i3, -1);
        r1 = dm(i4, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
        r0 = dm(i5, -1);
        r1 = dm(i0, -1);
        r2 = r0 - r1;
        r2 = abs r2;
        comp(r2, r3);
        if ne r12 = r12 + 1;
        comp(r2, r3);
        if ne r14 = r15;
        comp(r2, r13);
        if gt r13 = r2;
    .dst_bd: r15 = r15 - 1;
    dm(_dst_bndiff)   = r12;
    dm(_dst_bmaxdiff) = r13;
    dm(_dst_bfirst)   = r14;
#endif

    /* ================= TIMING ================================
     * Same work either side: ONE block of BLOCK samples for TWO channels.
     * The scalar arm is the calibration against sigprofile.sh's per-class
     * numbers; the null arm is the loop and call overhead, subtracted
     * from both. */

    /* --- null --- */
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 8) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tn until lce;
        nop;
        nop;
    .dst_tn: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 9) = r0;

    /* --- COMP scalar, two channels --- */
    i0 = _dst_cpA;
    call _cref_load;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 0) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tcs until lce;
        i3 = _dst_xA;
        i4 = _dst_pA;
        call _cref_blk;
        i3 = _dst_xB;
        i4 = _dst_pB;
        call _cref_blk;
        nop;
        nop;
    .dst_tcs: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 1) = r0;

    /* --- COMP paired --- */
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 2) = r0;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tcp until lce;
        r4 = _dst_cpA;  r5 = _dst_cpB;
        r6 = _dst_ceA;  r7 = _dst_ceB;
        r8 = _dst_pA;   r9 = _dst_pB;
        call _comp_pair_blk;
        nop;
        nop;
    .dst_tcp: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 3) = r0;

    /* --- GATE scalar, two channels --- */
    i0 = _dst_gpA;
    call _gref_load;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 4) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tgs until lce;
        i3 = _dst_xA;
        i4 = _dst_pA;
        call _gref_blk;
        i3 = _dst_xB;
        i4 = _dst_pB;
        call _gref_blk;
        nop;
        nop;
    .dst_tgs: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 5) = r0;

    /* --- GATE paired --- */
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 6) = r0;
    r0 = DSP4_BLOCK_SIZE;
    dm(_dsim_n) = r0;
    dm(_dsim_n + 1) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tgp until lce;
        r4 = _dst_gpA;  r5 = _dst_gpB;
        r6 = _dst_gsA;  r7 = _dst_gsB;
        r8 = _dst_pA;   r9 = _dst_pB;
        call _gate_pair_blk;
        nop;
        nop;
    .dst_tgp: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 7) = r0;

#if DSP4_SIMD_PROBE
    /* --- biquad, 4 stages (EQ shape): scalar then paired --- */
    call _dst_bprep;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 10) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tb4s until lce;
        i0 = _dst_bcA; i1 = _dst_bsA; i2 = _dst_pA; r4 = 4;
        call _bq_fx_cascade_blk;
        i0 = _dst_bcB; i1 = _dst_bsB; i2 = _dst_pB; r4 = 4;
        call _bq_fx_cascade_blk;
        nop;
        nop;
    .dst_tb4s: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 11) = r0;

    call _dst_bprep;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 12) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tb4p until lce;
        r8 = _dst_bcA;  r9 = _dst_bsA;  r10 = _dst_pA;
        r11 = _dst_bcB; r12 = _dst_bsB; r13 = _dst_pB;
        r4 = 4;
    #if !DSP4_SKIP_PAIR
    call _bq_pair_blk;
#endif
        nop;
        nop;
    .dst_tb4p: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 13) = r0;

    /* --- biquad, 2 stages (FILT shape) --- */
    call _dst_bprep;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 14) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tb2s until lce;
        i0 = _dst_bcA; i1 = _dst_bsA; i2 = _dst_pA; r4 = 2;
        call _bq_fx_cascade_blk;
        i0 = _dst_bcB; i1 = _dst_bsB; i2 = _dst_pB; r4 = 2;
        call _bq_fx_cascade_blk;
        nop;
        nop;
    .dst_tb2s: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 15) = r0;

    call _dst_bprep;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 16) = r0;
    r10 = dm(_dst_iters);
    lcntr = r10, do .dst_tb2p until lce;
        r8 = _dst_bcA;  r9 = _dst_bsA;  r10 = _dst_pA;
        r11 = _dst_bcB; r12 = _dst_bsB; r13 = _dst_pB;
        r4 = 2;
    #if !DSP4_SKIP_PAIR
    call _bq_pair_blk;
#endif
        nop;
        nop;
    .dst_tb2p: nop;
    r0 = dm(_diag_ticks);
    dm(_dst_tick + 17) = r0;
#endif

    r0 = 1;
    dm(_dst_done) = r0;
    rts;
_dyn_selftest.end:

#endif /* DSP4_SIMD_DYN */
