#!/bin/bash
# famverify.sh — every D24 kernel family on the part, addressed through the
# LANDED contract (`defs/products/d24/dsp.csv`).
#
# THE SHIPPING FLOAT CONFIGURATION, like goldnode.sh and conform.sh: plain
# ./build.sh, which is DSP4_BQ_FLOAT=1 / DSP4_GAIN_FLOAT=1 by default. That
# makes the build its own W0 check — this bar changes no source that
# reaches an image, so the md5 printed below must equal the baseline the
# session started from.
#
# The contract is staged as JSON because the bench has no `defs` checkout.
# tools/dsp/landed_map.py writes it, carrying the defs.lock pin and the
# sha256 of the CSV, so a bench run cannot quietly score against a
# different contract than the one this tree is on.
#
#   ./famverify.sh                        every family, both chips
#   FAMILIES=GATE,COMP ./famverify.sh     just those
#   CHIPS=1 ./famverify.sh                chip 1 only
#   BUILD=0 ./famverify.sh                reuse whatever is already staged
#   N=32 ./famverify.sh                   shorter captures
#   DSP4_SCOPE_BLK_TAP=0 ./famverify.sh   the pre-S10 witness (see below)
set -u
cd "$(dirname "$0")"
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
ROOT=../../../..
# WHERE THIS RUN'S IMAGES LIVE ON THE BENCH.
#
# ~/dspboot holds the staged pairs the window rolls back to. They are the
# PREFIXED ones -- blk_* (the shipping pair), cand_*, geq_*, dyn_*, flr_*,
# conf_*, ship_*, tx_* -- and nothing here writes those.
#
# `chip1.ldr` / `chip2.ldr` ARE NOT ONE OF THEM. This header used to call
# them "the window pair" while some thirty measurement scripts in this
# directory scp their build straight over them, and both cannot be true.
# CHECKED ON THE PART, 2026-09-10 (S16-7): those two files were
# 08d0b9a4 / 6a349c13, which is no staged pair at all -- it is whatever
# the last measurement run left there. They are the SHARED SCRATCH SLOT
# that dsp4_boot.py boots by default (`--dir <d>` reads <d>/chipN.ldr),
# and treating them as an artifact is what made this bar look dangerous
# when it is not.
#
# What DOES protect the artifacts is the prefix, and what protects two
# concurrent runs from each other is bench_lock.sh above. STAGE is still
# useful -- a run that wants its image to survive the next script names
# its own directory -- and it stays defaulted to /home/app/dspboot so
# nothing that calls this changes behaviour.
STAGE="${STAGE:-/home/app/dspboot}"
PRODUCT="${PRODUCT:-d24}"
OUT="${OUT:-famverify-$(date +%Y%m%d-%H%M).json}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports (dsp4_scope/dsp4_diag/dsp4_config/gainfix). Symlinked, not
# copied, so there is one working set and a staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi

# THE BLOCK-AWARE WITNESS IS PART OF THIS BAR (S11-5, 2026-09-09).
#
# S10 settled S9-5 with `DSP4_SCOPE_BLK_TAP=1` -- a `_scope_tap` call emitted
# after every node in the generated chain, carrying that node's identity and
# where its block ACTUALLY is, because under block kernels a pooled node's
# `_buf_<node>` is a one-word `.var` nothing writes. It recorded the shipping
# configuration at 17 of 20 families LIVE. This script never set the switch,
# so the BAR read the same image at NINE, with COMPRESSOR/FADER_PAN/TUBE_SAT
# reading INERT and COMPRESSOR's numeric arm FAILED -- measured both ways on
# 2026-09-09, same tree, one variable. A bar that scores the shipping image
# eight families below the record is not a bar.
#
# So it defaults ON. This script already builds its own image and stages it
# away from ~/dspboot; the tap is an instrument in a measurement build, and
# `DSP4_SCOPE_BLK_TAP=0` is the control that reproduces the old reading.
#
# IT FITS ALONGSIDE THE PAIRED KERNELS AGAIN (S16-2, 2026-09-10). It did
# not when this was written: DSP4_SCOPE_BLK_TAP=1 with both
# DSP4_STRIP_FUSED=1 and DSP4_SIMD_DYN=1 overflowed chip 1's `sec_swco`,
# which is why the fused/SIMD lever was certified one half at a time
# (S11-4). Two things changed. The LDF grew a THIRD code tier into
# Block 1's leftover (sec_swco_ovf2, 2026-09-09), and build.sh now
# CHOOSES what goes into it -- DSP4_COLD_OBJS puts the boot, config and
# design-step objects there and keeps every per-block kernel in Blocks 3
# and 2. Measured on the DSP4_DYN_LUT arm plus this witness: it links
# with 8 bytes to spare in Block 2 and 7,702 bytes of cold code in
# Block 1, and the whole 20-family walk runs.
#
# The tap is still an INSTRUMENT: some of its own code is in the
# contended block by design, and no capacity number is taken from an
# image built with it.
export DSP4_SCOPE_BLK_TAP="${DSP4_SCOPE_BLK_TAP:-1}"

if [ "${BUILD:-1}" = "1" ]; then
  ./build.sh > /tmp/famverify_build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/famverify_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' /tmp/famverify_build.log | head; exit 1; fi
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1)
  C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  echo "  image: chip1.ldr ${C1:0:8} chip2.ldr ${C2:0:8}  (shipping float configuration)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json /tmp/chip2.sym.json \
      $BENCH:$STAGE/ || exit 3
fi

# THE CONTRACT ITSELF, staged. Not a copy of the addresses — the file.
python3 $ROOT/tools/dsp/landed_map.py --product "$PRODUCT" \
        --json /tmp/landed-$PRODUCT.json || exit 3

# THE BLOCK FILE COMES FROM THE TREE THAT WAS BUILT, not from tools/pi
# (review D49, and conform.sh/busgold.sh already do this). With the block
# size a build parameter, staging the repo copy labels a bench run with a
# block size the image on the part may not have.
BLOCKPY="${DSP_SRC_DIR:-$PWD/src}/dsp4_block.py"
[ -f "$BLOCKPY" ] || BLOCKPY="$ROOT/tools/pi/dsp4_block.py"
scp -q $ROOT/tools/pi/dsp4_family_verify.py $ROOT/tools/pi/dsp4_node_verify.py \
    $ROOT/tools/pi/dsp4_conform.py "$BLOCKPY" \
    $ROOT/tools/dsp/fixed_ref.py $ROOT/tools/dsp/boundary_vectors.py \
    /tmp/landed-$PRODUCT.json \
    $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q famverify_run.sh $BENCH:/home/app/ || exit 3

ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT FAMILIES='${FAMILIES:-}' CHIPS='${CHIPS:-1,2}' \
            N='${N:-64}' OUT='$OUT' BQ_ARM='${BQ_ARM:-float}' \
            bash /home/app/famverify_run.sh"
RC=$?
scp -q $BENCH:$STAGE/$OUT ./goldens/$OUT 2>/dev/null \
  && echo "  report: goldens/$OUT"
exit $RC
