provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S131 runbook — the D24 matrix switch-over (desk only; do NOT execute from this document)

Written for S134 (overnight, no hands). Nothing below was run on the unit
except the dry run in §6, which built into scratch directories under
`/home/app/s134fw/` and was deleted afterwards — the unit was never flashed,
no rail or GPIO state was touched, and `app cli loadfw` was never invoked.
PW runs the real thing tomorrow (2026-09-28) with the hub.

Background: `mx26 docs/investigation-matrix-generation-2026-09-27.md` (read in
full before starting). Summary: MW-D24-2 is running matrix generation
`e80ccab5d6d8` (the unit's own 2026-08-18 pack, 5412 names, `Sys001Skin001` =
5412) — a generation built before S0 from a pre-purge master, not from any
defs tag. The target is `f9677e5fae5e` (5006 names, `Sys001Skin001` = 4698),
which is what `defs-v2026.09.27.3` publishes and what dsp's own
`defs.lock` already pins (`D24_MATRIX_GEN=f9677e5fae5e`). `defs-v2026.09.27.5`
is the mx26 pin target for tomorrow; its two commits over `.3`
(`mic-gain-codes.csv` schema + `defs-publish.sh` portability) do not touch
the D24 matrix, confirmed by `git -C defs log defs-v2026.09.27.3..defs-v2026.09.27.5`
here — **the matrix itself is `.3`, unchanged since**.

**This is not an incremental patch.** Comparing the unit's live pack against
this repo's own `MW/D24/MX/_matrix.csv` (same generation as the published
`_matrix.csv` — `matrix_gen_id.py` reports the same base-id `f9677e5fae5e`
and the same `Sys001Skin001` = 4698 for both; only the exact CSV bytes differ,
because this copy carries `gen_dsp.py`'s DSP-address backfill columns the
raw published export does not):

| | count |
|---|---|
| names only on the unit (pre-purge `Aa*`, `Main[2-4]`, `Rtg*`, …) | 3309 |
| names only in the target generation (incl. the 2 new cells) | 2903 |
| names in both | 2103 |
| **names in both at the same address** | **0** |

Every one of those 2103 shared names moves. Confirmed by dry run (§6): the
newly generated `matrix.h` and the flashed one disagree on literally every
line but the three-line header comment.

---

## 1. Backups — take ALL of these before touching anything

| what | path on unit | backup as | current value (verified live tonight) |
|---|---|---|---|
| app binary | `/home/app/app` | `/home/app/app.bak-s131-pregen` | md5 `b05e9fd55e15289e6529f66c72778e33` (mx26 `b05e9fd5`) |
| matrix pack | `/home/app/config/_matrix.mxc` | `/home/app/config/_matrix.mxc.bak-s131-pregen` | sha256 `5ff4c99107da31d4842701a57a9fff3677384c96834166d26eedcbb86c0190d2` |
| integrity manifest | `/home/app/config/matrix-integrity.json` | `/home/app/config/matrix-integrity.json.bak-s131-pregen` | already mismatches its own pack (BuildTs 260714102659, pre-existing, not this session's doing) |
| H1S1 image | `/home/app/firmware/H1S1.shex` | `/home/app/firmware/H1S1.shex.bak-s131-pregen` | md5 `272868c889fc87ead0a3b4bb277f55e2` |
| H1S3 image | `/home/app/firmware/H1S3.shex` | `/home/app/firmware/H1S3.shex.bak-s131-pregen` | md5 `a0db4f65ed61a99f76c8f6ebd00df893` |
| H1S4 image | `/home/app/firmware/H1S4.shex` | `/home/app/firmware/H1S4.shex.bak-s131-pregen` | md5 `1222e007920015d4cdd8ec9426a288d3` |

`/home/app/fwbuild/pack-backup-H1S3.shex` and `pack-backup-H1S4.shex` already
exist from earlier sessions and match the currently-flashed images by name
convention — take the `.bak-s131-pregen` copies anyway so this window has its
own, unambiguous rollback set. Verify every backup's md5/sha256 against the
table above immediately after copying, before step 2 starts.

**ONE-COMMAND ROLLBACK, any time, any step:** restore all six files from
their `.bak-s131-pregen` copies (never piecemeal — the mx26 doc's own rule),
`sudo systemctl restart matrix-app`, and re-flash the three `.bak-s131-pregen`
`.shex` files with `app cli loadfw H1S1` / `H1S3` / `H1S4` if any panel MCU
was reflashed with the new pair. If no panel MCU was reflashed yet, the
`app`+pack+`matrix-integrity.json` restore alone is enough.

---

## 2. Ordered steps

### Step 1 — App (hub executes)
Build mx26 `main` HEAD (`2c21aa2`, includes `5cf57b2` FactoryView) as
`dotnet publish src/sw/app/app.csproj -c Release -r linux-arm64
--self-contained -p:PublishSingleFile=true` (the same procedure
`docs/runbook-cm4-starter.md` step 2.4 uses for a fresh unit). Copy the
published binary to `/home/app/appUpdate`, then `sudo systemctl restart
matrix-app` — the unit's own `ExecStartPre` does the atomic rename to
`/home/app/app` and runs `validate-app.sh`; this is the unit's normal update
path, not new. Confirm the new binary's md5 in the boot log / `ls -l
/home/app/app` before moving on.
**Rollback:** `cp /home/app/app.bak-s131-pregen /home/app/app && sudo
systemctl restart matrix-app`.
**Time:** dotnet publish is a few minutes on the hub's own machine (not
timed this session — the hub has real numbers from routine use); the restart
+ validate is under 10 s on the unit.

### Step 2 — Pack
Stop `matrix-app` (`sudo systemctl stop matrix-app`; already stopped for the
whole window per the "one window, together" rule). Copy the published
`_Matrix/Products/D24/pd/generated/_matrix.mxc` to
`/home/app/config/_matrix.mxc`. Verify sha256
`c66a9d4bdb71e2f081af17365c038d5878f4858cc67b2de7fb61a7409c48fa68` (per the
mx26 investigation doc — reverify against the Dropbox file at execution time,
don't trust this document's copy of the hash). Delete
`config/matrix-integrity.json` (it already mismatches today's pack and
nothing regenerates it automatically) or regenerate it if there's a known
generator — check before assuming there isn't one.
**Rollback:** restore `_matrix.mxc` (and `matrix-integrity.json` if kept)
from `.bak-s131-pregen`.
**Time:** under 1 minute (one file copy + one hash check).

### Step 3 — Panel headers: regenerate `matrix.h`
Both H1S3 and H1S4 (and H1S1 — see step 6) share one `matrix.h`: every cell
name in the published `_matrix.csv`, `#define <Name> <Address>`, sorted by
address ascending, with the same three-line header comment style the current
file uses (adjusted to name the new generation instead of the app build id —
see §6 for the exact generator used in tonight's dry run, which needs only
the CSV's `_Cell`/`MxAdd` columns). Copy the regenerated `matrix.h` into
`H1S1/Core/Inc/`, `H1S3/Core/Inc/`, and `H1S4/Core/Inc/`, replacing the
existing file in each build tree.
Then: `python3 defs/tools/matrix_gen_id.py --compare <published _matrix.csv>
<matrix.h>` for each — must report `ALIGNED (full-id f9677e5fae5e, base-id
f9677e5fae5e)`. Tonight's dry run got exactly that (§6).
**Rollback:** the three build trees' `matrix.h` files are source, not
on-unit state — restoring them costs nothing (they're never flashed by
themselves). If images were already built/flashed from a bad header, the
rollback is step 1's whole-set restore.
**Time:** under 1 minute per board (script + one compare command); ~3
minutes for all three.

### Step 4 — H1S4 (left panel): bind `Sys001SwLeft001`
Add `Sys001SwLeft001` to `MATRIX[]` and its parallel enum
(`pSys001SwLeft001`), then repoint **every** `pSys001Skin001` reference in
`rsw[]` (6 entries) and `wled[]` (9 entries) to `pSys001SwLeft001`. Nothing
else changes — same pins, same radio indices 1–6, same "white pair"
groupings. This is a pure data-table edit: `RdRadioSwitch()`/`WrRadioLed()`
are generic and data-driven (`sizeof(rsw)/sizeof(rsw[0])` loops), so no GPIO
init / `.ioc` change is needed. Verified by dry-run build tonight — clean
compile, `text` +4 bytes (§6).
**Rollback:** re-flash `H1S4.shex.bak-s131-pregen` via `app cli loadfw H1S4`.
**Time:** build ~10 s (dry-run measured). Flash time not measured this
session — time it live on the FIRST board flashed and use that figure for
the rest of the estimate.

### Step 5 — H1S3 (right panel): bind `Sys001SwTalk001` — 🔴 SEE THE OPEN QUESTION BELOW
`defs/products/d24/fw.csv` gives the physical binding: `TB_SW` = PA13
(radio index 1), `TB_LED0` = PF6 (index 1), `TB_LED1` = PF7 (index 2). All
three pins already exist as `#define`s in H1S3's `main.h` and are already
brought up by `MX_GPIO_Init()` (PA13/PF6/PF7 sit in the same
`GPIO_MODE_INPUT`/`GPIO_PULLUP` blocks every other radio-switch and
radio-LED pin on this MCU starts in — `WrRadioLed()` reconfigures a pin to
`GPIO_MODE_OUTPUT_PP` at scan time regardless of its boot-time mode, the same
trick every existing LED entry relies on). So the *mechanical* part — adding
`Sys001SwTalk001` to `MATRIX[]`/enum — is exactly like step 4 and was
dry-run built clean tonight (§6, `text` +4 bytes).

**But the cell's own defs note is explicit that ordinary `rsw[]`/`wled[]`
one-hot semantics don't fit it, and this session did not attempt to write
that logic — see §7.** The mechanical-only build (identifier declared,
nothing bound to it yet) is a safe interim: it changes nothing observable
(catalog row 92 stays NOT TESTED, exactly as today), so if §7 isn't resolved
in time this step can ship as "declared but not yet wired" without blocking
the rest of the window.
**Rollback:** re-flash `H1S3.shex.bak-s131-pregen` via `app cli loadfw H1S3`.
**Time:** build ~10 s once the logic (if any) is decided. Flash time as
step 4.

### Step 6 — H1S1: check and rebuild
H1S1 (`Core/Inc/matrix.cs`) carries the **same** `matrix.h` and the same
base four cells (`Enc001`, `Skin001`, `Test001`, `Test002`) as H1S3/H1S4, but
declares no `rsw[]`/`wled[]` of its own — `Sys001Skin001` is declared and
never otherwise referenced in its source. It still needs the header swap
(step 3) and a rebuild so its `Sys001Skin001` reads 4698 rather than 5412 —
otherwise H1S1 and the running app/panels would disagree about what that
address even is, per the mx26 doc's own warning. Dry-run rebuilt clean
tonight with `text`/`data`/`bss` byte-for-byte unchanged (as expected — only
`#define` values changed, no new symbols) (§6).
**Rollback:** re-flash `H1S1.shex.bak-s131-pregen` via `app cli loadfw H1S1`.
**Time:** build ~15 s (dry-run measured, STM32U575/Cortex-M33 — slightly
more source than H1S3/H1S4). Flash time not measured.

### Step 7 — Build each `.shex`
From each `Debug/H1SxN.hex` (built by `make -f makefile all` from the
project's own `Debug/`, after the one-line Windows-path fix in the makefile
— see `MW/D24/DSP/s129/data/panel-build-repro.md` §3, reproduced again
tonight):
```
python3 /home/app/fwbuild/hex2shex.py H1S1.hex H1S1 H1S1.new.shex
python3 /home/app/fwbuild/hex2shex.py H1S3.hex H1S3 H1S3.new.shex
python3 /home/app/fwbuild/hex2shex.py H1S4.hex H1S4 H1S4.new.shex
```
Dry-run tonight: H1S1 2174 records / 34737 bytes, H1S3 1364 records / 21788
bytes, H1S4 924 records / 14748 bytes (§6) — all comfortably close to the
currently-flashed sizes (34K/21.7K/14.4K).
**Rollback:** N/A (build artifact, nothing on the unit yet at this point).
**Time:** instant (objcopy + a small Python script), well under a minute for
all three.

### Step 8 — Flash H1S3 + H1S4 (+ H1S1) together
Copy each `H1SxN.new.shex` to `/home/app/firmware/H1SxN.shex` (this is
literally where `app cli loadfw <name>` reads from — confirmed tonight:
`app cli loadfw --help` errors looking for
`/home/app/firmware/--help.shex`), then:
```
app cli loadfw H1S1
app cli loadfw H1S3
app cli loadfw H1S4
```
one at a time, checking each MCU's own verify/ack before moving to the next
(this is the same path the 2026-08-21 H1S1 SPI-fix reflash used —
`MW/D24/HW/hardware-map.md` §"the second master is GONE"). "Together" means
in the same maintenance window with matrix-app stopped throughout, not
literally one command — nothing here suggests `loadfw` takes more than one
name.
**Rollback:** re-flash the matching `.bak-s131-pregen` `.shex` for whichever
board(s) were touched.
**Time:** unknown — not timed this session (no flash was performed). Time
the FIRST board live and use it to estimate the rest; three boards of this
size should not be a large fraction of the window.

### Step 9 — Reboot
`sudo systemctl start matrix-app` (or reboot the unit outright, if that's
the hub's normal post-flash habit). 
**Rollback:** step 1's whole-set restore, then restart/reboot again.
**Time:** app start + DRM/panel bring-up, a few seconds to ~10s based on
routine boots.

### Step 10 — Verify
- Boot log: `Matrix generation base-id f9677e5fae5e (5006 names / 5006
  addresses, max 5006)` (grep the app's own log, same line format the mx26
  doc quotes for the current `e80ccab5d6d8` boot).
- `Sys001Skin001` = 4698 on the right panel; a left-panel press arrives on
  5005 and **never** on 4698 (the aliasing this whole change exists to
  remove); a talkback press (once step 5's logic lands) arrives on 5006.
- An EQ gain change lights **no** panel indicator (today it would light the
  left board's index-3 pair, since that's the aliased `Main004EqGain001` =
  5005 = old `Sys001Skin001` index 3 collision named in the mx26 doc).
- `grep "MCU verified" /home/app/logs/log` for all three boards (the same
  check `d24_selftest.py`'s `handback()` already does — see
  `MW/D24/DSP/s129/data/panel-build-repro.md`).
- Record the md5 of every flashed `.shex` (and the app binary, and the pack)
  on the gate line, per the mx26 doc's own closing instruction.
- Run a fresh automatic self-test pass (`--auto-only`, as this session's §
  fix to `d24_selftest.py`/`d24_runall.py` now handles NW4 and a died batch
  correctly) to confirm nothing else regressed.
**Rollback:** any verify failure → step 1's whole-set restore, not a partial
fix-forward.
**Time:** a few minutes for the checks above, plus one automatic-set pass
(~150 s, measured this session in §5 of the S134 report).

---

## 3. Total time (best estimate)

| step | time |
|---|---|
| 1 App | hub's own dotnet publish (minutes, not timed here) + <10s restart |
| 2 Pack | <1 min |
| 3 Panel headers | ~3 min (all three boards) |
| 4 H1S4 bind | ~10s build + unmeasured flash |
| 5 H1S3 bind | ~10s build (mechanical part) + unmeasured flash — blocked on §7 for the real binding |
| 6 H1S1 rebuild | ~15s build + unmeasured flash |
| 7 Build .shex | <1 min, all three |
| 8 Flash | unmeasured — time the first board live |
| 9 Reboot | ~10s |
| 10 Verify | ~5 min + one ~150s automatic pass |
| **Total** | dominated by the app publish and the three unmeasured flashes; everything DSP-side that could be dry-run tonight is seconds, not minutes |

## 4. Steps needing PW at the bench
Probably none strictly, but a look at the panels after step 9 (to visually
confirm the left board no longer lights on EQ gain changes, and that a
talkback press does something sensible once §7 is resolved) is cheap
insurance and matches "a look at the panels" from the dispatch.

## 5. Pre-checks for tomorrow, before starting
- `deploy-bench-tools.sh --check` on the Pi tools (this session found and
  fixed a real, previously-unnoticed drift in `d24_selftest.py` — don't
  start the window with a second one).
- Confirm the unit is in the state this session left it: AN_EN low, CS_M
  high, chain SAFE, `app` still `b05e9fd5`, `d24-testui` active,
  `matrix-app` inactive, no `d24_runall.py`/`d24_selftest.py` running.
- Verify all six `.bak-s131-pregen` backups exist and their hashes match
  §1's table BEFORE step 2 touches anything.
- Re-fetch the published `_matrix.csv`/`.mxc` from Dropbox `_Matrix` fresh
  (don't reuse a stale local copy) and re-verify their hashes against the
  mx26 doc's stated values — this document's copies of those hashes are
  second-hand and should not be trusted over the live file.

---

## 6. Tonight's dry run (evidence, nothing flashed)

All work done in `/home/app/s134fw/{H1S1,H1S3,H1S4}/`, `rsync -a` from
`/home/app/fwbuild/{H1S1,H1S3,H1S4}/`. Deleted after. `arm-none-eabi-gcc
(15:14.2.rel1-1) 14.2.1` — the same toolchain S129 proved gives a
byte-identical rebuild of the currently-flashed H1S3/H1S4 images from
unmodified source.

- `matrix.h` regenerated from this repo's `MW/D24/MX/_matrix.csv` (5006
  `#define`s, sorted by address) — `matrix_gen_id.py --compare` against the
  csv itself: `ALIGNED (full-id f9677e5fae5e, base-id f9677e5fae5e)`.
  Diffed against the currently-flashed `matrix.h`: 3309 names only on the
  unit, 2903 only in the new generation, 2103 shared, **0 shared at the same
  address** — matches the mx26 doc's own count (off by exactly +2, the two
  new cells, since that doc compared against `.24.2` which predates them).
- H1S4: `Sys001SwLeft001` added to `MATRIX[]`/enum, all 6 `rsw[]` + 9
  `wled[]` entries repointed from `pSys001Skin001`. Built clean: `text`
  13868→13872 (+4, one new `MATRIX[]` word), `data` unchanged, `bss`
  1916→1924 (+8, one new `matrix[][]` row). `.shex`: 924 records / 14748
  bytes (md5 `88ff6305130b81d2abbd7f890c663707`).
- H1S3: `Sys001SwTalk001` added to `MATRIX[]`/enum only (no `rsw[]`/`wled[]`
  binding — see §7). Built clean: `text` 20572→20576 (+4), `data`/`bss`
  unchanged. `.shex`: 1364 records / 21788 bytes (md5
  `ef89709fc81c21544d8c88d2d78e2838`).
- H1S1: `matrix.h` swapped only, no source change. Built clean: `text`
  34080, `data` 657, `bss` 1940 — **identical** to the pre-change build (as
  expected: no new symbol, only `#define` values changed). `.shex`: 2174
  records / 34737 bytes (md5 `cd4cc76179b7952839abc9210de5f4b7`).
- All three source trees, the generated `matrix.h`, and the three `.shex`
  outputs are archived under `MW/D24/DSP/s134/gen/` in this repo.
- Nothing was flashed. No `app cli loadfw` call was made. No GPIO/rail state
  was touched by any part of this exercise.

---

## 7. 🔴 OPEN QUESTION FOR PW / THE HUB — `Sys001SwTalk001`'s write semantics don't fit the existing radio-scan mechanism

`MW/D24/MX/_matrix.csv`'s own note on `Sys001SwTalk001` (landed S129
addendum 7): "WRITE is the two-indicator mask: bit0 = TB_LED0, bit1 =
TB_LED1, so 0 = both dark, 3 = both lit. READ is the switch: 1 while it is
held, 0 when it is released, and both edges are reported."

H1S3's existing generic mechanism (`RdRadioSwitch()`/`WrRadioLed()`, used by
every other button on both panels) does neither of these things:
- `WrRadioLed()` lights an LED on **equality** (`matrix[matrixAdd][RXD] ==
  radioData`) — a one-hot radio selection among mutually exclusive values.
  Two LEDs sharing one cell can be lit ONE AT A TIME this way (write 1 →
  LED0, write 2 → LED1), never both together — `3 = both lit` needs a
  **bitwise** test (`RXD & 1`, `RXD & 2`), which is different code, not a
  table entry.
- `RdRadioSwitch()` only acts on press (`!HAL_GPIO_ReadPin(...) &&
  matrix[TXD] != radioData`) and never clears `TXD` back to 0 on release —
  fine for a sticky radio-group selector, wrong for "both edges reported."

So step 5 as the mx26 doc first described it ("Bind Sys001SwTalk001 (TB_SW /
TB_LED0 / TB_LED1)") is **not** a same-shape repeat of step 4 — it needs new
firmware logic in `MainLoop()`/`Eol()`, not a `rsw[]`/`wled[]` entry. This
session did not write that logic: inventing bit-level LED-drive and
switch-edge-detection code for physical hardware, untested, the night before
a flash window, is exactly the kind of call that should be PW's, not
assumed.

**Options for the hub to choose between:**
1. Write the bespoke mask/edge logic for `Sys001SwTalk001` before tomorrow's
   window (needs someone who can verify against the real TS482/talkback
   hardware — not something to dry-run blind).
2. Ship tomorrow with `Sys001SwTalk001` declared but unbound (§ Step 5's
   mechanical-only build, already proven to compile clean) — catalog row 92
   stays NOT TESTED exactly as today, nothing regresses, and the talkback
   binding becomes a follow-up session.
3. Re-read the cell note as non-binding and treat `Sys001SwTalk001` as an
   ordinary one-hot radio pair after all (write 1 = LED0 only, write 2 =
   LED1 only, no simultaneous-both state, sticky read not edge-reported) —
   if the app side doesn't actually need the mask/edge behavior the defs
   note describes, this is a same-shape repeat of step 4 and can ship
   tomorrow. This needs someone who knows what the app/host side actually
   drives and expects to read back.

Recorded here per the no-question-dialogs rule (PW 2026-09-19): this is the
question and its options, for the hub to answer by re-dispatch or steer.
