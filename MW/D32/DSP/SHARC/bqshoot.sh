#!/bin/bash
# bqshoot.sh — RIG A2 of the biquad shootout spike (2026-09-02).
#
# Times today's FIXED cascade against a FLOAT DF-II-T one, scalar and
# SIMD, in a STANDALONE rig: no graph integration, no contract edit, the
# shipping image untouched. Five timed loops in ordinary main-loop
# context, so it needs no witness and no signal -- callcal.sh's pattern.
#
# The cycle number is half the answer. tools/dsp/bq_float_delta.py prices
# the float arm's NUMERIC cost at 0.52 dB on an LF shelf at +15 dB Q3.16,
# eleven times the bar golden_harness holds the contract to. Read both.
#
#   ./bqshoot.sh
#   ./bqshoot.sh
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..

DSP4_BISECT=0 DSP4_BQ_SHOOTOUT=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_STRIPS=2 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > /tmp/bqshoot_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/bqshoot_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 /tmp/bqshoot_build.log; exit 1; fi
echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_bq_shoot.py $BENCH:/home/app/dspboot/
scp -q bqshoot_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/bqshoot_run.sh"
