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

/* ---- Audio block parameters ---- */
#define BLOCK_SIZE         32
#define NUM_CHANNELS       32      /* console channel strips */
#define SAMPLE_RATE        48000
#define TDM_WORD_BITS      32

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
#if CHIP_ID == 1
    dm(_rx_active_buf) = r4;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r4;
#endif
    C_RETURN
_set_rx_bufs.end:

.global _set_tx_bufs;
_set_tx_bufs:
    r4 = lshift r4 by -2;
    r8 = lshift r8 by -2;
    dm(_tx_ping_w) = r4;
    dm(_tx_pong_w) = r8;
#if CHIP_ID == 1
    dm(_ic_tx_active_buf) = r4;
#elif CHIP_ID == 2
    dm(_tx_active_buf) = r4;
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
#if CHIP_ID == 1
    r2 = dm(_rx_active_buf);
#elif CHIP_ID == 2
    r2 = dm(_ic_rx_active_buf);
#endif
    r3 = dm(_rx_ping_w);
    comp(r2, r3);
    if ne jump (pc, .rx_use_ping); /* active was pong -> back to ping */
    r3 = dm(_rx_pong_w);          /* active was ping -> pong */
.rx_use_ping:
#if CHIP_ID == 1
    dm(_rx_active_buf) = r3;
#elif CHIP_ID == 2
    dm(_ic_rx_active_buf) = r3;
#endif

    /* Toggle outbound pointer */
#if CHIP_ID == 1
    r2 = dm(_ic_tx_active_buf);
#elif CHIP_ID == 2
    r2 = dm(_tx_active_buf);
#endif
    r3 = dm(_tx_ping_w);
    comp(r2, r3);
    if ne jump (pc, .tx_use_ping);
    r3 = dm(_tx_pong_w);
.tx_use_ping:
#if CHIP_ID == 1
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
