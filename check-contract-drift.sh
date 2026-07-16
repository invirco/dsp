#!/usr/bin/env bash
# Pre-merge contract drift check for mx26 -> mx-dsp workflow.
#
# Default mode validates contract sync and regeneration determinism.
# Strict mode additionally requires zero git-status changes in contract files.
#
# Usage:
#   ./check-contract-drift.sh
#   ./check-contract-drift.sh --strict

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
STRICT=0

if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

cd "$ROOT_DIR"

./sync-from-mx26.sh
python3 validate-matrix-contract.py
python3 MW/D32/DSP/gen_dsp.py --force >/dev/null

echo "Contract validation and regeneration completed"

if [[ $STRICT -eq 1 ]]; then
  mapfile -t CONTRACT_FILES <<'EOF'
defs.lock
MW/D24/DEFS/d24.csv
MW/D24/FW/fw.csv
MW/D24/MX/d24-mx-master.csv
MW/D24/MX/_matrix.csv
MW/D32/DEFS/d32.csv
MW/D32/FW/fw.csv
MW/D32/MX/d32-mx-master.csv
MW/D32/MX/_matrix.csv
MW/D32/DSP/ghost_cells.h
MW/D32/DSP/SHARC/src/chip1/dsp_params.asm
MW/D32/DSP/SHARC/src/chip2/dsp_params.asm
MW/D32/DSP/dsp_address_map.md
MW/D32/FW/H1S1/Core/Inc/ghost_cells.h
MW/D32/FW/H1S1/Core/Src/ghost_cells.c
MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h
EOF

  drift="$(git status --porcelain -- "${CONTRACT_FILES[@]}")"
  if [[ -n "$drift" ]]; then
    echo "ERROR: Contract drift detected in strict mode:" >&2
    echo "$drift" >&2
    echo "Resolve drift or commit intended updates before merge." >&2
    exit 1
  fi
  echo "Strict drift check passed (no contract file changes)"
fi
