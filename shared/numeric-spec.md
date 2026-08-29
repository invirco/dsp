# DSP4 numeric specification (decision D5)

Status: draft-normative, 2026-07-31; core families VALIDATED by
tools/dsp/golden_harness.py — 16/16 as of 2026-08-29, when the
wide-accumulator and blend boundary families were added (the long-stale
"9/9" was review finding D36). Governs the fixed-point audio
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

## Wide-accumulator bounds (PW ruling: saturate, never wrap)

Every 32-bit touchpoint saturates (above). The 64-bit and 80-bit
accumulators need the same guarantee, and for those it is a BOUND that
has to be stated, not a saturate instruction: a value that wraps in a
wide accumulator re-enters range and reads back as a clean wrong sample.

### Bus accumulators (review finding D1 — the review's one SEVERE)

Bus summing is exact and order-independent, with ONE round/saturate at
readout (above). The accumulator lives in MEMORY between contributions,
and what is stored is **the whole 80-bit SHARC multiplier result,
MR2F:MR1F:MR0F — three words, [lo, hi, ex]** (`lib/mac64_fx.asm`,
`bus_accumulators.asm`). Q8.56 in 80 bits: range ±2^23 = ±8388608.0
linear.

**NORMATIVE BOUND: |Σ x·g| ≤ 4096 = 2^12, eleven bits (2048×) below the
store.** A bus takes at most ~64 contributions; a strip exit saturates at
±7.999 and one crosspoint coefficient is Q4.28 up to 7.999, so a single
contribution reaches 64.0. Wrap is not unlikely, it is unreachable from
representable inputs. `fixed_ref.mix_sum` saturates at the same
boundary rather than being unbounded — that is the PW saturate-never-
wrap ruling applied to a 64-bit-and-wider touchpoint, and the margin is
what makes it a formality rather than a limit.

It was TWO words until 2026-08-29. MR2F was discarded on store and
rebuilt from the sign of `hi` on load, capping the stored value at
64-bit Q8.56 = ±128.0 with nothing saturating it — and the readout's
saturation check then ran on a value that had ALREADY wrapped, so a
wrapped sum came out as a clean, full-scale, WRONG-SIGN sample rather
than as a clip. Reachable: three contributions at 64.0 cross it, 32
coherent channels at full scale exceed it by 16×. The model could not
see it (unbounded ints), and no golden vector went near it.

**Why three words and not a saturating 64-bit accumulate.** Saturating
at ±128.0 clips a PARTIAL SUM: a bus whose contributions cancel (+100
and −100) has a legitimate small answer, and a saturating accumulate
returns the wrong one, order-dependently. Exactness and
order-independence are what the wide accumulator is for. Measured cost
on the part: **+2.003 cycles/MAC** per-sample and **+2.005** in the
block kernel, against ~5–6 for a saturating accumulate.

### Dual-instance crossfade blend (review finding D3)

`out = old + rns(a31·(new − old), 31)`, with `a31 = fix(alpha·2^31)` in
**float32** (the parameter plane is float32 by ruling, so alpha and the
multiply are both float32; modelling it in float64 was measured to
disagree with the part by 15 LSB). Model: `fixed_ref.xfade_blend`.

**The difference is EXACT and is never formed in a 32-bit register.**
`new` and `old` are independently saturated Q4.28 outputs, so
`new − old` spans ±(2^32−1); the kernel forms `a31·new − a31·old` as two
MACs into the 80-bit MRF. Same instruction count as the 32-bit subtract
it replaces, and identical arithmetic everywhere that subtract did not
wrap.

**The final add cannot overflow, and this is a bound, not an
assumption:** |a31| ≤ 2^31−1 and |new−old| ≤ 2^32−1, so
`rns(a31·(new−old), 31) ≤ 2^32−2`, and `old ≥ −2^31`, giving
`out ≤ 2^31−2 < I32_MAX`. Symmetrically at the lower end. No saturation
is applied to it and none is needed. Equivalently: the result is a
convex combination of two int32s and lies within the interval they span,
bar one LSB of rounding — which the golden harness asserts.

**DOMAIN: alpha ∈ [0, 1).** The kernel's ramp guarantees it — the new
alpha is stored only when still below 1.0, otherwise the crossfade ENDS
and alpha is zeroed — so the largest alpha ever blended is one step
short of unity. `alpha == 1.0` makes the float32 product exactly 2^31,
which is not a 32-bit integer; `fix` was measured on the part to return
0xFFFFFFFF for it, not a saturated 0x7FFFFFFF. That corner is
unreachable and deliberately unmodelled. **Any change to the alpha ramp
must preserve alpha < 1.0.**

### Biquad error feedback (review finding D2)

`fixed_ref.biquad` keeps the stage remainder `efb = acc − (y<<28)` in
the Q8.56 domain, and the SHARC kernel stores it as a 64-bit pair —
range ±2^63, MR2F discarded (`lib/biquad_fx.asm`).

**Where it is provably safe.** When the stage output does not saturate,
`y = rns(acc,28)` exactly, so `efb` is the rounding remainder and
`|efb| ≤ 2^27` by construction — 36 bits below the store boundary. The
efb can only grow through the SATURATION branch, where `y` is clamped
and the difference is no longer a remainder.

**The pessimistic bound does not close.** Treating the four state words
as independent at ±8.0 and choosing adversarial signs,
`|acc| ≤ 8 · S · 2^56` where
`S = 4|b0| + |n1| + |n2| + |c1| + |c2| + 3`. Over the product's own
design space (RBJ peaking / shelves / HPF / LPF; f0 20 Hz–20 kHz, gain
±15 dB, Q 0.1–10, quantised through `biquad_coeffs_q`) the worst S is
**38.56**, giving `|acc| ≤ 2^64.27` — ABOVE the 2^63 store. A
conversion-time clamp on Σ|coeff| would have to demand S ≤ 16, which
rejects settings the product's own DEFS ranges allow, so that option is
closed.

**The reachable bound, measured.** Driving the worst design-space
coefficient sets with full-scale adversarial input (random ±full scale,
square at f0, DC; 200 k samples per set; greedy per-sample adversary as
a cross-check) the largest `|efb|` observed anywhere is **2^62.606**, at
f0 = 14.16 kHz, +15 dB, Q = 0.1. The state words are not independent —
y1/y2 are this filter's own past outputs — and that is what keeps the
reachable value inside the store.

**NORMATIVE BOUND: `|efb| < 2^63` holds for every input within the
design space, with 0.394 bits of margin (1.314×).**

That margin is thin and it is recorded as thin. It is only consumed
under SUSTAINED output saturation with an extreme EQ setting, and the
consequence of exceeding it is not a rounding error: a wrapped efb of
order 2^63 re-enters the next accumulation as ~2^35 in Q4.28, which
saturates the stage output until the state washes out.

**Option, NOT taken here, for PW:** saturate the efb store-back at
±(2^63−1). It is bit-identical to today's arithmetic everywhere in the
reachable domain (the clamp never fires below 2^62.61), it executes the
saturate-never-wrap ruling on this touchpoint, and it costs ~3
instructions per stage per sample on the hottest kernel in the strip.
Because it touches ruled per-sample arithmetic it needs sign-off, and
the biquad inner loop is being reworked anyway (review finding D21) —
folding it in there is cheaper than adding it now.

**Adjacent, recorded here because the same corner produced it:** at
+15 dB with Q ≤ 0.12 the peaking design gives `n1 = b1 + 2·b0` up to
8.318, which does not fit Q4.28 and SATURATES at conversion — the
filter silently becomes a different filter. 1323 of 909 315 swept
design-space sets are affected, all of them in that corner. Coverage
for `_bq_fx_convert_N` is review finding D27.

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
  unchanged; host and mx26 untouched).
- REVISED 2026-07-31 (during kernel conversion): the ENTIRE parameter
  plane — dispatch tables, ramp engine, target/step/current scalars —
  stays FLOAT and byte-identical to the archived float firmware. Each
  fixed kernel converts its current control value(s) to fixed ONCE PER
  BLOCK (a FIX at sample_idx==0; block-rate float math is control
  plane, allowed). This avoids per-cell-kind conversion in the generic
  ramp path, keeps ramp precision, and matches how the golden harness
  quantizes control values. Coefficient-set staging (biquads) converts
  at crossfade-swap time instead, as already implemented.

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

### Boundary vectors, and where the bit-exact half is checked

The tolerance half is `golden_harness.py`. The BIT-EXACT half, for the
two wide touchpoints above, is `MW/D32/DSP/SHARC/numverify.sh`: it
builds `DSP4_NUM_SELFTEST=1`, which runs the REAL `_acc64_mac` /
`_acc64_rns28` and a blend probe emitted from the same generator
expression as every EQ/FILT/CROSSOVER node, over the vectors in
`tools/dsp/boundary_vectors.py` — the same vectors the harness uses —
and compares the part's results against `fixed_ref`.

Result 2026-08-29, on the part at 491.52 MHz: **57 of 57 bit-exact**,
in both a per-sample and a block-kernel build. Negative control
(`DSP4_NUM_NEGCTL=1`, the pre-fix arithmetic): **31 of 31 boundary
vectors detected, 26 of 26 non-boundary vectors untouched.**
