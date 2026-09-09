/*======================================================================
 * tx_probe.asm — TRANSMIT-PATH ORDER INSTRUMENT (chip 2, bench only)
 *
 * Built only with DSP4_TXPROBE=1; the file assembles to nothing
 * otherwise, so a default image is byte-identical with and without it.
 *
 * WHAT IT ANSWERS. The staircase through Pi -> CPLD -> DSPA -> fabric ->
 * DSPB -> CPLD -> Pi returns every sample at the right position INSIDE
 * its 8-sample block but a third of blocks in place and the rest from
 * roughly the last 225 blocks (S7-5). Every stage but the chip-2
 * TRANSMIT path has been excluded by measurement. The transmit path is
 * buffer -> SPORT3 lane 3 -> CPLD, and nothing so far distinguishes
 *   (i)  the block leaving the DSP already out of order, from
 *   (ii) the block arriving at the gather already out of order.
 *
 * HOW. Chip 2's TX lane 3 is a FULL-WINDOW lane (mcpde=0, cs_mask
 * 0x0003): the DMA moves all 8 window words per frame and slots 0 AND 1
 * are driven onto the wire. Slot 0 (region word 192 + 8*s) is
 * C2_MAIN_ST_OUT — the audio the Pi captures on its LEFT channel. Slot 1
 * (region word 193 + 8*s) is driven but NO node writes it, so it leaves
 * the part as zero and the Pi records it on its RIGHT channel. The
 * _maincap LOGIC build latches both slots from ONE DSP frame
 * (CAP_SLOT_L=0 / CAP_SLOT_R=1, snapshot per S7-1), so a recorded stereo
 * frame is a coherent pair.
 *
 * This writes a self-describing word into slot 1 immediately after the
 * gather has written slot 0 for the same sample of the same block:
 *
 *     bits 31..8  block counter, incremented once per block
 *     bit  4      0 = the active TX buffer is ping, 1 = pong
 *     bits 2..0   sample index within the block
 *
 * The stamp is in order BY CONSTRUCTION. So the capture decides it:
 *   - stamps arrive monotonic  => the buffer->wire path is in order and
 *     the scramble is UPSTREAM of the gather;
 *   - stamps arrive scrambled  => the transmit path, and the
 *     displacement is then read directly in BLOCKS instead of inferred
 *     from the audio value.
 *
 * It costs the audio nothing: slot 1 carries no product signal.
 *======================================================================*/

#ifndef DSP4_TXPROBE
#define DSP4_TXPROBE 0
#endif

#if DSP4_TXPROBE && CHIP_ID == 2

/* Region word offset and per-sample stride of chip 2's TX lane 3 slot 1.
 * Slot 0 is _c2_tx_off[18] = 192 / _c2_tx_stride[18] = 8 in the
 * generated chip2/block_io.asm; slot 1 is the next word of the same
 * window. Overridable so a different lane can be stamped without
 * editing this file. */
#ifndef DSP4_TXPROBE_OFF
#define DSP4_TXPROBE_OFF 193
#endif
#ifndef DSP4_TXPROBE_STRIDE
#define DSP4_TXPROBE_STRIDE 8
#endif

.section/dm seg_dmda;

.global _tx_blk_ctr;
.var _tx_blk_ctr = 0;

.extern _tx_active_buf;
.extern _tx_ping_w;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _tx_probe_tick — once per block, before the gather loop. Clobbers r0.
 *----------------------------------------------------------------------*/
.global _tx_probe_tick;
_tx_probe_tick:
    r0 = dm(_tx_blk_ctr);
    r0 = r0 + 1;
    dm(_tx_blk_ctr) = r0;
    rts;
_tx_probe_tick.end:

/*----------------------------------------------------------------------
 * _tx_probe_stamp — r0 = sample index (0..7). Call AFTER _gather_chip2
 * for the same sample, so the stamp and the audio word land in the same
 * frame of the same buffer half. Clobbers r1-r5 and i4; the chip-2
 * sample loop reloads r5/r6 from _sample_idx/BLOCK_SIZE after the
 * gather, so nothing it holds survives across this call either.
 *----------------------------------------------------------------------*/
.global _tx_probe_stamp;
_tx_probe_stamp:
    r1 = dm(_tx_active_buf);        /* the half the gather just wrote */
    r2 = DSP4_TXPROBE_STRIDE;
    r2 = r0 * r2 (SSI);
    r3 = DSP4_TXPROBE_OFF;
    r2 = r2 + r3;
    r2 = r1 + r2;
    i4 = r2;

    r3 = dm(_tx_blk_ctr);
    r3 = lshift r3 by 8;
    r4 = 7;
    r4 = r0 and r4;
    r3 = r3 or r4;                  /* sample index, bits 2..0 */

    r5 = dm(_tx_ping_w);
    comp(r1, r5);
    if eq jump (pc, .txp_half_done);
    r5 = 0x10;
    r3 = r3 or r5;                  /* pong marker, bit 4 */
.txp_half_done:
    dm(i4, 0) = r3;
    rts;
_tx_probe_stamp.end:

#endif /* DSP4_TXPROBE && CHIP_ID == 2 */
