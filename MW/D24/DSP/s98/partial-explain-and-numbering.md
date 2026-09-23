provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S98 — a PARTIAL row explains itself, and the number on screen is a number you can look up

Two bugs PW found live-testing the S97 wizard on MW-D24-2, both fixed and both
proved on the unit.

- **A row covered by several tests showed one of them.** `#102 H1S1 MCU link`
  reads PARTIAL because `ML1` passes and `ML2` returns NO DATA; both are written
  in the same second, and the newest-stamp rule broke the tie in favour of the
  PASS — the one line that does not explain the colour. The page now prints
  **every** test that covers the row, non-PASS first.
- **The number on screen could not be looked up.** `#102` looked up as line 102
  of `--export-keys` gives `P1 pedal (rev B) | Pedal link + 9 V`. **The
  orderings were never wrong** — all 204 rows of the export, the deployed
  catalog and the runner's `ITEMS` table agree, row for row. The number simply
  was not *in* either artefact, so looking it up meant counting data lines in a
  file with a header, which is off by one every time. The number is now a
  printed column in both.

A third defect turned up on the way and is fixed with them: on the 82-character
identity rows the `board | item` line wrapped and its second half landed on top
of the class line — on the one control whose whole job is to say which item is
on screen.

---

## 1. Bug 1 — the roll-up is the worst verdict, so showing one result is showing the wrong one

### 1.1 What was happening

`TestSkinStore.LastResultLine` took the newest row per item and printed it:

```csharp
var newest = list.OrderByDescending(r => r.Stamp, StringComparer.Ordinal).First();
return $"last: {newest.Test} {newest.Verdict} at {newest.Stamp} — {m}";
```

A row's status, though, is the **worst** of its tests — that is the workbook's
merge rule and the store applies it. So on any multi-test row the status and the
one printed line answer different questions, and on `#102` they disagreed
outright: `ML1 PASS` and `ML2 NO DATA` carry the *same* stamp
(`2026-09-23T19:16:18Z` on today's run), `OrderByDescending` is not stable on a
tie, and the page showed the PASS.

`ML2`'s NO DATA is not a fault. H1S1 publishes no firmware-version cell at all —
its whole local table is `Sys001Enc001` / `Sys001Skin001` / `Sys001Test001` /
`Sys001Test002` — so `ML2` is one of the ten rows S96 already found can never
turn red. That is exactly the kind of thing the page has to say out loud, and it
was the thing being hidden.

This is not an edge case. Of the 204 catalog rows, **17 are covered by two
tests, one by three and one by four**; every one of them could print a line that
did not match its own colour.

### 1.2 What it does now

`ResultLines` replaces `LastResultLine`. Under the instruction, the page prints
one line per test:

```
2 tests cover this row — 1 not passing · 1 PASS:
   ML2  NO DATA  2026-09-23T19:16:18Z — no H1S1 version cell; host side H1S1.shex 5dc7acdea…
   ML1  PASS     2026-09-23T19:16:18Z — Sys001Test001 (5414) x3 = ['0x00', '0x00', '0x00'], …
```

- **FAIL first, then everything else that is not a PASS, then the passes**, test
  id breaking the tie so the order is stable between repaints rather than
  following the file. A technician reads for what is not green.
- **A scripted test with no recorded row gets a line of its own** — `ML-B0
  NOT RUN — scripted for this row, nothing recorded on this unit`. A row can sit
  short of green because a test never ran, and that must not look like no reason
  at all.
- The count header appears only when more than one test covers the row; a
  single-test row prints its one line as before.
- Measured text is trimmed to 70 characters so a line never wraps. The full
  value is in `item-status.csv` and in the run log.
- With `DETAIL` on the block goes away with the instruction it sits under, the
  same rule `SHORT` and `REMEDY` already follow.

### 1.3 Where it lives on the page

The one-line summary was at the bottom of the run block (y 806, 32 px). Four
result lines do not fit there, so the block moved into the body, under the
instruction and above the remedial line — the only place on the page with real
room — and the run note took the space it left.

| | before | after |
|---|---|---|
| instruction `SHORT` | 300, h 190, size 36 | 300, h 84, size 32 — two lines |
| results | — | 392, h 104, size 19 — up to five lines |
| remedial `REMEDY` | 495, h 220, size 26 | 524, h 180, size 23 — up to six lines |
| last result | 806, h 32 | gone |
| run note `RUNNOTE` | 840, h 66 | 806, h 100 |

The heights are set against `DrawWrapped`'s own last-line rule — it emits any
line whose *top* is inside the box, so a box overruns by up to one line height —
and against the worst row on the unit, `#129 Ethernet`: two instruction lines,
five result lines (four tests plus the header) and six remedial lines (691
characters, two failed tests' paragraphs). The first attempt at this layout
clipped that remedy mid-sentence; `live-129-ethernet.png` is the one that does
not.

Two generator gates stop the next such clip being discovered on a factory unit
instead of at build time: `SHORT_MAX` (170 characters, longest today 148) and
`KEY_MAX` (see §3).

### 1.4 Proved live on MW-D24-2

Unit `app@192.168.1.219`, binary `669e3b935ba61606426824c0786ac146` md5-matched
against the local publish, skin `f517539d6a7c2b3ac72a65d35267f8da`. Presses went
in through `/dev/uinput` (`d24_touch_inject.py --serve`) exactly as in S94–S97:
**they prove the skin, the store and the runner, and nothing about the ILITEK
panel or its cable.** That is still PW's finger.

| capture | row | what it shows |
|---|---|---|
| `live-102-before-run.png` | `#102 H1S1 MCU link` | the exact item from the bug report — `ML2 NO DATA` **above** `ML1 PASS`, the tie no longer hiding the reason |
| `live-102-after-run.png` | `#102`, after a real `ML1,ML2` run | both lines re-stamped `19:16:18Z` by the run started from this page; the store's own log records `#102 finished at 20:16:25 — PARTIAL` |
| `live-126.png` | `#126 Right panel MCU link` | the second multi-test PARTIAL the dispatch named — `ML-B0 NO DATA` above `ML-P1 PASS` |
| `live-129-ethernet.png` | `#129 Ethernet (RJ45)` | the worst row: four tests, `2 FAIL · 1 not passing · 1 PASS`, `NW2`/`NW3` FAIL first, `NW4` NO DATA, `NW1` PASS last, and the whole remedial paragraph under it |

The `#102` run was a real section-B run: it stopped the mixer (already down in
test mode), booted the DSP pair, passed the inter-chip link gate `OVERALL:
CLEAN`, and handed back with `SAFE image: VERIFIED 200/200`, `CS_M: 27: ip pu`,
`AN_EN: 26: … lo` and `matrix-app: left stopped (--no-app-restart)`. Verdict
`PARTIAL` again, for the right reason, and now with the reason on the glass.

`item-status-as-handed-back.csv` is the results file as it stands after that run.

---

## 2. Bug 2 — the number was correct and unlookupable

### 2.1 The reproduction

```
$ sed -n '102p' keys.csv          # "#102" read off the wizard
P1 pedal (rev B),Pedal link + 9 V,control,UNTESTED – no fixture,2+4

$ sed -n '103p' keys.csv          # the row actually being tested
DSP PCBA (H1S1 MCU wiring),H1S1 MCU (STM32U575) link,mcu link,UNTESTED – no fixture,1
```

A pedal connector instead of an MCU link — "a completely different item", as the
dispatch put it. The cause is the header line: the display number is the row's
position among the **data** rows, and the file's line 102 is data row 101.

The same trap was in the workbook PW actually reads. `d24-connector-status.xlsx`
had its header on sheet row 1, so item 102 sat on spreadsheet row 103, and
neither sheet nor export carried a number column to check against.

### 2.2 The orderings were never different — that was checked, not assumed

The dispatch asked whether the wizard's imported `ITEMS` table orders or counts
rows differently from the hub's canonical export. It does not:

| comparison | result |
|---|---|
| `--export-keys` (204 rows) vs the `test-catalog.csv` deployed on the unit | **0 mismatches** — same order, and every `num` equals its position |
| the 28 workbook row numbers written into `d24_selftest.py`'s `ITEMS` comments | **all 28** name the item at that position in the export |
| the runner's 36 distinct `(board, item)` keys | all present in the export, verbatim |
| the catalog regenerated today vs the one on the unit | byte-identical |

So this was not a real divergence papered over — there was nothing to diverge.
The failure was that a correct ordering had no number printed anywhere a reader
could match against.

### 2.3 The fix: print the position, and check it

**`build-d24-connector-status.py`**

- `--export-keys` now writes `num,board,item,class,status,section`. `num` is the
  1-based position and is the number the wizard prints.
- The xlsx `Connectors` sheet gains `#` as column A with the same number. The
  status-colour rule, the freeze pane, the auto-filter and every `Summary`
  formula moved one column with it (board `A→B`, status `E→F`,
  PASS/FAIL/NO DATA `F,G,H→G,H,I`, Automation `P→Q`); the regenerated workbook
  was read back and each checked. `STAMP` bumped to `21:10 BST 2026-09-23`, and
  the Notes sheet carries a line saying what the `#` column is and is not.

**`build-d24-test-skin.py`**

- `load_keys()` requires the `num` column and **exits** if any row's `num` is not
  its position, naming the first disagreement. A pre-S98 export is refused with
  the command to re-run.

**`d24_selftest.py --keys`** (dsp)

- still checks every key is present, and now also checks `num` against the
  position **and** parses this file's own `# NNN` comments, verifying each names
  the item at that position. They were hand-typed and nothing checked them
  before. Exercised both ways: clean today (`36 distinct items … 28 row numbers
  in the table match their position`), and against a deliberately stale comment:
  `# 101 says 'H1S1 MCU (STM32U575) link', the export has 'Pedal link + 9 V'`.

**On screen** — the class line under the big `#102` now opens with
`row 102 of 204`, so the number reads as a place in a list rather than as an
identity. `board | item` remains the identity, as §1.1 of the spec has always
said; nothing is keyed on the number.

The workbook on PETERBC is **not** updated by this session — regenerating it is
`build-d24-connector-status.py --status <item-status.csv>` and the copy step is
PW's (the OneDrive fork-avoidance dance in the generator's docstring).

---

## 3. Found on the way — the identity line was wrapping onto the class line

`live-126-identity-wrap-before.png` shows it: `Right panel MCU link (fw.csv
SW_RIGHT)` did not fit the 1180 px `KEY` box at size 34, so `SW_RIGHT)` wrapped
to a second line and drew on top of `class mcu link`. The longest key is 82
characters (`#52`). `KEY` is now size 28 in a box that admits exactly one line,
and the generator refuses to build a key longer than `KEY_MAX` (84 characters).
`live-126.png` is the same row afterwards.

---

## 4. Tests

`dotnet test src/sw/app.Tests` — **158 passed, 0 failed** (153 before; five added).

| test | pins |
|---|---|
| `EveryTestCoveringARowIsShown_NotJustTheNewest` | `#102` verbatim, same-second tie: both lines present, `ML2` above `ML1 PASS`, the count header |
| `FailComesAboveEveryOtherVerdict` | `#129` verbatim: five lines, `2 FAIL` in the header, `NW2 NW3 NW4 NW1` in that order |
| `ATestThatNeverRanIsPrintedRatherThanMissing` | a scripted test with no recorded row prints `NOT RUN`, above the PASS |
| `TheDetailViewTakesTheResultsBlockWithTheInstruction` | `RESULTS` is empty with `DETAIL` on |
| `TheClassLineSaysTheNumberIsAPosition` | `#102` and `row 102 of …` |

One existing helper was wrong and is fixed with them: the tests' `Row()` builder
wrote a multi-test `tests` cell unquoted, so `"ML1,ML2"` silently became two
columns and every field after it shifted. No test had used a multi-test row
before.

---

## 5. What changed

| repo | file | change |
|---|---|---|
| mx26 | `tools/d24/build-d24-connector-status.py` | `num` column in `--export-keys`; `#` column A in the workbook + every shifted reference; stamp; Notes line |
| mx26 | `tools/d24/build-d24-test-skin.py` | `load_keys` verifies `num`; results block in the body; `SHORT_MAX` / `KEY_MAX` gates; one-line identity |
| mx26 | `src/sw/app/Core/TestSkinStore.cs` | `ResultLines` replaces `LastResultLine`; `RESULTS` field (`LAST` kept as an alias); `row N of M` on the class line |
| mx26 | `src/sw/app/App.axaml.cs` | `MX_DRM_CAPTURE_MS` — re-save the render capture every N ms, so a screen reached by pressing `NEXT` can be witnessed at all (§6) |
| mx26 | `tools/d24/preview-d24-test-skin.py` | the same results block and class line, ported |
| mx26 | `src/sw/app.Tests/TestSkinWizardTests.cs` | five tests; the CSV-quoting fix in `Row()` |
| mx26 | `docs/spec-d24-test-skin.md` | §1.1 rewritten, §2.5 added (old §2.5 → §2.6), layout table, §10 |
| mx26 | `docs/spec-d24-selftest.md` | the `num` column in the results contract and the row-number convention |
| dsp | `tools/pi/d24_selftest.py` | `check_keys` verifies positions and the `ITEMS` comment numbers |
| dsp | `MW/D24/DSP/s98/` | this report, the export, the catalog and skin as deployed, the results file as handed back, five captures |

---

## 6. `MX_DRM_CAPTURE_MS`, and a note for the next session

S97 established that `MX_DRM_CAPTURE_PATH` renders the live view tree to a PNG,
correcting the spec's claim that this unit cannot be screenshotted. It fired
**once**, at startup, so it could only ever show the page the app opens on — and
the whole wizard past the queue head is reached by pressing `NEXT`. Setting
`MX_DRM_CAPTURE_MS` re-saves the same file on that period (minimum 250 ms), so
the file always holds what is on the panel now. It is off unless the variable is
set, and it was set on the unit through a systemd drop-in for this session only.

Reading the file needs one care: the save is not atomic, so a copy can catch it
at zero bytes. Sample the size twice and copy when it is stable.

---

## 7. Unit left as

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` inactive — test mode, as S97 left it |
| app binary | `669e3b935ba61606426824c0786ac146`, md5-matched on the unit; rollback at `/home/app/app.bak-s98-pre` (`dc558ff1…`, the S97 build) |
| skin | `/home/app/skins/D24TEST.mxs` `f517539d6a7c2b3ac72a65d35267f8da`; pre-S98 at `D24TEST.mxs.bak-s98-pre` |
| catalog | unchanged — today's regeneration is byte-identical to the deployed file |
| capture drop-in | removed; `systemctl show d24-testui -p Environment` is back to the two shipped variables |
| touch injector | `--serve` process killed, `/tmp/tap` removed |
| hardware | last run's handback: `SAFE image: VERIFIED 200/200`, `CS_M: 27: ip pu`, `AN_EN: 26: … lo`. AN_EN never raised this session |
| rootfs | 87 % (890 M free); the superseded `app.bak-s97-pre` was deleted to hold the binary count at two |
