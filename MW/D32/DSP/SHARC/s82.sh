#!/bin/bash
# s82.sh — stage and boot THE SIGNED PAIR, prove the part reads back the
# signed configuration, and re-take the converter observations on the
# post-S34 shipping bitstream.
#
# The pair is built from shipping.config and nothing else -- no override on
# the command line, because the whole point of S82 is that the configuration
# is the FILE. `check_shipping_config.sh` prints the triple this image must
# read back; `dsp4_buildcfg.py --expect-shipping` on the part is the other
# half, and the OLD triple is passed to the same tool as the negative control.
#
# STAGED, NOT DEPLOYED. The pair goes to /home/app/ship_s82, never to
# ~/dspboot: S82 does not deploy, and ~/dspboot/ldr/manifest.txt is untouched.
#
#   ./s82.sh              build, stage, boot, measure
#   BUILD=0 ./s82.sh      re-boot what is already staged
set -u
BUILD="${BUILD:-1}"
STAGE="${STAGE:-/home/app/ship_s82}"
WORK="${WORK:-/tmp/s82}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
    ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done; \
    ln -sfn /home/app/dspboot/input_patch.json '$STAGE'/input_patch.json" || exit 3

if [ "$BUILD" = "1" ]; then
  ./build.sh all > "$WORK/build.log" 2>&1 || { echo "BUILD FAILED, see $WORK/build.log"; exit 1; }
  grep -qiE '\[Error|Build FAILED' "$WORK/build.log" && { echo "BUILD FAILED, see $WORK/build.log"; exit 1; }
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > build/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > build/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr build/chip1.sym.json build/chip2.sym.json $BENCH:$STAGE/
  scp -q $ROOT/tools/pi/dsp4_checkchip.py $ROOT/tools/pi/dsp4_boot.py $BENCH:$STAGE/
  # The landed map and the input patch the config tool needs, from the same
  # place every other staged arm takes them.
  ssh $BENCH "ln -sfn /home/app/dspboot/landed-d24.json $STAGE/landed-d24.json 2>/dev/null; \
              ln -sfn /home/app/dspboot/input_patch.json $STAGE/input_patch.json 2>/dev/null" || true
fi
echo "== the signed pair: chip1.ldr $(md5sum build/chip1.ldr|cut -c1-32) chip2.ldr $(md5sum build/chip2.ldr|cut -c1-32)"
./check_shipping_config.sh --expect-shipping | head -1

scp -q s82_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/s82_run.sh '$STAGE' $STAGE/s82.json" 2>&1 | tee "$WORK/s82_run.out"
