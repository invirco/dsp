/*
 * pwr-mcu bootloader — first 4 KB, write-protected (WRP) once installed.
 * Validates the app image at 0x08001000 (magic + length header at +0x10,
 * zlib CRC32 appended at end) and jumps to it; on any failure it sits in a
 * triple-blink loop forever.
 *
 * RAIL POLICY (changed 2026-09-13): the board's passive default used to be
 * rails ON (pull-ups on UPS_EN / PSU_DIG_EN), so this code never touched the
 * rail pins and a corrupt app left the unit powered and reflashable. On
 * 2026-09-13 the pull-ups were lifted and pull-downs fitted (every U34 reset
 * had been floating the enables ON for the reset + bootloader window and
 * starting every buck — the standby-burst loop). The passive default is now
 * rails OFF, so the reflash property has to come from HERE: read the rocker
 * FIRST and drive UPS_EN/PSU_DIG_EN to match it — rocker ON → rails asserted
 * (the CM4 comes up and can reflash a corrupt app over SWD), rocker OFF →
 * rails driven low. The app's gpio_init() writes the same values, so the
 * takeover stays glitchless.
 *
 * Runs on reset-default HSI 8 MHz; the app does its own clock setup. The
 * Cortex-M0 has no VTOR: fine here, neither image uses interrupts. If a
 * future app needs them, remap vectors to SRAM via SYSCFG_CFGR1 MEM_MODE.
 */

#include <stdint.h>
#include "board.h"

#define APP_BASE   0x08001000u
#define APP_MAX    (12u * 1024u)
#define APP_MAGIC  0x4D583236u          /* 'MX26' */

void Boot_Reset(void);
static void Boot_Fault(void) { for (;;) { } }

__attribute__((section(".isr_vector"), used))
static const void *vectors[] = {
    (void *)0x20001000u,
    Boot_Reset,
    Boot_Fault,                          /* NMI */
    Boot_Fault,                          /* HardFault */
};

static uint32_t crc32(const uint8_t *p, uint32_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

/* triple-blink, pause, repeat = "no valid app" (LED only; the rails keep
   whatever rails_follow_rocker() set — ON with the rocker ON, for reflash) */
static void blink_forever(void)
{
    RCC_AHBENR |= (1u << 22);
    GPIO_MODER(GPIOF) = (GPIO_MODER(GPIOF) & ~(3u << 2)) | (1u << 2);
    for (;;) {
        for (int i = 0; i < 6; i++) {
            GPIO_ODR(GPIOF) ^= (1u << 1);
            for (volatile uint32_t d = 0; d < 100000u; d++) { }
        }
        for (volatile uint32_t d = 0; d < 800000u; d++) { }
    }
}

/* Rocker-gated rail defaults: PF0 low = rocker ON (external 10K pull-up).
   Data first, then direction — the same order and values as the app. */
static void rails_follow_rocker(void)
{
    RCC_AHBENR |= (1u << 17) | (1u << 22);                    /* GPIOA, GPIOF */
    (void)RCC_AHBENR;                                          /* clock settle */
    int rocker_on = !((GPIO_IDR(GPIOF) >> 0) & 1u);
    GPIO_ODR(GPIOA) = rocker_on ? ((1u << 2) | (1u << 3)) : 0u;
    GPIO_MODER(GPIOA) = (GPIO_MODER(GPIOA) & ~((3u << 4) | (3u << 6)))
                      |  ((1u << 4) | (1u << 6));             /* PA2, PA3 out */
}

void Boot_Reset(void)
{
    rails_follow_rocker();
    const uint32_t *app = (const uint32_t *)APP_BASE;
    uint32_t magic = app[4];             /* +0x10 */
    uint32_t len   = app[5];             /* +0x14, patched by mkimage.py */

    if (magic == APP_MAGIC &&
        len >= 0x20u && len <= APP_MAX - 4u && (len & 3u) == 0u &&
        crc32((const uint8_t *)APP_BASE, len) ==
            *(const uint32_t *)(APP_BASE + len)) {
        uint32_t sp = app[0];
        uint32_t pc = app[1];
        __asm volatile("msr msp, %0 \n bx %1" :: "r"(sp), "r"(pc));
    }
    blink_forever();
}
