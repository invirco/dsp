#!/usr/bin/env bash
# regen-s49-proposal.sh — regenerate the S49 contract proposal, byte for byte.
#
# WHY THIS SCRIPT EXISTS, AND WHY S44 NEEDED NO EQUIVALENT.
#
# S44 proposed ADDRESSES for cells the products already defined, so
# `gen_dsp.py --propose` could read `MW/<P>/MX/_matrix.csv` as it stood and
# `--check-proposal` could reproduce the result from the committed tree alone.
#
# S49 is a different shape. The `Test[1-1]*` family is declared in the CELL
# LIBRARY (`defs/common/cells/mx_master.csv`, 13 rows) and reaches no product:
# `defs/tools/def_master.py` gates the `Test` prefix on the def keys `util` and
# `util.osc`, and NO product def declares either. So the cells are not in any
# `<p>-mx-master.csv`, not in any `_matrix.csv`, and therefore not in
# `dsp-unmapped.csv` either -- gen_dsp.py's proposal is the intersection of the
# graph's expansion with the product's CELL SET, and a cell no product defines
# falls out of it entirely. (The S49 dispatch stated the thirteen cells were
# already listed `no-graph-node` in `dsp-unmapped.csv`. They are not, on any of
# the four products; see CONTRACT-PROPOSAL-S49.md section 1.)
#
# The proposal is therefore TWO things and not one:
#
#   1. a DEF change -- two lines per product -- which only the hub can land;
#   2. the ADDRESSES that follow from it, which this repo derives.
#
# This script derives (2) from (1) without touching `defs/`: it copies each
# product def to a scratch directory, appends the two keys, re-runs defs' OWN
# `def_master.py` and `expand_matrix.py` on the pinned cell library, stages the
# result at the path `sync-defs.sh` already uses for a half-finished expansion
# (`MW/<P>/MX/_matrix.expansion.csv`), runs `gen_dsp.py --propose`, and clears
# the stage again. Nothing in `defs/` is read except as an input and nothing in
# it is written.
#
#   ./proposals/regen-s49-proposal.sh          regenerate the proposal
#   ./proposals/regen-s49-proposal.sh --check  regenerate and prove it is
#                                              byte-identical to what is filed
#
# The --check arm is the S49 gate-3 equivalent of `gen_dsp.py
# --check-proposal`: same question, one transformation further back.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFS_DIR="$ROOT_DIR/defs"
PRODUCTS=(d32 d24 d16 d12)

# The def keys the Test family is gated on. `util` is the scope,
# `util.osc` the function gate -- both from defs/tools/def_master.py's
# PREFIX_RULES, read there and not guessed.
DEF_KEYS=(util util.osc)

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

command -v python3 >/dev/null || { echo "python3 missing" >&2; exit 2; }
[[ -f "$DEFS_DIR/tools/def_master.py" ]] || {
  echo "regen-s49-proposal.sh: the defs submodule is not checked out." >&2
  echo "  git submodule update --init defs" >&2; exit 2; }

PIN="$(awk -F= '$1=="DEFS_TAG"{print $2}' "$ROOT_DIR/defs.lock" | tr -d ' "')"
echo "regen-s49-proposal.sh"
echo "  defs pin : ${PIN:-<none>}"
echo "  def keys : ${DEF_KEYS[*]}"
echo "  products : ${PRODUCTS[*]}"
echo

TMP="$(mktemp -d)"
STAGES=()
cleanup() {
  local s
  for s in ${STAGES+"${STAGES[@]}"}; do [[ -e "$s" ]] && rm -f "$s"; done
  rm -rf "$TMP"
  return 0
}
trap cleanup EXIT

if [[ $CHECK -eq 1 ]]; then
  cp -a "$ROOT_DIR/proposals/defs" "$TMP/filed"
fi

for p in "${PRODUCTS[@]}"; do
  P="${p^^}"
  src="$DEFS_DIR/products/$p/$p.csv"
  [[ -f "$src" ]] || { echo "no def for $p at $src" >&2; exit 2; }

  # THE DEF, PLUS THE TWO KEYS, and refuse to add one that is already there
  # -- a duplicate key is a def the hub would have to reconcile, and a key
  # that has landed means this whole script is obsolete and should be
  # deleted rather than quietly doing nothing.
  cp "$src" "$TMP/$p.csv"
  for k in "${DEF_KEYS[@]}"; do
    if grep -q "^$k," "$TMP/$p.csv"; then
      echo "  $p: def key '$k' is ALREADY DECLARED." >&2
      echo "  The prerequisite has landed; regenerate with a plain" >&2
      echo "  'gen_dsp.py --propose' and retire this script." >&2
      exit 3
    fi
    printf '%s,1\n' "$k" >> "$TMP/$p.csv"
  done

  python3 "$DEFS_DIR/tools/def_master.py" "$TMP/$p.csv" \
      "$DEFS_DIR/common/cells/mx_master.csv" -o "$TMP/$p-mx-master.csv" \
      >/dev/null
  n_test="$(grep -c '^Test\[' "$TMP/$p-mx-master.csv" || true)"
  [[ "$n_test" == "13" ]] || {
    echo "  $p: the master gained $n_test Test rows, expected 13" >&2; exit 4; }

  # Staged at the path sync-defs.sh uses for an expansion that is not
  # finished yet; gen_dsp.py::matrix_input_path() prefers it over the
  # committed matrix, which is exactly the hook wanted here.
  stage="$ROOT_DIR/MW/$P/MX/_matrix.expansion.csv"
  [[ -e "$stage" ]] && {
    echo "  $stage already exists -- a sync-defs.sh run is half finished." >&2
    echo "  Finish it (gen_dsp.py) before proposing." >&2; exit 5; }
  python3 "$DEFS_DIR/tools/expand_matrix.py" "$TMP/$p-mx-master.csv" \
      -o "$stage" >/dev/null
  STAGES+=("$stage")

  # The def itself is part of the proposal: the tree under proposals/
  # mirrors defs/products/, so the hub lands it by copying across.
  install -D -m 0644 "$TMP/$p.csv" \
      "$ROOT_DIR/proposals/defs/products/$p/$p.csv"
  echo "  $p: master +13 Test rows, expansion staged, def filed"
done

echo
python3 "$ROOT_DIR/MW/D32/DSP/gen_dsp.py" --propose \
  | sed -n '/Proposing dsp.csv/,$p' | sed 's/^/  /'

echo
for s in "${STAGES[@]}"; do rm -f "$s"; done
STAGES=()
echo "  stages cleared; MW/<P>/MX/_matrix.csv untouched"

if [[ $CHECK -eq 1 ]]; then
  echo
  if diff -r "$TMP/filed" "$ROOT_DIR/proposals/defs" >/dev/null; then
    echo "CHECK PASSED — the regenerated proposal is byte-identical to the"
    echo "  files committed under proposals/defs/."
  else
    echo "CHECK FAILED — the regenerated proposal differs from what is filed:" >&2
    diff -r "$TMP/filed" "$ROOT_DIR/proposals/defs" | head -40 >&2
    exit 1
  fi
fi
