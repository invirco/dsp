/*======================================================================
 * main.asm — Entry point for D32 DSP (both Chip 1 and Chip 2)
 *
 * Boot sequence:
 *   1. Hardware reset → interrupt vector table → _start
 *   2. Publish the compile-time chip identity (-DCHIP_ID)
 *   3. Register bring-up: SRU + SPORT + DMA/SEC/SPI (C config files)
 *   4. Wait for Pi product config (PRODUCT_ID, CHAN_MASK, ... + COMMIT)
 *   5. Enter main loop: wait for _block_ready, run 32-sample block
 *
 * Block processing (per DMA completion):
 *   For each sample n in [0..31]:
 *     1. Scatter: DMA RX buffer[n] → per-node _rx_slot_* variables
 *     2. Call process chain (all nodes, single sample)
 *     3. Gather: per-node _tx_slot_* variables → DMA TX buffer[n]
 *
 * Ramp counters run at sample rate (frame counts × BLOCK_SIZE).
 * One firmware source serves both chips and both products (D3), but
 * it builds TWO images — chip1.dxe and chip2.dxe, selected by
 * -DCHIP_ID and slave-booted into their own part over their own CS.
 * Chip-specific runtime paths read _chip_id.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

#include <def21564.h>
#include "diag.h"
#include "c_abi.h"

/* Chip identity is COMPILE-TIME, not detected. Resolved 2026-08-11
 * against the rev-C schematic: the DSPA (U6) and DSPB (U5) sheets are
 * identical, so there is no per-chip strap to read — the two parts
 * differ only in which host chip select reaches them (CS1 -> DSPA,
 * CS2 -> DSPB), and each is slave-booted with its own image over that
 * CS. The old runtime detect read "FLAG0" at an invented address
 * (0x08004040); the 2156x has no FLAG pins at all, so it could only
 * ever have returned garbage. -DCHIP_ID=1|2 is the single source. */
#define BLOCK_SIZE  32

.section/dm seg_dmda;

.global _chip_id;
.var _chip_id = 0;                /* 1 = Chip 1 (Input DSP), 2 = Chip 2 (Output DSP) */

/* Boot config received flag (set by product_config.asm CONFIG_COMMIT) */
.global _boot_config_received;
.var _boot_config_received = 0;

/* Build-flag stamp, carried INTO the image and readable off the running
 * part. A bisect is only as good as the guarantee that the flag it names
 * actually reached the assembler; on 2026-08-23 four DSP4_STUB_* defines
 * silently did not, because a build.sh string replace matched nothing,
 * and a whole day of stub results turned out to be one identical image.
 * Peek this and compare against what was asked for -- that closes the
 * loop through the assembler, the linker, the loader and the boot. */
.global _build_flags;
.var _build_flags =
      (DSP4_BLOCK_MASK        & 0xF)
    | ((DSP4_NODE_LIMIT       & 0xFFF) << 4)
    | ((DSP4_COMMIT_STAGE     & 0x3)   << 16)
    | ((DSP4_NO_IDLE_OVERRIDE & 0x1)   << 18)
    | ((DSP4_STUB_COMPGAIN    & 0x7)   << 19)
    | ((DSP4_STUB_EXP2        & 0x1)   << 22)
    | ((DSP4_STUB_LOG2        & 0x1)   << 23)
    | ((DSP4_STUB_POLY        & 0x1)   << 24)
    | ((DSP4_COMP_NOCVT       & 0x1)   << 25)
    | ((DSP4_BLOCK_DECIMATE   & 0x3F)  << 26);
/* Second stamp word — the first is full. */
.global _build_flags2;
.var _build_flags2 = (DSP4_STRIPS & 0x3F);
/* Non-zero while _spi_poll is running, so the 1 kHz tick cannot re-enter
 * a drain the main loop is already half way through. */
.var _spi_poll_busy = 0;
/* Block decimation counter — see DSP4_BLOCK_DECIMATE in the main loop. */
.var _blk_decim = 0;

/* Block-processing cost accounting, at CCLK resolution.
 *
 * TCOUNT counts core clocks down to 0 and reloads from TPERIOD, and the
 * diag tick ISR fires on each reload. Combining the two gives the exact
 * cycle cost of one block pass:
 *
 *   cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
 *          + (tcount_start - tcount_end)
 *
 * Exact per pass, so one sample is a measurement rather than a sample of
 * a distribution -- which matters, because differencing 1 ms-quantised
 * averages could not resolve a single node (about 4,700 cycles) against
 * the noise of a 2,000-pass total. _proc_cyc is the last pass, _proc_cyc_max
 * the worst seen. */
.global _proc_cyc;
.var _proc_cyc = 0;
.global _proc_cyc_max;
.var _proc_cyc_max = 0;
.global _proc_passes;
.var _proc_passes = 0;
.var _proc_t0 = 0;
.var _proc_c0 = 0;

/* Sample index within current block (0..31) */
.global _sample_idx;
.var _sample_idx = 0;


#if DSP4_BQ_SELFTEST
.extern _bq_selftest;
#endif

.section/pm seg_pmco;

/* External symbols */
.extern _sru_init;
.extern _sport_cfg_init;
.extern _dma_cfg_init;
.extern _diag_init;
#if DSP4_BISECT >= 5
.extern _bisect_park_asm;
#endif
.extern _diag_boot_stage;
#if DSP4_BISECT == 27
.extern _spi2_rx_work;
#endif
#if DSP4_BISECT == 23
.extern _bisect_dump_asm, _diag_ticks, _diag_sec_count;
.extern _diag_unk_csid, _diag_unk_count, _spi_rx_count;
#endif
.extern ldf_stack_space, ldf_stack_length;
.extern _block_ready;
.extern _rx_active_buf, _tx_active_buf;
.extern _ic_rx_active_buf, _ic_tx_active_buf;
.extern _meter_decay_block;
#if CHIP_ID == 1
.extern _meter_scan_chip1;
#elif CHIP_ID == 2
.extern _meter_scan_chip2;
#endif

#if CHIP_ID == 1
.extern _chip1_process_all;
.extern _scatter_chip1, _gather_chip1;
#elif CHIP_ID == 2
.extern _chip2_process_all;
.extern _scope_inject, _scope_record;
.extern _scatter_chip2, _gather_chip2;
#else
#error "CHIP_ID must be defined as 1 or 2"
#endif

/*----------------------------------------------------------------------
 * _start — Reset entry point
 *----------------------------------------------------------------------*/
/*----------------------------------------------------------------------
 * _spi_poll — collect one parameter request if a whole one has arrived.
 *
 * The link is polled, not interrupt-driven: SEC delivery could enter the
 * handler while the host was still clocking, so the FIFO-full condition
 * was momentarily true mid-transfer and the drain took one real word
 * plus one still arriving. Polling only ever looks BETWEEN transactions.
 * Called from .wait_boot and from the main loop; both wake at least at
 * the 1 kHz diag tick, far above what this link needs.
 * Clobbers r0, r1 and whatever _spi2_rx_work clobbers.
 *--------------------------------------------------------------------*/
.global _spi_poll;
_spi_poll:
    /* Reentrancy guard. This is called from the main loop AND from the
     * 1 kHz diag timer ISR, and the ISR can preempt the loop in the
     * middle of a drain. A plain flag is enough and is race-free in the
     * one direction that exists: the ISR can interrupt the loop, the
     * loop can never interrupt the ISR, so the ISR simply declines when
     * the loop is already inside. */
    r0 = dm(_spi_poll_busy);
    r1 = 0;
    comp(r0, r1);
    if ne rts;
    r1 = 1;
    dm(_spi_poll_busy) = r1;

    r0 = dm(REG_SPI2_STAT);
    r1 = 0x00007000;               /* SPI_STAT.RFS, bits 14:12 */
    r0 = r0 and r1;
    r1 = 0x00004000;               /* RFS = 4 = Full: a whole request */
    comp(r0, r1);
    if ne jump (pc, .spi_poll_out);
    call _spi2_rx_work;            /* call, not tail-jump: the flag below */
.spi_poll_out:
    r0 = 0;
    dm(_spi_poll_busy) = r0;
    rts;
_spi_poll.end:

.global _start;
_start:
#if DSP4_BISECT == 5
    /* TEMP bisect rung 0 (2026-08-21, tasks.md NOW item 3 deletes it):
     * park on the FIRST instruction the boot stream hands control to,
     * before anything else exists — no stack, no diag timer, no C. Five
     * pulses on PB_05 (Pi GPIO8/GPIO12) therefore means exactly one
     * thing: the .ldr landed and the part is executing our code. Silence
     * means it is not, and nothing downstream of it can be read. */
    r4 = 5;
    call _bisect_park_asm;      /* never returns */
#endif

    /* Chip identity: compile-time (see the note at the top of this
     * file). Kept in _chip_id so the runtime paths are unchanged. */
    r0 = CHIP_ID;
    dm(_chip_id) = r0;

    /* ---- C runtime for the C config functions ----
     * The stack out of the LDF's RESERVE(ldf_stack_space,
     * ldf_stack_length) block AND the compiler's DAG registers. This
     * used to set only B/I/L; M7 and M14 were left at whatever the boot
     * kernel had put in them, which broke both halves of the cc21k call
     * convention and is why the first C call (_sru_init) never returned.
     * See src/c_abi.h for the convention and the evidence. */
    C_RUNTIME_INIT

    /* Interrupts: start from a known state. The SPI target boot kernel
     * runs with interrupts of its own and hands control over with
     * whatever it had unmasked still in IMASK and whatever it had taken
     * still latched in IRPTL. _diag_init only ORs TMZLI in, so anything
     * the kernel left enabled survives into our firmware and fires into
     * an IVT that has no handler for it the moment _diag_init sets
     * IRPTEN. CCES's own ___lib_setup_c clears both for exactly this
     * reason; this firmware does not link it, so it does it here. */
    r0 = 0;
    imask = r0;
    irptl = r0;
    nop;
    nop;

#if DSP4_BISECT == 6
    /* TEMP bisect rung (2026-08-21, goes with the rest of the
     * DSP4_BISECT scaffolding): the C stack is set up and nothing has
     * touched a peripheral yet. Six pulses = _start ran its prologue. */
    r4 = 6;
    call _bisect_park_asm;      /* never returns */
#endif

    /* Diagnostics FIRST, before any peripheral touches hardware: it
     * arms the core timer that drives the LED fault codes, so from here
     * on a hang anywhere below still flashes the stage it reached
     * (diag.asm). It enables interrupts globally too — only TMZLI is
     * unmasked at this point, so nothing else can fire yet. */
    call _diag_init;

#if DSP4_BISECT == 7
    /* TEMP bisect rung: _diag_init returned — core timer armed, LED
     * alive. Seven pulses. */
    r4 = 7;
    call _bisect_park_asm;
#endif

    /* Register bring-up (C, per dsp4-plumbing.md): DAI/SRU routing,
     * half-SPORT multichannel config, then DDE descriptor rings + SEC
     * + SPI2 slave + SPEN (dma_config.c also hands the asm side its
     * buffer pointers). Each stamp means "the call above returned", so
     * N flashes on the LED reads as "stuck in step N+1". */
    CCALL(_sru_init)
    r0 = DIAG_STAGE_SRU;
    dm(_diag_boot_stage) = r0;

#if DSP4_BISECT == 8 || DSP4_BISECT == 10
    /* TEMP bisect rung: _sru_init returned. Eight pulses for the whole
     * function; ten when sru_config.c has been cut short at the
     * DAI0/DAI1 boundary (rung 10 there), which is how the hang inside
     * it is split between the two halves. */
    r4 = DSP4_BISECT;
    call _bisect_park_asm;
#endif

    CCALL(_sport_cfg_init)
    r0 = DIAG_STAGE_SPORT;
    dm(_diag_boot_stage) = r0;

#if DSP4_BISECT == 9
    /* TEMP bisect rung: _sport_cfg_init returned; the next call is
     * _dma_cfg_init. Nine pulses. */
    r4 = 9;
    call _bisect_park_asm;
#endif

    CCALL(_dma_cfg_init)
    r0 = DIAG_STAGE_DMA;
    dm(_diag_boot_stage) = r0;

    /* Unmask the SEC core interrupt and enable interrupts globally —
     * needed before .wait_boot: the product config arrives over SPI. */
    bit set imask BITM_REGF_IMASK_SECI;
    bit set mode1 BITM_REGF_MODE1_IRPTEN;
    nop;

    r0 = DIAG_STAGE_WAITCFG;
    dm(_diag_boot_stage) = r0;

#if DSP4_BISECT >= 23 && DSP4_BISECT <= 26
    /* TEMP bisect rung 23 (2026-08-22) — did the SPI interrupt path ever
     * run?
     *
     * With the SPI2 pins finally routed (dma_config.c spi2_init), the
     * part drives MISO — but it drives ONE constant word forever, the
     * same value whatever the host sends, at every clock and in either
     * mode. That is a TX FIFO that nobody ever loads: the receive side
     * is not being serviced. This rung waits with interrupts ON so the
     * host can transact, then shuts everything off and frames the
     * counters that say which link in the chain is missing —
     * SEC route -> SEC ISR -> SPI handler.
     *
     * Rung 24 is the same thing with SECI masked, so only the core
     * timer can interrupt. Rung 25 masks EVERYTHING, and is the control
     * that has to be run first: it proves the dump instrument itself
     * works, without which 23 and 24 going quiet prove nothing.
     *
     * Decode with `dsp4_clkprobe.py --frame secspi`. */
#if DSP4_BISECT == 24 || DSP4_BISECT == 26
    bit clr imask BITM_REGF_IMASK_SECI;
    nop;
    nop;
#elif DSP4_BISECT == 25
    r0 = 0;
    imask = r0;
    nop;
    nop;
#endif
    /* Wait with a plain busy loop, NOT on _diag_ticks. Whether the core
     * timer ISR runs at all is one of the things this rung is asking —
     * waiting on its counter would deadlock on exactly the failure it
     * is meant to report, which is what the first version of this rung
     * did. ~450e6 iterations at 13 cycles is about 12 s at 491.52 MHz.
     * Interrupts stay ON throughout so the host can transact. */
    r9 = 450000000;
.b23_wait:
    r9 = r9 - 1;
    if ne jump (pc, .b23_wait);

    bit clr mode1 BITM_REGF_MODE1_IRPTEN;
    bit clr mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;

    /* Take PB_05 back off SPI2 flow control to report on it. */
    r0 = 0x00000020;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;

.b23_frame:
    r4 = 0xA5C3F00D;              /* proves the decoder */
    call _bisect_dump_asm;
    r4 = dm(_diag_ticks);         /* is the core timer ISR alive? */
    call _bisect_dump_asm;
    r4 = dm(_diag_sec_count);     /* did the SEC ISR ever fire? */
    call _bisect_dump_asm;
    r4 = dm(_spi_rx_count);       /* did the SPI handler ever run? */
    call _bisect_dump_asm;
    r4 = dm(_diag_boot_stage);    /* 6 = CONFIG_COMMIT applied */
    call _bisect_dump_asm;
    r4 = dm(_boot_config_received);
    call _bisect_dump_asm;
    r4 = dm(REG_SPI2_STAT);       /* live: RUWM, TUR, RFIFO state */
    call _bisect_dump_asm;
    r4 = dm(_diag_resp_drop);     /* answers dropped: TFIFO was not empty */
    call _bisect_dump_asm;
    r4 = dm(_product_id);         /* CFG_PRODUCT_ID as the part stored it */
    call _bisect_dump_asm;
    /* No extra gap: _bisect_dump_asm already ends every word with a
     * 6-unit low, and the host aligns the transcript on the constant. */
    jump (pc, .b23_frame);
#endif

#if DSP4_BISECT == 21
    /* TEMP bisect rung 21 (2026-08-21): everything before the host
     * handshake has run — SRU, SPORTs, DMA rings, SEC, SPI2 — and the
     * core is about to sit in .wait_boot. Three LONG pulses, because
     * this is _bisect_park_asm's busy loop (~400 ms each at the
     * measured 491.52 MHz CCLK) and not the much shorter C park in
     * dma_config.c, so the two are never confused. It takes PB_05 back
     * off SPI2 flow control, so it is a diagnostic build only. */
    r4 = 3;
    call _bisect_park_asm;
#endif

    /* Wait for product config from the Pi/CM4 host (D1) — the host
     * writes the 0xF000+ config registers then CONFIG_COMMIT, which
     * applies input patch + scope gates and sets the flag below. */
#if DSP4_BISECT >= 30 && DSP4_BISECT <= 32
    /* TEMP bisect rung 30 (2026-08-23) — SELF-CONFIGURE and report from
     * inside the running main loop.
     *
     * Two things this fixes about rung 29. First, it does not need the
     * host at all: it applies the product config itself, so a flaky
     * parameter link cannot stop the measurement. Second, and this is
     * what made rung 29 useless, the wait happens INSIDE the main loop
     * rather than before it — rung 29 busy-waited ahead of .main_loop,
     * so the block loop never ran and FRAME_COUNT could not have moved
     * whatever the hardware was doing.
     *
     * The question it answers: with the loopback bitstream on the CPLD,
     * does a single audio block ever arrive? */
    r0 = 1;                        /* d24 */
    dm(_product_id) = r0;
    call _product_config_commit;   /* sets _boot_config_received + stage 6 */
#endif

.wait_boot:
    /* Poll here as well as in the main loop: the config that releases
     * this loop arrives over the very link being polled, so without it
     * the firmware waits forever for a message nothing is collecting. */
#if !DSP4_POLL_ISR_ONLY
    call _spi_poll;
#endif
#if DSP4_BISECT == 27
    /* TEMP bisect rung 27 (2026-08-22) — POLL the SPI instead of waiting
     * for the SEC to deliver its interrupt.
     *
     * The handler runs exactly ONCE per reset even though the RFIFO is
     * verifiably EMPTY at init (rung 22 after the flush: RFE=1, ROR=0,
     * RUWM=0) and the SPI2_STAT route is correct (SEC0_SCTL71 = 0x5).
     * That splits into two candidates: the SPI block never re-raises, or
     * the SEC never re-delivers. Polling SPI_STAT.RFE and calling the
     * SAME handler answers it — if the link round-trips when polled, the
     * SPI side is sound and the fault is in interrupt delivery.
     *
     * This is a diagnostic, not a design change: the parameter link is
     * meant to be interrupt-driven so it cannot steal cycles from the
     * audio block loop. */
.poll_spi:
    r0 = dm(0x31030040);          /* SPI2_STAT */
    r1 = 0x00400000;              /* RFE, bit 22: 1 = RFIFO empty */
    r0 = r0 and r1;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .poll_spi);   /* empty — nothing to collect */
    call _spi2_rx_work;
    jump (pc, .poll_spi);
#endif
    r0 = dm(_boot_config_received);
    r1 = 0;
    comp(r0, r1);
    if eq jump (pc, .wait_boot);

#if DSP4_BISECT >= 30 && DSP4_BISECT <= 32
    /* Reachable ONLY by the branch from inside the loop. Without this
     * jump the report sits in the straight-line path and executes on the
     * way past, before the main loop has run a single iteration —
     * which is exactly how rung 29 produced a FRAME_COUNT of 0 that
     * meant nothing (and, the first time round, a DIAG_TICKS of 0 that
     * gave the game away). */
    jump (pc, .main_loop);
.b30_report:
    bit clr mode1 BITM_REGF_MODE1_IRPTEN;
    bit clr mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;
    r0 = 0x00000020;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;
.b30_frame:
    r4 = 0xA5C3F00D;
    call _bisect_dump_asm;
    r4 = dm(_diag_ticks);
    call _bisect_dump_asm;
    r4 = dm(_diag_sec_count);     /* any SEC interrupt at all? */
    call _bisect_dump_asm;
    r4 = dm(_frame_count);        /* AUDIO BLOCKS — the whole question */
    call _bisect_dump_asm;
    r4 = dm(_diag_boot_stage);
    call _bisect_dump_asm;
    r4 = dm(_diag_unk_csid);
    call _bisect_dump_asm;
    r4 = dm(REG_SPORT0_ERR_A);
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_STAT);
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_CFG);        /* did our CFG write take? */
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_ADDRSTART);  /* the buffer address the DDE holds */
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_DSCPTR_NXT); /* consumed by the fetch attempt? */
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_DSCPTR_CUR); /* what it actually tried to fetch */
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_XCNT);       /* loaded from the descriptor? (want 256) */
    call _bisect_dump_asm;
    r4 = dm(REG_CDU0_STAT);       /* are the CDU outputs actually running? */
    call _bisect_dump_asm;
    r4 = dm(REG_CDU0_CFG0);
    call _bisect_dump_asm;
    r4 = dm(REG_CDU0_CFG1);
    call _bisect_dump_asm;
    r4 = dm(REG_CGU0_STAT);
    call _bisect_dump_asm;
    r4 = dm(REG_SPORT0_CTL_A);    /* is the SPORT itself enabled? */
    call _bisect_dump_asm;
    jump (pc, .b30_frame);
#endif

#if DSP4_BISECT == 29
    /* TEMP bisect rung 29 (2026-08-22) — report from AFTER the host
     * handshake. CONFIG_COMMIT has been applied and the firmware is
     * about to enter the audio main loop, a path that had never
     * executed on hardware until today: stage 6 was only ever proven on
     * a build that parked in .wait_boot. The bench sees the parameter
     * link go dead immediately after a successful commit, so the
     * question is whether the core survives the transition at all and
     * whether any audio block ever arrives. Wait with interrupts ON so
     * blocks can flow, then dump. */
    r9 = 200000000;
.b29_wait:
    r9 = r9 - 1;
    if ne jump (pc, .b29_wait);

    bit clr mode1 BITM_REGF_MODE1_IRPTEN;
    bit clr mode2 BITM_REGF_MODE2_TIMEN;
    nop;
    nop;
    r0 = 0x00000020;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;
.b29_frame:
    r4 = 0xA5C3F00D;
    call _bisect_dump_asm;
    r4 = dm(_diag_ticks);         /* core alive? */
    call _bisect_dump_asm;
    r4 = dm(_diag_sec_count);     /* any SEC interrupt at all? */
    call _bisect_dump_asm;
    r4 = dm(_frame_count);        /* audio blocks since reset */
    call _bisect_dump_asm;
    r4 = dm(_diag_boot_stage);
    call _bisect_dump_asm;
    r4 = dm(_diag_unk_csid);      /* a SEC source with no handler? */
    call _bisect_dump_asm;
    r4 = dm(REG_SPORT0_ERR_A);    /* the block-clock lane */
    call _bisect_dump_asm;
    r4 = dm(REG_DMA0_STAT);       /* named, not guessed: an unmapped
                                   * MMR read HANGS the core, and a
                                   * guessed 0x31022008 did exactly
                                   * that here on 2026-08-22 */
    call _bisect_dump_asm;
    r4 = dm(_diag_unk_count);
    call _bisect_dump_asm;
    jump (pc, .b29_frame);
#endif

    /* ---- Main loop ---- */
.main_loop:
#if DSP4_BQ_SELFTEST
    /* Selftest runs ONCE from the main loop, and the placement took three
     * attempts to get right:
     *   - from CONFIG_COMMIT it executed inside the diag timer ISR (which
     *     services the parameter link as a backstop), with the secondary
     *     register file live and a 1 ms timer waiting to re-enter;
     *   - before interrupts were enabled it blocked the boot handshake, so
     *     host SPI traffic arrived with nothing draining the RFIFO and the
     *     response stream came up permanently out of phase.
     * Here the link is up, the graph is configured, and this is ordinary
     * main-loop context. */
    r0 = dm(_bqst_done);
    r0 = pass r0;
    if ne jump (pc, .bqst_skip);
    call _bq_selftest;
.bqst_skip:
#endif
    /* NO `idle` HERE. It used to be, as a low-power wait for the DMA
     * interrupt, and it wedged the parameter link the instant the loop
     * was entered -- which is to say the instant CONFIG_COMMIT released
     * .wait_boot. That is why the card looked dead after configuration
     * while being perfectly healthy before it: .wait_boot spins, this
     * loop slept.
     *
     * Bisected on the bench 2026-08-23 with three independent guards,
     * all other things equal:
     *
     *   block work off, commit applies off, idle ON   -> link dead
     *   block work off, commit applies ON,  idle off  -> BOOT_STAGE 7,
     *                                                    1500 blocks/s,
     *                                                    link healthy
     *
     * so it is the instruction itself, not the config, not the commit's
     * apply calls and not the block loop. Spinning costs power this card
     * does not care about; the interrupts that matter still preempt. */
#if DSP4_NO_IDLE_OVERRIDE
    idle;
#endif

    /* ---- Parameter link, POLLED (2026-08-22) ----
     * The SPI2 request FIFO is serviced from here rather than from the
     * SEC. Interrupt delivery for this source could enter the handler
     * while the host was still clocking a transaction, so the FIFO-full
     * condition was momentarily true mid-transfer and the drain took
     * one real word plus one still arriving — reads came back with
     * words duplicated or dropped. Polling only ever looks BETWEEN
     * transactions, which is exactly why the polled variant read
     * cleanly where the interrupt path did not (bench 2026-08-22).
     *
     * Cost is nil: the loop already wakes on the 1 kHz diag tick even
     * with no audio, and once per block (1500/s) with audio, which is
     * far above what a parameter link needs. The SEC keeps the audio
     * block clock, which is the source that actually has to be
     * interrupt-driven. sec_init() no longer routes SPI2_STAT. */
#if !DSP4_POLL_ISR_ONLY
    call _spi_poll;
#endif

#if DSP4_BISECT >= 30 && DSP4_BISECT <= 32
    /* Let the loop actually RUN for ~8 s, then report. */
    r0 = dm(_diag_ticks);
    r1 = 8000;
    comp(r0, r1);
    if ge jump (pc, .b30_report);
#endif

    r0 = dm(_block_ready);
    r1 = 0;
    comp(r0, r1);
    if eq jump (pc, .main_loop);

    /* Clear block-ready flag */
    r0 = 0;
    dm(_block_ready) = r0;

#if DSP4_BLOCK_DECIMATE > 1
    /* Process only every Nth block, to buy the node graph N times the
     * per-block cycle budget without changing WHAT it computes. This
     * separates "a node is broken" from "the graph does not fit in a
     * block period" -- the two look identical from outside, because a
     * main loop that never finishes a block never services the link
     * either. Audio is wrong while this is on; it is a measurement, not
     * a mode. */
    r0 = dm(_blk_decim);
    r0 = r0 + 1;
    r1 = DSP4_BLOCK_DECIMATE;
    comp(r0, r1);
    if lt jump (pc, .decim_skip);
    r0 = 0;
.decim_skip:
    dm(_blk_decim) = r0;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .main_loop);
#endif

    /* Audio is flowing: the LED switches from fault codes to a steady
     * 1 Hz square. Restamped every block so a stall that leaves the
     * main loop alive still reads 7 — DIAG_FRAME_COUNT is the register
     * that tells you whether blocks are still arriving. */
    r0 = DIAG_STAGE_RUNNING;
    dm(_diag_boot_stage) = r0;

    /* ---- Block processing: 32 samples per block ---- */
    r0 = dm(_diag_ticks);
    dm(_proc_t0) = r0;
    r0 = tcount;
    dm(_proc_c0) = r0;

#if CHIP_ID == 1

    /* ========== Chip 1 block loop ========== */
.block_chip1:
#if DSP4_BLOCK_KERNELS
    /* Per-BLOCK kernels. Scatter the WHOLE block into the 32-word input
     * arrays, run each node exactly once, then gather the whole block.
     * The node chain no longer pays a call/rts and a _sample_idx guard
     * 32 times over; the loop lives inside the kernel. */
    r5 = 0;
.c1_scat_loop:
    dm(_sample_idx) = r5;
    r0 = r5;
#if DSP4_BLOCK_MASK & 1
    call _scatter_chip1;
#endif
    call _scope_inject;
    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c1_scat_loop);

#if DSP4_BLOCK_MASK & 2
    call _chip1_process_all;
#endif

    r5 = 0;
.c1_gath_loop:
    dm(_sample_idx) = r5;
    call _scope_record;
#if !DSP4_POLL_ISR_ONLY
    r0 = dm(_sample_idx);
    r1 = 7;
    r0 = r0 AND r1;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .skip_poll_bk1);
    call _spi_poll;
.skip_poll_bk1:
#endif
    r0 = dm(_sample_idx);
#if DSP4_BLOCK_MASK & 4
    call _gather_chip1;
#endif
    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c1_gath_loop);
#else
    r5 = 0;                       /* sample index */
    r6 = BLOCK_SIZE;

.c1_sample_loop:
    dm(_sample_idx) = r5;

    /* Scatter: DMA RX → input slot variables */
    r0 = r5;                      /* sample index arg */
#if DSP4_BLOCK_MASK & 1
    call _scatter_chip1;
#endif

    /* Stimulus: the one point where an input slot holds a value the
     * node chain has not yet consumed. Off unless the host armed it. */
    call _scope_inject;

    /* Process all Chip 1 nodes (single sample) */
#if DSP4_BLOCK_MASK & 2
    call _chip1_process_all;
#endif

    /* Capture the watched node output for this sample. */
    call _scope_record;

    /* Service the parameter link PER SAMPLE, not per block.
     *
     * The main loop polls it once per block, so the DSP answers ~1500/s
     * while the host can clock ~10 transactions into a single block
     * period at 1 MHz. The surplus overruns the response FIFO, and a
     * dropped answer comes back as a well-formed (echo, 0) -- a wrong
     * value that cannot be told from a real one. Measured 2026-08-23:
     * ~8 reads in 25 correct under a 1-strip load, and a dropped scope
     * ARM write silently returned the PREVIOUS capture, which made a
     * working signal chain read as dead at the first node.
     *
     * Every 8th sample, not every sample: 6000 polls/s is still far above
     * any burst the host can produce, at an eighth of the cost. Polling
     * on EVERY sample was too expensive for CHIP 2 -- after CONFIG_COMMIT
     * it stopped restamping _diag_boot_stage (BOOT_STAGE read 0, link
     * intermittent), the signature of a main loop that can no longer
     * finish a block. Chip 1 carried it fine, and chip 1 was the only one
     * being checked, which is how it went unnoticed for four families. */
#if !DSP4_POLL_ISR_ONLY
    r0 = dm(_sample_idx);
    r1 = 7;
    r0 = r0 AND r1;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .skip_poll_c1);
    call _spi_poll;
.skip_poll_c1:
#endif

    /* Gather: output slot variables → IC TX DMA buffer */
    r0 = dm(_sample_idx);         /* reload (process may have clobbered r5) */
#if DSP4_BLOCK_MASK & 4
    call _gather_chip1;
#endif

    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    /* Reload the bound. _scatter_chipN and _gather_chipN BOTH load the
     * active DMA buffer address into r6 -- ~0x95350 -- so the loop bound
     * set before .cN_sample_loop is gone by the time we get here. The
     * compare below then ran the 32-sample loop about 610,000 times per
     * block, which is not a fault but is indistinguishable from a hang:
     * the main loop never comes back, the parameter link goes dead, and
     * that is exactly what the card did from the instant CONFIG_COMMIT
     * released .wait_boot. r5 is already reloaded from _sample_idx two
     * lines up for precisely this reason; r6 was missed. */
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c1_sample_loop);

#endif
    /* Post-block: scan input slot vars for peak levels, then decay */
    call _meter_scan_chip1;
    r0 = 32;
    call _meter_decay_block;

    /* cycles = ticks_elapsed * TPERIOD + (tcount_start - tcount_now) */
    r2 = tcount;
    r0 = dm(_diag_ticks);
    r1 = dm(_proc_t0);
    r0 = r0 - r1;
    r1 = DIAG_TPERIOD;
    r0 = r0 * r1 (SSI);
    r1 = dm(_proc_c0);
    r1 = r1 - r2;
    r0 = r0 + r1;
    dm(_proc_cyc) = r0;
    r1 = dm(_proc_cyc_max);
    comp(r0, r1);
    if le jump (pc, .proc_nomax);
    dm(_proc_cyc_max) = r0;
.proc_nomax:
    r0 = dm(_proc_passes);
    r0 = r0 + 1;
    dm(_proc_passes) = r0;

    jump (pc, .main_loop);

#elif CHIP_ID == 2

    /* ========== Chip 2 block loop ========== */
.block_chip2:
#if DSP4_BLOCK_KERNELS
    /* Per-BLOCK kernels. Scatter the WHOLE block into the 32-word input
     * arrays, run each node exactly once, then gather the whole block.
     * The node chain no longer pays a call/rts and a _sample_idx guard
     * 32 times over; the loop lives inside the kernel. */
    r5 = 0;
.c2_scat_loop:
    dm(_sample_idx) = r5;
    r0 = r5;
#if DSP4_BLOCK_MASK & 1
    call _scatter_chip2;
#endif
    call _scope_inject;
    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c2_scat_loop);

#if DSP4_BLOCK_MASK & 2
    call _chip2_process_all;
#endif

    r5 = 0;
.c2_gath_loop:
    dm(_sample_idx) = r5;
    call _scope_record;
#if !DSP4_POLL_ISR_ONLY
    r0 = dm(_sample_idx);
    r1 = 7;
    r0 = r0 AND r1;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .skip_poll_bk2);
    call _spi_poll;
.skip_poll_bk2:
#endif
    r0 = dm(_sample_idx);
#if DSP4_BLOCK_MASK & 4
    call _gather_chip2;
#endif
    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c2_gath_loop);
#else
    r5 = 0;
    r6 = BLOCK_SIZE;

.c2_sample_loop:
    dm(_sample_idx) = r5;

    /* Scatter: IC RX DMA → recv slot variables */
    r0 = r5;
#if DSP4_BLOCK_MASK & 1
    call _scatter_chip2;
#endif

    /* Stimulus: the one point where an input slot holds a value the
     * node chain has not yet consumed. Off unless the host armed it. */
    call _scope_inject;

    /* Process all Chip 2 nodes (single sample) */
#if DSP4_BLOCK_MASK & 2
    call _chip2_process_all;
#endif

    /* Capture the watched node output for this sample. */
    call _scope_record;

    /* Service the parameter link PER SAMPLE, not per block.
     *
     * The main loop polls it once per block, so the DSP answers ~1500/s
     * while the host can clock ~10 transactions into a single block
     * period at 1 MHz. The surplus overruns the response FIFO, and a
     * dropped answer comes back as a well-formed (echo, 0) -- a wrong
     * value that cannot be told from a real one. Measured 2026-08-23:
     * ~8 reads in 25 correct under a 1-strip load, and a dropped scope
     * ARM write silently returned the PREVIOUS capture, which made a
     * working signal chain read as dead at the first node.
     *
     * Every 8th sample, not every sample: 6000 polls/s is still far above
     * any burst the host can produce, at an eighth of the cost. Polling
     * on EVERY sample was too expensive for CHIP 2 -- after CONFIG_COMMIT
     * it stopped restamping _diag_boot_stage (BOOT_STAGE read 0, link
     * intermittent), the signature of a main loop that can no longer
     * finish a block. Chip 1 carried it fine, and chip 1 was the only one
     * being checked, which is how it went unnoticed for four families. */
#if !DSP4_POLL_ISR_ONLY
    r0 = dm(_sample_idx);
    r1 = 7;
    r0 = r0 AND r1;
    r1 = 0;
    comp(r0, r1);
    if ne jump (pc, .skip_poll_c2);
    call _spi_poll;
.skip_poll_c2:
#endif

    /* Gather: output slot variables → DAC TX DMA buffer */
    r0 = dm(_sample_idx);
#if DSP4_BLOCK_MASK & 4
    call _gather_chip2;
#endif

    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    /* Reload the bound. _scatter_chipN and _gather_chipN BOTH load the
     * active DMA buffer address into r6 -- ~0x95350 -- so the loop bound
     * set before .cN_sample_loop is gone by the time we get here. The
     * compare below then ran the 32-sample loop about 610,000 times per
     * block, which is not a fault but is indistinguishable from a hang:
     * the main loop never comes back, the parameter link goes dead, and
     * that is exactly what the card did from the instant CONFIG_COMMIT
     * released .wait_boot. r5 is already reloaded from _sample_idx two
     * lines up for precisely this reason; r6 was missed. */
    r6 = BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .c2_sample_loop);

#endif
    /* Post-block: scan output slot vars for peak levels, then decay */
    call _meter_scan_chip2;
    r0 = 18;
    call _meter_decay_block;

    /* cycles = ticks_elapsed * TPERIOD + (tcount_start - tcount_now) */
    r2 = tcount;
    r0 = dm(_diag_ticks);
    r1 = dm(_proc_t0);
    r0 = r0 - r1;
    r1 = DIAG_TPERIOD;
    r0 = r0 * r1 (SSI);
    r1 = dm(_proc_c0);
    r1 = r1 - r2;
    r0 = r0 + r1;
    dm(_proc_cyc) = r0;
    r1 = dm(_proc_cyc_max);
    comp(r0, r1);
    if le jump (pc, .proc_nomax);
    dm(_proc_cyc_max) = r0;
.proc_nomax:
    r0 = dm(_proc_passes);
    r0 = r0 + 1;
    dm(_proc_passes) = r0;

    jump (pc, .main_loop);

#endif /* CHIP_ID */

_start.end:
