#!/bin/bash
# s20matrix.sh — the driven capacity matrix for the S20 proposal.
#
# s19matrix.sh re-priced the STAGED PAIRS under load and found that the
# configuration `shipping.config` names fits neither product (D24 118.9 % /
# 119.2 %, D32 158.2 % / 142.8 %), that `s16_*` fits D24 and not D32, and that
# one arm it built for comparison -- `s16` plus DSP4_STRIP_FUSED and
# DSP4_SIMD_DYN -- fits both. It could not recommend that arm because it was
# an environment, not a configuration: five DSP4_* on a command line, with
# DSP4_C2_BQ_GRAPH left at 0 on the strength of a finding that had already
# been closed.
#
# So the arms here are CONFIGURATION FILES. `shipping.config.s20` is the
# proposal; `s20f` is the same file plus the one override it names as its own
# alternative (DSP4_BQ_SIMD_PIPE=2). Each arm's md5 is printed, and
# cfgverify.sh has already proved both read the file back to the bit.
#
# The three-row driven ladder, both products, both chips, REPS boots, is
# capacity.sh's; nothing about the instrument changed this session. Every
# earlier row in the decision table is S19's and stays S19's -- re-measuring
# `blk_*`, `s16_*` and `s18_*` would be re-measuring the same instrument on the
# same bench on the same day.
#
# THE BITSTREAM IS PART OF THE INSTRUMENT: `./loadlogic.sh driveall` must have
# been run, and `./loadlogic.sh shipping` must be run afterwards. This script
# does neither, deliberately -- a CPLD flash is not something a measurement
# loop should do behind the operator.
#
#   ./s20matrix.sh                      both arms, both products, 2 boots
#   ARMS=s20 PRODUCTS=d32 ./s20matrix.sh
#   REPS=1 DWELL=30 ./s20matrix.sh
set -u
cd "$(dirname "$0")"

ARMS="${ARMS:-s20 s20f}"
PRODUCTS="${PRODUCTS:-d24 d32}"
REPS="${REPS:-2}"
DWELL="${DWELL:-30}"
WORK="${WORK:-/tmp/dspcap}"
CONFIG="${CONFIG:-shipping.config.s20}"

flags_for() {
    case "$1" in
        s20)  echo "" ;;
        # The pipelined SIMD sample loop: bit-exact against the unpipelined
        # loop by construction (same operations, same operands, same order of
        # additions), ~5 points of chip 2. shipping.config.s20 names it at 0
        # and names this arm as where it is measured.
        s20f) echo "DSP4_BQ_SIMD_PIPE=2" ;;
        *)    echo "UNKNOWN" ;;
    esac
}

for arm in $ARMS; do
    F="$(flags_for "$arm")"
    [ "$F" = "UNKNOWN" ] && { echo "unknown arm $arm" >&2; exit 2; }
    D="$WORK/$arm"
    if [ ! -f "$D/chip1.ldr" ]; then
        echo "=== building $arm ($CONFIG${F:+ + $F})"
        env $F SHIPPING_CONFIG="$PWD/$CONFIG" DSP_BUILD_DIR="$D" \
            ./build.sh all > "$D.log" 2>&1 || {
            echo "BUILD FAILED — $D.log"; exit 1; }
    fi
    echo "=== arm $arm  $(md5sum $D/chip1.ldr | cut -c1-8) / $(md5sum $D/chip2.ldr | cut -c1-8)  [$CONFIG${F:+ + $F}]"
    for prod in $PRODUCTS; do
        echo "--- $arm / $prod"
        env $F SHIPPING_CONFIG="$PWD/$CONFIG" \
            BUILD=0 ARM="$arm" PRODUCT="$prod" REPS="$REPS" DWELL="$DWELL" \
            ./capacity.sh --driven || echo "!!! $arm/$prod FAILED"
    done
done
echo "=== matrix done; goldens/cap-s20*-{A,B,C}*.json"
