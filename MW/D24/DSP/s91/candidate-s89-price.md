provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S91 — candidate-s89 staged, and the driven row re-priced under the fix

**The one-line answer.** The driven row is **UNCHANGED**. On the bar's own
row — D24, chip 2, `capacity.sh --driven` on the `driveall` bitstream — the
shipping arm reads **84.38 %** and candidate-s89 reads **84.39 %**, a delta of
**+0.01 points**, while chip 1, whose code is byte-identical between the two
arms, moved **−0.22** on the same row. S89e's "zero cycles, zero DM" claim was
tested under load and it holds: the fix is an order of magnitude inside the
instrument that measures it.

| | chip 2 driven, D24 | vs the 84.47 % bar |
|---|--:|--:|
| shipping (`DSP4_TX_DEFER=0`) | **84.38 %** (boots 84.39 / 84.38) | −0.09 |
| **candidate-s89** (`DSP4_TX_DEFER=2`) | **84.39 %** (boots 84.30 / 84.49) | **−0.08** |

Zero missed blocks in every D24 row of both arms, over 3.24 M blocks. The
driven regime was proved on every driven row rather than assumed: 48 of 48
dynamics envelopes live on chip 1 and 28 of 28 on chip 2, on all four D24
boots.

---

## Gate 1 — candidate-s89 is staged, and it is the artifact S89e named

A build from HEAD with **no override** — `shipping.config` carries
`DSP4_TX_DEFER=2` since S89e — reproduces S89e's pair exactly:

    chip1.ldr  5b0629f0b39ed6e7c93e629b2d593803   (426,464 B)
    chip2.ldr  9da000f0f95ea0165f5fab43ba96e06e   (367,056 B)

`check_shipping_config.sh --expect-shipping` computes the triple
`0xCF45FF10 / 0xE2018E6F / 0xC47C0FA6`, which is S89e's third word.

**The control arm re-proves the switch is inert when off, in this session and
by accident rather than by design.** `capacity.sh` built the
`DSP4_TX_DEFER=0` arm for the ladder below and printed
`chip1.ldr e3e25a79  chip2.ldr 41a6b913` — the S82 signed pair, byte for byte.
So the only difference between what is signed today and what is staged is the
one named switch, checked twice tonight on two independent build invocations.

Staged to `~/dspboot/candidate-s89` by a new `MW/D32/DSP/SHARC/deploy-s89.sh`,
modelled on `deploy-s82.sh` and carrying the same four verbs
(`--stage`/`--status`/`--deploy`/`--rollback`), a README that states the pair,
the triple and what the switch does, both symbol maps, and the shipping
bitstream so the candidate is self-describing. **Nothing was flashed and the
standing slot was not touched.** `~/dspboot/candidate-s82` md5s are unmoved
(`e3e25a79…` / `41a6b913…`).

**`deploy-s82.sh` names a bitstream that stopped being shipping at S85** — it
copies `dsp4_logic.7a6a4529f29c` into the candidate directory and calls it
SHIPPING, and the label moved to `d02d83b3cc22`. `deploy-s89.sh` carries the
current one. The older script is left alone: it is the S82 artifact and
rewriting it would change what that candidate says about itself.

## Gate 2 — the driven ladder, both products, both arms

`ARM=… PRODUCT=… ./capacity.sh --driven`, two boots an arm, three rows a boot,
135,048–135,054 blocks a row, on `dsp4_logic_driveall.943f27966c28` — the same
stimulus S86 took the 84.47 % bar on, design-ID `32'h27966c28` read back off
the part before the ladder and `32'h83b3cc22 SHIPPING` read back after it.

**Mean `_proc_cyc`, the field every row on record is quoted in:**

| row | D24 chip 1 (null arm) | D24 chip 2 | D32 chip 1 (null arm) | D32 chip 2 |
|---|--:|--:|--:|--:|
| A silent, default | 43.02 → 43.02 (**+0.00**) | 77.65 → 77.56 (**−0.09**) | 54.95 → 54.86 (−0.09) | 92.57 → 92.69 (+0.12) |
| B silent, loaded | 57.55 → 57.55 (**+0.00**) | 84.40 → 84.46 (**+0.06**) | 75.83 → 75.88 (+0.05) | 102.89 → 103.09 (+0.20) |
| **C DRIVEN, loaded** | 57.59 → 57.38 (**−0.22**) | **84.38 → 84.39 (+0.01)** | 76.05 → 75.95 (−0.10) | 102.98 → 102.88 (−0.10) |

**Chip 1 is what makes those deltas a measurement.** `DSP4_TX_DEFER` is a
per-chip mask naming chip 2 only, so chip 1's code does not move between the
arms — the images differ in one byte and that byte is chip 1's own config
stamp. Its six deltas across the two products run **−0.22 … +0.05**, and the
largest chip-2 delta anywhere in the table is **+0.20**. The candidate's own
boot-to-boot spread reaches **0.28 points on D24 and 0.29 on D32**; the
control's reaches 0.19 and 0.40. Every chip-2 delta in this table is smaller
than the spread of the arm it was taken on.

**Worst block after clear**, the number a budget actually has to cover:

| row | D24 chip 1 | D24 chip 2 | D32 chip 1 | D32 chip 2 |
|---|--:|--:|--:|--:|
| A | 43.20 → 43.14 (−0.06) | 77.63 → 77.76 (+0.13) | 55.08 → 55.23 (+0.16) | 92.85 → 92.94 (+0.09) |
| B | 57.67 → 57.68 (+0.00) | 84.48 → 84.62 (+0.14) | 76.15 → 76.20 (+0.05) | 103.00 → 103.02 (+0.03) |
| C | 58.06 → 57.90 (−0.16) | 84.85 → 84.96 (+0.11) | 76.44 → 76.68 (+0.23) | 103.20 → 103.32 (+0.12) |

**Chip 2's worst block reads +0.11…+0.14 on all three D24 rows, and the same
sign shows in S89e's silent table (+0.13 / +0.16).** Saying it is inside the
noise would be half the truth: a consistent sign across six independent rows
is not what noise looks like. What bounds it is that chip 1's null-arm worst
block swings **−0.16 … +0.23** over the same rows, so the instrument cannot
resolve a tenth of a point on this field; and that the measurement window on a
deferred build legitimately grew to cover `_blk_latch_bufs` and the gather
(S89e states this and it is why the window moved with the code). **If it is
real it is about a tenth of a point on the worst block, against 15 points of
headroom to 100 %.** It is stated rather than averaged away.

### Missed blocks, which are not this fix's

| arm | D24 | D32 |
|---|---|---|
| shipping | **none in any row** | B chip 2: 7,192 · C chip 2: 7,239 |
| candidate-s89 | **none in any row** | B chip 2: 7,409 · C chip 2: 7,469 |

**D32's loaded configuration does not fit on either arm and never did.** Chip 2
sits at 102.9–103.1 % of budget the moment the load is applied and drops
2.66–2.77 % of blocks, on the shipping arm as much as on the candidate. That
is the standing D32 position — S18 measured 112.3 % driven, and
`DSP4_C2_BQ_GRAPH=0` plus `shipping.config.s20` is the open proposal about it
— not something this switch introduces. Every silent row and every chip-1 row
on both products missed nothing.

## Gate 3 — famverify, on the candidate configuration

`STAGE=/home/app/s91fam PRODUCT=d24 ./famverify.sh`, **exit 0**, on the
restored shipping bitstream, contract pin `defs-v2026.09.19.3`, CSV sha256
`220a14eca190…`.

**All 20 audio-live families read LIVE** — ANTI_FB, COMPRESSOR, CROSSOVER,
DELAY, EQ_BIQUAD, FADER_PAN, FX_ENGINE, FX_RETURN, GAIN, GATE, GEQ, HPF_LPF,
LIMITER, MATRIX, MATRIX_OUT, MIX_BUS, MONITOR, NOISE_GEN, ROUTING, TUBE_SAT —
and **every contract count is complete** (20/20, 17/17, 46/46, 31/31, …).
The three numeric arms that produce a verdict are **BIT_EXACT**: FADER_PAN,
GATE, TUBE_SAT.

Against the last full D24 walk on record (`famverify-s25-d24.json`), **24 of 27
families carry identical verdicts**. The three that differ are all explained
and none is this switch:

- **FADER_PAN numeric FAILED → BIT_EXACT.** S83 fixed it; this is the fix
  still landed.
- **COMPRESSOR numeric FAILED → NO_VERDICT.** The arm declines rather than
  fails, and says why in the report: *"the node does not arrive at the same
  state twice, so no repeat can be the noise floor."* Its audio arm is LIVE.
- **TALKBACK LIVE → NO_FLOOR.** The talkback front end is AN_EN-gated (S70,
  item 27) and the rails are down at handback.

## Gate 3 — the cable-loop THD row, and what could not be taken

### The candidate is clean on the part today: 0.32122 %, PASS

    ARM=s91load BUILD=0 ./loopthd.sh       -22.22 dBFS,  0.32122 %  PASS  exit 0
                       at -22.0 drive      -31.46 dBFS,  0.03342 %

A `DSP4_TEST_NODES=1` build of the candidate configuration (`chip1 0d4a4416`,
`chip2 6f11a1dd`), booted through the S89-1 link gate with zero retries, on
the restored shipping bitstream, lane Monitor L (strip 20) → MIC 6 (strip 6),
595 chain at gain code 0. That **reproduces S89e's 0.3212…0.3216 % and its
−22.21…−22.25 dBFS return level to the third decimal**, on a fresh boot a day
later with the CPLD flashed twice in between. The loop tracks the drive (9.24
dB of return for 10 dB of stimulus), so it is a live lane and not a floor.

### 🔴 THE ROW CANNOT BE TAKEN IN THE DRIVEN REGIME ON THIS LANE, AND THE REASON IS IN THE RTL

The dispatch asks for this row "at the driven regime". **It is not measurable
there, and that is a property of the bitstream, not a shortfall of the
attempt.** `driveall` assigns

    assign i_dspa[5:0] = {6{pcm_drive}};        rtl/dsp4_logic_top.v:572

so **every DSPA input lane carries the Pi's playback**, MIC 6 among them. The
lane the loop cable returns on is overwritten by the stimulus by construction:
on `driveall` the cable is disconnected as far as the DSP is concerned. A
driven-regime loop reading needs the loop's return on a lane the stimulus does
not drive — a codec input — and the cable is on a mic input, which is PW's
hands to move.

### What was measured instead, and why it still failed

The stand-in was the **loaded configuration on the shipping bitstream**, which
is the right one on the axis that matters: the defect is a function of *where
in the block period the gather lands*, that position is a function of the
graph's cycle count, and S82, S85 and S86 all put chip 2's loaded row within
**0.08 points** of its driven row (84.27/84.34, 84.36/84.35, 84.41/84.47). Same
position, no CPLD flash needed.

`LOAD_SETUP=1` was added to `tools/pi/dsp4_loop_thd.sh` for it: it applies
`dsp4_driven_setup.py --mode load` to both chips after the gated boot and
before the route write, and **prints where the gather actually landed** —
chip 2's `_proc_cyc` as a percentage of budget, read on the same boot as the
THD number beside it. That half works: it read **84.32 %** and **84.50 %** on
the two attempts with the dynamics engaged, which is the driven position to
within a tenth.

**The reading itself is INCONCLUSIVE and the leg said so rather than printing
a number.** Four things were eliminated on the part, in this order:

| what was tried | return level | tracking |
|---|--:|---|
| load applied, rails down | −115.66 dBFS | — |
| rails raised (AN_EN `op dh`) | −63.35 dBFS | 0.01 dB for 10 dB |
| dynamics cleared off the loop path (`--off Comp,Gate,Limiter`) | −19.00 dBFS | 0.52 dB for 10 dB |
| 595 chain written to gain code 0 | −19.00 dBFS | 0.50 dB for 10 dB |
| 31 other strips closed off MAIN | −19.00 dBFS | 0.58 dB for 10 dB |

**The loaded configuration puts about −19 dBFS of broadband content on the
measurement strip's post-fader tap**, roughly 3 dB above what the loop itself
returns, and no route change moves it. The same arm on the same boot with the
load *not* applied reads −22.22 dBFS and 0.32 %, so the lane, the cable, the
chain and the build are all fine. The loaded regime and this cable loop cannot
be asserted together on this lane.

The two diagnoses along the way are worth keeping because both looked like the
answer and neither was: the load turns every dynamics node on at a −60 dB
threshold and the loop's donor is Monitor L, whose source is MAIN, so the MAIN
compressor and limiter sit downstream of both strips the route write clears
(that took it from −63 to −19); and the load opens every strip into MAIN, so
MAIN sums 32 lanes of converter noise (closing 31 of them changed nothing, so
that one was wrong). Both are now written into the leg where the next session
will read them.

**What the driven-regime question can be answered with instead.** S89e measured
the fixed build clean at **three graph speeds — 78.8 %, 86.7 % and 93.1 % of
budget** — which brackets tonight's driven 84.4 % from both sides, and the
unfixed build folds at one of those three and is clean at the other two. That
is the load-independence proof, and it is an argument from an existing
measurement rather than a new one.

## Gate 4 — the numbers, plainly, and no ship/no-ship call

**BETTER, WORSE or UNCHANGED: UNCHANGED.** +0.01 points on the bar's own row,
against a null arm swinging −0.22 on the same row and a boot-to-boot spread of
0.28. S89e's "zero cycles, zero DM" survives being tested under load; the
switch moves the gather, it does not add work.

**Nothing in the driven regime changes the picture S89e closed.** The fold is
fixed, the triple moves in one word, the twenty families are LIVE with every
contract count complete, the loop reads its floor, and the D24 driven row sits
where it sat. **Whether candidate-s89 ships is PW's call and this session does
not make it.**

Two things a reader should carry forward rather than take as settled:

- **Chip 2's worst-block figure is consistently ~0.12 points higher on the
  candidate** across six rows and two sessions. Bounded by the null arm's own
  ±0.2 swing and worth about a tenth of a point against 15 points of headroom,
  but it has a sign and the sign repeats.
- **The cable-loop THD row has no driven-regime reading and will not get one
  on this lane.** Either the loop cable moves to a codec input (PW's hands),
  or the row is accepted as an idle-regime row with S89e's three-speed
  bracket standing in for the load axis.

## Files

- `MW/D24/DSP/s91/candidate-s89-price.md` — this report.
- `MW/D24/DSP/s91/readings.csv` — 48 rows, one per arm × product × row × boot × chip.
- `MW/D24/DSP/s91/tools/s91_caprows.py` — the table above, from the goldens.
- `MW/D32/DSP/SHARC/deploy-s89.sh` — stage/status/deploy/rollback for the candidate.
- `MW/D32/DSP/SHARC/goldens/cap-s91{ctl,fix,ctl32,fix32}-*.json` — 24 row files.
- `MW/D32/DSP/SHARC/goldens/famverify-s91-cand.json`.
- `tools/pi/dsp4_loop_thd.sh` — `LOAD_SETUP` / `LOAD_OFF` and the position readout.

## Unit as found

- **Shipping CPLD `d02d83b3cc22` back in flash and PROVED, not assumed**:
  `design_id 32'h83b3cc22 cfg_bits 16'h0010 SHIPPING` read off the part after
  the reflash and again at handback. `driveall` was on it only for the ladder.
- **`~/dspboot/candidate-s82` untouched** — `e3e25a79…` / `41a6b913…`, unmoved.
- **`~/dspboot/candidate-s89` staged, not flashed** — `5b0629f0…` / `9da000f0…`.
- The standing slot still holds the S82 signed pair, double boot+config'd at
  handback: **BOOT_STAGE 7 both chips**, FRAME_COUNT running, `SPORT0_ERR_A 0`,
  `BUILD_CFG 0xCF45FF10 / CFG2 0xE2018E6F`.
- **The inter-chip link is proved clean at handback**: `s89_signbit.py`
  **OVERALL: CLEAN**, both lanes, exit 0.
- **AN_EN (GPIO26) `lo`**, CS_M (GPIO27) `ip pu`, `matrix-app` **active, 3 of 3
  MCUs** (H1S1, H1S3, H1S4).
- S87's four uncommitted files untouched. `defs.lock` unmoved, no generated
  artifact moved.

**Two deliberate differences, both restored, both stated because they were
real while they lasted:**

- **AN_EN was raised** (`op dh`) for the loop readings and put back `lo`. The
  analog loop cannot be read through dark rails — the first attempt returned
  −115.7 dBFS and the leg called it INCONCLUSIVE, which is the correct answer
  and not a measurement. S89e did the same and restored the same way.
- **The 595 preamp chain was written twice**: to gain code 0 (all-zero image,
  the S88/S89e reference state) for the readings, then back to **SAFE**
  (`01 ×24, 00` — gain 0, phantom off, MUTED), VERIFIED 200/200, which is the
  state `d24_selftest.py` parks it in and what S90 left. Worth recording: the
  pass-1 shift-out before the first write read
  `00 13 6E 20 00 00 00 00 00 E0 FE 00 00 00 00 00 00 E0 FE 00 00 00 00 00 00`,
  which is **S89e's pre-existing image and not SAFE**, so the chain was not in
  the state S90's report implies it was left in.

One thing that is not a difference but should not surprise anyone reading the
bench: `capacity.sh`, `loopthd.sh` and `famverify.sh` all `scp` their Python
into a stage directory that symlinks `/home/app/dspboot/*.py`, so those writes
go **through** the symlinks and refresh the bench copies from this tree
(S83-2's trap, established behaviour of every one of these scripts, not new
tonight). `s89_signbit.py` was additionally copied into `/home/app/dspboot`,
where it had never been staged, so the handback gate could run at all.
