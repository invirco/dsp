#!/bin/bash
# bqgraph.sh — is the PAIRED-BIQUAD graph bit-exact against the one that
# pairs only the dynamics?
#
# Same shape and the same instrument as pairgraph.sh, one class earlier in
# the strip. Three builds of the same graph, one bus capture from each:
#
#   off   DSP4_BQ_GRAPH=0        dynamics paired, FILT and EQ per strip.
#                                This is the configuration the session-3
#                                capacity table was measured on, and it is
#                                the reference.
#   on    DSP4_BQ_GRAPH=1        FILT and EQ paired too -- must MATCH.
#   neg   DSP4_BQ_GRAPH=1        the pair takes strip B's coefficients and
#         DSP4_BQ_NEGCTL=1       state from strip A, so it computes ONE
#                                channel twice -- must DIFFER.
#
# THE BIQUADS ARE LOADED WITH REAL COEFFICIENTS (--bq). With the bypass
# set the paired and scalar cascades are bit-identical BY CONSTRUCTION, so
# a comparison taken at bypass passes whatever the pairing does -- which is
# exactly why session 3's bus golden reproduced with no biquad coefficient
# coverage at all (review finding D49's neighbour). Every arm here writes a
# different filter design into each strip of the pair.
#
#   ./bqgraph.sh              strip 1 driven, strip 2 muted
#   STRIP=2 ./bqgraph.sh      the other way round
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
STRIP="${STRIP:-1}"
N="${N:-64}"
STRIPS="${STRIPS:-2}"
OUT=/tmp/bqgraph
mkdir -p $OUT

run_one() {   # tag  BQ_GRAPH  BQ_NEGCTL
  local tag=$1 bq=$2 neg=$3
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=1 \
    DSP4_BQ_GRAPH=$bq DSP4_BQ_NEGCTL=$neg \
    DSP4_STRIP_FUSED=${FUSED:-1} DSP4_STRIPS=$STRIPS ./build.sh \
    > /tmp/bqgraph_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/bqgraph_build.log)" -ne 0 ]; then
    echo "$tag: BUILD FAILED"; grep -iE '\[Error' /tmp/bqgraph_build.log | head; return 1; fi
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      ../../../../tools/pi/dsp4_block.py ../../../../tools/pi/dsp4_pairgraph.py \
      $BENCH:/home/app/dspboot/
  scp -q pairgraph_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/pairgraph_run.sh $STRIP $N bq_$tag --bq"
  scp -q $BENCH:/home/app/dspboot/pairgraph_bq_$tag.json $OUT/ 2>/dev/null
}

for spec in "off 0 0" "on 1 0" "neg 1 1"; do
  # shellcheck disable=SC2086
  set -- $spec
  echo "--- $1 ---"
  run_one "$1" "$2" "$3" || exit 1
done

echo "=== verdict ==="
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_bq_off.json $OUT/pairgraph_bq_on.json
python3 ../../../../tools/pi/dsp4_pairgraph.py --compare $OUT/pairgraph_bq_off.json $OUT/pairgraph_bq_neg.json
