#!/bin/bash
# s20restore.sh — put the bench back the way the window expects it, and PROVE it.
#
# S19's §5 is the model: the staged window pair booted from a scratch directory
# (never ~/dspboot, S10-7), CHIP_ID and BOOT_STAGE read on both chips, and zero
# overruns over a dwell after DIAG_CLEAR. What S19 could NOT do was quote the
# cycle words, because `blk_*` predates the symbol-map staging discipline and
# has no sym.json beside it -- so this prints the named diag registers
# (DIAG_FRAME_COUNT, DIAG_BLK_OVERRUN), which do not need a map, and says so.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
PAIR="${PAIR:-blk}"
DWELL="${DWELL:-30}"
SCRATCH="${SCRATCH:-/home/app/dspcap/restore}"
ROOT=../../../..
scp -q $ROOT/tools/pi/dsp4_boot.py $ROOT/tools/pi/dsp4_checkchip.py \
       $ROOT/tools/pi/dsp4_capacity.py $BENCH:/home/app/dspboot/ || exit 3
scp -q s20restore_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "PAIR='$PAIR' DWELL='$DWELL' SCRATCH='$SCRATCH' \
            bash /home/app/s20restore_run.sh"
