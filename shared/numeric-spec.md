# DSP4 numeric specification (decision D5)

> ## 2026-09-03 — THE SHARC AUDIO PATH IS 40-BIT FLOAT (PW ruling)
>
> **The biquad cascades and GAIN's audio word ship as 40-bit float on
> SHARC.** `DSP4_BQ_FLOAT` and `DSP4_GAIN_FLOAT` default ON; the whole
> of D5's fixed path below — offset-form Q4.28 direct-form I, round once
> per cascade, first-order error feedback, the ‖h‖₁ headroom guard —
> **stays in the tree behind `DSP4_BQ_FLOAT=0` and remains normative for
> the FPGA engine** (`fpga/`), which is fixed-point and always was. It is
> a reference model, not dead code: the fixed build must keep rebuilding
> its recorded W0 witnesses byte for byte, and that bar is what proves it
> intact.
>
> What is unchanged, and it is most of this document: **the sample format
> is still Q4.28**. The float is INSIDE a cascade, not on the bus. Every
> word crossing between nodes, every bus accumulator, every TDM slot,
> every meter and every dynamics envelope is exactly what it was.
>
> The four sections this ruling actually moves are marked **[FLOAT]**
> below: *Coefficient formats*, *Accumulators and rounding*, *Scope
> exceptions*, and *Acceptance tolerances*. Read them with §"The float
> cascade" at the end, which states the whole of it in one place.

Status: draft-normative, 2026-07-31; core families VALIDATED by
tools/dsp/golden_harness.py — **59/59 as of 2026-08-30**, when the NODE
families were added (COMP's wet path, the GATE ladder, FADER_PAN, TUBE,
the TDM boundaries, `_bq_fx_convert_N` and the meter: review findings
D26-D34). It was 16/16 on 2026-08-29, when the wide-accumulator and
blend boundary families were added, and the long-stale "9/9" before that
was review finding D36. Governs the fixed-point audio
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

## Accumulators and rounding **[FLOAT]**

- **The SHARC biquad cascades do not use a wide accumulator any more.**
  Under `DSP4_BQ_FLOAT` a stage is five float multiplies and four float
  adds in the register file, each rounded ONCE at the float boundary;
  there is no 64-bit extract, no per-stage saturate and no error-feedback
  word, because in float the rounding IS the format and there is no
  remainder to carry. The rest of this section — bus summing, MACs, the
  meter — is unchanged and still wide and exact.

- Biquads (FIXED arm), mix summing, MACs: accumulate in **≥64 bits**
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
reachable value inside the store. (Those two paragraphs quote the
2026-08-29 pre-ruling sweep: worst S 38.56, |efb| 2^62.606. Both moved
when n1 stopped saturating — see the normative bound below.)

**NORMATIVE BOUND: `|efb| < 2^63` holds for every input within the
design space.** Re-measured 2026-08-29 after the halved-n1 encoding
landed: **2^61.648, 1.352 bits of margin (2.553×)**, at f0 = 12.62 kHz,
+15 dB, Q = 0.1 under DC drive. The pre-ruling figure was 2^62.606 and
0.394 bits, and the improvement is a consequence of the encoding rather
than of anything aimed at this bound: that worst set is one of the 1 323
whose n1 used to saturate, so what the bound was measuring there was a
different — and more extreme — filter than the one the settings ask
for. The pessimistic bound still does not close (worst S = 41.743,
`|acc| ≤ 2^64.383`), for the reasons below.

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
for `_bq_fx_convert_N` is review finding D27. **That saturation is
fixed by the halved-n1 encoding below.**

### Minimum filter Q, and the halved n1 (PW ruling 2026-08-29)

**MINIMUM Q = 0.10, NORMATIVE.** It matches the wide-gentle extreme of
the console field rather than the mainstream 0.3 floor, and the corner
it admits is in spec. `fixed_ref.check_q` and `dsp_simulate.check_q`
REJECT a lower Q — they do not clamp it, because a silently clamped Q
is the same class of defect as the silently saturated n1 it was ruled
alongside. The product-side design code that turns (f0, Q, gain) into
the RBJ set the DSP receives lives outside this repo and needs the same
floor.

**n1 IS STORED HALVED, IN Q5.27, AND THE KERNEL ACCUMULATES ITS PRODUCT
TWICE.** Of the five offset coefficients n1 is the only one whose
design-space range escapes Q4.28. Over the full swept space that
`bound_efb.design_space` enumerates — peaking, both shelves and HP/LP,
869 627 quantised sets — **1 323 reach |n1| ≥ 8** and saturated Q4.28.
Q5.27 puts the ceiling at 16.0 and clears **1 313 of those 1 323**. The
two MACs go into the exact 80-bit MRF, so `nh·x1 + nh·x1` is `n1·x1`
with no intermediate rounding.

**TEN SETS STILL SATURATE, and that is a finding, not a rounding.** The
largest |n1| in the space is **17.835**, and it is not the peaking
corner the ruling was written for: it is a LOW SHELF at f0 = 18.9–20 kHz,
+14…15 dB, shelf-Q 2.8–3.5 — ten sets, all of them a low shelf placed
at the top of the audio band. Q5.27 does not reach them and neither
would the six-word split option below, whose ceiling is also 16. Closing
them is a RANGE decision for PW, not an encoding one: either the DEFS
bound low-shelf f0 (a low shelf at Nyquist is not a control anyone
means to offer) or the stored n1 needs a third bit and a third MAC.
Until then, conversion of those ten sets silently produces a different
filter, exactly as the 1 323 did.

**UNIFORM AND UNCONDITIONAL.** Every cascade form pays the extra MAC on
every stage of every sample whatever the loaded coefficients are — the
instruction stream must not vary with settings, or a measured ceiling
becomes a function of what happened to be loaded when it was measured.
Cost ≈ +6 cycles/sample on a scalar strip, ≈ +3 per channel paired.

**WHAT IT COSTS IN ACCURACY, MEASURED.** One bit of n1 resolution: the
grid goes from 2^−28 to 2^−27. On golden_harness's biquad sweep the
worst magnitude error against float64 moves **0.046151 dB → 0.060560
dB**, both at f0 = 20 Hz / −12 dB / Q = 4, and is **unchanged at
0.003479 dB for f0 ≥ 50 Hz** — the cost lands only at LF, which is
exactly where the offset form's benefit lives. Still 6.6× better than
the shipping FP32 firmware's 0.4 dB on the same case. The harness bar
moved 0.05 → 0.07 dB to match, and the 0.046 dB figure quoted under
*Coefficient formats* below is the PRE-RULING number.

**OPTION NOT TAKEN, costed for PW.** A six-word coefficient block that
splits n1 into two Q4.28 halves summing EXACTLY to `round(n1·2^28)`
would give the same doubled range at the same +1 MAC, with NO
resolution loss — the arithmetic would stay bit-identical to the
pre-ruling kernel for every setting where n1 already fitted, and only
the 22 saturating sets would change. It costs one DM word per stage
(EQ: 4 stages × 3 buffers × 32 nodes = 384 words per chip, against
177 KB free) and it changes the internal coefficient-block stride from
5 to 6, which is wired into the generator, all four cascade forms,
`_bq_fx_convert_N` and both self-test tables. It is a strictly better
trade on the numbers above; it is not taken here because the ruling
names the halved form.

## Coefficient formats **[FLOAT]**

- **SHARC, since 2026-09-03 — the biquad wire is FIVE float32 words a
  stage in D5's OWN OFFSET ENCODING**, and that encoding is the reason
  float is accurate enough to ship:

      b0,   n1 = b1 + 2·b0,   n2 = b2 − b0,   c1 = 2 + a1,   c2 = 1 − a2

  a0 normalised to 1. `_bq_fx_convert_N` becomes a COPY — the wire word
  IS the stored word — and the kernel reconstructs the direct
  coefficients in REGISTERS once per stage per block, five arithmetic
  instructions and two constant reads.

  **Why the offset form survives the move to float, when its original
  reason (headroom) does not.** Carried directly, a1 = −1.9948 for a
  20 Hz biquad, where one float32 ulp is 2.4e−7 against Q4.28's 3.7e−9:
  **six bits worse on the number that places the pole**, because
  fixed-point precision is ABSOLUTE and float's is RELATIVE, and pole
  placement error is an absolute error. 2 + a1 = 0.0052 puts them back.
  Measured worst response error over the DEFS set:

  | coefficient wire | worst error |
  |---|---|
  | float32 DIRECT (what the arm carried before this landing) | 0.3715 dB |
  | Q4.28 offset — the fixed contract | 0.0265 dB |
  | **float32 OFFSET — the shipping wire** | **0.0080 dB** |
  | golden bar | 0.046 dB |

  The reconstruction ROUNDS ONCE, at the register file's 32 significand
  bits: `c1 − 2.0` is exact only while c1's lowest set bit is at or above
  2⁻³¹. That rounding is the difference between the **0.0042 dB this was
  modelled at** and the **0.0080 dB it is built at** — the model had
  reconstructed in longdouble and so credited the wire with precision the
  part has not got. Running the offset form THROUGH the recursion instead
  (w1′ = 2·w1 + w2 + n1·x − c1·y, w2′ = n2·x − w1 + c2·y) would avoid the
  rounding entirely at seven ALU ops against four pairable multiplies —
  one more instruction per sample per stage, ~3% of chip 2, for ~0.003 dB.
  **Priced and not taken.**

  **The identity filter is not b0 = 1 and four zeros.** Under this
  encoding bypass is (1.0, 2.0, −1.0, 2.0, 1.0); five zeros after b0
  reconstruct to a1 = −2, a2 = 1 — a double pole at z = 1, an integrator
  squared, not silence. Every bypass initialiser and every host-wire
  staging buffer in the generated tree carries the offset words under
  `DSP4_BQ_FLOAT` (`dsp_codegen.py::_BQ_FLOAT_BYPASS_STAGE`).

- **The FIXED wire is unchanged and is still direct-form RBJ float32**
  under `DSP4_BQ_FLOAT=0`, because that arm converts and this one copies.
  The wire format is therefore a property of the arm, not a constant, and
  the two must not be mixed.

- Biquad topology, FIXED ARM (NORMATIVE for `DSP4_BQ_FLOAT=0` and for the
  FPGA engine): **offset-coefficient direct-form I with
  first-order error feedback** (fixed_ref.biquad). Stored coefficients:
  b0, n2 = b2−b0, c1 = 2+a1, c2 = 1−a2 in **Q4.28**, and **n1 = b1+2·b0
  stored HALVED in Q5.27**, its product accumulated twice (see *Minimum
  filter Q, and the halved n1* above).
  Rationale (measured): plain DF1 with 32-bit coefficients fails at LF
  (12.8 dB response error at 20 Hz; today's FP32 firmware shows 0.4 dB
  on the same case); the offset form passes 0.046 dB worst-case, ~9×
  better than the shipping FP32, and the error feedback puts the LF
  rounding-noise floor below −130 dBFS.
- Linear gains (faders, sends, pan legs): **Q4.28**
  (up to +24 dB as a single coefficient; larger boosts compose).
  DCA products were on this list until 2026-08-30; the CM4 control
  daemon now folds DCA into the fader TARGET it already sends, so no
  DCA product is formed on the DSP at all.
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
  unchanged; host and mx26 untouched). **The biquad coefficient words'
  MEANING changed on 2026-09-03** — five float32 words a stage, D5's
  offset encoding, under `DSP4_BQ_FLOAT`; direct-form RBJ under
  `DSP4_BQ_FLOAT=0`. Same protocol, same word count, same addresses, same
  type; a different encoding, per arm. See *Coefficient formats*.
- REVISED 2026-07-31 (during kernel conversion): the ENTIRE parameter
  plane — dispatch tables, ramp engine, target/step/current scalars —
  stays FLOAT and byte-identical to the archived float firmware. Each
  fixed kernel converts its current control value(s) to fixed ONCE PER
  BLOCK (a FIX at sample_idx==0; block-rate float math is control
  plane, allowed). This avoids per-cell-kind conversion in the generic
  ramp path, keeps ramp precision, and matches how the golden harness
  quantizes control values. Coefficient-set staging (biquads) converts
  at crossfade-swap time instead, as already implemented.

## The `fix` domain at the parameter boundary (2026-08-30)

`Rn = FIX Fx` is the one instruction every block-rate conversion above
ends with, and **it neither saturates nor two's-complement wraps on this
part.** At exactly 2^31 it was measured to return `0xFFFFFFFF`, i.e. -1
— twice, independently: the compressor's parallel blend at 100 %
(2026-08-23, which is why that conversion carries an explicit negative
clamp afterwards) and the crossfade alpha at 1.0 (2026-08-29, which is
why the alpha ramp is specified to stop one step short of unity).

**One measured point is not a model of the overflow behaviour**, so
`fixed_ref.fix32` REFUSES anything outside ±(2^31 - 1) rather than
inventing the rest of it (the no-fallback policy). That makes the
in-range domain a REQUIREMENT ON THE KERNEL: every host parameter that
reaches a `fix` must be clamped into range first.

Two families do clamp — `ChanCompPar` (review finding D40, percent, with
the 100 % repair) and `ChanGateRng` (D39, dB, clamped to 0..60). Four
cells reach a `fix` with nothing between: `ChanLevel`, `ChanPan`
(finding D64) and `ChanTubeSat`, `ChanCompMake` (finding D65, where the
masters' own scale law puts the documented maximum far outside the
domain and the wire contract records the unit as UNDECLARED).

## Node arithmetic (the golden-coverage batch, 2026-08-30)

Everything above this point specifies PRIMITIVES. These are the
compositions — the arithmetic between the primitives, which is where the
last three shipped audio defects lived (the squared pan gain, the
percent parallel blend, the dry-by-default compressor) and which had no
reference of any kind until review findings D26-D34 were closed.

- **COMPRESSOR wet path.** `wet = rns28(rns28(dry*gain) * makeup)` —
  **two roundings**, because both operands are Q4.28 and the triple
  product does not fit one accumulator. Then
  `out = dry + rns31((wet - dry) * par)`, with the difference formed in
  a 32-bit register. That difference is BOUNDED rather than lucky: gain
  is in [0, 1] and makeup is non-negative, so wet and dry always carry
  the same sign and |wet - dry| ≤ 2^31. The bound depends on a
  non-negative makeup, which nothing enforces (finding D4).
- **GATE ladder.** Per sample: follower, threshold compare in the log2
  domain (`env == 0` counts as below), then either open (target = unity,
  hold counter reloaded) or below (counter decremented
  **unconditionally and never floored**; target drops to the range floor
  only once it reaches zero), then a one-pole smoother onto the target
  and one MAC. The follower and the smoother share the same attack and
  release alphas. `|x|` is the ALU's ABS with ALUSAT clear, so
  `|I32_MIN|` is `I32_MIN`.
- **FADER_PAN.** `gq = fix(level * 2^28)`, forced to zero by mute (the
  2026-08-25 crosspoint-coefficient fold); pan legs `1 - pan` and `pan`,
  a **LINEAR** law whose two legs sum to unity. The level is applied by
  the node's own MAC and the legs are ROUTING's crosspoint coefficients;
  folding the level into the legs as well is the 2026-08-23 defect, and
  it is exact at unity level, which is why it shipped.
  [REVIEW: the masters document a constant-power law. Linear is what is
  implemented and what this specifies; review finding D42 is PW's.]
- **TUBE_SAT**, plugin-class (PW ruling 2026-08-30):
  `y = rns28(x * (1 + rns28(sat * (1 - rns28(x*x)))))` — **three
  chained roundings**, each saturating, with the two ALU adds wrapping.
  A soft clip only for |x| ≤ 1; above that `1 - x²` turns the curve
  over, and Q4.28 reaches 8.0. The BASE strip's requirement is the
  bypass path, which is the identity and must cost nothing.
- **TDM boundaries.** In: arithmetic `>>3`, which **truncates toward
  -inf** — no rounding half, so up to one LSB of downward bias, accepted
  rather than paid for per input slot per sample. Out: `<<3` with a
  round-trip test, saturating to full scale **by the sign of the
  source**. That is the only clip in the graph where Q4.28's headroom is
  finally spent.

---

## The float cascade (PW ruling 2026-09-03) **[FLOAT]**

The whole of the SHARC float path, stated once. `DSP4_BQ_FLOAT` and
`DSP4_GAIN_FLOAT` default ON; `DSP4_BQ_FLOAT=0` restores every word of
the fixed reference model.

### The arithmetic

Direct form II TRANSPOSED, which is right for float the way the offset
DF-I form is right for Q4.28:

    y   = w1 + b0·x
    w1' = w2 + b1·x − a1·y
    w2' =      b2·x − a2·y

Five products, no 64-bit extract, no per-stage round, no per-stage
saturate, no error-feedback word.

### Where the bits are, and where they are not

**The state is 40-bit.** MODE1.RND32 (bit 16) is CLEARED, so the register
file carries 32 significand bits against IEEE single's 24, and the block
kernels hold w1/w2 in REGISTERS across all `DSP4_BLOCK_SIZE` samples of a
stage. It costs nothing — one `bit clr` against one `bit set` — and it is
worth 33–48 dB of noise floor over float32.

**Two places the signal leaves the register file, and both are 32-bit DM
words.** `_bq_fx_cascade_blk` runs stage-outer / sample-inner, so a stage
writes its whole block of y to the block buffer and the next stage reads
it back: **the forward path between stages is 32-bit float even in the
40-bit arm**, and so is the entry pass's `FLOAT Rx BY -28`, which
quantises a 32-significant-bit Q4.28 word to 24 bits on its way in. The
state crosses each BLOCK boundary the same way. What stays at 40 bits is
the RECURSION — w1/w2, and the full-precision y that feeds them, not the
truncated copy handed on — which is where a high-Q LF biquad's state
error lives, so the 40 bits keep what they were bought for. Measured on
the response table, the forward path's 32 bits are worth **nothing**
(0.0080 dB either way). All three crossings are in `bq_float_ref.py` and
all three are proved on the part by `bqeverify.sh float`.

**The per-sample kernel is different and cannot be made the same.**
`_bq_fx_cascade_N` holds the cascade value in a register across stages,
so the CROSSFADE path is not bit-identical to steady state under float.
Known, and it is a property of the loop shape, not a defect.

### Overflow: no guard, one clamp

`DSP4_BQ_GUARD` is FORCED off, not merely defaulted off. An 8-bit
exponent absorbs the ‖h‖₁ = 1285 (+62 dB) worst case in the DEFS set that
costs the fixed path eight mantissa bits — **proved, not asserted: the
4-band-all-+15 dB cascade peaks at 1285.0 against float32's 3.4e38, 2.6e35×
of headroom** (`bq_float_ref.py --overflow`). So there is no sizer, no
load-time impulse run, no header word, no entry scale, no exit rescale
and no per-stage saturate.

**What remains is ONE clamp, and it is an output clamp, not a sizing.**
The inter-node bus is still Q4.28, so the word a cascade hands on must
fit ±8 whatever the cascade did internally: one `CLIP Fx BY 7.99999952`
(0x40FFFFFF, the largest float32 below 8.0, so the following `FIX BY 28`
gives 0x7FFFFF80 and cannot wrap) per sample on the cascade output. The
guarded fixed arm clamps in the same place. **Clipping preserves sign;
the wrap the guard exists to prevent inverts it.**

### The C-wire, and what cross-node equivalence now means

**Nodes interchange FIXED PCM, not internal format.** Q4.28 on the
inter-node bus, on every bus accumulator, in every TDM slot and across
the inter-chip link — unchanged. What a node does INSIDE is its own
business, and after this ruling the SHARC does biquads in float while the
FPGA engine will do them in fixed from `fixed_ref.py`.

So **the equivalence between the two targets is at the fixed-PCM
interchange, not at bit-identity of the internal arithmetic**, and the
two-step equivalence stated under *Acceptance tolerances* now reads:
SHARC ≡ `bq_float_ref` (bit-exact, on the part), FPGA ≡ `fixed_ref`
(bit-exact), and both ≈ float64 within the tolerances. A sample handed
across the C-wire is the same format from either; the two will not
produce the same word from the same filter, and are not required to.

**No ASRC. That still holds** — one clock domain, one sample rate, no
rate conversion anywhere in the interchange — and it is what makes a
fixed-PCM interchange sufficient.

### GAIN

`_gsimd_gain_blk`'s AUDIO word is one FLOAT, one multiply, one CLIP and
one FIX in place of the 64-bit extract and the branch-free saturate:
eighteen instructions per two samples become eleven. The METER's wide MAC
and its exact 80-bit sum of squares stay fixed beside it (see *Scope
exceptions*). The meter's three ops are INTERLEAVED into the float chain,
because FLOAT→multiply→CLIP→FIX is a four-deep serial dependency: written
as four consecutive instructions the loop returned 1.49 of the 3.5
cycles/sample/strip its instruction count had deleted, and interleaved it
returns **2.76**. The scalar body, the `DSP4_GAIN_SIMD=0` body and the
`DSP4_MTR_OFF` body stay fixed and are the byte-for-byte controls they
always were.

The D20 mic-pre tap decision is unchanged: **the tap stays.** Its store is
the ROUTER's, not the meter's (pickoff 0, post-trim), and under float it
publishes the post-clip Q4.28 word exactly as before — the same word, in
the same place, in the same block. Float does not touch it, and the
GAIN→FILT coefficient fold that D20's −17 c/s/strip is blocked on is
still the thing that would.

### What it costs and what it buys, measured whole-graph

Block 16, both chips, two boots a point, minimum taken, witnesses clean.
The instrument reproduces itself to 0.007% on chip 2 and exactly on
chip 1.

| arm | chip 2 | % of 327,680 | chip 1 | % |
|---|---|---|---|---|
| contract, per-stage saturate | 306,939 † | 93.67% | 304,363 † | 92.88% |
| fixed round-once + guard | 264,683 | 80.77% | 292,863 | 89.38% |
| **float, offset wire + float GAIN** | **249,751** | **76.22%** | **290,193** | **88.56%** |

† carried from sessions 22–23, same scripts on the same bench.

Chip 2 frees **14,932 cycles/block, 4.56% of budget**, and 57,188 against
the contract (17.45%). Chip 1 frees 2,670, 0.81%. Chip 1's smaller win is
arithmetic, not disappointment: 256 biquad stages against chip 2's 632,
in a graph dominated by GAIN, its meter and the dynamics.

The offset reconstruction is the one thing float gives back: **3,217
cycles/block on chip 2, 0.98% of budget**, for the 46× accuracy it buys.

### Noise floor: the one place fixed is still better, and why

Arithmetic only, against each arm's own coefficients: **fixed is 8–22 dB
quieter than float at 40 bits** (−151.7 dBFS against −109.6 on the LF
shelf), because the fixed path carries the first-order ERROR FEEDBACK the
round-once ruling deliberately kept and float has no residual to carry.
Float at 40 bits is 33–48 dB quieter than float32, at zero cycle cost —
there is no reason to run this kernel at 32 bits. A 40-bit state that
never passed through a 32-bit DM word would be worth a further ~12 dB on
the LF shelf and nothing in the response table; in DM it would cost ~2.7%
of chip 2, in PM no cycles, and chip 1 has no PM to spare. Priced, not
built.

---

## Scope exceptions **[FLOAT]**

- **The SHARC biquad cascades and GAIN's audio word are 40-bit float**
  (PW ruling 2026-09-03) — see *The float cascade* below. They convert at
  the cascade boundary, `FLOAT Rx BY -28` in and `CLIP` then
  `FIX Fx BY 28` out, because the inter-node bus is still Q4.28.
- **GAIN's METER is NOT in that exception and stays fixed.** A meter
  wants the PRE-CLIP wide word and an exact sum of squares across the
  block: `mrb = x·g (ssi)` gives the full Q8.24 over-range a 32-bit store
  cannot hold, and MRF accumulates 80 bits with no rounding and no
  saturation, which is order-independent and is what makes the SIMD split
  exact. Float would make both approximate. So the wide MAC stays beside
  the float audio path, and the gain the audio applies is FLOATed from
  the same Q4.28 word the meter's MAC uses — polarity and mute already
  folded in — so the two cannot disagree about what gain was applied.
- FX engines (FX_ENGINE nodes) stay float32 (D5). Their inputs/outputs
  convert at the node boundary (Q4.28 ↔ float32, one instruction each
  way on SHARC).
- Meters store linear Q4.28 peaks; dB conversion remains host-side.

## Acceptance tolerances (golden harness) **[FLOAT]**

**Two models, two bit-exact bars, one tolerance bar.** `fixed_ref.py` is
normative for the fixed arm and for the FPGA engine; **`bq_float_ref.py`
is normative for the SHARC float cascade kernels**, and it is exact
rather than approximate — every 40-bit operation is computed in
`numpy.longdouble` (a 64-bit significand, which holds the product of two
32-bit significands) and rounded ONCE. Both are held to the part:
`bqeverify.sh` for the fixed arm and `bqeverify.sh float` for the float
arm, each 0 ULP over 192 loaded cascades × 3 drive levels × 4 blocks, at
block 8 and block 16. The tolerances below are then measured on the
models.

Per kernel family, reference model vs float64-reference on the
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

Two-step equivalence, per target and per arm:

- **SHARC float cascade** ≡ `bq_float_ref` (bit-exact, proved on the part
  by `bqeverify.sh float`), and `bq_float_ref` ≈ float64 within the
  tolerances above.
- **SHARC fixed arm and the FPGA RTL** ≡ `fixed_ref` (bit-exact), and
  `fixed_ref` ≈ float64 within the same tolerances.

The two targets meet at the FIXED-PCM INTERCHANGE and not at bit-identity
of the internal arithmetic — see *The float cascade → The C-wire*. They
will not produce the same word from the same filter, and are not required
to; both are held to the same response and noise-floor bars against
float64, which is what the tolerances are for.

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

For the NODE families the bit-exact half is
`MW/D32/DSP/SHARC/goldnode.sh`, and it works the other way round: rather
than emitting the vectors into the image, it DRIVES THE SHIPPING GRAPH,
captures a node's input and output over the same stimulus from the same
rested state, and requires `fixed_ref` to reproduce the captured output
word for word from the node's own converted parameters. The thing under
test is the shipping node body, not a probe copy of it — which is the
honest half of review finding D35, since `bq_selftest.asm` and
`dyn_selftest.asm` both compare assembly against assembly. Its negative
controls are the deliberately-wrong twins in `fixed_ref`
(`gate_step_nohold`, `comp_wet_1round`, `tube_2round`,
`fdr_pan_squared`), so it needs one image and one boot; a stimulus on
which a twin agrees is reported as unable to measure, never as a pass.
