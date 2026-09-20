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
# EVERY ARTIFACT NAMED IN THIS SCRIPT MUST BE REBUILDABLE FROM A COMMIT.
#
# That rule is written here because this script broke it for four months
# without anyone being able to see it (S36-3). `driveall` named
# `e13b5dec84e0`, which matches NO committed state of the logic tree at any
# point in its history -- a dirty-tree build whose source was never committed
# -- and it is the bitstream every driven capacity row since S28 was measured
# on, including the 100.82 % D32 worst-use figure. `pisel` named
# `bd9c100db7c2`, which predates the design-ID stamp and so cannot identify
# itself on the part at all. Both are retired to bitstream/retired/ (nothing
# deleted; see the README there).
#
# So: before adding a name below, rebuild the artifact from the commit in its
# manifest, in a clean tree, and check you get the same label and the same
# pof bytes. The svf differs by one `!Device #1: ... <wall-clock>` comment
# line on every rebuild -- hash the POF.
#
#   ./loadlogic.sh maincap        33b6eb00a4e8, the transmit-stamp capture
#   ./loadlogic.sh pisel          983656926e3e, the CPLD-only loop reference
#   ./loadlogic.sh driveall       c49f4128a083, the DRIVEN-CAPACITY stimulus
#                                 (S19: every DSPA input lane carries the
#                                 Pi's playback, so the graph can be
#                                 measured under load for zero DSP cycles)
#   ./loadlogic.sh shipping       7a6a4529f29c, THE STATE THE BENCH LIVES IN
#   ./loadlogic.sh --id           what is on it now
#
# `shipping` MOVED AT S82, AND EVERY CONVERTER READING TAKEN BEFORE IT IS VOID.
#
# Until 2026-09-20 this label named `a1f6672af6c3`, built 2026-08-21 at commit
# `a4ee3d1f` -- an ANCESTOR of `ded71079`, the S34 converter-clock fix. On that
# bitstream U3 pins 142/141 are INPUTS, so nothing drives the converter bit
# clock or frame sync at all and no converter on the card can work. S81
# measured the consequence as an A/B on the part: same pair, same firmware,
# same symbol map, half an hour apart, only the bitstream changed -- all four
# `_buf_C1_XIN_CODEC_0*` read exact digital zero on `a1f6672af6c3` and carry
# moving converter noise on this tree's. PW adopted the fix on 2026-09-20.
#
# `a1f6672af6c3` is RETIRED to bitstream/retired/ and is not flashable from
# here. It is also the one artifact on the shelf that cannot say what it is:
# it predates the design-ID stamp, so `dsp4_logic_id.py` answers "no reply"
# and its identity rests on a flash log. Hence the gate below.
#
# NO DESIGN ID, NO FLASH (S81-Q2, ruled S82). Every name in the case
# statement resolves to an artifact whose manifest carries a `design_id:`
# line, and this script CHECKS that before it copies anything to the bench.
# The one deliberate exception in this tree is `s37_shipping_step0`, whose
# manifest says design_id NONE and says why (it does not fit at that size);
# it goes on the part through tools/pi/logic_flash.sh, not this script, and
# that is now a property of the tool rather than a convention.
#
#   ATTEMPTS=5 ./loadlogic.sh shipping    how many tries before giving up
#
# `driveall` MOVED AGAIN AT S78, AND THE AMPLITUDE MOVED WITH IT.
#
# Until 2026-09-20 `driveall` named `14df62d98a4d`, which broadcast the Pi
# lane's framing onto EVERY DSPA input lane. chip 1's RX halves do not share
# one frame delay (`src/chip1/lane_config.c`: c1_rx_lanes_mfd =
# { 2,2,2,2,2,2,1,2 }), so the seven MFD-2 halves read that stimulus ONE BIT
# LEFT and only lane 6 read it exactly -- S77-3, located by measurement in
# S78-3. A full-scale square therefore wrapped to 2 LSB and every driven row
# taken before S77 was a silence row on 46 of chip 1's 48 input kernels.
#
#   driveall         c49f4128a083  the FIXED stimulus: bit-exact on every
#                                  lane. Drive it at the amplitude you mean.
#   driveall-pre78   14df62d98a4d  what every driven capacity row up to and
#                                  including S78's bisect was taken on. Keep
#                                  it to reproduce an old row; its stimulus
#                                  is 6 dB hot on every converter lane and
#                                  `drive_audio.sh` must be told so.
#   driveall-base    1ee6b5056fb7  `main` immediately before the S78 fix, as
#                                  the one-change control for c49f4128a083.
#                                  (14df62d98a4d is NOT rebuildable from
#                                  main -- the slot-map hash moved at S72.)
#
# A ROW TAKEN ON ONE OF THESE IS NOT COMPARABLE WITH A ROW TAKEN ON ANOTHER
# AT THE SAME `AMP`. See drive_audio.sh, which refuses to guess which is on
# the part.

# THE THREE INSTRUMENTS MOVED BASE AT S37, AND NO BAR TAKEN ON THEM TRANSFERS
# UNTIL IT IS RE-TAKEN ONCE.
#
# maincap/pisel/driveall above are built from main AFTER the S34 converter
# clock and S36 X-logic parking merges: 403/302/400 logic elements against the
# old 404/303/401, and 68 pins against 71. The pin change is in every
# configuration, so the bytes changed in all three. The 82-sample latency bar
# (S29) and the driven capacity rows (S28) were taken on the OLD pair and are
# not like-for-like against these. The first session with the unit re-takes
# them once on the new artifacts; that is the regression that closes S36-2.
#
# Until then the old base is still here, under its own names, so the S29
# differential can be reproduced against the numbers it was taken with:
#
#   ./loadlogic.sh maincap-s36    d903ae1ac4a9, main before the two merges
#   ./loadlogic.sh pisel-s36      2c1355bbc69b, its matching reference
#                                 (same commit as maincap-s36, and unlike the
#                                 retired bd9c100db7c2 it carries a design ID
#                                 the part can be asked for)
#   ./loadlogic.sh driveall-s36   907492a607bd, the rebuildable equivalent of
#                                 the retired e13b5dec84e0 -- same logic, and
#                                 it differs only in the stamped design_id
#
# NOT FOR THE STEP-0 FLASH. s37_shipping_step0.c62c024714f2 goes on the part
# through tools/pi/logic_flash.sh, which holds the AN_EN interlock and stages
# a verified rollback before the first write. This script retries three times
# and has no interlock, because it only ever moves between known-good
# bitstreams. Do not use it to put something new on the CPLD.
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
cd "$(dirname "$0")"
# THE FLASH TAKES THE BENCH LOCK (S82). This script stops `matrix-app`,
# reprograms the CPLD and hands the GPIOs back -- which is the most
# disruptive thing anything in this tree does to the card -- and it was the
# one bench driver that took no lock at all. A `loadlogic.sh driveall` landing
# in the middle of a `capacity.sh` run reconfigures the instrument under the
# measurement and hands back pins the run is using, and nothing stopped it.
# (S81-4.2 closed this class for seven drivers; this one was not in that list
# because it does not build an image.)
#
# `--id` takes it too: it plays a knock through the CM4's PCM link and
# `arecord`s the reply, which a concurrent audio arm would corrupt in both
# directions.
#
# Nothing in the tree INVOKES this script -- every reference is a comment
# telling a human to run it -- so there is no caller that could already hold
# the lock and deadlock behind this.
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
case "${1:-}" in
  # main + s34-converter-clock + s36-xlogic-park (merge 7eabfa5f, S37)
  maincap)      SVF=dsp4_logic_maincap.33b6eb00a4e8.svf ;;
  pisel)        SVF=dsp4_logic_pisel.983656926e3e.svf ;;
  driveall)     SVF=dsp4_logic_driveall.943f27966c28.svf ;;
  driveall-pre85) SVF=dsp4_logic_driveall.c49f4128a083.svf ;;
  driveall-pre78) SVF=dsp4_logic_driveall.14df62d98a4d.svf ;;
  driveall-base)  SVF=dsp4_logic_driveall.1ee6b5056fb7.svf ;;
  # the base every bar on record was taken on, kept until they are re-taken
  maincap-s36)  SVF=dsp4_logic_maincap.d903ae1ac4a9.svf ;;
  pisel-s36)    SVF=dsp4_logic_pisel.2c1355bbc69b.svf ;;
  driveall-s36) SVF=dsp4_logic_driveall.907492a607bd.svf ;;
  # S85: shipping adopts the label that carries the ad[0..2] witness in every
  # configuration (hub ruling S84-N1). The DRIVEN lane path is unchanged --
  # i_dspa[0..2] are still the same wire they were -- and the S82 84.34 % D24
  # driven row was re-taken on the matching driveall build to prove it.
  shipping)     SVF=dsp4_logic.d02d83b3cc22.svf ;;
  shipping-s82) SVF=dsp4_logic.7a6a4529f29c.svf ;;
  # RETIRED S82, and named here only so the refusal is a sentence rather
  # than a usage line. See bitstream/retired/README.md.
  shipping-pre-s34|a1f6672af6c3)
     echo "$0: dsp4_logic.a1f6672af6c3 is RETIRED (S82)." >&2
     echo "  It is the PRE-S34 bitstream: U3.142/U3.141 are inputs, so the" >&2
     echo "  converter bit clock and frame sync are undriven and no converter" >&2
     echo "  on the card can work. PW adopted the fix 2026-09-20; the" >&2
     echo "  shipping label now names dsp4_logic.7a6a4529f29c." >&2
     echo "  The artifact is kept at bitstream/retired/ so old records" >&2
     echo "  resolve. It is not flashed again." >&2
     exit 2 ;;
  --id)     ssh $BENCH "cd /home/app/dspboot && python3 dsp4_logic_id.py"; exit $? ;;
  *) echo "usage: $0 maincap|pisel|driveall|driveall-pre78|driveall-base|maincap-s36|pisel-s36|driveall-s36|shipping|--id" >&2
     echo "       (something NEW on the part goes through tools/pi/logic_flash.sh)" >&2
     exit 2 ;;
esac
SRC=../../../../shared/dsp4-logic/bitstream/$SVF

# ---- NO DESIGN ID, NO FLASH (S81-Q2, ruled S82) ----
#
# `a1f6672af6c3` was on this bench for a month under the name "shipping" and
# could not be asked what it was: it predates the design-ID stamp, so
# `dsp4_logic_id.py` answers "no reply: nothing in the capture carried the
# 0xD594 marker" and the only evidence of which bitstream was on the part was
# a flash log. Ten sessions then diagnosed a converter fault that was the
# bitstream. A bitstream that cannot identify itself is never flashed again.
#
# The check is on the MANIFEST beside the artifact, not on a list of names
# kept here -- a list is a second copy of a fact and would go stale the first
# time somebody added a bitstream. A manifest whose `design_id:` line reads
# anything but a 32-bit hex literal (the step-0 image says "NONE — AND THAT
# IS NOT FIXABLE AT THIS SIZE") does not pass either.
MAN="${SRC%.svf}.manifest"
if [ ! -f "$MAN" ]; then
    echo "$0: no manifest beside $SVF -- refusing to flash an artifact that" >&2
    echo "  cannot say what it is. Expected $MAN" >&2
    exit 4
fi
DESIGN_ID="$(sed -n "s/^design_id: *32'h\([0-9a-fA-F]\{8\}\) *$/\1/p" "$MAN" | head -1)"
if [ -z "$DESIGN_ID" ]; then
    echo "$0: $SVF has NO DESIGN ID in its manifest and will not be flashed." >&2
    echo "  (S81-Q2, ruled S82: a bitstream that cannot report its own" >&2
    echo "  identity leaves the bench unable to say what it measured on.)" >&2
    sed -n 's/^design_id:/  manifest says design_id:/p' "$MAN" >&2
    exit 4
fi
echo "== $SVF design_id 0x$DESIGN_ID (ask the part with: $0 --id)"

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
