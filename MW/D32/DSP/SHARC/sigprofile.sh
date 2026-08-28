#!/bin/bash
# sigprofile.sh — per-CLASS cycle profile with the stimulus ON.
#
# profile.sh measures a silent bench, where GATE and COMP both short out
# before log2 and a strip reads ~30% cheap. This is its signal-present
# twin: same TCOUNT/_proc_cyc methodology, same DSP4_NODE_LIMIT prefix cut
# and same DEC (decimation changes how OFTEN a pass runs, never what one
# costs), with DSP4_PROFILE_SIGNAL=1 and DSP4_BLOCK_KERNELS=1.
#
# Every point is witnessed before its number is accepted: strip 1's GAIN
# coefficient must read 1.0f. Roughly one boot in three lands the
# CFG_COMMIT header word there instead, which zeroes everything downstream
# and makes the whole chain report the SILENCE cost with BOOT_STAGE, pass
# rate, DMA and SPORT all clean (root-caused 2026-08-28).
#
# The chain is strip-ordered — IN GAIN FILT EQ GATE COMP TUBE DLY FDR RTG —
# so limits 1..10 add one node of each class and consecutive differences
# are that class's cost.
#
#   ./sigprofile.sh 1 2 3 4 5 6 7 8 9 10
#   DSP4_PROFILE_SIGNAL=0 ./sigprofile.sh ...   same sweep, silence control
set -u
DEC="${DEC:-32}"; DWELL="${DWELL:-20}"
SIG="${DSP4_PROFILE_SIGNAL:-1}"
FUS="${DSP4_STRIP_FUSED:-0}"
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
for L in "$@"; do
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=$SIG \
    DSP4_STRIP_FUSED=$FUS DSP4_NODE_LIMIT=$L DSP4_BLOCK_DECIMATE=$DEC ./build.sh > /tmp/sigprof_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/sigprof_build.log)" -ne 0 ]; then
    echo "limit=$L BUILD FAILED"; continue; fi
  read -r PT PP <<<"$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
print(a('proc_cyc'), a('proc_passes'))")"
  # the symbol table moves on every build; the witness reads .var addresses
  python3 ../../../../tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json ../../../../tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
  scp -q sigprofile_run.sh $BENCH:/home/app/
  echo "limit=$L sig=$SIG fused=$FUS  $(ssh $BENCH "bash /home/app/sigprofile_run.sh $PT $PP $DWELL" 2>&1 | tr '\n' ' | ')"
done
