#!/usr/bin/env bash
# Pre-merge contract drift check for the defs -> dsp workflow.
#
# Default mode verifies the defs pin and re-runs the whole generation.
# Strict mode additionally requires zero git-status changes in the files
# that generation produces, INCLUDING the submodule gitlink: a moved
# `defs/` is a contract change and has to be committed as one.
#
# Both modes first run ./check-sharc-codegen-drift.sh, which checks the
# GENERATED SHARC sources by content against a scratch generation rather than
# by git status -- a hand-edit that is committed is still drift.
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

# THE GENERATED SHARC SOURCES ARE PART OF THE CONTRACT, AND WERE NOT CHECKED
# (S43, from S42-5). This script used to regenerate the matrices and the D32
# address artifacts and call that the whole generation; the 726 files
# tools/dsp/dsp_codegen.py emits were in no gate at all, and drifted from
# their own generator in 117 files for three days without a word. It runs
# FIRST and on its own defs-independent inputs (dsp.csv + the generator), so a
# failure further down -- the d24 graph/dsp.csv disagreement below, for
# instance -- cannot mask it the way it would if this were appended.
./check-sharc-codegen-drift.sh

./sync-defs.sh
python3 validate-matrix-contract.py
python3 MW/D32/DSP/gen_dsp.py --force >/dev/null

# TABLE'S OWN AGREEMENT WITH MxDatS (S53). Table comes from the master row
# only now (the generator's hand-typed second copy is retired); this checks
# the master's own claim against itself -- Table's top breakpoint code
# should be MxDatS-1. Reports every violator; does not fail the build or
# touch the master (this repo is a consumer of it).
python3 check-table-mxdats.py

# THE PUBLISHED MATRIX MUST CARRY THE ADDRESSES ITS LANDED MAP DEFINES
# (S45-3). Everything above this line checks the matrix against the
# EXPANSION -- the lock hash, MxAdd continuity, the family allowlist -- and
# the expansion has no DSP address columns in it. So for as long as
# gen_dsp.py backfilled D32's matrix and only D32's, MW/D24/MX/_matrix.csv
# could carry a DSP address on 0 of its 4,985 rows while the landed map
# mapped 3,737 of them, and every gate in this script passed. The matrix is
# the ONE artefact the console app loads, so that was a D24 unable to write
# a single DSP node state, invisible to the whole intake path. It runs
# AFTER the regeneration, on what generation actually produced, not on what
# it was asked to produce.
python3 check-matrix-addresses.py

echo "Contract validation and regeneration completed"

if [[ $STRICT -eq 1 ]]; then
  mapfile -t CONTRACT_FILES <<'LIST'
defs
defs.lock
MW/D12/MX/_matrix.csv
MW/D16/MX/_matrix.csv
MW/D24/MX/_matrix.csv
MW/D32/MX/_matrix.csv
MW/D32/DSP/ghost_cells.h
MW/D32/DSP/SHARC/src/chip1/dsp_params.asm
MW/D32/DSP/SHARC/src/chip2/dsp_params.asm
MW/D32/DSP/dsp_address_map.md
MW/D32/FW/H1S1/Core/Inc/ghost_cells.h
MW/D32/FW/H1S1/Core/Src/ghost_cells.c
MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h
LIST

  drift="$(git status --porcelain -- "${CONTRACT_FILES[@]}")"
  if [[ -n "$drift" ]]; then
    echo "ERROR: Contract drift detected in strict mode:" >&2
    echo "$drift" >&2
    echo "Resolve drift or commit intended updates before merge." >&2
    exit 1
  fi
  echo "Strict drift check passed (no contract file changes)"
fi
