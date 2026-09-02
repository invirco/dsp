#!/bin/bash
# sigprofile2.sh — per-CLASS cycle profile for CHIP 2 (review finding D16).
#
# sigprofile.sh's twin. Same instrument (TCOUNT/_proc_cyc, DSP4_NODE_LIMIT
# prefix cut, DEC decimation so the pass always completes, witnessed before
# the number is accepted), pointed at the OTHER part.
#
# TWO THINGS ARE DIFFERENT AND BOTH MATTER.
#
# 1. THE CUT IS DSP4_NODE_LIMIT2, NOT DSP4_NODE_LIMIT. Chip 2's whole input
#    is chip 1's mix fabric, so cutting chip 1's chain to N would leave chip 2
#    measuring its classes on SILENCE -- and silence measures GATE, COMP and
#    LIMITER on their cheap branch. Chip 1 runs WHOLE here (DSP4_NODE_LIMIT=0,
#    32 strips, stimulus on) and only chip 2's chain is cut.
#
# 2. THE WITNESS IS TWO-SIDED. Chip 1's is sigprofile.sh's own -- strip 1's
#    GAIN coefficient must read 1.0f, because roughly one boot in three lands
#    the CFG_COMMIT header word there and the whole graph then reports the
#    silence cost with everything else reading clean. Chip 2 adds its own:
#    it is NEVER CONFIGURED (BOOT_STAGE 5 is its pass mark), so what has to be
#    witnessed is that the FABRIC IS CARRYING SOMETHING -- at least one
#    inter-chip RX slot non-zero. The run prints which slots were live, so the
#    record says what chip 2 was actually carrying rather than assuming.
#
# THE CHIP-2 GRAPH RUNS ON ITS .var INITIALISERS. Nothing configures chip 2,
# so the biquad cascades are at bypass coefficients (cost is coefficient-
# independent: same instructions either way) and the dynamics are at their
# compiled defaults. That is stated rather than hidden; it is the same class
# of caveat as the chip-1 record's signal/silence split.
#
#   ./sigprofile2.sh 47 48 49 50 51 52 53 54
#   BLOCK=32 ./sigprofile2.sh 47 48        same ladder at another block size
set -u
DEC="${DEC:-32}"; DWELL="${DWELL:-12}"
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-1}"
SIMD="${DSP4_SIMD_DYN:-1}"
BQ="${DSP4_BQ_GRAPH:-1}"
# Chip-2 biquad pairing (native interleave, 2026-09-02). 0 is the
# CONTROL: the dynamics-paired chain the 240,681 figure was measured
# on, byte for byte -- verified by rebuilding it from the previous
# commit and matching the .ldr.
C2BQ="${DSP4_C2_BQ_GRAPH:-1}"
BLOCK="${BLOCK:-8}"
WORK="${WORK:-/tmp/sigprof2}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

# BLOCK != 8 is built from a SCRATCH TREE generated with DSP4_GEN_BLOCK, for
# captable.sh's reason: the block size is baked into every generated file, and
# regenerating the repo tree back and forth is how a stale measurement tree
# gets built from. The directory name carries a digest of everything the tree
# is generated from, so a tree made from different inputs is a different
# directory and cannot be picked up by accident.
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

for L in "$@"; do
  D="$WORK/b$BLOCK-l$L-q$C2BQ"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG \
    DSP4_STRIP_FUSED=$FUS DSP4_SIMD_DYN=$SIMD DSP4_BQ_GRAPH=$BQ \
    DSP4_C2_BQ_GRAPH=$C2BQ \
    DSP4_NODE_LIMIT=0 DSP4_NODE_LIMIT2=$L \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "block=$BLOCK limit2=$L BUILD FAILED"; continue; fi
  read -r PT PP <<<"$(python3 -c "
import re
s=open('$D/chip2.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
print(a('proc_cyc'), a('proc_passes'))")"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         "$SRC/../tools/pi/dsp4_block.py" $BENCH:/home/app/dspboot/ 2>/dev/null \
    || scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
              $ROOT/tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
  scp -q $ROOT/tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
  scp -q $ROOT/tools/pi/gainfix.py $BENCH:/home/app/dspboot/
  scp -q sigprofile2_run.sh $BENCH:/home/app/
  echo "block=$BLOCK limit2=$L sig=$SIG c2bq=$C2BQ  $(ssh $BENCH "bash /home/app/sigprofile2_run.sh $PT $PP $DWELL" 2>&1 | tr '\n' ' | ')"
done
