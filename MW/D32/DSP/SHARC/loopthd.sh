#!/bin/bash
# loopthd.sh — THE CABLE-LOOP THD LEG OF THE SHIPPING PROOF, host half.
#
# Builds the named configuration with DSP4_TEST_NODES=1 and nothing else
# moved, stages it to its own directory, and runs tools/pi/dsp4_loop_thd.sh
# on the part. THE EXIT CODE IS THE VERDICT.
#
# WHY IT IS A LEG OF THE PROOF AND NOT A DIAGNOSTIC (S88-1, S89e). Every bar
# this project ran on the signed configuration was digital or host-side --
# goldens, dsp_validate, the dry run, conformance, famverify, the driven
# capacity row -- and the configuration shipped with 57 % THD at the XLR.
# The defect lived between the output slot and the wire, where not one of
# those bars looks. This one listens. Run it on any configuration before
# signing it, the way `capacity.sh` is run before quoting a row.
#
# WHAT IT MEASURES AND WHAT IT CANNOT. TEST_OSC and TEST_MEAS are the
# instrument, and shipping.config carries DSP4_TEST_NODES=0, so this proves
# the CONFIGURATION with the self-test nodes added, not the byte-identical
# shipping image. That is the only self-reading form this bench has: a
# shipping image has no oscillator to drive its own output with. The arm's
# md5 is printed, and a report must say which image was measured.
#
# THE LANE IS THE UNIT'S. OSC_STRIP/MEAS_STRIP name the loop cable's two
# ends -- Monitor L (strip 20) -> MIC 6 (strip 6) on MW-D24-2 today. A cable
# move is an environment variable.
#
#   ./loopthd.sh                                  the shipping configuration
#   ARM=ctl DSP4_TX_DEFER=0 ./loopthd.sh          a control arm
#   BOOTS=3 ./loopthd.sh                          three gated boots
#   OSC_STRIP=6 MEAS_STRIP=5 ./loopthd.sh         AUX 1 -> MIC 5
#   BUILD=0 ARM=... ./loopthd.sh                  re-run what is staged
#   LOAD_SETUP=1 ./loopthd.sh                     the LOADED regime (S91): the
#                                                 graph put in its loaded
#                                                 configuration before the loop
#                                                 is read, and the position the
#                                                 gather then landed at printed
#                                                 beside the THD number
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219

ARM="${ARM:-ship}"
BOOTS="${BOOTS:-1}"
STAGE="/home/app/loopthd/$ARM"        # NOT ~/dspboot (S10-7)
WORK="${WORK:-/tmp/loopthd}"
D="$WORK/$ARM"
mkdir -p "$WORK"

OVR=""
for v in $(env | sed -n 's/^\(DSP4_[A-Z0-9_]*\)=.*/\1/p' | sort); do
    OVR="$OVR $v=${!v}"
done
echo "=== loop THD arm '$ARM'  config=$(basename "${SHIPPING_CONFIG:-shipping.config}")" \
     " lane=strip ${OSC_STRIP:-20} -> strip ${MEAS_STRIP:-6}  overrides:${OVR:- none}"

if [ "${BUILD:-1}" = "1" ]; then
    DSP_BUILD_DIR="$D" DSP4_TEST_NODES=1 ./build.sh all > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
        echo "BUILD FAILED — $D.log"; grep -iE '\[Error|Build FAILED' "$D.log" | head; exit 1; fi
    echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)  DSP4_TEST_NODES=1"
    # A FRESH symbol map with every arm (S10-9): a stale map points the
    # oscillator and the analyser at whatever now lives at that address, and
    # it answers.
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
    # input_patch.json must be linked beside the tool, not only present in
    # dspboot: dsp4_config.py loads it from next to ITSELF and a stage dir
    # symlinks the tool, so __file__ is the link (S83-2). Without it both
    # chips stop at BOOT_STAGE 5 and every reading is taken unconfigured.
    ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
        ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done; \
      ln -sfn /home/app/dspboot/input_patch.json '$STAGE'/input_patch.json" || exit 3
    scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
        $BENCH:$STAGE/ || exit 3
    scp -q $ROOT/MW/D24/DSP/input_patch.json $BENCH:$STAGE/ || exit 3
fi
# The instrument, the boot gate and the link scorer are part of the ARM, not
# of whatever the bench happens to hold.
# s89_set.py IS PART OF THE ARM AND IT IS NOT IN /home/app/dspboot. The stage
# directory symlinks dspboot's *.py, so a tool that lives only in this repo
# never arrives -- and the leg writes its route with stderr discarded, so the
# FIRST run of this script measured an unrouted default config: the donor
# strip's own compressor (on by default, threshold near -22 dBFS, S70-3)
# compressed the loop, 10 dB of drive moved the return 4.9 dB, and the leg
# still said PASS. Named here and checked in the leg.
scp -q $ROOT/tools/pi/dsp4_loop_thd.sh $ROOT/tools/pi/dsp4_boot_linked.sh \
       $ROOT/tools/pi/s89_signbit.py $ROOT/tools/pi/dsp4_s49_osc.py \
       $ROOT/tools/pi/s89_set.py \
       $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_config.py \
       $BENCH:$STAGE/ || exit 3
# THE LOADED-REGIME HALF (S91). `LOAD_SETUP=1` puts the graph in the loaded
# configuration before the loop is read, which needs the setup tool, the
# capacity reader that says where the gather then landed, and the LANDED
# CONTRACT they both address the part through -- generated here from the
# tree's own defs pin, the same way capacity.sh does it, so a bench run
# cannot score against a contract this tree is not on.
PRODUCT="${LOAD_PRODUCT:-d24}"
python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3
scp -q $ROOT/tools/pi/dsp4_driven_setup.py $ROOT/tools/pi/dsp4_capacity.py \
       /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
scp -q $ROOT/tools/pi/dsp4_loop_thd.sh $ROOT/tools/pi/dsp4_boot_linked.sh \
       $BENCH:/home/app/ || exit 3

ssh $BENCH "OSC_STRIP='${OSC_STRIP:-20}' MEAS_STRIP='${MEAS_STRIP:-6}' \
            THD_LIMIT_PCT='${THD_LIMIT_PCT:-1.0}' DRIVES='${DRIVES:--12.0 -22.0}' \
            LOAD_SETUP='${LOAD_SETUP:-0}' LOAD_PRODUCT='$PRODUCT' \
            LOAD_OFF='${LOAD_OFF-Comp,Gate,Limiter}' \
            bash /home/app/dsp4_loop_thd.sh 'loopthd/$ARM' $BOOTS"
