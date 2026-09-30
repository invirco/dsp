provenance: AI-drafted 2026-09-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S153 — the 150 ohm step's auto-advance, and AS-ADC judging U15 again

Hub dispatch `tasks.md` 2026-09-30 13:17Z. PW: "fix the 150R test".

## 1. What was wrong: two faults, not one

The hub diagnosed the slow case (the peak-hold meter) and asked whether the
"drop" was sometimes the lead coming out. The evidence says yes, and it is
worse than that: **the fast case is the wrong one.**

The noise step's arrival test was `hi - lvl >= detect_drop_db` on the STRIP
METER, where `hi` is the loudest reading since the prompt. The prompt goes up
straight after the gain steps have been read, and at that moment the meter is
still **latched on the gain step's tone** (factory.log 2026-09-30: "the meter,
which is not what this is judged on, read -24.x"). So `hi` starts at about
−24 dBFS and the meter DRAINS at 6.52 dB/s:

* **FAST (MIC 3, 8, 9, 11, 15, 19 today, about 2.7 s, about 44 readings):** the
  drain alone crosses 3 dB inside half a second, and the window goes steady
  once the latch has drained down to whatever is in the socket. 44 polls at
  about 55 ms is 2.4 s, and 2.4 s × 6.52 dB/s is about 16 dB of drain. The
  operator's hand move takes 3–8 s, so on those channels the reading was taken
  **with the tone lead still in, or with the input open. It was not the
  150 ohm plug.** Those six noise figures from today's run are not
  terminated-input figures.
* **SLOW (the other channels, 14–17 s):** on these the open input's peaks
  climb back within 3 dB of `hi` (S125: an open input at gain 63 peaks at
  −29..−65 dBFS on the meter), so the window restarts. Then the 1.0 dB /
  3-block steady rule has to be met on a peak-hold sawtooth of noise, and that
  takes about 11 s.

The physical model in `noise_step_check.py` reproduces **both modes** from the
same code. On it, the S152 detector graded the plug on only 36 of 48 steps;
12 ended at 2.1–2.5 s with the lead in, or at 4.4–5.4 s with the input open.
The rest ended 8.6 s after the plug (median), 10.4 s at worst.

## 2. The fix

`tools/pi/d24_patch.py`, noise rows only:

* **The instrument is the measurement node's RMS**, one 85.3 ms window per
  poll, and each poll waits for a fresh window. The first reading also pays
  whatever settle `_prepare`'s osc-off and gain-63 writes are still owed.
  `_prepare` already points `MeasChan` at the lane.
* **The arrival test reads the shape of the swap** (`Station._noise_met`). The
  lane is cut into plateaus: 3 blocks within 1.0 dB, using the same
  DETECT_STABLE_BLOCKS and DETECT_STEADY_DB as before. A new plateau starts
  only after the lane has moved `detect_drop_db` away from the last one,
  whether by a level change or by a connector's crackle. The first plateau is
  the lead as prompted. The step is met when the lane is `drop` below that
  first plateau **and** `drop` below a later one (the open input). The existing
  stability window then grades it.
* **Everything else is unchanged:** the stability window and its restart,
  wrong-lane naming, NO SIGNAL, the timeout question at 20 s and the give-up
  at 40 s, PAUSE, pipelined scoring, and the settle clock started from the
  arrival.

**Why not an absolute level.** The hub suggested one. The data says it cannot
work on every channel. S55's own −70 dBFS rule could not separate open from
150 ohm on J31 (open −78.7, terminated −86). MIC 17's open input read −52 dBFS
in S125, level with a lead that is still in. MIC 1–4 and 13–16 have never
been measured either way.

**Result on the model:** 48 of 48 steps graded on the plug, **0.54 s after it
goes in (median), 0.67 s at worst**. That is 5–6.5 s after the prompt for a
person who pulls at 1.5–3 s and plugs 2–3.5 s later, against 12–15 s before.
The lead left in and the lead pulled with nothing fitted both time out on
MIC 7, MIC 17 and MIC 6, and are never graded.

## 3. Margin, per powered channel (dispatch item 2)

Node RMS at gain 63. Open is from S125's map (09-26). Terminated is from S55
(09-16), with both instruments shown. The full table is at the top of
`noise_step_check.out`.

* **open → plug is 5.9–13.3 dB on 15 of the 16 surveyed channels**, against a
  3.0 dB `drop`.
* **MIC 6 is the exception.** Against its open input (−81.0) it is **1.1 dB on
  S55's node figure (−82.04)** and **6.6 dB on S55's capture figure (−87.59)**.
  The two S55 instruments agree to about 1 dB on every other channel, so the
  node figure looks like the outlier, but that is not proved. On the node
  figure the step does not advance and raises the no-signal question.
* **lead → open is 27–31 dB everywhere except MIC 17 (1.2 dB).** There the
  split relies on the pull's crackle. The model has one on every pull; the
  bench has not been asked.
* **MIC 1–4 and 13–16: no data at all.** They had no front ends on 09-16 or
  09-26.

## 4. What it cannot see (stated, not hidden)

* If the operator wiggles the tone lead hard enough to move the RMS by 3 dB,
  and it then sits still for 330 ms before the pull, that reads as a plateau of
  its own. The open input would then be graded. With the lead in, the source is
  AUX 1's low-impedance idle output, so handling the cable should not move it.
  Not measured.
* A channel whose open and terminated levels sit within 3 dB has no second
  step to find. It raises the no-signal question and is not graded wrong.

## 5. Tone rows untouched: proved

* The tone branch of `detect` is byte-for-byte the old expression, and `watch()`
  with no arguments is the old meter peek.
* `patch_auto_advance_check.py` (S145) passes in full, including the removal
  edge, the wrong-input naming, the timeout question and the whole-pass
  ENTER-free screens. Its noise test now models the real swap (lead → open →
  plug) and adds the two refusals. The old trace started with the lead
  already out.
* Whole-pass dry run (`--simulate`, s121 list): **the verdict columns are
  identical, row for row, before and after** (PASS 246; the one NO DATA is the
  mini-jack sense, which needs a matrix pack this desk lacks). The simulator's
  noise swap is now two moves, as it happens on the bench, where before the
  lead vanished the moment the prompt went up.

## 6. AS-ADC judges all three converters

`d24_selftest.py::t_asadc` scored U39 and U60 only and called U15 "known dead"
for every unit. It now scores **U15, U39 and U60**. A unit that really lacks a
group's front ends can say so in `/home/app/selftest/adc-exempt.conf` (one
ref per line); that converter is then reported and not scored, and the limit
text names the file. The default is no file, so nothing is exempt. A word in
the file that is not a converter ref gives NO DATA rather than being read as
"exempt nothing". Desk-tested on seven cases: all alive, U15 dead with and
without the file, U39 dead with U15 exempt, a typo, all exempt, and a scan
missing lanes.

**Not changed, and it is the hub's:** the catalog ITEM KEY is
`ADC AK5558 ×3 (U15 dead, U39, U60)`, and its limit/instruction text says
"U15's eight lanes are KNOWN DEAD". The key is what `ITEMS` matches the
workbook on, so renaming it here would orphan the row. The wording belongs to
the upstream catalog.

## 7. Limits

`detect_drop_db` stays **3.0 dB, provisional**. Its `source` text in
`MW/D24/DSP/s121/patch-limits.csv` now says it is read on node RMS, what the
swap rule is, the measured margins including MIC 6's, and that MIC 1–4/13–16
are unmeasured. That file is the generator's hand-tuned source: `patch-limits`
is copied from it and never written by it. `gen_patch_paths.py --check` is OK,
and a regeneration leaves every generated file byte-identical.

## 8. Deploy

PW's run was live when the desk work finished (see the block status for the
outcome). The deploy is gated on `systemctl is-active d24-factory` reading
inactive, with `.bak-s153-pre` backups of `d24_patch.py`, `d24_selftest.py`
and `s121/patch-limits.csv`, and an atomic rename. It aborted once, cleanly,
when PW pressed START between the check and the copy.

Outcome: the first attempt aborted cleanly; the watcher deployed at
13:37:18Z, and every file is md5-equal to the repo.

## 9. Hub addendum: the press page on a resumed pass

PW, 2026-09-30: on a resumed pass whose presses had all passed, the board's
standing page ("press the button that is lit") stayed up while only row 94's
temperature-sense listen ran. He twice looked for a light that was not
there, and then the run "jumped to audio".

* `d24_runall.panel_station` now works out whether any press step is owed on
  the board. If none is, it puts up "<BOARD>: every button already passed -
  nothing to press." (CHECKING, PAUSE only) instead of the press page.
* `d24_panel.sense_sweep` has a `quiet(row)` hook, called as an unasked phase
  starts. The station uses it to put up "<BOARD>: checking the temperature
  sense - nothing to press." On a fresh pass the last press page used to stand
  over that listen as well.
* `MW/D24/DSP/s153/panel_resume_check.py` drives the real station. On the
  pre-fix code it gives 4 FAIL; with the fix it passes, and the fresh-pass
  control still opens on the press page. S137, S138b and S145 all pass.
  Deployed 13:50:20Z with `.bak-s153-pre` rollbacks.
