/*======================================================================
 * spi_handler.asm — SPI parameter receive handler for ADSP-21564 (D32)
 *
 * Chip 2 receives SPI traffic from the Pi/CM4 host on SPI2 (CS2).
 * Protocol: 32-bit address + 32-bit coefficient word per write.
 *
 * Address space: 0x0000–0x0FFF → Chip 2 parameter RAM only.
 * The host selects this chip by asserting CS2; Chip 1 uses CS1 independently.
 *
 * For each write, the handler:
 *   1. Reads the address and data from the SPI receive FIFO.
 *   2. Resolves ramp profile from flags bits 11:8.
 *   3. Writes via _ramp_set_target or directly for Instant parameters.
 *
 * This handler runs as SPI2 RX interrupt on Chip 2 only.
 *
 * SPI protocol format (MSB first):
 *   Word 0:  [31:16] = address[15:0]
 *            [15:0]  = flags (bits 11:8 = ramp_profile_id)
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

/* ---- ADSP-21564 SPI register addresses (from HRM) ---- */
/* Real ADSP-2156x SPI2 MMR addresses (sys/ADSP-21564.h) */
#define SPI2_RFIFO   0x31030050   /* SPI2 receive FIFO */
#define SPI2_TFIFO   0x31030058   /* SPI2 transmit FIFO */
#define SPI2_STAT    0x31030040   /* SPI2 status */
#define SPI2_CTL     0x31030004   /* SPI2 control */

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

/* Chip 2 SPI dispatch table (in dsp_params.asm) — maps SPI address → DM target */
.extern _spi_dispatch_c2;
.extern _spi_dispatch_c2_size;   /* bounds for dispatch (generated) */

/* SPI stats (debug) */
.var _spi_rx_count = 0;
.var _spi_err_count = 0;


.extern _product_config_write;

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _spi2_rx_work — SPI2 receive handler
 *
 * Called from _sec_isr (SEC source INTR_SPI1_STAT) with secondary
 * r0-r7 + DAG1 low active. Reads one {address, value} pair from the
 * RX FIFO.
 *----------------------------------------------------------------------*/
.global _spi2_rx_work;
_spi2_rx_work:
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

    /* ---- Chip 2: local parameter write ---- */

    /* Extract ramp profile ID (bits 11:8) */
    r3 = r0;
    r3 = lshift r3 by -RAMP_PROFILE_SHIFT;
    r4 = RAMP_PROFILE_MASK;
    r3 = r3 AND r4;

    /* Product-config register block at 0xF000+ (product_config.asm) */
    r4 = 0xF000;
    comp(r2, r4);
    if ge jump (pc, .spi_config);

    /* Bounds check address against dispatch table size (generated) */
    r4 = dm(_spi_dispatch_c2_size);
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
    i0 = _spi_dispatch_c2;
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
    i0 = _spi_dispatch_c2;
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

.spi_error:
    r2 = dm(_spi_err_count);
    r5 = 1;
    r2 = r2 + r5;
    dm(_spi_err_count) = r2;

.spi_done:
    rts;

.spi_read:
    /* READ request: look up DM value at address in r2, write to TFIFO */
    r4 = dm(_spi_dispatch_c2_size);
    comp(r2, r4);
    if ge jump (pc, .spi_read_zero);     /* out-of-range → return 0 */
    i0 = _spi_dispatch_c2;
    m0 = r2;
    modify(i0, m0);
    r4 = dm(i0, 0);                      /* DM address of target variable */
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .spi_read_zero);     /* unmapped → return 0 */
    i1 = r4;
    r4 = dm(i1, 0);                      /* read value from DM */
    jump (pc, .spi_read_respond);
.spi_read_zero:
    r4 = 0;
.spi_read_respond:
    dm(SPI2_TFIFO) = r4;                 /* preload TX FIFO for master readback */
    jump (pc, .spi_done);
_spi2_rx_work.end:
