provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S138b — the design half of S138: the phantom lamp sweep, the click/shunt trials, and the two sense rows

Dispatch `tasks.md` 2026-09-28 16:16Z, plus **HUB ADDENDUM 1** ("one insertion,
two results"). **NO FLASH, NO APP DEPLOY, AN_EN never raised, no phantom
applied, no analog write, no BLOWER/FAN write.** The only thing that reached the
unit was `deploy-bench-tools.sh` — Python tool files, md5-verified, backed up,
no rails and no images (§6).

Everything S138 recorded blocked is built. Two of S138's six findings were
**wrong**, and both because the primary source was out of reach: the rulings
were on `origin` in `~/mx26` behind a stale clone, and the 595 shunt bit was
sitting in plain sight under the name `mute`.

## 1. The primary source, read (answers S138-1)

`git -C ~/mx26 pull` brought 291 new lines of `pipeline.md`. Both entries the
dispatch quotes are there and were read rather than relayed:

- **08:06 BST 2026-09-28** (`pipeline.md:255-261`) — the two-LED lamp fixture
  (XLR-M, pin 2 → 3.9 kΩ → LED "2" → pin 1, pin 3 → 3.9 kΩ → LED "3" → pin 1,
  ≈4.0 mA per LED off the 6.81 kΩ feeds), "moved input to input like the 150 Ω
  plug as a SEPARATE sweep", phantom on → "are BOTH lights on?" ENTER / NOT LIT,
  phantom off → both dark, operator-observed; and the click/shunt trials, "for
  PW to review and SIGN OFF the click limits — informational until signed".
- **07:59 BST 2026-09-28** (`pipeline.md:263-268`) — the gaps doc ruled.

**And the shunt ruling has a primary source too, which S138-3 got wrong.**
mx26 `docs/ref-d24-analog-attach.md` §"Phantom switching — the shunt-first
sequence (PW 2026-09-16)": *"Q0 is the phantom shunt: it grounds that channel's
mic-pre input coupling caps. It is not a mute and not a pad."* The five ruled
steps, the two provisional waits (`ShuntSettleMs` 50 ms, `PhantomSettleMs`
300 ms) and the failure end state ("leaves the shunt engaged") are all there,
and `docs/d24-analog-xlr-map.md` carries the same sentence about bit 0.

## 2. The rename: Q0 is the phantom shunt, and the wire did not move

`d24_chain.byte(shunt, phantom, gain)` — `mute=` still accepted as the
deprecated alias the app's own bench CLI keeps, and passing both with different
values is refused rather than silently resolved. Plus `split()` (the inverse,
so a read-back prints in the ruling's names), `with_shunt`/`with_phantom` (both
refusing transmit position 24, which is U34's byte where Q0 is INSTR1 and not a
shunt at all), and `phantom_sequence()` — PW's five steps as pure arithmetic, so
they can be asserted image by image off the bench and so the station and any
later tool cannot each grow their own version.

`Analog.phantom(channels, on)` in `d24_patch.py` is the three **verified loads**
around it. `CHAIN_TONE`/`CHAIN_NOISE`/`step_image`/the SAFE-image label all say
"shunt" now; the DSP strip's digital mute is untouched and unrelated.

**All 256 encodings are proved byte-identical to the pre-rename arithmetic** —
the old expression is copied into the proof deliberately, so a wire that has
been right since S51 cannot have been changed by a docstring.

## 3. 1.2(a) — the phantom lamp sweep

`d24_patch.py --patch-only --lamp-sweep`, a **separate** entry that the factory
START refuses to run (it applies phantom, so it is not something a worker
reaches by pressing START before PW has signed it off).

- 24 XLR mic inputs, in the list's own order, addressed by `send_pos` — never
  the strip number and never the chain index (S125's three-orders lesson). An
  input with no transmit position anywhere in the list is recorded NO DATA, not
  guessed at; TALKBACK and the mini-jacks are out of scope, not "skipped".
- **Two screens per input, and both of the ruling's observations.** The MOVE
  screen is up while phantom is off on every input, so a lamp lit there is
  phantom present with phantom off → `LAMP_STUCK_ON`. The CHECK screen is the
  ruling's own question → NOT LIT records `LAMP_LEG_FAULT`. One button
  vocabulary, no new button in the app, no extra press. The label wart is
  finding **S138b-2**.
- **Every transition is the shunt-first sequence.** The proof counts the loads
  and reads their bits: MIC 1 gets 3 for phantom on and 3 for off, in the order
  (1,0,0) → (1,1,0) → (0,1,0) then (1,1,0) → (1,0,0) → (0,0,0), and no load
  anywhere in the sweep moves phantom in one image.
- **Phantom comes off everything it touched on every way out** — the answer, a
  NOT LIT, a PAUSE, a timeout, a failed load — as ONE sequence over the whole
  set, because the ruling's step 1 is "every channel whose phantom is about to
  change". The mic-pre safety handback is unchanged and is proved to still run,
  in PW's order (rails down, then CS_M high, then SAFE), against the real
  `Analog.down` with only the wire and the shell stubbed.

## 4. 1.2(b) — the click/shunt trials, inside the EIN step

`--click-trials`, **off by default**, INFORMATIONAL always: no verdict, no
window, no PASS and no FAIL anywhere on the path. `--trial-inputs` names the
good channels by hand; the default is every input whose EIN reading came back.

Four trials per input — phantom off→on and on→off, each with the shunt
**engaged** and with it **released**. The two arms are the same shape (one
image moves phantom, with the shunt already where it is going) so the only
difference between them is the thing being measured. **The released arm is the
one place in this tree that moves phantom without the sequence, and that is what
it is for**: PW's 09-16 rule says never do it, PW's 09-28 ruling asks for the
rule's worth to be measured. It only ever runs with the 150 Ω terminator
fitted, never a microphone, it says so in the log every time, and the handback
afterwards goes back through the sequence.

**The table format is fixed here** (`CLICK_COLUMNS`, `click_table`), and the
instrument declares itself above it rather than in a comment PW will not see:

| column | what it is |
| --- | --- |
| `floor_dbfs` | the lane with the plug in and nothing moving: the median of the pre-toggle samples |
| `peak_dbfs`, `t_peak_ms` | the highest sample after the toggle, and when. The meter LATCHES, so a peak cannot be missed between polls — only reported up to `poll_ms_max` late |
| `above_floor_ms` | to the last sample still more than 6 dB over the floor |
| `decay_only_ms` | how much of that the meter's own 6.52 dB/s decay accounts for on its own |
| `residual_ms` | the difference — the transient's own duration, as far as this instrument can see it |
| `truncated` | the capture ended with the lane still ringing, so `above_floor_ms` is a LOWER BOUND and no residual is reported |
| `energy_db_s` | Σ p·dt over the samples above the floor. An UPPER BOUND, same latch |
| `polls`, `poll_ms_mean`, `poll_ms_max` | what the cadence actually was |

PW signs against `peak_dbfs` and `residual_ms`. `truncated` and `CLICK_POST_S`
2.5 s are finding **S138b-6** — the proof caught the table reporting 0 ms of
ringing about the loudest click in the set.

## 5. 2.2 and 2.3 — the two sense rows, and ADDENDUM 1

**Row 93 is not a station.** PW: *"one insertion gives both the L/R signal test
and the jack-switch detect"*, so the detect rides the mini-jack step of the
analog patch loop, which already asks the operator to push a plug into a
mini-jack for rows 95/96.

- `MiniJackSense` — a read-only listen on `Sys001SwMiniJack001`, resolved **by
  name** off the unit's own pack (S136; the deploy guard for hard-coded
  addresses passes). No `send`, no `cell_line`, no sentinel: open, drain, read.
- **The arm is in `_prepare`**, which is the last thing before `p.connect` and
  `announce` in both paths into it — the first patch of a block and the
  pipeline's look-ahead — so the drain cannot miss an edge and an edge cannot
  land in a window nothing is watching. The proof asserts this by **ordering**,
  not by reading the code: the arm's sequence number is lower than the
  mini-jack screen's.
- The edge is drained inside `detect()`'s own wait loop, which is already
  waiting for the operator's hands.
- **The removal is free.** The detect binds to the FIRST mini-jack patch, and
  the next patch's own prompt ("… to MINI-JACK 2, with MINI-JACK 1 empty") is
  the instruction that takes the plug out. Only a list with a single mini-jack
  patch spends one screen on it. `--mj-detect-input` moves the binding.
- Verdicts: PASS on two different values; FAIL, naming it, when the cell
  answered but the value never moved; NO DATA — never FAIL — when nothing was
  transmitted at all (finding **S138b-4**). Zero is a real value, not "no
  reply".
- The row carries `rows=93`, so `patch_station` folds it onto the catalog row
  with no special case. `GRADED_ELSEWHERE` stops the panel station claiming it,
  and — the subtle half — stops `record_not_run` FORCING a NOT TESTED over a
  verdict the analog station had just landed. Negatively controlled.

**Row 94 stays on the panel bus** (`d24_panel.sense_sweep`, run from
`panel_station` on the same already-open bus, and standalone as
`d24_panel.py --mode sense`). It asks the operator for nothing, because its read
half is a temperature count and not a switch — finding **S138b-3** — and it
never writes, because the write half is the BLOWER/FAN drive mask. Graded: the
pass-through transmits at all, and 0 < count < 255. `rows_for` now includes it,
which is what makes `manual_step` call it a LOOP row instead of BLOCKED.

**Row 93's text follows one jack**, as the dispatch instructs, and the reason the
catalog's "jack 1, then 2" is not a contradiction is finding **S138b-1**: two
sockets, one MJ_SW net. Recorded for PW, with the consequence that matters — if
the NC contacts are paralleled, one plug may not lift the net at all — and the
check grades EDGES so it needs neither answer first.

## 6. Proofs, guards and what reached the unit

Five scripted proofs, **195 checks, all green**, no unit, no bus, no serial
port, no SPI, no rails, no phantom:

| proof | checks |
| --- | --- |
| `shunt_sequence_check.py` | 42 — the 256 encodings, the five steps both directions, a mixed set, an already-shunted channel, the failure end state at all three steps |
| `lamp_sweep_check.py` | 41 — scope, the screens and their words, the loads and their bits, both faults, PAUSE, a failed load, the real handback |
| `click_trials_check.py` | 44 — the metrics against captures whose answer is known by construction, the four trials, the two arms, the handback, the gate, the table |
| `mj_sense_check.py` | 37 — the arm-before-the-prompt ordering, all four verdicts, `rows=93`, the runall routing and the `record_not_run` control |
| `sense_sweep_check.py` | 31 — row 94's three verdicts, the arm, no write, by-name resolution, `--mode sense`, the LOOP routing |

Regressions, all green: S138's `find_cell_events_check.py` and
`session_end_power_check.py`; S137's `panel_glass_buttons_check.py` (**23**
screens, "no dead ENTER"); S137's two panel-loop injections, reproducing their
own report's verdicts (right 24 PASS / 2 FAIL / 1 NOT TESTED / 1 NO DATA; left
8 / 2 / 1 / 1) with `unreached` down from 4 to 2 on the right board, which is
rows 93 and 94 leaving it. The fixture pack is `s138b/fixtures/config/
_matrix.csv` (`MATRIX_ADDR_HOME`), extended with `Sys001SwLeft001`/
`Sys001SwTalk001` so the S137 proofs reproduce.

`check-no-hardcoded-matrix-addr.py`: OK. `deploy-bench-tools.sh --check`:
guard clean, six station tools and one pair-drop file drifted (this session's
six, plus `d24_bus_probe.py` and `codec4619.py` which S138 built and never
deployed). **Deployed via the script**, backups `*.bak-20260928-180115`,
re-verified, and `--check` afterwards reads "nothing to deploy", 19 of 19 same.
Nothing else on the unit was touched: no rails, no GPIO, no app, no MCU or CPLD
image, no cell write.

## 7. Bench rows QUEUED, not run — in PW's order

1. **The phantom lamp sweep (1.2a)**, once the two-LED fixture exists:
   `d24_patch.py --patch-only --lamp-sweep`. 24 inputs, two presses each. First
   run also answers whether the 50 ms / 300 ms sequence waits are long enough
   to see by eye.
2. **The click/shunt trials (1.2b)**, on the good channels:
   `--click-trials --trial-inputs "…" --click-out …`, 150 Ω plug fitted. The
   table is what PW signs the limits against; watch the `truncated` column.
3. **Absolute dBu levels (1.3)** — already built for noise/EIN (S138-2); the
   gain-law rows are still owed.
4. **The power switch at session end (1.4)** — built and proved in S138, ready
   to run.
5. **MJ1 + PS-MJ**, as part of the mini-jack step of an ordinary analog pass —
   and it needs the H1S3 reflash first (S138b-4), or it reports NO DATA with
   that reason. Also settles S138b-1: does one plug lift MJ_SW, or two?
6. **TF1 + PM-FAN** — TF1 read-only via the panel sense sweep, same H1S3
   precondition. TF1's warm-up half (two readings 10 min apart) is still owed.

## 8. Owed, and to whom

- **mx26**: the catalog rows for 1.2(a), 1.2(b) and the reworded row 93.
  `test-catalog.csv` is generated upstream from this repo's `d24_selftest.py`
  tables plus `docs/spec-d24-selftest.md` prose and is never hand-edited here
  (S138). Today's catalog has no per-input phantom row at all — only the +48
  BUTTON rows 66/67.
- **H1S3 firmware**: a rebuild against a generation that carries both sense
  cells AND reads the nets (MJ_SW, PA1). The shipped image reads neither
  (S138b-4).
- **PW**: S138b-1 (one plug or two), S138b-2 (the NOT LIT label on the move
  screen), the click limits after the trials, the TF1 degree band, and TF1's
  warm-up delta.
