provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# One capacity instrument, and the lever that actually closes D32

**This table replaces the S11-morning capacity record and settles S10-6.**
Everything is `BLOCK=16` unless the row says otherwise, and the budget is
derived from the clock read back on every point: `CGU0_CTL 0x00005000`,
`CGU0_DIV 0x451442C1` → **983.040 MHz**, **327,680 cycles/block** at block
16 and **655,360** at block 32.

Instrument: **`SHARC/capacity.sh` + `capacity_run.sh` + `tools/pi/dsp4_capacity.py`**,
new this session and the only one used. Every arm is a full build from
`shipping.config` plus named overrides, staged to its own path (never
`~/dspboot`), with a fresh `chipN.sym.json`, and every reading carries the
CGU words and **both** build-config words.

## 0. S10-6 is settled, and the answer was not decimation

The record's instrument (`sigprofile2.sh` / `fxcost.sh`) read chip 2
**78,245 cycles/block low at D24 and 108,331 low at D32** against the
shipping pair — 24 % and 33 % of budget, in the direction the documented
signal/silence split cannot produce. `DSP4_BLOCK_DECIMATE=32` was the
standing candidate. It is not the cause.

| arm, D24 mask | chip 1 `_proc_cyc` | chip 1 worst | chip 2 `_proc_cyc` | chip 2 worst |
|---|--:|--:|--:|--:|
| shipping (S10) | 234,267 **71.5 %** | 277,752 **84.8 %** | 303,891 **92.7 %** | 304,874 **93.0 %** |
| shipping **+ `DSP4_BLOCK_DECIMATE=32`** | 234,821 **71.66 %** | 277,589 **84.71 %** | 302,971 **92.46 %** | 303,954 **92.76 %** |
| shipping **+ `DSP4_STRIP_FUSED=1` + `DSP4_SIMD_DYN=1`** | 194,502 **59.36 %** | 237,333 **72.43 %** | 221,984 **67.74 %** | 233,033 **71.12 %** |
| the record's instrument (`fxcost.sh`) | 408,939 | — | **225,646** | — |

**Decimation costs nothing** — 554 cycles on chip 1 and −920 on chip 2, both
inside the pass-to-pass spread. **The gap is two build switches that are not
in `shipping.config` and default to 0 in `build.sh`:** `DSP4_STRIP_FUSED`
and `DSP4_SIMD_DYN`, which `fxcost.sh` and `sigprofile2.sh` have always
forced to 1. With them on, chip 2 reads **222,314** against the instrument's
**225,646** — 3,332 cycles apart, 1.0 % of budget — and at D32 **268,790**
against **261,093**, 2.3 % apart. That is the whole disagreement.

**So the profile scripts were never measuring the shipping image, and the
S8-2 shape repeated exactly**: a number quoted for a build that is not the
one running. `DSP4_PROFILE_SIGNAL` was known and declared; these two were
not declared anywhere.

### The word that exists to prevent this could not

`DIAG_BUILD_CFG` read **`0xCF45FF10` on all three arms above** — three
images 81,299 cycles/block apart on chip 2. S10-5 recorded that the word
had no spare bit; this is that recording coming true. **`DIAG_BUILD_CFG2`
(0xE0EB) is added**: signature `0xC2`, the decimation factor in 23..16, and
the cost switches in the low byte. Shipping reads **`0xC2010044`**; the
fused/SIMD arm reads **`0xC201004F`**; a block-32 image reads
`DIAG_BUILD_CFG 0xCF45FF20`. `check_shipping_config.sh` now computes both
words and reads `build.sh`'s own defaults for the switches
`shipping.config` does not name, so the same fact is not written down in a
third place.

### Ruling on the profile tool

**Retired for capacity claims about the shipping image.** It remains valid
for attributing cost to a CLASS inside its own arm, and that arm is now
legible on the part rather than only in the script. Every `.4` / 09-03 /
09-08 chip-2 row is re-read as **"the fused/SIMD build, decimated 32:1,
signal forced"** — which is why they were 24–33 % below the product.

## 1. Lever 1, BLOCK 32: it links, it boots, and it makes D32 WORSE

One build said whether it links and one boot said whether it fits. Both
answers are in.

| | chip 1 | chip 2 |
|---|--:|--:|
| **links** | `chip1.ldr` 444,704 B (block 16: 421,768) | `chip2.ldr` 313,268 B (280,284) |
| **D32 all-ones**, 2 boots | 565,056–565,207 **86.22 %**, worst 620,189 **94.63 %**, OVERRUN **0** | 770,092–770,138 **117.51 %**, worst 797,558 **121.7 %**, OVERRUN **14.86 %** |
| **D24 mask** | 434,190 **66.25 %**, worst 476,505 **72.71 %**, OVERRUN 0 | 581,234 **88.69 %**, worst 582,916 **88.95 %**, OVERRUN 0 |

**D32 chip 2 goes from 112.7 % to 117.51 % of budget and from 11.26 % to
14.86 % of blocks missed.** The estimate was a 5–10 % saving; the part
delivers a 4.8-point loss.

Per sample, which is where the estimate came from:

| | chip 1 | chip 2 |
|---|--:|--:|
| block 16, D32 | 19,137 cyc/sample | 23,089 |
| block 32, D32 | 17,658 (**−7.7 %**) | 24,067 (**+4.2 %**) |

**The 2026-09-01 trend was a chip-1 and per-class trend and it does not
transfer to chip 2's graph.** Chip 1 gains what the trend predicted; chip 2,
which carries the six FX engines and their delay memory, loses. Doubling
the block doubles every kernel's working set, and chip 2's is the one that
does not fit whatever the loop count is.

**And the price is four times what the plan assumed.** Measured through-DSP
latency (§3): block 16 is **66 samples**, block 32 is **131** —
**+65 samples / +1.354 ms**, not +16 / +0.333 ms. The signal crosses four
block-buffered stages (RX and TX on each chip), not one.

D24 does improve at block 32 — chip 1's worst block 84.8 % → 72.7 %, chip
2's 93.0 % → 89.0 % — so the lever is not worthless; it is just not a D32
lever, and it costs 1.354 ms to take.

## 2. The lever that DOES close D32, and the half of it that is not proven

| D32 all-ones, 2 boots each | chip 1 `_proc_cyc` | chip 1 worst | chip 2 `_proc_cyc` | chip 2 worst | OVERRUN |
|---|--:|--:|--:|--:|--:|
| **shipping** | 306,190 **93.4 %** | 361,246 **110.3 %** | 369,424 **112.7 %** | 370,832 **113.2 %** | **11.26 %** |
| `DSP4_STRIP_FUSED=1` | 299,269 **91.33 %** | 354,816 **108.28 %** | 365,882 **111.66 %** | 366,699 **111.91 %** | **10.32 %** |
| `DSP4_STRIP_FUSED=1` + `DSP4_SIMD_DYN=1` | 251,433–251,922 **76.7–76.9 %** | 307,247 **93.76 %** | 268,548–268,790 **81.95–82.03 %** | 284,249 **86.75 %** | **0** |

**D32 FITS with both switches on: zero missed blocks on both chips over
270,082 blocks, worst block 93.76 % on chip 1 and 86.75 % on chip 2.** The
target was 41,744 cycles on chip 2; this delivers **100,634**.

**But the split is the whole story.** `DSP4_STRIP_FUSED` alone is worth
**3,542 cycles/block on chip 2 — 1.08 % of budget — and does not close it.**
Everything else, **97,092 cycles/block = 29.6 % of budget**, is
`DSP4_SIMD_DYN`: GATE and COMP for two channels in one instruction stream.

And `DSP4_SIMD_DYN` is the half whose audio arm does not pass (§4).

## 3. Through-DSP latency, measured, with the CPLD loop as the reference

20 reps per arm, `dsp4_dsp_latency.py`, `_maincap` bitstream for the
through-DSP arms and `_pisel` for the reference, duplex overlay, the same
0.3 s `arecord` pre-roll on every arm so only differences are quoted.

| arm | min | median | DSP contribution (median) |
|---|--:|--:|--:|
| LOGIC loop (`_pisel`), reference | 14,429 | 14,436 | — |
| block 16, `DSP4_TX_EARLY=0` | 14,496 | 14,501 | **65–67 samples, 1.375 ms** |
| block 16, `DSP4_TX_EARLY=2` (chip 2) | 14,511–14,515 | 14,518 | **82** |
| block 16, `DSP4_TX_EARLY=3` (both) | 14,526 | 14,535 | **99** |
| block 32, `DSP4_TX_EARLY=0` | 14,561 | 14,567 | **131** |

**The alignment contract's block-16 through-DSP figure is 66 samples /
1.375 ms.** The 72-sample number it has been carrying is a **block-8**
figure taken on an image that was missing 70 % of its blocks; it is not
comparable and is superseded rather than corrected.

The LOGIC-loop minimum reproduces the 2026-09-09 sessions' 14,431 and
14,432 to within three samples on a third instrument run, which is what
makes the rest of the column worth reading.

**A latency arm needs `dsp4_passthru_setup.py` and this was nearly missed.**
Without it the through-DSP arm returned an offset of 14,779 on all 20 reps
with a **coherent fraction of 0.0 %** and a peak width of 400 — seventeen
sources sum into `C2_MIX_MAIN_L` and the stimulus never comes back. An
offset with a zero coherent fraction is not a latency; it is the scorer
saying so. `latency_run.sh` now runs the setup and says why.

## 4. What the bars say about the lever

`famverify.sh`, D24, both chips, contract `defs-v2026.09.08.4`, one
variable per arm:

| arm | contract | audio | numeric |
|---|---|---|---|
| **shipping configuration** | 20/20 families, **0 FAILED** | **17/20 LIVE** | COMPRESSOR / FADER_PAN / TUBE_SAT **BIT_EXACT** |
| `DSP4_STRIP_FUSED=1` | 20/20, **0 FAILED** | **17/20 LIVE**, verdict for verdict identical | the same three **BIT_EXACT** |
| `DSP4_SIMD_DYN=1` | 20/20, **0 FAILED** | ANTI_FB / CROSSOVER / GEQ / LIMITER **NO_CAPTURE**, GATE **INERT** | the same three **NO_STIMULUS** |
| both | — | **DOES NOT LINK**: chip 1 `sec_swco` overflow | — |

**`DSP4_STRIP_FUSED` is proven and worth 1.1 %. `DSP4_SIMD_DYN` closes D32
and is not proven.** Its contract arm is untouched — every cell still
answers at its landed address on all twenty families — but four families
stop capturing and the three numeric arms lose their stimulus.

That is **not** a demonstration of an audio defect, and it must not be
recorded as one. It is the same shape as S9-5: the paired graph adds a pool
slot and reorders the chain into pairs, so where a node's block lives moves,
and the witness reads a symbol chosen before it moved (S10-2). Settling it
is a session, and it is the same session that would settle whether the
`sec_swco` wall can be got round — because **the witness and the paired
kernels do not currently fit on chip 1 at the same time**, so the arm that
would certify the lever cannot presently be built.

## 5. Every prior capacity row, re-annotated

| date | figure | BLOCK | instrument | what it actually was | still valid? |
|---|--:|---|---|---|---|
| 09-03 `.3` | chip 2 256,919 | 16 | sigprofile2 | fused + SIMD + decimate 32 + signal | **instrument only** |
| 09-08 `.4` | chip 2 261,848 / 310,185 | 16 | fxcost | fused + SIMD + decimate 32 + signal, all-ones | **instrument only** |
| 09-09 chan-mask | chip 1 202,786 / chip 2 226,442 | 16 | sigprofile2 | fused + SIMD + decimate 32 + signal | **instrument only** |
| 09-09 S9 | chip 2 303,894 | 16 | wire + `_proc_cyc` | the shipping image | **valid** |
| 09-09 S10 | the D24/D32 table | 16 | `dsp4_capacity.py` | the shipping image | **valid** |
| 09-09 S11 | this document | 16, 32 | `capacity.sh` | named arm per row, both cfg words read back | **valid** |
