/*======================================================================
 * bulkprobe.asm — how big a boot stream will this card actually load?
 *
 * 2026-08-21: rdyprobe (a 1024-byte stream) boots and runs; the full
 * firmware (207 KB) is accepted byte-for-byte by the host and then never
 * executes a single instruction — proved with a park on the FIRST
 * instruction of _start (DSP4_BISECT=5), which stayed silent. Lowering
 * the SPI clock 10x changed nothing, so it is not a clock-rate race.
 *
 * This image is rdyprobe with a controllable slab of dead code after the
 * toggle loop, so the ONLY variable is boot-stream size. It answers
 * "where between 1 KB and 200 KB does slave boot stop working?" without
 * dragging the firmware's own content into the question.
 *
 *   ./build.sh bulkprobe          # 0, 1, 2, 3, 4 -> the whole ladder
 *
 * BULK selects the slab, in nops: 0 none, 1 1 K, 2 4 K, 3 16 K, 4 32 K,
 * then the refinement rungs 5 = 6 K, 6 = 8 K, 7 = 10 K, 8 = 12 K, and
 * 9 = 4.25 K, 10 = 4.5 K, 11 = 5 K, 12 = 5.5 K, and the firmware-sized
 * rungs 13 = 64 K (~131 KB stream), 14 = 52 K (~107 KB, chip2-sized),
 * 15 = 96 K (~197 KB, chip1-sized).
 * The slab sits after an unconditional jump and is never executed; if a
 * given size boots, PB_05 (Pi GPIO8 / GPIO12) toggles at ~1 Hz exactly
 * as rdyprobe does.
 *
 * Diagnostic tool, hand-maintained. Same pin and polarity notes as
 * rdyprobe.asm — read them there.
 *======================================================================*/

#include <def21564.h>

#define RDY_BIT (1 << 5)   /* PB_05 = SPI2_RDY net */

#define CCLK_HZ          400000000
#define CYCLES_PER_ITER  5
#define HALF_PERIOD_MS   500
#define DELAY_ITERS ((CCLK_HZ / CYCLES_PER_ITER / 1000) * HALF_PERIOD_MS)

#ifndef BULK
#define BULK 0
#endif

#define R2(x)     x x
#define R4(x)     R2(R2(x))
#define R16(x)    R4(R4(x))
#define R64(x)    R4(R16(x))
#define R128(x)   R2(R64(x))
#define R256(x)   R16(R16(x))
#define R512(x)   R2(R256(x))
#define R1024(x)  R4(R256(x))
#define R2048(x)  R2(R1024(x))
#define R4096(x)  R16(R256(x))
#define R16384(x) R4(R4096(x))

#if   BULK == 0
#define BULK_BODY
#elif BULK == 1
#define BULK_BODY R1024(nop;)
#elif BULK == 2
#define BULK_BODY R4096(nop;)
#elif BULK == 3
#define BULK_BODY R16384(nop;)
#elif BULK == 4
#define BULK_BODY R2(R16384(nop;))
/* Refinement rungs, added once 2 booted and 3 did not. */
#elif BULK == 5
#define BULK_BODY R4096(nop;) R2048(nop;)
#elif BULK == 6
#define BULK_BODY R2(R4096(nop;))
#elif BULK == 7
#define BULK_BODY R2(R4096(nop;)) R2048(nop;)
#elif BULK == 8
#define BULK_BODY R2(R4096(nop;)) R4096(nop;)
/* Second refinement, once 2 (4 K nops) booted and 5 (6 K) did not. */
#elif BULK == 9
#define BULK_BODY R4096(nop;) R256(nop;)
#elif BULK == 10
#define BULK_BODY R4096(nop;) R512(nop;)
#elif BULK == 11
#define BULK_BODY R4096(nop;) R1024(nop;)
#elif BULK == 12
#define BULK_BODY R4096(nop;) R1024(nop;) R512(nop;)
/* Firmware-sized rungs, added 2026-08-21 once the limit turned out to be
 * boot-stream DURATION rather than size (tasks.md P2.2). 14 and 15 are
 * cut to match the real chip2 (108 KB) and chip1 (208 KB) streams, so a
 * production image and a probe of the same length can be compared
 * directly — that is what separates "the stream is too long" from
 * "something in the firmware image itself is wrong". */
#elif BULK == 13
#define BULK_BODY R4(R16384(nop;))
#elif BULK == 14
#define BULK_BODY R2(R16384(nop;)) R16384(nop;) R4096(nop;)
#elif BULK == 15
/* One input section cannot straddle two L1 code blocks — the linker
 * places a section whole, and block2/block3 are 128 KB each — so the
 * chip1-sized rung is cut as two 96 KB sections. */
#define BULK_BODY  R2(R16384(nop;)) R16384(nop;)
#define BULK_BODY2 R2(R16384(nop;)) R16384(nop;)
#else
#error "BULK must be 0..15"
#endif

#ifndef BULK_BODY2
#define BULK_BODY2
#endif

.section/pm seg_pmco;

.global _start;
_start:
    r0 = RDY_BIT;
    dm(REG_PORTB_FER_CLR)  = r0;
    dm(REG_PORTB_INEN_CLR) = r0;
    dm(REG_PORTB_DATA_CLR) = r0;
    dm(REG_PORTB_DIR_SET)  = r0;

.probe_loop:
    r0 = RDY_BIT;
    dm(REG_PORTB_DATA_TGL) = r0;

    r1 = DELAY_ITERS;
.delay:
    r1 = r1 - 1;
    if ne jump (pc, .delay);

    jump (pc, .probe_loop);

/* Dead weight — never reached, only ever loaded. */
    BULK_BODY
_start.end:

/* Second slab, in its own section so the linker can place it in the
 * other L1 code block (see BULK 15). Empty for every other rung. */
.section/pm seg_swco;
_bulk2:
    BULK_BODY2
_bulk2.end:
