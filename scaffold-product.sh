#!/usr/bin/env bash
# scaffold-product.sh — create the standard MW/<PRODUCT> tree for a new
# matrix-based product and print the integration checklist.
#
# Usage: ./scaffold-product.sh D48

set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Z][A-Z0-9]+$ ]]; then
  echo "Usage: $0 <PRODUCT>   (e.g. D48 — uppercase alphanumeric)" >&2
  exit 1
fi

P="$1"
LOWER="$(echo "$P" | tr '[:upper:]' '[:lower:]')"
ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE="$ROOT/MW/$P"

if [[ -d "$BASE" ]]; then
  echo "ERROR: $BASE already exists." >&2
  exit 1
fi

mkdir -p "$BASE"/{DEFS,FW,MX,DSPCFG,DSP/SHARC/src}

cat > "$BASE/README.md" <<EOF
# $P

Standard product tree — populated by the mx26 contract flow.

- DEFS/$LOWER.csv          — feature definition        (synced from mx26)
- FW/fw.csv           — hardware config           (synced from mx26)
- MX/$LOWER-mx-master.csv  — expanded product master   (synced from mx26)
- MX/_matrix.csv      — runtime matrix snapshot   (synced + DSP backfill)
- DSPCFG/             — tier-2 dsp.csv when mx26 provides it
- DSP/SHARC/          — DSP graph (dsp.csv) + generated source (src/)

Codegen lives in the shared package: tools/dsp/ (see repo README).
EOF

echo "Created $BASE:"
find "$BASE" | sed "s|$ROOT/||"

cat <<EOF

Next steps to integrate $P:
  1. mx26: publish src/pd/$LOWER.csv, src/pd/$LOWER/fw.csv, $LOWER-mx-master.csv.
  2. Add $P source/dest paths + hash keys to sync-from-mx26.sh
     (mirror the existing D24/D32 blocks) and to check-contract-drift.sh.
  3. Add expected families to matrix-families-allowlist.txt (intentionally).
  4. ./regenerate-dsp-contract.sh --update-lock   # pins $P in defs.lock
  5. Author the DSP graph: MW/$P/DSP/SHARC/dsp.csv
     (generate from matrix via: python3 tools/dsp/gen_dsp_csv.py, adapted)
  6. Generate source: python3 tools/dsp/dsp_codegen.py \\
       MW/$P/DSP/SHARC/dsp.csv MW/$P/DSP/SHARC/src
  7. Validate: python3 tools/dsp/dsp_validate.py MW/$P/DSP/SHARC/dsp.csv
  8. Copy a build.sh from MW/D32/DSP/SHARC/ and adjust the -proc target.
  9. Record baselines in contract-baseline.md; update tasks.md.
EOF
