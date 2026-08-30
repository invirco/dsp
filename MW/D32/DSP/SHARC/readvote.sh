#!/bin/bash
# readvote.sh — how often does a HEALTHY part answer a diag read with 0?
#
#   ./readvote.sh --reads 300
#
# See tools/pi/dsp4_readvote.py. Boots and configures first, then hammers
# registers whose correct value cannot be 0 and scores three host-side read
# policies over the same samples. BUILD=0 reuses whatever is on the card.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STRIPS="${STRIPS:-2}"
CCLK="${CCLK:-983}"
if [ "${BUILD:-0}" != "0" ]; then
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_CCLK_TARGET=$CCLK ./build.sh > /tmp/readvote_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/readvote_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; exit 1; fi
  md5sum build/chip1.ldr build/chip2.ldr
  scp -q build/chip1.ldr build/chip2.ldr $BENCH:/home/app/dspboot/
fi
scp -q ../../../../tools/pi/dsp4_readvote.py ../../../../tools/pi/dsp4_diag.py \
       ../../../../tools/pi/dsp4_config.py ../../../../tools/pi/dsp4_boot.py \
       ../../../../tools/pi/dsp4_bootlog.py $BENCH:/home/app/dspboot/
scp -q readvote_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/readvote_run.sh $*"
