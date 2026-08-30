#!/bin/bash
# dcapar.sh — the D57/D59 cell-semantics evidence, on the part.
#
# Two contract defects were found on the bench on 2026-08-30 and fixed the
# same day, and both change what a DEFAULT-configured strip does:
#
#   D57  `<Cat>[n]RtgDca[1-1]` is a DCA ASSIGNMENT and the kernel treated
#        it as a linear gain, so writing the masters' documented "off"
#        value of 0 silenced the channel.
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
      /tmp/chip2.sym.json $BENCH:/home/app/dspboot/ || exit 3
fi

scp -q $ROOT/tools/pi/dsp4_dcapar_probe.py $ROOT/tools/pi/dsp4_conform.py \
    $ROOT/tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/ || exit 3
scp -q dcapar_run.sh $BENCH:/home/app/ || exit 3
ssh $BENCH "STRIP=${STRIP:-1} WORDS=${WORDS:-32} ATTEMPTS=${ATTEMPTS:-5} \
              bash /home/app/dcapar_run.sh"
