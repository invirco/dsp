provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S139 report — D24 onto the block-audit generation `46109e9fb812`

NO FLASH. `MW-D24-2` was read and dry-run-built against only (SSH scratch
dirs under `/home/app/s139fw/`, deleted after use), never written to:
`app` stayed `b05e9fd55e15289e6529f66c72778e33`, `matrix-app` inactive,
GPIO26 (AN_EN) low, GPIO27 (CS_M) high, before and after — checked at both
ends of the session.

## 0. Contract advance

`defs.lock` moved: `DEFS_COMMIT` `2eb02ee` → `877ea5f`, `CONTRACT_VERSION`
`defs-v2026.09.27.3` → `defs-v2026.09.28.1` (`./sync-defs.sh --update-lock`).
`D24_MATRIX_GEN` `f9677e5fae5e` → `46109e9fb812`, matching the dispatch's
number exactly. `D24_FW_SHA256` is **unchanged**
(`82bdec7bb2ff5c22c599649555337f4937388e4d7e189fc306fdc0826a257ef9`) —
`defs/products/d24/fw.csv` did not move in this tag, so the panel LED/switch
tables S137 reconciled against (`panel_coverage.py --check`, 20/20 switches;
the catalog fix in `s137-report.md` §4) are still the ones live at this pin;
nothing to redo there.

`MW/D24/MX/_matrix.expansion.csv` (staged; not yet installed — see §2)
expands to **5,767 cells**, generation `46109e9fb812`, matching the dispatch.
Address move confirmed as ruled: `Sys001Skin001` 4698 → **4360**,
`Sys001Def001` 2557 → **4175**, plus (found this session, relevant to S131):
`Sys001Enc001` 4514 → **4176**, `Sys001SwLeft001` 5005 → **4643**,
`Sys001SwTalk001` 5006 → **4644**. This is a full re-lay, not a patch: of the
2,105 names shared with the currently-flashed 08-18 pack, **zero** keep their
address (§4).

## 1. `gen_dsp.py`: new unmapped families from the block audit

`gen_dsp.py --dry-run` (and `--check-proposal`) died immediately on
`Mtk001Rec001` — `_UNMAPPED_REASONS` had no entry and no-fallback exits
loudly, per the hard rule. Full accounting (built by re-running the graph's
own `_unmapped_reason()` against every row landed in
`defs/products/{d24,d32}/dsp-unmapped.csv`, not by hand-inspection):

- **91 new `(family, suffix)` entries added**, text copied verbatim from the
  landed reason so `check_proposal()` reproduces it exactly (ruling D2
  Mtk-recorder host-managed, D3/D4 aux/main send+limiter families, D5-D13
  the rest of the new fields, D15 the FX sample-play family — see the new
  block in `gen_dsp.py` just above `_GEQ_BAND_CELL`).
- **1 entry updated**: `('Chan', 'DynMtr')`'s reason text changed upstream
  between `defs-v2026.09.28` and `.28.1` (same ruling, reworded) — the old
  hand-written prose no longer matches the landed file byte for byte.
- **15 cell-specific overrides added** (`_BLOCK_AUDIT_CELL_REASONS`, checked
  ahead of the family dict): `Noise001Dest011` and the fourteen
  `Talk00[12]Dest0(04-10)` cells. Both families (`Noise/Dest`, `Talk/Dest`)
  already carry a bespoke hand-written reason for their ORIGINAL instances
  (the S24/S25 fan-out and routing findings) — these specific new instances
  get the audit's own generic text instead, so the family default keeps
  meaning what it always meant for cells 1-3/1-10 and these new ones don't
  silently inherit prose that isn't about them.
- Everything else the audit added (Dca/DcaOn family, `Name` labels, the
  wholly `mcu-only`-prefixed Sys/Rec/Fdr/Mute cells) already falls through
  the existing `host_managed` set / `('*','Name')` wildcard /
  `mcu-only-prefixes.txt` fallback with no change needed — confirmed by
  running the real function, not by assuming the family list was exhaustive.
- Two pre-existing cells (`Rec001CueSel001`, `Rec001Mtr00[12]`) were
  matching the blanket `Rec` mcu-only prefix incorrectly before their own
  family entries existed (same class of bug the new families would have hit
  blind); adding their explicit entries fixes this too, verified by the same
  re-run (0 errors, 0 mismatches against every landed row in both products).

## 2. Regeneration result

`gen_dsp.py --check-proposal` (and the ordinary no-`--propose` path) still
**fails**, but for a different, structural reason, not a missing reason:

```
ERROR: d24/dsp.csv cell set disagrees with the graph — 0 the graph proposes
and the landed file lacks, 357 the landed file has and the graph does not
propose.
ERROR: d24/dsp-unmapped.csv cell set disagrees with the graph — 0 the graph
proposes and the landed file lacks, 5 the landed file has and the graph
does not propose.
```

This is the **362 dropped cells** the dispatch names, all `Chan*MatrixOn*` /
`Chan*MatrixSend*` (48+48 = the `ROUTING` nodes `C1_RTG_01..24`),
`GrpGate*` (4 boards × 12 params), `GrpGeq*` (4 × 31 bands), and the
`MainCtr`/`MainL`/`MainR`/`MainSub` compressor+crossover+EQ+meter+mute
blocks, plus 5 previously-unmapped strays
(`MainCtr001Delay001`, `MainSub001Delay001`, `Matrix00[12]Name001`,
`Rta001Src001`). **357 of the 362 dropped cells WERE DSP-mapped** — full
list with node/type/address in `s139/gen/dropped-was-mapped.csv` (357
rows). **The DSP nodes themselves are untouched — this is a graph accounting
list, not a code deletion**: `C1_RTG_01..24` (ROUTING), `C2_GRP_GATE_01..04`
(GATE), `C2_GRP_GEQ_01..04` (GEQ), `C2_MAIN_OCOMP_01..04` (COMPRESSOR),
`C2_MAIN_OEQ_04` (EQ_BIQUAD), `C2_MAIN_OUT_03/04` (OUTPUT_TDM),
`C2_MAIN_XOVER` (CROSSOVER), `C2_MTR_MAIN_03/04` (METER), `C2_MTX_FDR_01/02`
(FADER_PAN) all still build; they simply have no D24 cell reaching them any
more, by the audit's own ruling (D24 dropped the group/matrix/quad-main
surface, not this repo).

Since `defs/products/d24/{dsp.csv,dsp-unmapped.csv}` were **not** touched by
`defs-v2026.09.28.1` (confirmed: `git -C defs diff .27.3 .28.1 --stat` shows
zero change to either file — only `dsp-unmapped.csv` gained the 1,123 new
audit rows via a *different*, already-checked-in change), the landed
contract has not yet been pruned of the 362 dropped names. **This is upstream
work, not something this repo edits** (defs is a consumer boundary; nothing
here rewrites a landed defs file). What this session DID, per the dispatch:
ran `gen_dsp.py --propose` for real (not dry-run) and landed fresh proposals
at `proposals/defs/products/{d12,d16,d24,d32}/{dsp.csv,dsp-unmapped.csv}` —
these correctly DROP the 362 stale D24 rows and add the 1,123 new ones,
ready for the hub to submit upstream to `defs` and re-tag. D24 proposal
counts: **3,632 mapped / 2,135 unmapped = 5,767** (was 3,989 / 1,017 = 5,006).
D32/D16/D12 proposals regenerated too (unaffected by the D24 drop; their
diffs are purely additive from the same audit's Mtk/DynMtr/etc. rows).

**No new cell maps onto an existing node.** All 1,123 additions landed as
`dsp-unmapped.csv` rows (confirmed: `products/d24/dsp.csv` has zero diff
between tags) — the dispatch's "unless an existing DSP node already
implements them" case did not occur this generation.

Coverage summary (D24, from the proposal run):
| | before (.27.3, gen `f9677e5fae5e`) | after (.28.1, gen `46109e9fb812`) |
|---|---|---|
| defined | 5,006 | 5,767 |
| mapped | 3,989 | 3,632 |
| unmapped | 1,017 | 2,135 |

## 2a. `validate-matrix-contract.py`: the family allowlist

Running the full `./regenerate-dsp-contract.sh` (not just `gen_dsp.py` in
isolation) surfaced a second, separate no-fallback gate: 91 new matrix cell
families (the same ones §1 gave DSP-mapping reasons for) are not in
`matrix-families-allowlist.txt`, so `validate-matrix-contract.py` refused
all four products. `--update-allowlist` (rebuild from D32's own matrix, the
documented mechanism) picked up every new family D32 also carries by
construction, leaving 26 D24-only families PW's D6/D9 rulings added to D24's
stereo main bus and centre cluster (anti-feedback, GEQ, and a third main
output) that D32 has no equivalent shape for — added by hand to
`NON_D32_FAMILIES["D24"]` in `validate-matrix-contract.py`, the same named
adoption-record pattern the existing `MainCtr*`/`MainOut3Mode` entries use
(not a wildcard). `python3 validate-matrix-contract.py` now passes clean for
all four products at this generation.

**Contract note** (`release-notes-contract-convention.md`):
- version: `defs-v2026.09.28.1`
- source repo/ref: `invirco/defs`, tag `defs-v2026.09.28.1`
- source commit: `877ea5fd806fc70de665e008da220bcf24e13077`
- products affected: D12, D16, D24, D32 (D24 structurally: +1,123/−362 cells;
  D12/D16/D32 additively only)
- change class: schema (91 new cell families) + counts (D24 net +761 cells)
- risk: medium — D24's DSP-address backfill cannot complete yet (§2)
- validation run: `./regenerate-dsp-contract.sh` — passes through
  `dsp_codegen`, `sync-defs.sh`, `validate-matrix-contract.py`
  (post-allowlist-update); stops at `gen_dsp.py`'s no-fallback drift check
  on the 362 dropped D24 cells (§2), which is upstream work, not a defect in
  this run.

## 3. Hard-coded matrix-address grep (S136's guard)

`python3 tools/pi/check-no-hardcoded-matrix-addr.py` → clean
("no hard-coded matrix addresses in any tools/pi file that imports
codec4619"). Nothing regressed; S136's name-resolution work
(`matrix_addr.py`, `d24_panel.py --mode resolve`, etc.) needs no change for
this generation move — it was built precisely to not need one.

## 4. Runbook re-verification: matrix.h / `.shex` dry run against `46109e9fb812`

Same recipe as S134/S135, against the new generation, in fresh scratch
copies (`/home/app/s139fw/{H1S1,H1S3,H1S4}/`, `rsync -a` from
`/home/app/fwbuild/`, deleted after):

- **`matrix.h` regenerated** from this repo's `MW/D24/MX/_matrix.expansion.csv`
  (5,767 `#define`s, sorted by address) — `defs/tools/matrix_gen_id.py
  --compare` against the CSV: `ALIGNED (full-id 46109e9fb812, base-id
  46109e9fb812)`.
  Diffed against the currently-flashed `matrix.h` (fetched fresh from
  `/home/app/fwbuild/H1S3/Core/Inc/matrix.h`, generation `e80ccab5d6d8`):
  **3,307 names only on the unit, 3,662 only in the new generation, 2,105
  shared, 0 shared at the same address** — every one of the 2,105 shared
  names still moves, same conclusion as S134's dry run, now against the
  right target.
- **H1S4**: `matrix.cs` reused byte-for-byte from `s134/gen/H1S4/matrix.cs`
  (the `Sys001SwLeft001` bind — symbolic names only, no address literals, so
  nothing needed changing for the new generation). Built clean: `text`
  13868→13872 (+4), `bss` 1916→1924 (+8) — identical deltas to S134.
  `.shex`: 924 records / 14748 bytes (md5 `f54848b0d63751fb8cf3fbb17dc17ebe`),
  header id `H1S3` (crossed, per S135 — matches the currently-flashed
  `H1S4.shex`'s own header line exactly).
- **H1S3**: `matrix.cs` reused from `s135/gen/H1S3-A/matrix.cs` (the
  unbound declare-only variant the hub chose to ship). Built clean: `text`
  20572→20576 (+4), `data`/`bss` unchanged. `.shex`: 1364 records / 21788
  bytes (md5 `8eeafb4f770cc56169b2115c4b96108e`), header id `H1S4` (crossed,
  matches the currently-flashed `H1S3.shex`).
- **H1S1**: `matrix.h` swap only, no source change. Built clean: `text`
  34080, `data` 657, `bss` 1940 — **identical** to the currently-flashed
  build (as expected). `.shex`: 2174 records / 34737 bytes (md5
  `8067f1d402cde5aec10fc74c00f5e9d9`), header id `H1S1` (matches).

  🔴 **WRONG SOURCE (found in S131, fixed in S141).** This rebuild's source
  tree was `/home/app/fwbuild/H1S1`, and that copy was stale: `matrix.cs`
  dated 2025-12-30, predating S69's `CodecPoll()`. Flashing
  `s139/gen/H1S1/H1S1.shex` (this `8067f1d4…`) during S131 regressed ML1/CC/MC
  and the DSP boot. S131 rebuilt from the real source, `~/build-h1s1`
  (scratch `~/s131/H1S1`), which reproduced the pre-S131 image byte-for-byte
  (`272868c8…`) and, with `s139/gen/matrix.h` swapped in, gave the correct
  `19a5492d…` — archived at `MW/D24/DSP/s131/H1S1/`. S141 synced
  `/home/app/fwbuild/H1S1`'s `matrix.h`/`matrix.cs`/`main.c` from
  `~/build-h1s1` so the next on-unit build from that path can't repeat this;
  old copies kept as `*.bak-s141-stale-20260928-124440`.
- Record counts (2174/1364/924) and byte sizes are **unchanged from S134's
  original dry run** — only the `#define` values moved, not the payload
  shape, so nothing about the flash mechanics changes with the new
  generation.
- Talkback variant B (S135) was **not** re-built this session — it's a
  source-only diff from A (`matrix.cs` + `Eol.c`), so the same `matrix.h`
  swap applies to it unchanged; re-build it alongside A at execution time if
  PW still wants it live (§5b of the runbook, unaffected by this dispatch).
- All three source trees, `matrix.h`, and the six `.hex`/`.shex` outputs are
  archived under `MW/D24/DSP/s139/gen/`.
- Nothing was flashed. No `app cli loadfw` call was made. No GPIO/rail state
  was touched. Verified unchanged after: `app` md5 unchanged, `matrix-app`
  inactive, GPIO26 low, GPIO27 high.

## 5. Runbook

`MW/D24/DSP/s131-runbook.md` updated: a new HUB ADDENDUM 3 block records the
move to `46109e9fb812` / `defs-v2026.09.28.1`, flags every per-cell address
this doc previously asserted (`Sys001Skin001`=4698, `Sys001Enc001`=4514,
`Sys001SwLeft001`=5005, `Sys001SwTalk001`=5006, and `Main004EqGain001`=5005)
as **STALE** — this move reassigns essentially every existing address, not
an append — and gives the new values (4360/4176/4643/4644). §6 (S134's dry
run) and §6a (S136's fix) both get a pointer to this session's re-run
(§4 above / `s139-report.md`) rather than a second rewrite of their own
numbers, matching how §6 already carries S137's STALE flag as a kept
record. §10's checklist items that name a generation or count now say
`46109e9fb812` / 5,767 where they said `b630825d8fed` / 5,031 or
`f9677e5fae5e` / 5,006.

## 6. What's still owed (not in this NO-FLASH session's scope)

- **Land the `proposals/` update upstream**: `defs/products/d24/{dsp.csv,
  dsp-unmapped.csv}` need the 362 dropped rows removed and the 1,123 new
  rows added at the hub gate, then this repo's defs pin can move past
  `defs-v2026.09.28.1` to a tag where `gen_dsp.py` (no `--propose`) passes
  clean and `--force` can actually backfill `MW/D24/MX/_matrix.csv`. Until
  then `MW/D24/MX/_matrix.csv` **stays at the previous backfill** —
  `_matrix.expansion.csv` is staged but not installed (`sync-defs.sh`'s own
  message: "STAGED at MW/D24/MX/_matrix.expansion.csv; gen_dsp.py backfills
  and installs it") because the fatal drift check blocks the install step.
  This is expected, no-fallback behaviour, not a bug in this session's work.
- S131 itself (the real switch-over) still targets whatever generation is
  live when the hub actually runs it — re-check the pin at execution time,
  same caution S137's addendum already gave.
