/*
 * pwr-mcu host link commands (wire format: link.h). Mirrored in the host
 * tool tools/pi/d24_pwrlink.py — change both together.
 * A reply is cmd | 0x80 with payload[0] = status.
 */
#ifndef PROTO_H
#define PROTO_H

/* both images */
#define CMD_PING        0x01u   /* -> mode-specific status block            */

/* app only (rev D CHANGE 6 pedal supply; harmless on rev C) */
#define CMD_P1_ALIVE    0x10u   /* host saw the pedal talk: heartbeat        */
#define CMD_P1_HOLD     0x11u   /* [secs 1..60]: UPDATE HOLD, re-armable     */
#define CMD_P1_RELEASE  0x12u   /* end the hold now                          */
#define CMD_P1_CYCLE    0x13u   /* [off_ms hi, lo]: clamp, wait, re-probe    */
#define CMD_ENTER_BOOT  0x20u   /* "BOOT": mailbox + SYSRESETREQ             */

/* bootloader only (option 2: app update over AN_EN / PI_SD) */
#define CMD_ERASE       0x30u   /* "ERAS": erase the 12 app pages            */
#define CMD_WRITE       0x31u   /* [off hi, lo, data (even, <= 64)]          */
#define CMD_READ        0x32u   /* [off hi, lo, n <= 64] -> data             */
#define CMD_CHECK       0x33u   /* -> valid, len[4], crc[4]                  */
#define CMD_GO          0x34u   /* validate and start the app                */

#define ST_OK           0u
#define ST_UNKNOWN      1u
#define ST_BAD_ARG      2u
#define ST_FLASH        3u
#define ST_VERIFY       4u
#define ST_REFUSED      5u
#define ST_INVALID      6u

#define MODE_APP        'A'
#define MODE_BOOT       'B'

#define FW_VERSION_MAJOR 2u
#define FW_VERSION_MINOR 0u
#define BOOT_VERSION     2u

#endif
