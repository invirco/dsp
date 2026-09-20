#!/bin/bash
# deploy-s82.sh — the SIGNED pair and the shipping LOGIC bitstream, staged.
#
# S82 STAGES AND DOES NOT DEPLOY. PW's window decides when the signed
# configuration goes on the unit; this script is the one command that does it
# and the one command that undoes it, written and staged in the session that
# built the pair rather than reconstructed later from a report.
#
# WHAT "DEPLOY" MEANS ON THIS CARD, stated because it is not obvious: the DSP
# pair is not booted by `matrix-app` and there is no boot flash. The standing
# slot is /home/app/dspboot/chip{1,2}.ldr plus their symbol maps, which is what
# a bare `dsp4_boot.py --dir .` in ~/dspboot picks up, and it is also the
# SHARED SCRATCH SLOT every measurement script overwrites (S16-9). So deploying
# means putting the signed pair there and saying so in ~/dspboot/ldr/manifest.txt,
# and the way back means putting the AS-FOUND pair back.
#
#   ./deploy-s82.sh --stage      copy the candidate to the card (S82 did this)
#   ./deploy-s82.sh --status     what is staged, what is standing, what is flashed
#   ./deploy-s82.sh --deploy     PW's window: the signed pair becomes the standing pair
#   ./deploy-s82.sh --rollback   the way back: the AS-FOUND pair returns
#
# THE WAY BACK IS THE AS-FOUND PAIR AND NOT "the previous contents of the
# scratch slot", because the scratch slot is not an artifact -- it is whatever
# the last bar left there. /home/app/s78restore holds the pair this unit was
# found with (84c79513... / bb2a7c6e...) and is what every session since S78
# has restored to.
#
# THE BITSTREAM IS NOT PART OF EITHER SWITCH. dsp4_logic.7a6a4529f29c is
# already ON the part (S82 gate 0) and is the shipping LOGIC from now on; it is
# copied into the candidate directory so the candidate is self-describing, and
# `loadlogic.sh shipping` is how it is (re)flashed. A bitstream and a DSP pair
# are not deployed together: the CPLD survives a DSP reboot and vice versa.
set -u
cd "$(dirname "$0")"
ROOT=../../../..
BENCH="${BENCH:-app@192.168.1.219}"
CAND=/home/app/dspboot/candidate-s82
STANDING=/home/app/dspboot
ASFOUND=/home/app/s78restore
SVF=dsp4_logic.7a6a4529f29c.svf

case "${1:---status}" in

--stage)
  [ -f build/chip1.ldr ] && [ -f build/chip2.ldr ] || {
      echo "deploy-s82: no build/chip{1,2}.ldr — run ./build.sh first" >&2; exit 2; }
  ./check_shipping_config.sh --expect-shipping || exit 2
  [ -f build/chip1.sym.json ] || python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > build/chip1.sym.json
  [ -f build/chip2.sym.json ] || python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > build/chip2.sym.json
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1); C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  TRIPLE=$(./check_shipping_config.sh --expect-shipping | sed -n '1s/.*must read //p')
  ssh $BENCH "mkdir -p $CAND" || exit 3
  scp -q build/chip1.ldr build/chip2.ldr build/chip1.sym.json build/chip2.sym.json $BENCH:$CAND/ || exit 3
  scp -q $ROOT/shared/dsp4-logic/bitstream/$SVF $BENCH:$CAND/ || exit 3
  scp -q $ROOT/shared/dsp4-logic/bitstream/dsp4_logic.7a6a4529f29c.manifest $BENCH:$CAND/ || exit 3
  ssh $BENCH "cat > $CAND/README.txt" <<EOF
THE SIGNED CONFIGURATION, STAGED — NOT DEPLOYED.

Built $(date -u +%FT%TZ) from MW/D32/DSP/SHARC/shipping.config, no override.

  chip1.ldr   md5 $C1
  chip2.ldr   md5 $C2
  the part must read $TRIPLE

  LOGIC       $SVF, design_id 0x4529f29c, SHIPPING
              (already on the part since S82; loadlogic.sh shipping reflashes it)

Signed by PW 2026-09-20: DSP4_SIMD_DYN + DSP4_STRIP_FUSED + DSP4_DYN_LUT +
DSP4_GATE_LINTHR, over SHARED_KERNELS=15, AUXIN_BYPASS and the product scope
gate. Three accepted numeric bounds travel with it: DYN_LUT 0.0950 dB,
GATE_LINTHR 0.0002 dB, COMPRESSOR 0.00518 dB.

  deploy:    MW/D32/DSP/SHARC/deploy-s82.sh --deploy
  way back:  MW/D32/DSP/SHARC/deploy-s82.sh --rollback   (the AS-FOUND pair)
EOF
  echo "staged at $BENCH:$CAND"
  ssh $BENCH "ls -la $CAND; echo; md5sum $CAND/chip1.ldr $CAND/chip2.ldr"
  ;;

--status)
  echo "== flashed LOGIC"; ./loadlogic.sh --id
  ssh $BENCH "
    echo; echo '== staged candidate ($CAND)'
    [ -d $CAND ] && md5sum $CAND/chip1.ldr $CAND/chip2.ldr || echo '  (nothing staged)'
    echo; echo '== standing pair ($STANDING)'
    md5sum $STANDING/chip1.ldr $STANDING/chip2.ldr 2>/dev/null || echo '  (no pair in the standing slot)'
    echo; echo '== as-found pair ($ASFOUND)'
    md5sum $ASFOUND/chip1.ldr $ASFOUND/chip2.ldr 2>/dev/null || echo '  (MISSING — the way back is gone)'
    echo; echo '== ~/dspboot/ldr/manifest.txt'
    cat $STANDING/ldr/manifest.txt 2>/dev/null || echo '  (none)'"
  ;;

--deploy)
  # A deploy is only meaningful against a candidate that IS the signed
  # configuration, so the host half of the check runs first and the part is
  # scored afterwards. The as-found pair is copied aside under its own name
  # before anything is overwritten -- the scratch slot's previous contents are
  # not an artifact and are not what the way back restores.
  ./check_shipping_config.sh --expect-shipping || exit 2
  ssh $BENCH "set -e
    [ -f $CAND/chip1.ldr ] || { echo 'nothing staged at $CAND'; exit 2; }
    [ -f $ASFOUND/chip1.ldr ] || { echo 'REFUSING: no as-found pair at $ASFOUND — there would be no way back'; exit 2; }
    mkdir -p $STANDING/ldr
    cp -p $CAND/chip1.ldr $CAND/chip2.ldr $CAND/chip1.sym.json $CAND/chip2.sym.json $STANDING/
    {
      echo \"artifact: chip1.ldr md5 \$(md5sum $STANDING/chip1.ldr | cut -d' ' -f1)\"
      echo \"          chip2.ldr md5 \$(md5sum $STANDING/chip2.ldr | cut -d' ' -f1)\"
      echo \"deployed: \$(date -u +%FT%TZ) from $CAND (S82, the signed configuration)\"
      echo \"logic:    $SVF design_id 0x4529f29c\"
      echo \"way back: MW/D32/DSP/SHARC/deploy-s82.sh --rollback  (the AS-FOUND pair, $ASFOUND)\"
    } > $STANDING/ldr/manifest.txt
    echo 'deployed. The standing slot now holds the signed pair.'"
  echo
  echo "Now boot it and score the part:"
  echo "  ssh $BENCH 'cd $STANDING && python3 dsp4_boot.py --dir . && python3 dsp4_buildcfg.py --expect-shipping'"
  ;;

--rollback)
  ssh $BENCH "set -e
    [ -f $ASFOUND/chip1.ldr ] || { echo 'no as-found pair at $ASFOUND'; exit 2; }
    cp -p $ASFOUND/chip1.ldr $ASFOUND/chip2.ldr $ASFOUND/chip1.sym.json $ASFOUND/chip2.sym.json $STANDING/
    rm -f $STANDING/ldr/manifest.txt
    echo 'rolled back to the AS-FOUND pair:'
    md5sum $STANDING/chip1.ldr $STANDING/chip2.ldr"
  ;;

*) sed -n '1,40p' "$0" >&2; exit 2 ;;
esac
