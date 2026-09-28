#!/usr/bin/env bash
# build-images.sh — rebuild S146's DSP4 image arms and GATE them on md5.
#
# The `.ldr` files are not committed (nothing in this repo has ever tracked a
# .dxe/.ldr/.doj), so the window reproduces them instead of fetching them.
# That is only safe if "reproduces" means BYTE-IDENTICAL, so this script
# refuses to leave an arm in place whose md5 is not the one S146 priced.
#
# Arm A is the only arm the S146 window loads. B, C and D are built so that
# the decisions that need them (PW's DSP4_C2_BQ_GRAPH signature, a
# factory-test-v3, bench row 11) cost no rebuild.
#
#   ./build-images.sh            # all four arms, each gated
#   ./build-images.sh A          # just the shipping arm
#
# Provenance this was priced at (MW/D24/DSP/s146/switch-runbook.md §2.2):
#   git HEAD                24cb19ff2944f8a63de2d7104d1951656aa08f6d
#   src tree sha256         b0ebdd705406c6819aeb1c923a223eea89fbc68d4605e55d28219bc3a81dee29
#   check-sharc-codegen-drift.sh   757 generated / 0 differ

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SHARC="$ROOT/MW/D32/DSP/SHARC"

# arm | build dir suffix | extra build flags | chip1.ldr md5 | chip2.ldr md5
ARMS=(
"A|bq0|                                  |1be74e042cff134c7085dfb08dade517|2bddaa05367887eb2a349cde7b3d5055"
"B|bq1|DSP4_C2_BQ_GRAPH=1                |6d7b86ec69778900ce63b9eb79c144ea|e76d2dc8463292a2ba2f6b9172cb6be5"
"C|tn |DSP4_TEST_NODES=1                 |7f226919a5d181410c3804d92678da19|d97645bfb800290b8f998924d939361c"
"D|rta|DSP4_RTA=1 DSP4_CUE=1             |a026897ff6fd33654733f85c077599d6|ebf2fea4cca2f740cd560b1155134cc3"
)

want="${1:-ALL}"
rc=0

for row in "${ARMS[@]}"; do
    IFS='|' read -r arm suf flags m1 m2 <<<"$row"
    suf="${suf// /}"; flags="$(echo "$flags")"
    [ "$want" = "ALL" ] || [ "$want" = "$arm" ] || continue

    dir="$SHARC/build_s146_$suf"
    echo "=== arm $arm  ($suf)  ${flags:-shipping.config as it stands}"
    ( cd "$SHARC" && env $flags DSP_BUILD_DIR="$dir" ./build.sh all >"$dir.log" 2>&1 ) || {
        echo "  BUILD FAILED — see $dir.log"; rc=1; continue; }

    for c in 1 2; do
        python3 "$ROOT/tools/dsp/map_syms.py" "$dir/chip$c.map.xml" > "$dir/chip$c.sym.json"
    done

    g1="$(md5sum "$dir/chip1.ldr" | cut -d' ' -f1)"
    g2="$(md5sum "$dir/chip2.ldr" | cut -d' ' -f1)"
    if [ "$g1" = "$m1" ] && [ "$g2" = "$m2" ]; then
        echo "  OK  chip1 $g1  chip2 $g2"
    else
        echo "  *** MD5 MISMATCH — THIS IS NOT THE TREE S146 PRICED ***"
        echo "      chip1 got $g1 want $m1"
        echo "      chip2 got $g2 want $m2"
        echo "      Check: git rev-parse HEAD, git status --porcelain,"
        echo "             ./check-sharc-codegen-drift.sh"
        rc=1
    fi
done

echo
if [ $rc -eq 0 ]; then
    echo "every arm built reproduces its recorded image byte for byte"
else
    echo "AT LEAST ONE ARM DID NOT REPRODUCE — do not stage it"
fi
exit $rc
