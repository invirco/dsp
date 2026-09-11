#!/bin/bash
# logic_flash.sh — put a LOGIC bitstream on the DSP4 CPLD under the AN_EN
# interlock, on ONE attempt, with a rollback that is staged before the first
# byte is written.
#
# Runs ON THE DESK and drives the bench over ssh, like loadlogic.sh. The
# remote half is a QUOTED heredoc; the same bytes run in --self-test, so what
# is tested is what is shipped.
#
#   ./logic_flash.sh 138dba7274d6                 the isolated converter fix
#   ./logic_flash.sh dsp4_logic.a1f6672af6c3.svf  by name
#   ./logic_flash.sh ../../shared/dsp4-logic/bitstream/x.svf   by path
#
#   --dry-run          every gate and every read, no openocd write. Safe on a
#                      live unit; this is how you find out whether the
#                      interlock is currently satisfiable.
#   --rollback <svf>   what goes back if the flash does not take.
#                      Default dsp4_logic.a1f6672af6c3.svf — the bitstream the
#                      bench lives on.
#   --stop-app         stop matrix-app, then RE-READ GPIO26. See below.
#   --leave-app-stopped  do not restart matrix-app at the end.
#   --an-en-waived "<written reason>"   PW's shape-3 ruling, recorded.
#   --self-test <dir>  run the remote half locally against the stubs in <dir>.
#
# ---------------------------------------------------------------------------
# WHY THE INTERLOCK IS THE FIRST THING IN THE SCRIPT AND NOT A LINE IN A
# DISPATCH (S35-1).
#
# The rule is "do not flash the CPLD with the analog rails possibly up". It
# was carried as prose in successive dispatches, and every session that met it
# read GPIO26 by hand. S35 found the pin HIGH and found out why: the app
# asserts AN_EN itself, unconditionally, in Boot.Init(), nine lines before it
# reads the MCU list. So the interlock is not met rarely — it is met NEVER
# while matrix-app runs, and two earlier sessions had already recorded
# "AN_EN never asserted" meaning "this session did not assert it", which reads
# as "the pin was low". It was not.
#
# A rule nobody can execute is not a rule, so it goes in the tool. This script
# reads the pin itself, refuses on HIGH, and refuses on anything it cannot
# parse — fail closed, because an unreadable interlock is an unmet one.
#
# S35-1 left PW three ways to rule, and each has a flag rather than a
# workaround:
#
#   * stop matrix-app and re-read the pin      --stop-app
#   * gate on something that tracks the rails  (needs hardware; not this tool)
#   * confirm the board is detached and waive  --an-en-waived "<reason>"
#
# --stop-app does NOT assume the pin follows the app down. S35 could not say
# whether it does, because S35 did not stop the app. The script stops it,
# waits, re-reads, and then applies the same refusal to the new reading. If
# GPIO26 stays high with the app stopped, that is a finding and the flash
# still does not happen.
#
# ---------------------------------------------------------------------------
# WHY ONE ATTEMPT, WHEN loadlogic.sh RETRIES THREE TIMES.
#
# loadlogic.sh moves the bench between known-good bitstreams and a retry is
# free. This script exists for the other case: putting something NEW on the
# part, where a half-written configuration is the thing to be afraid of. So
# the discipline is FLASH-OK ON ATTEMPT 1, or the rollback goes back
# immediately — before anything else is tried, and from a copy whose md5 was
# taken while the part was still known-good.
#
# The rollback is verified to EXIST and its md5 recorded BEFORE the first
# write. A rollback discovered to be missing after a failed flash is not a
# rollback.
#
# WHAT COUNTS AS OK is S27-5's answer, not the IDCODE: a MAX V answers its
# IDCODE from the JTAG tap whether or not the configuration flash took. The
# check is that openocd's command chain reached its `shutdown` with no `tdo
# check error` on the way. The IDCODE is still read before AND after, because
# it separates "the flash failed" from "the tap was never there".
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
BENCH="${BENCH:-app@192.168.1.219}"
BITDIR="${BITDIR:-$HERE/../../shared/dsp4-logic/bitstream}"
ROLLBACK="dsp4_logic.a1f6672af6c3.svf"
DRYRUN=0; STOPAPP=0; RESTART=1; WAIVER=""; SELFTEST=""
ARG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)            DRYRUN=1 ;;
    --rollback)           ROLLBACK="${2:?--rollback needs an svf}"; shift ;;
    --stop-app)           STOPAPP=1 ;;
    --leave-app-stopped)  RESTART=0 ;;
    --an-en-waived)       WAIVER="${2:-}"; shift ;;
    --self-test)          SELFTEST="${2:?--self-test needs a stub dir}"; shift ;;
    -h|--help)            sed -n '2,60p' "$0"; exit 0 ;;
    -*)                   echo "unknown option: $1" >&2; exit 2 ;;
    *)                    ARG="$1" ;;
  esac
  shift
done

[ -n "$ARG" ] || { echo "usage: $0 [options] <svf|label>   (--help for options)" >&2; exit 2; }

# A waiver must carry a reason. `--an-en-waived` on its own is the thing this
# whole header exists to prevent.
if [ -n "${WAIVER-}" ] && [ -z "${WAIVER// /}" ]; then
  echo "!! --an-en-waived requires the written reason as its argument." >&2
  echo "   e.g. --an-en-waived 'PW 2026-09-12: analog board detached, confirmed by hand'" >&2
  exit 2
fi

# ---- Resolve the artifact on the desk -------------------------------------
# Accept a path, a bare filename, or a 12-hex build label.
if [ -f "$ARG" ]; then
  SRC="$ARG"
elif [ -f "$BITDIR/$ARG" ]; then
  SRC="$BITDIR/$ARG"
else
  MATCH=$(ls "$BITDIR"/*"$ARG"*.svf 2>/dev/null)
  COUNT=$(printf '%s\n' "$MATCH" | grep -c . )
  if [ "$COUNT" = "1" ]; then SRC="$MATCH"
  elif [ "$COUNT" = "0" ]; then
    echo "!! no svf matching '$ARG' in $BITDIR" >&2; exit 2
  else
    echo "!! '$ARG' matches $COUNT artifacts — name one:" >&2
    printf '%s\n' "$MATCH" | sed 's|.*/|   |' >&2; exit 2
  fi
fi
case "$SRC" in
  *.svf) ;;
  *.pof) echo "!! openocd plays SVF, not POF. Use ${SRC%.pof}.svf" >&2; exit 2 ;;
  *)     echo "!! not an svf: $SRC" >&2; exit 2 ;;
esac

SVF=$(basename "$SRC")
MD5=$(md5sum "$SRC" | cut -d' ' -f1)
MANIFEST="${SRC%.svf}.manifest"

echo "== logic_flash: $SVF"
echo "   desk copy  : $SRC"
echo "   desk md5   : $MD5"
if [ -f "$MANIFEST" ]; then
  sed -n 's/^/   manifest   : /p' "$MANIFEST" | head -20
else
  echo "   manifest   : NONE BESIDE IT — this artifact cannot say what it is."
fi
echo "   rollback   : $ROLLBACK"
[ "$DRYRUN" = "1" ] && echo "   MODE       : DRY RUN — every gate and read, no write"
[ -n "$WAIVER" ]    && echo "   AN_EN      : WAIVED — $WAIVER"

# ---- Stage it, and prove the copy arrived intact --------------------------
if [ -z "$SELFTEST" ]; then
  if ! ssh "$BENCH" "test -f /home/app/$SVF"; then
    echo "== staging $SVF to the bench"
    [ "$DRYRUN" = "1" ] && { echo "   (dry run: not copying)"; }
    if [ "$DRYRUN" = "0" ]; then
      scp -q "$SRC" "$BENCH:/home/app/" || { echo "!! scp failed" >&2; exit 3; }
    fi
  fi
fi

# Both forms take the remote half as ONE argument string and the heredoc on
# stdin, so the same bytes run over ssh and under --self-test.
RUN=(ssh "$BENCH")
[ -n "$SELFTEST" ] && RUN=(env "PATH=$SELFTEST:$PATH" bash -c)

"${RUN[@]}" "SVF='$SVF' MD5='$MD5' ROLLBACK='$ROLLBACK' DRYRUN='$DRYRUN' \
      STOPAPP='$STOPAPP' RESTART='$RESTART' WAIVER='$WAIVER' bash -s" <<'REMOTE'
set -u
cd /home/app 2>/dev/null || cd .
LOG=./logic-flash.log
say() { echo "$@"; }
rec() { { echo "$(date -u +%FT%TZ) [logic_flash] $*"; } >> "$LOG" 2>/dev/null; }

rec "=== session: $SVF md5=$MD5 rollback=$ROLLBACK dryrun=$DRYRUN waiver='${WAIVER:-none}'"

fail() { say "   !! $1"; rec "REFUSED: $1"; exit "${2:-4}"; }

# ---- The artifact is here and is the file the desk hashed ----------------
[ -f "$SVF" ] || fail "$SVF is not staged on the bench" 3
BENCH_MD5=$(md5sum "$SVF" | cut -d' ' -f1)
say "   bench md5  : $BENCH_MD5"
[ "$BENCH_MD5" = "$MD5" ] || fail "md5 MISMATCH desk=$MD5 bench=$BENCH_MD5 — the staged copy is not the artifact" 3
rec "md5 verified on the bench: $BENCH_MD5"

# ---- The rollback exists NOW, before anything is written ------------------
# A rollback discovered to be missing after a failed flash is not a rollback.
[ -f "$ROLLBACK" ] || fail "rollback $ROLLBACK is NOT on the bench — refusing to write anything" 3
RB_MD5=$(md5sum "$ROLLBACK" | cut -d' ' -f1)
say "   rollback   : $ROLLBACK ($RB_MD5) — present"
rec "rollback verified present: $ROLLBACK $RB_MD5"

# ---- Optional: PW's shape-1 ruling — stop the app, then RE-READ ----------
APP_WAS=""
if [ "$STOPAPP" = "1" ]; then
  APP_WAS=$(systemctl is-active matrix-app 2>/dev/null || true)
  say "   matrix-app : $APP_WAS -> stopping (GPIO26 will be RE-READ, not assumed)"
  rec "stopping matrix-app (was: $APP_WAS)"
  if [ "$DRYRUN" = "0" ]; then
    sudo systemctl stop matrix-app >/dev/null 2>&1
    sleep 3
  else
    say "   (dry run: matrix-app left alone; the read below is the LIVE pin)"
  fi
fi

# ---- THE INTERLOCK -------------------------------------------------------
# Fail closed. An interlock that cannot be read is an interlock that is not
# met, and `pinctrl` not being there at all is the loudest version of that.
command -v pinctrl >/dev/null 2>&1 || fail "pinctrl is not on this bench — cannot read AN_EN, so cannot flash" 4
RAW=$(pinctrl get 26 2>&1)
say "   AN_EN (26) : $RAW"
rec "pinctrl get 26: $RAW"

# pinctrl prints e.g. `26: op -- pd | hi // GPIO26 = output`. Take the level
# from the field after the `|` and nowhere else, so a comment or a pin alias
# containing "hi"/"lo" cannot decide an interlock.
LEVEL=$(printf '%s\n' "$RAW" | sed -n 's/.*|[[:space:]]*\(hi\|lo\)\b.*/\1/p' | head -1)
case "$LEVEL" in
  lo) AN_EN=low ;;
  hi) AN_EN=high ;;
  *)  AN_EN=unreadable ;;
esac
say "   AN_EN state: $AN_EN"

if [ "$AN_EN" != "low" ]; then
  if [ -n "${WAIVER:-}" ]; then
    say "   !! AN_EN is $AN_EN and the interlock is WAIVED IN WRITING:"
    say "      $WAIVER"
    rec "INTERLOCK WAIVED (AN_EN=$AN_EN): $WAIVER"
  else
    say ""
    say "   !! AN_EN IS ${AN_EN^^} — NOT FLASHING."
    if [ "$AN_EN" = "high" ]; then
      say "      The analog rails may be up and the analog board may be attached."
      say "      If matrix-app is running this is EXPECTED, not a fault: the app"
      say "      asserts AN_EN in Boot.Init() at every boot (S35-1). The pin being"
      say "      high is not evidence that anyone raised it on purpose."
      say ""
      say "      PW's ruling decides which of these applies:"
      say "        --stop-app                    stop matrix-app and re-read the pin"
      say "        --an-en-waived '<reason>'     board confirmed detached, in writing"
      say "      There is no third option in this tool, and no default."
    else
      say "      'pinctrl get 26' did not say hi or lo, so the interlock could not"
      say "      be read. That is treated as NOT MET. Raw output is above."
    fi
    rec "REFUSED: AN_EN=$AN_EN, no waiver"
    [ "$STOPAPP" = "1" ] && [ "$RESTART" = "1" ] && [ "$DRYRUN" = "0" ] && {
      say "   restarting matrix-app"; sudo systemctl start matrix-app >/dev/null 2>&1; }
    exit 5
  fi
fi

# ---- IDCODE before -------------------------------------------------------
idcode() {
  sudo openocd -f cpld-jtag.cfg -c 'init; scan_chain; shutdown' 2>&1 \
    | sed -n 's/.*tap\/device found: \(0x[0-9a-fA-F]*\).*/\1/p' | head -1
}
handback() {
  # openocd's linuxgpiod driver leaves its GPIOs claimed, which kills the DSP
  # SPI link and looks exactly like a bricked card. The canonical sequence is
  # S8-3's, not the a0-everything line restore_bench.sh still carries.
  sudo pinctrl set 6,24 op dh >/dev/null 2>&1
  sudo pinctrl set 8,12 ip >/dev/null 2>&1
  sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
  sleep 2
}

BEFORE=$(idcode)
say "   IDCODE before: ${BEFORE:-NONE}"
rec "IDCODE before: ${BEFORE:-NONE}"
[ -n "$BEFORE" ] || say "   !! NO TAP BEFORE THE FLASH — the JTAG chain is not answering"

if [ "$DRYRUN" = "1" ]; then
  say ""
  say "   DRY RUN — every gate above passed and NOTHING was written."
  say "   The real run is the same command without --dry-run."
  rec "DRY RUN complete, no write attempted"
  handback
  [ "$STOPAPP" = "1" ] && [ "$RESTART" = "1" ] && sudo systemctl start matrix-app >/dev/null 2>&1
  exit 0
fi

# ---- ONE attempt ---------------------------------------------------------
play() {
  sudo openocd -f cpld-jtag.cfg -c "init; svf -tap cpld.tap $1; shutdown" \
    > /tmp/logic-flash.out 2>&1
  RC=$?
  { echo "=== $(date -u +%FT%TZ) $1 rc=$RC"; cat /tmp/logic-flash.out; } >> "$LOG"
  # S27-5: the IDCODE is not the check. The chain reaching its shutdown with
  # no tdo check error is.
  grep -q 'shutdown command invoked' /tmp/logic-flash.out \
    && ! grep -qiE 'tdo check error|mismatch|verify failed' /tmp/logic-flash.out
}

say "   -- flashing $SVF (ONE attempt)"
if play "$SVF"; then
  say "   FLASH-OK on attempt 1"
  rec "FLASH-OK attempt 1: $SVF $MD5"
  OUTCOME=0
else
  say "   !! FLASH FAILED ON ATTEMPT 1. What openocd said:"
  grep -iE 'tdo check error|mismatch|verify failed|error' /tmp/logic-flash.out \
    | grep -v 'Translation from khz' | head -6 | sed 's/^/      /'
  grep -q 'shutdown command invoked' /tmp/logic-flash.out \
    || say '      (the command chain never reached its shutdown — the svf aborted)'
  rec "FLASH FAILED attempt 1: $SVF"
  say "   -- ROLLING BACK to $ROLLBACK"
  if play "$ROLLBACK"; then
    say "   ROLLBACK OK — the part is back on $ROLLBACK ($RB_MD5)"
    rec "ROLLBACK OK: $ROLLBACK $RB_MD5"
    OUTCOME=7
  else
    say "   !! ROLLBACK ALSO FAILED. THE CPLD IS IN AN UNKNOWN STATE."
    say "      Do not power-cycle expecting it to recover; a MAX V keeps its"
    say "      configuration flash. Full openocd output: $LOG"
    rec "ROLLBACK FAILED — CPLD state UNKNOWN"
    OUTCOME=8
  fi
fi

AFTER=$(idcode)
say "   IDCODE after : ${AFTER:-NONE}"
rec "IDCODE after: ${AFTER:-NONE}"

handback

if [ "$STOPAPP" = "1" ] && [ "$RESTART" = "1" ]; then
  say "   restarting matrix-app (it will re-assert AN_EN — S35-1)"
  sudo systemctl start matrix-app >/dev/null 2>&1
  rec "matrix-app restarted"
fi

# The part cannot be trusted to say what it is: bitstreams older than the
# design-ID stamp have no identity in them at all (S35-3). Read it back where
# the artifact does carry one.
if [ "$OUTCOME" = "0" ]; then
  say ""
  say "   NEXT: confirm what is actually on the part —"
  say "     cd /home/app/dspboot && python3 dsp4_logic_id.py"
  say "   A bitstream built before the design-ID stamp answers nothing, and"
  say "   its identity then rests on this log and nowhere else."
fi
exit $OUTCOME
REMOTE
RC=$?
echo "== logic_flash exit $RC"
exit $RC
