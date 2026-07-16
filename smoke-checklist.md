# smoke checklist

Status: active
Date: 2026-07-15
Scope: D24 and D32 contract bump verification after regeneration.

## Run commands

1. ./regenerate-dsp-contract.sh
2. ./check-contract-drift.sh

## Checklist

- [ ] Contract sync completed with lock verification
- [ ] D24 MxAdd contiguous check passed
- [ ] D32 MxAdd contiguous check passed
- [ ] D32 family allowlist compatibility passed
- [ ] DSP regeneration completed without fatal errors
- [ ] Generated files present:
  - MW/D32/DSP/ghost_cells.h
  - MW/D32/DSP/SHARC/src/chip1/dsp_params.asm
  - MW/D32/DSP/SHARC/src/chip2/dsp_params.asm
  - MW/D32/DSP/dsp_address_map.md
  - MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h
- [ ] Regenerate summary captured in release notes or PR
- [ ] Informational mapping gaps reviewed:
  - DSP cells not in matrix
  - matrix cells without DSP mapping
- [ ] Contract note fields added per release-notes-contract-convention.md

## Pass criteria

All checks above are complete with no hash mismatch, no unexpected family additions, and no unreconciled drift for intended merge scope.
