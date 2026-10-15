/* J8 pedal supply — see p1.h. */
#include "p1.h"
#include "config.h"
#include "proto.h"

static int due(uint32_t ms, uint32_t when) { return (int32_t)(ms - when) >= 0; }

static void clamp(struct p1 *p, uint32_t ms, uint8_t why)
{
    p1_hw_enable(0);
    p1_hw_discharge(0);
    if (p->state == P1_ON) p->reclamps++;
    p->state = P1_OFF;
    p->why = why;
    p->t = ms;
    p->next_probe = ms + CFG_P1_PROBE_PERIOD_MS;
}

static void start_probe(struct p1 *p, uint32_t ms)
{
    p1_hw_enable(0);
    p1_hw_discharge(1);
    p->state = P1_DISCHARGE;
    p->t = ms;
    p->early = p->late = 0xFFFFu;
    p->probes++;
}

void p1_init(struct p1 *p, uint32_t ms)
{
    uint8_t *b = (uint8_t *)p;
    for (uint32_t i = 0; i < sizeof *p; i++) b[i] = 0;
    p1_hw_enable(0);
    p1_hw_discharge(0);
    p->state = P1_OFF;
    p->early = p->late = 0xFFFFu;
    p->next_probe = ms + CFG_P1_FIRST_PROBE_MS;
}

void p1_tick(struct p1 *p, uint32_t ms, int rails_up)
{
    if (p->hold && due(ms, p->hold_until)) {          /* hold expired */
        p->hold = 0;
        p->hb_deadline = ms + CFG_P1_HEARTBEAT_MS;
    }
    if (!rails_up) {
        if (p->state != P1_OFF) clamp(p, ms, P1W_RAILS);
        p->hold = 0;
        p->next_probe = ms + CFG_P1_FIRST_PROBE_MS;
        return;
    }
    switch (p->state) {
    case P1_OFF:
        if (due(ms, p->next_probe)) start_probe(p, ms);
        break;
    case P1_CYCLE_OFF:
        if (ms - p->t >= p->off_ms) start_probe(p, ms);
        break;
    case P1_DISCHARGE:
        if (ms - p->t >= CFG_P1_DISCHARGE_MS) {
            p1_hw_discharge(0);
            p->state = P1_MEASURE;
            p->t = ms;
        }
        break;
    case P1_MEASURE:
        if (p->early == 0xFFFFu && ms - p->t >= CFG_P1_EARLY_MS) p->early = p1_hw_adc();
        if (ms - p->t >= CFG_P1_LATE_MS) {
            p->late = p1_hw_adc();
            if (p->early <= CFG_P1_EARLY_MAX &&
                p->late >= CFG_P1_LATE_MIN && p->late <= CFG_P1_LATE_MAX &&
                p->late >= p->early + CFG_P1_RISE_MIN) {
                p1_hw_enable(1);                      /* the P1 signature: 9 V on */
                p->state = P1_ON;
                p->why = P1W_NONE;
                p->t = ms;
                p->enables++;
                p->hb_deadline = ms + CFG_P1_FIRST_HB_MS;
            } else {
                clamp(p, ms, P1W_NO_SIGNATURE);
            }
        }
        break;
    case P1_ON:
        if (CFG_P1_HEARTBEAT_REQUIRED && !p->hold && due(ms, p->hb_deadline))
            clamp(p, ms, P1W_HEARTBEAT);
        break;
    }
}

int p1_alive(struct p1 *p, uint32_t ms)
{
    if (p->state != P1_ON) return ST_REFUSED;
    p->hb_deadline = ms + CFG_P1_HEARTBEAT_MS;
    return ST_OK;
}

int p1_hold(struct p1 *p, uint32_t ms, uint32_t secs)
{
    if (secs < 1u || secs > CFG_P1_HOLD_MAX_S) return ST_BAD_ARG;
    p->hold = 1;
    p->hold_until = ms + secs * 1000u;
    return ST_OK;
}

int p1_release(struct p1 *p, uint32_t ms)
{
    if (p->hold) { p->hold = 0; p->hb_deadline = ms + CFG_P1_HEARTBEAT_MS; }
    return ST_OK;
}

int p1_cycle(struct p1 *p, uint32_t ms, uint32_t off_ms)
{
    if (off_ms < CFG_P1_CYCLE_MIN_MS || off_ms > CFG_P1_CYCLE_MAX_MS) return ST_BAD_ARG;
    p1_hw_enable(0);
    p1_hw_discharge(0);
    if (p->state == P1_ON) p->reclamps++;
    p->state = P1_CYCLE_OFF;
    p->why = P1W_CYCLE;
    p->t = ms;
    p->off_ms = (uint16_t)off_ms;
    return ST_OK;
}

uint32_t p1_hold_left_ms(const struct p1 *p, uint32_t ms)
{
    return (p->hold && !due(ms, p->hold_until)) ? p->hold_until - ms : 0u;
}
