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
 *   1  round 1 (2026-08-19): park straight after arm_region(A). FIRES
 *      since 2026-08-21 (it needed the IMASK clear in _start, rung 17).
 *   2  variant B: park moved after arm_region(B) — the round-1 follow-up
 *      when 1 survives, i.e. A is clean and B is the next suspect.
 *   3  variant C: EN-write-order experiment. Same park point as round 1
 *      (after A), but arm_region writes DSCPTR and CFG with DMA_CFG.EN
 *      CLEAR and then sets EN in a second write, instead of one CFG write
 *      that both configures and starts the channel. If C survives where 1
 *      dies, the descriptor fetch is being kicked off before the
 *      descriptor pointer has landed.
 *   4  reached-at-all check: park on ENTRY to dma_cfg_init, before
 *      anything in this file touches a register. Added 2026-08-21 —
 *      the rung below round 1, because the full firmware had never been
 *      observed running at all on this card (only the standalone blink /
 *      rdyprobe images had), so "1 dies" and "the image never ran" were
 *      not yet distinguishable.
 *   5  the rung below that again: park on the FIRST instruction of
 *      _start (main.asm, via _bisect_park_asm in diag.asm). Nothing in
 *      this file participates. 5 pulses = the boot stream landed and the
 *      core is running our code; silence = it is not.
 *   6..9  parks in main.asm between 5 and 4, added 2026-08-21 once rung 5
 *      fired on chip 2 and rung 4 did not — so the firmware starts and
 *      dies somewhere in the init sequence upstream of this file. They
 *      park after the C stack prologue (6), after _diag_init (7), after
 *      _sru_init (8) and after _sport_cfg_init (9), and each pulses its
 *      own number, so one stagewatch sample names the last call that
 *      returned. Nothing in this file participates in these either.
 *   11 no park anywhere — the whole firmware runs, but diag.asm still
 *      mirrors the status LED onto PB_05. Added 2026-08-21 when the
 *      parks started firing: it is how the LIVE stage code is read over
 *      ssh, since a production (0) build drives LD3/LD2 only and needs
 *      eyes at the card. The mirror takes SPI2_RDY, so a build with it
 *      cannot also do host flow control — 11 is an instrument, not a
 *      shipping configuration.
 *   13..15 the first lane of arm_region(), split into its three steps:
 *      park before the DSCPTR write (13, 5 pulses), between DSCPTR and
 *      CFG (14, 6 pulses), and after CFG has started the descriptor
 *      fetch (15, 7 pulses). Added 2026-08-21 once the C-ABI fix let
 *      the firmware reach this file at all and rung 1 became the first
 *      park that does NOT fire.
 *   16 not a park: pulses the lane number after each lane of every
 *      arm_region() call and carries on. The last burst in the
 *      transcript is the last lane that armed, so one build names the
 *      lane instead of one build per lane.
 *   17 rung 1 with interrupts turned off BEFORE the first channel is
 *      armed rather than after the last. The control for rung 16's
 *      result.
 *   18..20 the tail of dma_cfg_init: after sec_init (18, 4 pulses),
 *      after spi2_init (19, 5) and after enable_region (20, 6 = the
 *      whole function ran). 19 and 20 take PB_05 back off SPI2 flow
 *      control, so they are diagnostics only.
 *   21 in main.asm, not this file: park at .wait_boot, so everything
 *      up to the host handshake has run. Three LONG pulses (the asm
 *      park's, not this file's short ones).
 *   22 not a park either: reads SPI2_CTL/RXCTL/TXCTL/STAT and the
 *      PORTA/PORTB FER and MUX registers straight after spi2_init() and
 *      frames them onto PB_05 in clkprobe.asm's encoding, forever.
 *      Decode with `dsp4_clkprobe.py --frame spi2`. It is how the
 *      all-zero parameter link gets split into "the writes did not
 *      take" versus "the pins are not on SPI2".
 *
 * HOW A PARK REPORTS (2026-08-21). Not via the LED state machine: that is
 * driven by _diag_timer_isr, so it answers a question about the interrupt
 * path as much as about this file, and it needs eyes on LD3/LD2. Instead
 * bisect_park() turns interrupts off and drives PB_05 (SPI2_RDY -> Pi
 * GPIO8 on chip 1 / GPIO12 on chip 2) from a plain busy loop: N pulses,
 * long gap, repeat, where N is the last completed stage stamp. So one
 * `dsp4_stagewatch.py --chip 1` sample says which park was reached, with
 * no interrupt, no SEC, no SPI and nobody at the bench:
 *
 *   1 pulse  = entered dma_cfg_init (variant 4)
 *   2 pulses = arm_region(A) returned (variants 1 and 3)
 *   3 pulses = arm_region(B) returned (variant 2)
 *   nothing  = the park was not reached
 *
 * The default is still 1, but READ WHAT THAT MEANS NOW. As of 2026-08-21
 * every rung fires on both chips: the whole init sequence runs and rung 21
 * parks at the host handshake. So a plain `./build.sh` produces an image
 * that PARKS after arm_region(A) — deliberately, because the SPI parameter
 * link downstream of dma_cfg_init has still never answered, and a build
 * that runs on into it cannot be read on this bench. Build with
 * DSP4_BISECT=0 for a production image, or 21 to prove the init sequence.
 *--------------------------------------------------------------------*/
#ifndef DSP4_BISECT
#define DSP4_BISECT 1
#endif
#if DSP4_BISECT < 0 || DSP4_BISECT > 29
#error "DSP4_BISECT must be 0 (production), 1, 2, 3 (variants), 4 (entry park), 5 (_start park), 6..10 (main.asm pre-init parks; 10 also cuts sru_config.c short at the DAI0/DAI1 boundary) 11 (no park at all, LED mirror on PB_05 only) 13..15 (inside arm_region, first lane) 16 (a mark per lane, does not stop) 17 (rung 1 with interrupts off before arming) 18..20 (after sec_init, after spi2_init, after enable_region) 21 (main.asm, at the host handshake) 22 (dump the SPI2 + pin-mux registers) 23/24/25 (main.asm: the SEC/SPI counters at the handshake; 24 masks SECI, 25 masks everything, 26 gives TMZLI an RTI-only vector, 27 polls the SPI instead of using the SEC, 29 dumps from AFTER the host handshake)"
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

#if DSP4_BISECT
static void bisect_park(int code);   /* defined below; rungs 13-15 park
                                      * from inside arm_region */
static void bisect_mark(int code);   /* same, but RETURNS — rung 16 */
#endif

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
#if DSP4_BISECT == 13
        /* Rungs 13-15 split the first lane's arming into its three
         * steps, because rung 1 (park after the whole of arm_region(A))
         * is where the firmware now stops — see tasks.md 2026-08-21.
         * 5 pulses = the descriptors are built in memory and no DMA
         * register has been touched. */
        if (i == 0) { bisect_park(5); }
#endif
        REG32(dma + DMA_OFF_DSCPTR) =
            l1_to_sys((uint32_t)&desc[i][0][0]);
#if DSP4_BISECT == 14
        /* 6 pulses = the DSCPTR write returned, so sport_dma_base()'s
         * address is a real MMR. Silence at 14 with 13 firing means it
         * is not. */
        if (i == 0) { bisect_park(6); }
#endif
        REG32(dma + DMA_OFF_CFG) = cfg;   /* starts descriptor fetch */
#if DSP4_BISECT == 15
        /* 7 pulses = the first channel was started and the core
         * survived the descriptor fetch it kicks off. */
        if (i == 0) { bisect_park(7); }
#endif
#if DSP4_BISECT == 16
        /* Rung 16 does not stop: it pulses the lane number after each
         * lane is armed and carries on, so the LAST burst in the
         * transcript names the last lane that completed. One build
         * instead of one per lane. Region A on chip 1 is 8 lanes and
         * sport_dma_base() switches to the second DMA MMR bank at
         * sport 4, which is the reason this granularity matters. */
        bisect_mark(i + 1);
#endif
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
    /* SPI2_STAT is deliberately NOT routed (2026-08-22). The parameter
     * link is polled from the main loop instead: interrupt delivery
     * could enter the handler mid-transaction, so the FIFO-full
     * condition was momentarily true while the host was still clocking
     * and the drain took one real word plus one still arriving. Polling
     * only looks between transactions. The SEC keeps the block clock,
     * which is the source that genuinely needs an interrupt.
     *   sec_route(SPI2_STAT_SRC); */
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
     * (pull-up => FCPL=0, pull-down => FCPL=1).
     *
     * NOTE (2026-08-20) — this is the RUNTIME polarity only. During SPI
     * SLAVE BOOT the polarity is the on-chip boot kernel's and is fixed
     * ACTIVE-LOW ("The boot code requires the SPIx_RDY signal function
     * as active-low", HRM ch.40 SPI Slave Boot Mode), which the board's
     * pulldown fights: the line rests ASSERTED during boot, so the
     * HRM's in-reset hold-off does not work on this card. Making it
     * work needs R34/R22 as pull-UPS, which would then also flip this
     * FCPL to 0. Until then the two phases disagree on polarity by
     * design and tools/pi/dsp4_boot.py handles boot as active-low while
     * dsp4_diag.py/dsp4_config.py stay active-high. FCWM=1 = deassert at
     * 75% full, matching what the boot ROM uses; against a 2-deep FIFO
     * that is "stall once a whole transaction is waiting".
     *
     * All five of these registers are readable back over the diagnostic
     * block (DIAG_SPI_CTL / RXCTL / TXCTL / STAT), so the bench can
     * confirm the part actually took this configuration instead of
     * inferring it from source — and DSP4_BISECT=22 reads them, and the
     * pin registers below, out over PB_05 without needing the link to
     * work at all. */
    /* ---- PIN ROUTING (2026-08-22) ----
     *
     * Configuring SPI2 does not connect it to anything. Nothing in this
     * firmware ever set PORTA_FER, PORTB_FER or either MUX, so the block
     * came up correctly configured and wired to no pads at all: a rung-22
     * dump off the running part read SPI2_CTL 0x0001A501 (EN, EMISO,
     * SIZE32, FCEN, FCPL, FCWM — exactly what the writes below ask for)
     * with PORTA_FER, PORTA_MUX, PORTB_FER and PORTB_MUX ALL ZERO. That
     * is why every host readback came back all-zero: the part was never
     * listening, and never drove MISO.
     *
     * Pin assignment from the ADSP-2156x data sheet Rev. A, Tables 10 and
     * 11 (GPIO Multiplexing) — the pin-mux table the earlier bring-up
     * notes recorded as missing:
     *
     *   PA_00  SPI2_MISO   mux function 0
     *   PA_01  SPI2_MOSI   mux function 0
     *   PA_04  SPI2_CLK    mux function 0
     *   PA_05  SPI2_SEL1   mux function 0, and SPI2_SS on the INPUT TAP —
     *          which is the one that matters here, because in slave mode
     *          "SPI_SS acts as the slave select input" (HRM ch.15). This
     *          is the host's CS1/CS2 arriving.
     *   PB_05  SPI2_RDY    mux function 1
     *
     * Port A wants function 0 on all four, so its MUX field is already
     * correct at reset and only FER is set. Port B's is not: MUX5 must be
     * 1, read-modify-written so the other port B pins keep theirs.
     *
     * The LED (PA_12) is deliberately NOT in this list — diag.asm owns it
     * as GPIO, which is mux-independent. */
    REG32(REG_PORTB_MUX) = (REG32(REG_PORTB_MUX) & ~BITM_PORT_MUX_MUX5)
                           | ((uint32_t)1u << BITP_PORT_MUX_MUX5);
    REG32(REG_PORTA_FER_SET) = (1u << 0) | (1u << 1) | (1u << 4) | (1u << 5);
    REG32(REG_PORTB_FER_SET) = (1u << 5);

    /* ---- DISABLE FIRST, to flush whatever boot left in the RFIFO ----
     *
     * The SPI target boot kernel drives this same SPI2, and it hands over
     * with the block still ENABLED. There is no RFIFO flush bit on this
     * part: "the receive FIFO is reset (cleared) when the SPI is disabled
     * after being enabled" (HRM 15, SPI_RFIFO). So unless the firmware
     * takes EN low at least once, SPI2 starts life holding whatever the
     * tail of the boot stream left in a 2-deep FIFO.
     *
     * That is what the bench saw on 2026-08-22: on a FRESH boot, before
     * the host had sent a single parameter transaction, SPI2_RDY already
     * read LOW — i.e. deasserted, "not ready" — with ROR, TUR and FCS set
     * and RUWM asserted. A full FIFO from the word go also explains the
     * handler running exactly ONCE: RUWM latches, the handler drains two
     * words, but the level never reaches the RRWM=empty deassertion
     * condition, so SPI_ILAT.RUWM never releases and the SEC never sees
     * another edge.
     *
     * Errors are cleared explicitly too (W1C) so a later ROR means a NEW
     * overrun rather than the boot residue. */
    REG32(REG_SPI2_CTL) = 0u;                    /* EN low: resets RFIFO */
    REG32(REG_SPI2_STAT) = BITM_SPI_STAT_ROR | BITM_SPI_STAT_TUR;
    REG32(REG_SPI2_ILAT_CLR) = BITM_SPI_ILAT_RUWM;

    REG32(REG_SPI2_RXCTL) = BITM_SPI_RXCTL_REN | ENUM_SPI_RXCTL_UWM_FULL |
                            ENUM_SPI_RXCTL_RWM_0;
    REG32(REG_SPI2_TXCTL) = BITM_SPI_TXCTL_TEN;
    REG32(REG_SPI2_IMSK_SET) = BITM_SPI_IMSK_RUWM;
    REG32(REG_SPI2_CTL) = BITM_SPI_CTL_EN | ENUM_SPI_CTL_SIZE32 |
                          BITM_SPI_CTL_EMISO |
                          BITM_SPI_CTL_FCEN | BITM_SPI_CTL_FCPL |
                          ENUM_SPI_CTL_FIFO1;   /* FCWM: RFIFO >= 75% */

    /* The transmit path is PROVEN (2026-08-22): priming SPI_TFIFO with a
     * sentinel made MISO return that sentinel instead of the constant
     * 0x697EBB71, which identified the old constant as nothing more than
     * an unloaded shift register. The priming is removed again because it
     * puts every read response one transaction out of step. */
}

#pragma linkage_name _dma_cfg_init
void dma_cfg_init(void);

#if DSP4_BISECT
#pragma linkage_name _diag_stage_set
extern void diag_stage_set(int stage);  /* TEMP bisect stamps 2026-08-19 */
#define DIAG_STAGE(n) diag_stage_set(n)

#pragma linkage_name _diag_irq_off
extern void diag_irq_off(void);         /* TEMP bisect helper 2026-08-21 */

/* PB_05 = SPI2_RDY -> card edge CS3/CS4 -> Pi GPIO8 / GPIO12. Same pin,
 * same push-pull-over-the-10K-pulldown reasoning as src/blink/rdyprobe.asm.
 * Safe here because every park is upstream of spi2_init(), so the SPI2
 * flow-control function of the pin is never configured in a park build. */
#define PORTB_FER_CLR   0x31004088u
#define PORTB_INEN_CLR  0x310040ACu
#define PORTB_DATA_SET  0x31004090u
#define PORTB_DATA_CLR  0x31004094u
#define PORTB_DIR_SET   0x3100409Cu
#define RDY_PIN_BIT     (1u << 5)

/* Busy-loop delays. CCLK on this card is 491.52 MHz, MEASURED off the
 * core timer 2026-08-21 (src/blink/clkprobe.asm) and confirmed against
 * the CGU registers read out of the running part — not the 400 MHz this
 * firmware's constants assume, and NOT the ~190 MHz an earlier estimate
 * inferred from the blink rate. That estimate divided by an assumed 5
 * cycles per delay-loop iteration; the real figure is 13, which is the
 * whole of the discrepancy. These counts land near 40 ms / 320 ms at
 * 491.52 MHz, and the decoder in tools/pi/dsp4_stagewatch.py works on
 * ratios rather than absolute times. */
#define PARK_PULSE_ITERS   1500000u
#define PARK_GAP_ITERS    12000000u

static void park_delay(unsigned int iters)
{
    volatile unsigned int i;
    for (i = 0; i < iters; i++) { }
}

/* The pulse engine shared by bisect_park() and bisect_mark(). Emits
 * `code` pulses on PB_05 followed by a long gap; interrupts are already
 * off by the time it is called. */
static void bisect_pulses(int code)
{
    int n;

    for (n = 0; n < code; n++) {
        REG32(PORTB_DATA_SET) = RDY_PIN_BIT;
        park_delay(PARK_PULSE_ITERS);
        REG32(PORTB_DATA_CLR) = RDY_PIN_BIT;
        park_delay(PARK_PULSE_ITERS);
    }
    park_delay(PARK_GAP_ITERS);
}

/* Take the pin, once. Idempotent, so a mark can call it every lane. */
static void bisect_take_pin(void)
{
    diag_irq_off();
    REG32(PORTB_FER_CLR)  = RDY_PIN_BIT;    /* GPIO, not SPI2 */
    REG32(PORTB_INEN_CLR) = RDY_PIN_BIT;
    REG32(PORTB_DATA_CLR) = RDY_PIN_BIT;    /* low before driving */
    REG32(PORTB_DIR_SET)  = RDY_PIN_BIT;
}

/* One burst, then carry on. */
static void bisect_mark(int code)
{
    bisect_take_pin();
    bisect_pulses(code);
}

/*----------------------------------------------------------------------
 * bisect_dump_word — put a 32-bit register value on PB_05.
 *
 * Same pulse-width framing as src/blink/clkprobe.asm, so
 * tools/pi/dsp4_clkprobe.py decodes it unchanged: 8 units high / 4 low
 * as a header, then 32 bits MSB first, a bit being 1 unit high (0) or 3
 * units high (1) each followed by 1 unit low, then 6 units low.
 *
 * clkprobe times its units off the core timer because it is measuring
 * the clock. Here the clock is known and only the RATIOS matter — the
 * host derives the unit from the shortest run — so this uses the same
 * busy loop as the parks and needs no timer, which matters because
 * bisect_take_pin() has just shut the timer off.
 *--------------------------------------------------------------------*/
#define DUMP_UNIT_ITERS  (PARK_PULSE_ITERS / 4)

static void bisect_dump_word(uint32_t v)
{
    int b;

    REG32(PORTB_DATA_SET) = RDY_PIN_BIT;
    park_delay(8u * DUMP_UNIT_ITERS);
    REG32(PORTB_DATA_CLR) = RDY_PIN_BIT;
    park_delay(4u * DUMP_UNIT_ITERS);

    for (b = 0; b < 32; b++) {
        REG32(PORTB_DATA_SET) = RDY_PIN_BIT;
        park_delay((v & 0x80000000u) ? (3u * DUMP_UNIT_ITERS)
                                     : DUMP_UNIT_ITERS);
        REG32(PORTB_DATA_CLR) = RDY_PIN_BIT;
        park_delay(DUMP_UNIT_ITERS);
        v <<= 1;
    }
    park_delay(6u * DUMP_UNIT_ITERS);
}

static void bisect_park(int code)
{

    /* Own the pin outright: with interrupts left on, _diag_timer_isr's
     * LED mirror drives PB_05 too and the two patterns interleave. */
    bisect_take_pin();

    for (;;) {
        bisect_pulses(code);
    }
}
#else
#define DIAG_STAGE(n) ((void)0)
#endif

void dma_cfg_init(void)
{
#if DSP4_BISECT == 17
    /* Rung 17 is rung 1 with ONE variable changed: interrupts are shut
     * off (and the pin taken) BEFORE any channel is armed, instead of
     * inside the park afterwards. Rung 16 shows every lane of both
     * regions arming and arm_region() returning, yet rung 1's park two
     * statements later is silent — and the only difference between the
     * two paths is whether the core timer was still firing while the
     * channels came up. This build says which. */
    bisect_take_pin();
#endif
    DIAG_STAGE(1);
#if DSP4_BISECT == 4
    bisect_park(1);     /* 1 pulse = the image runs and got this far */
#endif
    arm_region(REGION_A_LANES, REGION_A_COUNT, 0,
               REGION_A_PING, REGION_A_PONG, desc_a);
    DIAG_STAGE(2);
#if DSP4_BISECT == 1 || DSP4_BISECT == 3 || DSP4_BISECT == 17
    bisect_park(2);     /* 2 pulses = arm_region(A) returned */
#endif
    arm_region(REGION_B_LANES, REGION_B_COUNT, 1,
               REGION_B_PING, REGION_B_PONG, desc_b);
    DIAG_STAGE(3);
#if DSP4_BISECT == 2
    bisect_park(3);     /* 3 pulses = arm_region(B) returned too */
#endif

    sec_init();
    DIAG_STAGE(4);
#if DSP4_BISECT == 18
    bisect_park(4);     /* 4 pulses = sec_init() returned */
#endif
    spi2_init();
    DIAG_STAGE(5);
#if DSP4_BISECT == 19
    /* 5 pulses = spi2_init() returned. This park re-takes PB_05 from
     * the SPI2 flow-control function spi2_init() just gave it, which is
     * fine for a diagnostic build and is why 19 and 20 must never ship. */
    bisect_park(5);
#endif
#if DSP4_BISECT == 22
    /* Rung 22 — the SPI2 configuration, read back off the part.
     *
     * The parameter link answers all-zero (tasks.md 2026-08-21), and
     * that has two quite different causes: spi2_init()'s writes did not
     * take, or the pins are not routed to SPI2 at all. This reads both
     * halves out over PB_05 and settles it without needing the link
     * that is broken.
     *
     * ORDER MATTERS. Every register is snapshotted BEFORE the pin is
     * taken, because taking it clears PORTB_FER — which is one of the
     * values in question. Reading it afterwards would report the
     * diagnostic's own handiwork.
     */
    {
        uint32_t snap[9];
        snap[0] = 0xA5C3F00Du;              /* proves the decoder */
        snap[1] = REG32(REG_SPI2_CTL);
        snap[2] = REG32(REG_SPI2_RXCTL);
        snap[3] = REG32(REG_SPI2_TXCTL);
        snap[4] = REG32(REG_SPI2_STAT);
        snap[5] = REG32(REG_PORTA_FER);
        snap[6] = REG32(REG_PORTA_MUX);
        snap[7] = REG32(REG_PORTB_FER);
        snap[8] = REG32(REG_PORTB_MUX);

        bisect_take_pin();
        for (;;) {
            int w;
            for (w = 0; w < 9; w++) {
                bisect_dump_word(snap[w]);
            }
            park_delay(PARK_GAP_ITERS);
        }
    }
#endif

    /* Hand the asm side its buffer views (byte -> word inside) */
    set_rx_bufs(REGION_A_PING, REGION_A_PONG);
    set_tx_bufs(REGION_B_PING, REGION_B_PONG);

    /* All rings armed: enable the serial ports (clock slaves — they
     * start on the next LOGIC frame sync) */
    DIAG_STAGE(6);
    enable_region(REGION_A_LANES, REGION_A_COUNT, 0);
    enable_region(REGION_B_LANES, REGION_B_COUNT, 1);
#if DSP4_BISECT == 20
    bisect_park(6);     /* 6 pulses = the whole of dma_cfg_init ran */
#endif
}
