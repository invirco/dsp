#!/bin/bash
# sigstrips.sh — the SIGNAL-PRESENT twin of strips.sh.
#
# strips.sh measures a ceiling on a bench with no analog input, so the gate
# sits shut and the compressor idle and both take the branch that skips
# log2/exp2 entirely. That is an upper bound, not a feasibility answer.
# This drives the same sweep with DSP4_PROFILE_SIGNAL=1, which adds a
# full-rate +/-0.5 (-6 dBFS) square wave to every strip's input inside the
# IN kernel -- above the -40 dB gate threshold and the -20 dB compressor
# threshold at every sample, so the dynamics run the path they run with
# real audio.
#
# Every point reports the dynamics witness alongside the pass rate. Read
# the verdict by the HONEST rule: the FULL block rate is real time --
# 48000/BLOCK, so 1500/s at BLOCK=32 and 6000/s at BLOCK=8.
# audio_verdict.py's REAL_TIME label only means it cleared 97% of that,
# and anything below the full rate is dropping blocks.
#
#   DSP4_CCLK_TARGET=786 ./sigstrips.sh 10 11 12 13
#   DSP4_PROFILE_SIGNAL=0 ... same sweep as the silence control
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-0}"
for S in "$@"; do
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG DSP4_STRIP_FUSED=$FUS DSP4_STRIPS=$S \
    ./build.sh > /tmp/sigstrips_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/sigstrips_build.log)" -ne 0 ]; then
    echo "strips=$S BUILD FAILED"; continue; fi
  PP=$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
m=re.search(r\"proc_passes' address='(0x[0-9a-fA-F]+)'\",s); print(m.group(1) if m else '')")
  # the symbol table moves on every build; the witness reads .var addresses
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json ../../../../tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
  scp -q sigstrips_run.sh $BENCH:/home/app/
  echo "strips=$S sig=$SIG fused=$FUS clk=${DSP4_CCLK_TARGET:-0}  $(ssh $BENCH "bash /home/app/sigstrips_run.sh $PP $S" 2>&1 | tr '\n' ' | ')"
done
