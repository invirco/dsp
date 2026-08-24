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
 *      poke _scope_mode <- 1 impulse (sample 0 only), 2 step (every sample)
 *      poke _scope_idx  <- 0
 *      poke _scope_arm  <- 1
 *  ... wait SCOPE_LEN samples ...
 *      peek _scope_buf[0 .. SCOPE_LEN-1]
 *
 * An impulse response characterises a biquad completely, so EQ/FILT is
 * an impulse plus an FFT on the host rather than a swept sine.
 *----------------------------------------------------------------------*/

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
/* Incremented every time the host arms. The arm write is fire-and-forget
 * like every write on this link, and when it was dropped wait() saw the
 * PREVIOUS run's finished state and fetch() returned that run's buffer --
 * a stale capture indistinguishable from a fresh one. The host checks
 * this advanced before believing any data. */
.global _scope_runs;
.var _scope_runs = 0;

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
    /* Under per-block kernels the input slots are 32-word arrays, so the
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
    /* Node output buffers are 32-word arrays too: read the element for
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
    r0 = dm(_scope_arm);
    r1 = 0;
    comp(r0, r1);
    if eq rts;
    r0 = dm(_scope_inj);
    comp(r0, r1);
    if eq jump (pc, .sib_nostim);
    l4 = 0;
    i4 = r0;
    r5 = dm(_scope_amp);
    r3 = dm(_scope_mode);
    r4 = 2;
    comp(r3, r4);
    if eq jump (pc, .sib_step);
    /* impulse: amp in sample 0, silence after */
    dm(i4, 1) = r5;
    r2 = 31;
    lcntr = r2, do .sib_z until lce;
    .sib_z:
        dm(i4, 1) = r1;
    jump (pc, .sib_go);
.sib_step:
    r2 = 32;
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
