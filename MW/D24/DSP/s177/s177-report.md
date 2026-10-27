provenance: AI-drafted 2026-10-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S177: D24 analog-in → analog-out latency, and what ≤ 1.0 ms costs

Desk study. Nothing flashed, no unit contacted (MW-D24-2 is away on fixture
work). Every figure is counted from this tree's source or taken from a
measurement on record (cited); projections are marked as projections. The
arithmetic is `s177_latency_model.py` beside this file, which reproduces the
measured arms before it prints anything.

## 0. The answer

- **Today, measured: 91.4 samples = 1.904 ms** analog in → analog out (S60's
  whole-loop chirp, 91.40 repeated in S54, S55 and the S121 per-unit nominal).
  The hub's 93 (5 + 82 + 5.8) adds the Pi-path contract number, which carries
  about two samples of Pi re-framing an analog path never crosses (§1.3).
- **The pipeline is 80 of those 91.4 samples: five blocks of 16.** Two per
  chip, plus one for chip 2's transmit guard (`DSP4_TX_EARLY=2`). The fabric
  hop between the chips costs well under a sample. Converters 10.8, residual
  0.6.
- **≤ 1.0 ms needs the pipeline ≤ 36.6 samples.** On the current card that is
  reachable only at **block 8 on both chips with the guard replaced by a
  2-frame TX phase offset (47.4 samples, 0.988 ms)**, and two things on that
  line are unproven: whether the DMA's lead is short enough for a 2-frame
  offset (S9-2 says it is about 2 frames, so 3 is the safe figure and that
  gives **49.4 samples, 1.029 ms**), and whether chip 2 fits block 8 with
  headroom (**projected 87.6 % in the default regime, 101.5 % in S150's worst
  regime** — not a fit).
- **The best that fits today: block 16 with the guard replaced by a 3-frame TX
  phase offset on chip 2: 78.4 samples, 1.633 ms** (−13 samples, −0.27 ms).
  Zero cycles, and it removes the deadline the guard was bought for rather
  than moving it. This is the first recommendation.
- **The route that clears 1.0 ms with margin is a card change**: chip 1 has no
  path to the DACs today (its eight output ports are the one-way MIX fabric to
  chip 2, wired direct, not through LOGIC). A rev E with one DSPA TDM8 output
  into LOGIC and one DSPB → DSPA return lane lets the critical routes stay on
  one chip: **46.4 samples, 0.967 ms at block 16**, no block-size change.

## 1. The 80-sample pipeline, stage by stage

### 1.1 What one chip costs: two blocks, counted from the source

- `src/dma_config.c:341-372`: every lane is a 2D autobuffer, **one DMA row =
  one block** (`XCNT = lane_words × DSP4_BLOCK_SIZE`), `YCNT = 2` (ping/pong).
  All lanes share LOGIC's frame sync and are armed together, so every lane's
  row boundary is the same instant (`:330-337`); the block interrupt is the
  SPORT0 RX row end.
- `src/sport_init.asm:319-397`: the ISR toggles the pending RX and TX rows and
  raises `_block_ready`; `_blk_latch_bufs` (`:449-479`) hands the core the RX
  row that just completed and the TX row the DDE clocks NEXT (the S8-1 phase
  fix: "it fills the row the DDE has just finished with, and that row goes out
  on the next block", `:193-216`).
- So a sample at position j of input row n waits **B − j** frames for the row
  to complete, the graph runs for **one block period** (`src/main.asm`
  main loop, `_block_ready` at `:939`), and the sample leaves at **position j**
  of the next TX row: **2B for every j**, independent of where in the period the
  graph finishes, and independent of the other chip's row phase (each chip's
  in → out is fixed on its own grid; the fabric is continuous TDM).

### 1.2 The table at block 16 (shipping: `shipping.config` `DSP4_GEN_BLOCK=16`, `TX_EARLY=2`, `TX_DEFER=2`)

| stage | samples | ms | source |
|---|--:|--:|---|
| AK5558 ADC, short-delay sharp (SD strap) | 5 | 0.104 | AK5558 data sheet; strap read in `dsp4-s42-20260913.md:85-93` |
| LOGIC ADC retime | 1 BCK (1/256 frame) | — | `rtl/dsp4_logic_top.v:762` |
| chip 1: input row assembly (B − j) + graph period (B) + output position (j) | 32 | 0.667 | §1.1 |
| chip 1 → chip 2 MIX fabric (TDM16, direct PCB) | < 1 | — | `tdm-lines.csv` MIX_0..2; folded into the residual |
| chip 2: same two blocks | 32 | 0.667 | §1.1 |
| chip 2 transmit guard, `DSP4_TX_EARLY=2` | 16 | 0.333 | `_blk_latch_bufs`; S11 measured +16 per chip |
| `DSP4_TX_DEFER=2` (deferred gather) | 0 | 0 | writes the same row, earlier in the period (`s89/dac-fold-fix.md:124`) — **not re-measured since S89e** |
| AK4458 DAC, short-delay sharp (parallel-mode default) | 5.8 | 0.121 | AK4458 data sheet table 16 |
| residual (TDM slot positions, retime, filter definitions) | 0.6 | 0.013 | S60 − 80 − 10.8 |
| **total** | **91.4** | **1.904** | **S60, measured** |

**Model check** (`s177_latency_model.py`, Pi-path residual 2.5): B16 guard
off 66/67 measured vs 66.5; guard on chip 2 82 vs 82.5; guard on both 99 vs
98.5; **B32 guard off 131 vs 130.5**; S60 analog 91.40 vs 91.40. Two block
sizes and three guard settings on one rule — the model is the firmware.
(The record's block-8 "72 samples" was an image missing 70 % of its blocks
and is superseded, `dsp4-capacity-s11-20260909.md:141-145`.)

### 1.3 Reconciling 91 (S60) with 93 (hub) and 82 (contract)

- The **82 contract** is the Pi path: Pi → LOGIC re-framer → chip 1
  (`XIN_PI → XS_XFER`, no strip) → chip 2 (`C2_PI_IN → MIX_MAIN → MAIN_FDR →
  MAIN_DLY → MAIN_ST_OUT`) → re-framer → Pi, minus LOGIC's own Pi loop
  (`rtl/dsp4_logic_top.v:518-522`). Its 2–3 samples above 80 are the
  re-framer's frame each way and the capture snapshot
  (`rtl/dsp4_pcm_reframe.v:15-16, :427`).
- The **S60 loop** is analog: TEST_OSC on strip 6 → AUX 1 → chip 2 → DAC
  OUT_01 → cable → MIC 5 (AK5558) → strip 5 → TEST_MEAS, against the strip's
  own digital block (deconvolves to 0 with no analog) — the whole loop, nothing
  subtracted (`findings.md:4480-4533`). It crosses chip 1 once and chip 2 once,
  which is exactly the mic → bus → output path.
- So **5 + 82 + 5.8 = 92.8 double-counts the Pi framing**; the analog path is
  80 + 10.8 + 0.6 = **91.4**. The S83 80 vs the 82 contract is the same
  arm inside its own 19-sample spread (`s83/contract-lanes.md:233-242`).

### 1.4 The aux and matrix rules

- S150 (PW 2026-09-29): "0.33 ms latency is ok, but no more" for the aux
  matrix arm = **exactly one block, 16 samples**; Main, monitors and phones
  stay at the base figure (`s150-report.md:131-147`). The arm
  (`DSP4_C2_AUX_MTX`) **ships 0** and its bench row was never executed
  (`s146/switch-runbook.md:879-884`, `tasks.md:307`). The "98-sample aux
  contract" is S148's proposal of 82 + 16, never measured.
- Every lever below scales that term with the block: at block 8 it is 8
  samples (0.167 ms) and stays inside PW's 0.33 ms rule.

## 2. The levers, priced

Capacity references (budget 327,680 cycles/block at block 16, 983.04 MHz;
abort line **~97 % or any missed block**, `s148-full-cell-fit.md:674`;
"a fit with no headroom is not a fit", PW 2026-08-28, `tasks.md:11955-11961`):

| | chip 1 | chip 2 | source |
|---|--:|--:|---|
| S91 driven, D24, last on-part row (pre `C2_BQ_GRAPH`) | 57.59 % (worst 58.06) | 84.38 % (worst 84.85) | `s91/candidate-s89-price.md:66-90`, 0 missed in 3.24 M blocks |
| S148 baseline (construction, with `C2_BQ_GRAPH`) | 58.91 % | 74.7 % | `s148-full-cell-fit.md:664-672` |
| S150 regimes R1 / R2′ / R3 / R4′ (construction) | — | 76.37 / 83.83 / 82.82 / **90.28 %** | `s150-report.md:284-305` |

**Per-block fixed cost F.** A block-size change moves load by F/327,680:
at block B the load is L16 + F·(16/B − 1)/327,680. F from S19's three-size
ladder (`dsp4-capacity-decision-20260902.md:23-27`), the only one on record:
**chip 1 ≈ 73.5 k cycles (+22.4 points at block 8), chip 2 ≈ 36.9 k
(+11.3 points)**; session 11's ladder agrees for chip 1 (≈ 70 k). Those
ladders predate round-once, float, `SIMD_DYN`, `DYN_LUT` and `BQ_GRAPH`, so
**today's F is unmeasured** — the block-8 rows below are projections.

### (a) Block 16 → 8 (and 4)

| | chip 1 @ B8 | chip 2 @ B8 | latency (with guard) |
|---|--:|--:|--:|
| S91 measured basis | ≈ 80.0 % | ≈ 95.7 % | 51.4 samples, 1.071 ms |
| S148 baseline | ≈ 81.3 % | ≈ 86.0 % | |
| S150 R1 / R4′ | — | ≈ 87.6 % / **≈ 101.5 %** | |

- Block 8 alone **does not reach 1.0 ms** (1.071 ms with the guard), and
  chip 2's worst regime does not fit. Kernel efficiency also falls a little at
  block 8 (S17 per-class: GEQ 983 → 1043 cycles/sample, LIM 289 → 316,
  `dsp4-chip2-blockkernels-20260901.md:131-137`); that is inside F's fit.
- **Block 4**: chip 1 ≈ 57.6 + 67.2 = 125 %, chip 2 ≈ 84.4 + 33.8 = 118 %.
  No.
- At block 8 **chip 1 needs a transmit fix too**: its inter-chip gather runs at
  the end of its own graph (the latent S9-2 defect, never witnessed because
  nothing captures chip 1's IC TX). At ≈ 80 % of an 8-frame period its first
  sample is written about 1.6 frames before the boundary — on the wrong side
  of a ~2-frame DMA lead (b2 below).

### (b) The guard (hub's "output guard 2 → 1"): what it is, and what replaces it

**The guard does not absorb late blocks, and nothing on the SHARC does.**
`_block_ready` is a flag, not a queue: a block that overruns is lost and its
half re-sent stale whatever the guard is (`sport_init.asm:375-389`,
`findings.md:12723-12725`). (The "CM0 R1 work" the dispatch cites is not in
this repo.) The guard exists for **late FRAMES with zero late blocks**
(S9-2, `findings.md:14567-14603`): the TX DMA fetches frame 0 of the next
row **before** the row boundary, so a gather that finishes late in the period
loses frame 0, and at a heavier load frame 1.

SHARC late-block evidence, all D24 rows: **0 missed blocks** in S82, S86 and
S91 (3.24 M blocks); average-to-worst spread **+0.5 points** on both chips in
S91 (S11's older chip-1 build had +13). **No histogram of block finish time
exists**; the counters are `DIAG_BLK_OVERRUN`, `_proc_cyc`, `_proc_cyc_max`.
The DMA lead, from S9-2: the gather writing sample 0 about 1.5 frames before
the boundary already lost frame 0 at 92.7 % load, and the heavier arm lost 2
frames — **the lead is about 2 frames**.

- **(b1) Guard off, gather at the end of the graph (TX_EARLY=0)**: 64 → 75.4
  samples, 1.571 ms, and the deadline comes back at roughly 87 % of the period
  minus the gather, load-dependent. Chip 2's measured worst is 84.85 % and
  S150's regimes reach 90.3 %. **Not safe.**
- **(b2) TX phase offset — the S177 proposal.** Keep `TX_DEFER`'s deferred
  gather (a fixed point immediately after the interrupt, ~6,000 cycles), have
  it write the row the DDE starts **k frames after that interrupt** instead of
  one a whole period later, by **starting the TX row grid k frames behind the
  RX grid**. The deadline is then k frames minus the
  ~2-frame lead minus the gather (0.3 frame at B16), **fixed, whatever the
  graph costs** — the same invariant S89e restored, kept. On the other side,
  the row finished being read B − k frames before the write, so there is no
  S89 fold.
  **k = 3: the guard's 16 samples become 3.** Zero cycles, zero DM. Today's
  load is untouched, so the capacity margin is unchanged.
  - Mechanism risk: the 2D autobuffer has no lead-in descriptor (descriptor
    flow raises ERRC 3 on this part, `dma_config.c`), so the offset has to come
    from **enabling the TX SPORTs/DMAs k frames after RX**, timed off the RX
    channel's `XCNT_CUR`. That is a desk prototype plus a bench proof (the
    `DSP4_TXPROBE` stamp at 100.0000 % ordered, then a k sweep down to the
    failure, which measures the lead directly).

### (c) Fewer chip stages

- **Blocked by the hardware on rev C and rev D.** `shared/dsp4-logic/tdm-lines.csv`:
  DSPA's outputs O0–O7 are the MIX fabric, **direct PCB to DSPB, not through
  LOGIC** (`rtl/dsp4_logic_top.v:4-5`); only DSPB drives the DAC lanes B_O0–2;
  the mics enter DSPA only (A_I0–2); and **there is no DSPB → DSPA lane**, so FX
  returns, aux inputs, Pi, USB and BT — all chip 2 — could not reach a Main
  formed on chip 1.
- Chip 2 forwarding a chip-1 lane pin-to-pin through its SRU does not rescue
  it: the MIX lanes are TDM16 on the fabric clocks, the DACs TDM8 on the
  converter clocks, and the return path is still missing.
- **On a rev E card**, one DSPA TDM8 output into LOGIC (converter clocks) plus
  one DSPB → DSPA return lane makes mic → Main / monitors a one-chip path:
  **35 samples, 46.4 total, 0.967 ms at block 16 with b2**, or 0.633 ms at
  block 8. Main and monitor master chains move to chip 1 (≈ 40 points free at
  B16) and FX returns arrive one stage late (wet, uncorrelated). Any dry,
  correlated source that still goes through chip 2 into those buses would
  have to be delay-matched.

### (d) Combinations

| configuration | pipeline | total | ms | fits? |
|---|--:|--:|--:|---|
| today: B16, chip-2 guard | 80 | 91.4 | 1.904 | yes (measured) |
| **B16 + b2 (k=3) on chip 2** | **67** | **78.4** | **1.633** | **yes: no cycles** |
| chip 1 B8 + chip 2 B16, b2 both | 54 | 65.4 | 1.363 | chip 1 ≈ 80 % at B8: projected yes |
| B8 both, chip-2 guard | 40 | 51.4 | 1.071 | chip 2 ≈ 96–102 %: no |
| B8 both, b2 k=3 both | 38 | 49.4 | 1.029 | chip 2 at B8: no headroom |
| B8 both, b2 k=2 both | 36 | 47.4 | **0.988** | only if the lead is < 2 frames, and chip 2 at B8 |
| rev E, one chip, B16 + b2 | 35 | 46.4 | **0.967** | yes (chip 1 ≈ 40 points free) |
| rev E, one chip, B8 + b2 | 19 | 30.4 | 0.633 | chip 1 ≈ 80 % + the masters |
| B4 both, guard | 20 | 31.4 | 0.654 | no (118–125 %) |

**Best achievable that fits on the current card: 1.633 ms (block 16, b2).**
The block-8 lines would need chip 2's block-8 load under ~90 % in the worst
regime. Today's F, measured, decides whether that is close. A dual-rate chip 2
— the FX / reverb nodes kept at 16 and run on alternating block-8 periods, so
they do not pay the doubled per-block cost — is the design lever to try if it
is not. Converter levers are spent: the AK5558 is already short-delay, and the
AK4458's short-delay **slow** filter (4.8/fs, −1 sample) needs I2C control
mode — a strap and bus change.

### The AK4619 (talkback, aux in), noted per the dispatch

Its ADC still runs the sharp filter: register 0AH reads 0x00 on the part
(`s69/talkback.md:206`, `s108/dac-path-root-cause.md:60`). The data sheet
gives a **group delay of 22/fs**, and short-delay sharp (ADxSD = 1) gives
**8/fs**, so 0AH 0x00 → 0x22 saves **14 samples, 0.29 ms** on the codec
inputs. The DAC is already short-delay (DA1SD/DA2SD = 1,
`s108/...:83`). That is a separate firmware item (H1S1 init / `codec4619.py`),
proven on the bench later, and not part of this study's path.

## 3. 96 kHz

The structure is in samples, so **the same configuration halves in time**.
Both converters keep the same group delay in samples at 96 kHz (AK5558
short-delay 5/fs, AK4458 5.8/fs, data sheets). That gives **today's 91.4
samples = 0.952 ms**, with b2 **78.4 = 0.817 ms**, and block 8 with b2
**0.515 ms**.

The compute doubles: 10,240 cycles per sample instead of 20,480, so every
load figure above doubles (chip 2 ≈ 169 % on S91's basis). The part also
**refuses a 96 k build before the cycle budget does**: every fabric line is
TDM16, which needs 49.152 MHz at 96 kHz against the data sheet's 31.25 MHz
external SPORT clock (S24, `tasks.md:7051`).

So 96 kHz on DSP4 means half the channels per chip plus a fabric re-design (TDM8
lanes, twice as many). That is the D6 line: 32 ch at 48 kHz on the SHARC card,
96 kHz on the single-chip FPGA engine. The FPGA answer is also the latency
answer: a fabric engine pays no per-block overhead, so it can run at very
small blocks, which is where the hub's A&H SQ figure (< 0.7 ms at 96 kHz) comes
from.

## 4. Recommendation, PW questions, bench plan

**Recommendation.** Take b2 now: −13 samples for no cycles, and it removes
the deadline rather than moving it. Measure today's block-8 F before ruling on
block 8. Put the rev E fabric change (DSPA TDM8 → LOGIC, DSPB → DSPA return) on
the card roadmap as the route that clears 1.0 ms with margin. Do not chase
1.0 ms on the current card by spending headroom: no configuration that fits
reaches it.

### PW questions (1by1, recommendation first)

1. **The guard → a TX phase offset (b2) on chip 2.** **Rec: (a) yes.** Desk
   prototype (TX enabled k frames behind RX, deferred gather into the row that starts k frames later),
   then the bench k sweep. Contract 82 → about 69 on the Pi path; analog
   1.904 → 1.633 ms. (b) Keep the guard.
2. **Block 8.** **Rec: (a) measure first.** A captable ladder at block 8 and
   block 16 on today's shipping build, both chips, in S150's R1 and R4′
   regimes, gives today's F. Rule on block 8 only if chip 2's R4′ at block 8
   reads ≤ ~90 %. (b) Rule now on the S19-era projection (not a fit). (c) Drop
   block 8.
3. **Card rev E fabric change** (one DSPA TDM8 output into LOGIC on the
   converter clocks, plus one DSPB → DSPA return lane) for a one-chip critical
   path. **Rec: (a) put it on the card roadmap** as the ≤ 1.0 ms route (0.967 ms
   at block 16). It needs the graph to be re-partitioned (Main and monitor
   masters on chip 1) and a delay-matching rule for buses. (b) No: the target
   moves to "best on the current card" (1.633 ms).
4. **Chip 1's latent transmit race** (S9-2's chip-1 half, never witnessed).
   **Rec: (a) leave it at block 16** (chip 1 at ~58 % finishes its row about 5
   frames ahead of the DMA's ~2-frame lead). Apply b2 to chip 1 only together with any block-8 move,
   where it is required. (b) Apply b2 to chip 1 now (+3 samples).
5. **The latency contract after S89e.** The 82 has not been measured since
   `TX_DEFER=2` shipped, and neither has the analog loop. **Rec: (a)
   re-measure both first in the bench window** (Q4 plan below), before any
   change, so b2's saving is measured against today's own figure.
6. **AK4619 ADC short delay (0AH 0x00 → 0x22, −14 samples on talkback and aux
   in).** **Rec: (a) a separate item**, done and bench-proven with the rest of
   the bench window. (b) Fold it into this work.
7. **AK4458 short-delay slow (−1 sample, needs I2C control mode).** **Rec: (b)
   no.** A strap and bus change for 0.02 ms, and it changes the response.

### Bench-proof plan (MW-D24-2, when it is back; `MW/D32/DSP/SHARC/latency.sh`, `dsp4_chirp`)

1. **Baseline on the staged pair, before anything changes:**
   - LOGIC reference: `LOGIC_ONLY=1 ./latency.sh` (pisel).
   - Through-DSP: `ARM=s177base BUILD=0 STAGE=<staged> ./latency.sh` (maincap), 20 reps × 2 boots.
   - The S60 analog loop (strip 6 → AUX 1 → OUT_01 → MIC 5), checked against the S121 nominal 91.40 ± 0.5.
   - This closes the post-S89e gap.
2. **b2 arms at k = 4, 3, 2 (and 1 to find the edge):**
   - Ordering: `DSP4_TXPROBE` stamp, 100.0000 % ordered at full D24 load and with the Pi input added (S9-2's heavier arm).
   - Latency: `latency.sh`, expect 82 − 16 + k.
   - Audio and capacity: the analog THD loop (the S89 fold detector), driven capacity unchanged, `busgold` / `famverify`.
3. **Block-8 F ladder:**
   - `captable.sh` at block 8 and block 16, today's shipping switches, both chips.
   - The R1 and R4′ regimes, 2 boots, `DIAG_BLK_OVERRUN` 0.
4. **Restore the staged pair and the LOGIC bitstream found on the unit (record its design ID before step 1), and re-read both.**

Nothing in 2–3 ships without its own dispatch.
