#!/usr/bin/env bash
# Deterministic regenerate flow for mx26 -> mx-dsp contract intake.
#
# Steps:
# 1) Sync and verify (or update lock if requested)
# 2) Regenerate D32 DSP artifacts from MW/D32/MX/_matrix.csv
# 3) Print concise artifact summary

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
UPDATE_LOCK=0

if [[ "${1:-}" == "--update-lock" ]]; then
  UPDATE_LOCK=1
fi

cd "$ROOT_DIR"

if [[ $UPDATE_LOCK -eq 1 ]]; then
  ./sync-from-mx26.sh --update-lock
else
  ./sync-from-mx26.sh
fi

python3 validate-matrix-contract.py

# --enable-grp-geq-alias: transitional bridge backing the 48 GrpPeq matrix
# cells with the Group GEQ nodes (bands 1-12 at identical addresses).
# Remove the flag once mx26 renames GrpPeq -> GrpGeq.
python3 MW/D32/DSP/gen_dsp.py --force --enable-grp-geq-alias

d24_rows=$(tail -n +2 MW/D24/MX/_matrix.csv | wc -l | awk '{print $1}')
d32_rows=$(tail -n +2 MW/D32/MX/_matrix.csv | wc -l | awk '{print $1}')
map_rows=$(grep -c '^| ' MW/D32/DSP/dsp_address_map.md || true)

printf '\nRegenerate summary\n'
printf '  D24 matrix rows: %s\n' "$d24_rows"
printf '  D32 matrix rows: %s\n' "$d32_rows"
printf '  Address map rows: %s\n' "$map_rows"
printf '  Generated: %s\n' "MW/D32/DSP/ghost_cells.h"
printf '  Generated: %s\n' "MW/D32/DSP/SHARC/src/chip1/dsp_params.asm"
printf '  Generated: %s\n' "MW/D32/DSP/SHARC/src/chip2/dsp_params.asm"
