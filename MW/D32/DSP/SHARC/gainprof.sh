#!/bin/bash
# gainprof.sh — what does the GAIN class cost, SIMD against scalar?
#
# sigprofile.sh's instrument (TCOUNT/_proc_cyc, DSP4_NODE_LIMIT prefix cut,
# DEC decimation, the GAIN-coefficient witness) with the two things that
# dispatch needed and sigprofile.sh cannot do:
#
#   1. IT BUILDS AT ANY BLOCK SIZE, from a scratch tree generated with
#      DSP4_GEN_BLOCK, the way sigprofile2.sh and captable.sh do. The
#      2026-09-02 ruling put the operating point at 16 and every figure in
#      dsp4-function-costs.csv above it is a block-8 or block-32 figure.
#
#   2. IT SWEEPS DSP4_GAIN_SIMD, so the same ladder is walked twice and the
#      class cost is a DIFFERENCE OF DIFFERENCES rather than a number
#      compared against a record taken on another day, at another block
#      size, in another graph configuration.
#
# THE LADDER IS FOUR POSITIONS, NOT TWO, AND THAT IS DELIBERATE. Under the
# paired graph the chain runs head A (IN GAIN), head B (IN GAIN), then the
# pair calls -- so limits 1..4 are A.IN, A.GAIN, B.IN, B.GAIN and the GAIN
# class is measured TWICE per arm, on two different strips, from two
# independent consecutive differences. A class whose two readings disagree
# by more than the instrument's spread has not been measured.
#
# THE POOL PARITY IS WITNESSED, NOT ASSUMED. The SIMD kernel reads two
# adjacent samples with `dm(i0, 2)`, so PEy takes the word after PEx's.
# Every block slot sits at _blk_pool + n*BLOCK, so the parity of the whole
# pool is the parity of its base, and the base is whatever the linker
# chose. It is printed for every point rather than trusted.
#
# REPEATS, AND WHY THE MINIMUM. A point is one BOOT, and boots differ:
# the first run of this ladder had the scalar arm reproduce beautifully
# (549 and 551 cycles for the same class on two strips, 0.4% apart) and
# the SIMD arm throw a point 540 cycles high, which made one of its two
# consecutive differences NEGATIVE. The signal here is a few hundred
# cycles on a baseline of sixteen thousand, so the instrument's spread is
# comparable to what is being measured and a single boot is not a
# measurement. REPS boots per point, MINIMUM taken -- bqshoot.sh's rule,
# and the right one: the ways a boot can cost MORE are many and the ways
# it can cost less are none.
#
#   ./gainprof.sh                    block 16, both arms, limits 1 2 3 4
#   REPS=3 ./gainprof.sh             three boots a point, minimum taken
#   LIMITS=0 REPS=3 ./gainprof.sh    the WHOLE graph, 32 gain nodes of
#                                    signal instead of one
#   BLOCK=8 ./gainprof.sh            the same at the old operating point
#   DSP4_MTR_OFF=1 ./gainprof.sh     GAIN without its meter
#   ARMS="1" ./gainprof.sh           SIMD arm only
#   LIMITS="1 2" ./gainprof.sh       one strip's reading only
set -u
DEC="${DEC:-32}"; DWELL="${DWELL:-20}"
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-1}"
SIMD="${DSP4_SIMD_DYN:-1}"
BQ="${DSP4_BQ_GRAPH:-1}"
BLOCK="${BLOCK:-16}"
ARMS="${ARMS:-0 1}"
LIMITS="${LIMITS:-1 2 3 4}"
REPS="${REPS:-1}"
# DSP4_MTR_OFF=1 takes the METER out, and it is named here rather than left
# to environment inheritance so the work-directory key can carry it. The
# class ladder otherwise BUNDLES the strip's meter NODE into GAIN, because
# a meter takes its source's ladder position -- this is how GAIN's own cost
# is separated from it. Note it also selects the UNMETERED kernel body, so
# it measures "GAIN with no meter", not "the metered kernel minus the
# meter node".
# ROUND ONCE PER CASCADE (landed 2026-09-03). Named here rather than left
# to environment inheritance so the work-directory key carries it and the
# two arms cannot share a build directory. 0 is the CONTROL and rebuilds
# the per-stage-saturating cascade kernels byte for byte.
RO="${DSP4_BQ_ROUNDONCE:-1}"
# The per-cascade headroom guard, passed through so chip 1 can be
# measured on the SAME arm chip 2 was. The round-once landing measured
# chip 1 with GD unset (i.e. the guard ON by default) but recorded the
# figure as "round-once"; the guard session only ever measured chip 2,
# so GD=0 here is what makes chip 1 a like-for-like pair with it.
GD="${DSP4_BQ_GUARD:-1}"
# THE FLOAT ARM (2026-09-03). FL=1 swaps the four cascade kernels for
# software float DF-II-T and forces the guard off with them; FL32=1 is
# its 32-bit control (MODE1.RND32 set). FL=0 is every existing point
# byte for byte, so the float arms and the fixed ones are a PAIRED
# measurement on one instrument in one session.
# Float is the SHIPPING cascade since 2026-09-03, so this instrument
# defaults to it; DSP4_BQ_FLOAT=0 is the fixed reference arm.
FL="${DSP4_BQ_FLOAT:-1}"
FL32="${DSP4_BQ_FLOAT32:-0}"
# GAIN follows the cascade unless asked otherwise.
GFL="${DSP4_GAIN_FLOAT:-$FL}"
MTROFF="${DSP4_MTR_OFF:-0}"
WORK="${WORK:-/tmp/gainprof}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

# A tree generated from different inputs is a different directory and
# cannot be picked up by accident -- sigprofile2.sh's rule, and the reason
# a stale measurement tree cannot be built from.
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

for G in $ARMS; do
for L in $LIMITS; do
  D="$WORK/b$BLOCK-g$G-l$L-m$MTROFF-r$RO-d$GD-f$FL$FL32"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG \
    DSP4_STRIP_FUSED=$FUS DSP4_SIMD_DYN=$SIMD DSP4_BQ_GRAPH=$BQ \
    DSP4_GAIN_SIMD=$G DSP4_NODE_LIMIT=$L DSP4_NODE_LIMIT2=0 \
    DSP4_MTR_OFF=$MTROFF DSP4_BQ_ROUNDONCE=$RO DSP4_BQ_GUARD=$GD \
    DSP4_BQ_FLOAT=$FL DSP4_BQ_FLOAT32=$FL32 DSP4_GAIN_FLOAT=$GFL \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "block=$BLOCK simd=$G limit=$L BUILD FAILED"; continue; fi
  read -r PT PP POOL <<<"$(python3 -c "
import re
s=open('$D/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
p=int(a('_blk_pool'),16); q=int(a('_blk_pool1'),16)
print(a('proc_cyc'), a('proc_passes'),
      ('even' if (p|q)%2==0 else 'ODD-POOL'))")"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  cp -f "$D/chip1.sym.json" /tmp/chip1.sym.json
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" \
         "$SRC/dsp4_block.py" $BENCH:/home/app/dspboot/ 2>/dev/null \
    || scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" \
              $ROOT/tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
  scp -q $ROOT/tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
  scp -q $ROOT/tools/pi/gainfix.py $ROOT/tools/pi/tubeon.py $BENCH:/home/app/dspboot/
  scp -q sigprofile_run.sh $BENCH:/home/app/
  BEST=""
  for r in $(seq 1 "$REPS"); do
    R="$(ssh $BENCH "bash /home/app/sigprofile_run.sh $PT $PP $DWELL 0" 2>&1 | tr '\n' ' | ')"
    C="$(echo "$R" | grep -oE '[0-9]+ cycles/pass' | grep -oE '^[0-9]+')"
    echo "block=$BLOCK simd=$G limit=$L mtroff=$MTROFF ro=$RO gd=$GD fl=$FL$FL32 rep=$r pool=$POOL  $R"
    if [ -n "$C" ]; then
      if [ -z "$BEST" ] || [ "$C" -lt "$BEST" ]; then BEST="$C"; fi
    fi
  done
  echo "block=$BLOCK simd=$G limit=$L mtroff=$MTROFF ro=$RO gd=$GD fl=$FL$FL32 pool=$POOL  MIN=${BEST:-none} cycles/block over $REPS boot(s)"
done
done
