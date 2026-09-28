provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S145 report — the pin to `defs-v2026.09.28.4`, and signal arrival as the go-ahead

NO FLASH. NO BENCH. Desk-only: nothing was deployed, no SPI, no bus, no serial
port, no GPIO, no rails, no phantom. The unit was not contacted at all.

---

# Part 1 — `defs.lock` at `defs-v2026.09.28.4`, contract regenerated

## 1.1 What landed upstream, and it is two tags, not one

S144's proposals landed as **`defs-v2026.09.28.4`** (defs `dd951d6ca3af73edab9f6b9ec7a38c1179e2269c`).
This repo was pinned at `.28.2` (`b106eb5…`, S140), so the move takes
**`.28.3` as well** — S143's group→aux crosspoint mappings, which never had a
pin of their own. The dispatch header's counts are the `.28.3 → .28.4` slice
(S144's own contribution, and they reproduce exactly); the intake this repo
actually performed is the cumulative one. Both are below, because only one of
them is what `_matrix.csv` now carries.

| product | changed address | new | gone | (S144 slice `.28.3→.28.4`) |
|---|--:|--:|--:|---|
| d24 | 40 (`MainCtr*`, `MainSub*`) | **168** | 0 | 40 / 104 / 0 |
| d32 | 24 (`MainSub*`) | **128** | 18 | 24 / 32 / 18 |
| d16 | 24 (`MainSub*`) | **68** | 18 | 24 / 20 / 18 |
| d12 | 24 (`MainSub*`) | **32** | 18 | 24 / 16 / 18 |

Every "new" row moved OUT of that product's `dsp-unmapped.csv` by the same
count, and every "gone" row moved into it — the two files are complementary and
were checked as such, not counted separately.

- **The 40 d24 changes are the ruled D6/R5 outcome, and nothing else.** Every
  one of them moves a `MainCtr*` (24) or `MainSub*` (16) cell off a generic
  output-strip node onto the dedicated Centre/LF nodes:
  `C2_MAIN_OEQ_03 → C2_CTR_EQ` (19), `C2_MAIN_OEQ_04 → C2_WOOF_EQ` (9),
  `C2_MAIN_OLIM_03 → C2_CTR_LIM` (4), `C2_MAIN_OLIM_04 → C2_WOOF_LIM` (4),
  `C2_MAIN_OUT_03 → C2_CTR_FDR` (1), `C2_MAIN_OUT_04 → C2_WOOF_FDR` (1),
  `C2_MAIN_XOVER → C2_WOOF_XOVER` (2). No other d24 cell changed address.
- **The 18 that go on d32/d16/d12 are the stale `MainSub Comp*` + `MainSub Mtr`
  set**, exactly as S144 recorded them: declared from the superseded
  post-crossover model, dropped by D24's own generation, and those three
  products' masters have not caught up. They are now named in
  `dsp-unmapped.csv` rather than carrying an address. Nothing was built back
  here; it stays recorded for the hub as stale upstream.
- **No definition moved.** `defs.lock`'s only changed lines are `DEFS_COMMIT`,
  `CONTRACT_VERSION` and `DEFS_MANIFEST_SHA256`. Every per-product def, master,
  `fw.csv`, wire-table and cell-master hash is byte-identical to `.28.2`, and
  so is every matrix expansion hash and every matrix generation id. **D24 stays
  on generation `46109e9fb812`** — the generation the flashed unit and the app
  are on. Only the DSP-side landed map moved.
- The `Table` column of `products/*/dsp.csv` is kept from the previously landed
  file per S53, which is why the landed files differ from
  `proposals/defs/products/*/dsp.csv` by most of their rows on that one column
  and by nothing else. `gen_dsp.py`'s own drift check ignores it by design;
  `dsp-unmapped.csv` is byte-identical to the proposal after line endings.

## 1.2 The gates, all of them

1. **Submodule checked out to the tag, gitlink staged, `./sync-defs.sh
   --update-lock`.** Result: `DEFS_COMMIT=dd951d6ca3af73edab9f6b9ec7a38c1179e2269c`,
   `CONTRACT_VERSION=defs-v2026.09.28.4`,
   `DEFS_MANIFEST_SHA256=f614f159fe5fa76714382496adeb5e72e147f3c6e875d9587e40535386af9611`.
   All four matrices re-expanded, all four generations unchanged
   (`c17a20250e22` / `83db0103e482` / `46109e9fb812` / `ea81d22ee149`); D24 and
   D32 staged at `_matrix.expansion.csv` for `gen_dsp.py` to finish, per S44-1.
2. **`gen_dsp.py` with no `--propose` runs clean.** `--check-proposal` first:
   *"check-proposal OK — the graph reproduces the landed dsp.csv /
   dsp-unmapped.csv exactly for d32, d24"* — 724 nodes, 5,999 cell mappings,
   7,250 dispatch entries.
3. **`./regenerate-dsp-contract.sh` end to end, every gate passed:**
   - `tools/dsp/dsp_codegen.py` — 799 SHARC sources regenerated;
   - `sync-defs.sh` — lock + manifest verify, four expansions;
   - `validate-matrix-contract.py` — MxAdd contiguity + family allowlist, passed;
   - `gen_dsp.py --force` — clean; `dsp_params.asm` (chip 2), `ghost_cells.h`,
     `mx_dsp_map.h` (5,890 entries), `dsp_address_map.md` (5,996 rows) rewritten;
   - `gen_input_patch.py --all` — D24 `input_patch.json`, 47 entries / 24 rows;
   - `check-matrix-addresses.py` — **D32 5,890/5,890, D24 3,800/3,800**.
4. **Backfill installed.** `MW/D24/MX/_matrix.csv`, 5,767 rows, generation
   `46109e9fb812`, **3,800 of 3,800 mapped cells carry a DSP address** (1,967
   named unmapped, each with a reason) — S144's predicted 3,632 → 3,800, landed.
   D32 alongside: 8,737 rows, 5,890/5,890. Both `_matrix.expansion.csv` files
   consumed and renamed into place by `gen_dsp.py`; nothing staged left on disk.
5. **Independent determinism check.** `./check-contract-drift.sh` afterwards: a
   second full regeneration leaves the git working tree **exactly** the set of
   files the first one did and not one more.
   `check-sharc-codegen-drift.sh`: 757 generated, **0 differ from the committed
   tree**, 0 emitted-but-absent, 53 hand-written. `audit-compat-aliases.py`:
   `alias-audit.md` unchanged. `check-table-mxdats.py`: 97 Table/MxDatS
   mismatches — pre-existing, reports to the hub, unchanged by this move.

## 1.3 Hashes (post-regen)

```
defs.lock:
  DEFS_COMMIT=dd951d6ca3af73edab9f6b9ec7a38c1179e2269c
  CONTRACT_VERSION=defs-v2026.09.28.4
  D24_MATRIX_GEN=46109e9fb812     (unchanged)
  D32_MATRIX_GEN=ea81d22ee149     (unchanged)

defs/products/d24/dsp.csv            37d6e3038c1a9021928028e4edab20cffab7e584e6d5d2e867744b746bc522b6
defs/products/d24/dsp-unmapped.csv   dae967e2c05e7c2ea15d61e35946004fc7e437327d56de49a6b44c3a2cf762b9
defs/products/d32/dsp.csv            2f1876504c241b0ae4b1e39003ca72b6fd154e056d578fed01d261dae26cb9ce

MW/D24/MX/_matrix.csv  (installed)   6f7a06cb52a6addd6483cbfd1ad07683ad59c54e0add5f9974ef68961bdcc77b
MW/D32/MX/_matrix.csv  (installed)   e14dc43b4e19af217e6ddfb163ab8a46f0a73635fb30619587c1216ce726ab7a
MW/D32/DSP/ghost_cells.h             83bd4f866b5b5abcabc76a5c78718d7ce34b9878d173e9a28a3edd95446aaefd
MW/D32/DSP/dsp_address_map.md        77bdb4faa4821fd3ac74f5f0a5f761bf32dd870ae27a3a0e875c9f17e4ea751c
```

## 1.4 What the regeneration says and this session did not act on

`gen_dsp.py`'s validation reports **104 DSP cells the graph reaches that are in
no `_matrix.csv` row** — `Main001AntiFb*` and the rest of S144's item 4 on the
D32 master. It is not a regression of this move: the graph has not changed since
S144 and neither has the D32 expansion, so the number was already 104 before the
pin advanced. It is an upstream gap (the D32 mx-master does not declare cells the
D32 graph will answer on) and it is recorded, not papered over — see finding
S145-1. The three long-standing uncatalogued-node warnings (`C2_HPT_01`,
`C2_MAIN_COMP`, `C2_MAIN_LIM`) are unchanged.

---

# Part 2 — the patch loop: signal arrival is the go-ahead

PW, `pipeline.md`, 2026-09-28 ~18:1x BST, verbatim: *"when input signal cables
are moved, they are automatically detected, and if so they can be measured and
pass/failed and prompt next move without a required enter; a button would only
need to be pressed to move on if signal is not detected."* This supersedes the
09-26 speed review's "ENTER still decides" for every patch the detector can see.

## 2.1 Arrival is the go-ahead, and it is the default

`--auto-advance` is no longer a flag that is off; it is what the station does.
`Station(auto_advance=True)`, the CLI default, and **RUN ALL passes no mode of
its own at all** — `d24_runall.patch_station` takes both the patcher and the
station from their own defaults, so the two paths cannot drift into being two
different tests wearing one name (which is the fault S126 had to fix once
already). `--confirm-enter` is the 09-26 loop, kept for a before/after timing
run and for the S128 glass-button regression, and for nothing else.

**No ENTER anywhere on a detected patch.** Proved over a whole dry run of the
91-patch list: 241 distinct screens, **not one carries an `enter` button, and
not one of them names ENTER in its instruction, status, action, extra or
lead-line.** `LV.instruction_for(..., confirm=False)` ends in a full stop; the
"Signal found - press ENTER." hint is replaced on this path by
`SIGNAL_HOLDING` = "Signal found - hold still.", which asks for nothing.

## 2.2 The stability window: three blocks, two readings, 1.0 dB

The old detector returned on the FIRST poll in which the lane had risen, and the
first such poll is in the middle of the operator's hand movement — an XLR
latches after its pins mate, a TRS is wiped along its travel, a mini-jack passes
through both legs shorted. On the ENTER path a bad reading there was caught by
the pre-arm's own `PREARM_STABLE_DB` at the press; with no press there is nothing
behind it. So the step now ends when the lane has been **present and steady**,
and not when it first went loud. Nothing is graded mid-insertion.

- **N = 3 instrument blocks = 256 ms.** The block is `TEST_MEAS`'s own
  (4,096 samples at 48 kHz, `WIN_S` 85.3 ms). Three because it must outlast the
  mechanical event — S125 measured the strip meter decaying at 6.52 dB/s and the
  gain step needing 167 ms to read the node honestly, and 256 ms is longer than
  both — and because it must stay small against the operator's own hand: at
  S123's projected 3–8 s per move it is 3–8 % of one step, spent while their
  hand is still on the connector.
- **Steady is 1.0 dB across the window.** The instrument here is the strip
  meter, a peak-hold latch, not the measurement node: a continuous sine reads
  flat on it and anything that moves the connector moves it by far more than a
  dB. 1.0 dB is twice the 0.5 dB the node is held to, on an instrument at least
  twice as coarse; a reading that passes it and is still wrong is caught
  downstream by `rms_spread`.
- **The window SLIDES.** Measured from the first poll it never recovers: a
  connector that wobbles 4 dB as it seats leaves a 4 dB spread in the list, and
  the spread would still be 4 dB a minute after the lane went still. The test is
  about the last 256 ms, so that is what it reads.
- **Two readings, not three, and this was measured rather than reasoned.** A
  poll is 50 ms plus the read. On the 24 mic strips the read is a meter word and
  costs nothing (S121: all twenty-four in 32 ms), so the window carries five or
  six readings. **The three codec return lanes — the talkback XLR and the two
  mini-jack legs — have no meter**, so `watch` reads the measurement node and
  that costs one 85.3 ms window: a poll there is ~135 ms and the same window
  carries TWO. A three-reading rule reads as stricter and is not — it is simply
  unsatisfiable on those three lanes, and the dry run ran all three (`P59`
  TALKBACK, `P90`/`P91` MINI-JACK) to the timeout on a good unit until this was
  two. Two is what makes it a window rather than a point, and it is the floor the
  coarsest lane on the unit can deliver.
- **A break restarts it.** One poll of tone that goes away again does not grade
  and does not shorten the next window. Proved against a control: a clean
  insertion and an insertion interrupted for four polls, and the interrupted one
  cannot come in before the clean one plus the interruption.

## 2.3 NO SIGNAL is the only button

The panel loop's NOT LIT pattern, one station along. `buttons_for` returns
`['nosignal', 'pause']` for **every** `WAITING` and `CHECKLEAD` screen on this
path — before this change `confirm=False` fell straight through to `['pause']`,
so auto-advance drew a screen on which the operator could say nothing at all
about a socket that would not carry, which is the one thing PW's ruling says a
button is still for. `Live.command()` accepts `nosignal` (a button the screen
draws and the reader drops is a dead button — S137's fault), and the dialog
channel carries it too.

- **A press records the row FAIL "no signal detected"** — PW's words — on every
  sub-test of the patch, with the detail "the operator said no signal reached
  MIC n; no tone was on any other input either", and the walk advances at once.
- **It is the operator's judgement about the PATH, which is why it is a FAIL and
  `nodata` is not.** The station's standing rule that a wrong patch is a prompt
  and never a fail holds: `detect` sweeps every lane before it will honour the
  press, so a tone anywhere on the unit sends the operator back to re-patch
  instead of landing this row. The station's own giving-up stays NO DATA.
- **The station owns its own screen.** Under RUN ALL one `Live` is built for the
  whole pass with `confirm=True`, which is right for the setup pages because they
  really do ask for ENTER. Left alone, every waiting screen this station wrote
  under RUN ALL would have carried a dead ENTER — S137's fault again, one station
  along. The station takes the flag for as long as it owns the screen and
  `teardown` gives it back.

## 2.4 The timeout raises the question and decides nothing

`detect_timeout_s` is the list's own **20.0 s** in every list in the tree. It used
to END the step, which on the ENTER path was harmless (the caller swept and
re-prompted) and on this one would be a station giving up on a socket while the
operator was still walking back to it. Now the red screen goes up — "Nothing has
arrived at MIC 5 for 20 seconds.", one plain action, NO SIGNAL under it — and the
loop carries on watching, so **a lead pushed home after the prompt still advances
the step on its own** (proved: the step ends `rise` at t > 20 s). The hard bound
is the same number again: asked at 20 s, given up at 40 s. The ENTER path is
untouched and still ends at its own deadline.

## 2.5 Wrong input, named while they are standing there

Every second while nothing is arriving on the asked-for lane, all twenty-four
mic strips are swept (32 ms, S121) and a tone on another one is named in PW's own
shape — **"Signal on MIC 7, expected MIC 5."** — with one plain action under it.
Before this the sweep only ran when a step had already failed to detect, so a
lead in the wrong socket was silent for the whole 20 s. It grades nothing and
records nothing: the only output is the line the operator reads, and it **comes
down again** when the lead reaches the right socket, so no stale accusation is
left on the glass. A NO SIGNAL press while a tone is on another input is refused
and the patch is offered again. Cost: 26.2 s over a 91-patch pass, booked under
"looking for a misplaced lead", entirely behind the hands.

## 2.6 The removal edge

A lane that is **already carrying when the prompt goes up** cannot be graded
until it has been seen to fall back by the same threshold an arrival has to
clear. This is not defensive: it is the real shape of two kinds of patch in the
list — "Move the other end to AUX 2" leaves the lead in the same socket, and the
terminator swap does too — and without it the detector would grade a socket the
operator has not touched yet. Proved both ways: a lane that never changes is
never graded however loud it is, and a removal followed by an arrival is. The
prompt-time level also seeds the quietest/loudest extremes, which it did not
before.

## 2.7 The ENTER channel, and why it is still wired

`Live.command` carries `enter`, `pause`, `start`, `exit` and `notlit` because
something app-side already draws each of those. **`nosignal` is new, and whether
the deployed factory app draws it cannot be settled from this repo — the app is
not in it.** That is the same wall S138b hit over STILL LIT. So the ENTER
channel, which certainly reaches this station, is given the same answer in two
presses: the first raises the question, the second, with the question already up,
is the answer. And the USB keyboard is read on both paths now — it used to be
switched off whenever a press could only mean "the lead is in", and PW's ruling
gives it something to say.

Nothing about that weakens the ruling, and it is asserted four ways: ENTER on an
arriving patch does not end it early; one ENTER on a silent lane records nothing;
the second ENTER, with the question up, is the answer; and however many ENTERs
arrive, a tone on another input is never graded as the asked row.

## 2.8 What this costs and what it saves

Dry run, the 91-patch list, same unit model, the two paths side by side:

| hand move | arrival is the go-ahead | ENTER decides |
|---|---|---|
| 3 s | 273 s hands + 126 s machine = **6.7 min** | 346 s hands (273 + 73 pressing) + 98 s machine = 7.4 min |
| 5 s | 455 s hands + 126 s machine = **9.7 min** | 528 s hands (455 + 73 pressing) + 98 s machine = 10.4 min |
| 8 s | 728 s hands + 126 s machine = **14.2 min** | 801 s hands (728 + 73 pressing) + 98 s machine = 15.0 min |

73 s of pressing comes off the operator's path at every hand speed. The machine
figure rises by 28 s, and where it goes is stated rather than hidden: the
wrong-input sweep is 26.2 s of it (and is in both columns), and the ENTER path's
40.4 s of pre-armed readings become 33.4 s of ordinary settled readings here,
because a step that ends on the signal has nothing to pre-arm for. Worst block is
1.876 s a step against 5.0 s of hand, so none of it is time the operator waits.

**The ruling changes WHEN a patch is graded, not HOW.** Asserted: the same 246
readings, patch for patch, sub-test for sub-test, with the same verdicts on both
paths (FAIL 24, NO DATA 1, PASS 221) — and the same as the committed tree before
this session.

## 2.9 S138b still works

- The **mini-jack insertion sense** is still drained from inside this wait loop,
  which is what makes the edge free; `mj_sense_check.py` green, 37 checks.
- The **phantom lamp sweep** still asks with ENTER and NOT LIT and is untouched
  by the ruling: it judges two LEDs with an eye and has no signal to detect, so
  there is nothing for arrival to be the go-ahead of. `lamp_sweep_check.py`
  green, 41 checks, and the lamp screen still draws `['notlit', 'pause']`.
- Factory-screen-simple rule holds: a waiting screen still carries the
  instruction, the status line, `n of N` and its buttons and nothing else, and
  every instruction still fits the glass.

## 2.10 The proofs

| proof | checks |
|---|--:|
| `MW/D24/DSP/s145/patch_auto_advance_check.py` (new) | **85, all green** |
| `MW/D24/DSP/s128/glass_buttons_check.py` (the ENTER path) | OK |
| `MW/D24/DSP/s137/panel_glass_buttons_check.py` | OK, 23 screens |
| `MW/D24/DSP/s138b/{mj_sense,lamp_sweep,click_trials,shunt_sequence,sense_sweep}_check.py` | 195, all green |
| `MW/D24/DSP/s138/{session_end_power,find_cell_events}_check.py` | 21, all green |
| `d24_patch.py --strings` → `d24_runall.py --check-md` | clean — no Matrix-internal vocabulary |
| `d24_patch.py --screens` (24 screens incl. 2 new) | enumerated; no frame, no display on the desk |
| `deploy-bench-tools.sh --check` | guard clean; would deploy the 3 changed files |

`glass_buttons_check.py` now passes `--confirm-enter` explicitly, with the reason
in the file: it is S128's regression for the ENTER path, and on the default path
there would be no ENTER for it to check. Its opposite — no ENTER anywhere, NO
SIGNAL on every waiting screen — is asserted by the new proof.

Two new screens are in the `--screens` walk so they can be photographed on the
unit: `14b-no-signal-recorded` and `16b-terminator-holding`.
`13-wrong-socket` and `14-no-signal` now carry the ruled status lines.

## 2.11 NOT DEPLOYED, and why

`deploy-bench-tools.sh --check` is clean and would deploy exactly the three
changed files (`d24_patch.py`, `d24_live.py`, `d24_runall.py`; repo md5s
`d5c8065e…`, `535743c8…`, `ee4e6184…`). **It was not run.** See finding S145-2:
the ruled screen's one button is `nosignal`, and until the factory app draws it,
deploying would put PW's next live pass on a screen where a patch that will not
detect can only be escaped with PAUSE (which ends the pass) or with a USB
keyboard, which S123 recorded as not present on the unit. The two-press ENTER
fallback of §2.7 needs a channel the operator can reach, and on the armed factory
screen there are no dialogs. So the deploy is queued behind one app-side
question, and it is one line for the hub to answer.

---

# Findings

**S145-1 — 104 cells the D32 graph will answer on that the D32 master does not
name.** Reported by `gen_dsp.py`'s own validation at every regeneration:
`Main001AntiFb*` and the rest of S144's item 4. Not a regression of this move
(the graph and the D32 expansion are both unchanged since S144, so the count was
already 104 at `.28.2`); it is an upstream gap, and the consequence is that the
DSP has live SPI addresses no product definition declares — the same shape as the
three long-standing uncatalogued-node warnings. Owed to the hub: either the D32
mx-master declares them or the graph stops reaching them.

**S145-2 — 🔴 the ruled screen's one button needs the factory app, and the app is
not in this repo.** `Live.command` carries `enter`, `pause`, `start`, `exit` and
`notlit` because something app-side already draws each; `nosignal` is new. S137
added `notlit` through this repo alone and it worked on the glass, which means
either the app draws an arbitrary button name or `notlit` already existed
app-side — and which of those is true **cannot be established from here**, and
settling it would need the unit, which this dispatch forbids. Consequence if the
app does not draw it: on a patch that will not detect, the glass carries only
PAUSE, and PAUSE ends the pass. Mitigations built: the two-press ENTER fallback
(§2.7) and the USB keyboard re-enabled on this path — but the armed factory
screen draws no dialogs, and S123 recorded that no keyboard is on the unit. So
the three station files are **built, proved and not deployed**, and the hub's
answer is one of: (a) confirm the app draws unknown buttons, and deploy; (b) add
NO SIGNAL to the app, then deploy; (c) deploy anyway and accept PAUSE as the
escape.

**S145-3 — the stability window cannot be three readings, and the reason is a
hardware asymmetry worth writing down.** The talkback XLR and both mini-jack
legs have no strip meter, so the auto-advance reads the measurement node for
them and one read costs an 85.3 ms window — a poll cadence of ~135 ms against
50 ms on the 24 mic strips. A window stated in READINGS rather than in TIME is
therefore not portable across the lanes of one unit: three readings in 256 ms is
satisfiable on 24 of 27 lanes and impossible on the other three, and the failure
mode is silent (those three patches run to the timeout on a good unit). Stated
here because the same asymmetry will bite anything else that times a per-lane
poll: **the three codec return lanes are an order of magnitude slower to watch
than a mic strip.**

**S145-4 — the dispatch header's counts are S144's slice, not this repo's
intake.** `.28.3` was never pinned here, so advancing `.28.2 → .28.4` takes
S143's group→aux crosspoints as well: d24 takes 168 new cells, not 104. Both
figures are in §1.1. S144's own report carries the same seam — its table says
+104 while its prose correctly predicts 3,632 → 3,800 (which is +168) — so the
prose was right and the table was the slice. Nothing is wrong in the artifact;
the number to quote for this repo is 168.

---

# Not touched

No flashing. No app deploy. No station-tool deploy. No SPI, no matrix bus, no
serial port, no GPIO, no rails, AN_EN never raised, no phantom, no 595 chain
write, no display. The unit's state is whatever S138b left it and was not
re-verified here, because nothing in this session could have changed it.

# Outcome

🟢 Both parts done, with one item recorded rather than guessed past.

- **Part 1 closed.** `defs.lock` at `defs-v2026.09.28.4`, `gen_dsp.py` clean
  with no `--propose`, `./regenerate-dsp-contract.sh` passes every gate end to
  end, D24's DSP-address backfill for generation `46109e9fb812` installed at
  3,800/3,800 (D32 5,890/5,890), determinism re-checked independently.
- **Part 2 built and proved desk-side**, 85 new checks green and every earlier
  proof still green. **Queued, not done: the deploy**, behind S145-2 — one
  app-side question about whether the factory screen can draw a NO SIGNAL
  button.
