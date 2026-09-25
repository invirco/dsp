provenance: AI-drafted 2026-09-25 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S110 — AL1: the speaker + MEMS acoustic loop, one row and one press

MW-D24-2 (rev C+). Replaces MM1 and SP1 with one test, one catalog row and one
button, and deploys the whole self-test set to the unit's glass.

## 1. What the test does

`AL1` in `tools/pi/d24_selftest.py`. One press, five steps:

1. **Prerequisites, named and read back.** `AN_EN` is read; if it is down the
   run raises it (PW 2026-09-24 ruling) and records that it did, so handback can
   lower it. The pair is checked for `_osc_blk_q_C1_TEST_OSC` — without a
   `DSP4_TEST_NODES=1` image the oscillator cells take writes and nothing reads
   them. One `dsp4_rxscan.py` pass says whether the MEMS lane is carrying at
   all. The TEST_OSC → speaker route is asserted and **read back through the
   image's own dispatch table**; a failed route write is `NO DATA`, never a
   measurement of the default configuration.
2. **Baseline** — tone off, one continuous 4,096-sample window on the MEMS lane.
   Taken **with the route already asserted**, because strip 20's own input noise
   reaches the speaker by the same path the tone does; a floor measured with
   `MainOn` off is not the floor the tone should be compared against.
3. **Tone** — 1 kHz into strip 20 at **−20 dBFS peak by default**, faded in over
   150 ms, three windows, faded out **in the same session**. Measured on the
   part: **0.55–0.62 s of oscillator-on time**, against a 3 s design cap.
4. **Baseline again** — proves the floor came back and the reading was the tone.
5. **Handback** — 595 chain SAFE, `CS_M` driven high, `AN_EN` lowered if this run
   raised it.

**The instrument is the S49 measurement node, not rxscan.** `C1_TEST_MEAS`
accumulates over a continuous window on the part and publishes RMS, THD+N and a
noise figure. A scatter of rxscan word reads cannot give a THD figure at all and
under-reads a peak by up to 6 dB.

### Where the microphone is: MeasChan **54**, and it is not a strip

The dispatch asked for "the strip that carries `XIN_MEMS`". There is none.
`C1_XIN_MEMS` feeds `C1_TALK_02`, a TALKBACK node whose output is a per-block
scalar that nothing downstream reads (the `Talk001Dest` fan-out gap
`dsp-unmapped.csv` records), so MeasChan 1–32 (strips) and 33–50 (buses) both
miss it. The converter-return lane codes (S69/S73,
`tools/dsp/dsp_codegen.py::TEST_MEAS_LANE_CODES`) tap the input lane itself —
the last place the converter's output is still exactly what the converter made —
and **`C1_XIN_MEMS` is code 54**. Proven on the part: `MeasChan <- 0x36` reads
back, the window serial advances, and the level tracks the tone.

### Two additions to the shared tool

`tools/pi/dsp4_s49_osc.py` gained `--ramp-ms` and `--then-off`. Both default off,
so every existing caller is unchanged.

- **`--ramp-ms`** fades `OscLevel` in equal dB steps. `OscOn 0` cuts the sine at
  whatever instant the write lands, and into a speaker that step is a click that
  lands in the next measurement window: the first tone-off baseline taken after
  an abrupt stop read **−38.15 dBFS against a settled floor of −58** — a 20 dB
  error made entirely by the harness.
- **`--then-off`** stops the tone inside the same session and prints the
  on-time. Two invocations cannot: the second one's interpreter start, link
  resync and chip check all run with the speaker still sounding, which is two to
  four seconds of tone per measurement instead of 0.6 s.

## 2. The reading is acoustic, not crosstalk

Negative control, taken by hand with the route otherwise identical:

| `Mon001Level001/002` | tone | MEMS lane RMS | THD+N |
|---|---|---|---|
| **0.0 (speaker feed cut)** | −20 dBFS, running | **−57.72 dBFS** | 0.00 dB — no fundamental |
| **1.0 (restored)** | −20 dBFS, running | **−49.10 dBFS** | −7.16 dB = 43.8 % |

With the oscillator running into the same graph and only the monitor feed
muted, the microphone reads its own floor. The 8.6 dB rise is sound out of the
speaker and back in through the mic, not electrical coupling or a DSP artefact.

## 3. Calibration — 15 runs, taken on this unit today

`d24_selftest.py --only AL1 --al1-calibrate`, three drive levels × 5 reps,
2026-09-25T13:15Z, pair `/home/app/loopthd/s109`. Full log:
`data/calibration-runs.txt` (and `data/calibration-runs-first-fit.txt`, the
earlier grid that exposed the fit bug in §3.1).

```
  drive    rep   baseline      tone        SNR     THD+N        THD+N     noise    on
  dBFS           dBFS       dBFS        dB        dB           %      dBFS     s
   -30.0     1     -57.74     -55.97       1.77     -2.16       78.014    -58.13   0.60
   -30.0     2     -54.47     -56.05      -1.58     -2.23       77.340    -58.28   0.55
   -30.0     3     -58.38     -55.86       2.52     -2.09       78.638    -57.95   0.62
   -30.0     4     -59.14     -55.21       3.93     -1.75       81.761    -56.96   0.60
   -30.0     5     -57.89     -55.26       2.63     -1.73       81.950    -56.99   0.57
   -20.0     1     -56.77     -49.12       7.64     -7.07       44.330    -56.19   0.56
   -20.0     2     -60.79     -49.54      11.25     -9.37       34.006    -58.91   0.60
   -20.0     3     -56.10     -49.19       6.91     -7.77       40.875    -56.96   0.60
   -20.0     4     -56.75     -49.41       7.33     -8.55       37.389    -57.96   0.60
   -20.0     5     -57.64     -49.65       7.99     -8.22       38.816    -57.87   0.57
   -10.0     1     -56.15     -39.98      16.17    -29.73        3.262    -69.71   0.62
   -10.0     2     -57.08     -39.98      17.10    -28.12        3.925    -68.10   0.55
   -10.0     3     -56.53     -39.99      16.53    -24.33        6.072    -64.33   0.60
   -10.0     4     -57.86     -40.00      17.86    -29.37        3.399    -69.37   0.60
   -10.0     5     -57.47     -39.98      17.48    -24.69        5.824    -64.68   0.59
  mean at  -30.0: tone -55.67 dBFS (spread 0.84 dB), baseline -57.52, SNR 1.85 dB, THD+N -1.99 dB = 79.517 %
  mean at  -20.0: tone -49.38 dBFS (spread 0.52 dB), baseline -57.61, SNR 8.23 dB, THD+N -8.19 dB = 38.931 %
  mean at  -10.0: tone -39.99 dBFS (spread 0.02 dB), baseline -57.02, SNR 17.03 dB, THD+N -27.25 dB = 4.340 %
```

**What the spread says.** The tone level is the stable quantity: 0.52 dB spread
over 5 reps at −20 dBFS and **0.02 dB at −10**. The baseline is the noisy one
(−54.5 to −60.8, it is a microphone in a room), and SNR inherits that noise.
That is why the level window does the work and the SNR threshold only carries a
label — see §4.

**−30 dBFS is below what this loop can measure.** The predicted mic level there
is −58.8 dBFS, which is the mic's own floor; the five readings scattered over
0.84 dB around it and their THD+N sat at 78–82 %, i.e. no fundamental in the
window. The lowest drive that reads on this unit today is **−20 dBFS**.

### 3.1 One fit rule, found by getting it wrong first

The first calibration excluded low points by SNR and produced a slope of
**0.790 dB/dB** instead of 0.968 — two of the five −30 dBFS points happened to
sit 4.4 and 7.0 dB above their own baseline purely because the baseline window
before them was quiet, the SNR gate let them in, and they bent the line. A line
bent that way would have made every later reading at −10 dBFS look 2 dB low.

The rule now is **THD+N ≤ −6 dB**: a point defines the line only if the
fundamental is at least half of what was in the window. It admits every −20 and
−10 point and no −30 point, by a wide margin (−1.15 dB vs −7.07 dB).
`AL1_FIT_THDN_MAX_DB`, with the reason, in the runner.

## 4. The provisional windows — one table, one command

`AL1_CAL` at the top of the AL1 section of `tools/pi/d24_selftest.py`. **Every
number is PROVISIONAL until the speaker supplier datasheet, and again until
PW's R97 amp-gain change.** They are set to catch a fault, not to grade one.

```
slope_db_per_db   0.940     mic dBFS = slope x drive + intercept
intercept_dbfs  -30.590
level_tol_db      4.000     LOW below pred - this
level_hi_tol_db   7.000     the same window's other edge; high_fails = False
snr_min_db        3.900     below this -> NO SOUND
floor_max_dbfs  -48.500     a baseline louder than this is not a floor
thdn_abs_db      -4.100     CLIP, absolute backstop
thdn_margin_db    4.900     CLIP, past what the measured SNR already explains
```

**The level window is relative, which is the point.** `pred = 0.940 × drive −
30.59`. When PW adds amp gain the intercept moves and the test still works after
one command:

```
python3 tools/pi/d24_selftest.py --section C --only AL1 --al1-calibrate \
        --pair /home/app/loopthd/s109 --no-append --no-app-restart
```

It re-measures, prints every run and the old and new tables side by side, says
what moved, and **rewrites the table in the source file** — the comments above
it are untouched. Commit the result: the table is the test.

**Verdict order and what each one is for.**

| verdict | rule | what it is really doing |
|---|---|---|
| **NO SOUND** | `SNR < snr_min_db` | a LABEL. Set low (3.9 dB) on purpose — a false NO SOUND on a loud bench is the worse error |
| **LOW** | `tone < pred − level_tol_db` | the one that actually catches a dead loop. With no tone the mic reads its floor, 7 dB or more below the line, whatever the room is doing |
| **CLIP** | `THD+N > max(thdn_abs_db, −SNR + thdn_margin_db)` | clip or any other distortion |
| **PASS** | otherwise | `PASS+` when the level is above the window's upper edge — reported, not scored |

NO SOUND **cannot say which stage**, and the test says so: the DSP graph, codec
slot 0, the AK4619 DAC (U3.22), C23/SPKR/J59.12=J42.12/C82, the TS482 (U32) and
its 5 V, SPKR0/SPKR1, the lswitch J1.6/7 FPC, the J2 lead, the speaker, the air,
the ADAU7002 and its PDM clock, and the A_I7 slot-4 lane are all in series.
First checks: the J2 speaker lead and the J13 = lswitch J1 FPC; then probe
U3.22 to split the loop in half.

### 🟡 At the safe −20 dBFS default, THD+N is a weak clip detector

The tone sits about 8 dB over the mic's floor at −20 dBFS, so THD+N cannot read
better than about −8 dB (40 %) however clean the speaker is — the calibration
shows exactly that. It becomes a real measurement at −10 dBFS (−24 to −30 dB,
3–6 %), where clipping would be obvious. The **level** check is sharp at both.

The default stays −20 dBFS as the dispatch specified. `--al1-level -10` is the
setting that makes the distortion half of the test bite, still 10 dB below the
full scale PW drove by hand today and inside the −6 dBFS hard cap. **PW's
call.** After the R97 gain change every mic level rises with it and the margin
improves on its own.

## 5. One row, one press (PW addendum 2026-09-25)

The workbook still counts two parts — 56 the mic, 57 the speaker. The bench
surface now carries **one row**. That split is implemented where it belongs:

- **`MERGED_KEYS`** in mx26 `tools/d24/build-d24-connector-status.py`. The
  workbook row list and **its numbering are untouched** — which matters, because
  93 parenthesised row references in `spec-d24-selftest.md` and the `# NNN`
  comments in the runner's ITEMS table are written against those numbers.
  `--export-keys` emits ONE key for the group at row 56's number, with a new
  `covers` column (`56 57`); **57 is a deliberate gap**.
- `build-d24-test-skin.py` reads `num`/`covers` instead of the line position,
  and collects the spec prose written against every covered row.
- The runner's `ITEMS['AL1']` is the single merged key; **`MM1` and `SP1` are
  kept as `--only` aliases** and print `--only: SP1 -> AL1` when used.
- Two cross-checks that assumed `num == position` were relaxed to what actually
  protects the lookup — unique, ascending, every workbook number covered exactly
  once — in both `load_keys` (mx26) and `check_keys` (runner).
- `scrape_spec`'s row-number ceiling was `len(keys)`, which silently dropped the
  reference to row 203 the first time a merge existed. It is now the highest
  workbook number.

**Verified by regeneration, not by reading.** Baseline catalogs were generated
from `git HEAD` of both repos in throwaway worktrees and diffed against the new
ones, keyed on `num`:

> baseline 203 rows, new 202. Nums only in baseline: **[57]**. Nums only in new:
> **[]**. **Rows differing (excluding the new `covers` column): [56]** — item,
> class, tests, remedy, explain, pass_when, manual.

Every other row is byte-identical. `D24TEST.mxs` regenerates **byte-identical to
the deployed skin** (`f517539d6a7c2b3ac72a65d35267f8da`) — the wizard has been
position-independent since S96 — so the skin was not redeployed.

## 6. Deploy (S105 procedure)

**No app rebuild.** Only `tools/` and `docs/` changed in mx26; nothing under
`src/sw/app/`. The catalog's new `covers` column is read by name
(`CsvHelper.GetValue(csv, r, col)`), so an extra column is inert to the app.

`test-catalog.csv`: **202 rows** (was 203). The unit's own log agrees:
`TestSkinStore: catalog 202 rows from /home/app/selftest/test-catalog.csv`, and
the wizard's denominator moved 203 → **202** on the glass.

All nine deployed files md5-match the repo after `scp`; rollbacks at
`*.bak-s110-pre`:

| file | deployed md5 | rollback md5 |
|---|---|---|
| `test-catalog.csv` | `2d3561fc93b60aa339b1afc1bdd947f7` | `fa4f87c3c732d44ae7d8558701d7d661` (S105's) |
| `d24_selftest.py` | `d7aaa92660d42c403474b1dc154a1cb4` | `8184cbca94d97c4a2c2443e8ad76be0b` |
| `dsp4_s49_osc.py` | `5f135a5abffb1f223e59008e55291633` | `d63c1ec40a206625b497b5271967dfe3` |
| `s89_signbit.py` | `e934400434b00d5abd8ffe5672c486fd` | `fbc9e76b3f1041e841d3e4a8a9bfc3b6` |
| `s89_set.py` | `bead35c7522632d659ff9a5a9abf2cea` | unchanged |
| `s89_slotcap.py` | `ac9c81427479435e4ebc57e92c59b981` | unchanged |
| `d24_bus_probe.py` | `1c79f4adda08ce9b5c0cee028aa2e6bb` | unchanged |
| `d24_inputs.py` | `fd25d7fa41d41a940bcdf7f534d94d88` | unchanged |
| `d24_touch_inject.py` | `96c5cfe80a67e69cd640a4c20710cc71` | unchanged |
| `/home/app/app` | `998a12bfe5daaca4dd924f9dc8673397` | unchanged — no rebuild |
| `/home/app/skins/D24TEST.mxs` | `f517539d6a7c2b3ac72a65d35267f8da` | unchanged — regenerated byte-identical |

Two of those were **stale on the unit**, not just re-copied: `s89_signbit.py`
still printed `pinctrl set 27 ip pu` (the pre-S109 CS_M wording) and
`dsp4_s49_osc.py` predated the ramp.

### On the glass, through the touch UI's own press path

Captures in `data/`, all real `MX_DRM_CAPTURE_PATH` renders of the live screen.

- `s110-row56-before.png` — **#56 Left Switch PCBA | Panel MEMS mic (talkback) +
  Speaker**, `scripted today: AL1`, one `START TEST`, 23 / 202.
- The press: `TESTSKIN: press TESTACT 'START' at 40,920` →
  `systemd-run … d24_selftest.py --local --no-soak-wait --no-app-restart --csv
  /home/app/selftest/item-status.csv --section C --only AL1` → **`AL1 PASS`**.
- `s110-row56-tile.png` — after a second press: **PASS tile**, 24 / 202, and the
  numbers line **in full**:
  `AL1  PASS  2026-09-25T13:32:01Z — PASS base -60.1 tone -49.3 SNR 10.7 dB THD+N -8.0 dB 40.0%`
- `NEXT` from #56 goes to **#58** and `PREV` comes back to #56: the merge is
  coherent to the wizard's own navigation.

Nobody else was at the panel: the log carried no `TESTACT` presses this session
but this session's own, and the injector was killed and its FIFO removed at
handback.

### The tile had to be earned

The first press produced `PASS -- drive -20.0 dBFS, baseline -57.00 dBFS, tone
-49.36 dBFS (p…` on the glass. `TestSkinStore.OneResultLine` **truncates
`measured` at 70 characters**. The line now carries exactly what PW asked for —
verdict word, baseline, tone, SNR, THD+N in dB and percent — inside that budget,
with the drive level, the predicted level, the in-window noise, the floor
afterwards and the on-time in the evidence, which the CSV keeps in full.

## 7. Unit as left

| | |
|---|---|
| `AN_EN` (GPIO26) | **`hi` at session start** (PW raised it before the hub hold) → **LOWERED to `lo` at handback**. `sudo pinctrl set 26 op dh` raises it again |
| `CS_M` (GPIO27) | `op -- pu \| hi` — DRIVEN, per S109 |
| 595 mic-gain chain | SAFE, `VERIFIED 200/200` (gain 0, phantom off, MUTED) on every handback |
| `matrix-app` | `inactive` (never started) |
| `d24-testui` | `active`, queue back to **RUNNABLE**, row #56 selected |
| CPLD | **not touched** — still `dsp4_logic.90e24de0dd4a` |
| H1S1 | not touched |
| `defs.lock` | unmoved at `defs-v2026.09.24.2` — **no contract bump owed** |

### 🟡 `/home/app/selftest/pair.conf` LEFT IN PLACE, pointing at `/home/app/loopthd/s109`

Normally a bench artefact a session removes at handback. Left deliberately:
**without it the button PW just asked for returns `NO DATA`.** The wizard's
START passes no `--pair`, the default is the signed candidate, and `TEST_OSC`'s
injection hook only exists under `DSP4_TEST_NODES=1` — the shipping image takes
every oscillator write and reads none of them. The runner prints the pair
directory and both images' md5s in its banner and carries them in AL1's
evidence, so no reading can be mistaken for the shipping pair's.
To undo: `rm /home/app/selftest/pair.conf`.

## 8. Still open

- **🔴 Thresholds are provisional.** No speaker supplier datasheet, and the R97
  amp-gain change has not happened. One command re-calibrates (§4).
- **🟢 CLOSED §10 (2026-09-25 follow-up).** THD+N at the −20 dBFS default was
  noise-limited (§4); PW's call was neither "leave it" nor "−10" but **default
  −6 / cap −3**, recalibrated on the part. See §10.
- **🔴 For the hub, in mx26 — the class line overlaps the `tests` line on the
  glass, and it is not this row's fault.** The app composes
  `row N of M · class C · workbook says S [(no run on this unit yet)] ·
  automation A · SECTION` into a 1400 px box at size 19, which holds about 147
  characters. **184 of 202 rows are over it before their first run and 112
  after** — visible in `data/s110-row56-before.png` (row 56, class 182 chars)
  and in the row-58 capture, whose class string this session never touched. The
  generator now prints the budget and the count (`CLASS_MAX`), and row 56's
  class was shortened to `panel mic + speaker` so it fits once the row has a
  result. **The real fix is a second line or an ellipsis in `TestSkinStore`'s
  `CLASS` case — a C# change and an app rebuild, which this dispatch was told to
  report rather than do.**
- **🟡 The MEMS lane still carries the pull-up tail** (`…FFF`, low 12 bits). It
  is far below the measured floor (−57 dBFS) and does not move any figure here;
  it would matter if the mic's own noise ever came down by 40 dB.
- **🟢 `12H` reads `0x00` — closed already.** S109 took that readback off the
  part with `codec4619.py --run` and no rails; nothing was owed here.
- **🟢 S109-4 closed** — the mic is on A_I7 slot 4, 0-based. The slot-5 wording
  in mx26's inventory is corrected in this session's change; `mems-slot-test.sh`
  is now redundant and is kept only as a record.
- **🟡 S105's capture drop-in** (`/etc/systemd/system/d24-testui.service.d/
  s105-capture.conf`) is still installed and was used for this session's
  captures. Left in place, as S105 left it.

## 9. Files

| repo | file | change |
|---|---|---|
| dsp | `tools/pi/d24_selftest.py` | `AL1` + `AL1_CAL` + `--al1-level/--al1-calibrate/--al1-keep-rails`; `MM1`/`SP1` removed and aliased; AN_EN handback; `check_keys` relaxed |
| dsp | `tools/pi/dsp4_s49_osc.py` | `--ramp-ms`, `--then-off` |
| dsp | `MW/D24/DSP/s110/` | this report, the deployed `test-catalog.csv`, `export-keys.csv`, `data/` |
| mx26 | `tools/d24/build-d24-connector-status.py` | `MERGED_KEYS`, `covers` in `--export-keys`, MEMS slot 5 → 4, speaker path recorded |
| mx26 | `tools/d24/build-d24-test-skin.py` | `num`/`covers`, `load_keys` rule, `scrape_spec` ceiling, `CLASS_MAX`, AL1 remedial line |
| mx26 | `docs/spec-d24-selftest.md` | MM1 + SP1 → AL1 |
| unit | `/home/app/selftest/*` | nine files deployed, md5-matched, `*.bak-s110-pre` |
| unit | `/home/app/selftest/pair.conf` | written and LEFT — §7 |

## 10. Follow-up: level (2026-09-25, PW ruling)

PW ruled the §8 open item closed the other way from what it asked about: not
−10 dBFS, but a new default of **−6 dBFS** and a new hard cap of **−3 dBFS**
(was −20 / −6). Reason: at −20 the mic sat only ~8 dB over its own floor, so
THD+N could not read better than ~−8 dB (40 %) on a healthy unit — a weak clip
detector, not a real one. PW drove the speaker to 0 dBFS by hand with no
audible or visible clipping, so −3 is safe for the 0.6 s ramped burst this test
uses.

**Recalibrated on MW-D24-2**, `--al1-calibrate` with the bracket moved to
`-12/-6/-3` dBFS (was `-30/-20/-10`), 5 reps each, same fit rule (`THD+N <=
-6 dB` defines the line — all 15 points fitted this time, 0 excluded, because
every bracketed level now reads a real tone). Raw log:
`data/calibration-runs-level-followup.txt`.

```
                         old (S110)      new (this follow-up)
slope_db_per_db            0.940              1.029
intercept_dbfs           -30.590            -29.650
level_tol_db                4.000              4.000
level_hi_tol_db             7.000              7.000
snr_min_db                  3.900             15.400
floor_max_dbfs            -48.500            -48.300
thdn_abs_db                -4.100            -16.700
thdn_margin_db              4.900             10.800
```

**What moved and why.** `snr_min_db` jumped from 3.9 to 15.4 dB because SNR at
the new, much louder default is itself much higher (~19-20 dB at −6 dBFS vs
~8 dB at the old −20 dBFS default) — NO SOUND is still a label, not the safety
net (the level window still does that work), it just labels correctly at the
new volume. `thdn_abs_db` moved from −4.1 to −16.7 dB (~14.6 %): **THD+N at
the new default is a real number, not noise** — measured 5.5-10.3 % across 5
reps at −6 dBFS (mean −21.31 dB = 8.6 %), close to but a little above PW's "a
few percent" expectation; the fit rule set the ceiling 3 dB past the worst of
those 5 readings, same rule as before, applied to real distortion instead of
mic noise this time. `slope_db_per_db` and `intercept_dbfs` moved slightly
(0.940 → 1.029, −30.59 → −29.65) because the fit line is now anchored by three
much louder points instead of three quiet ones — the line is still a straight
fit in dB, so the table still survives the next amp-gain change the same way.
`level_tol_db`/`level_hi_tol_db` did not move: the run-to-run spread at the new
levels (0.04-0.05 dB) is far inside the 4 dB floor the window already carried.

**Verified against the new windows on the part**, immediately after
recalibrating: one live `--only AL1` run at the new −6 dBFS default (no
`--al1-level` override) — `PASS base -52.6 tone -36.0 SNR 16.6 dB THD+N -24.3
dB 6.1%` — inside the recalibrated line and ceiling. (One run in between hit a
transient inter-chip link FOLD on that boot cycle, unrelated to the level
change — see `MW/D24/DSP/s110/data/` timestamps around 13:46Z; the next boot
came up CLEAN and is the PASS quoted above.)

**Redeployed, S105 procedure.** Only `d24_selftest.py` (the constants + the
recalibrated table) and `test-catalog.csv` (the AL1 remedial line, which
referenced the old "-20 dBFS default is mostly noise" reasoning and needed to
say something true) changed; the skin regenerates **byte-identical**
(`f517539d6a7c2b3ac72a65d35267f8da`) so it was not redeployed, matching the
S110 precedent. Rollback copies taken first as `*.bak-s110-level-pre`,
matching the previously-deployed md5s (`d7aaa92660d42c403474b1dc154a1cb4`,
`2d3561fc93b60aa339b1afc1bdd947f7`) before overwrite:

| file | deployed md5 |
|---|---|
| `d24_selftest.py` | `7ec3e742eecd6517bb020cfec0393fe0` |
| `test-catalog.csv` | `fd4de54e1f60aa89a43ffde47536c45a` |

`d24-testui` restarted to pick up the new catalog; the app's own log confirms
`TestSkinStore: catalog 202 rows from /home/app/selftest/test-catalog.csv` —
the row count is unchanged, only row 56's `remedy` text differs (confirmed by
the same keyed-diff method §5 used: nums only-old = only-new = {}, rows
differing = {56}). The touch-UI-to-runner wiring itself was not touched this
session (only the level constants and the AL1_CAL table) and was already
proven working through the touch path earlier the same day (`item-status.csv`
on the unit carries two AL1 PASS rows from touch presses at 13:25:53Z and
13:32:01Z, both before this redeploy); re-verification after redeploy was done
with the identical `--only AL1` invocation the skin's START button runs,
rather than a fresh synthetic touch-injection cycle, since PW was at the bench
and the injector's device-enumeration caveat (§S110) would have needed a
second `d24-testui` bounce right next to a live session.

**Unit as left**: `AN_EN` lo, `CS_M` `op -- pu | hi` (DRIVEN), 595 chain SAFE,
`matrix-app` inactive, `d24-testui` active on the recalibrated catalog,
`pair.conf` unchanged at `/home/app/loopthd/s109`, CPLD and H1S1 not touched,
`defs.lock` unmoved — no contract bump owed (no def CSV, slot map, wire table
or generated artefact changed).
