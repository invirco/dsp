#!/bin/bash
# dcapar.sh — the cell-semantics evidence, on the part.
#
# Two contract defects were found on the bench on 2026-08-30 and fixed the
# same day, and both change what a DEFAULT-configured strip does:
#
#   D57  `<Cat>[n]Dca[1-1]` (spelled `RtgDca` before the 2026-08-25 rename)
#        is a DCA ASSIGNMENT and the kernel treated
#        it as a linear gain, so writing the masters' documented "off"
#        value of 0 silenced the channel. SUPERSEDED the same day by PW's
#        Q2 ruling: `Dca`/`DcaOn` are HOST-MANAGED, the CM4 control daemon
#        folds DCA into the fader target it already sends, and the address
#        is RESERVED. The bar now measures that the cell LEFT the wire --
#        the handler rejects the write while its mapped neighbour is
#        accepted, and the bus does not move — which subsumes D57.
#   D59  CompPar's power-on default left the compressor FULLY DRY, so a
#        default strip's compressor threshold was not an audible control.
#
# The probe is written to run against EITHER image so the fix has a
# before. The useful sequence is:
#
#   BUILD=0 ./dcapar.sh          against whatever is already on the bench
#                                (the shipping baseline = the BEFORE run)
#   ./dcapar.sh                  build this tree, stage it, run (AFTER)
#
# It leaves the bench holding the image it last flashed -- restore the
# shipping baseline afterwards, as with every bar in this directory.
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
OUT=/tmp/dcapar; mkdir -p $OUT

if [ "${BUILD:-1}" = "1" ]; then
  # THE SHIPPING CONFIGURATION. Both defects are about what the product
  # does at its defaults, so measuring them on a research build would
  # answer a question nobody asked.
  echo "=== build (shipping configuration) ==="
  ./build.sh > $OUT/build.log 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' $OUT/build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error' $OUT/build.log | head; exit 1; fi
  echo "  chip1.ldr $(md5sum build/chip1.ldr | cut -c1-8) \
chip2.ldr $(md5sum build/chip2.ldr | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > /tmp/chip1.sym.json
  python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > /tmp/chip2.sym.json
  scp -q build/chip1.ldr build/chip2.ldr /tmp/chip1.sym.json \
      /tmp/chip2.sym.json $BENCH:$STAGE/ || exit 3
fi

scp -q $ROOT/tools/pi/dsp4_dcapar_probe.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_block.py $BENCH:$STAGE/ || exit 3
# BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
# with every run, so a bench cannot be left on a stale dsp4_boot.py that
# still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
# every script in here defines one.
scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
scp -q dcapar_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STAGE='$STAGE' STRIP=${STRIP:-1} WORDS=${WORDS:-32} ATTEMPTS=${ATTEMPTS:-5} \
              bash /home/app/dcapar_run.sh"
