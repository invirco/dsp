#!/bin/bash
# busgold.sh — hold the efficiency batch to a STORED bus capture.
#
# Every item in the D20-D25 efficiency batch is bit-exact BY CONSTRUCTION:
# each one deletes work that had no effect on a sample, or moves work to a
# rate at which it produces the same answer. A claim of that shape is
# testable with one instrument -- capture the main bus out of a running
# graph and require it to reproduce, word for word, the capture the code
# produced before the batch.
#
#   goldens/busgraph-prebatch-20260829.json
#       taken 2026-08-29 on the tree at 87fded2 (fix session 1's last
#       commit) with DSP4_BLOCK_KERNELS=1, DSP4_STRIPS=2, strip 1 driven and
#       strip 2 muted, 256 consecutive words of _buf_C1_BUS_MAIN_L.
#       sha256 811af470...
#
# The harness is dsp4_pairgraph.py unchanged: it configures both strips over
# SPI with OPPOSITE dynamics settings, so the two lanes sit in opposite arms
# of every predicated branch, and it writes ~20 parameters per strip before
# capturing. That is what gives the comparison the power to fail -- a node
# that stopped noticing a parameter write, or a delay line whose wrap moved
# by one, cannot reproduce the golden.
#
#   ./busgold.sh                 current tree vs the golden
#   GOLD=<file> ./busgold.sh     against a different stored capture
#   TAG=x ./busgold.sh           name the capture (default: cur)
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
STRIP="${STRIP:-1}"; N="${N:-256}"; STRIPS="${STRIPS:-2}"; TAG="${TAG:-cur}"
GOLD="${GOLD:-goldens/busgraph-prebatch-20260829.json}"
OUT=/tmp/busgold; mkdir -p $OUT

DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
  DSP4_CTL_ALWAYS=${CTL_ALWAYS:-0} DSP4_CTL_NEGCTL=${CTL_NEGCTL:-0} \
  DSP4_SIMD_DYN=${SIMD:-0} DSP4_STRIP_FUSED=${FUSED:-0} \
  ./build.sh > $OUT/build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
echo "  $TAG: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"
python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_block.py $ROOT/tools/pi/dsp4_pairgraph.py \
    $BENCH:/home/app/dspboot/
scp -q pairgraph_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/pairgraph_run.sh $STRIP $N $TAG" || exit 4
scp -q $BENCH:/home/app/dspboot/pairgraph_$TAG.json $OUT/ || exit 4
echo "=== vs $GOLD ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare "$GOLD" $OUT/pairgraph_$TAG.json
