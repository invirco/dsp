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

* **The latency figures are scaled, not measured, AND THE REQUAL COULD NOT
  CLOSE THIS — see §7.3.** `dsp_block.h` records ~23 samples ≈ 0.48 ms at
  block 8, itself derived from **93 samples measured at block 32**. Block
  16 is interpolated at ~2.9 × BLOCK. **The bench's audio return path is
  currently dead, so the measurement could not be made.**
* ~~The ~6% margin at block 16 is thin and was taken decimated.~~
  **RESOLVED — SEE §7. The undecimated real-time run passes at block 16
  and fails at block 8.**
* ~~No bar has been run at block 16.~~ **RESOLVED — SEE §7.4. The full
  bar set has now been run at block 16 and passes, D80 excepted.**
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

---

## 7. BLOCK-16 REQUAL (added later the same session)

### 7.1 The undecimated real-time run — the falsifier, and it passed

Every capacity figure in §1 was taken with `DEC=32`, which changes how
often a graph pass runs and not what one costs. The question that
decimation cannot answer is whether the graph actually keeps up in real
time. Run at `MODE=rate` (undecimated), 32 strips, stimulus present:

```
BLOCK 16:  REAL_TIME (3000 passes/s of 3000)
BLOCK  8:  OVER_BUDGET: transport 5997/s but only 5187 passes/s
```

Both points witnessed on the signal path, not the cheap branch: **gate
OPEN 32 / SHUT 0, comp ACTIVE 32 / unity 0, unreadable 0, signal present
on all 32 strips**. `DMA0_STAT 0x6200`, `SPORT0_ERR_A 0`, `BOOT_STAGE 7`
in both.

**This is a direct pass/fail, not an extrapolation from a cycle count**,
and it agrees with the cycle count from an unrelated direction: block 8
achieves 5,187 of the 5,997 passes/s the transport demands, i.e. 86.5%,
which implies **115.6% of budget against the 116.4% measured by cycle
count on chip 1 — 0.8% apart, two instruments sharing no arithmetic.**

**Block 16 sustains real time with the full 32-strip graph. Block 8 does
not.** That is the recommendation's load-bearing claim and it is now
measured rather than inferred.

### 7.2 Golden harness at block 16 — 59/59

Run with `DSP4_GEN_BLOCK=16`, which is a real block-16 result rather than a
re-run of the block-8 one: the meter coefficients are derived from the
BLOCK RATE (`DSP4_MTR_ALPHA_Q`, `DSP4_MTR_BETA_Q`), so a block-size change
is exactly what would break them. It is also the third recorded
meter-defect class in this tree, so it is the right thing to check first.

### 7.3 The latency measurement DID NOT HAPPEN, and why

**The one number the recommendation trades on is still scaled, and this
requal failed to replace it.** That is stated plainly because it is the
weakest point of the package.

The recorded 93-sample figure was taken DIFFERENTIALLY against a second
CPLD bitstream looping inside LOGIC, which cancels ALSA start skew. That
bitstream cannot be swapped remotely. So the plan was to avoid the swap
entirely: measure THROUGH-DSP at blocks 8, 16 and 32 in one session with
identical ALSA settings, where the DIFFERENCES cancel the skew and the
LOGIC path just as well, with block 32 anchoring on the recorded absolute.

**It returned nothing at any of the three block sizes.** Diagnosed rather
than assumed:

| check | result |
|---|---|
| ALSA devices | present and correctly named — `hw:dsp4pcm,0` capture, `,1` playback |
| pin mux | `pinctrl 18-21 = a0`, PCM_CLK/FS/DIN/DOUT on ALT0 as the recipe requires |
| interface clocking | `arecord` returns its full 144,000 frames, so the I2S clock is running |
| **captured audio** | **0 non-zero samples of 144,000, max abs 0** |

A raw play/record pair with **no DSP involvement at all** captures pure
silence, so this is upstream of the firmware, upstream of anything in this
session, and independent of block size: **the CPLD is not returning audio
on the Pi's capture lane in the bench's present state.** Restoring it is a
LOGIC bring-up task needing Quartus and JTAG, which is physical-access
work.

**Consequence for the decision.** The ~0.49 ms cost of block 16 remains an
interpolation from a single measurement taken at block 32, and PW should
treat it as such. It is the one claim in this package with no measurement
behind it at the chosen operating point. **If the latency budget is tight
enough that 0.5 ms decides the answer, the bench audio path must be
restored and the pipeline measured at block 16 before committing** — the
capacity side of the decision is settled, the cost side is not.

### 7.4 The full bar set at block 16

| bar | verdict at block 16 | against block 8 |
|---|---|---|
| `c2bqgold.sh` — biquad pairing | **BIT-EXACT**, 49 output blocks 0 differ | identical |
| — its negative control | **6 of 6** channel-B cascades moved, **0 of 2** channel-A | identical |
| — the round-trip arm vs scalar / vs latched | **0 of 49** each | identical |
| — latch witness | 1 on all five probed pairs | identical |
| `c2xgold.sh` — cross-chain dynamics pairing | **BIT-EXACT**, 49 output blocks 0 differ | identical |
| — its negative control | **2 of 2** SUB outputs moved, **0 of 2** MAIN | identical |
| `busgold.sh` — chip 1's main bus vs the stored session-6 golden | **GRAPH BIT-EXACT, 0 of 256 words** | identical |
| `conform.sh` — contract conformance, both chips | **PASS** | identical |
| — presence, chip 1 | 6032 / 388 / 117 / 56 / 159 | **identical** |
| — presence, chip 2 on its own map | 1701 / 24 / 21 / 175 / 31 | **identical** |
| — declared-unit checks | 18 pass, 16 fail (the named D41 ones) | identical |
| — negative control wrong-unit | FAILED as required, 4 of 4 | identical |
| `golden_harness.py` (`DSP4_GEN_BLOCK=16`) | **59/59** | identical |
| `c2gold.sh` — per-sample reference vs block kernels | FAILED (meters 19 of 24) — **D80**, set probes 0 differ | same count, same signature |

**`busgold` is the strongest of these and deserves a sentence.** The stored
golden is 256 consecutive words of `_buf_C1_BUS_MAIN_L` captured at
BLOCK 8 on 2026-08-30. The block-16 build reproduces it **word for word**,
which says the block size does not change the audio at all — not
approximately, not within a tolerance. That is the property a block-size
change most needed to demonstrate and the one hardest to fake.

**Both pairing bars carry their negative controls at block 16 exactly as
at block 8**, which is what makes the two BIT-EXACT verdicts mean
something rather than being comparisons that cannot fail.

**A defect in the bars was found and fixed on the way.** `busgold.sh` and
`conform.sh` staged `tools/pi/dsp4_block.py` — the SHIPPING block-8 file —
regardless of which image they had just built. `conform` checks RAMP
TIMINGS and ramp frame counts are derived from the block rate, so a
block-16 image would have been scored against block-8 ramp expectations.
Both now stage the `dsp4_block.py` from the tree they built from, which is
the convention `captable.sh` and `sigprofile2.sh` already follow and for
the same stated reason.

### 7.5 D80 at block 16 — reproduced, larger, and not newly explained

`c2gold` fails at block 16 exactly as at block 8: **19 of 24 meters
differ, set probes 0 differ**, peaks LOW in the block arm and RMS HIGH,
opposite directions so not a gain error, confined to the GATE/COMP-engaged
chains. The **magnitude is larger — worst 0.995% against 0.598% at block 8
today**, inside the 1.249% cross-build worst session 17 recorded.

A larger divergence at block 16 is what the convergence-curve explanation
PREDICTS rather than evidence of something new: the per-sample arm makes
sixteen body calls per block against the block arm's one, so the two arms'
speed difference is bigger, and the meters are per-block IIRs read
mid-convergence. **The audio path agrees bit-for-bit in both arms.** That
is a consistent reading, not a proof — one run at each block size cannot
separate a block-size effect from capture-state variation, and **D80
remains open and unexplained either way.**

### 7.6 What the requal changes about the recommendation

**Nothing, and that is the point.** Block 16 was recommended on capacity;
it now also carries the full bar set, an undecimated real-time pass, and a
bit-exact main bus against a golden captured at block 8. The one gap that
remains open is the LATENCY COST (§7.3), which the bench could not measure
because its audio return path is dead.
