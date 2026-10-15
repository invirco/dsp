/*
 * pwr-mcu host link — framed commands over the two GPIO nets the CM4
 * already shares with U34, identical on rev C and rev D:
 *   AN_EN  (CM4 GPIO26 -> PA10)  host -> MCU
 *   PI_SD  (PA5 -> CM4 GPIO4)    MCU -> host
 *
 * Pulse-width code. A pulse is an excursion AWAY from the line's idle level
 * and back; its width is the symbol:
 *     < LINK_W_GLITCH   ignored
 *     < LINK_W_SPLIT01  bit 0      (sent 200 us)
 *     < LINK_W_SPLIT1S  bit 1      (sent 600 us)
 *     < LINK_W_LEVEL    START      (sent 1400 us; opens a frame)
 *     >= LINK_W_LEVEL   not a pulse: the line has changed level (AN_EN's
 *                       normal job); the new level becomes the idle level
 *                       and any frame in progress is dropped.
 * Pulses are separated by at least LINK_GAP_US at the idle level; a gap of
 * LINK_W_END closes the frame. On AN_EN the idle level is whatever the host
 * wants the analog power to be (pulses are high from a low line, low from a
 * high line), so a frame never moves the analog rails: the app filters
 * AN_EN's level over CFG_ANEN_STABLE_MS (config.h), far longer than any
 * pulse. PI_SD idles low and pulses high; the D24 app's shutdown watch
 * (gpiomon, 200 ms debounce) never sees a sub-2 ms pulse.
 *
 * Frame: [cmd][len][len payload bytes][crc16 hi][crc16 lo], bits MSB first,
 * CRC-16/CCITT-FALSE over cmd..payload. A stretched pulse (host preempted)
 * becomes a wrong symbol, the CRC fails, the frame is dropped silently and
 * the host retries on its reply timeout.
 *
 * The code is pure logic: link_step() gets the timer and the input level and
 * returns the output level, so the same file runs in the bootloader (8 MHz
 * HSI), the app (40 MHz PLL) and the host test (tests/link_test.c). It uses
 * no static writable data (the bootloader has no .data/.bss).
 */
#ifndef LINK_H
#define LINK_H

#include <stdint.h>

#define LINK_W_GLITCH   60u
#define LINK_W_SPLIT01  400u
#define LINK_W_SPLIT1S  900u
#define LINK_W_LEVEL    2000u
#define LINK_W_END      3000u

#define LINK_T_ZERO     200u
#define LINK_T_ONE      600u
#define LINK_T_START    1400u
#define LINK_GAP_US     200u

#define LINK_MAX_PAYLOAD 68u                 /* WRITE: 2 offset + 64 data */
#define LINK_MAX_FRAME   (LINK_MAX_PAYLOAD + 4u)

struct link {
    uint32_t now;          /* extended us clock (from the 16-bit timer) */
    uint16_t t_last;
    uint8_t  idle;         /* committed idle level of the input */
    uint8_t  away;         /* input currently away from idle */
    uint32_t t_edge;       /* when the input last changed */
    uint8_t  in_frame;
    uint16_t nbits;
    uint8_t  rx[LINK_MAX_FRAME];
    uint8_t  rx_ready;     /* bytes of a complete, CRC-checked frame */
    /* transmitter */
    uint8_t  tx[LINK_MAX_FRAME];
    uint16_t tx_bits;
    int16_t  tx_pos;       /* -1 = START pulse */
    uint8_t  tx_phase;     /* 0 idle, 1 pulse, 2 gap */
    uint8_t  out;
    uint32_t tx_t;
};

uint16_t link_crc16(const uint8_t *p, uint32_t n);
void     link_init(struct link *l, uint16_t t_us, int in_level);
/* call as often as possible; returns the level to drive on the output */
int      link_step(struct link *l, uint16_t t_us, int in_level);
/* a received frame: returns 1 and points at cmd/len/payload, else 0 */
int      link_rx(struct link *l, uint8_t *cmd, uint8_t *len, const uint8_t **payload);
void     link_rx_done(struct link *l);
/* queue a reply frame; ignored while one is still going out */
void     link_send(struct link *l, uint8_t cmd, const uint8_t *payload, uint8_t len);
int      link_tx_busy(const struct link *l);

#endif
