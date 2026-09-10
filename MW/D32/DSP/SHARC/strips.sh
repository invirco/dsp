#!/bin/bash
# strips.sh — find the largest DSP4_STRIPS that holds REAL TIME at 1x.
# Verdict is audio truth (FRAME_COUNT + _proc_passes + SPORT_ERR), not
# how responsive the parameter link feels: the link is polled from the
# main loop, so under load it needs patience, and treating a slow link as
# a dead card is what made a running graph look hung.
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
for S in "$@"; do
  DSP4_BISECT=0 DSP4_STRIPS=$S ./build.sh > /tmp/strips_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/strips_build.log)" -ne 0 ]; then echo "strips=$S BUILD FAILED"; continue; fi
  PP=$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
m=re.search(r\"proc_passes' address='(0x[0-9a-fA-F]+)'\",s); print(m.group(1) if m else '')")
  scp -q build/chip1.ldr build/chip2.ldr ../../../../tools/pi/dsp4_block.py $BENCH:$STAGE/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:$STAGE/audio_verdict.py
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q strips_run.sh $BENCH:/home/app/
  echo "strips=$S  $(ssh $BENCH "STAGE='$STAGE' bash /home/app/strips_run.sh $PP" 2>&1 | tr '\n' ' | ')"
done
