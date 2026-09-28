provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S131 runbook — the D24 matrix switch-over (desk only; do NOT execute from this document)

Written for S134 (overnight, no hands). Nothing below was run on the unit
except the dry run in §6, which built into scratch directories under
`/home/app/s134fw/` and was deleted afterwards — the unit was never flashed,
no rail or GPIO state was touched, and `app cli loadfw` was never invoked.
PW runs the real thing tomorrow (2026-09-28) with the hub.

**S135 (2026-09-28, desk, nothing flashed) added:** step 5b, the optional
talkback image, with both `.shex` variants prebuilt; a correction to step 7,
where the `.shex` MCU id S134 prescribed would have cross-flashed the two
panels; a note on step 8's single-session form. §7's open question is now
answered and closed. Detail: `MW/D24/DSP/s135/s135-report.md`.

🟢 **S140 (2026-09-28, desk, nothing flashed) closes S139's owed step —
`gen_dsp.py` now runs clean and the D24 backfill is installed.** Pin is now
**`defs-v2026.09.28.2`** (defs commit `b106eb5`) — the DSP-side landed map
only; D24 generation is still **`46109e9fb812`**, unchanged, and every
per-cell address this document names below at that generation is still
correct. `defs/products/d24/{dsp.csv,dsp-unmapped.csv}` are now pruned of
the 357/5 rows S139 found drifted (see `MW/D24/DSP/s140/s140-report.md`),
so `gen_dsp.py` (no `--propose`) passes its no-fallback check-proposal gate
clean for d32+d24, and `MW/D24/MX/_matrix.csv` on disk now carries the
**`46109e9fb812`** backfill for real: 5,767 rows, **3,632/3,632 mapped
cells carry a DSP address**. `./regenerate-dsp-contract.sh` passes every
gate end to end (was blocked at the address-check gate since S139). §6's
dry-run numbers below (matrix.h/`.shex` diffs) are unaffected — they never
depended on the DSP-side landed map — and stand as verified. Nothing
flashed, unit untouched.

Background: `mx26 docs/investigation-matrix-generation-2026-09-27.md` (read in
full before starting). Summary: MW-D24-2 is running matrix generation
`e80ccab5d6d8` (the unit's own 2026-08-18 pack, 5412 names, `Sys001Skin001` =
5412) — a generation built before S0 from a pre-purge master, not from any
defs tag.

🔴 **S139, HUB ADDENDUM 3: the target moved AGAIN, past `b630825d8fed` /
`defs-v2026.09.28`, and this move is NOT append-only.**
It is now **`46109e9fb812`** at **`defs-v2026.09.28.1`** (defs commit
`877ea5f`), **5,767 names** — PW's block-audit rulings (D1-D17, 2026-09-28)
in one tag: +1,123 new cells over `b630825d8fed` (all landed unmapped, no
new DSP mappings), −362 D24 cells dropped (group/matrix-mixer/quad-main
surface the audit ruled out for D24; 357 of them WERE DSP-mapped — full
list `MW/D24/DSP/s139/gen/dropped-was-mapped.csv`; the DSP nodes themselves
are untouched, they simply have no D24 cell reaching them any more).
`defs.lock` **IS** advanced this session (`sync-defs.sh --update-lock`),
unlike S137's addendum — `D24_MATRIX_GEN=46109e9fb812`,
`CONTRACT_VERSION=defs-v2026.09.28.1`. `defs/products/d24/fw.csv` is
byte-identical to `.27.3` (`D24_FW_SHA256` unchanged), so the panel LED/
switch tables S137 reconciled (`panel_coverage.py --check`, 20/20) are
still correct at this pin.

**THE ADDRESS MOVE IS NOT APPEND-ONLY, UNLIKE EVERY PRIOR MOVE THIS RUNBOOK
DESCRIBES.** PW ruled a ONE-TIME re-lay: 4,555 of the prior 5,031 D24 names
changed address. Every per-cell number this runbook asserts anywhere below
is now **STALE**:
- `Sys001Skin001`: 4698 → **4360**
- `Sys001Enc001`: 4514 → **4176**
- `Sys001SwLeft001`: 5005 → **4643**
- `Sys001SwTalk001`: 5006 → **4644**
- `Main004EqGain001` (the old aliasing collision the mx26 doc named): 5005 →
  no longer at that address either — re-derive with `d24_panel.py --mode
  resolve` at execution time, never trust a number written in this document.

Verified this session (not read-only-checkout arithmetic like S137's
addendum — the pin was actually advanced and `sync-defs.sh` actually
expanded the matrix): `MW/D24/MX/_matrix.expansion.csv` is 5,767 rows,
`matrix_gen_id.py` reports base-id `46109e9fb812` against it directly. A
fresh `matrix.h` built from it and diffed against the currently-flashed one
(fetched live from `/home/app/fwbuild/H1S3/Core/Inc/matrix.h`, gen
`e80ccab5d6d8`): **3,307 names only on the unit, 3,662 only in the new
target, 2,105 shared, 0 shared at the same address** — every shared name
still moves (S134's own conclusion, §6, holds; only the counts moved).
`gen_dsp.py`'s dry run needed 91 new unmapped-family reasons plus one
corrected one (`Chan/DynMtr`'s text changed again upstream) before it would
even run — added this session, see the S139 report. **`gen_dsp.py` (no
`--propose`) still fails**, but on the 362-dropped-cell drift, not a missing
reason: `defs/products/d24/{dsp.csv,dsp-unmapped.csv}` haven't been pruned
of the dropped rows yet, so `MW/D24/MX/_matrix.csv`'s DSP-address backfill
has **not** been re-run (`--force` is blocked by the same fatal check) —
this repo's `MW/D24/MX/_matrix.csv` on disk is still the PREVIOUS backfill.
Fresh proposals are landed at `proposals/defs/products/*/` for the hub to
submit upstream; full detail and the check-proposal transcript are in
`MW/D24/DSP/s139/s139-report.md`.

§6 (S134's dry run) and §6a (S136's fix) both re-verified this session
against `46109e9fb812` (matrix.h regen + all three `.shex` rebuilds, same
recipe, nothing flashed) — see §4 of the S139 report for the full build
log; their own numbers below are kept as the S134/S137 historical record
and are not rewritten in place.

🔴 **S137, HUB ADDENDUM 2 (superseded by the above — kept as a record of what
was true 2026-09-28 before the audit landed): the target moved again, past `defs-v2026.09.27.5`.**
It is now **`b630825d8fed`** at `defs-v2026.09.28` (5031 names,
`Sys001Skin001` still = 4698 — append-only, existing addresses do not move).
`defs-v2026.09.28` appends `Sys001SelectedFx001` (1 cell) and
`Chan{N}DynMtr001` (24 cells, one per channel) over `.27.3`/`.27.5`, which is
why this is a real matrix move and not the no-op `.3`→`.5` comparison the
paragraph below originally described. Verified this session by checking
`defs` out to the tag read-only (`git -C defs checkout defs-v2026.09.28`),
expanding `d24-mx-master.csv` and running `matrix_gen_id.py`, then restoring
the submodule to the pinned commit — **`defs.lock` itself is untouched, still
pinned at `defs-v2026.09.27.3` / `D24_MATRIX_GEN=f9677e5fae5e`, and moving it
is its own dispatch** (`sync-defs.sh --update-lock` +
`regenerate-dsp-contract.sh`, all four products, the families allowlist
regenerated), not done in this NO-FLASH session. `MW/D32/DSP/gen_dsp.py`
needed a `('Chan', 'DynMtr')` host-managed no-fallback reason before that
contract move can even run clean (added this session; see the S137 report)
— **but adding it is not enough on its own**: `gen_dsp.py --dry-run` against
a `defs-v2026.09.28` checkout still errors ("d32/dsp-unmapped.csv cell set
disagrees with the graph ... 33 the landed file has and the graph does not
propose", 25 for d24) because the local `dsp.csv` graph does not know about
the new cells at all yet — that side needs the full `sync-defs.sh` pipeline
to actually regenerate `dsp.csv`/`dsp-unmapped.csv` together, not a
one-line patch. The `('Chan', 'DynMtr')` reason is necessary groundwork, not
sufficient by itself.

**This is not an incremental patch.** The unit's live pack against the
*previous* target (`f9677e5fae5e`, 5006 names) was:

| | count |
|---|---|
| names only on the unit (pre-purge `Aa*`, `Main[2-4]`, `Rtg*`, …) | 3309 |
| names only in the target generation (incl. the 2 new cells) | 2903 |
| names in both | 2103 |
| **names in both at the same address** | **0** |

Against the now-current target (`b630825d8fed`, 5031 names) the shared/
unit-only rows are unchanged in kind — the 25 new cells are new names, not
matched by anything in the unit's pre-purge pack — so **names in both stays
2103 and names only in the target rises to 2928 (2903 + 25) = 5031 total**.
This is arithmetic from the verified counts above, not a re-run of the dry
diff against the unit's live pack; re-run §6's dry run against
`b630825d8fed` before relying on it at the bench.

Every one of those 2103 shared names moves. Confirmed by dry run (§6, against
the `f9677e5fae5e` target — re-run against `b630825d8fed` before S131): the
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
mx26 investigation doc — this was hashed against the `f9677e5fae5e` pack;
**§0, HUB ADDENDUM 3 (S139) moved the target to `46109e9fb812`
(`defs-v2026.09.28.1`), so this hash is stale and must be retaken from the
current published file, not compared against the number above**). Delete
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
<matrix.h>` for each — must report `ALIGNED (full-id 46109e9fb812, base-id
46109e9fb812)` (§0, HUB ADDENDUM 3 — re-verified this session, §4 of
`MW/D24/DSP/s139/s139-report.md`; still re-run against whatever is actually
published before trusting the `ALIGNED` line at execution time, since the
target has moved more than once).
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

### Step 5 — H1S3 (right panel): declare `Sys001SwTalk001`, unbound (see §7, answered)
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
one-hot semantics don't fit it, and S134 did not attempt to write that logic
— see §7, since answered: S135 wrote it and built it as the optional step 5b
image.** The mechanical-only build (identifier declared, nothing bound to it
yet) is what this step flashes, and it is a safe interim: it changes nothing observable
(catalog row 92 stays NOT TESTED, exactly as today), so this step ships as "declared but not
yet wired" without blocking the rest of the window, and step 5b is a separate,
reversible decision at the panel.
**Rollback:** re-flash `H1S3.shex.bak-s131-pregen` via `app cli loadfw H1S3`.
**Time:** build ~10 s once the logic (if any) is decided. Flash time as
step 4.

**RESOLVED by the hub (S135):** ship the unbound build here — option 2 — and
treat the bound one as the optional step 5b below. Both images are already
built; §7's open question is answered and closed.

### Step 5b — OPTIONAL: the talkback image (S135, decide at the bench)

Only if PW wants talkback live in this window. Skipping it changes nothing:
step 5's unbound image is the default and catalog row 92 stays NOT TESTED
exactly as today.

Two prebuilt images, both in this repo at `MW/D24/DSP/s135/gen/`, both already
stamped with the right MCU id (see step 7):

| variant | file | md5 | what it is |
|---|---|---|---|
| **A** | `gen/H1S3-A/H1S3.shex` | `f21480b56744f4b2a4ca775d0ebd92fb` | step 5's unbound build — the default |
| **B** | `gen/H1S3-B/H1S3.shex` | `f0bacb7bfb91f036e50b8f5987daf255` | A + the talkback logic |

B differs from A in one source file and, at the map level, in exactly two
functions plus two new ones: of 150 functions in both images 148 are
instruction-identical, and `RdRadioSwitch()`/`WrRadioLed()` are among them, so
no other button's behaviour moves. Detail and evidence: `MW/D24/DSP/s135/s135-report.md`.

**To take it:** copy `gen/H1S3-B/H1S3.shex` to `/home/app/firmware/H1S3.shex`
in place of the step-7 output, then flash exactly as step 8 does. Nothing else
in the window changes.

**PW's bench check, after step 9:**

1. **The switch, both edges.** Press and hold talkback: the host reads
   `Sys001SwTalk001` (5006) = **1**. Release it: the host reads **0**. Both
   have to arrive — the whole point of this logic over the radio scan is that
   the release is reported at all. On a bus log the press is `ikpv1` and the
   release is `ikpv` with no data character; that is how every cell sends a
   zero on this protocol and the host reads it as 0.
   Hold it down for a second or two: no repeat, no chatter (20 ms debounce).
2. **The indicators, as a mask.** Write `Sys001SwTalk001` = **1** → TB_LED0
   only. = **2** → TB_LED1 only. = **3** → **both lit together** (this is the
   one an `rsw[]`/`wled[]` binding could never do). = **0** → both dark.
3. **Nothing else moved.** Walk the rest of the right panel once — every
   button still lights its own indicator, and the encoder ring still steps.

**If any of it is wrong — roll back, do not debug in the window.** Copy
`gen/H1S3-A/H1S3.shex` over `/home/app/firmware/H1S3.shex` and re-flash H1S3;
that is the unbound image the window was always going to ship, so the rest of
the switch-over stands and only talkback goes back to NOT TESTED. If the panel
is worse than that, fall back to `H1S3.shex.bak-s131-pregen` and §1's
whole-set restore.

**Time:** no build (both images are prebuilt); one extra H1S3 flash, plus a
couple of minutes for the three checks.

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

> ⚠️ **`/home/app/fwbuild/H1S1` WAS STALE (found in S131, fixed in S141).**
> The dry-run rebuild above (and S139's re-run of it) built from
> `/home/app/fwbuild/H1S1`, whose `matrix.cs`/`main.c` dated 2025-12-30 —
> before S69's `CodecPoll()` existed. That is why "byte-for-byte unchanged"
> above is describing the WRONG baseline: S139's resulting `.shex`
> (`8067f1d4…`, archived at `s139/gen/H1S1/`) was flashed during S131 and
> regressed ML1/CC/MC and the DSP boot. The real source is `~/build-h1s1`
> (the hub machine); rebuilding from there reproduced the pre-S131 image
> byte-for-byte (`272868c8…`) and, with the current `matrix.h` swapped in,
> gave the correct `19a5492d…` — this is what S131 actually flashed and
> verified. Evidence and both images: `MW/D24/DSP/s131/H1S1/`; the S139
> report's H1S1 bullet carries the same correction. S141 synced
> `/home/app/fwbuild/H1S1`'s `matrix.h`/`matrix.cs`/`main.c` from
> `~/build-h1s1` so an on-unit rebuild from this step no longer reproduces
> the stale image (old copies: `*.bak-s141-stale-20260928-124440`
> alongside each file). **Any future H1S1 rebuild should still diff its
> output against `MW/D24/DSP/s131/H1S1/H1S1.shex` before flashing.**

### Step 7 — Build each `.shex`
From each `Debug/H1SxN.hex` (built by `make -f makefile all` from the
project's own `Debug/`, after the one-line Windows-path fix in the makefile
— see `MW/D24/DSP/s129/data/panel-build-repro.md` §3, reproduced again
tonight):
```
python3 /home/app/fwbuild/hex2shex.py H1S1.hex H1S1 H1S1.new.shex
python3 /home/app/fwbuild/hex2shex.py H1S3.hex H1S4 H1S3.new.shex
python3 /home/app/fwbuild/hex2shex.py H1S4.hex H1S3 H1S4.new.shex
```

> ⚠️ **THE ID ARGUMENT IS CROSSED FOR H1S3/H1S4, AND IT IS NOT A TYPO.**
> S134 wrote this step with `H1S3 -> H1S3` and `H1S4 -> H1S4`; S135 found that
> would cross-flash the two panels. `hex2shex.py`'s second argument becomes the
> header record, and MH1 uses it to pick the **slave socket**:
> `myHS = GetCharHexByte(myRXstring[4], myRXstring[6])` then
> `S_Boot[(myHS & 0xf) - 1]()`, so `H1S4` → `SB4` and `H1S3` → `SB3`. The images
> running on the unit today are `H1S3.shex` carrying id `H1S4` and `H1S4.shex`
> carrying id `H1S3`: the source-tree names do not match the hardware sockets,
> and the working images compensate here. Rebuilding both from the unit's own
> source reproduces each deployed file **byte-for-byte except line 1**, which
> is how this was established; the 2026-08-19 flash log shows the same crossing
> live. Evidence: `MW/D24/DSP/s135/data/shex-mcu-id-evidence.txt`.
>
> **Check it before step 8:** `head -1` each new `.shex` against `head -1` of
> the matching `.bak-s131-pregen` file. The two header lines must be identical.
> S134's archived dry-run `H1S3.shex` and `H1S4.shex` under
> `MW/D24/DSP/s134/gen/` carry the wrong ids (its `H1S1.shex` is fine) — they
> were never flashed; do not lift them straight into `/home/app/firmware/`.
> Socket-correct images with the identical payloads are in
> `MW/D24/DSP/s135/gen/`:
>
> | image | id | md5 |
> |---|---|---|
> | `gen/H1S3-A/H1S3.shex` (step 5, unbound) | `H1S4` | `f21480b56744f4b2a4ca775d0ebd92fb` |
> | `gen/H1S3-B/H1S3.shex` (step 5b, talkback) | `H1S4` | `f0bacb7bfb91f036e50b8f5987daf255` |
> | `gen/H1S4/H1S4.shex` (step 4 bind) | `H1S3` | `8540b6ad39530d6696763ef14c656a40` |
>
> For H1S1, S134's `gen/H1S1/H1S1.shex` is already correct.
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
`MW/D24/HW/hardware-map.md` §"the second master is GONE").

**S135 correction: `loadfw` DOES take more than one name**, and that is how
the currently-flashed panel pair was written. `app cli loadfw H1S1,H1S3,H1S4`
(or `all`) runs `FirmwareLoader.FlashAll()`, which concatenates the images into
one S_FLASH session, strips the EOF record from all but the last, and lets MH1
switch sockets on each extended-address record — exactly the 2287-record
sequence in the 2026-08-19 flash log. Either form works; the combined one is
one reset cycle instead of three and is the proven path. Whichever is used,
`matrix-app` stays stopped for the whole window.
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
**§6a is closed (S136): the bench tools resolve every address by name, so no
edit is owed here.** Run `d24_panel.py --mode resolve` first and confirm its
header alone before anything else below.

🔴 **HUB ADDENDUM 2 (S137, SUPERSEDED — kept as a record of what was true
2026-09-28 before the block audit landed; see HUB ADDENDUM 3 in §0 and below
for the current numbers).**

~~Verified independently this session by checking `defs` out to
`defs-v2026.09.28` read-only... the D24 base-id is `b630825d8fed`... 5031
names... `Sys001Skin001` is unchanged at 4698 (append-only: existing
addresses do not move)...~~ **This turned out to be true only up to
`defs-v2026.09.28` — the very next tag, `.28.1` (S139), is NOT append-only:
PW's block audit re-laid 4,555 of the 5,031 addresses.** See §0's HUB
ADDENDUM 3 for the full account.

🔴 **HUB ADDENDUM 3 (S139): current target `46109e9fb812` /
`defs-v2026.09.28.1`, 5,767 names, verified live (pin actually advanced, not
a read-only checkout).**

- `d24_panel.py --mode resolve` header must show generation `46109e9fb812`,
  and `Sys001Skin001` = **4360** / `Sys001Enc001` = **4176** /
  `Sys001SwLeft001` = **4643** / `Sys001SwTalk001` = **4644**, none of them
  NOT TESTED any more.
- Boot log: `Matrix generation base-id 46109e9fb812 (5767 names / 5767
  addresses, max 5767)` (grep the app's own log, same line format the mx26
  doc quotes for the current `e80ccab5d6d8` boot).
- `Sys001Skin001` = 4360 on the right panel; a left-panel press arrives on
  4643 and **never** on 4360 (the aliasing this whole change exists to
  remove); a talkback press (once step 5's logic lands) arrives on 4644.
- **The old `Main004EqGain001` = 5005 aliasing story (mx26 doc, S135/S137) no
  longer applies as written**: `Main004EqGain001` is a unit-only pre-purge
  name that isn't in ANY defs generation, and at `46109e9fb812` address 5005
  belongs to a DIFFERENT new cell, `MainCtr001Geq020` (one of the audit's new
  GEQ bands, itself unmapped — `no-graph-node`, ruling D6). So: an EQ gain
  change still lights no panel indicator (nothing on this address reads a
  panel LED either way), but it is no longer meaningful to describe it as
  "the same collision, moved" — re-derive whichever address matters with
  `d24_panel.py --mode resolve` rather than trusting a fixed number here.
- `grep "MCU verified" /home/app/logs/log` for all three boards (the same
  check `d24_selftest.py`'s `handback()` already does — see
  `MW/D24/DSP/s129/data/panel-build-repro.md`).
- Record the md5 of every flashed `.shex` (and the app binary, and the pack)
  on the gate line, per the mx26 doc's own closing instruction.
- **The post-switch panel check is the panel loop itself (S137), not a
  one-off press per board.** Run both boards through
  `d24_runall.py --manual-only` (or the factory screen's own START, which
  reaches the same `panel_station()`) and confirm, per PW's panel-loop
  ruling: the walk order is the fixed defs/fw.csv order on both boards
  (unchanged pass to pass — `--random-panel-order` stays off); every switch
  is reached in turn (`panel_coverage.py --check` reports "every control is
  either graded or named with its reason", 20 of 20 switches); the armed
  screen's NOT LIT button is present and working (a deliberate dark-panel
  press records the LED **FAIL — "operator saw no light"** and the switch
  **NOT TESTED — "skipped: LED dark"**, and the walk advances at once with no
  retry); a correct press records both rows PASS; a wrong-board or
  wrong-button press FAILs the switch and names the board. See
  `MW/D24/DSP/s137/` for the scripted desk proof of all of this with no
  finger at the bench.
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
| 5 H1S3 bind | ~10s build (mechanical part) + unmeasured flash |
| 5b talkback (optional) | no build — one extra H1S3 flash + ~2 min of checks |
| 6 H1S1 rebuild | ~15s build + unmeasured flash |
| 7 Build .shex | <1 min, all three |
| 8 Flash | unmeasured — time the first board live |
| 9 Reboot | ~10s |
| 10 Verify | ~5 min + one ~150s automatic pass |
| **Total** | dominated by the app publish and the three unmeasured flashes; everything DSP-side that could be dry-run tonight is seconds, not minutes |

## 4. Steps needing PW at the bench
Probably none strictly, but a look at the panels after step 9 (to visually
confirm the left board no longer lights on EQ gain changes) is cheap insurance
and matches "a look at the panels" from the dispatch. **Step 5b is the one part
that genuinely needs PW at the panel** — pressing the talkback key and watching
its two indicators is the only way to confirm the binding, which is why it is
optional and separable from the rest of the window.

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

🔴 **STALE (S137, HUB ADDENDUM 2): this section's numbers are S134's real
dry-run evidence against the `f9677e5fae5e` target and are kept as a record
of what was actually run — but the target has since moved to `b630825d8fed`
(§0). This dry run was NOT re-run against the new target in this (NO-FLASH,
D24-panel-loop) session; re-running it — new `matrix.h`, new `.shex`, diffed
against the currently-flashed images, exactly as below — is still owed
before S131 executes.**

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
  `ef89709fc81c21544d8c88d2d78e2838`). **S135: that payload is exactly right —
  it reproduced byte-for-byte on a second machine — but the file's MCU id is
  `H1S3`, which is the wrong socket (step 7). Use
  `MW/D24/DSP/s135/gen/H1S3-A/H1S3.shex` (md5
  `f21480b56744f4b2a4ca775d0ebd92fb`), same payload, id `H1S4`.**
- H1S1: `matrix.h` swapped only, no source change. Built clean: `text`
  34080, `data` 657, `bss` 1940 — **identical** to the pre-change build (as
  expected: no new symbol, only `#define` values changed). `.shex`: 2174
  records / 34737 bytes (md5 `cd4cc76179b7952839abc9210de5f4b7`).
- All three source trees, the generated `matrix.h`, and the three `.shex`
  outputs are archived under `MW/D24/DSP/s134/gen/` in this repo.
- Nothing was flashed. No `app cli loadfw` call was made. No GPIO/rail state
  was touched by any part of this exercise.

---

## 6a. ✅ FIXED (hub ruling, built by S136) — the address step is now automatic; there is nothing left to do here before step 10

S135 found `tools/pi/d24_panel.py` (and `codec4619.py`) hard-coding the
radio-group addresses as literals (`SKIN = 0x1524`, `ENC = 0x1470`,
`SYS001TEST001 = 0x1526`, …), true of MW-D24-2's 2026-08-18 pack alone. The
hub's ruling was the second option this section used to pose: **the tools
now read every address by NAME from the unit's own deployed pack, every
time, so this cannot recur.**

`tools/pi/matrix_addr.py` resolves a cell name off `{HomePath}/config/
_matrix.mxc` (else `_matrix.csv`), the same artefact and the same order
`Core/AppContext.ResolveMatrixPath` uses — so a station tool and the app
it is testing alongside always agree on what a name means. `d24_panel.py`,
`d24_bus_probe.py` and `codec4619.py` no longer carry a single literal
address; `tools/pi/check-no-hardcoded-matrix-addr.py` is a generator-side
guard against a new one creeping back in, and `deploy-bench-tools.sh` runs
it before every deploy and refuses to deploy on a hit.

**A name absent from the deployed pack is never a guess or a crash**: on
tonight's 08-18 pack, `d24_panel.py --mode resolve` reports
`Sys001SwLeft001`/`Sys001SwTalk001` as NOT TESTED ("cell not in this unit's
matrix (generation e80ccab5d6d8)"), and `--panel left` reports every one of
its rows the same way rather than falling back to the old shared-cell
aliasing guess. Proved on MW-D24-2 itself, S136 report
`MW/D24/DSP/s136/s136-report.md`.

**So after step 8, no address edit is owed here** — the same unedited
tools resolve `Sys001Skin001`/`Sys001Enc001`/`Sys001SwLeft001`/
`Sys001SwTalk001` off whatever pack is deployed. What step 10 should check
instead: `d24_panel.py --mode resolve`'s header reports **generation
`46109e9fb812`** (§0, HUB ADDENDUM 3 — S139; not `b630825d8fed`,
`f9677e5fae5e`, nor `e80ccab5d6d8`), and its `resolved` block then reads
`Sys001Skin001: 4360`, `Sys001Enc001: 4176`, `Sys001SwLeft001: 4643`,
`Sys001SwTalk001: 4644` — no longer NOT TESTED, because the switch-over
landed the names this session could only report absent. (This tool needs no
code change either way — S136's whole point was that it resolves by name
off whatever pack is deployed; only the expected NUMBERS in this checklist
moved.)

## 7. ✅ ANSWERED (hub, 2026-09-27; built by S135) — `Sys001SwTalk001`'s write semantics don't fit the existing radio-scan mechanism

**Ruling: option 2 ships, option 1 is prepared as step 5b.** The window flashes
the unbound image, so nothing regresses if the talkback binding is not taken.
S135 then wrote the bespoke mask/edge logic and built it as a separate H1S3
image (variant B), for PW to verify at the bench and adopt or drop on the spot
— see step 5b and `MW/D24/DSP/s135/s135-report.md`. Option 3 was not taken: the
cell note is binding, and the mask half (`3` = both lit) is not expressible as
a one-hot radio pair at all.

The analysis below stands as written and is why the logic is bespoke.

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

**Options the hub chose between (2 taken for the window, 1 prepared as step 5b):**
1. Write the bespoke mask/edge logic for `Sys001SwTalk001` before tomorrow's
   window (needs someone who can verify against the real TS482/talkback
   hardware — not something to dry-run blind). **— built by S135 as variant B,
   offered as the optional step 5b.**
2. Ship tomorrow with `Sys001SwTalk001` declared but unbound (§ Step 5's
   mechanical-only build, already proven to compile clean) — catalog row 92
   stays NOT TESTED exactly as today, nothing regresses, and the talkback
   binding becomes a follow-up session. **— CHOSEN; this is what step 5
   flashes.**
3. Re-read the cell note as non-binding and treat `Sys001SwTalk001` as an
   ordinary one-hot radio pair after all (write 1 = LED0 only, write 2 =
   LED1 only, no simultaneous-both state, sticky read not edge-reported) —
   if the app side doesn't actually need the mask/edge behavior the defs
   note describes, this is a same-shape repeat of step 4 and can ship
   tomorrow. This needs someone who knows what the app/host side actually
   drives and expects to read back.

Recorded here per the no-question-dialogs rule (PW 2026-09-19): this is the
question and its options, for the hub to answer by re-dispatch or steer.
Answered by the hub in the S135 dispatch; kept for the record.
