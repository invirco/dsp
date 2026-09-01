#!/bin/bash
# c2gold.sh — CHIP 2, PER-SAMPLE vs BLOCK-KERNEL, BIT-EXACT (finding D16).
#
# The bar chip 2 did not have. busgold.sh, goldnode.sh, bqgraph.sh and the
# vector bars are all chip-1 instruments -- "the one XOVER instance is on
# chip 2, where no vector bar runs" -- so a chip-2 conversion could otherwise
# only claim "it builds and the cycle count moved".
#
# WHAT IT COMPARES, AND WHY THAT IS A FAIR COMPARISON. Every converted chip-2
# node keeps its scalar `_buf_<id>` live and equal to the LAST SAMPLE OF THE
# BLOCK: the wrapper's body writes it on every call, so the last call leaves
# sample BLOCK-1 there; FADER_PAN's and the cascades' kernels store it
# explicitly for the same reason. The per-sample build's `_buf_<id>` is also
# the last sample it processed. So the two builds publish THE SAME SAMPLE
# POSITION in the same word, node for node, and comparing them is a direct
# bit-exactness test of the conversion -- not a proxy.
#
# THE INPUT IS THE SAME IN BOTH BUILDS BY CONSTRUCTION. DSP4_PROFILE_SIGNAL
# puts the same alternating +/-0.5 square into the INTERCHIP_RECV kernels of
# both, so neither build depends on the inter-chip fabric (which delivers
# nothing on this bench -- see sigprofile2.sh) and both see an identical,
# deterministic input sequence with the same phase at the block boundary.
#
# THE METERS ARE IN THE COMPARISON ON PURPOSE. Their agreement is the direct
# evidence for the third item of the D16 dispatch: chip 2's OUTPUT_TDM and
# bus-COMPRESSOR meters were decimated to one sample per block because their
# SOURCES were unconverted. If the sources are really converted, the block
# build's meter and the per-sample build's meter are folding the same eight
# samples and must agree bit for bit.
#
# NEGATIVE CONTROL: the same comparison run against a DELIBERATELY WRONG
# pairing (each node against its neighbour in the probe list). A bar that
# cannot fail is not a bar.
set -u
DWELL="${DWELL:-12}"
BLOCK="${BLOCK:-8}"
WORK="${WORK:-/tmp/c2gold}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

SRC="$PWD/src"
if [ "$BLOCK" != "8" ]; then
  SRC="$WORK/src$BLOCK"
  rm -rf "$SRC"; cp -r "$PWD/src" "$SRC"
  DSP4_GEN_BLOCK=$BLOCK python3 $ROOT/tools/dsp/dsp_codegen.py \
      "$PWD/dsp.csv" "$SRC" --force >/dev/null 2>&1
  grep -q "define DSP4_BLOCK_SIZE   $BLOCK\$" "$SRC/dsp_block.h" || {
      echo "c2gold: generated tree for block $BLOCK does not say so" >&2; exit 5; }
fi

run_arm() {   # $1 = kernels (0|1) -> writes $WORK/arm$1.json on the card
  local K="$1" D="$WORK/k$K-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=$K DSP4_PROFILE_SIGNAL=1 \
    DSP4_BLOCK_DECIMATE=1 ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM $K BUILD FAILED (see $D.log)" >&2; return 1; fi
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:/home/app/dspboot/
  scp -q c2gold_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/c2gold_run.sh $DWELL /home/app/dspboot/arm$K.json" \
    2>&1 | sed "s/^/  arm$K: /"
}

echo "=== chip-2 gold, BLOCK=$BLOCK ==="
run_arm 0 || exit 1
run_arm 1 || exit 1
scp -q $BENCH:/home/app/dspboot/arm0.json $BENCH:/home/app/dspboot/arm1.json "$WORK/"
python3 - "$WORK/arm0.json" "$WORK/arm1.json" <<'PYEOF'
import json, sys
a = json.load(open(sys.argv[1]))
b = json.load(open(sys.argv[2]))
names = [n for n in a if n in b]
diff = [n for n in names if a[n] != b[n]]
print(f'\nCHIP-2 GOLD: {len(names)} probes, {len(diff)} differ '
      f'(per-sample arm vs block-kernel arm, BIT-EXACT means 0)')
for n in diff:
    print(f'  DIFFERS  {n:34s} per-sample=0x{a[n]:08X} block=0x{b[n]:08X}')
# NEGATIVE CONTROL: pair each probe with its NEIGHBOUR across the two arms.
# If the comparison above cannot fail, this will not fail either.
shifted = names[1:] + names[:1]
nc = sum(1 for n, m in zip(names, shifted) if a[n] != b[m])
print(f'NEGCTL: {nc} of {len(names)} differ under a deliberately wrong pairing '
      f'({"PASSED" if nc >= len(names) // 2 else "FAILED — the comparison cannot fail"})')
print('VERDICT: ' + ('CHIP-2 BIT-EXACT' if not diff else f'DIFFERS ({len(diff)})'))
sys.exit(0 if not diff else 1)
PYEOF
