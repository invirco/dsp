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
# 512, not 128. The GATE SIDECHAIN case added 2026-09-10 is driven by a
# PLAIN TONE through a Q 10 resonance, and a Q 10 pair at 500 Hz takes
# about 270 samples to ring up -- at 128 the case reports nothing and
# reads like a pass.
NSAMP="${NSAMP:-512}"
WORK="${WORK:-/tmp/bqguard}"
mkdir -p "$WORK"

# The vectors and the reference come out of ONE generator run, so the
# table the part holds and the results the host scores against cannot
# drift apart -- bqeverify.sh's rule.
python3 $ROOT/tools/dsp/gen_bqg_vectors.py --nsamp "$NSAMP" \
    --out src/lib/bqg_vectors.h --json "$WORK/bqg_vectors.json" || exit 4

D="$WORK/img"
# DSP4_BQ_FLOAT=0 IS NOT OPTIONAL HERE AND WAS MISSING (S17-1).
# shipping.config carries DSP4_BQ_FLOAT=1 and build.sh sources it wherever
# the environment is silent; dsp_block.h then does `#undef DSP4_BQ_GUARD /
# #define DSP4_BQ_GUARD 0` because the float cascade needs none of the
# guard machinery. So from the float landing (2026-09-03) onward this
# script asked for DSP4_BQ_GUARD=1 and got an image with the guard, the
# sizer and lib/bq_headroom.asm compiled out -- the guard's own bar,
# building the thing it is a bar for out of the image. The guard is the
# FIXED arm's, so the arm is named here.
DSP_BUILD_DIR="$D" DSP4_BISECT=0 DSP4_BQG_VERIFY=1 DSP4_BQ_FLOAT=0 \
  DSP4_BQ_ROUNDONCE=1 \
  DSP4_BQ_GUARD=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_STRIPS=2 \
  DSP4_BLOCK_KERNELS=1 ./build.sh > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' "$D.log" | head -20; exit 1; fi
echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
    "$WORK/bqg_vectors.json" \
    $ROOT/tools/pi/dsp4_bqg_verify.py $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q bqguard_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/bqguard_run.sh"
