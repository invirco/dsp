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
