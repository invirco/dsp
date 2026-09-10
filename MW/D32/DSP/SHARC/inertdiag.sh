#!/bin/bash
# inertdiag.sh — the four INERT families (ANTI_FB, GEQ, CROSSOVER,
# FX_ENGINE), diagnosed mechanically on the part.
#
# THE SHIPPING FLOAT CONFIGURATION, like famverify.sh: plain ./build.sh,
# which is DSP4_BQ_FLOAT=1 / DSP4_GAIN_FLOAT=1 by default. This bar changes
# no source that reaches an image, so the md5 printed below must equal the
# baseline the session started from -- that is the W0 check.
#
# Every address it writes is resolved BY CELL NAME out of the landed
# `defs/products/d24/dsp.csv`, staged as JSON by landed_map.py with the
# defs.lock pin and the CSV's sha256 inside it.
#
#   ./inertdiag.sh                       all four families + capacity
#   FAMILIES=GEQ ./inertdiag.sh          one family
#   BUILD=0 ./inertdiag.sh               reuse whatever is already staged
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
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-inertdiag-$(date +%Y%m%d-%H%M).json}"

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/inertdiag_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/inertdiag_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/inertdiag_build.log | head; exit 1; fi
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

scp -q $ROOT/tools/pi/dsp4_inert_diag.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_block.py $ROOT/tools/dsp/fixed_ref.py \
    /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q inertdiag_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT FAMILIES='${FAMILIES:-}' N='${N:-32}' \
            OUT='$OUT' bash /home/app/inertdiag_run.sh"
RC=$?
scp -q $BENCH:$STAGE/$OUT ./goldens/$OUT 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
