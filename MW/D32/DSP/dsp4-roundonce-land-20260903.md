provenance: AI-drafted 2026-09-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Round-once, LANDED — validated, measured in the graph, and the guard priced

*2026-09-03, session 22. Follow-on from RIG C
(`dsp4-roundonce-rigc-20260902.md`) under PW's standing ruling: take the
per-stage SATURATE deletion, keep the error feedback, adopt no arm that
deletes it, treat headroom as a separate per-cascade control-rate design.*

Three things happened, in the order the dispatch required them: the
bit-identity claim was **validated on the asm** instead of on the Python
model, the deletion was **landed in the shipping kernels** and re-measured
**in the graph on both chips**, and the per-cascade `‖h‖₁` headroom guard
— the one thing RIG C priced and never built — was **built far enough to
measure and to test**.

---

## 0. The one-line result

**Chip 2 goes 93.70% → 80.21% of budget and chip 1 goes 92.88% → 88.89%,
measured whole-graph at block 16 on the part, both arms in one session on
one instrument.** The landed kernel is **0-ULP identical to the contract**
over 18,432 output words of a 192-cascade DEFS curve set — and identical
*exactly where the model says nothing overflows*, diverging on exactly the
29 of 576 (cascade, level) cells `fixed_ref` predicts and no others.
**The guard that restores the overflow guarantee costs 162.6 cycles per
cascade per block, about 1.3% of chip 2's budget against the 13.5% the
deletion freed**, and holds every named worst case — including the
four-band all-+15 dB cascade at `‖h‖₁` = 1285 — with **no internal wrap
and a worst response error of 0.0105 dB against a 0.046 dB bar**.

---

## 1. VALIDATED — the gap RIG C left open, closed

RIG C's own "still open" list opens with it: *"C·E is TIMED, NOT
VALIDATED. The ladder runs zeroed banks... the bit-identity claim is
measured on the PYTHON model, not on `_bqe_cascade_simd`. A diff of the
kernel against `fixed_ref` is the next bar and it does not exist."*

It exists now: `SHARC/bqeverify.sh`, `src/lib/bqe_verify.asm`,
`tools/dsp/gen_bqe_vectors.py`, `tools/pi/dsp4_bqe_verify.py`.

**What it runs.** 192 four-stage cascades — twelve named worst cases from
the state-bound work (the HF shelf +12 dB Q5.01, the four-band coherent
+15 dB, the LF shelf D5 was decided on, the FILT chain, a GEQ, a bypass
control) plus a stratified sample of the DEFS design space, 768 design
points in all — at three drive levels (−20 dBFS pseudo-random, −6 dBFS
square, 0 dBFS square) over four consecutive blocks. Both kernels run
over byte-identical words inside the DSP with their own state, the two
output blocks are diffed on-chip, and each arm's **whole** output stream
is reduced to an order-sensitive hash and a running 32-bit sum.

**Why the hash and not a capture.** Two asm arms agreeing proves they
agree; it does not prove either is the ruled arithmetic — the same gap
`dsp4_bq_verify.py` was written to close for the fused cascade. The host
recomputes both hashes from `fixed_ref` over the identical vectors, so
18,432 words of full-coverage model equivalence come off the link as two
words.

**And the divergence bitmap is the two-sided control**, which is the part
that makes this a bar rather than an assertion. A test that only asserted
"zero differences" would pass on a rig that never drove anything hard
enough to saturate — precisely what the zeroed-bank ladder did. So the
host predicts *which* (cascade, level) cells diverge and the part must
diverge on exactly those:

| arm A | hash/sum A | hash/sum B | A vs B | bitmap |
|---|---|---|---|---|
| `DSP4_BQ_ROUNDONCE=0`, the saturating contract | `8AD9CE2B / 85A57384` — **matches `fixed_ref.biquad`** | `522C6AAF / C55541BB` — **matches the round-once model** | **848 of 18,432 words, first at 746, max \|d\| 2147438683 — the model's own prediction, to the word and the index** | **29 of 576 cells, MATCH** |
| `DSP4_BQ_ROUNDONCE=1`, the LANDED kernel | `522C6AAF / C55541BB` | `522C6AAF / C55541BB` | **0 of 18,432** | **0 of 576** |

**So the claim is now stated in a form that could have failed, and did
not**: over 547 of 576 (cascade, level) cells the round-once kernel is
bit-for-bit the contract, and the 29 that differ are the ones `‖h‖₁` says
overflow. The landed kernel is byte-identically the validated arm.

*(The bar found two defects in itself before it found none in the kernel.
The first run scored a correct part as a mismatch because the model took
`abs(a − b)` in Python while the part computes a 32-bit **wrapping**
subtract followed by `Rn = ABS Rx` with ALUSAT clear and a **signed**
compare — a true |difference| does not fit in 32 bits once an arm has
wrapped, so the metric has to be defined by the instruction. The second
read the landed arm as a dead link, because `_bqev_first` is −1 when
nothing differs and 0xFFFFFFFF is how this link answers a dropped
transaction; every reader in the tree throws that word away. Both are
fixed in the instrument, not worked around in the score.)*

---

## 2. LANDED — the deletion in the shipping kernels

`DSP4_BQ_ROUNDONCE` (default **1**) removes the per-stage saturate from
**all four** fixed cascade forms — `_bq_fx_cascade_N`, the fused and
unfused `_bq_fx_cascade_blk`, and `_bq_fx_cascade_simd` — so the scalar
node bodies, the block kernels and the paired graph cannot disagree about
the arithmetic. The error feedback is untouched everywhere.

**The control is PROVED, not assumed.** `DSP4_BQ_ROUNDONCE=0` rebuilds
W0 **byte for byte**: `23c1e662 / e45bb82a`, 301,764 / 182,092 bytes.
Nothing outside the guarded lines moved.

**W0 MOVES, and it is meant to.** The shipping default now builds
`2249afea / 3173acb3`, 301,732 / 182,060 bytes — 32 bytes smaller on each
chip, all of it `lib/biquad_fx` (448 → 414 bytes of code, the seven
instructions of `_bq_fx_cascade_N`'s clamp; the default image carries
`DSP4_BLOCK_KERNELS=0`, so the block and SIMD kernels are not in it and
the graph builds that use them shrink by more).

### Capacity, in the graph, both chips, both arms, one session

Whole-graph, block 16, `DSP4_PROFILE_SIGNAL=1`, two boots per point,
minimum taken, witnesses clean (`gain_coeff=0x3F800000`, chip-2 fabric
live on MAIN_L/AUX_01/GRP_01, pool parity `even`):

| | contract (`RO=0`) | round-once (`RO=1`) | freed | budget 327,680 |
|---|---|---|---|---|
| **chip 2** whole graph | **307,033** | **262,841** | **44,192** | **93.70% → 80.21%** |
| **chip 1** whole graph | **304,363** | **291,264** | **13,099** | **92.88% → 88.89%** |

**The instrument reproduces session 19 to 0.03%**: 307,033 against the
306,950 the capacity decision was taken on, from another session and
another operator of the same script. And **the graph beats the rig's
prediction**: RIG C's two-point fit said 40,850 cycles off chip 2 and
12.5% of budget; the graph gives 44,192 and 13.5%. Chip 1's 13,099 is
4.00% of budget, which is the FILT and EQ classes of 32 strips.

### The standalone ladder agrees, and says so by collapsing

At block 16 the shootout ladder now reads **rung 1 (`_bq_fx_cascade_blk`)
= 14.49 and rung 14 (`_bqe_cascade_blk`) = 14.49; rung 2
(`_bq_fx_cascade_simd`) = 7.26 and rung 15 (`_bqe_cascade_simd`) = 7.26**.
The shipping kernels and RIG C's arms have become the same number because
they have become the same arithmetic — an independent confirmation of the
landing that needed no new instrument.

### Bars

| bar | result |
|---|---|
| `bqeverify.sh` both arms | **PASS** (§1) |
| `bqst.sh` — both asm cascades vs `fixed_ref` | **PASS**, 0 of 16, negative control fires 15 of 16 |
| `busgold.sh` — graph against the stored bus capture | **GRAPH BIT-EXACT, 0 of 256**, sha256 `ba3f52ec` |
| `c2bqgold.sh` — chip-2 pairing | **BIT-EXACT**; NEGCTL moved 6 of 6 channel-B and 0 of 2 channel-A; round-trip 0 of 49 against both arms |
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK**, no contract file touched, no contract version moved |

`busgold` is reported with its own warning intact: its capture is taken
with **bypass biquad coefficients and unity gain**, so it cannot see a
biquad numeric change at all. It is evidence the rest of the graph did
not move, not evidence about the cascade. The cascade's evidence is
`bqeverify` (192 real cascades, 18,432 words), `bqst` (asm against
`fixed_ref`) and `c2bqgold` (the paired chip-2 graph against its scalar
twin).

---

## 3. PRICED — the per-cascade `‖h‖₁` headroom guard

RIG C: *"headroom sized on `‖h‖₁` per cascade at PARAMETER-LOAD time...
that variant was priced by instruction count and NEVER BUILT; it is the
honest next spike."* Built, measured and tested here, in both halves.

### The design

At parameter-load, once per coefficient swap, take the worst `‖h‖₁` over
every **partial** cascade — the wrap happens *inside*, in y1/y2, so a
prefix that overflows overflows whether or not the full cascade's gain
comes back down — and pick

    H = max(0, ceil(log2(‖h‖₁ · xmax / 8)))

Then the cascade **input** is shifted down H bits on entry and the
cascade **output** is shifted back up and saturated once on exit. The
recursion lives at the scaled level where it is representable; only the
word handed to the next node comes back up. **y stays UNSCALED in the
history registers — that is the whole design, and it is why a per-cascade
CLAMP does not work and a per-cascade SCALE does.**

### The cycles, measured

`bq_shootout.asm` rungs 16 and 17, block 16, 28 stages, paired. The real
guard applies its two shifts **once per cascade**, which on a 28-stage
bank is 1/28 of a cycle and below the instrument's resolution — so the
cost is measured **amplified**, with the scale on every stage, and
divided:

| rung | c/call | c/band-sample | delta vs rung 15 |
|---|---|---|---|
| 15 `_bqe_cascade_simd` (landed) | 6504.4 | 7.26 | — |
| 16 entry scale, every stage | 6982.0 | 7.79 | **+477.6 c/call = +0.533/band-sample** |
| 17 exit scale + single clamp, every stage | 10578.8 | 11.81 | **+4074.4 c/call = +4.547/band-sample** |

The entry is ONE instruction and measures 0.533 c/band-sample paired —
half an instruction per band-sample, which is what "paired" means and is
the instrument agreeing with itself. **The exit is EIGHT, and the reason
is register pressure**: it needs three loop invariants (+H, −H and the
saturation pattern) and under round-once exactly **one** register is free
(r15, which used to hold the saturation pattern), so two of them are
re-read from memory every sample. A kernel that could hold all three
would be six instructions and about 3.0 c/band-sample amplified.

**Per cascade per block of 16, per SIMD pair: 17.1 cycles entry + 145.5
exit = 162.6 cycles.** What that is worth depends entirely on cascade
depth, and this is the number to argue about:

| cascade stages | guard c/band-sample | total | vs today's 11.30 |
|---|---|---|---|
| 1 | 5.080 | 12.34 | **0.92×** — *worse than today* |
| 2 | 2.540 | 9.80 | 1.15× |
| **4** (EQ) | **1.270** | **8.53** | **1.32×** |
| 6 | 0.847 | 8.11 | 1.39× |
| 28 (GEQ) | 0.181 | 7.44 | 1.52× |

**The first row is the finding nobody has stated**: on a ONE-stage call
the guard costs more than the per-stage saturate it replaces, because the
per-stage clamp *is* the per-cascade clamp when there is one stage — and
FILT calls the cascade once per section. A guard wired in must therefore
be skipped where H = 0, which is free to decide (H is already a
control-rate word) and is what 96% of the design space wants anyway.

**Chip 2, estimated from the measured per-cascade cost.** The graph has
38 cascade instances (21 `EQ_BIQUAD` + 17 `GEQ`), of which `c2bqgold`
witnesses 24 running as 12 paired calls. At 162.6 cycles per paired call
and roughly twice that per channel scalar, the guard costs **3,100–4,200
cycles/block = 0.9–1.3% of budget** against the **13.5%** the deletion
freed: **chip 2 lands at ~81.2–81.5% instead of 80.21%, against 93.70%
today.** This is an estimate from a measured per-cascade cost, not a
whole-graph measurement — the guard is not wired into the graph.

### The numbers, tested (`tools/dsp/bq_headroom_guard.py`)

Sizing is done on the **de-quantised** coefficient words, not on the RBJ
design, so what is bounded is the filter the part runs. `‖h‖₁` is summed
over the recursion with the length chosen from the pole radius and
whatever is still moving at the cap **bounded and added**, so every
number is an upper bound and never a truncation that flatters the guard.
Wraps are counted under **matched-sign drive at 0 dBFS** — the input that
achieves `‖h‖₁` — because a square wave at f0 reaches only max|H|, which
is exactly why sizing headroom off an EQ curve is the mistake.

| cascade | `‖h‖₁` | H | wraps, unguarded | wraps, guarded | err unguarded | err guarded | floor guarded |
|---|---|---|---|---|---|---|---|
| FILT: HPF 20 + LPF 20k | 3.8 | 0 | 0 | **0** | 0.0000 | 0.0000 | −155.9 |
| peak +15 dB Q3 @1k | 6.9 | 0 | 0 | **0** | 0.0000 | 0.0000 | −164.7 |
| peak +15 dB Q10 @20 | 7.3 | 0 | 0 | **0** | 0.0000 | 0.0000 | −146.6 |
| peak +15 dB Q0.1 @5k | 9.8 | 1 | **114** | **0** | 0.0000 | 0.0000 | −161.5 |
| LF shelf +15 dB Q3.16 @20 | 20.7 | 2 | 3 | **0** | 0.0000 | 0.0093 | −139.1 |
| HF shelf +12 dB Q5.01 @20 | 93.9 | 4 | 10 | **0** | 0.0000 | 0.0066 | −124.6 |
| 4-band EQ, mixed | 4.0 | 0 | 0 | **0** | 0.0000 | 0.0000 | −160.7 |
| **4-band all +15 dB @1k Q1** | **1285.0** | **8** | **4666** | **0** | 0.0000 | **0.0011** | −81.1 |
| 28-band GEQ all +6 dB | 18.8 | 2 | **2989** | **0** | 0.0000 | 0.0105 | −117.5 |

*Wraps over 8,000 samples of matched-sign drive. The HF shelf's `‖h‖₁` of
93.9 is the state-bound work's 97.3 arrived at independently, from the
quantised words rather than the RBJ design.*

**Every row is inside the 0.046 dB golden bar, worst 0.0105 dB, and no
guarded cascade wraps once.** The unguarded column is what shipped today
and is the reason the guard is worth building: the four-band all-+15 dB
setting — which the DEFS ranges allow and a console operator can dial —
wraps **4,666 of 8,000** samples under worst-case drive, and the 28-band
GEQ at a uniform +6 dB wraps 2,989.

**And this is where per-cascade sizing changes the answer RIG C
reached.** RIG C priced a FIXED H and found that at H = 8 the LF shelf
costs 5.74 dB — a hundred and twenty-five times the bar, worse than
float on the very axis D5 was decided on. **Sized per cascade, only the
cascade that needs H = 8 pays it, and that cascade's own error at H = 8
is 0.0011 dB**, because its signal is +62 dB and its quantisation floor
is irrelevant against it. The LF shelf pays H = 2 and 0.0093 dB. The
fixed-H result and the per-cascade result are not the same measurement
and should never have been quoted as one.

*(The noise-floor column is measured at a drive backed off far enough
that the exit clamp does not fire, and the level used is reported by the
script. A four-band +15 dB EQ driven at −20 dBFS puts +42 dBFS on its
output; measuring the clipping residual and calling it a noise floor is
the error the first run of this script made.)*

### H over the DEFS design space

Single stages, 0 dBFS drive, `‖h‖₁` from `bq_state_bound.l1_norm` on the
de-quantised words, over the full 869,627-set grid:

| H | sets | share |
|---|---|---|
| **0** | **838,080** | **96.37%** |
| 1 | 26,068 | 3.00% |
| 2 | 4,529 | 0.52% |
| 3 | 224 | 0.03% |
| 4 | 484 | 0.06% |
| 6 | 242 | 0.03% |

Worst single stage `‖h‖₁` = 378.3 (+51.6 dB), an LF shelf at 20 Hz,
+10.5 dB, Q 6.31. That is larger than the state-bound work's 97.3 because
this bounds the QUANTISED filter and adds the analytic tail — which at
the worst corner is 11% of the sum, so the number is a genuine upper
bound and a loose one for poles this close to the unit circle. Sizing H
off an upper bound is the correct direction of error: it can only spend a
bit that was not needed, never leave a wrap unguarded.

**The settings that pay headroom are the ones running tens of dB of
gain**, and they are 3.6% of the space.

---

## 4. What this says, plainly

1. **The saturate deletion is landed, validated on the asm, and measured
   in the graph.** Chip 2 93.70% → 80.21%, chip 1 92.88% → 88.89%, both
   arms on one instrument in one session. The claim that it is
   bit-identical to the contract where nothing overflows is now a bar
   that predicts its own exceptions and passes.
2. **The overflow guarantee is what was given up, and the guard that buys
   it back is affordable**: 162.6 cycles per cascade per block,
   ~1.3% of chip 2's budget against 13.5% freed, and it holds the worst
   reachable setting inside the golden bar with no wrap.
3. **Per-cascade sizing is what makes fixed round-once work**, and it is
   a different answer from the fixed-H one RIG C priced. At fixed H = 8
   the fixed option was worse than float on the LF axis; sized per
   cascade the worst error over every named case is 0.0105 dB against
   float's 0.520.
4. **The guard is not free on short cascades and must be skipped where
   H = 0.** One-stage calls pay more than the clamp they replaced.
5. **Still open**: the guard is a rig, not a graph — nothing computes H at
   parameter-load in the firmware, nothing carries it in the coefficient
   block, and no node calls the guarded kernel. Dynamics envelopes carry
   the same wrap argument and are still unpriced. And `bqeverify` runs at
   block 8 (the repo tree's size); the arithmetic is block-size
   independent bar the unroll count, but no bit-exactness bar was run at
   block 16 this session.

---

## 5. Files

* `SHARC/src/lib/biquad_fx.asm` — `DSP4_BQ_ROUNDONCE`, all four kernels
* `SHARC/src/lib/bqe_verify.asm`, `SHARC/bqeverify.sh`,
  `SHARC/bqeverify_run.sh`, `tools/dsp/gen_bqe_vectors.py`,
  `tools/pi/dsp4_bqe_verify.py` — the validation bar
* `SHARC/src/lib/bq_shootout.asm` rungs 16/17 — the guard's cycles
* `tools/dsp/bq_headroom_guard.py` — the guard's sizing, safety and
  numeric cost
* `SHARC/sigprofile2.sh`, `SHARC/gainprof.sh` — `DSP4_BQ_ROUNDONCE`
  threaded through, so the two arms are a paired measurement
* Costs: `dsp4-function-costs.csv`, session 22
