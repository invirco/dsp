#!/bin/bash
# s19matrix.sh — re-price every staged pair UNDER LOAD, both products,
# both chips, both regimes (S19 gate 2).
#
# Every capacity figure in this tree before 2026-09-10 was taken with the
# bench silent, and S18 measured what that is worth: chip 2 reads 92.7 % of
# budget with its dynamics below threshold and 112.3 % with them engaged, on
# one image and one product. So the decision table PW is holding is a table
# of silence figures, and it has to be taken again with the graph on the
# branch a working desk puts it on.
#
# THE ARMS ARE THE STAGED PAIRS, REBUILT FROM THIS TREE. A staged .ldr has
# no symbol map beside it for most of the pairs, and dsp4_capacity.py needs
# the map the image was built with (S10-9), so each arm is rebuilt here from
# `shipping.config` plus the overrides that define it and its md5 is
# recorded beside the staged pair's. Where they differ, the tree has moved
# since the pair was staged (S17 put four bytes into DIAG_CLEAR, S18's
# generator pass rewrote the node files) and the row says so.
#
#   blk   the shipping default, no overrides            302d6142 / 3b3a6f8e
#   s16   DSP4_GATE_LINTHR=1 DSP4_DYN_LUT=1             (S16's recommendation)
#   s16f  the same + DSP4_BQ_SIMD_PIPE=2                (six-slot biquad)
#   s18   DSP4_SHARED_KERNELS=3                         (COMP + TUBE shared)
#
# Each (arm, product) runs the three-row driven ladder on each of REPS
# boots: silent/default, silent/loaded, driven/loaded. See capacity_run.sh
# for why those three and not one.
#
# THE BITSTREAM IS PART OF THE INSTRUMENT: `./loadlogic.sh driveall` must
# have been run, and `./loadlogic.sh shipping` must be run afterwards. This
# script does neither, deliberately — a CPLD flash is not something a
# measurement loop should do behind the operator.
#
#   ./s19matrix.sh                 the whole matrix
#   ARMS='blk s16' ./s19matrix.sh  a subset, in that order
#   REPS=1 DWELL=30 ./s19matrix.sh
set -u
cd "$(dirname "$0")"

ARMS="${ARMS:-blk s16 s18 s16f}"
PRODUCTS="${PRODUCTS:-d24 d32}"
REPS="${REPS:-2}"
DWELL="${DWELL:-30}"
WORK="${WORK:-/tmp/dspcap}"

flags_for() {
    case "$1" in
        blk)  echo "" ;;
        s16)  echo "DSP4_GATE_LINTHR=1 DSP4_DYN_LUT=1" ;;
        s16f) echo "DSP4_GATE_LINTHR=1 DSP4_DYN_LUT=1 DSP4_BQ_SIMD_PIPE=2" ;;
        s18)  echo "DSP4_SHARED_KERNELS=3" ;;
        # The only candidate that has ever made D32 fit, re-priced DRIVEN.
        # shipping.config names both at 0 and says why: SIMD_DYN is 29.6 %
        # of chip 2 and STRIP_FUSED 1.08 %, and together they took chip 2
        # from 112.7 % to 82.0 % AT SILENCE -- which is the number this
        # session exists to distrust. C2_BQ_GRAPH stays 0 (S12-5: paired
        # chip-2 biquads do not reach the audio).
        s16sd) echo "DSP4_GATE_LINTHR=1 DSP4_DYN_LUT=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1" ;;
        *)    echo "UNKNOWN" ;;
    esac
}

for arm in $ARMS; do
    F="$(flags_for "$arm")"
    [ "$F" = "UNKNOWN" ] && { echo "unknown arm $arm" >&2; exit 2; }
    D="$WORK/s19$arm"
    if [ ! -f "$D/chip1.ldr" ]; then
        echo "=== building $arm ($F)"
        env $F DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1 || {
            echo "BUILD FAILED — $D.log"; exit 1; }
    fi
    echo "=== arm $arm  $(md5sum $D/chip1.ldr | cut -c1-8) / $(md5sum $D/chip2.ldr | cut -c1-8)  [$F]"
    for prod in $PRODUCTS; do
        echo "--- $arm / $prod"
        BUILD=0 ARM="s19$arm" PRODUCT="$prod" REPS="$REPS" DWELL="$DWELL" \
            ./capacity.sh --driven || echo "!!! $arm/$prod FAILED"
    done
done
echo "=== matrix done; goldens/cap-s19*-{A,B,C}*.json"
