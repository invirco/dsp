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
# THE SHARED SCRATCH SLOT, NAMED (S16-9). ~/dspboot/chip{1,2}.ldr is not a
# staged pair -- it is whatever the last measurement run left there, and this
# script overwrites it. The staged pairs are the PREFIXED ones (blk_*, cand_*,
# geq_*, dyn_*, flr_*, conf_*, ship_*, tx_*, s16_*) and nothing here writes
# those. STAGE names a directory of this run's own when the image must survive
# the next script; it defaults to the scratch slot so nothing that calls this
# changes behaviour.
STAGE="${STAGE:-/home/app/dspboot}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports. Symlinked, not copied, so there is one working set and a
# staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi
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
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json dynst_read.py ../../../../tools/pi/dsp4_block.py $BENCH:$STAGE/
scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:$STAGE/audio_verdict.py
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q dynst_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/dynst_run.sh $HZ"
