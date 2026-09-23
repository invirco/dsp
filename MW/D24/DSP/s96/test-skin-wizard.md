provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S96 — the D24 test skin is a linear wizard, and the section-B/C path works

The 25×10 grid is gone. The skin is **one page** that shows one test at a time:
`PREV` / `NEXT` top left, `N / 204 PASSED` top right, one imperative instruction
line in the body, a full-width animated progress bar, and `START TEST`. PASS
updates the score and advances by itself; FAIL stays put and prints what to do.

**And gate 0 holds: the section-B/C run path — the gate in front of 31 of the 36
scripted rows, which S95 proved was killing the runner along with the app — now
works, and was proven on the unit.** Witnessed at 12:23: `matrix-app` stopped at
12:23:01 with the runner still alive, the DSP pair booted, handback restarted the
app at 12:23:16, and **the restarted app picked the still-running test back up by
itself** and reaped its verdict at 12:23:42.

Unit: `app@192.168.1.219`, `matrix-app` active, `D24TEST` still the boot skin,
app binary `6552104ea2867ab38576cd62cf782e2c` md5-matched against the local
publish.

Presses went in through `/dev/uinput` (`d24_touch_inject.py --serve`), exactly as
in S94/S95 — **not** through the panel's ILITEK controller. They prove the skin,
the hit-testing, the store, the queue and the runner. **They prove nothing about
the touch panel or its cable.** That is still PW's finger.

---

## 1. Gate 0 — the runner now outlives the app it stops

S95's diagnosis was right and the fix is one line of shape. `setsid` makes a new
**session**; `matrix-app.service` kills by **cgroup**
(`KillMode=control-group`, the systemd default), so the runner — still inside
that service's cgroup — was SIGTERMed by the very `systemctl stop matrix-app` it
had issued.

The run is now launched into a transient systemd unit of its own:

```
sudo -n systemd-run --collect --unit=d24-selftest \
     --property=User=app --property=Group=app \
     --property=WorkingDirectory=/home/app/selftest \
     /bin/bash -c '<the runner invocation>'
```

`--scope` was the dispatch's suggestion and is not what landed. A scope runs the
command in the **caller's** context, and the caller here is `sudo`, so the run
would have executed as root and left root-owned rows in `item-status.csv` and
root-owned directories under `logs/`. A transient **service** with
`User=app`/`Group=app` lands in `/system.slice/d24-selftest.service` — outside
the app's cgroup, which is the whole point — while still running as the user
that owns every file it touches. `--collect` reaps the unit on exit so the name
is free for the next press.

**Proved at the shell first**, before any UI work, so the mechanism was not being
debugged through a touchscreen:

```
d24-gate0probe.service  ControlGroup=/system.slice/d24-gate0probe.service   (not the app's)
d24-gate0stop.service   stop matrix-app → sleep 10 → wrote "survived-the-stop" → start matrix-app
                        unit: inactive   app: active   /tmp/gate0b.txt: survived-the-stop
```

**Then proved from the screen** — the thing S94 declined to try and S95 only hit
by accident. `START` pressed twice on row 56 (`Panel MEMS mic`, section C):

| | |
|---|---|
| 12:23:01 | `started MM1 … in d24-selftest.service`; `matrix-app` **inactive**, runner **active** |
| | DSP pair booted, six registers per chip, inter-chip link gate `OVERALL: CLEAN` |
| 12:23:12 | handback: SAFE image `VERIFIED 200/200`, `CS_M: 27: ip pu`, `AN_EN: 26: … lo`, `systemctl start matrix-app` |
| 12:23:16 | app started |
| 12:23:23 | app logs `adopted the run still going in d24-selftest.service — this app was restarted by it`, re-selects row 56, restarts the progress bar |
| 12:23:42 | `#56 finished at 12:23:42 — UNTESTED` (MM1 NO DATA: `1 MEMS lanes all STATIC with AN_EN 26: op -- pd \| lo`, which is correct and honest) |
| 12:23:47 | runner exits |

### 1.1 The app is no longer the run's parent, so it stopped tracking it as one

This is the part that is design rather than plumbing, and it is what makes the
B/C path actually *usable* rather than merely survivable:

- **Liveness is `systemctl is-active d24-selftest.service`**, polled only while a
  run is in flight. `Process.HasExited` would have reported "finished" the moment
  `systemd-run` returned, i.e. immediately.
- **A marker file `/home/app/selftest/running.txt`** carries the key, the test
  IDs and the start time. On start-up the app reads it, asks systemd whether the
  unit is still alive, and if it is **adopts the run**. If the unit has gone, the
  run finished while the app was down and the results file already carries the
  verdict; the marker is cleared and that row is selected.

So a technician pressing `START` on a section-B row sees the display go away and
come back **on the same row, still running, with the bar going** — and then the
verdict. Before this, they would have come back to the top of the queue with no
idea whether anything had happened.

---

## 2. Gate 1 — the score is correlated with the workbook

`StatusOf` now falls back to the workbook's own `declared_status` where
`item-status.csv` has nothing at all for a row. **A fresh live run always
overrides it**; the fallback only ever fills a hole.

| declared | shows as | why |
|---|---|---|
| `FAIL` | **FAIL**, red | the hub's 11:17 note: MIC 20 is FAIL in the workbook, is not one of the 36 rows the runner covers, and the skin was calling it untested |
| `PARTIAL…` | PARTIAL, amber | |
| `PASS` | PASS, green | |
| `BENCH FAULT` | UNTESTED, amber | **deliberately not red.** BENCH FAULT is the workbook saying the *measurement* was invalid, not that the unit failed — which is exactly what amber already means |
| `UNTESTED – …` | UNTESTED, amber | |

Effect on this board: **3 rows that were amber are now red** — MIC 7 (#22),
MIC 8 (#23), MIC 20 (#24) — and all three are open supplier items with a
diagnosis already written down (§4). The 5 `BENCH FAULT` rows stay amber. The
detail line says `workbook says FAIL (no run on this unit yet)` so the two
sources are never confused.

### 2.1 The scoping choice, stated

**Score = passed / 204 — every canonical workbook row, not the 36 a button can
run today.** The score answers "how much of this unit is proven", and scoping
the denominator to today's automatable rows would let the board read 100 % while
168 rows had never been looked at. The number is never shown alone: the line
under it reads, over all 204,

```
N FAIL · N not resolved · N runnable now · N not yet automated
```

so the 168 rows outside the default queue are on screen as a number at all times.

---

## 3. Gate 2 — the wizard

**29 controls, none of them per-row.** The grid cost one control per row and had
a hard 250-cell ceiling the generator had to check for; the wizard's shape does
not change with the catalog length, so the list can now grow past 250 without
touching the skin. Every verdict was already keyed on `board|item` rather than on
a slot, so nothing in the data model had to change to drop the grid.

| region | holds |
|---|---|
| header | `PREV` / `NEXT`; the score and its breakdown; the queue position |
| identity | display number, `board \| item`, the status chip, the class line, what is scripted |
| body | **one instruction line** — or the `DETAIL` prose block in the same space — plus the remedial line when the row is failing |
| run | the progress bar, elapsed time, the last recorded result, what `START` will do, and the touch self-check tile |
| footer | `START TEST`, `DETAIL`, `QUEUE`, `EXIT TO MIXER` |

### 3.1 The 168 not-yet-automated rows — what the queue does with them

PW asked for "prev/next … step through all un-passed tests remaining". Taken
literally that is **185 rows, 168 of which have no runner at all** — 168 screens
with nothing to press, which is not factory-friendly however simple it is. So
`QUEUE` cycles three widths and defaults to the factory one:

| mode | contains | today |
|---|---|---|
| `QUEUE: RUNNABLE` *(default)* | un-passed **and** a button can run it | 17 rows |
| `QUEUE: UNPASSED` | every un-passed row — PW's literal reading | 185 rows |
| `QUEUE: ALL ROWS` | every row, passed ones included | 204 rows |

**Nothing is excluded silently.** The score line names all four counts at all
times; a not-yet-automated row, when stepped to, says
`NOT YET AUTOMATED — specified, not built` with `START` disabled and a run note
telling the operator to press NEXT; and no press ever silently no-ops.

The third mode is not padding. **A row that has passed is otherwise
unreachable**, and re-checking a row after a repair is a thing a factory does —
the dispatch left that as my call and this is the call. It is one extra state on
a button that already existed.

### 3.2 The progress bar

Full width now rather than squeezed into a 72×60 cell, so it says two things at
once: the **fill** is elapsed time against the expected length of that section's
run (25 s for A, 240 s for B/C) and a **sheen** sweeps the filled part once per
1400 ms cycle, so the bar is visibly alive even while the fill is holding. The
status chip breathes on the same phase.

**The fill stops at 95 % and holds.** Nothing here knows the run is nearly done,
and a bar sitting at 100 % on a running test is a lie the operator would act on.
The text beside it always names the real elapsed time and switches to
`longer than expected, still going` rather than stopping at the estimate.

Witnessed: **6304 forced repaints at 20 Hz** on the 5½-minute Ethernet run, and
34 on the 2-second CM4 run. S95 only ever got 32–46 because the only rows it
could safely run finished in under three seconds.

### 3.3 PASS is silent, FAIL is not

- **PASS** → score up, row leaves the queue, wizard advances by itself. No modal.
- **FAIL** → row turns red, `DETAIL` is forced off so the short answer is read
  first, and the remedial line appears under the instruction. The line is also
  written to the app log, because this unit cannot be screenshotted and it is
  otherwise unwitnessed.
- **anything else** (PARTIAL / NO DATA) → amber, wizard stays put.

`PREV`/`NEXT` are dead while a run is in flight; stepping away would leave the
operator watching a bar belonging to something else.

---

## 4. The remedial text — and the eighteen lines that were wrong

The mechanism is a new `remedy` column in `test-catalog.csv`, authored in
`build-d24-test-skin.py`, shown only on FAIL, with a generic fallback in the app
for a row with nothing authored.

**The honest count: 29 of 204 rows carry an authored remedial line, and those 29
are exactly the rows that can reach FAIL today — 0 fall back to the generic
line.** (26 runnable rows whose tests have a FAIL branch, plus the 3 the workbook
declares FAIL.) The generic line stays in the app because the first new automated
row without an authored diagnosis will reach it.

**And it shows only what actually failed.** The catalog holds one paragraph per
covering test, prefixed with that test's ID, and the app keeps only the
paragraphs whose test came back FAIL. Row 129 is covered by four tests; printing
all four diagnoses for a failure that was NW1's alone overflowed the box and
buried the answer — which the preview tool caught, rendering the real geometry
from the real data. A declared-only FAIL has no failing test to filter on and
gets everything the catalog holds, which for those rows is a single unprefixed
paragraph about the row itself.

Sources, and no others: the spec's own `method` / `PASS when` column for the test
that failed, and findings already written down about **this** board — the
CS_M / U2 all-zeros case, U15's known-dead ADC lanes, NW3's gateway control, and
`docs/d24-pcb-supplier-notes.md`'s two open items (A4 on MIC 7's gain leg, A5 on
MIC 8 / MIC 20's HF noise excess), which is what gives the three declared-FAIL
rows a real answer instead of "reseat it".

### 4.1 🔴 Written from the spec, eighteen of them described a test the runner does not run

The lines were drafted from `docs/spec-d24-selftest.md` and then checked against
`t_<id>` in `tools/pi/d24_selftest.py`. **Eighteen of thirty-two were wrong** —
not vague, wrong — and every one has been rewritten or removed. The pattern is
one thing: **the spec is the intent and the runner is the behaviour, and they
have diverged**, usually because a capability the spec assumes does not exist
yet. Examples:

| test | the spec-derived line said | the runner actually |
|---|---|---|
| `AS-CM4` | PASS wants core volts in the CM4's window | reads volts, reports them, and gates on `throttled 0x0 and temp < 70 and app active` only |
| `DR2` | PASS wants both SHARCs up **with the shipping build ids** | reads build ids, reports them, and gates on `BOOT_STAGE ≥ 7` |
| `AS-DSPB` | wants the **TX slots** contiguous and carrying data | takes no TX-slot read at all; for chip 2 it takes no lane read either |
| `USB-HUB` | the hub must enumerate **with its four ports** | counts `Class=Hub` lines and passes on `≥ 1` |
| `CC1` | 0xBB = **all four** MIC amps at +27 dB | MGN2L/MGN2R — two |
| `MM1` | idle floor **inside the declared window** | no level comparison exists; PASS means the lane is CARRYING |
| `DC1`/`DC2` | if all eight selects read nothing, suspect the shared path | CS3/CS4 are **inputs** on DSP4 and CS5–CS8 have **no part behind them**; six of the eight are structurally NO DATA and always will be |
| `HD0-2` | FAIL if the status left `connected` **or a hotplug event was counted** | the hotplug count is evidence only; FAIL is the status alone |

### 4.2 🔴 Nine of the twenty-five scripted test families have no FAIL branch at all

They can return only PASS or NO DATA today: **`HD-PWR`, `ML2`, `ML-M`, `ML-P1`,
`ML-P2`, `ML-B0`, `AS-DAC`, `AS-PWR`, `SP1`.** Five of those are hard-coded NO
DATA because the thing they need does not exist — no H1S1 version cell (`ML2`),
no BOOT0/NRST drive on H1S1 (`ML-B0`), no TEST_OSC stimulus on the shipping image
(`AS-DAC`), no reader for the power MCU's published words (`AS-PWR`), no
TEST_OSC → SPKR route in the topology (`SP1`).

They get **no remedial line**, and the generator asserts that they do not — what
to do about a failure that cannot happen is not something that file is entitled
to say.

**The consequence is bigger than the remedial text, and it is the second real
finding of this session: ten workbook rows have a button that can never turn them
red.** Rows **57, 126, 127, 143, 144, 145, 152, 198, 201, 202**. Their
instruction line says "No action needed — press START TEST", which over-promises:
pressing it records another NO DATA and nothing else. They read as amber forever
until the missing firmware or def lands.

**Recommended, not done here (it is a catalog/def change, not a skin one):** a
`can_fail` flag per row, so the instruction can say *why* the row is stuck and
`START` can be disabled rather than inviting a press that cannot help. It belongs
with the `needs_bench_host` / `needs_soak_window` flags S95 asked for — same
column family, same reason.

---

## 5. Gate 3 — live on the unit

All presses through `uinput`. Nine distinct button functions exercised:
`PREV`, `NEXT`, `QUEUE` (all three states), `START` (both the single-press and
the two-press confirm), `DETAIL`, and the disabled `START`.

### 5.1 A real FAIL cycle, from a real fault

A genuine failure was needed and none was available to hand, so one was
**induced, reversibly, at the thing the test actually measures**: `eth0` was
restricted to advertise 100baseT/Full only, inside a transient unit that restored
`0x03F` after 300 s whatever happened, so the link could not be left broken.

```
12:16:16  START pressed on #129 Digital|Ethernet (RJ45)   → d24-selftest.service
          NW1  FAIL  Link detected: yes, Speed: 100Mb/s, Duplex: Full
          NW2  FAIL  tx_dropped: 3 over the run, 0 on the idle control
          NW3  FAIL  bench host 100.0% loss; gateway worst 6.0% [5.5, 4.5, 6.0], max RTT 11.2 ms
          NW4  NO DATA (the driving host's path, correctly refused)
12:21:45  #129 finished — FAIL        (progress animation: 6304 forced repaints)
```

Row 129 went **amber → red** under a button press, the score's FAIL count moved,
the wizard stayed put, and the remedial line appeared. Nobody at the bench.

**The self-inflicted result was then re-taken**, which matters: leaving a FAIL
caused by the session in the unit's own results file is the S95 §6.2 mistake in
another direction. On the restored gigabit link, 12:25–12:30:
`NW1 PASS, NW2 PASS, NW3 FAIL, NW4 NO DATA`.

### 5.2 A real PASS cycle

```
12:36:04  START pressed on #194 Assemblies|CM4 compute module (reached via QUEUE: ALL ROWS)
12:36:06  #194 finished — PASS
12:36:06  PASS — advanced to #195 Assemblies|SHARC DSP A     ← silent, no modal
          progress animation: 34 forced repaints
```

**Stated plainly: the score did not move on that one, because #194 was already
green.** Nothing on this unit can currently go amber → green from a button —
every one of the 17 rows in the runnable queue is blocked on something outside
the unit (a bench host, a soak window, the section-2 harness, AN_EN, or one of
§4.2's nine missing capabilities). The PASS *mechanism* is proven; a PASS that
raises the score needs one of those blockers cleared first, and that is not this
session's to clear.

### 5.3 The FAIL page's own words, in the log

The remedial line is the whole point of a FAIL and this unit cannot be
screenshotted, so the page writes what it is showing. Third Ethernet run,
12:42:00:

```
TestSkinStore: #129 finished at 12:42:00 — FAIL
TestSkinStore: FAIL page shows — WHAT TO DO: PASS wants link up, 1000Mb/s, Full
  duplex. No link at all is the cable or J7; a link that comes up at 100Mb/s is
  the cable or the magnetics, not the CM4. Swap the cable to a known-good one
  before suspecting the board.  rx/tx errors, dropped and overruns must all be
  zero across the run...
TestSkinStore: progress animation stopped after 6290 forced repaints at 20 Hz
```

and on the final build, with the per-test filter in (§4), the same row failing on
NW2 and NW3 instead:

```
12:53:29  #129 finished at 12:53:29 — FAIL
12:53:29  FAIL page shows — WHAT TO DO: rx/tx errors, dropped and overruns must
          all be zero across the run, against a 30 s idle control. …
          NW3 pings the bench host AND, as a control, the unit's own default
          gate…                                   (the log line's own 300-char trim)
```

**NW1's and NW4's paragraphs are absent and NW2's and NW3's are present, which
is exactly which of the four failed on that run.** (The entry spans two log
lines because the field carries a real newline between paragraphs.)

### 5.4 🔴 Row 129 reads FAIL, and the reading is unsettled rather than a declared fault

On the **restored** gigabit link NW3 still FAILs, and by its own rule: loss
appeared toward **both** targets — 100 % to the bench host `192.168.1.211`
(simply not present; this machine is `.133`) and **1.5–6.0 % to the unit's own
gateway**, on all three runs, over three 200-packet passes each at 0.2 s.

But a plain 200-packet ping to the same gateway **at 0.05 s**, taken a minute
after one of them from the same unit, read **0 % loss over 200/200**. So the loss
is repeatable at NW3's own cadence and absent at another, which is the signature
of the switch rate-limiting ICMP rather than of the unit's link — and that would
make **the gateway control itself unreliable**, which matters because the control
is the only thing standing between "the bench host is missing" and a red cell
against the unit's Ethernet.

Left as it stands in `item-status.csv` — it is a real reading, not a session
artefact — and flagged here rather than quietly cleaned. **It wants one bench
half-hour with a host actually on `.211`** before anyone reads row 129 as an
Ethernet fault.

---

## 6. What is in the tree

**mx26**

| file | |
|---|---|
| `src/sw/app/Core/TestSkinStore.cs` | rewritten: the queue, the score, the declared-status fallback, the transient-unit launch, the marker adoption, the remedial field |
| `src/sw/app/Controls/MixerControl.cs` | `TESTCELL`/`TESTRSVD` retired; `TESTSTAT` and `TESTPROG` added; `PREV`/`NEXT`/`QUEUE` in the press path |
| `src/sw/app.Tests/TestSkinWizardTests.cs` | **new** — 10 tests over a fixture directory: the fallback, the three queues, wrap-around, the score's scoping, the remedy and its per-test filter, the short/detail exclusion |
| `src/sw/app.Tests/TestSkinLayoutTests.cs` | the wizard's button geometry, including that the longest label each button can carry still fits it |
| `tools/d24/build-d24-test-skin.py` | one wizard skin instead of grid + detail; the `remedy` column and its two authoring tables; `NO_FAIL_TESTS` and the assertion that guards it |
| `tools/d24/preview-d24-test-skin.py` | renders the wizard from the real `skin.csv` geometry — **and is what caught a layout collision**: the `DETAIL` block ran into the progress bar on a verbose row |
| `docs/spec-d24-test-skin.md` | rewritten for the wizard; the grid moved to §11 "Superseded", kept as history |

**dsp**: this report, and `MW/D24/DSP/s96/test-catalog.csv` (the generated
catalog as deployed).

Test suite **150/150 green** (127 before this session, +10 wizard, +13 layout
rows).

---

## 7. What is not done

- **No screenshot**, for the reasons S94 §6 gives, which have not changed: the
  app renders through DRM and `ffmpeg`/`modetest`/`grim`/`fbgrab` are all absent.
  Everything visual here is witnessed by a log line or by an independent render.
- **`needs_bench_host` / `needs_soak_window` / `can_fail` flags** — asked for by
  S95 and re-asked for above (§4.2). The wizard's default queue *accidentally*
  protects the soak case (HD0-2's rows are PASS, so `QUEUE: RUNNABLE` never steps
  to them), but `QUEUE: ALL ROWS` does not, and that is not a defence.
- **A passing row is reachable only through `QUEUE: ALL ROWS`.** That is
  deliberate and stated, not an oversight, but a technician re-testing after a
  repair has to know the button exists.
- **The 45 §4b analog rows still name PW's no-dScope ruling** rather than a
  method, because the replacement method is the queued spec rewrite and was not
  invented here.

---

## 8. The unit as handed back

| | |
|---|---|
| `matrix-app` | active, boot skin **D24TEST** (the wizard) |
| app binary | `e009e8056eff528cc83368b6e0a3d036`, md5-matched on the unit; rollback at `/home/app/app.bak-s96-pre` |
| skin | `D24TEST.mxs` `bff6c5f768b36a8b996e14bf5f4ac4fa`, 29 controls, loaded clean with no dropped rows |
| retired | `D24TESTD.mxs` → `D24TESTD.mxs.retired-s96` (the grid's detail skin) |
| catalog | `test-catalog.csv` `bf5c274750fa2ecd1386d7810ee17f48`, 204 rows, `remedy` column added; previous kept at `test-catalog.csv.bak-s96-pre` |
| injected touch device | destroyed, `d24-touchinj.service` stopped, FIFO removed |
| transient units | `d24-selftest`, `d24-gate0probe`, `d24-gate0stop`, `d24-ethguard`, `d24-touchinj` all `--collect`ed; none left behind |
| `eth0` | restored to autoneg advertising `0x03F`, link **1000Mb/s Full** |
| AN_EN (GPIO26) | never raised — `lo` throughout, including across the section-C DSP boot |
| CS_M (GPIO27) | `ip pu`, restored by the runner's own handback |
| 595 chain | SAFE image `VERIFIED 200/200` by handback after the section-C run |
| CPLD | untouched — no flash this session |
| DSPs | booted once, by the section-C run's own `boot_pair`, and handed back through the runner's handback |
| disk | 85 %, 980 MB free (was 87 %, 870 MB) — two superseded app backups and the stale .NET extraction caches pruned |
| `defs.lock` | unmoved; no generated DSP artifact touched, so no contract note is due |
| the score, as left on screen | **19 / 204 PASSED · 4 FAIL · 181 not resolved · 17 runnable now · 168 not yet automated** — reproduced independently by `preview-d24-test-skin.py` from the same two files |

The four FAILs are MIC 7, MIC 8 and MIC 20 — the three the workbook already
declared and that §2 now paints red for the first time — and row 129, Ethernet,
for the reason in §5.4. `item-status.csv` as handed back is in this directory as
`item-status-as-handed-back.csv`.
