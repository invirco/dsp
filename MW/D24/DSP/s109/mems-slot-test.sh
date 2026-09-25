#!/usr/bin/env bash
# mems-slot-test.sh -- WHICH TDM SLOT IS THE PANEL MIC ON? (🔴 S109-4)
#
# S109 brought the MEMS lane alive: `digital U13` is an ADAU7002, its
# MEMS_CONFIG resistor puts it on TDM slots 5-6 ONE-BASED = 0-based 4 and 5,
# and BOTH of those carry after the CPLD fix. The datasheet argument says the
# mic is the LEFT channel = slot 4 (`lswitch U3` IMP34DT05 has LR tied to GND,
# DS12725 Table 6) and the tree is built that way. But `M_I2S` has no pull
# resistor, so the half U13 tri-states decodes to something that MOVES too,
# and from the desk the two slots cannot be told apart. Only a sound at the
# panel separates them.
#
# THIS SCRIPT IS THE WHOLE TEST. Run it, tap the panel when it says to, read
# the last three lines. It boots the slot-4 pair, then the slot-5 pair, takes
# a QUIET BASELINE for each before asking for any sound, and scores the tap
# window against that baseline -- so a lane that is merely noisy cannot pass.
#
#     ssh app@<unit>
#     cd /home/app && ./mems-slot-test.sh
#
# WHAT IT DOES TO THE UNIT
#   * `AN_EN` (GPIO26) is NEVER WRITTEN. It is read and reported. This test
#     reads a microphone; it needs no analog rails.
#   * NO audio is played, nothing is sent to the panel speaker, the 595
#     mic-pre chain is not written, no codec register is written, no CPLD is
#     flashed.
#   * it DRIVES `CS_M` (GPIO27) high and it stops `matrix-app` (see below).
#   * it boots the DSP pair twice per slot -- that is the recipe, not a retry.
#
# THE TWO STANDING BENCH RULES IT CARRIES, so nobody has to remember them:
#
#   CS_M: `pinctrl set 27 op dh`, DRIVEN, not `ip pu`. GPIO27 gates the U2
#   analog MISO buffer, and a CS_M that is low puts U2 on MISO so the DSP
#   parameter link will not phase -- it presents as "MAGIC never came back"
#   on a perfectly healthy part. `ip pu` was the recipe until 2026-09-25 and
#   IS NO LONGER ENOUGH (S109-5): the pin read `ip pu | hi`, the fix
#   apparently applied, and the link still would not phase over four boots.
#   The pull no longer holds the pin against whatever sinks it. Going from
#   `ip pu|hi` to `op dh` creates no edge, so it does not clock the 595 latch.
#
#   DOUBLE BOOT+CONFIG: `dsp4_config.py`'s commit desyncs the parameter link
#   every time (pre-existing, reproduces on the original image), so the whole
#   boot+config cycle is run TWICE. It then reaches BOOT_STAGE 7. A single
#   pass leaves the chips at BOOT_STAGE 5 and every reading taken there is
#   fiction.
#
# WHY IT SAMPLES INSTEAD OF CAPTURING. `dsp4_rxscan.py --reps 32` reads 32
# words out of the RX DMA region spread over the scan's wall clock, not 32
# consecutive samples -- so the waveform is scrambled and PEAK UNDER-READS by
# up to ~6 dB. That is fine here and it is why the verdict is a RELATIVE one:
# the same instrument, the same lane, the same image, quiet vs tapped. It is
# not a level measurement and must never be quoted as one.
#
# Options:
#   --dry-run          print every command and touch nothing (runs anywhere)
#   --reduce-only DIR  re-score an existing run's JSONs and exit
#   --quiet-secs N     quiet baseline window, default 10
#   --tap-secs N       tap window, default 15
#   --stop-app         required only if `matrix-app` is RUNNING (see below)
#   --outdir DIR       where the JSONs land, default /home/app/s109-memsslot

set -uo pipefail

EXPECT_DESIGN=4de0dd4a
SLOT4_DIR=/home/app/loopthd/s109      # lane 7 mask 0x0010 -> 0-based slot 4
SLOT5_DIR=/home/app/loopthd/s103      # lane 7 mask 0x0020 -> 0-based slot 5
LANE=XIN_MEMS
REPS=32
QUIET_SECS=10
TAP_SECS=15
OUTDIR=/home/app/s109-memsslot
DRY=0
STOP_APP=0
REDUCE_ONLY=

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)      DRY=1 ;;
    --stop-app)     STOP_APP=1 ;;
    --quiet-secs)   QUIET_SECS="${2:?}"; shift ;;
    --tap-secs)     TAP_SECS="${2:?}"; shift ;;
    --outdir)       OUTDIR="${2:?}"; shift ;;
    --reduce-only)  REDUCE_ONLY="${2:?}"; shift ;;
    -h|--help)      sed -n '2,60p' "$0"; exit 0 ;;
    *)              echo "unknown option: $1" >&2; exit 64 ;;
  esac
  shift
done

say()  { printf '%s\n' "$*"; }
rule() { printf '%s\n' "------------------------------------------------------------"; }
die()  { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }

# run: echo under --dry-run, execute otherwise.
run() {
  if [ "$DRY" = 1 ]; then printf '  + %s\n' "$*"; return 0; fi
  "$@"
}
# runq: same, but the command is a shell string (needs a subshell).
runq() {
  if [ "$DRY" = 1 ]; then printf '  + %s\n' "$1"; return 0; fi
  bash -c "$1"
}

# ---------------------------------------------------------------- reducer ---
# Reads every <slot>-<phase>-NN.json a run produced and prints the verdict.
# Split out so it can be re-run on an old directory (--reduce-only) and so it
# can be exercised on synthetic JSONs with no unit present.
reduce() {
  python3 - "$1" "$LANE" <<'PYEOF'
import glob, json, os, sys

d, lane = sys.argv[1], sys.argv[2]
SLOTS = (('slot4', 4), ('slot5', 5))
PHASES = ('quiet', 'tap')


def series(slot, phase):
    """(n_scans, best_rms, best_peak, controls_all_ok) for one window."""
    rms, peak, ctl_ok, n = [], [], True, 0
    for f in sorted(glob.glob(os.path.join(d, '%s-%s-*.json' % (slot, phase)))):
        try:
            j = json.load(open(f))
        except Exception:
            continue
        n += 1
        m = j.get('meta') or {}
        if not m.get('frame_count_delta'):
            ctl_ok = False
        for c in (m.get('controls') or {}).values():
            if c.get('distinct', 1) != 1:
                ctl_ok = False
        row = next((r for r in (j.get('lanes') or [])
                    if r.get('node') == lane), None)
        if row is None or 'rms_dbfs' not in row:
            continue
        rms.append(row['rms_dbfs'])
        peak.append(row['peak_dbfs'])
    if not rms:
        return n, None, None, ctl_ok
    return n, max(rms), max(peak), ctl_ok


print('')
print('%-7s %-6s %5s %11s %11s' % ('slot', 'phase', 'scans', 'best rms', 'best peak'))
res = {}
for slot, num in SLOTS:
    row = {}
    for phase in PHASES:
        n, r, p, ok = series(slot, phase)
        row[phase] = (n, r, p, ok)
        print('%-7s %-6s %5d %11s %11s%s'
              % (slot, phase, n,
                 '--' if r is None else '%.2f' % r,
                 '--' if p is None else '%.2f' % p,
                 '' if ok else '   [CONTROLS FAILED]'))
    res[slot] = row

print('')
verdicts = {}
for slot, num in SLOTS:
    q, t = res[slot]['quiet'], res[slot]['tap']
    if q[1] is None or t[1] is None:
        print('slot %d: NO DATA -- %s window produced no %s reading'
              % (num, 'quiet' if q[1] is None else 'tap', lane))
        continue
    if not (q[3] and t[3]):
        print('slot %d: NO VERDICT -- rxscan controls failed; the peek path '
              'was not trustworthy' % num)
        continue
    d_rms, d_peak = t[1] - q[1], t[2] - q[2]
    # 3 dB on the best-of-N rms is well outside the scan-to-scan spread that
    # a quiet lane shows (S109 read the same lane twice, twenty minutes and a
    # reboot apart, within ~7 dB on ONE scan each -- best-of-N is much
    # tighter). A tap on the panel is tens of dB, not units.
    moved = d_rms >= 3.0 or d_peak >= 3.0
    verdicts[num] = (moved, d_rms, d_peak)
    print('slot %d: %-12s rms %+6.2f dB, peak %+6.2f dB over its own quiet '
          'baseline' % (num, 'MOVED' if moved else 'did not move', d_rms, d_peak))

print('')
mv = [n for n, v in verdicts.items() if v[0]]
if len(verdicts) < 2:
    print('ANSWER: INCOMPLETE -- both slots need a quiet window and a tap '
          'window before this can be answered. Re-run.')
elif len(mv) == 1:
    n = mv[0]
    print('ANSWER: THE MIC IS ON SLOT %d.' % n)
    if n == 5:
        print('  The tree is built for slot 4, so this is a CHANGE: '
              'slot-map.csv `A_I7,4,MEMS_TB` -> `A_I7,5`, then regenerate. '
              'The CPLD does not change either way.')
    else:
        print('  That is what the tree is already built for '
              '(slot-map.csv `A_I7,4`). Nothing to change; S109-4 closes.')
elif len(mv) == 2:
    a, b = verdicts[4], verdicts[5]
    print('ANSWER: BOTH SLOTS MOVED -- this run does not separate them.')
    print('  slot 4 %+.2f dB rms, slot 5 %+.2f dB rms.' % (a[1], b[1]))
    print('  Most likely the tap was loud enough to reach the mic through the '
          'panel on both windows, or the tri-stated half is following the '
          'driven one. Re-run with a quieter, more localised tap (one '
          'fingernail next to the mic port, not a knock on the panel).')
else:
    print('ANSWER: NEITHER SLOT MOVED. The tap did not reach the mic, or the '
          'mic is not on either slot.')
    print('  Before concluding the second: was the tap during the printed '
          'window, and next to the mic port on the LEFT panel?')
PYEOF
}

if [ -n "$REDUCE_ONLY" ]; then
  reduce "$REDUCE_ONLY"
  exit 0
fi

# ------------------------------------------------------------- preflight ---
rule
say "MEMS SLOT TEST (S109-4) -- which TDM slot is the panel mic on?"
say "  no rails, no speaker, no audio played. AN_EN is never written."
rule

[ "$DRY" = 1 ] && say "*** DRY RUN: nothing below is executed. ***"

say ""
say "[1/6] rails and pins, read first"
if [ "$DRY" = 1 ]; then
  say "  + pinctrl get 26   (AN_EN -- READ ONLY, never written)"
  say "  + pinctrl get 27   (CS_M)"
else
  AN_EN=$(pinctrl get 26 2>&1) || true
  say "  AN_EN  $AN_EN"
  case "$AN_EN" in
    *hi*) say "  NOTE: the analog rails are UP. This test does not need them and"
          say "        will not lower them deliberately -- but stopping matrix-app"
          say "        DOES drop AN_EN (bench note 19), so if the mixer is running"
          say "        you will lose the rails when this proceeds." ;;
  esac
  say "  CS_M   $(pinctrl get 27 2>&1)"
fi

say ""
say "[2/6] is this the S109 bitstream?"
if ! runq "cd '$SLOT4_DIR' && python3 dsp4_logic_id.py --expect $EXPECT_DESIGN"; then
  die "the CPLD is not on design $EXPECT_DESIGN, or it did not answer.
  Both slots only carry on the S109 bitstream, so there is nothing to
  compare until it is on the part. If the read said 'no reply': the ID knock
  needs the DUPLEX PCM overlay and answers 'no reply' for EVERY bitstream on
  \`dsp4-pcm-slave\` -- check /boot/config.txt before believing the part is
  wrong (bench note 12)."
fi

say ""
say "[3/6] the bus: matrix-app must be down for the DSP pins"
if [ "$DRY" = 1 ]; then
  say "  + systemctl is-active matrix-app"
  say "  + sudo systemctl stop matrix-app   (only if it is active AND --stop-app)"
else
  if systemctl is-active --quiet matrix-app; then
    if [ "$STOP_APP" != 1 ]; then
      die "\`matrix-app\` is RUNNING. Booting the DSP pair needs the SPI/JTAG
  pins it owns, so it has to be stopped -- and stopping it DROPS AN_EN
  (bench note 19), which it will NOT raise again. That is a real change to
  the unit, so this script will not do it without being told:

      ./mems-slot-test.sh --stop-app

  Restoring AN_EN afterwards is \`sudo pinctrl set 26 op dh\` and it is the
  hub's to run, not this script's."
    fi
    say "  stopping matrix-app (--stop-app given)"
    run sudo systemctl stop matrix-app
    sleep 2
    say "  AN_EN now: $(pinctrl get 26 2>&1)"
  else
    say "  matrix-app already inactive -- nothing to stop."
  fi
fi

# CS_M and the boot pin hand-back. NOT `pinctrl set 6,7,8,...,25 a0`, which
# every older run script does and which leaves chip 2's CS asserted (GPIO24's
# ALT0 is SD0_DAT2, not a deasserted CS) so chip 2 boots chip1.ldr.
pins() {
  run sudo pinctrl set 7,9,10,11,22,23,25 a0
  run sudo pinctrl set 6,24 op dh     # the two chip selects, DEASSERTED
  run sudo pinctrl set 8,12 ip        # the two SPI_RDY lines
  # DRIVEN high, not pulled: since S109 a pull-up no longer holds CS_M, and a
  # low CS_M enables U2 onto MISO so the link cannot phase.
  run sudo pinctrl set 27 op dh
}
say ""
say "[4/6] pins"
pins

run mkdir -p "$OUTDIR"

# ------------------------------------------------------------------ boot ---
boot_pair() {   # $1 = stage dir
  local dir="$1"
  say "  boot+config, pass 1"
  runq "cd '$dir' && python3 dsp4_boot.py --dir ." || return 1
  runq "cd '$dir' && python3 dsp4_config.py --product d24 --chip 1" || true
  runq "cd '$dir' && python3 dsp4_config.py --product d24 --chip 2" || true
  # THE SECOND PASS IS THE RECIPE, NOT A RETRY: the config commit desyncs the
  # parameter link every time, and the pair only reaches BOOT_STAGE 7 after
  # the whole cycle has run twice.
  say "  boot+config, pass 2 (required -- see the header)"
  run sudo pinctrl set 6,24 op dh
  runq "cd '$dir' && python3 dsp4_boot.py --dir ." || return 1
  runq "cd '$dir' && python3 dsp4_config.py --product d24 --chip 1" || true
  runq "cd '$dir' && python3 dsp4_config.py --product d24 --chip 2" || true
  run sudo pinctrl set 6,24 op dh
  if [ "$DRY" = 1 ]; then say "  + dsp4_diag.py --chip 1 | grep BOOT_STAGE"; return 0; fi
  local st
  st=$(bash -c "cd '$dir' && python3 dsp4_diag.py --chip 1 2>&1" | grep -o 'BOOT_STAGE[^,]*' | head -1)
  say "  chip 1 $st"
  case "$st" in *7*) return 0 ;; esac
  say "  chip 1 did not reach BOOT_STAGE 7 -- readings from this pair are not"
  say "  trustworthy. (If the link would not phase at all, re-read CS_M.)"
  return 1
}

# ---------------------------------------------------------------- window ---
# Repeated scans across a window, best-of-N. One --reps 32 scan is ~1-3 s, so
# a 15 s window is several scans and the tap only has to land inside one.
window() {   # $1 = stage dir  $2 = slot tag  $3 = phase  $4 = seconds  $5 = banner
  local dir="$1" slot="$2" phase="$3" secs="$4" banner="$5" n=0 end
  if [ "$DRY" = 1 ]; then
    say "  + [$secs s] $banner"
    say "  + repeat for $secs s: cd $dir && python3 dsp4_rxscan.py --symdir . --reps $REPS --tag $slot-$phase --json $OUTDIR/$slot-$phase-NN.json"
    return 0
  fi
  end=$(( $(date +%s) + secs ))
  while [ "$(date +%s)" -lt "$end" ]; do
    n=$((n+1))
    printf '\n  >>> %s   [%d s left, scan %d]\n' "$banner" "$(( end - $(date +%s) ))" "$n"
    sudo pinctrl set 6,24 op dh
    bash -c "cd '$dir' && python3 dsp4_rxscan.py --symdir . --reps $REPS \
             --tag '$slot-$phase' --json '$OUTDIR/$slot-$phase-$(printf '%02d' $n).json'" \
      >"$OUTDIR/$slot-$phase-$(printf '%02d' $n).log" 2>&1 \
      || say "      (that scan did not complete -- see $OUTDIR/$slot-$phase-$(printf '%02d' $n).log)"
  done
  say "  $n scans written for $slot/$phase"
}

do_slot() {   # $1 = stage dir  $2 = slot tag  $3 = human slot number
  rule
  say "SLOT $3   ($1)"
  rule
  boot_pair "$1" || say "  continuing anyway so the run produces a record, but read the caveat above"
  say ""
  say "  QUIET BASELINE -- ${QUIET_SECS}s. Do not touch the unit, do not talk."
  window "$1" "$2" quiet "$QUIET_SECS" "QUIET PLEASE -- baseline, hands off"
  say ""
  say "  TAP WINDOW -- ${TAP_SECS}s."
  window "$1" "$2" tap "$TAP_SECS" "TAP THE LEFT PANEL NEXT TO THE MIC NOW"
}

say ""
say "[5/6] slot 4, then slot 5"
do_slot "$SLOT4_DIR" slot4 4
do_slot "$SLOT5_DIR" slot5 5

say ""
say "[6/6] verdict"
if [ "$DRY" = 1 ]; then
  say "  + reduce $OUTDIR"
else
  reduce "$OUTDIR"
  say ""
  rule
  say "unit as left: AN_EN never written ($(pinctrl get 26 2>&1))"
  say "              CS_M $(pinctrl get 27 2>&1) -- driven high, as the recipe now requires"
  say "              595 chain not written, no codec write, no CPLD flash, no audio played"
  say "              the slot-5 pair (s103) is the one left booted"
  say "raw scans:    $OUTDIR"
  rule
fi
