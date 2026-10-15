/*
 * D24 power-MCU firmware skeleton — behavior contract from
 * src/fw/d24-pwr-mcu-def.csv (fn.* rows) as confirmed 2026-08-18.
 *
 * States: STANDBY -> BOOT -> ON -> SHUTDOWN -> STANDBY.
 * Rocker (PF0) is level-sensed: low = requested ON. The unified shutdown
 * sequence serves both triggers (rocker to OFF | 12 V fail) and always runs
 * to completion — a mid-sequence rocker/12 V reversal reboots from STANDBY
 * afterwards, never aborts a save.
 *
 * Takeover is glitchless: output data values are written before the pins
 * become outputs — the rails get the ROCKER's value (2026-09-13: driving
 * them high unconditionally made every reset pulse the rails).
 * No interrupts; superloop on a polled 1 ms SysTick. Between ticks the
 * host link (link.h: frames on AN_EN, replies on PI_SD) is polled against
 * TIM17's 1 us count. The app sits at 0x08001000 behind the WRP bootloader
 * (boot.c), which drives the rails before this code ever runs.
 *
 * 2026-10-15: host link commands (proto.h) — PING, ENTER_BOOT (option 2
 * update), and the rev D J8 pedal supply (p1.c: sense before enable,
 * heartbeat re-clamp, UPDATE HOLD, power-cycle). AN_EN's analog request is
 * its level held CFG_ANEN_STABLE_MS. One image for rev C and rev D.
 */

#include "config.h"
#include "board.h"
#include "link.h"
#include "proto.h"
#include "p1.h"

/* ---- vectors ------------------------------------------------------- */
void Reset_Handler(void);
static void Fault_Handler(void) { for (;;) { } }

__attribute__((section(".isr_vector"), used))
static const void *vectors[] = {
    (void *)MAILBOX_ADDR,       /* initial SP: under the boot mailbox */
    Reset_Handler,
    Fault_Handler,              /* NMI */
    Fault_Handler,              /* HardFault */
};

/* App image header at +0x10, right after the 4-entry vector table — the
   bootloader validates this. len is patched by mkimage.py, which also
   appends the CRC32. */
__attribute__((section(".app_header"), used))
static const uint32_t app_header[2] = { 0x4D583236u /* 'MX26' */, 0u };

/* ---- state --------------------------------------------------------- */
enum state { ST_STANDBY, ST_BOOT, ST_ON, ST_SHUTDOWN };
enum trigger { TRIG_NONE, TRIG_SWITCH, TRIG_FAIL };

static enum state    state;
static enum trigger  shdn_trigger;
static uint32_t      ms;                 /* monotonic 1 ms tick */
static uint32_t      state_entry_ms;

/* debounced inputs */
static uint32_t rocker_stable_ms, mhrx_low_ms, anen_low_ms;
static uint32_t mhrx_high_ms;                    /* last ms MHRX read low: Pi is
                                                    "up" once it has stayed high
                                                    for CFG_MHRX_UP_MS */
static int      rocker_raw_prev, rocker_on;      /* debounced level      */
static int      v12_ok = 1;                      /* hysteresis output    */
static int      anen_level;                      /* AN_EN's level, held
                                                    CFG_ANEN_STABLE_MS: the
                                                    analog request (frame
                                                    pulses never reach it) */
static uint32_t anen_level_ms;                   /* last ms it agreed */
static struct link lk;                           /* host link (link.h) */
static struct p1   ped;                          /* J8 pedal supply (p1.h) */
static int      pi_sd_req;                       /* PI_SD = save-and-shutdown */
static int      enter_boot_pending;              /* ENTER_BOOT acked: reset
                                                    once the reply is out */
static int      mhrx_seen_high;                  /* guards a stuck-low MHRX
                                                    sense: a low only counts
                                                    as the Pi-off ack after
                                                    the Pi was seen alive */
static int      anen_seen_high;                  /* AN_EN as a second Pi-off
                                                    ack: MHRX is shared with
                                                    the DSP board, where a
                                                    blank CPLD's weak pull-ups
                                                    can hold it high after the
                                                    Pi halts (bench 2026-08-18:
                                                    60 s failsafe with card
                                                    fitted). AN_EN never leaves
                                                    the digital board. */

/* ---- reset log (diagnostic, 2026-09-13) ------------------------------
   With the rocker OFF the bench saw NRST toggling every 50–100 ms and a
   rail burst every 10–15 resets. This records WHY each reset happened:
   RCC_CSR[31:24] = LPWR WWDG IWDG SFT POR PIN OBL V18PWR. Lives in .noinit
   so it survives every reset except a real power-on; read it from the CM4
   over SWD:  openocd ... -c "init" -c "mdw 0x20000000 20" -c "shutdown"
   word0 = magic 0x52534C47 ('RSLG'), word1 = reset count since power-on,
   word2 = last RCC_CSR, words 3..18 = ring of the last 16 RCC_CSR values
   (index = count & 15), word19 = the ms count the PREVIOUS run reached. */
#define RSLG_MAGIC 0x52534C47u
struct reset_log { uint32_t magic, count, last, ring[16], prev_ms; };
__attribute__((section(".noinit"), used)) static struct reset_log rslg;
static void reset_log_record(void)
{
    uint32_t csr = RCC_CSR;
    if (rslg.magic != RSLG_MAGIC) { rslg.magic = RSLG_MAGIC; rslg.count = 0; rslg.prev_ms = 0; }
    rslg.last = csr;
    rslg.ring[rslg.count & 15u] = csr;
    rslg.count++;
    RCC_CSR = csr | (1u << 24);                /* RMVF: one cause per reset */
}

/* shutdown sequencing */
static uint32_t clk12_stop_ms;
static int      clk48_stopped;
static int      pi_alive_at_entry;               /* MHRX or AN_EN high when the
                                                    shutdown began; if the Pi was
                                                    already off, no ack is owed */

/* ---- low-level helpers --------------------------------------------- */
static void pin_high(uint32_t port, int pin) { GPIO_BSRR(port) = 1u << pin; }
static void pin_low(uint32_t port, int pin)  { GPIO_BSRR(port) = 1u << (pin + 16); }
static int  pin_read(uint32_t port, int pin) { return (GPIO_IDR(port) >> pin) & 1u; }

#ifdef BENCH_SAFE
/* rails may only be asserted, never cut — see config.h */
static void rail_ups(int on)  { if (on) pin_high(GPIOA, 2); }
static void rail_dig(int on)  { if (on) pin_high(GPIOA, 3); }
#else
static void rail_ups(int on)  { if (on) pin_high(GPIOA, 2); else pin_low(GPIOA, 2); }
static void rail_dig(int on)  { if (on) pin_high(GPIOA, 3); else pin_low(GPIOA, 3); }
#endif

/* PSU sync clocks: CCR=0 parks the pin low ("no clock = rail off") */
static void clk12(int on) { TIM_CCR1(TIM14) = on ? 8u : 0u; }   /* 20% (instant; the up direction uses the ramp) */
static void clk48(int on) { TIM_CCR4(TIM3)  = on ? 32u : 0u; }  /* 80% (instant; the up direction uses the ramp) */
static uint32_t clk12_step_ms, clk48_step_ms;
/* Duty ramps (PW 2026-09-15): called every tick while analog power is wanted.
   12CLK: 0 -> START, then +1 compare per step until 8. 48CLK: waits for 12CLK
   at full duty (phantom last up), then 0 -> START, +1 per step until 32. */
static void clk12_ramp(void)
{
    uint32_t c = TIM_CCR1(TIM14);
    if (c == 0u) { TIM_CCR1(TIM14) = CFG_CLK12_RAMP_START; clk12_step_ms = ms; }
    else if (c < 8u && ms - clk12_step_ms >= CFG_CLK12_RAMP_MS / (8u - CFG_CLK12_RAMP_START)) {
        TIM_CCR1(TIM14) = c + 1u; clk12_step_ms = ms;
    }
}
static void clk48_ramp(void)
{
    uint32_t c = TIM_CCR4(TIM3);
    if (TIM_CCR1(TIM14) < 8u) return;                 /* +/-15 V first */
    if (c == 0u) { TIM_CCR4(TIM3) = CFG_CLK48_RAMP_START; clk48_step_ms = ms; }
    else if (c < 32u && ms - clk48_step_ms >= CFG_CLK48_RAMP_MS / (32u - CFG_CLK48_RAMP_START)) {
        TIM_CCR4(TIM3) = c + 1u; clk48_step_ms = ms;
    }
}
static uint32_t ups_on_ms;                            /* when UPS_EN went high from standby */

static void led(int on) { if (on) pin_high(GPIOF, 1); else pin_low(GPIOF, 1); }
static void led_blink(uint32_t period_ms) { led((ms / period_ms) & 1u); }

/* ---- init ---------------------------------------------------------- */
static void clock_init(void)
{
    /* 40 MHz: HSI/2 x10 — gives integer 1 MHz PWM with 20%/80% duty */
    FLASH_ACR = (FLASH_ACR & ~7u) | 1u | (1u << 4);   /* 1 WS + prefetch */
    RCC_CFGR  = (RCC_CFGR & ~(0xFu << 18)) | (8u << 18);  /* PLLMUL x10 */
    RCC_CR   |= (1u << 24);                            /* PLLON */
    while (!(RCC_CR & (1u << 25))) { }                 /* PLLRDY */
    RCC_CFGR  = (RCC_CFGR & ~3u) | 2u;                 /* SYSCLK = PLL */
    while ((RCC_CFGR & (3u << 2)) != (2u << 2)) { }

    SYST_RVR = 40000u - 1u;                            /* 1 ms tick */
    SYST_CSR = 5u;                                     /* enable, core clock */
}

static void gpio_init(void)
{
    RCC_AHBENR |= (1u << 17) | (1u << 18) | (1u << 22);   /* A, B, F */

    /* RESET-SAFE RAIL DEFAULTS (bench 2026-09-13): with the rocker OFF the
       unit drew a ~5 ms multi-amp burst once a second — UPS_EN/PSU_DIG_EN
       went high just before each one. Every reset of this MCU pulsed the
       rails: in reset the pins are hi-Z and the board pull-ups float both
       enables ON, then this function drove them HIGH before the rocker was
       ever read, and only standby_outputs() after clock/PWM/ADC init took
       them low. With 12 V absent that loop fed itself (UPS_EN off → +5V_PI
       boost off → +3V3ON decays → brown-out reset → pins float → boost on
       → boot → ...) off the supercap. So: read the rocker FIRST and give
       the enables the value the state machine is about to want. Rocker ON
       → rails asserted (matches the passive default: glitchless takeover);
       rocker OFF → rails driven LOW as the very first output action. The
       residual window while NRST is asserted (pins hi-Z) cannot be closed
       in firmware — rev C makes the enables default OFF (errata CHANGE 3). */
    int rocker_now = !pin_read(GPIOF, 0);                /* low = ON */
    GPIO_ODR(GPIOA) = (rocker_now ? ((1u << 2) | (1u << 3)) : 0u)
                    | (1u << 6);                          /* P1_EN high = clamped */
    GPIO_ODR(GPIOF) = 0;                                  /* LED off */

    /* pull-downs on the two Pi-driven inputs (float when Pi is off) and on
       PA7 P1_SENSE (rev C: N/C, so it reads 0 = "no pedal") */
    GPIO_PUPDR(GPIOA) = (GPIO_PUPDR(GPIOA)
        & ~((3u << (0 * 2)) | (3u << (7 * 2)) | (3u << (10 * 2))))
        |  ((2u << (0 * 2)) | (2u << (7 * 2)) | (2u << (10 * 2)));

    /* PA1 analog; PA2/3/5/6/9 out; PA4 AF; PA0/PA7/PA10 in; SWD untouched */
    GPIO_MODER(GPIOA) = (GPIO_MODER(GPIOA)
        & ~((3u << 2) | (3u << 4) | (3u << 6) | (3u << 8) | (3u << 10)
          | (3u << 12) | (3u << 14) | (3u << 18)))
        |  ((3u << 2)                                   /* PA1 analog   */
          | (1u << 4) | (1u << 6)                       /* PA2,PA3 out  */
          | (2u << 8)                                   /* PA4 AF       */
          | (1u << 10)                                  /* PA5 out      */
          | (1u << 12)                                  /* PA6 out      */
          | (1u << 18));                                /* PA9 out      */
    GPIO_AFRL(GPIOA) = (GPIO_AFRL(GPIOA) & ~(0xFu << 16)) | (4u << 16); /* PA4 AF4 */

    GPIO_MODER(GPIOB) = (GPIO_MODER(GPIOB) & ~(3u << 2)) | (2u << 2);   /* PB1 AF */
    GPIO_AFRL(GPIOB) = (GPIO_AFRL(GPIOB) & ~(0xFu << 4)) | (1u << 4);   /* AF1 */

    GPIO_MODER(GPIOF) = (GPIO_MODER(GPIOF) & ~(3u << 2)) | (1u << 2);   /* PF1 out */
}

static void pwm_init(void)
{
    RCC_APB1ENR |= (1u << 1) | (1u << 8);      /* TIM3, TIM14 */

    TIM_PSC(TIM14)   = 0;                      /* 40 MHz / 40 = 1 MHz */
    TIM_ARR(TIM14)   = 39u;
    TIM_CCR1(TIM14)  = 0;                      /* parked low */
    TIM_CCMR1(TIM14) = (6u << 4) | (1u << 3);  /* PWM1 + preload */
    TIM_CCER(TIM14)  = 1u;
    TIM_CR1(TIM14)   = 1u;

    TIM_PSC(TIM3)    = 0;
    TIM_ARR(TIM3)    = 39u;
    TIM_CCR4(TIM3)   = 0;
    TIM_CCMR2(TIM3)  = (6u << 12) | (1u << 11);
    TIM_CCER(TIM3)   = (1u << 12);
    TIM_CR1(TIM3)    = 1u;

    /* TIM17: free-running 1 us count for the host link */
    RCC_APB2ENR     |= (1u << 18);
    TIM_PSC(TIM17)   = 39u;                    /* 40 MHz -> 1 MHz */
    TIM_ARR(TIM17)   = 0xFFFFu;
    TIM_EGR(TIM17)   = 1u;
    TIM_CR1(TIM17)   = 1u;
}

static void adc_init(void)
{
    RCC_APB2ENR |= (1u << 9);
    ADC_CR |= (1u << 31);                      /* ADCAL */
    while (ADC_CR & (1u << 31)) { }
    ADC_CR |= 1u;                              /* ADEN */
    while (!(ADC_ISR & 1u)) { }
    ADC_CHSELR = (1u << 1);                    /* ch1 = PA1 = SENS_12V */
    ADC_SMPR   = 7u;                           /* longest sample time */
}

static uint32_t adc_read(void)
{
    ADC_CR |= (1u << 2);                       /* ADSTART */
    while (!(ADC_ISR & (1u << 2))) { }         /* EOC */
    return ADC_DR;
}

/* ---- J8 pedal supply hooks (p1.h) ------------------------------------ */
void p1_hw_enable(int on) { if (on) pin_low(GPIOA, 6); else pin_high(GPIOA, 6); }

void p1_hw_discharge(int on)
{
    if (on) {
        pin_low(GPIOA, 7);
        GPIO_MODER(GPIOA) = (GPIO_MODER(GPIOA) & ~(3u << 14)) | (1u << 14);
    } else {
        GPIO_MODER(GPIOA) &= ~(3u << 14);      /* input, pull-down */
    }
}

/* analog only for the conversion; the pull-down holds the pin otherwise */
uint16_t p1_hw_adc(void)
{
    GPIO_MODER(GPIOA) |= (3u << 14);
    ADC_CHSELR = (1u << 7);
    uint32_t v = adc_read();
    ADC_CHSELR = (1u << 1);
    GPIO_MODER(GPIOA) &= ~(3u << 14);
    return (uint16_t)v;
}

/* ---- debounced inputs ---------------------------------------------- */
static void inputs_tick(void)
{
    /* rocker: level with contact-bounce filter */
    int raw = !pin_read(GPIOF, 0);             /* low = ON */
    if (raw != rocker_raw_prev) { rocker_stable_ms = ms; rocker_raw_prev = raw; }
    if (ms - rocker_stable_ms >= CFG_ROCKER_DEBOUNCE_MS) rocker_on = raw;

    /* 12 V with hysteresis */
    uint32_t code = adc_read();
    if (v12_ok)  { if (code < CFG_SENS12_FAIL_CODE) v12_ok = 0; }
    else         { if (code > CFG_SENS12_OK_CODE)   v12_ok = 1; }

    /* Pi-off trackers (consumed only in ST_SHUTDOWN): sustained low on
       either MHRX or AN_EN counts, each gated on having seen the Pi alive */
    if (pin_read(GPIOA, 0))  { mhrx_low_ms = ms; mhrx_seen_high = 1; }
    else                     { mhrx_high_ms = ms; }
    if (pin_read(GPIOA, 10)) { anen_low_ms = ms; anen_seen_high = 1; }

    /* the analog request: the link's idle level (pulses removed), held */
    if (lk.idle == anen_level)                          anen_level_ms = ms;
    else if (ms - anen_level_ms >= CFG_ANEN_STABLE_MS)  anen_level = lk.idle;
}

/* ---- host link -------------------------------------------------------- */
static void link_poll(void)
{
    int o = link_step(&lk, (uint16_t)TIM_CNT(TIM17), pin_read(GPIOA, 10));
    GPIO_BSRR(GPIOA) = (pi_sd_req || o) ? (1u << 5) : (1u << (5 + 16));
    if (enter_boot_pending && !link_tx_busy(&lk)) {
        p1_hw_enable(0);
        MAILBOX[0] = MAILBOX_UPDATE;
        MAILBOX[1] = ~MAILBOX_UPDATE;
        __asm volatile("dsb");
        SCB_AIRCR = AIRCR_SYSRESETREQ;
        for (;;) { }
    }
}

static int clocks_running(void) { return TIM_CCR1(TIM14) != 0u || TIM_CCR4(TIM3) != 0u; }

static void link_cmd(void)
{
    uint8_t c, n;
    const uint8_t *p;
    if (!link_rx(&lk, &c, &n, &p)) return;
    if (state != ST_BOOT && state != ST_ON) { link_rx_done(&lk); return; }  /* Pi not up */

    uint8_t r[20];
    uint8_t rn = 1;
    r[0] = ST_OK;
    switch (c) {
    case CMD_PING: {
        uint32_t odr = GPIO_ODR(GPIOA);
        uint32_t hl = (p1_hold_left_ms(&ped, ms) + 999u) / 1000u;
        r[1] = MODE_APP; r[2] = FW_VERSION_MAJOR; r[3] = FW_VERSION_MINOR;
        r[4] = (uint8_t)state;
        r[5] = (uint8_t)((rocker_on ? 1u : 0u) | (v12_ok ? 2u : 0u) | (anen_level ? 4u : 0u)
             | (clocks_running() ? 8u : 0u) | ((odr >> 2) & 1u) << 4 | ((odr >> 3) & 1u) << 5);
        r[6] = ped.state; r[7] = ped.why; r[8] = (uint8_t)hl;
        r[9] = (uint8_t)(ped.early >> 8); r[10] = (uint8_t)ped.early;
        r[11] = (uint8_t)(ped.late >> 8); r[12] = (uint8_t)ped.late;
        r[13] = (uint8_t)ped.probes; r[14] = (uint8_t)ped.enables; r[15] = (uint8_t)ped.reclamps;
        r[16] = (uint8_t)rslg.count;
        rn = 17;
        break;
    }
    case CMD_P1_ALIVE:   r[0] = (uint8_t)p1_alive(&ped, ms); break;
    case CMD_P1_HOLD:    r[0] = n == 1 ? (uint8_t)p1_hold(&ped, ms, p[0]) : ST_BAD_ARG; break;
    case CMD_P1_RELEASE: r[0] = (uint8_t)p1_release(&ped, ms); break;
    case CMD_P1_CYCLE:
        r[0] = n == 2 ? (uint8_t)p1_cycle(&ped, ms, ((uint32_t)p[0] << 8) | p[1]) : ST_BAD_ARG;
        break;
    case CMD_ENTER_BOOT:
        if (n != 4 || p[0] != 'B' || p[1] != 'O' || p[2] != 'O' || p[3] != 'T') r[0] = ST_BAD_ARG;
        else if (clocks_running()) r[0] = ST_REFUSED;    /* AN_EN low first */
        else enter_boot_pending = 1;
        break;
    default:
        r[0] = ST_UNKNOWN;
        break;
    }
    link_rx_done(&lk);
    link_send(&lk, (uint8_t)(c | 0x80u), r, rn);
}

/* ---- state machine -------------------------------------------------- */
static void enter(enum state s) { state = s; state_entry_ms = ms; }

static void enter_shutdown(enum trigger t)
{
    shdn_trigger = t;
    /* If the Pi is already off when the shutdown begins (a `poweroff`
       before the rocker, or a unit that never booted it), no Pi-off ack
       can ever arrive: MHRX/AN_EN were never seen high this sequence and
       only the 60 s failsafe exits (bench 2026-09-12). Snapshot it. */
    pi_alive_at_entry = pin_read(GPIOA, 0) || pin_read(GPIOA, 10);
    clk12(0);                                  /* ±15 V ramp down first */
    clk12_stop_ms = ms;
    clk48_stopped = 0;
    if (t == TRIG_FAIL || !CFG_KEEP_DIG_ON_SWITCH_OFF)
        rail_dig(0);                           /* shed load immediately */
    pin_low(GPIOA, 9);                         /* PWR_FAIL: radios off */
    pi_sd_req = 1;                             /* PI_SD: app saves     */
    mhrx_low_ms = ms;
    anen_low_ms = ms;
    mhrx_seen_high = 0;
    anen_seen_high = 0;
    enter(ST_SHUTDOWN);
}

static void standby_outputs(void)
{
    clk12(0); clk48(0);
    rail_dig(0);
    rail_ups(0);
    pi_sd_req = 0;                             /* no back-powering the CM4 */
    pin_low(GPIOA, 9);
    led(0);
}

void Reset_Handler(void)
{
    /* C runtime: copy .data from flash, zero .bss */
    extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss;
    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; ) *dst++ = 0;

    reset_log_record();                        /* before anything can reset us again */
    clock_init();
    gpio_init();
    pwm_init();
    adc_init();
    link_init(&lk, (uint16_t)TIM_CNT(TIM17), pin_read(GPIOA, 10));
    anen_level = lk.idle;
    p1_init(&ped, 0);

    /* gpio_init already gave the rails the rocker's value; decide the
       initial state from the rocker AND the 12 V input. Booting blindly on
       the rocker alone with 12 V absent would run the UPS from the
       supercap for nothing; STANDBY re-enters BOOT the moment 12 V is OK. */
    rocker_raw_prev = !pin_read(GPIOF, 0);
    rocker_on = rocker_raw_prev;
    v12_ok = adc_read() > CFG_SENS12_OK_CODE;
    if (rocker_on && v12_ok) { pin_high(GPIOA, 9); enter(ST_BOOT); }
    else                     { standby_outputs();  enter(ST_STANDBY); }
    mhrx_high_ms = ms;

    for (;;) {
        link_poll();
        if (!(SYST_CSR & (1u << 16))) continue;   /* wait for 1 ms tick */
        ms++;
        rslg.prev_ms = ms;                     /* how far this run got */
        inputs_tick();
        link_cmd();
        p1_tick(&ped, ms, (state == ST_BOOT || state == ST_ON) &&
                          (GPIO_ODR(GPIOA) & (1u << 3)));

        switch (state) {
        case ST_STANDBY:
            /* honour the rocker position whenever 12 V is present */
            if (v12_ok && rocker_on) {
                rail_ups(1); ups_on_ms = ms;       /* PSU_DIG_EN follows after CFG_DIG_STAGGER_MS (ST_BOOT) */
                pin_high(GPIOA, 9);
                enter(ST_BOOT);
            }
            break;

        case ST_BOOT:
            led_blink(CFG_BOOT_BLINK_MS);
            /* staggered digital enable: PSU_DIG_EN CFG_DIG_STAGGER_MS after
               UPS_EN when the rails are coming up from standby; a reset with
               the rails already on (gpio_init set both) never comes through
               here with PSU_DIG_EN low, so nothing is dropped */
            if (!(GPIO_ODR(GPIOA) & (1u << 3)) && ms - ups_on_ms >= CFG_DIG_STAGGER_MS) rail_dig(1);
            if (!rocker_on)      { enter_shutdown(TRIG_SWITCH); break; }
            if (!v12_ok)         { enter_shutdown(TRIG_FAIL);   break; }
            /* "Pi is up" = MHRX sustained high for CFG_MHRX_UP_MS (the Pi's
               UART TX idling high), or AN_EN already asserted (the app is
               past its analog gate). AN_EN alone was the old condition and
               with the gated app (AN_EN only after the clocks + 595 safe
               image are proven, never at boot) the MCU sat in ST_BOOT for
               the whole session (2026-09-12). Caveat: a blank DSP-board CPLD
               can hold MHRX high (2026-08-18) — then ST_ON is entered early,
               which costs nothing: rails are the same, clocks still follow
               AN_EN. Analog clocks are started by the ST_ON branch. */
            if (anen_level ||
                ms - mhrx_high_ms >= CFG_MHRX_UP_MS) {
                enter(ST_ON);
            }
            break;

        case ST_ON:
            if (!rocker_on)      { enter_shutdown(TRIG_SWITCH); break; }
            if (!v12_ok)         { enter_shutdown(TRIG_FAIL);   break; }
            /* analog power follows AN_EN — the stop is ordered the same as
               in shutdown (main rails first, phantom after the delay): the
               pop risk is identical whoever commands the stop */
            if (!anen_level) {
                if (TIM_CCR1(TIM14) != 0u) { clk12(0); clk12_stop_ms = ms; }
                if (TIM_CCR4(TIM3) != 0u &&
                    ms - clk12_stop_ms >= CFG_PHANTOM_OFF_DELAY_MS) clk48(0);
                if (CFG_LED_SOLID_MEANS_PI_UP) led(1);
                else                           led_blink(CFG_BOOT_BLINK_MS);
            } else {
                clk12_ramp(); clk48_ramp();        /* duty ramps, phantom last up */
                led(1);
            }
            break;

        case ST_SHUTDOWN:
            led_blink(CFG_SHDN_BLINK_MS);
            /* phantom off only after the ±15 V rails are down */
            if (!clk48_stopped && ms - clk12_stop_ms >= CFG_PHANTOM_OFF_DELAY_MS) {
                clk48(0);
                clk48_stopped = 1;
            }
            /* Pi-off acknowledge: sustained low on MHRX or AN_EN (each only
               after the Pi was seen alive this sequence), or the failsafe */
            if ((clk48_stopped &&
                 (!pi_alive_at_entry ||
                  (mhrx_seen_high && ms - mhrx_low_ms >= CFG_MHRX_ACK_LOW_MS) ||
                  (anen_seen_high && ms - anen_low_ms >= CFG_MHRX_ACK_LOW_MS))) ||
                 ms - state_entry_ms >= CFG_SHUTDOWN_TIMEOUT_MS) {
                standby_outputs();
                enter(ST_STANDBY);   /* reboots from there if rocker is ON */
            }
            break;
        }
    }
}
