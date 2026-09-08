#!/usr/bin/env bash
# sync-defs.sh — consume the `defs` submodule (invirco/defs).
#
# This repo is a CONSUMER of the definitions, not a second source of them.
# Every product def, the cell master, the wire declaration and the ONLY
# matrix expander live in `defs/`, pinned by `defs.lock` to a `defs-v*` tag.
# Nothing here copies a definition CSV into the tree and nothing here
# rewrites an expansion after the expander produced it: both were how this
# repo used to grow a matrix generation of its own.
#
# What it does:
#   1. verifies the checked-out submodule against defs.lock (commit + tag)
#   2. verifies the defs content manifest against defs.lock
#   3. regenerates MW/<P>/MX/_matrix.csv with defs/tools/expand_matrix.py
#      and verifies the expansion hash + matrix generation id
#
# The DSP address columns (DspSpi/DspPage/DspAdd/DspAddHex/Ramp*) are NOT
# part of the expansion: gen_dsp.py backfills them afterwards as a
# consumer-side derived table. This script always writes the bare
# expansion, so the pair (sync-defs.sh; gen_dsp.py --force) is the whole
# definition of MW/<P>/MX/_matrix.csv.
#
# Use --update-lock to refresh defs.lock from the current submodule state.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFS_DIR="$ROOT_DIR/defs"
LOCK_FILE="$ROOT_DIR/defs.lock"
UPDATE_LOCK=0

if [[ "${1:-}" == "--update-lock" ]]; then
  UPDATE_LOCK=1
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--update-lock]" >&2
  exit 2
fi

PRODUCTS=(d24 d32)

sha() { sha256sum "$1" | awk '{print $1}'; }

read_lock_value() {
  local key="$1"
  [[ -f "$LOCK_FILE" ]] || { echo ""; return; }
  awk -F= -v k="$key" '$1==k {print $2}' "$LOCK_FILE" | tail -n 1
}

fail=0
verify() {
  local key="$1" val="$2"
  [[ $UPDATE_LOCK -eq 1 ]] && return 0
  local expected
  expected="$(read_lock_value "$key")"
  if [[ -z "$expected" ]]; then
    echo "ERROR: $key is unset in defs.lock. Run: ./sync-defs.sh --update-lock" >&2
    fail=1
    return 0
  fi
  if [[ "$expected" != "$val" ]]; then
    echo "ERROR: defs.lock mismatch for $key" >&2
    echo "  locked: $expected" >&2
    echo "  actual: $val" >&2
    fail=1
  fi
}

# ---------------------------------------------------------------------------
# 1. The submodule itself
# ---------------------------------------------------------------------------
if [[ ! -f "$DEFS_DIR/defs.toml" ]]; then
  echo "ERROR: the defs submodule is not checked out at $DEFS_DIR." >&2
  echo "       Run: git submodule update --init defs" >&2
  exit 1
fi

DEFS_COMMIT="$(git -C "$DEFS_DIR" rev-parse HEAD)"

# The pin must be a real defs-v* tag. A commit with no tag is exactly the
# untracked skew the pin exists to kill, so --update-lock refuses it.
DEFS_TAG=""
if tag_name="$(git -C "$DEFS_DIR" describe --tags --exact-match 2>/dev/null)"; then
  [[ "$tag_name" == defs-v* ]] && DEFS_TAG="$tag_name"
fi
if [[ -z "$DEFS_TAG" ]]; then
  if [[ $UPDATE_LOCK -eq 1 ]]; then
    echo "ERROR: defs HEAD ($DEFS_COMMIT) carries no defs-v* tag — tag it in" >&2
    echo "       invirco/defs before pinning it here." >&2
    exit 1
  fi
  DEFS_TAG="UNTAGGED"
fi

# The gitlink recorded in THIS repo's index, which is what a fresh clone
# would check out. A dirty or moved submodule working tree is drift.
GITLINK="$(git -C "$ROOT_DIR" ls-files -s defs | awk '{print $2}')"
if [[ -n "$GITLINK" && "$GITLINK" != "$DEFS_COMMIT" ]]; then
  echo "ERROR: defs/ working tree ($DEFS_COMMIT) is not the commit this repo" >&2
  echo "       records ($GITLINK). Run: git submodule update defs" >&2
  exit 1
fi

verify DEFS_COMMIT "$DEFS_COMMIT"
verify CONTRACT_VERSION "$DEFS_TAG"

# ---------------------------------------------------------------------------
# 2. The defs content manifest
# ---------------------------------------------------------------------------
# defs-manifest.sh hashes every declaration and generated artifact in the
# submodule (tools/ excluded — it is the generator, not a definition). One
# hash over that manifest catches any edit inside a checked-out submodule
# that the commit id alone would not.
DEFS_MANIFEST="$(bash "$DEFS_DIR/tools/defs-manifest.sh")"
DEFS_MANIFEST_SHA="$(printf '%s\n' "$DEFS_MANIFEST" | sha256sum | awk '{print $1}')"
verify DEFS_MANIFEST_SHA256 "$DEFS_MANIFEST_SHA"

# The individual declarations this repo reads, named so a mismatch says
# which definition moved rather than only that something did.
declare -A CONSUMED=(
  [MX_CELL_MASTER]="common/cells/mx_master.csv"
  [WIRE_UNITS]="common/wire/wire-units.csv"
  [D24_DEF]="products/d24/d24.csv"
  [D24_FW]="products/d24/fw.csv"
  [D24_MASTER]="gen/matrix/d24-mx-master.csv"
  [D24_WIRE_TABLE]="gen/matrix/d24-wire-table.csv"
  [D32_DEF]="products/d32/d32.csv"
  [D32_FW]="products/d32/fw.csv"
  [D32_MASTER]="gen/matrix/d32-mx-master.csv"
  [D32_WIRE_TABLE]="gen/matrix/d32-wire-table.csv"
)
declare -A CONSUMED_SHA=()
for key in "${!CONSUMED[@]}"; do
  f="$DEFS_DIR/${CONSUMED[$key]}"
  if [[ ! -f "$f" ]]; then
    echo "ERROR: defs is missing ${CONSUMED[$key]} — the pin does not carry" >&2
    echo "       a definition this repo consumes." >&2
    exit 1
  fi
  CONSUMED_SHA[$key]="$(sha "$f")"
  verify "${key}_SHA256" "${CONSUMED_SHA[$key]}"
done

# ---------------------------------------------------------------------------
# 3. The expansion
# ---------------------------------------------------------------------------
declare -A MATRIX_SHA=() MATRIX_GEN=()
for p in "${PRODUCTS[@]}"; do
  P="${p^^}"
  mkdir -p "$ROOT_DIR/MW/$P/MX"
  out="$ROOT_DIR/MW/$P/MX/_matrix.csv"
  python3 "$DEFS_DIR/tools/expand_matrix.py" \
    "$DEFS_DIR/gen/matrix/$p-mx-master.csv" -o "$out" >/dev/null
  MATRIX_SHA[$P]="$(sha "$out")"
  MATRIX_GEN[$P]="$(python3 "$DEFS_DIR/tools/matrix_gen_id.py" "$out" \
                     | awk '$1=="base-id"{print $2}')"
  verify "${P}_MATRIX_SHA256" "${MATRIX_SHA[$P]}"
  verify "${P}_MATRIX_GEN" "${MATRIX_GEN[$P]}"
done

if [[ $fail -ne 0 ]]; then
  echo "Run --update-lock only after review and intent to bump the contract." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. defs.lock
# ---------------------------------------------------------------------------
if [[ $UPDATE_LOCK -eq 1 ]]; then
  {
    echo "# definitions lock for the dsp spoke."
    echo "#"
    echo "# The definitions are the \`defs\` submodule; this file pins WHICH"
    echo "# commit of it, and records the hashes of everything read out of it."
    echo "# Generated/updated by ./sync-defs.sh --update-lock — never by hand."
    echo ""
    echo "DEFS_REPO=invirco/defs"
    echo "DEFS_PATH=defs"
    echo "DEFS_COMMIT=$DEFS_COMMIT"
    echo "CONTRACT_VERSION=$DEFS_TAG"
    echo "DEFS_MANIFEST_SHA256=$DEFS_MANIFEST_SHA"
    echo ""
    echo "# Declarations consumed by this repo (paths relative to defs/)."
    for key in $(printf '%s\n' "${!CONSUMED[@]}" | sort); do
      echo "${key}_SHA256=${CONSUMED_SHA[$key]}"
    done
    echo ""
    echo "# MW/<P>/MX/_matrix.csv as defs/tools/expand_matrix.py writes it,"
    echo "# BEFORE gen_dsp.py backfills the DSP address columns. _GEN is the"
    echo "# matrix generation id (defs/tools/matrix_gen_id.py base-id) — the"
    echo "# one number that is comparable against the console and the app."
    for p in "${PRODUCTS[@]}"; do
      P="${p^^}"
      echo "${P}_MATRIX_SHA256=${MATRIX_SHA[$P]}"
      echo "${P}_MATRIX_GEN=${MATRIX_GEN[$P]}"
    done
  } > "$LOCK_FILE"
  echo "Updated defs.lock from defs@$DEFS_TAG ($DEFS_COMMIT)"
else
  echo "Verified defs@$DEFS_TAG ($DEFS_COMMIT) against defs.lock"
fi

for p in "${PRODUCTS[@]}"; do
  P="${p^^}"
  printf '  %s _matrix.csv expanded — generation %s\n' "$P" "${MATRIX_GEN[$P]}"
done
