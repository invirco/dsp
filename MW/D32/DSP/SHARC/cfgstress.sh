#!/bin/bash
# cfgstress.sh — CONFIG_COMMIT wedge amplifier (see tools/pi/dsp4_cfgstress.py).
#
#   ./cfgstress.sh --boots 6 --commits 40 --raw          # CCLK raise ON  (983)
#   CCLK=0 ./cfgstress.sh --boots 6 --commits 40         # CCLK raise OUT
#
# CCLK=0 builds with DSP4_CCLK_TARGET=0, which is the ONE thing that removes
# _cgu_raise_cclk from the commit path; everything else about the two arms is
# identical. That is the bisect.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STRIPS="${STRIPS:-2}"
CCLK="${CCLK:-983}"
if [ "${BUILD:-1}" != "0" ]; then
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_COMMIT_STAGE=${COMMIT_STAGE:-2} \
    DSP4_CCLK_TARGET=$CCLK ./build.sh > /tmp/cfgstress_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/cfgstress_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/cfgstress_build.log | head; exit 1; fi
  md5sum build/chip1.ldr build/chip2.ldr
  scp -q build/chip1.ldr build/chip2.ldr $BENCH:/home/app/dspboot/
fi
scp -q ../../../../tools/pi/dsp4_cfgstress.py ../../../../tools/pi/dsp4_boot.py \
       ../../../../tools/pi/dsp4_config.py ../../../../tools/pi/dsp4_diag.py \
       $BENCH:/home/app/dspboot/
scp -q cfgstress_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/cfgstress_run.sh $*"
