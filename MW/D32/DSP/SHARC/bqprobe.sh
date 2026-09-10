#!/bin/bash
# bqprobe.sh — THE PER-INSTRUCTION CYCLE PROBE (S14, 2026-09-09).
#
# Twenty-two rungs of ONE loop nest — 28 outer x 15 inner, the pipelined
# biquad kernel's own trip counts — whose inner body is the only thing
# that differs between them. Rungs 0-3 are 2/3/5/8 nops; rungs 4-8 build
# the shipping pipelined body up one instruction at a time; 9-17 take it
# apart (dependences broken, memory deleted, PM instead of DM, the raw
# per-unit result latencies, PEYEN off); 18-19 do the same for the OLD
# eight-instruction loop; 20-21 price the loop nest and the real per-stage
# prologue.
#
# WHY. S13-5 pipelined the loop 8 instructions to 5, bit-exact (bqeverify
# 0 ULP, same hash), and the GEQ pair moved 5,983 -> 5,655 cycles/block:
# 5.5 % where the instruction count predicted 25 %. Instruction count is
# not the binding resource and the 3.75 c/band-sample target's premise is
# invalid. This measures what IS.
#
# THERE IS NO DOCUMENT TO READ INSTEAD. The ADSP-2156x SHARC+ Hardware
# Reference (Rev 1.0, Dec 2020) has no core chapter: zero occurrences of
# "pipeline stage" or "Instruction Pipeline", and every "stall" in its
# 101,300 lines is peripheral flow control. It states neither the pipeline
# depth nor how many cycles a compute result takes before a dependent
# instruction can read it. The part is the document.
#
# Standalone rig: no graph integration, no contract edit, the shipping
# image untouched. Read the DELTAS, not the absolute column.
#
#   ./bqprobe.sh            # the repo tree's block size
#   BLOCK=8 ./bqprobe.sh    # a scratch tree at block 8
set -u
cd "$(dirname "$0")"
BENCH=app@192.168.1.219
# THE SHARED SCRATCH SLOT, NAMED (S16-9). ~/dspboot/chip{1,2}.ldr is not a
# staged pair -- it is whatever the last measurement run left there, and this
# script overwrites it. The staged pairs are the PREFIXED ones (blk_*, cand_*,
# geq_*, dyn_*, flr_*, conf_*, ship_*, tx_*, s16_*) and nothing here writes
# those. STAGE names a directory of this run's own when the image must survive
# the next script; it defaults to the scratch slot so nothing that calls this
# changes behaviour.
STAGE="${STAGE:-/home/app/dspboot}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports. Symlinked, not copied, so there is one working set and a
# staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi
ROOT=../../../..
# Default to the SHIPPING block size rather than a literal. shipping.config
# is the one place it is named; a literal here is how a measurement ends up
# taken at a block size the product does not run (findings S8-2).
BLOCK="${BLOCK:-$(python3 "$(dirname "$0")/../../../../tools/dsp/build_config.py" DSP4_GEN_BLOCK)}"
WORK="${WORK:-/tmp/bqprobe}"
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
DSP4_BISECT=0 DSP4_BQ_PROBE=1 DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 \
DSP4_STRIPS=2 DSP4_BLOCK_KERNELS=1 \
  ./build.sh > "$D.log" 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
  echo "BUILD FAILED"; tail -30 "$D.log"; exit 1; fi
echo "  block $BLOCK  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"

python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
    $ROOT/tools/pi/dsp4_bq_probe.py $BENCH:$STAGE/
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q bqprobe_run.sh $BENCH:/home/app/
ssh $BENCH "STAGE='$STAGE' bash /home/app/bqprobe_run.sh"
