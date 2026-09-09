#!/bin/bash
# capacity.sh — THE capacity instrument. One tool, one number, on the image
# that is actually on the part.
#
# WHY THIS EXISTS AND WHY IT IS NOT sigprofile2.sh/fxcost.sh.
#
# Until 2026-09-09 the capacity record was taken with the profile scripts,
# which build an INSTRUMENT and not the shipping image: DSP4_PROFILE_SIGNAL=1,
# DSP4_BLOCK_DECIMATE=32, and -- unrecorded until S11 -- DSP4_STRIP_FUSED=1
# and DSP4_SIMD_DYN=1, neither of which is in shipping.config and both of
# which default to 0 in build.sh. Read against the shipping pair the two
# instruments disagreed by 78,245 cycles/block on chip 2 at D24 and 108,331
# at D32 (S10-6), i.e. 24 % and 33 % of budget, and the record could not say
# which was the product.
#
# So capacity is measured HERE, with one method:
#
#   * the arm is a full build from shipping.config plus the named overrides,
#     and the overrides are printed AND land in the image's DIAG_BUILD_CFG;
#   * `tools/pi/dsp4_capacity.py` reads `_proc_cyc`, `_proc_cyc_max`,
#     `_proc_passes`, DIAG_BLK_OVERRUN, DIAG_FRAME_COUNT and the CGU words,
#     so the budget comes from the clock the part is running;
#   * a FRESH chipN.sym.json is staged with every arm (S10-9: a stale map
#     points `_proc_cyc` at whatever now lives at that address, and it
#     answers);
#   * the arm runs from its OWN staging path, never ~/dspboot (S10-7: the
#     profile scripts scp over the pair the window rolls back to).
#
# Usage:
#   ./capacity.sh                              shipping arm, D24 mask
#   ARM=d32 PRODUCT=d32 ./capacity.sh          shipping arm, all-ones
#   ARM=dec32 DSP4_BLOCK_DECIMATE=32 ./capacity.sh
#   ARM=b32 BLOCK=32 ./capacity.sh             a different block size
#   BUILD=0 ARM=... ./capacity.sh              re-boot what is already staged
#
# Every DSP4_* in the environment is passed to build.sh, so an arm is one
# command and the command is the arm's definition.
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219

ARM="${ARM:-ship}"
PRODUCT="${PRODUCT:-d24}"
DWELL="${DWELL:-45}"
REPS="${REPS:-2}"
BLOCK="${BLOCK:-}"                 # empty = the tree's own block (shipping.config)
# NOT ~/dspboot. See S10-7.
STAGE="${STAGE:-/home/app/dspcap/$ARM}"
WORK="${WORK:-/tmp/dspcap}"
D="$WORK/$ARM"
mkdir -p "$WORK"

# The overrides this arm carries, as build.sh will see them. Printed so the
# arm's definition is in the log beside its number, and so an arm that
# silently inherited an exported DSP4_* from the shell is visible.
OVR=""
for v in $(env | sed -n 's/^\(DSP4_[A-Z0-9_]*\)=.*/\1/p' | sort); do
    OVR="$OVR $v=${!v}"
done
echo "=== capacity arm '$ARM'  product=$PRODUCT  block=${BLOCK:-tree}  overrides:${OVR:- none}"

if [ "${BUILD:-1}" = "1" ]; then
    SRC="$PWD/src"
    if [ -n "$BLOCK" ]; then
        # A block size other than the tree's needs its own generated tree.
        # Same srckey discipline as fxcost.sh: the tree is keyed by the CSV,
        # the generator and the sources, so two arms cannot share a tree they
        # disagree about.
        K="$( { echo "block=$BLOCK"
                sha256sum "$PWD/dsp.csv" "$ROOT/tools/dsp/dsp_codegen.py"
                find "$PWD/src" -type f ! -name .srckey -print0 \
                    | LC_ALL=C sort -z | xargs -0 sha256sum
              } | sha256sum | cut -c1-16 )"
        T="$WORK/src$BLOCK-$K"
        if [ "$(cat "$T/.srckey" 2>/dev/null)" != "$K" ]; then
            rm -rf "$T"; cp -r "$PWD/src" "$T"; rm -f "$T/.srckey"
            DSP4_GEN_BLOCK=$BLOCK python3 $ROOT/tools/dsp/dsp_codegen.py \
                "$PWD/dsp.csv" "$T" --force > "$WORK/$ARM.gen.log" 2>&1 \
                || { echo "codegen FAILED — $WORK/$ARM.gen.log"; exit 5; }
            grep -q "define DSP4_BLOCK_SIZE   $BLOCK\$" "$T/dsp_block.h" || {
                echo "srctree: generated tree for block $BLOCK does not say so"; exit 5; }
            echo "$K" > "$T/.srckey"
        fi
        SRC="$T"
        export DSP4_GEN_BLOCK=$BLOCK
    fi
    DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
        echo "BUILD FAILED — $D.log"; grep -iE '\[Error|Build FAILED' "$D.log" | head; exit 1; fi
    echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
    # THE BOOT-STREAM SIZES, every arm, so a link that only just fitted is
    # on record beside the number it produced (the 2026-08-24 DM overflow).
    grep -E "\.ldr: [0-9]+ bytes" "$D.log" | sed 's/^/  /'
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"

    ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
        ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
    scp -q "$D/chip1.ldr" "$D/chip2.ldr" $BENCH:$STAGE/ || exit 3
    # sym.json is NOT symlinked -- it must be this build's (S10-9).
    scp -q "$D/chip1.sym.json" "$D/chip2.sym.json" $BENCH:$STAGE/ || exit 3
fi

python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3
scp -q $ROOT/tools/pi/dsp4_capacity.py $ROOT/tools/pi/dsp4_checkchip.py \
       $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_buildcfg.py \
       $ROOT/tools/pi/gainfix.py /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
scp -q capacity_run.sh $BENCH:/home/app/ || exit 3

for r in $(seq 1 "$REPS"); do
    echo "--- boot $r ---"
    ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT DWELL=$DWELL \
                OUT=cap-$ARM-$PRODUCT-r$r.json bash /home/app/capacity_run.sh" || exit 4
    scp -q $BENCH:$STAGE/cap-$ARM-$PRODUCT-r$r.json ./goldens/ 2>/dev/null
done
echo "  reports: goldens/cap-$ARM-$PRODUCT-r*.json"
