#!/bin/bash
# s33flip.sh — host half of the S32 gate-4 flip proof, repeated on the FINAL
# candidate-B bytes (S33 gate 4).
#
# It does NOT build and it does NOT stage an image: it runs against a staging
# directory the capacity instrument has already filled and measured, so the
# bytes flipped here are the bytes the rows in dsp4-s33-20260911.md §3 were
# taken on. The md5 is printed on the bench side before the boot.
#
#   STAGE=/home/app/dspcap/s33b ./s33flip.sh          candidate B
#   STAGE=/home/app/dspcap/s33a ./s33flip.sh          the control
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
STAGE="${STAGE:-/home/app/dspcap/s33b}"
OUT="${OUT:-s33-flip.json}"

# The probe travels with the run (the D74 lesson in bench_lock.sh): a fix to
# the flip tool in this tree must not be able to be absent from the bar.
scp -q $ROOT/tools/pi/dsp4_s32_flip.py $BENCH:/home/app/dspboot/ || exit 3
scp -q s33flip_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=${PRODUCT:-d32} NODES='${NODES:-C2_PI_IN,C2_SNK_IN_01,C2_SNK_IN_02,C2_SNK_IN_03,C2_SNK_IN_04}' \
            OUT='$OUT' bash /home/app/s33flip_run.sh"
RC=$?
mkdir -p goldens
scp -q "$BENCH:$STAGE/$OUT" ./goldens/ 2>/dev/null
echo "  report: goldens/$OUT  (rc=$RC)"
exit $RC
