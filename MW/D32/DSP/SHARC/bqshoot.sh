#!/bin/bash
# bqshoot.sh — the biquad/gain shootout ladder (2026-09-02).
#
# RIG A2 (float, round once) and RIG C (fixed-point, round once) timed
# against today's per-stage fixed kernels, in a STANDALONE rig: no graph
# integration, no contract edit, the shipping image untouched. Five timed
# loops in ordinary main-loop context became fourteen; the pattern is
# callcal.sh's and needs no witness and no signal.
#
# Rungs 1-4  cascade: today fixed scalar/SIMD, float scalar/SIMD
# Rungs 5-8  cascade: RIG C fixed round-once, rounded and truncating
# Rungs 9-13 GAIN: today, round-once, round-once with the D20 tap kept,
#            and the last two again without the meter
#
# The cycle number is half the answer. tools/dsp/bq_float_delta.py prices
# the float arm at 0.52 dB on an LF shelf; tools/dsp/roundonce_noise.py
# and tools/dsp/bq_state_bound.py price RIG C in headroom bits and in the
# recursive-state guard it needs. Read them together.
#
#   ./bqshoot.sh            # block 8, the repo tree
#   BLOCK=16 ./bqshoot.sh   # block 16, the working operating point
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
BLOCK="${BLOCK:-8}"
WORK="${WORK:-/tmp/bqshoot}"
source ./bench_lock.sh; bench_lock_acquire "$0"
mkdir -p "$WORK"

# BLOCK != 8 is built from a SCRATCH TREE generated with DSP4_GEN_BLOCK,
# keyed on its inputs so a stale tree cannot be built from -- sigprofile2's
# rule, and gainprof.sh's copy of it.
srckey() {
    {   echo "block=$1"
        sha256sum "$PWD/dsp.csv" "$ROOT/tools/dsp/dsp_codegen.py"
        find "$PWD/src" -type f ! -name .srckey -print0 \
            | LC_ALL=C sort -z | xargs -0 sha256sum
    } | sha256sum | cut -c1-16
}
srctree() {
    if [ "$1" = "8" ]; then echo "$PWD/src"; return; fi
    local k t
    k="$(srckey "$1")"
    t="$WORK/src$1-$k"
    if [ "$(cat "$t/.srckey" 2>/dev/null)" != "$k" ]; then
        rm -rf "$t"; cp -r "$PWD/src" "$t"; rm -f "$t/.srckey"
        DSP4_GEN_BLOCK=$1 python3 $ROOT/tools/dsp/dsp_codegen.py \
            "$PWD/dsp.csv" "$t" --force >/dev/null 2>&1
        if ! grep -q "define DSP4_BLOCK_SIZE   $1\$" "$t/dsp_block.h"; then
            echo "srctree: generated tree for block $1 does not say so" >&2
            exit 5
        fi
        echo "$k" > "$t/.srckey"
    fi
    echo "$t"
}
SRC="$(srctree "$BLOCK")"
D="$WORK/b$BLOCK"

DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
DSP4_BISECT=0 DSP4_BQ_SHOOTOUT=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 \
DSP4_STRIPS=2 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 "$D.log"; exit 1; fi
echo "  block $BLOCK  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_bq_shoot.py $BENCH:/home/app/dspboot/
scp -q bqshoot_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/bqshoot_run.sh"
