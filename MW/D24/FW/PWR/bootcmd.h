#ifndef BOOTCMD_H
#define BOOTCMD_H

#include <stdint.h>
#include "link.h"

#define APP_MAGIC   0x4D583236u          /* 'MX26' */
#define APP_MAX     (12u * 1024u)
#define BOOT_PAGE   1024u

/* why the bootloader is listening (PING reply) */
#define REASON_REQUESTED 1u              /* the app's ENTER_BOOT (mailbox) */
#define REASON_NO_APP    2u              /* header/CRC check failed */

/* hardware hooks: boot.c on the part, tests/boot_test.c on the desk */
const uint8_t *bh_app(void);                 /* the 12 KB app region */
int bh_erase(uint32_t page);                 /* app page 0..11; 0 = ok */
int bh_prog16(uint32_t off, uint16_t v);     /* halfword at app offset; 0 = ok */

uint32_t boot_crc32(const uint8_t *p, uint32_t n);
int boot_app_valid(const uint8_t *app, uint32_t *len_out, uint32_t *crc_out);
/* handles one received frame, queues the reply; returns 1 = start the app
   once the reply has gone out */
int bootcmd(struct link *l, uint8_t cmd, uint8_t len, const uint8_t *p,
            uint8_t reason, int rocker_on);

#endif
