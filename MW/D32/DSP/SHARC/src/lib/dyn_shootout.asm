/*======================================================================
 * dyn_shootout.asm — THE DYNAMICS GAIN-COMPUTER SHOOTOUT (S14, 2026-09-09).
 *
 * SPIKE ONLY. Standalone rig, never in a shipping image, no graph
 * integration, no contract edit. Guarded on DSP4_DYN_SHOOTOUT.
 *
 * THE QUESTION. PW, 2026-09-09: "other processing progress is leaving
 * dynamics processing as a hog, so it's a priority to address", and
 * "the compressor and gate cycles could be improved a lot, using LUTs
 * with interpolation, and still fit the SIMD structure", and "the
 * envelope and knee become part of the LUT graph". With it, a ruling
 * that changes what is possible: the dynamics accuracy target is
 * 0.1 dB worst case over 0 to -100 dBFS, not the polynomial's 0.0001 dB.
 *
 * WHERE THE CYCLES ARE. The paired COMPRESSOR's per-sample body is about
 * 251 instructions for two channels, and 211 of them are the gain
 * computer: LOG2Q_SIMD 73, the knee 49, EXP2Q_SIMD 89. Both log2 and
 * exp2 are 6-term Horner polynomials through POLYQ_SIMD, which is 60
 * instructions on its own. The paired GATE pays LOG2Q_SIMD too -- 73
 * instructions to produce a number it uses for ONE comparison.
 *
 * THE THREE CONTENDERS, timed the shootout way against the same
 * envelope and the same gain application:
 *
 *   (a) TODAY. COMPGAIN_SIMD as it ships: 6-term polynomial log2, the
 *       knee arithmetic, 6-term polynomial exp2.
 *   (b) THE ONE TABLE, level -> gain. The whole static curve --
 *       threshold, ratio, knee, range, ceiling -- baked into ONE table
 *       by a DESIGN step that runs only when a parameter changes, the
 *       same parameter-written pattern as the GEQ. Per sample: leftz
 *       gives the exponent, the top K mantissa bits give the sub-index,
 *       two adjacent words are read and interpolated. No log2, no knee,
 *       no exp2. The table is log-spaced BY CONSTRUCTION -- one octave
 *       per exponent step, 2^K points per octave -- which is why the
 *       index costs a leftz and a shift instead of a logarithm.
 *   (c) A REDUCED-ORDER POLYNOMIAL. The same shape as today with a
 *       3-term Horner instead of 6-term; at a 0.1 dB bar the extra
 *       terms may simply not be needed, and this form has no gather at
 *       all, so it is the contender the LUT has to beat.
 *
 * THE SIMD PROBLEM, ANSWERED THREE WAYS RATHER THAN AVOIDED. A table
 * lookup is a GATHER at two different indices and the DAGs are shared:
 * one address per access, whatever PEYEN says. dyn_simd_fx.asm's guard
 * says so and refuses to build DSP4_DYN_TABLES beside DSP4_SIMD_DYN.
 * That guard is about the OLD form (a log2 table and an exp2 table
 * inside the polynomial's place); this rig measures what it costs to
 * keep the pairing and pay for the gather anyway:
 *
 *   rung 4  index in SIMD, PEYEN down for the gather, PEYEN up for the
 *           interpolation. Both channels' indices leave SIMD in ONE
 *           store, because a direct-address store inside a PEYEN region
 *           writes PEy's word right after PEx's -- the same property
 *           that makes _bqfl_two a pair.
 *   rung 5  the same, with channel A's two words read over DM and
 *           channel B's over PM in the SAME instruction -- one table,
 *           both buses. Saves two instructions and pays whatever the PM
 *           bus costs against instruction fetch.
 *   rung 6  the whole gain computer unpaired, both channels in scalar.
 *
 * AND THE GATE'S OWN LEVER, WHICH IS NOT A TABLE AT ALL. The paired
 * GATE computes log2(env) to compare it against a log threshold, and
 * `log2(env) >= thr` is `env >= 2^thr`. DSP4_GATE_LINTHR already does
 * that conversion once per block in the SCALAR kernel and has since S8,
 * where it was worth 101 cycles/sample; dsp_codegen.py's paired-graph
 * header #errors on it because the two are different arithmetic. The
 * difference is a threshold shift of at most 0.0002 dB, which was worth
 * arguing about against a 0.0001 dB polynomial and is not worth arguing
 * about against a 0.1 dB ruling. Rung 12 is what it costs.
 *
 * THE METHOD is bq_probe.asm's: 28 x 15 iterations per call, one
 * timestamp pair either side of each rung, the whole ladder run REPS
 * times, the host takes the MINIMUM so a pass the 1 kHz diag-tick ISR
 * landed in is dropped. Rung 0 is the nest and is subtracted.
 *
 * THE TABLE'S CONTENTS DO NOT AFFECT THE CYCLE COUNT -- the instruction
 * stream does not vary with the loaded words -- so a zeroed table times
 * the same path a designed curve would. What the contents DO decide is
 * the error, and that is a host-side question, not this rig's.
 *======================================================================*/

#include "dsp_block.h"
#include "diag.h"
#include "lib/dyn_simd_inline.h"

#if DSP4_DYN_SHOOTOUT

#define DSH_STAGES  28
#define DSH_INNER   (DSP4_BLOCK_SIZE - 1)
#define DSH_RUNGS   20
#define DSH_REPS    5
#define DSH_ITERS   8

/* The level -> gain table. K mantissa bits per octave, so 2^K points per
 * octave; the envelope is Q4.28, whose exponent from `leftz` runs 0..31,
 * so 32 octaves x 2^K covers the whole representable range with no high
 * clamp needed and 100 dB of it to spare. K = 2 is 128 entries + the
 * interpolation guard, which is PW's "50-75 points" band once the octaves
 * below -100 dBFS are dropped by the DESIGN step; K is a #define here
 * because the CYCLE cost does not depend on it and the ERROR does. */
/* K = 3, THE MEASURED CHOICE (S15). tools/dsp/dyn_lut_design.py builds
 * the table on exactly this grid and sweeps the error against the exact
 * fixed-point curve: at K = 3 the COMPRESSOR is 0.011 dB and the
 * LIMITER 0.028 dB over 0 to -100 dBFS, against PW's 0.1 dB bar. K = 2
 * is 85 words and holds for the compressor (0.045 dB) but NOT for the
 * limiter (0.247 dB), whose infinite ratio and hard knee is the sharpest
 * corner any of these curves has. */
#define DSH_K       3
#define DSH_FSH     (31 - DSH_K)

/* THE OCTAVES THE TABLE ACTUALLY COVERS. -100 dBFS is 1e-5 of full
 * scale, whose leading 1 sits at bit 11 of a Q4.28 word, so octave 10 is
 * one below the bottom of the bar and octave 30 is the top of Q4.28's
 * positive range. Below OCT_LO every one of these curves is exactly
 * flat, so the clamp to the floor entry is correct and not an
 * approximation. It saves 10 octaves = 80 words a node at K = 3. */
#define DSH_OCTLO   10
#define DSH_OCTHI   30
#define DSH_TBLN    (((DSH_OCTHI - DSH_OCTLO + 1) << DSH_K) + 1)

.section/dm seg_dmda;

.global _dsh_done;    .var _dsh_done   = 0;
.global _dsh_magic;   .var _dsh_magic  = 0xD5B4D003;
.global _dsh_iters;   .var _dsh_iters  = DSH_ITERS;
.global _dsh_reps;    .var _dsh_reps   = DSH_REPS;
.global _dsh_rungs;   .var _dsh_rungs  = DSH_RUNGS;
.global _dsh_stages;  .var _dsh_stages = DSH_STAGES;
.global _dsh_inner;   .var _dsh_inner  = DSH_INNER;
.global _dsh_kbits;   .var _dsh_kbits  = DSH_K;
.global _dsh_tbln;    .var _dsh_tbln   = DSH_TBLN;
.global _dsh_tper;    .var _dsh_tper   = DIAG_TPERIOD;
.global _dsh_blk;     .var _dsh_blk    = DSP4_BLOCK_SIZE;
.global _dsh_tick;    .var _dsh_tick[DSH_RUNGS * DSH_REPS * 4];

/* The ladder's own loop state lives in DM for bq_shootout.asm's measured
 * reason: a rung body owns the whole register file. */
.var _dsh_rep;
.var _dsh_tp;
.var _dsh_m1[2];

/* Every scratch word the rungs touch from inside a PEYEN region is a
 * PAIR: a direct-address access there takes the word after the address
 * for PEy. */
.var _dsh_ix[2];
.var _dsh_t0[2];
.var _dsh_t1[2];

.global _dsh_gtbl;  .var _dsh_gtbl[DSH_TBLN];
.global _dsh_sig;   .var _dsh_sig[2 * DSP4_BLOCK_SIZE];

/* S15 gate 1. The SECOND table, in DM, for the two-table blend a ramping
 * parameter needs (S14: the design step is ~211 instr/point, 3-6 % of a
 * whole block for ONE node, so a ramp blends between two tables instead
 * of rebuilding per block). */
.global _dsh_gtbl_b; .var _dsh_gtbl_b[DSH_TBLN];

/* The DM PAGE a table is copied into if the tables live in L2 and only
 * the ACTIVE node's is wanted in DM. One page, DSH_PAGE words. */
#define DSH_PAGE  64
.global _dsh_page;  .var _dsh_page[DSH_PAGE];

/* Scratch pairs for the blend's second gather. */
.var _dsh_u0[2];
.var _dsh_u1[2];

/*----------------------------------------------------------------------
 * S15 GATE 1 — THE TABLE'S HOME.
 *
 * S14 measured a DM-RESIDENT table and named the open risk itself: 96
 * dynamics nodes x their own table is ~2,420 words at shipped defaults
 * and ~5,000 worst case, and the write-up assumed that could only live
 * in L2. An L2-resident table is a DIFFERENT INSTRUMENT — L2 is off the
 * core's L1 crossbar and every gathered word crosses the system bus —
 * so the 24.5 c/sample/channel the LUT bought is not transferable until
 * the gather is measured where the table would actually sit.
 *
 * The same table declared in seg_delay, which the LDF maps to
 * mem_L2_bw (L2 SRAM CTL0 at 0x20000000, overflowing to CTL1). Nothing
 * else about the rung changes, so the delta IS the cost of the home.
 *--------------------------------------------------------------------*/
.section/dm seg_delay;
.global _dsh_gtbl_l2;  .var _dsh_gtbl_l2[DSH_TBLN];
.global _dsh_page_src; .var _dsh_page_src[DSH_PAGE];

.section/dm seg_dmda;

.section/pm seg_pmco;
.extern _diag_ticks;
.extern _log2_poly_dup;
.extern _exp2_poly_dup;

#define DSH_T   r3 = dm(_dsh_tp); i5 = r3; l5 = 0; \
                r2 = tcount; r0 = dm(_diag_ticks); \
                dm(i5,1) = r0; dm(i5,1) = r2; \
                r3 = i5; dm(_dsh_tp) = r3;

/*----------------------------------------------------------------------
 * THE CONTENDERS.
 *--------------------------------------------------------------------*/

/* (c) POLYQ with THREE Horner terms instead of six. Identical text to
 * POLYQ_SIMD but for the trip count, so the per-term cost is exactly the
 * difference between this rung and today's. */
#define POLYQ3_SIMD(L) \
    l0 = 0; \
    r1 = dm(i0, 2); \
    r5 = 2; \
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

#define LOG2Q3_SIMD(L) \
    r1 = leftz r0; \
    r2 = 3; \
    r2 = r2 - r1; \
    r3 = ashift r0 by r1; \
    r4 = 0x7FFFFFFF; \
    r0 = r3 and r4; \
    r4 = r2; \
    i0 = _log2_poly_dup; \
    POLYQ3_SIMD(L) \
    r3 = 16; \
    r0 = r0 + r3; \
    r0 = ashift r0 by -5; \
    r2 = lshift r4 by 25; \
    r0 = r0 + r2;

#define EXP2Q3_SIMD(L) \
    r2 = ashift r0 by -25; \
    r4 = r2; \
    r3 = lshift r2 by 25; \
    r1 = r0 - r3; \
    r0 = lshift r1 by 6; \
    i0 = _exp2_poly_dup; \
    POLYQ3_SIMD(L) \
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

#define COMPGAIN3_SIMD(LA, LB) \
    r1 = 0; \
    r2 = 0; \
    r7 = 1; \
    comp(r0, r1); \
    if gt r7 = pass r2; \
    LOG2Q3_SIMD(LA) \
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
    EXP2Q3_SIMD(LB) \
    r2 = 0; \
    r3 = 0x10000000; \
    comp(r7, r2); \
    if ne r0 = pass r3;

/*----------------------------------------------------------------------
 * (b) THE ONE TABLE, level -> gain.
 *
 * In  r0 = |envelope|, Q4.28.   Out r0 = gain, Q4.28.
 * Obeys COMPGAIN_SIMD's register contract exactly -- r0-r5 and r7 are
 * scratch, r6 and r8-r15 are the caller's -- so it drops into the pair
 * kernels where COMPGAIN_SIMD sits without moving anything else.
 *
 * THE INDEX IS A LOGARITHM WITHOUT A LOGARITHM. leftz gives the binary
 * exponent, which IS the octave; the top DSH_K bits of the normalised
 * mantissa sub-divide it. So the table is log-spaced by construction and
 * the index costs a count-leading-zeros, two shifts and an add. The
 * remaining mantissa bits, shifted up, ARE the interpolation fraction in
 * Q0.31 -- no second extraction.
 *
 * THE ONLY CLAMP IS AT THE BOTTOM. leftz of a zero envelope is 32, one
 * past the table, so the index goes negative; everything above is inside
 * a 32-octave table by construction. A DESIGN step that only fills the
 * octaves down to -100 dBFS points the rest at the table's floor entry,
 * so the clamp stays one compare and one conditional move.
 *
 * THE GATHER LEAVES SIMD, AND COMES BACK. Both channels' addresses go
 * out in ONE store because a direct-address store inside a PEYEN region
 * writes PEy's word after PEx's; the four gathered words come back in
 * two paired reads for the same reason. PEy's registers are NOT
 * disturbed while PEYEN is down -- only the compute unit is idle -- so
 * r4, the interpolation fraction, survives the excursion and does not
 * have to be spilled.
 *--------------------------------------------------------------------*/
#define LUT_INDEX_SIMD \
    r1 = leftz r0; \
    r2 = 31 - DSH_OCTLO; \
    r2 = r2 - r1;                  /* the octave, biased by OCT_LO */ \
    r3 = ashift r0 by r1;          /* leading 1 to bit 31 */ \
    r4 = 0x7FFFFFFF; \
    r3 = r3 and r4;                /* mantissa fraction, Q0.31 */ \
    r4 = lshift r3 by -DSH_FSH;    /* top K bits: the sub-index */ \
    r2 = lshift r2 by DSH_K; \
    r2 = r2 + r4;                  /* index */ \
    r4 = 0; \
    comp(r2, r4); \
    if lt r2 = pass r4;            /* below the table -> the floor entry */ \
    r4 = DSH_TBLN - 2; \
    comp(r2, r4); \
    if gt r2 = pass r4;            /* above it -> the last cell */ \
    r4 = lshift r3 by DSH_K; \
    r5 = 0x7FFFFFFF; \
    r4 = r4 and r5;                /* the interpolation fraction, Q0.31 */

/* THE MASK IS NOT OPTIONAL, and S14's rig did not have it (S15-4).
 * `r3` is the mantissa fraction in Q0.31; shifting it left by K to
 * discard the K bits already spent on the sub-index pushes what is left
 * up INTO BIT 31, and LUT_INTERP_SIMD's `mrf = r5 * r4 (ssi)` is a
 * SIGNED multiply -- so an interpolation fraction of 0.75 arrives as
 * -0.25 and the interpolation runs backwards out of the cell.
 *
 * It could not show in S14: the table's contents do not change the
 * instruction stream, so the shootout measured the right cycles for the
 * wrong arithmetic, and the error was a host-side model that assumed the
 * kernel did what the comment said. tools/dsp/dyn_lut_design.py computes
 * the index bit for bit the way this macro does and measures the error
 * that results: 0.389 dB at K=4 with the sign-extended fraction, 0.005 dB
 * with the mask. Two instructions. */

#define LUT_INTERP_SIMD \
    r5 = r3 - r2;                  /* T[i+1] - T[i] */ \
    mrf = r5 * r4 (ssi); \
    r1 = 0x40000000; \
    r3 = 1; \
    mrf = mrf + r1 * r3 (ssi); \
    r1 = mr0f; \
    r3 = mr1f; \
    r1 = lshift r1 by -31; \
    r3 = lshift r3 by 1; \
    r1 = r1 or r3; \
    r0 = r2 + r1;

/* rung 4: gather in scalar, both channels over DM. */
#define LUTGAIN_DM \
    LUT_INDEX_SIMD \
    r5 = _dsh_gtbl; \
    r2 = r2 + r5; \
    dm(_dsh_ix) = r2;              /* both channels' addresses, one store */ \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_ix); \
    i0 = r2; \
    r3 = dm(_dsh_ix + 1); \
    i1 = r3; \
    r2 = dm(i0, 1); \
    r3 = dm(i0, 0); \
    r5 = dm(i1, 1); \
    r7 = dm(i1, 0); \
    dm(_dsh_t0) = r2; \
    dm(_dsh_t0 + 1) = r5; \
    dm(_dsh_t1) = r3; \
    dm(_dsh_t1 + 1) = r7; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_t0); \
    r3 = dm(_dsh_t1); \
    LUT_INTERP_SIMD

/* rung 5: gather in scalar, channel A over DM and channel B over PM in
 * the SAME instruction. Two instructions cheaper, one more table. */
#define LUTGAIN_PM \
    LUT_INDEX_SIMD \
    dm(_dsh_ix) = r2;              /* the raw index; the bases differ */ \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_ix); \
    r5 = _dsh_gtbl; \
    r2 = r2 + r5; \
    i0 = r2; \
    r3 = dm(_dsh_ix + 1); \
    r5 = _dsh_gtbl; \
    r3 = r3 + r5; \
    i8 = r3; \
    r2 = dm(i0, m1), r5 = pm(i8, m9); \
    r3 = dm(i0, m0), r7 = pm(i8, m8); \
    dm(_dsh_t0) = r2; \
    dm(_dsh_t0 + 1) = r5; \
    dm(_dsh_t1) = r3; \
    dm(_dsh_t1 + 1) = r7; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_t0); \
    r3 = dm(_dsh_t1); \
    LUT_INTERP_SIMD

/* rung 14: THE SAME GATHER, the table in L2. Byte for byte LUTGAIN_DM
 * but for the base address, so the delta is the home and nothing else. */
#define LUTGAIN_L2 \
    LUT_INDEX_SIMD \
    r5 = _dsh_gtbl_l2; \
    r2 = r2 + r5; \
    dm(_dsh_ix) = r2; \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_ix); \
    i0 = r2; \
    r3 = dm(_dsh_ix + 1); \
    i1 = r3; \
    r2 = dm(i0, 1); \
    r3 = dm(i0, 0); \
    r5 = dm(i1, 1); \
    r7 = dm(i1, 0); \
    dm(_dsh_t0) = r2; \
    dm(_dsh_t0 + 1) = r5; \
    dm(_dsh_t1) = r3; \
    dm(_dsh_t1 + 1) = r7; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_t0); \
    r3 = dm(_dsh_t1); \
    LUT_INTERP_SIMD

/* rung 16: THE TWO-TABLE BLEND, which is what a RAMPING parameter costs
 * if the design step is not run per block. One index serves both tables
 * -- they are the same shape -- so the index arithmetic is paid once and
 * the second table costs one more pair of gathers and one crossfade.
 *
 * The LUT form FREES r8-r11 (threshold, slope, half-knee, k2 are baked
 * into the table), so the blend fraction and the second base live in
 * registers exactly as they would in the graph: r9 = fraction Q4.28,
 * r8 = the parked gain from table A. */
#define LUTGAIN_BLEND \
    LUT_INDEX_SIMD \
    dm(_dsh_ix) = r2; \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_ix); \
    r3 = dm(_dsh_ix + 1); \
    r5 = _dsh_gtbl; \
    r7 = r2 + r5; \
    i0 = r7; \
    r7 = r3 + r5; \
    i1 = r7; \
    r5 = dm(i0, 1); \
    dm(_dsh_t0) = r5; \
    r5 = dm(i0, 0); \
    dm(_dsh_t1) = r5; \
    r5 = dm(i1, 1); \
    dm(_dsh_t0 + 1) = r5; \
    r5 = dm(i1, 0); \
    dm(_dsh_t1 + 1) = r5; \
    r5 = _dsh_gtbl_b; \
    r7 = r2 + r5; \
    i0 = r7; \
    r7 = r3 + r5; \
    i1 = r7; \
    r5 = dm(i0, 1); \
    dm(_dsh_u0) = r5; \
    r5 = dm(i0, 0); \
    dm(_dsh_u1) = r5; \
    r5 = dm(i1, 1); \
    dm(_dsh_u0 + 1) = r5; \
    r5 = dm(i1, 0); \
    dm(_dsh_u1 + 1) = r5; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dsh_t0); \
    r3 = dm(_dsh_t1); \
    LUT_INTERP_SIMD \
    r8 = r0; \
    r2 = dm(_dsh_u0); \
    r3 = dm(_dsh_u1); \
    LUT_INTERP_SIMD \
    r5 = r0 - r8; \
    mrf = r5 * r9 (ssi); \
    MRF_RNS28_SIMD \
    r0 = r0 + r8;

/*----------------------------------------------------------------------
 * The ladder.
 *--------------------------------------------------------------------*/
.global _dsh_selftest;
_dsh_selftest:
    r0 = _dsh_tick;
    dm(_dsh_tp) = r0;
    r0 = 0;
    dm(_dsh_rep) = r0;

.dsh_rep:

#define DSH_RUNG(N, SUB) \
    DSH_T \
    r10 = dm(_dsh_iters); \
    lcntr = r10, do N until lce; \
        call SUB; \
        nop; \
    N: nop; \
    DSH_T

    DSH_RUNG(.dsh_r0,  _dsh_null)
    DSH_RUNG(.dsh_r1,  _dsh_env)
    DSH_RUNG(.dsh_r2,  _dsh_cg_poly)
    DSH_RUNG(.dsh_r3,  _dsh_cg_poly3)
    DSH_RUNG(.dsh_r4,  _dsh_cg_lut_dm)
    DSH_RUNG(.dsh_r5,  _dsh_cg_lut_pm)
    DSH_RUNG(.dsh_r6,  _dsh_cg_lut_unp)
    DSH_RUNG(.dsh_r7,  _dsh_log2)
    DSH_RUNG(.dsh_r8,  _dsh_rns)
    DSH_RUNG(.dsh_r9,  _dsh_comp_today)
    DSH_RUNG(.dsh_r10, _dsh_comp_lut)
    DSH_RUNG(.dsh_r11, _dsh_gate_today)
    DSH_RUNG(.dsh_r12, _dsh_gate_lin)
    DSH_RUNG(.dsh_r13, _dsh_gate_lut)
    DSH_RUNG(.dsh_r14, _dsh_cg_lut_l2)
    DSH_RUNG(.dsh_r15, _dsh_comp_lut_l2)
    DSH_RUNG(.dsh_r16, _dsh_cg_lut_blend)
    DSH_RUNG(.dsh_r17, _dsh_l2page)
    DSH_RUNG(.dsh_r18, _dsh_lim_today)
    DSH_RUNG(.dsh_r19, _dsh_lim_lut)

    r0 = dm(_dsh_rep);
    r1 = 1;
    r0 = r0 + r1;
    dm(_dsh_rep) = r0;
    r1 = DSH_REPS;
    comp(r0, r1);
    if lt jump (pc, .dsh_rep);

    r0 = 1;
    dm(_dsh_done) = r0;
    rts;
_dsh_selftest.end:

/*----------------------------------------------------------------------
 * The rung bodies. Every one: raise PEYEN, seed the parameter registers
 * the macros read, run 28 x 15, drop PEYEN. MODE1 is saved and restored
 * WHOLE and interrupts are NOT masked -- the systemic per-ISR PEYEN clear
 * is what makes that safe, and it is the discipline every SIMD kernel in
 * this tree relies on.
 *
 * THE SEEDS ARE A REAL OPERATING POINT, not zero. r8 = threshold, r9 =
 * slope, r10 = half-knee, r11 = k2 are the compressor's parameters as
 * COMPGAIN_SIMD reads them; halfk is non-zero so the SOFT-knee arm is the
 * one that runs, which is the expensive one and therefore the honest one
 * to time. The envelope seed is -6 dBFS, which is above the threshold, so
 * the branchless kernel's unity flag is clear and every arm does its
 * work. Cost is data-independent in the paired kernel by construction --
 * both candidates are always computed and selected -- but seeding it at a
 * real point is what makes that claim checkable.
 *--------------------------------------------------------------------*/

#define DSH_PROLOGUE \
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l8 = 0; \
    r15 = 1; \
    m1 = r15; \
    m9 = r15;                      /* the dual gather's two strides */ \
    r15 = mode1; \
    dm(_dsh_m1) = r15; \
    dm(_dsh_m1 + 1) = r15; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r13 = 0x08000000;              /* dry sample, -6 dBFS in Q4.28 */ \
    r14 = 0x08000000;              /* envelope state */ \
    r6  = 0x00300000;              /* attack alpha  */ \
    r12 = 0x10000000;              /* makeup = unity */ \
    r8  = 0xFF000000;              /* threshold, Q6.25 log domain */ \
    r9  = 0x40000000;              /* slope */ \
    r10 = 0x02000000;              /* half-knee, non-zero: the soft arm */ \
    r11 = 0x20000000;              /* k2 */ \
    i3 = _dsh_sig;                 /* the release-alpha park */ \
    i5 = _dsh_sig;                 /* the witness park */

#define DSH_EPILOGUE \
    r15 = dm(_dsh_m1); \
    mode1 = r15; \
    nop; \
    nop; \
    rts;

/* OPEN/CLOSE rather than DSH_NEST(OUT, IN, BODY): a body passed as a
 * macro ARGUMENT is split at every comma the preprocessor can see, and
 * the dual-bus gather's `r2 = dm(i0,1), r5 = pm(i8,1)` has one that no
 * parenthesis protects. */
#define DSH_NEST_OPEN(OUT, IN) \
    lcntr = DSH_STAGES, do OUT until lce; \
        i2 = _dsh_sig; \
        i4 = _dsh_sig; \
        lcntr = DSH_INNER, do IN until lce;

#define DSH_NEST_CLOSE(OUT, IN) \
        IN: nop; \
    OUT: nop;

/* The envelope + attack/release one-pole, verbatim from _comp_pair_blk. */
#define DSH_ENV_BODY \
        r0 = abs r13; \
        r4 = r0 - r14; \
        r5 = 0; \
        r2 = r6; \
        r3 = dm(i3, 0); \
        comp(r4, r5); \
        if le r2 = pass r3; \
        mrf = r2 * r4 (ssi); \
        r2 = 0x40000000; \
        r3 = 1; \
        mrf = mrf + r2 * r3 (ssi); \
        r2 = mr0f; \
        r3 = mr1f; \
        r2 = lshift r2 by -31; \
        r3 = lshift r3 by 1; \
        r5 = r2 or r3; \
        r14 = r14 + r5;

/* The gain application, verbatim from _comp_pair_blk: two rounds and the
 * parallel mix. */
#define DSH_APPLY_BODY \
        r1 = r0; \
        r0 = r13; \
        mrf = r0 * r1 (ssi); \
        MRF_RNS28_SIMD \
        r1 = r12; \
        mrf = r0 * r1 (ssi); \
        MRF_RNS28_SIMD

.global _dsh_null;
_dsh_null:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_n_o, .dsh_n_i)
 nop;
    DSH_NEST_CLOSE(.dsh_n_o, .dsh_n_i)
    DSH_EPILOGUE
_dsh_null.end:

.global _dsh_env;
_dsh_env:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_e_o, .dsh_e_i)
 DSH_ENV_BODY
    DSH_NEST_CLOSE(.dsh_e_o, .dsh_e_i)
    DSH_EPILOGUE
_dsh_env.end:

.global _dsh_cg_poly;
_dsh_cg_poly:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_a_o, .dsh_a_i)
 r0 = r14; COMPGAIN_SIMD(.dsh_a_p1, .dsh_a_p2)
    DSH_NEST_CLOSE(.dsh_a_o, .dsh_a_i)
    DSH_EPILOGUE
_dsh_cg_poly.end:

.global _dsh_cg_poly3;
_dsh_cg_poly3:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_b_o, .dsh_b_i)
 r0 = r14; COMPGAIN3_SIMD(.dsh_b_p1, .dsh_b_p2)
    DSH_NEST_CLOSE(.dsh_b_o, .dsh_b_i)
    DSH_EPILOGUE
_dsh_cg_poly3.end:

.global _dsh_cg_lut_dm;
_dsh_cg_lut_dm:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_c_o, .dsh_c_i)
 r0 = r14; LUTGAIN_DM
    DSH_NEST_CLOSE(.dsh_c_o, .dsh_c_i)
    DSH_EPILOGUE
_dsh_cg_lut_dm.end:

.global _dsh_cg_lut_pm;
_dsh_cg_lut_pm:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_d_o, .dsh_d_i)
 r0 = r14; LUTGAIN_PM
    DSH_NEST_CLOSE(.dsh_d_o, .dsh_d_i)
    DSH_EPILOGUE
_dsh_cg_lut_pm.end:

/* rung 6: PW's option (ii) -- the whole gain computer unpaired. PEYEN
 * goes down ONCE and both channels' indices, gathers and interpolations
 * run in scalar. Two of everything, no toggle per stage of the
 * computation; the rig says which trade wins. */
.global _dsh_cg_lut_unp;
_dsh_cg_lut_unp:
    DSH_PROLOGUE
    bit clr mode1 0x00200000;
    nop;
    nop;
    DSH_NEST_OPEN(.dsh_f_o, .dsh_f_i)

        r0 = r14;
        LUT_INDEX_SIMD
        r5 = _dsh_gtbl;
        r2 = r2 + r5;
        i0 = r2;
        r2 = dm(i0, 1);
        r3 = dm(i0, 0);
        LUT_INTERP_SIMD
        r0 = r14;
        LUT_INDEX_SIMD
        r5 = _dsh_gtbl;
        r2 = r2 + r5;
        i0 = r2;
        r2 = dm(i0, 1);
        r3 = dm(i0, 0);
        LUT_INTERP_SIMD
    DSH_NEST_CLOSE(.dsh_f_o, .dsh_f_i)
    DSH_EPILOGUE
_dsh_cg_lut_unp.end:

/* rung 7: LOG2Q_SIMD alone -- what the paired GATE pays today to produce
 * one number it uses for one comparison. */
.global _dsh_log2;
_dsh_log2:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_g_o, .dsh_g_i)
 r0 = r14; LOG2Q_SIMD(.dsh_g_p)
    DSH_NEST_CLOSE(.dsh_g_o, .dsh_g_i)
    DSH_EPILOGUE
_dsh_log2.end:

.global _dsh_rns;
_dsh_rns:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_h_o, .dsh_h_i)
 mrf = r13 * r13 (ssi); MRF_RNS28_SIMD
    DSH_NEST_CLOSE(.dsh_h_o, .dsh_h_i)
    DSH_EPILOGUE
_dsh_rns.end:

/* rungs 9-10: the WHOLE compressor per-sample body, both ways. Same
 * envelope, same gain application, same parallel mix; only the gain
 * computer differs, which is the comparison PW asked for. */
#define DSH_COMP_TAIL \
        r5 = r0 - r13; \
        r4 = r15; \
        mrf = r5 * r4 (ssi); \
        r1 = 0x40000000; \
        r2 = 1; \
        mrf = mrf + r1 * r2 (ssi); \
        r1 = mr0f; \
        r2 = mr1f; \
        r1 = lshift r1 by -31; \
        r2 = lshift r2 by 1; \
        r1 = r1 or r2; \
        r0 = r13 + r1;

.global _dsh_comp_today;
_dsh_comp_today:
    DSH_PROLOGUE
    r15 = 0x10000000;              /* parallel mix = fully wet */
    DSH_NEST_OPEN(.dsh_i_o, .dsh_i_i)

        r13 = dm(i2, 2);
        DSH_ENV_BODY
        r0 = r14;
        COMPGAIN_SIMD(.dsh_i_p1, .dsh_i_p2)
        dm(i5, 0) = r0;
        DSH_APPLY_BODY
        DSH_COMP_TAIL
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_i_o, .dsh_i_i)
    DSH_EPILOGUE
_dsh_comp_today.end:

.global _dsh_comp_lut;
_dsh_comp_lut:
    DSH_PROLOGUE
    r15 = 0x10000000;
    DSH_NEST_OPEN(.dsh_j_o, .dsh_j_i)

        r13 = dm(i2, 2);
        DSH_ENV_BODY
        r0 = r14;
        LUTGAIN_DM
        dm(i5, 0) = r0;
        DSH_APPLY_BODY
        DSH_COMP_TAIL
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_j_o, .dsh_j_i)
    DSH_EPILOGUE
_dsh_comp_lut.end:

/* rungs 18-19: THE WHOLE LIMITER per-sample body, both ways (S16).
 *
 * The limiter is the compressor without the makeup and without the
 * parallel mix, so its body is DSH_ENV_BODY, the gain computer, and ONE
 * round -- not DSH_APPLY_BODY, which is two, and not DSH_COMP_TAIL at
 * all. That is why it gets its own pair of rungs rather than being read
 * off rungs 9-10: 65 % of it is the gain computer (S14-4 measured 162 of
 * 251 instructions per sample-pair as log2 + exp2) precisely BECAUSE
 * there are no other stages to dilute it, so the compressor's ratio
 * understates what the table is worth here.
 *
 * `_lim_pair_blk` is chip 2's kernel and lives in src/lib2; these rungs
 * are in src/lib with the rest of the ladder because they are the
 * ARITHMETIC, not the kernel, and DSP4_DYN_SHOOTOUT is a bench build
 * that runs on either part. */
#define DSH_LIM_APPLY \
        r1 = r0; \
        r0 = r13; \
        mrf = r0 * r1 (ssi); \
        MRF_RNS28_SIMD

.global _dsh_lim_today;
_dsh_lim_today:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_v_o, .dsh_v_i)

        r13 = dm(i2, 2);
        DSH_ENV_BODY
        r0 = r14;
        COMPGAIN_SIMD(.dsh_v_p1, .dsh_v_p2)
        DSH_LIM_APPLY
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_v_o, .dsh_v_i)
    DSH_EPILOGUE
_dsh_lim_today.end:

.global _dsh_lim_lut;
_dsh_lim_lut:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_w_o, .dsh_w_i)

        r13 = dm(i2, 2);
        DSH_ENV_BODY
        r0 = r14;
        LUTGAIN_DM
        DSH_LIM_APPLY
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_w_o, .dsh_w_i)
    DSH_EPILOGUE
_dsh_lim_lut.end:

/* rungs 11-13: the WHOLE gate per-sample body three ways. Today it
 * computes log2(env) for one comparison; rung 12 compares in the LINEAR
 * domain instead (DSP4_GATE_LINTHR's arithmetic, which the paired graph
 * #errors on today); rung 13 reads the open/closed TARGET out of the same
 * level -> gain table the compressor uses. The hold state machine and
 * the gain smoother are identical in all three. */
#define DSH_GATE_SM \
        r1 = r14 - 1; \
        r2 = 0; \
        comp(r1, r2); \
        if le r12 = pass r9; \
        r2 = 0x10000000; \
        comp(r0, r8); \
        if ge r12 = pass r2; \
        comp(r0, r8); \
        if ge r1 = pass r15; \
        r14 = r1;

#define DSH_GATE_SMOOTH \
        r4 = r12 - r11; \
        r5 = 0; \
        r2 = r6; \
        r3 = r7; \
        comp(r4, r5); \
        if le r2 = pass r3; \
        mrf = r2 * r4 (ssi); \
        r2 = 0x40000000; \
        r3 = 1; \
        mrf = mrf + r2 * r3 (ssi); \
        r2 = mr0f; \
        r3 = mr1f; \
        r2 = lshift r2 by -31; \
        r3 = lshift r3 by 1; \
        r5 = r2 or r3; \
        r11 = r11 + r5; \
        r1 = r11; \
        r0 = r13; \
        mrf = r0 * r1 (ssi); \
        MRF_RNS28_SIMD

/* The gate's own envelope, which parks its state in r10 rather than r14
 * -- the pair kernel's allocation, kept so the count is honest. */
#define DSH_GATE_ENV \
        r0 = abs r13; \
        r4 = r0 - r10; \
        r5 = 0; \
        r2 = r6; \
        r3 = r7; \
        comp(r4, r5); \
        if le r2 = pass r3; \
        mrf = r2 * r4 (ssi); \
        r2 = 0x40000000; \
        r3 = 1; \
        mrf = mrf + r2 * r3 (ssi); \
        r2 = mr0f; \
        r3 = mr1f; \
        r2 = lshift r2 by -31; \
        r3 = lshift r3 by 1; \
        r5 = r2 or r3; \
        r10 = r10 + r5;

#define DSH_GATE_SEED \
    r7  = 0x00080000;              /* release alpha */ \
    r10 = 0x08000000;              /* envelope */ \
    r11 = 0x10000000;              /* gain */ \
    r12 = 0x10000000;              /* gain target */ \
    r14 = 64;                      /* hold count */ \
    r15 = 64;                      /* hold reload */ \
    r9  = 0x00100000;              /* range */

.global _dsh_gate_today;
_dsh_gate_today:
    DSH_PROLOGUE
    DSH_GATE_SEED
    r8 = 0xFF000000;               /* threshold in the LOG domain */
    DSH_NEST_OPEN(.dsh_k_o, .dsh_k_i)

        r13 = dm(i2, 2);
        DSH_GATE_ENV
        r0 = r10;
        LOG2Q_SIMD(.dsh_k_p)
        r1 = 0x80000000;
        r2 = 0;
        comp(r10, r2);
        if le r0 = pass r1;
        DSH_GATE_SM
        DSH_GATE_SMOOTH
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_k_o, .dsh_k_i)
    DSH_EPILOGUE
_dsh_gate_today.end:

/* The linear-domain threshold: the whole of the log2 above collapses to
 * the envelope itself, because log2(env) >= thr is env >= 2^thr and the
 * DESIGN step already knows 2^thr. The guard against log2(0) goes with
 * it -- zero is simply below the linear threshold. */
.global _dsh_gate_lin;
_dsh_gate_lin:
    DSH_PROLOGUE
    DSH_GATE_SEED
    r8 = 0x00400000;               /* the SAME threshold, 2^thr, Q4.28 */
    DSH_NEST_OPEN(.dsh_l_o, .dsh_l_i)

        r13 = dm(i2, 2);
        DSH_GATE_ENV
        r0 = r10;
        DSH_GATE_SM
        DSH_GATE_SMOOTH
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_l_o, .dsh_l_i)
    DSH_EPILOGUE
_dsh_gate_lin.end:

/* The level -> gain table doing the gate's static curve as well: the
 * table returns the OPEN or CLOSED gain directly, and the state machine
 * reads it rather than comparing a level. The hold logic still needs the
 * open/closed decision, so the compare stays -- against the table's own
 * output, which costs nothing extra. */
.global _dsh_gate_lut;
_dsh_gate_lut:
    DSH_PROLOGUE
    DSH_GATE_SEED
    r8 = 0x08000000;
    DSH_NEST_OPEN(.dsh_m_o, .dsh_m_i)

        r13 = dm(i2, 2);
        DSH_GATE_ENV
        r0 = r10;
        LUTGAIN_DM
        DSH_GATE_SM
        DSH_GATE_SMOOTH
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_m_o, .dsh_m_i)
    DSH_EPILOGUE
_dsh_gate_lut.end:

/*----------------------------------------------------------------------
 * S15 GATE 1 — the four rungs that settle the table's home.
 *--------------------------------------------------------------------*/

/* rung 14: the gain computer, table in L2. */
.global _dsh_cg_lut_l2;
_dsh_cg_lut_l2:
    DSH_PROLOGUE
    DSH_NEST_OPEN(.dsh_p_o, .dsh_p_i)
 r0 = r14; LUTGAIN_L2
    DSH_NEST_CLOSE(.dsh_p_o, .dsh_p_i)
    DSH_EPILOGUE
_dsh_cg_lut_l2.end:

/* rung 15: the WHOLE compressor body with the table in L2 — the number
 * that goes into the generator if L2 is where the tables have to live. */
.global _dsh_comp_lut_l2;
_dsh_comp_lut_l2:
    DSH_PROLOGUE
    r15 = 0x10000000;
    DSH_NEST_OPEN(.dsh_q_o, .dsh_q_i)

        r13 = dm(i2, 2);
        DSH_ENV_BODY
        r0 = r14;
        LUTGAIN_L2
        dm(i5, 0) = r0;
        DSH_APPLY_BODY
        DSH_COMP_TAIL
        dm(i4, 2) = r0;
    DSH_NEST_CLOSE(.dsh_q_o, .dsh_q_i)
    DSH_EPILOGUE
_dsh_comp_lut_l2.end:

/* rung 16: the two-table blend, both tables in DM — what a RAMPING
 * parameter costs per sample against rebuilding the table per block. */
.global _dsh_cg_lut_blend;
_dsh_cg_lut_blend:
    DSH_PROLOGUE
    r9 = 0x08000000;               /* blend fraction, half way */
    DSH_NEST_OPEN(.dsh_s_o, .dsh_s_i)
 r0 = r14; LUTGAIN_BLEND
    DSH_NEST_CLOSE(.dsh_s_o, .dsh_s_i)
    DSH_EPILOGUE
_dsh_cg_lut_blend.end:

/* rung 17: THE PAGING COST. Four words copied L2 -> DM per sample slot,
 * which over a 16-sample block is a 64-word page — one dynamics node's
 * table at the shipped defaults with room to spare. If the L2 gather is
 * expensive and this is cheap, the answer is a per-node DM page filled
 * once per block; if this is expensive too, it is not.
 *
 * Scalar and sequential, because that is what a page copy is. */
.global _dsh_l2page;
_dsh_l2page:
    DSH_PROLOGUE
    bit clr mode1 0x00200000;
    nop;
    nop;
    b0 = _dsh_page_src;
    l0 = DSH_PAGE;                 /* circular: the wrap is free, so what */
    b1 = _dsh_page;                /* is timed is the COPY and not a test */
    l1 = DSH_PAGE;
    m1 = 1;
    DSH_NEST_OPEN(.dsh_t_o, .dsh_t_i)

        r0 = dm(i0, m1);
        dm(i1, m1) = r0;
        r0 = dm(i0, m1);
        dm(i1, m1) = r0;
        r0 = dm(i0, m1);
        dm(i1, m1) = r0;
        r0 = dm(i0, m1);
        dm(i1, m1) = r0;
    DSH_NEST_CLOSE(.dsh_t_o, .dsh_t_i)
    l0 = 0;
    l1 = 0;
    DSH_EPILOGUE
_dsh_l2page.end:

#endif /* DSP4_DYN_SHOOTOUT */
