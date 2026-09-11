#!/bin/bash
# playpath.sh — WHERE THE CM4's PLAYBACK STOPS INSIDE THE DSP (S29 gate 4).
#
# S12-10, S17 and S27-7 all end at the same wall: the through-DSP latency
# arm scores 0.0 % coherent at every offset and the main chain reads a
# constant. S27-7 read the END of the chain (`_buf_C2_MIX_MAIN_L` ..
# `_buf_C2_MAIN_ST_OUT`, all 0xfffffffc) and could only say "upstream of the
# DSP" -- reading the end of a dead chain says it is dead, not where.
#
# This walks the WHOLE chain instead:
#
#   C1_XIN_PI_L/R  ->  (inter-chip)  ->  C2_XR_PI_L/R  ->  C2_PI_IN
#                  ->  C2_MIX_MAIN_L/R -> C2_MAIN_FDR -> _DLY -> _ST_OUT
#
# and reports the first stage that is not moving with the stimulus.  It
# needs NO capture path and NO duplex overlay: every reading comes off the
# DSP over SPI.  The `driveall` bitstream is enough (it puts the Pi's
# playback on every DSPA lane, lane 6 included, which is where the Pi's
# playback goes on the shipping and `maincap` bitstreams anyway), so the
# break can be found on the bench as the capacity arms leave it.
#
#   STAGE=/home/app/dspcap/s29ctl BUILD=0 ./playpath.sh
#   BOOT=0 ./playpath.sh          probe what is already booted
#   PASSTHRU=0 ./playpath.sh      without silencing the other 16 sources
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ARM="${ARM:-playpath}"
STAGE="${STAGE:-/home/app/dspcap/$ARM}"
PRODUCT="${PRODUCT:-d24}"

python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3
scp -q $ROOT/tools/pi/dsp4_s29_playpath.py $ROOT/tools/pi/dsp4_checkchip.py \
       $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_config.py \
       $ROOT/tools/pi/dsp4_passthru_setup.py $ROOT/tools/pi/dsp4_conform.py \
       $ROOT/tools/pi/gainfix.py /tmp/landed-$PRODUCT.json $BENCH:$STAGE/ || exit 3
# dsp4_passthru_setup.py hardcodes /home/app/dspboot for the contract and the
# helpers; it is the SAME file (latency.sh does this too).
scp -q /tmp/landed-$PRODUCT.json $BENCH:/home/app/dspboot/ || exit 3
scp -q playpath_run.sh drive_audio.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT='$PRODUCT' BOOT='${BOOT:-1}' \
            PASSTHRU='${PASSTHRU:-1}' SAMPLES='${SAMPLES:-12}' \
            EXTRA='${EXTRA:-}' bash /home/app/playpath_run.sh"
