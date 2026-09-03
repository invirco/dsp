provenance: AI-drafted 2026-09-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The headroom guard, WIRED — sized on the part, measured in the graph, and the dynamics priced

*2026-09-03, session 23. Follow-on from the round-once landing
(`dsp4-roundonce-land-20260903.md`), which ended on: "the guard is a
RIG — nothing computes H at parameter-load in the firmware, nothing
carries it in the coefficient block, and no node calls the guarded
kernel. Dynamics envelopes carry the same wrap argument and are still
unpriced."*

Both are closed. The guard is wired end to end and its cost is a
whole-graph measurement rather than an estimate; the dynamics envelopes
turn out not to carry the same argument at all, and the reason is
provable rather than measured.

---

## 0. The one-line result

**Chip 2, whole graph, block 16, one bench session: the contract is
306,939 cycles (93.67% of budget), round-once alone is 262,970 (80.25%),
and round-once WITH THE GUARD is 264,741 (80.79%) for the 94% of the
design space that needs no headroom and 269,397 (82.21%) with both
scaling passes live on every cascade.** So the true cost of the
fixed+guard option is **80.8% typical, 82.2% worst case, against 93.7%
today** — and the guard's own share of that is **0.54% typical, 1.96%
worst case** against the 13.4% the deletion freed.

**The sizer is real and it agrees with its model on the part**: over
seven worst-case cascades — including a 28-band GEQ, which is 28,672
stage-samples of impulse response — `lib/bq_headroom.asm` computes
exactly the H `tools/dsp/bq_h_load.py` computes, and the guarded kernel's
whole output stream hashes to the guarded model's.

**And the before/after is on the part, not asserted**: over matched-sign
drive at 0 dBFS the unguarded round-once cascade inverts sign against
float on 72 of 896 words, on exactly the three of seven cascades the
model names; guarded, on **none**.

---

## 1. Where H comes from, and why it is not where anyone would first put it

The guard needs `‖h‖₁` over the worst PARTIAL cascade, at
parameter-load, on the part. The offline sizer
(`bq_headroom_guard.py`) gets it by running the impulse response to
convergence — up to 60,000 samples. **That is not an algorithm a DSP can
run**: a 20 Hz Q10 section has a pole radius of 1 − 6.5e-5, so
convergence is a quarter of a million samples, and a 28-band GEQ is
twenty-eight of them.

Three things had to be got right, and the first two are the ones the
design turns on.

### The bound has to come from a BOUNDED run

`tools/dsp/bq_h_load.py` is the algorithm the part runs, and it is
normative for `bq_headroom.asm` in the way `fixed_ref.py` is for
`biquad_fx.asm`:

    N     = clamp(ceil(6 / (1 - r_max)), 128, 1024)
    tot  += |h_k[n]|                        per PREFIX k
    env   = max(env * r_k, |h_k[n]|)        for n >= N/2
    ‖h‖₁ <= (tot + env * r/(1-r)) * 1.125

**The decaying peak-hold and the warm-up are not refinements; without
either one the bound is useless in a different direction.** A plain
window MAX under-reads by an unbounded factor when the window lands on a
null — a 20 Hz mode has a 2400-sample period and any window a load-time
budget can afford is a fraction of one. And holding the peak from sample
zero lets **h[0], the impulse itself**, dominate `env` forever at r ≈ 1:
that alone sizes a 20 Hz Q10 peak at **H = 12 against a true H = 0**, a
factor of 2331 in the bound. Excluding the first half of the run makes
`env` an estimate of the RINGING amplitude, which is what the tail is
made of.

### The pole radius is the LARGER root, not sqrt|a2|

`sqrt|a2|` is the geometric MEAN of the two roots and is the radius only
for a conjugate pair. For real roots — every low-Q design, and every
cascade of two identical HP/LP sections — it under-reads the slow one,
which both shortens the run and shrinks the tail term. **Both errors are
in the unsafe direction for a bound whose whole job is to be an upper
one.** Found by validating the load-time sizer against
`bq_state_bound.l1_norm` and getting 8,669 of 37,105 sets under it;
`bq_state_bound.py` had the same defect and is fixed here too, so the
number that work reports is now an upper bound in the real-pole cases as
well.

### What it costs against the offline sizer

`bq_h_load.py --check` is the bar, and it is two-sided: the bound must
never fall below the converged `‖h‖₁`, and it must not be so loose that
it spends headroom nobody needed.

| | offline | load-time |
|---|---|---|
| H = 0 | 35,653 | 34,958 |
| H = 1 | 1,338 | 1,907 |
| H = 2 | 114 | 240 |

Over 37,105 quantised single stages the load-time bound is **never below
the converged norm**, its median ratio is 1.125 — the safety factor, and
nothing else — and **97.79% of the space gets the same H the offline
sizer picks; 2.21% pays one extra bit.** H = 0 still covers **94.2%** of
the space. On the named cascades the cap bites only on the 28-band GEQ,
which comes out at 3.2× and pays one bit.

### It runs in the MAIN LOOP, and that is the whole design

A 28-band GEQ is 28 × 1024 = **28,672 stage-samples**. Inline in block
work that is several blocks of arithmetic, with the size of the hit a
function of how many nodes an operator happened to move at once — the
shape of bug that only ever appears in front of an audience. So the
engine runs from `main.asm`'s idle spin, `DSP4_BQHR_BUDGET` samples per
pass, **one job at a time**: a node that asks while it is busy is told
so and asks again next block, which is what bounds a whole-console
recall to N times as LONG rather than N times as much CPU at once.

**The graph's per-block cost of the sizing is therefore zero.** The only
thing it spends is latency — the crossfade does not start until H is
written, which is about a millisecond and a half for a four-band EQ.
No race is possible: the node graph runs from the main loop too, so the
engine and the nodes that talk to it are serialised by construction.

---

## 2. What the kernels do with it

H is the **first word of every cascade's coefficient block** — one word,
two interleaved for a SIMD pair, so the two strips of a pair can carry
different headroom (the shift amount is a register and each PE shifts by
its own). All four fixed cascade kernels read it, and:

* **H = 0 jumps over both scaling passes whole**, so the sample loop is
  byte for byte the unguarded one. That is the 94% case and it costs one
  load, one test and one branch per cascade.
* **H > 0** shifts the cascade INPUT down H in a pass over the block and
  the OUTPUT back up, with the single clamp, in another. y stays
  UNSCALED in the history registers — the recursion runs at the level
  where `‖h‖₁·x` fits Q4.28 and only the word handed to the next node
  comes back up.

### The register pressure, relieved

Session 22 measured the guard's exit at **eight instructions**, because
three loop invariants (+H, −H and the saturation pattern) met exactly
one free register under round-once and two were re-read from memory
every sample. The dispatch asked whether that could be relieved cheaply.

**It is relieved by not being in the loop at all.** A dedicated pass over
the block has the whole register file, so the exit is six instructions
with no spill and the entry is three; and the pass form has a second
property the in-loop form cannot have — it is *skippable*, which is what
makes H = 0 free. The cost of that choice is that the scaling is a
second and third walk over the block rather than riding the existing
one; the graph says the trade is worth about half a percent.

### FILT became ONE cascade, and had to

FILT's block kernel has always run its HPF and LPF as a single
two-stage call, on the strength of the two coefficient arrays being
adjacent in memory. A header in front of each would have sat in the
middle of that cascade's coefficients. So under the guard the per-sample
path makes the same single call the block path makes, and the pair
carries ONE header. It is not an optimisation: the headroom is a
property of the cascade, and this is where the cascade begins and ends.

---

## 3. The measurements

### Capacity, chip 2, whole graph, block 16 — four arms, one session

`DSP4_PROFILE_SIGNAL=1`, two boots per point, minimum taken, witnesses
clean on every point (`gain_coeff=0x3F800000`, chip-2 fabric live on
MAIN_L/AUX_01/GRP_01).

| arm | cycles/block | % of 327,680 |
|---|---|---|
| contract, per-stage saturate (`RO=0`) | **306,939** | **93.67%** |
| round-once, no guard (`GUARD=0`) | **262,970** | **80.25%** |
| round-once + guard, **H = 0** (the 94% case) | **264,741** | **80.79%** |
| round-once + guard, **forced on every cascade** | **269,397** | **82.21%** |

**The instrument reproduces itself across sessions**: the contract arm
comes out at 306,939 against session 22's 307,033 (0.03%), and the
guard-off arm at 262,970 against 262,841 (0.05%) — and that second one
is also the proof that everything added this session is inert when the
guard is off.

**The guard costs 1,771 cycles typical and 6,427 forced**, 0.54% and
1.96% of budget. Session 22's rig-based estimate was 3,100–4,200 cycles
(0.9–1.3%); **the graph says the estimate was optimistic by about half
again**, which is the usual direction for a per-call cost extrapolated
from an amplified per-stage one.

### Three W0 witnesses, and two of them are unchanged

| build | chip1.ldr | chip2.ldr | bytes |
|---|---|---|---|
| `DSP4_BQ_ROUNDONCE=0` — the contract control | `23c1e662` | `e45bb82a` | 301,764 / 182,092 |
| `DSP4_BQ_GUARD=0` — the landed round-once kernel | `2249afea` | `3173acb3` | 301,732 / 182,060 |
| default — round-once + guard | `4e89e062` | `4d1d314c` | 312,196 / 191,476 |

**The first two are byte for byte the recorded witnesses.** Every line
of the guard is inside `#if DSP4_BQ_GUARD`, and the guard is defined to
follow round-once, so the contract control could not move and did not.
The image grows 10,464 bytes on chip 1 — and it grew 19,328 in the first
build, before the per-node hand-off became a CALL to `_bq_hr_node1`
instead of forty inline instructions in each of a hundred and sixty
nodes. Inline, it **overflowed `sec_swco` on chip 1** in the profiling
build, which is how the refactor got prioritised.

### The guard on the part: `bqguard.sh`

Seven worst-case cascades, 128 samples of matched-sign drive at 0 dBFS
each. The part runs the sizer for real — request, main-loop service,
poll — and then runs each cascade TWICE from ONE image, because the
header is data: writing zero to it is the whole of "turn the guard off
for this cascade", so the two arms cannot differ in anything else.

| cascade | stages | H model | H part | inversions guarded | unguarded | model |
|---|---|---|---|---|---|---|
| EQ 4-band +15/+15/−15/−15 @1k Q1 | 4 | 3 | **3** | **0** | 0 | 0 |
| 4-band all +15 dB @1k Q1 | 4 | 8 | **8** | **0** | 47 | 47 |
| 28-band GEQ all +6 dB | 28 | 3 | **3** | **0** | 12 | 12 |
| HF shelf +12 dB Q5.01 @20 | 1 | 5 | **5** | **0** | 0 | 0 |
| LF shelf +15 dB Q3.16 @20 | 1 | 3 | **3** | **0** | 0 | 0 |
| peak +15 dB Q0.1 @5k | 1 | 1 | **1** | **0** | 13 | 13 |
| FILT: HPF 20 + LPF 20k | 4 | 0 | **0** | **0** | 0 | 0 |

**Guarded stream hash `AB14B806`/`4E4813B7`, unguarded `F0A2389A`/
`C782FC68` — both MATCH the model**, so the guarded kernel is not merely
free of sign inversions, it computes the guarded model's words. Counting
inversions proves the wrap is gone; the hash proves the right words
replaced it.

**The unguarded arm is the two-sided control.** A bar that only asserted
"guarded inverts nothing" would pass on a drive that never reached the
ceiling — exactly what the zeroed-bank ladder did, and the mistake
`bqeverify.sh` was built to avoid. Here 3 of 7 cascades invert sign
unguarded, on 72 words in all, and the host knows which.

### THE REFERENCE IS FLOAT, NOT THE CONTRACT, and that is a correction

The first version of this bar scored against the per-stage-saturating
contract and reported the cancelling cascade as "19 inversions guarded
and 19 unguarded" — which reads as the guard doing nothing. It is the
CONTRACT clipping. On a cascade whose partial gain is +33 dB the
per-stage clamp fires internally: it stays bounded, which is what it is
for, but it is not correct.

Scored against float the three arms separate the way the argument says
they should — **clipping preserves SIGN, wrapping inverts it** — and one
more thing falls out that is worth PW's attention:

| cascade | contract | unguarded round-once | guarded |
|---|---|---|---|
| EQ 4-band +15/+15/−15/−15 | **19** | 0 | **0** |
| 4-band all +15 dB | **14** | 47 | **0** |

**On the hot-prefix settings the guarded round-once kernel is MORE
correct than the kernel shipping today.** The contract's internal clamp
is not free of error, it is merely bounded; the guard removes the error
instead of bounding it.

### Bars

| bar | result |
|---|---|
| `bqguard.sh` — the sizer and the guard on the part | **PASS** (§3) |
| `bqeverify.sh` both arms, **block 8** | **PASS** — RO=0: 848 of 18,432 words, 29 of 576 cells, first at 746 — the model's prediction to the word; RO=1: 0 of 18,432 |
| `bqeverify.sh` both arms, **block 16** | **PASS** — RO=0: 1,797 of 36,864, 30 of 576 cells, first at 1,366; RO=1: 0 of 36,864 |
| `bqst.sh` — both asm cascades vs `fixed_ref` | **PASS**, 0 of 16, negative control 15 of 16 |
| `c2bqgold.sh` — chip-2 pairing | **BIT-EXACT**, round-trip 0 of 49 against both arms |
| `busgold.sh` — graph vs the stored bus capture | **GRAPH BIT-EXACT, 0 of 256**, sha256 `ba3f52ec` |
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK**, no contract file touched, no contract version moved |
| `bq_h_load.py --check` | **PASS** — never under the converged norm on 37,105 sets |
| W0 controls | **both prior witnesses byte for byte** |

`bqeverify` at block 16 closes the last "still open" item the landing
left: the arithmetic is now shown bit-exact at the shipping block size,
not only at the repo tree's 8.

*(`bqeverify` builds both arms with `DSP4_BQ_GUARD=0`, deliberately. Its
question is whether the round-once ARITHMETIC is the round-once model;
the guard is a separate question with its own bar, which checks the
guarded kernel word for word. Building the guard in as well also does
not fit — the shootout ladder, the verify rig and the guard together
overflow `sec_swco` on chip 1, and a debug instrument is the wrong place
to spend the last of chip 1's PM.)*

---

## 4. The dynamics, priced — and they are not the same argument

RIG C's last open item, in its own words: *"dynamics envelopes carry the
same wrap argument and were not priced at all."* They do not, and the
reason is structural.

### The envelope cannot overflow, and it is a proof rather than a bound

    env' = env + alpha * (x - env) = (1 - alpha) * env + alpha * x

`alpha` is a **Q0.31 word, so 0 ≤ alpha < 1 by format**. Therefore
`|env'| ≤ max(|env|, |x|)` every sample, and by induction `|env|` never
exceeds the largest input it has seen. Equivalently: the smoother's
impulse response is `alpha·(1−alpha)ⁿ`, which is **non-negative**, so
`‖h‖₁ = ΣΗ[n] = H(1) = 1` **exactly** — the very norm the guard is sized
on is one, for every attack and release time in the range.

**The attack/release switch does not break it**, which is worth saying
because a switched system usually does break a bound proved for a fixed
one: the bound holds per sample for whichever alpha was chosen, both are
in [0,1), and the max is over both.

`tools/dsp/dyn_state_bound.py` exercises it rather than asserting it —
attack 0.05–500 ms × release 1–5000 ms × four adversarial drives
including the worst switching pattern. **Worst `|env| / max|x|` over the
whole sweep: 1.000000.** Headroom the guard would size: **0**.

### The gain computer has room in every intermediate

Swept over threshold × ratio × knee × the whole input range, each
log-domain intermediate against its own format's ceiling:

| quantity | format | ceiling | worst | headroom |
|---|---|---|---|---|
| `lvl` | Q6.25 | 64.0 | 28.00 | 2.3× |
| `over` | Q6.25 | 64.0 | 28.00 | 2.3× |
| `t` (knee) | Q6.25 | 64.0 | 3.96 | 16.2× |
| `t²` | Q6.25 | 64.0 | 15.67 | 4.1× |
| `gr` | Q6.25 | 64.0 | 12.84 | 5.0× |
| gain | Q4.28 | 8.0 | 1.00 | 8.0× |

### What round-once would delete there, and what would wrap

* `_envq_fx` has **no saturate at all**, and correctly so:
  `fixed_ref.envelope_step`'s `sat32` provably never fires, so the asm
  omitting it is an identity and not a shortcut.
* `_exp2q_fx` has **one** saturate, on the log2 → linear conversion, and
  it is **feed-forward**. Deleting it would wrap a large positive gain to
  a NEGATIVE one — a polarity inversion of the whole strip — for one
  instruction on a branch that is already there. Nothing to win.
* `_mrf_rns28[_simd]` is the Q4.28 extract-and-saturate where the gain is
  APPLIED. That is the GAIN path's round-once question and RIG C already
  priced it (9.03 → 3.55 c/sample/strip, with the D20 mic-pre tap
  returning the whole saving). It is feed-forward: the wrap it would
  allow is a clipped sample, not a state that rings on it.

**So the dynamics envelopes need no guard, and not because they are
gentle: because `‖h‖₁` = 1 exactly for a one-pole smoother with a
non-negative impulse response, against 378 for the worst biquad in the
same design space. The per-cascade headroom pattern does not transfer
because the hazard does not.**

### The one place it DOES transfer, and it is not wired

The gate's and talkback's **sidechain filters are biquads** and do carry
the argument. Swept over HPF × LPF × Q, the sidechain cascade reaches
**`‖h‖₁` = 150.7 — H = 5 — at HPF 8 kHz / LPF 8 kHz / Q 10**, a setting
the node's parameter string allows and a recalled preset can contain.
Those blocks carry the guard's header word for shape and **nothing sizes
them; they are left at H = 0.**

**The reason is not the guard, it is the conversion**: those nodes call
`_bq_fx_convert_N` on EVERY invocation while their filter is on, not
once per parameter change, so there is no parameter-load moment to hang
a control-rate sizing off — and a per-sample sizer is not a thing.
Converting them when the parameters change, which is also several
hundred cycles a sample of pure waste, is the fix and it makes them the
same shape as every other cascade in the tree.

---

## 5. What this says, plainly

1. **The fixed+guard option is fully costed now, in the graph and not
   from a rig: chip 2 at 80.79% typical and 82.21% worst case, against
   93.67% for the contract.** The guard's share is 0.54%/1.96%.
2. **The sizing is real, runs where it cannot hurt audio, and agrees
   with its model on the part** — including on a 28-band GEQ, where the
   engine grinds 28,672 stage-samples of impulse response through the
   idle spin between blocks.
3. **The overflow guarantee is demonstrated, not asserted**: 72 sign
   inversions unguarded on the cascades the model names, zero guarded,
   and the guarded stream hashes to the model word for word.
4. **The guard makes the fixed path more correct than the contract on
   hot-prefix settings**, because the per-stage clamp bounds the error
   rather than removing it.
5. **The dynamics envelopes are not the same problem** and need nothing.
   The sidechain filters are, and are the one cascade class in the tree
   still unsized — measured, bounded at H = 5, with a named fix.
6. **Still open**: the sidechain conversion (above); `bq_h_load`'s cap
   costs the 28-band GEQ one headroom bit that the offline sizer would
   not spend; and the guard has been measured for CYCLES in the graph
   but the graph has never been run with a non-zero H from a real
   coefficient swap — chip 2 is not configured on this bench, so the
   forced-H arm is the closest thing, and it is a cost measurement
   rather than an audio one.

---

## 6. Files

* `SHARC/src/lib/bq_headroom.asm` — the sizer, the main-loop engine, and
  the per-node hand-off (`_bq_hr_node1`, `_bq_hr_ask`, `_bq_hr_ask2`)
* `SHARC/src/lib/biquad_fx.asm` — `DSP4_BQ_GUARD` in all four kernels,
  the header word, the entry/exit passes
* `tools/dsp/bq_h_load.py` — the load-time sizer, normative for the asm,
  with `--check` as its bar
* `tools/dsp/bq_state_bound.py` — pole-radius fix (the larger root)
* `SHARC/src/lib/bq_guard_test.asm`, `SHARC/bqguard.sh`,
  `SHARC/bqguard_run.sh`, `tools/dsp/gen_bqg_vectors.py`,
  `tools/pi/dsp4_bqg_verify.py` — the on-part bar
* `tools/dsp/dyn_state_bound.py` — the dynamics pricing
* `tools/dsp/dsp_codegen.py` — the header word, the sizing hand-off, the
  interleave counts, in every family that owns a cascade
* `SHARC/build.sh`, `SHARC/sigprofile2.sh` — `DSP4_BQ_GUARD` and
  `DSP4_BQ_GUARD_FORCE` threaded through, so the arms are paired
  measurements on one instrument
* Costs: `dsp4-function-costs.csv`, session 23
