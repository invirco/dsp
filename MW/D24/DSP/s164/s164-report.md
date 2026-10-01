provenance: AI-drafted 2026-10-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S164: AUX A level, front phones patch, input headroom

## 1. AUX A 1-2/3-4/5-6/7-8 (P63-P66): what the jack really carries

The dispatch said these jacks come from the AK4619 codec. They don't. The
netlist (`~/mx26/docs/d24-analog-paths.md`, "Rear XLR OUT_1..8 also appear
unbalanced on the phone-jack board") and the phone-jack BOM (`_mx/MW/D24/HW/D24
Phone Jack PCBA rev B/Bill Of Materials D24 Phone Jack.xls`) agree:

- each AUX A tip/ring is the matching rear XLR's `OUT_n+` / `OUT_n-`, taken off
  the analog board's J9 → phone-jack J5 FPC;
- one NJM4580L per output (U1..U8): unit B is a difference amplifier with all
  four resistors at 10k 0.1 % (R43/R45, R44/R46 for OUT_01), unit A a follower
  of it, and both drive the jack through 33R (1206);
- gain = 1 on hot − cold, so **the tip carries the full balanced level**.

So one leg against the lane's balanced XLR reference should read **0 dB**, not
−6.02. Loading can't account for any difference: the XLR stage has 33R build-out
resistors on each leg (R1875/R1876) and the TRS stage has 2 × 33R in parallel.
The AK4619 drives only the panel speaker on a D24 (S102/S122).

Measured on MW-D24-2: −1.42 dB (P63 L, pass 5, MIC 1 ref 5.28 → 3.86) and
−0.8 dB (hand check 2026-09-30, MIC 3). Both sit inside the ±3 dB window, and
nothing in the stage explains them. The resume's four jacks give the
cross-check PW asked for.

**Change:** `single_ended_db` is gone. Each single-ended row names its own key
(`level_key` column): `trs_aux_out_db = 0.00` (derived; its source cell gives
the trace) and `phones_out_db`. level_tol, the stereo match, R-inverted and the
null are unchanged.

## 2. The front phones jack (row 97, P67)

DAC_09/10 = U92 (AK4458) ch 1/2 → `analog J10` tip/ring through NJM4580M
U90/U91. It's the XLR stage's multiple-feedback low-pass (2 × 1k in,
6k2 feedback, gain 3.1 on the DAC differential), which gives half the
balanced XLR's 6.2: **a −6.02 dB prediction**, in phase with the XLR hot on the
tip.

**Netlist anomaly:** U90.5/U91.5 (+in) sit on GND, and the mirror network that
should feed them (R1982/C843, R1976 6k2 to GND) is left on its own net. If the
board is built that way, the stage takes one DAC leg only. That predicts
**−12.04 dB** plus the DAC's common-mode DC × 3.1 on an output with no coupling
capacitor. The schematic is the place to settle this; the first reading will
show which build is on the unit.

MONITOR L/R (J53/J54, U93) read **−26.2 dB** against the XLR on pass 4, which
is also unexplained.

Because of this, `phones_out_db = nan`: the level is **recorded, not judged**
until a unit has read it. The polarity (L normal, R inverted), the L/R match
(1.5 dB) and the null (−30 dB) **are** judged.

The patch is one K2 patch on MIC 1 with three sub-tests, driven like
MAIN/MONITOR by the donor's pan: L `main:L`, R `main:R`, null `main:C` (pan 0.5
= index 63). `Mon PhonesLevel` is opened at unity in the standing write.

Row 97 had carried the catalog's NOT TESTED since pass 1. Two runner changes
keep that word from blocking the new test:

- `settled()` no longer counts NOT TESTED as tested on a runnable row;
- `put()` lets any measurement replace NOT TESTED. Before this, a measured FAIL
  would have stayed in history under a NOT TESTED headline.

## 3. Input headroom (PW definition)

Headroom is the input level at which THD+N reaches 1 % (−40 dB), at gain
code 0. It is reported in dBu at the connector (drive + `units.csv` dac_fs_dbu,
the AUX 1 full scale, 23.13) and in dBFS at the converter, with THD in dB and %.

- It's one more sub-test (`hr`) at the end of each of the 24 gain-walk patches,
  so the lead is already in.
- The ramp runs from −12 dBFS drive up in 0.5 dB steps to a 0 dBFS ceiling.
  Each step settles 3 windows and reads 2. The crossing step is read twice, and
  the level is interpolated linearly. All of these numbers are
  `patch-limits.csv` keys (`headroom_*`).
- It sits on no catalog row. The runner keeps it per patch in
  `state.json patches[Pnn].hr` (dBu, dBFS, drive, THD), and the resume owes it
  until it has been recorded once.
- On the resume, a gain-walk patch whose gain steps already carry verdicts is
  walked for the `hr` sub-test **alone**.
- A ramp with no tone under it is NO DATA ("no tone reached"). It is never
  reported as "headroom above X".

**The reference (PW ruling):** `tools/accept/headroom_ref.py --state
runall/state.json --write` averages the pass into `headroom_ref_dbu`. It leaves
out, and names, any input more than 3 dB from the median and any input with no
level. It also writes each input's value as `headroom_micNN_dbu` and the source
pass. While the reference reads `nan`, the pass records and does not grade.
After that, an input more than `headroom_tol_db = 1.0` (PROVISIONAL) below the
reference fails.

Cost: about 6 s of machine time per input on the unit (about 13 steps), and
207 s per pass on the model.

## 4. Fixture owed: the −20 dB pad lead (K6)

This is listed in `patch-plan.md` under "Fixtures owed" and has not been built.
It enables **output headroom**: each XLR output ramped to 1 % THD into one
input at code 0. Without the pad, the input clips first, because the outputs
swing about 5.6 dB more than an input takes.

## 5. Proof

- `s164_check.py` passes end to end on the model, starting from the unit's real
  paused state and catalog. It covers the list, the limits, the scorer, a
  resume that walks 55 patches (24 headroom-only plus P63-P93) with rows 1-24
  unchanged, row 97 graded, all headroom values recorded, and the reference
  average with its exclusion and the next pass's grading.
- Regression suites: see `regression.out`. The changes to earlier suites are
  expectation updates for S164: s159 `trs_dry_run`'s model leg went from −6.02
  to −1.42, the mini-jack patch id is now looked up, and the s159/s163 resume
  sets now include the headroom-owed patches.
