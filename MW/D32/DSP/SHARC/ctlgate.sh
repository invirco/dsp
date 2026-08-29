#!/bin/bash
# ctlgate.sh — the control-rate gate (review findings D22/D24) against its
# own negative control, ON THE PART.
#
# THE CLAIM is that skipping a node's control-rate prep on a block where
# nothing changed is EXACT, not approximate: the prep is idempotent on
# unchanged inputs, so not running it stores the same coefficients it would
# have stored. A claim of that shape is worth exactly what its control is
# worth, so this builds the same tree twice --
#
#   gate    DSP4_CTL_ALWAYS=0   the gate is in (the build being proved)
#   always  DSP4_CTL_ALWAYS=1   the gate is compiled out; every node preps
#                               every block, as it did before the gate
#
# -- and captures the MAIN BUS from a running graph in each, word for word.
#
# THE BUS, not a pool slot, for the reason dsp4_pairgraph.py gives: it is
# the sum of every strip's router output and it is the same symbol in both
# builds. The capture harness IS dsp4_pairgraph.py, unchanged -- it drives
# a known step into one strip with the gate and compressor in opposite arms
# on the two strips, which is what makes a coefficient that went stale
# visible in the sum.
#
# WHAT MAKES THIS ABLE TO FAIL. The capture is taken AFTER the harness has
# written ~20 parameters per strip over SPI. A gate that never noticed a
# write would hold the boot-time coefficients and the two captures could
# not agree; a gate that noticed writes but lost a RAMP would disagree
# while the fader was still moving. Both are the failure this looks for.
#
#   ./ctlgate.sh              strip 1 driven
#   STRIP=2 ./ctlgate.sh      the other strip of the pair driven
#   FUSED=1 ./ctlgate.sh      same question on the fused kernels
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
STRIP="${STRIP:-1}"
N="${N:-64}"
STRIPS="${STRIPS:-2}"
OUT=/tmp/ctlgate
mkdir -p $OUT

run_one() {   # tag  CTL_ALWAYS  CTL_NEGCTL
  local tag=$1 always=$2 neg=$3
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_CTL_ALWAYS=$always DSP4_CTL_NEGCTL=$neg \
    DSP4_SIMD_DYN=${SIMD:-0} DSP4_STRIP_FUSED=${FUSED:-0} DSP4_STRIPS=$STRIPS \
    ./build.sh > $OUT/build_$tag.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build_$tag.log)" -ne 0 ]; then
    echo "$tag: BUILD FAILED"; grep -iE '\[Error' $OUT/build_$tag.log | head; return 1; fi
  echo "  $tag: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      $ROOT/tools/pi/dsp4_block.py $ROOT/tools/pi/dsp4_pairgraph.py \
      $BENCH:/home/app/dspboot/
  scp -q pairgraph_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/pairgraph_run.sh $STRIP $N $tag"
  scp -q $BENCH:/home/app/dspboot/pairgraph_$tag.json $OUT/ 2>/dev/null
}

for spec in "always 1 0" "gate 0 0" "deaf 0 1"; do
  # shellcheck disable=SC2086
  set -- $spec
  echo "--- $1 (DSP4_CTL_ALWAYS=$2 DSP4_CTL_NEGCTL=$3) ---"
  run_one "$1" "$2" "$3" || exit 1
done

echo "=== verdict: the gated build must MATCH the ungated one ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/pairgraph_always.json $OUT/pairgraph_gate.json
echo "=== negative control: the DEAF gate must DIFFER ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/pairgraph_always.json $OUT/pairgraph_deaf.json
