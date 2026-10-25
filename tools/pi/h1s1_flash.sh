#!/bin/bash
# h1s1_flash.sh — load an H1S1 (DSP card U7) image through MH1, behind the
# card guard. S174.
#
# Runs ON THE DESK and drives the bench over ssh, like logic_flash.sh. It is
# the MW/D24/FW/H1S1/README.md "How flashed" recipe (stage the .shex as
# /home/app/firmware/H1S1.shex, `app cli loadfw H1S1`) with the guard in
# front of it:
#
#   THE CARD GUARD (PW ruling S173 Q4 (a)): no H1S1 flash without POSITIVE
#   identification of the card. The rev C card's U7 is an STM32U575, the rev
#   D card's an STM32G0B1 (DSPC MOD 5); an image for the other part does not
#   run, and MH1's loader MASS-ERASES U7 before it writes a byte -- so a
#   wrong image leaves U7 blank, and on rev D a blank U7 is a card with no
#   RST_C driver (S173-3). The image says which part it is for by its
#   initial stack pointer (U575 image: 0x200C0000 = rev C; G0B1 image:
#   0x20024000 = rev D; anything else is refused), and the bench must name
#   the same card through dspcard_id.py. "Nothing answered" is not a card.
#
#   ./h1s1_flash.sh ../../MW/D24/FW/H1S1/image/H1S1.shex --stop-app --dry-run
#   ./h1s1_flash.sh ../../MW/D24/FW/H1S1G0/image/H1S1G0.shex --stop-app
#
#   --dry-run            image check, staging check and the card guard; no
#                        file is replaced and loadfw is not run.
#   --stop-app           stop matrix-app first (it owns /dev/serial0, which
#                        both the guard's H1S1 read and loadfw need), restart
#                        it at the end. Without it the app must already be
#                        stopped.
#   --leave-app-stopped  do not restart matrix-app at the end.
#   --self-test <dir>    run the remote half locally against the stubs in <dir>.
#
# Exit: 0 loaded (or dry run passed), 2 bad image/usage, 3 staging, 5 app
# running, 6 card guard refused, 7 loadfw failed (the previous image is back
# in place as H1S1.shex; U7 is ERASED until it is loaded again).
set -u

BENCH="${BENCH:-app@192.168.1.219}"
DRYRUN=0; STOPAPP=0; RESTART=1; SELFTEST=""; ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)            DRYRUN=1 ;;
    --stop-app)           STOPAPP=1 ;;
    --leave-app-stopped)  RESTART=0 ;;
    --self-test)          SELFTEST="${2:?--self-test needs a stub dir}"; shift ;;
    -h|--help)            sed -n '2,40p' "$0"; exit 0 ;;
    -*)                   echo "unknown option: $1" >&2; exit 2 ;;
    *)                    ARG="$1" ;;
  esac
  shift
done
[ -n "$ARG" ] || { echo "usage: $0 [options] <image.shex>   (--help)" >&2; exit 2; }
[ -f "$ARG" ] || { echo "!! no such image: $ARG" >&2; exit 2; }

# ---- What the image is for -------------------------------------------------
HDR=$(head -1 "$ARG" | tr -d '\r')
[ "${HDR:0:7}" = ":02H1S1" ] || { echo "!! $ARG is not an H1S1 shex (header '$HDR')" >&2; exit 2; }
# First data record at offset 0: its first word is the initial SP, little-endian.
SP_HEX=$(grep -m1 '^:10000000' "$ARG" | cut -c10-17)
SP=$(printf '%s' "$SP_HEX" | sed 's/\(..\)\(..\)\(..\)\(..\)/\4\3\2\1/')
case "$SP" in
  200C0000) IMG_REV=C; PART="STM32U575 (rev C U7)" ;;
  20024000) IMG_REV=D; PART="STM32G0B1 (rev D U7)" ;;
  *) echo "!! $ARG: initial SP 0x${SP:-none} is neither the U575 image's (0x200C0000)" >&2
     echo "   nor the G0B1 image's (0x20024000) -- cannot say which card it is for." >&2
     exit 2 ;;
esac
MD5=$(md5sum "$ARG" | cut -d' ' -f1)
NAME="H1S1.shex.s174-$MD5"
echo "== h1s1_flash: $ARG"
echo "   md5        : $MD5"
echo "   built for  : $PART -> card rev $IMG_REV"
[ "$DRYRUN" = "1" ] && echo "   MODE       : DRY RUN — image, staging and card guard; no write"

if [ -z "$SELFTEST" ]; then
  _D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -r "$_D/../../MW/D32/DSP/SHARC/bench_lock.sh" ]; then
    # shellcheck source=/dev/null
    . "$_D/../../MW/D32/DSP/SHARC/bench_lock.sh"
    bench_lock_acquire "$0"
  fi
  scp -q "$ARG" "$BENCH:/home/app/firmware/$NAME" || { echo "!! scp failed" >&2; exit 3; }
fi

RUN=(ssh "$BENCH")
[ -n "$SELFTEST" ] && RUN=(env "PATH=$SELFTEST:$PATH" bash -c)

"${RUN[@]}" "NAME='$NAME' MD5='$MD5' IMG_REV='$IMG_REV' DRYRUN='$DRYRUN' \
      STOPAPP='$STOPAPP' RESTART='$RESTART' FWDIR='${FWDIR:-/home/app/firmware}' \
      DSPCARD_ID='${DSPCARD_ID:-/home/app/dspboot/dspcard_id.py}' bash -s" <<'REMOTE'
set -u
LOG="$FWDIR/h1s1-flash.log"
say() { echo "$@"; }
rec() { echo "$(date -u +%FT%TZ) [h1s1_flash] $*" >> "$LOG" 2>/dev/null; }
APP_STOPPED=0
restart_app() {
  [ "$APP_STOPPED" = "1" ] && [ "$RESTART" = "1" ] && {
    say "   restarting matrix-app"; sudo systemctl start matrix-app >/dev/null 2>&1; }
}
fail() { say "   !! $1"; rec "REFUSED: $1"; restart_app; exit "${2:-6}"; }

rec "=== session: $NAME md5=$MD5 for rev $IMG_REV dryrun=$DRYRUN"
cd "$FWDIR" 2>/dev/null || fail "$FWDIR is missing on the bench" 3
[ -f "$NAME" ] || fail "$NAME is not staged in $FWDIR" 3
[ "$(md5sum "$NAME" | cut -d' ' -f1)" = "$MD5" ] || fail "staged copy md5 mismatch" 3

# ---- matrix-app owns /dev/serial0 -----------------------------------------
if [ "$(systemctl is-active matrix-app 2>/dev/null)" = "active" ]; then
  if [ "$STOPAPP" = "1" ]; then
    say "   matrix-app : active -> stopping (the guard and loadfw need the bus)"
    sudo systemctl stop matrix-app >/dev/null 2>&1; sleep 3; APP_STOPPED=1
  else
    fail "matrix-app is running and owns /dev/serial0: pass --stop-app" 5
  fi
fi

# ---- THE CARD GUARD ---------------------------------------------------------
[ -f "$DSPCARD_ID" ] || fail "card identification tool $DSPCARD_ID is not on the bench -- cannot identify the card, so cannot flash" 6
ID_OUT=$(python3 "$DSPCARD_ID" --want "$IMG_REV" 2>&1); ID_RC=$?
printf '%s\n' "$ID_OUT" | grep -v '^{' | sed 's/^/   card id    : /'
rec "card id (want rev $IMG_REV, rc=$ID_RC): $(printf '%s' "$ID_OUT" | grep '^{')"
case "$ID_RC" in
  0) say "   card guard : positively rev $IMG_REV -- matches the image" ;;
  3) fail "THE CARD COULD NOT BE IDENTIFIED -- NOT FLASHING. Nothing named a revision (lines above); a rev D card with a blank U7 or a rev C CPLD image is silent too, so 'no answer' is not rev C." 6 ;;
  4) fail "THE SOURCES DISAGREE ABOUT THE CARD -- NOT FLASHING. Find out why." 6 ;;
  5) fail "THIS IS NOT A REV $IMG_REV CARD -- NOT FLASHING. loadfw mass-erases U7 first, and an image for the other part will not run: U7 would be left blank." 6 ;;
  *) fail "card identification failed (rc=$ID_RC) -- NOT FLASHING." 6 ;;
esac

if [ "$DRYRUN" = "1" ]; then
  say "   DRY RUN — every gate passed and NOTHING was replaced or loaded."
  rec "DRY RUN complete"
  restart_app; exit 0
fi

# ---- Stage as H1S1.shex, keep the previous one -------------------------------
BAK=""
if [ -f H1S1.shex ]; then
  BAK="H1S1.shex.bak-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p H1S1.shex "$BAK" || fail "could not back up H1S1.shex" 3
  say "   previous   : H1S1.shex -> $BAK ($(md5sum "$BAK" | cut -d' ' -f1))"
fi
cp "$NAME" H1S1.shex || fail "could not stage H1S1.shex" 3

say "   -- app cli loadfw H1S1"
OUT=$(app cli loadfw H1S1 2>&1); RC=$?
printf '%s\n' "$OUT" | tail -5 | sed 's/^/      /'
{ echo "=== loadfw rc=$RC"; printf '%s\n' "$OUT"; } >> "$LOG"
if [ "$RC" = "0" ] && printf '%s' "$OUT" | grep -q 'OK: H1S1'; then
  say "   LOADED: H1S1 = $MD5 (rev $IMG_REV image)"
  rec "LOADED $MD5"
  restart_app; exit 0
fi
say "   !! loadfw FAILED. U7 was mass-erased by MH1's loader and is BLANK."
[ -n "$BAK" ] && { cp -p "$BAK" H1S1.shex; say "      H1S1.shex is back to $BAK; load it with: python3 sreset.py; app cli loadfw H1S1"; }
rec "loadfw FAILED rc=$RC; H1S1.shex restored from ${BAK:-nothing}"
restart_app; exit 7
REMOTE
RC=$?
echo "== h1s1_flash exit $RC"
exit $RC
