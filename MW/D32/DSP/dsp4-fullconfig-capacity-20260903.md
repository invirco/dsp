provenance: AI-drafted 2026-09-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The full market config fits both chips — 31-band GEQ on every output, whole graph, measured

*2026-09-03, session 26. Cycle measurement only; no audio, nothing
shipped. The shipping `dsp.csv` is untouched and every W0 witness
rebuilds byte for byte.*

---

## 0. The answer

**THE COMPLETE PRODUCT FITS BOTH CHIPS AT BLOCK 16 / 983.04 MHz, WITH
MARGIN, AND THE WHOLE COST OF PW'S MARKET BAR LANDS ON THE CHIP THAT HAD
THE HEADROOM.**

| arm (chip 2, block 16, budget 327,680) | cycles/block | % | margin |
|---|---|---|---|
| shipping graph — 28-band GEQ on aux/grp/main | 249,737 | 76.21% | 77,943 |
| 31 bands on those same three classes | 254,677 | 77.72% | 73,003 |
| **FULL MARKET BAR — 31-band GEQ on every program output** | **272,505** | **83.16%** | **55,175** |
| + a 31-band GEQ on the monitor feed as well | 278,549 | 85.01% | 49,131 |

| arm (chip 1, block 16, budget 327,680) | cycles/block | % | margin |
|---|---|---|---|
| shipping graph, 32 full strips | 289,727 | 88.42% | 37,953 |
| **full market config** | **289,847** | **88.46%** | **37,833** |

**Chip 1 moves by 120 cycles — 0.04% of budget, and the two baseline
boots are 0.82% apart, so this is the instrument's own noise and not a
cost.** That is the expected result and it is worth stating as a
prediction that held: the graphic EQ is an OUTPUT-side feature, every
instance of it lives on chip 2, and chip 1's graph is the 32 input strips
and the mix fabric.

**The market bar costs 22,768 cycles/block on chip 2 — 6.95% of budget —
and chip 2 had 23.79% free.** After it, **chip 1 is the tighter part**,
which is a change of which chip the next capacity question is about.

---

## 1. What "the full market config" is, and what was assumed

The shipping graph already carries a 28-band graphic EQ on the twelve aux
buses, the four groups and the main bus. PW's bar is **31 bands
(1/3-octave, 20 Hz – 20 kHz) on ALL outputs**. Everything below is
generated, not hand-edited:

    python3 tools/dsp/gen_dsp_csv.py \
        --geq-bands 31 --geq-outputs aux,grp,main,sub,mainout \
        --out /path/to/full.csv

`--geq-bands` and `--geq-outputs` are new parameters of
`gen_dsp_csv.py`. **Their defaults (28, `aux,grp,main`) regenerate the
shipping `dsp.csv` byte for byte**, which is what makes the two arms a
paired measurement rather than two graphs from two sessions.

### The GEQ instances the market bar adds

| where | channels × bands | new? |
|---|---|---|
| Aux 1–12 | 12 × 31 | bands only (was 28) |
| Groups 1–4 | 4 × 31 | bands only (was 28) |
| Main L/R | 2 × 31 | bands only (was 28) |
| Sub out | 1 × 31 | **NEW node** `C2_SUB_GEQ` |
| Main outs 1–4 (post-crossover) | 4 × 31 | **NEW nodes** `C2_MAIN_OGEQ_01..04` |

Chip-2 biquad stages go from **632 to 841**: +54 from the band count on
instances that already existed, +155 from the five new ones.

### Four assumptions, stated rather than buried

1. **"All outputs" means all PROGRAM outputs.** The monitor/phones feed
   is a listening path off the main fader, not a program output, so the
   headline config leaves it out — **and it is measured anyway** rather
   than left as a claim: `--geq-outputs …,mon` adds
   `C2_MON_GEQ` (2 × 31, +62 stages) and costs **6,044 cycles/block,
   1.84% of budget.** It fits too, at 85.01%. PW's call, priced either
   way.
2. **The main stereo out and the codec aux out are already covered.**
   Both are fed from `C2_MAIN_DLY`, downstream of the main bus GEQ; a
   second graphic EQ on them would be the same EQ twice.
3. **Bus and output COUNTS are not parameters of this generator, on
   purpose.** NUM_AUX=12, NUM_GRP=4, NUM_FX=6 and the four post-crossover
   main outputs are pinned by the single-sourced TDM slot map
   (`shared/dsp4-logic/generated/sport_map.json`, decision D2). A count
   invented here would disagree with the slot map rather than change the
   product. The GEQ's EXTENT is a market decision; the bus count is a
   hardware one.
4. **The strip side of "full" was already full.** Chip 1's 32 strips
   carry IN → GAIN → FILT → EQ(4) → GATE → COMP → TUBE → DLY → FDR → RTG
   plus the meter, with the mix fabric and the superset inputs, and that
   is what session 25 measured. Nothing was added to chip 1; nothing
   about the market bar asks for anything to be.

---

## 2. Where the 22,768 cycles go, split by measurement rather than model

Three arms make the split a subtraction of measured numbers instead of an
attribution:

| step | Δ cycles/block | Δ % of budget | stages added | c/blk per stage |
|---|---|---|---|---|
| 28 → 31 bands on the existing 17 instances | +4,940 | +1.51% | 54 | 91.5 |
| the five NEW instances (sub + 4 main outs) | +17,828 | +5.44% | 155 | 115.0 |
| the monitor, if it is included | +6,044 | +1.84% | 62 | 97.5 |

**A band added to a cascade that already exists is the cheapest kind of
GEQ there is — 91.5 cycles/block, i.e. 5.7 cycles/sample/stage — and a
new instance costs about a quarter more per stage than that.** The
difference is per-NODE work that a longer cascade does not pay again:
the crossfade and staged-coefficient checks, the block copy the paired
driver makes, the call, and the node's share of the float path's
per-stage coefficient reconstruction. Read the other way: of the 17,828,
about 14,183 is stages and about 3,645 — 729 cycles/block each — is the
five nodes themselves.

**The new main-output GEQs are PAIRED, the sub's is not.** `OGEQ` was
adopted into the chip-2 MOUT pair family, so `C2_MAIN_OGEQ_01/02` and
`03/04` run as two interleaved-SIMD pairs at 31 stages each; the sub is
the only instance in its chain and stays scalar, as `C2_SUB_COMP` and
`C2_SUB_LIM` did before the cross-chain pairs took them.

---

## 3. Does it land where the headroom is?

Yes, and that is the point of the split.

* **Chip 2 carries 100% of the graphic EQ load and started at 76.21%.**
  It absorbs the market bar and ends at 83.16%, 16.84% clear.
* **Chip 1 carries none of it and stays at 88.4%.** It is now the tighter
  of the two by 5.3 points, having been 12.2 points tighter before.

So the answer to "does the whole product fit" is yes on both parts, and
the answer to "which part is the next capacity question about" changes
from chip 2 to **chip 1** — where the load is 32 strips, their meters and
their dynamics, and where the float cascade won only 0.81% because chip 1
has 256 biquad stages against chip 2's 841.

### Memory fits too, and it is not close

Chip 2, same builds (profiling instrument included, so these are upper
bounds on the shipping image):

| pool | shipping | full market bar | + monitor |
|---|---|---|---|
| code (VISA SW) | 52.1% | 54.2% | 54.5% |
| DM data + stack | 62.6% | **70.9%** | 71.9% |
| delay lines | 82.4% | 82.4% | 82.4% |

`dsp_memreport.py` reports all pools below 90% on every arm. DM is where
a GEQ shows up — two coefficient instances and the state per band — and
it has 109,108 words left.

---

## 4. The instrument, and what it was made to prove

Same instrument and the same discipline as the float landing: block 16,
`DSP4_PROFILE_SIGNAL=1`, `DEC=32`, fused + paired + biquad-paired,
**two boots a point, minimum taken**, every point witnessed (strip 1's
GAIN coefficient reads 1.0f; chip 2's inter-chip RX slots carry signal)
before its number is accepted. Chip 1 is `captable.sh MODE=cyc`, chip 2
is `sigprofile2.sh` with the chain uncut.

**The instrument reproduced itself against session 25 before it was
believed**: chip 2's shipping arm reads 249,737 against 249,751 — 0.006%
— and chip 1's reads 289,727 against 290,193, 0.16%. Neither number was
carried; both were re-measured this session so that every difference in
this document is a difference between two points taken hours apart on one
bench.

**Chip 2 is not configured on this bench**, so the whole chip-2 graph
runs on its `.var` initialisers — bypass coefficients in every cascade.
A biquad's cost is coefficient-independent (same instructions either way)
and a GEQ's cost is not conditional on its gains, so this measures the
31-band cost correctly; it is the same caveat every chip-2 figure in this
tree carries, and it is why there is no audio claim here.

**Two graphs, two build directories.** `captable.sh` and `sigprofile2.sh`
now take `DSP_CSV`, and both the scratch SOURCE tree and the BUILD
directory carry a digest of the csv they were made from. Without the
second half of that, the two arms would have shared a build directory and
the second point would have booted the first one's image — the same
stale-tree defect the srckey mechanism was built for on 2026-08-30, one
level down.

### The feature is in the image, not just in the csv

A cycle measurement of a feature that did not get emitted is a
measurement of nothing, so the emitted tree was read rather than assumed:
`process_chain.asm` calls `_C2_SUB_GEQ_process`,
`_C2BQP_MOUT_OGEQ_01_02_process` and `_C2BQP_MOUT_OGEQ_03_04_process`,
and the OGEQ pair drivers load `r4 = 31`.

---

## 5. One codegen hazard found and fixed

`_C2_PAIR_FAMILIES` states each chip-2 pair family as a fixed chain of
classes, and an instance missing any of them is dropped as incomplete.
Adding `OGEQ` to the MOUT family would therefore have dropped **all four
instances in the shipping graph**, silently un-pairing the four main
output compressors and limiters that ship paired today — a capacity
regression that no bar in this tree would have caught, because the
shipping graph would still have built and still have been bit-exact.

The fix is `_c2_family_classes()`: a class absent from the graph
entirely is dropped from the TEMPLATE, not from the family. Verified the
only way that matters — **the shipping tree regenerates file-for-file
identical after the change**, and all three W0 witnesses rebuild byte for
byte.

---

## 6. Bars

| bar | result |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py`, shipping csv | **OK**, 666 nodes |
| `dsp_validate.py`, full-config csv | **OK**, 671 nodes (672 with the monitor) |
| shipping `src/` regenerated from shipping `dsp.csv` | **file-for-file identical** |
| W0 `DSP4_BQ_FLOAT=0` | `4e89e062` / `4d1d314c`, 312,196 / 191,476 — **byte for byte** |
| W0 `DSP4_BQ_ROUNDONCE=0` | `23c1e662` / `e45bb82a`, 301,764 / 182,092 — **byte for byte** |
| W0 `DSP4_BQ_GUARD=0` | `2249afea` / `3173acb3`, 301,732 / 182,060 — **byte for byte** |
| float default `./build.sh` | `906a70f7` / `3a2d930c`, 301,580 / 181,908 — the sizes session 25 recorded |
| `busgold.sh` | **GRAPH BIT-EXACT**, 0 of 256, sha256 `ba3f52ec` |

No contract file touched, no contract version moved, no D5 change.
`check-contract-drift.sh` deliberately not run (it syncs ~12k lines as a
side effect; known hazard).

---

## 7. What this does NOT say

* **No audio.** Chip 2 is not audio-configured on this bench and the
  31-band designs were never loaded; this is a cycle result about the
  cost of the graph, not a listening result about the filter.
* **The full config has never been through a coefficient swap.** It runs
  at bypass throughout, so the crossfade path of the five new instances
  is unexercised — the same gap session 25 left open for the float arm on
  a configured chip 2.
* **The full config is a PARAMETER, not the shipping graph.** Nothing in
  `MW/D32/DSP/SHARC/dsp.csv` changed. Adopting the market bar means
  changing the generator's defaults and re-running the contract flow,
  with the SPI address movement that implies — which is a contract
  decision, not a measurement.
