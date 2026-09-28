provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S140 report — close S139's owed step: pin `defs-v2026.09.28.2`, `gen_dsp.py` clean, D24 backfill installed

NO FLASH. Desk-only. Unit not touched this session.

## 1. What moved

S139's `proposals/defs/products/*/{dsp.csv,dsp-unmapped.csv}` landed upstream
as `defs-v2026.09.28.2` (defs commit `b106eb5406bd054dd67db669def92297dba24319`,
tag `defs-v2026.09.28.2`). Diff from `.28.1` (`877ea5fd806fc70de665e008da220bcf24e13077`),
confirmed against the landed tag before use:

- `products/d24/dsp.csv`: −357 lines (exactly the 357 dropped-but-DSP-mapped
  cells from `MW/D24/DSP/s139/gen/dropped-was-mapped.csv` — verified these
  are the same set, not re-derived here)
- `products/d24/dsp-unmapped.csv`: −5 lines — `MainCtr001Delay001`,
  `MainSub001Delay001`, `Matrix001Name001`, `Matrix002Name001`,
  `Rta001Src001` (all now DSP-mapped or otherwise resolved upstream; exact
  removed rows confirmed by diff, matches the dispatch header)
- `products/d12/dsp-unmapped.csv`, `products/d16/dsp-unmapped.csv`: +2 lines
  each — `Usb001HostSync001` / `Usb001HostSyncWhy001` (`hardware-control`,
  RT1180/net firmware owns them, no DSP path)
- `products/d32/dsp.csv`: +4/−4 lines (no product-def or master hash
  changed — `D32_DEF_SHA256` etc. in `defs.lock` are identical before/after)
- No `def`, `fw.csv`, mx-master, wire-table, or `mx-cell-master` hash
  changed. D24 matrix expansion generation is unchanged:
  **`46109e9fb812`** (5,767 cells) both before and after this move — only
  the DSP-side landed map moved, not the matrix.

## 2. Build

1. **`defs.lock` advanced** to `defs-v2026.09.28.2` via
   `./sync-defs.sh --update-lock` after checking the submodule out to the
   tag and staging the gitlink bump. `DEFS_COMMIT=b106eb5406bd054dd67db669def92297dba24319`,
   `CONTRACT_VERSION=defs-v2026.09.28.2`. All per-product def/master/fw/wire
   hashes unchanged from `.28.1` (expected — only dsp.csv/dsp-unmapped.csv
   moved). `D24_MATRIX_GEN` unchanged at `46109e9fb812`.

2. **`gen_dsp.py` (no `--propose`) now runs clean** — the no-fallback
   check-proposal gate: `check-proposal OK — the graph reproduces the
   landed dsp.csv / dsp-unmapped.csv exactly for d32, d24`. Confirmed with
   `--dry-run` first, then run for real with `--force`.

3. **DSP-address backfill re-run and installed.** `MW/D24/MX/_matrix.csv`
   now carries generation `46109e9fb812` (5,767 rows) with DSP addresses:
   **3,632/3,632 mapped cells carry an address** (2,135 named unmapped —
   same figures S139 already found for the graph; this session's move only
   fixed the landed-file drift that was blocking the write, not the
   mapped/unmapped counts themselves). `_matrix.expansion.csv` was
   consumed/renamed into place by `gen_dsp.py` as designed (S44-1); nothing
   staged remains on disk. D32 alongside: 8,737 rows, 5,780/5,780 mapped
   cells carry an address.

4. **`./regenerate-dsp-contract.sh` run end to end — every gate passed:**
   - SHARC codegen (`tools/dsp/dsp_codegen.py`) — ran first, unaffected by
     this move
   - `sync-defs.sh` (lock + manifest verify, all four matrix expansions)
   - `validate-matrix-contract.py` — MxAdd contiguity (D24: 1..5767, 408
     families) and family allowlist (451 families, D32 set) — **passed**
   - `gen_dsp.py --force` — clean, as above
   - `gen_input_patch.py --all` — D24 `input_patch.json` regenerated (47
     entries, 24 rows), others identity
   - `check-matrix-addresses.py` — **passed**: D32 5780/5780, D24 3632/3632
   - Also ran `./check-contract-drift.sh` (default mode) afterward as an
     independent determinism check: identical result, 0 git-status diff
     from a second regeneration, SHARC codegen drift check "0 differ from
     committed tree". `check-table-mxdats.py`'s Table/MxDatS mismatch
     report (97 rows) is pre-existing, reports to the hub, not a gate
     failure — unchanged by this session's move.
   - `audit-compat-aliases.py` — ran, `alias-audit.md` updated (3-line
     diff, cosmetic — reflects the dropped/added cell names above)

## 3. Hashes (post-regen)

```
defs.lock:
  DEFS_COMMIT=b106eb5406bd054dd67db669def92297dba24319
  CONTRACT_VERSION=defs-v2026.09.28.2
  D24_MATRIX_GEN=46109e9fb812  (unchanged)
  D24_MATRIX_SHA256=750d4e2cd1a11d56a2208ba717ef6c16867e2c7c7dbf3934adf1dc18b0ea7f83  (unchanged — expansion, pre-backfill)

defs/products/d24/dsp.csv           sha256 8a084b0732905a22ca1865fba49c9ca2d2fb26ef01fb375bd7d9b8cdef66c250
defs/products/d24/dsp-unmapped.csv  sha256 e9ca8ac72fe31cba85edbd10f7d7a6ae66e09c5fc4f6ed6a54893a0ff75f6f20
defs/products/d12/dsp-unmapped.csv  sha256 a055861c95703162c1e78f56abafe4d263f77bd2de9af909f3ad0f1ffb7aa5e7
defs/products/d16/dsp-unmapped.csv  sha256 af9537835b77a3838cc37fee3e9a5682b3d88246dfb63fc9dabbe8156586fd46

MW/D24/MX/_matrix.csv (backfilled, installed)  sha256 0b194f99ce307eaeed97c1e4296fe0b5070c8f2b063f1f15d3328e10ceb3677b
MW/D32/MX/_matrix.csv (backfilled, installed)  sha256 7156eed49c3c49b55ec971c95bba3099452058e3fc2d32b0078eb323def70768
MW/D32/DSP/ghost_cells.h                       sha256 0e7e89801355095c2f03a21bbbc3ab2fe806ed0e8efb5d4de92586a950e87474
MW/D32/DSP/dsp_address_map.md                  sha256 5184792d85ef025d9753cf1253c8c4ad491be94a70f6223c210711eadb383b00
```

## 4. Counts summary

| | before (`.28.1`, S139) | after (`.28.2`, this session) |
|---|---|---|
| D24 dsp.csv rows | (357 more) | 3,668 lines / graph reproduces exactly |
| D24 dsp-unmapped.csv rows | (5 more) | 2,149 lines / graph reproduces exactly |
| D24 `_matrix.csv` DSP addresses | **not writable** (`gen_dsp.py` blocked by drift) | **3,632/3,632 mapped cells carry an address**, installed |
| `gen_dsp.py` (no `--propose`) | fails on 362-row drift | **clean** |
| `regenerate-dsp-contract.sh` | not runnable end to end | **all gates pass** |

## 5. Not touched

No flashing, no app deploy, no bus/GPIO/pin activity — this was a desk-only
defs/generator move. Unit state is whatever S139 left it (`app` md5
`b05e9fd5…`, `matrix-app` inactive, GPIO26 lo / GPIO27 hi) — not
re-verified here since nothing in this session could have changed it.

## 6. Outcome

🟢 Done. S139's owed step is closed: `defs.lock` at `defs-v2026.09.28.2`,
`gen_dsp.py` runs clean with no `--propose`, D24's DSP-address backfill for
generation `46109e9fb812` is installed in `MW/D24/MX/_matrix.csv`, and
`./regenerate-dsp-contract.sh` passes every gate end to end. `s131-runbook.md`
updated to name `.28.2` and mark the backfill done (§ addendum below the
existing S139 entry, prior entries left as the historical record per
established practice in that document).
