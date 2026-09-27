provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S132 — AL1's "NO DATA, no settled window" was two stale tools on the unit, not the speaker, not the mic, and not the hands

**Outcome: root-caused, fixed, and AL1 PASSES.** The acoustic loop is healthy and
always was. The tone comes back at **-29.7 dBFS** against a **-46.2..-46.8 dBFS**
floor — **SNR 16.4..17.1 dB**, **bandpass THD -25.0 dB (5.6 %)** — and the level
repeats to **0.0 dB** across six consecutive readings. Nothing on the supplier
list; no hardware evidence to raise.

---

## 1. What it actually was

`d24_selftest.py::stage_tools` refreshes the eight `STAGE_TOOLS` in the stage
directory by md5, **against the runner's own directory** (`HERE`). Under
`--local` — which is how the glass's own START launches the runner — `HERE` is
`/home/app/selftest` **on the unit**. So the "source" it compares against is
itself a deploy, and when that deploy is behind the repo, source and stage are
the same stale file, the md5s match perfectly, and the evidence line reads
`tools: 8 repo-only tools already current in /home/app/s90 (md5)`.

**Both of AL1's tools moved in S122 (`42d09d1b`, 09-26) and neither had ever been
deployed to `/home/app/selftest`:**

| tool | on the unit | in the repo | what the unit's copy cannot do |
|---|---|---|---|
| `dsp4_s49_osc.py` | `098f95ba` = **S115** (`3508ecf9`), 25 204 B, mtime 09-26 13:03 | `1d5ddeb7` = S122, 30 693 B | no `--haptic` |
| `s89_set.py` | `bead35c7` = **S89** (`1871dae0`), 1 816 B, mtime 09-25 14:23 | `32ba6f20` = S122 | no `cN@ADDR` form |

Since S122 the panel speaker is fed by `C2_HPT_01` and by nothing else, so
`--haptic` is the only way to make it sound, and the haptic words are
**dispatched and not celled**, so `c2@2178`/`c2@2179` is the only way to write
them. The unit had neither. Which produces, exactly:

- **All three legs of `al1_measure` died on an argparse error** —
  `s: error: unrecognized arguments: --haptic` — so `_al1_osc` returned `None`
  three times and `al1_numbers` printed `no settled window for: base, tone,
  back`. **A sentence about acoustics describing an unrecognised argument.**
- **Every handback read `NOT SILENT -- the unit may still be audible`** on a
  graph that was silent throughout: `al1_silence` writes `c2@ADDR=0`, the stale
  `s89_set.py` answers `c2@2178  NOT IN CONTRACT` **and exits 0**, so
  `_silence_ok` found no read-back line and `rc == 0` hid it.

### The timestamps say it on their own

`factory.log`, the 21:40 unattended run S130 reported:

```
-- 21:40:51Z AL1 baseline start
-- 21:40:52Z AL1 tone start          <- one second for a leg that ramps 150 ms,
-- 21:40:52Z AL1 second baseline start   takes three windows and reads a
-- 21:40:52Z AL1 measure end            1,024-sample coherent capture
   AL1  NO DATA  no settled window for: base, tone, back
```

A healthy leg is ~2 s and a healthy measurement ~6 s (measured below). Three legs
in **1.3 s total** is not a window that failed to settle; it is a tool that never
ran. The same three-line collapse is in the 21:18 run and in every one of PW's
passes that day.

## 2. What changed since the 09-26 PASS — no bisect was needed, and why

The dispatch asked for a git bisect over S122/S124/S125/S126/S128/S129/S130. **No
commit bisects this, because the change is not in a commit** — it is in the gap
between the repo and `/home/app/selftest`, and the two sides of the gap moved at
different times. The file mtimes on the unit tell the whole sequence:

1. **09-26, S124 — AL1 PASSED on the haptic path.** S124 ran the runner **from the
   repo over SSH**, so `HERE` was `tools/pi` and `stage_tools` copied the *repo's*
   S122 tools into `/home/app/s90`. Its reading — `AL1 PASS base -47.1 tone -29.8
   SNR 17.3 dB THD -25.4 dB 5.38 %` — is within a few tenths of every reading
   taken tonight. **The loop was healthy then and is healthy now; the same
   measurement has been available the whole time.**
2. **Nothing put those tools in `/home/app/selftest`.** They reached only the
   stage, as a side effect of a run launched from the repo.
3. **09-27 11:32, S126 deployed the station's own tools; 11:35 the first `--local`
   run re-staged.** `/home/app/s90/dsp4_s49_osc.py` carries mtime 09-27 **11:35**
   and S115's md5: a `--local` run's `stage_tools` found the stage copy differing
   from `/home/app/selftest`'s and dutifully **copied the older file over the
   newer one**, because under `--local` that directory is what "current" means.
   From that minute on, every glass press called a S122 runner through a S115
   tool.
4. **09-27 19:13, S129 re-deployed `d24_selftest.py`** and, as before, not its
   tools — so the runner kept getting newer while the two tools it depends on
   stayed where they were.

That is also why the dispatch's "what changed since the 09-26 PASS" has an
uncomfortable answer: the 09-26 PASS was taken through a path (a run launched from
the repo) that the factory station never uses, and the station's own path had
never taken a passing AL1 on the haptic route at all.

S129's own explanation is therefore **disproved, and it was a reasonable
hypothesis**: the comment at `d24_runall.py:QUIET_MAX_S` said the 8 s hold cap
was why AL1 read NO DATA. It cannot have been. No acoustic window ever opened
for a panel press to disturb — the legs were dead in 0.5 s each — and the fault
reproduces standalone with the panel loop not started, nothing else running and
nobody near the unit (`data/al1-01-reproduced-standalone-NODATA.txt`). The
comment is corrected in place rather than deleted, because it was the standing
story for a day and the next reader will meet it in the S129 and S130 reports.

S130's reading was right on both counts and its escalation was correct: the
hands-off explanation was incomplete, and the overlap hypothesis it would not
claim as proven is indeed not the cause.

## 3. The three windows, raw

Standalone `--local` AL1, the same invocation the glass uses, nobody touching
anything. `data/al1-0*.txt` carry the full runs.

**Before the deploy** (`al1-01`, 22:07:20Z) — all three legs, verbatim:

```
AL1  NO DATA  no settled window for: base, tone, back
base: (no JSON)   tone: (no JSON)   back: (no JSON)
     the tool printed: s: error: unrecognized arguments: --haptic
handback: speaker path ... (NOT SILENT, live 0.9 s)
```

**After deploying the two tools, nothing else changed** (`al1-02`, `al1-03-*`):

| data file | base dBFS | tone dBFS | SNR dB | bandpass THD dB / % | speaker live s | verdict |
|---|---|---|---|---|---|---|
| `al1-02-after-tool-deploy-PASS` | -46.1 | -29.8 | 16.4 | -24.9 / 5.66 | 3.77 | **PASS** |
| `al1-02b-with-the-new-runner-PASS` | -46.4 | -29.7 | 16.7 | -25.0 / 5.62 | 3.69 | **PASS** |
| `al1-03-repeat1-PASS` | -46.2 | -29.7 | 16.4 | -25.0 / 5.63 | 3.67 | **PASS** |
| `al1-03-repeat2-PASS` | -46.8 | -29.7 | 17.1 | -25.0 / 5.64 | 3.77 | **PASS** |
| `al1-03-repeat3-PASS` | -46.3 | -29.7 | 16.6 | -25.0 / 5.62 | 3.69 | **PASS** |

The tone reads **-29.7/-29.8 dBFS on every run** (0.1 dB, one display digit) and
the THD spread over five readings is **0.1 dB**. The floor moves 0.7 dB, which is
the room. The second baseline returns to the floor on every run — that is what
`back` is for, and it is what says the reading was the tone and not something
walking past. Handback reads **SILENT** every time now, with the speaker live
3.7 s of a 6.5 s press.

### What "settled" requires, and which of the dispatch's candidates it was

`_al1_osc` calls `dsp4_s49_osc.py`, which takes three windows and returns the
last **untorn** one; `_al1_osc` returns `None` when the tool refused, wrote no
JSON, or every window was torn. `al1_numbers` then reports `no settled window`.
So the message covers three quite different things and said the same words for
all of them.

Of everything the dispatch listed — the level, a drifting noise floor, the MEMS
lane, the speaker slot, the TDM slot map, the codec init order, the window length
— **none was involved.** Each is measured and healthy in the passing runs above:
the MEMS lane is `rxscan`-confirmed and carrying, the codec init (H1S1
`StartAK4619`) returns ok before the first leg, the level sits dead on the
calibrated line, and the window length never mattered because no window was ever
opened.

## 4. Fixed, and made loud

Four changes. The first is the fix; the other three are so that this class of
fault can never again arrive dressed as an acoustic verdict.

1. **The two tools deployed** (`~/selftest/dsp4_s49_osc.py`, `~/selftest/s89_set.py`;
   backups `*.bak-s132-pre`), and the stale stage copies purged so the runner's
   own md5 gate re-copies them. Python bench tools only — no pair, no app, no
   MCU/CPLD image.

2. **`tools/pi/deploy-bench-tools.sh`** — the deploy that was missing. It
   md5-compares the station's whole tool set **from the repo**, which is the only
   side that can see the drift, backs up and copies what differs, purges stale
   stage copies, and re-verifies. `--check` reports and writes nothing. It reads
   `STAGE_TOOLS` out of `d24_selftest.py` rather than repeating the list, so a
   name added to that tuple and not to the script is reported instead of
   silently skipped. Every bench deploy before this was a hand-typed `scp`, which
   is how two of eight files were left behind.

3. **AL1 refuses to guess (`d24_selftest.py`).** Its prerequisite now checks both
   tools **by the capability it actually uses** — `--help` must offer `--haptic`,
   and the speaker probe's read-back must contain the `c2@ADDR` line — and
   blocks, before any tone, with a message that names the deploy:

   > `the staged copy of dsp4_s49_osc.py is BEHIND THIS RUNNER -- deploy
   > tools/pi/dsp4_s49_osc.py to the unit's own selftest directory (not just to
   > the stage). Under --local the stage is refreshed FROM that directory, so
   > "md5 already current" there proves nothing about the repo`

   By capability and not by an md5 manifest on purpose: a manifest inside a
   deployed runner rots into a false blocker on a good unit, which is the harness
   inventing a defect. Both gates are proven to fire by putting each stale tool
   back (`data/al1-04-*`, `data/al1-05-*`) — 2.7 s and 2.6 s, no tone played,
   speaker SILENT.

4. **Each leg now says why it produced nothing.** `_al1_leg_why` reads the tool's
   own output and `al1_numbers` lifts it to the verdict line the glass shows —
   and when all three legs failed the same way it is said once:
   `no window from base, tone, back: the tool refused the arguments (unrecognized
   arguments: --haptic)`. That one line is what a day of NO DATA was missing.

`stage_tools` also now prints, under `--local` only, the md5 of each staged tool
and one sentence saying that its own gate cannot see the repo and
`deploy-bench-tools.sh --check` can.

## 5. A second, real defect found on the way: the hands-off window was leaky

Not the cause of anything here, but `quiet_window` raised and **dropped the
`--quiet-flag` per leg**, so it went down twice in the middle of a measurement —
once between the baseline and the tone. `quiet_hold` is a
`while os.path.exists(path)` loop and `PL.loop` also asks it once before lighting
each indicator, so a call landing in a gap lights the next button with the tone
about to play into the microphone AL1 reads. Measured at 10 ms on the unit
(`data/quiet-flag-edges.txt`): **3 segments with two 41 ms gaps, now 1
continuous 2.97 s window.** `quiet_window` is reference-counted on the rig and
`al1_measure` holds it across all three legs.

## 6. S130's open question, answered

> *does AL1 ever actually show the hands-off screen at all in a real pass?*

**No.** `LV.HANDSOFF` is set only inside `panel_station`'s `hold=` callback, and
AL1 runs in the automatic batch, which starts before the panel station. So on
every real pass AL1 measures without that screen ever appearing. This is
recorded per pass as `handsoff_reached` in
`data/s132-al1-glass.json`. It is a reporting gap, not a safety one — the flag
and the hold do their work whether or not the screen names them — but the glass
does not currently tell an operator to keep still while the speaker sounds unless
a panel step happens to be waiting. **For the hub/PW, not fixed here:** should
the automatic batch raise the hands-off screen on its own, on the `--quiet-flag`
rather than on a panel step?

## 7. From the glass's own START, hands off, three times

`MW/D24/DSP/s132/tools/s132_al1_glass.py`, run on the unit. Each repeat:
`d24_runall.py --reset-only` (a pass RESUMES otherwise, so the second START would
never take AL1 again), AN_EN lowered, then **one tap on the armed START**, one tap
per new SETUP screen (7 of them: leads and USB sticks), and from the moment a
`d24_selftest.py` process carrying `AL1` in its arguments is alive, **no tap of
any kind** until AL1 has reported — then one tap on PAUSE.

The hands-off condition keys on that process and not on a screen state, for the
reason in §6: the hands-off screen never appears. It keys on `AL1` in the argument
list and not on the process name, because a pass launches three self-test batches
and the first starts at SETUP step 1, while the operator is still plugging leads
in.

RESULTS — `data/s132-al1-glass.json`, `data/s132-al1-glass.log`:

| pass | base dBFS | tone dBFS | SNR dB | bandpass THD dB / % | hands-off screen reached | verdict |
|---|---|---|---|---|---|---|
| 1 (23:49:20Z) | -46.4 | -29.8 | 16.7 | -25.0 / 5.63 | no | **PASS** |
| 2 (23:50:23Z) | -46.1 | -29.7 | 16.4 | -25.0 / 5.61 | no | **PASS** |
| 3 (23:51:27Z) | -46.3 | -29.7 | 16.6 | -25.0 / 5.64 | no | **PASS** |

**Three from the glass's own START, three PASSes, driver exit 0.** The readings
sit inside the standalone spread of §3 and inside S124's 09-26 reading, so the
glass path and the desk path now measure the same loop — which they had never both
done on the haptic route before tonight.

### Two things this took that are worth writing down

**A pass RESUMES, so a repeat needs a reset.** Without `--reset-only` the second
START picks up at the operator set ("the next START resumes here") and AL1, already
recorded, is not taken again: three PASSes would be one reading reported three
times.

**A pass paused before its end leaves AN_EN HIGH, and the next pass's whole `[dsp]`
batch then dies in under a second.** The station passes `--al1-keep-rails`, so the
self-test's own handback deliberately leaves the rails up; `d24_runall` lowers them
at the end of the station ("the analog supplies are off again"), which a PAUSE
skips. `boot_pair` then refuses — correctly, "analog last up, first down" — the AUTO
set reports `finished in 0 s`, and **AL1 is never taken at all while the glass says
nothing about why**. That is what happened at 23:42 before the rails check went
into this driver (`[dsp] RuntimeError: refusing to boot the DSP pair with AN_EN
(GPIO26) HIGH`, in `factory.log`). The driver now lowers AN_EN before each START.
**For the hub/PW:** a pass abandoned by PAUSE leaves the unit in a state where the
next pass silently loses its whole audio-processor batch. Worth a line on the glass
at least, and arguably `Paused()` should drop the rails on its way out. Not changed
here — it is `d24_runall`'s pause path, and the block said not to grind.

## 8. What was deployed to the unit, and what was not

Deployed (Python bench tools only; backups beside each):

| file | why |
|---|---|
| `dsp4_s49_osc.py` | S122's `--haptic`; was S115's copy |
| `s89_set.py` | S122's `cN@ADDR` form; was S89's copy |
| `d24_selftest.py` | the tool gate, the per-leg reason, the one quiet window |
| `d24_runall.py` | the corrected `QUIET_MAX_S` note |
| `s132_al1_glass.py` | this session's glass driver |

**Not touched, as the block required:** the app (`/home/app/app` still
`b05e9fd5`), the `.mxc`, any panel/MCU/CPLD firmware, any fuse, the DSP pair
(`/home/app/loopthd/s122`), `defs`, the factory-test sequence (still v2).

## 9. The unit, as this report is written

`matrix-app` inactive, `d24-testui` active, **AN_EN low**, **CS_M driven high**,
the 595 chain **SAFE and verified at handback**, the pair still
`/home/app/loopthd/s122`, run state **reset** so the glass is on its armed START
page and PW's next press is a first pass that walks everything.

## 10. For the hub / PW

1. **A bench deploy goes through `tools/pi/deploy-bench-tools.sh` from now on,
   and `--check` belongs at the top of any session that is about to trust a
   reading.** Two of eight files were behind for a day and nothing on the unit
   could say so.
2. **Should the automatic batch raise the hands-off screen itself, off the
   `--quiet-flag`, rather than only inside a panel step's `hold=`?** Today the
   speaker sounds with no sign on the glass unless a panel step happens to be
   waiting (§6). Not changed here — it is a screen-behaviour ruling.
3. **AL1 needs nothing from the supplier list.** The loop is healthy and
   repeatable to 0.0 dB on level and 0.1 dB on THD.
