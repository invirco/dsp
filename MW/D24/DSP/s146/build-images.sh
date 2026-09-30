#!/usr/bin/env bash
# build-images.sh — rebuild S146's DSP4 image arms and GATE them on md5.
#
# The `.ldr` files are not committed (nothing in this repo has ever tracked a
# .dxe/.ldr/.doj), so the window reproduces them instead of fetching them.
# That is only safe if "reproduces" means BYTE-IDENTICAL, so this script
# refuses to leave an arm in place whose md5 is not the one S146 priced.
#
# Arm A and arm B are fixed BYTE-CONTENT identities (S146), not "shipping.
# config as it stands" -- A is the DSP4_C2_BQ_GRAPH=0 image, B is the
# DSP4_C2_BQ_GRAPH=1 image. Which one needs the env override moves with
# shipping.config's own default, and it just did: S147 (PW, 2026-09-29,
# "sign BQ_GRAPH") landed DSP4_C2_BQ_GRAPH=1 IN shipping.config, so B is now
# what shipping.config builds unadorned and A now needs the explicit
# DSP4_C2_BQ_GRAPH=0 override to reproduce -- the two rows' flags swapped
# accordingly, their recorded md5s did not. B ships (switch-runbook.md); A
# is kept as the fallback/rollback arm, still staged. C and D still cost no
# rebuild for the decisions that need them (factory-test-v3, bench row 11).
#
#   ./build-images.sh            # all four arms, each gated
#   ./build-images.sh B          # just the shipping arm
#
# Provenance the CURRENT md5s were taken at (S150, 2026-09-29):
#   git HEAD                (this commit)
#   check-sharc-codegen-drift.sh   760 generated / 0 differ
#
# S150 BUILT THE AUX MATRIX AND MOVED NOT ONE OF THESE FOUR MD5s. The switch
# it added (DSP4_C2_AUX_MTX) defaults OFF, because its 360 crosspoint words
# are proposed and not yet landed at the hub gate, so all four arms rebuild
# the images S149 recorded BYTE FOR BYTE on both chips. Arm M below is the
# matrix arm and it is the one that moves.
#
# Provenance of the four before that (S149, 2026-09-29):
#   git HEAD                00663c581c75e8090c36ea70c21659d3b59d1315
#   src tree sha256         567b5e8a22f7b4555059f2f3a0b77c15f87d1ece2d992ff4183f8c732fb7f075
#   check-sharc-codegen-drift.sh   759 generated / 0 differ
#
# Superseded (S146/S147/S148 provenance, before S149's three chip-2 items):
#   git HEAD                24cb19ff2944f8a63de2d7104d1951656aa08f6d
#   src tree sha256         b0ebdd705406c6819aeb1c923a223eea89fbc68d4605e55d28219bc3a81dee29
#   check-sharc-codegen-drift.sh   757 generated / 0 differ

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SHARC="$ROOT/MW/D32/DSP/SHARC"

# UPDATED S149 (2026-09-29). Three chip-2 items landed between S148 and this
# row: the live-crosspoint mix fabric (DSP4_C2_MIX_FABRIC, PW-approved L1),
# the follower pairing (L2) and PW's reverb cap (DSP4_FX_REVERB_CAP=3). All
# three default ON in shipping.config, so EVERY arm's chip-2 image moved and
# the md5s below are re-recorded.
#
# EVERY ARM'S CHIP-1 MD5 IS UNCHANGED, and that is not luck: all three items
# are chip-2 only (mix_fabric.asm and fx_cap.asm live in src/chip2/, and
# chip 1 has neither a chip-2 mix bus nor an FX engine). It is also the
# cheapest available check that the blast radius is what S149 says it is --
# four independent builds, four unmoved chip-1 images.
#
# Superseded chip-2 md5s (S148 provenance, before S149's items):
#   A  2bddaa05367887eb2a349cde7b3d5055    B  e76d2dc8463292a2ba2f6b9172cb6be5
#   C  8674f98fdf2975b974c8fc83430c4240    D  edbdb100e7fb60b14e0e5285b156471c
# Superseded before that (pre-S147 default, DSP4_C2_BQ_GRAPH=0), C and D only:
#   C  chip1 7f226919a5d181410c3804d92678da19  chip2 d97645bfb800290b8f998924d939361c
#   D  chip1 a026897ff6fd33654733f85c077599d6  chip2 ebf2fea4cca2f740cd560b1155134cc3
#
# arm | build dir suffix | extra build flags | chip1.ldr md5 | chip2.ldr md5
# S154 (2026-09-30) MOVED ALL FOUR ARMS ON BOTH CHIPS, and no flag moved, so
# the triples do not. Chip 1: the pan law boots at law 2 (stereo constant
# power, PW ruling 2026-09-30) and carries a third resident table. Chip 2:
# C2_MAIN_COMP, C2_MAIN_LIM and C2_MAIN_OCOMP_01/02 -- uncelled, and booted ON
# -- boot OFF. Arm C is factory-test-v4, deployed on MW-D24-2. ARM B, THE
# SHIPPING ARM, IS RE-RECORDED HERE AND NOT RE-SIGNED: signing it is PW's.
# Superseded (S150 provenance, before S154):
#   A  1be74e042cff134c7085dfb08dade517 / e2de920d22edbbe76c1210a737abf6b7
#   B  6d7b86ec69778900ce63b9eb79c144ea / 0a460926f8a2c9088bc0bc509f30769e
#   C  c031613ac9a0a02e4c1d493bea19765d / 0b63f4e044e00e4a7cbe7b2ff345c0b6
#   D  c9bf6659fd888626465932c3814adb5f / c1d9f5db83bad18b78c000178a49191b
ARMS=(
"A|bq0|DSP4_C2_BQ_GRAPH=0                |00eb01a39a55e69ab60cb3e7909fcbba|f7ddc3283df74add7b47b2f7f05d6dfb"
"B|bq1|                                  |06e167fb005dfd6ed227bcf8287d2f90|2b99eb447b6e83ae953b87974eb2dca0"
"C|tn |DSP4_TEST_NODES=1                 |7caa1bf46f4b325c39d60b7df2fe93e1|4a9406ed755e8bc0d02ac9937c70590f"
"D|rta|DSP4_RTA=1 DSP4_CUE=1             |5c6161d5d167197fdfa303f2f4ccdb86|7e031c6377db4dceccd716ef5a37ee95"
)

# ---- ARM M: THE AUX MATRIX (S150) --------------------------------------
#
# NOT one of the four, and it is built differently, because it cannot be
# built the same way. `DSP4_C2_AUX_MTX=1` needs a dispatch table that has
# addresses for the 360 crosspoint words, and those are PROPOSED and not
# landed -- `MW/D32/DSP/SHARC/src/chip*/dsp_params.asm` tracks the LANDED
# contract and correctly does not have them. So this arm is built out of a
# SCRATCH copy of src/ with the GRAPH's own dispatch tables dropped in, via
# gen_dsp.py --params-dir, which is exactly what that flag exists for: it
# answers "does the graph assemble, link and fit" while the proposal is in
# flight, and it never writes into the tree.
#
# SAME BYTES, DIFFERENT PROVENANCE. Nothing has gated these rows and the
# defs pin does not describe this image. It is a desk image: do not stage
# it, do not sign it. When the hub lands the proposal and the pin advances,
# this becomes an ordinary arm -- and then the SHIPPING arm, if PW says so.
#
# Chip 1's image differs from arm B's in EXACTLY ONE CONSTANT, the
# DIAG_BUILD_CFG3 instrument bit: the matrix is chip-2 code and chip 1 has
# no aux sum. Chip 2: code 177,958 (67.9 %), DM 346,732 (92.4 % — OVER the
# 90 % warn line, see the S150 report), delay 1,886,112 (91.0 %, unmoved).
ARM_M_C1=e549e1fad764c790d272337f8b8a0f85
ARM_M_C2=a317906713e9a11f193d98db94295f0c

want="${1:-ALL}"
rc=0

if [ "$want" = "M" ]; then
    scratch="$SHARC/build_s150_mtx"
    src="$SHARC/src_s150_mtx"
    echo "=== arm M  (the aux matrix, DSP4_C2_AUX_MTX=1, GRAPH provenance)"
    rm -rf "$src" "$scratch"
    python3 "$ROOT/MW/D32/DSP/gen_dsp.py" --force --propose \
        --params-dir "$SHARC/params_s150_mtx" >/dev/null 2>&1 || true
    cp -a "$SHARC/src" "$src"
    cp "$SHARC/params_s150_mtx/chip1/dsp_params.asm" "$src/chip1/"
    cp "$SHARC/params_s150_mtx/chip2/dsp_params.asm" "$src/chip2/"
    ( cd "$SHARC" && env DSP4_C2_AUX_MTX=1 DSP_SRC_DIR="$src" \
        DSP_BUILD_DIR="$scratch" ./build.sh all >"$scratch.log" 2>&1 ) || {
        echo "  BUILD FAILED — see $scratch.log"; exit 1; }
    g1="$(md5sum "$scratch/chip1.ldr" | cut -d' ' -f1)"
    g2="$(md5sum "$scratch/chip2.ldr" | cut -d' ' -f1)"
    if [ "$g1" = "$ARM_M_C1" ] && [ "$g2" = "$ARM_M_C2" ]; then
        echo "  OK  chip1 $g1  chip2 $g2"
        echo "  (desk image: the crosspoint addresses are PROPOSED, not landed)"
        exit 0
    fi
    echo "  *** MD5 MISMATCH ***"
    echo "      chip1 got $g1 want $ARM_M_C1"
    echo "      chip2 got $g2 want $ARM_M_C2"
    exit 1
fi

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
