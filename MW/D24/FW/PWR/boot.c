/*
 * pwr-mcu bootloader — first 4 KB, write-protected (WRP) once installed.
 *
 * ORDER AT RESET (2026-10-15):
 *  1. RAILS FIRST. Read the rocker (PF0) and drive UPS_EN/PSU_DIG_EN to match
 *     before anything else, so the hi-Z window of any reset (SYSRESETREQ from
 *     a hot-attach flash, ENTER_BOOT, NRST) ends within microseconds of the
 *     core starting. Rocker OFF -> both driven low. Rocker ON -> both
 *     asserted, EXCEPT after a power-on/brown-out reset (PORRSTF): then the
 *     rails were off, so PSU_DIG_EN is held low for CFG_DIG_STAGGER_MS after
 *     UPS_EN (staggered enables, errata STAGGERED ENABLES). A warm reset never
 *     staggers: the rails were up, and dropping PSU_DIG_EN would glitch them.
 *     On rocker-follow boards (rev C hand mod, rev D copper) the 3V3_SW
 *     pull-ups hold both enables high while the part is in reset, so after a
 *     POR the digital bucks see EN high for the reset temporization before
 *     this code pulls PSU_DIG_EN down — see report-2026-10-15.md.
 *  2. Mailbox (top of SRAM): the app's ENTER_BOOT asks to stay here.
 *  3. App valid (magic + length header at +0x10, CRC32 at +len) and not
 *     asked to stay -> jump. Otherwise UPDATE MODE.
 *
 * UPDATE MODE (option 2): the host link on AN_EN/PI_SD (link.h, proto.h,
 * bootcmd.c) erases, writes, reads back and checks the app region, then GO.
 * The LED shows why it is here: triple blink = no valid app (the safe loop
 * of 2026-08-18), double blink = asked by the app. The rails keep following
 * the rocker (debounced, staggered) — the same thing the rocker-follow
 * hardware would do with the part in reset; there is no app here to run an
 * orderly save, so do not switch off during a U34 update. A requested
 * session left idle for CFG_BOOT_IDLE_MS returns to a valid app.
 *
 * Runs on reset-default HSI 8 MHz; TIM17 counts microseconds. No .data or
 * .bss (boot.ld asserts it): all state is on the stack. The Cortex-M0 has no
 * VTOR; neither image uses interrupts.
 */

#include <stdint.h>
#include "board.h"
#include "config.h"
#include "link.h"
#include "bootcmd.h"
#include "proto.h"

void Boot_Reset(void);
static void Boot_Fault(void) { for (;;) { } }

__attribute__((section(".isr_vector"), used))
static const void *vectors[] = {
    (void *)MAILBOX_ADDR,                /* stack top sits under the mailbox */
    Boot_Reset,
    Boot_Fault,                          /* NMI */
    Boot_Fault,                          /* HardFault */
};

static uint16_t us(void) { return (uint16_t)TIM_CNT(TIM17); }

static void timer_init(void)
{
    RCC_APB2ENR |= (1u << 18);           /* TIM17 */
    TIM_PSC(TIM17) = 7u;                 /* 8 MHz HSI -> 1 us */
    TIM_ARR(TIM17) = 0xFFFFu;
    TIM_EGR(TIM17) = 1u;                 /* load PSC now */
    TIM_CR1(TIM17) = 1u;
}

static void delay_ms(uint32_t n)
{
    while (n--) { uint16_t t0 = us(); while ((uint16_t)(us() - t0) < 1000u) { } }
}

static int rocker_on(void) { return !(GPIO_IDR(GPIOF) & 1u); }

static void rails(int ups, int dig)
{
    GPIO_BSRR(GPIOA) = (ups ? (1u << 2) : (1u << 18)) | (dig ? (1u << 3) : (1u << 19));
}

/* Data first, then direction — glitchless against the passive default. */
static void rails_follow_rocker(void)
{
    RCC_AHBENR |= (1u << 17) | (1u << 22);                    /* GPIOA, GPIOF */
    (void)RCC_AHBENR;                                          /* clock settle */
    int on  = rocker_on();
    int por = (RCC_CSR & CSR_PORRSTF) != 0u;
    rails(on, on && !por);
    GPIO_MODER(GPIOA) = (GPIO_MODER(GPIOA) & ~((3u << 4) | (3u << 6)))
                      |  ((1u << 4) | (1u << 6));             /* PA2, PA3 out */
    if (on && por) {
        timer_init();
        delay_ms(CFG_DIG_STAGGER_MS);
        rails(1, 1);
    }
}

/* ---- flash hooks for bootcmd.c ------------------------------------- */
const uint8_t *bh_app(void) { return (const uint8_t *)APP_BASE; }

static void fl_unlock(void)
{
    if (FLASH_CR & (1u << 7)) { FLASH_KEYR = 0x45670123u; FLASH_KEYR = 0xCDEF89ABu; }
    while (FLASH_SR & 1u) { }
}

static int fl_finish(uint32_t mode_bit)
{
    while (FLASH_SR & 1u) { }
    uint32_t sr = FLASH_SR;
    FLASH_SR = (1u << 5) | (1u << 4) | (1u << 2);              /* clear EOP/WRPRT/PG */
    FLASH_CR &= ~mode_bit;
    FLASH_CR |= (1u << 7);                                     /* LOCK */
    return (sr & ((1u << 4) | (1u << 2))) != 0u;
}

int bh_erase(uint32_t page)
{
    if (page >= APP_MAX / FLASH_PAGE) return 1;
    fl_unlock();
    FLASH_CR |= 2u;                                            /* PER */
    FLASH_AR = APP_BASE + page * FLASH_PAGE;
    FLASH_CR |= (1u << 6);                                     /* STRT */
    return fl_finish(2u);
}

int bh_prog16(uint32_t off, uint16_t v)
{
    if (off >= APP_MAX) return 1;
    fl_unlock();
    FLASH_CR |= 1u;                                            /* PG */
    *(volatile uint16_t *)(APP_BASE + off) = v;
    return fl_finish(1u);
}

/* ---- update mode ---------------------------------------------------- */
static void update_mode(uint8_t reason)
{
    struct link lk;
    uint32_t ms = 0, last_rx = 0, rk_t = 0, dig_due = 0;
    uint16_t tms;
    int start = 0, rk, rk_raw, dig_pending = 0;
    uint32_t alen, acrc;

    RCC_CSR |= (1u << 24);               /* RMVF: no app will log this boot */
    timer_init();
    GPIO_BSRR(GPIOA) = 1u << (5 + 16);                         /* PI_SD low */
    GPIO_PUPDR(GPIOA) = (GPIO_PUPDR(GPIOA) & ~(3u << 20)) | (2u << 20);  /* PA10 pd */
    GPIO_MODER(GPIOA) = (GPIO_MODER(GPIOA) & ~((3u << 10) | (3u << 20))) | (1u << 10);
    GPIO_BSRR(GPIOF) = 1u << (1 + 16);
    GPIO_MODER(GPIOF) = (GPIO_MODER(GPIOF) & ~(3u << 2)) | (1u << 2);   /* PF1 LED */

    tms = us();
    link_init(&lk, tms, (GPIO_IDR(GPIOA) >> 10) & 1u);
    rk = rk_raw = rocker_on();

    for (;;) {
        uint16_t t = us();
        int o = link_step(&lk, t, (GPIO_IDR(GPIOA) >> 10) & 1u);
        GPIO_BSRR(GPIOA) = o ? (1u << 5) : (1u << (5 + 16));
        if ((uint16_t)(t - tms) >= 1000u) { tms += 1000u; ms++; }

        uint8_t c, n;
        const uint8_t *p;
        if (link_rx(&lk, &c, &n, &p)) {
            start |= bootcmd(&lk, c, n, p, reason, rk);
            link_rx_done(&lk);
            last_rx = ms;
        }
        if (start && !link_tx_busy(&lk)) break;

        /* LED: 2 or 3 blinks of 100 ms, then a pause; 1.6 s cycle */
        uint32_t ph = ms % 1600u;
        uint32_t nb = reason == REASON_NO_APP ? 3u : 2u;
        GPIO_BSRR(GPIOF) = (ph < nb * 200u && (ph % 200u) < 100u) ? (1u << 1) : (1u << 17);

        /* rails keep following the rocker */
        int raw = rocker_on();
        if (raw != rk_raw) { rk_raw = raw; rk_t = ms; }
        if (raw != rk && ms - rk_t >= CFG_ROCKER_DEBOUNCE_MS) {
            rk = raw;
            rails(rk, 0);
            dig_pending = rk;
            dig_due = ms + CFG_DIG_STAGGER_MS;
        }
        if (dig_pending && (int32_t)(ms - dig_due) >= 0) { rails(1, 1); dig_pending = 0; }

        /* a requested session the host abandoned goes back to the app */
        if (reason == REASON_REQUESTED && ms - last_rx >= CFG_BOOT_IDLE_MS &&
            !link_tx_busy(&lk) && boot_app_valid(bh_app(), &alen, &acrc))
            break;
    }
    GPIO_BSRR(GPIOA) = 1u << (5 + 16);
    GPIO_BSRR(GPIOF) = 1u << (1 + 16);
}

static void start_app(void)
{
    const uint32_t *app = (const uint32_t *)APP_BASE;
    __asm volatile("msr msp, %0 \n bx %1" :: "r"(app[0]), "r"(app[1]));
}

void Boot_Reset(void)
{
    rails_follow_rocker();

    int requested = MAILBOX[0] == MAILBOX_UPDATE && MAILBOX[1] == ~MAILBOX_UPDATE;
    MAILBOX[0] = 0u;
    MAILBOX[1] = 0u;

    uint32_t alen, acrc;
    if (!requested && boot_app_valid(bh_app(), &alen, &acrc))
        start_app();
    update_mode(requested ? REASON_REQUESTED : REASON_NO_APP);
    start_app();                         /* update_mode returns only on a valid app */
    for (;;) { }
}
