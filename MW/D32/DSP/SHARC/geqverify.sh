#!/bin/bash
# geqverify.sh — the GEQ band design on the part —
# FX_ENGINE), diagnosed mechanically on the part.
#
# THE SHIPPING FLOAT CONFIGURATION, like famverify.sh: plain ./build.sh,
# which is DSP4_BQ_FLOAT=1 / DSP4_GAIN_FLOAT=1 / DSP4_GEQ_DESIGN=1 by
# default. THE IMAGE MOVES with this work and is expected to -- what the
# md5 below is for is that every run of this bar in a session scores the
# same image, and that the number in the write-up names it.
#
# Every address it writes is resolved BY CELL NAME out of the landed
# `defs/products/d24/dsp.csv`, staged as JSON by landed_map.py with the
# defs.lock pin and the CSV's sha256 inside it.
#
#   ./geqverify.sh                       all four families + capacity
#   FAMILIES=GEQ ./geqverify.sh          one family
#   BUILD=0 ./geqverify.sh               reuse whatever is already staged
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-geqverify-$(date +%Y%m%d-%H%M).json}"

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/geqverify_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/geqverify_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/geqverify_build.log | head; exit 1; fi
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1)
  C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  echo "  image: chip1.ldr ${C1:0:8} chip2.ldr ${C2:0:8}  (shipping float configuration)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      $BENCH:/home/app/dspboot/ || exit 3
fi

python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3

scp -q $ROOT/tools/pi/dsp4_geq_verify.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_family_verify.py $ROOT/tools/pi/dsp4_block.py \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/geq_ref.py \
    /tmp/landed-$PRODUCT.json $BENCH:/home/app/dspboot/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:/home/app/dspboot/
scp -q geqverify_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "PRODUCT=$PRODUCT NODE='${NODE:-C2_AUX_GEQ_01}' \
            CELLFMT='${CELLFMT:-Aux001Geq%03d}' BANDS='${BANDS:-0}' \
            BAND='${BAND:-17}' N='${N:-1024}' \
            OUT='$OUT' bash /home/app/geqverify_run.sh"
RC=$?
scp -q "$BENCH:/home/app/dspboot/${OUT%.json}*.json" ./goldens/ 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
