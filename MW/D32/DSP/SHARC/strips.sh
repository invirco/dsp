#!/bin/bash
# strips.sh — find the largest DSP4_STRIPS that holds REAL TIME at 1x.
# Verdict is audio truth (FRAME_COUNT + _proc_passes + SPORT_ERR), not
# how responsive the parameter link feels: the link is polled from the
# main loop, so under load it needs patience, and treating a slow link as
# a dead card is what made a running graph look hung.
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
for S in "$@"; do
  DSP4_BISECT=0 DSP4_STRIPS=$S ./build.sh > /tmp/strips_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/strips_build.log)" -ne 0 ]; then echo "strips=$S BUILD FAILED"; continue; fi
  PP=$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
m=re.search(r\"proc_passes' address='(0x[0-9a-fA-F]+)'\",s); print(m.group(1) if m else '')")
  scp -q build/chip1.ldr build/chip2.ldr ../../../../tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
  scp -q strips_run.sh $BENCH:/home/app/
  echo "strips=$S  $(ssh $BENCH "bash /home/app/strips_run.sh $PP" 2>&1 | tr '\n' ' | ')"
done
