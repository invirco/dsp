# contract baseline

Status: active baseline
Date: 2026-07-18
Source repo: invirco/mx26
Source commit: 2f92f8b9ef3465e716ea90bddaa67d91e0da77e8
Contract version: defs-v2026.07.18

## Input hashes (from defs.lock)

D24_DEF_SHA256: 397c696b89d2b14d0c971e086e3fbe3d789392ed45733ff8e8cf82bad1bcec7a
D24_FW_SHA256: 8d3f6bfaabde0f99f8ef5be50fcbf35f1d2ced70bcc58ccde2778d419c87f42a
D24_MASTER_SHA256: 1aa3a3401b9c32186c86ec5ea039df94922f57043faaaf14c18e3d9d49900a35
D24_MATRIX_SHA256: d8b1e72d9e372cfb8b5bd1e8fd939c326db1cdecbc3e35c9067bd7e219163cda
D24_DSP_CFG_SHA256: ABSENT

D32_DEF_SHA256: 1149527f1e9972d143b67a1c895eff6ebf37a21aca20b71b6b7af7207dd5c5d3
D32_FW_SHA256: 15364f130dd39245b73bc6836ebc3a0acf1f3fd1fa9911e28306079501b09294
D32_MASTER_SHA256: ed472290a3691907e4e4f5a099ff5f4c90a29979445b7ec95e945e4f87809170
D32_MATRIX_SHA256: e656caeb50e27b994830ef5b5011f0b79af816d680e4e65d545a173139996f84
D32_DSP_CFG_SHA256: ABSENT

## Regenerate metrics (regenerate-dsp-contract.sh)

- D24 matrix rows: 4702
- D32 matrix rows: 6856
- dsp.csv nodes: 612
- Expanded cell mappings: 5405
- Dispatch entries: 6585
- Matrix cells matched/backfilled: 5405
- Address map rows: 5407
- D32 matrix families allowlisted: 304 (current generated families: 301)

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

- Current regenerate run reports informational gaps:
  - 951 _matrix.csv cells without DSP mapping (expected MCU-only or unmapped controls)
- 2026-07-18: synced mx26 commit 2f92f8b9 with new matrix families and expanded D24/D32 matrices.
- 2026-07-18: previous 349-cell DSP gap families were added in matrix contract; backfilled mapping now reaches 5405/5405 generated DSP cells.
- 2026-07-18: alias retirement guard now prunes FxEqHi, AuxPeq, SubMtr, AaChanDynMtr, and FxLfoMode from generated matrices.
- Compatibility and sanity gating now runs before DSP generation via validate-matrix-contract.py.
- Retired alias families (in alias-retire-families.txt): FxDuckThr, MainMtr, MainPeqGain, FxEqHi, AuxPeq, SubMtr, AaChanDynMtr, FxLfoMode.
