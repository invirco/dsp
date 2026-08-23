# Harness family results — D32 fixed-point kernels on hardware

provenance: AI-drafted 2026-08-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

One table for the D5 acceptance run: every kernel family measured on the
bench against `tools/dsp/fixed_ref.py`, which is normative. Bench is the
rev-C CM4 (`app@192.168.1.219`), `DSP4_STRIPS=1`, matrix-app stopped.

Stimulus and capture are both inside the DSP (`SHARC/src/scope.asm`). The
Pi audio path is NOT a measurement channel: measured 2026-08-23, a counter
played through it returns with ~8x gain and reordered by up to ~190
samples.

| family | verdict | worst error | vectors | report |
|---|---|---|---|---|
| GAIN | **PASS** | 0 LSB | 13 levels, −60…+18 dB | [gain](gain-2026-08-23.md) |
| EQ / FILT | **PASS** | 0 LSB | 13 coeff sets + 400-sample RBJ | [eq-filt](eq-filt-2026-08-23.md) |
| COMP | **PASS** | 0 LSB | 7 levels, −30…0 dBFS | [comp](comp-2026-08-23.md) |
| FDR gain/pan | **PASS** | 0 LSB | 9 points, level+pan | [fdr-bus](fdr-bus-2026-08-23.md) |
| FDR ramp time | **FAIL** | 32× slow | GainFast, GainSafe | [fdr-bus](fdr-bus-2026-08-23.md) |
| GATE | **PASS** | 0 LSB | 7 levels, −60…−6 dBFS | [gate](gate-2026-08-23.md) |
| LIM | **PASS** | 0 LSB | 6 levels, −6…+6 dBFS | [lim](lim-2026-08-23.md) |
| DLY | **PASS** | 0 LSB | 5 offsets, 0…200 samples | [dly-tube](dly-tube-2026-08-23.md) |
| TUBE | **PASS** | 0 LSB | 20 points, sat 0…1 | [dly-tube](dly-tube-2026-08-23.md) |
| bus summing | **PARTIAL** | 0 LSB single-term | multi-term not exercised | [fdr-bus](fdr-bus-2026-08-23.md) |
| MTR nodes | **FAIL** | meaningless | peak 3.85e−34 vs 0.5 | [mtr](mtr-2026-08-23.md) |
| meter lib (`_meter_peaks`) | **PASS** | exact | 2 levels | [mtr](mtr-2026-08-23.md) |

Errors are worst absolute difference in Q4.28 LSB against `fixed_ref` with
the DSP's own float32 parameter conversions modelled. Where a family also
has a dB or timing spec, the report carries it.

**Re-verified on the current image, 2026-08-23** (`dffca40`, after the
biquad and compressor fixes and the SPI poll change): EQ 9 vectors, COMP 7
levels and GATE 7 levels all re-run at **0 LSB**. The earlier families were
measured on builds predating the poll change, so this confirms the results
hold on the build that carries all the fixes rather than on the builds they
were found with.

## Defects this run has found

| defect | family | fix |
|---|---|---|
| every biquad ran with `b1 = 0` — `r1` and `f1` are the same SHARC register | EQ / FILT | `a42a315` |
| `parallel = 1.0` overflowed Q0.31 to −1, bypassing the compressor | COMP | `2ef49fd` |
| ramp engine wrote one word low — `dm(i4, N)` is post-modify | GAIN | `d2e4dc6`, moved into the generator in `2ef49fd` |
| fader gain applied TWICE on the L/R bus feed — bus low by the fader setting in dB at any position below unity | FDR | `45fdd47` |
| ramp times 32× longer than the cell table on every block-decrementing parameter | FDR | **proposed, not applied** |
| MTR nodes read a Q4.28 integer as IEEE-754 — no fixed→float conversion; RMS never updates; decay 32× fast; `_mtr_gr` never written | MTR | **design call, not applied** |
| `Scope()` used chip 1's RDY for both chips, and chip 2 was silently running chip 1's firmware — a chip-2 chain read as dead | LIM (bench, not a kernel defect) | `dffca40` |
| per-sample SPI poll starved chip 2's block loop — `BOOT_STAGE` stuck at 0 after config | LIM (bench, not a kernel defect) | `dffca40` |

## Open against D5, not silently accepted

- **Biquad coefficient conversion is float32.** `_bq_fx_convert_N` cannot
  represent Q4.28 exactly, so coefficients land 1–3 LSB from
  `fixed_ref.biquad_coeffs_q` (up to 22 LSB in the response). Preferred fix
  is the SHARC's 40-bit extended float, which is exact for Q4.28 and leaves
  the wire contract alone.
- **`_comp_parallel` defaults to 0.0, and at 0.0 the node emits dry.** A
  compressor with sensible threshold and ratio does nothing until the host
  writes `parallel`, while `CompOn` reads 1. Same semantic in D24's float
  node.

## Traps worth carrying forward

- A fixed-point one-pole does **not** settle to its target: it sticks
  short once the increment rounds to zero. This bit twice — a 183 LSB
  "hardware error" on COMP and a 1 LSB one on GATE, both entirely the
  model. Related: model the state the part is actually IN, not the declared
  initialiser. GATE's gain initialises to 1.0 but is sitting near `range`
  by the time any measurement runs, because the input has been silent.
- `attack`/`release` on COMP are per-sample **alpha coefficients**, not
  seconds. `0.001` is a ~21 ms time constant.
- Reset the **whole chain** before measuring. An EQ measured wrong for an
  hour because FILT still held the previous sweep's `lpf b0 = 0.1`.
- Never hand-edit generated node ASM. Regenerating silently reverted a real
  fix that had been applied that way.
