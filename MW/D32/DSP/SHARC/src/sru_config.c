/*======================================================================
 * sru_config.c — DAI/SRU signal routing for the DSP4 card
 *
 * Implements the SRU route list from MW/D32/DSP/dsp4-plumbing.md.
 * Identical wiring on both chips (the card is symmetric); the ROLES of
 * the lanes differ per the slot map (chip 1: A halves = ADC/superset
 * RX, B halves = mix-fabric TX; chip 2: A halves = mix-fabric RX,
 * B halves = DAC/codec/NET TX).
 *
 * DAI pin map (hardware-map.md — note the DAI0/DAI1 pin-19/20 swap):
 *   DAI0: 1=I0 2=O0 3=I1 4=O1 5=I2 6=O2 7=I3 8=O3
 *         9=FS0 10=BCK0 19=BCK1 20=FS1
 *   DAI1: 1=I4 2=O4 3=I5 4=O5 5=I6 6=O6 7=I7 8=O7
 *         9=FS2 10=BCK2 19=FS3 20=BCK3
 *
 * All SPORT halves are clock/FS slaves (LOGIC generates every BCK/FS).
 * Called once from _start (main.asm) before sport_cfg_init().
 *
 * Infrastructure (hand-maintained; TODO(dsp4-plumbing) slice 2).
 *======================================================================*/

#include <sru21564.h>

#pragma linkage_name _sru_init
void sru_init(void);

void sru_init(void)
{
    /* ---- DAI pad input buffers ----
     *
     * MUST come before any routing. The SRU only connects signals that
     * are already inside the part; the DAI pads have a separate input
     * enable in the PADS block that comes out of reset at ZERO, so with
     * routing alone every DAI input is dead at the pin. That is exactly
     * what the card did: SPORT0_A correctly configured and enabled in
     * TDM8 slave mode (CTL_A 0x31F1, MCTL_A 0x715, CS0_A 0xFF, DIV_A 0),
     * its DMA channel armed and clean (DMA0_STAT 0x00006200), and not a
     * single word ever arriving, because BCK0/FS0 never got past the
     * pad. Bench 2026-08-23: both registers read 0x00000000 on a running
     * chip 1, and nothing in this firmware had ever written them.
     *
     * Bit n enables the input buffer for DAI pin n+1; 20 pins per port.
     * Enabling it on a pin the SRU drives as an output is harmless -- it
     * only powers the input path -- so all twenty go on for both ports
     * rather than tracking direction in two places. */
    *(volatile unsigned int *)0x31004460u = 0x000FFFFFu;  /* PADS0_DAI0_IE */
    *(volatile unsigned int *)0x31004464u = 0x000FFFFFu;  /* PADS0_DAI1_IE */

    /* ---- DAI0: data pins <-> SPORT0-3 ---- */
    SRU(DAI0_PB01_O, SPT0_AD0_I);     /* I0 -> SPORT0 half A */
    SRU(SPT0_BD0_O, DAI0_PB02_I);     /* SPORT0 half B -> O0 */
    SRU(DAI0_PB03_O, SPT1_AD0_I);     /* I1 */
    SRU(SPT1_BD0_O, DAI0_PB04_I);     /* O1 */
    SRU(DAI0_PB05_O, SPT2_AD0_I);     /* I2 */
    SRU(SPT2_BD0_O, DAI0_PB06_I);     /* O2 */
    SRU(DAI0_PB07_O, SPT3_AD0_I);     /* I3 */
    SRU(SPT3_BD0_O, DAI0_PB08_I);     /* O3 */

    /* ---- DAI0: clock group CG0 (BCK0/FS0) -> SPORT0-3 half A ---- */
    SRU(DAI0_PB10_O, SPT0_ACLK_I);
    SRU(DAI0_PB10_O, SPT1_ACLK_I);
    SRU(DAI0_PB10_O, SPT2_ACLK_I);
    SRU(DAI0_PB10_O, SPT3_ACLK_I);
    SRU(DAI0_PB09_O, SPT0_AFS_I);
    SRU(DAI0_PB09_O, SPT1_AFS_I);
    SRU(DAI0_PB09_O, SPT2_AFS_I);
    SRU(DAI0_PB09_O, SPT3_AFS_I);

    /* ---- DAI0: clock group CG1 (BCK1/FS1) -> SPORT0-3 half B ---- */
    SRU(DAI0_PB19_O, SPT0_BCLK_I);    /* pin 19 = BCK1 */
    SRU(DAI0_PB19_O, SPT1_BCLK_I);
    SRU(DAI0_PB19_O, SPT2_BCLK_I);
    SRU(DAI0_PB19_O, SPT3_BCLK_I);
    SRU(DAI0_PB20_O, SPT0_BFS_I);     /* pin 20 = FS1 */
    SRU(DAI0_PB20_O, SPT1_BFS_I);
    SRU(DAI0_PB20_O, SPT2_BFS_I);
    SRU(DAI0_PB20_O, SPT3_BFS_I);

    /* ---- DAI0: pin buffer direction ---- */
    SRU(LOW, DAI0_PBEN01_I);          /* inputs */
    SRU(HIGH, DAI0_PBEN02_I);         /* outputs (O0-O3) */
    SRU(LOW, DAI0_PBEN03_I);
    SRU(HIGH, DAI0_PBEN04_I);
    SRU(LOW, DAI0_PBEN05_I);
    SRU(HIGH, DAI0_PBEN06_I);
    SRU(LOW, DAI0_PBEN07_I);
    SRU(HIGH, DAI0_PBEN08_I);
    SRU(LOW, DAI0_PBEN09_I);          /* clock pins: inputs */
    SRU(LOW, DAI0_PBEN10_I);
    SRU(LOW, DAI0_PBEN19_I);
    SRU(LOW, DAI0_PBEN20_I);

#if DSP4_BISECT == 10
    /* TEMP bisect rung (2026-08-21, goes with the rest of the DSP4_BISECT
     * scaffolding): return before the DAI1 half, so main.asm's post-
     * _sru_init park fires with 10 pulses instead of 8. It splits this
     * function in two — rung 8 silent but rung 10 firing means the hang
     * is in the DAI1/SPORT4-7 writes below, not the DAI0 ones above.
     * DAI1 routing is left unconfigured, which is fine because the park
     * is the next thing that happens. */
    return;
#endif

    /* ---- DAI1: data pins <-> SPORT4-7 ---- */
    SRU2(DAI1_PB01_O, SPT4_AD0_I);    /* I4 */
    SRU2(SPT4_BD0_O, DAI1_PB02_I);    /* O4 */
    SRU2(DAI1_PB03_O, SPT5_AD0_I);    /* I5 */
    SRU2(SPT5_BD0_O, DAI1_PB04_I);    /* O5 */
    SRU2(DAI1_PB05_O, SPT6_AD0_I);    /* I6 */
    SRU2(SPT6_BD0_O, DAI1_PB06_I);    /* O6 */
    SRU2(DAI1_PB07_O, SPT7_AD0_I);    /* I7 */
    SRU2(SPT7_BD0_O, DAI1_PB08_I);    /* O7 */

    /* ---- DAI1: clock group CG2 (BCK2/FS2) -> SPORT4-7 half A ---- */
    SRU2(DAI1_PB10_O, SPT4_ACLK_I);
    SRU2(DAI1_PB10_O, SPT5_ACLK_I);
    SRU2(DAI1_PB10_O, SPT6_ACLK_I);
    SRU2(DAI1_PB10_O, SPT7_ACLK_I);
    SRU2(DAI1_PB09_O, SPT4_AFS_I);
    SRU2(DAI1_PB09_O, SPT5_AFS_I);
    SRU2(DAI1_PB09_O, SPT6_AFS_I);
    SRU2(DAI1_PB09_O, SPT7_AFS_I);

    /* ---- DAI1: clock group CG3 (BCK3/FS3) -> SPORT4-7 half B ----
     * NOTE the swap vs DAI0: pin 19 = FS3, pin 20 = BCK3. */
    SRU2(DAI1_PB20_O, SPT4_BCLK_I);   /* pin 20 = BCK3 */
    SRU2(DAI1_PB20_O, SPT5_BCLK_I);
    SRU2(DAI1_PB20_O, SPT6_BCLK_I);
    SRU2(DAI1_PB20_O, SPT7_BCLK_I);
    SRU2(DAI1_PB19_O, SPT4_BFS_I);    /* pin 19 = FS3 */
    SRU2(DAI1_PB19_O, SPT5_BFS_I);
    SRU2(DAI1_PB19_O, SPT6_BFS_I);
    SRU2(DAI1_PB19_O, SPT7_BFS_I);

    /* ---- DAI1: pin buffer direction ---- */
    SRU2(LOW, DAI1_PBEN01_I);
    SRU2(HIGH, DAI1_PBEN02_I);
    SRU2(LOW, DAI1_PBEN03_I);
    SRU2(HIGH, DAI1_PBEN04_I);
    SRU2(LOW, DAI1_PBEN05_I);
    SRU2(HIGH, DAI1_PBEN06_I);
    SRU2(LOW, DAI1_PBEN07_I);
    SRU2(HIGH, DAI1_PBEN08_I);
    SRU2(LOW, DAI1_PBEN09_I);
    SRU2(LOW, DAI1_PBEN10_I);
    SRU2(LOW, DAI1_PBEN19_I);
    SRU2(LOW, DAI1_PBEN20_I);
}
