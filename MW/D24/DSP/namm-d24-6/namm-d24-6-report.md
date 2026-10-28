provenance: AI-drafted 2026-10-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# NAMM-D24-6 — D24 rev C board test: the factory runner as a per-board tester

Review stop. Desk only: nothing deployed, nothing flashed, MW-D24-2 not contacted.

## 1. What the runner does today (audit, 10-03 state + S170-S176)

- **One runner.** `tools/pi/d24_runall.py` is RUN ALL. The glass START (`d24-testui` → `d24_patch.py --run`) runs it with no arguments. The auto set is shelled out once per pass to `d24_selftest.py --only …`, in three phases: serial, then DSP, then network. Operator work runs under those phases: setup pages, then the left/right panel loops (M1/M2), then the analog patch station (M4).
- **Rules already in it.** The factory screen shows one big instruction with "n of N" and a PAUSE button, and nothing else (S126/S128). Panels are named, not J numbers (`Row.panel`, `NAMES`, the `--check-md` vocabulary grep). A resume runs only untested rows: `State.settled` (S163) leaves FAILs recorded and not re-run unless RE-TEST FAILED is asked for. A pass never moves past a FAIL without the operator confirming it (S157: NO SIGNAL / LEADS CORRECT). Every row gets a line in the report, never silently dropped (S117 §1). KNOWN_ABSENT and NOT RUN reasons are per row (S163, `classify`).
- **The catalog** on the unit is 202 rows (md5 `f380c70d7ba5`, copy in `MW/D24/DSP/s164/data/`). The runner classifies it into 34 auto, 91 manual (panel loop + patch), 3 background and 74 not run.
- **Desk regression, before this work:** 16 of 17 checks pass. `s138b/lamp_sweep_check` fails, as it did before S163; that failure is unchanged and untouched here.
- **Bench state:** the last runner deploy was S164 (10-01). The S175 change (`boot_pair` sends CFG_BOARD_REV from detector J) is in the repo but **not deployed**, and its bench proof (S175 step 3) is still owed.

## 2. Board profiles and the operator flow

The catalog's `board` column cannot say on its own which rows a board owns. It files parts under "Assemblies" and "Inter-board links". So the profiles are a table in `tools/pi/d24_boards.py`, built from `MW/D24/HW/hardware-map.md`. Each row has a role:

- **home:** the part is on this board.
- **link:** the row tests a connection that crosses this board.
- **carrier:** the row is run only to grade another row.

| profile | board | rows | what the operator does |
|---|---|---|---|
| `dsp` | DSP card | 45 | nothing: automatic set only (28 rows), no leads |
| `digital` | Digital board | 68 | network lead, two USB sticks in the top panel; 29 automatic + 3 background |
| `analog` | Analog board | 69 | the full analog station (93 patches, all 24 inputs) + USB sticks |
| `phonejack` | Phone Jack board | 6 | 5 jack patches (Aux Out A 1-8 TRS, Phones 1) |
| `left` | Left switch panel | 17 | the left panel loop (12 rows) + AL1 mic/speaker |
| `right` | Right switch panel | 40 | the right panel loop (33 rows) + 2 mini-jack patches for the jack-sense row |
| `p1` | P1 foot pedal | 7 | nothing runnable today (see §5) |

Every one of the 202 catalog rows is in at least one profile; the desk check enforces this. The full per-row table is generated: `coverage.md`, by `coverage.py`.

**Flow (as built).**

1. Fit the new board in MW-D24-2.
2. At the desk: `tools/accept/board_test.py start <profile> <label ID> [--rev C]`. This writes `/home/app/selftest/board.conf` and nothing else. It refuses while another board's session is open or a run is going.
3. At the unit: press START on the glass. It is the ordinary factory screen and the ordinary ruled flow, cut down to that board's rows. The setup pages ask only for what those rows use: the DSP card and panel boards get none; the Digital board gets the network lead and the USB sticks.
4. PAUSE / START resumes that board's untested rows only.
5. `board_test.py fetch` copies the board's report off the unit and writes `tools/accept/results/<ID>/<ID>-<profile>-<stamp>.csv`. That file has one line per profile row: verdict, reading, limit, who judged, role.
6. `board_test.py end` closes the session. START is then a whole-unit pass again.

The verdicts are keyed on the board's ID (`runall/boards/<ID>/state.json`), so a board can go to rework and come back to its own untested rows. The unit's whole-unit state is never touched. **Board ID** = FIX-L2: 7 Crockford base32 characters + a Luhn mod 32 check character. It is typed for now; lower case, O→0, I/L→1 and the hyphen are accepted. A mistyped character is refused before anything runs.

## 3. What changed (3 commits)

| commit | what |
|---|---|
| `b3e8534f` | `d24_boards.py` (profiles, ID check, board.conf); `d24_runall.py` board session (`--board/--board-id/--board-conf`, scoped rows, per-board state and report, setup pages filtered, power check only on the Digital board, refuses to boot the pair for a board with nothing runnable); `d24_patch.Station(rowless=…)`: outside the analog board the station walks only the patches that feed the board's own rows (without it, the right panel's jack-sense test walked 53 patches); `board_test.py`; deploy list gains `d24_boards.py` |
| `575bae8b` | **pre-existing runner bug fixed:** `run_manual` returned before it started the network phase, so any pass with no analog patch owed never ran NW1-4, HD0-1, HD-PWR, AS-CM4 or the USB checks. That covers a whole-unit resume after the analog station finished, and every Digital board pass. Those rows stayed owed for ever. Found by a stubbed desk pass of the Digital profile |
| (this) | coverage table, report |

**Desk proof.**

- `board_test_check.py`: 39 of 39 pass, with no unit. It covers profiles vs catalog, board.conf, ID refusal, the pedal stop, the whole-unit pass unchanged at 202 rows with no board block, setup pages, the station scope for the right panel and the phone jack board, the result file, and stubbed factory-order passes of the DSP card and Digital profiles.
- `d24_boards.py --self-test`: 12 of 12 pass, including every single-character error on the ID being caught.
- Regression: 17 of 18 pass. The one failure is `lamp_sweep`, the same as before this work. Record: `regression.out`.

## 4. Coverage

| board | rows | auto | panel loop | analog patches | background | not run |
|---|---|---|---|---|---|---|
| DSP card | 45 | 28 | 0 | 0 | 0 | 17 |
| Digital board | 68 | 29 | 0 | 0 | 3 | 36 |
| Analog board | 69 | 8 | 0 | 46 | 2 | 13 |
| Phone Jack board | 6 | 0 | 0 | 6 | 0 | 0 |
| Left switch panel | 17 | 3 | 12 | 0 | 0 | 2 |
| Right switch panel | 40 | 2 | 33 | 3 | 0 | 2 |
| P1 foot pedal | 7 | 0 | 0 | 0 | 0 | 7 |

The Mini Jack and HDMI FPC boards have no label (PW 2026-10-26), so they have no profile. Their rows sit in the Analog and Digital profiles.

## 5. Rows with no test (listed, not invented)

**DSP card**
- PSU monitor ADC PAD0-11, rows 113-124: no test is written.
- J1-J6, rows 164-168: assembler QC; already covered by automatic tests.
- No catalog row exists for:
  - the card revision (`dspcard_id` / `Sys001DspCardRev001`);
  - the IC1 inter-chip gate;
  - S176's `DIAG_IDCODE`.

**Digital board**
- Power switch, row 134: asked only on the wizard. The factory screen draws no dialogs (S161).
- Pedal socket and pedal link, rows 129 and 145: the pedal fixture is not built.
- analog-12v link, row 150.
- HDMI 1, row 132: not fitted.
- Option slots, d32compat and fan, rows 135-138, 149 and 152: no card exists.
- Headers, rows 169-192:
  - 3 are covered by automatic tests;
  - 14 are assembler QC;
  - 7 have no test.
- No catalog row exists for the touch panel USB (USB-TP) or the internal hub (USB-HUB).
- NW4 throughput cannot be graded on this bench: the link is 100 Mb/s.

**Analog board**
- Centre/LF out, row 35: there is no cell for it; aux 9-12 are masked off in firmware (S151).
- analog-12v link, row 150.
- Headers, rows 153-163: 2 are assembler QC, 9 have no test.
- Output headroom: the -20 dB pad lead K6 is listed as owed (S164), and no station step uses it yet.

**Left switch panel**
- BOOT0 red LED, row 55: the host cannot light it.
- Pedal UART through-path, row 58: needs the pedal.

**Right switch panel**
- C red LED, row 78: no indicator is declared for it.
- **Talkback switch and LEDs, row 92:** the `Sys001SwTalk001` read/light logic is not wired. It needs S135's optional H1S3 image.

**P1 foot pedal**
- Rows 98-101, plus links 129 and 145: there is no fixture, and no host read of the footswitches or display.
- The pedal does answer over its cable (S167/S170: the relay, the ROM, `d24_pedal.py update`), so a link test is possible but not written.

## 6. What PW needs at the bench

**For every board**
- MW-D24-2 back from fixture work, with every other board known-good.
- This machine on the bench network (`app@192.168.1.219`).
- The unit's `list.conf` left as it is: the short list, which matches the harness's own analog board (U15 front end not fitted).

**DSP card**
- New, blank boards must be programmed before the test, and each step is a flash, so each needs the hub's go:
  1. MH1 (U8) over SWD, mux channel 3;
  2. H1S1 (U7) by `h1s1_flash.sh`;
  3. the CPLD by `logic_flash.sh`.
- Both flash scripts run the `dspcard_id` guard. On a virgin card that guard rests on detector J, which is **not yet proven on silicon (S175-4)**.
- The SHARC pair is RAM-booted by the runner.

**Digital board**
- Move the CM4 module from the harness board (it carries the OS and the test tools).
- The display with its HDMI FPC, the touch panel, the network lead and two USB sticks.
- A blank U34 power MCU is programmed **over SWD only**: the F030x4 has no empty-flash check (2026-10-15 report §5).
- Open question: whether a rev C board with a blank U34 brings the CM4 up at all.

**Analog board**
- The five-lead kit:
  - K1: XLR-F to XLR-M;
  - K2: 6.35 mm TRS to XLR-M;
  - K3: XLR-F to 3.5 mm TRS;
  - K4: XLR-F to 6.35 mm TRS;
  - K5: the 150 ohm terminator.
- Two USB sticks.
- K6, the -20 dB pad, only if output headroom is wanted. No step uses it yet.
- No external signal source: the unit drives its own outputs into its inputs.
- `/home/app/selftest/adc-exempt.conf` must be absent or empty, so that U15 is scored on the new board.

**Phone Jack board**
- K2 only. On the unit's short list (`list.conf`) the jack patches land on MIC 8, which is live on the harness.

**Left and right switch panels**
- A finger and an eye.
- Blank H1S4/H1S3 are programmed by `app cli loadfw` through MH1 and the panel BOOT0 line.

**P1 pedal**
- Nothing yet. If a link test is wanted, it needs the pedal, its RJ45 lead and the relay path.

## 7. Bench plan (for the hub's window; not started)

1. S175 step 3, read-only, on MW-D24-2's own DSP card. This is the J proof that virgin DSP cards depend on.
2. Deploy: run `deploy-bench-tools.sh --check`, then deploy with backups first. This carries `d24_boards.py`, the runner, and S175's `boot_pair` change.
3. **Reference passes on the harness's own boards:** `dsp`, `digital`, `left`, `right` and `phonejack`, under a dummy label ID per board. This proves the harness and the runner path before a new board is blamed. About 15 minutes without `analog`.
4. New rev C boards one at a time: program if blank (hub go), then `start`, START, `fetch`, `end`.

## 8. Questions for PW (one at a time, recommendation first)

1. **Bench window order.** **Rec (a):** one window that runs §7 steps 1-3 (J proof, deploy, reference passes), then new boards. (b) Skip the reference passes and go straight to new boards.
2. **Programming blank new boards.** Each is a flash. **Rec (a):** a standing go, for the board-test window only, to program NEW boards (never the harness's own) with the repo's recorded images (md5s in the `MW/D24/FW/*/README` files and `shared/dsp4-logic/bitstream/`). (b) A go per board.
3. **DSP card and Digital board have no analog patch.** The automatic converter tests prove each lane is alive and not stuck, but not the level per channel. **Rec (a):** add a short "one patch per converter lane" list (3 ADC lanes + 2 DAC lanes, about 5 patches with K1) to both profiles. It is generated by `gen_patch_paths.py`, desk-first. (b) Leave them automatic-only.
4. **Right panel jack-sense (row 93).** **Rec (a), as built:** the right board's test carries the two mini-jack patches (one K3 lead), so the sense line is graded on the right board. (b) Leave row 93 to the Analog board test.
5. **Board ID entry.** **Rec (a), as built:** typed at the desk in `board_test.py start`. (b) A keypad on the glass, which needs mx26 app work. (c) Wait for the FIX-L2 scanner station.
6. **Missing tests worth writing before NAMM.** **Rec (a):** the talkback switch and LEDs (row 92, a show-floor feature) and a P1 link check over the cable (rows 101/129/145). Both are small and desk-first. The PSU ADC rows (113-124) wait. (b) None before NAMM.
