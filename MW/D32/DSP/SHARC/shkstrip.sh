#!/bin/bash
# shkstrip.sh — the SHARED kernels' per-strip witness (S18).
#
# The bar that famverify structurally cannot be: famverify drives
# `C1_COMP_01`, and a shared kernel entered with strip 1's record base every
# time is EXACTLY RIGHT for strip 1. So this writes a different compressor
# threshold to each of several strips over SPI and reads each strip's own
# converted word back out of its own record.
#
# Run on BOTH arms. The switch-off arm is the control: the same image
# without the shared kernels must produce the same words, because the
# arithmetic is the same arithmetic.
#
#   ./shkstrip.sh                       both arms
#   MASK=1 ./shkstrip.sh                one arm
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STAGE="${STAGE:-/home/app/dspcap/s18strip}"
WORK="${WORK:-/tmp/dspshk}"
# INSIDE THE PRODUCT. A strip the channel mask has off is never CALLED --
# process_chain jumps the whole gate group -- so its `_comp_cgp` keeps its
# `.var` initialiser of zero however correct the kernel is. The first run of
# this bar asked for strips 31 and 32 at D24 and reported the two zeros as a
# failure on BOTH arms, the switch-off control included, which is how it was
# caught. Override for a D32 boot.
STRIPS="${STRIPS:-1,2,7,16,23,24}"
mkdir -p "$WORK"

for MASK in ${MASK:-0 1}; do
    D="$WORK/m$MASK"
    echo "=== DSP4_SHARED_KERNELS=$MASK ==="
    DSP4_SHARED_KERNELS=$MASK DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
        echo "BUILD FAILED — $D.log"; exit 1; fi
    echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
    ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
        ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
    scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" $BENCH:$STAGE/ || exit 3
    python3 $ROOT/tools/dsp/landed_map.py --product d24 --json /tmp/landed-d24.json || exit 3
    scp -q $ROOT/tools/pi/dsp4_shk_perstrip.py $ROOT/tools/pi/dsp4_checkchip.py \
           $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/gainfix.py \
           /tmp/landed-d24.json $BENCH:$STAGE/ || exit 3
    scp -q shkstrip_run.sh $BENCH:/home/app/ || exit 3
    ssh $BENCH "STAGE='$STAGE' STRIPS='$STRIPS' bash /home/app/shkstrip_run.sh" \
        || { echo "PER-STRIP WITNESS FAILED at mask $MASK"; exit 4; }
done
