/*
 * pwr-mcu configuration. Values marked [TBD] await bench measurement —
 * keep them in sync with the timing.* rows in src/fw/d24-pwr-mcu-def.csv.
 */
#ifndef CONFIG_H
#define CONFIG_H

/* BENCH_SAFE build (-DBENCH_SAFE): the full state machine runs but the
   rail-cut writes (UPS_EN/PSU_DIG_EN low) are suppressed, so a firmware
   fault cannot power off the CM4 that hosts the SWD flash path. */

#define CFG_ROCKER_DEBOUNCE_MS      30      /* contact bounce only [TBD] */
#define CFG_PHANTOM_OFF_DELAY_MS    100     /* 12CLK stop -> 48CLK stop [TBD] */
#define CFG_MHRX_ACK_LOW_MS         100     /* sustained-low ack window [TBD] */
#define CFG_SHUTDOWN_TIMEOUT_MS     60000   /* ack failsafe [TBD] */
#define CFG_MHRX_UP_MS              2000    /* MHRX sustained high = Pi up;
                                               enters ST_ON (2026-09-13) */

/* LED meaning in ST_ON (PW ruling pending, 2026-09-13 default):
   1 = solid means the Pi is up, whatever the analog rails are doing;
   0 = solid only while AN_EN is asserted, 2 Hz blink otherwise (old). */
#define CFG_LED_SOLID_MEANS_PI_UP   1

#define CFG_BOOT_BLINK_MS           250     /* 2 Hz boot/shutdown-pending blink */
#define CFG_SHDN_BLINK_MS           100     /* 5 Hz during save_shutdown */

/* SENS_12V thresholds (V_adc = V12 x 0.1369, 3.3 V ref, 12-bit) [TBD] */
#define CFG_SENS12_FAIL_CODE        1783    /* ~10.5 V */
#define CFG_SENS12_OK_CODE          1903    /* ~11.2 V (hysteresis) */

/* Switch-off keeps the digital rails up so the screen can show shutdown
   feedback (decision deferred pending hold-up measurement — this is the
   stated direction; power-fail always sheds them immediately). */
#define CFG_KEEP_DIG_ON_SWITCH_OFF  1

/* Power-up sequencing (PW 2026-09-15): the digital enables are staggered and
   the analog converter clocks are duty-RAMPED, so nothing soft-starts all at
   once. Per-pulse converter energy goes with t_on^2, so a duty ramp (not a
   frequency ramp) is what limits the inrush of all four +/-15 V sections
   together. Compare units: TIM14/TIM3 count 40 ticks per 1 us period. */
#define CFG_DIG_STAGGER_MS          30      /* UPS_EN on -> PSU_DIG_EN on */
#define CFG_CLK12_RAMP_START        2       /* 5 % duty first pulse (below 2 the FET barely switches) */
#define CFG_CLK12_RAMP_MS           100     /* compare 2 -> 8 (20 %) over this */
#define CFG_CLK48_RAMP_START        8       /* phantom starts at 20 % ... */
#define CFG_CLK48_RAMP_MS           100     /* ... and ramps to 32 (80 %); starts only after 12CLK is at full duty (phantom last up) */

#endif
