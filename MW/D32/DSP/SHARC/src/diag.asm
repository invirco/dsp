/*======================================================================
 * diag.asm — bring-up diagnostics for the DSP4 card: a read-only
 * register block over the existing SPI parameter link, plus LED fault
 * codes on the per-DSP status LED.
 *
 * Rev C has NO emulator access to either SHARC: JTG_TCK/TMS/TDI/TDO and
 * JTG_TRST carry sheet-local stubs only and the ROOT DSPA/DSPB blocks
 * expose no JTAG ports, so nothing leaves the sheet (tasks.md,
 * 2026-08-11 addendum). The two channels that DO exist are the host SPI
 * link and one green LED per chip, and this file makes both carry state:
 *
 *   1. DIAGNOSTIC READBACK — a register block at 0xE000 that the CM4
 *      can interrogate on a running DSP: boot stage reached, SEC
 *      activity, block counter, SPI/SPORT/DMA error latches, and a
 *      generic peek window onto any MMR. That is most of what an
 *      emulator would be used for, over the link that already exists.
 *
 *   2. LED FAULT CODES — N flashes = "stuck after boot stage N" (see
 *      diag.h). Driven from the CORE TIMER, not from the audio block
 *      ISR, and started before any peripheral bring-up runs. That is
 *      the point: if the firmware hangs inside _sru_init, or the audio
 *      clock never arrives, or the SEC never fires, the LED keeps
 *      flashing the stage it got to. A heartbeat that depends on the
 *      thing being diagnosed tells you nothing.
 *
 * HARDWARE (rev-C schematic, DSPA page 5/10 and DSPB page 4/10 — the
 * two sheets are identical):
 *   PA_12 -> net BLINK_LED -> 1K series (R37 on DSPA/U6, R4 on DSPB/U5)
 *            -> green LED (LD3 on DSPA, LD2 on DSPB) -> GND.
 *   Drive HIGH to light. Each DSP owns its own LED; nothing else on the
 *   board drives these nets. PA_13 is the SHARED !BLINK net (LOGIC pin
 *   58 + supervisor) — an input here, never driven. Same pin and same
 *   polarity as src/blink/blink.asm, so the standalone blink image and
 *   the real firmware light the same LED.
 *
 * READ PROTOCOL. A read is a two-word SPI transaction like any other
 * write, with bit 13 (READ) set in word 0. But the RX watermark
 * interrupt only fires once BOTH words have been clocked in, by which
 * point the master has already shifted MISO for this transaction — so
 * the response cannot come back in the same transaction. The handler
 * pushes TWO words into SPI_TFIFO (which is exactly 2 deep at 32-bit
 * word size, HRM 15) and the master collects them on its NEXT
 * transaction:
 *
 *   transaction 1:  MOSI {addr|READ, 0}      MISO: previous/undefined
 *   transaction 2:  MOSI {DIAG_NOP, 0}       MISO: {echo, value}
 *
 * where echo is word 0 of the request, verbatim. The echo is what makes
 * this safe on a bench: the host can prove the answer belongs to the
 * question it asked, rather than trusting a pipeline it cannot see. If
 * the TFIFO is not empty when a response is due, the response is
 * DROPPED and DIAG_RESP_DROP counts it, rather than overflowing the
 * FIFO and silently shifting every later answer by one.
 *
 * Assembled once per chip via -DCHIP_ID. Infrastructure
 * (hand-maintained).
 *======================================================================*/

#include <def21564.h>
#include "diag.h"

/* PA_12 = BLINK_LED */
#define DIAG_LED_BIT      0x00001000

/* Core-timer period in CCLK cycles = one diag tick. Nominally 1 ms at
 * CCLK = 400 MHz, which is NOT yet measured on this board (same caveat
 * as blink.asm). The LED intervals below are in ticks, so if the
 * observed rate is off by N then CCLK is off by N — write the measured
 * number down rather than retuning this constant. DIAG_TICKS is
 * readable over SPI, so the CM4 can measure it directly: read TICKS,
 * sleep a known wall-clock second, read again. */
#define DIAG_TPERIOD      400000

/* LED intervals, in ticks. Fault code = N flashes then a long gap. */
#define DIAG_LED_ON       150
#define DIAG_LED_INTER    250     /* off, between flashes of one burst */
#define DIAG_LED_GAP      1200    /* off, between bursts */
/* Healthy: steady 1 Hz 50% square — visually distinct from any code. */
#define DIAG_LED_RUN_ON   500
#define DIAG_LED_RUN_OFF  500


.section/dm seg_dmda;

/* ---- Externally owned state that the register block exposes ---- */
.extern _chip_id;                 /* main.asm         */
.extern _boot_config_received;    /* main.asm         */
.extern _frame_count;             /* sport_init.asm   */
.extern _sec_active_csid;         /* sport_init.asm   */
.extern _product_id;              /* product_config.asm */
.extern _spi_rx_count;            /* chipN/spi_handler.asm */
.extern _spi_err_count;           /* chipN/spi_handler.asm */

/* ---- State owned here ---- */

/* Constants, held in DM so the table below can point at them uniformly. */
.var _diag_magic    = DIAG_MAGIC_VALUE;
.var _diag_build_id = DIAG_BUILD_VALUE;

.global _diag_boot_stage;
.var _diag_boot_stage = DIAG_STAGE_INIT;

.global _diag_ticks;
.var _diag_ticks = 0;             /* free-running; never cleared */

.global _diag_sec_count;
.var _diag_sec_count = 0;
.global _diag_unk_csid;
.var _diag_unk_csid = 0;
.global _diag_unk_count;
.var _diag_unk_count = 0;
.global _diag_blk_overrun;
.var _diag_blk_overrun = 0;
.global _diag_spi_stat_stk;
.var _diag_spi_stat_stk = 0;
.global _diag_resp_drop;
.var _diag_resp_drop = 0;

.global _diag_led_mode;
.var _diag_led_mode = DIAG_LED_AUTO;
.var _diag_peek_addr = 0;

/* LED state machine */
.var _diag_led_rem   = 1;         /* ticks left in the current interval */
.var _diag_led_state = 0;         /* 0 = LED off, 1 = LED on */
.var _diag_led_left  = 0;         /* flashes still owed in this burst  */

/*----------------------------------------------------------------------
 * _diag_table — DIAG_BASE + index -> address to read.
 *
 * Every readable register is "the 32-bit word at some address", so DM
 * variables and live MMRs share one mechanism: a peripheral entry just
 * holds the MMR address. A 0 entry reads back as 0.
 *----------------------------------------------------------------------*/
.var _diag_table[DIAG_TABLE_N] =
    _diag_magic,            /* 0xE000 MAGIC          */
    _chip_id,               /* 0xE001 CHIP_ID        */
    _diag_boot_stage,       /* 0xE002 BOOT_STAGE     */
    _boot_config_received,  /* 0xE003 BOOT_CFG       */
    _frame_count,           /* 0xE004 FRAME_COUNT    */
    _diag_ticks,            /* 0xE005 TICKS          */
    _diag_sec_count,        /* 0xE006 SEC_COUNT      */
    _sec_active_csid,       /* 0xE007 LAST_CSID      */
    _diag_unk_csid,         /* 0xE008 UNK_CSID       */
    _diag_unk_count,        /* 0xE009 UNK_COUNT      */
    _diag_blk_overrun,      /* 0xE00A BLK_OVERRUN    */
    _spi_rx_count,          /* 0xE00B SPI_RX_COUNT   */
    _spi_err_count,         /* 0xE00C SPI_ERR_COUNT  */
    REG_SPI2_STAT,          /* 0xE00D SPI_STAT  (live MMR) */
    _diag_spi_stat_stk,     /* 0xE00E SPI_STAT_STK   */
    _diag_resp_drop,        /* 0xE00F RESP_DROP      */
    _product_id,            /* 0xE010 PRODUCT_ID     */
    _diag_led_mode,         /* 0xE011 LED_MODE       */
    REG_SPORT0_ERR_A,       /* 0xE012 SPORT0_ERR_A (live MMR) */
    REG_DMA0_STAT,          /* 0xE013 DMA0_STAT    (live MMR) */
    REG_SPI2_CTL,           /* 0xE014 SPI_CTL      (live MMR) */
    REG_SPI2_RXCTL,         /* 0xE015 SPI_RXCTL    (live MMR) */
    REG_SPI2_TXCTL,         /* 0xE016 SPI_TXCTL    (live MMR) */
    _diag_build_id;         /* 0xE017 BUILD_ID       */


.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _diag_init — bring up the LED pin and the core timer.
 *
 * Called from _start BEFORE any peripheral bring-up, and it enables
 * interrupts globally on the way out. At that point only TMZLI is
 * unmasked, so the only thing that can fire is _diag_timer_isr, which
 * banks the low register file and touches no DAG register — it is safe
 * to have running underneath the C config functions.
 *----------------------------------------------------------------------*/
.global _diag_init;
_diag_init:
    /* PA_12 -> GPIO output, driven low. FER bit clear selects GPIO over
     * the peripheral function, which makes the pin's MUX setting moot. */
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_FER_CLR)  = r0;
    dm(REG_PORTA_INEN_CLR) = r0;
    dm(REG_PORTA_DATA_CLR) = r0;
    dm(REG_PORTA_DIR_SET)  = r0;

    /* Core timer: TCOUNT counts CCLK cycles down to 0, raises TMZLI,
     * and reloads from TPERIOD. Independent of the SEC, the SPORTs and
     * the audio clock — which is exactly why the fault codes survive a
     * failure in any of them. */
    r0 = DIAG_TPERIOD;
    tperiod = r0;
    tcount = r0;

    bit set imask BITM_REGF_IMASK_TMZLI;
    bit set mode2 BITM_REGF_MODE2_TIMEN;
    bit set mode1 BITM_REGF_MODE1_IRPTEN;
    nop;
    nop;
    rts;
_diag_init.end:

/*----------------------------------------------------------------------
 * _diag_timer_isr — TMZLI vector (IVT offset 0x058).
 *
 * ~1 kHz. Banks the low register file (SRRFL covers r0-r7) and uses NO
 * DAG register, so it needs no assumption about the secondary bank's L
 * registers and cannot disturb the ramp path or the block loop. TMZLI
 * is lower priority than SECI, so audio always wins; interrupt nesting
 * is off, so this can never preempt _sec_isr.
 *
 * It also wakes the main loop out of `idle` about 1000 times a second.
 * The loop re-checks _block_ready and goes straight back to idle, which
 * costs a handful of cycles against 1500 block interrupts a second.
 *----------------------------------------------------------------------*/
.global _diag_timer_isr;
_diag_timer_isr:
    bit set mode1 BITM_REGF_MODE1_SRRFL;
    nop;
    push sts;

    r0 = dm(_diag_ticks);
    r0 = r0 + 1;
    dm(_diag_ticks) = r0;

    /* Manual override: force the LED off or on, e.g. to identify which
     * physical card or which of the two chips you are talking to. */
    r0 = dm(_diag_led_mode);
    r1 = DIAG_LED_FORCE_OFF;
    comp(r0, r1);
    if eq jump (pc, .diag_led_off_now);
    r1 = DIAG_LED_FORCE_ON;
    comp(r0, r1);
    if eq jump (pc, .diag_led_on_now);

    /* Current interval still running? */
    r0 = dm(_diag_led_rem);
    r0 = r0 - 1;
    dm(_diag_led_rem) = r0;
    r1 = 0;
    comp(r0, r1);
    if gt jump (pc, .diag_tick_done);

    /* Interval expired — advance the state machine.
     * r4 = flashes per burst, r5 = on ticks, r6 = inter-flash off,
     * r7 = burst gap. */
    call _diag_led_params;

    r0 = dm(_diag_led_state);
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .diag_led_to_off);

    /* ---- was OFF -> turn ON ---- */
    r0 = dm(_diag_led_left);
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .diag_led_have_left);
    r0 = r4;                       /* burst finished: reload the count */
.diag_led_have_left:
    r0 = r0 - 1;
    dm(_diag_led_left) = r0;

    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_SET) = r0;
    r0 = 1;
    dm(_diag_led_state) = r0;
    dm(_diag_led_rem) = r5;
    jump (pc, .diag_tick_done);

.diag_led_to_off:
    /* ---- was ON -> turn OFF ---- */
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_CLR) = r0;
    r0 = 0;
    dm(_diag_led_state) = r0;

    r0 = dm(_diag_led_left);
    r1 = 0;
    comp(r0, r1);
    if eq jump (pc, .diag_led_gap);
    dm(_diag_led_rem) = r6;        /* more flashes to come in this burst */
    jump (pc, .diag_tick_done);
.diag_led_gap:
    dm(_diag_led_rem) = r7;
    jump (pc, .diag_tick_done);

.diag_led_off_now:
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_CLR) = r0;
    r0 = 0;
    dm(_diag_led_state) = r0;
    r0 = 1;
    dm(_diag_led_rem) = r0;        /* re-evaluate next tick */
    jump (pc, .diag_tick_done);

.diag_led_on_now:
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_SET) = r0;
    r0 = 1;
    dm(_diag_led_state) = r0;
    dm(_diag_led_rem) = r0;
    /* fall through */

.diag_tick_done:
    pop sts;
    bit clr mode1 BITM_REGF_MODE1_SRRFL;
    nop;
    rti;
_diag_timer_isr.end:

/*----------------------------------------------------------------------
 * _diag_led_params — blink shape for the current boot stage.
 * Out: r4 = flashes per burst, r5 = on ticks, r6 = inter-flash off
 *      ticks, r7 = burst gap ticks.
 *----------------------------------------------------------------------*/
.global _diag_led_params;
_diag_led_params:
    r4 = dm(_diag_boot_stage);
    r5 = DIAG_STAGE_OK;
    comp(r4, r5);
    if lt jump (pc, .diag_params_fault);

    /* Healthy: one long flash, one long gap = a 1 Hz square. */
    r4 = 1;
    r5 = DIAG_LED_RUN_ON;
    r6 = DIAG_LED_RUN_ON;
    r7 = DIAG_LED_RUN_OFF;
    rts;

.diag_params_fault:
    /* Clamp to 1..15 so a corrupted stage cannot produce a burst that
     * never ends (the LED would look permanently on). */
    r5 = 1;
    comp(r4, r5);
    if ge jump (pc, .diag_params_hi);
    r4 = 1;
.diag_params_hi:
    r5 = 15;
    comp(r4, r5);
    if le jump (pc, .diag_params_go);
    r4 = 15;
.diag_params_go:
    r5 = DIAG_LED_ON;
    r6 = DIAG_LED_INTER;
    r7 = DIAG_LED_GAP;
    rts;
_diag_led_params.end:

/*----------------------------------------------------------------------
 * _diag_read — resolve one diagnostic register.
 * In:  r2 = SPI address (>= DIAG_BASE)
 * Out: r4 = value (0 for anything unmapped)
 * Clobbers r4, r5, i0, m0. PRESERVES r0-r3 — the caller still needs
 * r0 (the request word) for the response echo.
 *----------------------------------------------------------------------*/
.global _diag_read;
_diag_read:
    r4 = DIAG_PEEK_DATA;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_peek);

    r4 = DIAG_BASE;
    r4 = r2 - r4;                 /* table index */
    r5 = DIAG_TABLE_N;
    comp(r4, r5);
    if ge jump (pc, .diag_rd_zero);

    i0 = _diag_table;
    m0 = r4;
    modify(i0, m0);
    r4 = dm(i0, 0);               /* address to read */
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .diag_rd_zero);
    i0 = r4;
    r4 = dm(i0, 0);
    rts;

.diag_rd_peek:
    /* The emulator substitute: whatever address was last written to
     * DIAG_PEEK_ADDR. Deliberately unchecked — the point is to reach
     * MMRs nobody thought to name here. Peeking a bad address will
     * fault the DSP, which on this board looks like a hang. */
    r4 = dm(_diag_peek_addr);
    r5 = 0;
    comp(r4, r5);
    if eq jump (pc, .diag_rd_zero);
    i0 = r4;
    r4 = dm(i0, 0);
    rts;

.diag_rd_zero:
    r4 = 0;
    rts;
_diag_read.end:

/*----------------------------------------------------------------------
 * _diag_write — the four writable diagnostic registers.
 * In: r2 = SPI address (>= DIAG_BASE, < 0xF000), r1 = value.
 * Anything else in range is ignored rather than counted as an error:
 * DIAG_NOP relies on that (it is the host's "give me the response"
 * transaction and must not itself queue one).
 * Clobbers r4.
 *----------------------------------------------------------------------*/
.global _diag_write;
_diag_write:
    r4 = DIAG_LED_MODE;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_led);
    r4 = DIAG_PEEK_ADDR;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_peek);
    r4 = DIAG_CLEAR;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_clear);
    rts;

.diag_wr_led:
    dm(_diag_led_mode) = r1;
    rts;

.diag_wr_peek:
    dm(_diag_peek_addr) = r1;
    rts;

.diag_wr_clear:
    /* Counters and sticky latches only. _diag_ticks and _frame_count
     * are deliberately NOT cleared: they are the two free-running rate
     * references, and a bench measurement that resets its own clock is
     * no measurement. */
    r4 = 0;
    dm(_diag_sec_count)    = r4;
    dm(_diag_unk_count)    = r4;
    dm(_diag_unk_csid)     = r4;
    dm(_diag_blk_overrun)  = r4;
    dm(_diag_spi_stat_stk) = r4;
    dm(_diag_resp_drop)    = r4;
    dm(_spi_rx_count)      = r4;
    dm(_spi_err_count)     = r4;
    rts;
_diag_write.end:
