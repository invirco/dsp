# contract baseline

Status: active baseline
Date: 2026-09-08
Definitions repo: invirco/defs (the `defs/` submodule)
Pinned commit: b0e4b487fdca25d6e4558dc953d7400aef13d686
Contract version: defs-v2026.09.08

Earlier baselines (mx26 `src/pd` era, up to defs-v2026.08.20) are in git
history; this repo stopped importing definition CSVs on 2026-09-08.

## Matrix generation ids (defs/tools/matrix_gen_id.py)

- D24: 7322e9a88b18 — ALIGNED with the defs expansion
- D32: f09af9c2cd1e — ALIGNED with the defs expansion

The previous, locally-expanded-and-pruned generation was `b4592dfb639e`
for D24: neither the tag it pinned (`85102bd3097d`) nor the hub. That is
the drift S1 removed.

## Input hashes (from defs.lock)

DEFS_MANIFEST_SHA256: 7a6525da000c971bb52df6f1ef53a812aa82c89913fd6aca179b8d35c9880d17
MX_CELL_MASTER_SHA256: 3f8260491ea136981bbab14f69b1b50c1d81cab1c4d24dcd5256b77de39eebc5
WIRE_UNITS_SHA256: e4c244acf372001ea2ba00e966b755876c55ad92300f75fb55024dacdee147cc

D24_DEF_SHA256: 397588274f49b9a78e3938e126b17dc4089808e3aee525e556afd94320051722
D24_FW_SHA256: 8d3f6bfaabde0f99f8ef5be50fcbf35f1d2ced70bcc58ccde2778d419c87f42a
D24_MASTER_SHA256: 2fa1ed8f4112d209225295007b16dc1fd265dcba239f47fb9c2dd30d660f377f
D24_WIRE_TABLE_SHA256: 60666a1be75b82b7143dc87d4bce386db210ecff15469013dbd90126b69ca50f
D24_MATRIX_SHA256: 80a3b4073eae629e606d1b77bf2961dd0456bb85939429ac14f36c1bf7d09ec0

D32_DEF_SHA256: 0261974209e1d09e6953f1616fb6bafddd7b1bfa3d562932ee716fc4e5f5ab73
D32_FW_SHA256: 15364f130dd39245b73bc6836ebc3a0acf1f3fd1fa9911e28306079501b09294
D32_MASTER_SHA256: a528bc7d977ecdfd8294d78473fb9d4fc50c29c9d7804fa50ea1a31c64df17c3
D32_WIRE_TABLE_SHA256: 7ca78dc645bc4870cb9b54cc479b30479cc55906a15a54423eb7d7e1d58dc6d9
D32_MATRIX_SHA256: 61762dcb5d3941bd82226c6803aa2376450c40b2c42b43547679543107f4b8b6

`*_MATRIX_SHA256` is the expander's output BEFORE gen_dsp.py backfills the
DSP address columns, which is the only part of `_matrix.csv` this repo owns.

## Regenerate metrics (regenerate-dsp-contract.sh)

- D24 matrix rows: 4946 (was 5125 at defs-v2026.08.20)
- D32 matrix rows: 6948 (was 6940)
- dsp.csv nodes: 666
- Expanded cell mappings: 5416
- Dispatch entries: 6717
- Matrix cells matched/backfilled: 5393
- Address map rows: 5418
- D32 matrix families allowlisted: 361 (114 removed, 165 added at this bump)

## Generated outputs checked

- MW/D24/MX/_matrix.csv
- MW/D32/MX/_matrix.csv
- MW/D32/DSP/ghost_cells.h
- MW/D32/DSP/SHARC/src/chip1/dsp_params.asm
- MW/D32/DSP/SHARC/src/chip2/dsp_params.asm
- MW/D32/FW/H1S1/Core/Inc/ghost_cells.h
- MW/D32/FW/H1S1/Core/Src/ghost_cells.c
- MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h
- MW/D32/DSP/dsp_address_map.md

## Notes

- The regenerate run reports, and these are gaps in the PRODUCT GRAPH rather
  than in the contract flow:
  - 8 graph nodes hold SPI addresses but reach no master cell category:
    C2_MAIN_{OEQ,OCOMP,OLIM}_{03,04} and C2_MTR_MAIN_{03,04}. The masters
    name three main output strips (MainL, MainR, MainSub) and the graph
    builds four post-crossover chains — review finding D52, still open, and
    dsp.csv's to resolve.
  - 23 generated cells are not in `_matrix.csv`: the main BUS compressor and
    limiter (`Main001Comp*`, `Main001Limiter*`), which the masters moved onto
    the per-output strips, plus `MainL001Mtr002`/`MainR001Mtr002` (the L;R
    meter taps on what is now a mono output strip).
  - 1011 `_matrix.csv` cells have no DSP mapping (MCU-only or unmapped
    surface controls: Name, Color, CueSel, Link, PadOn, MuteGrp, the matrix
    bus sends, the FX aux sends).
- Alias pruning is GONE. `prune-compat-aliases.py` and
  `alias-retire-families.txt` were retired on 2026-09-08: deleting families
  from the expansion and renumbering MxAdd behind them was how this repo
  grew a matrix generation of its own. `audit-compat-aliases.py` now proves
  the opposite — that the expansion in this tree is untouched.
- Two formerly-pruned families are carried by the definitions again and are
  therefore definitions, not aliases: `FxDuckThr` (6 rows, alongside
  `FxDuckSens`) and `PeqGain` (12 rows each on `MainL` and `MainR`).
- Compatibility and sanity gating runs before DSP generation via
  validate-matrix-contract.py.
