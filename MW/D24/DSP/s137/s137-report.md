provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S137 — PW's panel-loop ruling: fixed order, every switch in turn, NOT LIT records and skips

**No flashing. No app deploy — `app` stays `b05e9fd5`.** Everything below is a
desk change to the station tools plus two scripted (no-bus, no-unit) proofs.

## 1. The build

PW, verbatim: "keeping the leds in the same order will speed up operator
time, but make sure every switch is tested in turn, with a button to press if
led change is not observed so machine can note, and skip to next."

- **Fixed order.** `d24_panel.py`'s `PANELS['right']`/`PANELS['left']`
  sweep order was already fixed (never shuffled unless `--random-panel-order`
  is passed, default OFF) and already reconciles fully against
  `defs/products/d24/fw.csv` (`panel_coverage.py --check`: "every control is
  either graded or named with its reason", 20 of 20 switches). No reorder was
  made or needed — see §4 for why a literal reorder to fw.csv's raw
  declaration order would have made this WORSE, not better.
- **NOT LIT records and skips (`d24_panel.py::loop`).** Pressing it now:
  - LEDs the step's indicator row **FAIL — "operator saw no light"**;
  - records the switch row **NOT TESTED — "skipped: LED dark"**;
  - advances to the next switch **at once** — no retry, no "press it anyway".
  This replaces S128's old behaviour (FAIL the LED, then re-ask the SAME step
  for a "press it anyway" switch reading). The dead retry machinery
  (`tries`, `d24_live.panel_retry_words`/`panel_retry_words_blind`) is
  removed rather than left unreachable.
  - A correct press still records both rows PASS.
  - A wrong key still FAILs the switch and now names the board in the
    same-board case too (it already did in the cross-board case).
- **The armed factory screen has a working NOT LIT button now.** Before this
  session `can_say_notlit=live is None` meant the armed screen (which is
  every real run — `_walk` always constructs a `Live` if it wasn't handed
  one) could NEVER say NOT LIT, and its WAITING screens carried a dead ENTER
  from the default button set besides. Fixed by:
  - `d24_live.PANEL_BUTTONS = ['notlit', 'pause']`, explicitly overriding the
    default `buttons_for(WAITING, confirm)` on every panel-loop screen;
  - `Live.command()` now accepts `'notlit'` (it only accepted `pause`/
    `enter`/`exit` before);
  - `d24_runall.py`'s panel `ask()`/`tick()` reads `live.command() ==
    'notlit'` and feeds it to `PL.loop()` exactly as the dialog's NOT LIT
    button already was (`kind='glass', value='notlit'`);
  - `can_say_notlit=True` unconditionally now (both channels support it).
  - Found and fixed the same dead-ENTER bug on the encoder-turn screen
    (`panel_encoder`), which is not itself a NOT LIT-bearing step — it now
    gets `buttons=['pause']` instead of the default `['enter','pause']`.
- **Random order stays OFF**, and its docstrings/help text now say PW ruled
  fixed order rather than "PW has not ruled".

## 2. Dry-run proof

### 2a. Scripted pass, PASS / NOT LIT / wrong-key, on each board
`MW/D24/DSP/s137/scripts/{right,left}-pass-notlit-wrongkey.txt`, driven
through `d24_panel.py --mode loop --inject <script>` — no bus, no unit.
Right board (14 steps): FX MUTE correct (PASS/PASS), HOME **NOT LIT**
(led FAIL "operator saw no light", switch NOT TESTED "skipped: LED dark",
MENU's turn starts immediately — no retry), MENU wrong key (FAIL, names the
board), the other 11 correct (PASS/PASS). Left board (6 steps): MONO AUX
**NOT LIT** first (before the board's cell is even identified — proves the
identification path is untouched), STEREO AUX correct, FX wrong key (FAIL,
names the board), EQ/AUX ON FADERS/OVERVIEW correct. Full JSON row dumps are
reproducible with the commands above; the row-by-row verdicts were checked
by hand against the ruling's exact wording (see §1).

### 2b. The glass-button rule, for the panel loop
`MW/D24/DSP/s137/panel_glass_buttons_check.py` drives
`d24_runall.panel_station()` directly on both boards (`M1`/`M2`) with a real
`d24_live.Live`, hooking `Live._flush` the way S128's `glass_buttons_check.py`
hooks it for the analog station's ENTER rule, and checks every distinct
WAITING screen with a key-prompt instruction: NOT LIT is in `buttons`, ENTER
is not, and the instruction actually names a button to press. Also confirms
the ring-turn screen (excluded from the NOT LIT requirement — there is no
lit/dark judgement to make there) no longer carries a dead ENTER either.
Result: `OK: every panel-step screen carries its key prompt plus NOT LIT,
and no dead ENTER.` (23 screens checked across both boards.)

Both proofs need a scratch matrix pack (`MATRIX_ADDR_HOME` pointed at a
`config/_matrix.csv` with `Sys001Skin001`/`Sys001Enc001`/`Sys001SwLeft001`/
`Sys001SwTalk001`/`Sys001Test001`/`Sys001Test002`) since they run off the
desk, not the unit.

## 3. Runbook

`MW/D24/DSP/s131-runbook.md` step 10 now says the post-switch panel check
IS the panel loop (fixed order, `panel_coverage.py --check` 20/20, NOT LIT
proven live, wrong-key names the board) rather than a one-off press per
board. See §5 below for the generation-number updates folded in alongside it.

## 4. HUB ADDENDUM 1 — the phantom "C red LED"

PW: "i'm not aware of any red C led?" Confirmed: `defs/products/d24/fw.csv`
declares NO red LED for the `C` button — only a white pair (idx 10, the same
shape as every other button). The catalog row is real but mis-titled.

**Root cause, in `mx26/tools/d24/build-d24-connector-status.py`
(`right_buttons`, the per-button loop around line 182-199):** every button's
tuple carries an `extra` field for a genuine MCU-driven red LED bound to
that specific button (FX MUTE and REC/PLY have real ones — `FxMuteRed`/
`RecPlayRec`, both declared in fw.csv with their own `SkinNum`). The `C`
row's `extra` field was reused for something that is NOT a per-button red
LED at all: `LD1`, the board's ONE shared BOOT0/ROM-bootloader indicator,
which happens to sit physically next to `C` on the silk. The LEFT board's
BootLed is declared correctly and separately (line 167, its own standalone
`panel(LS, "BOOT0 indicator LED (red, fw.csv BootLed)", ...)` call, matching
catalog row 55) — the RIGHT board's BootLed never got the same standalone
treatment and instead leaked out through the per-button loop under the `C`
button's name.

**Exact fix (write this to mx26, not here — the catalog is generated
upstream, S119's commit `de96649e` confirms "Regenerated test-catalog.csv
from mx26 ... 7bb7c84"):**

In `right_buttons`, change the `C` row's `extra` field from the BootLed prose
to `""` (empty, like every other non-FxMute/RecPlay button), so the generic
per-button loop stops emitting a "C red LED" row at all — but special-case it
inside the loop's `if extra:` block so the position/row-count is UNCHANGED
(a rename in place, not a delete-and-append, which would renumber every
subsequent catalog row):

```python
    if extra:
        if 'BootLed' in extra:
            panel(RS, "BOOT0 indicator LED (red, fw.csv BootLed)",
                  "LD1 (red 0603) beside the C button — on MCU_S1 (Digital "
                  "S13, the panel BOOT0 line) via R1/R2; declared "
                  "defs-v2026.09.22", "panel LED", 1,
                  "PL1 lights when BOOT0 is forced (field-update path), off "
                  "in normal run",
                  "not MCU-driven I/O: it shows the panel MCU being held in "
                  "the ROM bootloader; symmetric with the left board's LD1 "
                  "(Digital S9)")
        else:
            panel(RS, f"{n} red LED{'s' if 'pair' in extra else ''}", extra,
                  "panel LED", 1, "PL1 lights on command",
                  f"red indicator placed with the {n} button; meaning not "
                  f"printed on the silk; {SILK}")
```

This keeps row 78's position (and every row after it) unchanged and gives it
the same name/criteria shape as row 55's left-board counterpart —
"BOOT0 indicator LED (red, fw.csv BootLed)", `PL1 lights when BOOT0 is
forced ..., off in normal run`, not "PL1 lights on command" (which was
simply false for this indicator).

**Reconciliation against defs — no other phantom or missing indicator.**
`defs/products/d24/fw.csv`'s complete LED-row set is 34 rows (20 per-button
white-pair rows across both boards + `FxMuteRed` + `RecPlayRec` + 8 encoder
singles + `BootLed`×2 + `TalkbackLed0`/`TalkbackLed1`), and
`panel_coverage.py`'s own table already reports "Indicators: 20 of 34
graded" against the CURRENT (unfixed) catalog — 34, matching exactly. The
catalog already carries one row per fw.csv LED declaration; row 78 is the
ONLY mismatch, and it is a rename, not a missing or extra row. Once mx26
lands the fix and this repo's `MW/D24/DSP/s119/test-catalog.csv` is
regenerated, `tools/pi/d24_panel.py`'s `UNREACHED['right'][78]` reason text
("no indicator is declared for this designator...") becomes wrong for the
renamed row and should be replaced with the same reasoning `UNREACHED['left'][55]`
already carries ("driven by the processor boot pin, not by the panel MCU:
nothing the host writes can light it") — **flagged for whoever picks up the
catalog regeneration; not done against the current, still-unfixed local
catalog copy in this session.**

## 5. HUB ADDENDUM 2 — the target generation moved, and gen_dsp.py's gap

- **`MW/D32/DSP/gen_dsp.py`** now carries a `('Chan', 'DynMtr')` →
  `'host-managed'` entry in `_UNMAPPED_REASONS`, using defs' own note on the
  cell verbatim (`Chan{N}DynMtr001` is HOST-DERIVED: the app sums
  `Chan{N}GateMtr001` + `Chan{N}CompMtr001`, both of which it already has;
  never sent to or from the DSP, not on any wire). Confirmed this doesn't
  regress the current pin: `gen_dsp.py --dry-run` at the pinned
  `defs-v2026.09.27.3` still ends `Done.` with no error.
- **This one line is necessary, not sufficient.** Checked out `defs` to
  `defs-v2026.09.28` read-only (`git -C defs checkout defs-v2026.09.28`,
  restored to the pinned commit afterward — `defs.lock` untouched, still
  `.27.3`) and ran `gen_dsp.py --dry-run` against it: it still errors —
  `"d32/dsp-unmapped.csv cell set disagrees with the graph — 0 the graph
  proposes and the landed file lacks, 33 the landed file has and the graph
  does not propose"` (25 for d24) — because the local `dsp.csv` graph
  (`tools/dsp/gen_dsp_csv.py`'s output) has no idea `Chan{N}DynMtr001`
  exists at all yet. Closing that needs the full `sync-defs.sh` pipeline to
  regenerate `dsp.csv`/`dsp-unmapped.csv` together against `.28`, which is
  its own dispatch (all four products, `regenerate-dsp-contract.sh`, the
  families allowlist) — **not attempted in this NO-FLASH, D24-panel-loop
  session.**
- **Verified independently, same read-only checkout:** `defs-v2026.09.28`'s
  D24 matrix is base-id **`b630825d8fed`**, 5031 names/addresses (up from
  5006 at `.27.3`/`.27.5` — `Sys001SelectedFx001` + 24× `Chan{N}DynMtr001`
  appended). Existing cells are unchanged: `Sys001Skin001` is still 4698.
  Matches HUB ADDENDUM 2's own numbers exactly (`Sys001SelectedFx001` = 5007,
  `Chan001-024DynMtr001` = 5008-5031).
- **`MW/D24/DSP/s131-runbook.md`** updated everywhere it names the
  generation: live numbers where I could verify them directly (per-cell
  addresses, the new total, the base-id), a `HUB ADDENDUM 2` note in §0
  giving the full account, and explicit STALE flags on §6's and the
  `_matrix.mxc` hash's recorded dry-run evidence (real results against the
  now-superseded `f9677e5fae5e` target, kept as a record rather than
  silently rewritten) — **re-running S134's dry-run diff (new `matrix.h`,
  new `.shex`, diffed against the flashed images) against `b630825d8fed` is
  still owed and was NOT done in this session**: it needs the embedded build
  trees and CCES-adjacent tooling this dispatch's NO-FLASH, desk-only scope
  did not call for, and getting it wrong in a pre-flight runbook is worse
  than leaving it flagged.
- **`defs.lock` itself was never touched.** Advancing the pin
  (`./sync-defs.sh --update-lock`) plus the full contract regeneration is a
  separate action spanning all four products and is recommended as its own
  dispatch before S131 runs.

## 6. What's NOT done

- The mx26 catalog fix (§4) — written here for the hub to apply.
- The full `defs.lock` advance to `.28` and the `dsp.csv`/`dsp-unmapped.csv`
  regeneration gen_dsp.py's own drift check still wants (§5).
- Re-running S134's matrix.h/.shex dry-run diff against `b630825d8fed` (§5).
- `d24_panel.py`'s `UNREACHED['right'][78]` reason text, once the catalog
  is actually regenerated with the renamed row (§4).

None of these block S137's own ruling, which is fully built and proven above.
