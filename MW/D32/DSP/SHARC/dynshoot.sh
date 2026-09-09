#!/bin/bash
# dynshoot.sh — THE DYNAMICS GAIN-COMPUTER SHOOTOUT (S14, 2026-09-09).
#
# Fourteen rungs of ONE loop nest (bq_probe.asm's harness) against the
# same envelope and the same gain application, so what differs between
# them is the GAIN COMPUTER:
#
#   1        the envelope + attack/release one-pole
#   2  3     the gain computer TODAY (6-term polynomial log2/knee/exp2)
#            and the same with 3-term polynomials
#   4  5  6  ONE level->gain table, the whole static curve baked in by a
#            DESIGN step, three ways round the shared-DAG gather: PEYEN
#            down for the gather over DM; the same over DM and PM in one
#            instruction; the whole computer unpaired
#   7  8     LOG2Q_SIMD alone (what the paired GATE pays today) and
#            MRF_RNS28_SIMD alone
#   9  10    the WHOLE compressor per-sample body, today and with the LUT
#   11 12 13 the WHOLE gate per-sample body: today, with the LINEAR-domain
#            threshold, and with the level->gain table
#
# WHY. PW, 2026-09-09: "other processing progress is leaving dynamics
# processing as a hog, so it's a priority to address", and "the compressor
# and gate cycles could be improved a lot, using LUTs with interpolation,
# and still fit the SIMD structure", and "the envelope and knee become
# part of the LUT graph" -- against a ruling that the dynamics accuracy
# target is 0.1 dB worst case over 0 to -100 dBFS, not the polynomial's
# 0.0001 dB.
#
# Standalone rig: no graph integration, no contract edit, the shipping
# image untouched. Cycles are per SAMPLE for a PAIR of channels; the
# per-channel column is half.
#
#   ./dynshoot.sh
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
ROOT=../../../..
# Default to the SHIPPING block size rather than a literal. shipping.config
# is the one place it is named; a literal here is how a measurement ends up
# taken at a block size the product does not run (findings S8-2).
BLOCK="${BLOCK:-$(python3 "$(dirname "$0")/../../../../tools/dsp/build_config.py" DSP4_GEN_BLOCK)}"
WORK="${WORK:-/tmp/dynshoot}"
source ./bench_lock.sh; bench_lock_acquire "$0"
mkdir -p "$WORK"

# BLOCK != 8 is built from a SCRATCH TREE generated with DSP4_GEN_BLOCK,
# keyed on its inputs so a stale tree cannot be built from -- sigprofile2's
# rule, and gainprof.sh's copy of it.
srckey() {
    {   echo "block=$1"
        sha256sum "$PWD/dsp.csv" "$ROOT/tools/dsp/dsp_codegen.py"
        find "$PWD/src" -type f ! -name .srckey -print0 \
            | LC_ALL=C sort -z | xargs -0 sha256sum
    } | sha256sum | cut -c1-16
}
srctree() {
    # THE REPO TREE IS THE SHIPPING CONFIGURATION, whatever that is today.
    # This used to read `if [ "$1" = "8" ]`, which was a literal copy of the
    # then-current block size; when the tree moved to block 16 on 2026-09-09
    # it would have handed back a block-16 tree for a block-8 measurement.
    # Ask the tree what it is (dsp_block.h is generated and carries it).
    local _treeblk
    _treeblk="$(sed -n 's/^#define DSP4_BLOCK_SIZE  *\([0-9][0-9]*\).*/\1/p' \
                    "$PWD/src/dsp_block.h" | head -1)"
    if [ "$1" = "$_treeblk" ]; then echo "$PWD/src"; return; fi
    local k t
    k="$(srckey "$1")"
    t="$WORK/src$1-$k"
    if [ "$(cat "$t/.srckey" 2>/dev/null)" != "$k" ]; then
        rm -rf "$t"; cp -r "$PWD/src" "$t"; rm -f "$t/.srckey"
        DSP4_GEN_BLOCK=$1 python3 $ROOT/tools/dsp/dsp_codegen.py \
            "$PWD/dsp.csv" "$t" --force >/dev/null 2>&1
        if ! grep -q "define DSP4_BLOCK_SIZE   $1\$" "$t/dsp_block.h"; then
            echo "srctree: generated tree for block $1 does not say so" >&2
            exit 5
        fi
        echo "$k" > "$t/.srckey"
    fi
    echo "$t"
}
SRC="$(srctree "$BLOCK")"
D="$WORK/b$BLOCK"

DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
DSP4_BISECT=0 DSP4_DYN_SHOOTOUT=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 \
DSP4_STRIPS=2 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 "$D.log"; exit 1; fi
echo "  block $BLOCK  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_dyn_shoot.py $BENCH:/home/app/dspboot/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:/home/app/dspboot/
scp -q dynshoot_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/dynshoot_run.sh"
