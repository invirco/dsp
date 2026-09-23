provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S95 — five live-testing fixes to the D24 test skin

All five landed and all five were exercised on the unit. The 36/37 bug was not
what it looked like: **it was not those two cells, and it was not the test skin.
It was the app's skin loader, and it was silently dropping fourteen cells.**

**And the session turned up something bigger than any of the five: the
section-B/C run path — the gate in front of 31 of the 36 scripted rows — is not
merely untested, it is broken, and the cause is diagnosed. See §6.3.** It was
found by accident, which is said plainly there.

Unit: `app@192.168.1.219`, `matrix-app` active, `D24TEST` still the boot skin.
App binary `1e0cdd5da77684f25cbd83c213b78900` (md5-matched against the local
publish), previous binary kept at `/home/app/app.bak-s95-pre`
(`f893bd12…`, the S94 build).

Presses went in through `/dev/uinput` (`d24_touch_inject.py --serve`), exactly
as in S94 — **not** through the panel's ILITEK controller. They prove the skin,
the hit-testing, the store and the runner. They prove nothing about the touch
panel or its cable. That is still PW's finger.

---

## 1. The 36/37 bug — root cause

**`SkinLoader` parsed `skin.csv` with `line.Split(',')`, and `skin.csv` is
RFC-4180 CSV.**

`MW-D24-2` rows 36 and 37 are `Monitor Out L (TRS, unbalanced)` and
`Monitor Out R (TRS, unbalanced)`. **The item name contains a comma.** The
generator writes `DefStr` as `board|item` verbatim through Python's `csv`
writer, which quotes any field containing one:

```
t036,SW,TESTCELL,,,"Analog|Monitor Out L (TRS, unbalanced)",,null,…,true,775,162,72,60,…
                     ^ one field to a compliant reader, two to a naive split
```

Split on `,`, that line gains a field, and **every column after `DefStr` shifts
by one**. `DefStr` is index 5; `Pass` is index 16. The shift made `Pass` read
what `Clone` held — the empty string — so:

```csharp
data.Pass = GetBool(fields, "Pass");     // "" → false
if (!data.Pass) return data;             // ← the control is never created
```

The row was dropped **with no log line at all**. On the panel that is a hole in
the grid showing the skin background (`#181C22`) — no number, near-black. That
is what PW saw.

### Why the dispatch's two hypotheses were both wrong

- **Not `TESTRSVD`.** Both rows generate as `TESTCELL`, verified in the `.mxs`
  actually deployed on the unit (unpacked from `/home/app/skins/D24TEST.mxs`).
- **Not a row-source divergence.** `build-d24-connector-status.py --export-keys`
  yields 204 rows, the catalog is 204 rows, and the ordering and numbering
  agree exactly. The generator's import of the runner's `ITEMS`/`SECTION`
  tables is sound.

### Why S94's log looked clean

S94 recorded `Skin loaded successfully, controls=257` and treated it as proof
all 250 cells loaded. **It is not evidence.** `LoadMixerControl(controlIndex, …)`
grows the control list until it reaches `controlIndex`, so a skipped row leaves
an invisible placeholder and the *next* row restores the count. 257 is reached
whether 250 cells loaded or 236 did.

### It is not a test-skin problem — it is a round-trip bug in the app

The app's own writer, `CsvHelper.CsvWriteToString`, quotes exactly these fields:

```csharp
if (value.Contains(",") || value.Contains("\"") || value.Contains("\n"))
    value = "\"" + value.Replace("\"", "\"\"") + "\"";
```

and `CsvHelper.ParseCsvLine` reads them back correctly. **`SkinLoader` was the
one half of the app that did not.** Any skin saved from the editor with a comma
in a label would have come back with its columns shifted. The test skin is
simply the first skin to contain one.

### The fix

`SkinLoader.ParseHeader` and `SkinLoader.ParseRow` now both go through
`CsvHelper.ParseCsvLine` (via one `SplitSkinLine` helper), and a data row whose
field count differs from the header's is **logged** rather than silently
mis-read. Of the 33 skins on the unit, `D24TEST` is the only one containing a
quote character at all, so the change is behaviour-neutral for everything
shipped — checked by unpacking all 33 `.mxs` files.

Regression tests: `src/sw/app.Tests/SkinLoaderCsvTests.cs` (3 tests — the
shifted-column case, the writer→loader round trip, and that an unquoted line
still splits identically).

### The fourteen cells that were missing, not two

| # | board \| item |
|---|---|
| 36, 37 | Analog \| Monitor Out L / R (TRS, unbalanced) |
| 39–42 | Analog \| Aux Out A 1-2 … 7-8 (TRS, Phone Jack sub-assembly) |
| 55 | Left Switch PCBA \| BOOT0 indicator LED (red, fw.csv BootLed) |
| 91 | Right Switch PCBA \| Encoder ring LEDs (8 white singles, fw.csv Enc1–Enc8) |
| 95, 96 | Analog \| Mini-jack 1 / 2 (3.5 mm, Mini Jack sub-assembly) |
| 131, 132 | Analog \| USB A (dual jack, hub port 3 / 4) |
| 199 | Assemblies \| ADC AK5558 ×3 (U15 dead, U39, U60) — two commas, shifted by two |
| 201 | Assemblies \| Power MCU (STM32F030F4, always-on) |

PW happened to spot 36 and 37 because they are adjacent in the second row; the
other twelve are scattered and read as ordinary dark cells.

**All fourteen pressed live on the fixed build**, each opening its detail page
with the full key intact:

```
TESTSKIN: press TESTCELL 'Analog|Monitor Out L (TRS, unbalanced)' at 775,162
TESTSKIN: selected #36 Analog|Monitor Out L (TRS, unbalanced) status=UNTESTED
TESTSKIN: press TESTCELL 'Analog|Monitor Out R (TRS, unbalanced)' at 849,162
TESTSKIN: selected #37 Analog|Monitor Out R (TRS, unbalanced) status=UNTESTED
…
TESTSKIN: selected #199 Assemblies|ADC AK5558 ×3 (U15 dead, U39, U60) status=PASS
TESTSKIN: selected #201 Assemblies|Power MCU (STM32F030F4, always-on) status=UNTESTED
```

---

## 2. The colour scheme — amber for anything not red or green

`ColorOf()` had five buckets. It now has three:

| status | colour |
|---|---|
| PASS | green `#1F9D3A` |
| FAIL | red `#C62828` |
| PARTIAL **and** UNTESTED | amber `#C9821A` |
| RUNNING | blue `#1B6FB5`, animated (§3) |

`TESTRSVD`'s near-black `#22272E` is untouched — it is "no row here", which is
a different statement from "a real row, not yet resolved", and it is drawn by a
different branch.

The legend now reads
`green PASS   red FAIL   amber EVERYTHING NOT YET RESOLVED   pulsing blue RUNNING   dark NO ROW`,
and the counts line reads `PASS 19  FAIL 0  NOT RESOLVED 185 (partial 5, untested 180)`
— one amber number with the split still available behind it, because the
workbook still distinguishes them even though the grid no longer does.

`grid-preview.png` beside this file shows it. **That is a render of the
generated `skin.csv` coloured from the unit's own `item-status.csv` by the same
roll-up rule, not a screenshot** — the same limit S94 hit and for the same
reason (§6 there). 19 green, 5 amber-PARTIAL, 180 amber-UNTESTED, 46 dark
reserved.

---

## 3. RUNNING now animates

It is drawn through `DrawingContext`, not XAML, so there is no storyboard to
hang an animation on. `TestSkinStore` gained a second `DispatcherTimer` at
50 ms that runs **only while `_running` is non-empty** and forces a repaint;
the cell reads `AnimPhase` (0→1 over 1400 ms) on each paint. Two things move:

- **the fill breathes** — lerped towards white on a raised cosine, from about
  18 % to 50 % of the way there and back, once per cycle. This is the half that
  carries across a 25-wide grid: the cell visibly brightens and dims.
- **a comet runs clockwise round the inside of the border** — a bright head with
  a seven-dot fading tail, one lap per cycle. This is the half that reads close
  up and gives it a direction of travel.

Both are eight `DrawRectangle` calls per paint and no geometry, so they cost
nothing and survive any cell size the grid takes. `grid-preview-running.png`
beside this file is an eight-frame strip of one cycle, drawn by the preview tool
running the same arithmetic — again, a render, not a screenshot.

Shown working live. Cell 128 (HDMI0 → TFT), START pressed, run to completion:

```
TESTSKIN: press TESTACT 'START' at 1400,960
TestSkinStore: RUNNING animation started — 20 Hz repaint while 1 key(s) run
TestSkinStore: started HD0-1,HD0-2 at 11:28:29 — setsid python3 …
TestSkinStore: HDMI FPC (rev B)|Display link HDMI0 → TFT finished, exit 0
TestSkinStore: RUNNING animation stopped after 32 forced repaints at 20 Hz
```

and a second press: `stopped after 46 forced repaints`. The frame count is the
witness, deliberately — a screenshot this unit cannot take would not show motion
anyway, and a static blue cell and an animated one log identically without it.
Both runs were short (1.7 s, 2.3 s), so PW will see a fraction of a cycle on a
section-A row and a proper minutes-long pulse on a section-B/C one.

---

## 4. Button labels are centred

`MixerControl.DrawText` treats `Txt1OffY` as the text's **top edge**, which is
right for a label placed on an artwork image and wrong for a plain rectangle
that is all label — and the generator was emitting absolute offsets (50 on an
80 px button, 52 on an 84 px one). Measured, headless, against the real
typeface:

| button | size | height | old top / gap below | new top / gap below |
|---|---|---|---|---|
| EXIT TO MIXER | 22 | 80 px | **50 / 12.4** | 31.2 / 31.2 |
| REFRESH | 22 | 80 px | **50 / 12.4** | 31.2 / 31.2 |
| BACK | 24 | 84 px | **52 / 12.8** | 32.4 / 32.4 |
| START TEST | 24 | 84 px | **52 / 12.8** | 32.4 / 32.4 |
| DETAIL | 24 | 84 px | **52 / 12.8** | 32.4 / 32.4 |

Four times as much space above as below — that is the "visibly off-centre" PW
saw, and it is now 32.4 / 32.4. The grid cell numbers got the same treatment
(they sat at 17 on a 60 px cell against a centred 21.2).

`TESTCELL` and `TESTACT` are drawn by a new `DrawTextCentred`, which centres in
both axes and reads `Txt1OffX`/`Txt1OffY` as **deltas from that centre**; the
generator now emits 0 for both. `DrawText` is unchanged for every other control
in every other skin. Pinned by `src/sw/app.Tests/TestSkinLayoutTests.cs`, which
asserts both halves: centred now, and demonstrably not centred before.

---

## 5. Short instruction + a Detail button

The detail page now **opens on one imperative line**. The full prose — what the
test is, when it passes, what evidence it wants — is behind a new **DETAIL**
button between BACK and the run note, and `HIDE DETAIL` puts it away. The
selection resets it, so a new row always opens short.

Mechanically: the catalog gained a `short` column; `TestSkinStore.Field()`
returns `""` for `SHORT` while detail is shown and `""` for
`H_EXPLAIN`/`EXPLAIN`/`H_PASS`/`PASSWHEN`/`H_MANUAL`/`MANUAL` while it is not,
so the two views share the same screen space with no new render machinery.

Live:

```
TESTSKIN: press TESTCELL 'Analog|Monitor Out L (TRS, unbalanced)' at 775,162
TESTSKIN: press TESTACT 'DETAIL' at 340,960
TESTSKIN: detail shown
TESTSKIN: press TESTACT 'DETAIL' at 340,960
TESTSKIN: detail hidden
```

`detail-pages-as-shown.txt` beside this file has four rows in both views
(reconstructed from the catalog, as in S94 — the presses are the proof the page
was reached, the transcript is what the fields resolve to).

### Coverage: 203 of 204 have a real short line, 1 falls back

The lines are **written in the generator**, not scraped. What is read from the
row is only which bucket it falls in, and every bucket is a fact the row already
carries:

| rows | short line | where the fact comes from |
|---|---|---|
| 5 | "No action needed — press START TEST. The app stays up and the colour changes when it finishes." | has a runner, `stops_app=0` |
| 31 | "No action needed — press START TEST twice. The display goes away for the run and comes back with the result." | has a runner, `stops_app=1` |
| 30 | "Out of scope — PW ruled this row out of the self-test set. There is nothing to run." | the row's own out-of-scope explain |
| 45 | "Analog grade — method being rewritten (PW: no dScope in the skin; a manual self-cable loop replaces it). Not built yet." | spec heading **4b. Analog grade — a dScope**, overridden by the ruling below |
| 30 | "Needs a meter on the header — rail, continuity or presence. Not built yet — nothing to press." | spec heading **4c. … — a meter** |
| 28 | "Needs an eye: the host lights one indicator at a time and you confirm the named one lit. Not built yet — nothing to press." | spec heading **4a. … — an eye** |
| 24 | "Needs a press: work the panel control while the host tails the UART. Not built yet — nothing to press." | spec heading **Section 3 — needs a press** |
| 6 | "Needs the section-2 harness plugged in — no rails, no analog. Not built yet." | spec heading **2A** |
| 4 | "Presence is section 2; the graded half still needs an eye or a meter. Not built yet — nothing to press." | spec heading **4d** |
| **1** | *(none)* → app falls back to **"See Detail for what this test needs."** | row 149, `Link 'hdmi-fpc'` |

The 36 scripted rows got the dispatch's line verbatim in spirit; **none of them
needs hands** — their `manual` field names evidence to record, not an action to
take, which was checked row by row. The other 167 real lines name the
**instrument the spec's own subsection heading names**, which is the spec's
answer rather than a guess about the row; the dispatch asked for section 1 plus
whatever else could be done accurately, and this is where the line was drawn.

**The 4b line follows PW's 11:29 ruling, which landed mid-session.** The
mandate ("no dScope anywhere in the self-test skin — ALL tests internally
generated and measured, manual self-cable instructions instead") was pushed to
mx26 twelve minutes before this work was committed, and the spec's §4b heading
it rewrites is exactly the heading 45 of these short lines key off. Instructing
a dScope on 45 cells would have put a just-ruled-out instrument in front of the
technician, so the line names the ruling and stops there — **the replacement
method is the queued spec rewrite, not something invented here**, and the spec
prose behind DETAIL still says "dScope" on 39 rows because that rewrite has not
happened yet. The catalog was regenerated and redeployed for this after the
first push (`test-catalog.csv` `d8773ea3…`).

**The one fallback is honest, not lazy.** Row 149 resolves to the spec's
`🔴 Proposed corrections to section 1's coverage` — the S94 §4.4 loose end,
where the row is classified automation-1 but is absent from the runner's
`ITEMS`. There is no accurate one-liner for a row whose classification is
itself open, so it gets the fallback and the Detail button.

---

## 6. 🔴 Five findings — one of them the biggest thing in this session

### 6.1 The unit's rootfs filled during the deploy and a truncated binary was installed

`/` was at **99 % with 111 MB free** when this session started, and `app` is
116 MB. The first `scp` of the new binary ran out of space part-way, **reported
the failure on stderr but exited 0**, and the install step moved a 92 MB
fragment over `/home/app/app`. The app then restart-looped. Recovered from
`app.bak-s95-pre`; no harm beyond about ten minutes.

The space was not the backups — it was **970 MB of stale .NET single-file
extraction caches** in `/home/app/.net/app/`, ten directories of ~100 MB, one
per distinct app binary ever run on the unit, going back to 18 August. Nothing
prunes them. They were cleared (they are a cache; the running binary re-extracts
its own on next start), and the unit is now at **87 %, 870 MB free** — healthier
than S94 left it.

**Worth a standing check before any future app deploy: `df -h /` first, and
`rm -rf /home/app/.net/app/*` with the service stopped if it is tight.** And
scp's exit code cannot be trusted here — verify the md5 on the unit *before*
moving a binary into place, which is what the rest of this deploy did.

### 6.2 🔴 Pressing START on a soak row downgrades it — the same trap as S94 §4.2, on a different axis

Proving the animation needed a real run, so cell 128 (HDMI0 → TFT) was started.
`HD0-2` is a **one-hour soak**, and the button runs the runner with
`--no-soak-wait`, so it took a **0-second window**, correctly called it
`NO DATA`, and appended it. Newest stamp wins, so **rows 128 and 204 went
PASS → PARTIAL** — green to amber — on the strength of a press that learned
nothing.

The runner did not lie; the *press* destroyed a genuine 3600-second reading from
22 Sep by superseding it. S94 flagged this for the host-relative tests
(`NW3`/`NW4`); it is the same failure on the soak axis, and the catalog does not
mark either kind.

**What was done about it:** the four zero-window `HD0-2 NO DATA` rows this
session caused (six rows in all, once the stray presses of §6.3 are counted)
were removed from `/home/app/selftest/item-status.csv` (kept verbatim in
`removed-hd02-nodata-rows.txt` beside this file;
`item-status.csv.bak-s95` on the unit is the file as it stood before). Nothing
else was touched — the two fresh `HD0-1 PASS` rows are genuine and stayed. The
roll-up is back to **19 PASS / 5 PARTIAL / 0 FAIL / 180 UNTESTED**, which is
where S94 handed it over. This is stated plainly rather than done quietly: a row
the runner itself labels NO DATA carries no information, and letting it bury an
hour of real evidence would have been the worse of the two errors — but it is
still a hand-edit of a results file and PW should know it happened.

**The real fix, for the next dispatch:** mark both kinds in the catalog —
`needs_bench_host` and `needs_soak_window` — and have the detail page say "this
half cannot be taken from the unit / from a button press" and refuse to
supersede a stronger reading with a weaker one. It is the third time this has
bitten.

### 6.3 🔴🔴 THE SECTION-B/C PATH DOES NOT WORK. It kills the runner along with the app.

**This is the session's real finding, and it arrived by accident.** Destroying
the `uinput` injector at teardown produced spurious presses — the device's last
state being reported as the kernel tore it down — and three of them landed
inside the START button's box. One of them landed on cell **202, `M MCU
(STM32G031)`, `ML-M`, runner section B**, and a second landed on it again,
which is exactly the two-press confirmation the design demands. So the
app-stopping path ran, unattended, with nobody in the room — the one thing S94
declined to do and this dispatch declined to do. **It failed.**

```
11:35:34  TESTSKIN: press TESTACT 'START'
11:35:34  TestSkinStore: started ML-M — setsid python3 …/d24_selftest.py --section B --only ML-M
11:35:35  sudo[33596]: app : COMMAND=/usr/bin/systemctl stop matrix-app
11:35:35  systemd[1]: matrix-app.service: Deactivated successfully.
          … and then nothing at all
```

No `run.log` header. No raw reads (`logs/2026-09-23T103535Z/` was created and
left **empty**). No results row. No restart. The unit sat with **no display**
from 11:35:35 until it was started by hand at 11:37:56.

**Why.** `matrix-app.service` runs with systemd's default
`KillMode=control-group`. **`setsid` creates a new session, not a new cgroup** —
the runner stays inside `matrix-app.service`'s cgroup, so the moment it calls
`systemctl stop matrix-app` systemd SIGTERMs the whole cgroup, the runner
included. It kills itself with the command whose entire purpose was to get out
of its own way. The design comment in `TestSkinStore.StartSelected` —
"setsid so the run outlives the app it may be about to stop" — is wrong about
Linux, and the service's own `status` line is the proof:
`code=killed ; status=15/TERM`.

**So S94's "built but untested" was optimistic: it is built and it does not
work, and 31 of the 36 scripted rows are behind it.** The second-press
confirmation works, the detached launch works, the stop works — and then the
runner dies.

**The fix** is to leave the cgroup, not the session: launch the run through
`systemd-run --scope --collect` (or as its own transient unit with
`--no-block`), so it lives in a cgroup systemd will not tear down with
`matrix-app`. That is a small change in `StartSelected` plus a re-test, and it
should be the next dispatch's first job — it is worth more than anything else
on the list, since it is the gate in front of 31 rows.

### 6.4 The amber collapse does not create the MIC 20 problem, but it does not solve it

The hub recorded at 11:17, mid-session, that **a row the workbook knows has
FAILED can show as untested on the skin** — MIC 20 is FAIL in the workbook but
is not one of the 36 rows the live runner covers, so `item-status.csv` has
nothing for it and the skin says UNTESTED. It is queued behind this dispatch,
and it was right not to fold it in.

For the record, since the note worries the two changes might collide: **this
change does not make that case worse.** A known-FAIL-with-no-live-result was
`UNTESTED` before and is `UNTESTED` now — slate then, amber now — so it was
already indistinguishable from a never-tested row. What the amber collapse
removes is the PARTIAL/UNTESTED distinction, and MIC 20 is in neither of those
buckets by way of the workbook. When the fallback lands, a workbook FAIL should
come through as **FAIL** and paint red, which is a third colour and unaffected
by anything here.

### 6.5 Bench-procedure hazard: tearing down the touch injector fires stray presses

The taps in §6.3 were not commanded. They appeared as the `uinput` device was
destroyed. Any future session using `d24_touch_inject.py --serve` should
**stop `matrix-app` before killing the injector**, or at least leave the skin on
a page where a stray press cannot start anything. A note for the injector's
docstring; this session was lucky that the row it hit was a link check.

---

## 7. What is not done

- **Sections B and C do not run at all** — see §6.3. That is no longer "untested",
  it is "tested and broken", with a diagnosed cause and a one-line shape of a
  fix. 31 of the 36 scripted rows are behind it.
- **The animation was only ever seen for a couple of seconds**, because the two
  section-A rows that are safe to run both finish in under three seconds
  (32, 44 and 46 forced repaints on the three runs). A working section-B row
  would show it properly.
- **No screenshot**, for the reasons S94 §6 gives, which have not changed.

---

## 8. The unit as handed back

| | |
|---|---|
| `matrix-app` | active, boot skin **D24TEST** |
| app binary | `1e0cdd5da77684f25cbd83c213b78900`, md5-matched on the unit; rollback at `/home/app/app.bak-s95-pre` (`f893bd12…`, S94) |
| skins | `D24TEST.mxs` `e07fd5cb…`, `D24TESTD.mxs` `97562236…` |
| catalog | `test-catalog.csv` `d8773ea3…`, 204 rows, `short` column added (regenerated after PW's 11:29 no-dScope ruling) |
| results | `item-status.csv`, roll-up 19 PASS / 5 PARTIAL / 0 FAIL / 180 UNTESTED; pre-session copy at `item-status.csv.bak-s95` |
| injected touch device | destroyed, FIFO removed, `/dev/input/` back to its six real devices (the ILITEK pair among them) |
| stray runs caused | three HD0-1/HD0-2 (§6.2) and one aborted ML-M (§6.3); the six zero-window `HD0-2 NO DATA` rows they appended were removed and are kept in `removed-hd02-nodata-rows.txt` |
| disk | 87 %, 870 MB free (was 99 %, 111 MB) |
| AN_EN (GPIO26) | never raised; the app's bring-up gate still stops at step 1, as designed |
| CPLD / DSPs / 595 chain | untouched — no flash, no DSP boot, no chain write this session |
| `defs.lock` | unmoved; no generated DSP artifact touched, so no contract note is due |
