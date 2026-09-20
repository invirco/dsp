#!/bin/bash
# latency.sh — through-DSP latency, host half. See latency_run.sh.
#
#   ARM=lat16 ./latency.sh                       the tree as it stands
#   ARM=lat16e DSP4_TX_EARLY=1 ./latency.sh      with the switch
#   ARM=b32 BUILD=0 STAGE=/home/app/cap_b32 ./latency.sh
#   LOGIC_ONLY=1 ./latency.sh                    the CPLD loop reference
#
# Needs the `_maincap` bitstream for a through-DSP arm and `_pisel` for the
# LOGIC-only reference (./loadlogic.sh).
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ARM="${ARM:-lat}"
STAGE="${STAGE:-/home/app/cap_$ARM}"
D="${WORK:-/tmp/dspcap}/$ARM"
# THE STAGED ARM NEEDS `input_patch.json`, AND UNTIL S83 IT NEVER GOT ONE.
#
# `dsp4_config.py` reads the input patch from a file beside ITSELF and
# `sys.exit`s at IMPORT if it is not there (dsp4_config.py:96-100). In a
# staged directory the tool is a symlink into ~/dspboot but `__file__` is
# the LINK, so the lookup lands in $STAGE and finds nothing -- while
# latency_run.sh sends the config tool's whole output to /dev/null. The
# chips therefore booted and were NEVER CONFIGURED: both sat at
# BOOT_STAGE 5, the bar took its twenty reps anyway, and the 0.0 %
# coherent fraction it reported was a correct reading of an unconfigured
# part (S82 4.3, root-caused S83-2 by reproducing the exit in
# /home/app/cap_s82lat by hand). `s82.sh` links the file and reaches
# stage 7 on the same pair, which is the whole of the difference.
#
# Linked OUTSIDE the BUILD guard, because `BUILD=0 STAGE=...` -- the
# documented way to re-measure a staged pair -- is exactly the arm that
# skipped the staging block and so could never have had it.
ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
    ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done; \
    ln -sfn /home/app/dspboot/input_patch.json '$STAGE'/input_patch.json" || exit 3
if [ "${BUILD:-1}" = "1" ]; then
  DSP_SRC_DIR="${DSP_SRC_DIR:-$PWD/src}" DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "BUILD FAILED — $D.log"; exit 1; fi
  echo "  image: chip1.ldr $(md5sum $D/chip1.ldr|cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr|cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" $BENCH:$STAGE/ || exit 3
fi
python3 $ROOT/tools/dsp/landed_map.py --product "${PRODUCT:-d24}" \
        --json /tmp/landed-${PRODUCT:-d24}.json || exit 3
scp -q $ROOT/tools/pi/dsp4_dsp_latency.py $ROOT/tools/pi/dsp4_checkchip.py \
       $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/gainfix.py \
       $ROOT/tools/pi/dsp4_passthru_setup.py $ROOT/tools/pi/dsp4_conform.py \
       /tmp/landed-${PRODUCT:-d24}.json $BENCH:$STAGE/ || exit 3
# dsp4_passthru_setup.py hardcodes /home/app/dspboot for the contract and the
# helpers; a staged arm needs the contract there too, and it is the SAME file.
scp -q /tmp/landed-${PRODUCT:-d24}.json $BENCH:/home/app/dspboot/ || exit 3
scp -q latency_run.sh $BENCH:/home/app/ || exit 3
for r in $(seq 1 "${REPS_BOOT:-2}"); do
  echo "--- boot $r ---"
  # DSP4_PCM_DEV IS FORWARDED (S27). dsp4_dsp_latency.py has read it since
  # S17 -- it is how one duplex device serves as both halves of the loop --
  # and no run script could set it, so the duplex overlay could only be used
  # by running the tool by hand. Under `dsp4-pcm-duplex` the card exposes ONE
  # device that plays and captures (`DSP4_PCM_DEV=hw:dsp4pcm,0`); under
  # `dsp4-pcm-slave` it is two, which is the tool's default and needs nothing
  # here. Addressed by NAME, so the card INDEX moving (it is 0 on the slave
  # overlay and 2 on duplex, behind the two HDMI cards) does not matter.
  ssh $BENCH "STAGE='$STAGE' REPS='${REPS:-20}' PRODUCT='${PRODUCT:-d24}' \
              DSP4_PCM_DEV='${DSP4_PCM_DEV:-}' \
              DSP4_PCM_CAP='${DSP4_PCM_CAP:-}' \
              DSP4_PCM_PLAY='${DSP4_PCM_PLAY:-}' \
              LOGIC_ONLY='${LOGIC_ONLY:-0}' bash /home/app/latency_run.sh"
done
