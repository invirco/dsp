provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The closed-loop audio acceptance layer (S66)

This is the audio part of the D24 automated acceptance test. It takes the product's definitions and the standard audio test set (mx26 `docs/spec-audio-test-set.md`) and produces one fixture per testable path. A runner executes the fixture and writes a pass/flag result per path. These are the same tables S54–S65 produced by hand, now generated. The layer is not a browser and not the UI-automation layer (that is the app/Avalonia layer).

## The three pieces

| piece | file | what it does |
|---|---|---|
| fixture generator | `tools/accept/gen_accept_fixtures.py` | defs → `MW/<P>/DSP/accept/fixtures/*.json` + `manifest.json` (deterministic) |
| runner | `tools/pi/dsp4_accept.py` | `run` one fixture against a source (live or replay), `report` a unit table, `plan` the time |
| dry run | `tools/accept/dryrun_d24.sh` | fixtures + replay maps from the recorded D24 data → `MW/D24/DSP/s66/` results, report, comparison with the hand tables, time projection |

Tables the layer reads, and nothing else:

| table | role |
|---|---|
| `defs/products/<p>/inputs.csv` | mic inputs: XLR, 595 send position, strip, rx cell |
| `defs/products/<p>/<p>-io.csv` | outputs (panel labels) |
| `defs/gen/matrix/<p>-diagram.csv` | the product topology (defs applies the gates) |
| `MW/<P>/MX/_matrix.csv` | expanded cells with `Neutral` and DSP address (generated from defs) |
| `tools/accept/path-cells.csv` | topology element → cell families. **Proposed for defs** (S66-1) |
| `tools/accept/battery.csv` | T1–T8, T4b, A1: which path types, factory vs full, method |
| `tools/accept/limits.csv` | every pass/flag limit, all **provisional**; PW tunes this file only |
| `tools/accept/units.csv` | per unit: DAC FS dBu, the loop (donor strip, aux, expected polarity/latency), EIN source, ADC floor |
| `tools/accept/step-costs.csv` | measured seconds per step (S60/S61/S63), for `plan` |

## The fixture rule

PW 09-14, with the `Neutral` column as defs defines it:

- **Path cells.** The in-line path is the longest route through the product topology from the input to the measurement point. For an input that is `io.in → ch.insel → ch.pre → ch.phase → ch.hpf → ch.lpf → ch.gate → ch.eq → ch.comp → ch.delay → ch.ins → ch.fdr → ch.pan → pick.postfdr`, measured by TEST_MEAS post-fader. Sidechain-key nodes are never part of the route, and a pick tap only appears at either end. Every cell bound to a path element is written to its `Neutral`.
- **Assigns.** A path element (assign or send) on the path is written to its `Neutral`, which means enabled. The same element for every other strip on that bus is written to 0 (isolation). The strip under measurement has every assign off, so it cannot feed the loop that stimulates it.
- **Stimulus.** On today's manual loop this is TEST_OSC on the donor strip (6) → AUX 1 → J45 → cable. The donor strip is made transparent with `CompOn 0`/`MainOn 0` (the S54-2 lesson) and only its AUX 1 send is live. When the donor is itself the path under test, the fixture moves the stimulus to strip 1, as S55 did for J32. On the harness this block is replaced by the harness source.
- **Drive.** `Chan Gain` (the DSP trim, 0 dB during the battery) and the 595 code (per test, at the fixture's send position) are set by the test, not by the fixture.
- **Undecidable and absent.** A cell whose `Neutral` is empty is **undecidable** and is listed, never guessed (`Main001Level001` on the main outputs). A family the binding names but the product lacks is listed as **absent**.
- **Output paths** loop back into the reference input (MIC 5 at code 0). Lane dBFS converts to dBu at the output as P + 3.01 + DAC FS − G_loop(ref, 0) (S57).

Generated for D24: 38 fixtures. 24 inputs; 11 outputs (AUX 1–8, Main L/R, C/LF); 2 Monitor Out fixtures emitted as `undecidable` (no `mon → io.out` edge); 1 node fixture (cue bus + RTA, `status: proposal`).

## Modes

| test | factory | full |
|---|---|---|
| T1 gain law | chirps at codes 0 1 2 4 8 16 32 63. Stages within ±0.5 dB of the universal mean; code 63 within ±0.5 dB of the stage sum | all 64 codes, monotonic per bit, deviation from the universal mean |
| T2 response | from the code 0 / 63 chirps: ±0.5 dB, 20 Hz at max gain ≥ −2.5 dB | same |
| T3 | THD+N at code 0 and THD h2..h10 at code 63, lane −3 dBFS pk | + THD+N vs level |
| T4 | outputs: dBu 20–20k and A (floor-corrected alongside) | + input floors at the T1 codes |
| T4b | EIN at code 63, dBu 20–20k / A / DC–24k, source stated | + code 0 (converter floor) |
| T5 / T8 | from the code 0 chirp, against the unit's loop polarity / latency | same |
| T6 | — | DSP strip mute depth |
| T7 | 10 kHz, worst neighbour | same |
| A1 | — | gain-change spans: peak ≤ −60 dBFS, pump ≤ 50 ms (S63) |

Verdicts: PASS, FLAG, NO DATA (never a pass), INFO. A path is FLAG if any test flags, INCOMPLETE if a test the mode needs has no data, and PASS otherwise. Until the product's ranges are extracted, a FLAG is a number to look at, not a reject.

## Sources

- **replay:MAP.json** answers from recorded data. Captures are analysed exactly as live captures would be (dsp4_chirp, dsp4_fft band power, s63_analyse for spans). A recorded tone/meter result is reported with its file and method. A key declared `none` reports NO DATA with its reason.
- **live** runs the s61lib rig: chain, chirp/tone, capture (bulk read). **Not exercised: S66 was a desk session.** No verified host command in this repo writes a cell by MxDat code, so the live source refuses to run until `ACCEPT_SET_CMD` names one. Order is level first, then code, then settle (S60-3).

## Dry run on the recorded D24 data (MW-D24-2)

`tools/accept/dryrun_d24.sh` → `MW/D24/DSP/s66/{run.out, report.md, compare.md, plan.out}`. Results are byte-identical on a re-run.

**Reproduction: 187 of 187 comparisons agree within tolerance** (`compare.md`). What was compared:

- **MIC 5 against S61 `results.json`.** Eight chirp gains, T2 at 20/50/100/10k/20k Hz for codes 0 and 63, latency, polarity and THD+N code 0: exact (≤ 0.0005 dB). THD code 63 against S63's 32-capture average: exact. EIN lane powers against S57: exact. A1 against S63: 70 transitions, 68 PASS / 2 pump flags, worst −74.0 dBFS.
- **The 15 S55 channels against `channels.md` and `trim-table.md`.** T2 20 Hz, T3 code 63, EIN 20–20k/A, T5, T8, and each channel's worst deviation from the universal mean. J29 is the only T1 flag.
- **AUX 1 output noise against S57:** −84.55 dBu 20–20k, −86.96 dBu(A), floor-corrected −85.18 / −88.13.
- **The cue/RTA node against the S65-3 table:** every level error and octave figure.

Three differences were explained, not hidden:

1. MIC 5's EIN dBu is 0.024 dB lower than S57's. The noise powers are identical; the runner divides by this run's T1 gain at code 63 (the S61 chirp, 58.743 dB, which carries the loop source's noise, +0.026 dB) where S57 used S54's tone gain (58.717).
2. The worst-deviation figures match to 0.001 dB, the rounding of the 3-decimal `law.csv`.
3. The first node run flagged PFL and the mono aux source for a "hot cold side". Both are mono by design. The fixture now marks those cases mono and the runner checks the two sides are equal.

**What the generated factory table says** (`report.md`):

| path | verdict | why |
|---|---|---|
| MIC 5 | PASS | T1 stage sum −0.068 dB; T2 20 Hz at 63 −2.07 dB; THD+N −88.96 dB = 0.0036 %; THD at max gain −64.33 dB = 0.061 %; EIN −127.2 / −130.5 dBu(A); T7 −133.06 dB; 91.398 samples, inverted |
| MIC 7 (J29) | FLAG | T1 code 8 −0.849 dB off the universal mean (the bit-3 stage, S55-2) |
| MIC 8 (J31) / MIC 20 (J32) | FLAG | EIN −123.2 / −125.2 dBu against the provisional −126.0 (the HF excess, S55-5) |
| 12 other S55 channels | INCOMPLETE | T3 THD-only at max gain and T7 were measured on MIC 5 only |
| AUX 1 | INCOMPLETE | only T4 output noise exists: PASS at −84.55 dBu |
| cue/RTA node | PASS | worst level −0.072 dB, octave ≥ 40.74 dB, cold ≤ −162.3 dBFS |
| MIC 1–4, 13–16 | not run | J15–J22 have no rails on this unit (S55-1) |

In full mode MIC 5 is FLAG on A1: the 0→1 thump pumps 229 ms, with the repeat still open at the capture end (S63-3). T6 is NO DATA everywhere: no DSP strip-mute measurement exists, because S54's T6 was the phantom shunt.

## Projected time

From `plan.out`, using `step-costs.csv`. The input battery costs are measured; output-path step counts are a model, not a measurement.

| | per input path | per output path | unit, manual loop | unit, harness |
|---|---:|---:|---:|---:|
| factory | 51.5 s desk analysis / 63.6 s CM4 (26.5 s S61 battery + 25 s T7 by meter) | 19.6 s | 24.2 min instrument (29.6 CM4); with 35 cable moves at 30 s, 41.7 min | 7.8 min (chirps 5.1 + tone/noise 2.3 + analysis 0.4) + 10.0 min T7 = **17.8 min** |
| full | 758 s (A1 spans alone 8.6 min) | 23.6 s | 5.1 h instrument, 5.4 h with moves | 4.7 h (A1 3.4 h of it) |

On the harness, T7 is now the largest factory item: 24 sources × 23 neighbours × 1.09 s by meter. Reading only the same-converter neighbours (7) would bring it to about 3.0 min and the unit to about 10.9 min. That is arithmetic, not measured. A multi-lane capture arm is the other lever (S61-3). The spec's "≈ 2 min on the harness" is not reachable while arm/fill is per strip.

## Running it

```
tools/accept/dryrun_d24.sh                                   # the whole desk dry run
python3 tools/accept/gen_accept_fixtures.py --product d24    # fixtures + manifest only
python3 tools/pi/dsp4_accept.py run --fixture MW/D24/DSP/accept/fixtures/d24-in-mic05.json \
        --mode factory --unit MW-D24-2 --source replay:MW/D24/DSP/s66/replay/d24-in-mic05.json --out DIR
python3 tools/pi/dsp4_accept.py report DIR --md report.md
python3 tools/pi/dsp4_accept.py plan --manifest MW/D24/DSP/accept/manifest.json --mode factory
```

Regenerate the fixtures after any defs bump; `manifest.json` records the defs commit, the contract and the sha256 of every input table.

## T3L — the cable-loop THD row, and the measured references behind it (S89e, 2026-09-22)

Added because the signed shipping configuration passed every other bar in this
document and shipped with 57 % THD at the XLR (S88-1). The defect lived between
the chip-2 output slot and the wire — the gather overwriting a transmit row the
DMA had not finished reading — and not one of goldens, `dsp_validate`, the dry
run, conformance, `famverify` or the driven capacity row looks there. They are
all digital or host-side. **T3L is the row that listens.**

| piece | file |
|---|---|
| the leg, with a verdict and an exit code | `tools/pi/dsp4_loop_thd.sh` |
| the build + stage half | `MW/D32/DSP/SHARC/loopthd.sh` |
| the boot gate it runs behind | `tools/pi/dsp4_boot_linked.sh` + `tools/pi/s89_signbit.py` |

**The measured references, on MW-D24-2, 2026-09-22, loop cable Monitor L →
MIC 6, 595 preamp chain at gain code 0, oscillator into strip 20, read at
strip 6 post-fader.** Every arm is a `DSP4_TEST_NODES=1` build of this tree
with the four signed switches on, booted through the S89-1 link gate.

| what | drive −12.0 dBFS | drive −22.0 dBFS |
|---|---|---|
| return level, every arm | −22.21…−22.25 dBFS | −31.44…−31.49 dBFS |
| clean (six independent arms) | **0.3212…0.3217 %** | 0.0187…0.0386 % |
| folded (`DSP4_TX_DEFER=0`, the shipping build before this fix) | **57.33…57.43 %** | 57.30…57.43 % |

0.32 % is **the analog loop's own floor**, not a DSP number: six arms built
from different switch positions read it to four significant figures, and S89's
all-off control read 0.360 % on the same cable. The separation from the defect
is 45 dB with nothing in between, which is what makes a single limit safe.
`t3l_loop_thd_max_pct = 1.0 %` sits in that gap. It is **not a product audio
specification** and must not be quoted as one — it is the did-anything-listen
gate.

Two traps this row has already fallen into once each, both now enforced by the
leg itself:

- **A pinned lane reads a plausible THD.** With the 595 chain left wherever
  `matrix-app` put it, the loop returned −0.7 dBFS at *every* drive from −12 to
  −42 dBFS — a 30 dB change in stimulus moving the reading 0.9 dB — and a
  *clean* build then read 39 % THD. The return-level window
  (`t3l_loop_level_min/max_dbfs`) makes that INCONCLUSIVE instead of a fail.
  Set the chain to the reference gain before measuring.
- **A folded inter-chip link looks exactly like a folded DAC** (~56 % THD, right
  level). The leg boots only through `dsp4_boot_linked.sh`, whose exit code is
  the gate, so the two cannot be confused.

**The row proves the CONFIGURATION, not the byte-identical shipping image.**
`TEST_OSC`/`TEST_MEAS` are the instrument and `shipping.config` carries
`DSP4_TEST_NODES=0`; a shipping image has no oscillator with which to drive its
own output. `loopthd.sh` therefore builds the configuration under proof with
`DSP4_TEST_NODES=1` and nothing else moved, and prints the arm's md5. A report
must say which image was measured.
