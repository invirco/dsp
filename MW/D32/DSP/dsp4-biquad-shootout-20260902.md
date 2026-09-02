provenance: AI-drafted 2026-09-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Biquad shootout — the options table PW rules from

Spike, 2026-09-02. Standalone rigs only: no graph integration, no
contract edit, shipping image untouched (W0 `23c1e662` / `e45bb82a`,
reproduced before and after).

---

## 1. The decision table

Cycles are **measured on the part**; dB figures are **modelled** against
the normative `fixed_ref`; RIG B's row is **not measured** and says so.

| | today (fixed, D5) | RIG A2 (float, relaxed rounding) | RIG B (IIR accelerator) |
|---|---|---|---|
| **c/band-sample, 1 ch** | **25.10** measured | **11.81** measured | n/a (engine is per-channel) |
| **c/band-sample, 2 ch SIMD** | **12.58** measured | **5.94** measured | **~0 core** (off-core engine) |
| **speed-up vs today** | 1.00× | **2.12×** | core load → ~0, but see §4 |
| **max response error** | 0 (is the contract) | **0.52 dB** LF shelf +15 dB Q3.16 | **unmeasured**; 40-bit float available, so ≤ A2 |
| **error, ordinary EQ** | 0 | 0.0001 dB | unmeasured |
| **arithmetic** | Q4.28 offset form, per-stage round + saturate + error feedback | IEEE float32 DF-II-T, round once at cascade output | IEEE float **32/40-bit**, HW MAC |
| **latency structure** | none added | none added | **+1 block stage, very likely** (§4) |
| **state continuity** | in the node's own state array | in the node's own state array | HW local memory, persists across iterations; explicit save-state mode |
| **bring-up cost** | none | kernel exists, **needs a correctness bar** | **not attempted — see §4** |
| **core cycles freed, chip 2 @ blk 8** | — | **~30,000 c/block** (§3) | up to ~64,000 c/block |
| **core cycles freed, chip 1** | — | chip 1's biquads are FILT+EQ, 6 stages/strip | as above |

## 2. RIG A2 — measured, and the rig validates itself

`SHARC/bqshoot.sh` + `src/lib/bq_shootout.asm`: five timed loops in
ordinary main-loop context, three repeats, host takes the minimum, rung 0
(empty loop, 2.03 c/iter) subtracted. 28-stage bank, BLOCK 8, identical
loop form on every rung, so the fixed and float rungs differ **only in the
arithmetic**.

**The fixed rungs reproduce the GRAPH cost ladder from a completely
different instrument** — 25.10 against the graph's 25.29 scalar (0.8%) and
12.58 against 12.83 paired (1.9%). That agreement is what makes the float
rungs believable. The SIMD rungs cost the same per call as their scalar
twins, which is direct evidence they compute two channels and not one.

**5.94 c/band-sample is exactly the floor session 18 derived** for the
current contract "with a zero-cost round and saturate". That is not a
coincidence: the float form *is* the fixed form with the numeric contract
removed — same five products, no 64-bit extract, no branch-free saturate,
no error-feedback MAC.

**PW's 3 c/band-sample is not met, and the gap is accounted for.** The
inner loop is eight instructions carrying eleven operations (five
multiplies, four ALU, a load, a store), so it is three instructions off
multiplier-bound. Perfect packing across samples would be five
instructions per sample per stage ≈ **3.75 c/band-sample**. So PW's
estimate is within about a quarter of the arithmetic's true floor, and
this kernel has not reached it — software pipelining across samples is the
remaining work, worth roughly another 1.5× on top of the 2.12×.

### The numeric price, in dB on real curves

`tools/dsp/bq_float_delta.py`, impulse → FFT, both arms taking the **same
quantised coefficients** so the comparison isolates arithmetic:

| design | max \|dB\| error, 20 Hz–20 kHz |
|---|---|
| ordinary peaks ±15 dB Q3 | 0.0001 |
| 4-band EQ, mixed | 0.0098 |
| 28-band GEQ alternating ±6 | 0.077 |
| 28-band GEQ all +6 | 0.176 |
| extreme +15 dB Q10 @ 20 Hz | 0.326 |
| **LF shelf +15 dB Q3.16 @ 20 Hz** | **0.520** |

Against the **0.046 dB** bar `golden_harness` holds the current contract
to, the worst case is **11× over** — and it is the same LF shelf session
18 identified as the worst design in the product's own space, the one that
drove the halved-g1 encoding. **Float is free for ordinary EQ and costs
half a decibel exactly where D5 was fought.**

## 3. What RIG A2 would free

Chip 2 carries 632 biquad stages across 50 dual-instance cascade nodes,
600 of them paired. At 8 samples a block that is 5,056 band-samples; at
12.58 → 5.94 the saving is about **33,500 cycles/block**, against chip 2's
measured 171,918. That is ~19.5% of chip 2 — comfortably more than the
8,078-cycle block-8 gap, **but it does not help chip 1**, which is the
further over of the two, and chip 1's biquad load is six stages a strip
rather than a 28-band GEQ.

## 4. RIG B — NOT MEASURED, and the bring-up assessment says why

**The dispatch's premise is wrong for this part, and that is the first
finding.** It specifies "fixed 1.31/5.27 per dsp.md's original guidance".
The ADSP-2156x HRM ch.35 says the IIR accelerator **"supports IEEE
floating point format 32/40-bit"** with "rounding modes compatible with
SHARC+ core MACs". `dsp.md`'s 1.31/5.27 guidance describes **previous**
SHARC generations. So RIG B is not a fixed-point option at all — it is a
*float* option, like A2, and with 40-bit available its numeric delta
should be **smaller** than A2's 32-bit 0.52 dB.

**Throughput looks ample.** One MAC unit at core clock. Chip 2's 632
stages × 5 MACs = 3,160 MACs/sample against 20,480 accelerator cycles per
sample at 983.04 MHz — **about 15% loaded**. Capacity is not the problem.

**Coefficient memory is the problem.** Local coefficient store is
1440 × 40 bits = **288 biquads**, against the **632** chip 2 needs. Legacy
mode (coefficients resident, loaded once) therefore cannot hold the load.
That forces **ACM**, where "the accelerator loads the biquad coefficients
for only the current channel before starting to process the current
channel" — i.e. **~3,160 coefficient words re-DMA'd every block**. That is
the same gather-every-block pathology the chip-2 biquad latch was built to
remove, relocated from the core to the DMA fabric rather than eliminated.

**Latency: a +1-block pipeline stage is very likely.** The engine is
window-based with a completion interrupt and works **exclusively through
DMA**. Overlapping it (accelerator on block N while the core does block
N+1) is the only way to avoid stalling the core on completion, and that is
by definition one more block of pipeline — **+0.33 ms at block 16**, on
top of the block-size decision's own cost.

**State continuity is answered by the hardware**: biquad states live in
local memory and persist across iterations, with an explicit
`IIR_CTL1.SS` save-state mode for switching the engine to other work. The
bit-pattern proof the dispatch asks for was not run.

**One instance** (`IIR0_*` registers only).

### The bring-up cost, reported rather than paid

Bringing RIG B up needs: ACM configuration, a TCB chain built and
validated for a peripheral this tree has never driven, DMA in/out
plumbing, completion-interrupt handling, a channel map for ~50 chip-2
cascade nodes, and a bit-pattern state-continuity bar. That is a session
of bring-up on its own, not a spike rung, and the dispatch's instruction
for that case is explicit — report the cost and stop.

**What is NOT known, and would decide it**: the end-to-end block cost
(setup + DMA in/out + completion + core involvement), whether the
coefficient DMA in ACM saturates any bus the audio path shares, and the
real 40-bit numeric delta.

## 5. Recommendation

**Neither option should be adopted to save block 8, because block 8 is not
recoverable on chip 1 either** (116.4% measured; see
`dsp4-capacity-decision-20260902.md`). Both rigs are chip-2-only levers and
chip 1 has no GEQ.

**RIG A2 is worth having on its own merits at block 16** — 2.12× measured,
~19.5% of chip 2 freed, and a further ~1.5× available from software
pipelining. But it is **not free**: adopting it reopens D5 on the LF axis
that D5 was decided on, and 0.52 dB on a +15 dB LF shelf is a real,
audible-band change to a shipped filter response. That is PW's call and
not an optimisation decision.

**RIG B deserves a proper session before it is ruled on**, because the
40-bit float path could plausibly give A2's speed at a *smaller* numeric
cost than A2 — but its ACM coefficient-DMA load and its likely +1-block
latency are real objections that only a bring-up can price.

**If the LF error is unacceptable at any speed**, then the answer is that
today's contract stands, block 16 carries both chips with ~6% margin, and
the cascade needs no further work.

## 6. What this spike did not do

* **RIG A2's kernel is TIMED, not VALIDATED.** The rig runs zeroed banks,
  which is sound for timing because the instruction stream does not vary
  with the data, but the asm has never been diffed against
  `bq_float_delta.py`'s model. Adoption needs that bar first, and it
  should be the next thing built.
* **RIG B was not brought up** — §4.
* Neither rig was run at BLOCK 16; both numbers are block-8.
