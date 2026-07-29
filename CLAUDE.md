# CLAUDE.md

DSP implementation repo (spoke) for Invirco matrix products. Matrix definitions
come from the **mx26** repo (hub) via a hash-pinned CSV contract. `README.md`
has the layout; `tasks.md` has current work state — read both first.

## Hard rules

- **defs.lock is authoritative.** Never hand-edit synced contract files
  (`MW/*/DEFS/*.csv`, `MW/*/FW/fw.csv`, `MW/*/MX/*.csv`). They come from mx26 via
  `./sync-from-mx26.sh`; local edits are drift and will fail `check-contract-drift.sh`.
- **Generated files are regenerated, not edited:** `MW/D32/DSP/ghost_cells.h`,
  `MW/D32/DSP/dsp_address_map.md`, `SHARC/src/*/dsp_params.asm`, node ASM
  skeletons under `SHARC/src/chip*/nodes/`, and `_matrix.csv` DSP-backfill
  columns. Change the generators (`MW/D32/DSP/gen_dsp.py`,
  `MW/*/DSP/SHARC/tools/*.py`) or the source `dsp.csv` instead.
- **Unknown matrix cell families must fail loudly** (no-fallback policy).
  New families are adopted intentionally via `matrix-families-allowlist.txt`.
- Never commit `MW/D32/DSP/SHARC/cces/` (toolchain) or license material.
- After any contract or generator change, run `./regenerate-dsp-contract.sh`
  and record contract version per `release-notes-contract-convention.md`.
- Update `tasks.md` on every contract bump.

## Where things happen

- Contract intake/validation: root scripts (`sync-from-mx26.sh`,
  `validate-matrix-contract.py`, `check-contract-drift.sh`,
  `regenerate-dsp-contract.sh`).
- D32 codegen: `MW/D32/DSP/gen_dsp.py` (matrix backfill, ghost cells, SPI
  dispatch) and `MW/D32/DSP/SHARC/tools/` (`gen_dsp_csv.py` → `dsp.csv` →
  `dsp_codegen.py` → node ASM; `dsp_validate.py`, `dsp_simulate.py`).
- SHARC build: `MW/D32/DSP/SHARC/build.sh` (needs CCES at
  `/opt/analog/cces/3.0.3`; dual-chip build with `-DCHIP_ID=1|2`, IVT
  re-assembled with `-nwc`).
- `attic/` is retired material (D24 ADAU1466/SigmaStudio era) — never build
  from it or extend it.

## Conventions

- Node IDs: `C<chip>_<TYPE>_<NN>` (e.g. `C1_EQ_07`, `C2_AUX_LIM_12`); one ASM
  file per node instance.
- Product trees are uniform: `MW/<PRODUCT>/{DEFS,FW,MX,DSPCFG,DSP}`. New
  products replicate this shape and join the same contract flow.
- D24's SHARC tree lags D32; D32 tooling is the superset/reference.
