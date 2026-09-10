#!/bin/bash
# bootchar.sh — characterise the boot+config handshake, one attempt per cycle.
#
#   ./bootchar.sh --cycles 30 --tag base
#   BUILD=0 ./bootchar.sh --cycles 16 --post-reset-delay 0.9 --tag pr900
#
# BUILD=1 (default) rebuilds and stages the characterisation image before
# running; BUILD=0 reuses whatever is already on the card, which is what the
# bisect arms want so that every arm is measured on ONE image.
#
# The image is deliberately small and self-test-free (DSP4_STRIPS=$STRIPS,
# block kernels on): it reaches BOOT_STAGE 7 when the handshake works, so a
# cycle that does not is the handshake and nothing else. The shipping
# 32-strip image cannot be used for this — it is 16x over the per-block
# budget and parks at BOOT_STAGE 5 by design, which is one of the two
# failure codes under investigation.
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
# The instrument's own switches are NAMED here rather than inherited from
# whatever happened to be exported, and echoed before the build, because a
# run whose flags silently did not reach the assembler is the 2026-08-23
# trap this tree has already paid for once. Two arms of this session's
# bisect were measured on an image that did not carry the flag they were
# testing, and the only reason it was caught is that the diagnostic
# registers read 0.
CFG_WATCH="${DSP4_CFG_WATCH:-0}"
# Tracks build.sh's default, which session 15 moved to 1 once D74 was
# root-caused off this flag. A 0 here would have quietly measured the
# UNFIXED path against a tree that ships the fix.
PARTIAL_FIX2="${DSP4_SPI_PARTIAL_FIX2:-1}"
echo "bootchar: STRIPS=$STRIPS CCLK=$CCLK DSP4_CFG_WATCH=$CFG_WATCH DSP4_SPI_PARTIAL_FIX2=$PARTIAL_FIX2 BUILD=${BUILD:-1}"
if [ "${BUILD:-1}" != "0" ]; then
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_CFG_WATCH=$CFG_WATCH DSP4_SPI_PARTIAL_FIX2=$PARTIAL_FIX2 \
    DSP4_CCLK_TARGET=$CCLK ./build.sh > /tmp/bootchar_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/bootchar_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/bootchar_build.log | head; exit 1; fi
  md5sum build/chip1.ldr build/chip2.ldr
  scp -q build/chip1.ldr build/chip2.ldr $BENCH:$STAGE/
fi
scp -q ../../../../tools/pi/dsp4_bootchar.py ../../../../tools/pi/dsp4_boot.py \
       ../../../../tools/pi/dsp4_config.py ../../../../tools/pi/dsp4_diag.py \
       $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q bootchar_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/bootchar_run.sh $*"
