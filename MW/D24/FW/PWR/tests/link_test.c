/* link.c off-target: round trips with jittered polling and a wrapping timer,
   high-idle AN_EN, stretched pulses (host preempted), level changes.
   `link_test emit F` / `link_test decode F` cross-check the host tool. */
#include <string.h>
#include "sim.h"

static struct line ln;
static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static int send_recv(uint8_t cmd, const uint8_t *pl, uint8_t n, int idle_xor,
                     uint32_t txj, uint32_t rxj, int stretch_at, uint32_t stretch_us,
                     uint8_t *got_cmd, uint8_t *got_n, uint8_t *got)
{
    struct link tx, rx;
    uint16_t t0 = (uint16_t)rnd(65536);
    link_init(&tx, t0, 0);
    link_send(&tx, cmd, pl, n);
    ln.n = 0;
    tx_record(&tx, &ln, txj, t0);
    if (stretch_at >= 0) {                     /* lengthen one pulse (level 1 run) */
        int k = 0;
        for (int i = 0; i < ln.n; i++)
            if (ln.lev[i] == 1 && k++ == stretch_at) { ln.us[i] += stretch_us; break; }
    }
    uint16_t tr = (uint16_t)rnd(65536);
    link_init(&rx, tr, idle_xor);
    tr = rx_feed(&rx, &ln, rxj, tr, idle_xor);
    uint8_t c, l; const uint8_t *p;
    if (!link_rx(&rx, &c, &l, &p)) return 0;
    *got_cmd = c; *got_n = l; memcpy(got, p, l);
    return 1;
}

static int write_line(const char *path)
{
    struct link tx;
    uint8_t pl[16];
    for (int i = 0; i < 16; i++) pl[i] = (uint8_t)(i * 17);
    link_init(&tx, 0, 0);
    link_send(&tx, 0x31, pl, 16);
    ln.n = 0;
    tx_record(&tx, &ln, 1, 0);
    FILE *f = fopen(path, "w");
    for (int i = 0; i < ln.n; i++) fprintf(f, "%d %u\n", ln.lev[i], ln.us[i]);
    fclose(f);
    return 0;
}

static int read_line(const char *path)
{
    FILE *f = fopen(path, "r");
    int lev; unsigned us;
    ln.n = 0;
    while (fscanf(f, "%d %u", &lev, &us) == 2) line_add(&ln, lev, us);
    fclose(f);
    struct link rx;
    link_init(&rx, 100, 0);
    rx_feed(&rx, &ln, 1, 100, 0);
    uint8_t c, l; const uint8_t *p;
    if (!link_rx(&rx, &c, &l, &p)) { printf("none\n"); return 1; }
    printf("%02x", c);
    for (int i = 0; i < l; i++) printf(" %02x", p[i]);
    printf("\n");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "emit"))   return write_line(argv[2]);
    if (argc == 3 && !strcmp(argv[1], "decode")) return read_line(argv[2]);

    uint8_t pl[LINK_MAX_PAYLOAD], got[LINK_MAX_PAYLOAD], gc, gn;
    int ok = 0;

    /* 1+2: random frames, low idle and high idle, polling jitter up to 50 us */
    for (int i = 0; i < 4000; i++) {
        uint8_t n = (uint8_t)rnd(LINK_MAX_PAYLOAD + 1), cmd = (uint8_t)rnd(256);
        for (int k = 0; k < n; k++) pl[k] = (uint8_t)rnd(256);
        int x = i & 1;
        int r = send_recv(cmd, pl, n, x, 20, 50, -1, 0, &gc, &gn, got);
        CHECK(r && gc == cmd && gn == n && !memcmp(got, pl, n), "round trip %d (n=%u idle=%d)", i, n, x);
        ok += r;
    }
    printf("round trips: %d of 4000 delivered intact (half with AN_EN idling high)\n", ok);

    /* 3: a stretched pulse must never deliver a wrong frame */
    int dropped = 0, intact = 0;
    for (int i = 0; i < 4000; i++) {
        uint8_t n = (uint8_t)(1 + rnd(16)), cmd = (uint8_t)rnd(256);
        for (int k = 0; k < n; k++) pl[k] = (uint8_t)rnd(256);
        uint32_t s = 150 + rnd(3000);
        int r = send_recv(cmd, pl, n, 0, 20, 50, (int)rnd((n + 4) * 8 + 1), s, &gc, &gn, got);
        if (!r) dropped++;
        else { CHECK(gc == cmd && gn == n && !memcmp(got, pl, n), "stretched pulse delivered a WRONG frame (%d)", i); intact++; }
    }
    printf("stretched pulses (+150..3150 us): %d dropped, %d delivered intact, 0 wrong allowed\n", dropped, intact);

    /* 4: a real level change (AN_EN raised and held) moves the idle level, no frame */
    {
        struct link rx;
        link_init(&rx, 0, 0);
        ln.n = 0; line_add(&ln, 0, 1000); line_add(&ln, 1, 50000);
        rx_feed(&rx, &ln, 30, 0, 0);
        uint8_t c, l; const uint8_t *p;
        CHECK(rx.idle == 1 && !link_rx(&rx, &c, &l, &p), "level change: idle=%d", rx.idle);
        printf("level change: idle level follows a held AN_EN, no frame: %s\n", rx.idle == 1 ? "OK" : "FAIL");
    }

    /* 5: tx_record output widths are in their classes */
    {
        struct link tx;
        link_init(&tx, 0, 0);
        uint8_t z[2] = {0x00, 0xFF};
        link_send(&tx, 0xA5, z, 2);
        ln.n = 0; tx_record(&tx, &ln, 20, 0);
        uint32_t mn = 1u << 30, mx = 0;
        for (int i = 1; i < ln.n - 1; i++) if (ln.lev[i] == 0) { if (ln.us[i] < mn) mn = ln.us[i]; if (ln.us[i] > mx) mx = ln.us[i]; }
        printf("tx gaps %u..%u us (sent %u), start pulse %u us (sent %u)\n", mn, mx, LINK_GAP_US, ln.us[0], LINK_T_START);
    }

    printf("%s (%d failures)\n", fails ? "LINK TEST FAILED" : "LINK TEST PASSED", fails);
    return fails != 0;
}
