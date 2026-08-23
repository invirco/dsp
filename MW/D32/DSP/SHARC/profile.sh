#!/bin/bash
# profile.sh — measure cycles per block pass on the part, for a list of
# DSP4_NODE_LIMIT points. Differences between consecutive points give the
# cost of the node that was added; the chain is strip-ordered
# (IN GAIN FILT EQ GATE COMP TUBE DLY FDR RTG) so limits 1..10 profile one
# node of each class.
#
# Runs under DSP4_BLOCK_DECIMATE so the link stays alive at every point --
# decimation changes how OFTEN a pass runs, never what a pass costs.
set -u
DEC="${DEC:-32}"; DWELL="${DWELL:-20}"
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
for L in "$@"; do
  DSP4_BISECT=0 DSP4_NODE_LIMIT=$L DSP4_BLOCK_DECIMATE=$DEC ./build.sh > /tmp/prof_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/prof_build.log)" -ne 0 ]; then echo "limit=$L BUILD FAILED"; continue; fi
  read -r PT PP PF <<<"$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
print(a('proc_cyc'), a('proc_passes'), a('proc_cyc_max'))")"
  scp -q build/chip1.ldr build/chip2.ldr $BENCH:/home/app/dspboot/
  R=""
  for try in 1 2 3; do          # the link is flaky; a point is worth retrying
    R=$(ssh $BENCH "bash /home/app/profile_run.sh $PT $PP $DWELL" 2>&1)
    case "$R" in *cycles/pass*) break;; esac
  done
  echo "limit=$L  $R"
done
