/* p1.c off-target: the J8 supply decisions against an RC model of the probe.
   The model is desk arithmetic (p1.h / config.h), not a measurement: final
   code ~250 for an open jack and for a pedal, a pedal crawling to it with
   tau 0.23 s after the discharge. Thresholds are the [TBD] config values. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "../p1.h"
#include "../config.h"
#include "../proto.h"

enum jack { REV_C, OPEN, PEDAL, SHORT };
static enum jack jack;
static uint32_t now, released;
static int en, dis, en_edges;

void p1_hw_enable(int on) { if (on && !en) en_edges++; en = on; }
void p1_hw_discharge(int on) { if (dis && !on) released = now; dis = on; }
uint16_t p1_hw_adc(void)
{
    double t = (now - released) / 1000.0;
    switch (jack) {
    case OPEN:  return 250;
    case PEDAL: return (uint16_t)(250.0 * (1.0 - 0.1 * exp(-t / 0.23)) * (1.0 - exp(-t / 0.23)) + 0.5);
    default:    return 0;                               /* rev C pull-down, short */
    }
}

static struct p1 p;
static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

/* run for ms, optional heartbeat period (0 = none); returns ms the supply was on */
static uint32_t run(uint32_t dur, uint32_t hb, int rails)
{
    uint32_t on = 0;
    for (uint32_t i = 0; i < dur; i++) {
        now++;
        p1_tick(&p, now, rails);
        if (hb && now % hb == 0) p1_alive(&p, now);
        on += en;
    }
    return on;
}

static void reset(enum jack j)
{
    jack = j; now = 0; released = 0; en = dis = en_edges = 0;
    p1_init(&p, now);
}

int main(void)
{
    reset(REV_C);
    run(60000, 1000, 1);
    CHECK(en_edges == 0 && p.probes > 15, "rev C: never enabled (%d), probes %u", en_edges, p.probes);
    printf("rev C (PA7 N/C, pull-down): %u probes in 60 s, 9 V never on, last early/late %u/%u\n", p.probes, p.early, p.late);

    reset(OPEN);
    run(60000, 1000, 1);
    CHECK(en_edges == 0, "open jack enabled");
    printf("open jack: %u probes, never on (early %u late %u)\n", p.probes, p.early, p.late);

    reset(SHORT);
    run(20000, 1000, 1);
    CHECK(en_edges == 0, "short enabled");

    reset(PEDAL);
    run(1500, 0, 1);
    CHECK(en && p.state == P1_ON, "pedal: on after the first probe (early %u late %u)", p.early, p.late);
    printf("pedal: on at %u ms (early %u, late %u)\n", now, p.early, p.late);
    run(60000, 1000, 1);
    CHECK(en && p.reclamps == 0, "pedal with heartbeat stays on");

    run(4000, 0, 1);                                      /* app stops hearing it */
    CHECK(!en && p.why == P1W_HEARTBEAT, "heartbeat loss re-clamps within %u ms", CFG_P1_HEARTBEAT_MS);
    jack = OPEN;                                          /* it was unplugged */
    run(30000, 1000, 1);
    CHECK(!en && en_edges == 1, "unplugged: stays clamped (%d enables)", en_edges);
    printf("heartbeat loss: clamped, re-probes find the open jack, stays off\n");

    reset(PEDAL);
    run(1500, 1000, 1);
    CHECK(p1_hold(&p, now, 0) == ST_BAD_ARG && p1_hold(&p, now, 61) == ST_BAD_ARG, "hold bounds");
    CHECK(p1_hold(&p, now, 60) == ST_OK, "hold 60");
    uint32_t t_hold = now;
    run(50000, 0, 1);
    CHECK(en, "on through 50 s of hold without heartbeat");
    p1_hold(&p, now, 60);                                 /* re-arm restarts the 60 s */
    run(59000, 0, 1);
    CHECK(en, "re-armed hold still on at +109 s");
    run(1000 + CFG_P1_HEARTBEAT_MS + 50, 0, 1);
    CHECK(!en && p.why == P1W_HEARTBEAT, "hold expiry then one heartbeat window, then clamp");
    printf("UPDATE HOLD: 60 s, re-armed at +50 s, clamped %u ms after the first arm\n", now - t_hold);

    reset(PEDAL);
    run(1500, 1000, 1);
    CHECK(p1_cycle(&p, now, 50) == ST_BAD_ARG, "cycle bound");
    CHECK(p1_cycle(&p, now, 1000) == ST_OK && !en, "cycle clamps at once");
    uint32_t t0 = now, t_on = 0;
    for (int i = 0; i < 3000 && !t_on; i++) { run(1, 1000, 1); if (en) t_on = now - t0; }
    CHECK(t_on >= 1000 + CFG_P1_DISCHARGE_MS + CFG_P1_LATE_MS && t_on < 2100, "cycle: back on after %u ms", t_on);
    printf("power-cycle 1000 ms: supply back on after %u ms (off + discharge + probe)\n", t_on);

    p1_hold(&p, now, 30);
    run(10, 1000, 0);                                     /* rails go down */
    CHECK(!en && !p.hold && p.why == P1W_RAILS, "rails down clamps and drops the hold");

    printf("%s (%d failures)\n", fails ? "P1 TEST FAILED" : "P1 TEST PASSED", fails);
    return fails != 0;
}
