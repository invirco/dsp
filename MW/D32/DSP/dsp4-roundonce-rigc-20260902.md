provenance: AI-drafted 2026-09-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# RIG C — fixed-point round-once, measured

*2026-09-02. Spike, standalone rigs only. No graph integration, no
contract edit, shipping image untouched. Instrument:
`SHARC/bqshoot.sh` + `src/lib/bq_shootout.asm` (sixteen timed rungs) and
`tools/pi/dsp4_bq_shoot.py`. Numeric price:
`tools/dsp/bq_state_bound.py` and `tools/dsp/roundonce_noise.py`.*

PW's D5 amendment of the same day moves the round and the saturate to
**once per strip (gain path) and once per cascade output (biquads)**.
RIG A2 answers that with float and is already measured at 5.94
c/band-sample and 0.52 dB on an LF shelf. RIG C is the fixed-point
answer: keep the Q-format contract, keep every coefficient word, and
buy the cycles by deleting the per-stage clamp and managing headroom
instead.

**The one-line result: the fixed round-once option splits into two
deletions that were being treated as one, and they price completely
differently. Deleting the SATURATE costs six instructions and — while
nothing overflows — costs nothing numerically at all. Deleting the ERROR
FEEDBACK costs one instruction and is worth 16 dB of LF response on the
shelf D5 was decided on. Every published account of "round once" so far,
this dispatch included, deletes both.**

---

## 1. Cycles, measured

Same ladder, same 28-stage bank, same iteration count, same block, five
timed loops in ordinary main-loop context, three repeats, minimum taken,
empty loop subtracted. **The rig reproduces its own previous session
exactly** — rungs 1–4 read 25.10 / 12.58 / 11.81 / 5.94 at block 8,
which is session 20's figures to the last digit — so the new rungs are
measured against a validated instrument and not against a rebuild.

| arm | instr/sample/stage | c/band-sample @8 | @16 | **marginal** | ratio vs today @16 |
|---|---|---|---|---|---|
| **today** `_bq_fx_cascade_simd` | 19 | 12.58 | 11.30 | 10.01 | 1.00× |
| **C·E** round-once, **error feedback kept** | 12 | 8.51 | **7.26** | 6.01 | **1.56×** |
| **C·C** round-once, no feedback, rounded | 12 | 7.70 | **6.85** | 6.01 | **1.65×** |
| **C·T** round-once, no feedback, truncating | 11 | 7.07 | **6.29** | 5.51 | **1.80×** |
| **A2** float DF-II-T | 8 | 5.94 | **5.47** | 5.01 | 2.06× |

*Marginal* is the two-point fit across blocks 8 and 16 — the cost of one
more band-sample, with the per-stage fixed cost removed. **It lands on
half the instruction count to within 0.02 cycles on every fixed arm**
(19→10.01, 12→6.01, 12→6.01, 11→5.51), which is what "paired" means and
is the strongest evidence the rig is measuring the loop and not the
harness. The float arm is the exception: eight instructions, 5.01
measured, so it carries one cycle of stall per sample that the fixed
arms do not.

**C·E and C·C have IDENTICAL marginal cost and differ only in fixed
cost per stage** (39.97 vs 26.95 cycles/stage): the feedback arm loads
and stores six state words instead of four and sets up MRF. That is why
the gap closes from 0.81 c/band-sample at block 8 to 0.41 at block 16
and would keep closing.

The 0.81 is **not** the adjacency of the feedback MAC to the ALU op that
produces its operand — moving the MAC after the store, so an instruction
stands between them, measured 8.51 as well. It is the MRF chain: the
no-feedback arms seed a cleared accumulator every sample, which breaks
the dependency; the feedback arm runs seven dependent MACs back to back.

### The extract is the floor, and it is why fixed cannot reach float

A stage output feeds the next stage's multiplier and its own y1/y2, so
it must exist as a 32-bit register every sample **whatever the rounding
policy is**. Extracting it from the 80-bit accumulator at a 28-bit shift
is four instructions on this part:

```
r2 = mr0f;  r3 = mr1f;
r0 = lshift r2 by -28;  r0 = r0 or lshift r3 by 4;
```

A one-instruction extract (`Rn = MR1F`) exists only when the shift is
exactly 32 — that is, when the coefficients are Q0.32 and bounded by
one. They are not: g1h is b1/2 and |b1| reaches 11.2 in the product's
own design space. **So float's advantage over any fixed round-once is
not the saturate; it is that float has no extract at all.** Six MACs and
four extract instructions is ten; the fixed floor is 5.0 c/band-sample
paired, and C·T measures 5.51.

*(`Rn = Rn OR LSHIFT Rx BY <data8>` requires its destination to be the
shifted-low operand — `r1 = r0 or lshift r3 by 4` is rejected by the
assembler. That is why these kernels carry y in r0 where the shipping
kernel carries it in r1.)*

### Chip 2, at block 16

632 biquad stages × 16 samples = 10,112 band-samples/block against chip
2's measured 306,950 cycles and 327,680 budget (93.7%).

| arm | cycles freed / block | % of chip 2 budget | chip 2 goes to |
|---|---|---|---|
| C·E | 40,850 | 12.5% | 81.2% |
| C·C | 45,000 | 13.7% | 80.0% |
| C·T | 50,660 | 15.5% | 78.2% |
| A2 | 58,950 | 18.0% | 75.7% |

---

## 2. GAIN, round once per strip

Rungs 9–13 carry the shipping SIMD gain loop verbatim and the round-once
variants beside it. Under round-once the gain node hands the chain a
**wide** word, and on this part that word is free: the product of two
Q4.28 words is Q8.56 in MRB and **MR1B is its top 32 bits — exactly
Q8.24, in one instruction and no shifter**. It is also the word the
meter already reads, so the round-once body is the metered body with the
arithmetic deleted and nothing added.

Two-point fit across blocks 8 and 16, cycles per sample per strip:

| arm | c/sample | fixed c/call | ratio |
|---|---|---|---|
| today, +meter | **9.03** | 61.0 | 1.00× |
| round-once, +meter | **3.55** | 61.0 | **2.54×** |
| **round-once, D20 tap kept bit-identical** | **9.01** | 61.1 | **1.00×** |
| today, −meter | 7.46 | 62.0 | 1.21× |
| round-once, −meter | **2.51** | 61.1 | **2.97×** |

9.03 against the graph's independently measured 9.50 c/sample for the
same loop is a 5% cross-check between two instruments that share no
arithmetic.

**AND THE THIRD ROW IS THE ANSWER TO THE DISPATCH'S GAIN QUESTION.** The
dispatch asks for the round-once gain figure *and* states that the D20
mic-pre tap stays bit-identical. Those two requirements are not
compatible, and the rig measures the incompatibility rather than
choosing between them. The tap is a Q4.28 rounded-and-saturated word;
MR1B has already dropped the four bits a Q4.28 rounding would have seen,
so a wide chain slot cannot produce it, and the node must compute the
narrow word anyway. **Keeping the tap returns the entire saving: 9.01
against today's 9.03.**

Giving the tap up: the graph's per-sample path goes 9.50 → 3.73, the
GAIN class goes 26.75 → **20.98 c/s** (1.28×), and chip 1 gains 2,954
cycles/block = **0.90% of budget**, 92.8% → 91.9%. **It does not reach
1–2 c/s and round-once is not the reason it does not**: at block 16 the
fixed 276 cycles/block is 17.25 c/s against the loop's 9.50, so the
sample loop was already the smaller half before this change and is
3.73 after it.

---

## 3. What it costs — and this is the whole point of RIG C

### 3a. Headroom, and therefore noise floor

Q4.28 is 0 dBFS = 1.0 with a ceiling of 8.0 (+18.06 dB). Carrying H bits
of headroom means Q(4+H).(28−H): the ceiling goes up 6.02 dB per bit and
**the noise floor comes up 6.02 dB per bit**. Total dynamic range is
unchanged — it is 32 bits either way — but H of those bits are spent
above 0 dBFS, where music is not.

| H | format | ceiling | noise floor | eff. bits |
|---|---|---|---|---|
| 0 | Q4.28 | +18.06 dB | −179.4 dBFS | 28 |
| 2 | Q6.26 | +30.10 dB | −167.3 dBFS | 26 |
| 4 | Q8.24 | +42.14 dB | −155.3 dBFS | 24 |
| 8 | Q12.20 | +66.23 dB | −131.2 dBFS | 20 |

**How much H the chain actually needs**, measured over the DEFS design
space by `bq_state_bound.py` — and the bound is **‖h‖₁, the l1 norm of
the impulse response, not max|H|**, because ‖h‖₁ is what an arbitrary
bounded input can reach and max|H| is only what a sine can:

| what | worst ‖h‖₁ | as dB | H needed |
|---|---|---|---|
| one biquad, worst single stage in the space | 97.3 | +39.8 | **4** |
| FILT: HPF 20 Hz 36 dB/oct + LPF 20 kHz | 4.5 | +13.1 | **0** |
| GEQ, 28 × +12 dB | 41.9 | +32.5 | **3** |
| **EQ: 4 bands, all +15 dB, coherent** | **1313** | **+62.4** | **8** |

Over **114,253** quantised sets (the full `bound_efb.design_space`
grid), 1.3% exceed 8.0 on a sine and 4.0% exceed it on worst-case drive;
the single worst is an HF shelf at +12 dB, Q 5.01, 20 Hz, at ‖h‖₁ = 97.3
against max|H| = 73.3 — **the sine bound understates the reachable one by
2.5 dB even at the corner, and by much more away from it.** The four-band row is the one that decides it, and
it is **ordinary**: four bands at +15 dB on one frequency is a setting
the DEFS ranges allow and a console operator can dial.

### 3b. The recursive state, not waved away

The normative topology is offset-coefficient **direct form I**, whose
state is x1 x2 y1 y2 plus the feedback remainder. x1/x2 are past inputs
and y1/y2 are past **outputs** — there is no separate internal node — so
*"the state overflows"* and *"the stage output overflows"* are the same
event. That matters twice:

* **Today, y is saturated at every stage, so the recursion stays
  representable by construction.** A clipped y is a wrong y but a
  bounded one, and the filter degrades into soft nonlinearity.
* **Under round-once the extract wraps.** In a recursive path a wrap is
  not a clipped sample; it is a full-scale sign inversion fed straight
  back into the poles, and a high-Q section rings on it.

Demonstrated, not asserted, on the worst set in the space (HF shelf
+12 dB Q5.01 at 20 Hz), driven at 0 dBFS by the matched-sign input
that achieves ‖h‖₁ — because that is the input the bound is about, and a
square wave at f0 reaches only max|H|, which is exactly why sizing
headroom off an EQ curve is the mistake:

```
contract (saturating): peak |y| = 8.000 x 0 dBFS  (clamps at 8.000)
round-once (wrapping): peak |y| = 8.000 x 0 dBFS,
                       18,433 of 40,000 samples OPPOSITE IN SIGN
```

Nearly half the block comes out with the wrong sign. The same run on a
+15 dB Q0.1 peak at 5 kHz — the worst *peaking* set — flips exactly one
sample in forty thousand, which is the other half of the point: this
fails rarely and catastrophically, which is the hardest kind of defect
to qualify against.

**Which designs.** ‖h‖₁ rises with **boost**, far faster than with Q.
For peaking sections, at the worst frequency for each cell:

| gain | Q 0.1 | Q 0.5 | Q 1 | Q 2 | Q 5 | Q 10 |
|---|---|---|---|---|---|---|
| +3 dB | 1.88 | 1.58 | 1.53 | 1.53 | 1.53 | 1.53 |
| +9 dB | 4.66 | 3.40 | 3.33 | 3.32 | 3.32 | 3.32 |
| +15 dB | **9.81** | 6.99 | 6.91 | 6.89 | 6.89 | 6.89 |

The *worst* Q for a peak is the **lowest** (0.1), not the highest — a
wide boost integrates more of the impulse response than a narrow one —
and no peaking section in the space needs more than 1 bit. **Shelves are
an order worse than peaks** (97.3 against 9.81) and they peak at
moderate Q (≈5) and the ends of the frequency range, where a shelf's
passband gain and its transition ringing add. **So "a high-Q filter"
names the wrong hazard: the hazards are high GAIN, SHELVES, and — by an
order more than either — CASCADES.**

**The guard, and why the cheap ones do not work.**

* A per-**cascade** clamp does not help: the wrap happens *inside*, in
  y1/y2, and is fed back before the cascade output exists.
* A per-**stage** clamp on y *is* the guard — and it is exactly the six
  instructions round-once deletes, so it gives the cycles straight back.
* **Headroom sized on ‖h‖₁ is the guard that keeps the cycles**, and it
  is nearly free in the sample loop: the entry scaling is one `ashift`
  per sample **per cascade** (not per stage) and the exit scaling folds
  into the single clamp that happens anyway. For a 4-band cascade that
  is +0.25 instructions per band-sample, ≈ +0.13 c/band-sample paired.
  *Priced by arithmetic, not measured on the part.*
* And H need not be a constant. It is computable at **parameter-load
  time** from ‖h‖₁ of the coefficient set actually loaded, so a flat EQ
  pays H = 0 and only a hot one pays — whose noise floor is irrelevant
  because its signal is +62 dB. **That is the design RIG C should be
  judged as, and it is the one thing in this write-up that has not been
  built.**

### 3c. Response error — where the fixed round-once actually breaks

Impulse → FFT, 20 Hz – 20 kHz, same method and same band
`bq_float_delta.py` uses for the float arm, against the current
contract. Max |dB|:

| design | C H=0 | C H=4 | **E H=0** | **E H=2** | **E H=4** | **E H=6** | **E H=8** |
|---|---|---|---|---|---|---|---|
| peak +15 dB Q3 @1 kHz | 0.0006 | 0.0087 | **0.0000** | 0.0001 | 0.0002 | 0.0007 | 0.0028 |
| +15 dB Q10 @20 Hz | 2.4649 | 2.5757 | **0.0000** | 0.0084 | 0.0336 | 0.3763 | 2.2642 |
| **LF shelf +15 dB Q3.16 @20 Hz** | **16.2615** | 33.5201 | **0.0000** | **0.0093** | 0.0603 | 0.1819 | **5.7363** |
| 4-band EQ, mixed | 0.0837 | 1.3111 | **0.0000** | 0.0018 | 0.0068 | 0.0232 | 0.1016 |
| 28-band GEQ all +6 dB | 1.9873 | 12.2185 | **0.0000** | 0.0105 | 0.0524 | 0.5296 | 1.7071 |

golden_harness holds the contract to **0.046 dB**; RIG A2 costs 0.520 dB
on the LF shelf row.

**Read the C column and the E column together and the session's finding
is in front of you.** C·H=0 has spent *no* headroom and already costs
16.26 dB on the LF shelf — that is the error feedback's absence, alone,
and it is thirty times worse than the float arm the ruling calls the
fallback. E·H=0 is **0.0000 dB, bit-identical to the contract**, on the
same twelve instructions, because a saturate that never fires is the
identity.

And the E row is where the headroom bill lands: **H ≤ 3 stays inside the
0.046 dB bar; H = 6 costs what float costs; H = 8 — the headroom the
four-band case needs — costs 5.74 dB, a hundred and twenty-five times
the bar.**

Noise floor, measured as residual RMS against float64 on the same
quantised coefficients, −20 dBFS 997 Hz drive, dBFS re 1.0:

| design | contract | E H=0 | E H=2 | E H=8 | C H=0 | C H=4 |
|---|---|---|---|---|---|---|
| LF shelf +15 dB Q3.16 @20 Hz | −149.2 | −149.2 | −139.2 | −104.3 | −94.6 | −63.7 |
| peak +15 dB Q10 @20 Hz | −146.9 | −146.9 | −137.3 | −99.4 | −92.0 | −69.9 |
| peak +6 dB Q1 @1 kHz | −170.7 | −170.7 | −157.9 | −121.1 | −154.1 | −129.9 |

### 3d. The gain path's own bits

The shipping gain node stores `sat32(rns(x*g, 28))`. Round-once stores
MR1B — Q8.24, **truncated**. Over 200,000 random samples at a non-round
gain:

```
today  Q4.28 round+sat   error RMS -179.4 dBFS   DC bias -3.7e-12
round-once Q8.24 trunc   error RMS -149.3 dBFS   DC bias -3.0e-08
```

30.1 dB, of which 24.1 is the four bits and the rest is that MR1B is a
shift and not a round. A rounded wide store costs one more MAC.

---

## 4. Where round-once is safe and where it is not

| path | safe? | why |
|---|---|---|
| GAIN, FADER, sends, crosspoints | **yes** | memoryless; one multiply, no state to corrupt. The only cost is the low bits and the tap's bit pattern. |
| MIX_BUS summing | **yes** | already a wide 64-bit accumulator with one saturate at the end — this is round-once and always has been. |
| FILT (HPF+LPF) | **yes** | ‖h‖₁ = 4.5, fits Q4.28 with no headroom at all. |
| TUBE_SAT | **no** | three chained roundings are the *specified* nonlinearity (D5, PW 2026-08-30); collapsing them changes the product's sound, not its noise floor. |
| EQ / GEQ cascades | **conditional** | safe at the headroom ‖h‖₁ demands, which is 0–3 bits for ordinary and GEQ settings and 8 for a coherent 4 × +15 dB. Above H ≈ 3 the response leaves the bar. |
| Dynamics envelopes | **not measured** | one-pole recursions in Q4.28 with Q0.31 alphas; the same wrap argument applies and this spike did not price them. |

---

## 5. Three-way, all measured, block 16

| axis | **today** fixed per-stage | **RIG C** fixed round-once | **RIG A2** float round-once |
|---|---|---|---|
| c/band-sample, paired | **11.30** | **7.26** (E) · 6.85 (C) · 6.29 (T) | **5.47** |
| ratio | 1.00× | 1.56× · 1.65× · 1.80× | 2.06× |
| chip-2 cycles freed /block | — | **40,850** (E) … 50,660 (T) | **58,950** |
| chip 2 goes to | 93.7% | 81.2% … 78.2% | 75.7% |
| noise floor (LF shelf, resid. RMS) | −149.2 dBFS | −149.2 (H=0) · −139.2 (H=2) · −104.3 (H=8) | not measured this way |
| effective bits | 28 | 28 − H | 24 (float32 mantissa) |
| response error, worst case | **0** (it is the reference) | **0.0000** (H=0) · 0.0105 (H=2) · **5.74 (H=8)** | **0.520** |
| against the 0.046 dB bar | — | passes to H ≈ 3, fails at H = 8 | **fails, 11×** |
| biquad-state safety | **guaranteed** — per-stage clamp | **wrap** unless H ≥ ‖h‖₁; 4 bits for the worst single stage, **8 for a reachable 4-band setting** | **guaranteed** — float cannot wrap, it saturates to ±inf |
| GAIN c/sample | 9.03 | **3.55**, or **9.01 with the D20 tap** | n/a |
| contract change | none | Q-format contract kept; clamp policy amended | float response change (D5 reopened) |

---

## 6. What this says, plainly

1. **The cheap half of round-once is free and should be taken on its own
   merits.** Deleting the per-stage *saturate* while keeping the error
   feedback is 12 instructions against 19, measures **7.26 c/band-sample
   at block 16 (1.56×, 40,850 cycles/block off chip 2)**, and at H = 0 is
   **bit-identical to the contract**. Nothing in the numeric spec moves.
   What it gives up is the overflow *guarantee*, and only that.
2. **The expensive half is the error feedback, and it should not be
   deleted.** It costs one instruction and is worth 16 dB of LF response
   — thirty times the float arm's whole numeric price. The C and T arms
   in the table are there to price that, not to be adopted.
3. **Fixed round-once cannot reach float's speed**, and the reason is
   structural, not an un-done optimisation: the 64-bit extract is four
   instructions and does not go away.
4. **The overflow guarantee is the real decision.** Sized for a
   reachable four-band +15 dB EQ it needs 8 bits of headroom, and at 8
   bits fixed round-once is *worse* than float on the very axis D5 was
   decided on (5.74 dB against 0.52). Sized per-cascade at parameter-load
   time from ‖h‖₁ it is nearly free and mostly H = 0 — **but that
   variant has not been built and this spike did not measure it.**
5. **GAIN's round-once saving and the D20 mic-pre tap are mutually
   exclusive, measured.** 3.55 c/sample without the tap, 9.01 with it
   against today's 9.03. That is a product decision, not a numeric one.
6. **Neither GAIN nor the cascade reaches the numbers the dispatches
   named** (1–2 c/s; 3 c/band-sample), and in both cases the arithmetic
   says why: GAIN's sample loop is no longer the larger half of its
   class, and the cascade's extract is a hard floor.

**Recommendation to PW: take the saturate deletion with the error
feedback kept (C·E) and treat the headroom question as a separate,
per-cascade, control-rate design — do not adopt any arm that deletes the
error feedback.** If the overflow guarantee must be absolute at a fixed
headroom, RIG C is worse than float on the LF axis and float (A2) is the
better trade. RIG B (the IIR accelerator, 40-bit float) is still
unmeasured and could give A2's speed at a smaller numeric cost; it
remains the one option in the space nobody has priced.

---

## 7. Still open

* **C·E is TIMED, NOT VALIDATED.** The rig runs zeroed banks, which is
  sound for timing and proves nothing about the asm. The bit-identity
  claim in §3c is measured on the **Python model** (`roundonce_noise.py`,
  E arm at H = 0), not on `_bqe_cascade_simd`. A diff of the kernel
  against `fixed_ref` is the next bar and it does not exist.
* The per-cascade control-rate headroom of §3b is priced by instruction
  count and never assembled.
* Dynamics envelopes were not priced at all.
* Nothing here ran in the graph; every figure is standalone-rig.
