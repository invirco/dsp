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
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-0}"
# SIMD strip pairing: passed through so the same instrument
# measures the scalar and the paired graph. Under pairing the
# chain is PAIR-ORDERED and DSP4_NODE_LIMIT counts positions in
# that order (18 per pair), which is what makes the paired
# dynamics readable as one consecutive difference.
SIMD="${DSP4_SIMD_DYN:-0}"
for S in "$@"; do
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG DSP4_STRIP_FUSED=$FUS DSP4_SIMD_DYN=$SIMD DSP4_STRIPS=$S \
    ./build.sh > /tmp/sigstrips_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/sigstrips_build.log)" -ne 0 ]; then
    echo "strips=$S BUILD FAILED"; continue; fi
  PP=$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
m=re.search(r\"proc_passes' address='(0x[0-9a-fA-F]+)'\",s); print(m.group(1) if m else '')")
  # the symbol table moves on every build; the witness reads .var addresses
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json ../../../../tools/pi/dsp4_block.py $BENCH:$STAGE/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:$STAGE/audio_verdict.py
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q sigstrips_run.sh $BENCH:/home/app/
  echo "strips=$S sig=$SIG fused=$FUS simd=$SIMD clk=${DSP4_CCLK_TARGET:-0}  $(ssh $BENCH "STAGE='$STAGE' bash /home/app/sigstrips_run.sh $PP $S" 2>&1 | tr '\n' ' | ')"
done
