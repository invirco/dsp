provenance: AI-drafted 2026-08-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# What a branch costs on the ADSP-21564, measured — and what that does to the AXIS 1 floors

**Review finding D66, closed by measurement.** Session 9 measured TUBE's
engaged body at 103.9 cycles/sample on the part against a ~52 c/s estimate
built by counting the emitted instructions at one cycle apiece, inferred
that the missing ~52 c/s was spread over the loop's three `call`/`rts`
pairs at ~17 c/s a pair, and stopped — because AXIS 1's floor table prices
COMP's and GATE's call fat with the *same* one-cycle-per-instruction count
that this measurement had just contradicted. This is the isolated
measurement D66 asked for.

## The instrument

`SHARC/src/lib/call_selftest.asm`, built with `DSP4_CALL_SELFTEST=1` and
read back by `tools/pi/dsp4_call_cal.py` (`SHARC/callcal.sh` drives both
halves). Eleven rungs, each an identical hardware loop over 20,000
iterations, differing only in the payload; the whole ladder runs three
times and the host takes the minimum, so a repeat the 1 kHz diag-tick ISR
landed in is discarded rather than averaged in. The window arithmetic is
`main.asm`'s own — `(ticks_end - ticks_start) * TPERIOD + (tcount_start -
tcount_end)` — which is exact per pass rather than 1 ms-quantised.

Chip 1, 491.52 MHz, block 8. Repeat-to-repeat spread across the whole
ladder is 0.01–0.41 %, and the widest of those is the null loop, where
0.4 % is two cycles.

| rung | cyc/iter | instructions issued | excess |
|---|---|---|---|
| 0 NULL — empty loop | 2.000 | 2 | +0.000 |
| 1 CALL_BARE — `call` → bare `rts` | 19.043 | 4 | **+15.043** |
| 2 CALL_NOP8 — `call` → `nop x8; rts` | 27.066 | 12 | **+15.066** |
| 3 INLINE_NOP8 — the same 8 nops inline | 10.017 | 10 | +0.017 |
| 4 CALL_RNS — `_mrf_rns28` called | 37.091 | 17 | +20.091 |
| 5 INLINE_RNS — `_mrf_rns28` inlined, one taken branch | 27.075 | 16 | +11.075 |
| 6 TUBE_CALL — TUBE's per-sample body as it ships | 103.267 | 50 | +53.267 |
| 7 TUBE_INLINE — the same body, calls inlined | 80.203 | 47 | +33.203 |
| 8 JUMP_UNCOND — one unconditional taken jump | 16.034 | 10 | **+6.034** |
| 9 INLINE_FREE — `_mrf_rns28` inlined, branch-free | 19.042 | 19 | +0.042 |
| 10 TUBE_FREE — TUBE's body inlined, branch-free | 47.121 | 47 | +0.121 |

## The model, and it closes

Four rungs with no branch in them — 0, 3, 9 and 10 — land on their
instruction count to within 0.12 cycles at 2, 10, 19 and 47 instructions.
**Straight-line code on this part issues at exactly one instruction per
cycle.** The floors in AXIS 1 assume that, and the assumption is correct.

Everything above the instruction count is paid at a *taken branch*:

| event | penalty, measured |
|---|---|
| unconditional taken `jump` | **+6.02 cyc** (rung 8 − rung 3, same 10 instructions) |
| taken conditional branch immediately after a `comp` | **+11.08 cyc** (rung 5 excess; rung 7 = 3 × 11.07) |
| `call` + `rts`, both taken | **+15.04 cyc** (rungs 1 and 2, +15.043 and +15.066) |
| `call` + a callee ending `comp; if eq rts` | +20.09 isolated (rung 4); **+17.76** measured in context inside TUBE's loop (rung 6) |

Three things this pins down that the record previously guessed at:

* **The pair cost does not depend on the callee.** Rung 1's callee is a
  bare `rts`; rung 2's is eight nops and an `rts`. They cost 15.043 and
  15.066 — the same number. This is generic branch overhead, not something
  specific to `_mrf_rns28`, which is exactly the question D66 asked.
* **It does not depend on where the callee lives.** Rungs 1 and 2 call a
  stub in the same object; rung 4 calls `_mrf_rns28` in `mac64_fx.asm`.
  Once the conditional return is accounted for, the pair costs the same.
  So the "L1 code locality / IT-buffer" hypotheses in D66 are not what is
  being seen — the mechanism is pipeline refill on a taken branch, which
  is what an 11-stage SHARC+ core with no delay slots filled will cost.
* **The penalty is additive and predictable.** Rung 7 is rung 10's 47
  instructions plus three taken conditional branches: 47 + 3 × 11.07 =
  80.2 predicted, 80.203 measured. Rung 10 is the same 47 instructions
  with the branches gone: 47.0 predicted, 47.121 measured. The prediction
  was written into the source before the rung was run.

## A third instrument, written for something else, says the same thing

`numverify.sh`'s timing arm has been in the tree since 2026-08-29 to
price the third word of the wide accumulator. It times three loops of
200,000 iterations and reports, on this session's run:

* **null loop 6.017 cycles/iteration** — its body is six instructions
  (two constants, an index load and three nops). One instruction per
  cycle, measured by a script that was not written to ask the question.
* `_acc64_mac` **29.144 cycles/MAC over the null loop**. The callee is 13
  instructions plus its `rts` (`mac64_fx.asm`), and the loop swaps one
  nop for the `call`, so the marginal instruction count is 14.
  **29.144 − 14 = 15.14 — the call/rts pair.**
* `_nst_mac_old`, the two-word form, **27.103**; the same subtraction on
  its 12-instruction body gives **15.10**.

Three numbers for the same thing from two independent instruments:
**15.04, 15.14, 15.10.** Nothing here was tuned to agree.

## The instrument agrees with the graph

Rung 6 is TUBE's per-sample body instruction for instruction
(`C1_TUBE_01.asm:70-83`). It reads **103.267 cycles/sample = 826.1
cycles/block**. Session 9 measured *the same body through the shipping
graph*, by a same-boot `TubeOn` 0→1 diff, at **829–834 cycles/block, 103.9
c/s**. The two instruments are **0.61 % apart** and share no arithmetic:
one is a node-limited graph diff over a DWELL window, the other is a
timed loop in main-loop context. Session 9's number stands, and so does
this ladder.

## What this does to the AXIS 1 floor table

**The floors do not move.** The floor column is the instruction count of
branch-free, packed, hardware-looped code, and rungs 3/9/10 prove that
form issues at exactly 1.000 cycles per instruction. Every "floor c/s"
figure in `review-dsp-20260828.md` stands as written.

**What moves is the named waste, and the ROI that follows from it.** The
review priced call fat at the same one cycle per instruction — "~9
call/rts pairs per sample ≈ 45–60 c/s" for COMP, "3 call/rts … ≈ 30 c/s"
for GATE — i.e. 5–7 cycles a pair. The measured pair is 15.04 cycles of
penalty on top of its two instructions, so those rows understate their
own recoverable cycles by about **3×**. The gap between emitted and floor
is unchanged (it was always measured); the *attribution* of the gap, and
therefore the ranking of the work that closes it, is what changes.

The pair counts below are a census of the emitted code, nested calls
included — which is the second correction, because the review counted
only the `call` instructions visible in the node file and missed the
callee's own calls.

| class | emitted c/s (blk 8) | call/rts pairs per sample, nested included | branch penalty, restated | review's figure |
|---|---|---|---|---|
| GATE (scalar) | 259.75 | 5 — `_envq_fx` ×2, `_log2q_fx` → `_polyq_fx`, `_mrf_rns28` | **~75 c/s of pairs** + ~11–22 of taken conditionals ≈ **86–97 c/s, 33–37 % of the class** | "3 call/rts ≈ 30 c/s" |
| COMP (scalar) | 433.1 | 8 — `_envq_fx`, `_compgain_fx` → `_log2q_fx` → `_polyq_fx`, → `_exp2q_fx` → `_polyq_fx`, `_mrf_rns28` ×2 | **~120 c/s of pairs** + ~25–55 of taken conditionals ≈ **145–175 c/s, 33–40 % of the class** | "~9 call/rts pairs ≈ 45–60 c/s" |
| TUBE active | 103.9 | 3 — `_mrf_rns28` ×3 | **56.1 c/s MEASURED**, not censused: rung 6 → rung 10, 103.267 → 47.121. **54 % of the class** | "~52 c/s undercount" |
| FILT (2 stages, scalar) | 136.9 | 0 pairs; 1 taken conditional per stage per sample (`biquad_fx.asm:382`) | **~22 c/s, 16 %** — previously unnamed as a cycle cost | "saturation via taken branch", unpriced |
| EQ (4 stages, scalar) | 265.75 | 0 pairs; 4 taken conditionals per sample | **~44 c/s, 17 %** | as above |
| GATE pair (paired graph) | 163.1 /channel | 3 per SIMD-sample = 1.5 /channel-sample | **~22.6 c/s/channel, 14 %** | not priced |
| COMP pair (paired graph) | 237.6 /channel | 7 per SIMD-sample = 3.5 /channel-sample | **~52.6 c/s/channel, 22 %** | not priced |

Two structural facts fall out of the census and neither was in the record:

1. **The SIMD kernels were already written branch-free and the scalar
   ones were not.** `_mrf_rns28_simd`, `_compgain_simd`, `_log2q_simd`,
   `_exp2q_simd` and `_bq_fx_cascade_simd` all saturate with a
   conditional MOVE, for a correctness reason (a conditional return would
   take PEx's flags for both channels). That decision, made for
   bit-exactness, was worth 6–11 cycles a site and nobody had counted it.
   In the FUSED + PAIRED capacity configuration the biquads therefore
   carry **no** branch penalty at all — the FILT/EQ rows above apply to
   the scalar record, not to the configuration the capacity table is about.
2. **What is left in the capacity configuration is entirely the call
   structure of the two dynamics pair kernels** — 7 pairs per SIMD-sample
   in `_comp_pair_blk` and 3 in `_gate_pair_blk`, none of them
   data-dependent. That is 75.2 cycles/sample/channel of pure pipeline
   refill in a strip that costs 837.0 (214,249 cycles/block ÷ 32 channels
   ÷ 8 samples), i.e. **9.0 % of the whole strip, in ten call sites, in
   two shared routines**.

## Which queue items changed rank

* **"Inline the call fat" goes to the top and its prize roughly triples.**
  It was sized at 45–60 c/s on COMP and ~30 on GATE. On the corrected
  model it is ~120 and ~75 in the scalar path, and 52.6 + 22.6 = 75.2
  c/s/channel in the *paired* path — which is the one the capacity table
  is measured in. Nothing else in the queue is worth that for the effort.
* **It should be done in the SHARED pair kernels first, not in the
  generated nodes.** `_comp_pair_blk` and `_gate_pair_blk` are one copy
  each for all 32 strips and both chips; inlining there costs program
  memory once. Inlining the same call sites into the 32 generated COMP
  and GATE nodes would cost it 64 times, and program memory is the wall
  session 3 already hit.
* **Branch-free saturation is a free-standing item worth having.** It is
  bit-identical by construction (the SIMD forms prove the identity is
  already relied on), costs about three instructions, and buys 11.08. On
  the scalar biquad path alone that is 22 c/s on FILT and 44 on EQ.
* **The GAIN=1MAC fold drops in relative rank.** It is worth ~21 c/s on a
  class of 22.9; the dynamics call fat is worth 75 c/s on the strip.
* **RTG stays where it was.** Its gap is a control-rate structure
  problem (D22/D23), not a branch problem — one call site.
* **TUBE is unaffected by this ranking**, per the PW plugin-group ruling.
  Its 56.1 c/s is recorded here as the *calibration* of the model, not as
  work to be scheduled.

## The strategic number

At 75.2 cycles/sample/channel recovered from the ten call sites in the two
dynamics pair kernels, and holding everything else equal:

| | before | predicted | **MEASURED after** | budget |
|---|---|---|---|---|
| 32 ch, block 8, 983.04 MHz | 214,249 (130.8 %) | ~195,000 (119.0 %) | **198,706 (121.3 %)** | 163,840 |
| 32 ch, block 32, 983.04 MHz | 657,082 (100.26 %) | ~580,000 (88.5 %) | **584,331 (89.2 %)** | 655,360 |

The predictions above were written before the measurement and are left
standing. Block 8 came in 3,700 cycles above the prediction (the graph
sees slightly less than the kernel does — 15,543 recovered against 17,280
from the per-class figure); block 32 came in 4,300 *below* it, 72,751
recovered against 69,120 predicted.

**THE MATERIAL CHANGE TO THE OUTLOOK: 32 channels on one chip at BLOCK 32
and 983.04 MHz is now 10.8 % UNDER budget, having been 0.26 % OVER.** It
had been sitting 1,722 cycles over — on the line, close enough that the
pass-rate instrument could not resolve which side of it the product was
on — and it is now 71,000 cycles inside, which is a margin the instrument
can see. One mechanical, bit-exact-by-construction change to two shared
routines did it.

**Block 8, the ruled operating point, does not reach 32 on this change**
and was never going to: it goes from 30.8 % over to 21.3 % over. It still
needs the rest of the queue, and on the corrected model the rest of the
queue is mostly more of the same — the scalar dynamics still carry 8 and 5
call/rts pairs a sample, and the scalar biquads still saturate through a
taken branch.

## The landing: the ten call sites, inlined and measured

`SHARC/src/lib/dyn_simd_inline.h` holds each helper's body once as a
macro. The standalone `_..._simd` routines in `dyn_simd_fx.asm` are kept
as the readable reference, and `tools/dsp/dyn_simd_inline_check.py`
flattens each of them — substituting every `call _x_simd;` with x's own
body, recursively — and diffs it against the macro expansion instruction
for instruction. All five match (16, 29, 45, 15 and 123 instructions),
and the checker was shown to fail: perturbing one shift in one macro
makes four of the five differ and names the first differing instruction.

`DSP4_DYN_INLINE` selects how much is inlined, so a regression bisects to
a class of inlining rather than to the whole change:

| level | what is inlined | chip1.ldr |
|---|---|---|
| 0 | nothing — every site is a `call` | `88cea050`, 394,344 bytes — **byte-identical to the pre-change build**, which is the control that says the flag is the only difference |
| 1 | `_mrf_rns28_simd` (3 sites, no nested hardware loop) | |
| 2 | + `_compgain_simd` and `_log2q_simd` with their nested `_polyq_simd`/`_exp2q_simd` (7 more sites) | 395,232 bytes, +888 |

On the part, `dynst.sh` — the scalar-vs-paired bit-exactness bar, which
runs both forms on byte-identical data inside the chip and diffs them —
with its own timing arm at 8,192 iterations (one tick = 7.5 cycles per
sample per channel, so the timing column quantises at that step):

| | COMP paired | GATE paired | bit-exact |
|---|---|---|---|
| before the change | 202.5 | 112.5 | COMP 0/32, GATE 0/32, BQ4 0/32 |
| level 0 (control) | 210.0 | 105.0 | 0/32, 0/32, 0/32 |
| level 1 | 187.5 | 97.5 | 0/32, 0/32, 0/32 |
| **level 2 (shipping default)** | **157.5** | **90.0** | **0/32, 0/32, 0/32** |

Level 1 removes one `_mrf_rns28_simd` pair from GATE's SIMD sample:
15.04 cycles over two channels is **7.5 cycles per sample per channel
predicted, and GATE moves 105.0 → 97.5, exactly one tick**. COMP loses
two pairs — 15.04 predicted per channel-sample — and moves 210.0 → 187.5,
which is 22.5, three ticks against two predicted; the instrument cannot
resolve better than ±7.5 here, so the honest reading is "one to three
ticks, consistent with the prediction", not a claim of 22.5.

**Level 2 is the one that matters and it lands where the ladder said it
would.** COMP's seven pairs were predicted to be worth 52.6 cycles per
sample per channel; **COMP measures 210.0 → 157.5, which is 52.5** — seven
ticks, and the prediction to a fifth of one tick. GATE's three pairs were
predicted at 22.6 and measure 105.0 → 90.0, which is 15.0: two ticks
against three predicted, inside the instrument's step. **Together the ten
sites are worth 67.5 cycles per sample per channel, measured**, against
75.2 predicted from a per-pair penalty measured on a completely different
instrument in a completely different loop. Bit-exactness is unchanged at
every level: scalar and paired still agree on 32 of 32 samples for COMP,
GATE and the four-stage biquad, which is what makes the saving a saving
rather than a change of arithmetic.

**A METHOD NOTE THAT COST AN HOUR AND IS WORTH RECORDING.** The first
three runs of the fully-inlined build came back with the main loop wedged
and `DMA0_STAT` at zero, and were nearly written up as a hang caused by
nesting `_polyq_simd`'s hardware loop inside the pair kernel's. They were
not: **two `dynst.sh` runs were on the bench at once**, each booting the
card out from under the other. The level-0 control — an image proven
byte-identical to a build that had already passed — reproduced the same
wedge under the same contention and passed cleanly on its own. This bench
has exactly one card and no interlock; a run that overlaps another
produces a symptom indistinguishable from a firmware hang.

## A defect in the margin instrument, found while using it

The first margin-at-32 run after the landing came back at **225,242
cycles/pass** at block 8 — *higher* than session 5's 214,249, on a build
that had just been measured 67.5 cycles/sample/channel cheaper. The
run's own log says why: `tubeon: 32 strip(s) TubeOn=1`.

Session 9 taught `sigprofile_run.sh` to drive `tubeon.py` before the
DWELL window so that a per-CLASS profile's limit-7 point would measure
the ACTIVE tube rather than the bypass copy. The call was
**unconditional**, on the reasoning — written in the comment — that it is
"harmless at limits below 7, the class is skipped entirely there and
never reads TubeOn". That is true of a node-limited profile and **false
of a whole-graph one**: `captable.sh`'s `MODE=cyc` margin question runs
with `DSP4_NODE_LIMIT=0`, so every one of the 32 strips ran its TUBE
engaged. At the 103.9 c/s session 9 itself measured, that is about
26,600 cycles/block of a plugin PW has ruled is never counted in the base
strip — and it is added to a row whose every earlier entry was taken with
TUBE bypassed.

Arithmetic that this is the whole story: 214,249 (session 5) + 26,598
(32 engaged tubes) − 17,280 (this session's 67.5 c/s/channel over 32
channels and 8 samples) = 223,567 against 225,242 measured, 0.7 % apart.

**Any `MODE=cyc` margin figure taken between session 9 and this fix is
inflated by an engaged TUBE and is not comparable to the record.** The
engage is now an explicit fourth argument to `sigprofile_run.sh`,
defaulting OFF; `sigprofile.sh` passes 1 because limit 7 is the whole
point of it, and `captable.sh` passes 0 explicitly rather than relying on
the default, because the default is what went wrong.
