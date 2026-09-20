#!/bin/bash
# s83.sh — stage and boot the DSP4_TEST_NODES arm of the SIGNED pair, then take
# the two analog gates S83 owes: MIC 5's lane (gate 2) and the talkback T1/T3
# re-take (gate 4).
#
# THE IMAGE IS THE SIGNED CONFIGURATION PLUS ONE SWITCH, and the switch is
# stated rather than implied: `DSP4_TEST_NODES=1` is DIAG_BUILD_CFG2 bit 24
# (S49), so the triple this arm must read back is
#
#     0xCF45FF10 / 0xE3018E6F / 0xC47C0F26
#
# against the shipping 0xCF45FF10 / 0xE2018E6F / 0xC47C0F26 — one bit, the
# instrument's own. `cfg_words.py` computes both; `check_shipping_config.sh`
# deliberately does NOT follow an environment override, because it is about the
# FILE, so an override shows up there as drift and that is correct.
#
#   ./s83.sh              build, stage, boot, measure
#   BUILD=0 ./s83.sh      re-boot what is already staged
set -u
BUILD="${BUILD:-1}"
STAGE="${STAGE:-/home/app/s83tn}"
WORK="${WORK:-/tmp/s83tn}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
    ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done; \
    ln -sfn /home/app/dspboot/input_patch.json '$STAGE'/input_patch.json" || exit 3

if [ "$BUILD" = "1" ]; then
  DSP_SRC_DIR="$PWD/src" DSP_BUILD_DIR="$WORK" DSP4_TEST_NODES=1 \
      ./build.sh all > "$WORK/build.log" 2>&1 || { echo "BUILD FAILED, see $WORK/build.log"; exit 1; }
  grep -qiE '\[Error|Build FAILED' "$WORK/build.log" && { echo "BUILD FAILED, see $WORK/build.log"; exit 1; }
fi
[ -f "$WORK/chip1.sym.json" ] || python3 $ROOT/tools/dsp/map_syms.py "$WORK/chip1.map.xml" > "$WORK/chip1.sym.json"
[ -f "$WORK/chip2.sym.json" ] || python3 $ROOT/tools/dsp/map_syms.py "$WORK/chip2.map.xml" > "$WORK/chip2.sym.json"
echo "== the TEST_NODES arm: chip1.ldr $(md5sum $WORK/chip1.ldr|cut -c1-32) chip2.ldr $(md5sum $WORK/chip2.ldr|cut -c1-32)"
DSP4_TEST_NODES=1 python3 $ROOT/tools/dsp/cfg_words.py 2>&1 | grep 'DIAG_BUILD_CFG' | sed 's/^/  /'

scp -q "$WORK/chip1.ldr" "$WORK/chip2.ldr" "$WORK/chip1.sym.json" "$WORK/chip2.sym.json" $BENCH:$STAGE/ || exit 3
scp -q $ROOT/tools/pi/dsp4_checkchip.py $ROOT/tools/pi/dsp4_boot.py $BENCH:$STAGE/ || exit 3
scp -q $ROOT/MW/D24/DSP/s83/tools/s83_lanescan.py $BENCH:$STAGE/ || exit 3
# The measurement libraries, re-staged from the tree rather than trusted on the
# card (S79-4: /home/app/s70's copy was a session stale and nothing deployed it).
scp -q $ROOT/MW/D24/DSP/s70/tools/*.py $BENCH:/home/app/s70/ || exit 3
scp -q $ROOT/MW/D24/DSP/s69/tools/*.py $BENCH:/home/app/s69/ || exit 3
scp -q $ROOT/MW/D24/DSP/s54/tools/*.py $BENCH:/home/app/s54/ || exit 3
scp -q $ROOT/MW/D24/DSP/s83/tools/s83_gate2.py $BENCH:/home/app/s83/ 2>/dev/null \
  || { ssh $BENCH "mkdir -p /home/app/s83"; scp -q $ROOT/MW/D24/DSP/s83/tools/s83_gate2.py $BENCH:/home/app/s83/; }

scp -q s83_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STAGE='$STAGE' GATES='${GATES:-2,4}' bash /home/app/s83_run.sh" 2>&1 | tee "$WORK/s83_run.out"
