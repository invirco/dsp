#!/bin/bash
# txorder.sh — the TRANSMIT-STAMP ORDER arm, host half.
#
# Builds a DSP4_TXPROBE=1 image (chip 2 stamps block/half/sample into TX
# lane 3 slot 1 beside the audio in slot 0, so the capture decides the
# order by construction — src/tx_probe.asm), stages it, and runs the
# bench's s9wire_run.sh: full D24 graph, both chips configured, the Pi
# playback staircase running, 192,000 frames scored.
#
# The arms this exists to compare:
#   TX=0  the shipping order -- 81.2499 % exact with the Pi input (S9-2)
#   TX=1  DSP4_TX_EARLY: the core fills the half the DDE is NOT clocking
#
#   TX=1 ./txorder.sh          the switch on
#   TX=0 ./txorder.sh          the control
#   LITE=1 TX=0 ./txorder.sh   load cut (s9wire_lite.sh), the 100 % reference
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
TX="${TX:-0}"
ARM="${ARM:-txe$TX}"
DIR="${DIR:-cap_$ARM}"
D="${WORK:-/tmp/dspcap}/$ARM"

if [ "${BUILD:-1}" = "1" ]; then
  DSP_BUILD_DIR="$D" DSP4_TXPROBE=1 DSP4_TX_EARLY=$TX ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "BUILD FAILED — $D.log"; grep -iE '\[Error|Build FAILED' "$D.log" | head; exit 1; fi
  echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)  TXPROBE=1 TX_EARLY=$TX"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  # Never ~/dspboot (S10-7).
  ssh $BENCH "mkdir -p '/home/app/$DIR' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '/home/app/$DIR'/\$(basename \"\$f\"); done" || exit 3
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
      $BENCH:/home/app/$DIR/ || exit 3
  scp -q $ROOT/tools/pi/dsp4_tx_order.py $ROOT/tools/pi/dsp4_checkchip.py \
      $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_buildcfg.py \
      $ROOT/tools/pi/gainfix.py $BENCH:/home/app/$DIR/ || exit 3
  # THE BLOCK FILE FROM THE TREE THAT WAS BUILT: dsp4_tx_order decodes a
  # sample field whose width follows BLOCK.
  BLOCKPY="${DSP_SRC_DIR:-$PWD/src}/dsp4_block.py"
  [ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"
  scp -q "$BLOCKPY" $BENCH:/home/app/$DIR/dsp4_block.py || exit 3
fi

RUNNER=s9wire_run.sh
[ "${LITE:-0}" = "1" ] && RUNNER=s9wire_lite.sh
ssh $BENCH "DUMP='${DUMP:-8}' bash /home/app/$RUNNER '$DIR'"
