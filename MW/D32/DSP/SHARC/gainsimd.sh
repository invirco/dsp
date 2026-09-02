#!/bin/bash
# gainsimd.sh — is the SIMD GAIN kernel bit-exact where busgold cannot look?
#
# THIS BAR EXISTS BECAUSE THE ONE ALREADY IN THE TREE IS BLIND HERE, and
# that was found by reading the kernel's register lifetimes rather than by
# a measurement. busgold drives a +/-0.5 square wave through a strip whose
# GAIN is pinned at UNITY by gainfix. At unity gain every product's low 28
# bits are zero, so `(x*g + 2^27) >> 28` and `(x*g) >> 28` give the same
# answer on every sample -- a kernel that dropped the rounding half
# entirely would reproduce the golden word for word. Nor can that stimulus
# saturate: |x| = 0.5 and the largest Q4.28 gain is under 8, so the product
# never leaves range and the saturation fix-up is never taken. The first
# cut of the SIMD kernel left PEy's rounding constant and saturation mask
# unwritten -- they are loaded with PEYEN still down, which writes PEx's
# copy only -- and busgold returned 0 of 256 with that wrong.
#
# So this bar sets a NON-ROUND GAIN (default 0.7071067811865476, i.e.
# -3.0103 dB, whose Q4.28 word is 0x0B504F33) before capturing. Every
# product then has 28 bits under the round, half of them on average land
# above the half, and a missing or mis-scaled rounding term moves the
# capture.
#
# THE COMPARISON IS ARM AGAINST ARM, NOT AGAINST A STORED GOLDEN, because
# the stimulus is deliberately not the one the goldens were taken with.
# Same tree, same stimulus, same configuration, ONE build flag different:
#
#   simd    DSP4_GAIN_SIMD=1                       the kernel under test
#   scalar  DSP4_GAIN_SIMD=0                       the reference -- and it
#           is the SAME BYTES as the pre-change tree, which is checked
#           separately by rebuilding the previous commit
#   neg     DSP4_GAIN_SIMD=1 + NEGCTL=1            PEy's gain word zeroed
#
# THE NEGATIVE ARM IS WHAT MAKES THE OTHER TWO WORTH READING. A "SIMD"
# kernel that never set PEYEN would run one unit over all sixteen samples
# and agree with the scalar arm perfectly -- indistinguishable from
# success from outside, which is the silent-fallback trap c2dyngold was
# caught by. Zeroing the odd unit's gain must silence every odd sample; if
# the capture does not move, PEYEN was never up.
#
#   ./gainsimd.sh                 all three arms
#   GVAL=0.5 ./gainsimd.sh        another gain (0.5 is EXACT -- expect the
#                                 rounding path to go blind again)
#   ARMS="simd scalar" ./gainsimd.sh
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STRIP="${STRIP:-1}"; N="${N:-256}"; STRIPS="${STRIPS:-2}"
GVAL="${GVAL:-0.7071067811865476}"
ARMS="${ARMS:-simd scalar neg}"
OUT=/tmp/gainsimd; mkdir -p $OUT

run_one() {   # tag  GAIN_SIMD  NEGCTL
  local tag=$1 gs=$2 ng=$3
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
    DSP4_SIMD_DYN=${SIMD:-0} DSP4_STRIP_FUSED=${FUSED:-0} \
    DSP4_GAIN_SIMD=$gs DSP4_GAIN_SIMD_NEGCTL=$ng \
    ./build.sh > $OUT/build_$tag.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build_$tag.log)" -ne 0 ]; then
    echo "  $tag: BUILD FAILED"; grep -iE '\[Error' $OUT/build_$tag.log | head
    return 1; fi
  echo "  $tag: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)  gain=$GVAL"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      $ROOT/tools/pi/dsp4_block.py $ROOT/tools/pi/dsp4_pairgraph.py \
      $ROOT/tools/pi/gainfix.py $BENCH:/home/app/dspboot/ || return 1
  scp -q gainsimd_run.sh $BENCH:/home/app/ || return 1
  ssh $BENCH "bash /home/app/gainsimd_run.sh $STRIP $N $tag '' $GVAL" || return 1
  scp -q $BENCH:/home/app/dspboot/pairgraph_$tag.json $OUT/ || return 1
}

for spec in "simd 1 0" "scalar 0 0" "neg 1 1"; do
  # shellcheck disable=SC2086
  set -- $spec
  case " $ARMS " in *" $1 "*) ;; *) continue ;; esac
  echo "--- $1 ---"
  run_one "$1" "$2" "$3" || exit 1
done

echo "=== verdict ==="
echo "-- simd vs scalar: MUST be bit-exact"
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/pairgraph_scalar.json $OUT/pairgraph_simd.json
echo "-- simd vs neg: MUST differ (PEy proven live)"
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare \
    $OUT/pairgraph_simd.json $OUT/pairgraph_neg.json
