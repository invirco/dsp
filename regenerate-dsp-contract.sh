#!/usr/bin/env bash
# Deterministic regenerate flow for the defs -> dsp contract intake.
#
# Steps:
# 0) Regenerate the SHARC sources from MW/D32/DSP/SHARC/dsp.csv
# 1) Verify the defs submodule against defs.lock and re-expand the matrices
# 2) Validate the expansion (MxAdd continuity, family allowlist)
# 3) Regenerate the D32 DSP artifacts from MW/D32/MX/_matrix.csv
# 4) Print concise artifact summary
#
# STEP 0 IS NEW IN S43 AND IS WHY THE TREE COULD DRIFT. This script claimed to
# be the deterministic regenerate flow and never ran tools/dsp/dsp_codegen.py,
# so "run the regenerate script" left 726 generated files untouched -- and on
# 2026-09-13 117 of them did not match their own generator. It runs FIRST,
# on inputs that do not depend on the defs expansion, so a failure downstream
# does not leave the SHARC half unregenerated.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
UPDATE_LOCK=0

if [[ "${1:-}" == "--update-lock" ]]; then
  UPDATE_LOCK=1
fi

cd "$ROOT_DIR"

python3 tools/dsp/dsp_codegen.py \
  MW/D32/DSP/SHARC/dsp.csv MW/D32/DSP/SHARC/src --force >/dev/null

if [[ $UPDATE_LOCK -eq 1 ]]; then
  ./sync-defs.sh --update-lock
else
  ./sync-defs.sh
fi

python3 validate-matrix-contract.py

python3 MW/D32/DSP/gen_dsp.py --force

d12_rows=$(tail -n +2 MW/D12/MX/_matrix.csv | wc -l | awk '{print $1}')
d16_rows=$(tail -n +2 MW/D16/MX/_matrix.csv | wc -l | awk '{print $1}')
d24_rows=$(tail -n +2 MW/D24/MX/_matrix.csv | wc -l | awk '{print $1}')
d32_rows=$(tail -n +2 MW/D32/MX/_matrix.csv | wc -l | awk '{print $1}')
map_rows=$(grep -c '^| ' MW/D32/DSP/dsp_address_map.md || true)

printf '\nRegenerate summary\n'
printf '  Contract: %s\n' "$(awk -F= '$1=="CONTRACT_VERSION"{print $2}' defs.lock)"
printf '  defs commit: %s\n' "$(awk -F= '$1=="DEFS_COMMIT"{print $2}' defs.lock)"
printf '  D12 matrix rows: %s (generation %s)\n' "$d12_rows" \
  "$(awk -F= '$1=="D12_MATRIX_GEN"{print $2}' defs.lock)"
printf '  D16 matrix rows: %s (generation %s)\n' "$d16_rows" \
  "$(awk -F= '$1=="D16_MATRIX_GEN"{print $2}' defs.lock)"
printf '  D24 matrix rows: %s (generation %s)\n' "$d24_rows" \
  "$(awk -F= '$1=="D24_MATRIX_GEN"{print $2}' defs.lock)"
printf '  D32 matrix rows: %s (generation %s)\n' "$d32_rows" \
  "$(awk -F= '$1=="D32_MATRIX_GEN"{print $2}' defs.lock)"
printf '  Address map rows: %s\n' "$map_rows"
printf '  Generated: %s\n' "MW/D32/DSP/ghost_cells.h"
printf '  Generated: %s\n' "MW/D32/DSP/SHARC/src/chip1/dsp_params.asm"
printf '  Generated: %s\n' "MW/D32/DSP/SHARC/src/chip2/dsp_params.asm"
printf '  Generated: %s SHARC sources from %s\n' \
  "$(find MW/D32/DSP/SHARC/src -name '*.asm' -o -name 'dsp_block.h' | wc -l | awk '{print $1}')" \
  "MW/D32/DSP/SHARC/dsp.csv"
