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
# THE CONFIGURATION, AND THE ONE SWITCH THAT IS NOT THE SHIPPING ONE
# (S19-7, fixed S21-5).
#
# This used to be plain `./build.sh` -- the shipping configuration, so that
# the build was its own W0 check. It was also the reason the bar FAILED
# IDENTICALLY ON EVERY STAGED PAIR for four sessions: with
# DSP4_BLOCK_KERNELS on, a strip node's per-node `_buf_<nid>` scalar is not
# in the signal path (the kernels pass blocks through a shared pool), and
# `_scope_record` reads sixteen consecutive words from whatever address it
# is given. Three of the four arms were therefore reading a stale word and
# fifteen of the next variable, and they read zero. S19-7 attributed it;
# the bar was wrong and the audio was not.
#
# So the arm carries `DSP4_SCOPE_BLK_TAP=1`, the BLOCK-AWARE witness S9-5
# built for exactly this and famverify has used since S10: the host names
# the node by its `_buf_<nid>` identity and the tap copies that node's
# whole block out of the pool slot its kernel just wrote. Everything else
# is the named configuration, and `SHIPPING_CONFIG` selects which one --
# so this bar can be run against `shipping.config`, `shipping.config.s20`
# or `shipping.config.s21` and says which it ran.
#
# THE CONTROL IS PRINTED, NOT ASSUMED: the run below builds the tap arm and
# also reports the same configuration with the tap OFF, whose md5 must be
# the staged pair's. The tap costs ~8 cycles per node per block and
# DIAG_BUILD_CFG2 bit 4 says it is on, so no capacity number is ever taken
# off this image.
#
#   ./goldnode.sh                 all four nodes
#   NODES=GATE,COMP ./goldnode.sh just those
#   N=48 ./goldnode.sh            shorter captures (each word is a paced read)
#   BUILD=0 ./goldnode.sh         reuse whatever is already staged
#   SHIPPING_CONFIG=$PWD/shipping.config.s20 ./goldnode.sh
#   TAP=0 ./goldnode.sh           the pre-S21 arm, for reproducing S19-7
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
ROOT=../../../..

TAP="${TAP:-1}"
CFGNAME="$(basename "${SHIPPING_CONFIG:-shipping.config}")"
if [ "${BUILD:-1}" = "1" ]; then
  # THE CONTROL FIRST, so the log carries the staged pair's md5 beside the
  # witness arm's and a reader can see that the only difference is the tap.
  DSP4_SCOPE_BLK_TAP=0 DSP_BUILD_DIR=/tmp/goldnode_ctl ./build.sh all \
      > /tmp/goldnode_ctl.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/goldnode_ctl.log)" -ne 0 ]; then
    echo "CONTROL BUILD FAILED"; grep -iE '\[Error' /tmp/goldnode_ctl.log | head
    exit 1; fi
  echo "  control (tap OFF, $CFGNAME): chip1.ldr \
$(md5sum /tmp/goldnode_ctl/chip1.ldr | cut -c1-8)  chip2.ldr \
$(md5sum /tmp/goldnode_ctl/chip2.ldr | cut -c1-8)  <-- must be the staged pair"

  DSP4_SCOPE_BLK_TAP=$TAP ./build.sh > /tmp/goldnode_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/goldnode_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/goldnode_build.log | head; exit 1; fi
  echo "  witness (tap=$TAP, $CFGNAME): chip1.ldr \
$(md5sum build/chip1.ldr | cut -c1-8)  chip2.ldr \
$(md5sum build/chip2.ldr | cut -c1-8)"
  grep -c "block-aware scope tap on" /tmp/goldnode_build.log >/dev/null 2>&1
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      $BENCH:$STAGE/ || exit 3
fi

scp -q $ROOT/tools/pi/dsp4_node_verify.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_block.py \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/boundary_vectors.py \
    $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
# dsp4_scope.py goes with the run too (S22-1): the arm/disarm contract this
# bar now depends on lives in it, and a bench copy that predates the fix
# would leave a stalled capture driving the graph with nothing saying so.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_scope.py" $BENCH:$STAGE/
scp -q goldnode_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STAGE='$STAGE' NODES=${NODES:-GATE,COMP,TUBE,FDR} N=${N:-96} \
            STRIPS='${STRIPS:-1}' bash /home/app/goldnode_run.sh"
