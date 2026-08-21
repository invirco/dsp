/*======================================================================
 * clkprobe.asm — read the clock tree and the peripheral MMR space out
 * of a SHARC that has no emulator, over the one wire that leaves the
 * card: PB_05 (SPI2_RDY -> Pi GPIO8 for chip 1 / GPIO12 for chip 2).
 *
 * WHY: two questions blocked P2.2 and neither could be answered from
 * the bench.
 *   1. What is CCLK really? Every delay constant in this firmware
 *      assumes 400 MHz. The only evidence against it was the blink
 *      rate, and that number is worthless on its own because it also
 *      depends on an ASSUMED cycles-per-iteration for a two-instruction
 *      loop. This image times everything off the CORE TIMER instead,
 *      which decrements once per CCLK cycle by construction, so the
 *      measured pulse width is CCLK and nothing else.
 *   2. Does a READ of a system MMR return? sru_init() hangs on its
 *      first SRU() macro, and that macro is a read-modify-write — the
 *      READ comes first (sru21568.h, _SRU_ROUTE). A posted write to a
 *      dead peripheral is silently dropped; a read stalls the core
 *      forever. So "sru_init never returns" is consistent with the DAI0
 *      block simply not answering the bus.
 *
 * OUTPUT — a pulse-width frame on PB_05, decoded by
 * tools/pi/dsp4_clkprobe.py. One tick = TICK_CYCLES core-clock cycles.
 *
 *   phase A  3 pulses (1 tick high, 1 tick low), then an 8-tick gap.
 *            Uses no MMR read at all: it says "the image runs and the
 *            core timer counts", and nothing more.
 *   phase B  five 32-bit frames: the constant 0xA5C3F00D (so the host
 *            decoder is proved on a known value first), then CGU0_CTL,
 *            CGU0_DIV, CGU0_STAT, CGU0_DIVEX.
 *            Frame = 8 ticks high, 4 low, then 32 bits MSB
 *            first; a bit is 1 tick low preceded by 1 tick high (0) or
 *            3 ticks high (1).
 *   phase C  6 clean square periods, SQ_TICKS high / SQ_TICKS low. This
 *            is the absolute CCLK measurement: half period =
 *            SQ_TICKS * TICK_CYCLES / CCLK.
 *   phase D  two more frames, read LAST because either may hang:
 *            PORTB_DATA (a peripheral this image has already written to
 *            successfully) then DAI0_DAT0 (the register the first SRU()
 *            in sru_config.c read-modify-writes).
 *   phase E  6 more square periods, then the whole transcript repeats
 *            from phase B — so a capture can start at any moment. A pin
 *            that goes dead instead never got through phase D.
 *
 * Reading the transcript: A but no B = the CGU space is unreachable.
 * A+B+C but no D = a peripheral MMR read hangs, and how far into D it
 * got says which one. All five phases = every read returned and the
 * hang in sru_init is not a dead bus.
 *
 * No interrupts are enabled, so the two-slot blink IVT is enough and
 * the timer only ever reloads TCOUNT.
 *
 * Infrastructure (hand-maintained). Built by build.sh's "clkprobe"
 * target, per chip via -DCHIP_ID, into clkprobe1.ldr / clkprobe2.ldr.
 *======================================================================*/

#include <def21564.h>

#define RDY_BIT      (1 << 5)      /* PB_05 = SPI2_RDY net */

/* One tick. Small enough that TCOUNT stays well inside a signed 32-bit
 * compare, big enough that one tick is milliseconds at any CCLK the
 * part can be running at (400 MHz .. 1 GHz spec range): 2e6 cycles is
 * 2.0 ms at 1 GHz and 4.07 ms at the 491.52 MHz this card measured. The
 * host decoder works in RATIOS of ticks, so it does not need to know
 * which. */
#define TICK_CYCLES   2000000
#define SQ_TICKS      32           /* half period of the phase C/E square */

.section/pm seg_pmco;

.global _start;
_start:
    /* PB_05 -> GPIO output, driven low. FER clear selects GPIO over the
     * peripheral function, so the pin's MUX setting is irrelevant —
     * same idiom as rdyprobe.asm. These are WRITES; nothing here reads
     * an MMR, deliberately. */
    r0 = RDY_BIT;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;

    /* Core timer free-running. TMZLI stays masked and IRPTEN stays off,
     * so TCOUNT just wraps and reloads from TPERIOD; no vector is ever
     * taken and the two-entry IVT is safe. */
    r0 = TICK_CYCLES;
    tperiod = r0;
    tcount = r0;
    bit set mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;

    /* ---- phase A: alive, before any MMR read ---- */
    r8 = 3;
.alive_pulse:
    call _pin_hi;
    r1 = 1;
    call _wait_ticks;
    call _pin_lo;
    r1 = 1;
    call _wait_ticks;
    r8 = r8 - 1;
    if ne jump (pc, .alive_pulse);
    r1 = 8;
    call _wait_ticks;

    /* ---- phase B: the clock tree ----
     * A known constant goes first so the host decoder proves itself on
     * a word whose value is not in question before any register value
     * is believed. */
.frame_top:
    r4 = 0xA5C3F00D;
    call _dump_word;
    r4 = dm(REG_CGU0_CTL);
    call _dump_word;
    r4 = dm(REG_CGU0_DIV);
    call _dump_word;
    r4 = dm(REG_CGU0_STAT);
    call _dump_word;
    r4 = dm(REG_CGU0_DIVEX);
    call _dump_word;

    /* ---- phase C: the absolute CCLK measurement ---- */
    r8 = 6;
.square_a:
    call _pin_hi;
    r1 = SQ_TICKS;
    call _wait_ticks;
    call _pin_lo;
    r1 = SQ_TICKS;
    call _wait_ticks;
    r8 = r8 - 1;
    if ne jump (pc, .square_a);
    r1 = 8;
    call _wait_ticks;

    /* ---- phase D: the reads that may not return ---- */
    r4 = dm(REG_PORTB_DATA);
    call _dump_word;
    r4 = dm(REG_DAI0_DAT0);
    call _dump_word;

    /* ---- phase E: survived — mark it, then run the whole transcript
     * again, so a capture started at any moment sees a complete frame.
     * If a phase D read does NOT return, the pin simply goes dead here
     * and never repeats, which is the same verdict read the same way. */
    r8 = 6;
.square_e:
    call _pin_hi;
    r1 = SQ_TICKS;
    call _wait_ticks;
    call _pin_lo;
    r1 = SQ_TICKS;
    call _wait_ticks;
    r8 = r8 - 1;
    if ne jump (pc, .square_e);
    r1 = 8;
    call _wait_ticks;
    jump (pc, .frame_top);

_start.end:

/*----------------------------------------------------------------------
 * _pin_hi / _pin_lo — drive PB_05. Clobber r0 only.
 *--------------------------------------------------------------------*/
_pin_hi:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_SET) = r0;
    rts;
_pin_hi.end:

_pin_lo:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_CLR) = r0;
    rts;
_pin_lo.end:

/*----------------------------------------------------------------------
 * _wait_ticks — wait r1 core-timer reloads.
 *
 * TCOUNT counts DOWN once per CCLK cycle and reloads TPERIOD at zero,
 * so the only moment TCOUNT increases is a reload. Polling for that is
 * exact to within one poll iteration (a handful of cycles against
 * TICK_CYCLES = 4e6), and — unlike a calibrated delay loop — it does
 * not depend on how many cycles the loop itself takes. That is the
 * whole point of this image.
 *
 * In: r1 = ticks (>= 1). Clobbers r1, r2, r3.
 *--------------------------------------------------------------------*/
_wait_ticks:
    r2 = tcount;
.wt_loop:
    r3 = tcount;
    comp(r3, r2);
    if le jump (pc, .wt_next);
    r1 = r1 - 1;
    if eq rts;
.wt_next:
    r2 = r3;
    jump (pc, .wt_loop);
_wait_ticks.end:

/*----------------------------------------------------------------------
 * _dump_word — emit r4 as a framed 32-bit pulse-width word.
 *
 * Header 8 ticks high / 4 low, then bits MSB first: high 1 tick = 0,
 * high 3 ticks = 1, each followed by 1 tick low. 6 ticks low after the
 * last bit so the host can see the frame end.
 *
 * In: r4 = value (consumed). Clobbers r0..r6, r12.
 *--------------------------------------------------------------------*/
_dump_word:
    call _pin_hi;
    r1 = 8;
    call _wait_ticks;
    call _pin_lo;
    r1 = 4;
    call _wait_ticks;

    r12 = 32;
.dw_bit:
    r1 = 1;
    r5 = lshift r4 by -31;        /* MSB, zero-filled */
    r4 = lshift r4 by 1;
    r6 = pass r5;                 /* sets AZ from the bit */
    if eq jump (pc, .dw_drive);
    r1 = 3;
.dw_drive:
    call _pin_hi;
    call _wait_ticks;
    call _pin_lo;
    r1 = 1;
    call _wait_ticks;
    r12 = r12 - 1;
    if ne jump (pc, .dw_bit);

    r1 = 6;
    call _wait_ticks;
    rts;
_dump_word.end:
