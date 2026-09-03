#!/bin/bash
# bqeverify.sh — is the ROUND-ONCE cascade kernel the round-once ARITHMETIC,
# on the part, over the DEFS curve set?
#
# RIG C (2026-09-02) left this open in as many words: "C.E is TIMED, NOT
# VALIDATED -- the ladder runs zeroed banks, and the bit-identity claim is
# measured on the PYTHON model, not on _bqe_cascade_simd; a diff of the
# kernel against fixed_ref is the next bar and does not exist." This is
# that bar, and it is the gate for landing the saturate deletion.
#
# tools/dsp/gen_bqe_vectors.py emits 192 four-stage cascades -- the named
# worst cases from the state-bound work plus a stratified sample of the
# DEFS design space -- at three drive levels over four consecutive blocks,
# and computes BOTH arms from fixed_ref. src/lib/bqe_verify.asm runs both
# kernels over the same words inside the DSP, diffs them on-chip, and
# hashes each arm's whole output stream.
#
#   ./bqeverify.sh           both arms (the default question)
#   ./bqeverify.sh 0         CONTROL only: arm A is the saturating contract
#   ./bqeverify.sh 1         LANDED only: arm A is the round-once kernel
#   BLOCK=16 ./bqeverify.sh  at the working operating point
#
# TWO BUILDS, AND BOTH ARE THE BAR.
#
#   DSP4_BQ_ROUNDONCE=0   arm A is today's per-stage-saturating kernel. It
#                         must hash to fixed_ref.biquad, arm B must hash to
#                         the round-once model, and the two must diverge on
#                         EXACTLY the (cascade, level) cells the model says
#                         overflow -- 29 of 576 on this set, all of them hot
#                         cascades at 0 dBFS. That is the 0-ULP identity
#                         claim, stated so that it can fail.
#   DSP4_BQ_ROUNDONCE=1   arm A is the LANDED kernel. Zero differing words,
#                         and both arms hash to the round-once model.
#
# A one-sided bar ("assert zero differences") would pass on a rig that
# never drove anything hard enough to saturate -- which is exactly what the
# zeroed-bank ladder did -- so the divergence bitmap is checked cell by
# cell, not just counted.
#
# BOTH ARMS ARE BUILT WITH DSP4_BQ_GUARD=0, and that is deliberate rather
# than incidental. This bar's question is whether the round-once
# ARITHMETIC is the round-once model, and the guard is a separate
# question with its own bar (bqguard.sh) -- which checks the guarded
# kernel word for word against the same model, over its own vectors, and
# with H sized by the part. Building the guard in here would also not
# fit: the shootout ladder, the verify rig and the guard together
# overflow sec_swco on chip 1, and a debug instrument is the wrong place
# to spend the last of chip 1's PM.
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
BLOCK="${BLOCK:-8}"
NCAS="${NCAS:-192}"
WORK="${WORK:-/tmp/bqeverify}"
MODE="${1:-both}"
mkdir -p "$WORK"

# BLOCK != 8 is built from a SCRATCH TREE generated with DSP4_GEN_BLOCK,
# keyed on its inputs so a stale tree cannot be built from -- bqshoot.sh's
# rule, and sigprofile2's before it.
srckey() {
    {   echo "block=$1"
        sha256sum "$PWD/dsp.csv" "$ROOT/tools/dsp/dsp_codegen.py"
        find "$PWD/src" -type f ! -name .srckey ! -name bqe_vectors.h \
             -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
    } | sha256sum | cut -c1-16
}
srctree() {
    if [ "$1" = "8" ]; then echo "$PWD/src"; return; fi
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

# The vectors and the reference come out of ONE generator run, so the table
# the part holds and the results the host scores against cannot drift apart.
python3 $ROOT/tools/dsp/gen_bqe_vectors.py --block "$BLOCK" --ncas "$NCAS" \
    --out "$SRC/lib/bqe_vectors.h" --json "$WORK/bqe_vectors.json" || exit 4

run_arm() {   # $1 = DSP4_BQ_ROUNDONCE
    local ro="$1" D="$WORK/b$BLOCK-ro$1"
    echo "=== DSP4_BQ_ROUNDONCE=$ro"
    DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
    DSP4_BISECT=0 DSP4_BQ_SHOOTOUT=1 DSP4_BQE_VERIFY=1 DSP4_BQ_ROUNDONCE=$ro \
    DSP4_BQ_GUARD=0 \
    DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_STRIPS=2 DSP4_BLOCK_KERNELS=1 \
      ./build.sh > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
      echo "BUILD FAILED"; grep -iE '\[Error' "$D.log" | head -20; return 1; fi
    echo "  block $BLOCK  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
    python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > /tmp/chip1.sym.json
    scp -q "$D/chip1.ldr" "$D/chip2.ldr" /tmp/chip1.sym.json \
        "$WORK/bqe_vectors.json" \
        $ROOT/tools/pi/dsp4_bqe_verify.py $BENCH:/home/app/dspboot/
    scp -q bqeverify_run.sh $BENCH:/home/app/
    ssh $BENCH "bash /home/app/bqeverify_run.sh $ro"
}

rc=0
if [ "$MODE" = both ] || [ "$MODE" = 0 ]; then run_arm 0 || rc=1; fi
if [ "$MODE" = both ] || [ "$MODE" = 1 ]; then echo; run_arm 1 || rc=1; fi
exit $rc
