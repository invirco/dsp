/*======================================================================
 * rdyprobe.asm — "did the application actually start?" image, readable
 * from the Pi with no bench eyes.
 *
 * blink.asm proves the same thing but reports on LD3/LD2, which only a
 * human standing at the card can see. This image is identical except
 * that it toggles PB_05 instead of PA_12. PB_05 is the SPI2_RDY net,
 * which leaves the card as CS3 (chip 1) / CS4 (chip 2) and lands on the
 * Pi as GPIO8 / GPIO12 — so the same "is it alive?" question can be
 * asked and answered entirely over ssh:
 *
 *   dsp4_boot.py --ldr rdyprobe1.ldr --chip 1
 *   for i in $(seq 1 12); do pinctrl get 8 | grep -oE 'lo|hi'; sleep .25; done
 *
 * Alternating lo/hi at the expected rate = the boot stream landed AND
 * the core is executing our code. Flat = it is not, and no downstream
 * result (readback, bisect park, LED) means anything until that is
 * fixed.
 *
 * Taking SPI2_RDY over is safe once boot is finished: the boot kernel is
 * done with the pin, the Pi holds CS deasserted, and the only other
 * thing on the net is an H1S1 monitor input. It does mean the part can
 * no longer be re-booted without a reset — dsp4_boot.py's RDY wait sees
 * whatever this loop last drove — so re-boot with the !RST_D pulse (the
 * default), not --no-reset.
 *
 * HARDWARE (rev C schematic, DSPA page 5/10 and DSPB page 4/10):
 *   PB_05 -> SPI2_RDY -> 10K pulldown (R34 on DSPA, R22 on DSPB) -> the
 *   card edge as CS3/CS4 -> Pi GPIO8 (chip 1) / GPIO12 (chip 2).
 *   The pin is driven push-pull here, so the pulldown does not fight it.
 *
 * RATE: chip 1 toggles at ~1 Hz, chip 2 at ~2 Hz — same 2:1 convention
 * as blink.asm, and the same free CCLK measurement if the observed rate
 * is off by a constant factor.
 *
 * Infrastructure (hand-maintained). Built by build.sh's "rdyprobe"
 * target, per chip via -DCHIP_ID, into rdyprobe1.ldr / rdyprobe2.ldr.
 *======================================================================*/

#include <def21564.h>

#define RDY_BIT (1 << 5)   /* PB_05 = SPI2_RDY net — Pi reads it on GPIO8 */

/* Delay calibration — see the note above. */
#define CCLK_HZ          400000000
#define CYCLES_PER_ITER  5
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
    /* PB_05 to GPIO output, driven low to start. FER bit clear = GPIO
     * rather than peripheral function, which is also what takes the pin
     * back off SPI2 after the boot kernel finished with it; with FER
     * clear the MUX setting for the pin is irrelevant. */
    r0 = RDY_BIT;
    dm(REG_PORTB_FER_CLR)  = r0;   /* GPIO, not SPI2 */
    dm(REG_PORTB_INEN_CLR) = r0;   /* not an input */
    dm(REG_PORTB_DATA_CLR) = r0;   /* start low before driving */
    dm(REG_PORTB_DIR_SET)  = r0;   /* now drive it */

.probe_loop:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_TGL) = r0;

    r1 = DELAY_ITERS;
.delay:
    r1 = r1 - 1;
    if ne jump (pc, .delay);

    jump (pc, .probe_loop);

_start.end:
