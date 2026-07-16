# contract baseline

Status: active baseline
Date: 2026-07-15
Source repo: invirco/mx26
Source commit: 96c54d0632a43bfcd53a3ae3012393949bfbdc3c
Contract version: defs-v2026.07.15

## Input hashes (from defs.lock)

D24_DEF_SHA256: a10719680b23711c4658b2f87812427bd5e559504eeedf040158600f53a9bb38
D24_FW_SHA256: 8d3f6bfaabde0f99f8ef5be50fcbf35f1d2ced70bcc58ccde2778d419c87f42a
D24_MASTER_SHA256: 1aa3a3401b9c32186c86ec5ea039df94922f57043faaaf14c18e3d9d49900a35
D24_MATRIX_SHA256: 37f8418bd993a0a395ca5d13e14b9355b10e4cb049f936d27f7ea0be8f313b61
D24_DSP_CFG_SHA256: ABSENT

D32_DEF_SHA256: c5ecac627d47bb5c924c97a1a558e70f68f68a67993785aa0ed29d9d35d0a8f9
D32_FW_SHA256: 9c29c419ea184f0002ee36962fb4eac8447b9fb67c966110f019ace6667e44e4
D32_MASTER_SHA256: 7bedab929d4b2d81727e5bc2929c044337021d35455da046fb3eea590c7b76fb
D32_MATRIX_SHA256: aa879cb51102130d6c6af3fa3da6bf5fc59c3589663ece22fd55e362f6c0b8e1
D32_DSP_CFG_SHA256: ABSENT

## Regenerate metrics (regenerate-dsp-contract.sh)

- D24 matrix rows: 4835
- D32 matrix rows: 6694
- dsp.csv nodes: 612
- Expanded cell mappings: 5405
- Dispatch entries: 6585
- Matrix cells matched/backfilled: 5056
- Address map rows: 5423
- D32 matrix families allowlisted: 272 (current generated families: 269)

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
  - 349 DSP cells not in _matrix.csv
  - 1140 _matrix.csv cells without DSP mapping
- 2026-07-16: expand_geq renamed Peq→Geq; +220 cells matched (AuxGeq×336 + MainGeq×28 now mapped, AuxPeq alias bands 1-12 still in matrix pending retirement)- 2026-07-16: FxEqHi→EqPresence and Sub→AaSub meter renames; stale-clear pass; 151 alias rows cleared (FxEqHi×6, AuxPeq×144, SubMtr×1)
- 2026-07-16: DynMtr→CompMtr in expand_meter (32 CompMtr now canonical); FxLfoMode/LfoShape, AaChanDynMtr/CompMtr added to alias audit; 32 stale DynMtr entries cleared- Treat these as tracked compatibility/mapping work, not immediate build failures.
- Compatibility and sanity gating now runs before DSP generation via validate-matrix-contract.py.
- Retired alias families (in alias-retire-families.txt): FxDuckThr, MainMtr, MainPeqGain.
