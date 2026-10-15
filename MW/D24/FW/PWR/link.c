/* pwr-mcu host link — see link.h for the wire format. */
#include "link.h"

uint16_t link_crc16(const uint8_t *p, uint32_t n)
{
    uint16_t c = 0xFFFFu;
    while (n--) {
        c ^= (uint16_t)(*p++ << 8);
        for (int k = 0; k < 8; k++)
            c = (c & 0x8000u) ? (uint16_t)((c << 1) ^ 0x1021u) : (uint16_t)(c << 1);
    }
    return c;
}

static void rx_reset(struct link *l)
{
    l->in_frame = 0;
    l->nbits = 0;
}

void link_init(struct link *l, uint16_t t_us, int in_level)
{
    uint8_t *b = (uint8_t *)l;
    for (uint32_t i = 0; i < sizeof *l; i++) b[i] = 0;
    l->t_last = t_us;
    l->idle = (uint8_t)(in_level != 0);
    l->tx_pos = -1;
}

static void rx_bit(struct link *l, int bit)
{
    if (!l->in_frame) return;
    if (l->nbits >= LINK_MAX_FRAME * 8u) { rx_reset(l); return; }
    uint8_t *b = &l->rx[l->nbits >> 3];
    if ((l->nbits & 7u) == 0) *b = 0;
    if (bit) *b |= (uint8_t)(0x80u >> (l->nbits & 7u));
    l->nbits++;
}

static void rx_end(struct link *l)
{
    uint16_t n = l->nbits >> 3;
    if ((l->nbits & 7u) == 0 && n >= 4u && l->rx_ready == 0 &&
        n == (uint16_t)(l->rx[1] + 4u) &&
        link_crc16(l->rx, n - 2u) == (uint16_t)((l->rx[n - 2u] << 8) | l->rx[n - 1u]))
        l->rx_ready = (uint8_t)n;
    rx_reset(l);
}

static uint32_t tx_width(const struct link *l)
{
    if (l->tx_pos < 0) return LINK_T_START;
    return (l->tx[l->tx_pos >> 3] & (0x80u >> (l->tx_pos & 7))) ? LINK_T_ONE : LINK_T_ZERO;
}

int link_step(struct link *l, uint16_t t_us, int in_level)
{
    l->now += (uint16_t)(t_us - l->t_last);
    l->t_last = t_us;
    int lev = in_level != 0;

    /* receiver: always tracks the line so the idle level stays right */
    if (!l->away) {
        if (lev != l->idle) { l->away = 1; l->t_edge = l->now; }
        else if (l->in_frame && l->now - l->t_edge >= LINK_W_END) rx_end(l);
    } else if (lev == l->idle) {
        uint32_t w = l->now - l->t_edge;
        l->away = 0;
        l->t_edge = l->now;
        if (w < LINK_W_GLITCH)       { }
        else if (w < LINK_W_SPLIT01) rx_bit(l, 0);
        else if (w < LINK_W_SPLIT1S) rx_bit(l, 1);
        else                         { rx_reset(l); l->in_frame = 1; }   /* START */
    } else if (l->now - l->t_edge >= LINK_W_LEVEL) {
        l->idle = (uint8_t)lev;                     /* a real level change */
        l->away = 0;
        l->t_edge = l->now;
        rx_reset(l);
    }

    /* transmitter */
    if (l->tx_phase == 1 && l->now - l->tx_t >= tx_width(l)) {
        l->out = 0; l->tx_phase = 2; l->tx_t = l->now;
    } else if (l->tx_phase == 2 && l->now - l->tx_t >= LINK_GAP_US) {
        l->tx_pos++;
        if (l->tx_pos >= (int16_t)l->tx_bits) { l->tx_phase = 0; l->tx_pos = -1; }
        else { l->out = 1; l->tx_phase = 1; l->tx_t = l->now; }
    }
    return l->out;
}

int link_rx(struct link *l, uint8_t *cmd, uint8_t *len, const uint8_t **payload)
{
    if (!l->rx_ready) return 0;
    *cmd = l->rx[0];
    *len = l->rx[1];
    *payload = &l->rx[2];
    return 1;
}

void link_rx_done(struct link *l) { l->rx_ready = 0; }

int link_tx_busy(const struct link *l) { return l->tx_phase != 0; }

void link_send(struct link *l, uint8_t cmd, const uint8_t *payload, uint8_t len)
{
    if (l->tx_phase != 0 || len > LINK_MAX_PAYLOAD) return;
    l->tx[0] = cmd;
    l->tx[1] = len;
    for (uint8_t i = 0; i < len; i++) l->tx[2u + i] = payload[i];
    uint16_t c = link_crc16(l->tx, 2u + len);
    l->tx[2u + len] = (uint8_t)(c >> 8);
    l->tx[3u + len] = (uint8_t)c;
    l->tx_bits = (uint16_t)((len + 4u) * 8u);
    l->tx_pos = -1;
    l->out = 1;
    l->tx_phase = 1;
    l->tx_t = l->now;
}
