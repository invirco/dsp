#!/bin/bash
# numverify.sh — the wide-accumulator and blend arithmetic against
# fixed_ref, ON THE PART (review findings D1 and D3).
#
# Builds the DSP4_NUM_SELFTEST image, stages it with the reference model
# and the shared vector set, boots, and diffs the part's results against
# fixed_ref. Then does it again with DSP4_NUM_NEGCTL=1 -- the PRE-FIX
# arithmetic -- which MUST fail, and must fail exactly on the vectors the
# model predicts cross a boundary.
#
#   ./numverify.sh            # positive then negative control
#   ./numverify.sh pos        # positive only
#   ./numverify.sh neg        # negative control only
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
MODE="${1:-both}"
ROOT=../../../..

stage() {   # $1 = NEGCTL value
  DSP4_BISECT=0 DSP4_NUM_SELFTEST=1 DSP4_NUM_NEGCTL=$1 \
    ./build.sh > /tmp/numverify_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/numverify_build.log)" -ne 0 ]; then
    echo "BUILD FAILED (NEGCTL=$1)"; tail -20 /tmp/numverify_build.log; exit 1; fi
  echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)  (NEGCTL=$1)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      $ROOT/tools/pi/dsp4_num_verify.py \
      $ROOT/tools/dsp/fixed_ref.py \
      $ROOT/tools/dsp/boundary_vectors.py $BENCH:$STAGE/
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q numverify_run.sh $BENCH:/home/app/
}

rc=0
if [ "$MODE" = both ] || [ "$MODE" = pos ]; then
  echo "=== POSITIVE: the fixed arithmetic must match fixed_ref"
  stage 0
  ssh $BENCH "STAGE='$STAGE' bash /home/app/numverify_run.sh" || rc=1
fi
if [ "$MODE" = both ] || [ "$MODE" = neg ]; then
  echo
  echo "=== NEGATIVE CONTROL: the PRE-FIX arithmetic must fail the boundary"
  stage 1
  ssh $BENCH "STAGE='$STAGE' bash /home/app/numverify_run.sh --negctl" || rc=1
fi
exit $rc
