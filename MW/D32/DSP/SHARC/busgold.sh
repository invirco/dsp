#!/bin/bash
# busgold.sh — hold the efficiency batch to a STORED bus capture.
#
# Every item in the D20-D25 efficiency batch is bit-exact BY CONSTRUCTION:
# each one deletes work that had no effect on a sample, or moves work to a
# rate at which it produces the same answer. A claim of that shape is
# testable with one instrument -- capture the main bus out of a running
# graph and require it to reproduce, word for word, the capture the code
# produced before the batch.
#
#   goldens/busgraph-postD59-20260830.json      <- THE CURRENT GOLDEN
#       taken 2026-08-30 (session 6) with CompPar's default at 100 %,
#       DSP4_BLOCK_KERNELS=1, DSP4_STRIPS=2, strip 1 driven and strip 2
#       muted, 256 consecutive words of _buf_C1_BUS_MAIN_L.
#       sha256 ba3f52ec...
#
#   goldens/busgraph-postD40-20260830.json      <- RETIRED, kept as evidence
#       the same capture with CompPar's default at 0, on the tree at
#       7afe947 (session 4's last commit). sha256 a2f1a00a...
#
#   goldens/busgraph-prebatch-20260829.json     <- RETIRED, kept as evidence
#       the same capture on the tree at 87fded2. sha256 811af470...
#
# WHY THERE ARE TWO, AND WHY THE BAR WAS SILENTLY UNRUNNABLE FOR A SESSION
# (review finding D58). Session 4's D39/D40 unit fixes changed the AUDIO by
# design -- CompPar went from a word that made the compressor fully wet to
# a percentage whose default is 0, so a default strip's compressor became
# DRY, and GateRng went from an encoding that produced no attenuation at
# all to real decibels. The stored golden predates both, and session 4 did
# not re-run this bar or re-baseline it. Bisected on the part 2026-08-30,
# three points, same instrument, same bench session:
#
#     241b7d2 (immediately before D39/D40)  sha256 811af470  0 of 256 differ
#     7afe947 (session 4's HEAD)            sha256 a2f1a00a  62 of 256
#     session 5 HEAD                        sha256 a2f1a00a  62 of 256
#
# The last line is the useful one: session 5's wide-word metering, its D55
# fix and its paired biquads produce a bus capture BYTE-IDENTICAL to the
# tree they were built on. The 62 words are D39/D40's, they are intended,
# and that golden was session 5's re-baseline.
#
# AND IT WAS RE-TAKEN AGAIN ON 2026-08-30 (session 6), IN THE SESSION THAT
# INVALIDATED IT, which is the rule the paragraph above exists to state.
# Review finding D59 moved CompPar's power-on value from 0 to 100 %, so a
# default-configured strip's compressor went from FULLY DRY to fully wet —
# and this bar's harness deliberately does not write CompPar, so the change
# lands in the capture: 234 of 256 words differ against the postD40 golden,
# first at word 22 (0x03FFFFF6 dry vs 0x03E8273B compressed), maxdiff
# 45,807,405. The audio change is the fix; the golden below is this
# session's re-baseline, sha256 ba3f52ec, and the retired one is kept
# beside it.
#
# (D57 landed in the same session and is NOT in those 234 words: the DCA
# cell reaches no audio, proven separately by dcapar.sh — 0 of 32 bus words
# differ between DCA 0 and DCA 1.0.)
#
# 2026-08-30, session 7: PW's Q2 ruling made `Dca`/`DcaOn` HOST-MANAGED, so
# the address is reserved and `dsp4_pairgraph.py` no longer writes it, and
# the `_fdr_dca_gain_` multiply came out of FADER_PAN. Both are predicted
# AUDIO-NEUTRAL — the cell already reached no audio, and x * 1.0 is exactly
# x in IEEE 754 — so `busgraph-postD59-20260830.json` was NOT re-taken. It
# is the CHECK on that prediction rather than a record of it, which is the
# only way a golden can carry weight across a change to the code it
# measures.
#
# The harness is dsp4_pairgraph.py unchanged: it configures both strips over
# SPI with OPPOSITE dynamics settings, so the two lanes sit in opposite arms
# of every predicated branch, and it writes ~20 parameters per strip before
# capturing. That is what gives the comparison the power to fail -- a node
# that stopped noticing a parameter write, or a delay line whose wrap moved
# by one, cannot reproduce the golden.
#
#   ./busgold.sh                 current tree vs the golden
#   GOLD=<file> ./busgold.sh     against a different stored capture
#   TAG=x ./busgold.sh           name the capture (default: cur)
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
# dsp4_block.py IS STAGED FROM THE TREE THIS POINT WAS BUILT FROM, not
# from tools/pi, for captable.sh's reason: the Pi-side scorer must be told
# the block rate the image on the part was actually built with. conform.sh
# checks RAMP TIMINGS, and ramp frame counts are derived from the block
# rate -- so a block-16 image scored against a block-8 dsp4_block.py
# misjudges every ramp. Falls back to tools/pi when DSP_SRC_DIR is unset,
# which is the shipping block-8 tree and the same file.
BLOCKPY="${DSP_SRC_DIR:-$ROOT/MW/D32/DSP/SHARC/src}/dsp4_block.py"
[ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"
ROOT=../../../..
STRIP="${STRIP:-1}"; N="${N:-256}"; STRIPS="${STRIPS:-2}"; TAG="${TAG:-cur}"
GOLD="${GOLD:-goldens/busgraph-postD59-20260830.json}"
OUT=/tmp/busgold; mkdir -p $OUT

DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_STRIPS=$STRIPS \
  DSP4_CTL_ALWAYS=${CTL_ALWAYS:-0} DSP4_CTL_NEGCTL=${CTL_NEGCTL:-0} \
  DSP4_SIMD_DYN=${SIMD:-0} DSP4_STRIP_FUSED=${FUSED:-0} \
  ./build.sh > $OUT/build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
  echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
echo "  $TAG: chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"
python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
    "$BLOCKPY" $ROOT/tools/pi/dsp4_pairgraph.py \
    $BENCH:/home/app/dspboot/
scp -q pairgraph_run.sh $BENCH:/home/app/
ssh $BENCH "bash /home/app/pairgraph_run.sh $STRIP $N $TAG" || exit 4
scp -q $BENCH:/home/app/dspboot/pairgraph_$TAG.json $OUT/ || exit 4
echo "=== vs $GOLD ==="
python3 $ROOT/tools/pi/dsp4_pairgraph.py --compare "$GOLD" $OUT/pairgraph_$TAG.json
