#!/bin/bash
# cfgverify.sh — does the part carry the configuration a NAMED FILE names?
#
# `check_shipping_config.sh` answers this question on the HOST: it proves
# shipping.config and the bench mirror in tools/pi/dsp4_buildcfg.py are one
# fact, and prints the two words a shipping image must read back. Nothing in
# the tree closed the loop on the PART for a configuration other than
# `shipping.config` -- and S20's whole premise is a SECOND named
# configuration (`shipping.config.s20`, a proposed successor), so the loop had
# to be closed for an arbitrary file.
#
# This boots the image and reads DIAG_BUILD_CFG and DIAG_BUILD_CFG2 off BOTH
# chips, then hands them to tools/dsp/cfg_words.py --check, which recomputes
# both words from the file, build.sh's defaults and the derivations. A
# mismatch prints which bits differ and exits 4. That is the only form of
# "the image is the configuration" this project accepts, because every one of
# S8-2, S9-1, S11-1 and S12-7 was a configuration nobody could read back.
#
#   ./cfgverify.sh                                      shipping.config
#   CONFIG=shipping.config.s20 ARM=s20 ./cfgverify.sh
#   CONFIG=shipping.config.s20 ARM=s20f DSP4_BQ_SIMD_PIPE=2 ./cfgverify.sh
#   BUILD=0 ARM=s20 ./cfgverify.sh                      boot what is built
#   STAGE_AS=s20 ... ./cfgverify.sh                     also stage the pair as
#                                                       ~/dspboot/s20_chipN.ldr
set -u
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219

CONFIG="${CONFIG:-shipping.config}"
ARM="${ARM:-ship}"
PRODUCT="${PRODUCT:-d24}"
STAGE="${STAGE:-/home/app/dspcap/$ARM}"
WORK="${WORK:-/tmp/dspcap}"
D="$WORK/$ARM"
[ -r "$CONFIG" ] || { echo "cfgverify.sh: no such config file: $CONFIG" >&2; exit 2; }

OVR=""
for v in $(env | sed -n 's/^\(DSP4_[A-Z0-9_]*\)=.*/\1/p' | sort); do
    OVR="$OVR $v=${!v}"
done
echo "=== cfgverify arm '$ARM'  config=$CONFIG  overrides:${OVR:- none}"

if [ "${BUILD:-1}" = "1" ]; then
    SHIPPING_CONFIG="$PWD/$CONFIG" DSP_BUILD_DIR="$D" ./build.sh all > "$D.log" 2>&1
    if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
        echo "BUILD FAILED — $D.log"; grep -iE '\[Error|Build FAILED' "$D.log" | head; exit 1; fi
fi
[ -f "$D/chip1.ldr" ] || { echo "cfgverify.sh: nothing built in $D" >&2; exit 1; }
echo "  image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8)  chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
[ -f "$D/chip1.sym.json" ] || python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
[ -f "$D/chip2.sym.json" ] || python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"

# The expected words, from the FILE, before the part is asked.
python3 $ROOT/tools/dsp/cfg_words.py "$CONFIG" | tail -2

ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
    ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" $BENCH:$STAGE/ || exit 3
scp -q $ROOT/tools/pi/dsp4_buildcfg.py $ROOT/tools/pi/dsp4_boot.py \
       $ROOT/tools/pi/dsp4_checkchip.py $ROOT/tools/pi/gainfix.py $BENCH:$STAGE/ || exit 3
scp -q cfgverify_run.sh $BENCH:/home/app/ || exit 3

# STAGING A PAIR IS A DELIBERATE ACT, and it never overwrites one: ~/dspboot's
# prefixed pairs are what the window rolls back to (S10-7, S16-9).
if [ -n "${STAGE_AS:-}" ]; then
    if ssh $BENCH "test -f /home/app/dspboot/${STAGE_AS}_chip1.ldr"; then
        echo "  ${STAGE_AS}_* is ALREADY STAGED — not replaced (S10-7)."
    else
        scp -q "$D/chip1.ldr" $BENCH:/home/app/dspboot/${STAGE_AS}_chip1.ldr || exit 3
        scp -q "$D/chip2.ldr" $BENCH:/home/app/dspboot/${STAGE_AS}_chip2.ldr || exit 3
        scp -q "$D/chip1.sym.json" $BENCH:/home/app/dspboot/${STAGE_AS}_chip1.sym.json || exit 3
        scp -q "$D/chip2.sym.json" $BENCH:/home/app/dspboot/${STAGE_AS}_chip2.sym.json || exit 3
        echo "  staged as ~/dspboot/${STAGE_AS}_chip{1,2}.ldr (with symbol maps)"
    fi
fi

OUT="$(ssh $BENCH "STAGE='$STAGE' PRODUCT=$PRODUCT bash /home/app/cfgverify_run.sh")" || {
    echo "$OUT"; echo "cfgverify.sh: the part never came up"; exit 4; }
echo "$OUT"

rc=0
for c in 1 2; do
    W="$(printf '%s\n' "$OUT" | sed -n "s/^CHIP$c CFGWORDS //p")"
    [ -n "$W" ] || { echo "chip $c: no words read"; rc=4; continue; }
    echo "--- chip $c: $W"
    python3 $ROOT/tools/dsp/cfg_words.py "$CONFIG" --check "$W" >/dev/null || rc=4
    python3 $ROOT/tools/dsp/cfg_words.py "$CONFIG" --check "$W" | tail -2 | sed 's/^/    /'
done
exit $rc
