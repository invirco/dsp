#!/bin/bash
# famverify.sh — every D24 kernel family on the part, addressed through the
# LANDED contract (`defs/products/d24/dsp.csv`).
#
# THE SHIPPING FLOAT CONFIGURATION, like goldnode.sh and conform.sh: plain
# ./build.sh, which is DSP4_BQ_FLOAT=1 / DSP4_GAIN_FLOAT=1 by default. That
# makes the build its own W0 check — this bar changes no source that
# reaches an image, so the md5 printed below must equal the baseline the
# session started from.
#
# The contract is staged as JSON because the bench has no `defs` checkout.
# tools/dsp/landed_map.py writes it, carrying the defs.lock pin and the
# sha256 of the CSV, so a bench run cannot quietly score against a
# different contract than the one this tree is on.
#
#   ./famverify.sh                        every family, both chips
#   FAMILIES=GATE,COMP ./famverify.sh     just those
#   CHIPS=1 ./famverify.sh                chip 1 only
#   BUILD=0 ./famverify.sh                reuse whatever is already staged
#   N=32 ./famverify.sh                   shorter captures
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
# WHERE THIS RUN'S IMAGES LIVE ON THE BENCH.
#
# ~/dspboot holds the staged pairs the window rolls back to -- blk_* (the
# shipping pair), chip* (the window pair), conf_*, ship_*, tx_* -- and this
# script used to scp its build straight over chip1.ldr and chip2.ldr, which
# are two of them. A measurement bar must not be able to destroy the
# artifact the product ships. Default stays /home/app/dspboot so nothing
# that calls this changes behaviour; set STAGE to run from anywhere else.
STAGE="${STAGE:-/home/app/dspboot}"
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-famverify-$(date +%Y%m%d-%H%M).json}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports (dsp4_scope/dsp4_diag/dsp4_config/gainfix). Symlinked, not
# copied, so there is one working set and a staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/famverify_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/famverify_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/famverify_build.log | head; exit 1; fi
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1)
  C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  echo "  image: chip1.ldr ${C1:0:8} chip2.ldr ${C2:0:8}  (shipping float configuration)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      $BENCH:$STAGE/ || exit 3
fi

# THE CONTRACT ITSELF, staged. Not a copy of the addresses — the file.
python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3

# THE BLOCK FILE COMES FROM THE TREE THAT WAS BUILT, not from tools/pi
# (review D49, and conform.sh/busgold.sh already do this). With the block
# size a build parameter, staging the repo copy labels a bench run with a
# block size the image on the part may not have.
BLOCKPY="${DSP_SRC_DIR:-$PWD/src}/dsp4_block.py"
[ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"
scp -q $ROOT/tools/pi/dsp4_family_verify.py $ROOT/tools/pi/dsp4_node_verify.py \
    $ROOT/tools/pi/dsp4_conform.py "$BLOCKPY" \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/boundary_vectors.py \
    /tmp/landed-$PRODUCT.json \
    $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q famverify_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT FAMILIES='${FAMILIES:-}' CHIPS='${CHIPS:-1,2}' \
            N='${N:-64}' OUT='$OUT' BQ_ARM='${BQ_ARM:-float}' \
            bash /home/app/famverify_run.sh"
RC=$?
scp -q $BENCH:$STAGE/$OUT ./goldens/$OUT 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
