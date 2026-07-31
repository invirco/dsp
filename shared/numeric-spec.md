# DSP4 numeric specification (decision D5)

Status: draft-normative, 2026-07-31; core families VALIDATED by
tools/dsp/golden_harness.py (9/9) on this date. Governs the fixed-point audio
path on BOTH targets: the SHARC DSP4 firmware (now) and the future
FPGA mixer engine (`fpga/`). Changes here are behavioural contract
changes — treat like the slot map (deliberate edits, noted in release
notes). Items marked [REVIEW] are judgment calls awaiting Peter's
sign-off; everything else follows from them.

## Sample format

- **Q4.28 in 32-bit words** (1 sign, 3 integer, 28 fraction bits).
- 0 dBFS (converter full scale) = ±1.0 → **+18.06 dB internal
  headroom** (max representable 8.0) before saturation. [REVIEW: if
  +24 dB headroom is wanted, the alternative is Q5.27 at the cost of
  one bit of noise floor; Q4.28/+18 dB is the working assumption.]
- TDM I/O: 32-bit slots, converters left-justified 24-bit. Scatter
  converts Q1.31→Q4.28 (arithmetic >>3); gather saturates Q4.28→Q1.31
  (<<3 with clip). SNR at the converter boundary is unchanged.

## Accumulators and rounding

- Biquads, mix summing, MACs: accumulate in **≥64 bits**
  (SHARC: 80-bit MRF; FPGA: 64-bit). Mix summing is therefore EXACT
  and order-independent — a deliberate improvement over FP32.
- Store-back to 32-bit state/output: **round-to-nearest** (convergent
  rounding where the hardware offers it: SHARC `SSFR`/MRF rounding),
  then **saturate**. Wrap-around is forbidden everywhere.

## Coefficient formats

- Biquad topology (NORMATIVE): **offset-coefficient direct-form I with
  first-order error feedback** (fixed_ref.biquad). Stored coefficients
  in **Q4.28**: b0, n1 = b1+2·b0, n2 = b2−b0, c1 = 2+a1, c2 = 1−a2.
  Rationale (measured): plain DF1 with 32-bit coefficients fails at LF
  (12.8 dB response error at 20 Hz; today's FP32 firmware shows 0.4 dB
  on the same case); the offset form passes 0.046 dB worst-case, ~9×
  better than the shipping FP32, and the error feedback puts the LF
  rounding-noise floor below −130 dBFS.
- Linear gains (faders, sends, pan legs, DCA products): **Q4.28**
  (up to +24 dB as a single coefficient; larger boosts compose).
- One-pole envelope/ramp alphas: **Q0.31** (unsigned range [0,1)).
- Delay crossfade / interpolation fractions: Q0.31.

## dB and dynamics math

- dB→linear and linear→dB via **log2/exp2 polynomial approximants**
  (normalize-then-poly): minimax degree-5 on the mantissa interval.
  Accuracy target: gain error **< 0.001 dB** across −60…+18 dB
  [REVIEW],
  verified by the golden harness — this bounds compressor/gate curve
  deviation from the float64 reference.
- Envelope followers: one-pole in Q4.28 state with Q0.31 alphas —
  same attack/release frame-count semantics as today (cell tables
  unchanged).

## Parameter boundary (contract preservation)

- The SPI wire continues to carry float32 words (spi_handler protocol
  unchanged; host and mx26 untouched). A single on-target conversion
  at the parameter-write/ramp boundary produces the fixed-point words
  above. The ramp engine ramps the CONVERTED fixed values.

## Scope exceptions

- FX engines (FX_ENGINE nodes) stay float32 (D5). Their inputs/outputs
  convert at the node boundary (Q4.28 ↔ float32, one instruction each
  way on SHARC).
- Meters store linear Q4.28 peaks; dB conversion remains host-side.

## Acceptance tolerances (golden harness)

Per kernel family, fixed-reference vs float64-reference on the
standard vector set:
- Biquad family: magnitude response within **±0.01 dB** for f0 ≥
  50 Hz and **±0.05 dB** including the 20 Hz extreme (both beat the
  FP32 baseline everywhere); residual vs float64 below **−120 dBFS**
  RMS.
- Gain/pan/summing: exact to LSB (summing) / ±0.5 LSB (gains).
- Dynamics: static curve within **±0.05 dB** [REVIEW]; envelope times
  within **±2%** of the float64 reference.
- End-to-end strip: null test vs float64 better than **−90 dBFS**
  RMS on program-like material. [REVIEW]

The SHARC asm and the FPGA RTL both implement the *fixed reference
model* (`tools/dsp/fixed_ref.py`) bit-exactly; the reference model is
what gets tolerance-tested against float64. Two-step equivalence:
target ≡ fixed_ref (bit-exact), fixed_ref ≈ float64 (tolerances).
