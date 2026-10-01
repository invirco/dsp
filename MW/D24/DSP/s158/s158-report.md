provenance: AI-drafted 2026-10-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S158 — the 150 ohm step: three runner faults, and the 150 ohm pass

MW-D24-2, 2026-10-01. PW: "test is failing at 150R tests, stop and fix", then
"maybe a key input is required for 150r" and "doing all 150r tests in a single
pass is way more efficient and easier to detect, let's build that in".

## What went wrong this morning (pass 2, runner S157 = `f87002c8`)

| step | what the log says | what it was |
|---|---|---|
| P13 MIC 1 terminator | PASS, plateaus `-52.1 -> -52.1 -> -76.5`, graded at -76.9 dBFS | **The open input was graded.** A wiggle of the tone lead made a second "lead in" plateau at the same level, so pulling the lead satisfied the two-step rule. MIC 1 open is -77.2, terminated -87.0 (measured twice today). |
| P15 MIC 2 terminator | the lead came out (-54.1 -> -75.3), nothing arrived, NO SIGNAL at 23 s | **The plug was in** (PW). MIC 2's terminated noise sits 1.8-2.0 dB under its open noise, and the rule wanted `detect_drop_db` = 3.0. |
| P16 AUX 1 -> MIC 3 | NO SIGNAL "after 0.7 s" | **A carried-over press.** `command.json` has no sequence number. A second LEADS CORRECT tap from P15, still in the file, was spent on P16's prompt. |
| P17 MIC 3 terminator | the lead came out (-50.8 -> -75.1), nothing arrived | Same as P15: a 1.8 dB step. In the S158 bench run the old rule did "arrive" on MIC 3, but only after 486 s, on slow drift and bumps. |

All four are reproduced on `f87002c8` in `terminator_pass_check.py` (cases 1a-1c) and shown gone on this tree.

## What the bench measured (PW at the glass, gain code 63, node RMS)

The trace is in `data/k5-trace-2026-10-01.csv`: every reading of 24 insertions, lead in, then out, then 150 ohm. `data/mic1-open-2026-10-01.csv` is 20 s of MIC 1 open with nothing fitted.

* **An open input is impulsive.** Over 20 s, MIC 1's single windows ran up to +5.7 dB over its median and down to -1.5 dB under it. Even a median of three still wanders 1.5 dB. That is why no single-reading rule is safe.
* **Every insertion makes a contact burst.** The plug going in reads 1-3 windows at +20 to +54 dB over the open input, on 20 of the 24 insertions. An open input left alone never jumped more than +5.7 dB.
* **Open to terminated, per input** (open / terminated dBFS, step):

| MIC | open | term | step | MIC | open | term | step |
|---|---|---|---|---|---|---|---|
| 1 | -77.4 | -87.0 | 9.6 | 13 | -79.0 | -94.0 | 15.0 |
| 2 | -75.0 | -78.1 | 3.2* | 14 | -81.2 | -93.1 | 11.9 |
| 3 | -76.4 | -79.2 | 2.8* | 15 | -76.9 | -92.7 | 15.8 |
| 4 | -75.8 | -78.8 | 3.0* | 16 | -81.9 | -93.7 | 11.7 |
| 5 | -79.2 | -87.3 | 8.2 | 17 | -81.6 | -87.3 | 5.7 |
| 6 | -79.6 | -85.0 | 5.4 | 18 | -81.7 | -91.9 | 10.2 |
| 7 | -79.6 | -83.0 | 3.5 | 19 | -81.4 | -89.0 | 7.7 |
| 8 | -79.3 | -85.1 | 5.8 | 20 | -78.3 | -83.0 | 4.7 |
| 9 | -81.0 | -87.2 | 6.1 | 21 | -81.5 | -87.5 | 6.0 |
| 10 | -80.8 | -90.4 | 9.6 | 22 | -81.5 | -89.2 | 7.7 |
| 11 | -79.7 | -86.1 | 6.4 | 23 | -81.1 | -91.0 | 9.9 |
| 12 | -76.3 | -90.1 | 13.7 | 24 | -73.9 | -90.9 | 17.0 |

\* MIC 2-4's terminated level kept falling slowly after the plug went in: MIC 2 went from -77.3 to -78.3 over a minute, and MIC 3 from -78.1 to -79.3. Just after insertion the step on those three is 1.8-2.7 dB. The table's "term" column is the level when the trace ended.

**Hardware finding for PW:** MIC 2, 3 and 4 terminate at -77..-79 dBFS. The other 21 inputs terminate at -83..-94. MIC 3 and 4 read the same on 2026-09-30 (-79.5 / -79.3). Those three preamps are about 10 dB noisier with a 150 ohm source, which is why their plug step is so small. The station still records them as PASS because no EIN window is ruled (`_score_noise`). The row's detail now carries the open and terminated levels side by side, so the next pass shows it.

## What changed

**The 150 ohm pass** (`gen_patch_paths.py`, PW 2026-10-01). The input walk is now AUX 1 -> MIC 1..24 (the seven gain steps each), then TALKBACK, then ONE terminator walked MIC 1 -> 24 (`P37`-`P60`, block "the 150 ohm pass"). The socket is empty when its prompt goes up, so the only event on that lane is the plug going in. `--terminator-each-input` brings the old order back for a timing run. The patch IDs after P12 renumber. RUN ALL folds results onto catalog rows, not patch IDs, and the walk re-runs every patch on every pass, so the paused run is unaffected.

**The arrival rule** (`d24_patch.py::_terminator_met`, constants `TERM_*`). The rule compares readings with the open input, never with a plateau history:

* The reference is the median of up to 20 readings before the last three. A transient at the prompt is outvoted, and slow drift is followed rather than taken for a plug. The reference freezes while the lane sits under it.
* The lane is judged on the median of the last three readings.
* The plug is in when that median settles 3.0 dB (`detect_drop_db`) under the open input, **or** 1.0 dB under it within 3 s of an insertion burst (one window 10 dB or more over the open input). The second branch is what MIC 2-4 need.
* The unchanged stability window then grades it.

**ENTER is on every 150 ohm screen** (`Live.wait_buttons`, `LV.TERMINATOR_BUTTONS`) and always ends the step. That is PW's key input; the app already draws ENTER. The step never puts up a red screen. After `detect_timeout_s` the status reads "Nothing seen at MIC n yet. If the terminator is in, press ENTER."

If the tone lead was in that socket at the prompt (the old order), the step is ENTER only. An ENTER while the lane still reads like the lead is asked once more ("still reads as if the tone lead is in"), and a second ENTER measures it.

**A press answers the screen it was pressed on** (`Live.command`). `live.json` now carries `screen`, which counts the screens that ask something (a new instruction or new buttons). If a command carries `screen`, it must match. If it doesn't (today's app), its `stamp` must not be older than the screen now up. PAUSE and EXIT are never dropped.

**One runner per unit** (`cmd_run`). The lock was per `--dir`, so a bench run into a scratch dir ran BESIDE a RUN ALL the glass had started (11:15, see below). The factory glass directory's lock is now taken too, and a run holding it refuses the newcomer.

**Smaller items.**

* The first patch of a run waits twice `detect_timeout_s` before its red screen. P1 timed out at 20 s and arrived at 22.6 s; the operator had just come off the setup pages.
* A graded fail's action line now says the signal arrived and the measurement is out of limits. PW had read P12's gain-step fail as "not detected".
* `--block K5` now selects the K5 patches inside the input block. Before, it matched nothing.
* `--verbose` logs every reading a noise step takes (`TRACE`), with the open reference and the insertion time.

## P12, the gain step (addendum 2, item 4)

* **Tolerance in force:** `gain_step_tol_db` = 0.25 dB (PW ruling 2026-09-27).
* **Expected values:** `defs/common/tables/mic-gain-codes.csv`, the median over 15 channels of the 2026-09-16 survey on this unit (J29 / MIC 7 excluded). MIC 1-4 were not powered for that survey, so MIC 1 is judged against the other channels' median. The survey's channel spread on code 8 is 0.037 dB.
* **MIC 1 element 4** read +34.39 dB and +34.38 dB on the two earlier passes in this log, and +34.63 dB today. The same channel moved 0.25 dB between runs, so this is run-to-run repeatability of a reading taken about 300 ms after the drive change, not a stable element fault and not per-channel spread. Over all 43 element-4 readings in the log, the median error is +0.07 dB and 5 exceed 0.25 dB. RETRY measures it again; a repeat would settle MIC 1.
* **P1 timeout:** 20 s was too short for the first patch of a pass; it now gets 40 s (see above).

## Proof

* `s158/terminator_pass_check.py`: all checks pass (`terminator_pass_check.out`):
  * the three faults reproduced on `f87002c8` and gone here;
  * **24/24 real insertions graded on the plug, median 0.96 s after it, worst 1.55 s**;
  * a minute of MIC 1 open is never graded;
  * **S153's physical model in the pass shape: 48/48 graded on the plug, median 0.67 s, worst 1.06 s** (S153 recorded 48/48 at 0.54 s in the old shape);
  * the old shape is ENTER only;
  * presses and the lock behave as described.
* Regression, all passing:
  * S145 `patch_auto_advance_check.py`: the noise section is rewritten to the new rule, and its whole-pass screen check now allows ENTER on the 150 ohm screens only.
  * S157 `detector_dry_run.py`: patch IDs renumbered, and the terminator case is now the pass shape.
  * S153 `noise_step_check.py`: its "after" side is pinned to `f87002c8`, the last tree with its rule.
  * S155 `patch_glass_checks.py`, S128 and S137 glass-button checks, S138/S138b, S153 panel resume.
* `s138b/lamp_sweep_check.py` fails one check ("the second input's screen says MOVE"), identically on clean HEAD. That failure predates this session.
* Deployed to MW-D24-2: `d24_patch.py` f2f0b4e1, `d24_live.py` 4a6da548, `s121/patch-paths.csv` ef7817a1, `s121/patch-plan.md` 2c76994c (backup `/home/app/backup-s158-pre`). A `--simulate` pass on the unit ran clean in the new order, projected at 9.6 min.

## The bench session, honestly

My first `--block K5` run found no patches and ended on FINISHED, which carries START. PW pressed it, which launched RUN ALL (11:14). My second K5 launch collided with RUN ALL's DSP boot and died in its floors. I paused RUN ALL.

PW pressed START again (11:15:34). My third launch missed the new run in its check and ran beside it for about a minute. Its teardown lowered AN_EN and restored the processing cells under RUN ALL. I put GPIO26 back to `op dh`. RUN ALL's patch station started after that teardown, read the original cells and re-bypassed them, so its readings were not affected.

PW asked to stop the aux re-test and do the 150 ohm only. I paused RUN ALL (pass 3: 78 PASS / 4 FAIL / 14 NO DATA / 73 not tested) and ran the K5 trace from a scratch copy, with the glass cleared at the end. The unit-wide lock above is the fix for this.
