#!/bin/bash
# fxverify.sh — the ANTI_FB notch design on the part.
#
# geqverify.sh's twin, on the family the 2026-09-08 inert-families pass
# left diagnosed but not fixed: eighteen parameter addresses that landed
# correctly and were read by nothing, an On switch read by nothing, and
# both coefficient banks at their compiled identity.
#
# THE SHIPPING FLOAT CONFIGURATION: plain ./build.sh, which is
# DSP4_BQ_FLOAT=1 / DSP4_GEQ_DESIGN=1 / DSP4_XOVER_DESIGN=1 /
# DSP4_FX_DESIGN=1 by default. The image moves with this work and is
# expected to; the md5 below is so every run in a session scores the
# same image and the write-up names it.
#
# Every address it writes is resolved BY CELL NAME out of the landed
# `defs/products/d24/dsp.csv`, staged as JSON by landed_map.py with the
# defs.lock pin and the CSV's sha256 inside it.
#
#   ./fxverify.sh                    the default aux node
#   NODE=C2_AUX_FX_07 PREFIX=Aux007 ./fxverify.sh
#   BUILD=0 ./fxverify.sh            reuse whatever is already staged
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
# WHERE THIS RUN'S IMAGES LIVE ON THE BENCH (S10-7). ~/dspboot holds the
# staged pairs the window rolls back to (blk_*, chip*, conf_*, ship_*,
# tx_*, cand_*), and this script used to scp its build straight over
# chip1.ldr and chip2.ldr, two of them. A measurement bar must not be
# able to destroy the artifact the product ships. Default stays
# /home/app/dspboot so nothing that calls this changes behaviour; set
# STAGE to run from anywhere else.
STAGE="${STAGE:-/home/app/dspboot}"
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-fxverify-$(date +%Y%m%d-%H%M).json}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports (dsp4_scope/dsp4_diag/dsp4_config/gainfix). Symlinked, not
# copied, so there is one working set and a staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi

# THE BLOCK-AWARE WITNESS IS PART OF THIS BAR (S12-8, 2026-09-09).
#
# This bar arms the scope on `_buf_<node>`, and under block kernels that is
# a one-word `.var` the kernel never writes -- the output block lives in a
# pool slot or a `_blk_<node>` array. Run without the tap on the staged
# shipping pair it reported the FX/AFB/GEQ/XOVER input as SILENT and
# refused a verdict; the same configuration rebuilt with the tap ran to a
# clean pass. S11-5 found this in famverify.sh and the fix was not carried
# here. `DSP4_SCOPE_BLK_TAP=0` is the control that reproduces the old
# reading.
export DSP4_SCOPE_BLK_TAP="${DSP4_SCOPE_BLK_TAP:-1}"

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/fxverify_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/fxverify_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/fxverify_build.log | head; exit 1; fi
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1)
  C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  echo "  image: chip1.ldr ${C1:0:8} chip2.ldr ${C2:0:8}  (shipping float configuration)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      $BENCH:$STAGE/ || exit 3
fi

python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3

# afb_ref imports geq_ref for the exponent polynomial: ONE literal for
# 2**x on [-1,1] in this repo, not two. Both go over.
scp -q $ROOT/tools/pi/dsp4_fx_verify.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_family_verify.py $ROOT/tools/pi/dsp4_block.py \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/afb_ref.py \
    $ROOT/tools/dsp/geq_ref.py \
    /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q fxverify_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT NODE='${NODE:-C2_FX_ENG_01}' \
            PREFIX='${PREFIX:-Fx001}' \
            UPSTREAM='${UPSTREAM:-_buf_C2_RECV_FX_01}' \
            INJECT='${INJECT:-_rx_ic_slot_C2_RECV_FX_01}' \
            N='${N:-1024}' OUT='$OUT' bash /home/app/fxverify_run.sh"
RC=$?
scp -q $BENCH:$STAGE/$OUT ./goldens/$OUT 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
