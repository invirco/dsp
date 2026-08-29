/*======================================================================
 * meter.asm — Peak-hold level metering for D32 DSP
 *
 * Each chip binary includes this file. The meter array is sized for
 * the maximum channel count used by either chip.
 *
 *   _meter_peaks[0..31]  — Chip 1: input strip levels (post-gain)
 *   _meter_peaks[0..17]  — Chip 2: output bus levels
 *
 * Decay: DSP4_MTR_DECAY_F32, derived in dsp_block.h from the BLOCK RATE
 *   as exp(-1 / (rate × τ)) with τ = 1.333 s — the same peak-hold time
 *   constant the rebuilt in-kernel meter uses (fixed_ref.METER_TAU_PEAK_S),
 *   so the two meters agree by construction instead of by coincidence.
 *
 *   It was a hand constant, 0.99950, derived for 48 kHz / 32 = 1500
 *   blocks/s and never revisited when the operating point became BLOCK=8.
 *   Applied at 6000 blocks/s it gives τ = 0.333 s: the documented 1.33 s
 *   peak hold decayed FOUR TIMES FAST, in the SHIPPING image (review
 *   finding D6). Same class as the third recorded meter defect — a
 *   constant derived for one block rate applied at another — in the one
 *   meter path the 2026-08-28 rebuild did not replace.
 *
 * Usage:
 *   block_io scatter calls _meter_update inline (per sample, per channel).
 *   main.asm calls _meter_decay_block(r0=num_channels) once per block.
 *
 * SPI readback: _meter_peaks[] is in the SPI dispatch table.
 *   H1S1 sends a READ request (SPI word 0 with READ flag) to get any
 *   meter value. See spi_handler.asm for protocol details.
 *======================================================================*/

#include "dsp_block.h"

#define MAX_METERS  64    /* enough for 32 ch + 18 outputs + headroom */

.section/dm seg_dmda;

.global _meter_peaks;
.var _meter_peaks[MAX_METERS];   /* float32 linear, initialized 0.0 */

/* Per-block decay coefficient, IEEE-754 single. Loaded with `f2 = dm()`
 * below, so the initialiser is the float's BIT PATTERN — see the header. */
.var _meter_decay = DSP4_MTR_DECAY_F32;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _meter_update — Peak-hold update for one channel (called per sample)
 *
 * In:  f0 = abs(sample)  — must be ≥ 0
 *      r1 = channel index (0-based)
 * Clobbers: f2, i0, m0
 *----------------------------------------------------------------------*/
.global _meter_update;
_meter_update:
    m0 = r1;
    i0 = _meter_peaks;
    modify(i0, m0);               /* i0 → _meter_peaks[r1] */
    f2 = dm(i0, 0);               /* current peak */
    comp(f0, f2);
    if le f0 = f2;                /* if new <= peak, keep old peak in f0 */
    dm(i0, 0) = f0;               /* write (either new peak or unchanged old) */
    rts;
_meter_update.end:

/*----------------------------------------------------------------------
 * _meter_decay_block — Apply decay to N channels (call once per block)
 *
 * In:  r0 = number of channels to decay
 * Clobbers: f2, f3, i0, m0, m1, lcntr
 *----------------------------------------------------------------------*/
.global _meter_decay_block;
_meter_decay_block:
    m0 = 0;
    m1 = 1;
    i0 = _meter_peaks;
    f2 = dm(_meter_decay);
    lcntr = r0; do .mdec until lce;
        f3 = dm(i0, m0);          /* read (no advance) */
        f3 = f3 * f2;             /* apply decay */
        dm(i0, m1) = f3;          /* write and advance */
    .mdec:
        nop;                      /* safe loop-end: label before nop, not before rts */
    rts;
_meter_decay_block.end:
