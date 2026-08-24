# DSP4 cycle budget — measured on the part

provenance: AI-drafted 2026-08-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

Measured on the rev-C bench, chip 1 (DSPA/U6), production firmware with a
d24 product config committed. Measurement, not estimate: the block loop
reads the core timer `TCOUNT` either side of each 32-sample block pass and
combines it with the 1 kHz diag tick,

    cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
           + (tcount_start - tcount_end)

which is exact to the core clock. `_proc_cyc` holds the last pass and
`_proc_cyc_max` the worst seen; both are readable over the diag peek
window. `MW/D32/DSP/SHARC/profile.sh` drives it across `DSP4_NODE_LIMIT`
points and `bisect.sh` verifies every build flag against a stamp read back
off the running part.

## The budget

| | |
|---|---|
| core clock | 491.52 MHz (measured, not assumed) |
| block rate | 1500 blocks/s = 48 kHz / 32 samples |
| **cycles available per block** | **327,680** |

## Where the budget goes

| item | cycles/block | % of budget |
|---|---|---|
| block I/O — scatter, gather, meter scan | 64,758 | 19.8% |
| buses, sends, cross-ins, transfers | 79,408 | 24.2% |
| **fixed overhead before any strip** | **144,166** | **44.0%** |
| one channel strip (10 nodes) | 63,131 | 19.3% |
| **all 32 strips** | **2,020,192** | **616%** |
| **full graph (431 nodes), measured** | **2,164,358** | **660%** |

The full chip-1 graph is **6.6× over budget**. This supersedes the earlier
"~16×", which came from power-of-two decimation thresholds and carried
their margin; the direct cycle count is the number to use.

## Cost per node class

Differenced across consecutive `DSP4_NODE_LIMIT` points within one strip,
so every row is one real node of that class running in place in the chain.
Per-sample is per-block ÷ 32.

| class | cycles/block | cycles/sample | share of a strip |
|---|---|---|---|
| **RTG** | **19,237** | **601** | **30.5%** |
| EQ | 10,812 | 338 | 17.1% |
| FILT | 7,254 | 227 | 11.5% |
| GATE | 6,539 | 204 | 10.4% |
| COMP | 6,453 | 202 | 10.2% |
| DLY | 4,720 | 148 | 7.5% |
| FDR | 4,082 | 128 | 6.5% |
| GAIN | 2,005 | 63 | 3.2% |
| TUBE | 1,269 | 40 | 2.0% |
| IN | 760 | 24 | 1.2% |
| **strip total** | **63,131** | **1,973** | 100% |

### Re-measured 2026-08-24, post-fix build — KERNEL REWRITE baseline

The table above was taken before the biquad, compressor, fader and ramp
fixes. GAIN re-measured on the current build as the reference the rewrite
must beat:

| point | cycles/pass |
|---|---|
| `DSP4_NODE_LIMIT=1` (IN only) | 67,809 |
| `DSP4_NODE_LIMIT=2` (IN + GAIN) | 70,130 |
| **GAIN** | **2,321 cycles/block = 72.5 cycles/sample** |

72.5 cycles/sample for a load, a multiply, a round and a store is almost
all overhead: a `call`/`rts` per sample, the `_sample_idx == 0` guard
re-evaluated 32 times, and a second `call`/`rts` into `_mrf_rns28`. That is
the case for per-block kernels, now measured rather than assumed.

### KERNEL REWRITE — GAIN converted 2026-08-24 (`DSP4_BLOCK_KERNELS=1`)

First family through the per-block conversion. Measured at the same
profile points, same build otherwise:

| point | per-sample | per-block | delta |
|---|---|---|---|
| `NODE_LIMIT=1` (IN only) | 67,809 | 62,238 | −5,571 |
| `NODE_LIMIT=2` (IN + GAIN) | 70,130 | 62,811 | −7,319 |
| **GAIN alone** | **2,321** (72.5/sample) | **573** (17.9/sample) | **4.05× faster** |

**Bit-exact: 0 LSB** against `fixed_ref` at gains 1.0, 0.5, 0.25, 2.0,
0.001 and 7.94328, with all 32 samples of the block identical under a step,
as they must be.

What the 4× came from, in order of size: the per-sample `call`/`rts` into
the node, the `_sample_idx == 0` guard re-evaluated 32 times per block, and
a second `call`/`rts` into `_mrf_rns28` — all of it overhead around a
load, a multiply, a round and a store. The kernel hoists the coefficient,
folds polarity and mute into it once (mute is exactly `x*0` in this
format), and inlines the rounding with its constants hoisted. The
saturation fix-up is a **conditional move rather than a branch**, so the
body stays inside a hardware loop.

IN dropped too — a 32-iteration copy loop instead of 32 calls.

The same overhead is paid by every one of the 431 nodes, so this ratio is
the case for the rest of the conversion. Next: RTG (601 cycles/sample, the
measured hot spot) and the bus/send path.

`DSP4_BLOCK_KERNELS=0` remains the default and the bit-exact reference: the
default build is **byte-identical** to the pre-conversion image, so the
shipping path is provably untouched.

### KERNEL REWRITE — RTG converted 2026-08-24 (cycles only, see caveat)

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=9` (through FDR) | 110,872 | 67,171 |
| `NODE_LIMIT=10` (+ RTG) | 130,058 | 69,790 |
| **RTG alone** | **19,186** (599.6/sample) | **2,619** (81.8/sample) |

**7.3× faster.** The per-sample figure reproduces the 601 cycles/sample in
the table above, which is a useful check on the instrument.

The MACs were never the cost. With only MAIN enabled by default that is
two `_acc64_mac` calls, about 30 cycles — buried inside 22 gated loop
iterations that were re-evaluated on every one of the 32 samples. The block
form runs the whole gating tree **once per block** and turns each enabled
contribution into a single `_acc64_mac_blk` over the block.

**CAVEAT — this is a cycles-only result.** RTG reads FDR's buffers, and FDR
is not converted yet, so the block accumulate walks past a scalar and the
DATA is garbage. Code shape and memory traffic are representative, so the
cycle count stands; bit-exactness cannot be claimed until the chain between
GAIN and RTG is converted. Recorded as measured, not as verified.

### The binding constraint is MEMORY, not cycles

Converting RTG needs per-sample bus accumulators — 25 buses × 32 samples ×
2 words = **1,600 words against 50** — and that **overflowed DM**:
`Out of memory in output section 'sec_stak'`. The IN+GAIN conversion had
already left under ~1.5 K words of headroom on chip 1.

Block buffers are expensive: every converted node's buffer becomes 32
words, and on chip 1 the IN nodes alone (46 × 64 for slot + buffer) are
~2.9 K words. A full conversion of the ten strip classes would want roughly
13–14 K extra words of internal DM, which the part does not have.

The accumulators are parked in L2 (`seg_delay`) to unblock the measurement,
which if anything makes the 2,619 figure **conservative** — L2 is slower
than internal DM.

**The real fix is buffer reuse.** A strip is a linear chain, so a node's
block buffer is dead as soon as its consumer has run: two ping-pong block
buffers per strip suffice instead of one per node — 64 words instead of
320, and it scales. That belongs in the generator as a buffer-pool
assignment, and it should land before the remaining classes are converted
rather than after.

### Buffer reuse landed 2026-08-24 — the memory blocker is gone

One buffer per node does not fit. Strips run **sequentially** (the call
chain is strip-ordered), so a strip's working set is dead the moment its
RTG has accumulated into the buses, and every strip can reuse the same
slots. One shared pool of **8 slots × 32 samples = 256 words** serves all
32 strips:

| slot | use |
|---|---|
| A, B | chain ping-pong: IN→A GAIN→B FILT→A EQ→B GATE→A COMP→B TUBE→A DLY→B FDR→A |
| FDR_L, FDR_R | pan split, live until the router has read both |
| TAP_TRIM, TAP_EQ, TAP_PREFDR, TAP_POSTFDR | the four taps the router picks from — these span the whole strip, so they cannot share the pair |

Measured `sec_dmda` on chip 1:

| build | words |
|---|---|
| default (per-sample) | 20,840 |
| block kernels, one buffer per node | **overflowed `sec_stak`** |
| block kernels, shared pool | **22,472** (+1,632) |

GAIN re-verified against `fixed_ref` reading its pooled slot rather than a
private buffer: still **0 LSB** at all six gains.

**Headroom is still under ~1,600 words.** Moving the bus accumulators back
from L2 to internal DM takes it to 24,072 and overflows again, so they stay
in L2 for now. The next reclaim is the **1,472 words of RX slot arrays**,
which disappear entirely if the IN kernel reads the DMA buffer directly and
does the Q1.31→Q4.28 shift itself — that removes a whole copy as well as
the storage.

### RX slot reclaim 2026-08-24 — scatter deleted, block I/O nearly halved

The `INPUT_TDM` kernels now read the DMA buffer **directly**, doing the
Q1.31→Q4.28 shift inline, using the lane offset and stride that
`gen_block_io` already computes and now hands to each node. Staging 46
channels into slot arrays first was pure cost: 1,472 words of DM **and** a
copy per sample per channel. `_scatter_chip1` is a bare `rts` under the
flag.

| point | per-sample | per-block | ratio |
|---|---|---|---|
| `NODE_LIMIT=1` — block I/O + IN | 67,809 | **32,707** | **2.07×** |
| GAIN alone | 2,321 | 574 | 4.04× |
| RTG alone | 19,186 | 2,626 | 7.3× |

`NODE_LIMIT=1` is a fair like-for-like: both block I/O and IN are fully
converted there. Nearly half the fixed overhead at that point was a copy
that did not need to exist.

`sec_dmda` on chip 1 across the whole conversion:

| build | words |
|---|---|
| default (per-sample) | 20,840 |
| block kernels, buffer per node | overflowed |
| + shared pool | 22,472 |
| + RX reclaim | **21,046** (+206 over default) |

**The DM ceiling is about 22,500 words**, tighter than it looked: putting
the 1,600 words of bus accumulators back internal reaches 22,646 and still
overflows, so they stay in L2 — which makes the RTG figure conservative
rather than optimistic.

One regression to note against the flag: the boot-time input patch
(`_rx_patch_regs`, which lets a D24 console remap which slot var receives
which RX channel) is bypassed when the kernels read DMA directly. It needs
folding into the per-node offset before this path can ship.

### FILT/EQ attempted and REVERTED 2026-08-24 — what the biquads need

The straightforward conversion — wrap the existing per-sample body in a
32-iteration loop driven from the pool — builds and runs but produces
**silence**, and it is reverted rather than left behind the flag.

Two things were learned and both matter for the retry:

1. **The active coefficients start at zero.** `_filt_hpf_A/B` have no
   initialiser, so a FILT node outputs nothing at all until a coefficient
   write and swap have happened. That is true of the shipping per-sample
   path too — worth knowing on its own — and it means "outputs zero" is the
   node's resting state, not necessarily evidence of a broken conversion.
2. **The swap/crossfade machinery is block-rate and was left per-sample.**
   Moving the `swap_pending -> _filt_start_xfade` check into the wrapper
   fixed one restart-every-sample bug, but the crossfade *alpha* advance
   and the A/B instance state are still per-sample inside the body, and the
   filter still did not converge. The crossfade plane has to be split
   properly — advance once per block by 32 steps, exactly as the ramps
   were — rather than wrapped wholesale.

So the biquads are not a wrap-it-and-go conversion like GAIN and RTG were.
They also stand to gain least from block form: their cost is real
arithmetic, not call overhead. The genuine lever for them is a
**register-resident block cascade** — load the biquad state into registers
once, run 32 samples, store it back — which removes roughly 12 memory
operations per sample per stage. That is a new library routine and wants
its own bit-exactness pass against `fixed_ref.biquad`.

Kept from the attempt, because it is needed by everything downstream: the
harness can now inject a whole block from **inside** the node chain
(`_scope_inject_blk`, called straight after the input node). The old
per-sample hook wrote an RX slot variable, and those no longer exist now
that the input kernels read DMA directly. GAIN re-verified through the new
hook: still 0 LSB at all six gains.

### Register-resident block cascade added 2026-08-24 — routine in, wiring open

`_bq_fx_cascade_blk` (`src/lib/biquad_fx.asm`, behind the flag) cascades a
whole block with the biquad state held in **registers**: six loads and six
stores per SAMPLE become six per STAGE. The per-sample arithmetic is a
line-for-line copy of `_bq_fx_cascade_N`, so it should be bit-exact by
construction.

The reordering is stage-at-a-time rather than sample-at-a-time. That is
safe for a **cascade** specifically: each stage is causal with its own
state, so running stage k over the whole block before stage k+1 produces
the same samples in the same order. It would NOT be safe for a feedback
topology across stages.

Register budget is the reason coefficients are still re-read per sample
(one instruction each): six state registers plus five coefficients plus
working room does not fit in sixteen.

**Wiring FILT/EQ is still open, but the search is now narrow.** Second
attempt, wired per the plan below and reverted again — with two real
findings banked on the way:

**Fixed and kept: the pool had a slot-clobber bug.** Every `INPUT_TDM`
node wrote `BLK_CHAIN_A`, but the non-strip inputs (`C1_XIN_*` — Pi,
codec, MEMS, sinks) are **not** covered by the `DSP4_STRIPS` gate, so they
run after the strips in the call chain and overwrote strip 1's slot *after*
its FILT had already written it. The symptom was a filter that looked
completely dead while its own state and linkage scalar showed it computing
correctly — which is what finally localised it. Non-strip inputs now get
private 32-word buffers; only strip inputs share the pool. This was a
latent hazard for every future class, not just FILT.

**Still open, and now precisely bounded:** with the block cascade wired,
`both_unity` passes at **0 LSB** while every real filter fails
(worst 1.2e8). Unity is exactly the case where the feedback terms cancel,
so the fault is in **state handling under genuine feedback** in the
register-resident loop — not in the MAC chain, the coefficient conversion,
the two-call HPF/LPF structure, or the block plumbing, all of which unity
exercises. Prime suspects in order: interaction with the MAC unit's
implicit registers across iterations, and m-register interference
(`_bq_fx_cascade_blk` sets m1/m2/m3 while `_bq_fx_cascade_N` also uses m1).

Also spotted while tracing, not yet biting: `_bq_fx_cascade_blk` never
advances `i0` between stages — the per-sample rewind leaves it on stage 0's
coefficients. FILT calls it once per section with `r4 = 1` so it does not
show, but EQ uses `r4 = 4` and would.

The plan the attempt followed, which still looks right:

1. Steady state uses `_bq_fx_cascade_blk` in place over the block, called
   once per section (HPF then LPF; their coefficient arrays are separate,
   and `i1` walks on to the next stage's state exactly as the per-sample
   version relies on).
2. **Crossfade keeps a per-sample fallback** — loop the existing body 32
   times. A crossfade lasts ~18 blocks and is a transient, so its cost does
   not matter, and this stops the A/B instance and alpha bookkeeping from
   having to be re-derived in block form. That bookkeeping is what defeated
   the first attempt.
3. Block-rate work — the `swap_pending -> _filt_start_xfade` check — runs
   ONCE in the wrapper, never inside the sample loop.

Expected gain is roughly 30 % on FILT (227 cycles/sample) and EQ (338),
about 8-9 % of a channel strip. Worth having, but note it is a much smaller
lever than the ones already taken: the big wins came where overhead
dominated, and biquads are arithmetic-bound.

### COMP wrapped 2026-08-24 — bit-exact, and MEASURABLY SLOWER. Reverted.

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=5` (through GATE) | 94,529 | 34,056 |
| `NODE_LIMIT=6` (+ COMP) | 100,761 | 40,813 |
| **COMP alone** | **6,232** (194.8/sample) | **6,757** (211/sample) |

The wrapper was bit-exact — the sweep returned values identical to the
per-sample family run that scored 0 LSB — and it cost **8 % more cycles**.

**Why, and it generalises: a wrap on its own is worthless.** It replaces
"`process_all` calls the node 32 times" with "the node calls its own body
32 times". The same number of calls happen, plus loop bookkeeping, and
nothing is hoisted. GAIN's 4× did **not** come from being wrapped; it came
from what the wrap made possible — dropping the `_sample_idx` guard,
hoisting the coefficient and the polarity/mute decision out of the loop,
and inlining `_mrf_rns28` with its constants. RTG's 7.3× likewise came from
running the gating tree once, not from looping.

So for every remaining class the question is not "can it be wrapped" but
"how much work can be lifted out of the sample loop". For COMP that is the
`_sample_idx` guard, four parameter loads, and two `_mrf_rns28` calls —
perhaps 30 of 195 cycles/sample, so ~15 %. The genuine lever is the one the
plan already names: run the **log2/exp2 gain computer at block rate and
interpolate the gain per sample**, which is a numeric change and needs a
`shared/numeric-spec.md` amendment with a stated error bound before it can
be verified against anything.

### FDR converted 2026-08-24 — 2.33x, and the chain is now verified

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=8` (through DLY) | 106,460 | 34,454 |
| `NODE_LIMIT=9` (+ FDR) | 110,864 | 36,340 |
| **FDR alone** | **4,404** (137.6/sample) | **1,886** (58.9/sample) |

Same treatment that worked for GAIN, and for the same reason: the three
coefficients and the mute decision hoisted out of the loop, and all three
`_mrf_rns28` calls inlined with their constants held. Mute folds into the
gain because `x*0` is exactly 0 in this format. Bus faders (AUX/GRP/SUB/FX)
are mono and get the same kernel without the pan split.

**RTG is no longer cycles-only.** With FDR converted, `GAIN -> FDR -> RTG ->
BUS` is a contiguous run of converted nodes through the shared pool, and it
verifies **0 LSB at 7 points** across level 1.0/0.5/0.25 and pan
0/0.25/0.5/0.75 — mono, pan-split L, and the summed bus all bit-exact
against `fixed_ref`, with the 64-bit accumulator's single round at readout
included.

Two capture traps worth recording, both mine rather than the DSP's: under
block kernels the scope indexes its source by sample, which is right for a
pool array and **wrong for a scalar** — reading index 1 of
`_buf_C1_BUS_MAIN_L` reads the word after it. That made a working bus read
as zero twice before the accumulator itself was checked and found correct.

### The compressor's gain computer is only 9.6 % of it — measured 2026-08-24

`DSP4_STUB_COMPGAIN=1` makes `_compgain_fx` return unity immediately, so
the difference against a normal build is exactly what the log2/exp2 gain
computer costs:

| build | COMP cycles/block |
|---|---|
| normal | 6,232 |
| `DSP4_STUB_COMPGAIN=1` | 5,634 |
| **gain computer** | **598 (18.7 cycles/sample, 9.6 % of COMP)** |

**This kills step 4 of the rewrite plan as written.** That step proposed
running the gain computer at BLOCK rate with per-sample interpolation, and
called for a `shared/numeric-spec.md` amendment with an error bound to
justify the approximation. The prize is 9.6 % of one node class — about
1 % of a channel strip — in exchange for making the dynamics no longer
bit-exact against `fixed_ref`. **Not worth it.** The polynomials were the
obvious suspect and they are not the problem; that is exactly why it was
worth measuring before amending a numeric spec.

The other 90 % is structure: the `_sample_idx` guard, three library calls
per sample (`_envq_fx` and two `_mrf_rns28`), the parameter loads, and the
parallel blend. Hoisting and inlining those is bit-exact and needs no spec
change — but `_compgain_fx` and its callees clobber r0-r6 and r8-r12, so
only **r7, r13, r14, r15** survive the call. Almost nothing can be hoisted
ACROSS it, which caps the realistic saving at roughly 26 cycles/sample
against the ~16 cycles/sample the wrapper itself costs. Net ≈ 5 %.

So COMP and GATE are, on this evidence, **not worth converting**: the
overhead that block form removes is not where their time goes. That is a
different answer from GAIN and RTG, and it is the measurement that says so
rather than a judgement call.

### Biquads — PARKED 2026-08-24, state note

FILT/EQ are the second-biggest strip cost (227 and 338 cycles/sample,
together 29 % of a strip) and come back after the dynamics. State at the
park:

- `_bq_fx_cascade_blk` exists, assembles, and is unused. Its per-sample
  arithmetic is a line-for-line copy of `_bq_fx_cascade_N`.
- Wired to FILT, `both_unity` passes at **0 LSB**; every real filter fails.
  Unity is exactly where the feedback terms cancel, so the fault is in
  **state handling under feedback** in the register-resident loop — the MAC
  chain, coefficient conversion, HPF/LPF two-call structure and block
  plumbing are all exercised and correct.
- **FIXED since the park:** `_bq_fx_cascade_blk` now advances `i0` by five
  between stages (and restores the per-sample rewind), so `r4 > 1` is
  correct and EQ's four bands are no longer blocked on it.

### 2026-08-24, self-test on the part: the block routine is NOT the fault

`_bq_fx_cascade_blk` was run against `_bq_fx_cascade_N` on byte-identical
data **inside the part** (`DSP4_BQ_SELFTEST`, `src/lib/bq_selftest.asm`),
and it is **bit-exact: 0 differing samples of 64, max |diff| = 0.**

The test was built to be hostile to the recorded suspects:

- **Two stages with DIFFERENT coefficients** — 1 kHz LPF Q0.707 then 300 Hz
  HPF Q2. Equal stages would hide a stage-pointer fault; unity stages hide
  everything.
- **An impulse followed by silence**, so every sample after the first is
  pure feedback tail — the ringing crosses zero inside the block
  (`ref[31] = −3,884,542`), so this is not a degenerate signal.
- **Two consecutive blocks off one state array**, which is exactly the
  block-boundary persistence case, and samples 32–63 match too.

So both of yesterday's sharpened suspects are cleared *for the routine*:
in-block state handling and cross-block persistence are correct. What the
test cannot clear — because it supplies them itself — is how the **node
wrapper** drives `i0`, `i1` and `i2`, and the A/B-instance and crossfade
bookkeeping around them. That is now the whole of the remaining suspect
space, and it is a much smaller one.

This is the second time on this page that a conclusion about the biquads
came from a test that could not see the fault. The lesson is the same one:
**a passing test proves only what its stimulus could have falsified.**

### FILT CONVERTED and bit-exact — 2026-08-24, fourth attempt

Once the self-test above proved the routine, the remaining suspect space
was just the wrapper, and the wrapper is where the fault was.

| | cycles/block | cycles/sample |
|---|---|---|
| FILT per-sample, re-measured on the CURRENT build | 6,973 | 217.9 |
| **FILT per block** | **4,062** | **126.9** |
| | | **1.72× faster** |

(Differenced `DSP4_NODE_LIMIT` 2 → 3, `DSP4_BLOCK_DECIMATE=32`, both arms
measured the same way on the same day. The pre-rewrite table's 7,254 was
not reused.)

**Bit-exact on the part: 0 differing samples of 24**, block build against
per-sample build, same stimulus and same coefficients — a real 2-stage
cascade (HPF `1,−2,1,−1.8,0.81` into a 1 kHz LPF) whose impulse response
rings through zero and back, so the comparison has something to fail on.
Method: `DSP4_NODE_LIMIT=3` cuts the chain immediately after FILT, so the
pool slot still holds FILT's output when the scope reads it — without that
cut, later strip nodes overwrite the slot and the capture is of whoever
wrote last.

What the wrapper has to get right, and what the earlier attempts did not:

- **Input and output are different pool slots.** FILT reads `BLK_CHAIN_B`
  (GAIN's output) and writes `BLK_CHAIN_A`. The cascade works IN PLACE at
  `i2`, so the block is copied into the output slot and filtered there.
- **`i1` carries over from HPF to LPF.** The per-sample node relies on this
  and so does the block form — the routine leaves `i1` on the next stage's
  state base after a call, which the self-test confirmed.
- **Crossfades are handed to the per-sample path one sample at a time.**
  The per-sample body is emitted under a second label,
  `_<nid>_process_sample`, and the block wrapper calls it 32 times while a
  swap is pending or a fade is running, staging through the scalar buffers
  it already uses. That is the reference implementation itself, so the
  alpha bookkeeping — and a crossfade COMPLETING mid-block, which flips the
  active instance and must switch the remaining samples of that block to
  steady state — is right by construction. Re-deriving that bookkeeping in
  block form is what defeated the first attempt. A crossfade lasts 576
  samples and is a transient, so the per-sample cost of it does not matter.

The default image stays byte-identical: without the flag `_<nid>_process`
falls straight through into the untouched per-sample body.

**A ×32 suspicion that turned out to be wrong, recorded so it is not
re-raised:** the crossfade advances `alpha` once per call and the chain is
called per sample, which looks exactly like the ramp ×32 defect. It is not
one. `XFADE_SAMPLES = 12 ms × 48 kHz = 576 SAMPLES`, not 576 frames, so a
per-sample step is correct.

### Third attempt, 2026-08-24 — PARKED again, but the suspect list was wrong

Outcome: still fails on real filters, so the biquads stay parked. The
useful product of this attempt is a correction to the reasoning above.

**"`both_unity` passes at 0 LSB" does not exonerate the state handling —
it cannot.** With unity coefficients the biquad reduces to
`y = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2` with `b1 = b2 = a1 = a2 = 0`,
i.e. **`y = x`, and the stored state contributes nothing whatsoever**. Any
fault that lives in *which* state a stage reads and writes — wrong
instance, wrong stride, HPF and LPF sharing one state block, state not
persisted across blocks, the A/B crossfade instance — passes unity at 0 LSB
and fails every real filter. The earlier note read the unity pass as
evidence that "the block plumbing is exercised and correct". It is not:
unity is blind to exactly the thing that is broken.

So the suspect order is now, and this is where the next attempt should
start:

1. **The state pointer the wrapper hands to `i1`** — per section, per
   instance, per block. Cheapest possible test: two sections with
   deliberately DIFFERENT coefficients, and check the second is not running
   the first's state.
2. State persistence across block boundaries (the register-resident copy is
   written back once per stage; confirm the wrapper does not re-zero or
   re-load it per block).
3. Only then the MAC-unit implicit registers and `m1` interference.

A line-by-line diff of the two inner bodies was done as part of this
attempt: the arithmetic, the MAC order, the rounding, the saturation test,
the error-feedback update and the state store order are **identical** to
`_bq_fx_cascade_N`. That is a real narrowing — it is not the maths.

- The block cascade assembles and is still **unwired**; wiring it is the
  next attempt's first step, with test (1) above run before anything else.

### Product-scope gating — measured 2026-08-24, and the first mechanism was a loss

Option 3 from the decision list ("fewer nodes per product") was still
saving nothing: `_scope_gates_apply` only forced *enable flags* off, and
every one of the 431 nodes was called on both products. Only **34 nodes**
carry a `scope=` in `dsp.csv` — 32 D32-only, 2 D24-only, all of them
`INPUT_TDM` / `INTERCHIP_SEND` / `INTERCHIP_RECV` / `AUX_INPUT` /
`OUTPUT_TDM`.

Measured on the part, chip 1, booted as **d24**, block-kernel build,
`DSP4_BLOCK_DECIMATE=32`, 1101 passes each:

| build | cycles/block | vs control |
|---|---|---|
| no gating at all (control) | 243,235 | — |
| per-NODE skip table | 244,795 | **+1,560 (WORSE)** |
| contiguous-RUN gating | **241,744** | **−1,491** |

**The per-node table is a net loss and that is the finding.** Skipping the
34 scoped nodes is worth 1,478 cycles/block, but a table word read plus a
test before *all 431* dispatch calls costs more than that. The ratio does
not improve in a per-sample build either — the check and the node cost both
scale by 32. A gate paid per node cannot pay for itself when 8 % of the
nodes are gated.

The scoped nodes are contiguous in call order, so the working mechanism is
one compare and one branch per **run**: two runs on chip 1 covering all 16
of its scoped nodes, about 8 cycles/block against 1,491 saved. Kept.

`DSP4_SCOPE_GATE` (default 1) selects it, so the saving stays measurable
against a control build. The default per-sample image is byte-identical to
the pre-conversion firmware (`d1c3dd5c…` / `85d546f9…`) — the gating is
guarded to `DSP4_BLOCK_KERNELS`, and the legacy generator output including
`_scope_gate_count` is emitted unchanged on the default path.

Scale check, because it matters more than the number: 1,491 cycles/block is
**0.46 % of the budget**. In a per-sample build the same nodes would cost
32× as much, so gating them would be worth up to ~14 % — but that is an
inference from this measurement, not a measurement. Either way it does not
change the capacity picture below.

Bit-exactness after gating: the `GAIN → FDR → RTG → BUS` chain still
matches the model at **0 LSB** across all seven level/pan cases, booted as
d32 with the D24-scoped run branched over.

### What stands out

**RTG is the most expensive node class on the part** — 601 cycles per
sample, more than EQ and COMP together, and 30% of an entire channel
strip. It is a routing node. That is the first place to look, and it is
not where anyone would have guessed: the dynamics and EQ maths get the
attention, and between them they cost less than the router.

**The dynamics are not the problem.** COMP at 202 cycles/sample runs an
envelope follower plus log2 and exp2 polynomial evaluations for that, and
GATE costs the same. They are reasonable.

**Fixed overhead is 44% of the budget before a single strip runs.** Block
I/O alone is ~20%: scatter walks 46 channels and gather 37 sends, each 32
times per block. Buses and sends are another ~24%.

## How many strips fit in real time — 2

Arithmetic: available for strips = 327,680 − 144,166 = 183,514, so
183,514 / 63,131 ≈ 2.9 strips.

Bench, judged on **audio truth** rather than link responsiveness —
`_proc_passes` counts completed block passes, so passes/s = 1500 means the
main loop finished every block:

| `DSP4_STRIPS` | passes/s | verdict |
|---|---|---|
| 1 | 1500 | real time |
| **2** | **1500** | **real time — this is the ceiling** |
| 3 | 1342 | 89% — dropping ~1 block in 9 |
| 4 | 1144 | 76% — over budget |

**Two channel strips hold real time at 1×**, against 32 required, and the
measurement agrees with the arithmetic to better than one strip.

### Re-measured 2026-08-24, after the kernel rewrite — still 2

| `DSP4_STRIPS` | transport | `_proc_passes` | verdict |
|---|---|---|---|
| **2** | 1500/s | **1500/s** | **REAL_TIME — still the ceiling** |
| 3 | 1500/s | 1329/s | OVER_BUDGET |

`BOOT_STAGE 7`, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A` clean at both
points. 1329 reproduces the 1342 measured before the rewrite, which is the
expected answer: **the default per-sample image is byte-identical**
(`d1c3dd5c…` / `85d546f9…`), so its ceiling could not have moved. Every
conversion so far sits behind `DSP4_BLOCK_KERNELS`.

**The converted build's ceiling cannot honestly be measured yet, and it was
not.** In a block-kernel build the six unconverted strip classes run ONCE
per block instead of 32 times, so the graph is not functionally equivalent
and a strips sweep on it would flatter itself by roughly 32× on 88 % of the
strip. The 5.17 figure above stays a projection from measured per-class
conversions until the whole strip converts.

**A measurement trap this re-run walked into first, worth recording.**
The initial sweep judged real time by `FRAME_COUNT` over a nominal dwell
and produced nonsense — 2,023 "blocks/s" at `DSP4_STRIPS=4`, above the
1,500 the transport can physically deliver. Two faults: `FRAME_COUNT` is
incremented by the block ISR and keeps perfect time whether or not the main
loop finishes its work, so it is structurally incapable of seeing an
over-budget graph; and dividing by the requested dwell rather than measured
elapsed inflated the rate. `dsp4_audio_verdict.py` exists precisely to
avoid both, and using it gave a clean answer at the first attempt on a link
that had refused fifteen. **Judge the loop by `_proc_passes`, never by
`FRAME_COUNT`** — the same lesson that cost a day earlier on this page,
relearned by ignoring it.

### A test artefact worth recording, because it cost a day

An earlier version of this page reported a "2.5× unexplained margin" —
that `DSP4_STRIPS=1` measured 73.3% of budget and still appeared dead.
**That was the test, not the DSP.** Aliveness was being judged by whether
the parameter link gave a prompt clean answer, and that link is serviced
by polling from the block loop: under load an answer is a block or more
away, which is normal, not a fault. The card was running the whole time —
`BOOT_STAGE 7`, `FRAME_COUNT` at 1500/s, `DMA0_STAT 0x00006200`,
`SPORT0_ERR_A` clean.

Two things came out of it and both are kept:

- **Judge audio by audio.** `_proc_passes` versus `FRAME_COUNT` separates
  "transport running" (an ISR increments FRAME_COUNT regardless) from
  "loop keeping up". `audio_verdict.py` reports UNKNOWN when the link
  never answers, distinct from AUDIO_DEAD — conflating those two is the
  original error.
- **The host was making it worse.** `dsp4_diag.py.read()` realigned the
  word phase on the first echo mismatch, when the usual cause is simply
  that the DSP has not polled yet. It now collects patiently
  (`COLLECT_TRIES`) before concluding anything is out of phase, so a slow
  answer is no longer turned into a manufactured fault.

## The capacity arithmetic, after everything converted so far

This is the number the conversion has to be judged against, and it is not
close.

Post-conversion, per strip and per block:

| | cycles/block |
|---|---|
| strip, before the rewrite | 63,131 |
| strip, now (IN, GAIN, FDR, RTG converted) | **42,306** |
| fixed overhead, before | 144,166 |
| fixed overhead, now (block I/O converted) | **109,064** |
| available for strips = 327,680 − 109,064 | **218,616** |

So **5.17 strips** by arithmetic, up from 2.91. Against what the products
need:

| | strips required | cycles/block needed | vs 218,616 available |
|---|---|---|---|
| D24 | 24 | 1,015,344 | **4.6× over** |
| D32 | 32 | 1,353,792 | **6.2× over** |

**The six unconverted classes are 88 % of what a strip now costs**: EQ 338,
FILT 227, GATE 204, COMP 202, DLY 148, TUBE 40 = 1,159 of 1,329
cycles/sample. Everything converted so far is the other 12 %.

And converting them is not enough either. Halve **all six** — better than
any measured conversion except RTG's, and COMP/GATE have already been
measured as not worth converting at all — and a strip falls to 23,762,
which fits **9.2 strips**. Still 2.6× short of D24.

That is the honest state of it: the rewrite is working (2.91 → 5.17 strips,
every step measured and bit-exact) and it cannot get one SHARC to 24
channels by itself. Scope gating, worth 0.46 % of budget, does not change
this; neither does any single remaining node class. What would move it is a
change of shape — fewer nodes per strip, a bigger block, or the strip count
per part — and that is a hub decision, not an optimisation.

## What this means for the decision

The gap is 6.6×. Reading it against the hub's four options:

1. **Per-block kernels.** 13,792 per-sample node calls per block become
   431. Removes call overhead and opens SIMD/pipelining. The measured
   spread supports this: IN at 24 cycles/sample is nearly all call
   overhead, and even at the top RTG's 601 is unlikely to be 601 cycles of
   arithmetic.
2. **Cheaper maths.** Worth having, but the profile says dynamics are not
   where the money is. **RTG first, then EQ and FILT.**
3. **Fewer nodes per product.** Currently saving nothing at all:
   `_scope_gates_apply` on chip 1 is a no-op — the generated body is
   `rts; /* no scoped nodes on this chip */` — so all 431 nodes run for
   D24 and D32 alike, and every measurement here already had a d24 config
   committed.
4. **Larger block.** Amortises overhead, costs latency. The profile does
   suggest a real overhead component, so this is not empty — but it should
   be judged after 1, since 1 removes most of the same overhead without
   the latency.

The one thing the data says on its own: **profile RTG before optimising
anything else.** It is a third of a strip.
