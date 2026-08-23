/*======================================================================
 * diag.h — bring-up diagnostics: boot-stage codes and the read-only
 * diagnostic register block.
 *
 * Shared by diag.asm, main.asm, product_config.asm and the host tool
 * tools/pi/dsp4_diag.py (which carries the same map in Python — keep
 * the two in step).
 *
 * WHY THIS EXISTS: the rev-C DSP4 card has no emulator access to either
 * SHARC — JTG_TCK/TMS/TDI/TDO and JTG_TRST are floating on both DSPs
 * (tasks.md, 2026-08-11 addendum). The SPI link and the per-chip LED are
 * therefore the entire debug channel, so both are made to carry as much
 * state as they can.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#ifndef _DSP4_DIAG_H
#define _DSP4_DIAG_H

/* ---------------------------------------------------------------------
 * Boot stages — the value in DIAG_BOOT_STAGE, and the number of LED
 * flashes when the firmware is stuck. A stage means "this step
 * COMPLETED"; the fault is in whatever comes next. So N flashes says
 * "stuck in step N+1".
 * ------------------------------------------------------------------- */
#define DIAG_STAGE_INIT      1   /* core + diag timer alive; in _sru_init      */
#define DIAG_STAGE_SRU       2   /* SRU routed; in _sport_cfg_init             */
#define DIAG_STAGE_SPORT     3   /* half-SPORTs configured; in _dma_cfg_init   */
#define DIAG_STAGE_DMA       4   /* DMA rings + SEC + SPI2 up; enabling ints   */
#define DIAG_STAGE_WAITCFG   5   /* interrupts on, waiting for host config     */
#define DIAG_STAGE_CONFIGED  6   /* CONFIG_COMMIT applied, waiting for audio   */
#define DIAG_STAGE_RUNNING   7   /* audio blocks running                       */

/* At DIAG_STAGE_RUNNING the LED stops flashing codes and shows a steady
 * 1 Hz 50% square instead, so "healthy" is unmistakable at a glance and
 * is never confused with a 7-flash code. */
#define DIAG_STAGE_OK        DIAG_STAGE_RUNNING

/* ---------------------------------------------------------------------
 * Diagnostic register block. Reads use the existing SPI parameter
 * protocol with the READ flag (bit 13) set; see diag.asm for the
 * two-word response format.
 *
 * Everything here is READ-ONLY except the four marked RW/W.
 * ------------------------------------------------------------------- */
#define DIAG_BASE            0xE000

#define DIAG_MAGIC           0xE000  /* constant 0xD5B40001 — link is alive  */
#define DIAG_CHIP_ID         0xE001  /* 1 or 2 — which part answered this CS */
#define DIAG_BOOT_STAGE      0xE002  /* DIAG_STAGE_* above                   */
#define DIAG_BOOT_CFG        0xE003  /* _boot_config_received                */
#define DIAG_FRAME_COUNT     0xE004  /* audio blocks since reset (1500/s)    */
#define DIAG_TICKS           0xE005  /* diag timer ticks (nominally 1 kHz)   */
#define DIAG_SEC_COUNT       0xE006  /* SEC interrupts serviced              */
#define DIAG_LAST_CSID       0xE007  /* last SEC_CSID (37=block, 71=SPI2)    */
#define DIAG_UNK_CSID        0xE008  /* last SEC_CSID matching no handler    */
#define DIAG_UNK_COUNT       0xE009  /* count of those                       */
#define DIAG_BLK_OVERRUN     0xE00A  /* blocks the main loop failed to keep up */
#define DIAG_SPI_RX_COUNT    0xE00B  /* SPI param transactions received      */
#define DIAG_SPI_ERR_COUNT   0xE00C  /* SPI writes to unmapped addresses     */
#define DIAG_SPI_STAT        0xE00D  /* live SPI2_STAT                       */
#define DIAG_SPI_STAT_STK    0xE00E  /* sticky OR of SPI2_STAT since clear   */
#define DIAG_RESP_DROP       0xE00F  /* read responses dropped (TFIFO busy)  */
#define DIAG_PRODUCT_ID      0xE010  /* 0 = D32, 1 = D24                     */
#define DIAG_LED_MODE        0xE011  /* RW 0=auto 1=force off 2=force on     */
#define DIAG_SPORT0_ERR_A    0xE012  /* live SPORT0_ERR_A (block-clock lane) */
#define DIAG_DMA0_STAT       0xE013  /* live DMA0_STAT   (block-clock lane)  */
#define DIAG_SPI_CTL         0xE014  /* live SPI2_CTL   — did EMISO/FCPL take? */
#define DIAG_SPI_RXCTL       0xE015  /* live SPI2_RXCTL — is RUWM non-zero?  */
#define DIAG_SPI_TXCTL       0xE016  /* live SPI2_TXCTL — is TEN set?        */
#define DIAG_BUILD_ID        0xE017  /* build stamp 0xYYYYMMDD               */

#define DIAG_TABLE_N         0x18    /* entries in _diag_table (0xE000..)    */

/* Generic peek window — reads any MMR or DM address on a running DSP.
 * This is what replaces the emulator: write PEEK_ADDR, read PEEK_DATA.
 * There is no bounds check; an address that faults will fault. */
#define DIAG_PEEK_ADDR       0xE0F0  /* RW */
#define DIAG_PEEK_DATA       0xE0F1  /* R  */
/* Scope control (src/scope.asm). Named registers, NOT the peek window:
 * peek/poke take TWO transactions (set address, then move data) and under
 * audio load the answer to the second can belong to a different request --
 * bench 2026-08-23 read _frame_count as 0 and a gain coefficient as
 * 0xE0FE0000, which is the DIAG_NOP request word echoing back. One
 * transaction per register cannot desynchronise that way. */
#define DIAG_SCOPE_SRC       0xE0E0  /* W  word address to record          */
#define DIAG_SCOPE_INJ       0xE0E1  /* W  word address to drive (0 = off) */
#define DIAG_SCOPE_AMP       0xE0E2  /* W  value to inject                 */
#define DIAG_SCOPE_MODE      0xE0E3  /* W  1 = impulse, 2 = step           */
#define DIAG_SCOPE_ARM       0xE0E4  /* RW write 1 to start; 0 when full   */
#define DIAG_SCOPE_RD        0xE0E5  /* W  set the read cursor             */
#define DIAG_SCOPE_DATA      0xE0E6  /* R  buf[cursor], cursor auto-bumps  */
#define DIAG_SCOPE_LEN       0xE0E7  /* R  capacity in samples             */
#define DIAG_SCOPE_RUNS      0xE0E8  /* R  arm count -- proves a run happened */
#define DIAG_SCOPE_IDX       0xE0E9  /* R  samples recorded this run       */

/* NOP — accepted and ignored. The host sends this as the second half of
 * a read (see diag.asm); it must not itself generate a response. */
#define DIAG_NOP             0xE0FE  /* W */
#define DIAG_CLEAR           0xE0FF  /* W  write anything: zero the counters */

/* Core-timer reload, in CCLK cycles. 491520 at the measured CCLK of
 * 491.52 MHz is a 1 kHz diag tick. Shared: diag.asm programs TPERIOD
 * with it and main.asm uses it to convert ticks to cycles. */
#define DIAG_TPERIOD         491520

#define DIAG_MAGIC_VALUE     0xD5B40001
#define DIAG_BUILD_VALUE     0x20260812

#define DIAG_LED_AUTO        0
#define DIAG_LED_FORCE_OFF   1
#define DIAG_LED_FORCE_ON    2

#endif /* _DSP4_DIAG_H */
