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
#include "c_abi.h"

.extern _scope_buf, _scope_src, _scope_inj, _scope_amp;
.extern _scope_mode, _scope_idx, _scope_arm, _scope_len, _scope_rd, _scope_go;

/* PA_12 = BLINK_LED */
#define DIAG_LED_BIT      0x00001000

/*----------------------------------------------------------------------
 * TEMP bisect mirror (P2.2, 2026-08-21) — goes with the rest of the
 * DSP4_BISECT scaffolding (tasks.md NOW item 3).
 *
 * The LED is the only instrument that can see inside dma_cfg_init, and
 * LD3/LD2 need a human at the card. PB_05 is the SPI2_RDY net, which
 * leaves the card as CS3/CS4 and lands on the Pi as GPIO8 (chip 1) /
 * GPIO12 (chip 2) — the same pin src/blink/rdyprobe.asm uses. Mirroring
 * every LED transition onto it makes the whole stage/flash code readable
 * over ssh, so a bisect round costs a `pinctrl get 8` sample instead of
 * a trip to the bench.
 *
 * Only in a DSP4_BISECT build. Production must NOT take this pin: at
 * runtime SPI2_RDY is the SPI2 flow-control output (dma_config.c
 * spi2_init, FCEN), and driving it as GPIO would break host flow
 * control. Every bisect variant parks before spi2_init runs, so the two
 * never contend. It also means the part cannot be re-booted without a
 * !RST_D pulse (dsp4_boot.py's default), same caveat as rdyprobe.
 *--------------------------------------------------------------------*/
#if DSP4_BISECT
#define DIAG_RDY_BIT      0x00000020        /* PB_05 = SPI2_RDY */
/* Busy-loop counts for _bisect_park_asm — 13 cycles per iteration at
 * the measured CCLK of 491.52 MHz (see the note by DIAG_TPERIOD), so
 * these land near 400 ms and 3.2 s. dsp4_stagewatch.py decodes ratios,
 * not absolute times, so the exact figures do not matter; they are only
 * documented so a transcript can be read without re-deriving them. */
#define DIAG_PARK_PULSE   15000000
#define DIAG_PARK_GAP    120000000
#define DIAG_MIRROR_HI    r0 = DIAG_RDY_BIT; dm(REG_PORTB_DATA_SET) = r0;
#define DIAG_MIRROR_LO    r0 = DIAG_RDY_BIT; dm(REG_PORTB_DATA_CLR) = r0;
#define DIAG_MIRROR_INIT  r0 = DIAG_RDY_BIT; \
                          dm(REG_PORTB_FER_CLR)  = r0; \
                          dm(REG_PORTB_INEN_CLR) = r0; \
                          dm(REG_PORTB_DATA_CLR) = r0; \
                          dm(REG_PORTB_DIR_SET)  = r0;
#else
#define DIAG_MIRROR_HI
#define DIAG_MIRROR_LO
#define DIAG_MIRROR_INIT
#endif

/* CCLK = 491.52 MHz, MEASURED 2026-08-21 off the core timer with
 * src/blink/clkprobe.asm and cross-checked against the CGU registers
 * read out of the running part: SYS_CLKIN0 24.576 MHz, CGU reset
 * defaults DF=0 MSEL=40 CSEL=1 SYSSEL=2 S0SEL=4, and the 2156x PLL's
 * built-in /2 — exactly the tree dsp4-architecture-decisions.md D10
 * predicted. The firmware does NOT program the CGU; it corrects its own
 * constants instead (D10 addendum). A two-instruction delay loop costs
 * 13 cycles per iteration on this core, not the 5 these files used to
 * assume; that factor, not the clock, is what made the blink images
 * look 2.1x slow and produced the retracted "~190 MHz" estimate. */

/* Core-timer period in CCLK cycles = one diag tick: 1.000 ms at the
 * measured clock. The LED intervals below are in ticks, so they now
 * mean what they say in milliseconds. DIAG_TICKS is readable over SPI,
 * so the CM4 can confirm it: read TICKS, sleep a known wall-clock
 * second, read again. */
/* DIAG_TPERIOD now lives in diag.h — main.asm needs it too, for the
 * block-cost accounting (cycles = ticks * TPERIOD + tcount delta). */

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
.extern _spi_poll;                /* main.asm — parameter link poll */
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

/* Bring-up diagnostics for the DMA descriptor hand-off (2026-08-23).
 * C cannot touch a word-addressed .var directly, which is why this goes
 * through a setter exactly like _diag_stage_set. */
.global _dbg_dscptr;
.var _dbg_dscptr = 0;
.global _dbg_desc0;
.var _dbg_desc0 = 0;

/* SPI2 stuck-partial-request recovery, see _diag_timer_isr. */
.var _spi_partial_ticks = 0;
.global _spi_partial_fix;
.var _spi_partial_fix = 0;

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
.global _diag_stage_set;

/* TEMP bisect helper 2026-08-19: C-callable stage stamp
   (C data refs cannot touch the word-addressed .var directly). */
_diag_stage_set:
    dm(_diag_boot_stage) = r4;
    C_RETURN

/* TEMP bring-up helper 2026-08-23: record what arm_region handed the DDE.
   In: r4 = descriptor address as written, r8 = first descriptor word. */
.global _dbg_set_dscptr;
_dbg_set_dscptr:
    dm(_dbg_dscptr) = r4;
    dm(_dbg_desc0) = r8;
    C_RETURN

#if DSP4_BISECT
/* TEMP bisect helper 2026-08-21: shut the core timer and global
   interrupts off, so a bisect park owns PB_05 outright instead of
   fighting _diag_timer_isr's mirror for the pin. C cannot reach MODE1 /
   MODE2, hence the helper. Goes with the rest of the scaffolding. */
.global _diag_irq_off;
_diag_irq_off:
    bit clr mode1 BITM_REGF_MODE1_IRPTEN;
    bit clr mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;
    C_RETURN
_diag_irq_off.end:

/*----------------------------------------------------------------------
 * _bisect_park_asm — TEMP bisect park, callable from the very first
 * instruction of _start (2026-08-21).
 *
 * Same reporting convention as bisect_park() in dma_config.c: r4 pulses
 * on PB_05 (SPI2_RDY -> Pi GPIO8 / GPIO12), then a long gap, forever.
 * This one depends on NOTHING — no C stack, no interrupts, no timer, no
 * peripheral except the GPIO block — so it answers "did this image
 * execute at all?" rather than "did some subsystem survive?".
 *
 * In: r4 = pulses per burst (the stage code). Never returns.
 *----------------------------------------------------------------------*/
.global _bisect_park_asm;
_bisect_park_asm:
    bit clr mode1 BITM_REGF_MODE1_IRPTEN;
    nop;
    r8 = r4;                          /* burst length, preserved */

    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;

.park_burst:
    r9 = r8;                          /* pulses left in this burst */
.park_pulse:
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_SET) = r0;
    r1 = DIAG_PARK_PULSE;
    call _park_delay;
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_CLR) = r0;
    r1 = DIAG_PARK_PULSE;
    call _park_delay;
    r9 = r9 - 1;
    if ne jump (pc, .park_pulse);
    r1 = DIAG_PARK_GAP;
    call _park_delay;
    jump (pc, .park_burst);

_park_delay:
    r1 = r1 - 1;
    if ne jump (pc, _park_delay);
    rts;
_bisect_park_asm.end:

/*----------------------------------------------------------------------
 * _bisect_dump_asm — TEMP (2026-08-22): put a 32-bit value on PB_05 in
 * the same pulse-width framing src/blink/clkprobe.asm uses, so
 * tools/pi/dsp4_clkprobe.py decodes it unchanged.
 *
 * The C version of this lives in dma_config.c (rung 22). This one is in
 * assembly because the values worth reading at the host handshake are
 * the diagnostic counters, and those are word-addressed `.var`s that C
 * cannot reach — the same reason _diag_stage_set exists.
 *
 * Assumes interrupts and the core timer are already off and PB_05 is
 * already a driven GPIO output. In: r4 = value (consumed). Clobbers
 * r0, r1, r5, r6, r12.
 *--------------------------------------------------------------------*/
#define DIAG_DUMP_UNIT   750000       /* ~20 ms at 13 cycles/iteration */

.global _bisect_dump_asm;
_bisect_dump_asm:
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_SET) = r0;
    r1 = 8 * DIAG_DUMP_UNIT;
    call _park_delay;
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_CLR) = r0;
    r1 = 4 * DIAG_DUMP_UNIT;
    call _park_delay;

    r12 = 32;
.bd_bit:
    r1 = DIAG_DUMP_UNIT;
    r5 = lshift r4 by -31;        /* MSB, zero-filled */
    r4 = lshift r4 by 1;
    r6 = pass r5;                 /* sets AZ from the bit */
    if eq jump (pc, .bd_drive);
    r1 = 3 * DIAG_DUMP_UNIT;
.bd_drive:
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_SET) = r0;
    call _park_delay;
    r0 = DIAG_RDY_BIT;
    dm(REG_PORTB_DATA_CLR) = r0;
    r1 = DIAG_DUMP_UNIT;
    call _park_delay;
    r12 = r12 - 1;
    if ne jump (pc, .bd_bit);

    r1 = 6 * DIAG_DUMP_UNIT;
    call _park_delay;
    rts;
_bisect_dump_asm.end:
#endif

.global _diag_init;
_diag_init:
    /* PA_12 -> GPIO output, driven low. FER bit clear selects GPIO over
     * the peripheral function, which makes the pin's MUX setting moot. */
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_FER_CLR)  = r0;
    dm(REG_PORTA_INEN_CLR) = r0;
    dm(REG_PORTA_DATA_CLR) = r0;
    dm(REG_PORTA_DIR_SET)  = r0;

    DIAG_MIRROR_INIT

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
    /* Full register file + DAG1, not just the low half: this ISR now
     * services the parameter link as a backstop and _diag_read
     * addresses its table through i0. Same set as _sec_isr. */
    bit set mode1 BITM_REGF_MODE1_SRRFL | BITM_REGF_MODE1_SRRFH |
                  BITM_REGF_MODE1_SRD1L | BITM_REGF_MODE1_SRD1H;
    nop;
    push sts;

    r0 = dm(_diag_ticks);
    r0 = r0 + 1;
    dm(_diag_ticks) = r0;

    /* ---- SPI2 stuck-partial-request recovery (2026-08-22) ----
     *
     * A parameter request is TWO words and _spi2_rx_work only drains
     * when SPI_RFIFO is FULL, so a single stale word left in the FIFO
     * wedges the link permanently: the level can never reach FULL again
     * and every later request is one word out of phase behind it.
     *
     * That is not hypothetical. Bench 2026-08-22: after boot the part
     * sat at SPI_STAT = 0x00142001 - RFS = 2, i.e. ONE word of two -
     * with SEC_COUNT and SPI_RX_COUNT frozen at 74 and identical across
     * runs with completely different host traffic, because the handler
     * had stopped being able to fire at all. The residue arrives around
     * the boot handover: spi2_init's EN-low flush happens before the
     * host has finished with the port, so a fragment can land after it.
     *
     * A real request only sits half-arrived for microseconds, so three
     * consecutive 1 ms ticks in that state means stale. Discard one
     * word; if it is still stuck next time, discard another. Cheaper
     * and less disruptive than an EN off/on, which would also throw
     * away a legitimately queued answer. */
    r0 = dm(REG_SPI2_STAT);
    r1 = 0x00007000;              /* SPI_STAT.RFS, bits 14:12 */
    r0 = r0 and r1;
    r1 = 0;
    comp(r0, r1);
    if eq jump (pc, .spi_rx_settled);      /* empty: nothing pending */
    r1 = 0x00004000;              /* RFS = 4 = Full: handler will take it */
    comp(r0, r1);
    if eq jump (pc, .spi_rx_settled);

    r0 = dm(_spi_partial_ticks);
    r0 = r0 + 1;
    dm(_spi_partial_ticks) = r0;
    r1 = 3;
    comp(r0, r1);
    if lt jump (pc, .spi_rx_checked);
    r0 = dm(REG_SPI2_RFIFO);      /* discard one stale word */
    r0 = 0;
    dm(_spi_partial_ticks) = r0;
    r0 = dm(_spi_partial_fix);
    r0 = r0 + 1;
    dm(_spi_partial_fix) = r0;    /* how often this had to fire */
    jump (pc, .spi_rx_checked);

.spi_rx_settled:
    r0 = 0;
    dm(_spi_partial_ticks) = r0;
.spi_rx_checked:

    /* ---- BACKSTOP: service the parameter link from the tick ----
     *
     * The main loop polls the link too, and while it keeps up that is
     * where the work happens -- it is far lower latency than 1 kHz. But
     * the loop stops keeping up the moment there is real audio: with
     * blocks arriving at 1500/s the per-block processing owns it, and
     * from the instant CONFIG_COMMIT lands the handler is never reached
     * at all. Bench 2026-08-23, with answer-every-transaction in place
     * so that ANY handler entry would echo: every read after
     * CONFIG_COMMIT returned 0x00000000, i.e. the handler was not
     * running, not merely out of phase.
     *
     * NOT gated on being the only poller -- _spi_poll carries a
     * reentrancy flag for that. It IS gated on boot stage: this tick
     * starts at DIAG_STAGE_INIT, long before dma_cfg_init has run
     * spi2_init, and polling a peripheral that is still being brought
     * up raced spi2_init's EN-low flush and wedged the link from boot.
     * That is what broke the first attempt at moving the poll here. */
    r0 = dm(_diag_boot_stage);
    r1 = DIAG_STAGE_DMA;
    comp(r0, r1);
    if lt jump (pc, .spi_poll_skip);
    call _spi_poll;
.spi_poll_skip:

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
    DIAG_MIRROR_HI
    r0 = 1;
    dm(_diag_led_state) = r0;
    dm(_diag_led_rem) = r5;
    jump (pc, .diag_tick_done);

.diag_led_to_off:
    /* ---- was ON -> turn OFF ---- */
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_CLR) = r0;
    DIAG_MIRROR_LO
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
    DIAG_MIRROR_LO
    r0 = 0;
    dm(_diag_led_state) = r0;
    r0 = 1;
    dm(_diag_led_rem) = r0;        /* re-evaluate next tick */
    jump (pc, .diag_tick_done);

.diag_led_on_now:
    r0 = DIAG_LED_BIT;
    dm(REG_PORTA_DATA_SET) = r0;
    DIAG_MIRROR_HI
    r0 = 1;
    dm(_diag_led_state) = r0;
    dm(_diag_led_rem) = r0;
    /* fall through */

.diag_tick_done:
    pop sts;
    bit clr mode1 BITM_REGF_MODE1_SRRFL | BITM_REGF_MODE1_SRRFH |
                  BITM_REGF_MODE1_SRD1L | BITM_REGF_MODE1_SRD1H;
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
    r4 = DIAG_SCOPE_DATA;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_data);
    r4 = DIAG_SCOPE_ARM;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_arm);
    r4 = DIAG_SCOPE_LEN;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_len);
    /* The write registers read back too. A write on this link is
     * fire-and-forget and IS dropped under audio load, and a scope armed
     * with a source of 0 records silence -- which is indistinguishable
     * from a real null measurement. Read-back is what tells the two
     * apart, so every arm verifies. */
    r4 = DIAG_SCOPE_SRC;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_src);
    r4 = DIAG_SCOPE_INJ;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_inj);
    r4 = DIAG_SCOPE_AMP;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_amp);
    r4 = DIAG_SCOPE_MODE;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_mode);
    r4 = DIAG_SCOPE_RD;
    comp(r2, r4);
    if eq jump (pc, .diag_rd_scope_rd);

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

.diag_rd_scope_data:
    /* Deliberately does NOT advance the cursor. The host sets _scope_rd
     * and reads this, so the read is idempotent and can be retried; an
     * auto-incrementing register cannot be, and every read here needs
     * retrying because the link answers out of step under audio load. */
    r4 = dm(_scope_rd);
    r5 = _scope_buf;
    r5 = r5 + r4;
    i0 = r5;
    r4 = dm(i0, 0);
    rts;

.diag_rd_scope_arm:
    r4 = dm(_scope_arm);
    rts;

.diag_rd_scope_len:
    r4 = dm(_scope_len);
    rts;

.diag_rd_scope_src:
    r4 = dm(_scope_src);
    rts;
.diag_rd_scope_inj:
    r4 = dm(_scope_inj);
    rts;
.diag_rd_scope_amp:
    r4 = dm(_scope_amp);
    rts;
.diag_rd_scope_mode:
    r4 = dm(_scope_mode);
    rts;
.diag_rd_scope_rd:
    r4 = dm(_scope_rd);
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
    r4 = DIAG_SCOPE_SRC;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_src);
    r4 = DIAG_SCOPE_INJ;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_inj);
    r4 = DIAG_SCOPE_AMP;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_amp);
    r4 = DIAG_SCOPE_MODE;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_mode);
    r4 = DIAG_SCOPE_RD;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_rd);
    r4 = DIAG_SCOPE_ARM;
    comp(r2, r4);
    if eq jump (pc, .diag_wr_scope_arm);
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

.diag_wr_scope_src:
    dm(_scope_src) = r1;
    rts;
.diag_wr_scope_inj:
    dm(_scope_inj) = r1;
    rts;
.diag_wr_scope_amp:
    dm(_scope_amp) = r1;
    rts;
.diag_wr_scope_mode:
    dm(_scope_mode) = r1;
    rts;
.diag_wr_scope_rd:
    dm(_scope_rd) = r1;
    rts;
.diag_wr_scope_arm:
    /* Arming also rewinds the write index, so the host cannot start a
     * capture on top of the previous one's tail. */
    r4 = 0;
    dm(_scope_idx) = r4;
    dm(_scope_go)  = r4;
    dm(_scope_arm) = r1;
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
