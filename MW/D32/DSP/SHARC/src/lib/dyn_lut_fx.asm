/*======================================================================
 * dyn_lut_fx.asm — THE LEVEL -> GAIN TABLE: the design step, and the
 * scalar lookup.
 *
 * WHY THIS FILE EXISTS. PW, 2026-09-09: "the compressor and gate cycles
 * could be improved a lot, using LUTs with interpolation, and still fit
 * the SIMD structure", then "and the envelope and knee become part of
 * the LUT graph", against a ruling that the dynamics accuracy target is
 * 0.1 dB worst case over 0 to -100 dBFS rather than the polynomial's
 * 0.0001 dB. So the target form is ONE table, level -> gain: the whole
 * static curve -- threshold, ratio, knee, and for the LIMITER its
 * ceiling -- is BAKED IN by a design step that runs only when a
 * parameter changes, and the per-sample gain computer collapses to
 * envelope -> index -> two words -> interpolate.
 *
 * WHAT IT IS WORTH, measured on the part (dyn_shootout.asm, S14 and
 * re-measured S15 with the arithmetic corrected): the gain computer
 * 215.2 -> 54.1 cycles per sample-pair, 74.9 % off; the WHOLE compressor
 * per-sample body 284.3 -> 123.1, 142.2 -> 61.6 per sample per channel,
 * 56.7 % off.
 *
 * THE INDEX IS A LOGARITHM WITHOUT A LOGARITHM. `leftz` gives the binary
 * exponent, which IS the octave; the top DYN_LUT_K bits of the
 * normalised mantissa sub-divide it. The table is therefore log-spaced
 * by construction and the index costs a count-leading-zeros, two shifts
 * and an add. The remaining mantissa bits, shifted up, ARE the
 * interpolation fraction in Q0.31 -- with one mask that is not optional,
 * see below.
 *
 * THE POINT COUNT IS MEASURED, NOT CHOSEN. tools/dsp/dyn_lut_design.py
 * builds the table on exactly this grid, indexes it with exactly this
 * arithmetic, and sweeps the resulting gain against the repo's own
 * fixed-point reference (tools/dsp/fixed_ref.py::comp_gain):
 *
 *     K   pts/oct   words   COMP defaults   LIMITER defaults
 *     2      4        85       0.045 dB         0.247 dB
 *     3      8       169       0.011 dB         0.028 dB
 *     4     16       337       0.004 dB         0.025 dB
 *
 * and over the whole documented parameter sweep -- 81 sets, thresholds
 * to -60 dB, ratios to 100:1, knees 0/6/18 dB -- K = 3 FAILS at
 * 0.135 dB (the limiter at -3 dB threshold, whose infinite ratio and
 * hard knee is the sharpest corner any of these curves has) and
 * K = 4 PASSES at 0.0950 dB. K = 4 is therefore the shipped value and
 * the margin against PW's bar is 5 %; K = 5 (673 words) halves the
 * error again and still fits DM, and is the lever if that margin is
 * judged too thin.
 *
 * THE OCTAVES. -100 dBFS is 1e-5 of full scale, whose leading 1 sits at
 * bit 11 of a Q4.28 word, so DYN_LUT_OCTLO = 10 is one octave below the
 * bottom of the bar and octave 30 is the top of Q4.28's positive range.
 * Below OCT_LO every one of these curves is exactly flat, so clamping to
 * the floor entry is correct rather than approximate, and it saves 10
 * octaves = 160 words a node.
 *
 * THE TABLE LIVES IN DM, and that was settled by measurement rather than
 * by the assumption S14 recorded (S15 gate 1). S14 wrote that 96 nodes x
 * their own table "would have to go to L2"; the linker map says DM has
 * 123,852 free bytes on chip 1 and 145,788 on chip 2 at the shipping
 * configuration, against 32 x 337 = 10,784 words (43 kB) on chip 1 and
 * 28 x 337 = 9,436 words (38 kB) on chip 2. It fits, with room. And the
 * rig measured what L2 would have cost if it had not: the same gather
 * from L2 is +22.1 cycles per sample-pair (54.1 -> 76.1, +29 %), and
 * PAGING a table from L2 into a DM slot is worse still -- 11.5 cycles a
 * word, so a 337-word page is 3,876 cycles a block against the 354 the
 * direct L2 gather costs over the same block.
 *
 * WHAT IS NOT HERE, AND WHY. S14 proposed blending two tables while a
 * parameter ramps. dyn_lut_design.py --blend measures that and it does
 * not work: a 10 dB threshold ramp reads 1.13 dB and a 57 dB one
 * 20.2 dB, against a 0.1 dB bar, because two curves whose KNEES sit at
 * different levels do not interpolate into the curve whose knee is
 * between them. It is exact at both ends and wrong in the middle, which
 * is the shape of every plausible-looking interpolation of a family of
 * kinked curves. So a ramping node runs the EXACT polynomial gain
 * computer -- the path that ships today -- and the table takes over when
 * the parameters settle and the design step has finished refilling it.
 * The switch happens at a block boundary between two gain curves that
 * agree to the table's own error, which is below the bar, so nothing
 * steps.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#include "dsp_block.h"
#include "lib/dyn_lut.h"

#if DSP4_DYN_LUT

.section/dm seg_dmda;

/* The design loop's own state. _compgain_fx clobbers r1-r12 and i0, so
 * the cursor, the destination and the parameter pointer cannot live in
 * registers across the call -- the same reason bq_shootout.asm parks its
 * ladder state. */
.var _dlut_par;
.var _dlut_dst;
.var _dlut_idx;
.var _dlut_end;

/* THE PAIRED LOOKUP'S SCRATCH, and every one of them is a PAIR: a
 * direct-address access inside a PEYEN region takes the word AFTER the
 * address for PEy, which is the whole mechanism that lets two channels'
 * indices leave SIMD in one store and four gathered words come back in
 * two reads. */
.global _dlut_ix;    .var _dlut_ix[2];
.global _dlut_t0;    .var _dlut_t0[2];
.global _dlut_t1;    .var _dlut_t1[2];

/* The two channels' table bases, written by the pair driver, read by
 * LUTGAIN_SIMD through i6 -- one word per PE. */
.global _dyn_lutp;   .var _dyn_lutp[2];

/* 1 when BOTH channels of the pair have a finished table. The choice is
 * per BLOCK, not per sample: the pair kernel branches on it once, before
 * its sample loop, so a node whose table is still being designed costs
 * the polynomial path and nothing else. */
.global _dlut_live;  .var _dlut_live[2] = 0, 0;

/* _dyn_lut_step's own parked arguments. Same reason as above:
 * _dyn_lut_fill under it clobbers r0-r12 and both index registers. */
.var _dls_p;
.var _dls_k;
.var _dls_t;
.var _dls_c;

.section/pm seg_pmco;
.extern _compgain_fx;

/*----------------------------------------------------------------------
 * _dyn_lut_step — one block's worth of design for one node: notice a
 * changed curve, restart if it changed, and fill DYN_LUT_CHUNK points.
 *
 * In:  r0 = &cgp[4]    the four CONVERTED parameters, which ARE the curve
 *      r1 = &lutk[4]   the parameters the table was last designed for
 *      r2 = &lut[0]
 *      r3 = &lutc      the design cursor
 * Out: nothing. Clobbers r0-r12, i0, i1, l0, l1.
 *
 * WHY THIS IS A ROUTINE AND NOT INLINE, and it is not a style
 * preference. Generated inline it is about forty instructions in each of
 * two bodies of each of thirty-two compressor nodes, and the first build
 * that had it inline linked chip 1 at 100.0 % of its code pool with
 * SIXTY-SIX BYTES free -- against 27,084 free at the shipping
 * configuration. The pool is the binding resource on chip 1, so the
 * duplication had to go; five instructions and a call replace it.
 *
 * THE KEY IS THE CONVERTED PARAMETERS, not the wire floats, because the
 * converted words are what the curve is a function of: two different
 * float thresholds that quantise to the same Q6.25 word describe the
 * same curve and must not trigger a rebuild.
 *--------------------------------------------------------------------*/
.global _dyn_lut_step;
_dyn_lut_step:
    dm(_dls_p) = r0;
    dm(_dls_k) = r1;
    dm(_dls_t) = r2;
    dm(_dls_c) = r3;

    i0 = r0;
    l0 = 0;
    i1 = r1;
    l1 = 0;
    r4 = 0;
    lcntr = 4, do .dls_cmp until lce;
        r5 = dm(i0, 1);
        r6 = dm(i1, 1);
        r5 = r5 xor r6;
    .dls_cmp: r4 = r4 or r5;
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .dls_fill);

    /* the curve moved: adopt the new key and design from the start */
    r0 = dm(_dls_p);
    i0 = r0;
    r1 = dm(_dls_k);
    i1 = r1;
    lcntr = 4, do .dls_cpy until lce;
        r5 = dm(i0, 1);
    .dls_cpy: dm(i1, 1) = r5;
    r0 = dm(_dls_c);
    i0 = r0;
    r5 = 0;
    dm(i0, 0) = r5;

.dls_fill:
    r0 = dm(_dls_c);
    i0 = r0;
    r4 = dm(i0, 0);
    r5 = DYN_LUT_N;
    comp(r4, r5);
    if ge jump (pc, .dls_done);        /* the table is finished */
    r0 = dm(_dls_p);
    r1 = dm(_dls_t);
    r2 = r4;
    r3 = DYN_LUT_CHUNK;
    call _dyn_lut_fill;
    r0 = dm(_dls_c);
    i0 = r0;
    r4 = dm(i0, 0);
    r5 = DYN_LUT_CHUNK;
    r4 = r4 + r5;
    r5 = DYN_LUT_N;
    comp(r4, r5);
    if gt r4 = pass r5;
    dm(i0, 0) = r4;
.dls_done:
    rts;
_dyn_lut_step.end:

/*----------------------------------------------------------------------
 * _dyn_lut_fill — design COUNT points of one node's table.
 *
 * In:  r0 = &params[4]   thr_q625, slope_q31, halfk_q625, k2_q625
 *      r1 = &table[0]
 *      r2 = the first index to write
 *      r3 = how many to write
 * Out: nothing.  Clobbers r0-r12, i0, i1, l0, l1.
 *
 * SPREAD OVER BLOCKS, NEVER ALL AT ONCE. One point is a whole
 * _compgain_fx -- log2, the knee, exp2, about 211 instructions -- so a
 * 337-point table is roughly 71,000 cycles against a block's 327,680.
 * That is 22 % of a block for ONE node, and there are up to 32 of them
 * on chip 1. The caller therefore asks for DYN_LUT_CHUNK points a block
 * and the node stays on the polynomial path until the cursor reaches the
 * end, which is what makes the rebuild free of any deadline.
 *--------------------------------------------------------------------*/
.global _dyn_lut_fill;
_dyn_lut_fill:
    dm(_dlut_par) = r0;
    r4 = r1 + r2;
    dm(_dlut_dst) = r4;
    dm(_dlut_idx) = r2;
    r4 = r2 + r3;
    r5 = DYN_LUT_N;
    comp(r4, r5);
    if gt r4 = pass r5;            /* never past the end of the table */
    dm(_dlut_end) = r4;

.dlf_lp:
    r0 = dm(_dlut_idx);
    r1 = dm(_dlut_end);
    comp(r0, r1);
    if ge jump (pc, .dlf_done);

    /* THE GRID POINT, exactly where the lookup will land.
     *
     *   oct = (idx >> K) + OCT_LO
     *   sub = idx & (2^K - 1)
     *   env = (2^K + sub) << (oct - K)
     *
     * The leading 1 lands at bit `oct` and the top K mantissa bits are
     * `sub`, which is precisely what _dyn_lut_gain's index arithmetic
     * takes apart again. OCT_LO is 10 and K is 4, so the shift count is
     * never negative and this is one shift and no special cases. */
    r3 = ashift r0 by -DYN_LUT_K;      /* oct - OCT_LO */
    r4 = DYN_LUT_OCTLO - DYN_LUT_K;
    r3 = r3 + r4;                      /* oct - K, the shift count */
    r4 = (1 << DYN_LUT_K) - 1;
    r5 = r0 and r4;                    /* sub */
    r4 = 1 << DYN_LUT_K;
    r5 = r5 + r4;                      /* 2^K + sub, the mantissa */
    r0 = lshift r5 by r3;              /* the envelope, Q4.28 */

    /* THE TOP GUARD ENTRY OVERFLOWS, and it is not academic (S15-11).
     *
     * The table's last word, index DYN_LUT_N-1, is the guard the
     * interpolation reads as T[i+1] when i is the last real cell. Its
     * grid point is octave DYN_LUT_OCTHI+1 = 31, whose envelope is
     * 1 << 31 -- which in a 32-bit register is NEGATIVE, so
     * _compgain_fx takes its `x_abs <= 0` path and returns UNITY. The
     * top cell would then interpolate from a heavily reduced gain back
     * UP to unity between +17.8 and +18.1 dBFS.
     *
     * Caught by tools/pi/dsp4_dyn_lut_check.py, which read the table
     * off the part and diffed it against the host model: 336 of 337
     * words identical, the mismatch at index 336 exactly.
     *
     * Q4.28's largest positive value is the right value there, and it
     * is four instructions once per table point. */
    r4 = 0x7FFFFFFF;
    r5 = 0;
    comp(r0, r5);
    if le r0 = pass r4;

    r1 = dm(_dlut_par);
    i0 = r1;
    l0 = 0;
    call _compgain_fx;                 /* r0 = the EXACT gain, Q4.28 */

    r1 = dm(_dlut_dst);
    i1 = r1;
    l1 = 0;
    dm(i1, 1) = r0;
    r1 = i1;
    dm(_dlut_dst) = r1;

    r0 = dm(_dlut_idx);
    r1 = 1;
    r0 = r0 + r1;
    dm(_dlut_idx) = r0;
    jump (pc, .dlf_lp);
.dlf_done:
    rts;
_dyn_lut_fill.end:

/*----------------------------------------------------------------------
 * _dyn_lut_gain — the scalar lookup. The paired form is the macro
 * LUTGAIN_DM in dyn_lut.h; this is the twin the per-sample body and the
 * scalar fallback use, and the two compute the same arithmetic in the
 * same order on the same operands, which is what lets sample 0 and
 * samples 1..N-1 of a paired block agree bit for bit.
 *
 * In:  r0 = envelope, Q4.28   i0 = &table[0]
 * Out: r0 = gain, Q4.28.  Clobbers r1-r5, i1, l1.
 *--------------------------------------------------------------------*/
.global _dyn_lut_gain;
_dyn_lut_gain:
    r5 = i0;                       /* the base, before i0 is spent */
    r1 = leftz r0;
    r2 = 31 - DYN_LUT_OCTLO;
    r2 = r2 - r1;                  /* the octave, biased by OCT_LO */
    r3 = ashift r0 by r1;          /* leading 1 to bit 31 */
    r4 = 0x7FFFFFFF;
    r3 = r3 and r4;                /* mantissa fraction, Q0.31 */
    r4 = lshift r3 by -DYN_LUT_FSH;
    r2 = lshift r2 by DYN_LUT_K;
    r2 = r2 + r4;                  /* the index */
    r4 = 0;
    comp(r2, r4);
    if lt r2 = pass r4;            /* below the table: the floor entry */
    r4 = DYN_LUT_N - 2;
    comp(r2, r4);
    if gt r2 = pass r4;            /* above it: the last cell */
    r2 = r2 + r5;
    i1 = r2;
    l1 = 0;

    /* THE FRACTION, AND THE MASK THAT IS NOT OPTIONAL (S15-4).
     * Shifting the Q0.31 mantissa fraction left by K to discard the K
     * bits already spent on the sub-index pushes what is left up INTO
     * BIT 31, and the interpolation multiply below is SIGNED -- so a
     * fraction of 0.75 would arrive as -0.25 and the interpolation
     * would run backwards out of the cell. It is two instructions and
     * it is the difference between 0.389 dB and 0.005 dB at K = 4,
     * measured by dyn_lut_design.py. S14's rig did not have it and
     * could not have seen it: the table's contents do not change the
     * instruction stream, so a cycle measurement is blind to this. */
    r4 = lshift r3 by DYN_LUT_K;
    r5 = 0x7FFFFFFF;
    r4 = r4 and r5;                /* the fraction, taken BEFORE the two
                                    * table words overwrite r3 */
    r2 = dm(i1, 1);                /* T[i]   */
    r3 = dm(i1, 0);                /* T[i+1] */

    r5 = r3 - r2;                  /* T[i+1] - T[i] */
    mrf = r5 * r4 (ssi);
    r1 = 0x40000000;
    r3 = 1;
    mrf = mrf + r1 * r3 (ssi);
    r1 = mr0f;
    r3 = mr1f;
    r1 = lshift r1 by -31;
    r3 = lshift r3 by 1;
    r1 = r1 or r3;                 /* rns((T[i+1]-T[i]) * frac, 31) */
    r0 = r2 + r1;
    rts;
_dyn_lut_gain.end:

#endif /* DSP4_DYN_LUT */
