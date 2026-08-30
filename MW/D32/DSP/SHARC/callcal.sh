#!/bin/bash
# callcal.sh — price a call/rts pair ON THE PART (review finding D66).
#
# Builds the DSP4_CALL_SELFTEST image, boots it and reads the ladder back.
# Nothing here touches node state or a parameter, so unlike the profiling
# instruments it needs no witness and no signal: it is eight timed loops
# in ordinary main-loop context.
#
#   ./callcal.sh
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..

DSP4_BISECT=0 DSP4_CALL_SELFTEST=1 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > /tmp/callcal_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/callcal_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 /tmp/callcal_build.log; exit 1; fi
echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_call_cal.py $BENCH:/home/app/dspboot/
scp -q callcal_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/callcal_run.sh"
