#!/bin/bash
# mtrverify.sh — the rebuilt meter against fixed_ref, on the part.
#
# Builds a block-kernel image with the square-wave stimulus on, stages it
# with the reference model and the block-size contract beside it, and runs
# dsp4_mtr_verify.py. The bar is EXACT agreement of the two 64-bit meter
# state words with fixed_ref.meter_block, plus a negative control against
# the other block size's coefficients.
#
#   ./mtrverify.sh                       # C1_MTR_01, 1 strip
#   STRIPS=4 ./mtrverify.sh C1_MTR_03
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
MTR="${1:-C1_MTR_01}"
STRIPS="${STRIPS:-1}"
DWELL="${DWELL:-25}"
DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 \
  DSP4_STRIPS=$STRIPS ./build.sh > /tmp/mtrverify_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/mtrverify_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; tail -20 /tmp/mtrverify_build.log; exit 1; fi
python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    ../../../../tools/pi/dsp4_block.py \
    ../../../../tools/pi/dsp4_mtr_verify.py \
    ../../../../tools/dsp/fixed_ref.py $BENCH:/home/app/dspboot/
scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
scp -q mtrverify_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/mtrverify_run.sh $DWELL $MTR"
