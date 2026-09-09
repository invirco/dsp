/*======================================================================
 * sport_init.asm — block ISR, SEC dispatch and buffer-pointer state
 *
 * Shared by both Chip 1 and Chip 2 (assembled with -DCHIP_ID=1|2).
 *
 * The register-level bring-up lives in C (TODO(dsp4-plumbing) slices
 * 2-3): sru_config.c (DAI routing), sport_config.c (half-SPORT
 * CTL/MCTL/CS), dma_config.c (DDE descriptor rings, SEC, SPI1, SPEN).
 * Geometry and DMA buffers are generated (chipN/block_io.asm +
 * chipN/lane_config.c). This file owns:
 *
 *  - the active-buffer pointer variables used by the scatter/gather
 *    paths, plus the C->asm setters (_set_rx_bufs/_set_tx_bufs) that
 *    convert byte addresses to the core word view (L1 NW = BW/4);
 *  - _sec_isr: the core SECI vector handler (IVT slot 15) — reads
 *    SEC_CSID, dispatches the block clock (SPORT0_A_DMA, source 37)
 *    and the SPI2 param link (INTR_SPI2_STAT, source 71), acks via
 *    SEC_END;
 *  - _sport_dma_work: per-block ping/pong toggle + block_ready.
 *
 * Bring-up notes: ISR uses secondary registers (SRRFL + DAG1 low) so
 * the main loop's registers survive; verify SEC CSID/END semantics and
 * MMR dm() access from asm on first hardware run.
 *======================================================================*/

#include <def21564.h>
#include "c_abi.h"

/* No local audio-block defines here. There used to be four
 * (BLOCK_SIZE 32, NUM_CHANNELS 32, SAMPLE_RATE 48000, TDM_WORD_BITS 32),
 * all of them unreferenced in this file. BLOCK_SIZE was review finding
 * D11: each .asm assembles independently so it collided with nothing
 * today, but it sat in exactly the file where a future use would
 * silently mean 32 while the rest of the tree runs at DSP4_BLOCK_SIZE.
 * If this file ever needs the block size, `#include "dsp_block.h"` —
 * that header is the single source. The SPORT SLEN/WSIZE fields below
 * are hardware word widths, not block sizes. */

.section/dm seg_dmda;

/* Current buffer pointers (word view; toggled by the block ISR). All
 * four are declared on both chips; the ones not used by this chip
 * stay 0. */
.global _rx_active_buf;
.var _rx_active_buf;
.global _tx_active_buf;
.var _tx_active_buf;
.global _ic_rx_active_buf;
.var _ic_rx_active_buf;
.global _ic_tx_active_buf;
.var _ic_tx_active_buf;

/* Ping/pong word addresses (set by _set_rx_bufs/_set_tx_bufs).
 * "rx" = this chip's inbound region (chip1 RX / chip2 IC RX),
 * "tx" = outbound region (chip1 IC TX / chip2 TX). */
.var _rx_ping_w;
.var _rx_pong_w;
.var _tx_ping_w;
.var _tx_pong_w;

#if DSP4_BLK_LATCH
/* THE HALF THE NEXT BLOCK GOES INTO, held apart from the half the
 * scatter/gather are currently walking.
 *
 * _scatter_chipN and _gather_chipN reload the active-buffer pointer from
 * DM on EVERY SAMPLE (see the generated chipN/block_io.asm), and the
 * block ISR used to retarget that same word. So when the interrupt
 * landed part-way through a block's sample loop -- which it does, every
 * block, at whatever point the loop had reached -- the block's remaining
 * samples were scattered from, or gathered into, the OTHER half at the
 * same sample offsets. Each transmitted 8-sample window then carried two
 * or three consecutive blocks spliced together at the sample the
 * interrupt happened to fall on: measured on the part 2026-09-09 with a
 * block counter stamped into TX lane 3 slot 1, samples 0-1 from block B,
 * samples 3-7 from B+1 and sample 2 from B+2, on a build with ZERO block
 * overruns. That is the ORDER DEFECT (S8-1).
 *
 * The ISR now advances these instead, and _blk_latch_bufs copies them
 * into the active pointers ONCE per block, before the sample loop runs.
 * The phase is unchanged -- the same halves in the same order -- and the
 * pointers simply stop moving under the loop's feet. */
.var _rx_pend_buf;
.var _tx_pend_buf;
#endif

#if DSP4_TXPROBE
/* The transmit-path order instrument reads this to record which half
 * the gather wrote into (src/tx_probe.asm). Exported only for that
 * build, so a default image cannot depend on it. */
.global _tx_ping_w;
#endif

/* Boot-time product config from the Pi/CM4 host (D1: Pi masters DSP SPI;
 * the S MCU is not in the parameter path) */
.global _chan_mask;
.var _chan_mask = 0xFFFFFFFF;     /* D32 default: all 32 channels active */
.global _aux_mask;
.var _aux_mask = 0x0FFF;          /* D32 default: 12 aux buses active */

/* Block-ready flag: set by DMA ISR, cleared by main loop after processing */
.global _block_ready;
.var _block_ready = 0;

/* Frame counter (for debug / profiling) */
.global _frame_count;
.var _frame_count = 0;

/* SEC source id currently being serviced. Held in DM rather than a
 * register because _spi2_rx_work clobbers r0 (it reads SPI2_RFIFO into
 * it), so the id read at the top of _sec_isr does NOT survive the
 * dispatch — writing a stale r0 to SEC_END would acknowledge the wrong
 * source and leave the real one asserted. Found 2026-08-12; the whole
 * SPI path would have wedged after its first interrupt. Also exposed
 * read-only as DIAG_LAST_CSID. */
.global _sec_active_csid;
.var _sec_active_csid = 0;

/* Diagnostic counters (diag.asm owns the storage) */
.extern _diag_sec_count;
.extern _diag_unk_csid;
.extern _diag_unk_count;
.extern _diag_blk_overrun;

/* Chip identity (defined in main.asm) */
.extern _chip_id;

.section/pm seg_pmco;

.extern _spi2_rx_work;

/*----------------------------------------------------------------------
 * _set_rx_bufs / _set_tx_bufs — C-callable (C ABI: args in r4, r8)
 * Store the inbound/outbound ping+pong buffer addresses, converted
 * from the C byte view to the core word view (>> 2), and initialize
 * the active pointers to ping.
 *----------------------------------------------------------------------*/
.global _set_rx_bufs;
_set_rx_bufs:
    r4 = lshift r4 by -2;         /* byte -> word */
    r8 = lshift r8 by -2;
    dm(_rx_ping_w) = r4;
    dm(_rx_pong_w) = r8;
#if DSP4_BLK_LATCH
    /* PONG, not ping -- see the phase note in _set_tx_bufs. The DDE
     * starts on the ping row, so the half the core may touch is the
     * other one. */
    dm(_rx_pend_buf) = r8;
#if CHIP_ID == 1
    dm(_rx_active_buf) = r8;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r8;
#endif
#else
#if CHIP_ID == 1
    dm(_rx_active_buf) = r4;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r4;
#endif
#endif
    C_RETURN
_set_rx_bufs.end:

.global _set_tx_bufs;
_set_tx_bufs:
    r4 = lshift r4 by -2;
    r8 = lshift r8 by -2;
    dm(_tx_ping_w) = r4;
    dm(_tx_pong_w) = r8;
#if DSP4_BLK_LATCH
    /* THE PHASE, AND IT WAS OFF BY ONE HALF.
     *
     * The DDE starts each region on its PING row and moves to pong at
     * the first row boundary -- which is the same edge that raises the
     * block interrupt. Starting the core on ping too, and toggling it in
     * that interrupt, put the core on exactly the half the channel was
     * working on: the gather wrote block N into the half being clocked
     * onto the wire, so the wire carried block N for the slots the DDE
     * had not reached yet and the two-blocks-old contents of that same
     * half for the ones it had already passed. Measured 2026-09-09 on a
     * build with ZERO block overruns: each transmitted 8-sample window
     * carried three consecutive blocks, the split at a fixed sample.
     *
     * Starting on PONG puts the core one half behind the channel for
     * good: it fills the row the DDE has just finished with, and that
     * row goes out on the next block. Costs nothing and adds no latency
     * the ping-pong did not already have. */
    dm(_tx_pend_buf) = r8;
#if CHIP_ID == 1
    dm(_ic_tx_active_buf) = r8;
#elif CHIP_ID == 2
    dm(_tx_active_buf) = r8;
#endif
#else
#if CHIP_ID == 1
    dm(_ic_tx_active_buf) = r4;
#elif CHIP_ID == 2
    dm(_tx_active_buf) = r4;
#endif
#endif
    C_RETURN
_set_tx_bufs.end:

/*----------------------------------------------------------------------
 * _sec_isr — core SECI vector (IVT slot 15)
 *
 * Demux via SEC_CSID: block clock (SPORT0_A_DMA = 37) and SPI2 status
 * (INTR_SPI2_STAT = 71). Ack by writing the source id to SEC_END —
 * reloaded from _sec_active_csid, not from r0, which the handlers
 * clobber. Banks the FULL
 * register file + DAG1 (SRRFL/SRRFH/SRD1L/SRD1H): the ramp path uses
 * i4/f8/f10/r10, so low-half banking alone would corrupt the
 * interrupted block processing. DAG2/PM registers are not used on the
 * ISR path (audited 2026-07-31).
 *----------------------------------------------------------------------*/
.global _sec_isr;
_sec_isr:
    bit set mode1 BITM_REGF_MODE1_SRRFL | BITM_REGF_MODE1_SRRFH |
                  BITM_REGF_MODE1_SRD1L | BITM_REGF_MODE1_SRD1H;
    nop;                          /* effect latency */
    push sts;
#if DSP4_SIMD_STRIPS
    /* THE INTERRUPTED CODE MAY HAVE BEEN RUNNING SIMD. `push sts` has
     * saved MODE1, so PEYEN is restored by `pop sts` on the way out -- but
     * without clearing it here the HANDLER BODY executes on both compute
     * units, and every register it writes becomes a pair write. Clearing
     * it per-ISR is the systemic fix; masking interrupts around every SIMD
     * region does not scale past one kernel. */
    bit clr mode1 0x00200000;      /* PEYEN */
    nop;
#endif

    r0 = dm(REG_SEC0_CSID0);      /* active source id */
    dm(REG_SEC0_CSID0) = r0;      /* ACK: see below */
    dm(_sec_active_csid) = r0;    /* survives the handlers; see above */

    /* The write-back on the line above is step 2 of the SEC handshake and
     * it is NOT optional (HRM ch.6, "Core/SEC Handshake Requirements"):
     *   1. read SEC_CSID[n] for the source id
     *   2. WRITE IT BACK to SEC_CSID[n] - this is the acknowledge that
     *      tells the SEC the core has accepted the request
     *   3. run the handler
     *   4. write the same id to SEC_END when the ISR is done
     * Without step 2 "the SEC knows what it passed to the core because of
     * the write to the SEC_CSID[n] register" never happens, so it never
     * arbitrates another request: the core is delivered EXACTLY ONE SECI
     * per reset. Bench 2026-08-22: ~21 host transactions gave SEC_COUNT=1
     * and SPI_RX_COUNT=1, while polling the very same handler from the
     * main loop (bisect rung 27) ran it repeatedly and round-tripped
     * DIAG_MAGIC, CHIP_ID and BUILD_ID correctly - which is what proved
     * the fault was delivery, not the SPI block or the handler. */

    r2 = dm(_diag_sec_count);
    r2 = r2 + 1;
    dm(_diag_sec_count) = r2;

    r1 = INTR_SPORT0_A_DMA;
    comp(r0, r1);
    if eq jump (pc, .sec_block);
    r1 = INTR_SPI2_STAT;
    comp(r0, r1);
    if eq jump (pc, .sec_spi);

    /* No handler for this source. Silently acking it would hide a
     * misrouted SEC configuration, so record what arrived. */
    dm(_diag_unk_csid) = r0;
    r2 = dm(_diag_unk_count);
    r2 = r2 + 1;
    dm(_diag_unk_count) = r2;
    jump (pc, .sec_ack);

.sec_block:
    call _sport_dma_work;
    jump (pc, .sec_ack);

.sec_spi:
    call _spi2_rx_work;

.sec_ack:
    r0 = dm(_sec_active_csid);    /* reload: the handlers clobber r0 */
    dm(REG_SEC0_END) = r0;        /* acknowledge source */

    pop sts;
    bit clr mode1 BITM_REGF_MODE1_SRRFL | BITM_REGF_MODE1_SRRFH |
                  BITM_REGF_MODE1_SRD1L | BITM_REGF_MODE1_SRD1H;
    nop;
    rti;
_sec_isr.end:

/*----------------------------------------------------------------------
 * _sport_dma_work — block boundary (one DMA-done per buffer half on
 * the block-clock lane; all lanes share the LOGIC frame sync, so one
 * toggle covers every lane). Called from _sec_isr; clobbers r2/r3
 * (secondary bank).
 *----------------------------------------------------------------------*/
.global _sport_dma_work;
_sport_dma_work:
    /* ACK THE DMA FIRST. DMA_STAT.IRQDONE is write-1-to-clear, and until
     * it is cleared the channel holds its interrupt request asserted --
     * so the SEC re-arbitrates the same source the instant SEC_END is
     * written and the core re-enters this ISR immediately, forever.
     * Bench 2026-08-23, first run with audio actually flowing: 11e6
     * frames and 11e6 SEC interrupts over 4.6 s of DIAG_TICKS, against
     * an expected 1500/s. Only bit 0 is written: IRQERR (bit 1) is left
     * alone so a real channel error stays latched and visible in
     * DIAG_DMA0_STAT. */
    r2 = 0x00000001;
    dm(REG_DMA0_STAT) = r2;

    /* Toggle inbound pointer */
#if DSP4_BLK_LATCH
    r2 = dm(_rx_pend_buf);
#elif CHIP_ID == 1
    r2 = dm(_rx_active_buf);
#elif CHIP_ID == 2
    r2 = dm(_ic_rx_active_buf);
#endif
    r3 = dm(_rx_ping_w);
    comp(r2, r3);
    if ne jump (pc, .rx_use_ping); /* active was pong -> back to ping */
    r3 = dm(_rx_pong_w);          /* active was ping -> pong */
.rx_use_ping:
#if DSP4_BLK_LATCH
    dm(_rx_pend_buf) = r3;
#elif CHIP_ID == 1
    dm(_rx_active_buf) = r3;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r3;
#endif

    /* Toggle outbound pointer */
#if DSP4_BLK_LATCH
    r2 = dm(_tx_pend_buf);
#elif CHIP_ID == 1
    r2 = dm(_ic_tx_active_buf);
#elif CHIP_ID == 2
    r2 = dm(_tx_active_buf);
#endif
    r3 = dm(_tx_ping_w);
    comp(r2, r3);
    if ne jump (pc, .tx_use_ping);
    r3 = dm(_tx_pong_w);
.tx_use_ping:
#if DSP4_BLK_LATCH
    dm(_tx_pend_buf) = r3;
#elif CHIP_ID == 1
    dm(_ic_tx_active_buf) = r3;
#elif CHIP_ID == 2
    dm(_tx_active_buf) = r3;
#endif

    /* Signal block ready. If it was ALREADY set, the main loop did not
     * finish the previous block before this one landed — the buffer
     * pointers have moved on regardless, so that block's audio is lost.
     * DIAG_BLK_OVERRUN counting up is the "the DSP cannot keep up"
     * indicator, and it is invisible from outside without this. */
    r2 = dm(_block_ready);
    r3 = 0;
    comp(r2, r3);
    if eq jump (pc, .blk_no_overrun);
    r2 = dm(_diag_blk_overrun);
    r2 = r2 + 1;
    dm(_diag_blk_overrun) = r2;
.blk_no_overrun:
    r2 = 1;
    dm(_block_ready) = r2;

    /* Increment frame counter */
    r2 = dm(_frame_count);
    r2 = r2 + 1;
    dm(_frame_count) = r2;

    rts;
_sport_dma_work.end:

#if DSP4_BLK_LATCH
/*----------------------------------------------------------------------
 * _blk_latch_bufs — called from the main loop once per block, after
 * _block_ready has been consumed and before the sample loop runs. Moves
 * the pending halves into the pointers the generated scatter/gather
 * walk, so a block's eight samples all come from, and all go to, ONE
 * buffer half. Clobbers r0, and r1 under DSP4_TX_EARLY (main-loop bank;
 * the caller is between blocks).
 *
 * DSP4_TX_EARLY (S9-2 Option A, 2026-09-09) — WHY THIS IS A POINTER AND
 * NOT A STAGING COPY.
 *
 * With zero blocks missed, the first frame of each DMA half still went out
 * carrying what that half held two blocks earlier: 87.4999 % of transmitted
 * frames ordered at the full D24 graph, 81.2499 % with the Pi playback input
 * added, 100.0000 % with the load cut. The gather finishes at the END of a
 * period the graph has spent 92.7 % of, and the DDE clocks frame 0 of that
 * same half at the TOP of it. Frame 0's deadline is a whole block period
 * earlier than the block's own, and under load the core loses that race
 * every block. It is a deadline, not an indexing error: the count of late
 * frames tracks the LOAD, not the block size.
 *
 * The 2026-09-09 costing proposed a STAGING BLOCK -- gather into scratch,
 * copy it into the DMA half at the top of the next period -- at ~640
 * cycles/block and 320 words of DM. That copy is not needed, and it would
 * not even have worked: a copy at the top of period N is still racing frame
 * 0 of period N, just with 640 cycles of head start instead of 300,000.
 *
 * There are TWO halves and the DDE touches each one every OTHER period, so
 * the half the DDE is not clocking is idle for a whole period and the core
 * can simply write THAT one. Period N: the DDE clocks half A while the core
 * fills half B; period N+1: the DDE clocks B -- complete before the period
 * began -- while the core fills A. No third buffer, no copy, no change to
 * the DMA topology or to the one-interrupt-one-half mapping the phase fix
 * and the diagnostics rest on. It costs one block of OUTPUT LATENCY and
 * nothing else, and the latency is measured on the part, not asserted.
 *
 * It is the OPPOSITE of _tx_pend_buf, so it is derived from the same toggle
 * the ISR uses and cannot drift from it.
 *
 * IT IS A PER-CHIP MASK, because the cost is per chip and it was measured
 * that way: 1 = chip 1's inter-chip TX, 2 = chip 2's converter TX, 3 = both.
 * The 2026-09-09 costing said "+16 samples"; with both chips on, the part
 * says +32 (through-DSP offset min 14,496 -> 14,526, median 14,501 ->
 * 14,535, 20 reps each). It has to: the signal crosses TWO outbound
 * regions, chip 1 -> fabric -> chip 2 -> converters, and each one that
 * moves a half ahead adds its own block. So the mask exists to let the
 * ruling buy one block or two; the arm that decides is whether chip-2-only
 * still reads 100.0000 % ordered on the wire.
 *----------------------------------------------------------------------*/
#define DSP4_TX_EARLY_HERE (((DSP4_TX_EARLY) >> (CHIP_ID - 1)) & 1)
#if DSP4_TX_EARLY && !DSP4_BLK_LATCH
#error "DSP4_TX_EARLY needs DSP4_BLK_LATCH: without the latch the buffer \
pointer moves under the sample loop and 'one half ahead' has no meaning."
#endif
.global _blk_latch_bufs;
_blk_latch_bufs:
    r0 = dm(_rx_pend_buf);
#if CHIP_ID == 1
    dm(_rx_active_buf) = r0;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r0;
#endif
    r0 = dm(_tx_pend_buf);
#if DSP4_TX_EARLY_HERE
    /* One half further on than the ISR's pending half. Same two rows, same
     * order; the core is simply a period ahead of the wire. */
    r1 = dm(_tx_ping_w);
    comp(r0, r1);
    if ne jump (pc, .txe_have);   /* pend was pong -> write ping */
    r1 = dm(_tx_pong_w);          /* pend was ping -> write pong */
.txe_have:
    r0 = r1;
#endif
#if CHIP_ID == 1
    dm(_ic_tx_active_buf) = r0;
#elif CHIP_ID == 2
    dm(_tx_active_buf) = r0;
#endif
    rts;
_blk_latch_bufs.end:
#endif
