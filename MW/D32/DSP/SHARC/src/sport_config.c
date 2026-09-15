/*======================================================================
 * sport_config.c — half-SPORT multichannel configuration from the
 * generated lane tables (TODO(dsp4-plumbing) slice 2)
 *
 * Consumes the per-lane config tables emitted into chipN/block_io.asm
 * by tools/dsp/dsp_codegen.py: entries of 4 words {sport, cs_mask,
 * words_per_sample, region_off} plus per-region scalars (count, dir,
 * mcpde, wsize). Registers written per MW/D32/DSP/dsp4-plumbing.md:
 *
 *   CTL:  SLEN=31, external clock/FS (ICLK=0, IFS=0), FSR=1,
 *         SPTRAN=1 on TX halves. SPEN is NOT set here — slice 3
 *         enables each half after its DMA ring is armed.
 *   MCTL: MCE=1, WOFFSET=0, WSIZE per region, MCPDE per region,
 *         MFD PER LANE from the generated <region>_mfd[] table.
 *   CS0:  generated channel-select mask.
 *
 * CKRE=1 is LOCKED via the slot-map timing conventions
 * (shared/dsp4-logic: sample on rising, launch on falling) — the LOGIC
 * RTL derives from the same source.
 *
 * MFD IS NOT LOCKED AND IS NOT UNIFORM (S42-1). It was 1 on every half,
 * and on the converter halves that was one bit clock early: the AK5558 /
 * AK4458 are strapped in the I2S variant at 8 slots of 32 bits = 256 BCK
 * per frame, i.e. AKM's TDM256 (S42-1 called it TDM128 here; the strap
 * bits it quoted were right, the decoded name was not -- corrected
 * 2026-09-15 against the netlist: U81 pin 14 TDM1 = +3V3, pin 13
 * TDM0 = GND, pin 15 DIF = +3V3. The MFD derivation is unaffected: it
 * rests on the I2S variant and on where LOGIC puts FS, not on the name).
 * The I2S variant puts one BCK between the frame edge
 * and the MSB, on top of the one BCK LOGIC already leaves by asserting FS
 * in the period before slot 0. So a converter half needs MFD = 2, while
 * the two halves the CPLD's own re-framer serves (the Pi PCM lane in and
 * the Pi return lane out) are built for MFD = 1 and stay there. The
 * measured consequence of getting it wrong is S39-4: every received word
 * arrived as (sample >>> 1), sign bit never set, on all twelve chip-1
 * lanes. The value per lane is decided in tools/dsp/dsp_codegen.py and
 * arrives here as data; nothing is chosen in this file.
 *
 * Infrastructure (hand-maintained). Compiled per chip with -DCHIP_ID.
 *======================================================================*/

#include <stdint.h>
#include <def21564.h>

#define SPORT_MMR_BASE   0x31002000u
#define SPORT_STRIDE     0x100u      /* SPORT block n -> n+1 */
#define HALF_B_OFFSET    0x80u       /* half A -> half B */
#define OFF_CTL          0x00u
#define OFF_MCTL         0x08u
#define OFF_CS0          0x0Cu

#define REG32(addr) (*(volatile uint32_t *)(addr))

/* Generated lane tables (chipN/lane_config.c) */
#if CHIP_ID == 1
extern const int c1_rx_lanes[];
extern const int c1_rx_lanes_count, c1_rx_lanes_dir, c1_rx_lanes_mcpde,
                 c1_rx_lanes_wsize;
extern const int c1_rx_lanes_mfd[];
extern const int c1_ic_lanes[];
extern const int c1_ic_lanes_count, c1_ic_lanes_dir, c1_ic_lanes_mcpde,
                 c1_ic_lanes_wsize;
extern const int c1_ic_lanes_mfd[];
#elif CHIP_ID == 2
extern const int c2_ic_lanes[];
extern const int c2_ic_lanes_count, c2_ic_lanes_dir, c2_ic_lanes_mcpde,
                 c2_ic_lanes_wsize;
extern const int c2_ic_lanes_mfd[];
extern const int c2_tx_lanes[];
extern const int c2_tx_lanes_count, c2_tx_lanes_dir, c2_tx_lanes_mcpde,
                 c2_tx_lanes_wsize;
extern const int c2_tx_lanes_mfd[];
#else
#error "CHIP_ID must be defined as 1 or 2"
#endif

static void cfg_region(const int *lanes, int count, int dir, int mcpde,
                       int wsize, const int *mfd)
{
    int i;
    for (i = 0; i < count; i++) {
        int sport = lanes[4 * i + 0];
        uint32_t cs = (uint32_t)lanes[4 * i + 1];
        uint32_t base = SPORT_MMR_BASE + (uint32_t)sport * SPORT_STRIDE
                        + (dir ? HALF_B_OFFSET : 0u);

        uint32_t ctl = ((uint32_t)31 << BITP_SPORT_CTL_A_SLEN)
                       | BITM_SPORT_CTL_A_FSR
                       | BITM_SPORT_CTL_A_CKRE;
        if (dir) {
            ctl |= BITM_SPORT_CTL_A_SPTRAN;
        }
        /* ICLK=0, IFS=0 (slave). CKRE=1 LOCKED (slot-map timing
         * convention: sample on rising, SPORT drives on falling —
         * matches the LOGIC RTL and the AKM converters). SPEN
         * deferred until the DMA rings are armed. */
        REG32(base + OFF_CTL) = ctl;

        REG32(base + OFF_MCTL) =
            BITM_SPORT_MCTL_A_MCE
            | ((uint32_t)mfd[i] << BITP_SPORT_MCTL_A_MFD)  /* per lane */
            | ((uint32_t)wsize << BITP_SPORT_MCTL_A_WSIZE)
            | (mcpde ? BITM_SPORT_MCTL_A_MCPDE : 0u);

        REG32(base + OFF_CS0) = cs;
    }
}

#pragma linkage_name _sport_cfg_init
void sport_cfg_init(void);

void sport_cfg_init(void)
{
#if CHIP_ID == 1
    cfg_region(c1_rx_lanes, c1_rx_lanes_count, c1_rx_lanes_dir,
               c1_rx_lanes_mcpde, c1_rx_lanes_wsize, c1_rx_lanes_mfd);
    cfg_region(c1_ic_lanes, c1_ic_lanes_count, c1_ic_lanes_dir,
               c1_ic_lanes_mcpde, c1_ic_lanes_wsize, c1_ic_lanes_mfd);
#elif CHIP_ID == 2
    cfg_region(c2_ic_lanes, c2_ic_lanes_count, c2_ic_lanes_dir,
               c2_ic_lanes_mcpde, c2_ic_lanes_wsize, c2_ic_lanes_mfd);
    cfg_region(c2_tx_lanes, c2_tx_lanes_count, c2_tx_lanes_dir,
               c2_tx_lanes_mcpde, c2_tx_lanes_wsize, c2_tx_lanes_mfd);
#endif
}
