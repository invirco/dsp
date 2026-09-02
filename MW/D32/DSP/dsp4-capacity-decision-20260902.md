provenance: AI-drafted 2026-09-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D32 DSP capacity — the decision package

For PW. Session 19, 2026-09-02. Everything below is measured on the part
unless it says otherwise.

---

## 1. The finding that decides this

**Block 8 does not fit on EITHER chip, and it never did on chip 1.**

| BLOCK | budget | chip 1 | | chip 2 | | both fit? | latency |
|---|---|---|---|---|---|---|---|
| 8 | 163,840 | 190,701 | 116.4% | 171,918 | **104.9%** | **no** | ~0.48 ms |
| **16** | **327,680** | **307,866** | **94.0%** | **306,950** | **93.7%** | **YES** | ~0.97 ms |
| 32 | 655,360 | 546,865 | 83.4% | 577,360 | 88.1% | YES | ~1.93 ms |

Chip 1 has been over budget at block 8 for the whole campaign — 115.7% in
session 18, 116.4% re-measured today, 0.6% apart. **The block-size decision
was already required for chip 1 before chip 2's optimisation work started.**
Nothing done to chip 2 could ever have saved the block-8 operating point,
because chip 2 was never the only thing over.

What the campaign changed is that **block 16 is now viable for both**. At
the D16 gate chip 2 measured 646,390 cycles at block 16 — **197.3%**. It is
now 93.7%.

## 2. Where chip 2 got to

| milestone | cycles/block @8 | % of part |
|---|---|---|
| D16 gate (session 17) | 342,090 | 208.8% |
| cascade rewrite (session 18) | 281,364 | 171.7% |
| dynamics + limiter pairing (session 18) | 240,681 | 146.9% |
| biquad native interleave (session 19) | 179,556 | 109.6% |
| block-wrapper trim | 178,672 | 109.1% |
| cross-chain dynamics pairing | **171,918** | **104.9%** |

**−49.7% cumulative.** Every step bit-exact against its predecessor, each
with a negative control that fires.

## 3. The exact remaining gap at block 8

**8,078 cycles per block = 48.5 MHz = 4.9%** on chip 2.
**26,861 cycles = 161 MHz = 16.4%** on chip 1.

Chip 2's remaining reachable levers, priced and measured, do not cover even
its own share:

| candidate | worth | status |
|---|---|---|
| dynamics pair latch | 360 cycles (2 MHz) | **priced, declined** — would freeze the dynamics control plane |
| everything else outside the cascade | ~1,000 cycles | fragmentary |
| the GEQ cascade | ~10,000 cycles | **numeric-contract change** |

The eight GEQ pairs are ~46,000 cycles, **26% of chip 2**. Session 18
established the cascade's floor at **5.94 cycles/band-sample with a
zero-cost round and saturate**, against 12.83 today; eleven of its nineteen
inner-loop instructions ARE the numeric contract — the 64-bit extract, the
branch-free saturate, the error-feedback MAC. Reaching the floor means
reopening D5, which was settled on measured LF accuracy (12.8 dB response
error at 20 Hz on plain DF1 fixed point) and noise floor (error feedback
takes the LF floor from −107 to below −130 dBFS).

**And none of it helps chip 1**, which has no GEQ and is the further over
of the two.

## 4. The options, with measured costs

### Option A — BLOCK 16  ← recommended

* **Both chips fit**: chip 1 94.0%, chip 2 93.7%. Margin ~6% each.
* **No feature loss.** 28-band GEQ on all outputs stays.
* **Cost: digital latency ~0.48 → ~0.97 ms**, an increase of about
  0.49 ms.
* Engineering: a regeneration and a requal. `DSP4_BLOCK_SIZE` is a build
  parameter and every loop count, slot array, DMA ring and ramp step
  follows from it, so this is not a rewrite — but it is a full requal.

### Option B — BLOCK 32

* Both fit with room: chip 1 83.4%, chip 2 88.1%. Margin 12–17%.
* No feature loss; real headroom for future features.
* **Cost: latency ~1.93 ms** — four times the block-8 figure.

### Option C — stay at BLOCK 8, cut features

* Chip 2 needs 8,078 cycles. A GEQ band costs ~1,582 cycles across the
  chip, so **a 23-band GEQ fits** — against PW's ruling that 31 bands on
  all outputs is the market bar, and we are already at 28.
* **This option does not work anyway.** It addresses chip 2 only, and
  chip 1 is 16.4% over at block 8 with no GEQ to cut. There is no known
  set of feature cuts that closes chip 1 at block 8.

### Option D — stay at BLOCK 8, reopen the numeric contract

* Dropping saturation from the cascade was priced by session 18 at
  8.94 c/band-sample. It would roughly close chip 2's 4.9%.
* **Also does not close chip 1**, and it trades a measured audio property
  for cycles. Not recommended at any price while Option A exists.

### Option E — raise the clock

* Chip 2 needs 1,031.5 MHz sustained, chip 1 1,144 MHz. 983.04 MHz is the
  exact 20,480× multiple of 48 kHz; the next clean multiple is beyond the
  ADSP-2156x family. Not available.

## 5. Recommendation

**Go to BLOCK 16.**

It is the smallest block that fits, which preserves as much of the
2026-08-28 latency ruling as the silicon allows. It costs about half a
millisecond of digital latency and no features, it needs no further
optimisation on either chip, and it leaves ~6% margin on both.

**Block 32 is the fallback**, and it is the right answer instead if either
of these turns out true in qual: 6% does not survive an undecimated
real-time run, or the roadmap wants headroom for features not yet counted.
It costs another ~1 ms of latency.

**What I would NOT do** is spend another session optimising chip 2 at
block 8. It is 4.9% away and the only lever of that size is inside the D5
numeric contract — and even a perfect result there leaves chip 1 16.4%
over. Block 8 is not recoverable by optimisation on either chip.

## 6. What this rests on, and what it does not

**Measured**: every cycle figure above, on the part, chip 1 running its
full 32 strips with stimulus present, `DEC=32`, both the chip-1 gain
witness and the chip-2 fabric witness required before a number was
accepted. Chip 2's block-8 figure reproduced across three boots to 0.17%;
chip 1's block-8 figure is 0.6% from session 18's independent measurement.

**NOT measured, and it matters**:

* **The latency figures are scaled, not measured.** `dsp_block.h` records
  ~23 samples ≈ 0.48 ms at block 8, itself derived from **93 samples
  measured at block 32**. Block 16 is interpolated at ~2.9 × BLOCK. Before
  committing on latency grounds, measure the pipeline at the chosen block
  size.
* **The ~6% margin at block 16 is thin and was taken decimated.** `DEC=32`
  changes how often a pass runs, not what one costs, but a real-time
  undecimated qual at block 16 is the thing that would actually falsify
  this.
* **No bar has been run at block 16.** Every bit-exactness result in this
  campaign — c2bqgold, c2xgold, c2gold, busgold, conform — was taken at
  block 8. The block-16 build links and runs; it has not been qualified.
* **D80 is still open** — a systematic 0.44–0.90% meter difference between
  the per-sample and block-kernel arms on the GATE/COMP-engaged chains,
  reproduced again today at worst 0.598%. It is a metering discrepancy,
  not an audio-path one (49 of 49 node output blocks are bit-identical),
  but it is unexplained.
* **A real coefficient swap has never been driven on chip 2.** The biquad
  pair latch's engage path is covered by a round-trip arm at block rate;
  the crossfade, `_bq_fx_convert_N` and the `_active_` flip that a host EQ
  change performs are not. This is the highest-value verification gap in
  the tree.
