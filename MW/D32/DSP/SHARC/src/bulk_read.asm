/*======================================================================
 * bulk_read.asm — stream a region of DM out of SPI2 by DMA (S61).
 *
 * WHY. A capture read over the parameter link is one peek per word, and a
 * peek is three transactions: write PEEK_ADDR, ask PEEK_DATA, collect.
 * Measured on MW-D24-2 (findings S61-1) every transaction costs ~100 us
 * at 8-10 MHz and ~250 us at 1 MHz, and the floor is SPI_RDY plus the
 * kernel's per-ioctl cost, not the SCLK -- so word-at-a-time tops out at
 * ~3,300 words/s whatever the clock. A 16,384-word capture took 12.3 s.
 *
 * WHAT. The host names a region and a length, the 1 kHz tick checksums
 * it in chunks, and a GO write hands the SPI2 transmit path to DMA26
 * (SPI2 TX DMA) for exactly that region. The host then clocks the whole
 * region in one CS-held transfer. The tick gives the port back to the
 * parameter link when the channel has stopped and the TFIFO is empty.
 *
 *   0xE0D0 BULK_ADDR  RW  first WORD address (the peek convention)
 *   0xE0D1 BULK_LEN   RW  words, 1..DSP4_BULK_MAX
 *   0xE0D2 BULK_CTL   W   1 = ARM (checksum), 2 = GO (stream), 0 = cancel
 *                     R   state: 0 idle, 1 summing, 2 armed, 3 streaming
 *   0xE0D3 BULK_SUM1  R   s1 = sum w          (mod 2^32)  over the region
 *   0xE0D4 BULK_SUM2  R   s2 = sum of the s1s (mod 2^32)  -- order-sensitive
 *   0xE0D5 BULK_RUNS  R   streams completed normally
 *   0xE0D6 BULK_ABORT R   streams ended by the timeout
 *   0xE0D7 BULK_ERR   R   rejected commands (bad state / length)
 *   0xE0D8 BULK_DSTAT R   DMA26_STAT at the end of the last stream
 *   0xE0D9 BULK_MS    R   ticks the last stream was live
 *
 * ON THE WIRE, from the first word clocked after GO:
 *   BULK_MAGIC, LEN, w[0] .. w[LEN-1], then whatever an empty TFIFO sends.
 * The header is pushed straight into the 2-deep TFIFO; the data follow by
 * DMA as the host clocks. The host finds the header at any word offset,
 * so the parameter link's two answer phases (D74) do not matter here.
 *
 * GO does not answer (spi_handler skips the echo when the state is 3):
 * the TFIFO belongs to the stream from that point. GO also takes SPI2
 * EN low and back, which flushes both FIFOs, and turns RX off for the
 * stream so the host's MOSI filler is never dispatched as a parameter
 * write (a zero pair is Chan001Gain001 = 0). The restore does the same
 * EN cycle, so the host must resync the link after a stream -- every
 * tool on this bench already does.
 *
 * Only DSP4_TEST_NODES builds carry it, so the shipping image is
 * unchanged. The idle cost is one load and compare in the tick and one
 * in _spi_poll.
 *======================================================================*/

#include <def21564.h>
#include "diag.h"
#include "dsp_block.h"

#if DSP4_TEST_NODES

#ifndef DSP4_BULK_MAX
#define DSP4_BULK_MAX      65536
#endif
#define BULK_CHUNK         1024        /* words checksummed per 1 ms tick */
#define BULK_TIMEOUT_MS    3000
#define BULK_MAGIC         0xB0CA5E61

#define BULK_IDLE          0
#define BULK_SUMMING       1
#define BULK_ARMED         2
#define BULK_STREAMING     3

#define SPI_TFS_MASK       0x00070000
#define SPI_TFS_EMPTY      0x00040000
#define SPI_STAT_ERRS      0x00000030  /* ROR | TUR, W1C */
#define SPI_ILAT_RUWM      0x00000002
#define SPI_TXCTL_TEN      0x00000001
#define SPI_TXCTL_TDR_NF   0x00000010  /* DMA request while TFIFO not full */
#define DMA_CFG_TX         0x00000221  /* EN | PSIZE04 | MSIZE04, WNR=0, STOP */
#define DMA_STAT_RUN       0x00000700
#define DMA_STAT_ERRC      0x00000070
#define DMA_STAT_W1C       0x00000003  /* IRQERR | IRQDONE */

.section/dm seg_dmda;

.global _bulk_state;
.var _bulk_state = 0;
.var _bulk_addr = 0;
.var _bulk_len = 0;
.var _bulk_pos = 0;
.var _bulk_s1 = 0;
.var _bulk_s2 = 0;
.var _bulk_runs = 0;
.var _bulk_aborts = 0;
.var _bulk_errs = 0;
.var _bulk_dstat = 0;
.var _bulk_ms = 0;
.var _bulk_quiet = 0;         /* consecutive ticks seen stopped + empty */
.var _bulk_ctl_save = 0;
.var _bulk_rxctl_save = 0;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _bulk_write — In: r2 = address (0xE0D0..0xE0DF), r1 = value.
 * Called from _diag_write, inside _spi2_rx_work. Clobbers r4-r7 only.
 *----------------------------------------------------------------------*/
.global _bulk_write;
_bulk_write:
    r4 = DIAG_BULK_CTL;
    comp(r2, r4);
    if eq jump (pc, .bw_ctl);
    r4 = DIAG_BULK_ADDR;
    comp(r2, r4);
    if eq jump (pc, .bw_addr);
    r4 = DIAG_BULK_LEN;
    comp(r2, r4);
    if eq jump (pc, .bw_len);
    rts;

.bw_addr:
    r4 = dm(_bulk_state);
    r5 = BULK_STREAMING;
    comp(r4, r5);
    if eq jump (pc, .bw_err);
    dm(_bulk_addr) = r1;
    r4 = BULK_IDLE;               /* a new region invalidates the sum */
    dm(_bulk_state) = r4;
    rts;

.bw_len:
    r4 = dm(_bulk_state);
    r5 = BULK_STREAMING;
    comp(r4, r5);
    if eq jump (pc, .bw_err);
    dm(_bulk_len) = r1;
    r4 = BULK_IDLE;
    dm(_bulk_state) = r4;
    rts;

.bw_ctl:
    r4 = dm(_bulk_state);
    r5 = BULK_STREAMING;
    comp(r4, r5);
    if eq jump (pc, .bw_err);     /* the tick owns a live stream */
    r5 = 1;
    comp(r1, r5);
    if eq jump (pc, .bw_arm);
    r5 = 2;
    comp(r1, r5);
    if eq jump (pc, .bw_go);
    r4 = BULK_IDLE;               /* anything else cancels */
    dm(_bulk_state) = r4;
    rts;

.bw_arm:
    r4 = dm(_bulk_len);
    r5 = 1;
    comp(r4, r5);
    if lt jump (pc, .bw_err);
    r5 = DSP4_BULK_MAX;
    comp(r4, r5);
    if gt jump (pc, .bw_err);
    r4 = 0;
    dm(_bulk_pos) = r4;
    dm(_bulk_s1) = r4;
    dm(_bulk_s2) = r4;
    r4 = BULK_SUMMING;
    dm(_bulk_state) = r4;
    rts;

.bw_go:
    r5 = BULK_ARMED;
    comp(r4, r5);
    if ne jump (pc, .bw_err);     /* GO needs a finished checksum */

    /* Flush both FIFOs and take RX out of the picture. */
    r4 = dm(REG_SPI2_CTL);
    dm(_bulk_ctl_save) = r4;
    r5 = dm(REG_SPI2_RXCTL);
    dm(_bulk_rxctl_save) = r5;
    r6 = 0;
    dm(REG_SPI2_CTL) = r6;        /* EN low: FIFOs reset */
    r6 = SPI_STAT_ERRS;
    dm(REG_SPI2_STAT) = r6;
    r6 = 0;
    dm(REG_SPI2_RXCTL) = r6;      /* REN off for the stream */
    r6 = SPI_TXCTL_TEN;
    dm(REG_SPI2_TXCTL) = r6;
    dm(REG_SPI2_CTL) = r4;        /* EN back, same configuration */

    /* Arm DMA26 from its registers, FLOW = STOP -- the arming that works
     * on this part (dma_config.c: descriptor lists take ERRC = 3). */
    r6 = 0;
    dm(REG_DMA26_CFG) = r6;
    r6 = DMA_STAT_W1C;
    dm(REG_DMA26_STAT) = r6;
    r6 = dm(_bulk_addr);
    r6 = lshift r6 by 2;          /* word address -> byte address */
    r7 = 0x00240000;              /* L1 needs its system alias; L2 is 1:1 */
    comp(r6, r7);
    if lt jump (pc, .bw_sys);
    r7 = 0x003FFFFF;
    comp(r6, r7);
    if gt jump (pc, .bw_sys);
    r7 = 0x28000000;
    r6 = r6 + r7;
.bw_sys:
    dm(REG_DMA26_ADDRSTART) = r6;
    r6 = dm(_bulk_len);
    dm(REG_DMA26_XCNT) = r6;
    r6 = 4;
    dm(REG_DMA26_XMOD) = r6;

    /* Header into the TFIFO (2 deep), pushes separated -- see the FIFO
     * write hazard note at .spi_read_respond. */
    r6 = BULK_MAGIC;
    dm(REG_SPI2_TFIFO) = r6;
    nop;
    nop;
    r6 = dm(_bulk_len);
    dm(REG_SPI2_TFIFO) = r6;
    nop;

    r6 = SPI_TXCTL_TEN | SPI_TXCTL_TDR_NF;
    dm(REG_SPI2_TXCTL) = r6;
    r6 = DMA_CFG_TX;
    dm(REG_DMA26_CFG) = r6;       /* EN last */

    r6 = 0;
    dm(_bulk_ms) = r6;
    dm(_bulk_quiet) = r6;
    r6 = BULK_STREAMING;
    dm(_bulk_state) = r6;
    rts;

.bw_err:
    r4 = dm(_bulk_errs);
    r5 = 1;
    r4 = r4 + r5;
    dm(_bulk_errs) = r4;
    rts;
_bulk_write.end:

/*----------------------------------------------------------------------
 * _bulk_read — In: r2 = address. Out: r4. Clobbers r4, r5; keeps r0-r3.
 *----------------------------------------------------------------------*/
.global _bulk_read;
_bulk_read:
    r4 = DIAG_BULK_ADDR;
    r5 = r2 - r4;
    r4 = 0;
    comp(r5, r4);
    if lt rts;
    r4 = 9;
    comp(r5, r4);
    if gt jump (pc, .br_zero);
    r4 = 0;
    comp(r5, r4);
    if eq jump (pc, .br_addr);
    r4 = 1;
    comp(r5, r4);
    if eq jump (pc, .br_len);
    r4 = 2;
    comp(r5, r4);
    if eq jump (pc, .br_state);
    r4 = 3;
    comp(r5, r4);
    if eq jump (pc, .br_s1);
    r4 = 4;
    comp(r5, r4);
    if eq jump (pc, .br_s2);
    r4 = 5;
    comp(r5, r4);
    if eq jump (pc, .br_runs);
    r4 = 6;
    comp(r5, r4);
    if eq jump (pc, .br_aborts);
    r4 = 7;
    comp(r5, r4);
    if eq jump (pc, .br_errs);
    r4 = 8;
    comp(r5, r4);
    if eq jump (pc, .br_dstat);
    r4 = dm(_bulk_ms);
    rts;
.br_addr:   r4 = dm(_bulk_addr);   rts;
.br_len:    r4 = dm(_bulk_len);    rts;
.br_state:  r4 = dm(_bulk_state);  rts;
.br_s1:     r4 = dm(_bulk_s1);     rts;
.br_s2:     r4 = dm(_bulk_s2);     rts;
.br_runs:   r4 = dm(_bulk_runs);   rts;
.br_aborts: r4 = dm(_bulk_aborts); rts;
.br_errs:   r4 = dm(_bulk_errs);   rts;
.br_dstat:  r4 = dm(_bulk_dstat);  rts;
.br_zero:
    r4 = 0;
    rts;
_bulk_read.end:

/*----------------------------------------------------------------------
 * _bulk_tick — from _diag_timer_isr (full register file + DAG1 shadowed,
 * so i0 and the shadow l0 = 0 are ours). Clobbers r0-r7, i0.
 *----------------------------------------------------------------------*/
.global _bulk_tick;
_bulk_tick:
    r0 = dm(_bulk_state);
    r1 = BULK_SUMMING;
    comp(r0, r1);
    if eq jump (pc, .bt_sum);
    r1 = BULK_STREAMING;
    comp(r0, r1);
    if eq jump (pc, .bt_stream);
    rts;

.bt_sum:
    r2 = dm(_bulk_len);
    r3 = dm(_bulk_pos);
    r4 = r2 - r3;                 /* words left */
    r5 = BULK_CHUNK;
    comp(r4, r5);
    if gt r4 = r5;
    r5 = dm(_bulk_addr);
    r5 = r5 + r3;                 /* first word of this chunk */
    r3 = r3 + r4;
    dm(_bulk_pos) = r3;
    r6 = dm(_bulk_s1);
    r7 = dm(_bulk_s2);
    r1 = 1;
.bt_sum_loop:
    i0 = r5;
    r0 = dm(i0, 0);
    r6 = r6 + r0;
    r7 = r7 + r6;
    r5 = r5 + r1;
    r4 = r4 - r1;
    if gt jump (pc, .bt_sum_loop);
    dm(_bulk_s1) = r6;
    dm(_bulk_s2) = r7;
    comp(r3, r2);
    if lt rts;
    r0 = BULK_ARMED;
    dm(_bulk_state) = r0;
    rts;

.bt_stream:
    r0 = dm(_bulk_ms);
    r0 = r0 + 1;
    dm(_bulk_ms) = r0;
    r1 = BULK_TIMEOUT_MS;
    comp(r0, r1);
    if gt jump (pc, .bt_abort);

    r2 = dm(REG_DMA26_STAT);
    r3 = DMA_STAT_ERRC;
    r3 = r2 AND r3;
    if ne jump (pc, .bt_abort);   /* the channel faulted: give the port back */
    r3 = DMA_STAT_RUN;
    r3 = r2 AND r3;
    if ne jump (pc, .bt_busy);    /* still moving words */
    r3 = dm(REG_SPI2_STAT);
    r4 = SPI_TFS_MASK;
    r3 = r3 AND r4;
    r4 = SPI_TFS_EMPTY;
    comp(r3, r4);
    if ne jump (pc, .bt_busy);    /* host has not clocked the tail yet */
    /* Stopped and empty on TWO ticks running: the last word has been in
     * the shift register at least 1 ms, far longer than one at any SCLK. */
    r3 = dm(_bulk_quiet);
    r3 = r3 + 1;
    dm(_bulk_quiet) = r3;
    r4 = 2;
    comp(r3, r4);
    if lt rts;
    r3 = dm(_bulk_runs);
    r3 = r3 + 1;
    dm(_bulk_runs) = r3;
    jump (pc, .bt_restore);

.bt_busy:
    r3 = 0;
    dm(_bulk_quiet) = r3;
    rts;

.bt_abort:
    r2 = dm(REG_DMA26_STAT);
    r3 = dm(_bulk_aborts);
    r3 = r3 + 1;
    dm(_bulk_aborts) = r3;

.bt_restore:
    dm(_bulk_dstat) = r2;
    r3 = 0;
    dm(REG_DMA26_CFG) = r3;
    r3 = DMA_STAT_W1C;
    dm(REG_DMA26_STAT) = r3;
    r4 = dm(_bulk_ctl_save);
    r3 = 0;
    dm(REG_SPI2_CTL) = r3;        /* EN low: flush whatever is left */
    r3 = SPI_STAT_ERRS;
    dm(REG_SPI2_STAT) = r3;
    r3 = SPI_ILAT_RUWM;
    dm(REG_SPI2_ILAT_CLR) = r3;
    r3 = dm(_bulk_rxctl_save);
    dm(REG_SPI2_RXCTL) = r3;
    r3 = SPI_TXCTL_TEN;
    dm(REG_SPI2_TXCTL) = r3;
    dm(REG_SPI2_CTL) = r4;
    r3 = BULK_IDLE;
    dm(_bulk_state) = r3;
    rts;
_bulk_tick.end:

#endif /* DSP4_TEST_NODES */
