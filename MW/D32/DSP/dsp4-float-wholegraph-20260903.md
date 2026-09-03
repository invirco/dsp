provenance: AI-drafted 2026-09-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Float on SHARC, whole graph, both chips — the decision number, and a correction to the numeric one

*2026-09-03, session 24. Decision input for PW's fixed-vs-float mandate
call. Nothing here ships: the D5 contract is untouched, the
fixed/round-once/guard path is untouched, `DSP4_BQ_FLOAT` defaults 0, and
all three recorded W0 witnesses rebuild byte for byte.*

---

## 0. The two results, and the second one is the surprise

**FLOAT LANDS CHIP 2 AT 75.24% OF BUDGET AND CHIP 1 AT 88.76%,
GUARD-FREE** — against 93.67% / 92.88% for the contract and
80.78% / 89.38% for fixed round-once with the ‖h‖₁ guard, every
figure block 16, whole graph, two boots a point, minimum taken, witnesses
clean. The float arm needs no headroom sizer, no header word, no entry
scale, no exit rescale and no per-stage saturate, and the model proves it
cannot: the worst cascade in the DEFS space reaches **1,285** against
float32's ceiling of 3.4 × 10³⁸, which is **2.6 × 10³⁵ times of
headroom** where the fixed path needs eight mantissa bits.

**AND THE NUMERIC PRICE IS NOT WHAT RIG A2 MEASURED, BECAUSE IT IS NOT IN
THE ARITHMETIC.** Float's response error on the LF shelf D5 was decided
on is **0.3715 dB**, eight times the 0.046 dB golden bar — and **0.0042
dB, eleven times UNDER the bar, if the wire carries the same OFFSET
coefficient word D5 already defines** (n1, n2, c1 = 2 + a1, c2 = 1 − a2)
instead of the raw RBJ words. The 0.37 dB is the float32 **coefficient
word**, not the float arithmetic: a 20 Hz biquad has a₁ = −1.9948, where
a float32 ulp is 2.4 × 10⁻⁷ and a Q4.28 ulp is 3.7 × 10⁻⁹ — **64 times
finer, six bits, on the number that places the pole.** Fixed-point
precision is absolute, float's is relative, and pole placement error is
an absolute error. D5's offset encoding was adopted for headroom; in
float it buys accuracy, and it buys nearly three decimal orders of it.

**The 40 bits are free and they are worth 33–48 dB of noise floor.**
Chip 2 measures 246,534 cycles/block at 40 bits against 247,290 at 32 —
the 40-bit arm is if anything the cheaper of the two, and the difference
is inside the instrument's spread — while the residual arithmetic noise
floor goes from −74.1 dBFS to −107.1 on the LF shelf and from −66.3 to
−114.0 on the 28-band GEQ. There is no reason to run this kernel at 32
bits.

**Fixed still wins on noise floor, and the reason is one instruction.**
Even at 40 bits the float cascade's arithmetic noise is 8–22 dB above the
fixed path's, because the fixed path carries a first-order **error
feedback** — the exact rounding residual, pushed back into the next
sample's accumulator — and float has no residual to carry. That is the
same one instruction the round-once ruling deliberately kept.

---

## 1. What was built, and what "guard-free" means precisely

`DSP4_BQ_FLOAT` replaces all four cascade kernels in `lib/biquad_fx.asm`
with software float **direct form II transposed** — the shootout's RIG A2
arithmetic — and `_bq_fx_convert_N` with a copy. Every line of it is
inside the macro and every line of the fixed kernels is inside its
negation, which is what makes `DSP4_BQ_FLOAT=0` byte for byte what it
was. Normative model: `tools/dsp/bq_float_ref.py`, which stands to these
kernels as `fixed_ref.py` stands to the fixed ones.

    y   = w1 + b0*x
    w1' = w2 + b1*x - a1*y
    w2' =      b2*x - a2*y

Five products, no 64-bit extract, no per-stage round, no per-stage
saturate, no error-feedback word.

### The guard is FORCED off, not defaulted off

`DSP4_BQ_GUARD` is defined to 0 whenever `DSP4_BQ_FLOAT` is 1
(`dsp_block.h`), so `DSP4_BQ_HDR` goes with it and the coefficient blocks
lose their header word. The float image contains **no `_bq_hr_*` symbol
at all** — no load-time sizer, no impulse run, no per-node hand-off —
against twelve in the shipping default. That is the deletion the
measurement is about, and it is verifiable in the map file rather than
asserted.

### What float still needs is ONE clamp, and the distinction matters

**The inter-node bus is still Q4.28.** Whatever a cascade does
internally, the word it hands the next node must fit ±8, so the kernel
does one `Fn = CLIP Fx BY 7.99999952` on the cascade OUTPUT before
`Rn = FIX Fx BY 28`. One instruction per sample, on the output only, with
nothing sized and nothing scaled.

That is a different object from the guard. The guard exists because in
Q4.28 an over-range **intermediate** wraps, and a wrap fed back into the
poles is a sign inversion rather than a clipped sample; it prevents that
by scaling the whole recursion down by a per-cascade H computed at
parameter-load. Float has no over-range intermediate to prevent — the
exponent absorbs it — so the only thing left is the bus, and the bus
clips in both arms. On the 4-band-all-+15 dB cascade (‖h‖₁ = 1285) the
guarded fixed arm and the float arm both clip the output and neither
wraps; float gets there without sizing anything.

### The domain crossing is a cost of float-in-a-fixed-graph, not of float

`Fn = FLOAT Rx BY -28` in and `Rn = FIX Fx BY 28` out, as passes over the
block in the block kernels — the guard's reason for being a pass rather
than two in-loop instructions applies unchanged: a dedicated pass has the
whole register file, and in the per-sample kernel it is one instruction
each way with no pass at all. A graph that carried float on the bus would
not pay it. It is inside every number below.

### The state is 40-bit, and that is the reset default

MODE1.RND32 is **bit 16**, and this firmware has never written it: MODE1
sits at its reset value, so the part has been running 40-bit
extended-precision float everywhere it uses float at all. The float
kernels clear it explicitly anyway and `DSP4_BQ_FLOAT32=1` sets it, each
saving and restoring MODE1 whole around the cascade — the boundary mode
is global and the image is full of other float code (coefficient ramps,
the legacy meter, the crossfade control plane), so an arm that silently
re-rounded all of it would not be a measurement of the biquads.

The block kernels hold w1/w2 in **registers** across all sixteen samples
of a stage, which is where a high-Q low-frequency biquad's state error
accumulates. State crosses each BLOCK boundary through a 32-bit DM word
and loses its low eight mantissa bits there; §3 prices what a
PM-resident 48-bit state would buy instead of asserting it is nothing.

### Nothing generated changed size

The float coefficient block is five words a stage — the RBJ float words
the host already writes over SPI — so it fits the existing array exactly
once the guard's header is gone, and the float state uses w1/w2 in the
first two of the existing six state words. No generated array moves, no
node's layout moves, the chip-2 interleaved pair arrays and their latch
are untouched. The only generated change is the **bypass initialiser**,
which had to change: the Q4.28 identity words read as denormals in float,
which is silence, not bypass.

---

## 2. Capacity, whole graph, both chips, block 16

`DSP4_PROFILE_SIGNAL=1`, two boots per point, minimum taken, witnesses
clean on every point (`gain_coeff=0x3F800000`, chip-2 fabric live on
MAIN_L/AUX_01/GRP_01, pool parity even). Chip 2 is `sigprofile2.sh` with
the chain uncut; chip 1 is `gainprof.sh` at `LIMITS=0`. Both instruments
gained a `DSP4_BQ_FLOAT` passthrough and nothing else.

| arm | chip 2 | % of 327,680 | chip 1 | % |
|---|---|---|---|---|
| contract, per-stage saturate | 306,939 † | 93.67% | 304,363 † | 92.88% |
| fixed round-once, guard OFF | 262,970 † | 80.25% | 291,746 | 89.03% |
| fixed round-once + guard | **264,702** | **80.78%** | **292,863** | **89.38%** |
| **float, 40-bit state** | **246,534** | **75.24%** | **290,861** | **88.76%** |
| float, 32-bit control | 247,290 | 75.47% | 290,829 | 88.75% |

† carried over, same scripts on the same bench: chip 2's two from session
23, chip 1's contract from session 22. Every unmarked figure is this
session's, and chip 1's guard-off row is the cross-check on the carried
one — it reproduces session 22's 291,264 to 0.17%.

**THE INSTRUMENT REPRODUCES ITSELF TO 0.015%.** The fixed round-once +
guard arm comes out at 264,702 here against session 23's 264,741 — a
paired control measured a day and a session apart, on the point the whole
comparison hangs off. Both boots of the float arm returned the identical
246,534.

**Float frees 18,168 cycles/block on chip 2 over the fixed guarded arm**
— 5.54% of budget — and **60,405 over the contract**, 18.43%. On chip 1
it frees 2,002 cycles over the guarded arm, 0.61% of budget.

### Chip 1 is a different question and the answer is a different size

**Chip 1 moves 292,863 → 290,861, which is 2,002 cycles and 0.61% of
budget**, against chip 2's 5.54%. That is not a disappointment, it is
arithmetic: chip 2 carries **632** biquad stages and chip 1 carries
**256** (a 4-stage FILT and a 4-band EQ on each of 32 strips), and
chip 1's cost is dominated by GAIN, its meter and the dynamics, none of
which this change touches. The shootout said as much in its options
table — *"it does not help chip 1, which is the further over of the
two"* — and the graph now says it with a number.

**Two chip-1 controls came out of this session that did not exist
before.** The guard had only ever been measured on chip 2; on chip 1 it
costs **1,117 cycles, 0.34% of budget** (292,863 with it against 291,746
without), against chip 2's 1,771 and 0.54% — the same shape, scaled by
the same stage count. And the guard-off arm reproduces session 22's
291,264 to **0.17%**, which is the chip-1 instrument validating itself
across sessions the way the chip-2 one did.

**The two float arms are within the instrument's spread of each other on
both chips and in opposite directions** — chip 2 reads 40-bit 756 cycles
cheaper than 32-bit, chip 1 reads it 32 cycles dearer. The honest
statement is that the 40 bits cost **nothing measurable**: the mode is
one `bit clr` against one `bit set` in the same place, so there is no
mechanism by which they could differ, and the readings say so.

---

## 3. The numeric cost, and where it actually comes from

`tools/dsp/bq_float_ref.py`. Every arm is scored against **the filter the
design asked for** — unquantised coefficients, float64, no clamp — so the
comparison is "how wrong is this filter", not "how far apart are two
implementations". Impulse at −6 dBFS, response error over 20 Hz–20 kHz.

The 40-bit arm is modelled exactly and not approximately: a product of
two 32-bit significands needs 64 bits before it is rounded and float64
has 53, so every operation runs in `numpy.longdouble` (80-bit, 64-bit
significand) and is rounded **once**, by Veltkamp splitting. The 24-bit
rounding it reduces to is checked against `numpy.float32` on 20,000
random values and agrees on every one.

| design | fixed D5 | flt40 wire | flt32 wire | **flt40 offset** | flt40 exact |
|---|---|---|---|---|---|
| ordinary peak +15 dB Q3 @1k | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| peak +15 dB Q0.1 @5k | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| EXTREME +15 dB Q10 @20 Hz | 0.0265 | 0.3027 | 0.2998 | **0.0007** | 0.0016 |
| HF shelf +12 dB Q5.01 @20 | 0.0151 | 0.3557 | 0.3375 | **0.0042** | 0.0013 |
| **LF shelf +15 dB Q3.16 @20 Hz** | 0.0147 | **0.3715** | **0.5346** | **0.0034** | 0.0107 |
| 4-band EQ, mixed | 0.0004 | 0.0044 | 0.0097 | 0.0001 | 0.0000 |
| EQ 4-band +15/+15/−15/−15 | 0.0000 | 0.0001 | 0.0001 | 0.0000 | 0.0000 |
| 4-band all +15 dB @1k Q1 | 0.0000 | 0.0005 | 0.0071 | 0.0005 | 0.0008 |
| 28-band GEQ all +6 dB | 0.0069 | 0.0606 | 0.1262 | 0.0002 | 0.0009 |
| 28-band GEQ alternating ±6 | 0.0064 | 0.1158 | 0.0881 | 0.0006 | 0.0013 |
| FILT: HPF 20 + LPF 20 kHz | 0.0026 | 0.0067 | 0.0664 | 0.0003 | 0.0001 |
| **WORST OVER THE SET** | **0.0265** | **0.3715** | **0.5346** | **0.0042** | **0.0107** |
| golden_harness bar | 0.046 | | | | |

* **flt40 wire** — `DSP4_BQ_FLOAT` as built: 40-bit arithmetic on the RBJ
  float32 words the SPI wire carries today.
* **flt32 wire** — `DSP4_BQ_FLOAT32`, RIG A2's arithmetic. Its 0.5346 dB
  on the LF shelf is the shootout's 0.520 dB arrived at from a different
  reference, which is the model reproducing a figure it was not fitted
  to.
* **flt40 offset** — the same 40-bit arithmetic on a float32 word
  carrying D5's OFFSET encoding (n1 = b1 + 2b0, n2 = b2 − b0, c1 = 2 + a1,
  c2 = 1 − a2), reconstructed in the kernel. **Not built; modelled.**
* **flt40 exact** — 40-bit arithmetic on unquantised coefficients: the
  control that separates the arithmetic from the coefficient word.

**READ THE LAST TWO COLUMNS TOGETHER AND THE HEADLINE INVERTS.** The
float arithmetic's own error is 0.0107 dB worst case — a quarter of the
golden bar — and the built arm's 0.3715 is thirty-five times that.
Everything between them is the float32 RBJ coefficient word. On the
offset wire the built arm would come out at 0.0042 dB, *better than the
shipping fixed contract's 0.0265*, and the two low-frequency rows that
drive the whole table drop by two decimal orders.

*(flt40 offset reads slightly better than flt40 exact on three rows.
That is coincidence, not a mechanism: at 0.003–0.011 dB the coefficient
quantisation error and the arithmetic error are the same size and
sometimes cancel. The claim is that both are an order of magnitude under
the bar, not that quantising helps.)*

### Residual noise floor

RMS error in dBFS against a float64 run of **the same coefficients each
arm is running**, 32,768 samples of −20 dBFS noise. Scoring against the
ideal filter instead would fold the coefficient word's deterministic
response error into a figure that is supposed to be noise.

| design | fixed D5 | flt40 | flt32 | flt40, state never stored |
|---|---|---|---|---|
| LF shelf +15 dB Q3.16 @20 Hz | **−151.7** | −107.1 | −74.1 | −121.4 |
| EXTREME +15 dB Q10 @20 Hz | **−138.9** | −121.5 | −75.8 | −121.3 |
| 4-band EQ, mixed | **−159.7** | −142.8 | −101.5 | −149.2 |
| 28-band GEQ all +6 dB | **−129.4** | −114.0 | −66.3 | −115.6 |

Three readings, in order of size:

1. **The 40 bits buy 33 to 48 dB and cost nothing.** float32 is 33 dB
   worse on the LF shelf, 46 on the Q10 peak and 48 on the GEQ. Whatever
   is decided about float, it should not be decided at 32 bits.
2. **The fixed path is still 8 to 22 dB quieter than float at 40 bits**,
   and that is the first-order error feedback. Q4.28's precision is
   absolute — 2⁻²⁸ at every level — and the residual it carries makes its
   quantisation noise first-order shaped, which is exactly the right
   medicine for a high-Q low-frequency section whose noise gain is large.
   Float's precision is relative and it has no residual to carry.
3. **The BLOCK BOUNDARY costs 14 dB on the worst case**, and that prices
   an option rather than closing one. The last column is a 40-bit state
   that never passes through a 32-bit word — what a PM-resident (48-bit)
   state array would give. It is worth 14.3 dB on the LF shelf, 6.4 on
   the 4-band and 1.6 on the GEQ, and **nothing at all in the response
   table** (0.3715 against 0.3721). In DM it would cost roughly fourteen
   instructions per stage per block — about 2.7% of chip 2's budget — and
   in PM it would cost no cycles and a large amount of PM, which chip 1
   does not have. Not built; priced.

### Overflow: the claim the guard exists for, tested

Matched-sign drive at 0 dBFS, the input that achieves ‖h‖₁, over the
named worst cases.

| design | ‖h‖₁ | fixed H | peak internal, float | headroom to 3.4e38 |
|---|---|---|---|---|
| peak +15 dB Q0.1 @5k | 9.8 | 1 | 9.8 | 3.5e37× |
| HF shelf +12 dB Q5.01 @20 | 92.4 | 4 | 10.5 | 3.2e37× |
| LF shelf +15 dB Q3.16 @20 | 20.7 | 2 | 8.4 | 4.0e37× |
| EQ 4-band +15/+15/−15/−15 | 1.0 | 0 | 18.9 | 1.8e37× |
| **4-band all +15 dB @1k Q1** | **1285.0** | **8** | **1285.0** | **2.6e35×** |
| 28-band GEQ all +6 dB | 18.8 | 2 | 16.0 | 2.1e37× |

**The worst case in the product's design space uses 3.8 × 10⁻³⁶ of the
exponent range.** Nothing in the float cascade can overflow, and the
eight mantissa bits the fixed path spends on that same cascade are
returned in full. The `EQ 4-band +15/+15/−15/−15` row is worth a second
look: ‖h‖₁ = 1.0 for the *whole* cascade because the four sections cancel,
but the worst PARTIAL prefix reaches 18.9 — which is precisely why the
fixed guard sizes on the worst partial and not on the whole, and
precisely what float does not have to know.

---

## 4. GAIN — does the same argument delete its round/saturate?

**Partly, and much less than the biquad's, because GAIN is memoryless.**
The biquad's win is structural: float deletes a per-stage extract, a
per-stage saturate and an entire parameter-load sizer, all of them
*recursive-path* machinery that exists because an intermediate can leave
Q4.28. A gain has no intermediate and no recursion. What it has is the
per-sample numeric contract: one gain MAC, one rounding MAC, ten
instructions of Q4.28 extract-and-saturate and two block stores —
9.50 c/sample/strip of the class's 26.75, the rest being the meter.

In float the ten become **one clip** — the output still has to fit the
Q4.28 bus — plus the two domain crossings, so about 4 instructions
against 12 in the numeric contract. That is roughly 6 c/sample/strip off
the per-sample path, against RIG C's measured 5.95 for the fixed
round-once version of the same idea. **So float and fixed round-once
arrive at almost the same place on GAIN, which is the tell: the saving is
the rounding contract, not the number format.**

Two things then take it back, and both are already on record. The D20
mic-pre tap must be a Q4.28 rounded and saturated word, so a float GAIN
pays a second crossing to produce it — the same "entire saving returned"
RIG C measured. And the class's fixed 276 c/block overhead is 17.25 c/s
at block 16 against the loop's 3.73, so the per-sample path is not where
GAIN's cost is. Estimate: **converting GAIN to float is worth about 0.9%
of chip 1 and only if the D20 tap is given up** — the same figure and the
same condition as the fixed round-once version. Not worth a session on
its own; worth doing for free if the graph bus ever goes float, which is
the decision that would actually change these numbers.

---

## 5. Bars

| bar | result |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` on `dsp.csv` | **OK**, 666 nodes, no errors |
| `busgold.sh` — graph vs the stored bus capture, `DSP4_BQ_FLOAT=0` | **GRAPH BIT-EXACT, 0 of 256**, sha256 `ba3f52ec` |
| W0, default (round-once + guard) | `4e89e062` / `4d1d314c`, 312,196 / 191,476 — **byte for byte** |
| W0, `DSP4_BQ_ROUNDONCE=0` (the contract control) | `23c1e662` / `e45bb82a`, 301,764 / 182,092 — **byte for byte** |
| W0, `DSP4_BQ_GUARD=0` (the landed round-once kernel) | `2249afea` / `3173acb3`, 301,732 / 182,060 — **byte for byte** |
| `DSP4_BQ_FLOAT=1` default build | `591a0b08` / `e7abb98e`, 301,528 / 181,872 — builds clean on both chips |
| contract files and contract version | **untouched** — no `MW/*/DEFS`, `MW/*/FW`, `MW/*/MX` file differs from HEAD |
| `_bq_hr_*` symbols in the float image | **0** on both chips, against 12 in the default |

Three W0 witnesses rather than one, because the float arm is defined to
follow neither round-once nor the guard and had to be shown inert in all
three configurations. Every line of it is inside `#if DSP4_BQ_FLOAT` and
every line of the fixed kernels inside `#if !DSP4_BQ_FLOAT`.

---

## 6. What this does NOT establish

* **THE FLOAT KERNELS' NUMERICS ARE MODELLED, NOT VALIDATED ON THE
  PART.** This is the same gap RIG C had before `bqeverify.sh` closed it,
  and it is the first thing to close if float is taken further. The
  vehicle exists and is small: `bqe_verify.asm`'s arm A **is**
  `_bq_fx_cascade_simd`, so it becomes the float kernel automatically
  under `DSP4_BQ_FLOAT`; what it needs is `gen_bqe_vectors.py --float`
  emitting RBJ float words into the same five-words-a-stage table, and
  `dsp4_bqe_verify.py` scoring hash A against `bq_float_ref` instead of
  `fixed_ref`. No assembly change at all. What IS on the part is that the
  whole graph runs the float kernels at real time on both chips with the
  witnesses clean and the fabric carrying signal.
* **The offset-wire result is a model, not a build.** The 0.0042 dB
  column is the most decision-relevant number in this document and no
  instruction has been written for it. It needs a wire-format change
  (host side) and a five-instruction reconstruction in the kernel
  prologue, which is stage-rate and would not move the capacity figures.
* **The crossfade path is not bit-identical to the steady-state path
  under float**, and cannot be. `_bq_fx_cascade_N` stores state to a
  32-bit DM word after every sample, so it runs at single precision;
  `_bq_fx_cascade_blk` holds it in registers at 40 bits across the block.
  In the fixed path the two are bit-exact. The difference is 2⁻²⁴
  relative on a 128-sample fade and is stated rather than measured.
* **Chip 2 is never configured on this bench**, so its cascades run on
  their `.var` bypass initialisers in every arm. The instruction stream
  does not vary with coefficients in either arm, so the capacity
  comparison is sound; it is the same caveat every chip-2 figure in this
  tree carries.
* **No block-size sweep.** Everything is block 16, the ruled operating
  point.

---

## 7. What the decision looks like now

Restating the four numbers PW asked for, and the one that was not asked
for and matters more.

| | chip 2 | chip 1 | worst response error | arithmetic noise floor |
|---|---|---|---|---|
| contract (D5 as shipping) | 93.67% | 92.88% | 0.0265 dB | −129 to −160 dBFS |
| fixed round-once + guard | 80.78% | 89.38% | ~0.0265 dB | ~as contract |
| **float, 40-bit, as built** | **75.24%** | **88.76%** | **0.3715 dB** | −107 to −143 dBFS |
| **float, 40-bit, offset wire** | **75.24%** | **88.76%** | **0.0042 dB** | −107 to −143 dBFS |

Float buys 5.5 points of chip 2 over the fixed guarded option and
0.61 of chip 1, deletes the entire load-time sizer and its
latency, and deletes the guard, the header word and both scaling passes.
It costs 8 to 22 dB of arithmetic noise floor that the error feedback is
buying today, and — **only on the RBJ wire word** — an order of magnitude
of low-frequency response accuracy that D5's own offset encoding gets
back for five stage-rate instructions.

The question this session can put to PW in one line: **the cycles say
float, the noise floor says fixed, and the response error says neither —
it says fix the wire format, which is a change worth making in either
arm.**
