/*======================================================================
 * spi_handler.asm — SPI parameter receive handler for ADSP-21564 (D32)
 *
 * Chip 1 receives SPI traffic from the Pi/CM4 host on SPI2 (CS1).
 * Protocol: 32-bit address + 32-bit coefficient word per write.
 *
 * Address space: 0x0000–0x0FFF → Chip 1 parameter RAM only.
 * Chip 2 has its own independent SPI connection (CS2) and a separate
 * spi_handler.asm instance. The host selects the target chip via the CS line.
 *
 * For each write, the handler:
 *   1. Reads the address and data from the SPI receive FIFO.
 *   2. Resolves ramp profile from flags bits 11:8.
 *   3. Writes via _ramp_set_target or directly for Instant parameters.
 *
 * This handler runs as SPI2 RX interrupt on Chip 1 only.
 *
 * SPI protocol format (MSB first):
 *   Word 0:  [31:16] = address[15:0]
 *            [15:0]  = flags (bit 12 = chip2, bits 11:8 = ramp_profile_id)
 *   Word 1:  [31:0]  = coefficient (IEEE 754 float32 or integer)
 *
 * Ramp profile IDs (bits 11:8):
 *   0 = Instant (default)
 *   1 = GainFast
 *   2 = GainSafe
 *   3 = EqSafe
 *   4 = DynSafe
 *
 * Infrastructure (hand-maintained). The rev-C card wires the host to
 * each DSP's SPI2 port (PA_00/01/04/05 + SPI_RDY on PB_05), which is
 * also the BMODE=0b010 slave-boot port; D8's move to SPI0/SPI1 is a
 * rev-D change and must not be made here early.
 *======================================================================*/

#include "../diag.h"

/* ---- ADSP-21564 SPI register addresses (from HRM) ---- */
/* Real ADSP-2156x SPI2 MMR addresses (sys/ADSP-21564.h) */
#define SPI2_RFIFO   0x31030050   /* SPI2 receive FIFO */
#define SPI2_TFIFO   0x31030058   /* SPI2 transmit FIFO */
#define SPI2_STAT    0x31030040   /* SPI2 status */
#define SPI2_CTL     0x31030004   /* SPI2 control */
#define SPI2_ILAT_CLR 0x31030048  /* SPI2 masked-interrupt CLEAR (W1C) */

/* The interrupt condition this handler services, and the two sticky
 * error bits worth clearing once they have been latched into
 * _diag_spi_stat_stk. Positions from sys/ADSP-21564.h: RUWM = 1,
 * ROR = 4, TUR = 5. */
#define SPI2_ILAT_RUWM  0x00000002
#define SPI2_STAT_RFS_MASK 0x00007000  /* SPI_STAT.RFS, bits 14:12 */
#define SPI2_STAT_RFS_FULL 0x00004000  /* RFS = 4 = Full RFIFO */
#define SPI2_STAT_ERRS  0x00000030   /* ROR | TUR */

/* SPI_STAT.TFS (bits 18:16) == 4 means "Empty TFIFO" (HRM Table 15-32).
 * At 32-bit word size SPI_TFIFO is only 2 words deep, which is exactly
 * one read response — so a response may only be queued into an empty
 * FIFO, or every later answer shifts by one. */
#define SPI2_TFS_MASK   0x00070000
#define SPI2_TFS_EMPTY  0x00040000

/* ---- Address space ---- */
#define RAMP_PROFILE_SHIFT 8     /* bits 11:8 = ramp profile ID */
#define RAMP_PROFILE_MASK  0x0F
#define READ_FLAG          0x00002000  /* bit 13: READ request */

/* ---- Ramp profile IDs ---- */
#define RAMP_INSTANT   0
#define RAMP_GAINFST   1
#define RAMP_GAINSAF   2
#define RAMP_EQSAFE    3
#define RAMP_DYNSAFE   4

/* ---- Block processing ---- */
#define BLOCK_SIZE     32


.section/dm seg_dmda;

/* Ramp profile table extern — contiguous array of 5 profiles × 5 words each */
.extern _ramp_profile_table;
.extern _ramp_set_target;

/* Chip 1 SPI dispatch table (in dsp_params.asm) — maps SPI address → DM target */
.extern _spi_dispatch_c1;
.extern _spi_dispatch_c1_size;   /* bounds for dispatch (generated) */

/* SPI stats — exposed read-only as DIAG_SPI_RX_COUNT /
 * DIAG_SPI_ERR_COUNT, and zeroed by a write to DIAG_CLEAR. */
.global _spi_rx_count;
.var _spi_rx_count = 0;
.global _spi_err_count;
.var _spi_err_count = 0;

.extern _diag_spi_stat_stk;
.extern _diag_resp_drop;


.extern _product_config_write;
.extern _diag_read;
.extern _diag_write;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _spi2_rx_work — SPI2 receive handler
 *
 * Called from _sec_isr (SEC source INTR_SPI2_STAT) with secondary
 * r0-r7 + DAG1 low active. Reads one {address, value} pair from the
 * RX FIFO.
 *----------------------------------------------------------------------*/
.global _spi2_rx_work;
_spi2_rx_work:
    /* Sample SPI_STAT before draining the FIFO and OR it into the
     * sticky latch: RUWM and the FIFO-status fields clear as soon as
     * the reads below empty RFIFO, so a later poll from the host can
     * never see them. ROR/TUR/MF/TC are the ones that matter — a
     * receive overrun or a mode fault is otherwise silent. */
    r2 = dm(SPI2_STAT);
    r3 = dm(_diag_spi_stat_stk);
    r3 = r3 OR r2;
    dm(_diag_spi_stat_stk) = r3;

    /* Collect ONLY when the receive FIFO actually holds something.
     *
     * The condition is RFIFO **FULL**, not merely non-empty. A request
     * is TWO words and this handler drains two; SPI_STAT.RFE only says
     * "not empty", so entering with a single word present drains one
     * real word and one garbage one, and from that moment every later
     * pair is shifted by a word. That is a permanent desync, and it is
     * what an RFE guard let through.
     *
     * Bench 2026-08-22, with the RFE guard: 51 config writes produced
     * 117 handler entries (2.3x too many), CONFIG_COMMIT never applied
     * — BOOT_STAGE stuck at 5, BOOT_CFG 0, PRODUCT_ID 0 — and host
     * reads came back one word out of phase. RFS = 4 (Full RFIFO, 2
     * words at 32-bit word size) is the condition that matches both the
     * RUWM=FULL interrupt trigger and the two-word protocol. */
    r2 = dm(SPI2_STAT);
    r3 = SPI2_STAT_RFS_MASK;
    r2 = r2 AND r3;
    r3 = SPI2_STAT_RFS_FULL;
    comp(r2, r3);
    if ne jump (pc, .spi_done);   /* not a whole request yet — see below */

    r0 = dm(SPI2_RFIFO);          /* Word 0: address + flags */
    r1 = dm(SPI2_RFIFO);          /* Word 1: coefficient value */

    /* Increment RX counter */
    r2 = dm(_spi_rx_count);
    r5 = 1;
    r2 = r2 + r5;
    dm(_spi_rx_count) = r2;

    /* Extract address (bits 31:16) */
    r2 = lshift r0 by -16;        /* address in r2 */
    r3 = 0xFFFF;
    r2 = r2 AND r3;

    /* Check READ flag (bit 13 of Word 0) — respond before dispatch */
    r4 = READ_FLAG;
    r4 = r0 AND r4;
    r5 = 0;
    comp(r4, r5);
    if ne jump (pc, .spi_read);

    /* ---- Chip 1: local parameter write ---- */

    /* Extract ramp profile ID (bits 11:8) */
    r3 = r0;
    r3 = lshift r3 by -RAMP_PROFILE_SHIFT;
    r4 = RAMP_PROFILE_MASK;
    r3 = r3 AND r4;

    /* Product-config register block at 0xF000+ (product_config.asm) */
    r4 = 0xF000;
    comp(r2, r4);
    if ge jump (pc, .spi_config);

    /* Diagnostic block at 0xE000+ (diag.asm). Mostly read-only; the
     * writable few are LED mode, the peek address and the counter
     * clear. Unknown addresses in range are ignored, NOT counted as
     * errors — DIAG_NOP depends on that. */
    r4 = DIAG_BASE;
    comp(r2, r4);
    if ge jump (pc, .spi_diag_write);

    /* Bounds check address against dispatch table size (generated) */
    r4 = dm(_spi_dispatch_c1_size);
    comp(r2, r4);
    if ge jump (pc, .spi_error);

    /* Dispatch on ramp profile */
    r5 = RAMP_INSTANT;
    comp(r3, r5);
    if eq jump (pc, .spi_instant);

    /* Ramped write: call _ramp_set_target
     * r0 = pointer to coefficient (from dispatch table)
     * r1 = target value (already in r1 as coefficient)
     * r2 = ramp mode
     * r3 = frame count (in samples = block frames × BLOCK_SIZE) */

    /* Look up target DM address from dispatch table */
    i0 = _spi_dispatch_c1;
    m0 = r2;
    modify(i0, m0);
    r0 = dm(i0, 0);              /* r0 = DM address of target variable */
    r5 = 0;
    comp(r0, r5);
    if eq jump (pc, .spi_error); /* unmapped SPI address */

    /* Look up frame count from ramp profile preset */
    /* r3 still has profile ID; each profile = 5 words (see ramp_tables.asm)
     * Table layout: { mode, up_frames, down_frames, curve, scope }
     * Profile base address = _ramp_profile_table + profile_id × 5 */
    r4 = r3;
    r5 = 5;
    r4 = r4 * r5 (SSI);           /* word offset into profile table */
    r7 = r4;                      /* save profile_base_offset before direction adjust */

    /* Determine direction: if target > current, use up_frames (+1); else down_frames (+2) */
    i1 = r0;
    f5 = dm(i1, 0);               /* current value */
    f6 = r1;                      /* target value (as float) */
    comp(f6, f5);
    if ge jump (pc, .spi_ramp_up);

    /* Down ramp — frame count is at offset +2 in profile */
    r5 = 2;
    r4 = r4 + r5;
    jump (pc, .spi_ramp_go);

.spi_ramp_up:
    /* Up ramp — frame count is at offset +1 in profile */
    r5 = 1;
    r4 = r4 + r5;

.spi_ramp_go:
    /* Read frame count from profile table at [base + direction_offset] */
    i0 = _ramp_profile_table;
    m0 = r4;
    modify(i0, m0);
    r3 = dm(i0, 0);               /* frame count (block-rate frames) */
    r3 = lshift r3 by 5;          /* × BLOCK_SIZE (32 = 2^5) */

    /* Read ramp mode from profile base (offset 0): use saved r7 */
    i0 = _ramp_profile_table;
    m0 = r7;                      /* profile_base_offset (profile_id * 5) */
    modify(i0, m0);
    r2 = dm(i0, 0);               /* mode: 0=Instant, 1=Slew, 2=LinearFrames */

    call _ramp_set_target;
    jump (pc, .spi_done);

.spi_instant:
    /* Direct write via dispatch table */
    i0 = _spi_dispatch_c1;
    m0 = r2;
    modify(i0, m0);
    r4 = dm(i0, 0);              /* r4 = DM address of target variable */
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .spi_error); /* unmapped SPI address */
    i1 = r4;
    dm(i1, 0) = r1;              /* write coefficient to target */
    jump (pc, .spi_done);

.spi_config:
    /* r2 = config address (0xF000+), r1 = value */
    call _product_config_write;
    jump (pc, .spi_done);

.spi_diag_write:
    /* r2 = diag address (0xE000+), r1 = value */
    call _diag_write;
    jump (pc, .spi_done);

.spi_error:
    r2 = dm(_spi_err_count);
    r5 = 1;
    r2 = r2 + r5;
    dm(_spi_err_count) = r2;

.spi_done:
    /* Acknowledge the SPI's own interrupt condition and clear the
     * sticky errors. ROR/TUR are write-1-to-clear and have already been
     * ORed into _diag_spi_stat_stk at the top of this function, so the
     * record survives while a NEW overrun stays visible instead of
     * being hidden behind the first one.
     *
     * HONEST STATUS (2026-08-22): this was added to explain why the
     * handler runs exactly ONCE per reset — ~21 host transactions gave
     * SEC_COUNT = 1, SPI_RX_COUNT = 1, with SPI_STAT = 0x00144033
     * (RUWM still asserted after the drain, ROR set, FCS stalling
     * SPI2_RDY). **It did not change that**: the same measurement after
     * this change is bit-identical. Clearing ILAT is still right — ADI's
     * own drivers do it — but it is NOT the cause, and the once-only
     * behaviour is still open. Do not read this comment as a fix. */
    r2 = SPI2_ILAT_RUWM;
    dm(SPI2_ILAT_CLR) = r2;
    r2 = SPI2_STAT_ERRS;
    dm(SPI2_STAT) = r2;
    rts;

.spi_read:
    /* READ request: resolve the value, then queue it with an echo of
     * the request word. The response is collected by the master's
     * NEXT transaction — the RX watermark only fires once both words
     * of THIS one are in, by which point MISO has already been
     * shifted. See the protocol note at the top of diag.asm. */
    r4 = DIAG_BASE;
    comp(r2, r4);
    if ge jump (pc, .spi_read_diag);
    r4 = dm(_spi_dispatch_c1_size);
    comp(r2, r4);
    if ge jump (pc, .spi_read_zero);     /* out-of-range → return 0 */
    i0 = _spi_dispatch_c1;
    m0 = r2;
    modify(i0, m0);
    r4 = dm(i0, 0);                      /* DM address of target variable */
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .spi_read_zero);     /* unmapped → return 0 */
    i1 = r4;
    r4 = dm(i1, 0);                      /* read value from DM */
    jump (pc, .spi_read_respond);
.spi_read_diag:
    call _diag_read;                     /* r4 = value; r0 preserved */
    jump (pc, .spi_read_respond);
.spi_read_zero:
    r4 = 0;
.spi_read_respond:
    /* Only queue into an EMPTY TFIFO (2 words deep at 32-bit). If the
     * host has not collected the previous answer, drop this one and
     * count it: a dropped response is recoverable, a FIFO overflow
     * silently misaligns every answer that follows. */
    r5 = dm(SPI2_STAT);
    r6 = SPI2_TFS_MASK;
    r5 = r5 AND r6;
    r6 = SPI2_TFS_EMPTY;
    comp(r5, r6);
    if ne jump (pc, .spi_read_drop);
    dm(SPI2_TFIFO) = r0;                 /* echo of the request word 0 */
    dm(SPI2_TFIFO) = r4;                 /* value */
    jump (pc, .spi_done);
.spi_read_drop:
    r5 = dm(_diag_resp_drop);
    r6 = 1;
    r5 = r5 + r6;
    dm(_diag_resp_drop) = r5;
    jump (pc, .spi_done);
_spi2_rx_work.end:
