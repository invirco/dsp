#!/bin/bash
# dynst.sh — build the paired-dynamics self-test, stage it, run it.
#
#   ./dynst.sh              983 MHz, one strip in the graph
#   CCLK=786 ./dynst.sh
#
# One strip (DSP4_STRIPS=1) on purpose: the self-test runs in the main
# loop and the block interrupt steals cycles from BOTH arms, so a heavy
# graph would inflate every number by the same factor and blunt the
# calibration against sigprofile.sh's per-class figures.
set -u
CCLK="${CCLK:-983}"
STRIPS="${STRIPS:-1}"
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
case "$CCLK" in
  983) HZ=983040000;;
  786) HZ=786432000;;
  *)   HZ=491520000;;
esac
DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=1 DSP4_SIMD_NEGCTL=${NEGCTL:-0} \
  DSP4_SIMD_PROBE=${PROBE:-1} DSP4_SKIP_PAIR=${SKIPPAIR:-0} DSP4_SKIP_SIMDCALL=${SKIPSIMD:-0} DSP4_BQP_NOSAVE=${NOSAVE:-0} DSP4_STRIP_FUSED=${FUSED:-1} DSP4_STRIPS=$STRIPS \
  DSP4_CCLK_TARGET=$CCLK ./build.sh > /tmp/dynst_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/dynst_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' /tmp/dynst_build.log | head; exit 1; fi
python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json dynst_read.py ../../../../tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
scp -q dynst_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/dynst_run.sh $HZ"
