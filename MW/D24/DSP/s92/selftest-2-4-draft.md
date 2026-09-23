provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S92 — D24 self-test sections 2–4, drafted for PW review

Every remaining workbook row classified, section 2 drafted in full, sections 3 and
4 specified but **not built and not run** — they need PW's hands or PW's eye and
this dispatch had neither. The spec is extended in place at mx26
`docs/spec-d24-selftest.md`; section 1 above it is untouched.

## 1. The counts

204 rows. 36 are section 1 (specified 2026-09-22, built and run in S90); 30 are
out of scope on PW's ruling — the PSU-monitor ADC PAD0–11 and the rail headers
proven only through it. **138 rows classified here**, of which one is a proposed
correction to section 1's coverage rather than new work, leaving 137.

| code | rows | |
|---|---|---|
| `2` | 3 | the unit judges it outright once something is plugged in |
| `2+4` | 52 | presence and RELATIVE behaviour are the unit's; the graded figure is the meter's |
| `2+3` | 1 | static state with a dummy plug is the unit's; the in/out transition needs a hand |
| `3` | 24 | a press, and nothing else will do |
| `3+4` | 1 | the press half and the indicator half are different tests on one row |
| `4` | 56 | an eye or a meter, with no section-2 half worth having |
| `1` | 1 | S92-C1 |

**56 rows have a section-2 half. 26 need a press. 109 have a section-4 half.**
Every count above was checked against the generator's own export rather than
counted by hand — the 4a/4b/4c/4d partition of the 109 is disjoint and exhaustive,
and the section-4-only enumeration reproduces the export's 56 exactly.

## 2. The three things PW should look at first

### 2.1 Section 2 is 56 rows, and 47 of them are gated on one ruling nobody has made

The analog loopback — LB1–LB12, every MIC row and every output row — needs the
analog rails. `AN_EN` is CM4 GPIO26, it is `lo` on the unit as found, **a
dispatched session may not raise it** (bench note 19 / S49-15), and S49-15 is
sharper than a permission: the first `matrix-app` restart after the hub raises it
by hand drops the rails again and the app will not raise them. A dark lane reads
about −115 dBFS and the honest verdict is INCONCLUSIVE — which is exactly what
S91's loop leg printed when it met this.

So **🔴 PW-1** is the gate on the whole of section 2B. Ruled (a) "standing
authorisation, runner raises and restores", section 2 is 56 rows a dispatched
session can close with nobody in the room. Ruled (c) "only with PW present", it is
9 rows, and the other 47 are section 4 in all but name. **Nothing else in this
draft changes the plan as much as that one answer.**

### 2.2 The highest-value thing PW can do is rule the analog-output class

**🔴 PL-8.** T1–T8 and T1a have never been ruled for outputs. That is why every
Aux, Main, Center/LF and TRS row reads PARTIAL or BENCH FAULT and why none of them
can reach PASS on any amount of bench time. It blocks 17 rows in section 4b
outright and leaves LB6/LB7/LB10 in section 2 able to prove relative agreement but
never absolute correctness. +23.13 dBu ±0.5 is the standing provisional figure.

### 2.3 Section 2 can settle the U15 question with no dScope

LB5. S90 §3.6 proved the converter: all eight of U15's lanes carry a real dithered
floor at −117.7…−115.0 dBFS, the same as U39's and U60's. What is unknown is
whether the front end for panel mics 1–4 and 13–16 is present at all. A loopback
into J15–J22 answers it — the lanes rise or they do not — and **either answer is
worth having**: it either makes eight "UNTESTED – dead section" rows gradeable or
it confirms the classification. That is the cheapest open diagnostic on the sheet.

## 3. The classification rule, and the three places it was not obvious

The spec's line resolves most rows on sight. Three it does not:

1. **Fitting the plug is not "a press".** A harness is fitted once and stays; a
   press is an action inside the test, repeated per row. So a loopback cable is
   section 2 and a footswitch is section 3.
2. **Presence and grade are separate tests on one row.** 53 rows carry two codes
   for this reason. Forcing them into one bucket would either lose the cheap test
   or promise the expensive one.
3. **A test the unit could judge but the rails will not permit is section 2, not
   section 1.** §2.1.

## 4. Prerequisites

### Buildable in a future dispatch with no bench time beyond a normal boot

| # | what |
|---|---|
| 2 | `tools/pi/d24_selftest2.py` — the section-2 runner, on section 1's results contract |
| 3 | the 2B walk: `dsp4_loop_thd.sh` generalised from one cable to the harness, over `d24_inputs.py`'s XLR ↔ 595 ↔ slot ↔ strip map |
| 4 | a `DSP4_TEST_NODES=1` arm of the shipping configuration (`MW/D32/DSP/SHARC/loopthd.sh`), **staged and not flashed** |
| 6 | per-port USB power read for UA2 — sysfs only, no firmware |

Useful but inert: 3 and 4 produce nothing until PW-1 is ruled and the cables are
fitted. 2 and 6 close UA1/UA2/MJ1/PD2/TF1 as soon as a stick and a dummy plug are in.

### Needs something else first

| # | what | blocked on |
|---|---|---|
| 1 | 🔴 PW-1, the AN_EN ruling | PW. Not code |
| 5 | the H1 cable set | hardware, and one visit to fit it |
| 7 | `d24-pwr-mcu-def.csv` where the spoke can read it | S90-P7, still open. Blocks PD1's gate half and all of 4c's rail work |
| 8 | the RT1180 slot-1 card | netcard repo; the card does not exist |

Two gates on 2B that are not prerequisites so much as facts that must be stated on
every 2B row: `shipping.config` carries `DSP4_TEST_NODES=0`, so the literal
shipping image cannot measure itself and 2B proves the *configuration*; and on the
`driveall` bitstream `i_dspa[5:0] = {6{pcm_drive}}`, so the loop cable is invisible
to the DSP and 2B must run on the shipping bitstream `d02d83b3cc22`.

## 5. 🔴 Provisional limits, for PW to rule

Eleven. Four want a PW ruling, three want a first bench reading, two want a
document, one wants a defs change, one wants an errata closed. None was invented.

| # | test(s) | the number | source |
|---|---|---|---|
| PL-1 | LB3 | drive tracking ±1.0 dB per 10 dB step | **first bench reading.** S91 tracked 9.24 dB for 10 dB — **±0.5 dB would fail on evidence already in hand**, so this is set wide on purpose |
| PL-2 | LB4 | loop THD+N ≤ 0.40 % at −22 dBFS | **existing measurement** — S91's 0.32122 %, reproduced to 0.3212–0.3216 % a day later across two CPLD flashes. But that is the LOOP's figure and **nobody has ruled a loop figure is a product figure** |
| PL-3 | LB6 | Aux-to-Aux spread ±1.0 dB | **first bench reading.** S88's +9.64 dBu on AUX 1–6 and 8 suggests the set matches; no spread was computed |
| PL-4 | LB11, DS-PH | the phones class, and its load | **PW.** No load impedance is stated anywhere |
| PL-5 | LB12, DS-MJ | the mini-jack class | **PW.** Direction (input) also unconfirmed at the gate |
| PL-6 | PS-L/R/MJ/F | bounce: no second edge within 20 ms | **first bench reading.** 20 ms is a placeholder, not a measurement of these switches |
| PL-7 | PS-ENC | detents per revolution | **a datasheet** — Soundwell ES162102E2B, not looked up here |
| PL-8 | DS-OUT | the analog-OUTPUT class | **PW.** §2.2 — the highest-value ruling on the list |
| PL-9 | DS-MON, LB8 | the Monitor class | **PW.** AK4619, unbalanced — the XLR figure does not transfer |
| PL-10 | HK1, PM-IEC | per-rail specs at every header | **a defs change** — declare the rail per channel in `fw.csv` Notes |
| PL-11 | PM-9V | the pedal rail: 9 V or 12 V | **an errata ruling** — schematic says 9 V, pedal side is labelled 12 V |

## 6. What would move a row out of section 3 or 4 — named, not built

- **A2 — panel switch idle self-report.** Each panel MCU already reads its SW pins;
  a line in the `testMessage[]` S90-P2 proposes (zero new cells, zero protocol)
  could publish the whole SW idle vector. Proves the pin, the pull-up and the MCU
  read path with no finger — **not** the switch contact, so it half-tests 20 rows
  rather than closing them.
- **A3 — per-DIM-rail current sense.** A shunt and an ADC channel per rail would
  let the unit read the current step when one LED is commanded: **27 of section
  4a's 28 rows become section 2**. It is a **rev-D hardware addition**, named so it
  lands on the rev-D list. It still would not prove *which* LED lit, so PM-ENC's
  position check stays an eye.
- **A7 — power switch state through the power MCU.** PWR_SW is the power MCU's and
  it publishes over MHRX; with prerequisite 7 the switch's state is a section-2
  read and only the press stays section 3.
- **A fan tach pin** on Digital J29/J30 in rev D would make PM-FAN section 2.
- **An option card in any of opt1/opt2/opt3** turns those three link rows section 2
  the day it is fitted — the card enumerating IS the link test.

## 7. 🔴 Two proposed corrections to section 1's coverage

Neither changes a section-1 test; both change which rows section 1 is credited with.

- **S92-C1 — `Link 'hdmi-fpc'` (149) is a section-1 row.** Its criterion is "IL2 the
  link's signals present at the far end" and HD0-1 passing **is** that check — the
  same inference the spec already accepts for `Link 'hdmi-pwr'` (152), which IS in
  the coverage list. Marked `1` in the Automation column, **which is why the column
  shows 37 rows at `1` against the coverage line's 36.** The two agree once the
  coverage line is edited.
- **S92-C2 — the TEMP third of row 94 needs no plug, no press and no meter.** It is
  a value the right panel MCU reads on PA1 and reports over the panel UART section 1
  already uses for ML-P1 — section-1 work by every criterion the spec states. It is
  coded `2+4` only because it shares a workbook row with BLOWER and FAN, which do
  need an eye. Hence TF1 sits in 2A's shape, not 2B's.

## 8. The workbook

`tools/d24/build-d24-connector-status.py` gains an **Automation** column (P) —
`1`, `2`, `3`, `4`, `2+4`, `2+3`, `3+4`, `—` per row — a section roll-up block on
the Summary sheet with a live `COUNTIF` per code and a one-line meaning, and a
Notes paragraph saying how to use it. `--export-keys` gains a fifth column
`section`; `board` and `item` stay columns 1–2, so the spoke's results contract is
unchanged. STAMP bumped to 12:20 BST 2026-09-23.

**Nothing else moved, and that was checked rather than assumed.** Both generators
run against S90's `item-status.csv`, cell for cell over the Connectors sheet,
columns A–O: **zero differences**, 204 rows either way, `merged 58 tests over 36
items` from both. `--export-keys` board+item identical row for row against the
pre-change export, 204 keys. `tools/pi/d24_selftest.py --keys` still accepts the
five-column table (`key check: 36 distinct items, all present in the export`,
exit 0).

The one intended difference is the 37-vs-36 at code `1` — S92-C1, §7.

## 9. What this dispatch did not do

- **It did not build a section-2 runner.** Prerequisites 2, 3, 4 and 6 are named
  as buildable; none was built. The dispatch asked for a draft for PW review, the
  way section 1 was drafted before it was built.
- **It did not run anything on the unit.** No SSH to MW-D24-2, no boot, no CPLD
  flash, no 595 write, no AN_EN. The unit is as S91 left it.
- **It did not touch `defs`, any generated artifact or `defs.lock`.** No contract
  input or output moved, so no contract note is due under
  `release-notes-contract-convention.md`.
- **It did not rewrite section 1.** The spec's first 110 lines are byte-identical.

## 10. Two things the next session will trip on

**The workbook generator cannot run in mx26 as found.** `defs` is an uninitialised
submodule there and its recorded URL is `https://github.com/invirco/defs.git`,
which fails with `could not read Username for 'https://github.com'` — the token is
dead. It needs the SSH remote, which works:

```
git -C ~/mx26 config submodule.defs.url git@github.com:invirco/defs.git
git -C ~/mx26 submodule update --init defs
```

**And `openpyxl` is not installed on this machine**, system-wide or in any venv —
a scratch venv was used for this dispatch. Both were worked around rather than
changed: mx26 is left exactly as found, submodule deinitialised and the local URL
override removed.

## 11. Where the work landed

- mx26 `docs/spec-d24-selftest.md` — sections 2–4 appended, section 1 unchanged.
- mx26 `tools/d24/build-d24-connector-status.py` — the Automation column.
- dsp `MW/D24/DSP/s92/selftest-2-4-draft.md` — this report.

**A note on the repo split, stated rather than glossed.** Both deliverables live
in mx26, because that is where the spec and the workbook generator live and the
dispatch asked for the spec to be extended *in place*. S90's dispatch had told
this spoke mx26 was read-only; S92's asks it to author content there, so this
session committed and pushed mx26 as well as dsp. If the hub wanted the draft
staged in the spoke instead, the commit is a single one and easy to move.
