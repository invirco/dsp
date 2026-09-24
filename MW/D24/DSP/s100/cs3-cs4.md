provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S100 — CS3/CS4 are SPI_RDY, and SPI_RDY has a real test

PW, on rows 105/106 sitting at a permanent NO DATA: *"if it's not a fail, then shouldn't it be a pass? as there
is nothing to resolve"*.

**Outcome in one line: the answer was neither — the spec asked the wrong question of a real signal, and the
right question has a real PASS. `DY1-RDY1` and `DY1-RDY2` both read PASS on MW-D24-2, rows 105 and 106 move
UNTESTED → PASS, score 21 → 23 of 204.** Checking the other six CS rows the same way found **two more** with the
same defect — CS7 and CS8 are not DSP chip selects either — and one mechanism bug that would have hidden the new
result: a renamed test's old results went on gating the row it no longer describes.

---

## 1. What SPI_RDY actually is, and why the old read proved nothing

`CS3`/`CS4` leave the DSP4 card as **`PB_05` on each SHARC — `SPI2_RDY`** — and land on CM4 `GPIO8` (chip 1) and
`GPIO12` (chip 2). `fw.csv` calls them `Dsp3`/`Dsp4` because they occupy H1S1 pins `B14`/`B13` on nets `CS3`/`CS4`,
which is how the workbook came to call them chip selects. They are not selects in either direction.

`spi2_init()` (`MW/D32/DSP/SHARC/src/dma_config.c`) muxes `PB_05` to SPI2 (`PORTB_MUX.MUX5 = 1`, `PORTB_FER` bit 5)
and configures the receive channel `FCEN=1, FCPL=1, FCWM=1`. So at runtime the pin is a **push-pull output**:

| | |
|---|---|
| HIGH | ready — the RX FIFO has room |
| LOW | deasserted — the FIFO is ≥ 75 % full, stall the host |
| high-Z | the part is in reset, or has not reached `spi2_init` |

Two facts make the old test unreadable and the new one decisive.

1. **Each part carries a 10K pulldown to GND on that net** (R34 on DSPA, R22 on DSPB), so an **undriven line rests
   LOW**. `FCPL=1` (active-high) is chosen *by the board* to match it — the HRM pairs pull-up with `FCPL=0` and
   pull-down with `FCPL=1`.
2. **A bare `pinctrl get` inherits whatever pull the CM4 pin was left in**, and on BCM2711 `GPIO8` powers up pulled
   **UP** while `GPIO12` powers up pulled **DOWN**. That is the whole reason the S99-era evidence reads
   `8: ip pu | hi` and then says *"the level does not prove a part is alive either"*: on GPIO8 it genuinely did not.
   On GPIO12 the same transcript already contained the proof and nobody could tell, because the two lines were read
   under different conditions and reported as one.

**Force the CM4's own pull DOWN and the ambiguity is gone.** With 10K to GND on the card *and* the CM4's ~50K to
GND, a HIGH can only be the part driving the pin.

Boot-time polarity is the opposite and is **not** what this tests. The on-chip boot kernel fixes `SPIx_RDY`
ACTIVE-LOW (HRM ch.40), which the board's pulldown fights — the line rests *asserted* during boot, so
`dsp4_boot.py`'s `wait_ready()` cannot prove a part is alive and its own docstring says so. That is a separate
phase with a separate polarity, and mixing the two is how "SPI_RDY" came to look untestable.

## 2. The test, and its criterion

> **`DY1` — the line must FOLLOW the part.** Read with the CM4 pin forced `ip pd`:
> **LOW while `!RST_D` is held low**, and **HIGH once that chip reads `BOOT_STAGE >= 7`.** Both halves required.

The stimulus is **the run's own recipe, not a new one** — the dispatch's hypothesis, and it held. `DR1` already
pulses `!RST_D` and `DR2` already runs `boot_pair()`; `DY1` sits after `DR2`, samples the pair as `DR2` left it,
dips `!RST_D` for 200 ms in one remote command (so the window is timed on the CM4, not across three ssh round
trips), and calls `boot_pair()` to bring the pair back for the DC selects that follow. One dip serves both chips
because `!RST_D` resets both parts together.

What passing both halves proves, none of which a static level proves:

- `PB_05` is bonded and muxed to SPI2 — something is actively driving the net;
- the net **card → J6 → CM4** is continuous — an open reads LOW under the CM4's own pulldown;
- it is shorted to neither rail — it moves both ways;
- SPI2 flow control is configured and **saying "ready"** — the pin's actual protocol function, not a level.

Three deliberate limits, stated rather than papered over:

- A chip that does not come back from the dip is **`NO DATA`** here, not FAIL: the HIGH half then has no part behind
  it to prove, and that verdict belongs to `DR2`.
- The first sample (the pair as `DR2` left it) is **evidence, not a gate** — if `DR2` failed, `DY1` must not fail
  for `DR2`'s reason.
- The FIFO-fill direction (`HIGH → LOW` as the RX FIFO passes 75 %) is **not** exercised. It needs the host to
  overrun a 2-deep slave FIFO on purpose, the shipping image has no `_bulk_rdy_hs` handshake to drive it
  (that is a `DSP4_TEST_NODES` build), and nothing on the parameter link honours RDY anyway. The reset/boot
  transition is the part of the signal this project can move today, and it is the part that carries the wiring.

### Live on MW-D24-2

`app@192.168.1.219`, stage `/home/app/s100` (candidate-s82 pair, `e3e25a79…` / `41a6b913…`):

```
--- 1. as DR2 left the pair (CM4 pull-down forced) ---
 8: ip    pd | hi        12: ip    pd | hi
--- 2. !RST_D (GPIO16) held low 200 ms ---
 8: ip    pd | lo        12: ip    pd | lo
--- 3. after boot_pair ---
 8: ip    pd | hi        12: ip    pd | hi      BOOT_STAGE 7/7
```

| test | row | verdict |
|---|---|---|
| `DY1-RDY1` | #105 `DSP chip-select CS3 (fw.csv Dsp3)` | **PASS** — CS3/GPIO8: running `hi`, in reset `lo`, after boot `hi` (BOOT_STAGE 7) |
| `DY1-RDY2` | #106 `DSP chip-select CS4 (fw.csv Dsp4)` | **PASS** — CS4/GPIO12: same |

A characterisation pass run before the test was written had already shown the line stays LOW after `!RST_D` is
*released* and before a boot stream is sent (`+100 ms`, `+1 s`, `+3 s` all `lo`) — the boot kernel's active-low
RDY and an undriven pin are indistinguishable there, which is why the HIGH half is tied to `BOOT_STAGE >= 7`
rather than to "the reset has been released".

It ran **twice**, on two ledgers: once driven over ssh from this workstation into the repo's
`MW/D24/DSP/accept/item-status.csv`, and once **on the unit** through exactly the command the display's START
button issues (`--local --no-app-restart --csv /home/app/selftest/item-status.csv`). Same verdict both times.

## 3. Gate 3 — the other six CS rows, checked one at a time

`fw.csv` declares `Dsp1..Dsp8` as **H1S1 pins** `B12 C14 B14 B13 C13 B15 C15 H0` on nets `CS1..CS8`. So every one
of these workbook rows is *an H1S1 pin on a net* — and **H1S1 drives none of them**: all eight are `GPIO_Input` by
decision (`~/build-h1s1` `Core/Src/main.c`, `MX_GPIO_Init_2`: *"ALL EIGHT CS pins are OWNED BY THE CM4 — this MCU
must never drive them"*). Not assumed: read against `hardware-map.md`, `dsp4-architecture-decisions.md` and the
H1S1 source, one row at a time.

| row | what the spec assumed | what it is | what changed |
|---|---|---|---|
| **CS1, CS2** (103/104) | *"H1S1 asserts one select at a time"* | live selects, but **the CM4 asserts them** — H1S1 never has | verdicts unchanged (PASS). The spec's method text is corrected, and **prereq 2 is withdrawn**: it asked for H1S1 firmware that must never exist |
| **CS3, CS4** (105/106) | a chip select | `SPI2_RDY` back from DSPA/DSPB | **`DY1`** — §2 |
| **CS5** (107) | *"no part behind it"* — true but incomplete | a spare select with no fitted part; on **this unit** the CM4 end is claimed — the D8 amendment gives `CS_M` a spare stack CS line and a proto wire carries CM4 `CS5` (GPIO27) to the `CS_M` pad | still `NO DATA`, with the real reason: no part *and* no read path, plus the note that driving it here would move mic gain. `MC1/MC2/MC3` exercise that **wire**; they do not exercise the board `CS5` net |
| **CS6** (108) | *"no part behind it"* | correct — the one genuinely idle select of the eight | `NO DATA`, reason sharpened |
| **CS7** (109) | a chip select | **`SWD_EN1`** — *"CS7/8 are permanently the CM4-owned SWD_EN selects"* (`dsp4-architecture-decisions.md`, D8 amendment), realised on rev C as the CS7/CS8 → SWD_EN1/EN3 proto wires | **same defect as CS3/CS4.** `NO DATA`, now saying what the net is. No test: this runner has no SWD transaction to prove a select with, and driving it blind takes the CM4's SWD channel select down (`archive/tasks-archive-2026-08-20.md:365-367`) |
| **CS8** (110) | a chip select | **`SWD_EN3`** — same decision, same proto-wire pair | as CS7 |

So **four** of the eight rows were mis-premised, not two. CS5–CS8 stay `NO DATA` — and the honest version of that
verdict names the missing capability instead of shrugging: the CM4 could drive a spare select and H1S1 could
confirm the net carried it, **if H1S1 published a cell reporting a pin's level**. It does not (its whole cell table
is `Sys001Enc001/Skin001/Test001/Test002`). That is now what prereq 2 asks for, in place of the assert-one-read-one
command it used to ask for.

## 4. The mechanism bug the rename exposed

`item-status.csv` is append-only and keyed on `(board, item, test)`, so **a renamed test leaves its old results in
the file for ever**. `StatusOf` rolled a row up over *every* result carrying its key, so `DC1-CS3` and `DC2-CS3`'s
two permanent NO DATAs would have gone on holding row 105 amber however `DY1-RDY1` read — the new test would have
been correct and invisible.

The fix is the S99 shape, one level up: **the catalog's `tests` column says which tests still cover a row, and a
result whose test is not in it does not gate.** `Entry.Covers(test)` in `TestSkinStore.cs`, mirrored in
`preview-d24-test-skin.py`. A retired result is still **shown**, on its own line, tagged
`[retired test — no longer covers this row]`, and sorted below the gating lines — S98's rule that a row explains
itself. A row whose *only* results are retired counts as never judged, exactly as one with no results does. The
header says `N informational` while that is all the non-gating lines are, and `N not gating` once a retired one is
among them. A row that declares no tests filters nothing.

Without this, every future test rename silently poisons its row. With it, `tests` is the single place that decides.

**Tests: 164/164 green** (162 + 2: a retired NO DATA that must not hold the row, and a retired FAIL that must not
turn it red).

## 5. On the glass

Deployed to MW-D24-2 and witnessed: app `1e1e412ce91eab1136933a436396411d`, catalog
`059d87304fd222f955f99cff4a95254e`, runner `bc8c4936dd94473f87724bfca781ecca` — all three md5-matched against the
local artefacts. The skin was regenerated and is **byte-identical** to the deployed `D24TEST.mxs`
(`f517539d…`), so it was not redeployed. Presses went in through `d24_touch_inject.py` on `/dev/uinput`: **they
prove the skin, the store and the catalog, and nothing about the ILITEK panel or its cable.**

| | before | after | capture |
|---|---|---|---|
| score | `21 / 204` · 4 FAIL · 179 not resolved · 15 runnable now | **`23 / 204`** · 4 FAIL · **177** not resolved · **13** runnable now | `live-head-score.png` |
| **#105** CS3 | UNTESTED | **PASS** — `scripted today: DY1-RDY1`, `3 tests cover this row — 1 PASS · 2 not gating`, `DY1-RDY1 PASS … running hi, in reset lo, after boot hi`, with `DC1-CS3`/`DC2-CS3` below it tagged `[retired test — no longer covers this row]` | `live-105-pass.png` |
| **#106** CS4 | UNTESTED | **PASS**, identically, on `DY1-RDY2` | `live-106-pass.png` |
| **#107** CS5 | UNTESTED | **UNTESTED, unchanged** — 2 tests, 2 not passing, **no retired tag anywhere**. The control case: the rename did not leak to a neighbouring row | `live-107-still-nodata.png` |
| **#109** CS7 | *"CS7 has no part behind it on DSP4"* | still NO DATA, now saying **"CS7 is not a DSP chip select: it is SWD_EN1, CM4-owned"** | `live-109-cs7-swden1.png` |

Predicted offline from the unit's own catalog and results file before deploying — `pass=23 fail=4
unresolved=177 runnable=13` — and the glass then read the same four numbers. Two independent computations: one by
`preview-d24-test-skin.py` on this machine, one by the app on the unit.

`DC1`/`DC2` were re-run across CS1, CS2 and CS5–CS8 on both ledgers afterwards, so the recorded evidence carries
the corrected per-select diagnoses rather than the old blanket line. `CS1`/`CS2` PASS unchanged (`CHIP_ID 1`/`2`,
`BUILD_ID 0x20260812`, the S82-signed triple).

The repo's own ledger rolls up to `23 / 3 FAIL / 178 / 13` against the same catalog — two fewer FAILs than the
unit's file because the two have drifted on the Ethernet rows since S98; the rows this session touched read
identically in both.

**One S99 leftover found and cleared**: `/tmp/tap`, the injector's FIFO, was still on the unit from 2026-09-23
20:16 (root-owned). Removed with the rest of this session's instrumentation.

## 6. Files

| repo | file | change |
|---|---|---|
| dsp | `tools/pi/d24_selftest.py` | `DY1-RDY1`/`DY1-RDY2` and their three-phase cycle; `DC1`/`DC2` fan out over `DC_SELECTS` (1,2,5–8) only; per-select `DC_NO_DATA` diagnoses replacing one blanket line; `pin_handback` leaves the two RDY lines `ip pd` so a later `pinctrl get` is readable on both |
| dsp | `MW/D24/DSP/s100/` | this report, the catalog as deployed, the live captures |
| dsp | `MW/D24/DSP/accept/item-status.csv` | two appended rows — the live `DY1` verdicts |
| mx26 | `docs/spec-d24-selftest.md` | new `DY1` row; `DC1` corrected (the CM4 asserts, and which selects can answer); prereq 2 withdrawn and replaced; gating table updated |
| mx26 | `tools/d24/build-d24-test-skin.py` | `DY1` diagnosis; `DC1` diagnosis corrected; the remedial family split understands `-RDY` as well as `-CS` |
| mx26 | `src/sw/app/Core/TestSkinStore.cs` | `Entry.Covers`; `StatusOf`, `IsDeclaredOnly`, `ResultLines` and the header count all skip retired results |
| mx26 | `tools/d24/preview-d24-test-skin.py` | the same rule, ported |
| mx26 | `src/sw/app.Tests/TestSkinWizardTests.cs` | 2 new tests |

Nothing in `defs/` was touched and `defs.lock` did not move.

## 7. Unit left as

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` inactive — test mode, as S97–S99 left it |
| app binary | `1e1e412ce91eab1136933a436396411d`, md5-matched; rollback at `/home/app/app.bak-s100-pre` (`f93fa5d3…`, the S99 build). `app.bak-s99-pre` deleted to hold the binary count at two |
| catalog | `059d87304fd222f955f99cff4a95254e`; pre-S100 at `test-catalog.csv.bak-s100-pre` |
| runner | `/home/app/selftest/d24_selftest.py` `bc8c4936…`; pre-S100 at `d24_selftest.py.bak-s100-pre` |
| skin | `/home/app/skins/D24TEST.mxs` `f517539d…`, **untouched** — the regenerated skin is byte-identical |
| instrumentation | capture drop-in removed and `systemctl show d24-testui -p Environment` back to the two shipped variables (checked against the running process's own `/proc/…/environ`); injector killed, `/tmp/tap` and every `s100-*` file removed |
| rootfs | 90 % (689 M free) |
| rails | `AN_EN` (GPIO26) `lo` throughout — never raised. `CS_M` (GPIO27) `ip pu` |
| chain | SAFE image (mute on, gain 0) verified 200/200 on the handback, after the final DSP boot |
| DSPs | booted and configured, `BOOT_STAGE 7/7`, inter-chip link gate CLEAN |
| RDY pins | `GPIO8`/`GPIO12` left `ip pd` — the state that makes the signal readable |
