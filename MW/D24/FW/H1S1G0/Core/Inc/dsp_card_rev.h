/* dsp_card_rev.h -- DSP card hardware revision straps, for the REV D H1S1
 * (U7 = STM32G0B1RET6). S173.
 *
 * Rev D only. Rev C's U7 is an STM32U575, whose pads 14/15/16 are
 * PA0/PA1/PA2 and carry rev C nets (DSPC-L11 §2); rev C has no straps, and
 * per PW (L11 Q4) its H1S1 reports nothing. Written at S173 in
 * MW/D24/FW/H1S1/revd/, moved here into the G0B1 port at S174, where
 * matrix.cs calls it from MainInit and carries the cell handling below.
 *
 * The straps (DSPC-L11, PW 2026-10-25 "L11 1by1, all per rec"):
 *   U7 PC1 / PC2 / PC3 (LQFP-64 pins 14 / 15 / 16) = REV_ID0 / 1 / 2,
 *   each one fitted 10K to +3V3 (= 1) or to GND (= 0).
 *   code = (GPIOC->IDR >> 1) & 7;   rev D = 1 (R90 to +3V3, R91/R92 to GND)
 * Read ONCE at boot with the internal pulls OFF (L11 Q3: no pull-flip
 * open-strap test).
 *
 * Register-level on purpose: it needs no HAL and no CMSIS device header, so
 * it can be checked on its own (arm-none-eabi-gcc -mcpu=cortex-m0plus) and
 * dropped into the port whatever HAL version that port settles on.
 * Addresses: RCC 0x4002 1000 (IOPENR +0x34), IOPORT GPIOC 0x5000 0800
 * (MODER +0x00, PUPDR +0x0C, IDR +0x10) -- checked against ST's STM32G0
 * CMSIS device header (stm32g031xx.h in the MH1 Drivers pack; the G0 family
 * shares this map; RM0444 itself is not on file). Compiles clean with
 * -mcpu=cortex-m0plus -Wall -Wextra -Werror (S173).
 */
#ifndef DSP_CARD_REV_H
#define DSP_CARD_REV_H

#include <stdint.h>

#define DCR_RCC_IOPENR   (*(volatile uint32_t *)0x40021034u)
#define DCR_GPIOC_MODER  (*(volatile uint32_t *)0x50000800u)
#define DCR_GPIOC_PUPDR  (*(volatile uint32_t *)0x5000080Cu)
#define DCR_GPIOC_IDR    (*(volatile uint32_t *)0x50000810u)

#define DSP_CARD_REV_D   1u   /* the code the rev D straps carry */

/* PC1..PC3: MODER = 00 (input), PUPDR = 00 (no pull). The G0's reset state
 * is ANALOG (11), in which the input buffer is off and IDR reads 0 -- so a
 * read without this setup would report every board as code 0. */
static inline uint8_t dsp_card_rev_read(void)
{
    const uint32_t m = (3u << 2) | (3u << 4) | (3u << 6);   /* PC1..PC3 fields */
    DCR_RCC_IOPENR |= (1u << 2);                            /* GPIOCEN */
    (void)DCR_RCC_IOPENR;                                   /* clock settles */
    DCR_GPIOC_PUPDR &= ~m;
    DCR_GPIOC_MODER &= ~m;
    /* A 10K strap into a few pF settles in well under a microsecond; a
     * short spin keeps the read clear of the MODER write at any SYSCLK. */
    for (volatile int i = 0; i < 64; i++) { }
    return (uint8_t)((DCR_GPIOC_IDR >> 1) & 7u);
}

/* THE BUS CELL (proposal S173: Sys001DspCardRev001 -- see
 * proposals/CONTRACT-PROPOSAL-S173.md; ruled Q1 (a), not in defs yet).
 * Implemented in matrix.cs (MainInit, RevCellPoll) along these lines:
 *
 *   MainInit():  code = dsp_card_rev_read();
 *                matrix[pSys001DspCardRev001][TXD] = code;
 *                matrix[pSys001DspCardRev001][TXF] = 1;      // report once
 *   MainLoop():  if (matrix[pSys001DspCardRev001][RXF]) {
 *                    if (matrix[pSys001DspCardRev001][RXD] == 0xFF) {  // request
 *                        matrix[pSys001DspCardRev001][TXD] = code;
 *                        matrix[pSys001DspCardRev001][TXF] = 1;
 *                    }
 *                    matrix[pSys001DspCardRev001][RXF] = 0;
 *                }
 *
 * The reply (0..7) can never equal the request (0xFF), so H1S1 hearing its
 * own reply on the multi-drop bus does not re-trigger it -- the S81 free-run
 * (CodecPoll's comment in matrix.cs) cannot happen on this cell. Poll()
 * sends a TXD of 0 as the address alone; code 0 is never a rev D answer. */

#endif /* DSP_CARD_REV_H */
