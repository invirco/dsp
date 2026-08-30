#!/bin/bash
# pairgraph.sh — is the PAIRED GRAPH bit-exact against the scalar one?
#
# Builds the same graph three ways and captures the main bus from each:
#
#   off     DSP4_SIMD_DYN=0             the reference
#   on      DSP4_SIMD_DYN=1             pair-ordered chain, odd pool, paired
#                                       dynamics -- must MATCH the reference
#   neg     DSP4_SIMD_DYN=1 NEGCTL=1    the pair gathers channel B from
#                                       channel A, so it computes one
#                                       channel twice -- must DIFFER
#
# The negative control is the whole point. A diff that cannot fail proves
# nothing, and an identical-data pair test is exactly that kind of diff.
#
#   ./pairgraph.sh              strip 1 driven, strip 2 muted
#   STRIP=2 ./pairgraph.sh      the other way round
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STRIP="${STRIP:-1}"
N="${N:-64}"
STRIPS="${STRIPS:-2}"
OUT=/tmp/pairgraph
mkdir -p $OUT

run_one() {   # tag  SIMD_DYN  NEGCTL
  local tag=$1 dyn=$2 neg=$3
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=$dyn DSP4_SIMD_NEGCTL=$neg \
    DSP4_STRIP_FUSED=${FUSED:-0} DSP4_STRIPS=$STRIPS ./build.sh \
    > /tmp/pairgraph_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/pairgraph_build.log)" -ne 0 ]; then
    echo "$tag: BUILD FAILED"; grep -iE '\[Error' /tmp/pairgraph_build.log | head; return 1; fi
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      ../../../../tools/pi/dsp4_block.py ../../../../tools/pi/dsp4_pairgraph.py \
      $BENCH:/home/app/dspboot/
  scp -q pairgraph_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/pairgraph_run.sh $STRIP $N $tag"
  scp -q $BENCH:/home/app/dspboot/pairgraph_$tag.json $OUT/ 2>/dev/null
}

for spec in "off 0 0" "on 1 0" "neg 1 1"; do
  # shellcheck disable=SC2086
  set -- $spec
  echo "--- $1 ---"
  run_one "$1" "$2" "$3" || exit 1
done

echo "=== verdict ==="
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_off.json $OUT/pairgraph_on.json
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_off.json $OUT/pairgraph_neg.json
