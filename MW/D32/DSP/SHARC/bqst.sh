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
    $ROOT/tools/dsp/fixed_ref.py $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q bqst_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/bqst_run.sh $BLOCK"
