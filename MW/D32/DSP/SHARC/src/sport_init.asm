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
 *    and the SPI1 param link (source 91), acks via SEC_END;
 *  - _sport_dma_work: per-block ping/pong toggle + block_ready.
 *
 * Bring-up notes: ISR uses secondary registers (SRRFL + DAG1 low) so
 * the main loop's registers survive; verify SEC CSID/END semantics and
 * MMR dm() access from asm on first hardware run.
 *======================================================================*/

#include <def21564.h>

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

/* Chip identity (defined in main.asm) */
.extern _chip_id;

.section/pm seg_pmco;

.extern _spi1_rx_work;

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
    rts;
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
    rts;
_set_tx_bufs.end:

/*----------------------------------------------------------------------
 * _sec_isr — core SECI vector (IVT slot 15)
 *
 * Demux via SEC_CSID: block clock (SPORT0_A_DMA = 37) and SPI1 status
 * (= 91). Ack by writing the source id to SEC_END. Banks the FULL
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

    r0 = dm(REG_SEC0_CSID0);      /* active source id */
    r1 = INTR_SPORT0_A_DMA;
    comp(r0, r1);
    if eq call _sport_dma_work;
    r1 = INTR_SPI1_STAT;
    comp(r0, r1);
    if eq call _spi1_rx_work;

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

    /* Signal block ready */
    r2 = 1;
    dm(_block_ready) = r2;

    /* Increment frame counter */
    r2 = dm(_frame_count);
    r2 = r2 + 1;
    dm(_frame_count) = r2;

    rts;
_sport_dma_work.end:
