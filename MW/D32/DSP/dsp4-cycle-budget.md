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
- Known and unfixed: `_bq_fx_cascade_blk` never advances `i0` between
  stages, so it is only correct for `r4 = 1`. FILT calls it that way; EQ
  would need `r4 = 4` and must not be attempted until that is fixed.
- Suspects, in order: MAC-unit implicit registers across iterations, and
  m-register interference (`m1` is used by both cascade routines).

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
