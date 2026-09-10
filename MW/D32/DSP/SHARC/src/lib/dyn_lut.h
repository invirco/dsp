/*======================================================================
 * dyn_lut.h — the level -> gain table's shape, and its PAIRED lookup.
 *
 * The shape is here rather than in one .asm because four places have to
 * agree on it exactly: the design step (dyn_lut_fx.asm), the scalar
 * lookup (the same file), the paired lookup (this file's macro, used by
 * dyn_simd_fx.asm and lib2/lim_simd_fx.asm), and the table declarations
 * the generator emits per node. A table designed on one grid and indexed
 * on another is worse than no table at all.
 *
 * tools/dsp/dyn_lut_design.py is the fifth, off the part: it computes
 * this index bit for bit and measures the error the resulting table
 * gives against tools/dsp/fixed_ref.py. THAT is where the constants
 * below come from -- see the ladder in dyn_lut_fx.asm's header.
 *====================================================================*/
#ifndef DSP4_DYN_LUT_H
#define DSP4_DYN_LUT_H

/* Mantissa bits per octave: 2^K points per octave. K = 4 is the
 * measured choice -- K = 3 fails the full parameter sweep at 0.135 dB
 * and K = 4 passes at 0.0950 dB against PW's 0.1 dB bar. */
#define DYN_LUT_K       4
#define DYN_LUT_FSH     (31 - DYN_LUT_K)

/* The octaves the table covers. Octave 10 is one below -100 dBFS in
 * Q4.28 and octave 30 is the top of its positive range. */
#define DYN_LUT_OCTLO   10
#define DYN_LUT_OCTHI   30

/* Length, including the guard entry the interpolation's T[i+1] reads. */
#define DYN_LUT_N   (((DYN_LUT_OCTHI - DYN_LUT_OCTLO + 1) << DYN_LUT_K) + 1)

/* Points designed per block per node while a table is being rebuilt.
 *
 * THE NUMBER IS SET BY THE WORST CASE, WHICH IS EVERY NODE AT ONCE.
 * Each node's key starts unmatched, so at the FIRST CONFIG_COMMIT all
 * thirty-two of chip 1's compressors restart their design in the same
 * block. One point is a whole _compgain_fx, about 211 instructions, so
 * the peak is 32 x CHUNK x 211 cycles on top of the graph:
 *
 *   CHUNK   peak added      chip 1 D32 (60.3 % base)   blocks to fill
 *      16   ~108,000 = 33 %          ~93 %                  22 (7.3 ms)
 *       4    ~27,000 =  8 %          ~68 %                  85 (28 ms)
 *
 * MEASURED: at CHUNK = 16 the s15l arm's `_proc_cyc_max` latched
 * 124.06 % on chip 1 -- a block that went OVER BUDGET -- where the same
 * arm's average was 60.27 % and every other arm's max was under 93 %.
 * `capacity.sh` cannot see it in its overrun delta, because that delta
 * starts after the boot and config ladder and the burst is inside it.
 *
 * 4 is the shipped value: the peak is a fifth of what it was and 28 ms
 * of the polynomial after a parameter move is inaudible -- it is the
 * arithmetic that already ships.
 *
 * OVERRIDABLE, AND THE REASON IS AN INSTRUMENT (S16). 28 ms is SHORTER
 * than the 1,024-sample scope buffer (21 ms) plus the SPI readback, so
 * tools/pi/dsp4_dyn_lut_audio.py -- which compares a capture taken
 * while the table is stale against one taken after it is designed --
 * cannot show that its first capture was the polynomial's: the design
 * finishes inside the capture. Building the measurement arm with
 * -DDYN_LUT_CHUNK=1 puts the design at 337 blocks = 112 ms, five times
 * the buffer, and the two captures then straddle the changeover
 * unambiguously. It is a measurement setting; 4 is what ships. */
#ifndef DYN_LUT_CHUNK
#define DYN_LUT_CHUNK   4
#endif

/*----------------------------------------------------------------------
 * LUTGAIN_SIMD — the paired lookup.
 *
 * In:  r0 = envelope pair, Q4.28.  i6 -> _dyn_lutp[2], the two channels'
 *      table bases (interleaved, A then B) -- i6 because r8-r11 are the
 *      caller's and every other DAG in the pair kernels is spoken for.
 * Out: r0 = gain pair, Q4.28.  Clobbers r0-r5, r7, i0, i1.
 *
 * This obeys COMPGAIN_SIMD's register contract exactly -- r0-r5 and r7
 * scratch, r6 and r8-r15 the caller's -- so it drops into the pair
 * kernels where COMPGAIN_SIMD sits without moving anything else.
 *
 * THE GATHER LEAVES SIMD, AND COMES BACK, and the pairing survives it.
 * Both channels' addresses go out in ONE store, because a direct-address
 * store inside a PEYEN region writes PEy's word right after PEx's -- the
 * same property that makes _bqfl_two a pair -- and the four gathered
 * words come back in two paired reads for the same reason. PEy's
 * registers are NOT disturbed while PEYEN is down (only the compute unit
 * is idle), so r4, the interpolation fraction, survives the excursion
 * and does not have to be spilled.
 *
 * MEASURED ON THE PART (dyn_shootout.asm rung 4, S15): 54.1 cycles per
 * sample-pair against COMPGAIN_SIMD's 215.2. Dropping the pairing
 * entirely costs 23.0 cycles MORE, and routing the second channel over
 * the PM bus costs 6.0 MORE rather than saving the two instructions it
 * removes -- S14-1's PM penalty, measured on a store and again on a read.
 *--------------------------------------------------------------------*/
#define LUTGAIN_SIMD \
    r1 = leftz r0; \
    r2 = 31 - DYN_LUT_OCTLO; \
    r2 = r2 - r1;                  /* the octave, biased by OCT_LO */ \
    r3 = ashift r0 by r1;          /* leading 1 to bit 31 */ \
    r4 = 0x7FFFFFFF; \
    r3 = r3 and r4;                /* mantissa fraction, Q0.31 */ \
    r4 = lshift r3 by -DYN_LUT_FSH; /* top K bits: the sub-index */ \
    r2 = lshift r2 by DYN_LUT_K; \
    r2 = r2 + r4;                  /* the index */ \
    r4 = 0; \
    comp(r2, r4); \
    if lt r2 = pass r4;            /* below the table: the floor entry */ \
    r4 = DYN_LUT_N - 2; \
    comp(r2, r4); \
    if gt r2 = pass r4;            /* above it: the last cell */ \
    r5 = dm(i6, 0);                /* each PE's own table base */ \
    r2 = r2 + r5; \
    dm(_dlut_ix) = r2;             /* both addresses, ONE store */ \
    r4 = lshift r3 by DYN_LUT_K; \
    r5 = 0x7FFFFFFF; \
    r4 = r4 and r5;                /* the fraction, Q0.31 (S15-4) */ \
    bit clr mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dlut_ix); \
    i0 = r2; \
    r3 = dm(_dlut_ix + 1); \
    i1 = r3; \
    r2 = dm(i0, 1); \
    r3 = dm(i0, 0); \
    r5 = dm(i1, 1); \
    r7 = dm(i1, 0); \
    dm(_dlut_t0) = r2; \
    dm(_dlut_t0 + 1) = r5; \
    dm(_dlut_t1) = r3; \
    dm(_dlut_t1 + 1) = r7; \
    bit set mode1 0x00200000; \
    nop; \
    nop; \
    r2 = dm(_dlut_t0); \
    r3 = dm(_dlut_t1); \
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

#endif /* DSP4_DYN_LUT_H */
