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
ssh $BENCH "set -u; cd /home/app
  echo '== loading $SVF =='
  md5sum $SVF
  sudo systemctl stop matrix-app >/dev/null 2>&1
  sudo openocd -f cpld-jtag.cfg -c 'init; svf -tap cpld.tap $SVF; shutdown' 2>&1 | tail -3
  sudo openocd -f cpld-jtag.cfg -c 'init; scan_chain; shutdown' 2>&1 | grep -i '0x020a30dd' || echo 'IDCODE NOT SEEN'
  sudo pinctrl set 6,24 op dh >/dev/null 2>&1
  sudo pinctrl set 8,12 ip >/dev/null 2>&1
  sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
  sleep 2"
