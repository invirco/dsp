#!/bin/bash
# s18regime.sh — chip 2's D24 cost across N boots, with the graph state that
# produced each one (S17-6).
#
# S17 recorded chip 2's D24 worst block at 92.88 % on one boot and 102.83 %
# on two others, same image, same product, same measured clock, with
# `_proc_passes` tracking the shortfall exactly and chip 1 flat to 0.3 %
# across the same boots — and could not say why. This runs the capacity
# ladder N times and takes a chip-2 branch-state snapshot on each boot at the
# same dwell, so the regime and its cause are one record.
#
#   ./s18regime.sh                       6 boots, D24, the tree's build
#   BOOTS=4 PRODUCT=d32 ./s18regime.sh
#   BUILD=0 ./s18regime.sh               re-boot what is already staged
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219

ARM="${ARM:-s18r}"
PRODUCT="${PRODUCT:-d24}"
BOOTS="${BOOTS:-6}"
DWELL="${DWELL:-45}"
# NOT ~/dspboot. See S10-7: the scratch slot is whatever the last run left.
STAGE="${STAGE:-/home/app/dspcap/$ARM}"
WORK="${WORK:-/tmp/dspcap}"
D="$WORK/$ARM"
mkdir -p "$WORK"

OVR=""
for v in $(env | sed -n 's/^\(DSP4_[A-Z0-9_]*\)=.*/\1/p' | sort); do
    OVR="$OVR $v=${!v}"
done
echo "=== regime arm '$ARM'  product=$PRODUCT  boots=$BOOTS  overrides:${OVR:- none}"

if [ "${BUILD:-1}" = "1" ]; then
    DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
        echo "BUILD FAILED — $D.log"; grep -iE '\[Error|Build FAILED' "$D.log" | head; exit 1; fi
    echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
    ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
        ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
    scp -q "$D/chip1.ldr" "$D/chip2.ldr" $BENCH:$STAGE/ || exit 3
    scp -q "$D/chip1.sym.json" "$D/chip2.sym.json" $BENCH:$STAGE/ || exit 3
fi

python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3
scp -q $ROOT/tools/pi/dsp4_capacity.py $ROOT/tools/pi/dsp4_checkchip.py \
       $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_buildcfg.py \
       $ROOT/tools/pi/dsp4_c2regime.py \
       $ROOT/tools/pi/gainfix.py /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
scp -q s18regime_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT BOOTS=$BOOTS DWELL=$DWELL \
            PREFIX=$ARM-$PRODUCT bash /home/app/s18regime_run.sh" || exit 4
mkdir -p goldens
scp -q "$BENCH:$STAGE/$ARM-$PRODUCT-*.json" ./goldens/ 2>/dev/null
echo "  reports: goldens/$ARM-$PRODUCT-{cap,regime}-b*.json"
