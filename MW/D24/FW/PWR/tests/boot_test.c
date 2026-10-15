/* bootcmd.c off-target: the whole option-2 update over the simulated link
   against a RAM flash with F0 programming rules (a halfword must read 0xFFFF
   before it is programmed). Uses the real built image: boot_test ../pwr-mcu.img */
#include <string.h>
#include "sim.h"
#include "../bootcmd.h"
#include "../proto.h"

static uint8_t flash[APP_MAX];
static int erases, progs;
const uint8_t *bh_app(void) { return flash; }
int bh_erase(uint32_t pg) { if (pg >= APP_MAX / BOOT_PAGE) return 1; memset(flash + pg * BOOT_PAGE, 0xFF, BOOT_PAGE); erases++; return 0; }
int bh_prog16(uint32_t off, uint16_t v)
{
    if ((flash[off] | flash[off + 1] << 8) != 0xFFFF) return 1;
    flash[off] = (uint8_t)v; flash[off + 1] = (uint8_t)(v >> 8); progs++;
    return 0;
}

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)
static struct line ln;
static uint8_t rep[LINK_MAX_FRAME], rep_n, rep_cmd;
static int started;

/* host frame -> MCU link -> bootcmd -> reply frame -> host link */
static int xfer(uint8_t cmd, const uint8_t *pl, uint8_t n)
{
    struct link host, mcu;
    link_init(&host, 0, 0);
    link_init(&mcu, 777, 0);
    link_send(&host, cmd, pl, n);
    ln.n = 0; tx_record(&host, &ln, 20, 0);
    uint16_t t = rx_feed(&mcu, &ln, 40, 777, 0);
    uint8_t c, l; const uint8_t *p;
    if (!link_rx(&mcu, &c, &l, &p)) return -1;
    started = bootcmd(&mcu, c, l, p, REASON_NO_APP, 1);
    link_rx_done(&mcu);
    ln.n = 0; tx_record(&mcu, &ln, 40, t);
    link_init(&host, 5, 0);
    rx_feed(&host, &ln, 20, 5, 0);
    if (!link_rx(&host, &c, &l, &p)) return -2;
    rep_cmd = c; rep_n = l; memcpy(rep, p, l);
    return p[0];
}

int main(int argc, char **argv)
{
    static uint8_t img[APP_MAX];
    FILE *f = fopen(argc > 1 ? argv[1] : "../pwr-mcu.img", "rb");
    size_t isz = fread(img, 1, sizeof img, f);
    fclose(f);
    memset(flash, 0x5A, sizeof flash);                     /* old junk */

    CHECK(xfer(CMD_PING, NULL, 0) == ST_OK && rep_cmd == (CMD_PING | 0x80) && rep[1] == MODE_BOOT
          && rep[3] == REASON_NO_APP, "PING");
    CHECK(xfer(CMD_CHECK, NULL, 0) == ST_OK && rep[1] == 0, "CHECK on junk says invalid");
    CHECK(xfer(CMD_GO, NULL, 0) == ST_INVALID && !started, "GO refused on junk");
    CHECK(xfer(CMD_ERASE, (const uint8_t *)"ERAX", 4) == ST_BAD_ARG && erases == 0, "ERASE needs its key");
    CHECK(xfer(CMD_ERASE, (const uint8_t *)"ERAS", 4) == ST_OK && erases == 12, "ERASE 12 pages");

    uint8_t w[66];
    int bad = 0;
    for (size_t off = 0; off < isz; off += 64) {
        size_t k = isz - off < 64 ? isz - off : 64;
        w[0] = (uint8_t)(off >> 8); w[1] = (uint8_t)off; memcpy(w + 2, img + off, k);
        if (xfer(CMD_WRITE, w, (uint8_t)(k + 2)) != ST_OK) bad++;
        if (off == 512 && xfer(CMD_WRITE, w, (uint8_t)(k + 2)) != ST_OK) bad++;   /* lost reply: resend */
    }
    CHECK(bad == 0, "WRITE %zu B in 64 B frames incl. one resend: %d bad", isz, bad);
    w[0] = 0; w[1] = 0; w[2] = (uint8_t)(img[0] ^ 0xFF); w[3] = img[1];
    CHECK(xfer(CMD_WRITE, w, 4) == ST_FLASH, "WRITE over programmed flash refused");
    w[0] = 0; w[1] = 1;
    CHECK(xfer(CMD_WRITE, w, 4) == ST_BAD_ARG, "odd offset refused");
    w[0] = (uint8_t)(APP_MAX >> 8); w[1] = 0;
    CHECK(xfer(CMD_WRITE, w, 4) == ST_BAD_ARG, "write past 12 KB refused");

    int rbad = 0;
    for (size_t off = 0; off < isz; off += 64) {
        size_t k = isz - off < 64 ? isz - off : 64;
        uint8_t q[3] = {(uint8_t)(off >> 8), (uint8_t)off, (uint8_t)k};
        if (xfer(CMD_READ, q, 3) != ST_OK || rep_n != k + 1 || memcmp(rep + 1, img + off, k)) rbad++;
    }
    CHECK(rbad == 0, "READ back: %d bad blocks", rbad);

    CHECK(xfer(CMD_CHECK, NULL, 0) == ST_OK && rep[1] == 1, "CHECK valid after write");
    uint32_t crc = (uint32_t)rep[6] << 24 | rep[7] << 16 | rep[8] << 8 | rep[9];
    uint32_t want = img[isz - 4] | img[isz - 3] << 8 | img[isz - 2] << 16 | (uint32_t)img[isz - 1] << 24;
    CHECK(crc == want, "CHECK crc 0x%08x vs image 0x%08x", crc, want);
    CHECK(xfer(CMD_GO, NULL, 0) == ST_OK && started, "GO starts a valid app");

    flash[0x200] ^= 1;                                      /* a flipped bit / torn write */
    CHECK(xfer(CMD_GO, NULL, 0) == ST_INVALID && !started, "GO refused after a flipped bit");
    CHECK(xfer(0x77, NULL, 0) == ST_UNKNOWN, "unknown command answered");

    printf("image %zu B, %d erases, %d halfwords programmed\n", isz, erases, progs);
    printf("%s (%d failures)\n", fails ? "BOOT TEST FAILED" : "BOOT TEST PASSED", fails);
    return fails != 0;
}
