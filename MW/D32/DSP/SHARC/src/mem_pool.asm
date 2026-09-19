/*======================================================================
 * mem_pool.asm — ONE memory pool for every delay line and reverb buffer,
 *                with two backends: L2 (what ships today) and EXTRAM
 *                (HyperRAM on xSPI0, staged by MDMA in whole blocks).
 *
 * PW ruling 2026-09-19: "dsp ram is required, but needs to work without
 * it until dsp board modified -- code it in place."
 *
 *----------------------------------------------------------------------
 * THE SHAPE, AND THE ONE IDEA THAT MAKES IT CHEAP
 *
 * EXTRAM EXTENDS THE L2 LINE; IT DOES NOT REPLACE IT.
 *
 * Every line keeps its L2 ring exactly as it has today -- H samples, the
 * head window. The external store holds the SAME history, and a read is
 * served from L2 whenever the requested offset is inside the head:
 *
 *     off <  H   ->  L2 head ring, the instruction sequence that ships
 *     off >= H   ->  a 2-block staging buffer, prefetched by MDMA
 *
 * Three things follow, and they are the whole reason for this shape:
 *
 *  1. ZERO ADDED LATENCY. The dispatch asked for the added latency "in
 *     a whole number of blocks". It is ZERO blocks and zero samples.
 *     Nothing in the audio path ever waits on the bus, because every
 *     offset short enough to be waited on is served out of L2, and every
 *     offset served from the external store is at least H samples old --
 *     H = 960 on the input lines, sixty blocks -- so its prefetch was
 *     issued fifty-eight blocks before it is read.
 *
 *  2. NO COHERENCY HAZARD. The write-behind for block n and the
 *     read-ahead for block n+2 are separated by at least H - 2*BLOCK
 *     samples of history. They cannot touch the same words. There is no
 *     forwarding case, no "is it in the staging buffer yet" test, and
 *     no per-sample decision of any kind.
 *
 *  3. THE FALLBACK IS NOT A SECOND IMPLEMENTATION. With no RAM, xlen is
 *     zero, no offset ever reaches the second branch, and what executes
 *     is the code that ships -- which is why the L2 arm can be, and is,
 *     proved BYTE-IDENTICAL rather than merely equivalent.
 *
 *----------------------------------------------------------------------
 * THE EXTERNAL LAYOUT
 *
 * The history store is indexed BY BLOCK, not by line:
 *
 *     hist[slot][line][BLOCK]     slot = 0..DSP4_POOL_SLOTS-1
 *                                 line = 0..DSP4_POOL_LINES-1
 *
 * Absolute sample a of line L lives at hist[(a / BLOCK) % SLOTS][L][a % BLOCK].
 *
 * That layout is chosen so the WRITE-BEHIND is a single contiguous
 * transfer: all LINES*BLOCK words a block produces are adjacent, so one
 * 1D MDMA flushes every line at once. Per-line rings would have needed
 * one transfer per line in each direction and doubled the arming cost.
 *
 * The READ-AHEAD is one transfer per line whose offset reaches the tail.
 * A window of BLOCK samples at an arbitrary offset straddles two slots,
 * so the fetch is 2D -- XCNT = BLOCK, YCNT = 2, YMOD = the slot stride --
 * landing 2*BLOCK words in the line's staging buffer, of which the
 * kernel reads a BLOCK-long span starting at a phase that is constant
 * for the whole block. The one case 2D cannot express is the slot ring
 * wrapping between the two rows; that happens to one line once every
 * SLOTS blocks (once per 250 ms) and is issued as two 1D transfers.
 *
 *----------------------------------------------------------------------
 * COST
 *
 * Per block, worst case, all lines at the full 250 ms:
 *
 *   write-behind   LINES*BLOCK words, 1 transfer
 *   read-ahead     2*BLOCK words per tail line, 1 transfer each
 *
 * Chip 1 (32 input delay lines) is 512 + 1024 = 1,536 words = 6,144 B
 * per 333.33 us block = 18.4 MB/s. Chip 2 (12 aux + sub + main + mon +
 * 6 FX echo = 21 lines) is 336 + 672 = 1,008 words = 4,032 B = 12.1 MB/s.
 * Against a 100 MHz octal-DDR HyperBus (200 MB/s raw, ~168 MB/s after
 * CA and latency overhead) that is 11.0 % and 7.2 % of the bus.
 *
 * Core cost is the arming -- six MMR writes for a 1D transfer, nine for
 * a 2D -- plus one extra store per sample per line to fill the write
 * staging. On chip 1: 33 arms * ~8 posted writes + 32*BLOCK stores =
 * about 780 cycles a block, 0.24 % of a 327,680-cycle budget at
 * 983.04 MHz. THIS IS A COMPUTED NUMBER, not a measured one; the part
 * has no RAM to measure it against. The bench check in the S75 report
 * is what turns it into a measurement.
 *
 *----------------------------------------------------------------------
 * WHAT DEGRADES, AND HOW
 *
 * If MDMA0 is still busy when the staging is issued, this module counts
 * a stall and SKIPS that block's transfers. Audio is unaffected for the
 * block in hand (its staging was fetched two blocks ago and is intact);
 * what is lost is one prefetch, re-issued on the next block. The failure
 * mode of a bus that cannot keep up is therefore a stall COUNT rising --
 * visible, bounded, and audible only as a repeated block on a line that
 * is at full tail depth -- and never a stalled core.
 *======================================================================*/

#ifndef DSP4_EXTRAM
#define DSP4_EXTRAM 0
#endif

#include "dsp_block.h"

/* THIS FILE LIVES IN src/ AND NOT src/lib/ FOR ONE REASON: src/lib is
 * assembled ONCE, with no -DCHIP_ID, and DSP4_POOL_LINES is per chip. A
 * pool in lib/ would compile against chip 2's line count and link into
 * chip 1, which is the kind of mismatch that assembles, links and is wrong.
 * src/ root is assembled twice, once per chip, like main.asm and diag.asm.
 *
 * A CHIP WITH NO POOL LINES STILL GETS THE WORDS AND THE ENTRY POINTS, and
 * only the machinery falls away. diag.asm reports _pool_backend on both
 * chips and main.asm calls both entry points on both chips, so the
 * alternative would be a CHIP_ID test at every one of those sites. Chip 2's
 * delay lines are not wired to the pool in S75 -- see dsp_block.h's
 * DSP4_POOL_LINES note for why that is scope and not oversight. */
#if DSP4_EXTRAM

.extern _extram_present;
.extern _extram_fail;
.extern _extram_init;
.extern _extram_probe;
.extern _extram_mdma_busy;
.extern _extram_mdma_1d;
.extern _extram_mdma_2d_src;

#if DSP4_POOL_LINES > 0
/* The generated registration table, chipN/pool_table.asm:
 *   _pool_head_base[LINES]   L2 head ring base, per line
 *   _pool_head_len[LINES]    H, per line
 *   _pool_max_len[LINES]     the full spec, per line
 * dsp_block.h carries DSP4_POOL_LINES and DSP4_POOL_SLOTS. */
.extern _pool_head_base;
.extern _pool_head_len;
#endif

#define POOL_LINES      DSP4_POOL_LINES
#define POOL_SLOTS      DSP4_POOL_SLOTS
#define POOL_ROW_WORDS  (DSP4_POOL_LINES * DSP4_BLOCK_SIZE)
#define POOL_ROW_BYTES  (POOL_ROW_WORDS * 4)
#define POOL_EXT_BASE   0x60000000

.section/dm seg_dmda;

/* 0 = L2 backend (today's layout and today's cost), 1 = EXTRAM.
 * THE one word every generated kernel tests. Read back by the host at
 * DIAG_EXTRAM_STAT so the running image says which backend it chose. */
.global _pool_backend;
.var _pool_backend = 0;

#if DSP4_POOL_LINES > 0
/* Which staging half this block reads: block n reads half (n & 1) and
 * the prefetch issued at the END of block n fills that same half for
 * block n+2. Two halves suffice because the fetch is issued after the
 * block that last read the half it targets. */
.global _pool_phase;
.var _pool_phase = 0;

/* Slot cursor: the history slot this block's samples are written to. */
.global _pool_slot;
.var _pool_slot = 0;

/* Per-line requested offset in samples, written by the DLY kernels each
 * block from their own _dly_read_offset_*; the pool needs them at
 * _pool_block_end to decide which lines need a tail fetch, and reading
 * them back out of the nodes would mean a table of node addresses. */
.global _pool_line_off;
.var _pool_line_off[POOL_LINES];

/* Per-line staging phase, the sub-block offset into the staged window.
 * Block-constant; the kernel adds it to the staging base. */
.global _pool_line_phase;
.var _pool_line_phase[POOL_LINES];

#endif  /* DSP4_POOL_LINES > 0 */

/* Stall counter -- see "WHAT DEGRADES" above. Present on both chips: the
 * host reads it at DIAG_EXTRAM_STALLS without knowing which chip has lines. */
.global _pool_stalls;
.var _pool_stalls = 0;

#if DSP4_POOL_LINES > 0
.section/dm seg_delay;

/* Write staging, ping-pong. Block n fills half (n & 1); the flush at the
 * end of block n sends that half out, and block n+1 fills the other. */
.global _pool_wstage;
.var _pool_wstage[2 * POOL_ROW_WORDS];

/* Read staging: two halves per line, 2*BLOCK words each. */
.global _pool_rstage;
.var _pool_rstage[POOL_LINES * 4 * DSP4_BLOCK_SIZE];


#endif  /* DSP4_POOL_LINES > 0 */

.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _pool_init — choose the backend and lay the external store out.
 *
 * In:  r0 = 0 to allow EXTRAM, non-zero to force L2 (the product
 *           configuration's dsp.extram key; see the S75 contract
 *           proposal). A product that can never fit the RAM says so
 *           here and the probe is not even attempted.
 * Out: _pool_backend, _extram_present, _extram_fail.
 * Clobbers: r0-r8, i0-i2.
 *
 * Called from main.asm AFTER the product configuration has arrived and
 * BEFORE audio starts. Not earlier: _extram_init takes Port A away from
 * SPI2, which is the parameter link on an unmodified card.
 *--------------------------------------------------------------------*/
.global _pool_init;
_pool_init:
    r8 = 0;
    dm(_pool_backend) = r8;
    dm(_pool_stalls) = r8;
#if DSP4_POOL_LINES > 0
    dm(_pool_phase) = r8;
    dm(_pool_slot) = r8;

    /* Every line starts with no tail: offset 0 is the L2 path, which is
     * what an L2-backend image does for every offset it ever sees. */
    i0 = _pool_line_off;
    i1 = _pool_line_phase;
    lcntr = POOL_LINES, do .pi_clear until lce;
        dm(i1, 1) = r8;
    .pi_clear: dm(i0, 1) = r8;
#else
    /* No lines on this chip: the backend stays L2 and the bus is never
     * touched. The probe would be harmless but it would also be a lie --
     * an image reporting EXTRAM in force with nothing using it. */
    rts;
#endif

    r1 = pass r0;
    if eq jump (pc, .pi_try);
    r1 = 5;                     /* EXF_FORCED_OFF */
    dm(_extram_fail) = r1;
    rts;

.pi_try:
    call _extram_init;
    call _extram_probe;
    r0 = dm(_extram_present);
    r0 = pass r0;
    if eq jump (pc, .pi_l2);

    r0 = 1;
    dm(_pool_backend) = r0;
.pi_l2:
    rts;
_pool_init.end:


/*----------------------------------------------------------------------
 * _pool_block_end — the staging, once per block, after the node graph.
 *
 * In:  nothing. Out: nothing.
 * Clobbers: r0-r12, i0-i2, m0-m2.
 *
 * Runs on the L2 backend too -- as an immediate rts. The call site in
 * main.asm is therefore unconditional and the backend decision lives in
 * exactly one place.
 *--------------------------------------------------------------------*/
.global _pool_block_end;
_pool_block_end:
#if DSP4_POOL_LINES == 0
    rts;
#else
    r0 = dm(_pool_backend);
    r0 = pass r0;
    if eq rts;

    /* The channel must be idle. Two blocks of slack say it will be; if
     * it is not, count it and skip -- never spin inside the block. */
    call _extram_mdma_busy;
    r0 = pass r0;
    if eq jump (pc, .pe_go);
    r0 = dm(_pool_stalls);
    r0 = r0 + 1;
    dm(_pool_stalls) = r0;
    jump (pc, .pe_advance);

.pe_go:
    /* ---- 1. write-behind: this block's whole row, one transfer ---- */
    r4 = dm(_pool_phase);
    r5 = POOL_ROW_WORDS;
    r6 = r4 * r5 (ssi);
    r0 = _pool_wstage;
    r0 = r0 + r6;               /* source: this block's half */

    r7 = dm(_pool_slot);
    r8 = POOL_ROW_BYTES;
    r1 = r7 * r8 (ssi);
    r2 = POOL_EXT_BASE;
    r1 = r1 + r2;               /* destination: hist[slot] */
    r2 = POOL_ROW_WORDS;
    call _extram_mdma_1d;

    /* ---- 2. read-ahead for block n+2, one line at a time ---- */
    /* target slot = (slot + 2) mod SLOTS */
    r7 = dm(_pool_slot);
    r8 = 2;
    r7 = r7 + r8;
    r8 = POOL_SLOTS;
    comp(r7, r8);
    if ge r7 = r7 - r8;

    r12 = 0;                    /* line index */
    i0 = _pool_line_off;
    i1 = _pool_line_phase;

.pe_line:
    r0 = dm(i0, 1);             /* this line's requested offset */
    i2 = _pool_head_len;
    m2 = r12;
    modify(i2, m2);
    r1 = dm(i2, 0);             /* H for this line */
    comp(r0, r1);
    if lt jump (pc, .pe_no_tail);

    /* q = off / BLOCK, ph = off % BLOCK, with BLOCK a power of two. */
    r14 = DSP4_BLOCK_SIZE - 1;
    r2 = r0 AND r14;                        /* ph */
    r3 = LSHIFT r0 BY -DSP4_BLOCK_SHIFT;    /* q  */

    /* start slot = (target - q - (ph ? 1 : 0)) mod SLOTS */
    r4 = r7 - r3;
    r5 = pass r2;
    if ne r4 = r4 - 1;
    r6 = POOL_SLOTS;
.pe_wrap:
    r5 = pass r4;
    if ge jump (pc, .pe_wrapped);
    r4 = r4 + r6;
    jump (pc, .pe_wrap);
.pe_wrapped:

    /* the kernel's read phase into the staged 2*BLOCK window:
     *   p0 = (BLOCK - ph) mod BLOCK */
    r5 = DSP4_BLOCK_SIZE;
    r5 = r5 - r2;
    r14 = DSP4_BLOCK_SIZE - 1;
    r5 = r5 AND r14;
    dm(i1, 0) = r5;

    /* source = EXT_BASE + start_slot*ROW_BYTES + line*BLOCK*4 */
    r8 = POOL_ROW_BYTES;
    r9 = r4 * r8 (ssi);
    r10 = DSP4_BLOCK_SIZE * 4;
    r11 = r12 * r10 (ssi);
    r9 = r9 + r11;
    r10 = POOL_EXT_BASE;
    r0 = r9 + r10;

    /* destination = _pool_rstage + (line*2 + phase) * 2*BLOCK */
    r9 = dm(_pool_phase);
    r10 = r12 + r12;
    r10 = r10 + r9;
    r11 = 2 * DSP4_BLOCK_SIZE;
    r10 = r10 * r11 (ssi);
    r1 = _pool_rstage;
    r1 = r1 + r10;

    /* Does the second row wrap the slot ring? One line, once per
     * SLOTS blocks. Two 1D transfers rather than a 2D one. */
    r9 = POOL_SLOTS - 1;
    comp(r4, r9);
    if eq jump (pc, .pe_split);

    r2 = DSP4_BLOCK_SIZE;       /* XCNT */
    r3 = 2;                     /* YCNT */
    r4 = POOL_ROW_BYTES - ((DSP4_BLOCK_SIZE - 1) * 4);
    /* YMOD IS THE STEP APPLIED AFTER THE LAST ELEMENT OF A ROW, and the
     * DDE has already applied XMOD to every element of that row INCLUDING
     * the last -- so the value that lands the next row ROW_BYTES from the
     * start of this one is ROW_BYTES minus the (XCNT-1) XMOD steps already
     * taken. Written out rather than folded into a constant because the
     * off-by-one here is the whole of the difference between a correct
     * fetch and one BLOCK-1 words adrift, and NOTHING ON THIS BENCH CAN
     * CHECK IT: the part has no RAM. It is the first thing the bench check
     * in the S75 report looks at. */
    call _extram_mdma_2d_src;
    jump (pc, .pe_next);

.pe_split:
    r2 = DSP4_BLOCK_SIZE;
    call _extram_mdma_1d;       /* row 0: the last slot */
    /* row 1: slot 0, into the second half of the staging */
    r0 = POOL_EXT_BASE;
    r11 = DSP4_BLOCK_SIZE * 4;
    r11 = r12 * r11 (ssi);
    r0 = r0 + r11;
    r9 = DSP4_BLOCK_SIZE * 4;
    r1 = r1 + r9;
    r2 = DSP4_BLOCK_SIZE;
    call _extram_mdma_1d;
    jump (pc, .pe_next);

.pe_no_tail:
    /* This line reads its L2 head this block, so no fetch is issued and
     * the staged phase is meaningless. Parked at 0 rather than left
     * holding the last tail value: if the host moves the line back into
     * the tail range the kernel reads this word on the very next block,
     * before the fetch that will replace it has landed, and a stale phase
     * there is a wrong-by-up-to-15-samples read rather than a silent zero. */
    r0 = 0;
    dm(i1, 0) = r0;

.pe_next:
    modify(i1, 1);
    r12 = r12 + 1;
    r9 = POOL_LINES;
    comp(r12, r9);
    if lt jump (pc, .pe_line);

.pe_advance:
    /* cursors forward one block */
    r0 = dm(_pool_phase);
    r1 = 1;
    r0 = r0 XOR r1;
    dm(_pool_phase) = r0;
    r0 = dm(_pool_slot);
    r0 = r0 + 1;
    r1 = POOL_SLOTS;
    comp(r0, r1);
    if ge r0 = r0 - r1;
    dm(_pool_slot) = r0;
    rts;
#endif  /* DSP4_POOL_LINES */
_pool_block_end.end:

#else   /* !DSP4_EXTRAM */

/* NOTHING IS EMITTED. Not a section, not a symbol, not a byte.
 *
 * That is the point: the L2 arm of this session is proved by the
 * shipping pair rebuilding BYTE-IDENTICAL, and a file that emitted even
 * an empty section would move every address behind it and make that
 * proof impossible to state. main.asm's call sites are gated the same
 * way. */

#endif  /* DSP4_EXTRAM */
