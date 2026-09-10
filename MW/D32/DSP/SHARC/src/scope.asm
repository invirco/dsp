/*----------------------------------------------------------------------
 * scope.asm — DSP-side stimulus and capture.
 *
 * The Pi audio round-trip is not a trustworthy measurement channel: it
 * carries an 8x gain error and reorders samples by up to ~190 places
 * (2026-08-23). Anything measured through it is measuring the channel.
 * This records a node output straight out of the sample loop instead,
 * and injects the stimulus at the same rate, so a family test never
 * leaves the DSP.
 *
 * Injection lands immediately AFTER _scatter_chipN and before the node
 * chain, which is the one point where an input slot variable holds a
 * value nothing downstream has overwritten yet.
 *
 * Host protocol, all via the DIAG peek/poke window:
 *      poke _scope_inj  <- word address of the input slot to drive
 *      poke _scope_src  <- word address of the node buffer to record
 *      poke _scope_amp  <- the value to inject
 *      poke _scope_mode <- 1 impulse (sample 0 OF THE RUN only -- see
 *                          _scope_inject_blk, S13-3), 2 step (every sample)
 *      poke _scope_idx  <- 0
 *      poke _scope_arm  <- 1
 *  ... wait SCOPE_LEN samples ...
 *      peek _scope_buf[0 .. SCOPE_LEN-1]
 *
 * An impulse response characterises a biquad completely, so EQ/FILT is
 * an impulse plus an FFT on the host rather than a swept sine.
 *----------------------------------------------------------------------*/

#include "dsp_block.h"

#define SCOPE_LEN 1024

.section/dm seg_dmda;
.global _scope_buf;
.var _scope_buf[SCOPE_LEN];
.global _scope_src;
.var _scope_src  = 0;
.global _scope_inj;
.var _scope_inj  = 0;
.global _scope_amp;
.var _scope_amp  = 0;
.global _scope_mode;
.var _scope_mode = 0;
.global _scope_idx;
.var _scope_idx  = 0;
.global _scope_arm;
.var _scope_arm  = 0;
.global _scope_len;
.var _scope_len  = SCOPE_LEN;
.global _scope_rd;
.var _scope_rd   = 0;
/* 0 until the stimulus has actually been driven for this run. Recording
 * waits for it, so sample 0 of the capture IS the injected sample. The
 * host's arm write lands at an arbitrary point in the block loop, and
 * when it landed between inject and record the first stored sample was
 * the one BEFORE the impulse -- the impulse then fell outside the buffer
 * and the whole capture read as zeros (bench 2026-08-23). */
.global _scope_go;
.var _scope_go   = 0;
/* HAS THE BLOCK INJECTOR DRIVEN ITS IMPULSE YET (S13-3, 2026-09-09)?
 *
 * _scope_go cannot answer that question for _scope_inject_blk, because
 * under DSP4_BLOCK_KERNELS BOTH injectors run in every block: the scatter
 * loop calls _scope_inject once per sample (and it raises _scope_go on the
 * first of them, which is correct for itself), and the node chain then
 * calls _scope_inject_blk, which rewrites the whole block and is the write
 * the chain actually reads. Gating the block injector on _scope_go
 * therefore silences it completely -- it never runs while _scope_go is
 * still 0 -- so it gets a flag of its own, cleared by the same arm write.
 */
.global _scope_fired;
.var _scope_fired = 0;
/* Incremented every time the host arms. The arm write is fire-and-forget
 * like every write on this link, and when it was dropped wait() saw the
 * PREVIOUS run's finished state and fetch() returned that run's buffer --
 * a stale capture indistinguishable from a fresh one. The host checks
 * this advanced before believing any data. */
.global _scope_runs;
.var _scope_runs = 0;
#if DSP4_SCOPE_BLK_TAP
/* Set by the chain right before _scope_inject_blk when the named injection
 * slot is a chip-1 RX slot that no block kernel reads; 0 otherwise. */
.global _scope_inj_blk;
.var _scope_inj_blk = 0;
#endif

/* BLOCK-AWARE WITNESS (DSP4_SCOPE_BLK_TAP, 2026-09-09, findings S9-5).
 *
 * Not a host-settable mode -- there is no memory POKE on the diag link,
 * only PEEK, and inventing a register for this would put a bench
 * instrument in the shipping register map. In a DSP4_SCOPE_BLK_TAP build
 * the tap IS the witness and _scope_record stands down; in every other
 * build the tap does not exist. One variable, decided at build time, and
 * DIAG_BUILD_CFG already says which build is on the part.
 */

.section/pm seg_pmco;
.extern _sample_idx;

/*----------------------------------------------------------------------
 * _scope_inject — drive the stimulus into the armed input slot.
 * Called from the sample loop after scatter. Clobbers r0-r5, i4, l4.
 * The sample loop reloads r5/r6 from memory after the node chain, so
 * clobbering them here is safe.
 *----------------------------------------------------------------------*/
.global _scope_inject;
_scope_inject:
    r0 = dm(_scope_arm);
    r1 = 0;
    comp(r0, r1);
    if eq rts;
    r0 = dm(_scope_inj);
    comp(r0, r1);
    if eq jump (pc, .scope_inj_nostim);   /* capture-only run */
#if DSP4_BLOCK_KERNELS
    /* Under per-block kernels the input slots are BLOCK-word arrays, so the
     * stimulus address advances with the sample the scatter loop is on.
     * Injecting at the base alone would drive only sample 0. */
    r2 = dm(_sample_idx);
    r0 = r0 + r2;
#endif
    l4 = 0;
    i4 = r0;
    r2 = dm(_scope_go);
    comp(r2, r1);
    if eq jump (pc, .scope_inj_first);    /* first sample of the run */
    r3 = dm(_scope_mode);
    r4 = 2;
    comp(r3, r4);
    if eq jump (pc, .scope_inj_drive);    /* step: every sample */
    dm(i4, 0) = r1;                       /* impulse: silence after 0 */
    rts;
.scope_inj_first:
    r2 = 1;
    dm(_scope_go) = r2;                   /* recording may start now */
.scope_inj_drive:
    r5 = dm(_scope_amp);
    dm(i4, 0) = r5;
    rts;
.scope_inj_nostim:
    r2 = 1;
    dm(_scope_go) = r2;                   /* nothing to drive: just record */
    rts;
_scope_inject.end:

/*----------------------------------------------------------------------
 * _scope_record — take one sample of the watched node buffer.
 * Called from the sample loop after the node chain, before gather.
 * Disarms itself when the buffer is full so the host can tell a
 * finished run from a stalled one by reading _scope_arm.
 *----------------------------------------------------------------------*/
.global _scope_record;
_scope_record:
    r0 = dm(_scope_arm);
    r1 = 0;
    comp(r0, r1);
    if eq rts;
#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_BLK_TAP
    /* _scope_tap owns the capture in this build. Recording here as well
     * would interleave a garbage sample of an unwritten scalar into every
     * block of a good capture -- which is the defect, not a second view
     * of it. */
    rts;
#endif
    r0 = dm(_scope_go);
    comp(r0, r1);
    if eq rts;                            /* stimulus not driven yet */
    r2 = dm(_scope_idx);
    r3 = SCOPE_LEN;
    comp(r2, r3);
    if ge jump (pc, .scope_rec_full);
    r0 = dm(_scope_src);
    comp(r0, r1);
    if eq jump (pc, .scope_rec_bump);
#if DSP4_BLOCK_KERNELS
    /* Node output buffers are BLOCK-word arrays too: read the element for
     * the sample this gather pass is on, not the base every time. */
    r4 = dm(_sample_idx);
    r0 = r0 + r4;
#endif
    l4 = 0;
    i4 = r0;
    r4 = dm(i4, 0);
    r5 = _scope_buf;
    r5 = r5 + r2;
    i4 = r5;
    dm(i4, 0) = r4;
.scope_rec_bump:
    r2 = r2 + 1;
    dm(_scope_idx) = r2;
    rts;
.scope_rec_full:
    dm(_scope_arm) = r1;
    rts;
_scope_record.end:

#if DSP4_BLOCK_KERNELS
/*----------------------------------------------------------------------
 * _scope_inject_blk — fill a whole block of stimulus at _scope_inj.
 *
 * Under per-block kernels the INPUT_TDM kernels read the DMA buffer
 * directly, so the old per-sample hook (which wrote an RX slot variable)
 * has nothing to write to -- the slot arrays are gone. This runs from
 * inside the node chain, straight after the input node, so it can drop a
 * known block into the shared pool where the rest of the chain will read
 * it.
 *----------------------------------------------------------------------*/
.global _scope_inject_blk;
_scope_inject_blk:
#if DSP4_SCOPE_BLK_TAP
    /* THE CHIP-1 REDIRECT (2026-09-09, findings S9-5).
     *
     * The host names the injection point by its RX SLOT symbol, which is
     * right for chip 2 -- an INTERCHIP_RECV's `_rx_ic_slot_<node>` is a
     * BLOCK-word array under block kernels and the chain reads it. It is
     * WRONG for chip 1: INPUT_TDM's block kernel reads the DMA buffer
     * straight into a pool slot, and `_rx_slot_<node>` survives as a ONE-WORD
     * variable that nothing reads -- so this routine used to fill sixteen
     * words over a one-word variable (fifteen of them into whatever DM
     * follows it) and drive a stimulus into a slot with no reader. Every
     * chip-1 strip family then measured SILENCE and read INERT.
     *
     * The chain hands the address in: r0 = the slot symbol the host names,
     * r1 = where that node's block actually is. r0 = 0 means "no redirect",
     * which is chip 2 and is this routine's behaviour byte for byte.
     */
    r2 = 0;
    comp(r0, r2);
    if eq jump (pc, .sib_noredir);
    r2 = dm(_scope_inj);
    comp(r0, r2);
    /* NOT THIS CALL SITE'S STRIP (S22-3, 2026-09-10).
     *
     * There used to be exactly ONE chip-1 call site, emitted after chain
     * index 0 -- so `_scope_inject_blk` could drive STRIP 1 and no other
     * strip on any block-kernel image, and `dsp4_node_verify.py --strip N`
     * for N != 1 reported "the injection is NOT reaching _buf_C1_EQ_nn"
     * with nothing saying why. A witness build now emits one call site per
     * strip, each naming its own RX slot in r0 and its own live chain slot
     * in r1, and a site whose slot the host did not arm on must do NOTHING:
     * falling through to .sib_noredir would make all 32 of them write a
     * block at whatever raw address `_scope_inj` holds, which is the very
     * one-word-variable overrun S9-5 was about, thirty-one times over.
     *
     * r0 == 0 still means "no redirect", which is chip 2, and reaches
     * .sib_noredir exactly as before. */
    if ne rts;
    dm(_scope_inj_blk) = r1;
    jump (pc, .sib_armchk);
.sib_noredir:
    r2 = 0;
    dm(_scope_inj_blk) = r2;
.sib_armchk:
#endif
    r0 = dm(_scope_arm);
    r1 = 0;
    comp(r0, r1);
    if eq rts;
    r0 = dm(_scope_inj);
    comp(r0, r1);
    if eq jump (pc, .sib_nostim);
#if DSP4_SCOPE_BLK_TAP
    r2 = dm(_scope_inj_blk);
    r3 = 0;
    comp(r2, r3);
    if eq jump (pc, .sib_dest);
    r0 = r2;                              /* the pool slot, not the slot var */
.sib_dest:
#endif
    l4 = 0;
    i4 = r0;
    r5 = dm(_scope_amp);
    r3 = dm(_scope_mode);
    r4 = 2;
    comp(r3, r4);
    if eq jump (pc, .sib_step);
    /* IMPULSE: amp in sample 0 OF THE RUN, silence for the rest of the
     * run -- which means the rest of THIS block and the whole of every
     * block after it (S13-3, 2026-09-09).
     *
     * This routine runs once per BLOCK, and it used to write the
     * amplitude into sample 0 every time it ran, so `mode 1` on a
     * block-kernel image was not an impulse at all: it was an IMPULSE
     * TRAIN at one per block -- 3 kHz at block 16 -- and what the audio
     * arms measured was that train's periodic steady state, not an
     * impulse response. The per-sample injector above has always had the
     * gate (`_scope_go` == 0 is the first sample of the run); the block
     * injector was written without it.
     *
     * What it cost: geqverify's +12 dB band read +8.451 dB and
     * afbverify's -18 dB notch read -4.799 dB on EVERY block-kernel
     * image, scalar and paired alike, while the same bars read
     * -17.99989 dB on the per-sample block-8 image of 2026-09-08. The
     * train's response reproduces all three of geqverify's points to
     * three decimals (+0.219 / +8.451 / -0.305 measured, +0.219 /
     * +8.451 / -0.305 modelled), so the defect was wholly the stimulus
     * and the audio was never in question. A narrow null fills far more
     * than a broad boost flattens, which is why the notch missed by
     * 13 dB and the boost by 3.5. */
    r2 = dm(_scope_fired);
    r4 = 0;
    comp(r2, r4);
    if ne jump (pc, .sib_quiet);
    r2 = 1;
    dm(_scope_fired) = r2;
    dm(i4, 1) = r5;
    r2 = DSP4_BLOCK_SIZE - 1;
    lcntr = r2, do .sib_z until lce;
    .sib_z:
        dm(i4, 1) = r1;
    jump (pc, .sib_go);
.sib_quiet:
    /* every block after the first: silence, so the run carries ONE
     * impulse and the capture is an impulse response. */
    r2 = DSP4_BLOCK_SIZE;
    lcntr = r2, do .sib_q until lce;
    .sib_q:
        dm(i4, 1) = r1;
    jump (pc, .sib_go);
.sib_step:
    r2 = DSP4_BLOCK_SIZE;
    lcntr = r2, do .sib_s until lce;
    .sib_s:
        dm(i4, 1) = r5;
.sib_go:
    r2 = 1;
    dm(_scope_go) = r2;
    rts;
.sib_nostim:
    r2 = 1;
    dm(_scope_go) = r2;
    rts;
_scope_inject_blk.end:
#endif

#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_BLK_TAP
/*----------------------------------------------------------------------
 * _scope_tap — THE BLOCK-AWARE WITNESS (2026-09-09, findings S9-5).
 *
 * Called from the generated chain immediately after every node, with
 *      r0 = the node's IDENTITY  -- its `_buf_<node>` address, which is
 *           already what the host pokes into _scope_src, so the host side
 *           of the family walk does not change at all;
 *      r1 = where that node's output block IS at this instant -- a
 *           blk_pool.h slot for a chip-1 strip node, `_blk_<node>` for a
 *           chip-2 node, `_buf_<node>` for the few that own a block array.
 *
 * WHY IT IS HERE AND NOT IN THE GATHER LOOP. The pool is REUSED: strip N's
 * BLK_CHAIN_B is strip N+1's the moment strip N+1's GAIN runs, and by the
 * end of the block every slot holds the last strip that touched it. There
 * is no later point at which a given node's block still exists. The only
 * correct place to read a node's block is where the node just left it,
 * which is here.
 *
 * Cost when the node is not the watched one: two immediate loads at the
 * call site, a call, two loads, a compare and an rts -- about eight cycles
 * per node per block, ~3.4k cycles on chip 1's ~430 positions, 1.0 % of
 * the 327,680-cycle budget. That is why the whole thing is behind
 * DSP4_SCOPE_BLK_TAP and never ships.
 *
 * Clobbers r0-r6, i4, i5, l4, l5 -- the same contract _scope_inject_blk
 * already has at the same call sites. Nothing in the chain is live in a
 * register across a node call.
 *----------------------------------------------------------------------*/
.global _scope_tap;
_scope_tap:
    r2 = dm(_scope_arm);
    r3 = 0;
    comp(r2, r3);
    if eq rts;                            /* not armed */
    r2 = dm(_scope_go);
    comp(r2, r3);
    if eq rts;                            /* stimulus not driven yet */
    r2 = dm(_scope_src);
    comp(r0, r2);
    if ne rts;                            /* not the watched node */
    r2 = dm(_scope_idx);
    r4 = SCOPE_LEN;
    comp(r2, r4);
    if ge jump (pc, .scope_tap_full);
    /* Copy min(BLOCK, SCOPE_LEN - idx) words. The clamp is not decoration:
     * SCOPE_LEN is not required to be a multiple of the block size, and a
     * run that ends mid-block would otherwise write past _scope_buf. */
    r5 = r4 - r2;                         /* room left */
    r6 = DSP4_BLOCK_SIZE;
    comp(r5, r6);
    if lt jump (pc, .scope_tap_go);
    r5 = r6;
.scope_tap_go:
    l4 = 0;
    l5 = 0;
    i4 = r1;                              /* the node's block, right now */
    r6 = _scope_buf;
    r6 = r6 + r2;
    i5 = r6;
    lcntr = r5, do .scope_tap_cp until lce;
        r6 = dm(i4, 1);
.scope_tap_cp:
        dm(i5, 1) = r6;
    r2 = r2 + r5;
    dm(_scope_idx) = r2;
    rts;
.scope_tap_full:
    dm(_scope_arm) = r3;                  /* run complete, host may fetch */
    rts;
_scope_tap.end:

/*----------------------------------------------------------------------
 * _scope_tap1 — the same witness for a node that has NO block kernel.
 *
 * TALKBACK and NOISE_GEN are not block-converted: under DSP4_BLOCK_KERNELS
 * the chain calls them once per block and they write ONE word to
 * `_buf_<node>`, so one word per block is their whole output and there is
 * no block to copy. This records that word and advances by one, which
 * decimates the capture to the block rate -- REAL samples, a block apart,
 * rather than a block of a value that was only ever written once.
 *
 * Same entry contract as _scope_tap; r1 is the scalar's address.
 *----------------------------------------------------------------------*/
.global _scope_tap1;
_scope_tap1:
    r2 = dm(_scope_arm);
    r3 = 0;
    comp(r2, r3);
    if eq rts;
    r2 = dm(_scope_go);
    comp(r2, r3);
    if eq rts;
    r2 = dm(_scope_src);
    comp(r0, r2);
    if ne rts;
    r2 = dm(_scope_idx);
    r4 = SCOPE_LEN;
    comp(r2, r4);
    if ge jump (pc, .scope_tap1_full);
    l4 = 0;
    l5 = 0;
    i4 = r1;
    r6 = _scope_buf;
    r6 = r6 + r2;
    i5 = r6;
    r6 = dm(i4, 0);
    dm(i5, 0) = r6;
    r2 = r2 + 1;
    dm(_scope_idx) = r2;
    rts;
.scope_tap1_full:
    dm(_scope_arm) = r3;
    rts;
_scope_tap1.end:
#endif
