/*======================================================================
 * ivt.asm — ADSP-21564 Interrupt Vector Table (static, fixed at boot)
 *
 * Placed in seg_rth at 0x000C0000 by the LDF.
 * Each vector entry: 4 PM-word instructions.
 *
 * Offsets used (PM word address from base):
 *   0x00 — Reset
 *   0x60 — SPORT0 DMA completion (_sport_dma_isr)
 *   0x90 — SPI1 RX ready         (_spi1_rx_isr,  both chips)
 *
 * All other vectors: _ivt_default (rti; nop; nop; nop)
 *
 * !! Validate all offsets against ADSP-21564 HRM §5 before production. !!
 *
 * Both chips use the SPI1 RX vector at 0x090. Each chip's binary links
 * against its own spi_handler.asm (_spi_dispatch_c1 / _spi_dispatch_c2).
 *======================================================================*/

.extern _start;
.extern _sport_dma_isr;
.extern _spi1_rx_isr;

.section/pm seg_rth;

/* --------------------------------------------------------------------
 * Default handler — used for all un-assigned vectors
 * ------------------------------------------------------------------ */
_ivt_default:
    rti; nop; nop; nop;

/* ====================================================================
 * Offset 0x000 — Vector  0: Reset
 * ==================================================================== */
    jump _start; nop; nop; nop;

/* Offset 0x004 — Vector  1 */ rti; nop; nop; nop;
/* Offset 0x008 — Vector  2 */ rti; nop; nop; nop;
/* Offset 0x00C — Vector  3 */ rti; nop; nop; nop;
/* Offset 0x010 — Vector  4 */ rti; nop; nop; nop;
/* Offset 0x014 — Vector  5 */ rti; nop; nop; nop;
/* Offset 0x018 — Vector  6 */ rti; nop; nop; nop;
/* Offset 0x01C — Vector  7 */ rti; nop; nop; nop;
/* Offset 0x020 — Vector  8 */ rti; nop; nop; nop;
/* Offset 0x024 — Vector  9 */ rti; nop; nop; nop;
/* Offset 0x028 — Vector 10 */ rti; nop; nop; nop;
/* Offset 0x02C — Vector 11 */ rti; nop; nop; nop;
/* Offset 0x030 — Vector 12 */ rti; nop; nop; nop;
/* Offset 0x034 — Vector 13 */ rti; nop; nop; nop;
/* Offset 0x038 — Vector 14 */ rti; nop; nop; nop;
/* Offset 0x03C — Vector 15 */ rti; nop; nop; nop;
/* Offset 0x040 — Vector 16 */ rti; nop; nop; nop;
/* Offset 0x044 — Vector 17 */ rti; nop; nop; nop;
/* Offset 0x048 — Vector 18 */ rti; nop; nop; nop;
/* Offset 0x04C — Vector 19 */ rti; nop; nop; nop;
/* Offset 0x050 — Vector 20 */ rti; nop; nop; nop;
/* Offset 0x054 — Vector 21 */ rti; nop; nop; nop;
/* Offset 0x058 — Vector 22 */ rti; nop; nop; nop;
/* Offset 0x05C — Vector 23 */ rti; nop; nop; nop;

/* ====================================================================
 * Offset 0x060 — Vector 24: SPORT0 DMA completion (both chips)
 * ==================================================================== */
    jump _sport_dma_isr; nop; nop; nop;

/* Offset 0x064 — Vector 25 */ rti; nop; nop; nop;
/* Offset 0x068 — Vector 26 */ rti; nop; nop; nop;
/* Offset 0x06C — Vector 27 */ rti; nop; nop; nop;
/* Offset 0x070 — Vector 28 */ rti; nop; nop; nop;
/* Offset 0x074 — Vector 29 */ rti; nop; nop; nop;
/* Offset 0x078 — Vector 30 */ rti; nop; nop; nop;
/* Offset 0x07C — Vector 31 */ rti; nop; nop; nop;
/* Offset 0x080 — Vector 32 */ rti; nop; nop; nop;
/* Offset 0x084 — Vector 33 */ rti; nop; nop; nop;
/* Offset 0x088 — Vector 34 */ rti; nop; nop; nop;
/* Offset 0x08C — Vector 35 */ rti; nop; nop; nop;

/* ====================================================================
 * Offset 0x090 — Vector 36: SPI1 RX (both chips)
 * ==================================================================== */
    jump _spi1_rx_isr; nop; nop; nop;

/* Offset 0x094 — Vector 37 */ rti; nop; nop; nop;
/* Offset 0x098 — Vector 38 */ rti; nop; nop; nop;
/* Offset 0x09C — Vector 39 */ rti; nop; nop; nop;

/* Offset 0x0A0 — Vector 40 */ rti; nop; nop; nop;

/* Offset 0x0A4..0x0FC — Vectors 41-63: default */
/* Fill remaining seg_rth space (vectors 41-63 = 23 × 4 instr = 92) */
/* Offset 0x0A4 — Vector 41 */ rti; nop; nop; nop;
/* Offset 0x0A8 — Vector 42 */ rti; nop; nop; nop;
/* Offset 0x0AC — Vector 43 */ rti; nop; nop; nop;
/* Offset 0x0B0 — Vector 44 */ rti; nop; nop; nop;
/* Offset 0x0B4 — Vector 45 */ rti; nop; nop; nop;
/* Offset 0x0B8 — Vector 46 */ rti; nop; nop; nop;
/* Offset 0x0BC — Vector 47 */ rti; nop; nop; nop;
/* Offset 0x0C0 — Vector 48 */ rti; nop; nop; nop;
/* Offset 0x0C4 — Vector 49 */ rti; nop; nop; nop;
/* Offset 0x0C8 — Vector 50 */ rti; nop; nop; nop;
/* Offset 0x0CC — Vector 51 */ rti; nop; nop; nop;
/* Offset 0x0D0 — Vector 52 */ rti; nop; nop; nop;
/* Offset 0x0D4 — Vector 53 */ rti; nop; nop; nop;
/* Offset 0x0D8 — Vector 54 */ rti; nop; nop; nop;
/* Offset 0x0DC — Vector 55 */ rti; nop; nop; nop;
/* Offset 0x0E0 — Vector 56 */ rti; nop; nop; nop;
/* Offset 0x0E4 — Vector 57 */ rti; nop; nop; nop;
/* Offset 0x0E8 — Vector 58 */ rti; nop; nop; nop;
/* Offset 0x0EC — Vector 59 */ rti; nop; nop; nop;
/* Offset 0x0F0 — Vector 60 */ rti; nop; nop; nop;
/* Offset 0x0F4 — Vector 61 */ rti; nop; nop; nop;
/* Offset 0x0F8 — Vector 62 */ rti; nop; nop; nop;
/* Offset 0x0FC — Vector 63 */ rti; nop; nop; nop;
