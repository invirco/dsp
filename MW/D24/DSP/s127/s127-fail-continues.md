provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S127 — a single fail restarts the factory test, repeats, restarts, freezes

MW-D24-2, 2026-09-27. PW at the bench, reporting three things in order:

> "hiccups, test restarted after a single fail, it should log the fail and
> continue testing. then after restart, after a few repeated instructions is
> suddenly started again then froze in factory test mode for a while"

and, after the hub's second addendum:

> "it didn't ask me to prep the hanging cables, or enter any usb sticks."

Four defects, four root causes, all four found in evidence rather than
inferred. Two of them are in this repo and are fixed and proved on the part.
Two are in the display app (mx26 `src/sw/app`) and are written up here as a
spec for the hub, because the app is not built from this tree.

---

## 1. The timeline, second by second

Reconstructed from `d24-factory.service` and `d24-testui.service` in the
journal, `/home/app/selftest/factory.log`, `runall/live.json`,
`runall/prompt.json`, `runall/patch-results.csv` and the app's own trace at
`/home/app/logs/trace`. All times BST.

| time | what happened | evidence |
|---|---|---|
| 11:44:24 | `matrix-app` stopped, `d24-testui` started — the armed factory screen | journal |
| 12:49:41 | **START #1.** The app runs `systemctl reset-failed d24-factory` then `systemd-run --unit=d24-factory … d24_patch.py --run --list-dir …/quick --dir …/runall --live …/runall` | `sudo[11969]` audit line |
| 12:49:4x–12:51:5x | the walk: P1…P7 PASS, **P8 MAIN R → MIC 7 NO DATA** ("the lane sat −18.1 dB over its own floor") — the single fail | `patch-results.csv`, `factory.log` |
| 12:51:56 | the pass ends: `the pass stopped at P9 (pause)`, rails down, chain safe, report written (8 rows) | `factory.log`; unit deactivated 12:51:56 |
| 12:52:00 | **START #2**, four seconds later. The walk begins again **at patch 1 of 59** | `sudo[12094]`, journal |
| 12:52:46 | the walk reaches P6; `prompt.json` is written for "Patch AUX 8 to MIC 7" | `prompt.json` stamp |
| **12:52:47** | **the display app dies with SIGSEGV**, after 27 min 30 s of CPU | journal |
| 12:52:50 → 13:00:16 | **the app aborts on every restart, 36 times**, ~6 s after each start; systemd restarts it every ~13 s | journal (37 "Main process exited": 1 SEGV + 36 ABRT); 180 matching exception blocks in `logs/trace` |
| 12:52:46 → 13:00:50 | the runner **carries on underneath**, holding at P6 "Waiting for the lead…", beating, **with the rails UP** | `live.json` heartbeat; `pinctrl get 26` = hi |
| 13:00:50 | this session writes `command.json` = pause. Rails down, chain SAFE, report written | `factory.log` |

Unit state at each point: AN_EN **high** from 12:49:4x to 13:00:50 — that is
**eleven minutes of rails up**, of which **eight had no working glass**.
CS_M stayed driven high throughout. PW's rule (analog last up, first down) was
never broken by the runner: the rails were owned by a live process the whole
time. What there was no owner for was the **operator's attention** — nothing on
the unit noticed that the only surface the instructions appear on had died.

### What PW saw, mapped onto that

1. **"test restarted after a single fail"** — P8 failed at ~12:51:5x, and the
   pass ended four seconds before START #2. START #2 began **at patch 1 of 59**
   and **overwrote the report**: the eight measured patches in
   `patch-results.csv` became five. See §2.
2. **"after restart, after a few repeated instructions"** — START #2 re-walked
   the same first patches PW had just done (AUX 1, AUX 4, AUX 5 … into MIC 7),
   and from 12:52:50 the app restarted every ~13 s, re-drawing the same
   instruction each time.
3. **"suddenly started again"** — the app restarting, 36 times.
4. **"froze in factory test mode for a while"** — the runner sat at P6 for 8
   minutes. Its patience is `detect_timeout_s` (20 s) × `ENTER_PATIENCE` (30) =
   **600 s per attempt, three attempts = 30 minutes per patch**, with the rails
   up and nothing on the glass to press.

---

## 2. Defect 1 — a fail ended the pass, and START threw the report away

### What the fail itself did

Nothing. `record()` logs a NO DATA verdict and the walk continues; that part of
the S126 code is correct and the dry run proves it. **The fail is not what
stopped the pass.**

### What did stop it

`Station.run()` had one branch for every glass answer that was not
`done`/`ack`/`retry`:

```python
if how == 'glass' and ans.get('button') in ('pause', 'skip', 'ignore'):
    self.finish_early(rows, ans)
    return self.rows_out
```

So **SKIP and IGNORE ended the whole pass**, exactly like PAUSE — and SKIP is
the one button an operator reaches for when a patch will not pass. Everywhere
else in the test (`apply_answer`, `record_manual`) SKIP is per-item: the row is
recorded SKIPPED with the operator's reason and the walk goes on. In the patch
station alone it was fatal. The same branch existed a second time in
`find_loop()`.

Measured, same fault, same list, one SKIP on one input:

| | measurements | patches walked |
|---|---|---|
| S126 rule (`skip` in the stop set) | **66 of 245** | **24 of 91** |
| S127 rule | **245 of 245** (237 PASS, 8 SKIPPED) | **89 of 91** |

`--fault skip:MIC 9`, `--fault ignore:MIC 9`, `--fault pause:MIC 9` are now in
the dry run's fault battery, so the operator's own buttons can be pressed
without a person.

### And the report did not survive the restart

`cmd_run` ended with `write_results(out, rows)` — a plain overwrite. PW's second
START wrote a five-row `patch-results.csv` over the eight-row one, and the P8
NO DATA that started all of this was gone. "Put every fail in the one report at
the end" cannot survive a file that only ever holds the last attempt.

### The fixes

* **Only PAUSE stops a pass** (`STOP_BUTTONS`). SKIP and IGNORE record the
  patch — `SKIPPED` / `IGNORED` with the operator's reason — and the walk
  continues (`Station.decided()`), at both sites.
* **A button the station has no rule for never ends a pass.** It is logged and
  the patch is offered again on a fresh dialog (a fresh one because
  `Glass.poll` matches on the posted sequence number and the answer that got us
  there is still on disk — re-using the old token would read it again and
  spin).
* **A skipped patch is not a fail and not a dead socket.** It does not enter
  the failure list the glass shows and it does not condemn a parking output.
* **The end screen counts all three outcomes.** `finished_words(passed, failed,
  not_tested)` — a pass that skipped four patches used to say "all 55 passed".
* **`merge_results()` replaces `write_results()` on the run path.** Each run
  also keeps its own `patch-results-<stamp>.csv`; `patch-results.csv` is the
  whole session, newest verdict per patch, in list order. Proved: eight rows
  including a NO DATA, then a five-patch second run — eight rows survive, the
  NO DATA survives, the five get their newer verdicts.

### Proved on the part (MW-D24-2, K2 block, six patches)

* **Forced fail on every patch** (`logs/on-part-forced-fail.txt`,
  `data/on-part-forced-fail.csv`): ENTER pressed with nothing patched. Six
  patches, three attempts each, **all fourteen rows NO DATA with plain
  reasons**, the walk **finished**, rails down, chain back to safe.
* **SKIP on every patch** (`logs/on-part-skip-every-patch.txt`,
  `data/on-part-skip-every-patch.csv`): **all fourteen rows SKIPPED** with
  "awaiting part", the walk **finished**, and the glass ended on
  `Finished - 0 passed, 6 not tested.` Under the S126 rule this run would have
  ended at patch 1.

---

## 3. Defect 2 — nothing stopped a second START, and nothing noticed a dead one

### A second START

The app's guard on this path is a `systemctl reset-failed d24-factory` in front
of every `systemd-run`. That is not a guard: it **clears** the previous unit's
state so a second press starts a second runner. On 2026-09-26 that put two
runners on the unit at once and the second died on the GPIO the first was
holding — the `OSError: [Errno 16] Device or resource busy` traceback still at
the top of `factory.log`. A stack trace where a sentence belonged.

**`RunLock`**, taken **before `Unit()` opens anything**, on both entry points:
one file, `runall/runner.lock`, with the pid, the start time and the argv.

* A second START while a run is live is **refused with one plain sentence**
  ("The test is already running. Carry on with the instructions.") and touches
  **neither `live.json` nor `progress.txt`** — the live run owns both, and
  overwriting either would take the real run's words off the screen, which is
  the very thing a second press must not do.
* A lock whose pid is gone is **stale and is taken over**, with a line saying
  so: a unit power-cycled mid-run must not need a person to delete a file
  before the test will run again.

### A runner that crashes, is signalled, or is killed

| way out | before S127 | now |
|---|---|---|
| last patch | report, rails down, tally | unchanged |
| PAUSE | report, rails down | unchanged, and the report **merges** |
| SIGINT / SIGTERM | teardown, **no report** | teardown, report, glass says the test stopped |
| an exception | **no report, no teardown if it raised before the Station existed**, last instruction left on the glass | rails down, report of what completed, glass says the test stopped, lock released — and the traceback still goes to the log |
| **SIGKILL / OOM / mains** | rails up, frozen instruction, dead lock — nothing can be done from inside a dead process | `--guard` (below) |

And one more the SIGTERM row hides, found by doing it: **`systemctl stop`
during the panel loops left the rails UP.** The teardown in `one_pass` was
guarded on `stopped`, which is set only when `Paused` is raised, so a SIGTERM
unwound straight past it and the unit went back on the bench live. It now
lowers on any way out of that phase that is not all the way through. Measured
on MW-D24-2 before and after.

Proved on the desk: with no DSP on this machine `Unit()` raises, and the run
leaves `patch-results.csv`, a glass reading *"The test stopped before it
finished - the test program stopped. The unit is safe. Press START to run the
test again."*, and **no lock**.

### `d24_patch.py --guard` — the other half of liveness

The heartbeat is the definition of live (S123), and only one side of that was
enforced. A runner killed outright cannot write anything, so it leaves the last
instruction on the glass, the heartbeat stopped, and **the rails up**.

Measured on the part, SIGKILL on a live run leaves exactly: `AN_EN` **hi**,
`live.json` frozen on *"Plug MONITOR L into MIC 8, then press ENTER."*
state `waiting`, and a lock naming a pid that no longer exists. That is PW's
"froze in factory test mode", reproduced deliberately.

`--guard` is one check, no run behind it, in this order:

1. a live pid holds the lock → **a run is going, touch nothing**;
2. the screen already says the run ended → only the rails are still worth
   checking;
3. otherwise the heartbeat has stopped for longer than the slack → **the run is
   gone**: say so on the glass in one plain sentence;
4. clear the dead lock, and put the rails **down** if they are up.

Proved on the part against a staged killed-run residue: *"the screen has not
been written for 121 s and no runner holds the lock: the run is gone"* → the
dead marker cleared, **AN_EN lo**, chain back to SAFE verified, the glass on
*"The test stopped before it finished… Press START to run the test again."*
with a START button. Run again: *"nothing to do"*, exit 0. It is idempotent and
it never touches a live run.

**It is not installed as a timer.** Putting a background service on a factory
unit is PW's call, not this session's. See §7.

---

## 4. Defect 3 — the armed START was never the factory test

PW's own words: *"it didn't ask me to prep the hanging cables, or enter any usb
sticks."*

The armed factory screen has launched `d24_patch.py` since S123, when the patch
walk **was** the whole of what that screen drove. S126 then built the full
ruled order — the setup pages, the three-phase overlap, the panel loops — in
`d24_runall.py`, **and nothing re-pointed the armed screen at it**. The app's
START, read verbatim out of the journal, is

```
systemd-run --collect --unit=d24-factory … /bin/bash -c 'python3 \
  /home/app/selftest/d24_patch.py --run \
  --list-dir /home/app/selftest/quick \
  --dir /home/app/selftest/runall --live /home/app/selftest/runall …'
```

so pressing START ran the analog patch walk on its own. There was no bug to
find in the setup pages: they were never launched.

**The fix, with no app change**: `d24_patch.py --run` **is the factory test**.
It hands over to RUN ALL in-process (`cmd_factory`). The station on its own is
`--patch-only`, which is a development and bench entry and never what the
factory screen launches.

**The list is not taken from the command line there**, which is the other half
of PW's rule. The unit says which list it has in `list.conf`, exactly as it
says which DSP pair it has in `pair.conf`, so the sequence is told nothing and
`find_list_dir()` reads the unit's own declaration. A `--list-dir` on a factory
START is ignored and the log says so rather than silently honouring it.

> One naming point for PW: on MW-D24-2 `list.conf` names
> `/home/app/selftest/quick`, and that directory is **not** a development
> shortcut — it is this unit's ten-unpopulated-inputs list, 59 patches / 151
> measurements, which is the right list for this unit. The name "quick" is what
> made it read as a shortcut. It should be renamed to something that says what
> it is.

### And the setup pages could not be got past at all

Found by pressing ENTER on them, which is the only way it could have been
found. `Setup._page()` asked the screen for its button **twice** in one turn:

```python
if self.live.command() == 'pause':  ...
if (self.keys is not None and self.keys.pressed()) or \
        self.live.command() == 'enter':  ...
```

`Live.command()` **takes** the button — it deletes the file it read. So an
ENTER was read by the first call, discarded because it was not `pause`, and
gone by the second. The only thing that could advance a setup page was a USB
keyboard's Enter — and S126 addendum 1 established that a factory pass has no
keyboard plugged in, and that one in the rear ports would falsely pass a USB
socket row.

Measured on the part before the fix: **seven ENTER presses over 100 s, still on
page 1 of 7.** After the fix (one read per turn): page 1 → 2 → 3 → … See §6.

`Station.paused_by_screen()` carried the same shape and had no callers. It is
removed rather than left waiting for its first one.

---

## 5. Defect 4 — the display app, which is not in this tree

Two separate app faults. The app is mx26 `src/sw/app`; both are written here as
a spec.

### 5a. The progress bar negates its own fraction — SIGABRT, deterministic

Every one of the 36 aborts is the same unhandled managed exception, logged 180
times in `/home/app/logs/trace`:

```
System.ArgumentException: -16.271186440677965 is not a valid value for 'Width'.
   at Avalonia.Layout.Layoutable.set_Width(Double value)
   at app_avalonia.Views.FactoryView.SetBar(Double frac)
   at app_avalonia.Views.FactoryView.Draw(FactoryStatus s, Armed armed)
   at app_avalonia.Views.FactoryView.OnTick()
   at app_avalonia.Views.FactoryView.Start()
   at app_avalonia.Views.FactoryView.<.ctor>b__16_0(Object _, VisualTreeAttachmentEventArgs _)
…
Program.CurrentDomain_UnhandledException: Unhandled exception on non-UI thread
```

**The law was measured, not guessed.** Five live files were staged on the part
with a beating heartbeat and the app started on each:

| `n` | `passed` | `failed` | width in the exception |
|---|---|---|---|
| 6 | 5 | 0 | −16.271186440677965 |
| 10 | 3 | 0 | −27.11864406779661 |
| 10 | 3 | 2 | −27.11864406779661 |
| 1 | 0 | 0 | −2.711864406779661 |
| 10 | 10 | 0 | −27.11864406779661 |

Width = **−160 × n / total** (total = 59), independent of `passed` and
`failed`. `160/59 = 2.711864406779661`. So `SetBar` is handed **the negation of
the progress fraction**, and .NET refuses a negative `Width`.

It is fatal only on the **attach** tick — `VisualTreeAttachmentEventArgs` →
`Start()` → `OnTick()`, which runs on a non-UI thread — so it kills the app if
and only if the app **starts while a run is live**. That is why PW's 12:49 run
drew a screen perfectly and the 12:52:50 restart could not: **the app cannot be
restarted during a run at all, from the first patch onward.** Once it started
crashing there was nothing to break the loop.

A sixth run with no `live.json` at all started clean, which is what makes the
handback safe.

**What a fix needs there:** the sign, and a clamp. `SetBar` should take
`frac` already clamped to `0…1` and reject nothing; better still, per this
tree's own contract in `d24_live.py`, *"there is no field the renderer has to
interpret, look up or count, because the moment the renderer counts something
it owns a rule"* — the fraction belongs in `live.json` as a field, not in
arithmetic on the C# side. This repo's side of that is now guaranteed:
`Live._flush()` clamps `0 ≤ n ≤ total` and `total ≥ 1`, so a run that stopped
before it had a list can no longer leave `total = 0` and a division nobody can
draw.

### 5b. The SEGV after 27 minutes

`d24-testui` consumed **27 min 30 s of CPU in 68 min of wall** — about 40 %,
continuously — and then took SIGSEGV at 12:52:47 with **nothing in its own
trace**: the last entry before it is 11:44:34, over an hour earlier. A native
fault that never reached managed handling. There is no core: `coredumpctl` is
not installed on the unit and `/var/lib/systemd/coredump/` is empty.

Not diagnosable from here. What would make it diagnosable next time is in §5c.

### 5c. The service could not be diagnosed, and could not stop flashing

`d24-testui.service` had `StandardOutput=null` and `StandardError=null`, so the
app's crash text was **discarded** — the 36 aborts were only recoverable
because the app happens to keep its own trace file. And `Restart=on-failure`
with no rate limit restarts for ever, so a deterministic startup crash is a
**strobing display** rather than a stopped service.

Both changed, deployed, and the file kept in this repo at
`s127/d24-testui.service` (rollback `/home/app/s127/d24-testui.service.bak-s127-pre`):

```
[Unit]  StartLimitIntervalSec=120
        StartLimitBurst=3
[Service] StandardOutput=journal
          StandardError=journal
```

Three attempts in two minutes rides out a transient; past that the unit is
telling us something, and a still screen says it better than a flashing one.

---

## 5d. And after the setup pages, the glass went back to "Press START"

Found the same way as the ENTER bug: by pressing it. With START now running the
full sequence, the seven setup pages went by and then the screen showed **the
armed page — "Audio patch test / 59 steps / Press START, then follow the
instructions"** — while the run carried on underneath, blocked on a dialog
(`Station 1 - Front panel switches`) that the armed display draws nothing for.
Photographed; the `d24-runall` unit name makes no difference to it (tested with
a marker unit active), so the armed FactoryView draws `live.json` and nothing
else, ever.

Two causes, both in this repo:

* the setup pages' screen was **closed** at the end of the setup block
  (`keys.stop()`, `live.clear()`, "the panel loops are the app's own dialogs")
  — true of the wizard, not of the armed factory display;
* the panel stations put every word they have into **dialogs**: a blocking
  station card, a per-step instruction, and two yes/no judgements.

Fixed, in the shape S126 used for the setup pages and the analog station:

* the screen and the keyboard now **live past the setup pages** and are closed
  after the panel loops, where the analog station builds its own;
* `glass_page()` — the setup pages' own wait loop, factored out — puts any
  station's words on the one screen the armed display draws;
* the **station card** is one instruction and ENTER
  (`LV.station_card_words`); the **panel loop** is one standing page,
  *"Press the button on the front panel that is lit."*, with `n of N` ticking
  as buttons land — the unit's own lit indicator is the per-step instruction,
  so the screen says the one thing the panel cannot and then stays still;
* the **two yes/no judgements** need two buttons and this screen has one. PW's
  own ruling in this dispatch covers it: *"where an error does make the next
  step impossible, the station records it, says so in one plain sentence on the
  glass, and carries on"*. They are recorded NO DATA — *"The always-lit rings:
  not checked, because this screen cannot ask a yes or no question yet."* —
  never guessed at and never waited on for ever.

Proved with no finger at the bench (`logs/panel-station-on-the-glass.txt`,
`panel-on-glass.py`): the right switch panel driven from a scripted key stream
with a stand-in for the app's ENTER button — the card answered on the glass,
32 rows landed in 0.5 s, 30 PASS and the 2 judgements NO DATA with their
reason. The dialog path is **byte-identical to HEAD** on the same harness
(`logs/panel-station-regression.txt`), so nothing that already worked changed.

🔴 **The two judgements are the one piece of coverage this leaves on the
floor, and PW has to rule on it.** The factory screen has one button by PW's
own design. Either it gains a YES/NO page, or those two rows are graded
somewhere else, or the factory test is driven from the wizard. Nothing was
invented here.

---

## 6. Proved on the glass

Photographed through the app's own capture file in front of the real display,
in `s127/screens/`:

* `01-armed.png` — the armed screen: **"Audio patch test / 59 steps / Press
  START, then follow the instructions."**
* the setup pages, in order, after the real START command — the network lead
  (with *"The unit can see it."*), the two USB sticks, then the kit.

The START used is the app's own, copied verbatim from the journal of PW's
12:52:00 press, so the path under test is the path PW's finger takes.

---

## 7. Owed, and what needs PW

* 🔴 **The app fix (5a), and it is the one that matters most.** Until `SetBar`
  stops negating, any restart of the display during a run is an unbreakable
  crash loop. The measured law and the stack are in §5a.
* 🔴 **The SEGV (5b)** — undiagnosed. With `StandardError=journal` in and
  `coredumpctl` installable, the next one leaves evidence.
* 🔴 **`--guard` is built and proved but not installed.** A `systemd` timer
  every 30 s would close the "rails up with no owner" window for good. Adding a
  background service to a factory unit is PW's call.
* 🔴 **Resume for the patch station.** RUN ALL already resumes — a paused
  sequence logs *"the next START resumes here"* — so with START now running the
  full sequence, PW's pause is resumable. `--patch-only` still restarts from
  patch 1; with `merge_results` in, that no longer loses anything, but it does
  re-walk. S123 estimated a resume at about thirty lines.
* 🔴 **Rename `/home/app/selftest/quick`.** It is this unit's real list, not a
  shortcut, and its name is what made it read as one (§4).
* 🟢 **PAUSE used not to stop a panel loop promptly** — `PL.loop` turned the
  press into a SKIPPED button and walked the rest of the panel, 30 s a button
  with nobody pressing them. Measured mid-loop this session, then fixed: once
  paused, every remaining button ends at once.
* 🟡 `"paused at step None of the operator set"` — the resume line names no
  step. Cosmetic, in `d24_runall.py`.
* 🟡 `live.json` still carries `"run": "setup"` through the panel loops,
  because the screen object is made once and kept. It is a label the app may
  use to choose a layout; changing it mid-run was not worth the risk today.
* 🟡 The station card says *"44 checks here"* where the loop then counts 14:
  the card counts the catalog rows the card covers, the loop counts the buttons
  it will light. Both are true and they read as a contradiction.
* 🟡 The armed screen still says **"Audio patch test / 59 steps"** from
  `factory.json`, which is now the wrong name for what START runs. Changing it
  is one line of data, but the honest step count for the full sequence is not
  59 and should be worked out rather than invented.

---

## 8. Deployed, and the unit as left

| file | md5 | rollback |
|---|---|---|
| `/home/app/selftest/d24_patch.py` | `7761e5a8b358d571e7ac17c83c91f26b` | `.bak-s127-pre` |
| `/home/app/selftest/d24_runall.py` | `0024bde71220e181c6f740921acf8693` | `.bak-s127-pre` |
| `/home/app/selftest/d24_live.py` | `1de7df2439866000b40a4719fe2dcb12` | `.bak-s127-pre` |
| `/etc/systemd/system/d24-testui.service` | this repo's `s127/d24-testui.service` | `/home/app/s127/d24-testui.service.bak-s127-pre` |

All three tools byte-identical to this repo.

**The unit, every line read back:**

* AN_EN **lo**, CS_M driven **hi**;
* the 595 chain at SAFE, marker `01 × 24, 00`, matching `SAFE_IMAGE` exactly;
* the staged pair unchanged and **unflashed** — `chip1.ldr`
  `7f226919a5d181410c3804d92678da19`, `chip2.ldr`
  `9e8a1a9edf19a90ce7ac3df1586c00f6`, byte for byte what S126 left (still v2);
* `matrix-app` inactive, `d24-factory` inactive, **`d24-testui` active with
  0 restarts**;
* `runall/` holds only `patch-results.csv` and `progress.txt` — **no live file,
  no prompt, no lock and no half-finished pass**, so START runs the whole test
  from the top and the display starts clean (which, until the app's bar is
  fixed, is what keeps it from crash-looping);
* the factory screen **ARMED** (`screens/13-handback-armed.png`);
* 1.2 GB free.

One reading this session could not take: the DSP pair is **not booted** (the
SPI link times out), because the last thing done to it was a `systemctl stop`
part way through the DSP phase. That is not a hazard with the rails down and
the chain safe, and the sequence boots the pair itself when PW presses START.

**What PW presses: START, on the D24's own screen.** Then the seven setup
pages, ENTER on each; then the front panel, ENTER on the card and the lit
buttons after it. The two indicator judgements will read NOT CHECKED with the
sentence in §5d until that ruling is made.
