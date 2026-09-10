#!/bin/bash
# s24probe.sh — the S24 gate on the part: the main output strips' own
# Level and Mute (`Main{L,R,Sub}[1-1]Level/Mute`, open question Q1 until
# this session).
#
# THE BUILD IS THE SHIPPING CONFIGURATION PLUS THE BLOCK TAP, which is the
# same arm every audio bar in this directory takes: the tap is the
# block-aware witness (S10/S11-5) and without it a pooled node's
# `_buf_<node>` is a one-word `.var` nothing writes, so the capture reads
# whatever the pool last held. `DSP4_SCOPE_BLK_TAP=0` is the control that
# reproduces the pre-tap reading.
#
# It stages away from ~/dspboot by default for S10-7's reason: a
# measurement bar must not be able to overwrite the pair the window rolls
# back to. STAGE names a directory of this run's own.
#
#   ./s24probe.sh                 MainL (output 1)
#   GATES=2 ./s24probe.sh         MainR; GATES=4 -> MainSub
#   BUILD=0 ./s24probe.sh         reuse whatever is already staged
#   PRODUCT=d32 ./s24probe.sh     configure both chips as a D32
#
# THE BENCH MUST BE DRIVEN for gates B/D: the bar needs signal at the main
# output, so `./loadlogic.sh driveall` + `drive_audio.sh start` first, and
# `./loadlogic.sh shipping` after. The probe says INCONCLUSIVE rather than
# PASS when the limiter's block is silent -- a zero that proves nothing is
# the one way this gate could quietly come out right.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
STAGE="${STAGE:-/home/app/s24}"
GATES="${GATES:-1}"
PRODUCT="${PRODUCT:-d24}"
BUILD="${BUILD:-1}"
OUT=/tmp/s24probe; mkdir -p $OUT

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports (dsp4_scope/dsp4_diag/dsp4_config/gainfix). Symlinked, not
# copied, so there is one working set and a staged run cannot drift from it.
# THE FILES THIS RUN SUPPLIES ITSELF ARE NOT SYMLINKED, and the reason is
# that an scp onto a symlink writes THROUGH it: staging this session's
# dsp4_scope.py over a link into ~/dspboot would silently replace the
# bench's shared copy for every other script on the machine. They are
# SKIPPED by the link loop instead of linked and then unlinked -- deleting
# them afterwards is what broke `BUILD=0` on the first attempt, because the
# loop runs on every invocation and the delete took out the real files a
# previous `BUILD=1` had staged.
STAGED_PY="dsp4_block.py dsp4_scope.py dsp4_conform.py dsp4_s24_probe.py \
dsp4_checkchip.py dsp4_boot.py"
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      b=\$(basename \"\$f\"); \
      case \" $STAGED_PY \" in *\" \$b \"*) continue;; esac; \
      ln -sfn \"\$f\" '$STAGE'/\$b; done" || exit 3
fi

# THE PROBE ITSELF IS STAGED ON EVERY RUN, INSIDE OR OUTSIDE THE BUILD
# BLOCK. It sat inside it, so `BUILD=0` -- the mode whose whole point is to
# re-run the questions against an image already on the bench -- scored the
# PREVIOUS run's copy of the questions.
scp -q $ROOT/tools/pi/dsp4_s24_probe.py $BENCH:$STAGE/ || exit 3

if [ "$BUILD" = "1" ]; then
  DSP4_BISECT=0 DSP4_SCOPE_BLK_TAP=1 ./build.sh > $OUT/build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
  echo "  witness arm: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8) \
[$(basename "${SHIPPING_CONFIG:-shipping.config}") tap=1]"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      "${DSP_SRC_DIR:-$PWD/src}/dsp4_block.py" \
      $ROOT/tools/pi/dsp4_scope.py $ROOT/tools/pi/dsp4_conform.py \
      $ROOT/tools/pi/dsp4_s24_probe.py \
      $ROOT/tools/pi/dsp4_checkchip.py $ROOT/tools/pi/dsp4_boot.py \
      $BENCH:$STAGE/ || exit 3
fi
scp -q s24probe_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STAGE='$STAGE' PRODUCT='$PRODUCT' bash /home/app/s24probe_run.sh '$GATES'"
