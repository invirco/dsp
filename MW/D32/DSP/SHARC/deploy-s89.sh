#!/bin/bash
# deploy-s89.sh — the DAC-FOLD FIX staged as a candidate pair, not deployed.
#
# Same shape and the same rules as deploy-s82.sh, one switch further on. The
# difference between this candidate and the signed S82 pair is ONE named
# switch, DSP4_TX_DEFER=2 (chip 2's converter gather moved to a fixed point in
# the block period), and the only thing that moves in the triple is
# DIAG_BUILD_CFG3 0xC47C0F26 -> 0xC47C0FA6.
#
# WHY THERE IS A CANDIDATE AT ALL. S88-1/S89 measured 57.4 % cable-loop THD at
# the XLR on the signed pair with every digital probe clean; S89e root-caused
# it (the gather ran at the END of the block period, so the instant the core
# wrote the transmit row was `interrupt + whatever the graph cost` — S82's
# audio switches made the core fast enough to cross the DDE's read position)
# and fixed it for zero cycles, zero DM and zero added latency. S91 priced it
# under load on the `driveall` stimulus. See MW/D24/DSP/s89/dac-fold-fix.md
# and MW/D24/DSP/s91/candidate-s89-price.md.
#
# STAGING IS NOT DEPLOYING. The standing slot (/home/app/dspboot/chip{1,2}.ldr)
# is not touched by --stage, and neither is the CPLD. Whether this pair becomes
# the pair that ships is PW's call.
#
#   ./deploy-s89.sh --stage      copy the candidate to the card (S91 did this)
#   ./deploy-s89.sh --status     what is staged, what is standing, what is flashed
#   ./deploy-s89.sh --deploy     PW's window: this pair becomes the standing pair
#   ./deploy-s89.sh --rollback   the way back: the AS-FOUND pair returns
#
# THE WAY BACK IS THE AS-FOUND PAIR (/home/app/s78restore), the same one
# deploy-s82.sh restores to, and for the same reason: the scratch slot is not
# an artifact, it is whatever the last measurement left there.
#
# THE BITSTREAM IS NOT PART OF EITHER SWITCH. dsp4_logic.d02d83b3cc22 is the
# shipping LOGIC and lives on the part; it is copied into the candidate
# directory so the candidate is self-describing, and `loadlogic.sh shipping` is
# how it is (re)flashed. A bitstream and a DSP pair are not deployed together.
set -u
cd "$(dirname "$0")"
ROOT=../../../..
BENCH="${BENCH:-app@192.168.1.219}"
CAND=/home/app/dspboot/candidate-s89
STANDING=/home/app/dspboot
ASFOUND=/home/app/s78restore
SVF=dsp4_logic.d02d83b3cc22.svf

case "${1:---status}" in

--stage)
  [ -f build/chip1.ldr ] && [ -f build/chip2.ldr ] || {
      echo "deploy-s89: no build/chip{1,2}.ldr — run ./build.sh first" >&2; exit 2; }
  ./check_shipping_config.sh --expect-shipping || exit 2
  [ -f build/chip1.sym.json ] || python3 $ROOT/tools/dsp/map_syms.py build/chip1.map.xml > build/chip1.sym.json
  [ -f build/chip2.sym.json ] || python3 $ROOT/tools/dsp/map_syms.py build/chip2.map.xml > build/chip2.sym.json
  C1=$(md5sum build/chip1.ldr | cut -d' ' -f1); C2=$(md5sum build/chip2.ldr | cut -d' ' -f1)
  TRIPLE=$(./check_shipping_config.sh --expect-shipping | sed -n '1s/.*must read //p')
  ssh $BENCH "mkdir -p $CAND" || exit 3
  scp -q build/chip1.ldr build/chip2.ldr build/chip1.sym.json build/chip2.sym.json $BENCH:$CAND/ || exit 3
  scp -q $ROOT/shared/dsp4-logic/bitstream/$SVF $BENCH:$CAND/ || exit 3
  scp -q $ROOT/shared/dsp4-logic/bitstream/dsp4_logic.d02d83b3cc22.manifest $BENCH:$CAND/ || exit 3
  ssh $BENCH "cat > $CAND/README.txt" <<EOF
THE DAC-FOLD FIX, STAGED — NOT DEPLOYED.

Built $(date -u +%FT%TZ) from MW/D32/DSP/SHARC/shipping.config, no override.

  chip1.ldr   md5 $C1
  chip2.ldr   md5 $C2
  the part must read $TRIPLE

  LOGIC       $SVF, design_id 0x83b3cc22, SHIPPING
              (already on the part; loadlogic.sh shipping reflashes it)

This is candidate-s82's configuration plus ONE named switch, DSP4_TX_DEFER=2
(S89e): chip 2's converter gather moved out of the end of the block period to
a fixed point immediately after the block interrupt, so the moment the core
writes the transmit row no longer depends on how long the node graph took.
Zero cycles, zero DM, zero added latency — contract latency stays 82 samples /
1.708 ms. With the switch OFF the pair rebuilds the S82 signed images byte for
byte; chip 1's image differs from S82's in exactly ONE BYTE, its own config
stamp. The signed numeric bounds are S82's, unmoved.

  cable-loop THD   57.33…57.43 % on the S82 pair -> 0.3212…0.3216 % on this one
                   (S89e, idle regime; S91 re-took it driven)
  driven capacity  MW/D24/DSP/s91/candidate-s89-price.md

  price:     MW/D24/DSP/s91/candidate-s89-price.md
  root cause: MW/D24/DSP/s89/dac-fold-fix.md
  deploy:    MW/D32/DSP/SHARC/deploy-s89.sh --deploy
  way back:  MW/D32/DSP/SHARC/deploy-s89.sh --rollback   (the AS-FOUND pair)
EOF
  echo "staged at $BENCH:$CAND"
  ssh $BENCH "ls -la $CAND; echo; md5sum $CAND/chip1.ldr $CAND/chip2.ldr"
  ;;

--status)
  echo "== flashed LOGIC"; ./loadlogic.sh --id
  ssh $BENCH "
    echo; echo '== staged candidate ($CAND)'
    [ -d $CAND ] && md5sum $CAND/chip1.ldr $CAND/chip2.ldr || echo '  (nothing staged)'
    echo; echo '== staged candidate-s82'
    [ -d $STANDING/candidate-s82 ] && md5sum $STANDING/candidate-s82/chip1.ldr $STANDING/candidate-s82/chip2.ldr || echo '  (nothing staged)'
    echo; echo '== standing pair ($STANDING)'
    md5sum $STANDING/chip1.ldr $STANDING/chip2.ldr 2>/dev/null || echo '  (no pair in the standing slot)'
    echo; echo '== as-found pair ($ASFOUND)'
    md5sum $ASFOUND/chip1.ldr $ASFOUND/chip2.ldr 2>/dev/null || echo '  (MISSING — the way back is gone)'
    echo; echo '== ~/dspboot/ldr/manifest.txt'
    cat $STANDING/ldr/manifest.txt 2>/dev/null || echo '  (none)'"
  ;;

--deploy)
  # Same order as deploy-s82.sh: the host half of the check first, the part
  # scored afterwards, and the as-found pair copied aside under its own name
  # before anything is overwritten.
  ./check_shipping_config.sh --expect-shipping || exit 2
  ssh $BENCH "set -e
    [ -f $CAND/chip1.ldr ] || { echo 'nothing staged at $CAND'; exit 2; }
    [ -f $ASFOUND/chip1.ldr ] || { echo 'REFUSING: no as-found pair at $ASFOUND — there would be no way back'; exit 2; }
    mkdir -p $STANDING/ldr
    cp -p $CAND/chip1.ldr $CAND/chip2.ldr $CAND/chip1.sym.json $CAND/chip2.sym.json $STANDING/
    {
      echo \"artifact: chip1.ldr md5 \$(md5sum $STANDING/chip1.ldr | cut -d' ' -f1)\"
      echo \"          chip2.ldr md5 \$(md5sum $STANDING/chip2.ldr | cut -d' ' -f1)\"
      echo \"deployed: \$(date -u +%FT%TZ) from $CAND (S89e, the deferred gather)\"
      echo \"logic:    $SVF design_id 0x83b3cc22\"
      echo \"way back: MW/D32/DSP/SHARC/deploy-s89.sh --rollback  (the AS-FOUND pair, $ASFOUND)\"
    } > $STANDING/ldr/manifest.txt
    echo 'deployed. The standing slot now holds the deferred-gather pair.'"
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
