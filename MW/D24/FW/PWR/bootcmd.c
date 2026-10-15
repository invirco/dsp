/*
 * Bootloader command handling (option 2: the app region rewritten from the
 * CM4 over the host link). Hardware is reached only through the three bh_*
 * hooks, so tests/boot_test.c runs this file against a RAM flash.
 *
 * Retry-safe by construction: a WRITE whose reply was lost is re-sent by the
 * host; halfwords that already hold the value are skipped, so the repeat
 * succeeds. Anything else written over non-erased flash is ST_FLASH.
 */
#include "bootcmd.h"
#include "proto.h"

uint32_t boot_crc32(const uint8_t *p, uint32_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* magic + length header at +0x10, zlib CRC32 appended at +len (mkimage.py) */
int boot_app_valid(const uint8_t *app, uint32_t *len_out, uint32_t *crc_out)
{
    uint32_t magic = rd32(app + 0x10u);
    uint32_t len   = rd32(app + 0x14u);
    *len_out = len;
    *crc_out = 0;
    if (magic != APP_MAGIC || len < 0x20u || len > APP_MAX - 4u || (len & 3u)) return 0;
    *crc_out = rd32(app + len);
    return boot_crc32(app, len) == *crc_out;
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

int bootcmd(struct link *l, uint8_t cmd, uint8_t len, const uint8_t *p,
            uint8_t reason, int rocker_on)
{
    uint8_t r[66];
    uint8_t n = 1;
    const uint8_t *app = bh_app();
    uint32_t alen, acrc;
    int start = 0;

    r[0] = ST_OK;
    switch (cmd) {
    case CMD_PING:
        r[1] = MODE_BOOT; r[2] = BOOT_VERSION; r[3] = reason;
        r[4] = (uint8_t)boot_app_valid(app, &alen, &acrc); r[5] = (uint8_t)rocker_on;
        n = 6;
        break;

    case CMD_ERASE:
        if (len != 4 || p[0] != 'E' || p[1] != 'R' || p[2] != 'A' || p[3] != 'S') { r[0] = ST_BAD_ARG; break; }
        for (uint32_t pg = 0; pg < APP_MAX / BOOT_PAGE; pg++)   /* header page first */
            if (bh_erase(pg)) { r[0] = ST_FLASH; break; }
        break;

    case CMD_WRITE: {
        uint32_t off = len >= 2 ? ((uint32_t)p[0] << 8) | p[1] : 0;
        uint32_t dn = len >= 2 ? len - 2u : 0;
        if (len < 4 || (off & 1u) || (dn & 1u) || dn > 64u || off + dn > APP_MAX) { r[0] = ST_BAD_ARG; break; }
        for (uint32_t i = 0; i < dn; i += 2) {
            uint16_t v = (uint16_t)(p[2 + i] | (p[3 + i] << 8));
            uint16_t cur = (uint16_t)(app[off + i] | (app[off + i + 1] << 8));
            if (cur == v) continue;                     /* a retried write */
            if (cur != 0xFFFFu || bh_prog16(off + i, v)) { r[0] = ST_FLASH; break; }
            if ((uint16_t)(app[off + i] | (app[off + i + 1] << 8)) != v) { r[0] = ST_VERIFY; break; }
        }
        break;
    }

    case CMD_READ: {
        uint32_t off = len == 3 ? ((uint32_t)p[0] << 8) | p[1] : 0;
        uint32_t rn = len == 3 ? p[2] : 0;
        if (len != 3 || rn == 0 || rn > 64u || off + rn > APP_MAX) { r[0] = ST_BAD_ARG; break; }
        for (uint32_t i = 0; i < rn; i++) r[1 + i] = app[off + i];
        n = (uint8_t)(1 + rn);
        break;
    }

    case CMD_CHECK:
        r[1] = (uint8_t)boot_app_valid(app, &alen, &acrc);
        put32(&r[2], alen); put32(&r[6], acrc);
        n = 10;
        break;

    case CMD_GO:
        if (boot_app_valid(app, &alen, &acrc)) start = 1;
        else r[0] = ST_INVALID;
        break;

    default:
        r[0] = ST_UNKNOWN;
        break;
    }
    link_send(l, (uint8_t)(cmd | 0x80u), r, n);
    return start;
}
