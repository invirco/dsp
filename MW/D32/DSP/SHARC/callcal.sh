#!/bin/bash
# callcal.sh — price a call/rts pair ON THE PART (review finding D66).
#
# Builds the DSP4_CALL_SELFTEST image, boots it and reads the ladder back.
# Nothing here touches node state or a parameter, so unlike the profiling
# instruments it needs no witness and no signal: it is eight timed loops
# in ordinary main-loop context.
#
#   ./callcal.sh
set -u
cd "$(dirname "$0")"
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

DSP4_BISECT=0 DSP4_CALL_SELFTEST=1 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > /tmp/callcal_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/callcal_build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 /tmp/callcal_build.log; exit 1; fi
echo "  image: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_call_cal.py $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q callcal_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/callcal_run.sh"
