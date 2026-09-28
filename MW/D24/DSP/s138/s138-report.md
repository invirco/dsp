provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S138 — the gaps-doc factory rows: what built clean, what is blocked

Dispatch `tasks.md` 2026-09-28 15:43Z, rulings 1.2–1.4 and 2.2–2.3
(pipeline.md 2026-09-28 07:59 + 08:06, relayed through the dispatch's own
paraphrase — see S138-1, that primary text was not reachable this session).
NO FLASH, NO BENCH: the unit was not contacted, nothing was deployed, no
`AN_EN`/phantom/analog write was made or even attempted.

## What this session actually did

Read six files end to end to place every new line correctly rather than
guess at the architecture: `tools/pi/d24_bus_probe.py`, `codec4619.py`,
`d24_panel.py`, `d24_runall.py` (the `Glass`/`State`/`manual_step`/`measure`
machinery, ~3400 lines), `d24_selftest.py`'s `ITEMS`/`SECTION`/test-function
shape, and enough of `d24_patch.py`'s `Station` class to know where the
lamp-check sweep would land and why this session did not put it there.
Confirmed `test-catalog.csv` is generated in `~/mx26` from this repo's own
`d24_selftest.py` ITEMS/SECTION tables plus `docs/spec-d24-selftest.md`
prose (`tools/d24/build-d24-test-skin.py`) — it is never hand-edited here,
and "build the rows" means wiring the runner, which is what this session did
where it could.

**Built and proved, entirely offline (no serial port, no unit, no display):**

1. `codec4619.find_cell_events(raw, addr)` — the general form of
   `d24_panel.py`'s own `_all_replies`, for any cell resolved by name.
2. `d24_bus_probe.py --mode listen --cell NAME --secs N` — a passive,
   read-only, by-name bus listen (S136's naming discipline; no write, no
   sentinel). Proof: `MW/D24/DSP/s138/find_cell_events_check.py`, 11/11
   checks against synthetic bus bytes and a faked serial layer.
3. `d24_panel.py`: resolves `Sys001SwMiniJack001`/`Sys001SwTempFan001` by
   name (tolerant, like `SW_LEFT`/`SW_TALK`), and `PanelBus.poll()` now
   surfaces both as named events. `UNREACHED['right'][93]`/`[94]`'s reasons
   corrected — "no matrix cell bound" was true when written and is not any
   more; the honest reason now is "no graded check wired yet" (S138-4).
4. `d24_runall.py`: `session_end_power_check()` — ruling 1.4, PS-PWR / row
   134. `manual_step()` already special-cased row 134 as BLOCKED with the
   reason "checked when the session ends, not inside a pass" (pre-S138); this
   is that mechanism. Fires once, after a pass finishes cleanly (never on
   PAUSE or a signal — those are the operator stopping short, not the session
   ending), asks the plain operator-judged question ("did it power down
   cleanly and come back up, twice?"), and records PASS/FAIL on row 134 the
   same way every other operator-judged row does. `--no-power-check` opts an
   engineering re-run out of power-cycling the unit on every invocation.
   Proof: `MW/D24/DSP/s138/session_end_power_check.py`, 10/10 checks, driven
   over a real subprocess's stdin (the `--stdin` path the file already
   documents), no display, no port.

## What is blocked, and why (see findings.md S138-1 … S138-6 for the full case)

- **1.2(a) the phantom lamp-check sweep and 1.2(b) the click/shunt trials
  mode were not built.** (b) is blocked outright: no shunt bit exists
  anywhere in this tree's 595 chain encoding today (`d24_chain.py`'s `byte()`
  is `gain<<2 | phantom<<1 | mute` — 25 bytes, no third control), so there is
  no bit to write and none was invented. (a) needs only the *existing*
  phantom bit and no shunt at all, but its natural home is `d24_patch.py`'s
  1300-line `Station` class, sequencing the same phantom/mute/gain chain the
  mic-pre safety handback depends on, against a physical two-LED fixture PW
  is building that this session cannot see or measure — recorded per
  CLAUDE.md's own model-tiering rule as design-grade/unknown-shape work
  rather than pushed through on a guess (S138-6).
- **2.2/2.3 MJ1/TF1 have read-only infrastructure, not a graded check.**
  Both sense cells are edge-pushed ("both edges are reported" per
  `mx_master.csv`), so a read taken after the operator's physical action —
  the only timing `d24_runall.py`'s existing `MEASURE` mechanism offers —
  cannot be verified correct without a part to test the kernel-buffer timing
  on. Worse for TF1: the same cell's WRITE half drives a real BLOWER/FAN
  (`mx_master.csv:615`), so even "write something harmless to provoke a
  reply" is out of bounds under this dispatch's own "no analog write" rule.
  (S138-4)
- **1.3 absolute dBu levels are already built** for noise/EIN
  (`dsp4_accept.py` `t4()`/`t4b()`, and THD+N-as-% already exists via
  `dbpct()`) — nothing new needed there. Extending the same conversion to
  T1's gain-law rows was NOT done, for lack of the primary ruling text
  (S138-1/S138-2).
- **1.4 power switch is built and proved** (see above) — the only one of
  the five ruled items with no open prerequisite.

## Bench rows queued, in the order PW will do them (none run this session)

Exactly as ruled, nothing added or reordered:

1. **Phantom lamp fixture sweep, per input** — phantom on: are BOTH lights
   on? ENTER / NOT LIT (NOT LIT records "phantom leg fault"); phantom off:
   both dark. Moved input to input like the 150 Ω plug. *(code not built —
   S138-6; needs the physical fixture PW is building)*
2. **Click/shunt trials** — inside the EIN step (150 Ω plug already in),
   shunt engaged, phantom toggled on/off both directions, peak/energy/
   duration table captured for PW to review and sign. Row is INFORMATIONAL
   until signed. *(blocked outright — S138-3, no shunt bit exists yet)*
3. **Absolute dBu levels** via the reference path, every THD+N also as %.
   *(already available for noise/EIN test IDs; not yet extended to T1 — see
   S138-2)*
4. **Power switch at session end** — power down, power up, twice; PASS/FAIL
   recorded on row 134. *(code built and proved this session — ready to run)*
5. **Mini-jack insertion sense (MJ1)** and **PS-MJ** (repeat insertion/
   removal, no bounce) — dummy plug fitted/removed at the mini-jack.
   *(read-only listen primitive built; no graded automated check — S138-4;
   S138-5 flags the catalog's "mini-jack 1, then 2" text against the single
   confirmed connector)*
6. **TEMP/BLOWER/FAN sense (TF1)** and **PM-FAN** (+12 V present, PWM
   pull-down drives, fan turns). *(read-only listen primitive built; no
   graded automated check — S138-4; "a plausible temperature that moves with
   warm-up" also cannot be proven from one reading, and no attempt was made
   to invent a two-point criterion this session)*

## Rules followed

Single trunk; `main` pulled before starting, will be pushed on completion;
this dispatch block's status updated with a short, honest outcome; no AI
attribution in this report, in findings.md, in tasks.md, or in any commit.
No dialogs — the six 🔴-shaped questions above are recorded in findings.md
(S138-1 … S138-6), not asked.
