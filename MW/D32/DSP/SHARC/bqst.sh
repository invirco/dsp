#!/bin/bash
# bqst.sh — is the FUSED block cascade bit-exact against the per-sample
# reference cascade, ON THE PART?
#
# src/lib/bq_selftest.asm runs _bq_fx_cascade_N and _bq_fx_cascade_blk over
# byte-identical data inside the DSP and diffs them: two stages with
# DIFFERENT coefficients (so a stage-pointer fault cannot hide), over two
# consecutive blocks, impulse then silence (so block 2 is pure feedback
# tail and a block-boundary state fault cannot hide either).
#
# This is the bar for review finding D21 -- the packed inner loop is a
# rewrite of the arithmetic's PLUMBING, not of the arithmetic, and the
# reference cascade it is diffed against is the one the numeric spec names.
#
# Since 2026-08-29 it also diffs BOTH cascades against fixed_ref itself
# (tools/pi/dsp4_bq_verify.py). Two asm arms agreeing proves they agree;
# it does not prove either one is the ruled arithmetic, and the biquad had
# no asm-vs-model instrument until the halved-n1 encoding needed one.
#
#   ./bqst.sh            fused (the default question)
#   FUSED=0 ./bqst.sh    the unfused block cascade, same bar
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_BQ_SELFTEST=1 \
  DSP4_STRIP_FUSED=${FUSED:-1} DSP4_STRIPS=${STRIPS:-2} \
  DSP4_SKIP_PAIR=${SKIP_PAIR:-1} \
  ./build.sh > /tmp/bqst_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/bqst_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' /tmp/bqst_build.log | head; exit 1; fi
echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8)  (FUSED=${FUSED:-1})"
BLOCK=$(sed -n 's/.*DSP4_BLOCK_SIZE[ \t]*\([0-9][0-9]*\).*/\1/p' src/dsp_block.h | head -1)
python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_block.py \
    $ROOT/tools/pi/dsp4_bq_verify.py \
    $ROOT/tools/dsp/fixed_ref.py $BENCH:/home/app/dspboot/
scp -q bqst_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/bqst_run.sh $BLOCK"
