#!/bin/bash
# fxcost.sh — FX_ENGINE's whole-graph cost at the OPERATING POINT.
#
# sigprofile2.sh builds and boots the whole chip-2 graph at a chosen
# block size; this drives the same tree, built the same way, and takes a
# PAIRED arm on each boot: the graph at the engines' landed Type, then
# with Type written over SPI to all six, then restored. The third read is
# the control -- a delta is only the algorithm's cost if the graph comes
# back to where it started.
#
# WHY IT EXISTS. Every capacity number on record was taken with
# FX_ENGINE at its landed default of Type 0 = Echo, which the dispatch
# did not implement, so the reverb had never run in a measurement. The
# 2026-09-08 pass measured Type 3 at block 8 and SCALED it; chip-2
# margin is the number the one-21564-per-chip decision rests on, and it
# is not settled by a scaling.
#
#   BLOCK=16 REPS=2 ./fxcost.sh          the operating point, two boots
#   BLOCK=8 ./fxcost.sh                  against the 09-08 block-8 pair
#   FXTYPE=2 BLOCK=16 ./fxcost.sh        cost another algorithm
set -u
DEC="${DEC:-32}"; DWELL="${DWELL:-6}"
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-1}"
SIMD="${DSP4_SIMD_DYN:-1}"
BQ="${DSP4_BQ_GRAPH:-1}"
C2BQ="${DSP4_C2_BQ_GRAPH:-1}"
XP="${DSP4_C2_XPAIR:-1}"
RO="${DSP4_BQ_ROUNDONCE:-1}"
GD="${DSP4_BQ_GUARD:-1}"
GDF="${DSP4_BQ_GUARD_FORCE:-0}"
FL="${DSP4_BQ_FLOAT:-1}"
FL32="${DSP4_BQ_FLOAT32:-0}"
GFL="${DSP4_GAIN_FLOAT:-$FL}"
# THE RUNTIME CHANNEL/AUX MASK (2026-09-09). Carried into the build AND
# into the build directory's name, for sigprofile2.sh's reason: the two
# arms must not share a directory, or the second boots the first's image.
CM="${DSP4_CHAN_MASK:-1}"
BLOCK="${BLOCK:-16}"
FXTYPE="${FXTYPE:-3}"
PRODUCT="${PRODUCT:-d24}"
WORK="${WORK:-/tmp/sigprof2}"     # SHARED with sigprofile2.sh on purpose:
                                  # the same srckey means the same tree,
                                  # so the arms are the same image.
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

# The block budget: 20480 cycles per sample-period-worth of block at
# 983.04 MHz / 48 kHz. Same arithmetic every capacity figure uses.
BUDGET=$((BLOCK * 20480))

CSV="${DSP_CSV:-$PWD/dsp.csv}"
CSVTAG="$(sha256sum "$CSV" | cut -c1-6)"
srckey() {
    {   echo "block=$1"
        sha256sum "$CSV" "$ROOT/tools/dsp/dsp_codegen.py"
        find "$PWD/src" -type f ! -name .srckey -print0 \
            | LC_ALL=C sort -z | xargs -0 sha256sum
    } | sha256sum | cut -c1-16
}
srctree() {
    if [ "$1" = "8" ] && [ "$CSV" = "$PWD/dsp.csv" ]; then
        echo "$PWD/src"; return; fi
    local k t
    k="$(srckey "$1")"
    t="$WORK/src$1-$k"
    if [ "$(cat "$t/.srckey" 2>/dev/null)" != "$k" ]; then
        rm -rf "$t"; cp -r "$PWD/src" "$t"; rm -f "$t/.srckey"
        DSP4_GEN_BLOCK=$1 python3 $ROOT/tools/dsp/dsp_codegen.py \
            "$CSV" "$t" --force >/dev/null 2>&1
        if ! grep -q "define DSP4_BLOCK_SIZE   $1\$" "$t/dsp_block.h"; then
            echo "srctree: generated tree for block $1 does not say so" >&2
            exit 5
        fi
        echo "$k" > "$t/.srckey"
    fi
    echo "$t"
}
SRC="$(srctree "$BLOCK")"

D="$WORK/b$BLOCK-c$CSVTAG-l0-q$C2BQ-x$XP-r$RO-g$GD-f$GDF-t$FL$FL32-m$CM"
DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG \
  DSP4_STRIP_FUSED=$FUS DSP4_SIMD_DYN=$SIMD DSP4_BQ_GRAPH=$BQ \
  DSP4_C2_BQ_GRAPH=$C2BQ DSP4_C2_XPAIR=$XP \
  DSP4_BQ_ROUNDONCE=$RO DSP4_BQ_GUARD=$GD DSP4_BQ_GUARD_FORCE=$GDF \
  DSP4_BQ_FLOAT=$FL DSP4_BQ_FLOAT32=$FL32 DSP4_GAIN_FLOAT=$GFL \
  DSP4_CHAN_MASK=$CM \
  DSP4_NODE_LIMIT=0 DSP4_NODE_LIMIT2=0 \
  DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "block=$BLOCK BUILD FAILED — $D.log"
  grep -iE '\[Error' "$D.log" | head; exit 1; fi
echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)  block=$BLOCK budget=$BUDGET"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3

scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
       /tmp/landed-$PRODUCT.json $BENCH:/home/app/dspboot/ || exit 3
scp -q $ROOT/tools/pi/dsp4_fx_cost.py $ROOT/tools/pi/dsp4_conform.py \
       $ROOT/tools/pi/dsp4_block.py $ROOT/tools/pi/gainfix.py \
       $BENCH:/home/app/dspboot/ || exit 3
scp -q fxcost_run.sh $BENCH:/home/app/ || exit 3

for r in $(seq 1 "${REPS:-2}"); do
  echo "--- boot $r ---"
  ssh $BENCH "PRODUCT=$PRODUCT FXTYPE=$FXTYPE BUDGET=$BUDGET DWELL=$DWELL \
              OUT=fxcost-b$BLOCK-t$FXTYPE-r$r.json bash /home/app/fxcost_run.sh"
  scp -q $BENCH:/home/app/dspboot/fxcost-b$BLOCK-t$FXTYPE-r$r.json \
         ./goldens/ 2>/dev/null
done
