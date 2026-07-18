#!/usr/bin/env bash
# Sync product-definition contract artifacts from mx26 into mx-dsp.
#
# Default behavior:
# - imports D24/D32 definition files
# - generates D24/D32 _matrix.csv from mx26 per-product masters
# - verifies hashes against defs.lock
#
# Use --update-lock to refresh defs.lock with current hashes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="$ROOT_DIR/defs.lock"
UPDATE_LOCK=0

if [[ "${1:-}" == "--update-lock" ]]; then
  UPDATE_LOCK=1
fi

select_mx26_repo() {
  if [[ -n "${MX26_REPO:-}" && -f "${MX26_REPO}/src/pd/d24.csv" ]]; then
    echo "$MX26_REPO"
    return
  fi

  local candidates=(
    "$HOME/mx26"
    "$HOME/Stonepower Dropbox/Peter Watts/mx26"
    "/tmp/mx26-scan"
  )

  local c
  for c in "${candidates[@]}"; do
    if [[ -f "$c/src/pd/d24.csv" ]]; then
      echo "$c"
      return
    fi
  done

  echo "ERROR: Could not find mx26 repository with src/pd files." >&2
  echo "Set MX26_REPO to a valid mx26 checkout path." >&2
  exit 1
}

require_file() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "ERROR: Missing required file: $f" >&2
    exit 1
  fi
}

sha() {
  sha256sum "$1" | awk '{print $1}'
}

read_lock_value() {
  local key="$1"
  if [[ ! -f "$LOCK_FILE" ]]; then
    echo ""
    return
  fi
  awk -F= -v k="$key" '$1==k {print $2}' "$LOCK_FILE" | tail -n 1
}

verify_or_write() {
  local key="$1"
  local val="$2"

  if [[ $UPDATE_LOCK -eq 1 ]]; then
    return
  fi

  local expected
  expected="$(read_lock_value "$key")"
  if [[ -z "$expected" || "$expected" == "UNSET" ]]; then
    echo "ERROR: $key is unset in defs.lock. Run: ./sync-from-mx26.sh --update-lock" >&2
    exit 1
  fi
  if [[ "$expected" != "$val" ]]; then
    echo "ERROR: Hash mismatch for $key" >&2
    echo "  expected: $expected" >&2
    echo "  actual:   $val" >&2
    echo "Run with --update-lock only after review and intent to bump contract." >&2
    exit 1
  fi
}

verify_or_write_optional() {
  local key="$1"
  local val="$2"

  if [[ $UPDATE_LOCK -eq 1 ]]; then
    return
  fi

  local expected
  expected="$(read_lock_value "$key")"
  if [[ -z "$expected" || "$expected" == "UNSET" ]]; then
    echo "ERROR: $key is unset in defs.lock. Run: ./sync-from-mx26.sh --update-lock" >&2
    exit 1
  fi
  if [[ "$expected" != "$val" ]]; then
    echo "ERROR: Hash mismatch for optional key $key" >&2
    echo "  expected: $expected" >&2
    echo "  actual:   $val" >&2
    echo "Run with --update-lock only after review and intent to bump contract." >&2
    exit 1
  fi
}

MX26_REPO_PATH="$(select_mx26_repo)"

D24_DEF_SRC="$MX26_REPO_PATH/src/pd/d24.csv"
D24_FW_SRC="$MX26_REPO_PATH/src/pd/d24/fw.csv"
D24_MASTER_SRC="$MX26_REPO_PATH/src/pd/d24-mx-master.csv"
D24_DSP_CFG_SRC="$MX26_REPO_PATH/src/pd/d24/dsp.csv"
D32_DEF_SRC="$MX26_REPO_PATH/src/pd/d32.csv"
D32_FW_SRC="$MX26_REPO_PATH/src/pd/d32/fw.csv"
D32_MASTER_SRC="$MX26_REPO_PATH/src/pd/d32-mx-master.csv"
D32_DSP_CFG_SRC="$MX26_REPO_PATH/src/pd/d32/dsp.csv"

for f in \
  "$D24_DEF_SRC" "$D24_FW_SRC" "$D24_MASTER_SRC" \
  "$D32_DEF_SRC" "$D32_FW_SRC" "$D32_MASTER_SRC" \
  "$MX26_REPO_PATH/tools/expand_matrix.py" \
  "$ROOT_DIR/prune-compat-aliases.py" \
  "$ROOT_DIR/alias-retire-families.txt"; do
  require_file "$f"
done

mkdir -p \
  "$ROOT_DIR/MW/D24/DEFS" "$ROOT_DIR/MW/D24/FW" "$ROOT_DIR/MW/D24/MX" "$ROOT_DIR/MW/D24/DSPCFG" \
  "$ROOT_DIR/MW/D32/DEFS" "$ROOT_DIR/MW/D32/FW" "$ROOT_DIR/MW/D32/MX" "$ROOT_DIR/MW/D32/DSPCFG"

cp "$D24_DEF_SRC" "$ROOT_DIR/MW/D24/DEFS/d24.csv"
cp "$D24_FW_SRC" "$ROOT_DIR/MW/D24/FW/fw.csv"
cp "$D24_MASTER_SRC" "$ROOT_DIR/MW/D24/MX/d24-mx-master.csv"

cp "$D32_DEF_SRC" "$ROOT_DIR/MW/D32/DEFS/d32.csv"
cp "$D32_FW_SRC" "$ROOT_DIR/MW/D32/FW/fw.csv"
cp "$D32_MASTER_SRC" "$ROOT_DIR/MW/D32/MX/d32-mx-master.csv"

D24_DSP_CFG_HASH="ABSENT"
if [[ -f "$D24_DSP_CFG_SRC" ]]; then
  cp "$D24_DSP_CFG_SRC" "$ROOT_DIR/MW/D24/DSPCFG/dsp.csv"
  D24_DSP_CFG_HASH="$(sha "$ROOT_DIR/MW/D24/DSPCFG/dsp.csv")"
else
  rm -f "$ROOT_DIR/MW/D24/DSPCFG/dsp.csv"
fi

D32_DSP_CFG_HASH="ABSENT"
if [[ -f "$D32_DSP_CFG_SRC" ]]; then
  cp "$D32_DSP_CFG_SRC" "$ROOT_DIR/MW/D32/DSPCFG/dsp.csv"
  D32_DSP_CFG_HASH="$(sha "$ROOT_DIR/MW/D32/DSPCFG/dsp.csv")"
else
  rm -f "$ROOT_DIR/MW/D32/DSPCFG/dsp.csv"
fi

python3 "$MX26_REPO_PATH/tools/expand_matrix.py" \
  "$ROOT_DIR/MW/D24/MX/d24-mx-master.csv" \
  -o "$ROOT_DIR/MW/D24/MX/_matrix.csv" >/dev/null
python3 "$MX26_REPO_PATH/tools/expand_matrix.py" \
  "$ROOT_DIR/MW/D32/MX/d32-mx-master.csv" \
  -o "$ROOT_DIR/MW/D32/MX/_matrix.csv" >/dev/null

python3 "$ROOT_DIR/prune-compat-aliases.py" \
  --aliases "$ROOT_DIR/alias-retire-families.txt" \
  "$ROOT_DIR/MW/D24/MX/_matrix.csv" \
  "$ROOT_DIR/MW/D32/MX/_matrix.csv" >/dev/null

D24_DEF_SHA="$(sha "$ROOT_DIR/MW/D24/DEFS/d24.csv")"
D24_FW_SHA="$(sha "$ROOT_DIR/MW/D24/FW/fw.csv")"
D24_MASTER_SHA="$(sha "$ROOT_DIR/MW/D24/MX/d24-mx-master.csv")"
D24_MATRIX_SHA="$(sha "$ROOT_DIR/MW/D24/MX/_matrix.csv")"

D32_DEF_SHA="$(sha "$ROOT_DIR/MW/D32/DEFS/d32.csv")"
D32_FW_SHA="$(sha "$ROOT_DIR/MW/D32/FW/fw.csv")"
D32_MASTER_SHA="$(sha "$ROOT_DIR/MW/D32/MX/d32-mx-master.csv")"
D32_MATRIX_SHA="$(sha "$ROOT_DIR/MW/D32/MX/_matrix.csv")"

verify_or_write D24_DEF_SHA256 "$D24_DEF_SHA"
verify_or_write D24_FW_SHA256 "$D24_FW_SHA"
verify_or_write D24_MASTER_SHA256 "$D24_MASTER_SHA"
verify_or_write D24_MATRIX_SHA256 "$D24_MATRIX_SHA"
verify_or_write D32_DEF_SHA256 "$D32_DEF_SHA"
verify_or_write D32_FW_SHA256 "$D32_FW_SHA"
verify_or_write D32_MASTER_SHA256 "$D32_MASTER_SHA"
verify_or_write D32_MATRIX_SHA256 "$D32_MATRIX_SHA"
verify_or_write_optional D24_DSP_CFG_SHA256 "$D24_DSP_CFG_HASH"
verify_or_write_optional D32_DSP_CFG_SHA256 "$D32_DSP_CFG_HASH"

SOURCE_COMMIT="UNKNOWN"
if [[ -d "$MX26_REPO_PATH/.git" ]]; then
  SOURCE_COMMIT="$(git -C "$MX26_REPO_PATH" rev-parse HEAD)"
fi

CONTRACT_VERSION="defs-v$(date +%Y.%m.%d)"
if [[ -d "$MX26_REPO_PATH/.git" ]]; then
  if tag_name="$(git -C "$MX26_REPO_PATH" describe --tags --exact-match 2>/dev/null)"; then
    if [[ "$tag_name" == defs-v* ]]; then
      CONTRACT_VERSION="$tag_name"
    fi
  fi
fi

if [[ $UPDATE_LOCK -eq 1 ]]; then
  cat > "$LOCK_FILE" <<EOF
# mx26 definitions lock for mx-dsp
# Generated/updated by sync-from-mx26.sh --update-lock

SOURCE_REPO=invirco/mx26
SOURCE_REF=main
SOURCE_COMMIT=$SOURCE_COMMIT
CONTRACT_VERSION=$CONTRACT_VERSION

D24_DEF_SHA256=$D24_DEF_SHA
D24_FW_SHA256=$D24_FW_SHA
D24_MASTER_SHA256=$D24_MASTER_SHA
D24_MATRIX_SHA256=$D24_MATRIX_SHA

D32_DEF_SHA256=$D32_DEF_SHA
D32_FW_SHA256=$D32_FW_SHA
D32_MASTER_SHA256=$D32_MASTER_SHA
D32_MATRIX_SHA256=$D32_MATRIX_SHA

D24_DSP_CFG_SHA256=$D24_DSP_CFG_HASH
D32_DSP_CFG_SHA256=$D32_DSP_CFG_HASH
EOF
  echo "Updated defs.lock from $MX26_REPO_PATH"
else
  echo "Verified contract hashes against defs.lock"
fi

echo "Synced D24 and D32 contract artifacts from: $MX26_REPO_PATH"
