// P1 foot pedal application -- S167, for the P1 rev B serial-program mod.
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
// LAMPS are active low (cathode to the pin). Their supplies are switched high
// side: DIM_0 = PB1 (TIM3_CH4) -> Q1/Q3 -> DIM0, the 7-segment common anode;
// DIM_1 = PB0 (TIM3_CH3) -> Q2/Q4 -> DIM1, LD1..LD8. Nothing lights unless
// TIM3 drives them, which the 2025-12-30 stub never did.
//
// PROTOCOL, 115200 8N1, one byte commands unless shown:
//   ':'          all lamps on, reply ":\n"          (the stub's behaviour, kept)
//   '.'          all lamps off, reply ".\n"
//   'V'          reply "P1 <version> uid=<24 hex> optr=<8 hex>\n"
//   'S'          reply "S<sw1><sw2>\n", 1 = pressed; also sent on every change
//   'L' + 4 hex  lamp bitmap (bit order below), reply "L<4 hex>\n"
//   'D' + digit  brightness 0..9 (0 = off, 9 = full), reply "D<d>\n"
//   "!BOOT\n"    reply "!BOOT\n", then option bytes nBOOT_SEL=1 nBOOT1=1
//                nBOOT0=0 and reload: the next start is the ROM bootloader.
// At power-up every lamp lights for 300 ms (lamp test), then all go off.
// If the application starts with nBOOT0=0 (the ROM's Go after an update) it
// restores nBOOT0=1 and reloads the option bytes, so the update is undone by
// nothing but a successful start of the new image.

#include "stm32c031xx.h"

#ifndef SEG_CC
#define SEG_CC 0                                 // 1: common-CATHODE display (FJ8102AY on the
                                                 // first rev B pedal), DIM0 tied to GND, Q3 out
#endif
#if SEG_CC
#define P1_VERSION "1.0-s167-cc"
#else
#define P1_VERSION "1.0-s167"
#endif

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

static volatile uint32_t ticks;
static volatile uint32_t lampMap;                // what Lamps() was last asked for
static volatile int segLevel = 9;                // SEG_CC: software dimming of the segments
static volatile uint8_t rxBuf[64];
static volatile uint8_t rxHead, rxTail;

static void LampsDrive(uint32_t map, int segsOn);

void SysTick_Handler(void)
{
    ticks++;
#if SEG_CC
    // 100 Hz, ten steps: the segments have no switched rail to PWM any more
    int phase = (int)(ticks % 10);
    LampsDrive(lampMap, phase < segLevel);
#endif
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

// LD1..LD4 (bits 0-3) are always active low on the DIM1 rail. The segments
// (bits 4-12) are active low on the DIM0 rail (common anode), or with SEG_CC
// active HIGH into a common cathode tied to GND.
static void LampsDrive(uint32_t map, int segsOn)
{
    for (int i = 0; i < 13; i++)
    {
        uint32_t bit = 1u << LAMP[i].pin;
        int on = (map >> i) & 1;
        if (SEG_CC && i >= 4)
            LAMP[i].port->BSRR = (on && segsOn) ? bit : (bit << 16);  // high = lit
        else
            LAMP[i].port->BSRR = on ? (bit << 16) : bit;               // low = lit
    }
}

static void Lamps(uint32_t map)
{
    lampMap = map;
    LampsDrive(map, 1);
}

static void Brightness(int level)                // 0..9
{
    uint32_t ccr = (level >= 9) ? 1000 : (uint32_t)level * 100;
    TIM3->CCR3 = ccr;                            // DIM_1, LD1..LD8
    TIM3->CCR4 = SEG_CC ? 0 : ccr;               // DIM_0, 7-segment (Q1 off when Q3 is out)
    segLevel = level;
}

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

    // lamps: outputs, high (off) first so nothing flashes on the way out
    for (int i = 0; i < 13; i++)
        LAMP[i].port->BSRR = (SEG_CC && i >= 4) ? (1u << (LAMP[i].pin + 16)) : (1u << LAMP[i].pin);
    for (int i = 0; i < 13; i++) PinMode(LAMP[i].port, LAMP[i].pin, 1, 0, 0);

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

static void Delay(uint32_t ms)
{
    uint32_t t0 = ticks;
    while ((uint32_t)(ticks - t0) < ms) { }
}

static int FlashOptWrite(uint32_t optr)
{
    if (FLASH->CR & FLASH_CR_LOCK) { FLASH->KEYR = 0x45670123u; FLASH->KEYR = 0xCDEF89ABu; }
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

    Lamps(LAMPS_ALL);                            // lamp test
    Delay(300);
    Lamps(0);

    sw = ReadSw();
    uint8_t swRaw = sw;
    uint32_t swT = ticks;
    char arg[6];
    int argN = 0;
    char mode = 0;                               // 'L', 'D' or '!' while collecting an argument
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
            TxByte('\n');
            break;
        }
        case 'S': TxSw(); break;
        case 'L': case 'D': case '!': mode = (char)c; argN = 0; break;
        default: break;
        }
    }
}
