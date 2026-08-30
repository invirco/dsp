# DSP4 cycle budget — measured on the part

provenance: AI-drafted 2026-08-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

## THE MEASURED CAPACITY TABLE — 2026-08-30 (session 5)

**This is the first table with the biquads paired in the graph as well as
the dynamics, and with PW's wide-word metering in the image.** Every
figure was taken on a source tree regenerated for its block size in the
same run — see the note at the end of this section, because the previous
attempt at this table was not.

### Ceilings — channels per chip, fused + paired + biquad-paired

Real time is the FULL block rate: 6000 blocks/s at BLOCK 8, 1500 at
BLOCK 32. Every accepted point is witnessed — all N gates OPEN and all N
compressors ACTIVE for a signal row, all N SHUT and unity for a silence
row.

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| BLOCK 8, signal | **18** | **23** |
| BLOCK 8, silence | **19** | **25** |
| BLOCK 32, signal | **24** | **32 — the whole product** |
| BLOCK 32, silence | **25** | **32** |

Against session 3's table on the same instrument: 16 / 22, 18 / 23,
21 / 28, 22 / 28.

The rejected points, so the misses read as misses. Block 8 at 983.04:
23 = 5999/s and 24 = 5918/s; at 786.432, 18 = 5999/s and 19 = 5667/s.
Block 8 silence at 983.04: 25 = 5999/s and 26 = 5825/s; at 786.432,
19 = 5999/s and 20 = 5846/s. Block 32 at 786.432: 24 = 1500/s and
25 = 1458/s; silence, 25 = 1500/s and 26 = 1473/s.

**AND THE RULED OPERATING POINT IS BLOCK 8, NOT BLOCK 32** (PW ruling
2026-08-28), where the ceiling is 23. Block 32 is four times the block
latency, and the 32-channel row is a statement about what the arithmetic
can be made to fit, not about what the product runs today. Both rows are
in the table for that reason and neither should be quoted without the
other.

**BLOCK 32 AT 983.04 HAS NO REJECTED POINT, because the graph runs out
before the chip does.** 32 strips is the whole D32 channel count, it
scores 1500 of 1500 passes/s with all 32 gates open and all 32
compressors active, and it did so on two separate boots. 28 and 30 pass
as well; there is no 33rd strip to fail.

### MARGIN AT 32 CHANNELS

Cycles per graph pass at 32 strips, signal present, graph decimated so it
completes whether or not it fits, against the real-time budget.

**983.04 MHz**

| config | BLOCK 8 (budget 163,840) | BLOCK 32 (budget 655,360) |
|---|---|---|
| session 3: paired + fused | 226,462 — 138.2 % | 736,848 — 112.4 % |
| + wide-word metering (`DSP4_BQ_GRAPH=0`) | 233,714 — 142.6 % | 743,884 — 113.5 % |
| **+ paired biquads (`DSP4_BQ_GRAPH=1`)** | **214,249 — 130.8 %** | **657,082 — 100.26 %** |

At 786.432 MHz the same cycle counts read **163.5 %** of budget at BLOCK 8
(214,249 of 131,072) and **125.3 %** at BLOCK 32 (657,082 of 524,288).

**THE TWO INSTRUMENTS DISAGREE AT ONE POINT AND IT IS THE HEADLINE ONE.**
The rate instrument says 32 strips at BLOCK 32 and 983.04 runs at 1500 of
1500 passes/s. The cycle instrument says the same graph is 657,082 cycles
against a 655,360 budget — **1,722 cycles over, 0.26 %**. Those are not
in conflict so much as beneath each other's resolution: 0.26 % of 1500
blocks/s is under four blocks a second, which the pass-rate counter cannot
see. **The honest statement is that 32 channels on one 21564 at BLOCK 32
and 983.04 MHz is ON THE LINE — reached by the pass-rate instrument,
0.26 % over by the cycle count — and it is not the comfortable fit that a
product decision would want.** Session 3's best was 12.4 % over.

Two other things the table says and the ceilings do not:

* **D24's 24 channels now fit one chip at 786.432 MHz and BLOCK 32**
  (24 = 1500/s, 25 = 1458/s), which session 2 recorded as not fitting.
* **A two-chip D32 split has room everywhere.** 16 per chip is under
  every ceiling in the table, including block 8 at 786.432.

### What each lever was worth, measured, not attributed by argument

Both rows are the same instrument at the same 32 strips, so the deltas
are differences of measurements rather than of models.

| lever | BLOCK 8 | BLOCK 32 |
|---|---|---|
| wide-word metering | +7,252 (+3.2 %) | +7,036 (+1.0 %) |
| paired biquads | −19,465 (−8.3 %) | −86,802 (−11.7 %) |

**The metering cost is a per-BLOCK constant, about 220 cycles per strip
per block, not a per-sample one** — it is nearly the same absolute number
at both block sizes, which is why it hurts four times as much at BLOCK 8.
That also means the pipelining fix did not do what it was built to do.
The measurement before it was 232,991 at BLOCK 8; the measurement after
it is 233,714 — but the second image also carries the two SHARED meter
routines that the program-memory squeeze forced, so what is measured is
the pair of changes together, not the pipelining alone, and the pair is
+723 cycles. Either way there is no recovery of the 6,500 the metering
costs. **The multiplier-stall hypothesis in that commit message is not
supported by this measurement and is corrected here; the two changes were
not separated, and that is a limitation of the measurement rather than a
result.** What is known
about the 220: a metered node gives up the `DSP4_STRIP_FUSED`
two-at-a-time loop because the meter owns MRF, and the hand-over adds two
calls per strip per block. Those do not add up to 220 and the remainder is
not attributed. It is carried as measured.

**The paired-biquad lever came in ahead of its own arithmetic at BLOCK 32
and behind it at BLOCK 8.** `dsp4-function-costs.csv` predicted
205,000–208,000 at BLOCK 8 (125–127 % of budget) before driver overhead;
the measurement is 214,249, i.e. the gather/scatter overhead is real and
is about what the dynamics pairs lose to it. At BLOCK 32 the prediction
had no row and the measured saving is 11.7 %.

### The stale-tree trap, stated because it nearly shipped a false table

`captable.sh` builds BLOCK-32 points from a scratch source tree, and it
used to cache that tree on the BLOCK SIZE alone: "if `dsp_block.h` already
says 32, reuse it." The tree in `/tmp` was a day old. The first BLOCK-32
half of this table was therefore measured on a tree with **no
`bq_pairs.asm`, no wide-word metering and no D55 fix in it** — and it
returned 28 / 21 / 28 / 22 and 737,160 cycles, which are session 3's
numbers to within the instrument's noise. **Reproducing the previous
session's table exactly is what made it visible**; nothing else about the
run looked wrong. The tree is now regenerated on every invocation and the
generated header is checked to say the block size it was asked for.

## WIDE-WORD METERING — 2026-08-29/30 (session 5), and what it cost

PW's ruling of 2026-08-29 ~17:05: every meter taps the SIGNAL'S WIDE FORM
at its tap point — the most-significant 32-bit word of the accumulator
that produced it, unrounded and unsaturated — and never a rounded 32-bit
store made for the meter's benefit.

**What was built.** Where a meter's source has a live MAC accumulator at
the tap point (chip 1's 32 GAINs, the six metered chip-2 FADER_PANs) the
meter's three per-sample instructions moved INTO the source's block loop
and read `mr1b` in register; the source hands the finished block
accumulators to the meter node in `_mtr_acc_<meter>`, five words once per
block, and the meter node does nothing per sample at all. The audio MAC
moved to MRB so MRF can carry the exact sum of squares, which also costs
the metered node its `DSP4_STRIP_FUSED` two-at-a-time loop — fusion wants
both accumulators for two audio samples and there is no third.

Chip 2's `OUTPUT_TDM` (17 meters) and bus `COMPRESSOR` (4) have NO
accumulator at their tap point — one is a copy, the other finishes in the
ALU — so they publish the same value in the meter's format instead
(`_mtr_wide_<src>`, an arithmetic shift of 4). Those meters lose four
bits at the BOTTOM (−144 dB instead of −168) and their
ONE-SAMPLE-PER-BLOCK decimation is unchanged: that is a property of an
unconverted per-sample source, it is recorded on the meter node, and it is
not fixed here.

The meter's input format is Q8.24 everywhere, so `_mtr_fold`'s
mean-square shift is 20 + log2(BLOCK) and its peak converts to the state's
Q4.28 view with a left shift of 4, clamped at 8.0 linear (+18.06 dBFS).
`fixed_ref.meter_block` takes Q8.24 for the same reason.

**Proven on the part, C1_MTR_01, BLOCK 8: `METER_BIT_EXACT` with BOTH
negative controls firing** — the BLOCK-32 coefficients, and the retired
narrow (rounded-store) form. The second control needed its own operating
point and that is the interesting part: **at unity gain the wide word and
the rounded store carry the same value**, so the standing meter bar could
not have told the ruling's arithmetic from the arithmetic it replaced.
At gain 0.497 they separate exactly, and the part reads the wide model's
`pk_blk>>4 = 4169139`, `ms_blk = 16576495` against the narrow model's
4169138 / 16576493.

**What it cost, and the first cut was not free.** At 32 strips, BLOCK 8,
signal present, cycles per graph pass: 226,462 (session 3, no wide meter)
→ **232,991**, which is +6,529 cycles/block, 204 per strip, **25.5
cycles/sample/strip** — for three instructions of arithmetic that also
deleted four per sample from the meter node. Reading `mr1b` in the
instruction after the MAC that produced it stalls on the multiplier's
result latency. The meter's ops now run ONE SAMPLE BEHIND, on the previous
sample's wide word while the current MAC is in flight, with the last
sample's done after the loop; seeding the pipeline register with zero is
exactly neutral, because zero adds nothing to a sum of squares and the
block peak is `max(hi, −lo)`, which is non-negative already.

**D20 IS STILL BLOCKED, and by the router rather than by the meter.** The
ruling's premise — "kill every tap store whose only consumer is a meter
(BLK_TAP_TRIM class)" — is not this graph: `BLK_TAP_TRIM` is read by
ROUTING's pickoff 0, which needs a Q4.28 sample, and GAIN still has to
write `BLK_CHAIN_B` for FILT. The −17 c/s/strip is the round/saturate plus
those two stores, so nothing on that node can be deleted by a metering
decision. What remains of D20 is the GAIN→FILT COEFFICIENT fold (g folded
into stage 1's b0/nh/n2, which is a numeric-spec amendment) plus
materialising the post-trim tap only for the sends that actually select
pickoff 0. It is said in the emitted node so the next reader does not have
to re-derive it.

## PAIRED BIQUADS IN THE GRAPH — 2026-08-30 (session 5)

`_bq_pair_blk` has been measured at 1.43–1.54× since its hang was
root-caused on 2026-08-29, and until this session nothing in the GRAPH
called it. FILT and EQ now run as one SIMD instruction stream per strip
PAIR, in the same two-pool arrangement the dynamics use:

    A: IN GAIN / B: IN GAIN / FILT pair / EQ pair / GATE pair / COMP pair
    A: TUBE DLY FDR RTG / B: TUBE DLY FDR RTG

Safe to reorder because both classes work IN PLACE on their own pool's
`BLK_CHAIN_B`, so no slot is read by one strip while the other writes it.
A pair whose channels are not both in steady state falls back to the two
scalar nodes, which work in place too.

**Bit-exact on the part, with a firing negative control**: strip 1 driven
and strip 2 muted, REAL filter designs written into both strips,
`DSP4_BQ_GRAPH=0` against `=1` → **0 of 64 main-bus words differ**;
against `DSP4_BQ_NEGCTL=1`, which gives strip B strip A's coefficients and
state so the pair computes one channel twice → **56 of 64 differ, maxdiff
69,476,676**. The negative control is also what witnesses that the paired
path is the one running.

**The bypass trap, stated because it nearly swallowed this proof.** With
bypass coefficients the paired and scalar cascades are bit-identical BY
CONSTRUCTION, so a comparison taken at bypass passes whatever the pairing
does — which is exactly why session 3's bus golden reproduced with no
biquad coefficient coverage at all. `bqgraph.sh` writes a different real
RBJ design into each strip of the pair before it captures anything.

**Program memory is now the binding constraint on chip 1.** The drivers
cost 5,670 bytes and the SIMD cascade another 754; the shipping
paired+fused image links with 1,782 bytes of code free and the 983 MHz
profile-stimulus measurement image with 642. The first cut of the drivers
cost 7,488 bytes and the measurement image did NOT link at all.

## THE MEASURED CAPACITY TABLE — 2026-08-29 (session 3)

**This is the first table taken with strip fusion and dynamics pairing in
the SAME image.** Session 2 could not build that combination at all: chip
1 was out of program memory and the linker was 4,890 bytes short. The
reclamation that unblocked it is recorded under *Program memory* below.

Every figure here was taken AFTER the halved-n1 encoding landed (PW
ruling, minimum EQ Q = 0.10), so the extra MAC per biquad stage is inside
every number. Figures from earlier sessions predate it.

### Ceilings — channels per chip, fused + paired, honest full-rate rule

Real time is the FULL block rate: 6000 blocks/s at BLOCK 8, 1500 at
BLOCK 32. Every accepted point is witnessed — all N gates OPEN and all N
compressors ACTIVE for a signal row, all N SHUT and unity for a silence
row — and every rejected point is a clean miss, not a marginal one.

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| BLOCK 8, signal | **16** | **22** |
| BLOCK 8, silence | **18** | **23** |
| BLOCK 32, signal | **21** | **28** |
| BLOCK 32, silence | **22** | **28** |

The rejected points, so the misses can be read as misses: block 8 at
983.04, 22 = 5999/s and 23 = 5739/s; at 786.432, 16 = 5999/s and
17 = 5930/s. Block 32 at 983.04, 28 = 1500/s and 29 = 1434/s; at
786.432, 21 = 1500/s and 22 = 1493/s. The silence rows: block 8 at
983.04, 23 = 5999/s and 24 = 5907/s; at 786.432, 18 = 6000/s and
19 = 5785/s. Block 32 at 983.04, 28 = 1500/s and 29 = 1483/s; at
786.432, 22 = 1500/s and 23 = 1459/s.

**A label to ignore in the raw logs (review finding D49).** Every line in
this session's sweep logs says `REAL_TIME (N passes/s of 1500)`, block 8
rows included, because generating the block-32 scratch tree overwrote
`tools/pi/dsp4_block.py` and audio_verdict.py takes its BAR from there.
The bar is the only thing that came from it — the measured `N passes/s`
is a pass-counter delta over wall time and does not depend on the block
size — and every ceiling above was decided by applying 48000/BLOCK by
hand, not by reading the label. The leak is fixed; the logs are not
reprinted.

**Against the record this replaces:** block 8 at 983.04 signal present
was 12 scalar-unfused (08-28), 15 paired-unfused (08-28) and 16
scalar-fused (08-29 session 2). It is now **22**.

**THE SILENCE CONTROL HAS ALMOST STOPPED MATTERING, and that is a
result.** Silence used to flatter a ceiling by ~29 %: it is now worth one
channel at block 8 and none at all at block 32. Pairing moved the
dynamics off the branch that silence was cheating on.

### MARGIN AT 32 CHANNELS — the number the ruling asks for

Cycles per graph pass at 32 strips, signal present, measured with the
graph decimated so it completes whether or not it fits, then compared
against the real-time budget for that block size and clock.

**983.04 MHz, BLOCK 8 — budget 163,840 cycles/block**

| config | cycles/block | % of budget | margin |
|---|---|---|---|
| scalar, unfused | 349,555 | 213.4 % | −185,715 (−113.4 %) |
| scalar, fused | 303,355 | 185.2 % | −139,515 (−85.2 %) |
| paired, unfused | 274,419 | 167.5 % | −110,579 (−67.5 %) |
| **paired + fused** | **226,462** | **138.2 %** | **−62,622 (−38.2 %)** |

**983.04 MHz, BLOCK 32 — budget 655,360 cycles/block**

| config | cycles/block | % of budget | margin |
|---|---|---|---|
| scalar, unfused | 1,280,847 | 195.4 % | −625,487 (−95.4 %) |
| scalar, fused | 1,095,628 | 167.2 % | −440,268 (−67.2 %) |
| paired, unfused | 922,754 | 140.8 % | −267,394 (−40.8 %) |
| **paired + fused** | **736,848** | **112.4 %** | **−81,488 (−12.4 %)** |

Fused + paired at 786.432 MHz: **174.0 %** of budget at BLOCK 8
(228,081 of 131,072) and **140.6 %** at BLOCK 32 (737,126 of 524,288).

**THE MARGIN AT 32 IS NEGATIVE IN EVERY MEASURED CONFIGURATION.** The
best is BLOCK 32 at 983.04 with fusion and pairing, and it is **12.4 %
over the budget**, not under it. Nothing in this table reaches 32
channels on one 21564; the honest statement of where the campaign stands
is that the gap has gone from roughly a factor of two to 12.4 %.

**Two chips is a different question and it is now answered with room.**
A two-chip D32 needs 16 per chip. At block 8 and 983.04 the ceiling is
22, against exactly 16 in session 2 — the split has stopped being
marginal.

### The two instruments agree, and they share no arithmetic

The ceiling sweep scores a pass rate on the part. The margin table counts
cycles in a decimated graph. Ratio of cycles at 32 strips, scalar-fused
against paired-fused: **1.340**. Ratio of the ceilings those two configs
reach at block 8 / 983.04: **22 / 16 = 1.375**. Three per cent apart, from
two measurements that have no step in common.

### What is in these numbers, and what is not

IN: strip fusion; dynamics pairing (GATE and COMP as pair drivers on the
pair-ordered chain); the D21 packed biquad loop; D22's control-rate gate;
D25's circular delay addressing; the halved-n1 MAC.

NOT IN, and it is the next lever: **the biquad cascade is NOT paired in
the graph.** `_bq_pair_blk` is still behind `DSP4_SIMD_PROBE` and only the
self-test calls it. Its factor is now measured rather than hung — 1.43 to
1.54× on a four-stage cascade, 1.43 to 1.57× on two stages, against the
FUSED cascade — and FILT and EQ together are the largest per-sample block
left in the strip. Wiring a FILT/EQ pair driver is the obvious next step
and it now has a number instead of a hang.

Also not in: D20's GAIN fold (blocked on a meter ruling), D24's parameter
shadows (re-evaluated below), and chip 2, which still has no block
kernels at all (review finding D16).

### Program memory — what was reclaimed and what it cost

Chip 1's `sec_swco` is full at 131,070 of 131,072 bytes in every
block-kernel build and everything spills into the block-2 overflow; the
two together are 262,144 bytes and there is no third tier. Free bytes:

| config | before | after |
|---|---|---|
| scalar, unfused | 15,062 | 29,518 |
| scalar, fused | 9,882 | 24,338 |
| paired, unfused | 418 | 17,134 |
| paired + fused | **−4,890 (would not link)** | **11,954** |

Three reclamations, each measured on its own: the DLY per-sample body,
dead in block-kernel builds because that class's block kernel has no
fallback into it, 13,568 bytes (424 in each of 32 nodes); `dyn_selftest`,
which was gated on `DSP4_SIMD_DYN` and therefore rode in every paired
build including a shipping one, 2,240 bytes; and `lib/dynamics.asm` plus
`lib/delay.asm`, float-era routines with no caller anywhere that the
linker placed anyway because they were on its command line, 888 bytes.
The halved-n1 MAC then cost 12 bytes back.

`tools/dsp/pm_audit.py` is the instrument: it attributes every byte of
the code output sections to the object that contributed it and rolls
objects up by node class. `dsp_memreport.py` says how much is left; this
says who is using it.

**The structural lever is still there and is still the big one.** RTG is
41,344 bytes of the paired+fused image — 16.6 %, 1,292 bytes per node
across 32 nodes — and the same indexed-array-plus-shared-routine move that
took the control-rate gate from 41 bytes per node to 3 has not been
applied to the rest of its prep.

---

## BLOCK SIZE (2026-08-28) — read this before any figure below

The working operating point is **block 8**, not 32 (PW ruling 2026-08-28).
**Every capacity figure in this document that does not say otherwise is a
BLOCK-32 figure** and is superseded by `dsp4-function-costs.csv`, which
carries the block size on every row.

**SUPERSEDED by the session-3 table at the top of this file** — those
rows are scalar-unfused and paired-unfused, and none of them had strip
fusion and pairing in the same image. Kept because they are the
comparison the new table is read against.

**RE-MEASURED 2026-08-28 (fourth session), signal present, honest 6000
blocks/s rule, channels per chip:**

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| block 32 (2026-08-27) | 11 | 14 |
| block 8, scalar | **9** | **12** |
| block 8, SIMD paired | **11** | **15** |

The block-8 figures recorded earlier the same day — 5 and 6 signal
present, 8 and 11 silence — were measured on a build in which the
compressor did four times its proper work per block (see the retraction
below). They are withdrawn. The block-32 rows are unaffected: at BLOCK=32
the defective loop count was the right one.

Every accepted point is witnessed with all N gates OPEN and all N
compressors ACTIVE, and every rejected one is a clean miss: 10 at 786
reads 5,679/s, 13 at 983 reads 5,656/s, 12 paired at 786 reads 5,903/s,
16 paired at 983 reads 5,756/s.

**16 per chip at 983 — what a two-chip D32 split needs — now misses by
4.2 % of the block budget.** That is a margin, not a factor.

### RETRACTED 2026-08-28 (fourth session): "COMP is block-invariant"

The paragraph that stood here said the strip costs 2,719.9 cycles/sample
at block 8 against 1,233.4 at block 32, that a two-point fit put 15,856
cycles/block of it in block-INVARIANT work, that 13.5k of that was COMP
alone, and therefore that cutting COMP's once-per-block section was worth
more at block 8 than SIMD. **All of it rests on a defect, and it is
withdrawn.**

`_COMP_BLK_BODY` in the generator carried a literal `lcntr = 31` — the
only loop count in the tree written as a number instead of derived from
the block size. At BLOCK=8 the compressor therefore ran **1 + 31 = 32
samples of an 8-sample block**, reading 32 words from `BLK_CHAIN_A` and
writing 32 to `BLK_CHAIN_B`, three slots past the end of each, over
`BLK_FDR_L`, `BLK_FDR_R` and `BLK_TAP_TRIM`. A node that does the same 32
samples of work whatever the block size measures as block-invariant
because it IS invariant. The measurement was honest; the instrument was
reading a defect.

It could not be caught by the byte-identical block-32 control that proved
the parameterisation, because the control image is the PER-SAMPLE build
and every affected line lives behind `DSP4_BLOCK_KERNELS` or a self-test
guard. **The shipping image never ran any of it.**

Five more literals of the same kind were found with it and are listed in
tasks.md (2026-08-28, fourth session): the bus-accumulator clear, the
paired biquad cascade's per-stage rewind, the backwards diff start index
in BOTH self-tests — which is why the paired-dynamics bit-exactness test
could not fail at block 8, negative control included — and the
cycles-per-sample divisor in `dynst_read.py`. Every one is now derived
from `DSP4_BLOCK_SIZE`.

The replacement figures are in `dsp4-function-costs.csv`, measured on the
same instrument with the loop count derived.

Digital latency at block 8 is **derived, not measured**: the block period
is measured (166.7 us, from FRAME_COUNT 5999-6000/s) and the ring
geometry and pipeline depth are unchanged, so the measured
93-samples-at-block-32 pipeline scales to ~23 samples = 0.48 ms. The
end-to-end measurement is blocked on the Pi-input-to-Pi-output route,
which the boot config does not set.

## SIMD IN THE GRAPH — 2026-08-28 (fourth session)

The paired dynamics kernels landed on 2026-08-28 (963f181) and measured
2.04-2.12x on COMP and 2.36-2.54x on GATE, bit-exact, with a negative
control that failed as it must. **No strip ran paired**, because the chain
is strip-ordered and the block pool is reused strip by strip: a pair could
never hold two live channels. This session wired it.

### Two pools, not a park

The scaffolding already in the tree parked ONE slot (`BLK_PAIR_PARK`) and
copied into and out of it. That is enough for a biquad pair inside a
single strip's kernel and not enough for a pair of whole strips: the TAPS
(trim, EQ, pre-fader) are written in the strip's HEAD and read by its
router in the TAIL, so parking the chain block alone leaves strip A's
router reading strip B's taps.

So the ODD strip of each pair gets a second complete pool (`_blk_pool1`,
8 slots x BLOCK = 64 words at BLOCK=8) and the even strip keeps the
original. **No copying at all**: the odd strip's nodes are GENERATED
against `BLK_*_P1` and the even strip's against `BLK_*`, both pools are
live across the pair, and the paired kernels read one channel from each.

    A: IN GAIN FILT EQ        (odd strip, pool 1)
    B: IN GAIN FILT EQ        (even strip, pool 0)
    GATE pair, COMP pair      (one channel from each pool)
    A: TUBE DLY FDR RTG
    B: TUBE DLY FDR RTG

The paired dynamics run IN PLACE on each pool's `BLK_CHAIN_B`, which is
the same net slot movement as the scalar ping-pong (B -GATE-> A -COMP-> B),
so the tails are untouched. With `DSP4_SIMD_DYN` off every `BLK_*_P1`
macro aliases its original, which is what keeps the shipping image
byte-identical while the generator emits P1 names for sixteen strips.

### Three places it could have been silently wrong

- **The block-rate parameter conversion is not duplicated.** Both dynamics
  classes convert once per block inside their own per-sample body, behind
  the `_sample_idx == 0` guard, and the scalar COMPRESSOR block kernel
  already drives that body for sample 0 for exactly this reason. The pair
  driver does the same for both channels and hands the pair kernel the
  remaining BLOCK-1 samples through `_dsim_n`. Sample 0 is bit-identical
  to the scalar path by construction, and there is no second copy of the
  conversion arithmetic to drift.
- **Declaration order is the pair interface.** `_gate_pair_blk` reads five
  consecutive parameter words and scatters four consecutive state words.
  COMP's eight were already consecutive, deliberately. GATE's were not:
  `hold` sat in the host parameter block and `hold_count` beside it, so a
  pair would have read `_buf_` as `hold` and written the hold count over
  `attq`. Under a paired graph both move, guarded, and the build now
  CHECKS the addresses out of the .map rather than trusting the ordering.
- **The fallback is net-preserving.** A pair whose channels disagree (one
  gate off, one sidechain filter on, one compressor bypassed) runs the two
  scalar nodes and squares the slots up, so "the dynamics section reads
  BLK_CHAIN_B and writes BLK_CHAIN_B" holds on both paths. An odd strip
  count falls out of the same mechanism: the last strip's two dynamics
  nodes run scalar on their own pool.

**Chip 2 is not applicable.** Its dynamics are `C2_GRP_COMP`,
`C2_MAIN_COMP` and friends, which do not match the strip-node pattern,
have no block kernel and have no pair. Its chain file is unchanged.

`DSP4_SIMD_GRAPH` separates "the paired KERNELS are in the image"
(`DSP4_SIMD_DYN`) from "the graph is WIRED for them". They have to be
separable: with the kernels and the 32 drivers both in, chip 1 overflows
`sec_swco`, and the kernel self-test wants the kernels and their scalar
twins without the drivers.

### The paired biquad cascade still hangs — SUPERSEDED 2026-08-30 (session 12)

> **THIS SECTION IS WRONG AND IS KEPT ONLY AS THE RECORD OF WHAT WAS
> BELIEVED.** `_bq_fx_cascade_simd` does not hang and, on the evidence
> below, never did in the form described here. See "THE CASCADE DOES NOT
> HANG" at the end of this file for the measurements. In short: the
> signature this section reads as a hang — `_bqst_done` stays 0, the part
> answers the link, BOOT_STAGE stops short — is an INTERMITTENT
> BOOT/CONFIG HANDSHAKE FAILURE that occurs on byte-identical images and
> on builds containing no paired cascade at all, and the self-test arm
> that was supposed to report on the cascade could not tell the two
> apart. Every "bisect" result recorded below is a perturbation of image
> layout, not a bisect.



`_bq_fx_cascade_simd` hangs the part when driven from the main loop with
the graph configured; it presents as "never reached stage 6", the part not
answering the link while the self-test owns the main loop. Nothing in the
GRAPH calls it — only the self-tests do — so it does not block the rung.

Two real defects in it were found and fixed and neither cleared the hang:
the per-stage rewind `m2 = -64` (right only at BLOCK=32; at BLOCK=8 stage
two read and WROTE 48 words before `_bqp_sig`), and the IRPTEN mask around
the whole cascade — the paired DYNAMICS kernels mask nothing and rely on
the per-ISR PEYEN clear, and masking is what a self-test that calls the
cascade thousands of times in a hardware loop cannot afford. What the
bisect says now: `DSP4_SKIP_SIMDCALL=1` boots and runs cleanly through
`_bq_pair_blk`'s interleave and scatter; **one stage hangs exactly as four
do**, so it is not the per-stage rewind or the state advance; and removing
the interrupt mask does not change it. That leaves the sample loop and the
MODE1 entry/exit.

## The 0.9 V rail at 983.04 — measured, in spec, and the margin is thin

PW measured **0.87 V at the card under load** at 983.04 MHz. The datasheet
window for VDD_INT (400 MHz ≤ CCLK ≤ 1 GHz) is **0.855 min / 0.900 nominal
/ 0.945 max**, so it is inside — but by **15 mV, 1.8 % above the minimum**,
and 30 mV under nominal.

**Two caveats on what that measurement covers, both worth stating:**

1. **It was taken at `DSP4_STRIPS=12`, which runs REAL-TIME** — the chip
   finishes each block with cycles to spare. The heaviest draw is a chip
   that never gets ahead, i.e. one running MORE than fits, computing
   flat out for the whole block period. That configuration was not
   measured and will draw more.
2. **Datasheet IDD figures are TJ = 25 °C typical.** Current rises with
   junction temperature, and there is no on-chip temperature sensor exposed
   over the diag link, so nothing here observes the hot case.

With 15 mV of headroom, both of those matter. **Opportunistic item: the
next time a max-strip (over-budget, never-idle) configuration is running
for another reason, flag it so the rail can be re-touched at that
operating point.** That is the measurement that would turn "in spec" into
"in spec with known margin".

Recorded as: 983.04 is closed for shipping on PW's measurement; the
worst-case load point remains unmeasured.


## SIMD ROLLOUT — where it actually stands, 2026-08-24

**Not rolled out. What exists is a pairing wrapper that builds but is not
verified in situ, and the in-graph rollout needs a restructure I have not
done.** Recording that plainly rather than implying progress.

### What is established

| | |
|---|---|
| PEy works on this part | verified live — both halves came back correct |
| `_bq_fx_cascade_simd`, two strips one instruction stream | **2.39×**, **0 differing samples of 64**, different coefficients per strip |
| `_bq_pair_blk` (gather → pair → scatter) | written, assembles, **NOT verified on the part** |
| predicted net gain | FILT **+47**, EQ **+97** cycles/sample/strip after interleave overhead |

### The blocker for in-graph use, which I under-scoped

Strips share an 8-slot pool and run **sequentially** — that is the whole
reason the pool is 256 words instead of 16 K. **Strip 2's block does not
exist while strip 1 is running**, so two strips cannot be paired without
either

- doubling the pool to 16 slots (+256 words of DM, which is already tight
  enough that a 1,024-word table overflowed `sec_stak` today), **and**
- reordering the call chain to run strip PAIRS together — IN(1), IN(2),
  GAIN(1), GAIN(2), FILT(1+2 paired), … — which changes node indices and
  therefore `DSP4_NODE_LIMIT`, the scope-skip table and the fabric
  measurement method,

or restructuring the pool into 16 pair-slots outright. Either is a real
piece of work with several verification steps, and it is the honest reason
this is not done.

### PEYEN AND INTERRUPTS — a real hazard, found and fixed

**The hypothesis was right.** An interrupt taken while `MODE1.PEYEN` is set
runs the HANDLER in SIMD mode: every register it writes becomes a pair
write, clobbering PEy shadows the ISR knows nothing about. The block and
diag ISRs fire ~2,500 times a second between them, and the fault is
timing-dependent rather than positional, which is why instruction-level
bisecting could not localise it.

It also explains why the standalone benchmark passed while the same routine
hung through the wrapper: **the benchmark had already masked `IRPTEN` for
its TCOUNT timing**, so PEYEN and an ISR never coincided. That measurement
passed for a reason unrelated to the code being correct in context.

**Systemic fix, per the steer:** both ISRs (`_diag_timer_isr`, `_sec_isr`)
now clear PEYEN immediately after `push sts`; `pop sts` restores it on the
way out. Masking around every SIMD region does not scale past one kernel.
Guarded by `DSP4_SIMD_STRIPS`, so the shipping image stays byte-identical.
`_bq_fx_cascade_simd` additionally saves `MODE1` whole, masks `IRPTEN`,
then sets PEYEN — **in that order**, because setting PEYEN first leaves a
window with interrupts still enabled, and MODE1 writes have a pipeline
shadow that widens it. My first attempt had the order wrong.

`CONFIG_COMMIT` now completes where it never did.

### IICDI ruled out; the hang is still not diagnosed — stopping here

`DSP4_BLOCK_MASK=0` was the right idea and it did clear the audio path out
of the way. What it did not do is find the fault.

**A diagnostic dead end worth recording.** The IICDI counter was first
placed where `diag.peek()` could read it — and `peek()` is a **two**
transaction handshake (write `PEEK_ADDR`, read `PEEK_DATA`). The diag ISR
backstop can serve a single read but not that handshake, so **a peek-based
counter is unreadable in exactly the situation it exists to diagnose.** It
was moved to a named diag register (`0xE018`), one transaction, readable
while the main loop is wedged. That is a general lesson about this link,
not a SIMD one.

**Result: `IICDI` read 0.** So the unaligned-long-word theory is **not
supported** — the vector never fired. That was the strongest hypothesis and
it is now off the list. Caveat: the one run that answered was on a build
whose diag table was mis-sized (see below), so it is weaker evidence than I
would like, and the corrected build then would not answer at all.

**A rule violated and fixed.** Adding the register put a duplicate entry in
the non-SIMD path of `_diag_table`, giving it 25 entries where it should
have 24, and **the shipping image changed** — `45911c85` against
`0df38e82`. Caught by the md5 check on the very next build and corrected;
shipping is back at `0df38e82`. The check earned its keep again.

**Where this stands.** `_bq_fx_cascade_simd` hangs when called with
interrupts enabled. Ruled out: iteration count, loop-count arithmetic,
PEYEN residue, PEYEN-in-ISR (fixed anyway, correctly), buffer alignment by
inspection, and now IICDI by measurement. The verification harness itself
has been the obstacle at every turn, and each placement failed for a
different structural reason.

I am stopping the bisect here rather than continuing to fire builds at it.
**Nothing is wired into the graph**, shipping is byte-identical, and the
tree with the SIMD flags off is CHAIN BIT-EXACT at 983.04 MHz.

The next person — likely me, next session — should start from the ILOPI
and SOVFI vectors, which are also bare `rti` and would livelock the same
way (SOVFI in particular: status/loop/PC stack overflow, and this code
calls a routine with nested hardware loops from inside another hardware
loop). Instrumenting all three fault vectors at once costs one build and
would have answered this hours ago.

### RETRACTION: "CONFIG_COMMIT now completes" was not evidence of a fix

I reported that the PEYEN fix resolved the hang because config started
succeeding. **That conclusion was wrong and is withdrawn.**

The diag timer ISR **services the parameter link as a backstop** — it says
so in its own header, and it is why the link answers when the main loop is
dead. So `CONFIG OK` proves the ISR is running. It proves nothing about the
main loop. Every "config now completes" reading in this investigation was
compatible with the main loop being wedged the entire time.

The measurement that actually distinguishes them: read `TICKS` and
`FRAME_COUNT` twice. With the selftest built in, `TICKS` reads 49,031 and
`FRAME_COUNT` 10,170 on the first pass and then the link degrades to no
answer — the part is not healthy, and `_bqst_done` reads **0**, meaning the
selftest never reached its final store. It hangs.

So the position is: **`_bq_fx_cascade_simd` still hangs when called with
interrupts enabled**, and the PEYEN work — which is correct and worth
keeping on its own merits — did not fix it.

**The strongest untested hypothesis, and where to start next.** The IVT
entry for **IICDI, "Unaligned long-word access", is `rti; nop; nop; nop;`**
— no handler. A SIMD access is long-word-like, so an unaligned one raises
IICDI, the `rti` returns to the faulting instruction, and it re-executes
forever: **the main loop livelocks while every ISR keeps running**, which
is exactly the observed signature. The `_bqp_*` buffers were checked as
even-addressed, but "even" may not be the alignment SIMD actually requires,
and the LDF only asks for `INPUT_SECTION_ALIGN(4)`.

Two cheap next steps, in order: put a real handler on the IICDI vector that
records a marker so the fault becomes visible instead of silent, and force
the SIMD buffers to a stronger alignment than the section default.

**None of this touches the shipping path.** Shipping image byte-identical
at `0df38e82`; the tree with SIMD flags off is CHAIN BIT-EXACT at
983.04 MHz.

### The harness placement findings still stand

Three selftest placements each failed for a different reason, and these are
real properties of the firmware regardless of the SIMD fault:

| placement | outcome |
|---|---|
| from `CONFIG_COMMIT` | ran inside the diag timer ISR, secondary register file live, 1 ms timer waiting to re-enter |
| before interrupts enabled | blocked the boot handshake; host SPI arrived with nothing draining the RFIFO, response stream permanently out of phase |
| once from the main loop | starves the SPI poll (every 8 samples from the block loop); ~50 µs of blocking drops a response and shifts the word phase by one |

**Any long-running blocking work inside the audio path desyncs the
parameter link.** That is worth knowing independently of SIMD.

### Foundation that IS in place

The earlier claim that pairing needs the pool doubled to 16 slots was
**wrong, and is corrected**: it needs **one** extra slot. Strip N's chain
value parks in `BLK_PAIR_PARK` while strip N+1 catches up, then the two are
interleaved. That is **32 words, not 256** — `_blk_pool` is 288 under
`DSP4_SIMD_STRIPS` and 256 otherwise. The park slot and its flag are in,
the build is clean, and the shipping image is unchanged.

What remains for the rollout: the paired call order — for a pair (N, N+1),
emit IN(N), GAIN(N), park, IN(N+1), GAIN(N+1), paired biquads, tail(N+1),
unpark, tail(N) — which changes node indices and so touches
`DSP4_NODE_LIMIT`, the scope-skip table and the fabric measurement method
in SIMD builds only.

## 983.04 MHz ENABLED AND VERIFIED — 2026-08-24 (U5/U6 read as KSWZ10)

PW read the marking: **ADSP-21564KSWZ10, the 1 GHz grade.** That removes
the only thing gating the 983.04 MHz target.

| | |
|---|---|
| CCLK, chip 1 | **983.04 MHz** measured (target 983.04) |
| CCLK, chip 2 | **983.05 MHz** measured |
| budget/block | 327,680 → **655,360** (2.00× the original) |
| real time | `_proc_passes` **1500/s**, `DSP4_STRIPS=1` |
| harness | **CHAIN BIT-EXACT, 0 of 7, twice** |
| 60 s soak | FRAME_COUNT monotonic at 1500/s, TICKS at 1000/s, **no resets** |
| SPORT0_ERR_A / DMA0_STAT | 0x00000000 / 0x00006200 |

Measured the same way as 786: `DIAG_TPERIOD` is built as 983,040 for a
1.000 ms tick, so a tick rate of 1000.0/s *is* the clock.

**I nearly reported 983 as unstable, on two bad reads.** A `chain.py` run
returned zero, and a `dsp4_diag` snapshot showed `FRAME_COUNT 0` and
`SPI_RX_COUNT 0` at `BOOT_STAGE 7` — which reads exactly like a part that
has reset. Both were transient link artefacts: the 60 s soak shows the
frame counter advancing monotonically throughout, and the harness is
bit-exact on two consecutive runs. **On this link a single anomalous read
is not evidence of anything** — that is the third time it has produced a
convincing false signal, and the rule is now to require a second reading
before drawing a conclusion.

### Power and thermal — the gap is real and is NOT closed

Datasheet IDD_TYP, VDD_INT 0.9 V, TJ 25 °C, ASF 1.0, DMA 328 MB/s:

| CCLK | IDD_TYP per chip |
|---|---|
| 600 MHz | 490 mA |
| 800 MHz | 619 mA |
| **1000 MHz** | **748 mA** |

So 983.04 draws roughly **740 mA per chip, ~1.5 A for the pair** on the
0.9 V rail, against ~610 mA/chip at 786.432 — an increase of about
**260 mA across the two chips**.

**This cannot be signed off from here, for two specific reasons:**

1. **The +0.9 V rail comes from the MOTHERBOARD** over the J1/J2 DIL100
   stack (`hardware-map.md`), so the regulator and its rating are not in
   this repo and its margin cannot be checked from the DSP card side.
2. **PW's "all three supplies measured in spec" was taken 2026-08-21, at
   CGU reset defaults — 491.52 MHz**, where each chip draws far less. That
   measurement does not cover this operating point and **should be
   repeated at 983.04 under load.**

Also unaddressed: these are TYPICAL figures at TJ = 25 °C. The datasheet
points to EE-471 for the real total-power equation, and there is no
on-chip temperature sensor exposed over the diag link, so **a 60 s soak is
not a thermal test.** A sustained run with a rail measurement is what would
close this.

**Recommendation: 983.04 is proven functionally correct and stable over a
minute, and is NOT yet proven thermally or electrically.** Treat it as
enabled for measurement work, not as shipped, until the rail is measured
at this operating point.


## CROSSPOINT-COEFFICIENT FOLD — measured 2026-08-27

The 08-25 mandate's fold, measured on the CONVERTED build with `profile.sh`
(TCOUNT, `DSP4_NODE_LIMIT` 8/9/10, DEC=32). Three ROUTING variants, because
lumping them would hide which part is a correctness price and which is the
fold:

| ROUTING | cycles/block | cycles/sample |
|---|---|---|
| before — the block-rate send prep sat behind a `_sample_idx == 0` guard that never fires here, so it never ran and **no send could carry signal** | 2,617 | 81.8 |
| guard fixed — prep runs, sends work | 3,196 | 99.9 |
| + crosspoint fold | 3,667 | 114.6 |

| FADER_PAN | cycles/block | cycles/sample |
|---|---|---|
| before — fader multiply, then pan multiply, then a unity MAC at the bus | 1,908 | 59.6 |
| after — pan leg IS the main-bus crosspoint coefficient, two round/saturate stages deleted | **1,011** | **31.6** |

**Net for the strip, against the honest baseline (sends working): −426
cycles/block, −13.3 cycles/sample.** The pre-fold ROUTING figure is cheaper
only because it was skipping work it was supposed to do.

### The active-crosspoint list — measured 2026-08-27 (late)

The fold left the accumulate path reading coefficients only, but it still
WALKED all 25 crosspoints every sample looking for the live ones. Which are
live is control state too, so it now resolves at control rate into a dense list
of (source, bus accumulator, coefficient) triples and a count; the audio path
iterates over live crosspoints only.

Per-sample build, per strip, four tree states so the memory layout, the fold
and the list are separated:

| variant | GAIN | FADER_PAN | ROUTING | chain @ NODE_LIMIT 10 |
|---|---|---|---|---|
| before this work | 71.7 | 147.6 | 589.2 | 130,185 |
| + the LDF reorder alone | 71.0 | 147.2 | 590.2 | 130,215 |
| + crosspoint fold | 64.4 | 75.0 | **598.1** | 127,631 |
| + active-crosspoint list | 64.3 | 60.8 | **202.3** | 114,675 |

(cycles/sample per strip; the chain column is cycles/block)

**ROUTING 589.2 → 202.3 cycles/sample, 2.91×**, and note the third row: the
fold ALONE made the per-sample router slightly worse, because it still walked
every crosspoint and added control-rate prep on top. The list is what pays.

| step | whole chain |
|---|---|
| LDF reorder / Block-1 spill | +30 cycles/block — nothing |
| crosspoint fold | −2,554 (−79.8 cycles/sample) |
| active list | −12,956 (−404.9 cycles/sample) |
| **total** | **−15,510 cycles/block, −484.7 cycles/sample** |

**THE SHIPPING CEILING MOVED FROM 2 STRIPS TO 3**, measured with `strips.sh` at
the default clock on `_proc_passes`: STRIPS=3 holds 1500/s where it measured
1342/s (89 %) on 2026-08-22; STRIPS=4 is over budget at 1334/s.

**In the CONVERTED build the list is neutral** — 63,156 → 63,203 cycles/block,
inside noise — because there the accumulate already ran once per block and the
list build costs about what the walk did. So this does not move the 786 MHz
channel ceiling; that stays 10. The gain is on the shipping image.

Two method notes from this measurement, both of which would otherwise mislead:

- **Per-node differencing carries layout noise that the chain figure does not.**
  FADER_PAN is byte-identical in the last two rows yet reads 75.0 and 60.8:
  ROUTING's code grew, which moved later objects and changed instruction-fetch
  alignment for bodies that run 32× a block. Quote the chain delta when the two
  disagree. The trustworthy FADER_PAN figure is −72.6 cycles/sample, which
  matches the two `_mrf_rns28` calls the fold deleted.
- **Spilling DM into Block 1 is free.** Rows one and two are the same code at
  different addresses.

### What that is worth, and what it is not

Applied to the measured ceiling above: 1,269 → ~1,256 cycles/sample/channel,
so 406,106 / (1,256 × 32) = **10.1 channels**. **The ceiling stays 10 and the
32-in-one verdict is unchanged.** This is a ~1 % capacity gain; its value is
correctness — before it, routing sends did not work in this build at all, and
every GAIN and FADER_PAN ramped parameter was unsettable over SPI on either
build (see tasks.md, outcome 2026-08-27 evening).

### The DM ceiling recorded here on 2026-08-24 was not a memory limit

"DM headroom is under ~1,600 words" was measuring the distance from `sec_dmda`
to a stack reserve declared AFTER it in the LDF, not exhausted memory. Sections
mapped to one region are placed in declaration order, so `sec_dmda` took Block 0
greedily and `sec_stak` got the remainder — while `sec_dmda_ovf` and the whole
of Block 1 sat at **0 %** with 180,224 bytes free. The true margin at that point
was **262 words**, and today's stride table had already pushed the converted
build past it: **DSP4_BLOCK_KERNELS would not link at all.** Reserving the stack
first fixes it; chip 1 now sits at Block 0 89.7 % + Block 1 11.9 %, 178,840 bytes
free overall. Any future note about DM headroom should quote the per-purpose
total from `dsp_memreport.py`, not a single region.


## STRIP FUSION — FILT+EQ measured, and the lever is small

FILT now cascades **in place on its input slot** and EQ continues on the
same slot: both block copies deleted, and FILT's two `r4 = 1` cascade calls
collapsed into one `r4 = 2` call (the HPF and LPF coefficient arrays are
adjacent — verified in the map at exactly 5 words). The FILT→EQ handoff is
**zero instructions**: no copy, no slot change, nothing between them.

Both arms measured identically, signal present, `NODE_LIMIT` 2/3/4:

| | FILT | EQ | FILT+EQ |
|---|---|---|---|
| unfused | 2,794 | 5,445 | 8,239 cycles/block = **257.5/sample** |
| **fused** | 3,025 | 5,051 | 8,076 = **252.4/sample** |
| | | | **−163 cycles/block, −5.1/sample, 2.0 %** |

**That is exactly what the memory-traffic model predicted** — four memory
ops per sample deleted, which at roughly one cycle each is 4–8 cycles. The
model and the part agree, which is the useful part of this result.

**It also settles the size of the fusion lever for the biquad chain: 2 %.**
The stage-to-stage structure was never the cost there. A biquad is ~29
instructions of arithmetic measured at ~43 cycles/sample, and its handoff
was already nearly free — the value moved through a pool slot that the next
stage read directly, not through a call or a round-trip to L2.

*(A first reading of this said fusion made FILT **worse**. That comparison
was invalid: the fused arm ran with `DSP4_PROFILE_SIGNAL=1` and the
reference came from a ladder without it, and the biquad's saturation check
is data-dependent. Same silence-versus-signal trap that invalidated the
dynamics numbers, approached from the other side. Both arms are now built
and measured the same way, with the unfused arm produced by stashing the
generator change rather than trusting an older figure.)*

### The rest of the strip does NOT fuse, and the reason is the register file

Fusing further was analysed before building it, using the FILT+EQ result as
calibration: **4 memory ops deleted measured −5.1 cycles/sample, so ≈1.3
cycles per memory op.**

**`_compgain_fx` leaves only four registers standing.** Transitively — it
calls `_exp2q_fx`, and the polynomial form of that reaches r6 — the clobber
set is r0–r6 and r8–r12, so the survivors are **r7, r13, r14, r15**. COMP
already uses all four (attq, dry, envelope, makeup). *Nothing* can carry
another stage's hoisted state across that call.

| fusion | saves | costs | net |
|---|---|---|---|
| COMP → TUBE → FDR | 4 ops/sample (2 boundaries) | 4 ops/sample — TUBE's `sat_q` and FDR's level and pan gains are hoisted **once per block** today and would have to reload **per sample** | **0** |
| GATE → COMP | 2 ops/sample | 7 ops/sample — GATE's seven state words spill and reload around every `_compgain_fx` call | **+5, clearly worse** |

So the general result: **fusing past a node that clobbers most of the
register file is a net loss, because the downstream stages lose their
hoisted invariants.** The saving is bounded by the number of boundaries;
the cost is bounded by the register file, and here the register file is the
smaller number.

This is a calibrated prediction, not a direct measurement — the calibration
comes from the FILT+EQ measurement above. It is recorded as a prediction
deliberately; if the 1.3 cycles/op figure is wanted on this grouping
specifically, the build is small and can be measured.

**What this means for the fusion directive overall.** The measured lever on
the biquad chain is 2 %, and the rest of the strip is net-zero. The strip's
cost is arithmetic — six biquads at ~29 instructions each, and the
compressor's gain computer — and arithmetic does not fuse away. The two
levers that remain large are the ones already measured: **SIMD pairing at
2.39×** and **the core clock at 1.6×**.


## LEVER STACK — numeric deviations for PW sign-off (batch)

Each entry states what it changes, what it is worth, and the **measured**
deviation, not just the theoretical bound. All are behind flags, all
default off, and none is in the shipping image.

### 1. GATE threshold in the linear domain — `DSP4_GATE_LINTHR`

GATE computes `log2(env)` for exactly one purpose: to compare it against a
threshold. `log2(env) >= thr` is `env >= 2^thr`, so the threshold is
converted once per block instead of the envelope 32 times.

| | |
|---|---|
| worth | **101 cycles/sample** (GATE 247.5 → 146.6, measured `NODE_LIMIT` 4→5) |
| theoretical bound | **0.0002 dB** shift of the effective threshold |
| **measured deviation on the part** | **0 differing samples of 120** |

The bound is the sum of the two polynomial errors, each 0.0001 dB worst
case over 0 to −100 dBFS (`log2_q` and `exp2_q` against exact). It is a
fixed offset on the threshold, not per-sample noise, and the linear compare
is *exact* where the log compare carried the polynomial error. Measured on
a real gate-opening transient, nothing differed at all — no envelope sample
landed within 0.0002 dB of the threshold.

**A bug this found, worth recording.** `_exp2q_fx` clobbers **r6**, and the
call was first placed after the attack alpha had been loaded into r6, so
the envelope follower ran on garbage. It measured as a **60 dB** difference
against a 0.0002 dB bound. The size of the discrepancy is what exposed it;
a subtler one might have been accepted as "the expected deviation". Check
the clobber list before placing a call — the same question that was got
wrong about `_compgain_fx` earlier on this page.

### 2. log2/exp2 by interpolated table — `DSP4_DYN_TABLES`

256-entry tables with linear interpolation replace the 6-term Horner
polynomials in `_log2q_fx` and `_exp2q_fx`.

| | |
|---|---|
| worth | **160 cycles/sample** across GATE+COMP (64,145 → 59,037 cycles/block at `NODE_LIMIT` 6) |
| accuracy, log2 | **0.000016 dB** worst — the polynomial it replaces is 0.0001 dB |
| accuracy, 2^f | **0.000008 dB** worst — likewise 0.0001 dB |
| **measured deviation on the part** | **NOT YET ESTABLISHED — see below** |

**More accurate than what it replaces**, which is the unusual part: this is
a numeric deviation from the current `fixed_ref` that moves *towards*
exact, not away. It still needs a spec amendment because the reference
changes.

Two implementation constraints, both discovered rather than assumed:

- **Register contract.** GATE and COMP hold their state in r6–r15 across
  these calls, so the table forms use r0–r5, i0, l0 and MRF and nothing
  else — a strict subset of the polynomial forms, which reached r6.
- **Memory.** Value+delta tables were 1,024 words and **overflowed
  `sec_stak`**. Storing values only and deriving the delta from the
  adjacent entry halves it to 514 words, which fits. `seg_pmda` would have
  been the tidier home — the LDF has a PM-data section described as
  "lookup tables — if any" — but nothing has ever used it and the linker
  does not map it even with a BW-qualified twin. Not worth chasing for
  512 words.

**Deviation measured, after two fixes to the probe and one to the
firmware: 0.00009 dB worst over 200 samples, with the compressor proven
active at −20.98 dB of gain reduction.** That sits between the two
approximations' own errors (0.0001 dB polynomial, 0.000016 dB table),
which is what it should be.

Getting there took three corrections, and the last is a real firmware
defect:

1. The first comparison returned "0 of 200 differ" while the captured peak
   equalled the injected amplitude — the compressor was passing through.
   With the stock attack of 0.001 the envelope only reaches about
   −20.8 dBFS after 200 samples, right at the default −20 dB threshold, so
   the gain computer never left unity. `dsp4_comp_gr.py` now uses a fast
   attack and a threshold well under the signal, and **refuses to print
   samples unless the output is measurably below the input**.
2. With the compressor active, the worst deviation read **1.75 dB at
   sample 25** — mid-attack — while the settled tails agreed. That is the
   envelope-state confound: the envelope persists across runs, so two
   captures start from different points on the transient.
3. **The real one.** The polynomial build's output was FROZEN from sample 1
   at 15,418,270 while the table build converged smoothly. `_compgain_fx`
   calls `_exp2q_fx`, and the polynomial `_exp2q_fx` **reaches r6** — where
   COMP's block kernel was keeping the attack alpha. The envelope follower
   ran on garbage from the second sample of every block.

**That defect was mine, introduced with the COMP block kernel, and masked
by the silent bench** — `_compgain_fx` returns unity before reaching exp2
when the envelope is zero, so the "0 of 32 bit-exact" verification of the
COMP conversion never exercised the path. The register note on this page
originally said only r7, r13, r14 and r15 survive the call; I overrode it
from a scan of `_compgain_fx`'s own text that was **not transitive through
its callees**. The original note was right. COMP now keeps attq in r7 and
reloads the release alpha from DM per sample.


### Speed grade is NOT readable from silicon — checked 2026-08-24

Asked of both running chips over the diag link:

| register | value |
|---|---|
| `TAPC_IDCODE` | `0x128320CB` → **REVID=1 (silicon rev 0.1)**, part 0x2832, mfg 0x065 |
| `CGU0/CDU0/DPM0/L2CTL0_REVID` | 0x30 / 0x11 / 0x20 / 0x04 — peripheral IP revisions |
| `OTPC0_BOOT_RR0/RR1/RR2` | all zero |

`IDCODE` carries **silicon revision, not speed grade** — the anomaly list
says so explicitly, and the JTAG part field 0x2832 is a family ID shared
across the 21560/61/64/68, not an ordering code. No OTP or fuse field
exposes the bin. `KSWZ8` and `KSWZ10` are the same die binned by test and
distinguished on the package marking.

**Do not infer the grade by running at 983.04 and seeing if it survives** —
that would show only that this sample worked at that moment and
temperature. The marking on U5/U6 has to be read.


## FABRIC AND THE MEASURED CEILINGS AT 786 AND 983 — 2026-08-27/28

### The fabric row was not double-counted, and its cost was an ADDRESS

Measured at the ledger's own boundary (`NODE_LIMIT` 320 vs 0) the fabric read
**86,212 cycles/block** against the **85,475** recorded 2026-08-24 — 0.9 %
apart, with the meters inside both. Nothing had been reclassified and nothing
had improved; the 40k row was a real lever.

Where it went, and why:

| segment | cycles/block | share |
|---|---|---|
| 32 meters | 32,324 | 37.5 % |
| cross-ins + talkback + noise | 1,106 | 1.3 % |
| **25 buses + 25 sends** | **52,427** | **60.8 %** |
| 12 inter-chip transfers | 355 | 0.4 % |

52,427 is 32.8 cycles/sample per bus node for ONE round-and-saturate. The
arithmetic never explained that — the 25 x 64-word accumulators were in
`seg_delay`, i.e. **L2 at 0x20000000, off-core and contending with the audio
DMA**. They were there because putting them internal "overflowed sec_stak",
which was not a memory limit but the LDF ordering defect (see the crosspoint
entry above). Moving them internal and inlining the readout:

| segment | before | after | delta |
|---|---|---|---|
| 32 strips | 977,214 | 935,430 | **−41,784** |
| cross-ins + buses + sends | 53,533 | 19,531 | **−34,002 (−63.5 %)** |
| full graph | 1,063,426 | 987,075 | −76,351 (−7.2 %) |
| **FABRIC (320 vs 0)** | **86,212** | **51,645** | **−34,567 (−40.1 %)** |

**The strips fell by more than the buses did** — ROUTING's `_acc64_mac_blk` was
paying the same L2 penalty on every crosspoint MAC. Fabric is now **1.29x** its
40k target, from 2.16x.

### Measured ceilings, converted build, per chip

| `DSP4_STRIPS` | 786.432 MHz | 983.04 MHz |
|---|---|---|
| **15** | **1500/s — ceiling** | — |
| 16 | 1446/s over budget | — |
| **20** | — | **1500/s — ceiling** |
| 21 | — | 1442/s over budget |

Arithmetic and bench agree to the channel, which no previous ceiling figure has
managed. With block I/O 32,707 (carried from 2026-08-24), fabric 51,645 and a
strip of 28,210 cycles/block = **881.6 cycles/sample**:

| clock | budget/block | predicted | measured |
|---|---|---|---|
| 786.432 | 524,288 | 15 | **15** |
| 983.04 | 655,360 | 20 | **20** |

No other value of block I/O predicts both, which retro-validates the carried
figure.

### Meter call inlined — target met, ceilings unmoved

`_mtr_step` inlined into the block loop (1,024 call/rts pairs per block gone,
two constants hoisted), arithmetic reproduced exactly including its quirk that
the new-peak path skips the RMS update:

| | before | after bus fix | + meter inline |
|---|---|---|---|
| 32 meters | 32,324 | 31,816 | **20,921** |
| **FABRIC (320 vs 0)** | 86,212 | 51,645 | **40,109 — target MET** |
| full graph | 1,063,426 | 987,075 | 975,578 |

**The ceilings did not move.** 786 stays 15 (16 now marginal at 1487/s, was
1446 over budget); 983 stays 20 (21 now marginal at 1471/s, was 1442). The
harness labels 1487 and 1471 REAL_TIME because its threshold is 1450 — by the
rule recorded 2026-08-24, anything under 1500 is dropping blocks. The inline
bought half a channel of margin, not a channel.

**The fabric row in the lever stack is now spent.** What remains for 32-in-one
is SIMD across the strip and the dynamics rework; the strip is untouched at
881.6 cycles/sample.

### THESE ARE SILENCE MEASUREMENTS — the governing caveat

`strips_run.sh` injects nothing and the bench has no analog input, so the gate
is closed and the compressor idle. The recorded 786 ceiling of **10** was taken
signal-present. The pre-fabric numbers measured the same night project **13.3**
at 786 against that 10, so **signal costs about a quarter of the headroom**:

| | silence (measured) | signal-present estimate |
|---|---|---|
| 786.432 | 15 | **~11–12** |
| 983.04 | 20 | **~15–16** |

**Do not quote the silence figures as the feasibility answer.** A
signal-present sweep is queued as the next rung in tasks.md — it is the number
that decides D32-on-card at 983, where a two-chip split needs 16/chip against a
15–16 estimate. Note that 16/chip is not a free split: chip 2's own graph is
3.8x over the same budget (2026-08-24, also silence). A
signal-present sweep needs a stimulus on every strip at once; the scope reaches
one input slot, so it does not. That measurement is the next thing this line of
work needs.

### The 32-in-one verdict, updated

**D24's 24 channels do not fit one chip at 983** — 20 measured in silence,
~15–16 with signal. D32's 32 are further still. Chip 2 remains 3.8x over its
own budget (2026-08-24, also silence) and is not the escape route. The 786
ceiling has moved **10 → 15** across this week in silence terms and the fabric
is 40 % cheaper, so the direction is right — but the remaining gap is a
**factor, not a margin**, and nothing left in the fabric closes it alone.

The largest single item still in the fabric is the meters at 32,324
cycles/block; decimating them recovers ~26,000 but changes what they report,
and they carry four recorded defects. **PARKED FOR PW** — see tasks.md.


## THE MEASURED CEILING AT 786.432 MHz, AND THE 32-IN-ONE VERDICT

Fully converted build, **signal present** so the dynamics take their real
path, no decimation, judged on `_proc_passes`:

| `DSP4_STRIPS` | `_proc_passes` | verdict |
|---|---|---|
| 8 | 1500/s | real time |
| 9 | 1500/s | real time |
| **10** | **1500/s** | **real time — the ceiling** |
| 11 | 1472/s | **marginal — dropping ~2 % of blocks** |
| 12 | 1377/s | over budget |
| 14 | 1219/s | over budget |

`dsp4_audio_verdict.py` calls 1472/s REAL_TIME because its threshold is
1450, but 1472 is not 1500 and blocks are being dropped: **10 is the honest
ceiling, 11 is marginal.**

Two rows had to be thrown away rather than read as data, both worth
recording:

- A first pass at `STRIPS=10` returned `0 passes/s` with `BOOT_STAGE 5` —
  the part never got past waiting for config, so it never ran the graph at
  all. Read as over-budget it would have put the ceiling at 9.
- `STRIPS=11` failed to link with unresolved symbols because **I ran a
  verification build in the same tree while the sweep was using it.** Two
  builds, one `build/` directory. The clean retry succeeded.

### The verdict, plainly

| | cycles/block |
|---|---|
| budget at 786.432 MHz | 524,288 |
| block I/O | 32,707 |
| fabric (converted) | 85,475 |
| **available for channels** | **406,106** |
| **needed per channel for 32** | **397 cycles/sample** |
| **actual, measured** | **1,269 cycles/sample** |

**32 channels in one 21564 at 786.432 MHz is NOT reachable. The measured
ceiling is 10.** That is a factor of **3.2** short, and the measurement
agrees with the arithmetic (which predicted 11) to within one channel.

What the remaining levers are worth, applied to the measured figure:

| | cycles/sample | channels/chip |
|---|---|---|
| today | 1,269 | **10** |
| + SIMD pairing (2.39×, measured, not yet wired into the graph) | 615 | 20.6 |
| + dynamics rework (GATE log removed, COMP tabled) | 491 | 25.8 |
| + fabric at its 40k target | 491 | **28.7** |
| **the same, at 983.04 MHz** | 491 | **37.0** |

So even with **every** lever landed — SIMD across the strip, both dynamics
changes, and the fabric hitting a target it is currently 2.1× away from —
786.432 MHz reaches about **29 channels, not 32**. The last row is the one
that closes it, and it needs a `KSWZ10` part.

### And chip 2 is not the escape route

Chip 2's own graph measures **1,978,933 cycles/block** — **3.8× over** the
same 524,288 budget, essentially the same load as chip 1, and that is a
**silence** reading so the true figure is higher. Its 235 nodes are 17
graphic EQs, 21 EQ biquads, 18 limiters, 24 fader/pans, 15 delays, 12
anti-feedback, 10 compressors and 6 FX engines.

Earlier in this work I described chip 2 as "comparatively idle" and built
two-chip splits on it. **That was an assumption, never a measurement, and it
was wrong.** No split that moves work to chip 2 survives until chip 2's own
load is cut first.


## 786.432 MHz ENABLED — 2026-08-24 (PW decision)

`DSP4_CCLK_TARGET=786`. **Measured on the part: CCLK 786.29 MHz against a
786.43 target, 0.02 % off.** The measurement is the diag tick itself:
`DIAG_TPERIOD` is built as 786,432 for a 1.000 ms tick, so a tick rate of
999.8/s *is* the clock. Had the CGU write silently failed, the tick would
have run at 625/s.

786.432 MHz is legal on **both** speed grades, so it needs no answer to the
`KSWZ8` vs `KSWZ10` question. 983.04 MHz stays prepared and off.

| | |
|---|---|
| cycles/block, was | 327,680 |
| **cycles/block, now** | **524,288** |
| gain | **1.60×** |

Stability at the new clock, `DSP4_STRIPS=1`:

| | |
|---|---|
| `_proc_passes` | **1500/s — REAL_TIME** |
| `FRAME_COUNT` | 1499.9/s |
| `SPORT0_ERR_A` | 0x00000000 |
| `DMA0_STAT` | 0x00006200 (RUN, no error) |
| `BLK_OVERRUN` | 8,593 and **static** over 8 s — accumulated during boot, not climbing |

`DIAG_TPERIOD` now tracks `DSP4_CCLK_TARGET`. It has to: the tick is the
instrument every cycle figure here is derived from, so a stale value would
silently rescale every measurement rather than fail. The `dma_config.c`
busy-loop delays are deliberately NOT rescaled — they are debug-only
(`DSP4_BISECT != 0`) and the stagewatch decoder reads ratios.

**786.432 is also the gentler choice on the peripherals.** SCLK0 moves only
61.44 → 65.536 MHz (6.7 %), where 983.04 would take it to 81.92.

### Bit-exactness at the new clock — RE-ESTABLISHED, and how the probe was wrong

`chain.py` returned values that looked like a regression. It is not one —
and the control run is what settles it:

| build | result |
|---|---|
| 786 MHz + fabric conversion | same values |
| 491 MHz + fabric conversion | **same values** |
| 491 MHz, no fabric conversion (control) | **same values** |

Identical in all three, so **neither the clock nor the fabric conversion
changed anything**. What expired is the probe's assumption. `chain.py`
checks `mono == input`, which held when only IN, GAIN, FDR and RTG were
converted — FILT, EQ, GATE, COMP, TUBE and DLY were unconverted then, never
touched the pool, and the strip really was transparent. All six are
converted now and the gate and compressor are **on by default**, so they
legitimately change the signal. Bypassing them over SPI moved `mono`
straight back to an exact power-of-two multiple of the input.

`chain.py` now **configures the strip it tests** — unity gain, unity
filters, unity EQ, dynamics bypassed, no delay — and assumes nothing. What
it does not set, it does not trust.

**Result at 786.432 MHz, with the fabric conversion in: BIT-EXACT, 0 of 7
cases.** mono, pan-split L and the summed bus all land exactly on the model
across level 1.0/0.5/0.25 and pan 0/0.25/0.5/0.75.

**It also runs a negative control, and the control earned its keep
immediately.** A probe that reports the input back could pass while reading
a dead buffer, so it halves the gain and requires the reading to change.
On the first run it did NOT change — because ramped parameters were being
written with `ramp_id=0`. That takes the INSTANT path, which sets only the
level word, and the node's block-rate code then does
`if frames <= 0: level = target` and clobbers it from a target never
written. This is already documented in `wrv()` and I walked into it anyway;
the control is the only reason it surfaced instead of becoming a false
pass. Gain, fader level, pan and DCA now go through `wrv(..., ramp_id=1)`.

That makes three checks on this bench that could not have failed as first
written — the `both_unity` biquad test blind to state, the delay test run
on 27 samples of silence, and this one. The lesson is now enforced in the
probes themselves rather than remembered.

### Fabric conversion — first cut measured

| | cycles/block |
|---|---|
| per-sample (original) | 95,434 |
| **buses + sends in block form** | **54,654** |
| | **1.75×** |

25 `MIX_BUS` and 37 `INTERCHIP_SEND` converted: one call per block instead
of 32, bus outputs and TX slots became 32-word arrays, and the gather now
indexes by sample. That last part was a live trap — the gather carried a
comment saying it deliberately did not index because nothing converted
wrote a TX slot, which stopped being true the moment the sends converted.
Left alone it would have transmitted sample 0 thirty-two times.

### The meters converted, and the 54,654 was indeed a floor

| | cycles/block |
|---|---|
| per-sample (original) | 95,434 |
| buses + sends converted, **meters still running once per block** | 54,654 |
| **buses + sends + meters, all running correctly** | **85,475** |

**The meters cost 30,821 cycles/block once they actually run** — and that
is the honest number. The 54,654 figure counted 32 meters at 1/32 of their
work, which is exactly the kind of flattering measurement the ordering was
meant to prevent; it is recorded here rather than quietly replaced.

So the fabric conversion is worth **95,434 → 85,475, only 1.12×**, not the
1.75× the intermediate number suggested. Converting buses and sends really
did remove most of their call overhead; correcting the meters gave a large
part of it straight back, because they had been skipping 31 of every 32
samples.

Against the dispatch's 40k target: **still 2.1× over.** At 786.432 MHz it is
**16.3 % of the 524,288-cycle budget**, down from 29.1 % of the old one.

**A self-inflicted cost still in that figure.** My meter block kernel calls
a per-sample subroutine rather than inlining the body, to avoid duplicating
arithmetic whose defects are under a separate open decision — 32 calls per
meter per block, about 6,100 cycles/block of pure call overhead across the
32 meters. Inlining it is straightforward and is the obvious next cut, but
it belongs with whatever the hub decides about the meters themselves.

### Meters: what was fixed and what deliberately was not

Every chip-1 meter taps its own channel's GAIN output, which under block
kernels lives in a shared pool slot the next strip overwrites. At chain
index 320+ each meter was reading data **thirty-one channels stale**. They
now run immediately after their source, and sample all 32 samples.

Two guards this needed, both found by checking rather than by the build
failing:

- The reorder initially changed the **shipping** image, because the guard
  was on the numeric format (always true) rather than on block kernels. The
  meter call is now emitted in BOTH positions, each `#if`-guarded, so the
  per-sample image keeps its bytes and its node indices.
- The relocated call carried no `NODE_LIMIT` guard, which would have made
  `DSP4_NODE_LIMIT` mean different things in the two builds — and the
  fabric measurement IS `NODE_LIMIT` 320 versus 0, so it would have started
  counting meters as strips. It now carries its original index.

**The meter arithmetic is unchanged, deliberately.** The four recorded MTR
defects — reading a Q4.28 word as an IEEE float among them — are still
there. Converting a node to block form is not the moment to quietly change
its numerics, and whether to fix or retire the meters is still the hub's
open decision. This fixed only WHEN a meter samples, not WHAT it computes.
It is now 30,821 cycles/block of known-defective work, which is an argument
for settling that decision.


## THE CORE IS RUNNING AT HALF ITS RATED SPEED — 2026-08-24

Everything on this page is measured at **CCLK 491.52 MHz**. The datasheet
(Rev. A, Feb 2026, now local) rates the ADSP-21564 at **800 MHz or 1 GHz**
depending on speed grade:

| ordering code | instruction rate | L2 |
|---|---|---|
| `ADSP-21564KSWZ8` | **800 MHz** | 2 MB |
| `ADSP-21564KSWZ10` | **1 GHz** | 2 MB |

And per decision **D10 the firmware does not program the CGU at all** — the
part runs on reset defaults (MSEL=40, the PLL's built-in ÷2, CSEL=1). D10
concluded a CGU write "would buy nothing and cost a PLL relock during
boot". That was correct when it was written and is **no longer true**: it
buys between 1.6× and 2.0× of the entire cycle budget, which is a larger
lever than SIMD, fusion and every kernel conversion on this page combined.

### The clock tree, audio-coherent at each option

`SYS_CLKIN0` is 24.576 MHz. `S0SEL`/`S1SEL` scale with `MSEL` so the
peripheral clocks — and therefore all TDM timing — stay exactly where they
are; only CCLK and SYSCLK move.

| | CCLK | SYSCLK | SCLK0 | SCLK1 |
|---|---|---|---|---|
| today, MSEL=40 S0SEL=4 | 491.52 | 245.76 | 61.44 | 122.88 |
| MSEL=64 S0SEL=6 | 786.43 | 393.22 | 65.54 | 131.07 |
| **MSEL=80 S0SEL=8** | **983.04** | **491.52** | **61.44** | **122.88** |

Datasheet ranges: fCCLK 400–1000, fSYSCLK 200–500, fSCLK0 30–125, and
Table 14 requires **fCCLK = 2 × fSYSCLK** — satisfied by all three rows.
**MSEL=80 is the clean one**: exactly 2×, still audio-rational (983.04 MHz
= 48 kHz × 20480), SCLK0 and SCLK1 unchanged, every clock in range.

### What it does to the fit

Fabric at its 40k target, signal-present strip, SIMD on:

| | budget/block | available | channels (SIMD) | channels (SIMD + dynamics rework) |
|---|---|---|---|---|
| 491.52 MHz (today) | 327,680 | 254,973 | 14.0 | 17.8 |
| 786.43 MHz | 524,288 | 451,581 | 24.7 | 31.6 |
| **983.04 MHz** | **655,360** | **582,653** | **31.9** | **40.7** |

**At 983.04 MHz, 32 full-function channels fit one 21564** — right on the
line with SIMD alone, comfortably with the dynamics rework. On the two-chip
card that is the D32 product with genuine headroom, which is what the
priority asked for.

### What has to be checked before relying on this

1. **THE FITTED SPEED GRADE IS UNKNOWN AND IT DECIDES THIS.** 983.04 MHz is
   legal on a `KSWZ10` and **over spec on a `KSWZ8`**, whose ceiling forces
   the 786.43 MHz row instead. Read the part marking on the card. Nothing
   here should be committed to until that is known.
2. **Power and thermal.** Roughly 2× the core clock is roughly 2× dynamic
   core power, on a board whose thermal design assumed the reset default.
3. **D10's original objection still applies to *when*, not whether** — a
   PLL relock with the boot kernel's SPI transfer in flight. Programming
   the CGU after boot completes avoids it.
4. **The anomaly list** has not been checked for PLL/CGU errata.
5. Every CCLK-derived constant moves with it: `DIAG_TPERIOD`, the
   `dma_config.c` busy-loop delays, and the profile instrument's own
   cycles-per-tick.

This does not retire any measurement on this page — the cycle *counts* are
properties of the code, not the clock. It changes what they are measured
against.


Measured on the rev-C bench, chip 1 (DSPA/U6), production firmware with a
d24 product config committed. Measurement, not estimate: the block loop
reads the core timer `TCOUNT` either side of each 32-sample block pass and
combines it with the 1 kHz diag tick,

    cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
           + (tcount_start - tcount_end)

which is exact to the core clock. `_proc_cyc` holds the last pass and
`_proc_cyc_max` the worst seen; both are readable over the diag peek
window. `MW/D32/DSP/SHARC/profile.sh` drives it across `DSP4_NODE_LIMIT`
points and `bisect.sh` verifies every build flag against a stamp read back
off the running part.

## The budget

| | |
|---|---|
| core clock | 491.52 MHz (measured, not assumed) |
| block rate | 1500 blocks/s = 48 kHz / 32 samples |
| **cycles available per block** | **327,680** |

## Where the budget goes

| item | cycles/block | % of budget |
|---|---|---|
| block I/O — scatter, gather, meter scan | 64,758 | 19.8% |
| buses, sends, cross-ins, transfers | 79,408 | 24.2% |
| **fixed overhead before any strip** | **144,166** | **44.0%** |
| one channel strip (10 nodes) | 63,131 | 19.3% |
| **all 32 strips** | **2,020,192** | **616%** |
| **full graph (431 nodes), measured** | **2,164,358** | **660%** |

The full chip-1 graph is **6.6× over budget**. This supersedes the earlier
"~16×", which came from power-of-two decimation thresholds and carried
their margin; the direct cycle count is the number to use.

## Cost per node class

Differenced across consecutive `DSP4_NODE_LIMIT` points within one strip,
so every row is one real node of that class running in place in the chain.
Per-sample is per-block ÷ 32.

| class | cycles/block | cycles/sample | share of a strip |
|---|---|---|---|
| **RTG** | **19,237** | **601** | **30.5%** |
| EQ | 10,812 | 338 | 17.1% |
| FILT | 7,254 | 227 | 11.5% |
| GATE | 6,539 | 204 | 10.4% |
| COMP | 6,453 | 202 | 10.2% |
| DLY | 4,720 | 148 | 7.5% |
| FDR | 4,082 | 128 | 6.5% |
| GAIN | 2,005 | 63 | 3.2% |
| TUBE | 1,269 | 40 | 2.0% |
| IN | 760 | 24 | 1.2% |
| **strip total** | **63,131** | **1,973** | 100% |

### Re-measured 2026-08-24, post-fix build — KERNEL REWRITE baseline

The table above was taken before the biquad, compressor, fader and ramp
fixes. GAIN re-measured on the current build as the reference the rewrite
must beat:

| point | cycles/pass |
|---|---|
| `DSP4_NODE_LIMIT=1` (IN only) | 67,809 |
| `DSP4_NODE_LIMIT=2` (IN + GAIN) | 70,130 |
| **GAIN** | **2,321 cycles/block = 72.5 cycles/sample** |

72.5 cycles/sample for a load, a multiply, a round and a store is almost
all overhead: a `call`/`rts` per sample, the `_sample_idx == 0` guard
re-evaluated 32 times, and a second `call`/`rts` into `_mrf_rns28`. That is
the case for per-block kernels, now measured rather than assumed.

### KERNEL REWRITE — GAIN converted 2026-08-24 (`DSP4_BLOCK_KERNELS=1`)

First family through the per-block conversion. Measured at the same
profile points, same build otherwise:

| point | per-sample | per-block | delta |
|---|---|---|---|
| `NODE_LIMIT=1` (IN only) | 67,809 | 62,238 | −5,571 |
| `NODE_LIMIT=2` (IN + GAIN) | 70,130 | 62,811 | −7,319 |
| **GAIN alone** | **2,321** (72.5/sample) | **573** (17.9/sample) | **4.05× faster** |

**Bit-exact: 0 LSB** against `fixed_ref` at gains 1.0, 0.5, 0.25, 2.0,
0.001 and 7.94328, with all 32 samples of the block identical under a step,
as they must be.

What the 4× came from, in order of size: the per-sample `call`/`rts` into
the node, the `_sample_idx == 0` guard re-evaluated 32 times per block, and
a second `call`/`rts` into `_mrf_rns28` — all of it overhead around a
load, a multiply, a round and a store. The kernel hoists the coefficient,
folds polarity and mute into it once (mute is exactly `x*0` in this
format), and inlines the rounding with its constants hoisted. The
saturation fix-up is a **conditional move rather than a branch**, so the
body stays inside a hardware loop.

IN dropped too — a 32-iteration copy loop instead of 32 calls.

The same overhead is paid by every one of the 431 nodes, so this ratio is
the case for the rest of the conversion. Next: RTG (601 cycles/sample, the
measured hot spot) and the bus/send path.

`DSP4_BLOCK_KERNELS=0` remains the default and the bit-exact reference: the
default build is **byte-identical** to the pre-conversion image, so the
shipping path is provably untouched.

### KERNEL REWRITE — RTG converted 2026-08-24 (cycles only, see caveat)

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=9` (through FDR) | 110,872 | 67,171 |
| `NODE_LIMIT=10` (+ RTG) | 130,058 | 69,790 |
| **RTG alone** | **19,186** (599.6/sample) | **2,619** (81.8/sample) |

**7.3× faster.** The per-sample figure reproduces the 601 cycles/sample in
the table above, which is a useful check on the instrument.

The MACs were never the cost. With only MAIN enabled by default that is
two `_acc64_mac` calls, about 30 cycles — buried inside 22 gated loop
iterations that were re-evaluated on every one of the 32 samples. The block
form runs the whole gating tree **once per block** and turns each enabled
contribution into a single `_acc64_mac_blk` over the block.

**CAVEAT — this is a cycles-only result.** RTG reads FDR's buffers, and FDR
is not converted yet, so the block accumulate walks past a scalar and the
DATA is garbage. Code shape and memory traffic are representative, so the
cycle count stands; bit-exactness cannot be claimed until the chain between
GAIN and RTG is converted. Recorded as measured, not as verified.

### The binding constraint is MEMORY, not cycles

Converting RTG needs per-sample bus accumulators — 25 buses × 32 samples ×
2 words = **1,600 words against 50** — and that **overflowed DM**:
`Out of memory in output section 'sec_stak'`. The IN+GAIN conversion had
already left under ~1.5 K words of headroom on chip 1.

Block buffers are expensive: every converted node's buffer becomes 32
words, and on chip 1 the IN nodes alone (46 × 64 for slot + buffer) are
~2.9 K words. A full conversion of the ten strip classes would want roughly
13–14 K extra words of internal DM, which the part does not have.

The accumulators are parked in L2 (`seg_delay`) to unblock the measurement,
which if anything makes the 2,619 figure **conservative** — L2 is slower
than internal DM.

**The real fix is buffer reuse.** A strip is a linear chain, so a node's
block buffer is dead as soon as its consumer has run: two ping-pong block
buffers per strip suffice instead of one per node — 64 words instead of
320, and it scales. That belongs in the generator as a buffer-pool
assignment, and it should land before the remaining classes are converted
rather than after.

### Buffer reuse landed 2026-08-24 — the memory blocker is gone

One buffer per node does not fit. Strips run **sequentially** (the call
chain is strip-ordered), so a strip's working set is dead the moment its
RTG has accumulated into the buses, and every strip can reuse the same
slots. One shared pool of **8 slots × 32 samples = 256 words** serves all
32 strips:

| slot | use |
|---|---|
| A, B | chain ping-pong: IN→A GAIN→B FILT→A EQ→B GATE→A COMP→B TUBE→A DLY→B FDR→A |
| FDR_L, FDR_R | pan split, live until the router has read both |
| TAP_TRIM, TAP_EQ, TAP_PREFDR, TAP_POSTFDR | the four taps the router picks from — these span the whole strip, so they cannot share the pair |

Measured `sec_dmda` on chip 1:

| build | words |
|---|---|
| default (per-sample) | 20,840 |
| block kernels, one buffer per node | **overflowed `sec_stak`** |
| block kernels, shared pool | **22,472** (+1,632) |

GAIN re-verified against `fixed_ref` reading its pooled slot rather than a
private buffer: still **0 LSB** at all six gains.

**Headroom is still under ~1,600 words.** Moving the bus accumulators back
from L2 to internal DM takes it to 24,072 and overflows again, so they stay
in L2 for now. The next reclaim is the **1,472 words of RX slot arrays**,
which disappear entirely if the IN kernel reads the DMA buffer directly and
does the Q1.31→Q4.28 shift itself — that removes a whole copy as well as
the storage.

### RX slot reclaim 2026-08-24 — scatter deleted, block I/O nearly halved

The `INPUT_TDM` kernels now read the DMA buffer **directly**, doing the
Q1.31→Q4.28 shift inline, using the lane offset and stride that
`gen_block_io` already computes and now hands to each node. Staging 46
channels into slot arrays first was pure cost: 1,472 words of DM **and** a
copy per sample per channel. `_scatter_chip1` is a bare `rts` under the
flag.

| point | per-sample | per-block | ratio |
|---|---|---|---|
| `NODE_LIMIT=1` — block I/O + IN | 67,809 | **32,707** | **2.07×** |
| GAIN alone | 2,321 | 574 | 4.04× |
| RTG alone | 19,186 | 2,626 | 7.3× |

`NODE_LIMIT=1` is a fair like-for-like: both block I/O and IN are fully
converted there. Nearly half the fixed overhead at that point was a copy
that did not need to exist.

`sec_dmda` on chip 1 across the whole conversion:

| build | words |
|---|---|
| default (per-sample) | 20,840 |
| block kernels, buffer per node | overflowed |
| + shared pool | 22,472 |
| + RX reclaim | **21,046** (+206 over default) |

**The DM ceiling is about 22,500 words**, tighter than it looked: putting
the 1,600 words of bus accumulators back internal reaches 22,646 and still
overflows, so they stay in L2 — which makes the RTG figure conservative
rather than optimistic.

One regression to note against the flag: the boot-time input patch
(`_rx_patch_regs`, which lets a D24 console remap which slot var receives
which RX channel) is bypassed when the kernels read DMA directly. It needs
folding into the per-node offset before this path can ship.

### FILT/EQ attempted and REVERTED 2026-08-24 — what the biquads need

The straightforward conversion — wrap the existing per-sample body in a
32-iteration loop driven from the pool — builds and runs but produces
**silence**, and it is reverted rather than left behind the flag.

Two things were learned and both matter for the retry:

1. **The active coefficients start at zero.** `_filt_hpf_A/B` have no
   initialiser, so a FILT node outputs nothing at all until a coefficient
   write and swap have happened. That is true of the shipping per-sample
   path too — worth knowing on its own — and it means "outputs zero" is the
   node's resting state, not necessarily evidence of a broken conversion.
2. **The swap/crossfade machinery is block-rate and was left per-sample.**
   Moving the `swap_pending -> _filt_start_xfade` check into the wrapper
   fixed one restart-every-sample bug, but the crossfade *alpha* advance
   and the A/B instance state are still per-sample inside the body, and the
   filter still did not converge. The crossfade plane has to be split
   properly — advance once per block by 32 steps, exactly as the ramps
   were — rather than wrapped wholesale.

So the biquads are not a wrap-it-and-go conversion like GAIN and RTG were.
They also stand to gain least from block form: their cost is real
arithmetic, not call overhead. The genuine lever for them is a
**register-resident block cascade** — load the biquad state into registers
once, run 32 samples, store it back — which removes roughly 12 memory
operations per sample per stage. That is a new library routine and wants
its own bit-exactness pass against `fixed_ref.biquad`.

Kept from the attempt, because it is needed by everything downstream: the
harness can now inject a whole block from **inside** the node chain
(`_scope_inject_blk`, called straight after the input node). The old
per-sample hook wrote an RX slot variable, and those no longer exist now
that the input kernels read DMA directly. GAIN re-verified through the new
hook: still 0 LSB at all six gains.

### Register-resident block cascade added 2026-08-24 — routine in, wiring open

`_bq_fx_cascade_blk` (`src/lib/biquad_fx.asm`, behind the flag) cascades a
whole block with the biquad state held in **registers**: six loads and six
stores per SAMPLE become six per STAGE. The per-sample arithmetic is a
line-for-line copy of `_bq_fx_cascade_N`, so it should be bit-exact by
construction.

The reordering is stage-at-a-time rather than sample-at-a-time. That is
safe for a **cascade** specifically: each stage is causal with its own
state, so running stage k over the whole block before stage k+1 produces
the same samples in the same order. It would NOT be safe for a feedback
topology across stages.

Register budget is the reason coefficients are still re-read per sample
(one instruction each): six state registers plus five coefficients plus
working room does not fit in sixteen.

**Wiring FILT/EQ is still open, but the search is now narrow.** Second
attempt, wired per the plan below and reverted again — with two real
findings banked on the way:

**Fixed and kept: the pool had a slot-clobber bug.** Every `INPUT_TDM`
node wrote `BLK_CHAIN_A`, but the non-strip inputs (`C1_XIN_*` — Pi,
codec, MEMS, sinks) are **not** covered by the `DSP4_STRIPS` gate, so they
run after the strips in the call chain and overwrote strip 1's slot *after*
its FILT had already written it. The symptom was a filter that looked
completely dead while its own state and linkage scalar showed it computing
correctly — which is what finally localised it. Non-strip inputs now get
private 32-word buffers; only strip inputs share the pool. This was a
latent hazard for every future class, not just FILT.

**Still open, and now precisely bounded:** with the block cascade wired,
`both_unity` passes at **0 LSB** while every real filter fails
(worst 1.2e8). Unity is exactly the case where the feedback terms cancel,
so the fault is in **state handling under genuine feedback** in the
register-resident loop — not in the MAC chain, the coefficient conversion,
the two-call HPF/LPF structure, or the block plumbing, all of which unity
exercises. Prime suspects in order: interaction with the MAC unit's
implicit registers across iterations, and m-register interference
(`_bq_fx_cascade_blk` sets m1/m2/m3 while `_bq_fx_cascade_N` also uses m1).

Also spotted while tracing, not yet biting: `_bq_fx_cascade_blk` never
advances `i0` between stages — the per-sample rewind leaves it on stage 0's
coefficients. FILT calls it once per section with `r4 = 1` so it does not
show, but EQ uses `r4 = 4` and would.

The plan the attempt followed, which still looks right:

1. Steady state uses `_bq_fx_cascade_blk` in place over the block, called
   once per section (HPF then LPF; their coefficient arrays are separate,
   and `i1` walks on to the next stage's state exactly as the per-sample
   version relies on).
2. **Crossfade keeps a per-sample fallback** — loop the existing body 32
   times. A crossfade lasts ~18 blocks and is a transient, so its cost does
   not matter, and this stops the A/B instance and alpha bookkeeping from
   having to be re-derived in block form. That bookkeeping is what defeated
   the first attempt.
3. Block-rate work — the `swap_pending -> _filt_start_xfade` check — runs
   ONCE in the wrapper, never inside the sample loop.

Expected gain is roughly 30 % on FILT (227 cycles/sample) and EQ (338),
about 8-9 % of a channel strip. Worth having, but note it is a much smaller
lever than the ones already taken: the big wins came where overhead
dominated, and biquads are arithmetic-bound.

### COMP wrapped 2026-08-24 — bit-exact, and MEASURABLY SLOWER. Reverted.

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=5` (through GATE) | 94,529 | 34,056 |
| `NODE_LIMIT=6` (+ COMP) | 100,761 | 40,813 |
| **COMP alone** | **6,232** (194.8/sample) | **6,757** (211/sample) |

The wrapper was bit-exact — the sweep returned values identical to the
per-sample family run that scored 0 LSB — and it cost **8 % more cycles**.

**Why, and it generalises: a wrap on its own is worthless.** It replaces
"`process_all` calls the node 32 times" with "the node calls its own body
32 times". The same number of calls happen, plus loop bookkeeping, and
nothing is hoisted. GAIN's 4× did **not** come from being wrapped; it came
from what the wrap made possible — dropping the `_sample_idx` guard,
hoisting the coefficient and the polarity/mute decision out of the loop,
and inlining `_mrf_rns28` with its constants. RTG's 7.3× likewise came from
running the gating tree once, not from looping.

So for every remaining class the question is not "can it be wrapped" but
"how much work can be lifted out of the sample loop". For COMP that is the
`_sample_idx` guard, four parameter loads, and two `_mrf_rns28` calls —
perhaps 30 of 195 cycles/sample, so ~15 %. The genuine lever is the one the
plan already names: run the **log2/exp2 gain computer at block rate and
interpolate the gain per sample**, which is a numeric change and needs a
`shared/numeric-spec.md` amendment with a stated error bound before it can
be verified against anything.

### FDR converted 2026-08-24 — 2.33x, and the chain is now verified

| point | per-sample | per-block |
|---|---|---|
| `NODE_LIMIT=8` (through DLY) | 106,460 | 34,454 |
| `NODE_LIMIT=9` (+ FDR) | 110,864 | 36,340 |
| **FDR alone** | **4,404** (137.6/sample) | **1,886** (58.9/sample) |

Same treatment that worked for GAIN, and for the same reason: the three
coefficients and the mute decision hoisted out of the loop, and all three
`_mrf_rns28` calls inlined with their constants held. Mute folds into the
gain because `x*0` is exactly 0 in this format. Bus faders (AUX/GRP/SUB/FX)
are mono and get the same kernel without the pan split.

**RTG is no longer cycles-only.** With FDR converted, `GAIN -> FDR -> RTG ->
BUS` is a contiguous run of converted nodes through the shared pool, and it
verifies **0 LSB at 7 points** across level 1.0/0.5/0.25 and pan
0/0.25/0.5/0.75 — mono, pan-split L, and the summed bus all bit-exact
against `fixed_ref`, with the 64-bit accumulator's single round at readout
included.

Two capture traps worth recording, both mine rather than the DSP's: under
block kernels the scope indexes its source by sample, which is right for a
pool array and **wrong for a scalar** — reading index 1 of
`_buf_C1_BUS_MAIN_L` reads the word after it. That made a working bus read
as zero twice before the accumulator itself was checked and found correct.

### The compressor's gain computer is only 9.6 % of it — measured 2026-08-24

`DSP4_STUB_COMPGAIN=1` makes `_compgain_fx` return unity immediately, so
the difference against a normal build is exactly what the log2/exp2 gain
computer costs:

| build | COMP cycles/block |
|---|---|
| normal | 6,232 |
| `DSP4_STUB_COMPGAIN=1` | 5,634 |
| **gain computer** | **598 (18.7 cycles/sample, 9.6 % of COMP)** |

**This kills step 4 of the rewrite plan as written.** That step proposed
running the gain computer at BLOCK rate with per-sample interpolation, and
called for a `shared/numeric-spec.md` amendment with an error bound to
justify the approximation. The prize is 9.6 % of one node class — about
1 % of a channel strip — in exchange for making the dynamics no longer
bit-exact against `fixed_ref`. **Not worth it.** The polynomials were the
obvious suspect and they are not the problem; that is exactly why it was
worth measuring before amending a numeric spec.

The other 90 % is structure: the `_sample_idx` guard, three library calls
per sample (`_envq_fx` and two `_mrf_rns28`), the parameter loads, and the
parallel blend. Hoisting and inlining those is bit-exact and needs no spec
change — but `_compgain_fx` and its callees clobber r0-r6 and r8-r12, so
only **r7, r13, r14, r15** survive the call. Almost nothing can be hoisted
ACROSS it, which caps the realistic saving at roughly 26 cycles/sample
against the ~16 cycles/sample the wrapper itself costs. Net ≈ 5 %.

So COMP and GATE are, on this evidence, **not worth converting**: the
overhead that block form removes is not where their time goes. That is a
different answer from GAIN and RTG, and it is the measurement that says so
rather than a judgement call.

### Biquads — PARKED 2026-08-24, state note

FILT/EQ are the second-biggest strip cost (227 and 338 cycles/sample,
together 29 % of a strip) and come back after the dynamics. State at the
park:

- `_bq_fx_cascade_blk` exists, assembles, and is unused. Its per-sample
  arithmetic is a line-for-line copy of `_bq_fx_cascade_N`.
- Wired to FILT, `both_unity` passes at **0 LSB**; every real filter fails.
  Unity is exactly where the feedback terms cancel, so the fault is in
  **state handling under feedback** in the register-resident loop — the MAC
  chain, coefficient conversion, HPF/LPF two-call structure and block
  plumbing are all exercised and correct.
- **FIXED since the park:** `_bq_fx_cascade_blk` now advances `i0` by five
  between stages (and restores the per-sample rewind), so `r4 > 1` is
  correct and EQ's four bands are no longer blocked on it.

### 2026-08-24, self-test on the part: the block routine is NOT the fault

`_bq_fx_cascade_blk` was run against `_bq_fx_cascade_N` on byte-identical
data **inside the part** (`DSP4_BQ_SELFTEST`, `src/lib/bq_selftest.asm`),
and it is **bit-exact: 0 differing samples of 64, max |diff| = 0.**

The test was built to be hostile to the recorded suspects:

- **Two stages with DIFFERENT coefficients** — 1 kHz LPF Q0.707 then 300 Hz
  HPF Q2. Equal stages would hide a stage-pointer fault; unity stages hide
  everything.
- **An impulse followed by silence**, so every sample after the first is
  pure feedback tail — the ringing crosses zero inside the block
  (`ref[31] = −3,884,542`), so this is not a degenerate signal.
- **Two consecutive blocks off one state array**, which is exactly the
  block-boundary persistence case, and samples 32–63 match too.

So both of yesterday's sharpened suspects are cleared *for the routine*:
in-block state handling and cross-block persistence are correct. What the
test cannot clear — because it supplies them itself — is how the **node
wrapper** drives `i0`, `i1` and `i2`, and the A/B-instance and crossfade
bookkeeping around them. That is now the whole of the remaining suspect
space, and it is a much smaller one.

This is the second time on this page that a conclusion about the biquads
came from a test that could not see the fault. The lesson is the same one:
**a passing test proves only what its stimulus could have falsified.**

### FILT CONVERTED and bit-exact — 2026-08-24, fourth attempt

Once the self-test above proved the routine, the remaining suspect space
was just the wrapper, and the wrapper is where the fault was.

| | cycles/block | cycles/sample |
|---|---|---|
| FILT per-sample, re-measured on the CURRENT build | 6,973 | 217.9 |
| **FILT per block** | **4,062** | **126.9** |
| | | **1.72× faster** |

(Differenced `DSP4_NODE_LIMIT` 2 → 3, `DSP4_BLOCK_DECIMATE=32`, both arms
measured the same way on the same day. The pre-rewrite table's 7,254 was
not reused.)

**Bit-exact on the part: 0 differing samples of 24**, block build against
per-sample build, same stimulus and same coefficients — a real 2-stage
cascade (HPF `1,−2,1,−1.8,0.81` into a 1 kHz LPF) whose impulse response
rings through zero and back, so the comparison has something to fail on.
Method: `DSP4_NODE_LIMIT=3` cuts the chain immediately after FILT, so the
pool slot still holds FILT's output when the scope reads it — without that
cut, later strip nodes overwrite the slot and the capture is of whoever
wrote last.

What the wrapper has to get right, and what the earlier attempts did not:

- **Input and output are different pool slots.** FILT reads `BLK_CHAIN_B`
  (GAIN's output) and writes `BLK_CHAIN_A`. The cascade works IN PLACE at
  `i2`, so the block is copied into the output slot and filtered there.
- **`i1` carries over from HPF to LPF.** The per-sample node relies on this
  and so does the block form — the routine leaves `i1` on the next stage's
  state base after a call, which the self-test confirmed.
- **Crossfades are handed to the per-sample path one sample at a time.**
  The per-sample body is emitted under a second label,
  `_<nid>_process_sample`, and the block wrapper calls it 32 times while a
  swap is pending or a fade is running, staging through the scalar buffers
  it already uses. That is the reference implementation itself, so the
  alpha bookkeeping — and a crossfade COMPLETING mid-block, which flips the
  active instance and must switch the remaining samples of that block to
  steady state — is right by construction. Re-deriving that bookkeeping in
  block form is what defeated the first attempt. A crossfade lasts 576
  samples and is a transient, so the per-sample cost of it does not matter.

The default image stays byte-identical: without the flag `_<nid>_process`
falls straight through into the untouched per-sample body.

**A ×32 suspicion that turned out to be wrong, recorded so it is not
re-raised:** the crossfade advances `alpha` once per call and the chain is
called per sample, which looks exactly like the ramp ×32 defect. It is not
one. `XFADE_SAMPLES = 12 ms × 48 kHz = 576 SAMPLES`, not 576 frames, so a
per-sample step is correct.

### EQ CONVERTED and bit-exact — 2026-08-24

Same wrapper pattern as FILT. EQ runs the cascade with `r4 = 4`, so it is
the first user of the i0-advance-between-stages fix — without that, every
band would have run with band 0's coefficients.

| | cycles/block | cycles/sample |
|---|---|---|
| EQ per-sample, re-measured on the CURRENT build | 11,590 | 362.2 |
| **EQ per block** | **7,998** | **250.0** |
| | | **1.45× faster** |

**Bit-exact on the part: 0 differing samples of 24**, four real peaking
bands (120 Hz −8 dB, 1 kHz +6 dB, 3.5 kHz −4 dB, 9 kHz +5 dB), captured at
`DSP4_NODE_LIMIT=4`. The run also crosses a coefficient swap — `EQ_ACTIVE`
reads 1, so the crossfade ran to completion through the per-sample
fallback and the steady-state capture is on the B instance.

EQ additionally maintains `BLK_TAP_EQ`, the post-EQ tap the router picks
from; the block path fills it from the output block, and the per-sample
fallback fills it sample by sample.

EQ gains less than FILT (1.45× against 1.72×) and that is the expected
shape: with four stages the per-stage state load/store that block form
saves is amortised over four times as much arithmetic, and the
coefficients are still re-read per sample because six state registers plus
five coefficients do not fit in sixteen.

### GATE and DLY CONVERTED — 2026-08-24

| | per-sample | per block | |
|---|---|---|---|
| GATE | 5,999 (187.5/sample) | **4,891** (152.8/sample) | **1.23×** |
| DLY | 4,185 (130.8/sample) | **2,000** (62.5/sample) | **2.09×** |

Both baselines re-measured on the current build (`DSP4_NODE_LIMIT` 4→5 and
7→8, `DSP4_BLOCK_DECIMATE=32`).

**GATE — 1.23×, and the modest number is the point.** None of the win is
in the maths; it is all work lifted out of the loop: the `_sample_idx == 0`
guard evaluated 32 times for work done once, the `_gate_on` and
`_gate_filter_on` tests, four converted parameters that are block
constants but were re-loaded from DM every sample, and envelope, gain,
gain target and hold count made register-resident across the block.
`_envq_fx`, `_log2q_fx` and `_mrf_rns28` all preserve r6–r15, which is
what makes that safe — the sidechain biquad does NOT (it clobbers r0–r12),
so a gate with its sidechain filter enabled falls back to the per-sample
path for the whole block.

This is the same class of node COMP is, and COMP measured 8 % SLOWER under
a bare wrap. The difference is entirely the hoisting. It also means COMP
is worth revisiting: it was judged on a wrap alone, which the general
lesson on this page says buys nothing.

**A trap the GATE conversion exposed.** Under `DSP4_BLOCK_KERNELS`,
`_sample_idx` is **31** when the node chain runs — the scatter loop leaves
it there — so a `_sample_idx == 0` guard never fires. Any unconverted node
that does its parameter conversion under that guard **never converts at
all** in a block build, and runs on whatever its `.var` initialisers hold
(0, for GATE's alphas and threshold). The block kernel does the conversion
unconditionally, once. This is another reason a block build is not
functionally equivalent while unconverted classes remain.

**DLY — 2.09×, and it is nearly all one thing.** The node runs an 8-way
delay-slot dispatch — up to sixteen compares and branches — on every
sample, for a decision that cannot change within a block, and it dwarfs
the actual delay-line I/O of about a dozen instructions. Hoisting that,
the read-offset clamp and the write-pointer load/store is the whole win;
the inner loop is unchanged arithmetic.

**Verifying DLY needed a different method, and two blind tests on the way
are worth recording.** DLY sits behind GATE, COMP and TUBE; COMP and TUBE
are not converted, so in a block build they never write the pool and DLY
is handed EQ's output while a per-sample build hands it TUBE's. Comparing
the builds directly would have compared two different stimuli.

- First attempt checked `out[i] == in[i − offset]` from two separate scope
  arms. It reported **0 mismatches over 27 samples — of zeros**: an
  impulse never opens the gate, so nothing reached DLY. The probe now
  refuses to report a pass unless the stimulus has at least four distinct
  and four non-zero values, because a constant or silent input satisfies
  that check for **any** delay, including none.
- With a real stimulus the same two-arm method showed 1–3 LSB differences
  that had nothing to do with the delay: FILT, EQ and GATE are all
  stateful, so two separate arms do not start from identical state.

The method that works is a true build-versus-build diff with **GATE, COMP
and TUBE all bypassed over SPI**, which makes both builds present EQ's
output to DLY. A resonant HPF in FILT keeps the signal varying — with the
default unity filters a step is constant and the test is blind again.
Result: **0 differing samples of 32**, 28 distinct values, with the
5-sample delay visible in the capture.

### COMP and TUBE CONVERTED — the wrap verdict was wrong

| | per-sample | per block | |
|---|---|---|---|
| COMP + TUBE together | 7,776 (243/sample) | **5,747** (179.6/sample) | **1.35×** |

**COMP was previously recorded as "not worth converting" and that is now
withdrawn.** It rested on two things, both wrong:

- It was measured as a bare WRAP, which came out 8 % slower. A wrap alone
  buys nothing — that is the general lesson of this whole page, and COMP
  was never measured any other way.
- The note that `_compgain_fx` "clobbers all but four registers" is not
  what the routine does. It touches r0–r3, r8–r12 and i0, so **r4–r7 and
  r13–r15 survive it**; intersecting with `_envq_fx` (which takes r4, r5)
  leaves r6, r7, r13, r14, r15 — enough for both alphas, the dry sample,
  the envelope and the makeup, which is most of COMP's per-sample DM
  traffic.

Implementation note worth reusing: rather than duplicate ninety lines of
parameter conversion into the block kernel, **sample 0 is run through the
per-sample body with `_sample_idx` forced to 0**, which performs the
makeup ramp and the whole conversion exactly as a per-sample build would;
samples 1–31 then run hoisted. TUBE hoists only when its saturation ramp
is settled — the ramp is per-sample by design, so `sat_q` changes within
the block while it runs, and a ramping TUBE hands the block to the
per-sample body.

Verified: **0 differing samples of 32** for the whole converted chain
IN→GAIN→FILT→EQ→GATE→COMP→TUBE, block build against per-sample build,
32 distinct non-zero values.

### Every class converted — the strip as fabbed, 2026-08-24

| class | cycles/sample |
|---|---|
| EQ | 250.0 |
| COMP + TUBE | 179.6 |
| GATE | 152.8 |
| FILT | 126.9 |
| RTG | 81.8 |
| DLY | 62.5 |
| FDR | 58.9 |
| GAIN | 17.9 |
| IN | 11.6 |
| **strip total** | **942** (30,144 cycles/block) |

Strip 1,973 → **942** cycles/sample, a **2.1×** improvement, every class
measured on the part. Projected ceiling 218,616 / 30,144 = **7.25 strips**.

**Against the goal line of 32 strips in one 21564**, this is the arithmetic
that matters:

| | |
|---|---|
| budget | 327,680 cycles/block |
| block I/O (converted) | 32,707 |
| bus/send fabric (not yet converted) | 79,408 |
| available for strips | 218,616 |
| **needed per strip for 32 strips** | **6,832 cycles/block = 213 cycles/sample** |
| **actual** | **30,144 = 942 cycles/sample** |
| **shortfall** | **4.4×** |

With the fabric brought to the dispatch's 40k target, available rises to
about 254,973 and the per-strip requirement to **249 cycles/sample** — a
**3.8×** shortfall. That is what fusion and SIMD pairing have to find.

### The strip after FILT and EQ — 2026-08-24

| class | cycles/sample | state |
|---|---|---|
| RTG | 81.8 | converted 7.3× |
| FDR | 58.9 | converted 2.33× |
| GAIN | 17.9 | converted 4.04× |
| IN | 11.6 | converted (block I/O) |
| **FILT** | **126.9** | **converted 1.72×** |
| **EQ** | **250.0** | **converted 1.45×** |
| **GATE** | **152.8** | **converted 1.23×** |
| **DLY** | **62.5** | **converted 2.09×** |
| COMP + TUBE | 243 | not converted |
| **strip total** | **1,005** | **32,173 cycles/block** |

(COMP and TUBE measured together as the `NODE_LIMIT` 5→7 difference on the
current per-sample build, 7,776 cycles/block — the original profile's
202 + 40 = 242 cycles/sample stands.)

Strip 1,973 → **1,005** cycles/sample across the whole rewrite; 1,141 →
1,005 from GATE and DLY alone. Projected ceiling
218,616 / 32,173 = **6.79 strips**, up from 5.99 and from 2.91 at the
start. The unconverted share is now **24 %** of a strip, down from 88 %.

D24's 24 strips need 772,152 cycles/block against 218,616 available —
**3.5× over**, from 4.0× and from 4.6×. Converting the last two classes
outright, at DLY's 2.09×, would take a strip to about 890 cycles/sample
and 7.7 strips: still **3.1× short of D24**. That is the whole point of
this table — every class has now been converted or measured, the total is
a factor of two better than it started, and it does not close the gap. The
remaining lever is a change of shape, not another class.

### Third attempt, 2026-08-24 — PARKED again, but the suspect list was wrong

Outcome: still fails on real filters, so the biquads stay parked. The
useful product of this attempt is a correction to the reasoning above.

**"`both_unity` passes at 0 LSB" does not exonerate the state handling —
it cannot.** With unity coefficients the biquad reduces to
`y = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2` with `b1 = b2 = a1 = a2 = 0`,
i.e. **`y = x`, and the stored state contributes nothing whatsoever**. Any
fault that lives in *which* state a stage reads and writes — wrong
instance, wrong stride, HPF and LPF sharing one state block, state not
persisted across blocks, the A/B crossfade instance — passes unity at 0 LSB
and fails every real filter. The earlier note read the unity pass as
evidence that "the block plumbing is exercised and correct". It is not:
unity is blind to exactly the thing that is broken.

So the suspect order is now, and this is where the next attempt should
start:

1. **The state pointer the wrapper hands to `i1`** — per section, per
   instance, per block. Cheapest possible test: two sections with
   deliberately DIFFERENT coefficients, and check the second is not running
   the first's state.
2. State persistence across block boundaries (the register-resident copy is
   written back once per stage; confirm the wrapper does not re-zero or
   re-load it per block).
3. Only then the MAC-unit implicit registers and `m1` interference.

A line-by-line diff of the two inner bodies was done as part of this
attempt: the arithmetic, the MAC order, the rounding, the saturation test,
the error-feedback update and the state store order are **identical** to
`_bq_fx_cascade_N`. That is a real narrowing — it is not the maths.

- The block cascade assembles and is still **unwired**; wiring it is the
  next attempt's first step, with test (1) above run before anything else.

### Product-scope gating — measured 2026-08-24, and the first mechanism was a loss

Option 3 from the decision list ("fewer nodes per product") was still
saving nothing: `_scope_gates_apply` only forced *enable flags* off, and
every one of the 431 nodes was called on both products. Only **34 nodes**
carry a `scope=` in `dsp.csv` — 32 D32-only, 2 D24-only, all of them
`INPUT_TDM` / `INTERCHIP_SEND` / `INTERCHIP_RECV` / `AUX_INPUT` /
`OUTPUT_TDM`.

Measured on the part, chip 1, booted as **d24**, block-kernel build,
`DSP4_BLOCK_DECIMATE=32`, 1101 passes each:

| build | cycles/block | vs control |
|---|---|---|
| no gating at all (control) | 243,235 | — |
| per-NODE skip table | 244,795 | **+1,560 (WORSE)** |
| contiguous-RUN gating | **241,744** | **−1,491** |

**The per-node table is a net loss and that is the finding.** Skipping the
34 scoped nodes is worth 1,478 cycles/block, but a table word read plus a
test before *all 431* dispatch calls costs more than that. The ratio does
not improve in a per-sample build either — the check and the node cost both
scale by 32. A gate paid per node cannot pay for itself when 8 % of the
nodes are gated.

The scoped nodes are contiguous in call order, so the working mechanism is
one compare and one branch per **run**: two runs on chip 1 covering all 16
of its scoped nodes, about 8 cycles/block against 1,491 saved. Kept.

`DSP4_SCOPE_GATE` (default 1) selects it, so the saving stays measurable
against a control build. The default per-sample image is byte-identical to
the pre-conversion firmware (`d1c3dd5c…` / `85d546f9…`) — the gating is
guarded to `DSP4_BLOCK_KERNELS`, and the legacy generator output including
`_scope_gate_count` is emitted unchanged on the default path.

Scale check, because it matters more than the number: 1,491 cycles/block is
**0.46 % of the budget**. In a per-sample build the same nodes would cost
32× as much, so gating them would be worth up to ~14 % — but that is an
inference from this measurement, not a measurement. Either way it does not
change the capacity picture below.

Bit-exactness after gating: the `GAIN → FDR → RTG → BUS` chain still
matches the model at **0 LSB** across all seven level/pan cases, booted as
d32 with the D24-scoped run branched over.

### What stands out

**RTG is the most expensive node class on the part** — 601 cycles per
sample, more than EQ and COMP together, and 30% of an entire channel
strip. It is a routing node. That is the first place to look, and it is
not where anyone would have guessed: the dynamics and EQ maths get the
attention, and between them they cost less than the router.

**The dynamics are not the problem.** COMP at 202 cycles/sample runs an
envelope follower plus log2 and exp2 polynomial evaluations for that, and
GATE costs the same. They are reasonable.

**Fixed overhead is 44% of the budget before a single strip runs.** Block
I/O alone is ~20%: scatter walks 46 channels and gather 37 sends, each 32
times per block. Buses and sends are another ~24%.

## How many strips fit in real time — 2

Arithmetic: available for strips = 327,680 − 144,166 = 183,514, so
183,514 / 63,131 ≈ 2.9 strips.

Bench, judged on **audio truth** rather than link responsiveness —
`_proc_passes` counts completed block passes, so passes/s = 1500 means the
main loop finished every block:

| `DSP4_STRIPS` | passes/s | verdict |
|---|---|---|
| 1 | 1500 | real time |
| **2** | **1500** | **real time — this is the ceiling** |
| 3 | 1342 | 89% — dropping ~1 block in 9 |
| 4 | 1144 | 76% — over budget |

**Two channel strips hold real time at 1×**, against 32 required, and the
measurement agrees with the arithmetic to better than one strip.

### Re-measured 2026-08-24, after the kernel rewrite — still 2

| `DSP4_STRIPS` | transport | `_proc_passes` | verdict |
|---|---|---|---|
| **2** | 1500/s | **1500/s** | **REAL_TIME — still the ceiling** |
| 3 | 1500/s | 1329/s | OVER_BUDGET |

`BOOT_STAGE 7`, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A` clean at both
points. 1329 reproduces the 1342 measured before the rewrite, which is the
expected answer: **the default per-sample image is byte-identical**
(`d1c3dd5c…` / `85d546f9…`), so its ceiling could not have moved. Every
conversion so far sits behind `DSP4_BLOCK_KERNELS`.

**The converted build's ceiling cannot honestly be measured yet, and it was
not.** In a block-kernel build the six unconverted strip classes run ONCE
per block instead of 32 times, so the graph is not functionally equivalent
and a strips sweep on it would flatter itself by roughly 32× on 88 % of the
strip. The 5.17 figure above stays a projection from measured per-class
conversions until the whole strip converts.

**A measurement trap this re-run walked into first, worth recording.**
The initial sweep judged real time by `FRAME_COUNT` over a nominal dwell
and produced nonsense — 2,023 "blocks/s" at `DSP4_STRIPS=4`, above the
1,500 the transport can physically deliver. Two faults: `FRAME_COUNT` is
incremented by the block ISR and keeps perfect time whether or not the main
loop finishes its work, so it is structurally incapable of seeing an
over-budget graph; and dividing by the requested dwell rather than measured
elapsed inflated the rate. `dsp4_audio_verdict.py` exists precisely to
avoid both, and using it gave a clean answer at the first attempt on a link
that had refused fifteen. **Judge the loop by `_proc_passes`, never by
`FRAME_COUNT`** — the same lesson that cost a day earlier on this page,
relearned by ignoring it.

### A test artefact worth recording, because it cost a day

An earlier version of this page reported a "2.5× unexplained margin" —
that `DSP4_STRIPS=1` measured 73.3% of budget and still appeared dead.
**That was the test, not the DSP.** Aliveness was being judged by whether
the parameter link gave a prompt clean answer, and that link is serviced
by polling from the block loop: under load an answer is a block or more
away, which is normal, not a fault. The card was running the whole time —
`BOOT_STAGE 7`, `FRAME_COUNT` at 1500/s, `DMA0_STAT 0x00006200`,
`SPORT0_ERR_A` clean.

Two things came out of it and both are kept:

- **Judge audio by audio.** `_proc_passes` versus `FRAME_COUNT` separates
  "transport running" (an ISR increments FRAME_COUNT regardless) from
  "loop keeping up". `audio_verdict.py` reports UNKNOWN when the link
  never answers, distinct from AUDIO_DEAD — conflating those two is the
  original error.
- **The host was making it worse.** `dsp4_diag.py.read()` realigned the
  word phase on the first echo mismatch, when the usual cause is simply
  that the DSP has not polled yet. It now collects patiently
  (`COLLECT_TRIES`) before concluding anything is out of phase, so a slow
  answer is no longer turned into a manufactured fault.

## Deliverables for the capacity decision

- **`dsp4-function-costs.csv`** — the per-function cost table as data: cycles
  per sample, cycles per block for 32 channels, share of the whole chip,
  whether SIMD can pair it, and the silence value where it differs.
- **`dsp4-channel-budget.html`** — the same model, interactive: toggle
  functions, channel count, one or two chips, SIMD, the dynamics rework and
  the fabric target, and see where it lands.

### The 2156x family, from the CCES architecture definitions

| | |
|---|---|
| ADSP-21562 … 21569 | single SHARC+, **all with 640 KB L1** |
| L2 | 992 KB (21562/21566), 1,248 KB (21563/21567), **1,760 KB (21564/21565/21569)** |
| ADSP-2157x/2158x/2159x | ARM + **two** SHARC+ cores |

**A family swap does not relieve the memory pressure**: every 2156x part has
the same 640 KB L1, and the 21564 already carries the largest L2 in the
family. The only 2156x variable that could help is core clock, and that
needs the datasheet — which we do not have locally, and analog.com blocks
both curl and WebFetch (see the recorded access note). **Unverified: treat
any clock difference as unconfirmed until the datasheet is in hand.**

The parts with genuinely more compute are the dual-SHARC 2157x/2158x/2159x,
which also carry an ARM core — a different class of part, package and BOM,
not a drop-in.

## The bus/send fabric, measured on the current build — 2026-08-24

Node 320 is the strip/fabric boundary in the chip-1 call chain (0–319 are
the 32 strips, 320–430 are meters, buses, sends, cross-ins and transfers),
so `DSP4_NODE_LIMIT` 320 versus 0 isolates the fabric directly.

| build | cycles/block |
|---|---|
| 32 strips, no fabric | 2,070,521 |
| full 431-node graph | 2,165,955 |
| **fabric** | **95,434 (29.1 % of the whole budget)** |

**Higher than the 79,408 carried from the original profile** — that figure
predates several changes and the current number supersedes it. Against the
dispatch's 40k target this needs a **2.39×** reduction.

**It is nearly all call overhead, and that is why the target is reachable.**
97 non-strip nodes on chip 1 — 37 `INTERCHIP_SEND`, 32 `METER`, 25
`MIX_BUS`, 2 `TALKBACK`, 1 `NOISE_GEN` — at 32 calls each is 3,104 calls per
block, so **30.7 cycles per call** for bodies of two to four instructions:

    MIX_BUS:          i2 = acc; call _acc64_rns28; dm(_buf) = r0; rts;
    INTERCHIP_SEND:   r0 = dm(_buf_<src>); dm(_tx_slot) = r0; rts;

That is the same shape GAIN had at 72.5 cycles/sample for one multiply,
and GAIN converted at 4.04×.

What hitting the target is worth, exactly:

| | available for strips | per strip for 32 |
|---|---|---|
| fabric as-is (95,434) | 199,539 | **194.9 cycles/sample** |
| fabric at 40k | 254,973 | **249.0 cycles/sample** |

So the fabric work is worth **54 cycles/sample/strip** of headroom — real,
but it does not change any conclusion above: the signal-present strip is
1,152 cycles/sample and the best measured path with SIMD and both dynamics
levers is ~442.

### Why the fused-build strips ceiling is not measured yet

It is gated on this conversion, and the reason is the same trap twice over:
in a block-kernel build the **fabric nodes are unconverted, so they run once
per block instead of 32 times** — they are 32× too cheap, and the graph is
not functionally equivalent. A strips ceiling measured on that build would
flatter itself exactly as a strips ceiling measured on a partly-converted
strip would have. It becomes meaningful the moment the fabric converts.

### What the conversion involves — one change or none

Bus outputs and TX slots become 32-word arrays, which means every consumer
indexes by sample: sends, meters, transfers and the chip-2 buses. The
gather is the easy part — it already walks a pointer table
(`_c1_ic_tx_ptrs`), so it needs one add to index the slot by sample.
Converting a subset produces a build that is silently wrong, so this lands
whole. Open risk: it wants roughly **1,900 extra words of DM**, and
headroom is already tight enough that the bus accumulators are still parked
in L2.

## EVERY DYNAMICS MEASUREMENT ON THIS PAGE WAS TAKEN ON SILENCE — corrected 2026-08-24

This invalidates two earlier conclusions and makes the capacity picture
**worse**, so it goes at the top of the record rather than in a footnote.

The bench has no analog boards and no audio source, so the TDM inputs are
silent. Both dynamics nodes short-circuit on a zero envelope **before they
reach log2**:

    _compgain_fx:   if le jump (pc, .cg_unity);   /* x <= 0 */
                    call _log2q_fx;               /* never reached */
    GATE:           r1 = pass r0;
                    if le jump (pc, .gate_below); /* skips _log2q_fx */

So every profile of GATE and COMP measured the cheap path. `DSP4_PROFILE_SIGNAL`
substitutes a constant −6 dBFS in the input kernel — above the −40 dB gate
threshold and the −20 dB compressor threshold — so every node runs the path
it runs with real audio.

| node | silence | **signal** | delta |
|---|---|---|---|
| GATE | 152.0 | **247.5** | +95.5 |
| COMP | 160.6 | **421.6** | +261.0 |
| GAIN, FILT, EQ, DLY, FDR, RTG, TUBE | unchanged | unchanged | — (no data-dependent branch) |
| **strip** | **795.4** | **1,151.9** | **+356.5 (45 % worse)** |

**COMP under signal is the most expensive node in the channel** — more than
the 4-band EQ.

### What this overturns

- **"The compressor's gain computer is only 9.6 % of it."** That measured
  598 cycles/block for `_compgain_fx` on a silent bench, where the routine
  returns unity in about four instructions. Under signal the same routine
  is **261 cycles/sample**. The section below it, which concluded the
  polynomials "were the obvious suspect and are not the problem", had the
  right instinct about measuring first and the wrong measurement.
- **Every capacity figure derived before this** — 823 cycles/sample, 7.25
  strips, 18.6 strips with SIMD — was optimistic, not conservative.

### The lesson, which is the same one twice

The biquad `both_unity` test could not fail because unity makes the state
irrelevant. This profile could not see the dynamics because silence makes
the expensive path unreachable. **A measurement is only worth what its
stimulus could have exercised**, and on a bench with no signal source that
has to be checked explicitly every time.

### What the levers are actually worth, sized on the signal numbers

| lever | cycles/sample recovered | kind |
|---|---|---|
| GATE: compare the threshold in the LINEAR domain | **~95** | algebra; needs a `fixed_ref` change, no table |
| COMP: log2/exp2 by table + interpolation | **~200 of 261** | numerics; needs `numeric-spec.md` + `fixed_ref.py`, D5 |
| TUBE removed from the fixed strip | ~3 | already bypassed at runtime; the real prize is its DM |

GATE only needs `log2(env)` to compare against a threshold, and that
comparison is equivalent in the linear domain: precompute `2^thr` once per
block. COMP genuinely needs the log **value** for its knee and slope, so
that one is a table or nothing.

### The fit, on signal-present numbers

| configuration | cycles/sample | strips per chip |
|---|---|---|
| **required for 32** (fabric at 40k) | **249** | **32** |
| signal strip, scalar | 1,152 | 6.9 |
| + SIMD on all but DLY/RTG | 566 | 14.1 |
| + GATE log deleted + COMP tabled | 442 | 18.0 |
| **basic strip: trim, HPF/LPF, EQ, fader, routing** (no dynamics, no delay) | **222** | **35.9 — fits** |

**32 full-function channels do not fit one 21564 by any combination of the
levers measured here.** 32 *basic* channels fit with margin. That is the
decision, and it is a product-shape decision rather than a coding one.

## SIMD pairing works, and the fit answer — 2026-08-24

### PEy is real and it is driven

Asked of the part rather than the manual (`DSP4_SIMD_PROBE`): enable
`MODE1.PEYEN`, do arithmetic on interleaved pairs, read both halves back.
**Both PEy results came back correct.** SIMD is available on the
ADSP-21564 and one instruction stream drives two compute units.

### A SIMD biquad cascade, measured

`_bq_fx_cascade_simd` runs the fused cascade for **two strips at once**,
coefficients, state and signal interleaved by strip. Two things had to
change from the scalar version:

- **Saturation became a per-PE conditional MOVE.** A jump uses PEx's
  condition for *both* units, so a branch would have saturated strip B
  whenever strip A clipped. Conditional *compute* is evaluated
  independently in each unit — that is the whole SIMD idiom. The saturated
  value is built **before** the compare, because the ALU ops that build it
  would otherwise overwrite the flags it is conditioned on.
- **`x` folds into the state update early**, before the rounding, purely to
  free r0 as the third temporary the branch-free saturation needs.

| | |
|---|---|
| scalar, two strips one after the other | 43 ms / 4000 iterations |
| **SIMD, the same two strips together** | **18 ms** |
| **factor** | **2.39×** (2.2–2.6 at ±1 tick) |
| output difference | **0 samples of 64** |

The strips carry **different coefficients** — identical strips would hide a
PEy quietly reading PEx's operands, which is exactly what this had to rule
out. Above 2× because the scalar arm pays two calls and two per-stage
setups where the SIMD arm pays one.

*(Instrument note: TCOUNT read back values inconsistent with a TPERIOD
reload and gave nonsense ratios. The 1 kHz diag tick over 4000 iterations
is the instrument that works, and it is the one this page already trusts.)*

### The fit against the goal line: 32 basic strips in ONE 21564

Required, and what the measured path actually delivers:

| | cycles/sample/strip | strips that fit one 21564 |
|---|---|---|
| **required for 32 strips** (fabric at its 40k target) | **249** | **32** |
| scalar, fused biquads — measured today | 823 | 9.7 |
| SIMD on the biquads only | 673 | 11.8 |
| SIMD on all but DLY and RTG | 428 | 18.6 |
| SIMD on the whole strip — **upper bound** | 344 | **23.2** |

**On measurement, 32 basic strips do not fit one 21564.** The last row is
an upper bound that assumes the entire strip pairs perfectly, and it still
lands at 23 strips against 32. There is no arrangement of the current
kernels that reaches the goal line.

**Why DLY and RTG probably cannot pair.** SIMD duplicates the compute
units and the register file (Rx/Sx) — it does **not** duplicate the address
generators. Both strips of a pair share one set of DAGs, so any node whose
*addressing* differs per strip cannot be a single SIMD access. DLY's
delay-line read offset and pool slot are per-strip, and RTG's routing is
data-dependent. That is why the realistic row is 18.6, not 23.2.

**What would have to change to reach 32/chip.** The dynamics are 332 of the
823 cycles/sample (GATE 153, COMP+TUBE 180) and are almost all log2/exp2
polynomial evaluation. Halving them — a numerics change needing D5
sign-off, not a coding change — gives 22 strips/chip with realistic SIMD.
Still not 32. The goal line is not reachable by generating better code for
the algorithms the strip currently runs.

**What IS comfortably reachable: 32 strips on the CARD.** The card carries
two 21564s. At the realistic 18.6 strips/chip the card does 37 strips
*today's kernels plus SIMD*, i.e. the full 32-channel product with margin —
which is the same product outcome, using the silicon already fabbed. What
it does not give is PW's "32 in one chip, two on the card = headroom".

## The capacity arithmetic, after everything converted so far

This is the number the conversion has to be judged against, and it is not
close.

Post-conversion, per strip and per block:

| | cycles/block |
|---|---|
| strip, before the rewrite | 63,131 |
| strip, now (IN, GAIN, FDR, RTG converted) | **42,306** |
| fixed overhead, before | 144,166 |
| fixed overhead, now (block I/O converted) | **109,064** |
| available for strips = 327,680 − 109,064 | **218,616** |

So **5.17 strips** by arithmetic, up from 2.91. Against what the products
need:

| | strips required | cycles/block needed | vs 218,616 available |
|---|---|---|---|
| D24 | 24 | 1,015,344 | **4.6× over** |
| D32 | 32 | 1,353,792 | **6.2× over** |

**The six unconverted classes are 88 % of what a strip now costs**: EQ 338,
FILT 227, GATE 204, COMP 202, DLY 148, TUBE 40 = 1,159 of 1,329
cycles/sample. Everything converted so far is the other 12 %.

And converting them is not enough either. Halve **all six** — better than
any measured conversion except RTG's, and COMP/GATE have already been
measured as not worth converting at all — and a strip falls to 23,762,
which fits **9.2 strips**. Still 2.6× short of D24.

That is the honest state of it: the rewrite is working (2.91 → 5.17 strips,
every step measured and bit-exact) and it cannot get one SHARC to 24
channels by itself. Scope gating, worth 0.46 % of budget, does not change
this; neither does any single remaining node class. What would move it is a
change of shape — fewer nodes per strip, a bigger block, or the strip count
per part — and that is a hub decision, not an optimisation.

## What this means for the decision

The gap is 6.6×. Reading it against the hub's four options:

1. **Per-block kernels.** 13,792 per-sample node calls per block become
   431. Removes call overhead and opens SIMD/pipelining. The measured
   spread supports this: IN at 24 cycles/sample is nearly all call
   overhead, and even at the top RTG's 601 is unlikely to be 601 cycles of
   arithmetic.
2. **Cheaper maths.** Worth having, but the profile says dynamics are not
   where the money is. **RTG first, then EQ and FILT.**
3. **Fewer nodes per product.** Currently saving nothing at all:
   `_scope_gates_apply` on chip 1 is a no-op — the generated body is
   `rts; /* no scoped nodes on this chip */` — so all 431 nodes run for
   D24 and D32 alike, and every measurement here already had a d24 config
   committed.
4. **Larger block.** Amortises overhead, costs latency. The profile does
   suggest a real overhead component, so this is not empty — but it should
   be judged after 1, since 1 removes most of the same overhead without
   the latency.

The one thing the data says on its own: **profile RTG before optimising
anything else.** It is a third of a strip.

## PROGRAM MEMORY IS NOW A CAPACITY CONSTRAINT, AND IT BLOCKS THE CONFIGURATION EVERY PROJECTION RESTS ON — measured 2026-08-29

Every capacity projection in `review-dsp-20260828.md` assumes the strip
is BOTH fused and paired. **That configuration does not build.** Not
because of cycles — because chip 1 runs out of program memory.

Measured on the part's own link map, chip 1, block 8, all 32 strips'
node bodies linked (`DSP4_STRIPS` gates the chain CALLS, not the code,
so the PM figure is the same at every strip count):

| configuration | PM words free | links? |
|---|---|---|
| scalar, unfused | 15,062 | yes |
| scalar, fused | 9,882 | yes |
| paired, unfused | 418 | yes |
| **paired, fused** | **over** | **NO** |

`sec_swco` (block 3) is FULL — 131,070 of 131,072 words — in every one
of those builds, so everything else spills into block 2's overflow
section, and the paired+fused build exhausts that too.

**This is not caused by the control-rate gate.** The same build with
`DSP4_CTL_ALWAYS=1`, which compiles the gate out entirely, still fails
to link. The gate is 164 words of the deficit; the configuration is over
without it. It is also not new — it is why the record has never carried
a fused+paired measurement, and why the review's caveat 2 ("fused+paired
at block 8 has never been built together") stayed open. The reason has
now been measured rather than assumed.

Where the memory goes: pairing costs about 14,600 words and fusion about
5,200. Both are per-node inlined code across 431 generated node files.

**The lever, and it is structural rather than incremental.** The graph
is 431 node files each carrying its own copy of a kernel that differs
from its neighbours only in which variables it names. ROUTING is the
worst: ~600 lines per node, ×32. The control-rate gate landed today is
the pattern that fixes it — the gate started as nine inline instructions
per node (~41 words each, 1,320 across 32 nodes, which by itself stopped
the paired build linking) and became a three-instruction call into one
shared routine driven by indexed per-strip arrays, for 896 words back
and about 2.5 cycles/sample/strip paid. Applying the same move to
ROUTING's whole prep section, and then to the dynamics bodies, is what
buys back the room the fused+paired configuration needs.

Until that lands, the honest statement about capacity is: **the paired
ceilings in the record are UNFUSED-paired, and fused+paired is not a
measurable configuration on chip 1.**

## THIS SECTION IS STALE — fused+paired links today, checked 2026-08-30 (session 11)

Sessions 5 through 10 landed the wide-word metering, D55, the RTG
control-epoch counter (D22) and the dynamics call-site inlining, none of
which were re-checked against the deficit above. Session 11 rebuilt the
exact configuration this section says does not link —
`DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_BQ_GRAPH=1 DSP4_STRIPS=32`,
block 8, all 431 chip-1 node files — with plain `./build.sh all`: **it
links.** `=== Build OK ===`, chip1.ldr 393,572 bytes, chip2.ldr 193,196
bytes, no `[Error`, no `Build FAILED`. `captable.sh MODE=cyc` then ran
the same configuration on the part at block 8 and block 32 and read
198,721 and 584,352 cycles/pass — 15 and 21 cycles off session 10's
published 198,706 and 584,331 (0.008% and 0.004%), i.e. the same number
inside the instrument's own noise, not a different one.

**So the "over / NO" row is wrong as a statement about today's tree.**
Nothing here was root-caused to find out which of the five intervening
landings closed the gap — the table above was never re-run — and that
question is still open if someone needs the mechanism. What is settled
is the fact the strategic sections since (`dsp4-branch-cost-20260830.md`,
and the D66/D67 entries in `review-dsp-20260828.md`) already assumed:
fused+paired is the configuration those margin figures are measured in,
it builds, and it is what is on the part.

## THE CASCADE DOES NOT HANG — 2026-08-30 (session 12)

**`_bq_fx_cascade_simd` was root-caused this session and the answer is
that there is nothing in it to root-cause.** The hang the record has
carried since 2026-08-24 is an artefact of two instruments, and the
"bisect" results that eliminated hypothesis after hypothesis were
eliminating nothing: each one perturbed the image, and the failure moves
with the image rather than with the code.

### What the failure actually is

The signature on record is "`_bqst_done` reads 0, the part answers the
parameter link, BOOT_STAGE stops short of running". Three measurements,
each on its own:

1. **`_bqs_phase` reads 0 in a wedged run** — the cascade was never
   entered. A phase marker was added at the top of `_bq_fx_cascade_simd`
   (`DSP4_BQ_TRACE`, default 0) together with exact iteration counters
   for both hardware loops. In a run that wedged at BOOT_STAGE 5, the
   marker is still at its initial 0: the routine had not executed a
   single instruction. Whatever stops the part stops it before the
   self-test runs at all, which is unsurprising once stated — the
   self-test runs from the main loop, and BOOT_STAGE 5 means the main
   loop is still in `.wait_boot` waiting for host config.
2. **The same image both wedges and runs.** `chip1.ldr f4ce7a9a`,
   byte-identical across three consecutive `bqst.sh` invocations: the
   first wedged at BOOT_STAGE 5, the second and third reached BOOT_STAGE
   7 and completed the self-test.
3. **A build containing no paired cascade and no self-test wedges too.**
   Eight independent boot+config cycles on a plain `DSP4_STRIPS=2` build
   (one cycle per attempt, no retries, because retrying hides the rate
   and the rate is the measurement): **BOOT_STAGE 7 7 7 7 0 7 7 0** — six
   of eight. This is the "link that degrades over a long session of
   reboots" already recorded at the end of session 5, and it is what
   every bisect in this investigation was actually sampling.

`bqst.sh` retries boot+config up to five times and reports only the last
attempt, so a wedge means "five failures in a row" and a pass means "at
least one success in five". At a per-cycle failure rate around a quarter
that is a coin the harness flips, and the coin was read as a property of
the code under test.

### When it runs, it runs exactly as designed

With the trace built in, a completing run reads:

| | |
|---|---|
| `_bqp_phase` (wrapper, 1 in … 8 scattered) | **8** |
| `_bqs_phase` (cascade, 1 in, 2 PEYEN, 3 loops done, 4 MODE1 back) | **4** |
| `_bqs_stages` (outer hardware loop) | **2** — the stage count asked for |
| `_bqs_samps` (inner hardware loop) | **16** — stages × BLOCK, exactly |

No loop overruns, no missing iterations, no re-entry. The loop-stack,
DAG-wrap and IT-buffer hypotheses on record are all excluded by these
counts rather than by argument.

### The self-test arm could not have passed, whatever the kernel did

The pair arm's comparison was structurally invalid and is rewritten:

* The scalar arm above it is a **timing** loop — it runs
  `_bq_fx_cascade_blk` over `_sq_xA` **in place, twice**, with `_sq_sA`
  persisting between passes. So `_sq_xA` never held "the scalar result";
  it held two chained in-place passes. The pair arm then rebuilt a fresh
  stimulus with **zeroed** state and ran **one** pass. Two different
  computations, diffed.
* **Strip B was never compared at all.** The B half of the loop read
  `dm(i5,1)` and `dm(_sq_xB)` — the second a direct address, so the same
  word every iteration — and then did nothing with either. No subtract,
  no compare, no counter.
* Nothing on the host ever read `_sq_pdiff`. The arm computed a verdict
  inside the part and had no way of getting it out, which is how a
  broken comparison stayed invisible for four sessions.

Both arms now run one pass over the same stimulus from zeroed state, both
strips are compared, and `dsp4_bq_verify.py` reads the result.

**`_sq_cB` was also not a different filter.** It was `_sq_cA`'s two
sections **in the opposite order** — word for word a different table, and
to within intermediate rounding the same transfer function. The stated
purpose of differing coefficients is to catch a PEy quietly reading PEx's
operands, and against the old sets the pair-arm negative control moved
exactly **one** sample of sixteen. Strip B is now LPF 5 kHz Q0.707 → HPF
1.5 kHz Q0.5 against strip A's LPF 1 kHz Q0.707 → HPF 300 Hz Q2.

### The verdict the record never had

| bar | result |
|---|---|
| `_bq_pair_blk` vs the scalar cascade, both strips, on the part | **0 of 16 differ** |
| the same with `DSP4_SIMD_NEGCTL=1` (strip B given strip A's coefficients and state) | **8 of 16 differ** — the whole of strip B |
| the paired GRAPH vs the dynamics-only graph (`bqgraph.sh`) | **0 of 64 bus words** — `GRAPH BIT-EXACT` |
| the same with `DSP4_BQ_NEGCTL=1` | **56 of 64** — `GRAPH DIFFERS` |

### And the lever was never blocked — it was already banked

`DSP4_BQ_GRAPH` pairs the FILT and EQ classes of a strip pair and has
**defaulted ON since session 5**. Every margin figure published since
then already carries it. Measured both ways on one tree in one run, 32
strips, signal present, 983.04 MHz, `TUBEON=0` explicit:

| config | BLOCK 8 (budget 163,840) | BLOCK 32 (budget 655,360) |
|---|---|---|
| `DSP4_BQ_GRAPH=0` — dynamics pairs only | 217,745 — **132.90 %** | 673,758 — **102.81 %** |
| `DSP4_BQ_GRAPH=1` — FILT and EQ paired | 198,072 — **120.89 %** | 584,845 — **89.24 %** |
| the lever | **−19,673 (−9.03 %)** | **−88,913 (−13.20 %)** |

Session 5 measured the same lever at −19,465 (−8.3 %) and −86,802
(−11.7 %) on a tree that has changed a great deal since; the two agree to
1 % and 2.4 %. **At block 32 this lever is the whole difference between
102.81 % of budget and 89.24 %** — 32 channels on one chip at block 32 is
under budget *because* FILT and EQ are paired, not in spite of a pairing
that never landed.

### Three findings that fell out of building the instrument

**D68 — every fault vector is silent twice over.** `IMASK` is zeroed at
`_start` and only `SECI` and `TMZLI` are ever ORed back in, so ILOPI,
CB7I, IICDI, SOVFI, ILADI, RINSEQI and CB15I are **masked**; and their
IVT entries are bare `rti`, which returns to the faulting instruction.
The 2026-08-24 conclusion "IICDI read 0, so the unaligned-long-word
theory is not supported" was therefore **vacuous**: the counter lived in
a handler that could not run, on a vector that could not be taken. The
answer happens to be the same — an unmasked, unhandled fault is what
would livelock, and no fault is unmasked — but the evidence was not
evidence. `DSP4_FAULT_TRAP` (default 0) unmasks all seven and puts a
counting handler on each.

**D69 — CB7I fires exactly once per boot, in every configuration.** With
the trap in, `_fault_count[CB7I]` reads 1 on every run measured,
including builds with the paired cascade call removed. `i7` is the C
stack pointer and `C_RUNTIME_INIT` sets `l7 = 0`, so the wrap is before
that — the boot kernel's leftovers, not this firmware's. Benign today
because the vector is masked; recorded because it is one more piece of
state the SPI target boot kernel hands over dirty.

**D70 — the ISRs run on a secondary DAG whose length registers are
initialised nowhere, and the boot kernel leaves two of them non-zero.**
`C_RUNTIME_INIT` zeroes `l0..l15` with `SRD1L/SRD1H` and `SRD2L/SRD2H`
**cleared**, so it zeroes the PRIMARY set. Both ISRs (`_sec_isr`,
`_diag_timer_isr`) run with `SRD1L|SRD1H` **set**, and nothing in the
tree ever writes the secondary lengths. Read back at `_start` before
anything can disturb them (`DSP4_DAG_PROBE`, default 0):

```
secondary DAG L at _start (l0..l15):
  0 0 0 0 0 0 000002FF 000002FF 0 0 0 0 0 0 0 0
```

**`l6` and `l7` come up as 0x2FF.** Every ISR-side access through `i6` or
`i7` — which includes anything the CCALL convention pushes — is circular
against a length nobody chose. `DSP4_DAG_SEC_INIT` (default 0) zeroes
them in sixteen instructions at boot.

**It is NOT the boot-handshake failure, and that is a measurement, not an
assumption.** Eight independent boot+config cycles each way, same build
otherwise: **6 of 8 with the fix, 6 of 8 without**. Eight cycles cannot
resolve a small effect, but there is no large one, and the hypothesis
that looked strongest going in is not supported. The fix is worth taking
on its own merits — an uninitialised length register in an interrupt
handler is a defect whether or not it is *this* defect — and it is left
behind a default-0 flag rather than changed silently, because it changes
the shipping image.

### What is still open

**The intermittent boot+config failure is the real open item, and it is
not a DSP-side hang.** ~~Rate measured this session: about 2 in 8
cycles.~~ **CORRECTED 2026-08-30 (session 13): the rate is a couple of
percent, not a quarter, and the "2 in 8" was the instrument.** Every
figure of that shape was taken by reading BOOT_STAGE — one register,
once — off a retrying script, and a dropped answer to that read comes
back as a well-formed (echo, 0), i.e. as BOOT_STAGE 0, which is
indistinguishable from a wedge (D72). Measured one attempt per cycle with
every cycle recorded, **the boot half never failed at all** (160 chip
boots, 160 successes) and the failure is a LOST CONFIG_COMMIT
TRANSACTION eaten by this firmware's own stuck-partial-request recovery
(D71, fixed behind `DSP4_SPI_PARTIAL_FIX2`). A second and rarer failure —
chip 1's core stopping dead, MAGIC included — is real, is not the same
thing, and is still open (D73). Full write-up:
`MW/D32/DSP/dsp4-boot-handshake-20260830.md`.

**W0.** No shipping path was touched: `./build.sh` reproduces chip1.ldr
`3f0e479a` and chip2.ldr `ab43c75b`, 301,732 and 182,060 bytes,
byte-identical to the session-10 baseline. Every switch added this
session (`DSP4_FAULT_TRAP`, `DSP4_BQ_TRACE`, `DSP4_DAG_PROBE`,
`DSP4_DAG_SEC_INIT`) defaults to the pre-existing behaviour, and the
self-test changes are inside `DSP4_SIMD_PROBE`. Golden harness 59/59.
