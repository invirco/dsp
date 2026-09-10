#!/bin/bash
# d80.sh — IS D80 ARITHMETIC, OR A POINT ON A CONVERGENCE CURVE?
#
# D80: chip 2's per-sample and block-kernel builds differ by 0.44-0.90 % on
# the meters of the chains whose GATE and COMP are ENGAGED, peak low and RMS
# high, while every node OUTPUT is bit-identical. Reproduced through every
# lever since 2026-08-28 and never root-caused.
#
# THE HYPOTHESIS THIS TESTS, and it is already half-written in c2gold_run.sh:
# a meter is a per-BLOCK IIR. Its RMS window is 300 ms and its peak decay
# 1.333 s AT BLOCK RATE, and c2gold runs both arms at DSP4_BLOCK_DECIMATE=32
# because neither fits a block period -- so in WALL CLOCK those constants are
# ~9.6 s and ~43 s. A 12 s dwell reads a curve. The two arms are built to run
# at DIFFERENT SPEEDS -- that is the whole point of the comparison -- so they
# read that curve at different points, and the difference is a function of
# HOW MANY GRAPH PASSES have folded, not of what one pass computes. The node
# outputs are unaffected because a block is recomputed from scratch every
# pass, which is exactly the asymmetry D80 records.
#
# HOW IT IS TESTED, and why this is not another dwell argument. Each arm is
# booted ONCE and its meters read at a LADDER of elapsed times, with
# DIAG_FRAME_COUNT and DIAG_BLK_OVERRUN bracketing every read. That gives two
# things nothing before had:
#
#   1. the TRAJECTORY -- if a meter is still moving between the last two
#      captures, a single-dwell comparison of it was never a value;
#   2. the two arms on a COMMON X AXIS -- graph passes, not seconds. If the
#      two arms' meters lie on the same curve against passes, D80 is that
#      curve and nothing else; if they separate at equal passes, it is
#      arithmetic and the separation is the quantity to chase.
#
# The stimulus is c2gold's: DSP4_PROFILE_SIGNAL puts the same +/-0.5 square
# into both arms' INTERCHIP_RECV kernels, so neither depends on the
# inter-chip fabric and both see an identical, deterministic input.
#
#   ./d80.sh
#   TIMES=12,30,60,120,240,480 ./d80.sh
set -u
TIMES="${TIMES:-12,30,60,120,240,480}"
BLOCK="${BLOCK:-$(python3 "$(dirname "$0")/../../../../tools/dsp/build_config.py" DSP4_GEN_BLOCK)}"
# The same decimation c2gold uses, and for the same reason: neither arm fits
# a block period. Changing it changes the wall-clock stretch of every meter
# constant, which is the effect under test, so it is a knob and it is named.
DEC="${DEC:-32}"
WORK="${WORK:-/tmp/d80}"
cd "$(dirname "$0")"
ROOT=../../../..
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
mkdir -p "$WORK"

SRC="$PWD/src"
if [ "$BLOCK" != "8" ]; then
  SRC="$WORK/src$BLOCK"
  rm -rf "$SRC"; cp -r "$PWD/src" "$SRC"
  DSP4_GEN_BLOCK=$BLOCK python3 $ROOT/tools/dsp/dsp_codegen.py \
      "$PWD/dsp.csv" "$SRC" --force >/dev/null 2>&1
  grep -q "define DSP4_BLOCK_SIZE   $BLOCK\$" "$SRC/dsp_block.h" || {
      echo "d80: generated tree for block $BLOCK does not say so" >&2; exit 5; }
fi

run_arm() {   # $1 = kernels (0|1) -> writes $WORK/d80arm$1.json
  local K="$1"
  local D="$WORK/k$K-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=$K DSP4_PROFILE_SIGNAL=1 \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM $K BUILD FAILED (see $D.log)" >&2; return 1; fi
  echo "  arm$K image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:$STAGE/
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q d80_run.sh $BENCH:/home/app/
  ssh $BENCH "STAGE='$STAGE' bash /home/app/d80_run.sh '$TIMES' $STAGE/d80arm$K.json" \
    2>&1 | sed "s/^/  arm$K: /"
}

echo "=== D80: meters against graph passes, BLOCK=$BLOCK DEC=$DEC times=$TIMES ==="
run_arm 0 || exit 1
run_arm 1 || exit 1
scp -q $BENCH:$STAGE/d80arm0.json $BENCH:$STAGE/d80arm1.json "$WORK/"
python3 "$ROOT/tools/pi/dsp4_d80.py" "$WORK/d80arm0.json" "$WORK/d80arm1.json" \
        --dec "$DEC" --block "$BLOCK"
