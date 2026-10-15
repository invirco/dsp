/*
 * J8 pedal supply, rev D CHANGE 6 (variant B2, PW ruling 2026-10-02):
 * sense before enable, heartbeat re-clamp, UPDATE HOLD, host power-cycle.
 *
 * Pure logic over four hooks so tests/p1_test.c can drive it. Hardware
 * (main.c): PA6 P1_EN ACTIVE LOW (low = U38 ADJ clamp released = 9 V on;
 * high or hi-Z = clamped, the board's 4K7 base pull-up makes hi-Z safe);
 * PA7 P1_SENSE = 22K/10K divider of the jack probe (100K from +3V3ON), ADC
 * ch7, idles as an input with the internal pull-down.
 *
 * Probe: PA7 driven low CFG_P1_DISCHARGE_MS (discharges the jack and any
 * pedal input caps through 22K), then released; the ADC reads at
 * CFG_P1_EARLY_MS and CFG_P1_LATE_MS. P1's ~10 uF input caps make a slow
 * crawl (tau ~0.24 s): low early, well up late. An open jack is already at
 * its level early; a short or an Ethernet port never rises. 9 V goes on only
 * on that signature. Thresholds are [TBD bench] (config.h) — they move with
 * temperature (diode set) and include the internal pull-down's load, which
 * is applied between conversions.
 *
 * rev C: PA6/PA7 are N/C. The pull-down holds PA7 at 0 V, so every probe
 * reads "no pedal" and P1_EN is never driven low; driving it would reach
 * nothing anyway (rev C pedal 9 V is unswitched).
 */
#ifndef P1_H
#define P1_H

#include <stdint.h>

enum p1_state { P1_OFF, P1_DISCHARGE, P1_MEASURE, P1_ON, P1_CYCLE_OFF };

/* why the supply was last clamped (PING telemetry) */
enum p1_why { P1W_NONE, P1W_NO_SIGNATURE, P1W_HEARTBEAT, P1W_RAILS, P1W_CYCLE };

struct p1 {
    uint8_t  state, why;
    uint32_t t;                  /* state entry */
    uint32_t next_probe;
    uint32_t hb_deadline;
    uint32_t hold_until;
    uint8_t  hold;               /* hold armed */
    uint16_t off_ms;             /* CYCLE clamp time */
    uint16_t early, late;        /* last probe's ADC codes */
    uint16_t probes, enables, reclamps;
};

/* hooks (main.c / tests) */
void     p1_hw_enable(int on);        /* 1 = PA6 low (9 V on), 0 = PA6 high */
void     p1_hw_discharge(int on);     /* 1 = PA7 out low, 0 = input + pull-down */
uint16_t p1_hw_adc(void);             /* one PA7 conversion */

void p1_init(struct p1 *p, uint32_t ms);
/* every 1 ms tick; rails_up = the digital rails are on (ST_BOOT/ST_ON) */
void p1_tick(struct p1 *p, uint32_t ms, int rails_up);
/* host commands; each returns a proto.h status */
int  p1_alive(struct p1 *p, uint32_t ms);
int  p1_hold(struct p1 *p, uint32_t ms, uint32_t secs);
int  p1_release(struct p1 *p, uint32_t ms);
int  p1_cycle(struct p1 *p, uint32_t ms, uint32_t off_ms);
uint32_t p1_hold_left_ms(const struct p1 *p, uint32_t ms);

#endif
