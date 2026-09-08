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

mkdir -p "$BASE"/{MX,DSP/SHARC/src}

cat > "$BASE/README.md" <<EOF
# $P

Standard product tree — populated by the defs contract flow.

The definitions are NOT here. \`$LOWER.csv\`, \`fw.csv\` and
\`$LOWER-mx-master.csv\` live in the \`defs\` submodule
(\`defs/products/$LOWER/\`, \`defs/gen/matrix/\`); this tree carries only
what is generated from them.

- MX/_matrix.csv      — GENERATED: defs/tools/expand_matrix.py + DSP backfill
- DSP/SHARC/          — DSP graph (dsp.csv) + generated source (src/)

Codegen lives in the shared package: tools/dsp/ (see repo README).
EOF

echo "Created $BASE:"
find "$BASE" | sed "s|$ROOT/||"

cat <<EOF

Next steps to integrate $P:
  1. defs: publish products/$LOWER/$LOWER.csv, products/$LOWER/fw.csv and
     gen/matrix/$LOWER-mx-master.csv, and tag a new defs-vYYYY.MM.DD.
  2. Move the defs submodule to that tag; add $P to PRODUCTS in sync-defs.sh
     and to the CONTRACT_FILES list in check-contract-drift.sh.
  3. Add expected families to matrix-families-allowlist.txt (intentionally).
  4. ./regenerate-dsp-contract.sh --update-lock   # re-pins defs.lock
  5. Author the DSP graph: MW/$P/DSP/SHARC/dsp.csv
     (generate from matrix via: python3 tools/dsp/gen_dsp_csv.py, adapted)
  6. Generate source: python3 tools/dsp/dsp_codegen.py \\
       MW/$P/DSP/SHARC/dsp.csv MW/$P/DSP/SHARC/src
  7. Validate: python3 tools/dsp/dsp_validate.py MW/$P/DSP/SHARC/dsp.csv
  8. Copy a build.sh from MW/D32/DSP/SHARC/ and adjust the -proc target.
  9. Record baselines in contract-baseline.md; update tasks.md.
EOF
