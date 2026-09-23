provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S99 — the factory-test scope ruling, applied

PW 2026-09-23 (`mx26 docs/decision-mx26-mandates.md`): *"for first pass factory test... firmware number is not
important, we just want to test if functional and responsive hardware is present (except for audio, because
performance could be related to function)."*

**Outcome in one line: one test was demoted, it holds two workbook rows, and both now read PASS on the unit —
`#102` and `#203`. The score moved 19 → 21 of 204, witnessed on the glass.** The other sixty-odd tests in
`docs/spec-d24-selftest.md` were read one at a time against the ruling and every one of them stays gating; seven
of them carried a *version-equality clause inside an otherwise-gating criterion*, and those clauses — not the
tests — are what the spec now records as informational. Three calls are flagged 🔴 rather than made.

---

## 1. What "the real work" turned out to be

The dispatch asked for a classification pass over every test and anticipated that `ML2` might not be alone. It is
alone as a **whole test**, and saying so plainly is the finding: applying the ruling by searching for "version"
would have demoted six or seven more and been wrong every time.

What the pass actually turned up is a second, subtler shape. **Seven spec criteria state a version/id equality
that the runner does not, and never did, put in its verdict.** S96 found the same class of divergence in the
remedial text; this is the criterion column. In each case the spec promised a gate the code does not apply, so
the ruling does not change behaviour there — it settles which half of the sentence was ever load-bearing, and the
spec now says so:

| test | the spec said | the runner's verdict actually is |
|---|---|---|
| `ML-M` | "ML1 PASS; **version reads**" | `ML1 == PASS`. MH1's firmware is not in `~/build-h1s1` and no version is read at all |
| `ML-P1` / `ML-P2` | "id answers, **matches the fw.csv MCU (STM32F030R8)**" | the `S_TEST` line answered. fw.csv declares a part number nothing on the wire repeats — the runner's own evidence string says so |
| `DR2` | "both SHARCs boot and answer; **ids equal the shipping pair**" | `BOOT_STAGE >= 7` on both. `BUILD_ID` is printed in `measured` |
| `AS-DSPA` / `AS-DSPB` | "**build id cell equals the shipping chip1 image**" (one of "all three") | `CHIP_ID` + advancing heartbeat + `BOOT_STAGE >= 7`. `BUILD_ID` is evidence |
| `DC2` | "**id matches the declared part**" | `CHIP_ID == the select number` — and that is the ruling's own example of a wiring check wearing an id |

`AS-CPLD` is the exception that proves the pattern: it is the one test whose id-equality clause **is** in the
verdict (`design_id == 83b3cc22`). It was left gating and flagged — see 🔴 S99-3.

## 2. The classification

The full per-test table is now in `mx26 docs/spec-d24-selftest.md`, section **"Gating vs informational"**, so it
lives beside the tests rather than only in a session report. Its machine-readable half is `INFORMATIONAL_TESTS`
in `tools/d24/build-d24-test-skin.py`, which writes the new `informational` column of `test-catalog.csv`.

### Reclassified: 1 test, 2 workbook rows

| | |
|---|---|
| test | **`ML2`** — read the H1S1 firmware-version cell |
| rows | **#102** `DSP PCBA (H1S1 MCU wiring) \| H1S1 MCU (STM32U575) link`; **#203** `Assemblies \| S MCU H1S1 (STM32U575)` |
| old behaviour | `ML1 PASS` + `ML2 NO DATA` → row **PARTIAL**, permanently: H1S1 publishes no version cell at all (its whole local cell table is `Sys001Enc001/Skin001/Test001/Test002`), so `ML2` could never be anything but NO DATA on any unit |
| new behaviour | the row rolls up over `ML1` alone → **PASS**. `ML2` still runs, its NO DATA is still printed, tagged `[informational — does not gate]`, and the identity block says `ML2 informational, does not gate the verdict` |
| why | it reads a firmware version and nothing else. `ML1` has already proved the same part, on the same wire, is present and answering three times identically. `ML2` asks an unrelated second question whose answer cannot bear on whether the hardware shipped correctly — PW's own case in point |

### Everything else: gating, with the reasoning stated

The three-way split the ruling implies, applied to all of section 1 and to the specified-only sections 2–4:

- **Presence/response — every other test in the spec.** `HD0-1` (EDID manufacturer + product: the right display is on the FPC),
  `HD0-2`, `HD-PWR`, `NW1`–`NW4`, `AS-CM4`, `USB-HUB`, `ML1`, `ML-M`, `ML-P1/P2`, `ML-B0`, `DC1`×8, `DC2`×8,
  `DR1`, `DR2`, `MC1`–`MC3`, `CC1`, `CC2`, `AS-DSPA/B`, `AS-CPLD`, `AS-ADC`, `AS-PWR`, `UA1`, `UA2`, `PD1`, `PD2`,
  `MJ1`, `TF1`, `SL1`, every `PS-*`, every `PM-*`, `HK1`, `HK1-use`, `IL-OPT`, `IL-D32`, `IL-PH`.
- **Audio, untouched by the ruling — 21 test ids.** `LB1`–`LB12`, `DS-IN`, `DS-OUT`, `DS-MON`, `DS-TB`, `DS-MJ`,
  `DS-PH`, `AS-DAC`, `MM1`, `SP1`. Not one number in section 4b or in any `LB*`/`T*` criterion was touched.
- **Informational — 1 test.** `ML2`.

Two judgement calls inside that list are worth stating because they could plausibly have gone the other way:

- **`CC1` stays gating** even though its PASS value (`05H == 0xBB`) is the value the shipping image writes. It is
  not a build-string comparison: it is a register read back **through CS_C, through the codec, over SPI**, so a
  PASS proves the part is present, selected, and holding state. What the ruling demotes is a match that proves
  nothing about whether the part works; this one proves little else.
- **`DC2` stays gating**, and the dispatch was right to ask for it to be checked rather than assumed. Its evidence
  string carries the spec's caution that "fw.csv Dsp*n* declares a pin and net, not a part number, so there is
  nothing on the wire to match it against" — but that describes a claim `DC2` *declines* to make. Read the code:
  `ok = (cid and int(cid, 0) == n)`. The verdict is that the part answering behind select *n* identifies itself as
  chip *n*. `BUILD_ID` and the S82-signed build triple are carried in `measured` and are not in the verdict at
  all. That is an assembly check, and it stays.

## 3. 🔴 Three calls left to PW

Flagged rather than guessed, as the dispatch asked. All three are also recorded in the spec beside the table.

- **🔴 S99-1 — `AS-CM4` gates on `systemctl is-active`, a software-state clause inside a hardware test.** Its
  other three criteria (throttled `0x0`, temp < 70 °C, core volts in window) are the CM4's own health and are
  plainly gating. "The product app is running in either role" is neither a hardware-presence check nor a firmware
  *version* check; it is closest in shape to what the ruling demotes. Demoting the whole test would throw the
  throttle and temperature gates away with it, and the mechanism is per test, not per clause — so `AS-CM4` was
  **left gating**. If PW wants that clause out of the verdict it is a two-line change in `t_ascm4` and the
  reading stays in `measured` either way.
- **🔴 S99-2 — this ruling does not unstick the rows held by a test that can never run, and four such tests are
  presence checks.** `ML-B0` (no BOOT0/NRST drive exists on H1S1), `AS-DAC` (no TEST_OSC on the shipping image),
  `AS-PWR` (no reader for the power MCU's words) and `SP1` (no TEST_OSC→SPKR route in the topology) are
  presence/performance checks by every reading of the ruling, so they stay gating — and all four are structurally
  NO DATA. Counted on the unit after S99: **rows 126 and 127 still read PARTIAL** for exactly the shape PW
  objected to on `#102` — a real PASS (`ML-P1`/`ML-P2`) held amber by a NO DATA that no unit can ever satisfy —
  and **rows 57, 143, 198 and 201 read UNTESTED** because their only test is one of those four. Six rows, for a
  reason about *capability*, not about this unit. That is S96's `can_fail` catalog flag, still unbuilt, and it is
  a different ruling from this one: `ML-B0` is a wiring check that cannot run, not a version check. Said out
  loud because `#126` sits two screens from `#102` and looks identical to it.
- **🔴 S99-3 — `AS-CPLD`'s id half IS in its verdict, and relaxing it would relax a standing bench rule.** The
  criterion is `design_id == 83b3cc22` **and** zero `BLK_OVERRUN` delta. Read as a build-identity match it is what
  the ruling demotes; read as "the right CPLD image is loaded, without which no DSP measurement taken afterwards
  means anything" it is a precondition S91 already imposes (2B runs on the shipping bitstream, never on
  `driveall`). Left **gating, unchanged**, rather than have this session quietly loosen that rule. If PW rules
  the id half informational, the criterion becomes "the CPLD answers a design id" and the id stays in `measured`.

## 4. The mechanism

A row's verdict is now rolled up over its **gating** tests only; informational ones are shown and marked.

| | |
|---|---|
| classification | `INFORMATIONAL_TESTS` in `tools/d24/build-d24-test-skin.py` — one entry, with its reason in the source. Checked in `build_catalog()` against the runner's own `SECTION` ids, so a typo exits rather than silently gating a row on a test that does not exist |
| carried by | a new `informational` catalog column: the subset of that row's `tests` that does not gate. A catalog written before S99 has no such column, which reads as "every test gates" — the pre-ruling behaviour |
| roll-up | `TestSkinStore.StatusOf` skips informational results. **A row whose only results are informational falls back to the workbook's declared status**, exactly as a row with no results does — an informational PASS is not a factory PASS any more than an informational NO DATA is a factory hold. `IsDeclaredOnly` agrees, so such a row still says "no run on this unit yet" |
| score | `Tally` is a function of `StatusOf` and needed no second opinion; it moved with the roll-up and is pinned by a test that would catch it acquiring one |
| detail page | informational lines sort **last**, whatever their verdict — they are the only lines that cannot explain the colour above them — and each carries `[informational — does not gate]`. The header counts them separately (`1 PASS · 1 informational`), and the identity block names them |
| an informational FAIL | printed as loudly as any other line and still does not gate. Pinned by a test |
| preview tool | `tools/d24/preview-d24-test-skin.py` ports all of the above, so the offline render still reproduces the unit exactly |

**Tests: 162/162 green** (158 before, 4 new): the demotion, an informational FAIL, a row with only informational
results, and the score counting the same way the row does.

## 5. Live on MW-D24-2

`app@192.168.1.219`, binary `f93fa5d352011317fa8a03795876d71c` md5-matched against the local publish, catalog
`bce747fb759bd05a5bd7c9f345315019` md5-matched, skin **unchanged and not redeployed** (regenerated
`D24TEST/skin.csv` is byte-identical to S98's). Presses went in through `d24_touch_inject.py` on `/dev/uinput`,
**not** the ILITEK panel — they prove the skin, the store and the catalog, and nothing about the touch hardware.

| | before (S98 build) | after | capture |
|---|---|---|---|
| score | `19 / 204` · 4 FAIL · 181 not resolved · 17 runnable now | **`21 / 204`** · 4 FAIL · **179** not resolved · **15** runnable now | `live-head-score.png` |
| **#102** H1S1 MCU link | PARTIAL | **PASS**, `2 tests cover this row — 1 PASS · 1 informational`, `ML2 NO DATA … [informational — does not gate]`, identity line `ML2 informational, does not gate the verdict` | `live-102-pass.png` |
| **#203** S MCU H1S1 | PARTIAL | **PASS**, identically | `live-203-pass.png` |
| **#126** Right panel MCU link | PARTIAL | **PARTIAL, unchanged** — `ML-B0 NO DATA` still holds it, no informational tag anywhere on the page. The control case: the demotion did not leak to a row whose NO DATA test is a wiring check | `live-126-still-partial.png` |
| **#129** Ethernet | FAIL | **FAIL, unchanged** — 4 tests, 2 FAIL, remedial text intact | `live-129-still-fail.png` |

The two rows that passed also **left the RUNNABLE queue** (17 → 15 rows), which is the roll-up and the queue
agreeing without being told to.

Predicted offline from the unit's own catalog and results file before deployment — `pass=21 fail=4
unresolved=179 runnable=15` — and the glass then read the same four numbers. The two artefacts were computed
independently: one by `preview-d24-test-skin.py` on this machine, one by the app on the unit.

## 6. Files

| repo | file | change |
|---|---|---|
| mx26 | `docs/spec-d24-selftest.md` | new "Gating vs informational" section with the full per-test table and the three 🔴 calls; six criterion cells corrected where the spec stated a version gate the runner does not apply |
| mx26 | `tools/d24/build-d24-test-skin.py` | `INFORMATIONAL_TESTS`, the `informational` catalog column, the runner-id check in `build_catalog()` |
| mx26 | `src/sw/app/Core/TestSkinStore.cs` | `Entry.Informational` / `IsInformational`; `StatusOf` gates on gating tests only and falls back when there are none; `IsDeclaredOnly`; `ResultLines` tags and re-ranks; the `TESTS` identity line |
| mx26 | `src/sw/app.Tests/TestSkinWizardTests.cs` | 4 new tests; `Header`/`Row` carry the new column |
| mx26 | `tools/d24/preview-d24-test-skin.py` | the same roll-up, tagging and ranking, ported |
| dsp | `MW/D24/DSP/s99/` | this report, the catalog as deployed, the results file as handed back, five captures |

Nothing in `defs/` was touched and `defs.lock` did not move. `tools/pi/d24_selftest.py` was **read, not changed**:
the ruling is about what a result gates, not about what the runner measures.

## 7. Unit left as

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` inactive — test mode, as S97/S98 left it |
| app binary | `f93fa5d352011317fa8a03795876d71c`, md5-matched; rollback at `/home/app/app.bak-s99-pre` (`669e3b93…`, the S98 build). `app.bak-s98-pre` deleted to hold the binary count at two |
| catalog | `bce747fb759bd05a5bd7c9f345315019`; pre-S99 at `test-catalog.csv.bak-s99-pre` |
| skin | `/home/app/skins/D24TEST.mxs` `f517539d…`, **untouched** — the regenerated skin is byte-identical |
| instrumentation | capture drop-in removed, `systemctl show d24-testui -p Environment` back to the two shipped variables; injector destroyed; every `s99-*` file removed from the unit |
| rails | `AN_EN` (GPIO26) `lo` throughout — never raised. `CS_M` (GPIO27) `ip pu` |
| hardware | no DSP boot, no 595 write, no CPLD access, no `matrix-app` start; `item-status.csv` unchanged by this session |
| rootfs | 88 % (790 M free) |
