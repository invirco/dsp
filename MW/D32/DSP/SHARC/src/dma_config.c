/*======================================================================
 * dma_config.c — DDE descriptor rings, SEC, SPI2 slave and SPORT
 * enable (TODO(dsp4-plumbing) slice 3)
 *
 * Per MW/D32/DSP/dsp4-plumbing.md:
 *  - Each active lane (half-SPORT) is a DMA channel (dir 0 = half A,
 *    1 = half B). The channel numbering skips MDMA0 at SPORT4, so the
 *    base comes from sport_dma_base() below, NOT from 2*sport + dir --
 *    see the comment there (HRM Table 27-2 / Table 23-6).
 *  - Ping-pong via 2-descriptor list rings (FLOW=DSCL, FETCH05:
 *    {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD}); XMOD = 4 bytes.
 *  - The block clock is SPORT0_A_DMA (SEC source 37) on both chips
 *    (chip 1: ADC lane 0; chip 2: mix-fabric lane 0). Its descriptors
 *    carry XCNT_INT so one interrupt fires per buffer half.
 *  - SEC routes source 37 + SPI2 status (source 71) to the core SECI
 *    vector; _sec_isr (sport_init.asm) demuxes via SEC_CSID and acks
 *    via SEC_END.
 *  - After all rings are armed, SPEN(PRI) is set on every configured
 *    half-SPORT, and the asm side receives the ping/pong buffer
 *    addresses via _set_rx_bufs/_set_tx_bufs (which convert the byte
 *    addresses to the core word view, L1 NW = BW/4).
 *
 * SPI2 runtime param link (D1: Pi masters; CS1->chip1 / CS2->chip2):
 * slave, 32-bit, mode 0; RX watermark interrupt + SPI_RDY flow control.
 * SPI2 (not SPI1) is what the rev-C card wires to the host, and it is
 * also the BMODE=0b010 slave-boot port — boot and runtime share it
 * until D8's rev-D SPI0/SPI1 remap. PROVISIONAL until exercised against
 * the Pi (watermark choice, RDY timing).
 *
 * Infrastructure (hand-maintained). Compiled per chip with -DCHIP_ID.
 *======================================================================*/

#include <stdint.h>
#include <def21564.h>

/* L1 core byte-view -> system view for the DDE (ADI libcc math inlined —
 * this bare-metal build links no runtime lib). 2156x: single MP port,
 * L1 byte space 0x00240000+, system alias = +0x28000000. */
static inline uint32_t l1_to_sys(uint32_t a)
{
    return (a >= 0x00240000u && a <= 0x003FFFFFu) ? (a + 0x28000000u) : a;
}

/*----------------------------------------------------------------------
 * P2.2 bisect scaffolding — TEMPORARY (tasks.md NOW item 3 deletes all of
 * it, plus diag_stage_set and _diag_stage_set in diag.asm, once the wedge
 * is understood). Select with `DSP4_BISECT=n ./build.sh`:
 *
 *   0  production path — no park, no stage stamps. What ships.
 *   1  round 1 (2026-08-19, currently running on chip1): park straight
 *      after arm_region(A). Steady 1 Hz square on LD2 = A survived;
 *      slow single blink = still dying inside A.
 *   2  variant B: park moved after arm_region(B) — the round-1 follow-up
 *      when LD2 reads steady, i.e. A is clean and B is the next suspect.
 *   3  variant C: EN-write-order experiment. Same park point as round 1
 *      (after A) so LD2 answers the same question, but arm_region writes
 *      DSCPTR and CFG with DMA_CFG.EN CLEAR and then sets EN in a second
 *      write, instead of one CFG write that both configures and starts
 *      the channel. If C survives where 1 dies, the descriptor fetch is
 *      being kicked off before the descriptor pointer has landed.
 *
 * The default stays 1 (park after A) so a plain rebuild still stops at the
 * bisect point rather than running on into untested territory. NOTE: the
 * SPORT4..7 DMA base fix below means a rebuild is NOT bit-identical to the
 * image running on chip1 as of 2026-08-20 — it is the same scaffolding
 * around corrected addressing.
 *--------------------------------------------------------------------*/
#ifndef DSP4_BISECT
#define DSP4_BISECT 1
#endif
#if DSP4_BISECT < 0 || DSP4_BISECT > 3
#error "DSP4_BISECT must be 0 (production), 1 (round 1), 2 (variant B) or 3 (variant C)"
#endif

#define REG32(addr) (*(volatile uint32_t *)(addr))

/* SPORT half -> DMA channel MMR base. The SPORT DMA channels are NOT one
 * contiguous block, and the two blocks are not adjacent in the MMR map
 * (HRM Table 27-2 "ADSP-2156x DMA Channel List" + Table 23-6, confirmed
 * against sys/ADSP-21564.h):
 *
 *   SPORT0..3 -> DMA0 ..DMA7   at 0x31022000 + (2*sport + dir) * 0x80
 *   DMA8, DMA9  = MDMA0_SRC / MDMA0_DST — a different SCB node (0x310A7000)
 *   SPORT4..7 -> DMA10..DMA17  at 0x31023000 + (2*(sport-4) + dir) * 0x80
 *
 * so ch = 2*sport + dir off one base is right only for SPORT0..3. For
 * SPORT4 and up it lands on 0x31022400 and upward — unpopulated MMR
 * space just past DMA7 — and an SCB access there never completes, which
 * stalls the core on its next MMR access.
 *
 * That is the 2026-08-19/20 dma_cfg_init wedge (P2.2). Chip 1's region A
 * carries SPORT0..7, so it dies on lane index 4 (SPORT4) INSIDE
 * arm_region(A) — which is exactly where the round-1 bisect park says it
 * dies. Chip 2 reaches SPORT4 in its region B (c2_tx lane index 4).
 * DMA_OFF_DSCPTR is DMA_DSCPTR_NXT, which is what descriptor-LIST flow
 * requires be written before DMA_CFG (HRM "Startup Minimum-Enable
 * Requirements"); that part was already right. */
#define DMA_MMR_BASE_LO 0x31022000u     /* DMA0..DMA7   — SPORT0..3 */
#define DMA_MMR_BASE_HI 0x31023000u     /* DMA10..DMA17 — SPORT4..7 */
#define DMA_STRIDE      0x80u
#define DMA_OFF_DSCPTR  0x00u           /* DMA_DSCPTR_NXT */
#define DMA_OFF_CFG     0x08u

static inline uint32_t sport_dma_base(int sport, int dir)
{
    uint32_t idx = (uint32_t)(sport < 4 ? sport : sport - 4);
    uint32_t half = 2u * idx + (uint32_t)dir;
    return (sport < 4 ? DMA_MMR_BASE_LO : DMA_MMR_BASE_HI) + half * DMA_STRIDE;
}

#define SPORT_MMR_BASE  0x31002000u
#define SPORT_STRIDE    0x100u
#define HALF_B_OFFSET   0x80u

#define SEC_SCTL_BASE   0x31089800u
#define SEC_SCTL_STRIDE 0x8u

#define BLOCK_CLOCK_SRC INTR_SPORT0_A_DMA   /* 37 */
#define SPI2_STAT_SRC   INTR_SPI2_STAT      /* 71 */

/* Generated lane tables + buffers (chipN/lane_config.c) */
#if CHIP_ID == 1
extern const int c1_rx_lanes[];
extern const int c1_rx_lanes_count, c1_rx_lanes_dir;
extern unsigned int c1_rx_buf_ping[], c1_rx_buf_pong[];
extern const int c1_ic_lanes[];
extern const int c1_ic_lanes_count, c1_ic_lanes_dir;
extern unsigned int c1_ic_buf_ping[], c1_ic_buf_pong[];
#define REGION_A_LANES c1_rx_lanes
#define REGION_A_COUNT c1_rx_lanes_count
#define REGION_A_PING  c1_rx_buf_ping
#define REGION_A_PONG  c1_rx_buf_pong
#define REGION_B_LANES c1_ic_lanes
#define REGION_B_COUNT c1_ic_lanes_count
#define REGION_B_PING  c1_ic_buf_ping
#define REGION_B_PONG  c1_ic_buf_pong
#elif CHIP_ID == 2
extern const int c2_ic_lanes[];
extern const int c2_ic_lanes_count, c2_ic_lanes_dir;
extern unsigned int c2_ic_buf_ping[], c2_ic_buf_pong[];
extern const int c2_tx_lanes[];
extern const int c2_tx_lanes_count, c2_tx_lanes_dir;
extern unsigned int c2_tx_buf_ping[], c2_tx_buf_pong[];
#define REGION_A_LANES c2_ic_lanes
#define REGION_A_COUNT c2_ic_lanes_count
#define REGION_A_PING  c2_ic_buf_ping
#define REGION_A_PONG  c2_ic_buf_pong
#define REGION_B_LANES c2_tx_lanes
#define REGION_B_COUNT c2_tx_lanes_count
#define REGION_B_PING  c2_tx_buf_ping
#define REGION_B_PONG  c2_tx_buf_pong
#else
#error "CHIP_ID must be defined as 1 or 2"
#endif

/* asm-side buffer pointer setters (sport_init.asm; byte -> word) */
#pragma linkage_name _set_rx_bufs
void set_rx_bufs(unsigned int *ping, unsigned int *pong);
#pragma linkage_name _set_tx_bufs
void set_tx_bufs(unsigned int *ping, unsigned int *pong);

/* Descriptor storage: [lane][half][element]; 8 lanes covers both
 * regions on either chip (region A up to 8, region B up to 5). */
#pragma align 32
static uint32_t desc_a[8][2][5];
#pragma align 32
static uint32_t desc_b[8][2][5];

static void arm_region(const int *lanes, int count, int dir,
                       unsigned int *ping, unsigned int *pong,
                       uint32_t desc[][2][5])
{
    int i, h;
    for (i = 0; i < count; i++) {
        int sport = lanes[4 * i + 0];
        uint32_t lane_words = (uint32_t)lanes[4 * i + 2];
        uint32_t region_off = (uint32_t)lanes[4 * i + 3];
        uint32_t dma = sport_dma_base(sport, dir);

        uint32_t cfg = ENUM_DMA_CFG_DSCLIST | ENUM_DMA_CFG_FETCH05
                       | ENUM_DMA_CFG_MSIZE04 | ENUM_DMA_CFG_PSIZE04
                       | BITM_DMA_CFG_EN
                       | (dir ? 0u : BITM_DMA_CFG_WNR);
        if (sport == 0 && dir == 0) {
            cfg |= ENUM_DMA_CFG_XCNT_INT;   /* block clock lane */
        }

        for (h = 0; h < 2; h++) {
            unsigned int *buf = h ? pong : ping;
            /* 2026-08-19 hardware fix: every address the DDE dereferences
             * must be a SYSTEM address, not the core L1 byte-view — the
             * fabric has no mapping at 0x002xxxxx, and a descriptor fetch
             * from there wedges the SCB and stalls the core on its next
             * MMR access (bench: 1-flash hang inside this function). */
            desc[i][h][0] = l1_to_sys((uint32_t)&desc[i][1 - h][0]); /* ring */
            desc[i][h][1] = l1_to_sys((uint32_t)(buf + region_off));
            desc[i][h][2] = cfg;
            desc[i][h][3] = lane_words * 32u;             /* words/block */
            desc[i][h][4] = 4u;                           /* byte stride */
        }

#if DSP4_BISECT == 3
        /* Variant C: configure with the channel DISABLED, then start it.
         * The in-descriptor CFG word above keeps EN set — that copy is
         * what the DDE reloads on each fetch, and clearing it there would
         * stop the ring after one block instead of testing write order. */
        REG32(dma + DMA_OFF_CFG) = cfg & ~BITM_DMA_CFG_EN;
        REG32(dma + DMA_OFF_DSCPTR) =
            l1_to_sys((uint32_t)&desc[i][0][0]);
        REG32(dma + DMA_OFF_CFG) = cfg;   /* EN set last: starts the fetch */
#else
        REG32(dma + DMA_OFF_DSCPTR) =
            l1_to_sys((uint32_t)&desc[i][0][0]);
        REG32(dma + DMA_OFF_CFG) = cfg;   /* starts descriptor fetch */
#endif
    }
}

static void enable_region(const int *lanes, int count, int dir)
{
    int i;
    for (i = 0; i < count; i++) {
        int sport = lanes[4 * i + 0];
        uint32_t ctl = SPORT_MMR_BASE + (uint32_t)sport * SPORT_STRIDE
                       + (dir ? HALF_B_OFFSET : 0u);
        REG32(ctl) |= BITM_SPORT_CTL_A_SPENPRI;
    }
}

static void sec_route(uint32_t src)
{
    REG32(SEC_SCTL_BASE + src * SEC_SCTL_STRIDE) =
        BITM_SEC_SCTL_SEN | BITM_SEC_SCTL_IEN;
}

static void sec_init(void)
{
    REG32(REG_SEC0_GCTL) = BITM_SEC_GCTL_EN;
    REG32(REG_SEC0_CCTL0) = BITM_SEC_CCTL_EN;
    sec_route(BLOCK_CLOCK_SRC);
    sec_route(SPI2_STAT_SRC);
}

static void spi2_init(void)
{
    /* Slave (MSTR=0), 32-bit, mode 0.
     *
     * Three fixes here on 2026-08-12, all of which had to be right
     * before the link could carry a single byte on hardware:
     *
     * 1. RUWM was left at 0. SPI_RXCTL.RUWM is the watermark LEVEL, and
     *    0 does not mean "lowest" — HRM Table 15-30 lists it as
     *    "Disabled". With it disabled SPI_STAT.RUWM never asserts, so
     *    the SPI_IMSK_RUWM unmask below could never produce a SEC
     *    event: no interrupt, no parameter handler, and the DSP waits
     *    in .wait_boot forever for a config that cannot arrive. At
     *    32-bit word size SPI_RFIFO is 2 words deep (HRM 15), and one
     *    protocol transaction is exactly 2 words, so UWM_FULL fires
     *    once per complete transaction — never mid-transaction, which
     *    is what a lower threshold would do. RRWM = 0 (empty RFIFO) is
     *    the deassertion condition: the handler drains both words and
     *    the request clears itself.
     *
     * 2. EMISO was not set. Per HRM Table 15-18 it "enables master-in
     *    slave-out mode... applicable only when the SPI is a slave" —
     *    i.e. without it this part never drives MISO at all, and every
     *    readback returns whatever the bus floats to.
     *
     * 3. SPI_TXCTL was never written, so TEN=0 and the transmit side
     *    was dead even with EMISO set. TTI is deliberately NOT set: the
     *    HRM restricts it to master mode. A slave with an empty TFIFO
     *    that is clocked anyway reports SPI_STAT.TUR, which is exactly
     *    the diagnostic we want, so the underrun is left visible rather
     *    than papered over.
     *
     * SPI_RDY flow control on the RX channel (FCEN=1, FCCH=0): the pin
     * deasserts as the receive FIFO fills, stalling the host. FCPL=1
     * (active-high) is set by the BOARD, not by taste — SPI2_RDY carries
     * a 10K pulldown to GND on both DSPs (R34 on DSPA, R22 on DSPB), so
     * the line reads "not ready" while the part is held in reset. The
     * HRM's slave-boot figure documents exactly this pairing
     * (pull-up => FCPL=0, pull-down => FCPL=1). FCWM=1 = deassert at
     * 75% full, matching what the boot ROM uses; against a 2-deep FIFO
     * that is "stall once a whole transaction is waiting".
     *
     * All five of these registers are readable back over the diagnostic
     * block (DIAG_SPI_CTL / RXCTL / TXCTL / STAT), so the bench can
     * confirm the part actually took this configuration instead of
     * inferring it from source. */
    REG32(REG_SPI2_RXCTL) = BITM_SPI_RXCTL_REN | ENUM_SPI_RXCTL_UWM_FULL |
                            ENUM_SPI_RXCTL_RWM_0;
    REG32(REG_SPI2_TXCTL) = BITM_SPI_TXCTL_TEN;
    REG32(REG_SPI2_IMSK_SET) = BITM_SPI_IMSK_RUWM;
    REG32(REG_SPI2_CTL) = BITM_SPI_CTL_EN | ENUM_SPI_CTL_SIZE32 |
                          BITM_SPI_CTL_EMISO |
                          BITM_SPI_CTL_FCEN | BITM_SPI_CTL_FCPL |
                          ENUM_SPI_CTL_FIFO1;   /* FCWM: RFIFO >= 75% */
}

#pragma linkage_name _dma_cfg_init
void dma_cfg_init(void);

#if DSP4_BISECT
#pragma linkage_name _diag_stage_set
extern void diag_stage_set(int stage);  /* TEMP bisect stamps 2026-08-19 */
#define DIAG_STAGE(n) diag_stage_set(n)
#else
#define DIAG_STAGE(n) ((void)0)
#endif

void dma_cfg_init(void)
{
    DIAG_STAGE(1);
    arm_region(REGION_A_LANES, REGION_A_COUNT, 0,
               REGION_A_PING, REGION_A_PONG, desc_a);
#if DSP4_BISECT == 1 || DSP4_BISECT == 3
    DIAG_STAGE(7);      /* steady square on LD2 = arm_region(A) survived */
    for (;;) { }        /* park — the question is arm_region(A) only */
#endif
    DIAG_STAGE(2);
    arm_region(REGION_B_LANES, REGION_B_COUNT, 1,
               REGION_B_PING, REGION_B_PONG, desc_b);
#if DSP4_BISECT == 2
    DIAG_STAGE(7);      /* variant B: steady square = arm_region(B) too */
    for (;;) { }        /* park — A is already known good at this point */
#endif
    DIAG_STAGE(3);

    sec_init();
    DIAG_STAGE(4);
    spi2_init();
    DIAG_STAGE(5);

    /* Hand the asm side its buffer views (byte -> word inside) */
    set_rx_bufs(REGION_A_PING, REGION_A_PONG);
    set_tx_bufs(REGION_B_PING, REGION_B_PONG);

    /* All rings armed: enable the serial ports (clock slaves — they
     * start on the next LOGIC frame sync) */
    DIAG_STAGE(6);
    enable_region(REGION_A_LANES, REGION_A_COUNT, 0);
    enable_region(REGION_B_LANES, REGION_B_COUNT, 1);
}
