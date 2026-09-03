#!/bin/bash
# bqguard.sh — does the HEADROOM GUARD size what its model sizes, and does
# it stop the sign inversion, ON THE PART?
#
# The 2026-09-03 landing priced the guard from a rig and left it in as
# many words: "the guard is a RIG -- nothing computes H at parameter-load
# in the firmware, nothing carries it in the coefficient block, no node
# calls the guarded kernel". This is the bar for the wired thing.
#
# TWO CLAIMS, ONE IMAGE, AND BOTH CAN FAIL.
#
#   1. lib/bq_headroom.asm computes the H that tools/dsp/bq_h_load.py
#      computes, for the same quantised coefficients. The part runs the
#      engine for real -- request, main-loop service, poll -- and reports
#      the header word it wrote.
#   2. With that H the round-once cascade no longer inverts sign against
#      float, and with the header forced to zero -- which is the kernel
#      that landed -- it does, on exactly the cascades the model says.
#
# Both arms come out of ONE image because the header is DATA: writing
# zero to it is the whole of "turn the guard off for this cascade", so
# the two arms cannot differ in anything else.
#
# THE UNGUARDED ARM IS THE TWO-SIDED CONTROL. A bar that only asserted
# "guarded inverts nothing" would pass on a drive that never reached the
# ceiling -- which is exactly what the zeroed-bank ladder did, and the
# mistake bqeverify.sh was built to avoid.
#
#   ./bqguard.sh
#   NSAMP=256 ./bqguard.sh     a longer horizon for the slow cascades
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
NSAMP="${NSAMP:-128}"
WORK="${WORK:-/tmp/bqguard}"
mkdir -p "$WORK"

# The vectors and the reference come out of ONE generator run, so the
# table the part holds and the results the host scores against cannot
# drift apart -- bqeverify.sh's rule.
python3 $ROOT/tools/dsp/gen_bqg_vectors.py --nsamp "$NSAMP" \
    --out src/lib/bqg_vectors.h --json "$WORK/bqg_vectors.json" || exit 4

D="$WORK/img"
DSP_BUILD_DIR="$D" DSP4_BISECT=0 DSP4_BQG_VERIFY=1 DSP4_BQ_ROUNDONCE=1 \
  DSP4_BQ_GUARD=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_STRIPS=2 \
  DSP4_BLOCK_KERNELS=1 ./build.sh > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' "$D.log" | head -20; exit 1; fi
echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
    "$WORK/bqg_vectors.json" \
    $ROOT/tools/pi/dsp4_bqg_verify.py $BENCH:/home/app/dspboot/
scp -q bqguard_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/bqguard_run.sh"
