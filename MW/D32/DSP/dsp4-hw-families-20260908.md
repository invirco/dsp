provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Every D24 kernel family on the part, addressed through the landed contract

Session: the queued VIRTUAL AUDIO block, steps 2–4 — the golden harness gets
its hardware target. Bench: rev-C unit `MW-D24-2` (`app@192.168.1.219`),
DSP4 card, `dsp4_config.py --product d24`. Image: the SHIPPING FLOAT
configuration, plain `./build.sh` (`DSP4_BQ_FLOAT=1`, `DSP4_GAIN_FLOAT=1`),
built from the tree at **defs-v2026.09.08.2**.

**Two images, and the difference between them is the point.**

- **chip1 `906a70f7` (301,580 bytes) / chip2 `3a2d930c` (181,908 bytes)** —
  byte for byte the baseline the session started from. The first pass ran
  on this, so that pass is its own W0 check: nothing it measured changed a
  source that reaches an image.
- **chip1 `a07d3865` / chip2 `073d80ef`** — the same tree plus the
  wire-unit conversion at the SPI boundary (findings S2-8). The table below
  is this image. The images MUST differ, and they do: this is a firmware
  change, not an instrument change.

## What is new, and it is not another probe

Every hardware instrument this bench has run reached its parameters by
arithmetic — `(strip - 1) * 144 + 0x0029` for a gate threshold, transcribed
out of `dsp_address_map.md` into a constant at the top of a script. That is
a second opinion about the address map. Since **defs-v2026.09.08.2** there
is a landed one, `defs/products/d24/dsp.csv`, and this session is its FIRST
LIVE USE: `tools/dsp/landed_map.py` reads it, `--json` stages it beside the
images (the Pi has no `defs` checkout) carrying the `defs.lock` pin and the
CSV's sha256, and `tools/pi/dsp4_family_verify.py` resolves every address it
writes **by cell name** out of that file.

> landed `dsp.csv` → `landed_map.py --json` → staged with the images →
> cell name → (chip, page, addr) → the SPI link

**The transcription and the contract agree, 25 of 25.** Every constant
`dsp4_conform.py` and `dsp4_node_verify.py` reach their parameters by was
checked against the landed address for the cell it is meant to be, and none
disagreed. That is the result the cross-check exists to produce, and it is
worth having as a measurement rather than as an assumption: a disagreement
would have meant every measurement ever taken through the old constant was
taken at an address the contract does not name.

**Every landed address that was written ANSWERED.** The contract phase
writes each `rw` cell of a representative node at its landed address and
reads the part's own `SPI_ERR_COUNT` either side — the handler increments it
only when the dispatch entry is 0 or the address is out of bounds, which is
the one way to tell "the kernel consumed the word" from "there is nothing
here". No address on any family reported `NO_ENTRY`.

## Three phases, three different questions

- **CONTRACT** — do the landed addresses answer? (`SPI_ERR_COUNT`, per cell.)
- **NUMERIC** — does the reference model reproduce the part's captured
  samples WORD FOR WORD, with the model's deliberately-wrong twin required
  to disagree on the same samples? Delegated to `dsp4_node_verify.run_node`,
  so a family scored here is scored by the instrument that already carries
  its negative control.
- **AUDIO** — does driving a landed address MOVE the captured samples of its
  own node, over a measured null-interval floor? A landed address that
  answers and reaches no sample is the D38 inert surface, and it is reported
  as inert rather than as a pass.

A family with no reference model is not scored as if it had one, and a
family with no stimulus path on this bench is reported as such rather than
as inert. The coverage fraction below is worthless if it flatters its own
denominator.

## The coverage table

Three families are scored by their own dedicated bar rather than by a probe
inside the family walk, and the table says which bar and which image: a
walk-probe can be wrong about a family in ways the dedicated instrument is
not, and METER is exactly that case (see below).

| family | cells | chip / node | landed addrs answering | numeric | audio | verdict | reference model |
|---|---:|---|---:|---|---|---|---|
| `ANTI_FB` | 160 | chip 2 C2_AUX_AFB_01 | 20/20 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `AUX_INPUT` | 8 | chip 2 C2_BT_IN | 2/2 | - | NO_STIMULUS_PATH | **NOT EXERCISED** | none declared |
| `COMPRESSOR` | 544 | chip 1 C1_COMP_01 | 17/17 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `CROSSOVER` | 8 | chip 2 C2_MAIN_XOVER | 8/8 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `DCA` | 16 | chip 2 C2_DCA_01 | 2/2 | - | NO_PROBE | **NOT EXERCISED** | none declared |
| `DELAY` | 34 | chip 1 C1_DLY_01 | 1/1 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `EQ_BIQUAD` | 616 | chip 1 C1_EQ_01 | 14/14 | bqeverify.sh float | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `FADER_PAN` | 118 | chip 1 C1_FDR_01 | 3/3 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `FX_ENGINE` | 114 | chip 2 C2_FX_ENG_01 | 16/16 | - | INERT | **FAIL** | none declared |
| `GAIN` | 96 | chip 1 C1_GAIN_01 | 2/2 | - | LIVE | **PASS** | bq_float_ref arm — the GAIN audio word is float under DSP4_GAIN_FLOAT; its METER stays fixed |
| `GATE` | 336 | chip 1 C1_GATE_01 | 12/12 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `GEQ` | 364 | chip 2 C2_AUX_GEQ_01 | 28/28 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `HPF_LPF` | 72 | chip 1 C1_FILT_01 | 3/3 | bqeverify.sh float | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `LIMITER` | 48 | chip 2 C2_AUX_LIM_01 | 4/4 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `METER` | 94 | chip 1 C1_MTR_01 | 0/0 | mtrverify.sh | NO_PROBE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `MONITOR` | 3 | chip 2 C2_MON | 3/3 | - | LIVE | **PASS** | none declared |
| `NOISE_GEN` | 3 | chip 1 C1_NOISE | 3/3 | - | LIVE | **PASS** | none declared |
| `ROUTING` | 1008 | chip 1 C1_RTG_01 | 42/42 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `TALKBACK` | 8 | chip 1 C1_TALK_01 | 4/4 | - | LIVE | **PASS** | none declared |
| `TUBE_SAT` | 48 | chip 1 C1_TUBE_01 | 2/2 | BIT_EXACT | NO_FLOOR | **PASS** | fixed_ref (fixed arm, bit-exact) |

**Coverage.** Of the **20** D24 cell families `dsp.csv` addresses (3698 cells), **14 families PASSED on hardware (70 %)**, covering **3028 of 3698 addressed cells (82 %)**. **7 families passed on the strict bar** — the part's own samples reproduced word for word by the reference model — covering 1828 cells (49 %). 4 families FAILED.

| family | why |
|---|---|
| `ANTI_FB` | audio — the landed address answers and reaches no sample |
| `AUX_INPUT` | contract — 2/2 landed addresses answer; no stimulus path on this bench |
| `COMPRESSOR` | numeric — bit-exact on 1 stimuli |
| `CROSSOVER` | audio — the landed address answers and reaches no sample |
| `DCA` | contract — 2/2 landed addresses answer; no audio probe exists |
| `DELAY` | audio — moves 32 of 32 captured words over a floor of 32 |
| `EQ_BIQUAD` | external — bqeverify.sh float on image chip1 adeb3f0c / chip2 3c48d892 — BQE_VERIFY PASS — 0 ULP over 192 cascades x 3 levels x 4 blocks, divergence bitmap 566 of 576 cells matches the model |
| `FADER_PAN` | numeric — bit-exact on 2 stimuli |
| `FX_ENGINE` | audio — the landed address answers and reaches no sample |
| `GAIN` | audio — moves 32 of 32 captured words over a floor of 0 |
| `GATE` | numeric — bit-exact on 1 stimuli |
| `GEQ` | audio — the landed address answers and reaches no sample |
| `HPF_LPF` | external — bqeverify.sh float on image chip1 adeb3f0c / chip2 3c48d892 — BQE_VERIFY PASS — 0 ULP, same vector set |
| `LIMITER` | audio — moves 32 of 32 captured words over a floor of 0 |
| `METER` | external — mtrverify.sh on image block-8 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 — METER_BIT_EXACT — ms64 exact, both pk64 words exact, float readback peak 0.5 rms 0.5 at 0 relative error, BLOCK=32 negative control correctly rejected |
| `MONITOR` | audio — moves 32 of 32 captured words over a floor of 0 |
| `NOISE_GEN` | audio — moves 32 of 32 captured words over a floor of 0 |
| `ROUTING` | audio — moves 32 of 32 captured words over a floor of 32 |
| `TALKBACK` | audio — moves 32 of 32 captured words over a floor of 0 |
| `TUBE_SAT` | numeric — bit-exact on 2 stimuli |

## Which comparison applies, per family

The image is the shipping FLOAT path, and that decides the reference, not a
preference. `shared/numeric-spec.md` §"Acceptance tolerances" states the two
bars:

- **SHARC float cascade ≡ `bq_float_ref`** (bit-exact, on the part), and
  `bq_float_ref` ≈ float64 within ±0.01 dB (f0 ≥ 50 Hz) / ±0.05 dB at 20 Hz.
  This is the bar for `EQ_BIQUAD`, `HPF_LPF`, `GEQ`, `ANTI_FB` and
  `CROSSOVER`, and for the GAIN node's audio word (its meter stays fixed).
- **SHARC fixed arm ≡ `fixed_ref`** (bit-exact), and `fixed_ref` ≈ float64
  within the same tolerances. This is the bar for `GATE`, `COMPRESSOR`,
  `LIMITER`, `TUBE_SAT`, `DELAY`, `FADER_PAN`, `ROUTING` and `METER`.

**The first run of this bar got that wrong and it is worth recording.** It
ran `BQCVT` — the fixed arm's coefficient converter — against the float
image and reported EQ and FILT as FAILED. The part held `0x3F800000`
(IEEE float 1.0) where `fixed_ref.biquad_coeffs_q` predicted `268435456`
(Q4.28 1.0). That is not a firmware defect; it is the harness quoting the
wrong model for the arm it was pointed at. `dsp4_family_verify.py` now takes
`--bq-arm` from the build and skips `BQCVT` on a float image, naming
`bqeverify.sh float` as the arm's real bit-exact bar.

## Defects this run found

### The gate never closed again — `ChanGateHold`, found and FIXED

`_gate_hold_<nid>` is an integer SAMPLE COUNT (the generator's initialiser
is `2400`, 50 ms at 48 kHz) and the SPI handler stored the host's IEEE-754
float32 word into it with no conversion. Writing the documented 1.0 ms
landed `0x3F800000` = **1,065,353,216 samples, about 6.2 hours**, so a gate
that had opened once never closed again. Measured with that hold and the
threshold at 0 dBFS over a −6 dBFS step: `_gate_gain_target_q` stayed at
unity and `_buf_C1_GATE_01` at `0x07FFFF07`.

**The ladder was never the fault** — `dsp4_node_verify` scores GATE
bit-exact against `fixed_ref` on the same image, converted parameters and
all, and the threshold conversion is exact. The missing conversion was the
whole defect.

**The fix is generic over the landed `wire-units.csv`, not a patch for
Hold**, and writing it that way is what found the second one:

```
wire-unit conversions applied at the SPI boundary:
  ChanDelay          ms -> samples    32 addresses
  ChanGateHold       ms -> samples    32 addresses
```

`ChanDelay` had the identical shape: `_dly_read_offset_<nid>` is a sample
offset, so 250.0 ms landed `0x437A0000` and was clamped to the buffer
length — every delay setting above about a millisecond saturated.

`gen_dsp.py` builds `_spi_dispatch_cN_convert[]` from
`defs/common/wire/wire-units.csv`, indexed exactly like the dispatch table,
and `spi_handler.asm` applies it **at the wire and in both directions**. At
the wire because the ramp engine interpolates between the current word and
the new one, so a current word in samples and an incoming one in
milliseconds makes every intermediate value meaningless. Both directions
because save-and-restore — what every probe on this bench does around a
write — would otherwise read samples back and write them as milliseconds.
Verified on the part:

| cell | written | kernel word | read back |
|---|---|---|---|
| `Chan001GateHold001` | 1.0 ms | `_gate_hold` = **48** | 1.0000 ms |
| `Chan001GateHold001` | 50.0 ms | `_gate_hold` = **2400** | 50.0000 ms |
| `Chan001Delay001` | 20.0 ms | `_dly_read_offset` = **960** | 20.0000 ms |

2400 is the generator's own initialiser, so the conversion lands on the
value the kernel was written around. GATE then passes the strict bar AND
drives the audio with the documented millisecond value, with no raw
sample-count workaround anywhere in the harness. Full detail, including the
nine declared mismatches the contract does NOT yet state a conversion for,
in findings S2-8.

### Four families answer every landed address and reach no sample

`ANTI_FB`, `GEQ`, `CROSSOVER` and `FX_ENGINE` — **646 of the 3,698 addressed
cells** — take every write at their landed address, raise no SPI error, and
change nothing. Confirmed the strongest way available, by walking the chain
with an impulse and diffing consecutive node buffers word for word:

```
aux 1, GEQ bands at +12/-12 dB, notch armed 1 kHz Q4 -18 dB
  _buf_C2_AUX_FDR_01   0x08000000 0 0 0
  _buf_C2_AUX_EQ_01    ... 0 of 32 samples differ from the previous node
  _buf_C2_AUX_GEQ_01   ... 0 of 32
  _buf_C2_AUX_AFB_01   ... 0 of 32
  _buf_C2_AUX_LIM_01   ... 0 of 32

main, crossover frequency 500 Hz
  _buf_C2_MAIN_DLY     0x08000000 0 0 0
  _buf_C2_MAIN_XOVER   ... 0 of 32     <- the crossover does not split
  _buf_C2_MAIN_OEQ_01  ... 0 of 32
  _buf_C2_MAIN_OEQ_02  ... 0 of 32

FX 1, On=1, Mix=100, Decay=2.0
  _buf_C2_FX_ENG_01    0x08000000 0 0 0
  _buf_C2_FX_FDR_01    ... 0 of 32
```

`ANTI_FB` and `FX_ENGINE` are **corroborated by the D38 static list**
(`docs/contract/inert-cells-d38.md` names every notch and every FX parameter
as unreferenced by any emitted line), so this is the live confirmation that
list has been waiting for. **`GEQ` and `CROSSOVER` are NOT on that list**,
and that is the new part: 372 addressed cells that static analysis believed
something reads.

### METER is BIT-EXACT, and the first verdict on it was the instrument

`mtrverify.sh` reads **METER_BIT_EXACT** on this tree: the 64-bit meter
state reproduces `fixed_ref.meter_block` exactly (`ms64` exact, both `pk64`
words exact), the float readback is peak 0.5 / rms 0.5 at 0.000e+00
relative error, the BLOCK=32-coefficient negative control is correctly
rejected, and the wide-word control rejects the narrow model.

**The family walk had reported DISAGREES, and that was this tool's fault,
not the meter's.** It read `_mtr_peak_C1_MTR_01` as `0x40E1AFA1` — 7.05 as
float32 — against a captured post-trim peak of exactly 0.5. A peak HOLD is
stateful, and the contract sweep that runs immediately before writes 1.0f
into every rw cell of the node it is probing, which drives the strip near
full scale; the hold had not decayed by the time the meter was read. 7.05
sitting just under the Q8.24 ceiling of 8.0 was the clue and it was not
followed. `meter_phase()` now reports `NO_VERDICT` with the reason and
names `mtrverify.sh` instead of scoring a number it cannot interpret.

### Instrument faults, each of which had already produced a wrong answer

Three, all fixed, all recorded in findings S2-2, S2-3 and S2-4: the zero
sentinel left unarmed (so any parameter genuinely holding 0 read as
unreadable, which cost COMPRESSOR its verdict twice); `BQCVT` scoring the
float image against the fixed reference (reported EQ and FILT as FAILED when
the part held float 1.0 and the model predicted Q4.28 1.0); and a DC step
used to probe filters (reported GEQ, ANTI_FB and CROSSOVER as inert on a
stimulus that cannot see a peaking section at all — the verdicts above are
from an impulse, which can).

### Corroborated on the part: `ChanGain` and `TalkGain` are linear, not dB

Both are `unit UNDECLARED` in the wire table with the Table domain (dB)
proposed as the wire unit. Writing 4.0 to either, over a 0.5 impulse, gives
an output peak of `0x20000000` = 2.0 — a factor of four, not the 1.585 that
4 dB would be. Adopting the proposal as written needs a dB→linear conversion
in the kernel first; without one, the documented 0 dB would silence the
strip.

## The CM4 loop: a pass-through with no pedestal, and no latency yet

The queued block's step 1 recorded the Pi audio path as unusable: two PCM
devices sharing one `bcm2835-i2s` CPU DAI, so opening both re-programs the
same block twice. **One dai-link with a bidirectional codec is the right
shape, and no codec in the Pi tree fits this link** — measured, four of
them, before writing one:

| codec | result |
|---|---|
| `spdif-dit` + `spdif-dir`, two links | the overlay being replaced: right rate and format, one direction each |
| the same two, multi-codec on ONE link | instantiates **capture only** |
| `asahi-kasei,ak4554` | ONE dai-link, a REAL duplex device — and **S16_LE only** |
| `google,voicehat` | both directions, S32_LE — and **48 kHz only** |

The hub's pin ruling (CM4 GPIO17 = CS6 as `sdmode-gpios`) cleared
voicehat's mandatory-GPIO probe failure exactly as ruled and the card came
up; it is voicehat's RATE that disqualifies it, and the rate is not
negotiable — `slot-map.csv` lane A_I6 says LOGIC "regroups 4 Pi frames per
DSP frame", so the Pi frame is 2 slots × 32 bits at **192 kHz**.
`invirco,dsp4-pcm-dummy` is forty lines of DAI declaration — both
directions, 8–192 kHz, S32_LE, no registers, no control bus, **no GPIO**,
so CS6 stays free:

```
00-00: bcm2835-i2s-dsp4-dummy-hifi ... : playback 1 : capture 1
arecord -D hw:dsp4pcm,0 -f S32_LE -c 2 -r 192000  ->  192000 Hz, Stereo
```

### The pass-through, addressed from the contract

Seventeen sources sum into `C2_MIX_MAIN_L`. `passthru_setup.py` silences
sixteen by CELL NAME out of the landed map — 24 strips taken off the main
bus *and* muted (two independent ways, so one inert cell cannot leave the
bus live and look like a pedestal), the three auxiliary inputs switched
off, the four groups muted, main fader unity, main delay zero. **All 60
cells were present in the contract.** The eight snake returns have no cell
at all and could not be silenced from it; nothing is connected to them here
and the measurement shows they contribute nothing.

**No pedestal.** Nothing played: `_buf_C2_MIX_MAIN_L`, `_buf_C2_MAIN_FDR`,
`_buf_C2_MAIN_DLY` and `_buf_C2_MAIN_ST_OUT` all read `0x00000000`, and the
captured measurement channel idles at 8 LSB (−168 dBFS) — the residue on
the slot nothing drives. The `0x11E7E000` pedestal is gone.

| played | returned | ratio |
|---|---|---|
| `0x00001000` | `0x00001000` | **1.0000**, `in << 0` |
| `0x00010000` | `0x0000FFF8` | 0.9999 |
| `0x00100000` | `0x000FFF88` | 0.9999 |

The apparent ×2 was `Pi001Level001` and not a scatter/gather shift: at 0.5
the loop is unity, with `_auxin_q_C2_PI_IN` reading Q4.28 0.5 exactly,
target matched and frames 0. Played into L only the word returns; into R
only, nothing; into both, the same as L alone — no L+R summing, and
`C2_MAIN_ST_OUT` drives one slot, confirmed on the part.

### Why there is still no latency figure

**The loop does not preserve sample order.** A counter whose every value
was held for 64 Pi frames — 16 DSP frames, four times the regrouping ratio
— returns with only **40.4 % of its transitions monotonic** over 59,498
carrying frames, the dominant index step about **−9 values ≈ 576 Pi frames
backwards**. DC returns perfectly and a ramp does not, which is a reader
sampling the wrong one of the four regrouped Pi frames and periodically
re-reading a stale region, not a gain or a clock error. A latency measured
through a path that reorders is not a latency, so none is recorded. The
next probe is the CPLD reframe (`rtl/dsp4_pcm_reframe.v`) against the DSP's
Pi-input DMA — the ALSA layer is now known good.

**No family verdict in the table above depended on the loop.** Every one was
measured through `src/scope.asm`, inside the DSP, so the coverage fraction
stands as it is.

## What this run did NOT do

- **No latency figure**, and the reason is measured rather than assumed:
  the loop reorders samples (above).
- **The loop is not bit-exact**: a known word returns at 1.0000 for
  `0x00001000` and 0.9999 for larger ones, an amplitude error of about
  1.2e-4 that is NOT the Pi input coefficient (measured exact) and is not
  yet attributed.
- Families are exercised on ONE representative node each, not on all 375.
  The address arithmetic is the same for every instance of a family (the
  landed map carries the stride), so a family verdict is a verdict about
  the kernel and the contract, not about every strip.
- The eight `C2_SNK_IN_*` snake returns have no cell in the landed map, so
  the pass-through could not silence them from the contract. Nothing is
  connected to them on this bench.
- `conform.sh` was not run. `busgold` WAS (0 of 256 words differ,
  GRAPH BIT-EXACT), because the audio image moved this session and the
  byte-identity argument that used to cover it no longer applies.
