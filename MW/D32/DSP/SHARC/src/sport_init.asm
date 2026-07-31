/*======================================================================
 * sport_init.asm — SPORT/TDM and interrupt configuration for ADSP-21564
 *
 * Shared by both Chip 1 and Chip 2. Chip-specific differences are
 * handled by the CHAN_MASK config word at boot time.
 *
 * SPORT layout (slot map SOT: shared/dsp4-logic/, decision D2;
 * sport_id = DAI port index, I=RX / O=TX, LOGIC drives all BCK/FS —
 * every SPORT is a clock slave):
 *
 *   Chip 1 (DSPA / U6):
 *     SPORT0..3 RX — ADC/NET TDM8 inputs (A_I0..A_I3, 32 ch)
 *     SPORT4 RX    — codec return  (A_I4: CODEC_RET, slots 0-3)
 *     SPORT5 RX    — D32 snake     (A_I5: SNAKE_RET, slots 0-7)
 *     SPORT6 RX    — Pi PCM        (A_I6: PI_PCM, slots 0-1)
 *     SPORT7 RX    — MEMS talkback (A_I7: MEMS_TB, slot 5)
 *     SPORT0..7 TX — mix fabric MIX_0..MIX_7 (8× TDM16 = 128 slots;
 *                    37 active: buses 0-24 + superset XFER 25-36, packed)
 *
 *   Chip 2 (DSPB / U5):
 *     SPORT0..7 RX — mix fabric MIX_0..MIX_7 (as above)
 *     SPORT0..1 TX — DAC 1-16 (B_O0 -> DA0, B_O1 -> DA3)
 *     SPORT2 TX    — codec out (D24) / snake out (D32) (B_O2)
 *     SPORT3 TX    — DAC MAIN (B_O3, provisional)
 *     SPORT4..7 TX — NET 1-32 (B_O4..B_O7)
 *
 * Configuration:
 *   - TDM8 framing 12.288 MHz BCK / TDM16 framing 24.576 MHz BCK,
 *     48 kHz FS, all clocks LOGIC-generated
 *   - DMA: chained ping-pong buffers, 32-sample blocks; RX/IC packed by
 *     channel-select masks, TX frame-indexed (see block_io.asm tables)
 *   - Interrupt: SPORT DMA completion triggers audio block processing
 *
 * TODO(dsp4-plumbing): the register-level configuration below still
 * implements the SUPERSEDED single-SPORT7 inter-chip model (chip 1 as
 * IC clock master, TDM-32). Rework register configs + DMA channel map
 * to the layout above against ADSP-2156x HRM before hardware bring-up.
 * Geometry constants and buffers are already updated.
 *
 * Infrastructure (hand-maintained; header layout mirrors the slot map).
 *======================================================================*/

/* ---- ADSP-21564 System Register addresses (abbreviated) ---- */
/* Full definitions would come from <defSHARC21564.h> or CCES headers */

#define SPORTx_CTL_A(n)   (0x08001000 + (n)*0x100)    /* SPORT n Control Reg A */
#define SPORTx_CTL_B(n)   (0x08001000 + (n)*0x100+4)  /* SPORT n Control Reg B */
#define SPORTx_MCTL(n)    (0x08001000 + (n)*0x100+8)  /* SPORT n Multichannel */
#define SPORTx_CS0(n)     (0x08001000 + (n)*0x100+0x40) /* TDM Channel Select 0 */
#define SPORTx_CS1(n)     (0x08001000 + (n)*0x100+0x44)
#define SPORTx_CS2(n)     (0x08001000 + (n)*0x100+0x48)
#define SPORTx_CS3(n)     (0x08001000 + (n)*0x100+0x4C)

#define DMAx_CFG(ch)      (0x08002000 + (ch)*0x40)    /* DMA channel config */
#define DMAx_ADDRSTART(ch)(0x08002000 + (ch)*0x40+4)
#define DMAx_COUNT(ch)    (0x08002000 + (ch)*0x40+8)
#define DMAx_MODIFY(ch)   (0x08002000 + (ch)*0x40+12)

#define SPI1_CTL          0x08000A04
#define SPI1_CLK          0x08000A08
#define SPI1_TCTL         0x08000A14
#define SPI1_RCTL         0x08000A18

#define IMASK              0x08004000    /* Interrupt mask register */
#define PICR0              0x08004010    /* Programmable interrupt controller */

/* ---- Audio block parameters ---- */
#define BLOCK_SIZE         32
#define NUM_CHANNELS       32      /* console channel strips */
#define SAMPLE_RATE        48000
#define TDM_SLOTS          32
#define TDM_WORD_BITS      32

/* ---- DMA ping-pong buffer sizes ----
 * RX (chip 1): 46 packed channels (32 ADC/NET + 3 codec + 2 Pi + 1 MEMS
 *   + 8 snake); TX (chip 2): frame-indexed, 8 sports × 8 slots = 64.
 * Both sized at full-frame capacity (64 slots) so patch changes never
 * outgrow them. Must cover block_io.asm rx_stride/tx_stride.
 */
#define FRAME_SLOTS      64
#define DMA_BUF_WORDS    (BLOCK_SIZE * FRAME_SLOTS)    /* 32×64 = 2048 words */


/* DMA ping-pong buffers: placed in seg_dma (32-word aligned per LDF) */
/* Inter-chip mix fabric: 37 active global slots (buses 0-24 + superset
 * XFER 25-36) packed contiguously; capacity is 128 (8× TDM16) — grow
 * IC_CHANNELS with the slot map. Must equal block_io.asm ic_stride. */
#define IC_CHANNELS  37
#define IC_BUF_WORDS (BLOCK_SIZE * IC_CHANNELS)

.section/dm seg_dma;

.var _dma_rx_ping[DMA_BUF_WORDS];
.var _dma_rx_pong[DMA_BUF_WORDS];
.var _dma_tx_ping[DMA_BUF_WORDS];
.var _dma_tx_pong[DMA_BUF_WORDS];

/* Inter-chip transport buffers (SPORT7) */
/* 128 channels (8 lanes × 16 ch/lane, per schematic) × 32 samples */
.var _dma_ic_rx_ping[IC_BUF_WORDS];
.var _dma_ic_rx_pong[IC_BUF_WORDS];
.var _dma_ic_tx_ping[IC_BUF_WORDS];
.var _dma_ic_tx_pong[IC_BUF_WORDS];

/* Current buffer pointers and control variables in normal DM data */
.section/dm seg_dmda;

/* Current buffer pointers (toggled by DMA ISR) */
.global _rx_active_buf;
.var _rx_active_buf;       /* points to ping or pong */
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
 * _sport_init — Configure all SPORTs, DMA, SPI, and interrupts
 *
 * Called once at startup after boot config is received.
 * Chip identity (1 or 2) is determined by hardware (board strapping)
 * and stored in _chip_id.
 *----------------------------------------------------------------------*/
.global _sport_init;
_sport_init:

    /* ---- SPORT0..3: ADC input (Chip 1) / DAC output (Chip 2) ---- */
    /*
     * TDM-8 configuration per SPORT (4 SPORTs × 8 ch = 32 total):
     *   - 8 slots per SPORT, 32-bit words
     *   - External frame sync (from CPLD), MSB first
     *   - Clock from CPLD MCLK / divider
     *
     * ADSP-21564 SPORT CTL_A register bit fields:
     *   [0]     SPEN    = 1 (enable)
     *   [3:2]   DTYPE   = 00 (right-justify, zero-fill)
     *   [8:4]   SLEN    = 11111 (31 → 32-bit word)
     *   [9]     ICLK    = 0 (external clock)
     *   [10]    IFS     = 0 (external frame sync)
     *   [14]    TDMMODE = 1
     *   [15]    TFSR    = 1 (frame sync required)
     *   [20:16] NCH     = 00111 (7 → 8 channels, 0-indexed)
     *
     * Bit pattern: 0x0007C3F1
     *   NCH=7(bits20:16) | TFSR(15) | TDMMODE(14) | SLEN=31(8:4) | SPEN(0)
     */
    #define SPORT_CTL_TDM8  0x0007C3F1

    /* Configure SPORTs 0-3 (unrolled: macros require compile-time constants) */
    /* SPORT0 */
    r1 = SPORT_CTL_TDM8;
    dm(SPORTx_CTL_A(0)) = r1;
    r1 = 0x00000001;          /* MCE = 1 */
    dm(SPORTx_MCTL(0)) = r1;
    r1 = 0x000000FF;
    dm(SPORTx_CS0(0)) = r1;

    /* SPORT1 */
    r1 = SPORT_CTL_TDM8;
    dm(SPORTx_CTL_A(1)) = r1;
    r1 = 0x00000001;
    dm(SPORTx_MCTL(1)) = r1;
    r1 = 0x000000FF;
    dm(SPORTx_CS0(1)) = r1;

    /* SPORT2 */
    r1 = SPORT_CTL_TDM8;
    dm(SPORTx_CTL_A(2)) = r1;
    r1 = 0x00000001;
    dm(SPORTx_MCTL(2)) = r1;
    r1 = 0x000000FF;
    dm(SPORTx_CS0(2)) = r1;

    /* SPORT3 */
    r1 = SPORT_CTL_TDM8;
    dm(SPORTx_CTL_A(3)) = r1;
    r1 = 0x00000001;
    dm(SPORTx_MCTL(3)) = r1;
    r1 = 0x000000FF;
    dm(SPORTx_CS0(3)) = r1;


    /* ---- SPORT7: Inter-chip TDM-32 transport ---- */
    /*
     * Single data lane, 32 slots × 32 bits = 1024 bits/frame, 48 kHz.
     * BCLK = 48000 × 32 × 32 = 49.152 MHz (from CPLD-provided MCLK).
     * 25 active slots (0-24): MAIN_L/R, SUB, GRP×4, AUX×12, FX×6.
     *
     * Chip 1 = TX master: generates BCLK and frame sync (ICLK=1, IFS=1).
     * Chip 2 = RX slave:  accepts external BCLK and frame sync (ICLK=0, IFS=0).
     *
     * CTL_A bit fields:
     *   [0]     SPEN    = 1
     *   [8:4]   SLEN    = 11111 (31 → 32-bit word)
     *   [9]     ICLK    = 1 (master) / 0 (slave)
     *   [10]    IFS     = 1 (master) / 0 (slave)
     *   [14]    TDMMODE = 1
     *   [15]    TFSR    = 1
     *   [20:16] NCH     = 11111 (31 → 32 slots)
     */
#if CHIP_ID == 1
    /* Chip 1 TX master: 0x001FC7F1 */
    r1 = 0x001FC7F1;
#elif CHIP_ID == 2
    /* Chip 2 RX slave:  0x001FC1F1 */
    r1 = 0x001FC1F1;
#endif
    dm(SPORTx_CTL_A(7)) = r1;
    r1 = 0x00000001;              /* MCE = 1 */
    dm(SPORTx_MCTL(7)) = r1;
    r1 = 0x01FFFFFF;              /* Slots 0-24 active (25 slots) */
    dm(SPORTx_CS0(7)) = r1;


    /* ---- DMA: Ping-pong chained buffers ---- */
    /*
     * DMA channel assignment:
     *   DMA0  = SPORT0 RX/TX  (8 ch × 32 samples)
     *   DMA1  = SPORT1 RX/TX
     *   DMA2  = SPORT2 RX/TX
     *   DMA3  = SPORT3 RX/TX
     *   DMA8  = SPORT7 TX (Chip 1) / RX (Chip 2) — inter-chip
     *
     * All use chained ping-pong: DMA auto-switches between ping and pong
     * buffers. The completion interrupt fires after each half.
     *
     * ADC/DAC DMA: 4 SPORTs share one contiguous RX buffer (32 ch stride).
     * Each SPORT writes 8 channels into its portion:
     *   SPORT0 → offset 0, SPORT1 → offset 8, etc.
     *   Total: 32 ch × 32 samples = 1024 words per ping/pong half.
     */

    /* DMA0 — SPORT0 (first 8 channels) — ping buffer */
    r0 = _dma_rx_ping;
    dm(DMAx_ADDRSTART(0)) = r0;
    r0 = DMA_BUF_WORDS;
    dm(DMAx_COUNT(0)) = r0;
    r0 = 1;                       /* modify = 1 (sequential words) */
    dm(DMAx_MODIFY(0)) = r0;
    r0 = 0x00010003;              /* EN | CHAINED | INT_ON_DONE */
    dm(DMAx_CFG(0)) = r0;

    /* DMA1-3: SPORT1-3 (channels 9-32), same config, offset base addresses */
    r0 = _dma_rx_ping;
    r1 = 8;                       /* 8-channel offset per SPORT */
    r0 = r0 + r1;                 /* SPORT1 base = ping + 8 */
    dm(DMAx_ADDRSTART(1)) = r0;
    r0 = DMA_BUF_WORDS;
    dm(DMAx_COUNT(1)) = r0;
    r0 = 1; dm(DMAx_MODIFY(1)) = r0;
    r0 = 0x00010003; dm(DMAx_CFG(1)) = r0;

    r0 = _dma_rx_ping;
    r1 = 16;
    r0 = r0 + r1;
    dm(DMAx_ADDRSTART(2)) = r0;
    r0 = DMA_BUF_WORDS; dm(DMAx_COUNT(2)) = r0;
    r0 = 1; dm(DMAx_MODIFY(2)) = r0;
    r0 = 0x00010003; dm(DMAx_CFG(2)) = r0;

    r0 = _dma_rx_ping;
    r1 = 24;
    r0 = r0 + r1;
    dm(DMAx_ADDRSTART(3)) = r0;
    r0 = DMA_BUF_WORDS; dm(DMAx_COUNT(3)) = r0;
    r0 = 1; dm(DMAx_MODIFY(3)) = r0;
    r0 = 0x00010003; dm(DMAx_CFG(3)) = r0;

    /* DMA8 — SPORT7 inter-chip (chip1=TX, chip2=RX) */
#if CHIP_ID == 1
    r0 = _dma_ic_tx_ping;
#elif CHIP_ID == 2
    r0 = _dma_ic_rx_ping;
#endif
    dm(DMAx_ADDRSTART(8)) = r0;
    r0 = IC_BUF_WORDS;
    dm(DMAx_COUNT(8)) = r0;
    r0 = 1; dm(DMAx_MODIFY(8)) = r0;
    r0 = 0x00010003; dm(DMAx_CFG(8)) = r0;

    /* Initialize buffer pointers */
    r0 = _dma_rx_ping;
    dm(_rx_active_buf) = r0;
    r0 = _dma_tx_ping;
    dm(_tx_active_buf) = r0;
    r0 = _dma_ic_rx_ping;
    dm(_ic_rx_active_buf) = r0;
    r0 = _dma_ic_tx_ping;
    dm(_ic_tx_active_buf) = r0;


    /* ---- SPI1: Parameter receive from Pi/CM4 host (both chips, D1) ---- */
    /* Chip 1 = CS1, Chip 2 = CS2 — independent chip selects, shared bus */
    /*
     * SPI1 slave configuration:
     *   SPIEN = 1 (enable), MSTR = 0 (slave mode)
     *   CPHA = 0, CPOL = 0 (mode 0 — sample on rising edge, idle low)
     *   SIZE = 1 (32-bit transfers)
     *   RXFLSH = 1 (flush RX FIFO on enable)
     *
     * Bit pattern: SPI1_CTL = 0x60000001  (SPIEN | 32-bit)
     * SPI1_RCTL = 0x00000001 (RFIFO interrupt on ≥1 word)
     */
    r0 = 0x60000001;              /* SPIEN, slave, 32-bit, mode 0 */
    dm(SPI1_CTL) = r0;
    r0 = 0x00000001;              /* RX FIFO threshold = 1 word */
    dm(SPI1_RCTL) = r0;


    /* ---- Interrupts ---- */
    /*
     * The interrupt vector table is statically defined in ivt.asm
     * (section seg_rth, placed at 0x000C0000 by the LDF).
     * ISR vectors: _sport_dma_isr, _spi1_rx_isr.
     *
     * Enable interrupts in IMASK:
     *   Bit 6  (0x040) — DMA0 completion (SPORT DMA, both chips)
     *   Bit 9  (0x200) — SPI1 RX         (both chips)
     *
     * NOTE: Bit positions are approximate. Validate against
     *       ADSP-21564 HRM §5 (Interrupt Controller) before production.
     */
    #define IMASK_DMA0    0x00000040
    #define IMASK_SPI1    0x00000200

    r0 = 0x00000240;              /* IMASK_DMA0 | IMASK_SPI1 = 0x040 | 0x200 */
    dm(IMASK) = r0;

    rts;
_sport_init.end:


/*----------------------------------------------------------------------
 * _sport_dma_isr — DMA completion ISR (audio block boundary)
 *
 * Toggles ping/pong buffers and sets _block_ready flag.
 * Main loop (or this ISR directly) then calls the process chain.
 *----------------------------------------------------------------------*/
.global _sport_dma_isr;
_sport_dma_isr:
    push sts;

    /* Toggle RX buffer pointer */
    r0 = dm(_rx_active_buf);
    r1 = _dma_rx_ping;
    comp(r0, r1);
    if eq jump (pc, .swap_to_pong);
    dm(_rx_active_buf) = r1;       /* was pong, switch to ping */
    jump (pc, .toggle_tx);
.swap_to_pong:
    r0 = _dma_rx_pong;
    dm(_rx_active_buf) = r0;

.toggle_tx:
    /* Toggle TX buffer pointer */
    r0 = dm(_tx_active_buf);
    r1 = _dma_tx_ping;
    comp(r0, r1);
    if eq jump (pc, .tx_pong);
    dm(_tx_active_buf) = r1;
    jump (pc, .toggle_ic);
.tx_pong:
    r0 = _dma_tx_pong;
    dm(_tx_active_buf) = r0;

.toggle_ic:
    /* Toggle inter-chip buffers similarly */
    r0 = dm(_ic_rx_active_buf);
    r1 = _dma_ic_rx_ping;
    comp(r0, r1);
    if eq jump (pc, .ic_rx_pong);
    dm(_ic_rx_active_buf) = r1;
    jump (pc, .ic_tx_tog);
.ic_rx_pong:
    r0 = _dma_ic_rx_pong;
    dm(_ic_rx_active_buf) = r0;

.ic_tx_tog:
    r0 = dm(_ic_tx_active_buf);
    r1 = _dma_ic_tx_ping;
    comp(r0, r1);
    if eq jump (pc, .ic_tx_pong);
    dm(_ic_tx_active_buf) = r1;
    jump (pc, .dma_isr_done);
.ic_tx_pong:
    r0 = _dma_ic_tx_pong;
    dm(_ic_tx_active_buf) = r0;

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
