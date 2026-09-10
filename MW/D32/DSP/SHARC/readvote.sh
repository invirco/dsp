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
STRIPS="${STRIPS:-2}"
CCLK="${CCLK:-983}"
if [ "${BUILD:-0}" != "0" ]; then
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_CCLK_TARGET=$CCLK ./build.sh > /tmp/readvote_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/readvote_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; exit 1; fi
  md5sum build/chip1.ldr build/chip2.ldr
  scp -q build/chip1.ldr build/chip2.ldr $BENCH:$STAGE/
fi
scp -q ../../../../tools/pi/dsp4_readvote.py ../../../../tools/pi/dsp4_diag.py \
       ../../../../tools/pi/dsp4_config.py ../../../../tools/pi/dsp4_boot.py \
       ../../../../tools/pi/dsp4_bootlog.py $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q readvote_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/readvote_run.sh $*"
