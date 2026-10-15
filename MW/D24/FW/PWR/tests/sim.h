/* Off-target helpers: a line as a list of (level, microseconds) runs, and
   a link driven over it with jittered polling and a wrapping 16-bit timer. */
#ifndef SIM_H
#define SIM_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "../link.h"

#define MAXRUNS 20000

struct line { int n; uint8_t lev[MAXRUNS]; uint32_t us[MAXRUNS]; };

static uint32_t rng = 12345u;
static uint32_t rnd(uint32_t n) { rng = rng * 1103515245u + 12345u; return (rng >> 8) % n; }

static void line_add(struct line *ln, int lev, uint32_t us)
{
    if (ln->n && ln->lev[ln->n - 1] == lev) { ln->us[ln->n - 1] += us; return; }
    ln->lev[ln->n] = (uint8_t)lev; ln->us[ln->n] = us; ln->n++;
}

/* Run a transmitter link until its frame is out; record its output line.
   poll_max = the largest gap between polls (us). */
static void tx_record(struct link *tx, struct line *out, uint32_t poll_max, uint16_t t0)
{
    uint16_t t = t0;
    int lev = link_step(tx, t, 0);
    uint32_t acc = 0;
    while (link_tx_busy(tx)) {
        uint32_t d = 1 + rnd(poll_max);
        t = (uint16_t)(t + d); acc += d;
        int nl = link_step(tx, t, 0);
        if (nl != lev) { line_add(out, lev, acc); acc = 0; lev = nl; }
    }
    line_add(out, lev, acc);
    line_add(out, lev, 5000);         /* idle tail: closes the frame */
}

/* Feed a line into a receiver with jittered polling. idle_xor flips every
   level (a high-idle AN_EN). Returns the end time. */
static uint16_t rx_feed(struct link *rx, const struct line *ln, uint32_t poll_max,
                        uint16_t t, int idle_xor)
{
    for (int i = 0; i < ln->n; i++) {
        uint32_t left = ln->us[i];
        while (left) {
            uint32_t d = 1 + rnd(poll_max);
            if (d > left) d = left;
            t = (uint16_t)(t + d); left -= d;
            link_step(rx, t, ln->lev[i] ^ idle_xor);
        }
    }
    return t;
}

#endif
