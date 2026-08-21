/*======================================================================
 * sruprobe.asm — walk the DAI0 half of sru_init()'s SRU writes one at a
 * time, in a standalone image, and report progress on PB_05.
 *
 * WHY: the firmware hangs inside sru_init() and never returns, and the
 * DSP4_BISECT rungs could only narrow it to "somewhere in the DAI0
 * half". That function is C, so a hang there has three candidate
 * causes and the bisect cannot separate them:
 *   (a) an SRU register access that does not complete,
 *   (b) the C stack — sru_init() is the FIRST C function _start calls,
 *       so it is also the first use of the i6/i7 stack set up there,
 *   (c) the core timer ISR, which _diag_init arms just before it.
 *
 * This image removes (b) and (c) entirely: no C, no stack, no
 * interrupts. It performs the SAME writes, in the same order, using the
 * assembly form of the SRU() macro out of the same ADI header, and
 * emits one 1-tick pulse after each. So the pulse count IS the number
 * of SRU operations that completed. All 36 and the SRU register space
 * is innocent — the fault is in the C environment around it.
 *
 * Frame on PB_05 (SPI2_RDY -> Pi GPIO8 chip 1 / GPIO12 chip 2), decoded
 * by tools/pi/dsp4_clkprobe.py --rle:
 *   3 pulses, 8-tick gap   image alive, timer counting, no MMR touched
 *   36 pulses              one per completed DAI0 SRU write
 *   8-tick gap
 *   3 words                DAI0_DAT0, DAI0_CLK0, DAI0_PIN0 read back,
 *                          so the writes are seen to have landed
 *   6 square periods       then the whole thing repeats
 *
 * Timing is off the core timer exactly as in clkprobe.asm; see there.
 *
 * Infrastructure (hand-maintained). Built by build.sh's "sruprobe"
 * target into sruprobe1.ldr / sruprobe2.ldr.
 *======================================================================*/

#include <def21564.h>
#include <sru21564.h>

#define RDY_BIT       (1 << 5)
#define TICK_CYCLES   2000000
#define SQ_TICKS      32

/* One SRU operation, then a pulse. The SRU() macro's assembly form is a
 * read-modify-write through r0/r1 (sru21568.h, _SRU_ROUTE), so it and
 * the helpers below may share those registers freely. */
#define STEP(out,in)  SRU(out,in) call _pulse;

.section/pm seg_pmco;

.global _start;
_start:
    r0 = RDY_BIT;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;

    r0 = TICK_CYCLES;
    tperiod = r0;
    tcount = r0;
    bit set mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;

.frame_top:
    /* ---- alive: nothing but GPIO writes so far ---- */
    r8 = 3;
.alive_pulse:
    call _pulse;
    r8 = r8 - 1;
    if ne jump (pc, .alive_pulse);
    r1 = 8;
    call _wait_ticks;

    /* ---- the DAI0 half of sru_config.c, write for write ---- */
    STEP(DAI0_PB01_O, SPT0_AD0_I)
    STEP(SPT0_BD0_O,  DAI0_PB02_I)
    STEP(DAI0_PB03_O, SPT1_AD0_I)
    STEP(SPT1_BD0_O,  DAI0_PB04_I)
    STEP(DAI0_PB05_O, SPT2_AD0_I)
    STEP(SPT2_BD0_O,  DAI0_PB06_I)
    STEP(DAI0_PB07_O, SPT3_AD0_I)
    STEP(SPT3_BD0_O,  DAI0_PB08_I)

    STEP(DAI0_PB10_O, SPT0_ACLK_I)
    STEP(DAI0_PB10_O, SPT1_ACLK_I)
    STEP(DAI0_PB10_O, SPT2_ACLK_I)
    STEP(DAI0_PB10_O, SPT3_ACLK_I)
    STEP(DAI0_PB09_O, SPT0_AFS_I)
    STEP(DAI0_PB09_O, SPT1_AFS_I)
    STEP(DAI0_PB09_O, SPT2_AFS_I)
    STEP(DAI0_PB09_O, SPT3_AFS_I)

    STEP(DAI0_PB19_O, SPT0_BCLK_I)
    STEP(DAI0_PB19_O, SPT1_BCLK_I)
    STEP(DAI0_PB19_O, SPT2_BCLK_I)
    STEP(DAI0_PB19_O, SPT3_BCLK_I)
    STEP(DAI0_PB20_O, SPT0_BFS_I)
    STEP(DAI0_PB20_O, SPT1_BFS_I)
    STEP(DAI0_PB20_O, SPT2_BFS_I)
    STEP(DAI0_PB20_O, SPT3_BFS_I)

    STEP(LOW,  DAI0_PBEN01_I)
    STEP(HIGH, DAI0_PBEN02_I)
    STEP(LOW,  DAI0_PBEN03_I)
    STEP(HIGH, DAI0_PBEN04_I)
    STEP(LOW,  DAI0_PBEN05_I)
    STEP(HIGH, DAI0_PBEN06_I)
    STEP(LOW,  DAI0_PBEN07_I)
    STEP(HIGH, DAI0_PBEN08_I)
    STEP(LOW,  DAI0_PBEN09_I)
    STEP(LOW,  DAI0_PBEN10_I)
    STEP(LOW,  DAI0_PBEN19_I)
    STEP(LOW,  DAI0_PBEN20_I)

    r1 = 8;
    call _wait_ticks;

    /* ---- read the routing back ---- */
    r4 = dm(REG_DAI0_DAT0);
    call _dump_word;
    r4 = dm(REG_DAI0_CLK0);
    call _dump_word;
    r4 = dm(REG_DAI0_PIN0);
    call _dump_word;

    r8 = 6;
.square:
    call _pin_hi;
    r1 = SQ_TICKS;
    call _wait_ticks;
    call _pin_lo;
    r1 = SQ_TICKS;
    call _wait_ticks;
    r8 = r8 - 1;
    if ne jump (pc, .square);
    r1 = 8;
    call _wait_ticks;
    jump (pc, .frame_top);

_start.end:

/*----------------------------------------------------------------------
 * Helpers — identical in behaviour to clkprobe.asm's.
 *--------------------------------------------------------------------*/
_pin_hi:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_SET) = r0;
    rts;
_pin_hi.end:

_pin_lo:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_CLR) = r0;
    rts;
_pin_lo.end:

/* One 1-tick-high, 1-tick-low pulse. Clobbers r0..r3. */
_pulse:
    call _pin_hi;
    r1 = 1;
    call _wait_ticks;
    call _pin_lo;
    r1 = 1;
    call _wait_ticks;
    rts;
_pulse.end:

/* In: r1 = core-timer reloads to wait. Clobbers r1, r2, r3. */
_wait_ticks:
    r2 = tcount;
.wt_loop:
    r3 = tcount;
    comp(r3, r2);
    if le jump (pc, .wt_next);
    r1 = r1 - 1;
    if eq rts;
.wt_next:
    r2 = r3;
    jump (pc, .wt_loop);
_wait_ticks.end:

/* In: r4 = value. Clobbers r0..r6, r12. */
_dump_word:
    call _pin_hi;
    r1 = 8;
    call _wait_ticks;
    call _pin_lo;
    r1 = 4;
    call _wait_ticks;

    r12 = 32;
.dw_bit:
    r1 = 1;
    r5 = lshift r4 by -31;
    r4 = lshift r4 by 1;
    r6 = pass r5;
    if eq jump (pc, .dw_drive);
    r1 = 3;
.dw_drive:
    call _pin_hi;
    call _wait_ticks;
    call _pin_lo;
    r1 = 1;
    call _wait_ticks;
    r12 = r12 - 1;
    if ne jump (pc, .dw_bit);

    r1 = 6;
    call _wait_ticks;
    rts;
_dump_word.end:
