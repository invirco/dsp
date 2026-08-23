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

## How many strips fit in real time — and a warning about this question

The arithmetic says available for strips = 327,680 − 144,166 = 183,514,
so 183,514 / 63,131 ≈ **2.9 strips**.

**The bench says otherwise, and the bench wins.** `DSP4_STRIPS=1` — one
strip with every bus, send and transfer kept — measures **240,129
cycles/pass, 73.3% of the budget**, so by the arithmetic it fits with room
to spare. It is nevertheless **0 alive / 3** at 1×, with the flag verified
in the running image via `_build_flags2`.

So the usable ceiling is well below 100% of the nominal budget:

| configuration | measured load | alive at 1× |
|---|---|---|
| 1 node | 20.0% | 3/3 |
| 1 strip prefix (10 nodes) | 39.0% | 1/3 |
| 2 strip prefix (20 nodes) | 50.0% | not tested |
| `DSP4_STRIPS=1` (1 strip + buses) | 73.3% | 0/3 |
| full graph | 660% | 0/6 |

Reliable below ~20%, marginal around ~39%, gone by ~73%. **Something is
consuming roughly a 2.5× margin that the cycle count alone does not
explain**, and it is not identified yet. Two candidates worth separating
before anyone sizes a design against these numbers:

- the alive/dead test is a *parameter-link* test — the harness reads over
  the SPI link, which the main loop services. It may be the link that
  gives out first, not the audio;
- interrupt overhead and overrun compounding, which the per-pass cycle
  count does not capture.

**The cycles/class table above is solid and is what the sizing decision
needs. The "how many strips fit" number is not settled**, and the honest
current answer is that even one strip does not hold 1× on this firmware.
`DSP4_STRIPS=N` builds the graph so the question stays directly testable.

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
