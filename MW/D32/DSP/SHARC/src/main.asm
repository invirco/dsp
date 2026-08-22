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

/* Sample index within current block (0..31) */
.global _sample_idx;
.var _sample_idx = 0;


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
_spi_poll:
    r0 = dm(REG_SPI2_STAT);
    r1 = 0x00007000;               /* SPI_STAT.RFS, bits 14:12 */
    r0 = r0 and r1;
    r1 = 0x00004000;               /* RFS = 4 = Full: a whole request */
    comp(r0, r1);
    if ne rts;
    jump _spi2_rx_work;            /* tail call: its rts returns to us */
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
.wait_boot:
    /* Poll here as well as in the main loop: the config that releases
     * this loop arrives over the very link being polled, so without it
     * the firmware waits forever for a message nothing is collecting. */
    call _spi_poll;
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
    idle;                          /* low-power wait for DMA interrupt */

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
    call _spi_poll;

    r0 = dm(_block_ready);
    r1 = 0;
    comp(r0, r1);
    if eq jump (pc, .main_loop);

    /* Clear block-ready flag */
    r0 = 0;
    dm(_block_ready) = r0;

    /* Audio is flowing: the LED switches from fault codes to a steady
     * 1 Hz square. Restamped every block so a stall that leaves the
     * main loop alive still reads 7 — DIAG_FRAME_COUNT is the register
     * that tells you whether blocks are still arriving. */
    r0 = DIAG_STAGE_RUNNING;
    dm(_diag_boot_stage) = r0;

    /* ---- Block processing: 32 samples per block ---- */
#if CHIP_ID == 1

    /* ========== Chip 1 block loop ========== */
.block_chip1:
    r5 = 0;                       /* sample index */
    r6 = BLOCK_SIZE;

.c1_sample_loop:
    dm(_sample_idx) = r5;

    /* Scatter: DMA RX → input slot variables */
    r0 = r5;                      /* sample index arg */
    call _scatter_chip1;

    /* Process all Chip 1 nodes (single sample) */
    call _chip1_process_all;

    /* Gather: output slot variables → IC TX DMA buffer */
    r0 = dm(_sample_idx);         /* reload (process may have clobbered r5) */
    call _gather_chip1;

    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    comp(r5, r6);
    if lt jump (pc, .c1_sample_loop);

    /* Post-block: scan input slot vars for peak levels, then decay */
    call _meter_scan_chip1;
    r0 = 32;
    call _meter_decay_block;

    jump (pc, .main_loop);

#elif CHIP_ID == 2

    /* ========== Chip 2 block loop ========== */
.block_chip2:
    r5 = 0;
    r6 = BLOCK_SIZE;

.c2_sample_loop:
    dm(_sample_idx) = r5;

    /* Scatter: IC RX DMA → recv slot variables */
    r0 = r5;
    call _scatter_chip2;

    /* Process all Chip 2 nodes (single sample) */
    call _chip2_process_all;

    /* Gather: output slot variables → DAC TX DMA buffer */
    r0 = dm(_sample_idx);
    call _gather_chip2;

    r5 = dm(_sample_idx);
    r5 = r5 + 1;
    comp(r5, r6);
    if lt jump (pc, .c2_sample_loop);

    /* Post-block: scan output slot vars for peak levels, then decay */
    call _meter_scan_chip2;
    r0 = 18;
    call _meter_decay_block;

    jump (pc, .main_loop);

#endif /* CHIP_ID */

_start.end:
