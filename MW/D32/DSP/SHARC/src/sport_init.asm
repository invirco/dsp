/*======================================================================
 * sport_init.asm — SPORT/TDM and interrupt configuration for ADSP-21564
 *
 * Shared by both Chip 1 and Chip 2 (assembled with -DCHIP_ID=1|2).
 *
 * SPORT layout (slot map SOT: shared/dsp4-logic/, decision D2;
 * sport_id = DAI port index, half A = RX (I ports), half B = TX
 * (O ports); SPORT0-3 on DAI0, SPORT4-7 on DAI1. LOGIC drives all
 * BCK/FS — every SPORT half is a clock slave):
 *
 *   Chip 1 (DSPA / U6):
 *     SPORT0..3 A RX — ADC/NET TDM8 inputs (A_I0..A_I3, 32 ch)
 *     SPORT4 A RX    — codec return  (A_I4: CS 0x0D — slots 0,2,3)
 *     SPORT5 A RX    — D32 snake     (A_I5: CS 0xFF)
 *     SPORT6 A RX    — Pi PCM        (A_I6: CS 0x03)
 *     SPORT7 A RX    — MEMS talkback (A_I7: CS 0x20)
 *     SPORT0..2 B TX — mix fabric MIX_0..MIX_2 (TDM16, packed 37 slots)
 *
 *   Chip 2 (DSPB / U5):
 *     SPORT0..2 A RX — mix fabric MIX_0..MIX_2 (as above)
 *     SPORT0..4 B TX — DAC 1-16, codec/snake, DAC MAIN, NET 1-8
 *                      (TDM8 full-window lanes)
 *
 * Geometry, CS masks, lane tables and the DMA ping-pong buffers are
 * GENERATED in chipN/block_io.asm (lane-major layout — see
 * MW/D32/DSP/dsp4-plumbing.md). This file owns the control variables,
 * the block ISR, and — once slices 2-3 land — the register-level
 * SPORT/SRU/DDE/SEC bring-up per that design doc.
 *
 * TODO(dsp4-plumbing): _sport_init below is a STUB. The former body
 * wrote invented MMR addresses (0x0800xxxx — not real 2156x register
 * space) implementing the superseded single-SPORT7 model, and has been
 * removed rather than left to mislead. Implement against
 * <def21564.h>/<sru21564.h> + the generated lane tables:
 *   1. SRU routing (DAI pin map in dsp4-plumbing.md)
 *   2. Half-SPORT CTL/MCTL/CS from _cN_*_lanes tables
 *   3. DDE 2-descriptor ping-pong rings per lane; SEC block-clock IRQ
 *   4. SPI slave for the Pi param link (real REG_SPI1_* addresses;
 *      spi_handler.asm has the same invented-address problem)
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

/* ---- Audio block parameters ---- */
#define BLOCK_SIZE         32
#define NUM_CHANNELS       32      /* console channel strips */
#define SAMPLE_RATE        48000
#define TDM_WORD_BITS      32

.section/dm seg_dmda;

/* Generated DMA buffers (lane-major, exact sizes) — block_io.asm */
#if CHIP_ID == 1
.extern _dma_rx_ping;
.extern _dma_rx_pong;
.extern _dma_ic_tx_ping;
.extern _dma_ic_tx_pong;
#elif CHIP_ID == 2
.extern _dma_ic_rx_ping;
.extern _dma_ic_rx_pong;
.extern _dma_tx_ping;
.extern _dma_tx_pong;
#endif

/* Current buffer pointers (toggled by the block ISR). All four are
 * declared on both chips (block_io externs per chip); the ones not
 * used by this chip stay 0. */
.global _rx_active_buf;
.var _rx_active_buf;
.global _tx_active_buf;
.var _tx_active_buf;
.global _ic_rx_active_buf;
.var _ic_rx_active_buf;
.global _ic_tx_active_buf;
.var _ic_tx_active_buf;

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

/*----------------------------------------------------------------------
 * _sport_init — STUB (see TODO(dsp4-plumbing) in the header)
 *
 * Currently only initializes the ping/pong base pointers so the
 * scatter/gather paths and the ISR are exercisable. No MMR access.
 *----------------------------------------------------------------------*/
.global _sport_init;
_sport_init:
#if CHIP_ID == 1
    r0 = _dma_rx_ping;
    dm(_rx_active_buf) = r0;
    r0 = _dma_ic_tx_ping;
    dm(_ic_tx_active_buf) = r0;
#elif CHIP_ID == 2
    r0 = _dma_ic_rx_ping;
    dm(_ic_rx_active_buf) = r0;
    r0 = _dma_tx_ping;
    dm(_tx_active_buf) = r0;
#endif
    rts;
_sport_init.end:

/*----------------------------------------------------------------------
 * _sport_dma_isr — block-boundary ISR (block clock: one DMA-done per
 * block toggles this chip's ping/pong base pointers; all lanes share
 * the LOGIC frame sync so one toggle covers every lane).
 *
 * TODO(dsp4-plumbing): hook to the SEC block-clock interrupt
 * (SPORT0_A_DMA) and acknowledge via SEC_END when slice 3 lands.
 *----------------------------------------------------------------------*/
.global _sport_dma_isr;
_sport_dma_isr:
    push sts;

#if CHIP_ID == 1
    /* Toggle RX buffer pointer */
    r0 = dm(_rx_active_buf);
    r1 = _dma_rx_ping;
    comp(r0, r1);
    if eq jump (pc, .rx_to_pong);
    dm(_rx_active_buf) = r1;
    jump (pc, .toggle_ic_tx);
.rx_to_pong:
    r0 = _dma_rx_pong;
    dm(_rx_active_buf) = r0;

.toggle_ic_tx:
    r0 = dm(_ic_tx_active_buf);
    r1 = _dma_ic_tx_ping;
    comp(r0, r1);
    if eq jump (pc, .ic_tx_to_pong);
    dm(_ic_tx_active_buf) = r1;
    jump (pc, .dma_isr_done);
.ic_tx_to_pong:
    r0 = _dma_ic_tx_pong;
    dm(_ic_tx_active_buf) = r0;

#elif CHIP_ID == 2
    /* Toggle IC RX buffer pointer */
    r0 = dm(_ic_rx_active_buf);
    r1 = _dma_ic_rx_ping;
    comp(r0, r1);
    if eq jump (pc, .ic_rx_to_pong);
    dm(_ic_rx_active_buf) = r1;
    jump (pc, .toggle_tx);
.ic_rx_to_pong:
    r0 = _dma_ic_rx_pong;
    dm(_ic_rx_active_buf) = r0;

.toggle_tx:
    r0 = dm(_tx_active_buf);
    r1 = _dma_tx_ping;
    comp(r0, r1);
    if eq jump (pc, .tx_to_pong);
    dm(_tx_active_buf) = r1;
    jump (pc, .dma_isr_done);
.tx_to_pong:
    r0 = _dma_tx_pong;
    dm(_tx_active_buf) = r0;
#endif

.dma_isr_done:
    /* Signal block ready */
    r0 = 1;
    dm(_block_ready) = r0;

    /* Increment frame counter */
    r0 = dm(_frame_count);
    r0 = r0 + 1;
    dm(_frame_count) = r0;

    pop sts;
    rti;
_sport_dma_isr.end:
