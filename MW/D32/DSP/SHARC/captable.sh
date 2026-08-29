#!/bin/bash
# captable.sh — the measured capacity table: build the whole matrix first,
# then walk the bench once.
#
# sigstrips.sh builds and runs one point at a time, which is right for a
# bracket search and wrong for a table: the table's 20-odd points are
# known up front, the builds are independent, and the bench is the only
# serial resource. This builds every point in parallel into its own
# directory and then runs them back to back, which is roughly half the
# wall clock and, more importantly, leaves the bench doing nothing but
# measuring.
#
# A point is BLOCK:CCLK:SIG:STRIPS[:LIMIT]
#     BLOCK   8 | 32     (32 generates its own source tree; see below)
#     CCLK    786 | 983  (DSP4_CCLK_TARGET)
#     SIG     1 | 0      (stimulus present / the silence control)
#     STRIPS  channel strips in the graph
#     LIMIT   DSP4_NODE_LIMIT -- keep only the first N nodes of the chain,
#             for the per-CLASS profile (MODE=cyc). Omitted or 0 = whole
#             chain. Consecutive limits differ by one node, so consecutive
#             differences are that node's cost. Under pairing the chain is
#             PAIR-ORDERED, 18 positions per pair, not strip-ordered.
#
# Config is fused + paired throughout unless FUSED/SIMD say otherwise --
# that is the configuration the table is about.
#
# dsp4_block.py is staged FROM THE SOURCE TREE THE POINT WAS BUILT FROM,
# not from tools/pi, so audio_verdict.py scores every point against its own
# block rate rather than against whichever tree was generated last.
#
# BLOCK=32 is built from a SCRATCH TREE generated with DSP4_GEN_BLOCK=32,
# not from the repo's src/: the block size is baked into every generated
# file, so the alternative is regenerating the tree twice per point and
# hoping the second regeneration lands back on the shipping bytes.
#
#   ./captable.sh 8:983:1:16 8:983:1:18 8:983:1:20
#   FUSED=0 SIMD=0 ./captable.sh ...      the scalar-unfused control
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
FUSED="${FUSED:-1}"
SIMD="${SIMD:-1}"
# BQ=0 is the CONTROL: dynamics-only pairs, which is the configuration the
# session-3 table was measured on. BQ=1 pairs FILT and EQ too.
BQ="${BQ:-1}"
# MODE=rate (default) scores the block rate at N strips -- the CEILING
# question. MODE=cyc measures cycles per graph pass at N strips with the
# graph decimated so it always completes -- the MARGIN-AT-32 question,
# which has to be answerable at strip counts that do NOT fit real time.
MODE="${MODE:-rate}"
DEC="${DEC:-32}"
DWELL="${DWELL:-20}"
WORK="${WORK:-/tmp/captable}"
mkdir -p "$WORK"

# ---- source trees, one per block size ----
srctree() {   # $1 = block size -> echoes the src dir to build from
    if [ "$1" = "8" ]; then echo "$PWD/src"; return; fi
    local t="$WORK/src$1"
    if [ ! -f "$t/dsp_block.h" ] || \
       ! grep -q "define DSP4_BLOCK_SIZE   $1\$" "$t/dsp_block.h"; then
        rm -rf "$t"; cp -r "$PWD/src" "$t"
        DSP4_GEN_BLOCK=$1 python3 $ROOT/tools/dsp/dsp_codegen.py \
            "$PWD/dsp.csv" "$t" --force >/dev/null 2>&1
    fi
    echo "$t"
}

# ---- phase 1: build every point, four at a time ----
build_one() {   # $1 = point
    IFS=: read -r B C S N L <<<"$1"
    L="${L:-0}"
    local d="$WORK/$MODE-$B-$C-$S-$N-$L-$FUSED$SIMD$BQ"
    local dec=1
    [ "$MODE" = cyc ] && dec=$DEC
    DSP_SRC_DIR="$(srctree "$B")" DSP_BUILD_DIR="$d" \
    DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$S \
    DSP4_STRIP_FUSED=$FUSED DSP4_SIMD_DYN=$SIMD DSP4_BQ_GRAPH=$BQ \
    DSP4_STRIPS=$N \
    DSP4_BLOCK_DECIMATE=$dec DSP4_NODE_LIMIT=$L \
    DSP4_CCLK_TARGET=$C ./build.sh all > "$d.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$d.log")" -ne 0 ]; then
        echo "BUILD FAILED  $1" >&2; echo "fail" > "$d.status"
    else
        echo "ok" > "$d.status"
    fi
}

# Every source tree the point list needs has to exist BEFORE the parallel
# builds start, or four of them race to generate the same one.
for p in "$@"; do IFS=: read -r B _ _ _ <<<"$p"; srctree "$B" >/dev/null; done

echo "=== building $# points (fused=$FUSED paired=$SIMD bq=$BQ)"
i=0
for p in "$@"; do
    build_one "$p" &
    i=$((i+1)); [ $((i % 4)) -eq 0 ] && wait
done
wait

# ---- phase 2: one pass over the bench ----
scp -q $ROOT/tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
scp -q sigstrips_run.sh sigprofile_run.sh $BENCH:/home/app/
echo "=== measuring"
for p in "$@"; do
    IFS=: read -r B C S N L <<<"$p"
    L="${L:-0}"
    d="$WORK/$MODE-$B-$C-$S-$N-$L-$FUSED$SIMD$BQ"
    if [ "$(cat "$d.status" 2>/dev/null)" != "ok" ]; then
        echo "block=$B clk=$C sig=$S strips=$N limit=$L  BUILD FAILED"; continue; fi
    read -r PT PP <<<"$(python3 -c "
import re
s=open('$d/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
print(a('proc_cyc'), a('proc_passes'))")"
    python3 $ROOT/tools/dsp/map_syms.py "$d/chip1.map.xml" > /tmp/chip1.sym.json
    scp -q "$d/chip1.ldr" "$d/chip2.ldr" /tmp/chip1.sym.json \
        "$(srctree "$B")/dsp4_block.py" $BENCH:/home/app/dspboot/
    if [ "$MODE" = cyc ]; then
        R=$(ssh $BENCH "bash /home/app/sigprofile_run.sh $PT $PP $DWELL" 2>&1)
    else
        R=$(ssh $BENCH "bash /home/app/sigstrips_run.sh $PP $N" 2>&1)
    fi
    echo "block=$B clk=$C sig=$S strips=$N limit=$L fused=$FUSED paired=$SIMD bq=$BQ  $(echo "$R" | tr '\n' ' | ')"
done
