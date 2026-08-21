/*======================================================================
 * blink.asm — "is this board alive?" image for the DSP4 SHARCs.
 *
 * Toggles the per-DSP status LED and nothing else. No SRU, no SPORT, no
 * DMA, no SEC, no SPI — so it separates two failures that look identical
 * on the bench: "the boot stream never landed" and "the boot stream
 * landed but the plumbing hangs". If this blinks, then power, the clock
 * into SYS_CLKIN0, reset release, the SPI slave-boot path from the CM4,
 * and the core are all good, and any remaining fault is in the audio
 * plumbing.
 *
 * HARDWARE (rev C schematic, DSPA page 5/10 and DSPB page 4/10 — the two
 * sheets are identical):
 *   PA_12 -> net BLINK_LED -> 1K series (R37 on DSPA/U6, R4 on DSPB/U5)
 *            -> green LED (LD3 on DSPA, LD2 on DSPB) -> GND.
 *   Drive HIGH to light. Each DSP owns its own LED: nothing else on the
 *   board drives these nets, so the two chips cannot fight.
 *   PA_13 is the net !BLINK, which is SHARED (it also reaches LOGIC pin
 *   58 and the supervisor). It is an INPUT here. Do not drive it.
 *
 * RATE: chip 1 blinks at ~1 Hz, chip 2 at ~2 Hz, so one glance tells you
 * which part booted which image — and if only one blinks, you know which
 * chip select failed.
 *
 * The delay is a counted loop, so the ABSOLUTE rate depends on both the
 * core clock and the cycles the loop itself costs. Both are now measured
 * (491.52 MHz and 13 cycles per iteration, see CCLK_HZ below), so the
 * rate should be within a percent of nominal. Do NOT read a wrong rate
 * back as a CCLK measurement — that inference is what produced the
 * retracted "~190 MHz" figure. src/blink/clkprobe.asm measures the clock
 * properly, off the core timer.
 *
 * Infrastructure (hand-maintained). Built by build.sh's "blink" target,
 * per chip via -DCHIP_ID, into blink1.ldr / blink2.ldr.
 *======================================================================*/

#include <def21564.h>

#define LED_BIT     0x00001000     /* PA_12 = BLINK_LED */

/* Delay calibration — see the note above. */
/* CCLK = 491.52 MHz, MEASURED 2026-08-21 off the core timer with
 * src/blink/clkprobe.asm and cross-checked against the CGU registers
 * read out of the running part: SYS_CLKIN0 24.576 MHz, CGU reset
 * defaults DF=0 MSEL=40 CSEL=1 SYSSEL=2 S0SEL=4, and the 2156x PLL's
 * built-in /2 — exactly the tree dsp4-architecture-decisions.md D10
 * predicted. The firmware does NOT program the CGU; it corrects its own
 * constants instead (D10 addendum). A two-instruction delay loop costs
 * 13 cycles per iteration on this core, not the 5 these files used to
 * assume; that factor, not the clock, is what made the blink images
 * look 2.1x slow and produced the retracted "~190 MHz" estimate. */
#define CCLK_HZ          491520000
#define CYCLES_PER_ITER  13
#if CHIP_ID == 1
#define HALF_PERIOD_MS   500       /* ~1 Hz */
#elif CHIP_ID == 2
#define HALF_PERIOD_MS   250       /* ~2 Hz */
#else
#error "CHIP_ID must be defined as 1 or 2"
#endif
/* Ordered to keep every intermediate inside 32 bits. */
#define DELAY_ITERS ((CCLK_HZ / CYCLES_PER_ITER / 1000) * HALF_PERIOD_MS)

.section/pm seg_pmco;

.global _start;
_start:
    /* PA_12 to GPIO output, driven low (LED off) to start.
     * FER bit clear = GPIO rather than peripheral function; with FER
     * clear the MUX setting for the pin is irrelevant. */
    r0 = LED_BIT;
    dm(REG_PORTA_FER_CLR)  = r0;   /* GPIO, not peripheral */
    dm(REG_PORTA_INEN_CLR) = r0;   /* not an input */
    dm(REG_PORTA_DATA_CLR) = r0;   /* start low before driving */
    dm(REG_PORTA_DIR_SET)  = r0;   /* now drive it */

.blink_loop:
    r0 = LED_BIT;
    dm(REG_PORTA_DATA_TGL) = r0;

    r1 = DELAY_ITERS;
.delay:
    r1 = r1 - 1;
    if ne jump (pc, .delay);

    jump (pc, .blink_loop);

_start.end:
