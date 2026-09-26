provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S117 — RUN ALL: one START, the automatic set pipelined, the operator set stepped, one report

Hub dispatch `tasks.md` 2026-09-26 13:17Z. Built on S113 (the order and the
groups), S114 (the compacted runners), S115 (bandpass THD and the silent
handback) and S116 (the five PW rulings).

PW's bar for this dispatch was the **simplest, fastest, most efficient** test
suite: fewest operator actions, least wall time, least code. Every choice below
is argued against that bar, and the two places where the honest answer cost
something are said out loud rather than papered over.

---

## 1. What was built, and where the decisions live

**One new file does all of it: `tools/pi/d24_runall.py` (1 300 lines).** The
on-glass wizard is a thin client. One press launches the script in a transient
systemd unit of its own; the script pipelines the automatic set, steps the
operator through the manual set, writes the report, and puts the review screen
up. The app does exactly three things:

* tails `runall/progress.txt` for the one progress line,
* draws whatever `runall/prompt.json` asks for, and
* writes the button that was pressed to `runall/answer.json`.

That split is the "least code" answer. The category split, the station order,
the rails rule, IGNORE, the pass arithmetic and the report all live in Python,
where they can be read and run on a desk with no unit; the C# side has no
opinion that could drift out of step with them. It also means the dialogs are
**slots, not fixed buttons**: a prompt names the buttons it offers, in order,
and six `ACT1..ACT6` controls take their labels from that list. A new kind of
dialog needs no skin change and no C# change.

**The automatic set is not reimplemented.** The auto phase shells out to
`d24_selftest.py` exactly once per pass, with `--only <the owed test ids>`, in
the catalog's own `group`/`order`. That runner already stops the mixer once,
stages once, boots the pair once and raises the rails once (S116 Q4); driving it
row by row would pay all of that per row. The verdicts are read back out of the
results CSV it appends to — the same file the glass rolls up from — so the
report and the glass cannot disagree.

### Files

| file | what |
|---|---|
| `tools/pi/d24_runall.py` | NEW. RUN ALL: categories, pipelining, station stepping, IGNORE, passes, the report, `--check-md` |
| mx26 `src/sw/app/Core/TestSkinStore.RunAll.cs` | NEW. The thin client: launch, poll, draw, answer |
| mx26 `src/sw/app/Core/TestSkinStore.cs` | partial; `covers`/`group`/`order` read; partner-row stamping; `--no-soak-wait` dropped; the body yields to a dialog |
| mx26 `src/sw/app/Controls/MixerControl.cs` | `STARTALL` and the six `ACT` slots on the existing `TESTACT` path |
| mx26 `tools/d24/build-d24-test-skin.py` | the dialog band, the six slots, `START ALL` beside `START TEST` |
| `MW/D24/DSP/s117/manual-dialogs.csv` | every manual dialog's text, generated — **this is the list for PW to review** |
| `MW/D24/DSP/s117/s117-tap-through.py` | the session's own hands: answers the wizard through the real touch device |

---

## 2. The shape, against the dispatch's six numbered points

### (1) Category

From the catalog's `automation` column — `1` is AUTO, any of 2/3/4 is MANUAL —
cross-checked against `group`, which is what RUN ALL actually orders by. The
cross-check prints a warning per disagreement rather than picking silently;
there is exactly one today (§5, finding S117-2).

Today's catalog splits **34 automatic, 77 operator-stepped, 91 not run**. Every
one of the 202 rows appears in the report exactly once, and every NOT RUN row
carries its reason.

### (2) START ALL

Beside the per-row START, which stays. It runs the owed automatic rows in
`group`/`order` (A1→A5) with no stops; verdicts land on the glass as they come
because the runner appends to `item-status.csv` as it goes and the store already
polls that file every 2 s. One progress line, in the place the per-row progress
text already had: group, plain-English test name, seconds gone, seconds left.
The "left" figure comes from a measured cost table (S116's 13:08:13Z full run,
per-test deltas), not an estimate.

### (3) Manual stepping

Station order is S113's M1…M7 with the **analog stations moved to the end** so
the rails go up once and late (S116 Q4 / PW 09-10: analog last up, first down):
switch panels, pedal, rear sockets, then analog loopback, then the meter
station. M6 (the expansion card that does not exist) and M8 (no bench time) are
not stations at all.

A **station card** first — what the operator needs in hand for the whole
station, and, for an analog station, that the supplies are live — acknowledged
once. Then one dialog per owed row, in panel names, never a firmware table name:
the catalog's `item` is the workbook's own string and carries `(fw.csv MonoAux)`
style brackets, which are stripped. One action per dialog, then either
`Done` (the runner measures) or `Yes / No` worded so **Yes is a pass** (only a
person can say). Every dialog also carries `Back`, `Skip`, `Ignore` and `Pause`
— six buttons, which is exactly the width of the glass, and the runner refuses
to build a dialog with a seventh.

`Back` re-does the previous step. `Pause` stops the pass where it is; the step
is in the state file, so the next START resumes there **through an app restart
and a power cycle**.

### (4) One complete report

Written at the end of every pass, as a pair on the unit:
`/home/app/selftest/reports/<serial>-<stamp>.md` and `.json`.

The `.md` is the human page: a summary tile (pass / fail / no data / ignored /
skipped / not tested / no verdict, wall time, automatic time, operator time),
then every check that is **not** a pass with FAILs first, then the passes, then
the set-asides, then the history. Per row: number, plain-English name, result,
reading, limit, **who judged it** (the unit or the operator), which pass
produced it, and what to do. It carries no Matrix-internal vocabulary — no test
id, no cell name, no firmware table name, no run-group code — and
`d24_runall.py --check-md` is the grep that proves it (§6).

The `.json` twin carries all of it: test ids, the serial, the catalog md5, the
factory image name and its build-configuration triple, and every row's raw
evidence.

The **scrollable on-glass list of non-PASS rows** the dispatch asks for is the
wizard's existing `QUEUE: EVERY UNPASSED` walk, not a new widget: PREV/NEXT step
it, the row page is the expansion, and DETAIL is the long form. That is the same
information for no new code, which is what "simplest" meant here. Said out loud
because it is a choice, not an oversight.

### (5) Review, then the next pass

After the report, a REVIEW screen. It is a **walk, not a list with checkboxes**,
and that is deliberate: the glass has no row picker, building one would have
been the only new widget in the whole change, and a walk costs the operator
nothing when they have nothing to set aside — the first review screen already
carries `START NEXT PASS`, so one press starts the next pass. Walking is only
paid by an operator who is actually setting rows aside: one press per row they
step past, two per row they set aside.

`START NEXT PASS` runs only what is **owed** — no PASS yet, not IGNORED, and
something exists to run for it. A row that has passed is never re-run. Each pass
is numbered; the report is regenerated after every pass as the unit's cumulative
state, with each row's final verdict, the pass that produced it, and the earlier
verdicts kept as history.

### (6) IGNORE

On any row or dialog, one press then a reason from the pick-list (awaiting part
/ known rev-C erratum / fixture not built / other). Written to
`/home/app/selftest/ignored.csv` against the unit's own serial with the catalog
md5 it was taken against, and it **expires** when that md5 moves — a row whose
runner or limits changed is exactly the case where last week's "ignore this" is
no longer a statement anybody made. Expired ignores are listed in the report and
count as owed again. `--unignore N` takes it back and restores the row's
previous verdict. An ignore is never a PASS; the report says in bold that the
unit cannot be signed off while any are outstanding.

---

## 3. What a manual row actually becomes, and the one thing that cost honesty

Every manual row is turned into a step by a small table keyed on the catalog's
`class` and `group`. There are four kinds:

| kind | what it is | what the report records |
|---|---|---|
| **measure** | the operator sets it up, the runner takes the reading | the reading, judged by the unit |
| **judge** | only a person can say; the question is worded so Yes = pass | the answer, judged by the operator |
| **fixture** | the check is real, the thing it needs is not at the bench | the station is still visited; SKIPPED with a reason |
| **blocked** | there is no check to run: no host capability and nothing a person can judge | NOT RUN, with the missing piece named |

Today's catalog lands like this:

| station | rows | measure | judge | fixture | blocked / not run |
|---|---|---|---|---|---|
| 1 Left switch panel | 14 | – | – | – | **14** |
| 2 Right switch panel | 36 | – | – | – | **36** |
| 3 Foot pedal | 6 | – | – | 3 | 3 |
| 4 Rear panel sockets | 5 | 2 | 1 | – | 2 |
| 5 Analog loopback | 48 | – | – | 48 | – |
| 6 Meter checks, lid off | 24 | – | 23 | – | 1 |

**The dialog text is NOT built from the catalog's own prose, and that is a
finding, not a preference.** `pass_when` and `short` are misaligned by one row
from row 128 upward (§5, finding S117-1): row 133, the mains inlet, carries the
second screen socket's criterion; row 134, the power switch, carries the
inlet's; row 198, the input converters, carries the output converters'.
Generating an instruction from that text would put the wrong instruction in
front of an operator. The step table is therefore built from the columns that
are reliable — `board`, `item`, `class`, `group` — and the generated wording is
in `manual-dialogs.csv` for PW to read in one place.

**The 50 switch-panel rows are the price, and they are not hidden.** Stations 1
and 2 have no runnable row today, so they are not visited and their 50 rows
appear in the report as *not tested — the host cannot see this control or sense
line change: this unit has no per-control read through the panel processors* and
*— the host cannot light one indicator at a time: this unit has no indicator
drive for the panel processors*. That is what the catalog itself already says
("Needs a press: work the panel control while the host tails the UART. Not built
yet"), and the wiring backs it: of the panel switches in the D24 firmware table
only `FxMute` declares a matrix cell at all, so even a bus listener could not
say WHICH control moved. Nothing was invented to fill the gap. **See the 🔴
question to PW in §8 — one ruling turns all 50 into gradeable rows.**

---

## 4. The run, on MW-D24-2

### 4.1 The automatic set, from a real touch on the glass

`START ALL` is the second footer button: **400 × 100 at (456, 920), centre
(656, 970)**. The six dialog slots are **295 × 68 at y = 844, the first at
x = 40, pitch 307 — centres (187 / 494 / 801 / 1108 / 1415 / 1722, 878)**. Every
press in this session went in through `d24_touch_inject.py --serve /tmp/tap` on
`/dev/uinput`, created before `d24-testui` was restarted (Avalonia's DRM backend
enumerates input once, at startup) — a real input device through libinput to the
control under the point. It is not a test of the panel's own ILITEK controller.

    14:46:53.890  TESTSKIN: press TESTACT 'STARTALL' at 456,920
    14:46:53.975  TestSkinStore: RUN ALL started at 14:46:53 in d24-runall.service

One press, then nothing until the automatic set was done: **39 tests over 34
rows in 210 s**, against S113's 435 s prediction and S116's measured 210.4 s —
the same, which is the point: RUN ALL adds no cost to the set it drives.

### 4.2 The operator set, walked end to end

The session has no hands at the bench, so every dialog was answered through the
real touch device by `s117-tap-through.py`, which watches `prompt.json`, picks
the slot and taps it. It waits 3 s after a prompt appears before tapping,
because the first attempt did not: **ACT1 pressed at 14:50:24.82, the store
loaded the dialog at 14:50:25.55** — the robot was faster than the app's 2 s
poll and the press fell on a page that had not drawn the dialog yet. A finger
cannot be that fast; the wait is what makes the robot as slow as a person.

Stations 1 and 2 have no runnable row, so the walk was stations 3, 4, 5, 6.
Every station was reached, its card acknowledged, its first dialog shown, and —
where the fixture is not at this bench — skipped with a reason:

| step | what happened |
|---|---|
| Station 3 card | acknowledged; checks 101, 129, 145 skipped, *fixture not built* |
| Station 4 card | acknowledged; **checks 130 and 131 MEASURED** — `Done`, then the unit looked: *nothing on port 3* / *nothing on port 4*, NO DATA, judged by the unit. Check 133 skipped, *other* (the session cannot see the rear panel) |
| **Back** | pressed on 133 → the walk returned to 131, which was answered again, then 133 came round again. Proven in the log: `[7] … 133 -> back`, `[8] … 131 -> done`, `[9] … 133 -> skip` |
| **Pause** | pressed on the first check of station 5 → the runner saved the step and exited; `d24-runall` inactive, state `{"phase":"manual","step":6,"row":1,"pass":1}` |
| **App restart** | `d24-testui` restarted with the run paused. START ALL came back reading **`RESUME: CHECK 1`**, read off the runner's own state file (`s117-resume-after-restart.png`) |
| Resume | one press; the walk carried on at station 5, check 1 |
| Station 5 card | acknowledged; 48 checks skipped, *fixture not built* |
| Station 6 card | acknowledged; 23 checks skipped, *fixture not built* |

**Pass 1: 18 PASS / 2 FAIL / 16 NO DATA / 75 skipped / 91 not tested, 202 rows,
463 s** (210 s automatic, the rest the operator set at a robot's ~6 s a step).

### 4.3 The review, IGNORE, and the next pass

The review screen came up on its own after the report: *Review — pass 1 done —
1 of 93 owed*, with `START NEXT PASS` in the green slot.

**IGNORE, through the glass:** `IGNORE` then `AWAITING PART` on check 1. The
owed count went 93 → 92 in the same second and `ignored.csv` gained

    serial,num,reason,catalog_md5,stamp
    10000000830b03af,1,awaiting part,96694c1357912229ad6e5b4feaf33884,2026-09-26T14:03:08Z

with the state reading `row 1: IGNORED, set aside: awaiting part`. The md5 is
the catalog the ignore was taken against, which is what expires it.

**No redundant tests, measured:**

| pass | tests asked for | rows owed | automatic seconds |
|---|---|---|---|
| 1 | 39 | 34 | 210 |
| 2 | **22** | **16** | **179** |

Pass 2's `--only` list has no `HD0-1`, no `AS-CM4`, no `HD-PWR`, no `MC1/2/3`,
no `DR1/DR2`, no `DY1`, no `DC1/DC2-CS1/CS2`, no `AS-DSPA/B` and no `AS-ADC` —
every row that passed in pass 1 was left alone. The rows still asked for are the
ones that did not pass: the network counters, the main control processor link,
the panel links (whose rows also declare the reprogramming-line check, which is
a permanent NO DATA), the three selects that reach nothing, the clock master,
the power processor, the output converters and the acoustic loop.

---

## 5. Findings

### S117-1 🔴 The catalog's PASS criterion is one row out of step, from row 128 to row 202

`pass_when` on row *N* carries the criterion of row *N−1*, for 75 consecutive
rows. It is not a handful of rows and it is not new — S116 found the same shift
on rows 127/203, fixed those two by hand and left the rest flagged rather than
guessed at. Read across the catalog it is unmistakable:

| row | what the row IS | whose criterion its `pass_when` carries |
|---|---|---|
| 128 | the network socket | the screen link (127) |
| 129 | the foot pedal socket | the network (128) |
| 130 | a rear USB socket | the pedal (129) |
| 133 | the mains inlet | the second screen socket (132) |
| 134 | the power switch | the mains inlet (133) |
| 140 | the audio processor B link | the audio processor A check (139) |
| 197 | the output converters | the clock master (196) |
| 198 | the input converters | the output converters (197) |
| 199 | the talkback converter | the input converters (198) |
| 202 | the main control processor | the dispatch processor (201) |

This matters three ways. The wizard's DETAIL page shows **PASS WHEN** straight
out of this column, so 75 rows currently tell a technician the wrong criterion.
An INSTRUCT dialog generated from it would tell an operator to do the wrong
thing — which is why S117's dialog text is built from `board` / `item` /
`class` / `group` instead, and why `manual-dialogs.csv` exists for PW to read.
And it means no manual row has a usable numeric limit today: the meter station's
question is therefore "does it read what the build sheet gives for it?", with
the build sheet as the authority, until the catalog carries limits that belong
to their own rows.

The fix is in the hub's generator (`mx26 tools/d24/build-d24-test-skin.py`,
`scrape_spec` / `build_catalog`), not here: this repo consumes the catalog.

### S117-2 🟡 One row's automation column disagrees with its group

Row 148 (the screen link ribbon) is `automation 1` — automatic — and sits in the
analog loopback station. RUN ALL orders by `group`, so it is stepped as an
operator check and says so on every run (`catalog warning: #148: automation '1'
but group 'M4'`). One of the two columns is wrong; the generator owns both.

### S117-3 🔴 The acoustic loop's NO SOUND today is the pinned MAIN bus, not the speaker

Every acoustic-loop press in the two RUN ALL passes read

    NO SOUND  base -18.0  tone -21.0  SNR -3.0 dB   (pass 1)
    NO SOUND  base -15.9  tone -18.9  SNR -3.0 dB   (pass 2)

A base of −18 dBFS on the panel microphone lane is 37 dB above the −55.4 dBFS
the same check read on this unit at 13:33 the same afternoon, when it PASSED
(`tone -35.8, THD -31.8 dB, 2.56 %`). That is the signature S115 recorded as
finding S115-2: the chip-2 MAIN bus pinned near full scale, which makes the
loop's signal-to-noise meaningless and the verdict fiction. S115 found that a
full boot-and-configure twice clears it and that a configure alone does not.

**Measured, not assumed.** Straight after the second pass, with nothing else
changed, the pair was reset and booted and the same check re-run:

    --section B --only DR1,DR2   DR1 PASS, DR2 PASS (BOOT_STAGE 7/7, 31 lanes carrying)
    --section C --only AL1       PASS  base -55.5  tone -34.8  SNR 20.6 dB  THD -32.0 dB  2.53 %

A boot, and the check that had read NO SOUND twice in a row passes at a base
37 dB lower, with the distortion figure S115 calibrated the ceiling against
(2.53 % against 2.56 % at 13:33 and the 3.758 % limit). **It has a consequence
for RUN ALL specifically**: a later pass does not boot the pair if the link is
alive, so once a unit is in this state every subsequent pass reads the same
fiction and the acoustic row can never come back. See §9 for the recommendation.

---

## 6. Acceptance, against the dispatch's own bar

| the bar | result |
|---|---|
| One START press runs the whole automatic set with no further input | **yes** — `TESTSKIN: press TESTACT 'STARTALL' at 456,920`, then 210 s with nothing touched |
| Manual stepping reaches every runnable manual row in station order | **yes** — stations 3, 4, 5, 6 in that order (analog last); stations 1 and 2 have no runnable row and their 50 rows are reported as not tested with the reason |
| Every catalog row appears exactly once in the report | **yes** — the two verdict tables together hold **202 rows, 202 distinct numbers, none missing**. A set-aside row is additionally summarised in its own section, which is a summary and not a second verdict |
| Pause/resume survives an app restart | **yes** — paused, `d24-testui` restarted, START ALL came back reading `RESUME: CHECK 1`, one press carried on |
| IGNORE round trip proven | **yes** — set through the glass with a reason, owed 93 → 92, written to `ignored.csv` against the serial and the catalog md5, `--unignore` restores the previous verdict |
| The `.md` report has no Matrix-internal vocabulary (grep it) | **yes** — `d24_runall.py --check-md <report>` is that grep and the report is clean |
| Questions for PW = 🔴 note, no dialog | **yes** — §8; no question dialog was opened |

### What `--check-md` actually greps for

Bench test ids, matrix cell names, firmware-table names, DSP node ids,
run-group codes, session tags, bench tool names and repository paths. It runs
over the page and exits non-zero naming every hit.

Two things it deliberately does not strip, both said out loud rather than
claimed as clean:

* **The reading and limit columns are the instrument's own words**, minus test
  ids and cell names. A technician chasing a NO DATA needs the actual reading
  ("CS6 reaches no fitted part", "0 % loss, max RTT < 5 ms"), and the hardware
  designators in them are the ones on their build sheet. The JSON twin has the
  unscrubbed original. **🔴 for PW in §8 if the human page must lose those too.**
* **Header designators stay in the meter station's dialogs.** PW's 09-21 rule is
  that the operator is told panel names — "MIC 5", "AUX 1 out" — and never a
  connector number for something they can see from outside. An internal header
  has no panel name and the designator is what is printed beside it on the
  board; taking it out would leave the operator hunting.

Row NAMES on the human page do get plain English: "main control processor
link", "audio processor select line 6", "clock master", "output converters",
"panel microphone and speaker". Panel items are left exactly as the workbook has
them, because "MIC 5" and "Aux Out A1" already are the names a person uses.

---

## 7. Deployed

Unit MW-D24-2 (`app@192.168.1.219`), serial `10000000830b03af`.

| artefact | md5 | rollback |
|---|---|---|
| `/home/app/app` | `b61a190c6b1655346378acc75b2e4432` | `/home/app/app.bak-s117-pre` = `432ae0fcba2400e74e9916e979103720` (S112's build) |
| `/home/app/skins/D24TEST.mxs` | `d0448ca4f0cb03cbd0434a1d2b0c9706` | `/home/app/skins/D24TEST.mxs.bak-s117-pre` = `f517539d6a7c2b3ac72a65d35267f8da` |
| `/home/app/selftest/d24_runall.py` | `d46962b528106612fa0c66f6f0d6737b` | new file; none |
| `/home/app/selftest/test-catalog.csv` | `96694c1357912229ad6e5b4feaf33884` (S116's) | `test-catalog.csv.bak-s117-pre` = `fd4de54e1f60aa89a43ffde47536c45a` |
| `/home/app/selftest/s117-tap-through.py` | session tool, not part of the product | — |

S116's catalog had never been deployed: the unit was still running the 25
September file, which has no `group` and no `order` columns — the two RUN ALL
orders by. That is why it goes out with this change.

The app was published the S107 way: `dotnet publish -c Release -r linux-arm64
--self-contained -p:PublishSingleFile=true`. `dotnet test src/sw/app.Tests`:
**163 / 163 pass**. The published md5 was checked against the copy on the unit
before each install; `d24-testui` was stopped for the swap and `matrix-app` was
never started.

### mx26 app changes — the S116 §9 list, now done

| S116 §9 | done |
|---|---|
| 1. Drop `--no-soak-wait` from the wizard's invocation | **done** — `RunnerInvocation()` no longer passes it; the runner still accepts it, so an older app does not break |
| 2. Read the corrected `tests` on rows 127/203 | **done** — the store has always read `tests` live from the catalog; the corrected catalog is now on the unit |
| 3. Partner-row stamping with the one-way guard | **done** — `DonorFor()`: a row with no gating result of its own takes the verdict of a row that covers it, but only when that row's test set is a superset of its own. Pressing the row that runs two tests stamps the row that runs one; the reverse does not |
| 4. Rows 103/104 should say `factory-test-v1`, not `S82-signed` | **done in the catalog** (S116); the app has no duplicate copy of that text — it reads `pass_when` live |
| 5. Read `group` / `order` | **done** — `Entry.Group` / `Entry.Order` are read; the row page says which run group a row is in; the ORDERING is the runner's, which is where RUN ALL now lives |

---

## 8. 🔴 For PW — flagged, not decided

**Q1 (the dispatch's own question). The meter station with the analog supplies
up.** The station order puts the two analog stations last so the rails go up
once and late (S116 Q4). The meter station is *lid off*. As built, a station
declares whether it needs the rails and they are raised once before the first
station that does — so the meter station would be walked with the analog
supplies live and its card says so in as many words: *"The analog supplies are
LIVE for this station."* **Is that the right order, or must the meter station
run rails-down, with the analog loopback the only live station?** Nothing was
decided here and no rails went up in this session's run: neither analog station
had its fixture, so both were skipped at their first dialog.

**Q2. The fifty switch-panel rows.** Stations 1 and 2 are the two switch panels
— 50 rows, the most obviously manual thing on the product — and today every one
of them is *not tested*, because the host has no per-control read and no
per-indicator drive, and the firmware table declares a matrix cell for exactly
one panel switch (`FxMute`). Nothing was invented to fill that. **But one ruling
may turn all 50 into gradeable rows: does the panel firmware light a button's
own indicator locally when the button is pressed?** If it does, one dialog per
button — *"Press MONO AUX. Did its white indicator light while it was down?"* —
grades the switch row and its indicator row together, with the operator
judging, needing no host capability at all. If it does not, the 50 rows need a
per-control read building, which is a dispatch of its own. The answer decides
which.

**Q3. How plain must the human page be?** The report's row names, headings and
prose are plain English and the acceptance grep proves no Matrix-internal
vocabulary reaches it. The *reading* and *limit* columns still carry the
instrument's own words, hardware designators and all, because a person chasing a
fault needs the reading rather than a paraphrase of it. **If the page must also
lose those, it is a pass over each of the 36 checks' own wording — say so and it
is done; it is not a guess worth making.**

**Q4. Where the report is exported.** The dispatch says the test-result hub is
still PW's, so the pair is written to the unit
(`/home/app/selftest/reports/`) and pulled to `MW/D24/DSP/s117/accept/` by hand.
There is no drop folder configured because none has been named.

---

## 9. What is not done, and one measurement to go with it

* **The reason pick-list has no free text.** "Other" is pickable; the spec says
  "other + on-glass text". There is no on-screen keyboard on this page, and
  adding one is a change of a different size. The reason is recorded as
  `other`; a session that needs to say more says it in the JSON by hand.
* **The scrollable non-PASS list is the existing queue walk**, not a new list
  widget (§2(4)). Deliberate, and the same information.
* **Stations 1 and 2 are not visited at all** because neither has a runnable
  row. If Q2 is answered yes they become the two biggest stations in the set.
* **The two analog stations were skipped at their first dialog**, as the
  dispatch allowed, so no rails went up under an operator dialog in this
  session and Q1 is untested in practice as well as undecided.
* **The acoustic loop needs a boot before a later pass can clear it** (finding
  S117-3). RUN ALL does not boot the pair on a pass where the link is already
  alive — that is S114's saving and it is right for every other check — but it
  means a unit that has fallen into the pinned-MAIN state carries a fictional
  acoustic verdict through every later pass. The cheapest fix, if PW wants one,
  is one line: make the acoustic check ask for a boot when it is owed on a pass
  after the first. Not done here because it is a change to the automatic set's
  cost and the dispatch's bar was to leave the automatic set alone.

---

## 10. How to run it

On the unit, from the glass: **START ALL**. Everything else is the wizard.

From a shell on the unit, for a bench session with no operator:

    python3 /home/app/selftest/d24_runall.py                 # a pass, from the glass
    python3 /home/app/selftest/d24_runall.py --stdin         # the same, answered on stdin
    python3 /home/app/selftest/d24_runall.py --auto-only     # the automatic set and the report
    python3 /home/app/selftest/d24_runall.py --autoskip      # walk every station, skip everything
    python3 /home/app/selftest/d24_runall.py --report-only   # re-write the report from state
    python3 /home/app/selftest/d24_runall.py --ignore 56 --reason 'fixture not built'
    python3 /home/app/selftest/d24_runall.py --unignore 56
    python3 /home/app/selftest/d24_runall.py --check-md REPORT.md
    python3 /home/app/selftest/d24_runall.py --dump-dialogs manual-dialogs.csv

`--stdin` takes `done`, `yes`, `no`, `back`, `pause`, `skip: <reason>`,
`ignore: <reason>` — the same answers the glass sends, which is what makes the
whole flow testable on a desk with no unit at all.

### Where the files are

| path | what |
|---|---|
| `/home/app/selftest/runall/state.json` | the unit's cumulative state: per row the verdict, the pass, the history; the step a pause stopped on |
| `/home/app/selftest/runall/prompt.json` | the dialog the runner wants drawn |
| `/home/app/selftest/runall/answer.json` | the button the operator pressed |
| `/home/app/selftest/runall/progress.txt` | the one progress line |
| `/home/app/selftest/ignored.csv` | set-asides, per serial, with the catalog md5 that expires them |
| `/home/app/selftest/reports/<serial>-<stamp>.md` / `.json` | the report pair |
| `/home/app/selftest/runall.log` | the runner's own console |

---

## 11. The captures

Real `MX_DRM_CAPTURE_PATH` renders off the unit's own framebuffer, 1 Hz
(S105's `s105-capture.conf`, already in place).

| file | what it shows |
|---|---|
| `s117-idle.png` | the page at rest with **START ALL** beside **START TEST** |
| `s117-auto-running.png` | the automatic set in flight: `RUNNING ALL…` with its comet, the one progress line, START TEST and PREV/NEXT correctly dead, and the touch tile reading *last touch 51 s ago* — the START ALL press |
| `s117-dlg-station.png`, `s117-dlg-instruct3.png` | a STATION card: what to have in hand, how many checks, READY / SKIP / IGNORE / PAUSE |
| `s117-dlg-instruct.png` | an INSTRUCT dialog: one action, DONE / < BACK / SKIP / IGNORE / PAUSE, `WAITING FOR YOU` on the START ALL button |
| `s117-dlg-reason.png` | the reason pick-list: AWAITING PART / KNOWN REV-C ERRATUM / FIXTURE NOT BUILT / OTHER / < BACK |
| `s117-dlg-review.png` | the review screen after pass 1, `START NEXT PASS` in the green slot |
| `s117-dlg-review-ignore.png` | the same, set-aside taken |
| `s117-paused.png`, `s117-resume-after-restart.png` | paused, then the same page after `d24-testui` was restarted: **RESUME: CHECK 1** |
| `s117-dlg-instruct2.png` | pass 2, before the class-line fix — the row identity line wrapping onto the `scripted today` line below it |

### One defect this change surfaced and fixed

`s117-dlg-instruct2.png` shows it: the row identity line ("row 101 of 202 ·
class … · automation … · section …") is longer than its box on rows whose
section heading is long, wraps, and draws on top of the line under it. The
generator has warned about this since S110 and says the fix belongs in the app,
because the generator owns only one of the five fields on that line. It was
rarely seen before because an operator walked the queue and never landed on
those rows; RUN ALL puts the page on every row it steps. One line in the store
now ellipsises it (`ClassLineMax = 147`), and `s117-dlg-instruct3.png` is the
same kind of page afterwards.
