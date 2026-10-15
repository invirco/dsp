/*
 * D24 Digital U34 (STM32F030F4P6) — minimal register map + pin roles.
 * Pin facts: src/fw/d24-pwr-mcu-def.csv pin.* rows.
 *
 *   PA0  MHRX sense in (hi = Pi powered; UART TX idles high)  [pull-down]
 *   PA1  SENS_12V ADC in (ch1)
 *   PA2  UPS_EN out      (+5V5 buck + +5V_PI boost pair)
 *   PA3  PSU_DIG_EN out  (+5V/+3V3/+0.9V digital bucks)
 *   PA4  PSU_12_CLK      TIM14_CH1 AF4, 1 MHz 20%  (gates the ±15 V set)
 *   PA5  PI_SD out       (save-and-shutdown request, active high)
 *   PA9  PWR_FAIL out    (0 = radios off in hardware; low in standby to
 *                         avoid back-powering an unpowered CM4)
 *   PA10 AN_EN in        (Pi requests analog power)           [pull-down]
 *   PB1  PSU_48_CLK      TIM3_CH4 AF1, 1 MHz 80%  (gates +45 V phantom)
 *   PF0  PWR_SW in       (rocker: closed = GND = ON; external 10K pull-up)
 *   PF1  PWR_LED out
 */
#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>

#define REG(a)          (*(volatile uint32_t *)(a))

/* clocks / flash */
#define RCC_CR          REG(0x40021000u)
#define RCC_CFGR        REG(0x40021004u)
#define RCC_AHBENR      REG(0x40021014u)
#define RCC_APB2ENR     REG(0x40021018u)
#define RCC_APB1ENR     REG(0x4002101Cu)
#define RCC_CSR         REG(0x40021024u)   /* reset-cause flags [31:24], RMVF bit 24 */
#define FLASH_ACR       REG(0x40022000u)

/* GPIO ports (offsets: MODER 0, PUPDR C, IDR 10, ODR 14, AFRL 20, AFRH 24) */
#define GPIOA           0x48000000u
#define GPIOB           0x48000400u
#define GPIOF           0x48001400u
#define GPIO_MODER(p)   REG((p) + 0x00u)
#define GPIO_PUPDR(p)   REG((p) + 0x0Cu)
#define GPIO_IDR(p)     REG((p) + 0x10u)
#define GPIO_ODR(p)     REG((p) + 0x14u)
#define GPIO_BSRR(p)    REG((p) + 0x18u)
#define GPIO_AFRL(p)    REG((p) + 0x20u)
#define GPIO_AFRH(p)    REG((p) + 0x24u)

/* timers (PSU sync clocks) */
#define TIM3            0x40000400u
#define TIM14           0x40002000u
#define TIM_CR1(t)      REG((t) + 0x00u)
#define TIM_CCMR1(t)    REG((t) + 0x18u)
#define TIM_CCMR2(t)    REG((t) + 0x1Cu)
#define TIM_CCER(t)     REG((t) + 0x20u)
#define TIM_PSC(t)      REG((t) + 0x28u)
#define TIM_ARR(t)      REG((t) + 0x2Cu)
#define TIM_CCR1(t)     REG((t) + 0x34u)
#define TIM_CCR4(t)     REG((t) + 0x40u)

/* ADC */
#define ADC_ISR         REG(0x40012400u)
#define ADC_CR          REG(0x40012408u)
#define ADC_CFGR1       REG(0x4001240Cu)
#define ADC_SMPR        REG(0x40012414u)
#define ADC_CHSELR      REG(0x40012428u)
#define ADC_DR          REG(0x40012440u)

/* SysTick (polled, no interrupts) */
#define SYST_CSR        REG(0xE000E010u)
#define SYST_RVR        REG(0xE000E014u)

#endif
