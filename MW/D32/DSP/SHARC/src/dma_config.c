/*======================================================================
 * dma_config.c — DDE descriptor rings, SEC, SPI1 slave and SPORT
 * enable (TODO(dsp4-plumbing) slice 3)
 *
 * Per MW/D32/DSP/dsp4-plumbing.md:
 *  - Each active lane (half-SPORT) is a DMA channel: DMA(2*sport + dir)
 *    (dir 0 = half A, 1 = half B; HRM Table 23-6).
 *  - Ping-pong via 2-descriptor list rings (FLOW=DSCL, FETCH05:
 *    {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD}); XMOD = 4 bytes.
 *  - The block clock is SPORT0_A_DMA (SEC source 37) on both chips
 *    (chip 1: ADC lane 0; chip 2: mix-fabric lane 0). Its descriptors
 *    carry XCNT_INT so one interrupt fires per buffer half.
 *  - SEC routes source 37 + SPI1 status (source 91) to the core SECI
 *    vector; _sec_isr (sport_init.asm) demuxes via SEC_CSID and acks
 *    via SEC_END.
 *  - After all rings are armed, SPEN(PRI) is set on every configured
 *    half-SPORT, and the asm side receives the ping/pong buffer
 *    addresses via _set_rx_bufs/_set_tx_bufs (which convert the byte
 *    addresses to the core word view, L1 NW = BW/4).
 *
 * SPI1 runtime param link (D1: Pi masters; CS1->chip1 / CS2->chip2):
 * slave, 32-bit, mode 0; RX watermark interrupt. PROVISIONAL until
 * exercised against the Pi (watermark choice, SPI_RDY flow control).
 *
 * Infrastructure (hand-maintained). Compiled per chip with -DCHIP_ID.
 *======================================================================*/

#include <stdint.h>
#include <def21564.h>

#define REG32(addr) (*(volatile uint32_t *)(addr))

#define DMA_MMR_BASE    0x31022000u
#define DMA_STRIDE      0x80u
#define DMA_OFF_DSCPTR  0x00u
#define DMA_OFF_CFG     0x08u

#define SPORT_MMR_BASE  0x31002000u
#define SPORT_STRIDE    0x100u
#define HALF_B_OFFSET   0x80u

#define SEC_SCTL_BASE   0x31089800u
#define SEC_SCTL_STRIDE 0x8u

#define BLOCK_CLOCK_SRC INTR_SPORT0_A_DMA   /* 37 */
#define SPI1_STAT_SRC   INTR_SPI1_STAT      /* 91 */

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
        uint32_t ch = 2u * (uint32_t)sport + (uint32_t)dir;
        uint32_t dma = DMA_MMR_BASE + ch * DMA_STRIDE;

        uint32_t cfg = ENUM_DMA_CFG_DSCLIST | ENUM_DMA_CFG_FETCH05
                       | ENUM_DMA_CFG_MSIZE04 | ENUM_DMA_CFG_PSIZE04
                       | BITM_DMA_CFG_EN
                       | (dir ? 0u : BITM_DMA_CFG_WNR);
        if (sport == 0 && dir == 0) {
            cfg |= ENUM_DMA_CFG_XCNT_INT;   /* block clock lane */
        }

        for (h = 0; h < 2; h++) {
            unsigned int *buf = h ? pong : ping;
            desc[i][h][0] = (uint32_t)&desc[i][1 - h][0]; /* ring */
            desc[i][h][1] = (uint32_t)(buf + region_off);
            desc[i][h][2] = cfg;
            desc[i][h][3] = lane_words * 32u;             /* words/block */
            desc[i][h][4] = 4u;                           /* byte stride */
        }

        REG32(dma + DMA_OFF_DSCPTR) = (uint32_t)&desc[i][0][0];
        REG32(dma + DMA_OFF_CFG) = cfg;   /* starts descriptor fetch */
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
    sec_route(SPI1_STAT_SRC);
}

static void spi1_init(void)
{
    /* Slave (MSTR=0), 32-bit, mode 0. PROVISIONAL: RX urgent-watermark
     * interrupt at the lowest threshold; revisit with the Pi link
     * (flow control via SPI_RDY not yet configured). */
    REG32(REG_SPI1_RXCTL) = BITM_SPI_RXCTL_REN;
    REG32(REG_SPI1_IMSK_SET) = BITM_SPI_IMSK_RUWM;
    REG32(REG_SPI1_CTL) = BITM_SPI_CTL_EN | ENUM_SPI_CTL_SIZE32;
}

#pragma linkage_name _dma_cfg_init
void dma_cfg_init(void);

void dma_cfg_init(void)
{
    arm_region(REGION_A_LANES, REGION_A_COUNT, 0,
               REGION_A_PING, REGION_A_PONG, desc_a);
    arm_region(REGION_B_LANES, REGION_B_COUNT, 1,
               REGION_B_PING, REGION_B_PONG, desc_b);

    sec_init();
    spi1_init();

    /* Hand the asm side its buffer views (byte -> word inside) */
    set_rx_bufs(REGION_A_PING, REGION_A_PONG);
    set_tx_bufs(REGION_B_PING, REGION_B_PONG);

    /* All rings armed: enable the serial ports (clock slaves — they
     * start on the next LOGIC frame sync) */
    enable_region(REGION_A_LANES, REGION_A_COUNT, 0);
    enable_region(REGION_B_LANES, REGION_B_COUNT, 1);
}
