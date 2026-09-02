#!/bin/bash
# conform.sh — the CONTRACT CONFORMANCE HARNESS (protocol goldens).
#
# Every other bar in this tree measures the kernel against itself. This one
# measures it against the MASTERS: the wire tables in docs/contract/ say
# what each cell is and what unit it carries, and this writes them over the
# live SPI plane and requires the documented consequence.
#
# It is a STANDING per-session bar (PW addendum 2026-08-29): a session's
# requal includes a conform run, exactly as it includes the smokes and the
# goldens. See smoke-checklist.md.
#
#   ./conform.sh                     full sweep, both chips, effect + inert
#   PHASE=effect ./conform.sh        the declared-unit checks only (fast)
#   CHIPS=1 ./conform.sh             one chip
#   LIMIT=200 ./conform.sh           pilot: first 200 addresses per chip
#   NEGCTL=1 ./conform.sh            run the negative controls as well
#   TAG=after ./conform.sh           name the result files
#   INERTWIN=state ./conform.sh      the retired control-state inert window
#
# THE INERT PHASE DRIVES THE GRAPH (2026-08-29). It arms the DSP-side scope
# with a -6 dBFS step into the input slot and watches the MAIN BUS, so
# "kernel-visible" means the audio path rather than a proxy for it. Session
# 4 could not do that and said so: its control-state window failed its own
# positive control on an idle graph, and the injection it tried went into
# _buf_C1_IN_01, which the input node overwrites every sample. The slot the
# step has to go into is _rx_slot_C1_IN_01 in a per-sample build and the
# pool in a block build; the probe resolves that from the symbol table.
#
# The plan is built IN THE TREE, from the contract, by tools/dsp/
# wire_contract.py -- so a harness run always tests the surface the current
# contract describes, and a contract bump that the kernel has not caught up
# with fails here rather than being tested against its own stale copy.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
# dsp4_block.py IS STAGED FROM THE TREE THIS POINT WAS BUILT FROM, not
# from tools/pi, for captable.sh's reason: the Pi-side scorer must be told
# the block rate the image on the part was actually built with. conform.sh
# checks RAMP TIMINGS, and ramp frame counts are derived from the block
# rate -- so a block-16 image scored against a block-8 dsp4_block.py
# misjudges every ramp. Falls back to tools/pi when DSP_SRC_DIR is unset,
# which is the shipping block-8 tree and the same file.
BLOCKPY="${DSP_SRC_DIR:-$ROOT/MW/D32/DSP/SHARC/src}/dsp4_block.py"
[ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"
ROOT=../../../..
TAG="${TAG:-cur}"
PHASE="${PHASE:-all}"
CHIPS="${CHIPS:-1 2}"
LIMIT="${LIMIT:-0}"
PRODUCT="${PRODUCT:-d32}"
OUT=/tmp/conform; mkdir -p $OUT

echo "=== plan (from the contract, not from the image) ==="
python3 $ROOT/tools/dsp/wire_contract.py --product $PRODUCT \
        --plan $OUT/plan.json || exit 2

if [ "${BUILD:-1}" = "1" ]; then
  # THE SHIPPING CONFIGURATION, and nothing else by default. The contract
  # is a promise about the image that ships; testing it against a research
  # build (block kernels, pairing, fusion) would prove conformance of a
  # firmware no product runs. Plain ./build.sh reproduces the bench's
  # baseline byte for byte, which is the W0 check as well as the setup.
  echo "=== build (shipping configuration) ==="
  ./build.sh > $OUT/build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
  echo "  chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      $BENCH:/home/app/dspboot/ || exit 3
fi

scp -q $ROOT/tools/pi/dsp4_conform.py "$BLOCKPY" \
    $OUT/plan.json $BENCH:/home/app/dspboot/ || exit 3
scp -q conform_run.sh $BENCH:/home/app/ || exit 3

for c in $CHIPS; do
  echo "=== chip $c — $PHASE ==="
  ssh $BENCH "PHASE=$PHASE LIMIT=$LIMIT NEGCTL=${NEGCTL:-0} \
              INERTWIN=${INERTWIN:-bus} INERTN=${INERTN:-12} \
              bash /home/app/conform_run.sh $c $TAG" || exit 4
  scp -q $BENCH:/home/app/dspboot/"conform_${TAG}_c${c}*.json" $OUT/ || exit 4
done

echo "=== report ==="
python3 $ROOT/tools/pi/dsp4_conform_report.py $OUT/conform_${TAG}_c*.json \
        --plan $OUT/plan.json --markdown $OUT/conform_${TAG}.md \
        --csv $OUT/conform_${TAG}.csv
echo "  table: $OUT/conform_${TAG}.md"
