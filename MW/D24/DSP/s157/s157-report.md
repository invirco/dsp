provenance: AI-drafted 2026-09-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S157 — patch-station detection: review and redesign

Design: `s157-design.md`, written before the code. Log table:
`factory-log-table.md` (from `factory_log_table.py`). Dry run:
`detector_dry_run.py` (+ `.out`).

## Tree state at dispatch, and what was done with it

HEAD carried S155's WIP ("tone rows on node RMS"). **I inherited it and
built on it.** Its direction was right: tone rows off the peak meter and
onto the node. Three changes on top:

- RMS became the **coherent** level, so noise can no longer arrive.
- S155's `_same_connection` / `hot0` gate is **removed**, together with its
  glass line, because no tone row has a removal edge any more.
- `where_is_it` became a steady-hint rule.

The unit ran `7c373481`'s `d24_patch.py` (md5 `62a4616c`) and HEAD's
`d24_live.py`, `d24_runall.py` and `d24_panel.py`. All four were md5'd and
diffed against the unit before the deploy.

## 1. Every run since the auto-advance landed

The full table is in `factory-log-table.md`: 278 prompts over 8 runs
(09-29 15:16Z → 09-30 18:04Z). **These are the "before" counts**, from the
same parser that will score the next pass:

| run | prompts | rises | drops | stalls | NO SIGNAL | wrong-socket claims | runner moved on by itself |
|---|---|---|---|---|---|---|---|
| 09-29 15:16 | 28 | 10 | 4 | 3 | 0 | 12 | 13 |
| 09-29 16:40 | 14 | 7 | 0 | 6 | 0 | 2 | 5 |
| 09-30 12:45 | 91 | 37 | 23 | 15 | 6 | 42 | 18 |
| 09-30 13:58 | 22 | 5 | 0 | 15 | 2 | 2 | 11 |
| 09-30 15:03 | 8 | 0 | 0 | 5 | 0 | 5 | 6 |
| 09-30 17:33 | 18 | 0 | 0 | 16 | 0 | 4 | 17 |
| 09-30 17:46 | 24 | 0 | 0 | 22 | 0 | 5 | 23 |
| 09-30 18:04 | 73 | 35 | 23 | 16 | 7 | 23 | 6 |

The parser reproduces the hub's counts for 16:40 (7 rises / 6 stalls) and
12:45 (37 / 15). For 18:04 it reads 16 stalls, not 12, because the log now
runs to the stop at ~19:35.

Causes, over every prompt that did not end in a clean graded PASS:

| cause | count | whose |
|---|---|---|
| runner: peak-latch (hot0 on an idle or draining lane; removal or rise never cleared the latch) | 60 | runner |
| runner: loop walk moved P1 on by itself (15:03, 17:33, 17:46: MIC 3, 4, 5 … with the lead still in MIC 1) | 47 | runner |
| wrong-socket claims that persisted (12:45 line block "MIC 5" ×5, 09-29 "MIC 7" ×4): a lead left in, or a latch — the log cannot tell which | 25 | undecidable |
| runner: wrong-socket claim on a patch that then arrived where it was asked for | 1 | runner |
| slow hands (timeout raised, then the lead arrived) | 1 | operator |
| arrived and graded FAIL / NO DATA | 3 | see below |
| noise step never detected, NO SIGNAL pressed (18:04 P25, MIC 8) | 1 | runner or margin |

**The unit accounts for at most three prompts, and none of them is the
stall.**

- 09-29 P8 MAIN R NO DATA: the booted-ON MAIN dynamics clamp, fixed in S154.
- 09-30 12:45 P68: a correct FAIL. The lead was in the XLR socket, not the
  jack centre.
- 09-30 18:04 P7 MAIN L → MIC 1: NO DATA, "−2.4 dB over its floor", after a
  peak-meter "rise" at 39.9 s. That is the instrument split in one row: the
  latch said something arrived and the node said no tone. The new detector
  cannot grade it that way. Whether MAIN L carried at that moment is a
  bench question (🔴 below).

Everything else is the runner.

## 2. The design

It is in `s157-design.md`, in short:

- Tone arrival = the node's coherent level ≥ `detect_rise_db` over the
  lane's own idle floor, for the stability window. Noise cannot pass it and
  the node has no history.
- The peak meter is a hint. It becomes a wrong-socket claim only when it is
  over the lane's own peak floor on two sweeps 1 s apart AND steady within
  1 dB. A draining latch loses 6.5 dB in that second, so it is never
  claimed.
- The removal edge exists only where the socket and the route both repeat:
  the 150 Ω step (S153's node plateaus, unchanged) and the hand retry of a
  graded fail. Both are on the node.
- Named states, and a log line at every transition:
  `P<n> PROMPTED / ARRIVING / ARRIVED / WAITING / WRONG_SOCKET / FAILED /
  NO SIGNAL / RETRY` with level, floor and instrument.

**A speed dependence in the 150 Ω step, found by the dry run and fixed.**
S153's plateau rule needed 256 ms of readings to call the lead "in" at the
prompt. A lead pulled within ~0.35 s of the prompt never formed that
plateau, so the swap showed one step and the plug could never arrive
(`--simulate --hand 1`: MIC 3–5 and 20–24 never arrived). The prompt's own
settled node reading is now the first plateau.

What is left is a physical floor: the socket has to be open for about
0.35 s (three node windows) between the lead coming out and the plug going
in. The whole-pass simulation passes all 246 readings at a hand time of
0.7, 0.8, 1, 3 and 10 s. It fails the 24 terminator steps at a hand time
of 0.5 s (0.25 s open), which no one can do with an XLR.

Cost: a tone-row poll is one node window (~85 ms plus the 50 ms poll)
instead of a 3 ms peek. An arrival is graded ~0.3–0.5 s after the plug.
Machine seconds for a whole simulated pass are unchanged at 116 s.

## 3. Never past a fail without the operator (every station)

- **Patch station.** A timeout, a wrong socket, or a graded FAIL / NO DATA /
  MISPATCH now stops on its FAILED screen with the failure named. It waits
  with no hard bound for LEADS CORRECT (record), RETRY (again from the
  prompt) or PAUSE. The detector keeps listening underneath, so a lead
  pushed home still arrives. After a graded fail, pulling the lead and
  plugging it again is also a retry.
- **Removed.** The 2×timeout give-up, `reprompt`, the NO DATA after
  `MAX_RETRIES`, `walked_past`, `repark` / `check_parks` / `parked_now`,
  and the loop walk's automatic move. The loop walk now moves to the next
  socket only after LEADS CORRECT, and logs and lists that confirmation.
- **Switch panels.** No key code, a wrong key, the wrong board, or no ack
  now stops on the step. YES records it, NO lights it again, PAUSE pauses.
  The encoder turn does the same.
- **Setup pages** are ENTER-confirmed already. **Background auto sets** have
  no operator step and are listed in the report, as before.
- **The end-of-run document.** Every confirmation is logged
  (`operator confirmed LEADS CORRECT on …`). A confirmed row is stored
  `judged=operator`, and its detail says the operator confirmed it.
- **RETRY.** The hub deployed it in the app (mx26 `1f2a7db`, `app` md5
  `409e52aa`). The FAILED screen offers `['nosignal', 'retry', 'pause']`
  and all three are drawn. `Live.command` reads `retry`.

## PW's other rulings

- **No parked leads.** Retired: `move_other_end`, `swap_for_plug`,
  `take_off`, `repark`, `move_input` / `move_output`, `park_kit_page`,
  `unpark`, `reparked`, `check_parks`, and the removal edge on tone rows.
  Every prompt is "Patch <out> to <in>." or "Fit the 150 ohm terminator in
  <in>.". The five kit setup pages are now one: "Put the four test leads
  and the 150 ohm plug on the bench." `hold_note` says "Keep the lead in…".
  The dry run proves that no screen, dialog or setup page says "other end",
  "stays", "park" or "leave the lead".
- **The walk is MIC 1–24 in order.** The list is untouched, and the
  `walked_past` skip is gone, so no input is skipped.
- **Row 94.** Every NO DATA sense row now holds one line on the glass for
  4 s: "The temperature sense: the panel firmware does not send it yet."
  The report keeps the full note, which says nothing was transmitted.
  **The H1S3 rebuild that would answer it is not scheduled anywhere in
  dsp `tasks.md`.** 🔴 below.

## 4. The dry run

`detector_dry_run.py`: 57 of 57 checks pass. Its simulator has a
draining peak latch, coherent-vs-noise separation, per-lane floors (MIC 1:
14 dB peak/RMS gap; MIC 15: −75.5 dBFS), a −54 dBFS gain-63 residual, and
leads left in. It proves:

- A fresh socket at 0.5 / 1 / 2 / 5 / 10 s: PASS, graded after the plug.
- Only the output end moved, at 0.3 / 1 / 5 s, with MIC 1's latch still
  full: PASS.
- Noise → tone with the residual on the lane and the plug at 1 s and 3 s:
  PASS at the plug.
- The 150 Ω swap with the lead pulled 0.2 s after the prompt and the plug
  in 0.5 / 1 / 5 s later: graded on the plug. Pulled with nothing fitted:
  never graded; it stops and waits.
- A wrong socket is named on the glass and passes once moved. A lead left
  in MIC 2 is named, and MIC 3 is not graded until it moves.
- Two draining latches (MIC 15, MIC 23) are never claimed.
- A dead output FAILs and stops. Nothing is recorded until LEADS CORRECT at
  95 s, and the screen carries all three buttons.
- Nobody for 125 s: no give-up, and the late lead still PASSES.
- RETRY re-prompts.
- A graded FAIL (a crossed TRS pair) stops. The lead out for 1 s is a
  retry. LEADS CORRECT records it, with the confirmation in the detail.
- The P1 loop walk does not move for 100 s and moves only after LEADS
  CORRECT.
- The panel loop stops on a timeout and on a wrong key: NO re-lights, YES
  records.
- Row 94's line is on the glass.
- The whole-pass forbidden-word check above.

Earlier suites, brought to the new rules where the ruling changed what
they assert:

| suite | result | what changed |
|---|---|---|
| S145 `patch_auto_advance_check` | green | "gives up at 2×timeout" became "never moves on by itself"; the S155 removal-edge test became "no tone row has a removal edge"; FAILED buttons include `retry` |
| S153 `noise_step_check` | green | the refusals are "still waiting at 42 s" |
| S155 `patch_glass_checks` | green | the hot0 / already-carrying checks became their S157 equivalents |
| S128 `glass_buttons_check` | green | — |
| S155 `measure_stall_check`, S153 `panel_resume_check`, S138b mj / shunt / click / sense, S138 power, S128 panel coverage, S137 panel buttons | green | unchanged (run with `MATRIX_ADDR_HOME` set to the s138b fixtures) |
| S138b `lamp_sweep_check` | 1 FAIL | fails identically at HEAD before this session ("the second input's screen says MOVE"); not this work |
| S127 `panel-on-glass.py` | error | `Args` has no `left_cell` (S129-era); predates this work |

`d24_runall.py --check-md` over every glass string: clean.

## 5. Deployed once, between runs (MW-D24-2, `d24-factory` inactive, nothing running)

Backup: `/home/app/backup-s157-pre/`, all four files exactly as the unit
ran them:

- `d24_patch.py` `62a4616c` (= `7c373481`)
- `d24_live.py` `950b43b2`
- `d24_runall.py` `ea21925d`
- `d24_panel.py` `81c58f3d`

Deployed, each byte-identical to this commit:

- `d24_patch.py` `86f0a78e`
- `d24_live.py` `ee9a3cd9`
- `d24_runall.py` `838e722d`
- `d24_panel.py` `f523142c`

All four compile on the unit. The unit's own `--simulate --hand 1` gives
246 PASS and 1 NO DATA (row 93: the sim has no sense hardware).

An earlier copy of `d24_patch.py` (`b36f436d`) sat on the unit for a few
minutes and was replaced by `86f0a78e` before anything ran. It lacked the
150 Ω fix above.

The patch list is untouched: `s121/patch-paths.csv` `54e96805` on both
sides. The runall `state.json` is untouched. The app is the hub's
`1f2a7db` (RETRY).

The "after" counts are owed by the next bench pass, from the same parser:
`python3 factory_log_table.py factory.log --since <that run's stamp>`.
