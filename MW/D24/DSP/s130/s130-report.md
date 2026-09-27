# S130 — overnight, no-hands: report

Unit: MW-D24-2. Unattended, per PW's "if you can work and improve the test
station, keep going". Touched nothing irreversible: no panel/MCU flashing, no
CPLD flash, no fuses, no defs cell/address work (the matrix-generation wall
is a separate hub agent's, untouched here).

## 1-2. The summary grid and the AL1 hands-off overlay, on the glass

Driven from the app's own START via `d24_touch_inject.py --serve` + a new
driver, `MW/D24/DSP/s130/tools/s130_drive.py` (based on S128's
`glass_drive.py`, extended to also tap the Primary border for `exit` — the
summary/EXIT screen reuses that same button per
`FactoryView.axaml.cs:buttons_for(SUMMARY) == ['exit']` — and to fire an
on-demand DRM capture, via the existing S128 `capture.request` mechanism, at
the `handsoff` state and at each distinct summary page).

**A real, same-day regression was found and fixed on the way, or neither
item could be proven at all.** `d24_panel.py`'s `PanelBus.light()` and
`InjectedBus.light()` still took one positional argument (`value`); S129
(`16acebb6`, today, 18:55) changed `loop()`'s call site to
`bus.light(st.idx, cells)` when it gave the left panel its own cell
(`cells_for()`, writing both `Sys001SwLeft001` and `Sys001Skin001` while a
board is unidentified) but did not update either `light()` method to accept
the second argument. The very first real (or `--simulate`d) panel step now
raised `TypeError: PanelBus.light() takes 2 positional arguments but 3 were
given`, killing the whole pass — the app landed cleanly back on armed START
("The test did not start. Press START to try again."), so nothing unsafe
happened, but no pass past Station 1 could ever complete. S129's own
"151 of 151 dry run" never exercised this path: that count is
`d24_patch.py`'s (analog patches), and the panel loop's own dry-run harness
is `InjectedBus`, in the same file, same broken signature — so this was
never run either. Fixed both methods to accept an optional `cells` tuple
(default `(SKIN,)`, unchanged for every other caller — `mode_probe`,
`mode_rtt`, `mode_light` all still pass one positional argument) and write
each cell in turn, waiting for MH1's ack on each. Proven with a synthetic
`InjectedBus` run: an unidentified left-panel step now writes `('swleft', v)`
and `('skin', v)` for every index, matching `cells_for()`'s own doc, and the
walk completes to NODATA (no key ever arrives) instead of crashing. Deployed
to the bench (`d24_panel.py`, backup `.bak-s130-pre`).

**Separately found and worth a line for the hub/PW: FactoryView has no UI for
`NOT LIT` / `SKIP` / `IGNORE`** — `panel_station()`'s `ask()` still posts
those through the `Glass`/`prompt.json` channel (`glass.post('instruct', ...,
['notlit'], ...)`, S120-era), and `FactoryView.axaml` has exactly three
buttons (ENTER/START/EXIT sharing one border, PAUSE, TEST MENU) and draws
nothing from `prompt.json`. An operator on the actual glass cannot press NOT
LIT today; a dark indicator can only be reported by NOT pressing anything and
letting the 30 s timeout land NODATA, never by the intended "I saw nothing
lit" answer. This is a separate, pre-existing gap (unrelated to S130's asks)
and is design-shaped, not a two-line fix — flagged here, not built.

### Item 1, the summary grid: PROVEN

Once the fix was in, a full unattended pass ran the bench-setup prompts
(which now include mini-jack: "Hang the XLR-to-mini-jack lead on AUX 3",
confirming item 4's kit change reached the live list), the panel loop, the
patch walk (all quick, with no real leads: "1 passed, 132 not tested"), and
landed cleanly on the two-page summary grid, `n=1/2` then `n=2/2`, each
tapped through EXIT. Screenshots: `MW/D24/DSP/s130/screens/` (this repo, the
durable copy), `~/hub-staging/s130-screens/` (staged for the hub), and
`/home/app/selftest/s130-screens/` (the unit's own copy) all carry the same
files. No timeout on the grid (confirmed: the run sat on page 1 until
tapped), EXIT works, and there is no START visible *under* the grid while it
is up.

**But found a real app bug going the other way — the grid stays over the
armed screen, not under it.** After EXIT, `FactoryView.axaml.cs`'s `Draw()`
sets `SummaryList.IsVisible` / `SummaryHead.IsVisible` from `summary`, but
the idle/armed path is a **separate method, `DrawIdle(armed)`, which never
touches either property.** So the grid's `ItemsControl` and heading stay
visible, composited over the armed START screen, until the next real
`Draw(s, ...)` call (i.e. the next START/prompt) resets them. Reproduced
twice, independently (`s130-screens/bug-summary-ghost-after-exit.png`, taken
~6 minutes apart with a fresh on-demand capture each time — identical
ghosting both times, so it is the live view tree, not a stale capture file).
Not fixed here (`FactoryView.axaml.cs` is the app pack, off limits per this
block's own brief) — a one-line fix for whoever owns it: `DrawIdle` should
set `SummaryList.IsVisible = SummaryHead.IsVisible = false` (and clear
`ItemsSource`) same as `Draw`'s non-summary path does.

A second, less certain observation: `summary-page-1.png` itself shows the
SAME kind of overlap between the grid's own heading/top row and whatever
screen preceded it (`s130-screens/summary-page-1.png`). This might be the
same missed-hide bug caught mid-transition rather than a separate one — not
chased further tonight.

Confirmed a third time on a second, independent full pass (run 3, 22:50-22:52
BST): `summary-page-1-run3.png`/`summary-page-2-run3.png` show the grid
cleanly; `armed-after-exit-run3.png` shows the same ghosting again, now with
that pass's own numbers ("18 passed, 144 not tested") — so the bug is not
tied to a specific pass's content, it is the transition itself, every time.

### Item 2, the AL1 hands-off overlay: NOT proven — a real, reproduced regression, escalating rather than grinding

**AL1 still fails "NO DATA — no settled window for: base, tone, back" in two
independent unattended passes tonight, one of them with zero touch input of
any kind during its window.** This directly contradicts S129's own claim
("Prove it PASSES again from the glass START... Desk-verified on all three
states").

- Run 1 (22:17 BST): AL1 ran automatically as part of the AUTO test batch
  (`d24_selftest.py --only ...,AL1 --quiet-flag ...`) about 30 s into the
  panel loop's *first* button (MONO AUX), while my own driver was still
  re-tapping the touchscreen every 3 s (a glass_drive.py-inherited habit,
  meant for slow-to-register ENTER presses, that also fires uselessly during
  a panel step — that button is graded off a real panel press, never off
  that touch). AL1: NO DATA, 3.1 s.
- Fixed the driver to stop the periodic re-tap (a real touch was landing at
  almost the exact second AL1's own log shows "measure end" the first time —
  strong circumstantial evidence it was self-inflicted). Re-ran clean: one
  tap per new screen only, nothing at all touched during the ~30 s MONO AUX
  is lit and waiting.
- **Result unchanged: AL1 still NO DATA, same message, 3.4 s, with the
  touchscreen never touched during its window.** So the touch was not (or
  not only) the cause.
- The one thing that *is* still true in both runs: AL1 runs concurrently with
  the panel loop's first button, which is already lit and waiting when AL1
  starts — S129's `quiet_hold()` fix only gates the panel loop **before it
  lights the *next* indicator**, not an indicator that is already lit and
  sitting idle. Whether that overlap (rather than a touch) is what disturbs
  AL1's acoustic window is a real hypothesis, not a proven cause — telling it
  apart from "AL1 just doesn't settle reliably in this exact invocation
  shape yet" needs either a clean run with the panel loop *not* started
  (hands, or a `--auto-only` pass) or reading `d24_selftest.py`'s AL1
  settle-window code directly, and either is root-cause work of a shape this
  block was told to stop rather than grind on.

**Escalating, per this block's own clause: 🔴 needs attention above sonnet
tier (or PW's own eyes), not solved here.** Evidence preserved: both AL1
NO-DATA events are in `factory.log` (search `AL1`, timestamps 2026-09-27
21:18:57Z and 21:40:52Z) and `s130-drive.log` shows the exact touch history
around each. No hands-off screenshot exists because the `handsoff` state was
never reached — AL1 running inside the AUTO batch, ahead of any panel step
needing it, appears not to route through `LV.HANDSOFF` at all in this
invocation path (that state is set only inside `panel_station`'s `hold=`
callback); worth an early question for whoever picks this up: does AL1 ever
actually show the hands-off screen at all in a real pass, or only avoid
disturbing panel work that has not started yet?

## 3. The PSU rail monitor — NOT built

See `MW/D24/DSP/s130/data/item-3-psu-monitor-conflict.md`. `defs`'s own
`fw.csv` says PAD0-11 are N/C on this board revision and carries PW's dated
ruling not to test them or infer rails from them; there is also no existing
code path that reads them at all, so item 3's premise ("read each rail
through the existing... path") does not hold on this unit. Building it would
mean reporting floating-ADC noise as if it were rail voltages, which the
no-fallback rule this repo runs on says not to do even gated INFORMATIONAL.
Not built; no catalog row proposed. The hub/PW question that unblocks it is
in that file.

## 4. Mini-jack inputs 1 and 2 — built, dry-run proven, deployed

- `tools/accept/gen_patch_paths.py`'s `block_k3` (mini-jack) already existed
  but had never been included in the live "quick" list (K3 excluded — no
  physical lead yet) and graded `level_ref='single'` against a window the
  catalog itself already says is unruled (PL-5). Fixed to `level_ref='info'`
  (informational: tone presence + level reported, never a hard FAIL),
  matching the K4 line-rows' pattern for the same "class unruled" situation.
- Regenerated and merged additively into the bench's live
  `quick/patch-paths.csv` and `quick/patch-kit.csv` (rows 152-155 / P60-P61,
  K3 kit entry placed in its canonical `K1,K4,K3,K2,K5` order) — additive
  only, nothing else in the live list touched. Backups: `*.bak-s130-pre`.
  Local tracked copy: `MW/D24/DSP/s130/quick/`.
- Dry-run proven on the bench: `d24_patch.py --simulate` (default list-dir,
  i.e. the live `quick/`) — **155/155 PASS**, including the new K3 block (2
  patches, 4 measurements, 0.4 machine-s, 12 hand-s).
- `test-catalog.csv` rows 95/96 (`short` field only) updated to say the
  check is built and dry-run proven, no lead yet, graded INFORMATIONAL —
  backup `test-catalog.csv.bak-s130-pre`.
- Still waits on tomorrow's bench for a real lead (K3 physically doesn't
  exist on the unit yet); HANDS 3 in the consolidated script (item 6) already
  uses it.

## 5. Random-order indicator lighting — built behind a flag, default OFF

- `d24_panel.py`: `loop()` takes `random_order=False`; when true, shuffles
  the panel's `steps` before the walk. Grading is unchanged (`st.idx` is
  matched by value, never by position), so this only permutes the order.
- `d24_live.py`: two new functions, `panel_press_words_blind` /
  `panel_retry_words_blind` — the board is still named ("RIGHT switch
  board:"), the button is not.
- `d24_runall.py`: new flag `--random-panel-order` (default off); when set,
  `panel_station()`'s `ask()` stops naming the button in the dialog lines,
  the glass instruction, and the dialog TITLE (which also carried the name).
- **Proof (no PW ruling yet, so this stays off by default and untouched in
  the normal flow):**
  - Default behaviour is provably unchanged: a scripted "perfect operator"
    bus walked the right panel and the lit order exactly matched the
    declared `PANELS['right']` order, all 14 PASS.
  - With `random_order=True`, five trials each produced a different walk
    order (e.g. `[14,11,6,13,8,7,3,10,9,12,4,1,5,2]`), every button still
    correctly graded PASS regardless of position (grading is by the key
    code's value, not the walk position).
  - `--dump-dialogs` / `--check-md` pass clean, including the two new blind
    wording functions (added to `d24_live.py`'s dialog enumeration alongside
    the existing named examples) — no leaked Matrix-internal vocabulary in
    either wording path.
- Not exercised through the full app+`d24_runall.py` harness with a fixture
  script, because `InjectedBus` scripts are fixed-order and a shuffled walk's
  order is only known after the shuffle — that needs an auto-responding test
  bus if PW green-lights the design, not built tonight (see escalation
  clause: don't grind on an unapproved design's tooling).

## 6. Tomorrow's bench session — one script

`~/hub-staging/s130-bench-script.md`, copied for the hub to place on PW's
Desktop. HANDS 1 (front panel, no leads) first, then HANDS 4 and HANDS 3 back
to back at the rear panel (sharing the K1 lead across both, K4 only touched
once), then HANDS 2 (meter-check the K4 lead the moment it comes off the
unit at the end of HANDS 3). Estimated ~8-10 minutes plus an optional ~7
more for the full patch walk.

## 7. Gain-table analysis tool — built, tested on synthetic data; the table itself fixed through defs, three addenda deep

- `MW/D24/DSP/s130/tools/gain_table_analysis.py`: takes per-element measured
  gain (law.csv shape: `channel,code,loop_gain_db`, normalized to the
  channel's own code 0) and, per element, against the reference table:
  mean/worst error, a linear fit of error vs. gain to classify GROWING (FET
  Rds(on)) vs FLAT (table/resistor) — see `--selftest`, five checks, all
  PASS — and a proposed per-element corrected table.
- **HUB ADDENDUM 1 (the hub's own dry-run against `law.csv`):** confirmed
  independently — 1 of 16 channels violates a per-code ±0.25 dB median check,
  MIC 7 (J29) at code 8, -0.85 dB low; the other 15 hold to 0.088 dB worst
  case, growing with gain (consistent with an FET Rds(on) signature, not a
  resistor-tolerance one).
- **HUB ADDENDUM 2 (PW, "fix the table — do it properly, through defs"):**
  extended `MW/D24/DSP/s55/tools/s55_ingest.py` itself (not a standalone
  script) with `write_codes()`, emitting **all 64 hardware codes' MEDIAN
  step** — `code, byte, step_db, spread_db, n_channels, excluded` — staged at
  `proposals/defs/common/tables/mic-gain-codes.csv` (same convention
  `mic-gain-law.csv` uses) and landed in the real defs repo:
  `common/tables/mic-gain-codes.csv` + `common/schema/mic-gain-codes.md`,
  **tag `defs-v2026.09.27.5`, commit `777af44`** (supersedes an earlier same-
  night `.4` that shipped the wrong column names — `hw_gain_db/min_db/max_db`
  instead of the addendum's `step_db/n_channels/excluded` — caught and
  corrected before anything downstream depended on it). Additive only in
  both commits — no cell, mx-master, wire table, fw.csv or product def
  touched, so neither intersects the in-flight matrix-generation
  reconciliation. **This repo's own `defs.lock` pin is deliberately NOT
  advanced** (S130's brief: don't touch defs while that reconciliation is
  live; a second contract bump tonight would race it) — `defs.toml`'s
  `current` line is `.5` (was stale at `.2` even before tonight; fixed in the
  same commit as the schema correction).
  - **Acceptance test, exactly as addendum 2 specified:** checking every
    channel's measured step at the seven canonical gain-step codes (the ones
    `patch-gain-steps.csv` actually uses) + the EIN code against this table
    at PW's ±0.25 dB window fails **exactly one pair — MIC 7 (J29), code 8**
    — and passes the other 127. (Checking all 64 codes densely, not just the
    seven steps, turns up eight more J29 failures at codes 9-15 and 24, all
    the same bit-3 element fault propagating through every code that sets
    that bit; no other channel fails at any code, at any of the 64.)
  - **Point `gen_patch_paths.py`'s gain-step EXPECTED values at that table,
    one row per step, no fit** (addendum 2's third ask): done.
    `load_gain_codes()` replaces `load_gain_law()`'s six-element fit; every
    one of the seven steps plus EIN is now `source=measured` in the
    regenerated `patch-gain-steps.csv` (codes 8/16/32 flip from `fitted` to
    `measured`; 8's expected value moves 34.283→34.344 dB, 16's
    41.494→41.587, 32's 48.046→48.128 — all within the fit's own 0.51 dB
    residual, so nothing that previously passed now fails). Reads
    `defs/common/tables/mic-gain-codes.csv` once the hub advances the pin,
    falling back to the staged `proposals/...` copy until then (both
    byte-identical, both generated by the same `s55_ingest.py` run) — so nothing
    breaks tonight and nothing needs touching again after the pin bump.
    Regenerated and redeployed to the bench's live `quick/patch-gain-steps.csv`
    (backup `.bak-s130-pre`); re-ran `d24_patch.py --simulate` on the bench
    afterward — still 155/155 PASS. Removed `load_gain_law()` and simplified
    `gain_db()` — both are dead code with this table in place (every code is
    now measured, so the function that only ever handled "not measured" is
    unreachable).
  - **HUB ADDENDUM 3, `defs.toml`'s tag line:** was still `.2` at `.3`; fixed
    in the same commit as the schema correction (now `.5`).
  - **HUB ADDENDUM 3, `defs-publish.sh` aborts on macOS bash (3.2) with no
    `--product`:** root-caused, not guessed — `products/dsp/dsp.csv` (a
    stray non-product entry the `products/d*/d*.csv` glob also matches) has
    no `gen/matrix/` files, so its `publish_gen` array stays empty; bash
    <4.4 raises `unbound variable` on `"${empty_array[@]}"` under `set -u`,
    and `--product D24` alone never reaches that entry, which is exactly why
    it "only aborts with no `--product`". Guarded all seven array expansions
    with the standard `${arr[@]+"${arr[@]}"}` idiom (same commit,
    `defs-v2026.09.27.5`). Verified it still runs end to end on bash 5.2 here
    (52 files published dry-run, 4 refused, unchanged from before the fix);
    **could not test on actual bash 3.2/macOS — none available in this
    environment, so PW should confirm on his own Mac before relying on this
    alone.** HUB ADDENDUM 3 also said the unit switch-over (app + `.mxc` +
    firmware reflash) is held for PW as S131 — nothing here touches the unit
    or the live app, only the desk-side generator and the defs repo.
- Smoke-tested `gain_table_analysis.py` against one real S55 channel (J35/MIC
  9, all 64 codes): runs clean end to end, mean error -0.046 dB, classified
  GROWING at a slope of -0.002 dB/dB — a real but tiny trend that clears the
  (provisional) classification thresholds close to their edge. **The
  thresholds (`GROW_THRESHOLD_DB`, `FLAT_R2_MARGIN`) are placeholders**
  pending real multi-code HANDS 4 data; said so in the tool's own docstring
  rather than hand-tuned against one channel.

## 8. For the hub

**Touch panel (new row, upstream in `test-catalog.csv`):**
```
204,Digital,"Touch panel (rear USB socket, hub port 2)",USB-A,PASS,1,USB-TP,A,0,"No action needed -- automatic, 0.1 s.",,"USB-TP: lsusb -t and udevadm to confirm 222a:0001 (ILI Multi-Touch Screen) is present, on the internal Microchip hub (not the root port), on hub PORT 2 specifically (the operator sticks use ports 3 and 4), and that usbhid is bound to it","USB-TP: the panel enumerates as 222a:0001 on the Microchip hub at port 2, and usbhid is bound -- a panel that enumerates and does not bind is a panel nobody can touch, and the glass is a finished unit's only input device","USB-TP: hub port number, VID:PID, bound driver name",A. Read from the CM4 (Linux),,204,A1,
```
(`num`=204, the next free id; `order`=204, `group`=A1 alongside the other
no-rails/no-analog automatic rows — the hub's call to place/renumber.)

**PSU:** no row — see item 3. Recommend the hub get PW to confirm whether ANY
rail-sense path exists on rev C before this is asked for again.

**Mini-jack:** no upstream change. Rows 95/96 already exist with the right
class/tests/PL-5 status; only this station's own `short` field text changed
(not a defs/catalog-schema matter).

**Also landed in defs, for the hub's awareness (not a catalog row):**
`mic-gain-codes.csv` at `defs-v2026.09.27.5` — see item 7. Pin bump left to
the hub to sequence after the 5005 reconciliation.

## Unit state at handback

Confirmed after the last pass finished on its own (not interrupted):
AN_EN (GPIO26) low, GPIO27 driven high (CS_M fix, per
[[dsp4-cs-m-miso-buffer]]), no firmware flashed, no CPLD touched. `d24-testui`
active and showing the armed screen (visually cluttered by the ghosting bug
above — functionally armed, START is live underneath); `matrix-app` inactive
the whole session (stopped by `d24-testui`'s own `Conflicts=`, never touched
directly) — restore it if the hub wants the normal mixer skin back. The
touch-inject FIFO server (`s130-tapserve`, transient) and all three drive
attempts (`s130-drive`/`s130-drive2`/`s130-drive3`, transient) are stopped
and gone. Cumulative pass state from this session's three no-lead unattended passes
was reset (`d24_runall.py --reset-only`, backup `runall/state.json.bak-
s130-pre`) so tomorrow's HANDS session is a genuine first pass and walks
everything, same as S129 left it — three passes of fake NOT TESTED/NO DATA
verdicts (no real lead was ever in a socket tonight) are not results worth
keeping, and "no test twice" would otherwise skip rows HANDS 1-4 actually
needs walked for real.
