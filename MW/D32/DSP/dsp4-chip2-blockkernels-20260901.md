provenance: AI-drafted 2026-09-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Chip 2 block-kernel conversion — review findings D16 and D50

Session of 2026-09-01. Working target BLOCK = 8 (PW ruling 2026-08-28);
costs published at 8, 16 and 32 (PW, this session).

## What D16 actually was

The finding reads "chip 2 has no block kernels: block-8 record is
chip-1-only". That is true and it understates the state of the tree in three
ways, each of which this session had to fix before a cost could be measured
at all.

**1. Under `DSP4_BLOCK_KERNELS` chip 2 processed one sample in eight.**
`main.asm` calls `_chip2_process_all` exactly ONCE per block in a
block-kernel build — the loop lives inside each kernel. Not one chip-2 signal
node had a kernel, so each ran its per-sample body once and samples
1..BLOCK-1 were never computed. Only the INTERCHIP_RECV nodes and the METER
nodes had a block form at all.

**2. `_gather_chip2` read seven words past the end of every output slot.**
`emit_copy_loop` indexes the slot by sample under block kernels
(`r5 = r5 + r0`), and `gen_output_tdm` declared `_tx_out_slot_<id>` as a
SCALAR. So the TDM gather read BLOCK words out of a one-word variable — seven
neighbouring variables per output, straight onto the wire. This has been true
of every chip-2 block-kernel build since the gather learned to index.

**3. All twenty-four chip-2 faders shared two buffers.**
`gen_fader_pan_fixed` has had a real block kernel since the pool rewrite, and
it pointed `i0`/`i1` at `BLK_CHAIN_B`/`BLK_CHAIN_A` unconditionally. Those are
STRIP POOL slots and chip 2 has no strip pool, so every aux, group, FX, sub
and main fader read and wrote the same two slots of chip 2's own `_blk_pool`:
in a block-kernel build each fader carried whichever fader ran last.

## And the thing that made the record impossible

**Chip 2's node graph had never run on this bench.** The main loop is gated on
`_boot_config_received`, which `CONFIG_COMMIT` sets. Every session to date
configured chip 1 only — "chip 2 is never configured; BOOT_STAGE 5 is its
pass mark" — and BOOT_STAGE 5 is WAITCFG. So chip 2 sat in `.wait_boot`
answering diagnostics, its SPORT frame counter advancing, and its node chain
never executed a single instruction. There was no chip-2 cost record to have
had, and no measurement was going to produce one until chip 2 was sent a
config commit of its own. `sigprofile2_run.sh` and `c2gold_run.sh` now do,
and chip 2's pass mark becomes STAGE 7 (RUNNING), the same as chip 1's.

## The conversion

Chip 1's kernels ride the strip pool: thirty-two identical strips run one
after another, eight shared slots serve all of them, and a node names its
input and output slot by position in the chain. Chip 2 is not that shape — a
heterogeneous graph of short chains with fan-out and no common chain position
— so the pool cannot be lifted onto it. Each converted chip-2 node publishes
its own `_blk_<id>[DSP4_BLOCK_SIZE]` and a consumer reads its input's by
name. The scalar `_buf_<id>` is unchanged; under block kernels it is the
staging word the wrapper writes before each call into the per-sample body,
which is exactly what chip 1's FILT and EQ transient paths already do.

Three shapes, in descending order of how much they buy:

- **Fused biquad cascade** (EQ_BIQUAD, GEQ, ANTI_FB — 50 nodes). One call to
  `_bq_fx_cascade_blk` walks every stage over the whole block with the state
  and the error feedback held in registers, against BLOCK calls to
  `_bq_fx_cascade_N`. This is chip 1's own fusion on chip 2's buffers.
  Transients (a coefficient swap, a crossfade) fall through to the generic
  wrapper, so the alpha bookkeeping and a crossfade completing mid-block are
  right by construction.
- **Existing kernels, correct buffers** (FADER_PAN — 24 nodes, OUTPUT_TDM —
  20, INTERCHIP_RECV — 37, METER — 27).
- **Generic wrapper** (LIMITER, COMPRESSOR, GATE, DELAY, FX_ENGINE, MIX_BUS,
  MONITOR, CROSSOVER, AUX_INPUT). Runs the per-sample reference body BLOCK
  times over the node's own block buffer. It removes the chain's call/rts and
  a re-evaluated guard and adds pointer bookkeeping; it is a correctness
  scaffold, not a speed-up, and it is where the next stage of work is.

D50 rides with the last group: `C2_AUX_DLY_*` take the non-pool DELAY
template, which had no block form at all, and they are wrapped.

### Why the wrapper keeps its pointers in DM

It calls the node's own per-sample body, which reaches library routines that
between them clobber every R register and — in `delay.asm` and `meter_fx.asm`
— i3-i6 as well. Chip 1's templates can hold `i3`/`i4` across their call
because each calls ONE known body; a wrapper generated for a dozen families
cannot, and a pointer silently clobbered by a callee is a wrong-address
store, not a link error.

## Traps, both audited

**Hardcoded loop counts that do not track `DSP4_BLOCK_SIZE`.** Every new loop
is `lcntr = DSP4_BLOCK_SIZE`. The audit of the generated chip-2 tree finds no
literal `lcntr` count anywhere and 51 sites of `r15 = 1`, all of which are
genuine per-SAMPLE increments (the delay write pointer, the gate hold
counter, the FX echo write pointer) that the wrapper now runs once per
sample, as the per-sample build does.

One real instance was found and fixed: **DCA**. It has no audio path, so it
gets no kernel and the chain simply reaches it once per sample in one build
and once per block in the other. Its `r15 = 1` frame decrement ran the ramp
BLOCK times long under block kernels — a GainSafe DCA move would have taken
240 ms at BLOCK=8 instead of 30. It now consumes a block's frames and applies
a block's step, the same correction GAIN and FADER_PAN carry.

**D12's guard.** The new declarations are `[DSP4_BLOCK_SIZE]`, so they track
the build-time macro; the generated `#if DSP4_BLOCK_SIZE != <N> / #error`
guards are untouched and still present. The 16 and 32 measurements are taken
from REGENERATED trees, never a flag flip.

## The gate — chip 2 does not fit, and the block size is not the lever

Whole chip-2 graph, `DSP4_NODE_LIMIT2=0`, signal present, chip 1 running its
full 32 strips, 983.04 MHz, graph decimated so the pass completes:

| block | cycles/block | % of budget @983.04 MHz | % @786.432 MHz |
|------:|-------------:|------------------------:|---------------:|
| 8     |      342,090 |               **208.8** |          261.0 |
| 16    |      646,390 |               **197.3** |          246.6 |
| 32    |    1,258,101 |               **192.0** |          240.0 |

**16 does not rescue it and 32 does not rescue it.** Going 8 → 32 moves the
figure sixteen points out of two hundred, because the work is per-SAMPLE and
the budget scales with the block: what a bigger block buys is the per-block
overhead amortised over more samples, and that overhead was never the
problem.

### Per class

Consecutive differences on the chip-2 chain, cycles/block and cycles/sample:

| class | n | blk 8 | c/smp | blk 16 | c/smp | blk 32 | c/smp |
|---|--:|--:|--:|--:|--:|--:|--:|
| GEQ (28 band) | 17 | 8,343 | 1042.9 | 15,734 | 983.4 | 30,440 | **951.2** |
| COMP | 10 | 4,065 | 508.1 | 8,776 | 548.5 | 16,340 | 510.6 |
| XOVER | 1 | 2,269 | 283.6 | 6,279 | 392.4 | 12,463 | 389.5 |
| GATE | 4 | — | — | 4,542 | 283.9 | 10,803 | 337.6 |
| LIM | 18 | 2,529 | 316.1 | 4,621 | 288.8 | 9,076 | 283.6 |
| AFB (6 notch) | 12 | 2,159 | 269.9 | 3,967 | 247.9 | 6,758 | 211.2 |
| EQ (4 band) | 21 | 756 | 94.5 | 2,347 | 146.7 | 5,034 | 157.3 |
| DLY | 15 | 1,211 | 151.4 | 1,639 | 102.4 | 3,295 | 103.0 |
| OUT | 20 | −798 | — | −425 | — | 420 | 13.1 |
| FDR | 24 | 721 | 90.1 | −243 | — | 101 | — |

Instrument resolution, stated because three rows are inside it: a repeat of
the same point agrees to 0.1% (17,241 against 17,258), but a CROSS-BOOT
difference at the 30k–60k level carries a few hundred cycles of spread. FDR,
EQ and OUT read negative at one or more sizes — which a node cannot cost — so
they are carried as below resolution rather than as numbers. Every class that
carries the budget is far above it.

The GATE point at block 8 was lost to a link-phase failure: `DiagLink`'s D74
calibration could not phase the link and RAISED, which is the fix behaving
exactly as designed. What was wrong is that the traceback escaped the run
script's retry ladder and was recorded as the point's result. Both run
scripts now retry the phasing and report `WITNESS-UNPHASED` on exhaustion.

### GEQ is the wall, and the fusion is not the problem

17 GEQ instances × 28 bands = **476 biquad stages per sample**. At the
measured 951.2 cycles/sample each, GEQ alone is 16,171 cycles/sample = **776
MHz at 48 kHz, 79% of a 983.04 MHz part**.

The fusion is working, and that is what makes this a cost rather than a
conversion artefact: GEQ measures **37.2 cycles per band-sample** against
chip 1's fused EQ at 40.5 — the same `_bq_fx_cascade_blk`, performing
consistently on both chips.

### Self-check: the parts sum to the whole

The ten class differences × their instance counts give 35,843 cycles/sample at
block 32. Adding the input side, measured separately (limit2=47 = 65,540
cycles/block = 2,048 cycles/sample), gives 37,891 against the **39,316**
measured for the whole graph — 3.6% apart, the remainder being the mix buses,
FX engines, meters and the fixed per-block overhead a cut chain never
reaches. The parts and the whole share no arithmetic.

### What the levers already proven on chip 1 are worth

Chip 1 has two, both measured IN THE GRAPH and neither wired on chip 2 today:
biquad pairing (`DSP4_BQ_GRAPH`, −13.2% at block 32, kernel 1.43–1.54×) and
dynamics pairing (COMP 1.72×, GATE 1.82× in the graph).

| | as measured | with both levers |
|---|--:|--:|
| biquad cascades (GEQ+EQ+AFB+XOVER) | 1,075 MHz | 768 MHz |
| dynamics (LIM+COMP+GATE) | 555 MHz | 321 MHz |
| **ten measured classes** | **1,720 MHz (175%)** | **1,179 MHz (119.9%)** |

**With every lever chip 1 has already proven, chip 2 still lands at 120% of a
983.04 MHz part — 196 MHz over.** GEQ alone, after pairing, is 554 MHz, 56%
of the part.

The generic wrapper is worth naming here rather than hiding: it costs about
15% against a hoisted kernel on the dynamics classes (chip 1's hoisted COMP
is 442.3 cycles/sample at block 8 against chip 2's 508.1). Replacing the
wrapper with real kernels on LIM, COMP, GATE, DLY and XOVER is worth roughly
90 MHz of the ~740 MHz shortfall. It is worth doing and it does not change
the answer.

### The PW ruling, and what it costs in cycles

**PW ruled on this before the gate fired** (tasks.md, 2026-09-01): 31-band
GEQ on all outputs is the market bar, contemporary mixers do it on one or two
SHARCs, and therefore *"the 851 MHz GEQ-alone number prices OUR primitive, not
the feature"*. Feature cuts, plugin demotion and chip splits are off the table
until the biquad cascade is at a competitive rate.

The measurement supports the ruling, and it can be made sharper than "~15x
off". **The question is not what the market does; it is what the shared
cascade has to reach for chip 2 to fit.** Everything below is arithmetic on
this session's measured parts.

Chip 2 carries **642 biquad stages per sample**: GEQ 17x28 = 476, EQ 21x4 =
84, ANTI_FB 12x6 = 72, CROSSOVER ~10. (Cross-check: 642 x 37.2 = 1,146 MHz
against the 1,075 MHz measured for those four classes, 6.6% apart.) Everything
on chip 2 that is *not* a biquad cascade measures **646 MHz**.

| cycles/band-sample | cascades | chip-2 total | % of a 983.04 MHz part |
|--:|--:|--:|--:|
| 37.2 (today) | 1,146 | 1,720 | 175.0 |
| 15 | 462 | 1,108 | 112.7 |
| **11.0** | 339 | 984 | **100.1 — break-even** |
| 6 | 185 | 830 | 84.5 |
| 3 (PW's target) | 92 | 738 | 75.1 |
| 2 | 62 | 707 | 71.9 |

**Break-even for the graph as it stands today is 11.0 cycles/band-sample — a
3.4x improvement, not 15x.** At 786.432 MHz it is 4.6, an 8.1x improvement.

And the target is softer still once the *other* lever is counted. Dynamics
pairing — which chip 1 has had since session 3 and chip 2 does not — takes the
non-cascade 646 MHz to about 412 MHz. That leaves 571 MHz for the cascades:

- for the graph as it stands, **18.5 cycles/band-sample**, a 2.0x improvement;
- for PW's target configuration (31-band GEQ on all 20 chip-2 outputs = 786
  stages/sample), **15.1 cycles/band-sample**, a **2.5x improvement**.

So PW's ruling is arithmetically sound and its 2–3 cycles/band-sample target
leaves real margin (75.1% of the part at 3, with the LARGER feature set at
77.2%). But the *fit* does not require the market rate: **2.5x on the biquad,
with the dynamics pairing chip 1 already has, carries the full 31-band-on-all-
outputs configuration at 983.04 MHz.**

One engineering caveat, recorded because it will decide how hard the target
is. ADI's SIMD `iircas` reference at 1–2 cycles/biquad-sample does not carry
this tree's numeric contract: our cascade is Q4.28 offset-form with **80-bit
error feedback held across samples** (findings D2 and D5), which a plain
`iircas` does not pay for. The record's own instruction-count floor for the
current algorithm is ~11 per stage per sample — which is, to within the
arithmetic above, exactly the break-even. **Reaching the current algorithm's
own floor is sufficient to fit the graph as it stands; beating it needs the
SIMD/PM-fetch/pipelining work the ruling names, and whether 2–3 is reachable
without renegotiating the error-feedback contract is the first question that
work has to answer.**

Levers, in the order the measurement ranks them:

1. **The biquad cascade** — 1,075 of 1,720 MHz, and the ruling's target.
   Cross-channel SIMD pairing is the one with existing measured evidence
   (chip 1's `DSP4_BQ_GRAPH`, 1.43–1.54x kernel, and it is not wired on chip 2
   at all); coefficients dual-fetched from PM, state in registers across the
   cascade, and a software-pipelined inner loop are the rest.
2. **Dynamics pairing** — 555 -> 321 MHz, again already proven on chip 1 and
   not wired on chip 2.
3. **Hoisted kernels for LIM/COMP/GATE/DLY/XOVER** in place of the generic
   wrapper — about 90 MHz.

## Verification — what is proved, and what is not

The dispatch asked for a bar with the conversion or an explicit statement of
the coverage limit. Both, as it turns out.

`SHARC/c2gold.sh` is new: it builds the SAME tree twice, once per-sample
(`DSP4_BLOCK_KERNELS=0`, the reference) and once with kernels, drives both
with the identical `DSP4_PROFILE_SIGNAL` stimulus, and compares chip 2 across
the two arms. Both arms configure chip 2. Both are decimated identically —
neither fits a block period, and an undecimated run reads as a dead card
rather than as a comparison.

### What passes

**All 44 raw node-output probes.** `_buf_<id>` is the last sample processed,
which only the block arm reads at a defined position, so these are compared as
SETS: the block arm's word must be one the per-sample reference actually
produces. 0 of 44 outside, across FDR, EQ, GEQ, AFB, LIM, DLY, OUT, GATE,
COMP, XOVER, MIX_BUS, FX_ENGINE, MONITOR, AUX_INPUT and the stereo/codec
outputs.

**Six of thirteen meter peaks, bit-identical** — every chain whose dynamics
are not engaged reads exactly 0.500000 in both arms (AUX 04/07/12, FX 01/06).

**The negative control fires**: 26 of 26 differ under a deliberately wrong
pairing, so the comparison can fail.

**And the D16 dispatch's third item is directly witnessed.** A dump of the
aux-04 chain in the block arm:

```
_blk_C2_RECV_AUX_04      0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_FDR_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_EQ_04        0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_GEQ_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_AFB_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_LIM_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_DLY_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_blk_C2_AUX_OUT_04       0x08000000 0xF8000000 0x08000000 0xF8000000
_mtr_wblk_C2_AUX_OUT_04  0x00800000 0xFF800000 0x00800000 0xFF800000
_buf_C2_AUX_OUT_04       0xF8000000
```

Every sample of the block carried through eight node classes, and the meter's
wide word is the whole block in Q8.24 rather than one sample repeated eight
times. That is the un-decimation the dispatch asked to be verified.

### What does NOT pass, stated plainly

**A systematic 0.44–0.70% difference between the two builds, confined to the
chip-2 chains whose GATE and COMP are actually engaged** (group, sub, main).
The block arm's peak is consistently ~0.70% LOW and its RMS ~0.44% HIGH —
opposite directions, so it is not a gain error.

It is not boot-to-boot noise, and that was controlled rather than assumed:
the same block-kernel build booted twice gives **19 of 26 probes bit-identical
and a worst case of 0.198%**, against a cross-build worst of 1.249% that is
consistent in sign on every affected chain. The difference is 3.5–6x the
instrument's own reproducibility.

**It is NOT root-caused.** Ruled out by evidence, not by argument:

- *the biquad cascades* — the aux chains carry three of them (EQ, GEQ, AFB)
  and agree EXACTLY;
- *stale sidechain reads* — `_gate_key_src_`, `_gate_det_src_` and
  `_comp_key_src_` are all 0 and the bodies read only their own input, which
  the wrapper stages per sample;
- *boot-to-boot variation* — controlled above.

What is left is GATE and COMP under the generic wrapper, and that is where
the next stage of this work starts. **No chip-1-grade bit-exactness claim is
made for chip 2's dynamics path.**

### A defect found in the bar's own first run, worth recording

`_fdr_level_C2_AUX_FDR_01` read `0xE0FE0000` — a diag header word, not a float
— and `_fdr_gq_C2_AUX_FDR_01` read `0xFFFFFFFF`, so that whole aux chain
carried zero while its neighbours carried the stimulus perfectly. This is the
chip-1 phenomenon `gainfix.py` exists to repair ("roughly one boot in three
lands the CFG_COMMIT header word in `_gain_coeff_C1_GAIN_01`"), seen on chip 2
for the first time because nobody had ever configured chip 2. `c2gold.sh` now
witnesses each chain's fader head in both arms and NAMES and excludes the
unhealthy ones instead of averaging them in. **Chip 2 has no `gainfix.py`
equivalent yet; it wants one before any chip-2 bar is trusted at scale.**

## What the conversion bought

The same tree, built both ways, same stimulus, same bench:

| chip-2 whole graph, block 8 | cycles/block | % budget @983.04 MHz |
|---|--:|--:|
| per-sample (the reference) | 551,868 | 336.8 |
| block kernels | **342,090** | **208.8** |
| | **-209,778 (-38.0%)** | |

The per-sample arm is built with `DSP4_STRIP_FUSED=0`, `DSP4_SIMD_DYN=0` and
`DSP4_BQ_GRAPH=0`, because all three refuse to build without block kernels.
That does not bias the comparison: every one is a chip-1 STRIP lever and none
of them touches a chip-2 node. The per-sample arm's compressor reads
`_comp_gain = 0x04C8FBF4`, about -10.5 dB of gain reduction, so its dynamics
are genuinely engaged rather than sitting on a cheap branch.

So the conversion is the largest single improvement measured on chip 2 to
date — and chip 2 is still at 208.8% of budget afterwards. That is the gate.

## Where this stopped, and what the next stage is

Landed and proven: the conversion, the five defects, the three-size cost
table, the two new instruments, the standing bars.

Open, in the order they are worth doing:

1. **D80** — root-cause the 0.44-0.70% dynamics difference. It is the one
   thing standing between this and a bit-exactness claim, and it is localised
   to GATE and COMP under the generic wrapper.
2. **D79** — a `gainfix.py` equivalent for chip 2. Every chip-2 bar is a
   lottery until there is one.
3. Real hoisted kernels for LIM, COMP, GATE, DLY and XOVER in place of the
   generic wrapper. Worth roughly 90 MHz of a ~740 MHz shortfall — worth
   doing, and it does not change the answer.
4. Wire the biquad and dynamics pairing chip 1 already has. Worth ~540 MHz,
   and still 196 MHz short.
5. The gate itself, which is PW's.
