#!/bin/bash
# mtxgold.sh — the matrix bus vector (S23 gate 1): the matrix buses carry
# the SAME SUM as a proven one, word for word.
#
# THE ARGUMENT, AND WHY IT NEEDS NO STORED GOLDEN. The dense crosspoint
# path is ONE path (the 08-25 crosspoint mandate, D22's bus-major fabric):
# a channel's post-fader block is parked once, each bus's row of `_xpc`
# holds one Q4.28 coefficient per strip, and one shared pass accumulates
# every bus in exact 80-bit arithmetic and reads it out with a single
# rns+saturate. So a strip sent at UNITY into aux 1, matrix 1 and matrix 2
# is the same source, times a coefficient of exactly 2^28, into three
# accumulators that differ only in which row of the matrix they are --
# and the three bus sums must be IDENTICAL. Not close: identical.
#
# That makes this a bar with no baseline to go stale, and it can fail three
# real ways that a stored golden could not distinguish: a matrix bus row
# indexed wrong in `_xpc`, a send-coefficient stride slipped by one, or one
# accumulator overlapping another's triple in `bus_accumulators.asm`.
#
# THE NEGATIVE CONTROL is the same capture with `Chan001MatrixOn001` at 0
# and the send level left alone: the assign bit is folded INTO the
# coefficient at control rate, so the bus must read EXACTLY zero. A bus
# that still carries the strip is a coefficient the assign bit did not
# reach -- which is S22-4's failure mode (a matrix write landing in the
# SPI handler's catch-all and never reaching the router's control gate).
#
# ONE BOOT for all four captures; see mtxgold_run.sh.
#
#   ./mtxgold.sh                  build, stage, capture, compare
#   BUILD=0 ./mtxgold.sh          reuse whatever is already staged
#   STRIP=2 ./mtxgold.sh          the odd/even other half of the pair
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
STAGE="${STAGE:-/home/app/mtxgold}"
STRIP="${STRIP:-1}"; N="${N:-256}"; STRIPS="${STRIPS:-2}"
BUILD="${BUILD:-1}"
# SIMD / FUSED DEFAULT FROM THE CONFIGURATION BEING BUILT, not from 0
# (S20-4): a bar cannot witness the configuration whose defining switches
# it overrides.
_cfg() { python3 "$ROOT/tools/dsp/build_config.py" "$1"; }
SIMD="${SIMD:-$(_cfg DSP4_SIMD_DYN)}";  SIMD="${SIMD:-0}"
FUSED="${FUSED:-$(_cfg DSP4_STRIP_FUSED)}"; FUSED="${FUSED:-0}"
OUT=/tmp/mtxgold; mkdir -p $OUT
BLOCKPY="${DSP_SRC_DIR:-$ROOT/MW/D32/DSP/SHARC/src}/dsp4_block.py"
[ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"

# The files this run supplies itself are SKIPPED by the link loop, not
# linked and then unlinked: an scp onto a symlink writes THROUGH it, and
# staging this session's dsp4_pairgraph.py over a link into ~/dspboot would
# replace the bench's shared copy for every other script on the machine.
STAGED_PY="dsp4_block.py dsp4_pairgraph.py dsp4_checkchip.py dsp4_boot.py"
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      b=\$(basename \"\$f\"); \
      case \" $STAGED_PY \" in *\" \$b \"*) continue;; esac; \
      ln -sfn \"\$f\" '$STAGE'/\$b; done" || exit 3
fi

if [ "$BUILD" = "1" ]; then
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_SIMD_DYN=$SIMD DSP4_STRIP_FUSED=$FUSED \
    ./build.sh > $OUT/build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
  echo "  chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8) \
[$(basename "${SHIPPING_CONFIG:-shipping.config}") SIMD=$SIMD FUSED=$FUSED]"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      "$BLOCKPY" $ROOT/tools/pi/dsp4_pairgraph.py \
      $ROOT/tools/pi/dsp4_checkchip.py $ROOT/tools/pi/dsp4_boot.py \
      $BENCH:$STAGE/ || exit 3
else
  scp -q $ROOT/tools/pi/dsp4_pairgraph.py $BENCH:$STAGE/ || exit 3
fi

scp -q mtxgold_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STAGE='$STAGE' bash /home/app/mtxgold_run.sh $STRIP $N" || exit 4
for a in aux1 mtx1 mtx2 aux1b mtx1off; do
  scp -q $BENCH:$STAGE/mtxgold_$a.json $OUT/ 2>/dev/null
done

echo "=== THE VECTOR: matrix 2 must equal matrix 1, word for word ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/mtxgold_mtx1.json $OUT/mtxgold_mtx2.json
echo "=== THE CONTROL: aux 1 against ITSELF, same boot, first and last ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/mtxgold_aux1.json $OUT/mtxgold_aux1b.json
echo "=== and matrix 1 against aux 1, to be read against that control ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/mtxgold_aux1.json $OUT/mtxgold_mtx1.json
echo "=== negative control: matrix 1 with the assign bit off ==="
python3 - "$OUT/mtxgold_mtx1off.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
nz = sum(1 for w in d['words'] if w)
print('  %s: %d of %d words non-zero, sha256 %s'
      % (d['tag'], nz, len(d['words']), d['sha256'][:16]))
print('  NEGATIVE CONTROL %s' % ('PASSES (exactly zero)' if not nz
                                 else 'FAILED'))
sys.exit(0 if not nz else 1)
EOF
