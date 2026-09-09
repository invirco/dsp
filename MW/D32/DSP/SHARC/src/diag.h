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

/* DSP4_BLOCK_SIZE, for DIAG_BUILD_CFG_VALUE below. Generated. */
#include "dsp_block.h"

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

#ifndef DSP4_CFG_WATCH
#define DSP4_CFG_WATCH 0
#endif

#if DSP4_CFG_WATCH
#define DIAG_TABLE_N         0x24    /* + the CONFIG_COMMIT watch block     */
#elif DSP4_SIMD_STRIPS
#define DIAG_TABLE_N         0x19    /* + IICDI_COUNT at 0xE018 */
#else
#define DIAG_TABLE_N         0x18    /* entries in _diag_table (0xE000..)    */
#endif
#define DIAG_IICDI_COUNT     0xE018

/* ---- CONFIG_COMMIT watch (DSP4_CFG_WATCH, diagnostic, default 0) ----
 *
 * A single write of CONFIG_COMMIT is what kills the part on the ~3%
 * of boot cycles that wedge (measured 2026-08-30, 1 of 32 one-attempt
 * cycles), and the wedged part answers every diag read with a
 * well-formed (echo, 0) -- so BOOT_STAGE "reads 0" and every other
 * register reads 0 too. Nothing on the part can report anything once
 * the core has stopped, which is why four sessions got no further than
 * the symptom.
 *
 * These registers exist to break that. CFG_PHASE says how far
 * _product_config_commit got; the CGU block says whether
 * _cgu_raise_cclk's four UNBOUNDED spin-waits on CGU0_STAT are what
 * stopped it, and how many iterations each one normally takes -- the
 * margin is unmeasured otherwise. With the watchdog fitted, a CGU
 * stall no longer stops the core: it bails out, stamps which wait
 * expired, and leaves the part answerable.
 */
#define DIAG_CFG_PHASE       0xE019  /* 0 none 1 entered 2 patch 3 cgu
                                        4 gates 5 complete             */
#define DIAG_CGU_FAIL        0xE01A  /* 0 none, else which wait expired */
#define DIAG_CGU_IT1         0xE01B  /* iterations: wait for bypass     */
#define DIAG_CGU_IT2         0xE01C  /* iterations: wait for un-bypass  */
#define DIAG_CGU_IT3         0xE01D  /* iterations: wait for align      */
#define DIAG_CGU_IT4         0xE01E  /* iterations: wait for DIV update */
#define DIAG_SPI_PART_FIX    0xE01F  /* times the stuck-partial recovery
                                        discarded a word since boot       */
#define DIAG_SPI_PART_TICKS  0xE020  /* ticks the RX FIFO has been seen
                                        part-full, live                   */
/* Added 2026-08-31, session 15 (D74). SPI_PART_FIX alone cannot say why
 * the recovery did not fire: it counts only the discards. These three say
 * what the tick actually saw. SEEN counts every tick that found the RX
 * FIFO part-full; SKIP counts the subset where DSP4_SPI_PARTIAL_FIX2's
 * gate restarted the dwell because _spi_rx_count had moved. REQ_WORD is
 * the last word 0 the handler assembled, so misframing is visible
 * directly rather than inferred from SPI_ERR_COUNT.
 *
 * WHAT THEY MEASURED. SKIP tracks SEEN essentially one for one under host
 * traffic with FIX at 0, i.e. with the D71 fix on, the discard never fires
 * while the host is polling — which was the expected half of session 14's
 * D74 hypothesis. The other half was wrong: at the same moment RFS reads
 * 0 (the RX FIFO is EMPTY), REQ_WORD is correctly framed, SPI_ERR_COUNT
 * and RESP_DROP are 0 and SPI_RX_COUNT is advancing. There is no residue
 * and no misframing. D74 is a HOST-side answer-phase error; see the
 * DSP4_SPI_PARTIAL_FIX2 note below and tools/pi/dsp4_diag.py. */
#define DIAG_SPI_PART_SEEN   0xE021  /* ticks that saw a part-full RX FIFO */
#define DIAG_SPI_PART_SKIP   0xE022  /* of those, ticks FIX2's gate skipped */
#define DIAG_SPI_REQ_WORD    0xE023  /* last assembled request word 0      */

/* ---- DSP4_SPI_PARTIAL_FIX2 ----------------------------------------
 *
 * The 2026-08-22 stuck-partial-request recovery in _diag_timer_isr
 * discards a word from SPI2_RFIFO after three consecutive 1 ms ticks
 * that find the RX FIFO neither empty nor full. Its trigger cannot tell
 * a STALE fragment from a request that is merely IN FLIGHT, and the
 * host's config burst is 51 back-to-back transactions clocked at 1 MHz
 * — 32 us per word — so a 1 kHz tick that keeps landing inside the
 * second word of successive transactions sees "part full" three times
 * running and throws a live word away.
 *
 * The discriminator is already in the firmware and was already in the
 * original bug's own evidence: when the link was genuinely stuck on
 * 2026-08-22, "SEC_COUNT and SPI_RX_COUNT frozen at 74". A live burst
 * ALWAYS advances _spi_rx_count between ticks; a stale fragment never
 * does. So the recovery arms only while the request counter is standing
 * still, and a burst in progress can no longer be mistaken for residue.
 */
#ifndef DSP4_SPI_PARTIAL_FIX2
#define DSP4_SPI_PARTIAL_FIX2 0
#endif

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

/* ---- DIAG_BUILD_CFG — THE IMAGE SAYS WHAT IT IS ---------------------
 *
 * A mismeasured configuration must never be silent again (findings S8-2,
 * S9-1). Until 2026-09-09 nothing on a running part said which block size,
 * which kernels or which core clock it had been built with, so a bench could
 * measure a BLOCK=16 block-kernel 983.04 MHz build for a week while shipping
 * a BLOCK=8 per-sample 491.52 MHz one, and every instrument agreed with
 * itself throughout.
 *
 * One 32-bit word, read in ONE transaction (not through the peek window:
 * peek is a two-transaction handshake and the second half can be answered
 * from a different request under audio load). It is a compile-time constant,
 * so it is readable at BOOT_STAGE 1, before the graph, the config or the
 * audio clocks exist.
 *
 *   31..24  0xCF        signature -- a 0 or a garbage read is not a config
 *   23      DSP4_BQ_GUARD
 *   22      DSP4_BQ_ROUNDONCE
 *   21      DSP4_PROFILE_SIGNAL     measurement arm, never shipping
 *   20      DSP4_TXPROBE            bench instrument, never shipping
 *   19      DSP4_BISECT != 0        PARKED debug build, never shipping
 *   18..17  CCLK: 0 = 491.52 (CGU reset), 1 = 786.432, 2 = 983.040
 *   16..14  DSP4_BLOCK_MASK         7 = the whole block loop
 *   13      DSP4_GAIN_FLOAT
 *   12      DSP4_BQ_FLOAT
 *   11      DSP4_SCOPE_GATE
 *   10      DSP4_CHAN_MASK
 *    9      DSP4_BLK_LATCH          the ping/pong phase fix
 *    8      DSP4_BLOCK_KERNELS
 *   7..0    DSP4_BLOCK_SIZE         samples per block
 *
 * tools/pi/dsp4_buildcfg.py decodes it; dsp4_diag.py prints the decode in
 * its dump and dsp4_checkchip.py prints it after every boot.
 */
#define DIAG_BUILD_CFG       0xE0EA  /* R  packed build configuration */

#ifndef DSP4_BLOCK_KERNELS
#define DSP4_BLOCK_KERNELS 0
#endif
#ifndef DSP4_BLK_LATCH
#define DSP4_BLK_LATCH 0
#endif
#ifndef DSP4_CHAN_MASK
#define DSP4_CHAN_MASK 0
#endif
#ifndef DSP4_SCOPE_GATE
#define DSP4_SCOPE_GATE 0
#endif
#ifndef DSP4_BQ_FLOAT
#define DSP4_BQ_FLOAT 0
#endif
#ifndef DSP4_GAIN_FLOAT
#define DSP4_GAIN_FLOAT 0
#endif
#ifndef DSP4_BLOCK_MASK
#define DSP4_BLOCK_MASK 7
#endif
#ifndef DSP4_BISECT
#define DSP4_BISECT 0
#endif
#ifndef DSP4_TXPROBE
#define DSP4_TXPROBE 0
#endif
#ifndef DSP4_PROFILE_SIGNAL
#define DSP4_PROFILE_SIGNAL 0
#endif
#ifndef DSP4_BQ_ROUNDONCE
#define DSP4_BQ_ROUNDONCE 0
#endif
#ifndef DSP4_BQ_GUARD
#define DSP4_BQ_GUARD 0
#endif

#if DSP4_CCLK_TARGET == 786
#define DIAG_CFG_CCLK 1
#elif DSP4_CCLK_TARGET == 983
#define DIAG_CFG_CCLK 2
#else
#define DIAG_CFG_CCLK 0
#endif
#if DSP4_BISECT != 0
#define DIAG_CFG_BISECT 1
#else
#define DIAG_CFG_BISECT 0
#endif

#define DIAG_BUILD_CFG_VALUE  ( 0xCF000000                              \
    | ((DSP4_BQ_GUARD        & 1) << 23)                                \
    | ((DSP4_BQ_ROUNDONCE    & 1) << 22)                                \
    | ((DSP4_PROFILE_SIGNAL  & 1) << 21)                                \
    | ((DSP4_TXPROBE         & 1) << 20)                                \
    | ((DIAG_CFG_BISECT      & 1) << 19)                                \
    | ((DIAG_CFG_CCLK        & 3) << 17)                                \
    | ((DSP4_BLOCK_MASK      & 7) << 14)                                \
    | ((DSP4_GAIN_FLOAT      & 1) << 13)                                \
    | ((DSP4_BQ_FLOAT        & 1) << 12)                                \
    | ((DSP4_SCOPE_GATE      & 1) << 11)                                \
    | ((DSP4_CHAN_MASK       & 1) << 10)                                \
    | ((DSP4_BLK_LATCH       & 1) <<  9)                                \
    | ((DSP4_BLOCK_KERNELS   & 1) <<  8)                                \
    | ( DSP4_BLOCK_SIZE      & 0xFF) )

/* DIAG_BUILD_CFG2 — THE SECOND CONFIG WORD, and why one was not enough.
 *
 * DIAG_BUILD_CFG has no spare bit: 31..24 is the signature and 23..8 are all
 * allocated (S10-5). That was recorded on 2026-09-09 as "an instrument build
 * can still be silent to the part", and on 2026-09-09 it BIT. Three arms were
 * measured in one session -- shipping, shipping+DSP4_BLOCK_DECIMATE=32, and
 * shipping+DSP4_STRIP_FUSED=1+DSP4_SIMD_DYN=1, which differ by 81,299
 * cycles/block on chip 2 -- and ALL THREE read DIAG_BUILD_CFG 0xCF45FF10.
 * The word that exists so a mismeasured configuration is never silent could
 * not tell the shipping image from the instrument that had been standing in
 * for it in the capacity record for a fortnight (S11-1).
 *
 * So the switches that change what the kernels COST, as opposed to what the
 * loop IS, get their own word. Same rules as the first: one compile-time
 * constant, one transaction, readable at BOOT_STAGE 1.
 *
 *   31..24  0xC2        signature -- distinct from 0xCF, so a host that
 *                       reads the wrong address gets a mismatch, not a decode
 *   23..16  DSP4_BLOCK_DECIMATE   1 = every block; anything else is a
 *                                 MEASUREMENT and the audio is wrong
 *   15..10  reserved (0)
 *    9..8   DSP4_TX_EARLY   per-chip mask, outputs written a half ahead
 *                           (S9-2 Option A): 1 = chip 1's inter-chip TX,
 *                           2 = chip 2's converter TX, 3 = both
 *    7      DSP4_FX_TYPE_DECLARED
 *    6      DSP4_GATHER_FIRST
 *    5      reserved (0)
 *    4      DSP4_SCOPE_BLK_TAP != 0   instrument, never shipping
 *    3      DSP4_SIMD_STRIPS
 *    2      DSP4_SIMD_GRAPH
 *    1      DSP4_SIMD_DYN
 *    0      DSP4_STRIP_FUSED
 */
#define DIAG_BUILD_CFG2      0xE0EB  /* R  packed kernel/cost configuration */

#ifndef DSP4_STRIP_FUSED
#define DSP4_STRIP_FUSED 0
#endif
#ifndef DSP4_SIMD_DYN
#define DSP4_SIMD_DYN 0
#endif
#ifndef DSP4_SIMD_GRAPH
#define DSP4_SIMD_GRAPH 0
#endif
#ifndef DSP4_SIMD_STRIPS
#define DSP4_SIMD_STRIPS 0
#endif
#ifndef DSP4_SCOPE_BLK_TAP
#define DSP4_SCOPE_BLK_TAP 0
#endif
#ifndef DSP4_BLOCK_DECIMATE
#define DSP4_BLOCK_DECIMATE 1
#endif
#ifndef DSP4_GATHER_FIRST
#define DSP4_GATHER_FIRST 0
#endif
#ifndef DSP4_TX_EARLY
#define DSP4_TX_EARLY 0
#endif
#ifndef DSP4_FX_TYPE_DECLARED
#define DSP4_FX_TYPE_DECLARED 0
#endif

#if DSP4_SCOPE_BLK_TAP != 0
#define DIAG_CFG2_BLK_TAP 1
#else
#define DIAG_CFG2_BLK_TAP 0
#endif

#define DIAG_BUILD_CFG2_VALUE ( 0xC2000000                              \
    | ((DSP4_BLOCK_DECIMATE   & 0xFF) << 16)                            \
    | ((DSP4_FX_TYPE_DECLARED & 1) <<  7)                               \
    | ((DSP4_GATHER_FIRST     & 1) <<  6)                               \
    | ((DSP4_TX_EARLY         & 3) <<  8)                               \
    | ((DIAG_CFG2_BLK_TAP     & 1) <<  4)                               \
    | ((DSP4_SIMD_STRIPS      & 1) <<  3)                               \
    | ((DSP4_SIMD_GRAPH       & 1) <<  2)                               \
    | ((DSP4_SIMD_DYN         & 1) <<  1)                               \
    | ( DSP4_STRIP_FUSED      & 1) )

/* NOP — accepted and ignored. The host sends this as the second half of
 * a read (see diag.asm); it must not itself generate a response. */
#define DIAG_NOP             0xE0FE  /* W */
#define DIAG_CLEAR           0xE0FF  /* W  write anything: zero the counters */

/* Core-timer reload, in CCLK cycles. 491520 at the measured CCLK of
 * 491.52 MHz is a 1 kHz diag tick. Shared: diag.asm programs TPERIOD
 * with it and main.asm uses it to convert ticks to cycles. */
/* Core-timer reload = one diag tick = 1.000 ms of CCLK cycles. This MUST
 * track DSP4_CCLK_TARGET: the tick is the instrument every cycle figure on
 * this project is derived from, so a stale value here silently rescales
 * every measurement rather than failing. */
#if DSP4_CCLK_TARGET == 786
#define DIAG_TPERIOD         786432      /* CCLK 786.432 MHz */
#elif DSP4_CCLK_TARGET == 983
#define DIAG_TPERIOD         983040      /* CCLK 983.040 MHz */
#else
#define DIAG_TPERIOD         491520      /* CCLK 491.52 MHz, CGU reset defaults */
#endif

#define DIAG_MAGIC_VALUE     0xD5B40001
#define DIAG_BUILD_VALUE     0x20260812

#define DIAG_LED_AUTO        0
#define DIAG_LED_FORCE_OFF   1
#define DIAG_LED_FORCE_ON    2

#endif /* _DSP4_DIAG_H */
