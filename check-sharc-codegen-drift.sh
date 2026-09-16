#!/usr/bin/env bash
# Drift gate for the GENERATED SHARC sources.
#
# WHY THIS EXISTS (S43, from S42-5).
#
# `check-contract-drift.sh` regenerated the matrices and the D32 DSP address
# artifacts and called that "the whole generation". It never ran
# `tools/dsp/dsp_codegen.py`, so the 726 files that script emits -- every node
# .asm, both shared_kernels.asm, dsp_block.h, bus_accumulators.asm and the rest
# -- were outside every gate the repo had. They drifted, and nothing said so:
# on 2026-09-13 the committed tree differed from its own generator in 117 files,
# and the divergence had been sitting there since 2026-09-10 (S26). Two
# commits six minutes apart did it, both by regenerating less than the
# generator change reached:
#
#   4807d23d  added the pool_in_blk/pool_in_smp split to dsp_codegen.py and
#             committed C1_FILT_01..32 stubs generated before that hunk existed
#             -- 64 lines of i6/l6 setup the split removes.
#   608a1aa3  corrected the overflow comment in the generator after the bench
#             measured it at three points, and regenerated nothing.
#
# Neither was a hand-edit of generated output. Both were stale output. The
# class is the same either way and this gate catches both: the generator is
# the source, so its output IS the committed tree, byte for byte.
#
# METHOD. Generate into an EMPTY scratch directory -- never a copy of the tree,
# which would let the tree's own content leak into the thing it is checked
# against -- and require every emitted file to be byte-identical to its
# committed counterpart. Files that exist in src/ and are NOT emitted are the
# hand-written sources; they are listed below by name, and the list is checked
# too, so a generator that quietly stops emitting a file is caught (the file
# falls out of the generated set into the hand-written one) rather than
# silently dropping out of the gate.
#
# Usage:
#   ./check-sharc-codegen-drift.sh            # gate the committed tree
#   ./check-sharc-codegen-drift.sh --negative-control
#         # prove the gate fires: hand-edit one line of one generated file in a
#         # throwaway copy of the tree and require the gate to fail on it
#
# Exit: 0 pass, 1 drift, 2 usage or environment error.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

SRC_DIR="MW/D32/DSP/SHARC/src"
DSP_CSV="MW/D32/DSP/SHARC/dsp.csv"
CODEGEN="tools/dsp/dsp_codegen.py"

NEGCTL=0
[[ "${1:-}" == "--negative-control" ]] && NEGCTL=1

for f in "$DSP_CSV" "$CODEGEN"; do
  [[ -r "$f" ]] || { echo "ERROR: missing $f" >&2; exit 2; }
done
[[ -d "$SRC_DIR" ]] || { echo "ERROR: missing $SRC_DIR" >&2; exit 2; }

# The hand-written sources: everything under src/ that dsp_codegen.py does not
# emit. `chip*/dsp_params.asm` is generated too -- by MW/D32/DSP/gen_dsp.py,
# not by this generator -- and is gated by check-contract-drift.sh's own
# CONTRACT_FILES list, so it belongs here.
mapfile -t HANDWRITTEN <<'LIST'
blink/blink.asm
blink/blink_ivt.asm
blink/bulkprobe.asm
blink/clkprobe.asm
blink/rdyprobe.asm
blink/sruprobe.asm
bulk_read.asm
c_abi.h
cgu_init.asm
chip1/dsp_params.asm
chip1/spi_handler.asm
chip2/dsp_params.asm
chip2/spi_handler.asm
diag.asm
diag.h
dma_config.c
ivt.asm
lib2/lim_simd_fx.asm
lib/afb_design_fx.asm
lib/biquad.asm
lib/biquad_fx.asm
lib/bqe_verify.asm
lib/bq_guard_test.asm
lib/bq_headroom.asm
lib/bq_probe.asm
lib/bq_selftest.asm
lib/bq_shootout.asm
lib/call_selftest.asm
lib/delay.asm
lib/delay_pool.asm
lib/dynamics.asm
lib/dyn_fx.asm
lib/dyn_lut_fx.asm
lib/dyn_lut.h
lib/dyn_selftest.asm
lib/dyn_shootout.asm
lib/dyn_simd_fx.asm
lib/dyn_simd_inline.h
lib/dyn_tables_fx.asm
lib/geq_design_fx.asm
lib/mac64_fx.asm
lib/meter.asm
lib/meter_fx.asm
lib/xover_design_fx.asm
main.asm
product_config.asm
scope.asm
sport_config.c
sport_init.asm
sru_config.c
tx_probe.asm
LIST

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ---- the tree under test -------------------------------------------------
# Normally the committed tree itself. Under --negative-control, a throwaway
# copy with one line of one GENERATED file hand-edited, which is the fault
# this gate exists to catch.
TREE="$SRC_DIR"
if [[ $NEGCTL -eq 1 ]]; then
  TREE="$WORK/tree"
  cp -a "$SRC_DIR" "$TREE"
  victim="$TREE/chip1/nodes/C1_FILT_01.asm"
  [[ -f "$victim" ]] || { echo "ERROR: negative control victim missing" >&2; exit 2; }
  # A one-line hand-edit of the kind the mandate forbids: change a register
  # the per-sample stub loads. It assembles; it is wrong; nothing else says so.
  perl -0pi -e 's/(_C1_FILT_01_process_sample:\n    i7 = )_filt_hpf_A_C1_FILT_01;/${1}_filt_hpf_A_C1_FILT_02;/' "$victim"
  if git diff --no-index --quiet "$SRC_DIR/chip1/nodes/C1_FILT_01.asm" "$victim" 2>/dev/null; then
    echo "ERROR: negative control did not modify the victim file" >&2
    exit 2
  fi
  echo "negative control: one line hand-edited in chip1/nodes/C1_FILT_01.asm"
fi

# ---- generate into an empty directory ------------------------------------
GEN="$WORK/gen"
mkdir -p "$GEN"
if ! python3 "$CODEGEN" "$DSP_CSV" "$GEN" --force > "$WORK/codegen.log" 2>&1; then
  echo "ERROR: dsp_codegen.py failed; see below" >&2
  tail -30 "$WORK/codegen.log" >&2
  exit 2
fi

( cd "$GEN" && find . -type f | sed 's|^\./||' | sort ) > "$WORK/generated.txt"
n_gen=$(wc -l < "$WORK/generated.txt")
if [[ $n_gen -eq 0 ]]; then
  echo "ERROR: the generator emitted nothing" >&2
  exit 2
fi

# ---- every emitted file must match the tree, byte for byte ---------------
: > "$WORK/differ.txt"
: > "$WORK/missing.txt"
while IFS= read -r rel; do
  if [[ ! -f "$TREE/$rel" ]]; then
    echo "$rel" >> "$WORK/missing.txt"
  elif ! cmp -s "$GEN/$rel" "$TREE/$rel"; then
    echo "$rel" >> "$WORK/differ.txt"
  fi
done < "$WORK/generated.txt"

n_differ=$(wc -l < "$WORK/differ.txt")
n_missing=$(wc -l < "$WORK/missing.txt")

# ---- and the hand-written set must be exactly what is declared -----------
printf '%s\n' "${HANDWRITTEN[@]}" | sort > "$WORK/declared.txt"
git ls-files "$SRC_DIR" | sed "s|^$SRC_DIR/||" | sort > "$WORK/tracked.txt"
comm -23 "$WORK/tracked.txt" "$WORK/generated.txt" > "$WORK/actual_hw.txt"
hw_drift="$(diff "$WORK/declared.txt" "$WORK/actual_hw.txt" || true)"

echo "SHARC codegen drift check"
echo "  generated into a scratch tree: $n_gen files"
echo "  differ from the committed tree: $n_differ"
echo "  emitted but absent from the tree: $n_missing"
echo "  hand-written (not emitted): $(wc -l < "$WORK/actual_hw.txt")"

rc=0
if [[ $n_differ -gt 0 ]]; then
  echo "ERROR: $n_differ generated file(s) differ from the generator's output:" >&2
  sed 's/^/    /' "$WORK/differ.txt" | head -40 >&2
  [[ $n_differ -gt 40 ]] && echo "    ... and $((n_differ - 40)) more" >&2
  rc=1
fi
if [[ $n_missing -gt 0 ]]; then
  echo "ERROR: $n_missing generated file(s) are not in the committed tree:" >&2
  sed 's/^/    /' "$WORK/missing.txt" | head -40 >&2
  rc=1
fi
if [[ -n "$hw_drift" ]]; then
  echo "ERROR: the hand-written source set moved (< declared, > actual):" >&2
  echo "$hw_drift" | sed 's/^/    /' >&2
  echo "  A file that moved from generated to hand-written has left the gate." >&2
  echo "  Update the HANDWRITTEN list in this script only when that is intended." >&2
  rc=1
fi

if [[ $NEGCTL -eq 1 ]]; then
  if [[ $rc -eq 0 ]]; then
    echo "NEGATIVE CONTROL FAILED: the gate did not catch a hand-edited line" >&2
    exit 1
  fi
  echo "negative control passed: the gate caught it"
  exit 0
fi

if [[ $rc -ne 0 ]]; then
  echo "" >&2
  echo "The generator is the source. Regenerate rather than edit:" >&2
  echo "  python3 $CODEGEN $DSP_CSV $SRC_DIR --force" >&2
  echo "If the tree is right and the generator is wrong, change the generator." >&2
  exit 1
fi

echo "SHARC codegen drift check passed (tree == generator output)"
