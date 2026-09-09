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
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-famverify-$(date +%Y%m%d-%H%M).json}"

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
      $BENCH:/home/app/dspboot/ || exit 3
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
    $BENCH:/home/app/dspboot/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:/home/app/dspboot/
scp -q famverify_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "PRODUCT=$PRODUCT FAMILIES='${FAMILIES:-}' CHIPS='${CHIPS:-1,2}' \
            N='${N:-64}' OUT='$OUT' BQ_ARM='${BQ_ARM:-float}' \
            bash /home/app/famverify_run.sh"
RC=$?
scp -q $BENCH:/home/app/dspboot/$OUT ./goldens/$OUT 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
