/* main.h -- H1S1 on the DSP card rev D (U7 = STM32G0B1RET6). S174.
 *
 * Pin names follow the rev C H1S1 (MW/D24/FW/H1S1/Core/Inc/main.h) wherever
 * the net is the same; pins from invirco/dspcard review/stage2b-u7-pinmap.md
 * (stage 3d) + review/l11-report.md (REV_ID straps). Pins this firmware does
 * not name stay at their reset state (analog, input buffer off) -- that
 * includes SPI1 (PB3/PB4/PB5): on rev D H1S1 has no SPI slave left (the
 * codec select moved to the CM4's CS6, !CS_M is the CM4's CS5), so it never
 * touches the bus the CM4 boots the DSPs over.
 */
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32g0xx_hal.h"

void Error_Handler(void);

/* CM4-owned chip selects and RDY lines: inputs, never driven (rev C rule,
 * MW/D24/FW/H1S1 main.c MX_GPIO_Init_2). */
#define CS5_Pin GPIO_PIN_13          /* CS_M (595 latch, CM4 CS5)        */
#define CS5_GPIO_Port GPIOC
#define CS2_Pin GPIO_PIN_14          /* DSPB_SPI2_SS                     */
#define CS2_GPIO_Port GPIOC
#define CS7_Pin GPIO_PIN_15          /* PI_SPI_CS7 / SWD_EN1             */
#define CS7_GPIO_Port GPIOC
#define CS8_Pin GPIO_PIN_0           /* PI_SPI_CS8 / SWD_EN3 (rev C PH0) */
#define CS8_GPIO_Port GPIOF
#define CS1_Pin GPIO_PIN_12          /* DSPA_SPI2_SS                     */
#define CS1_GPIO_Port GPIOB
#define CS4_Pin GPIO_PIN_13          /* DSPB_SPI2_RDY                    */
#define CS4_GPIO_Port GPIOB
#define CS3_Pin GPIO_PIN_14          /* DSPA_SPI2_RDY                    */
#define CS3_GPIO_Port GPIOB

/* Resets this MCU drives. U7 is the ONLY RST_C driver on rev D (S173-3). */
#define RST_C_Pin GPIO_PIN_11        /* converters + 595 chain           */
#define RST_C_GPIO_Port GPIOA
#define RST_O_Pin GPIO_PIN_12        /* option cards, J3/J4 pin 75       */
#define RST_O_GPIO_Port GPIOA

/* Panel bus (MH1), as rev C. */
#define BLINK_Pin GPIO_PIN_6         /* S MCU_LED0                       */
#define BLINK_GPIO_Port GPIOB
#define BUSY_Pin GPIO_PIN_7          /* LOGIC_BUSY                       */
#define BUSY_GPIO_Port GPIOB
#define S2_Pin GPIO_PIN_8            /* data ready to MH1 (active low)   */
#define S2_GPIO_Port GPIOB
#define S3_Pin GPIO_PIN_9            /* MH1 data request                 */
#define S3_GPIO_Port GPIOB

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
