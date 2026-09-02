provenance: AI-drafted 2026-09-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Chip 2's biquad cascades, paired with a native interleave — and whether chip 2 fits

Session 19, 2026-09-02. Follows `dsp4-biquad-cascade-20260901.md` (session
18), whose closing section named this as the only large lever left and
priced it at 730 → 362 MHz.

---

## 1. What the lever is, and why it is not "wire the existing pairing onto chip 2"

Chip 1 has paired biquads since 2026-08-29. `_bq_pair_blk` gathers two
strips' coefficients and state into an interleaved scratch, runs
`_bq_fx_cascade_simd`, and scatters back. Session 18 priced that gather
exactly:

> 5 coefficient words in, 6 state words in and 6 state words out per stage
> per pair — 68 instructions per stage per pair, over 2 channels × 8
> samples = 16 band-samples, so **4.25 cycles per band-sample, and the
> figure does not depend on the stage count.**

Against a paired inner loop that saves 9.5 cycles per band-sample, a 4.25
gather turns a 2× lever into about 1.5×. That is what
`LEVER_BQPAIR_BLK8` measured from the other end: −8.3% against a −13%
prediction.

So the work is not to call `_bq_pair_blk` from chip 2. It is to **stop
gathering**.

## 2. The design that landed: a LATCH, not an interleave at conversion time

Session 18 proposed emitting the coefficients interleaved from
`_bq_fx_convert_N` (a stride, not a copy) and giving the per-sample
reference cascade a stride parameter in an M register. That reaches the
right per-block cost. It also rewrites the three kernels that ARE the
numeric contract — `_bq_fx_cascade_N`, `_bq_fx_cascade_blk`,
`_bq_fx_convert_N` — and every cascade node body's steady, transient and
staging paths with them.

What landed instead moves the AUTHORITY rather than the layout, and it
leaves every node body byte for byte unchanged.

Each pair owns two arrays and one word:

```
.var _bqi_c_<tag>[10*S];    /* interleaved coefficients, A word then B word */
.var _bqi_s_<tag>[12*S];    /* interleaved state, likewise                  */
.var _bqi_lat_<tag> = 0;    /* 1 = the interleaved arrays are authoritative */
```

and the driver has three paths:

| condition | what runs |
|---|---|
| both channels steady, latch down | **ENGAGE**: gather each channel's ACTIVE instance into the interleaved arrays, once; raise the latch; then run |
| both channels steady, latch up | the signal interleave and `_bq_fx_cascade_simd` — **no coefficient or state gather at all** |
| either channel transient | **DISENGAGE**: scatter the interleaved STATE back to each node's active instance, drop the latch, and call the two node bodies — the untouched reference path |

A gather costs 5 + 6 words per stage per pair ONCE PER COEFFICIENT SWAP.
A swap is a user gesture; a crossfade is 576 samples. Per block, all that
is left is the signal: 8 words per channel in and out, which on a 28-band
GEQ pair is **0.14 cycles per band-sample**.

**Nothing else can move the coefficients or the state.** Every write to
either goes through `_<pfx>_coeffs_next_` and `_<pfx>_swap_pending_`, and
`swap_pending` is one of the two words the steady test reads — so a change
takes the latch down before it can be seen. That is also why the disengage
scatters the STATE only: the coefficients cannot have changed while
latched, because a change is what brings the driver there.

**What is authoritative when.** Latched, the node's own coefficient and
state arrays are stale and nothing reads them — the chain calls the driver,
not the nodes. Unlatched, the interleaved arrays are stale and nothing
reads them. `_<pfx>_active_` cannot move while latched either, because it
only flips inside a node body at the end of a crossfade, and a crossfade is
one of the conditions that keeps the latch down.

## 3. What pairs, and it is an explicit table

`_C2_PAIR_FAMILIES` gained a second column, kept separate from the
dynamics one for the reason chip 1 keeps `DSP4_BQ_GRAPH` apart from
`DSP4_SIMD_GRAPH`: the dynamics-paired chain has to stay buildable, byte
for byte, as the control.

| family | chain classes | dynamics pairs | biquad pairs |
|---|---|---|---|
| AUX (12) | FDR EQ GEQ AFB LIM DLY OUT | LIM | **EQ (4) GEQ (28) AFB (6)** |
| GRP (4) | FDR EQ GEQ GATE COMP | GATE COMP | **EQ (4) GEQ (28)** |
| MOUT (4) | OEQ OCOMP OLIM OUT | OCOMP OLIM | **OEQ (4)** |

That is **24 pair drivers over 48 cascade nodes carrying 600 biquad
stages**, against 632 in all 50 of chip 2's dual-instance cascade nodes —
**95%**. What stays scalar is what has no partner: `C2_MAIN_GEQ` (28
bands), `C2_SUB_EQ` (4) and the crossover's own sections. They are single
instances in chains of their own and need the cross-chain DAG argument
this session did not make, exactly like the four single-instance dynamics
nodes.

Two invariants are CHECKED rather than assumed, and raise rather than
quietly pairing something else:

* both the dynamics-only paired set and the union with the biquads must be
  a CONTIGUOUS run of the chain's class order — the first is the control
  build's order, the second is this build's, and the reorder that produces
  either one only ever moves nodes inside the run;
* every biquad class must have an entry in `_C2_BQ_STAGES` stating where
  its stage count lives in `dsp.csv` (`bands` for EQ/GEQ/OEQ,
  `notch_count` for AFB). A class whose length the table cannot state is
  left scalar rather than paired at a guessed length. A pair is ONE
  instruction stream, so the two channels' lengths are compared and a
  mismatch raises.

## 4. Containment

* `DSP4_C2_BQ_GRAPH=0` is the control, and it is not merely "believed
  equivalent": the control arm was rebuilt from the previous commit's tree
  and matched **byte for byte — chip1.ldr `3bee918c`, chip2.ldr
  `ac6668a2`** — so it is exactly the configuration 240,681 cycles/block
  was measured on.
* **chip 1's `.ldr` is byte-identical across the two arms** (`3bee918c`),
  and no chip-1 generated file changed at all: the whole diff is
  `chip2/bq_pairs.asm`, `chip2/process_chain.asm` and two macros in
  `dsp_block.h`.
* **W0 holds**: the shipping image is `chip1.ldr 23c1e662` /
  `chip2.ldr e45bb82a`, 301,764 / 182,092 bytes, reproduced before the
  first line of this work and after the last. Every line added is inside
  `#if DSP4_C2_BQ_PAIRED_GRAPH`, which is 0 unless `DSP4_SIMD_DYN` is on.
* **Contract-neutral**: `gen_dsp.py --force` leaves `ghost_cells.h`,
  `dsp_address_map.md` and both `dsp_params.asm` byte-identical, so no
  contract version moves. No SPI-visible parameter is added or renamed.

---

## 5. Measured on the graph

Same instrument as sessions 17 and 18 — `sigprofile2.sh`, chip 1 running
whole with 32 strips and stimulus on, only chip 2's chain cut by
`DSP4_NODE_LIMIT2`, `DEC=32` so the pass always completes, both the
chip-1 gain witness and the chip-2 fabric witness required before a number
is accepted.

**THE CONTROL POINT REPRODUCED, THREE BOOTS.** The whole chip-2 graph in
the `DSP4_C2_BQ_GRAPH=0` arm — a build proved byte-identical to the
previous commit's — read **240,200**, **240,814** and session 18's
**240,681** cycles/block on three separate boots: a spread of **0.26%**.
That is what makes the difference below attributable.

### The cost ladder, both arms

`DSP4_NODE_LIMIT2` cuts chip 2's chain to the first N positions, so
consecutive differences are per-node costs. The aux-01 chain sits at the
same ladder positions in both arms up to position 47, which is what makes
the two ladders comparable; the paired arm's chain then reorders in place
(head A, head B, the four pair drivers, tail A, tail B).

| position | control arm (`c2bq=0`) | paired arm (`c2bq=1`) |
|---|---|---|
| 47 | `C2_AUX_FDR_01` | `C2_AUX_FDR_01` |
| 48 | `C2_AUX_EQ_01` (4) | `C2_AUX_FDR_02` |
| 49 | `C2_AUX_GEQ_01` (28) | **EQ pair** (2 × 4) |
| 50 | `C2_AUX_AFB_01` (6) | **GEQ pair** (2 × 28) |
| 51 | `C2_AUX_FDR_02` | **AFB pair** (2 × 6) |
| 52 | `C2_AUX_EQ_02` | LIM pair (paired in both arms) |


**Control arm, measured** (cycles per block, one instance each):

| node | stages | cycles | c/band-sample |
|---|---|---|---|
| `C2_AUX_FDR_01` | — | 754 | — |
| `C2_AUX_EQ_01` | 4 | 346 | 10.8 |
| **`C2_AUX_GEQ_01`** | **28** | **5,666** | **25.29** |
| `C2_AUX_AFB_01` | 6 | 1,849 | 38.5 |

**GEQ reproduces session 18 to 0.05%** — 5,666 against 5,669, 25.29
against 25.31 cycles per band-sample — which is what makes the paired
figure below attributable.

**THE EQ AND AFB SPLIT IS BELOW THE INSTRUMENT'S RESOLUTION AND IS NOT
QUOTED AS TWO NUMBERS.** 10.8 and 38.5 cycles per band-sample cannot both
be the same kernel running the same instruction stream. Their SUM is
sane — 2,195 cycles over 80 band-samples is 27.4, next to GEQ's 25.29 with
the per-call overhead amortised over ten stages instead of twenty-eight —
so what is unreliable is the boundary between two adjacent ladder points,
not the pair of them. This is the same limitation session 17 recorded when
FDR, EQ and OUT read NEGATIVE at one or more block sizes and were carried
as below-resolution rather than as numbers. GEQ is quoted because it is
large enough to be attributable and because it reproduced.

**Paired arm, measured**, same ladder, positions 47..52:

| driver | channels x stages | cycles | c/band-sample |
|---|---|---|---|
| `C2_AUX_FDR_01` / `_02` | — | 203 / 195 | — |
| **EQ pair** | 2 x 4 | 975 | 15.2 |
| **GEQ pair** | 2 x 28 | **5,748** | **12.83** |
| **AFB pair** | 2 x 6 | 1,876 | 19.5 |

### The headline per class

**The 28-band GEQ cascade goes 25.29 -> 12.83 cycles per band-sample, a
factor of 1.97 — the 2x this lever was priced at, and the whole of it.**
Two scalar 28-band cascades cost 2 x 5,666 = 11,332 cycles a block; the
pair costs 5,748.

**AND THE TARGET IS NOT MET. 12.83 IS NOT <= 11.0.** The dispatch's
break-even, and it is missed by 17%.

**THE MARGINAL COST *IS* 11.0, AND THE DIFFERENCE IS THE DRIVER.** GEQ and
AFB are the two ladder points above the instrument's resolution, and the
straight line through them separates the per-stage cost from the per-call
one:

| | per stage per block | per band-sample | fixed per call |
|---|---|---|---|
| scalar (1 channel) | 173.5 | 21.69 | 808 |
| paired (2 channels) | 176.0 = 88.0/channel | **11.00** | 820 |

So the paired cascade's marginal rate is 11.00 cycles per band-sample
against the scalar 21.69 — 1.97x, the same factor the GEQ ratio gives from
a different direction — and a 28-band pair carries 820/448 = **1.83
cycles per band-sample of driver on top of it**. That is the signal
interleave, the steady and latch tests, the `_buf_` republish and the
call itself, amortised over 28 stages instead of over 4.

**THIS IS A TWO-POINT FIT AND IS LABELLED AS ONE.** Two points determine a
line exactly; there is no residual and therefore no corroboration in the
fit itself. It is quoted because the two points are the two that
reproduced, and because the ratio it gives agrees with the ratio the GEQ
points give on their own.

### Parts against whole, and it is weaker than session 18's

The GEQ and AFB pairs alone — the classes whose ladder points are above
resolution — predict 8 x 5,584 + 6 x 1,822 = **55,604** cycles of saving
against the **61,258** the whole graph actually moved: they account for
**90.8%** of it, sharing no arithmetic with it. The remaining 5,654 is the
ten EQ pairs, i.e. about 565 cycles each, which is the right order for a
4-stage cascade pair but is NOT independently attributable, because the
EQ ladder point is not.

Session 18's parts-vs-whole checks landed at 1.0%, 5.2% and 6.7%. This one
is 9.2% on two of three classes and silent on the third, and the reason is
stated rather than averaged away: at a 17,000-cycle baseline the
point-to-point spread of this instrument is several hundred cycles, which
a 5,666-cycle node survives and a 346-cycle one does not. The same node,
`C2_AUX_FDR_01`, at the same ladder position, read 754 in one arm and 203
in the other.

---

## 6. The headline, and the plain answer

**Chip 2's whole graph, signal present, chip 1 running its full 32 strips,
block 8, 983.04 MHz, graph decimated so the pass completes:**

| arm | cycles/block | % of the 163,840-cycle budget | MHz at 48 kHz |
|---|---|---|---|
| control, `DSP4_C2_BQ_GRAPH=0` | 240,200 / 240,681 / 240,814 | 146.6% | 1,444 |
| **paired, native interleave** | **179,460 / 179,556** | **109.6%** | **1,077** |

**−61,258 cycles/block, −25.4%, from one lever with no change to any node
body.** At 786.432 MHz it is 137.0% of the 131,072-cycle budget, from
183.6%.

Cumulative over the whole campaign: **342,090 → 179,556, −47.5%**;
**208.8% → 109.6% of the part**.

### Does chip 2 fit? NO — AND IT IS 9.6% SHORT.

That is the plain answer the dispatch asked for. The graph needs 179,556
cycles a block and the part gives 163,840 at 983.04 MHz. It is over by
**15,716 cycles a block, 96 MHz, 9.6%.**

**The remaining gap is almost exactly the size of the one named lever
left.** Session 18 priced the hoisted LIM/COMP/GATE/DLY/XOVER kernels at
about 90 MHz — chip 2's signal nodes run under the GENERIC per-block
wrapper, which session 17 measured at ~15% over a hoisted kernel. 90 MHz
is 15,000 cycles a block against a 15,716-cycle gap. **On measured parts,
chip 2 lands at about 100.4% of the part after it** — which is a coin
toss, not a fit, and it is the same arithmetic session 18 used to predict
101.3% for this point and got 109.6%.

**Session 18's prediction for THIS lever was 1,086 MHz and the measurement
is 1,077 — 0.8% apart.** The pricing method is sound; what it does not
have is margin.

## 7. Verification

| bar | verdict |
|---|---|
| `c2bqgold.sh` — cascades scalar vs paired, one tree, identical stimulus | **49 output blocks, 0 differ — BIT-EXACT**, with a LIVE negative control |
| `c2bqgold.sh` — the ROUND-TRIP arm vs scalar | **0 of 49 differ** |
| `c2bqgold.sh` — the ROUND-TRIP arm vs latched | **0 of 49 differ** |
| `busgold.sh` — chip 1's main bus vs the stored session-6 golden | **GRAPH BIT-EXACT, 0 of 256 words** |
| `conform.sh` — contract conformance, both chips | **PASS**; presence 6032/388/117/56/159 on chip 1, chip 2 on its own map 1701/24/21/175/31, negative control 4 of 4, the 16 declared-unit fails the named D41 ones |
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK** |
| W0 | `chip1.ldr 23c1e662` / `chip2.ldr e45bb82a`, 301,764 / 182,092 bytes, reproduced four times across the session |

### The latch was witnessed, not assumed

A pair that never engaged ran its two scalar node bodies all along, and
from the outside that is indistinguishable from a bit-exact result — the
silent-fallback trap c2dyngold hit on 2026-09-01. Every arm reports
`_bqi_lat_*`: **1 in the paired arm on all five probed pairs, 0 in the
round-trip arm**, and the bar fails outright if the paired arm's latches
are down.

### The negative control FIRES, and this one is deliberate

`DSP4_C2_BQ_NEGCTL` gathers channel B's coefficients as ZERO, so B runs a
dead filter while A's is untouched. **It moved 6 of 6 channel-B cascade
outputs and 0 of the 2 independent-chain channel-A ones.**

**That closes the gap session 18 could not.** Chip 1's control — B takes
A's coefficients, so the pair computes one channel twice — is DEAD on chip
2: nothing configures chip 2's filters, so every cascade runs the same
`.var` bypass initialisers and A and B are numerically the same filter.
Session 18 recorded that its dynamics pairs' channel separation was
therefore unproven and that closing it needed distinct per-channel
settings over the SPI plane. Zeroing ONE channel needs no SPI plane at
all: the result can only be produced by a kernel that keeps the two
channels' coefficients apart, and it cannot be masked by the two channels
carrying the same signal.

**THE BAR FAILED ON ITS FIRST RUN, AND THE CRITERION WAS WRONG RATHER THAN
THE KERNEL.** The first cut required NO channel-A cascade to move and
`C2_MAIN_OEQ_01` moved. It reads `C2_MAIN_XOVER`, which is fed by the main
mix, which sums every aux and group output on the chip — so it is
DOWNSTREAM of every channel B and must move whatever the kernel does.
Requiring it to hold still was requiring the graph not to be a graph. The
criterion now scopes the must-not-move set to the aux and group cascades,
which read their own chain's fader; **in that same run all five of them
held still**. This is recorded rather than smoothed over: the criterion was
corrected after seeing a result, which is the weaker order to do it in, and
the same captures were re-scored rather than re-measured.

### What the round-trip arm covers, and why it had to exist

Nothing on this bench writes chip 2's filter coefficients. So in arms 0, 1
and n the gather runs ONCE, at the first block, and the scatter never runs
at all — which leaves the half of the design a real EQ change exercises
completely untested, and bit-exactness in those arms would not catch a
wrong scatter.

`DSP4_C2_BQ_NOLATCH` scatters the state back and drops the latch on EVERY
block, so the engage/disengage bookkeeping runs six thousand times a second
instead of once per user gesture. **It is bit-exact against both the scalar
arm and the latched arm, 0 of 49 output blocks each.** A gather that maps
the interleave wrongly in either direction cannot survive being run and
undone 6,000 times a second and still agree with both.

It is not a full substitute for a real coefficient swap — it never
exercises `_bq_fx_convert_N`, the crossfade blend, or the `_active_` flip —
and that gap is named in §9.

### The meters differ, and they are advisory for c2dyngold's reason

19 of 24 meter probes differ by a few tenths of a percent. They are
per-BLOCK IIRs whose 300 ms RMS window is ~56 seconds of wall clock under
`DEC=32` against a 12 second dwell, so they read a point on a convergence
curve — and the paired arm reaches a different point BECAUSE IT RUNS
FASTER. A bar scoring them is measuring its own speedup. Reported, not
scored, exactly as on 2026-09-01. `C2_MTR_AUX_01` was D79-sick on this
boot; the D81 exclusion named it and dropped that chain's seven probes.

---

## 8. What this cost in memory

Per pair, `10 x stages` words of interleaved coefficients and
`12 x stages` of interleaved state — about **6,600 words of DM across the
24 pairs**, into a block-0 that had roughly 22,000 free. Program memory:
24 drivers, and they are CHIP 2's alone. Chip 1 does not declare, link or
pay for any of it — its `.ldr` is byte-identical across the two arms.

## 9. What this session did NOT do

* **`C2_MAIN_GEQ` (28 bands), `C2_SUB_EQ` (4) and the crossover's sections
  stay scalar.** Single instances in chains of their own; pairing them
  needs the cross-chain DAG argument, the same one the four
  single-instance dynamics nodes (`C2_MAIN_COMP`, `C2_SUB_COMP`,
  `C2_MAIN_LIM`, `C2_SUB_LIM`) are still waiting on.
* **A REAL coefficient swap was never driven.** The round-trip arm covers
  the gather and the scatter at block rate; it does not cover
  `_bq_fx_convert_N`, the crossfade blend, or the `_active_` flip that a
  host EQ change actually performs. Closing it needs the chip-2 SPI
  coefficient path that `bqgraph.sh --bq` already has for chip 1, and it
  is the single most valuable thing to build next for this design,
  because the disengage path is what a user gesture reaches.
* **The EQ class's per-node cost is not attributable.** Two of the three
  ladder points are above the instrument's resolution and the third is
  not; the whole-graph number requires the ten EQ pairs to be saving about
  565 cycles each, but the ladder cannot say so on its own.
* **Chip 1's BLOCK-32 capacity point was not re-measured**, and neither was
  chip 2's — both levers landed at block 8. Session 18's corollary that
  this kernel predicts 10.11 c/band-sample paired at BLOCK 32 is still a
  prediction.
* **D80 stays open.** Nothing here touches it.

---

## 10. Where the remaining 179,556 cycles are — the section map

Session 18 priced the last lever, "hoisted LIM/COMP/GATE/DLY/XOVER
kernels", at about 90 MHz. **That price is stale, and this is the
measurement that retires it.** It was set when chip 2's signal nodes ran
under the generic per-block wrapper; the dynamics and biquad pairing has
since moved 76 of them onto pair drivers, and **only 43 nodes still
execute the wrapper at all.**

Measured with the same instrument at section boundaries rather than at
single nodes, so every difference spans a whole run of the chain and sits
far above the point-to-point spread that made the per-node ladder
unreliable:

| section | cycles | share |
|---|---|---|
| input / fabric head (0–46) | 17,234 | 9.6% |
| **12 aux chains (47–106)** | **80,273** | **44.7%** |
| 4 group chains (107–118) | 26,608 | 14.8% |
| main chain + 4 main outs (129–144) | 32,404 | 18.0% |
| sub chain (119–124) | 8,412 | 4.7% |
| FX (145–156) | 6,539 | 3.6% |
| USB / BT / mix (125–128) | 6,263 | 3.5% |
| monitor (157–159) | 1,818 | 1.0% |
| DCA / ST_OUT / codec tail (160–196) | 214 | 0.1% |
| **total** | **179,765** | 109.7% of budget |

(179,765 is a third boot of the paired arm against 179,460 and 179,556 —
0.17% spread.)

**THE EIGHT GEQ PAIRS ARE ~46,000 CYCLES, 26% OF THE WHOLE CHIP.** The aux
and group sections are 59.5% between them and the cascade is most of both.

### A ladder-position defect found and fixed on the way

A meter riding on a PAIRED node kept its SCALAR-chain position in the
`DSP4_NODE_LIMIT2` guard: `C2_MTR_GRP_01` runs at position 112 and was
guarded on 184. Harmless at `limit2 = 0` — the guard is always true and
the whole-graph image is unchanged — and wrong for every cut in between,
which is exactly where a cost ladder lives: a cut anywhere between the two
ran the group pair without its meter and charged the meter to whichever
section happened to contain 184. Fixed by giving a meter its source's
position when the source is inside a pair entry.

## 11. The wrapper trim — the hoisting lever at its real size

The generic wrapper carried a sample index in DM: load it, store it to
`_sample_idx`, reload it, increment it, store it back — **five
instructions a sample to drive a guard that only ever asks whether the
index is ZERO.**

Sample 0 is now peeled and run with `_sample_idx = 0`, the word is set to
1, and the remaining BLOCK−1 samples run with the guard shut. The
block-rate conversions still fire exactly once per block, which is the
only property the guard exists for.

**EVERY ONE OF THE 119 WRAPPED BODIES WAS AUDITED BEFORE THIS WAS
WRITTEN**, and the audit is the reason it is safe: all of them compare
`_sample_idx` against 0 and none reads it for anything else. That check
was not a formality — **the `C2_RECV_*` stimulus nodes read
`_sample_idx & 1`** to alternate the profile square, and would have broken
silently under this change. They carry their own block form and are not
wrapped. Chip 1 has NO wrapped nodes at all, so it cannot be affected.

The four nodes carrying a wide meter block used the sample index to place
each sample; they now use a walking sink pointer like every other stream.

**Measured: 179,594 (mean of three boots) → 178,684, a saving of about
910 cycles a block.** Predicted 1,634 from 43 nodes × 38 cycles, so the
instruction accounting is 56% optimistic and that is stated rather than
quoted as the prediction. It is outside the 305-cycle spread of the three
prior boots — 776 below the lowest of them — so it is real, and it is
**about 10 MHz of the 96 that were needed.**

`c2gold.sh` is the bar for this change, because it compares the
block-kernel build against the PER-SAMPLE REFERENCE — which is what the
wrapper implements. **49 of 49 node output words bit-identical.** Its
meter arm reports 19 of 24 differing and that is **D80, reproduced, not a
regression**: session 18 recorded the identical count and signature before
this change existed — peaks LOW in the block arm (−0.50 to −0.60% here),
RMS HIGH (+0.32 to +0.40%), opposite directions so not a gain error,
confined to the GATE/COMP-engaged chains, worst 0.598% against session
18's 0.896%. Had the trim broken the block-rate guard the node outputs
would have diverged grossly rather than agreeing bit for bit.

## 12. The dynamics pair latch — PRICED AND NOT BUILT

The obvious next move was to give the dynamics pair drivers the latch that
paid so well on the biquads. **It is worth 2.2 MHz, and it would also be
wrong.**

All a latch could remove is the PARAMETER gather, and it is tiny and does
not scale with anything:

| kernel | parameter words | gather/pair/block | pairs | total |
|---|---|---|---|---|
| `_lim_pair_blk` | 12 | 24 cycles | 8 | 192 |
| `_comp_pair_blk` | 16 | 32 cycles | 4 | 128 |
| `_gate_pair_blk` | 10 | 20 cycles | 2 | 40 |
| | | | | **360** |

Everything else those drivers do per block is the SIGNAL interleave (28
words in, 28 out per pair) and the two block copies, and a latch cannot
touch either — the signal is new every block by definition. The biquad
latch paid 61,258 cycles because a 28-band cascade gathers **308 words**
of coefficients and state per pair per block and the figure scales with
the stage count; the dynamics gather 12 to 16 words, fixed.

**AND IT WOULD BREAK THE CONTROL PLANE.** `C2_AUX_LIM_01.asm:132` writes
`_lim_attq_` inside the `_sample_idx == 0` guard at line 123: the dynamics
RE-CONVERT their control parameters every single block, by design, which is
what makes sample 0 bit-identical to the scalar path by construction.
Latching them would freeze threshold, ratio and attack at their
first-block values. The biquads were latchable precisely because
coefficients change only on an explicit swap and `_swap_pending_` is a
sound invalidation signal. **The dynamics have no equivalent, because
there is no unchanged state to latch.**

## 13. So where would the last 96 MHz come from? Not from one lever.

| candidate | worth | status |
|---|---|---|
| wrapper trim | ~910 cycles (~5 MHz) | **done, measured** |
| cross-chain pairing of the 4 single-instance dynamics | ~4,500 cycles (~27 MHz) | needs the deferred DAG argument |
| dynamics pair latch | 360 cycles (~2 MHz) | priced, declined — see §12 |
| the rest | ~10,000 cycles | **inside the cascade** |

Everything reachable without touching the D5 numeric contract comes to
roughly 6,000 of the 15,716 cycles needed. The remainder is in the GEQ
cascade, which is 26% of the chip and whose floor session 18 established
at **5.94 cycles per band-sample with a zero-cost round and saturate**,
against 12.83 today. Eleven of its nineteen inner-loop instructions ARE
the numeric contract — the 64-bit extract, the branch-free saturate, the
error-feedback MAC — so closing that gap is the LF-accuracy and
noise-floor decision D5 already made, not an optimisation.

**Chip 2 at 109.6% is not one lever away from fitting.** It is one product
decision away, or one more channel of headroom away.
