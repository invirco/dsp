# DSP4 cycle budget — measured on the part

provenance: AI-drafted 2026-08-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

Measured on the rev-C bench, chip 1 (DSPA/U6), production firmware with a
d24 config committed. This is measurement, not estimate: the block loop
reads the core timer `TCOUNT` at the start and end of each 32-sample block
pass and combines it with the 1 kHz diag tick, so

    cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
           + (tcount_start - tcount_end)

is exact to the core clock. `_proc_cyc` holds the last pass, `_proc_cyc_max`
the worst seen, and both are readable over the diag peek window.
`MW/D32/DSP/SHARC/profile.sh` drives it.

## The budget

| | |
|---|---|
| core clock | 491.52 MHz (measured, not assumed) |
| block rate | 1500 blocks/s = 48 kHz / 32 samples |
| **cycles available per block** | **327,680** |

## What the graph actually costs

| configuration | cycles/block | % of budget |
|---|---|---|
| block I/O only (scatter + gather + meters) + 1 node | 65,475 | 20.0% |
| 1 strip (10 nodes) | 127,889 | 39.0% |
| 2 strips (20 nodes) | 163,679 | 50.0% |
| 8 strips (80 nodes) | 491,520 | 150% |
| **full graph (431 nodes)** | **2,164,358** | **660%** |

The full chip-1 graph is **6.6× over budget**. Note this supersedes the
earlier "~16×" figure, which came from power-of-two decimation thresholds
and carried their margin; the direct cycle count is the number to use.

**Block I/O alone is not free: ~64,000 cycles, 20% of the budget, before a
single node runs.** That is scatter (46 channels), gather (37 sends) and
the meter scan, each walking its table 32 times per block.

## Cost per node class

Measured by differencing consecutive `DSP4_NODE_LIMIT` points across one
strip, so each row is one real node of that class in place in the chain.

| class | cycles/block | cycles/sample |
|---|---|---|
| IN | 760 | 24 |
| GAIN | 2,005 | 63 |
| FILT | 7,254 | 227 |
| EQ | 10,812 | 338 |
| GATE | 6,539 | 204 |
| COMP | 6,453 | 202 |
