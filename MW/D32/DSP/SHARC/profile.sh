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
for L in "$@"; do
  DSP4_BISECT=0 DSP4_NODE_LIMIT=$L DSP4_BLOCK_DECIMATE=$DEC ./build.sh > /tmp/prof_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/prof_build.log)" -ne 0 ]; then echo "limit=$L BUILD FAILED"; continue; fi
  read -r PT PP PF <<<"$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(re.escape(n)+r\"' address='(0x[0-9a-fA-F]+)'\",s); return m.group(1) if m else '0'
print(a('proc_cyc'), a('proc_passes'), a('proc_cyc_max'))")"
  scp -q build/chip1.ldr build/chip2.ldr ../../../../tools/pi/dsp4_block.py $BENCH:$STAGE/
  scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:$STAGE/audio_verdict.py
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q profile_run.sh $BENCH:/home/app/
  R=""
  for try in 1 2 3; do          # the link is flaky; a point is worth retrying
    R=$(ssh $BENCH "STAGE='$STAGE' bash /home/app/profile_run.sh $PT $PP $DWELL" 2>&1)
    case "$R" in *cycles/pass*) break;; esac
  done
  echo "limit=$L  $R"
done
