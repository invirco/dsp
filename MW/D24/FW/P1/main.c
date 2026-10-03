// P1 foot pedal application -- S167, for the P1 rev B serial-program mod;
// S169: one image for both display polarities.
//
// MCU U2 = STM32C031K4U6 (UFQFPN32, 16 KB flash). Register level, no HAL.
//
// THE MOD: USART1 moved to the ROM bootloader's pins so the same cable takes
// the first program, every update and the application:
//   PA9  (pin 19) USART1_TX AF1 -> U3 SN65LVDS1 -> J1 TX+/TX-
//   PA10 (pin 21) USART1_RX AF1 <- U4 SN65LVDS2 <- J1 RX+/RX-
//   PC14 (pin 2) and PA1 (pin 8), the old TX/RX, are still on those nets:
//   inputs, no pull, never driven.
//   SW2 moved from PA10 to PB2 (pin 17; the schematic's "PB15" is wrong).
//
// LAMPS: LD1..LD4 (LD1..LD8 on the board, two LEDs a pin) are active low on
// the DIM1 rail, which DIM_1 = PB0 (TIM3_CH3, 12 kHz PWM) switches through
// Q2/Q4. The 7-segment display hangs off the DIM0 rail: each segment pin
// drives one segment through 470R, the four display commons are DIM0.
//
// DISPLAY POLARITY (S169). The display may be common ANODE (BOM, SA08-11YWA)
// or common CATHODE (FJ8102AY on the first rev B pedal). The DIM0 rail is:
//   next P1 rev: U2 pins 11-14 (PA4-PA7) tied to DIM0, push-pull, all four
//                always written together: HIGH for CA, LOW for CC
//   rev B as designed: PB1 (DIM_0) -> Q1/Q3 -> DIM0, only CA can light;
//                PB1 is held HIGH for CA, LOW for CC
//   rev B interim (bench pedal): Q3 out, DIM0 to GND, PA4-PA7 unconnected,
//                only CC can light
// Both are driven on every board; on each variant the drive that is not
// wired goes nowhere. A segment is lit by driving its pin to the opposite
// level from the rail and dark at the rail's level, so the rail never moves
// to dim: brightness of the segments is software PWM on the segment pins.
// A wrong polarity never damages anything: where the rail follows the
// firmware (next rev, rev B with Q3) the lit segments are only reverse-biased
// by 3.3 V (display VR max 5 V) and the display is dark; on the interim (DIM0
// grounded) CA drives the UNLIT segments high, so the display shows inverted
// at the normal 470R segment current.
//   Which polarity: the stored setting (page 7) if it says CA or CC,
//   otherwise the start-up probe (Probe()), otherwise CA (the BOM part).
//
// PROTOCOL, 115200 8N1, one byte commands unless shown:
//   ':'          all lamps on, reply ":\n"          (the stub's behaviour, kept)
//   '.'          all lamps off, reply ".\n"
//   'V'          reply "P1 <version> uid=<24 hex> optr=<8 hex> disp=<CA|CC>
//                by=<stored|probe|default> set=<auto|CA|CC>
//                probe=<CA|CC|none|odd> adc=<4 x 3 hex>\n"
//   'S'          reply "S<sw1><sw2>\n", 1 = pressed; also sent on every change
//   'L' + 4 hex  lamp bitmap (bit order below), reply "L<4 hex>\n"
//   'D' + digit  brightness 0..9 (0 = off, 9 = full), reply "D<d>\n"
//   'P' + char   display polarity setting: 'A' common anode, 'C' common
//                cathode, 'U' auto (probe again now), '?' read only; stored
//                in flash if it changed and applied at once; reply
//                "P set=<..> disp=<..> by=<..>\n" ("P ERR\n" if the write failed)
//   "!BOOT\n"    reply "!BOOT\n", then option bytes nBOOT_SEL=1 nBOOT1=1
//                nBOOT0=0 and reload: the next start is the ROM bootloader.
// At power-up the display is probed (nothing lights), then every lamp lights
// for 300 ms (lamp test), then all go off.
// If the application starts with nBOOT0=0 (the ROM's Go after an update) it
// restores nBOOT0=1 and reloads the option bytes, so the update is undone by
// nothing but a successful start of the new image.

#include "stm32c031xx.h"

#define P1_VERSION "1.1-s169"

// lamp bitmap, bit n:
//  0 LD1 PB9  1 LD2 PA0  2 LD3 PA2  3 LD4 PA3
//  4 A PA11   5 B PA15   6 C PB5    7 D PB7   8 E PB3  9 F PA12  10 G PB4
// 11 L PB6   12 R PB8
static const struct { GPIO_TypeDef *port; uint8_t pin; } LAMP[13] = {
    { GPIOB, 9 }, { GPIOA, 0 }, { GPIOA, 2 }, { GPIOA, 3 },
    { GPIOA, 11 }, { GPIOA, 15 }, { GPIOB, 5 }, { GPIOB, 7 }, { GPIOB, 3 },
    { GPIOA, 12 }, { GPIOB, 4 }, { GPIOB, 6 }, { GPIOB, 8 },
};
#define LAMPS_ALL 0x1FFFu
#define SEG_FIRST 4

#define RAIL_PINS (0xFu << 4)                    // PA4..PA7, the next rev's DIM0 rail
#define RAIL_MODER_MASK (0xFFu << 8)
#define RAIL_MODER_OUT  (0x55u << 8)

enum { POL_NONE = 0, POL_CA = 1, POL_CC = 2 };           // also the setting: 0 = auto
enum { BY_STORED, BY_PROBE, BY_DEFAULT };
enum { PR_NONE, PR_CA, PR_CC, PR_ODD };

static volatile uint32_t ticks;
static volatile uint32_t lampMap;                // what Lamps() was last asked for
static volatile int segLevel = 9;                // software dimming of the segments
static volatile int dispPol;                     // POL_NONE until decided: segments stay inputs
static volatile uint8_t rxBuf[64];
static volatile uint8_t rxHead, rxTail;

static int polSet, polBy, probeRes;
static uint16_t probeAdc[4];                     // CC probe A, F; CA probe A, F

static void LampsDrive(uint32_t map, int segsOn);

void SysTick_Handler(void)
{
    ticks++;
    // 100 Hz, ten steps: the segment rail is static, so the segments are PWMed
    int phase = (int)(ticks % 10);
    LampsDrive(lampMap, segLevel >= 9 || phase < segLevel);
}

void USART1_IRQHandler(void)
{
    while (USART1->ISR & USART_ISR_RXNE_RXFNE)
    {
        uint8_t b = (uint8_t)USART1->RDR;
        uint8_t n = (uint8_t)((rxHead + 1) & 63);
        if (n != rxTail) { rxBuf[rxHead] = b; rxHead = n; }
    }
    USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF | USART_ICR_PECF;
}

static int RxGet(void)
{
    if (rxHead == rxTail) return -1;
    int b = rxBuf[rxTail];
    rxTail = (uint8_t)((rxTail + 1) & 63);
    return b;
}

static void TxByte(char c)
{
    while (!(USART1->ISR & USART_ISR_TXE_TXFNF)) { }
    USART1->TDR = (uint8_t)c;
}

static void TxStr(const char *s) { while (*s) TxByte(*s++); }

static const char HEX[] = "0123456789ABCDEF";

static void TxHex(uint32_t v, int digits)
{
    while (digits--) TxByte(HEX[(v >> (digits * 4)) & 0xF]);
}

static void PinMode(GPIO_TypeDef *g, int pin, uint32_t mode, uint32_t pull, uint32_t af)
{
    g->MODER = (g->MODER & ~(3u << (pin * 2))) | (mode << (pin * 2));
    g->PUPDR = (g->PUPDR & ~(3u << (pin * 2))) | (pull << (pin * 2));
    if (mode == 2)
    {
        volatile uint32_t *afr = &g->AFR[pin >> 3];
        int sh = (pin & 7) * 4;
        *afr = (*afr & ~(0xFu << sh)) | (af << sh);
    }
}

// LD1..LD4 (bits 0-3) are active low on the DIM1 rail. A segment (bits 4-12)
// is lit at the level opposite the DIM0 rail: low for CA, high for CC. Until
// the polarity is decided the segment pins are inputs and are not written.
static void LampsDrive(uint32_t map, int segsOn)
{
    int pol = dispPol;
    for (int i = 0; i < 13; i++)
    {
        uint32_t bit = 1u << LAMP[i].pin;
        int on = (map >> i) & 1;
        if (i < SEG_FIRST)
            LAMP[i].port->BSRR = on ? (bit << 16) : bit;               // low = lit
        else if (pol != POL_NONE)
        {
            int high = (on && segsOn) ? (pol == POL_CC) : (pol == POL_CA);
            LAMP[i].port->BSRR = high ? bit : (bit << 16);
        }
    }
}

static void Lamps(uint32_t map)
{
    lampMap = map;
    LampsDrive(map, segLevel > 0);
}

static void Brightness(int level)                // 0..9
{
    TIM3->CCR3 = (level >= 9) ? 1000 : (uint32_t)level * 100;   // DIM_1, LD1..LD8
    segLevel = level;
}

static void Delay(uint32_t ms)
{
    uint32_t t0 = ticks;
    while ((uint32_t)(ticks - t0) < ms) { }
}

// ---- the DIM0 rail -----------------------------------------------------------

// PA4..PA7 are set by ONE BSRR write and switched to outputs by ONE MODER
// write, so the four tied pins are never at different levels. PB1 (DIM_0,
// TIM3_CH4) follows: 100 % for CA (rev B Q1/Q3 on), 0 % for CC.
static void RailSet(int high)
{
    GPIOA->BSRR = high ? RAIL_PINS : (RAIL_PINS << 16);
    GPIOA->MODER = (GPIOA->MODER & ~RAIL_MODER_MASK) | RAIL_MODER_OUT;
    TIM3->CCR4 = high ? 1000 : 0;
}

static void SegsFloat(void)                      // segment pins: inputs, no pull
{
    for (int i = SEG_FIRST; i < 13; i++) PinMode(LAMP[i].port, LAMP[i].pin, 0, 0, 0);
}

static void ApplyPolarity(int pol)
{
    dispPol = POL_NONE;                          // SysTick leaves the segments alone
    SegsFloat();
    RailSet(pol == POL_CA);
    dispPol = pol;
    LampsDrive(lampMap, 0);                      // every segment at the rail's level first
    for (int i = SEG_FIRST; i < 13; i++) PinMode(LAMP[i].port, LAMP[i].pin, 1, 0, 0);
    Lamps(lampMap);
}

// ---- start-up probe ------------------------------------------------------------

static uint16_t AdcRead(uint32_t ch)             // mean of 4 conversions, 12 bit
{
    ADC1->CHSELR = 1u << ch;
    while (!(ADC1->ISR & ADC_ISR_CCRDY)) { }
    ADC1->ISR = ADC_ISR_CCRDY;
    uint32_t sum = 0;
    for (int i = 0; i < 4; i++)
    {
        ADC1->ISR = ADC_ISR_EOC;
        ADC1->CR |= ADC_CR_ADSTART;
        while (!(ADC1->ISR & ADC_ISR_EOC)) { }
        sum += ADC1->DR;
    }
    return (uint16_t)(sum / 4);
}

// Segment A (PA11, ADC_IN11) and F (PA12, ADC_IN12) are the only segment pins
// with an ADC input. Every other segment pin floats, so no other segment can
// carry current. Each probed pin sits in input mode on its 40k weak pull
// (25..55k) and the ADC reads the pad:
//   CC probe: rail LOW, pull-UP.  A CC segment conducts: the pin sits at the
//             LED's Vf at ~40 uA (~1.7 V, ~0.5 VDD); otherwise it reads VDD.
//   CA probe: rail HIGH, pull-DOWN. A CA segment conducts: the pin sits at
//             rail - Vf (~1.5 V); otherwise it reads 0.
// A digital read cannot tell ~0.5 VDD from either rail (VIL 0.3 VDD, VIH
// 0.7 VDD), hence the ADC. Both segments must agree. The probe current is
// ~40 uA in at most two segments for ~2 ms each: nothing visibly lights, and
// a display of the other polarity is only reverse-biased.
#define IN(v, lo, hi) ((v) >= (lo) && (v) <= (hi))

static int Probe(void)
{
    dispPol = POL_NONE;
    SegsFloat();

    RCC->APBENR2 |= RCC_APBENR2_ADCEN;
    ADC1->CFGR2 = ADC_CFGR2_CKMODE_0;            // PCLK/2 = 6 MHz
    ADC1->CR = ADC_CR_ADVREGEN;
    Delay(2);                                    // tADCVREG_STUP 20 us
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) { }
    for (volatile int i = 0; i < 20; i++) { }    // > 4 ADC clocks before ADEN
    ADC1->SMPR = 7u << ADC_SMPR_SMP1_Pos;        // 160.5 cycles: high-impedance source
    ADC1->ISR = ADC_ISR_ADRDY;
    ADC1->CR |= ADC_CR_ADEN;
    while (!(ADC1->ISR & ADC_ISR_ADRDY)) { }

    RailSet(0);
    PinMode(GPIOA, 11, 0, 1, 0);
    PinMode(GPIOA, 12, 0, 1, 0);
    Delay(2);
    probeAdc[0] = AdcRead(11);
    probeAdc[1] = AdcRead(12);

    RailSet(1);
    PinMode(GPIOA, 11, 0, 2, 0);
    PinMode(GPIOA, 12, 0, 2, 0);
    Delay(2);
    probeAdc[2] = AdcRead(11);
    probeAdc[3] = AdcRead(12);

    SegsFloat();
    RailSet(0);
    ADC1->CR |= ADC_CR_ADDIS;
    while (ADC1->CR & ADC_CR_ADEN) { }
    ADC1->CR = 0;
    RCC->APBENR2 &= ~RCC_APBENR2_ADCEN;

    // thresholds in 1/4095 VDD: path 0.29..0.81 / 0.20..0.71, open > 0.90 / < 0.10
    int ccPath = IN(probeAdc[0], 1200, 3300) && IN(probeAdc[1], 1200, 3300);
    int ccOpen = probeAdc[0] > 3700 && probeAdc[1] > 3700;
    int caPath = IN(probeAdc[2], 800, 2900) && IN(probeAdc[3], 800, 2900);
    int caOpen = probeAdc[2] < 400 && probeAdc[3] < 400;
    if (ccPath && caOpen) return PR_CC;
    if (caPath && ccOpen) return PR_CA;
    if (ccOpen && caOpen) return PR_NONE;        // no display, or no rail it can reach
    return PR_ODD;
}

// ---- flash: option bytes and the settings page --------------------------------

static void FlashUnlock(void)
{
    if (FLASH->CR & FLASH_CR_LOCK) { FLASH->KEYR = 0x45670123u; FLASH->KEYR = 0xCDEF89ABu; }
}

static int FlashOptWrite(uint32_t optr)
{
    FlashUnlock();
    if (FLASH->CR & FLASH_CR_OPTLOCK) { FLASH->OPTKEYR = 0x08192A3Bu; FLASH->OPTKEYR = 0x4C5D6E7Fu; }
    if (FLASH->CR & FLASH_CR_OPTLOCK) return -1;
    while (FLASH->SR & FLASH_SR_BSY1) { }
    FLASH->SR = FLASH->SR;                       // clear error flags
    FLASH->OPTR = optr;
    FLASH->CR |= FLASH_CR_OPTSTRT;
    while (FLASH->SR & FLASH_SR_BSY1) { }
    FLASH->CR |= FLASH_CR_OBL_LAUNCH;            // reloads the option bytes and resets
    for (;;) { }
}

// The ROM's Go after an update leaves nBOOT0=0: put it back and restart.
static void RestoreBoot(void)
{
    uint32_t optr = FLASH->OPTR;
    if (!(optr & FLASH_OPTR_nBOOT0) && (optr & FLASH_OPTR_nBOOT_SEL))
        FlashOptWrite(optr | FLASH_OPTR_nBOOT0);
}

static void EnterBootloader(void)
{
    uint32_t optr = FLASH->OPTR;
    optr |= FLASH_OPTR_nBOOT_SEL | FLASH_OPTR_nBOOT1;
    optr &= ~FLASH_OPTR_nBOOT0;
    while (!(USART1->ISR & USART_ISR_TC)) { }    // let the reply leave first
    FlashOptWrite(optr);
}

// Page 7 (0x08003800, outside the linker's 14 KB) is an append-only log of
// double-word records: w0 = 0x50310000 | value, w1 = ~w0. The last record
// with a matching w1 wins, so a write cut by a power loss is ignored and the
// previous value stands. The host's update erases only the pages the new
// image needs (d24_pedal.py rom-flash), so the setting survives an update.
#define SET_PAGE 7u
#define SET_BASE (FLASH_BASE + SET_PAGE * 2048u)
#define SET_SLOTS 256u
#define SET_MAGIC 0x50310000u

static const volatile uint32_t *SetSlot(uint32_t i)
{
    return (const volatile uint32_t *)(SET_BASE + i * 8u);
}

static int SettingRead(void)
{
    int v = POL_NONE;
    for (uint32_t i = 0; i < SET_SLOTS; i++)
    {
        uint32_t w0 = SetSlot(i)[0], w1 = SetSlot(i)[1];
        if (w0 == 0xFFFFFFFFu && w1 == 0xFFFFFFFFu) break;
        if (w1 == ~w0 && (w0 & 0xFFFFFF00u) == SET_MAGIC && (w0 & 0xFF) <= POL_CC) v = (int)(w0 & 0xFF);
    }
    return v;
}

static int FlashWait(void)
{
    while (FLASH->SR & FLASH_SR_BSY1) { }
    uint32_t sr = FLASH->SR;
    FLASH->SR = sr;
    return (sr & 0x0000C3FAu) ? -1 : 0;          // PROGERR..OPTVERR, RDERR
}

static int SettingWrite(int v)
{
    if (SettingRead() == v) return 0;
    uint32_t i = 0;
    while (i < SET_SLOTS && !(SetSlot(i)[0] == 0xFFFFFFFFu && SetSlot(i)[1] == 0xFFFFFFFFu)) i++;
    FlashUnlock();
    FLASH->SR = FLASH->SR;
    int err = 0;
    if (i == SET_SLOTS)
    {
        FLASH->CR = (FLASH->CR & ~FLASH_CR_PNB) | FLASH_CR_PER | (SET_PAGE << FLASH_CR_PNB_Pos);
        FLASH->CR |= FLASH_CR_STRT;
        err = FlashWait();
        FLASH->CR &= ~FLASH_CR_PER;
        i = 0;
    }
    if (!err)
    {
        uint32_t w0 = SET_MAGIC | (uint32_t)v;
        FLASH->CR |= FLASH_CR_PG;
        *(volatile uint32_t *)(SET_BASE + i * 8u) = w0;
        *(volatile uint32_t *)(SET_BASE + i * 8u + 4u) = ~w0;
        err = FlashWait();
        FLASH->CR &= ~FLASH_CR_PG;
    }
    FLASH->CR |= FLASH_CR_LOCK;
    return (err || SettingRead() != v) ? -1 : 0;
}

// Decide and apply. A stored CA/CC wins; with "auto" the probe decides; with
// no answer from the probe, CA (the BOM part; the wrong guess is only dark).
static void Decide(int probe)
{
    if (probe) probeRes = Probe();
    polSet = SettingRead();
    int pol;
    if (polSet != POL_NONE) { pol = polSet; polBy = BY_STORED; }
    else if (probeRes == PR_CA) { pol = POL_CA; polBy = BY_PROBE; }
    else if (probeRes == PR_CC) { pol = POL_CC; polBy = BY_PROBE; }
    else { pol = POL_CA; polBy = BY_DEFAULT; }
    ApplyPolarity(pol);
}

static const char *const POL_NAME[] = { "auto", "CA", "CC" };
static const char *const BY_NAME[] = { "stored", "probe", "default" };
static const char *const PR_NAME[] = { "none", "CA", "CC", "odd" };

static void TxPol(void)
{
    TxStr(" disp="); TxStr(POL_NAME[dispPol]);
    TxStr(" by="); TxStr(BY_NAME[polBy]);
    TxStr(" set="); TxStr(POL_NAME[polSet]);
}

// ---- start-up and the command loop ---------------------------------------------

static void Init(void)
{
    SCB->VTOR = FLASH_BASE;                      // the ROM's Go leaves its own table mapped
    // 12 MHz from HSI48/4 is the reset clock; set it again in case the ROM changed it
    RCC->CR |= RCC_CR_HSION;
    while (!(RCC->CR & RCC_CR_HSIRDY)) { }
    RCC->CFGR &= ~RCC_CFGR_SW;
    while (RCC->CFGR & RCC_CFGR_SWS) { }
    RCC->CR = (RCC->CR & ~RCC_CR_HSIDIV) | (2u << RCC_CR_HSIDIV_Pos);
    SystemCoreClock = 12000000u;

    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN | RCC_IOPENR_GPIOCEN;
    RCC->APBENR1 |= RCC_APBENR1_TIM3EN;
    RCC->APBENR2 |= RCC_APBENR2_USART1EN;

    // LD1..LD4: outputs, high (off) first so nothing flashes on the way out.
    // The segment pins stay inputs until the polarity is decided.
    for (int i = 0; i < SEG_FIRST; i++) LAMP[i].port->BSRR = 1u << LAMP[i].pin;
    for (int i = 0; i < SEG_FIRST; i++) PinMode(LAMP[i].port, LAMP[i].pin, 1, 0, 0);
    SegsFloat();

    PinMode(GPIOC, 14, 0, 0, 0);                 // old TX, still on the TX net
    PinMode(GPIOA, 1, 0, 0, 0);                  // old RX, still on the RX net
    PinMode(GPIOC, 15, 0, 1, 0);                 // SW1, pull-up
    PinMode(GPIOB, 2, 0, 1, 0);                  // SW2, pull-up (pin 17)

    // TIM3 PWM on PB0 (CH3, DIM_1) and PB1 (CH4, DIM_0), 12 kHz
    TIM3->PSC = 0;
    TIM3->ARR = 999;
    TIM3->CCMR2 = (6u << TIM_CCMR2_OC3M_Pos) | TIM_CCMR2_OC3PE
                | (6u << TIM_CCMR2_OC4M_Pos) | TIM_CCMR2_OC4PE;
    TIM3->CCER = TIM_CCER_CC3E | TIM_CCER_CC4E;
    Brightness(9);
    TIM3->CCR4 = 0;                              // DIM0 off until the polarity is known
    TIM3->EGR = TIM_EGR_UG;
    TIM3->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    PinMode(GPIOB, 0, 2, 0, 1);
    PinMode(GPIOB, 1, 2, 0, 1);

    // USART1 115200 8N1 on PA9/PA10, AF1
    USART1->CR1 = 0;
    USART1->BRR = 12000000u / 115200u;           // 104, 0.16 % fast
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE_RXFNEIE | USART_CR1_UE;
    PinMode(GPIOA, 9, 2, 0, 1);
    PinMode(GPIOA, 10, 2, 1, 1);                 // pull-up: idle high if the pair floats
    NVIC_EnableIRQ(USART1_IRQn);

    SysTick_Config(12000000u / 1000u);
}

static uint8_t sw;                               // bit0 SW1, bit1 SW2, 1 = pressed

static uint8_t ReadSw(void)
{
    return (uint8_t)(((GPIOC->IDR >> 15) & 1 ? 0 : 1) | ((GPIOB->IDR >> 2) & 1 ? 0 : 2));
}

static void TxSw(void)
{
    TxByte('S'); TxByte(sw & 1 ? '1' : '0'); TxByte(sw & 2 ? '1' : '0'); TxByte('\n');
}

static int HexVal(int c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

int main(void)
{
    Init();
    RestoreBoot();
    Decide(1);

    Lamps(LAMPS_ALL);                            // lamp test
    Delay(300);
    Lamps(0);

    sw = ReadSw();
    uint8_t swRaw = sw;
    uint32_t swT = ticks;
    char arg[6];
    int argN = 0;
    char mode = 0;                               // 'L', 'D', 'P' or '!' while collecting an argument
    uint32_t lamps = 0;

    for (;;)
    {
        // footswitches, 20 ms debounce, report on change
        uint8_t r = ReadSw();
        if (r != swRaw) { swRaw = r; swT = ticks; }
        else if (r != sw && (uint32_t)(ticks - swT) >= 20) { sw = r; TxSw(); }

        int c = RxGet();
        if (c < 0) continue;

        if (mode)
        {
            arg[argN++] = (char)c;
            if (mode == 'D')
            {
                if (c >= '0' && c <= '9') { Brightness(c - '0'); TxByte('D'); TxByte((char)c); TxByte('\n'); }
                mode = 0; argN = 0;
            }
            else if (mode == 'P')
            {
                int v = c == 'A' ? POL_CA : c == 'C' ? POL_CC : c == 'U' ? POL_NONE : -1;
                int err = 0;
                if (v >= 0)
                {
                    err = SettingWrite(v);
                    Decide(v == POL_NONE);       // "auto" probes again; the lamps come back after
                }
                if (v >= 0 || c == '?')
                {
                    if (err) TxStr("P ERR\n");
                    else { TxByte('P'); TxPol(); TxByte('\n'); }
                }
                mode = 0; argN = 0;
            }
            else if (mode == 'L' && argN == 4)
            {
                int v = 0, ok = 1;
                for (int i = 0; i < 4; i++) { int h = HexVal(arg[i]); if (h < 0) ok = 0; v = v << 4 | (h & 0xF); }
                if (ok) { lamps = (uint32_t)v & LAMPS_ALL; Lamps(lamps); TxByte('L'); TxHex(lamps, 4); TxByte('\n'); }
                mode = 0; argN = 0;
            }
            else if (mode == '!' && argN == 5)
            {
                if (arg[0] == 'B' && arg[1] == 'O' && arg[2] == 'O' && arg[3] == 'T' && arg[4] == '\n')
                {
                    TxStr("!BOOT\n");
                    EnterBootloader();
                }
                mode = 0; argN = 0;
            }
            continue;
        }

        switch (c)
        {
        case ':': lamps = LAMPS_ALL; Lamps(lamps); TxStr(":\n"); break;
        case '.': lamps = 0; Lamps(lamps); TxStr(".\n"); break;
        case 'V':
        {
            const uint32_t *uid = (const uint32_t *)UID_BASE;
            TxStr("P1 " P1_VERSION " uid=");
            TxHex(uid[2], 8); TxHex(uid[1], 8); TxHex(uid[0], 8);
            TxStr(" optr="); TxHex(FLASH->OPTR, 8);
            TxPol();
            TxStr(" probe="); TxStr(PR_NAME[probeRes]);
            TxStr(" adc=");
            for (int i = 0; i < 4; i++) { if (i) TxByte(','); TxHex(probeAdc[i], 3); }
            TxByte('\n');
            break;
        }
        case 'S': TxSw(); break;
        case 'L': case 'D': case 'P': case '!': mode = (char)c; argN = 0; break;
        default: break;
        }
    }
}
