provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Every D24 kernel family on the part, addressed through the landed contract

Session: the queued VIRTUAL AUDIO block, steps 2–4 — the golden harness gets
its hardware target. Bench: rev-C unit `MW-D24-2` (`app@192.168.1.219`),
DSP4 card, `dsp4_config.py --product d24`. Image: the SHIPPING FLOAT
configuration, plain `./build.sh` (`DSP4_BQ_FLOAT=1`, `DSP4_GAIN_FLOAT=1`),
built from the tree at **defs-v2026.09.08.2**.

**chip1.ldr `906a70f7` (301,580 bytes), chip2.ldr `3a2d930c` (181,908
bytes)** — byte for byte the baseline this session started from, so the
build is its own W0 check: nothing measured here changed a source that
reaches an image.

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

| family | cells | chip / node | landed addrs answering | numeric | audio | verdict | reference model |
|---|---:|---|---:|---|---|---|---|
| `ANTI_FB` | 160 | chip 2 C2_AUX_AFB_01 | 20/20 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `AUX_INPUT` | 8 | chip 2 C2_BT_IN | 2/2 | - | NO_STIMULUS_PATH | **NOT EXERCISED** | none declared |
| `COMPRESSOR` | 544 | chip 1 C1_COMP_01 | 17/17 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `CROSSOVER` | 8 | chip 2 C2_MAIN_XOVER | 8/8 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `DCA` | 16 | chip 2 C2_DCA_01 | 2/2 | - | NO_PROBE | **NOT EXERCISED** | none declared |
| `DELAY` | 34 | chip 1 C1_DLY_01 | 1/1 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `EQ_BIQUAD` | 616 | chip 1 C1_EQ_01 | 14/14 | NOT_APPLICABLE | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `FADER_PAN` | 118 | chip 1 C1_FDR_01 | 3/3 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `FX_ENGINE` | 114 | chip 2 C2_FX_ENG_01 | 16/16 | - | INERT | **FAIL** | none declared |
| `GAIN` | 96 | chip 1 C1_GAIN_01 | 2/2 | - | LIVE | **PASS** | bq_float_ref arm — the GAIN audio word is float under DSP4_GAIN_FLOAT; its METER stays fixed |
| `GATE` | 336 | chip 1 C1_GATE_01 | 12/12 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `GEQ` | 364 | chip 2 C2_AUX_GEQ_01 | 28/28 | - | INERT | **FAIL** | bq_float_ref (float cascade, bit-exact) |
| `HPF_LPF` | 72 | chip 1 C1_FILT_01 | 3/3 | NOT_APPLICABLE | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `LIMITER` | 48 | chip 2 C2_AUX_LIM_01 | 4/4 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `METER` | 94 | chip 1 C1_MTR_01 | 0/0 | - | NO_PROBE | **FAIL** | fixed_ref (fixed arm, bit-exact) |
| `MONITOR` | 3 | chip 2 C2_MON | 3/3 | - | LIVE | **PASS** | none declared |
| `NOISE_GEN` | 3 | chip 1 C1_NOISE | 3/3 | - | LIVE | **PASS** | none declared |
| `ROUTING` | 1008 | chip 1 C1_RTG_01 | 42/42 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `TALKBACK` | 8 | chip 1 C1_TALK_01 | 4/4 | - | LIVE | **PASS** | none declared |
| `TUBE_SAT` | 48 | chip 1 C1_TUBE_01 | 2/2 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |

**Coverage.** Of the **20** D24 cell families `dsp.csv` addresses (3698 cells), **13 families PASSED on hardware (65 %)**, covering **2934 of 3698 addressed cells (79 %)**. **4 families passed on the strict bar** — the part's own samples reproduced word for word by the reference model — covering 1046 cells (28 %). 5 families FAILED.

| family | why |
|---|---|
| `ANTI_FB` | audio — the landed address answers and reaches no sample |
| `AUX_INPUT` | contract — 2/2 landed addresses answer; no stimulus path on this bench |
| `COMPRESSOR` | numeric — bit-exact on 1 stimuli |
| `CROSSOVER` | audio — the landed address answers and reaches no sample |
| `DCA` | contract — 2/2 landed addresses answer; no audio probe exists |
| `DELAY` | audio — moves 32 of 32 captured words over a floor of 0 |
| `EQ_BIQUAD` | audio — moves 32 of 32 captured words over a floor of 0 |
| `FADER_PAN` | numeric — bit-exact on 2 stimuli |
| `FX_ENGINE` | audio — the landed address answers and reaches no sample |
| `GAIN` | audio — moves 32 of 32 captured words over a floor of 0 |
| `GATE` | numeric — bit-exact on 1 stimuli |
| `GEQ` | audio — the landed address answers and reaches no sample |
| `HPF_LPF` | audio — moves 32 of 32 captured words over a floor of 0 |
| `LIMITER` | audio — moves 32 of 32 captured words over a floor of 0 |
| `METER` | meter — the SPI readback disagrees with the capture |
| `MONITOR` | audio — moves 32 of 32 captured words over a floor of 0 |
| `NOISE_GEN` | audio — moves 32 of 32 captured words over a floor of 0 |
| `ROUTING` | audio — moves 32 of 32 captured words over a floor of 0 |
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

### The gate never closes again — `ChanGateHold` reaches the kernel unconverted

`_gate_hold_<nid>` is an integer SAMPLE COUNT (the generator's initialiser is
`2400`, 50 ms at 48 kHz) and the SPI dispatch stores the host's IEEE-754
float32 word into it with no conversion. Writing the documented 1.0 ms lands
`0x3F800000` = **1,065,353,216 samples, about 6.2 hours**. Measured: with
that hold and the threshold raised to 0 dBFS over a −6 dBFS step,
`_gate_gain_target_q` stayed at unity and `_buf_C1_GATE_01` at `0x07FFFF07`.
Written as a raw `48` the gate behaves:

| threshold | `_gate_gain_target_q` | capture peak |
|---|---|---|
| −80 dB | 268435456 (unity) | `0x07FFFF07` |
| 0 dB | 2684355 (the range floor) | `0x00147BDB` |

The ladder itself is bit-exact against `fixed_ref` on this image, and the
threshold conversion is exact. See findings S2-1.

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

### METER: the readback matches the captured peak under neither reading

`_mtr_peak_C1_MTR_01` read `0x40E1AFA1` while the post-trim point it declares
(`taps=post_trim;...`, so the word at +0 is `C1_GAIN_01`'s output) captured a
peak of exactly 0.5 (`0x08000000`). As IEEE float32 that word is 7.0527; as a
Q4.28 integer it is 4.0551. Neither is 0.5. The 2026-08-23 run recorded the
same family as broken in a different way (a Q4.28 integer read as float32,
giving 3.85e−34); the word is now a plausible float and still not the peak.
`mtrverify.sh` is the family's own bar and was not run this session.

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

## What this run did NOT do

- **The Pi audio loop is still not a measurement channel.** Step 1 of the
  queued block (pass-through unity, bit-exact by the known-word test) stands;
  duplex streaming on the CM4 does not. See the overlay section below.
- Families are exercised on ONE representative node each, not on all 375.
  The address arithmetic is the same for every instance of a family (the
  landed map carries the stride), so a family verdict is a verdict about the
  kernel and the contract, not about every strip.
- `LIMITER`, `GEQ`, `ANTI_FB`, `FX_ENGINE`, `CROSSOVER`, `MONITOR` and
  `AUX_INPUT` live on chip 2 and are only as good as chip 2's boot; where
  chip 2 did not come up as chip 2 the run says NOT MEASURED rather than
  scoring silence.
