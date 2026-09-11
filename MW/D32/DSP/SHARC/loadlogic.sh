#!/bin/bash
# loadlogic.sh — put a named LOGIC bitstream on the bench CPLD, and put the
# shipping one back.
#
# The transmit-stamp arm (txorder.sh / dsp4_tx_order.py) reads chip 2's TX
# lane 3 slot 1 through the Pi capture, and only the `_maincap` build routes
# it there: on the SHIPPING bitstream `arecord` returns "Input/output error"
# and zero frames, which the order tool reports as "NO STAMP". So the arm is
# a bench reconfiguration, and a bench reconfiguration needs a restore that
# is one command and is on record.
#
#   ./loadlogic.sh maincap        d903ae1ac4a9, the transmit-stamp capture
#   ./loadlogic.sh pisel          bd9c100db7c2, the CPLD-only loop reference
#   ./loadlogic.sh driveall       e13b5dec84e0, the DRIVEN-CAPACITY stimulus
#                                 (S19: every DSPA input lane carries the
#                                 Pi's playback, so the graph can be
#                                 measured under load for zero DSP cycles)
#   ./loadlogic.sh shipping       a1f6672af6c3, THE STATE THE BENCH LIVES IN
#   ./loadlogic.sh --id           what is on it now
#
#   ATTEMPTS=5 ./loadlogic.sh shipping    how many tries before giving up
#
# THE SUCCESS CHECK USED TO BE THE IDCODE, AND THE IDCODE IS NOT THE CHECK
# (S27-5). A MAX V answers its IDCODE from the JTAG tap whether or not the
# configuration flash took, so `scan_chain | grep 0x020a30dd` passes on a
# flash that failed halfway -- which is exactly the state S24 hit three
# times in a row with an svf MASK failure and no way for the script to say
# so.
#
# WHAT THIS OPENOCD ACTUALLY PRINTS, measured rather than assumed (the first
# version of this check assumed the upstream `svf file programmed
# successfully for N commands` line and reported nine good flashes as nine
# failures): the svf driver on the bench echoes each SVF command and prints
# NO summary. A run that completes ends with `shutdown command invoked`,
# because `-c 'init; svf ...; shutdown'` is ONE command chain and a failing
# svf aborts it before the shutdown. A TDO/MASK mismatch prints `tdo check
# error at line N` with READ/WANT/MASK beneath it. So the check is: the
# chain reached its shutdown, and no tdo check error on the way.
#
# `Error: Translation from khz to adapter speed not implemented` appears on
# EVERY run and is benign -- linuxgpiod has no settable speed -- so it is
# excluded by name rather than by grepping for something weaker.
#
# The script:
#
#   * reads the IDCODE BEFORE the flash as well as after, so a run that
#     could not see the tap at all is distinguishable from one that could;
#   * requires openocd's command chain to have reached its `shutdown`, with
#     no `tdo check error` in the run;
#   * RETRIES (default 3) on a failure, with a loud line per attempt, and
#     keeps every attempt's full openocd output in /home/app/logic-flash.log
#     on the bench;
#   * exits non-zero if no attempt succeeded, instead of leaving a caller
#     to discover it in the audio.
#
# The SVF is copied from the repo's bitstream/ if the bench does not have
# it, so a build made on the desk needs no second command to reach the part.
#
# openocd's linuxgpiod driver leaves its GPIOs claimed, which kills the DSP
# SPI link and looks exactly like a bricked card, so the pins are handed back
# every time -- in the CANONICAL sequence (S8-3), not the a0-everything line
# the bench's own restore_bench.sh still carries.
set -u
BENCH=app@192.168.1.219
case "${1:-}" in
  maincap)  SVF=dsp4_logic_maincap.d903ae1ac4a9.svf ;;
  pisel)    SVF=dsp4_logic_pisel.bd9c100db7c2.svf ;;
  driveall) SVF=dsp4_logic_driveall.e13b5dec84e0.svf ;;
  shipping) SVF=dsp4_logic.a1f6672af6c3.svf ;;
  --id)     ssh $BENCH "cd /home/app/dspboot && python3 dsp4_logic_id.py"; exit $? ;;
  *) echo "usage: $0 maincap|pisel|shipping|--id" >&2; exit 2 ;;
esac
SRC=../../../../shared/dsp4-logic/bitstream/$SVF
if ! ssh $BENCH "test -f /home/app/$SVF"; then
    [ -f "$SRC" ] || { echo "no $SVF here or on the bench" >&2; exit 2; }
    echo "== staging $SVF ($(md5sum "$SRC" | cut -c1-8))"
    scp -q "$SRC" $BENCH:/home/app/ || exit 3
fi
ATTEMPTS="${ATTEMPTS:-3}"
# The remote half is a QUOTED heredoc and the two variables it needs arrive
# in its environment. The previous form was a double-quoted ssh argument
# with every remote `$` hand-escaped, which is one backslash away from the
# desk expanding a bench variable and is not a thing to hand-audit.
ssh $BENCH "SVF='$SVF' ATTEMPTS='$ATTEMPTS' bash -s" <<'REMOTE'
set -u
cd /home/app
echo "== loading $SVF =="
md5sum "$SVF"
sudo systemctl stop matrix-app >/dev/null 2>&1

idcode() {
  sudo openocd -f cpld-jtag.cfg -c 'init; scan_chain; shutdown' 2>&1 \
    | sed -n 's/.*tap\/device found: \(0x[0-9a-fA-F]*\).*/\1/p' | head -1
}

BEFORE=$(idcode)
echo "   IDCODE before: ${BEFORE:-NONE}"
[ -n "$BEFORE" ] || echo "   !! NO TAP BEFORE THE FLASH -- the JTAG chain is not answering"

OK=0
for a in $(seq 1 "$ATTEMPTS"); do
  echo "   -- flash attempt $a of $ATTEMPTS"
  sudo openocd -f cpld-jtag.cfg -c "init; svf -tap cpld.tap $SVF; shutdown" \
    > /tmp/logic-flash.out 2>&1
  RC=$?
  { echo "=== $(date -u +%FT%TZ) $SVF attempt $a rc=$RC"; cat /tmp/logic-flash.out; } \
    >> /home/app/logic-flash.log
  if grep -q 'shutdown command invoked' /tmp/logic-flash.out \
     && ! grep -qiE 'tdo check error|mismatch|verify failed' /tmp/logic-flash.out; then
    echo "   FLASH OK on attempt $a ($(grep -c . /tmp/logic-flash.out) lines of SVF played, chain reached shutdown)"
    OK=$a
    break
  fi
  echo "   !! FLASH ATTEMPT $a FAILED (openocd rc=$RC). What it said:"
  grep -iE 'tdo check error|mismatch|verify failed|error' /tmp/logic-flash.out \
    | grep -v 'Translation from khz' | head -6 | sed 's/^/      /'
  grep -q 'shutdown command invoked' /tmp/logic-flash.out \
    || echo '      (the openocd command chain never reached its shutdown -- the svf aborted)'
  sleep 2
done

AFTER=$(idcode)
echo "   IDCODE after:  ${AFTER:-NONE}"

# The pins go back whatever happened: openocd's linuxgpiod driver leaves
# them claimed, and a failed flash that also left the DSP link dead reads
# as a bricked card.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
sleep 2

if [ "$OK" = "0" ]; then
  echo "   !! $SVF NOT PROGRAMMED after $ATTEMPTS attempts -- the CPLD is in an"
  echo "      UNKNOWN state. Full openocd output: /home/app/logic-flash.log"
  exit 7
fi
[ "$OK" = "1" ] || echo "   NOTE: it took $OK attempts. Recorded in /home/app/logic-flash.log."
exit 0
REMOTE
