#!/bin/bash
# goldnode.sh — the STRIP NODES against fixed_ref, ON THE PART.
#
# The golden-coverage bar for review findings D28 (COMP's wet path), D29
# (TUBE, plugin-class), D30 (the GATE state machine) and D31 (FADER_PAN's
# pan law and level coefficient) -- the four nodes the 2026-08-28 review
# found had no reference model of any kind, in the middle of a strip whose
# primitives were all covered.
#
# It is not a probe copy of the arithmetic. It drives the REAL GRAPH,
# captures each node's input and output over the same stimulus from the
# same rested state, and requires fixed_ref to reproduce the captured
# output word for word from the node's own converted parameters. That
# also closes the honest half of D35: every other in-part instrument this
# strip has compares ASSEMBLY AGAINST ASSEMBLY.
#
# THE NEGATIVE CONTROL IS IN THE MODEL, so there is ONE image and ONE
# boot. Each node is also run against a deliberately-wrong twin -- the
# gate ladder without its hold counter, the makeup without its second
# rounding, the tube without the middle of its three roundings, the fader
# with the level folded into the pan leg twice (the 2026-08-23 defect) --
# and the run requires the twin to DISAGREE with the part on the same
# captured samples. A stimulus that cannot separate them is reported as
# such and another amplitude is tried; it is never read as a pass.
#
# THE SHIPPING CONFIGURATION, like conform.sh: plain ./build.sh, which
# reproduces the bench's baseline byte for byte. That makes the build its
# own W0 check -- this bar changes no source that reaches an image, so
# the md5 printed below must equal the one the session started from.
#
#   ./goldnode.sh                 all four nodes
#   NODES=GATE,COMP ./goldnode.sh just those
#   N=48 ./goldnode.sh            shorter captures (each word is a paced read)
#   BUILD=0 ./goldnode.sh         reuse whatever is already staged
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/goldnode_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/goldnode_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/goldnode_build.log | head; exit 1; fi
  echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)  (shipping configuration)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      $BENCH:/home/app/dspboot/ || exit 3
fi

scp -q $ROOT/tools/pi/dsp4_node_verify.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_block.py \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/boundary_vectors.py \
    $BENCH:/home/app/dspboot/ || exit 3
scp -q goldnode_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "NODES=${NODES:-GATE,COMP,TUBE,FDR} N=${N:-96} \
            bash /home/app/goldnode_run.sh"
