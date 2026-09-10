#!/bin/bash
# pairgraph.sh — is the PAIRED GRAPH bit-exact against the scalar one?
#
# Builds the same graph three ways and captures the main bus from each:
#
#   off     DSP4_SIMD_DYN=0             the reference
#   on      DSP4_SIMD_DYN=1             pair-ordered chain, odd pool, paired
#                                       dynamics -- must MATCH the reference
#   neg     DSP4_SIMD_DYN=1 NEGCTL=1    the pair gathers channel B from
#                                       channel A, so it computes one
#                                       channel twice -- must DIFFER
#
# The negative control is the whole point. A diff that cannot fail proves
# nothing, and an identical-data pair test is exactly that kind of diff.
#
#   ./pairgraph.sh              strip 1 driven, strip 2 muted
#   STRIP=2 ./pairgraph.sh      the other way round
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
STRIP="${STRIP:-1}"
N="${N:-64}"
STRIPS="${STRIPS:-2}"
OUT=/tmp/pairgraph
mkdir -p $OUT

run_one() {   # tag  SIMD_DYN  NEGCTL
  local tag=$1 dyn=$2 neg=$3
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=$dyn DSP4_SIMD_NEGCTL=$neg \
    DSP4_STRIP_FUSED=${FUSED:-0} DSP4_STRIPS=$STRIPS ./build.sh \
    > /tmp/pairgraph_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/pairgraph_build.log)" -ne 0 ]; then
    echo "$tag: BUILD FAILED"; grep -iE '\[Error' /tmp/pairgraph_build.log | head; return 1; fi
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      ../../../../tools/pi/dsp4_block.py ../../../../tools/pi/dsp4_pairgraph.py \
      $BENCH:$STAGE/
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q pairgraph_run.sh $BENCH:/home/app/
  ssh $BENCH "STAGE='$STAGE' bash /home/app/pairgraph_run.sh $STRIP $N $tag"
  scp -q $BENCH:$STAGE/pairgraph_$tag.json $OUT/ 2>/dev/null
}

for spec in "off 0 0" "on 1 0" "neg 1 1"; do
  # shellcheck disable=SC2086
  set -- $spec
  echo "--- $1 ---"
  run_one "$1" "$2" "$3" || exit 1
done

echo "=== verdict ==="
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_off.json $OUT/pairgraph_on.json
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_off.json $OUT/pairgraph_neg.json
