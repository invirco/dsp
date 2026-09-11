#!/bin/bash
# capacity_run.sh — bench half of capacity.sh.
#
# fxcost_run.sh's boot/config ladder, unchanged, because it is the one that
# works: boot until chip 2 answers AS chip 2, configure BOTH chips (chip 2's
# main loop is gated on CONFIG_COMMIT and never runs its graph without it),
# gate on the PACED reader, repair the CFG_COMMIT header word that lands in
# strip 1's gain on roughly one boot in three.
#
# The one difference from every other run script in this tree: it runs from
# $STAGE and never assumes /home/app/dspboot, because ~/dspboot holds the
# pairs the window rolls back to (S10-7).
set -u
STAGE="${STAGE:-/home/app/dspboot}"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  echo ">>> BENCH LOCKED: waiting for the card." >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=capacity_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" \
    > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# The line that used to be here, `pinctrl set 6,7,8,9,10,11,12,22,23,24,25
# a0`, is WRONG: GPIO24 in ALT0 is SD0_DAT2, not a deasserted chip select,
# so chip 2's CS sits asserted while chip 1's boot stream clocks out and the
# card comes up as TWO CHIP 1s. Six consecutive boots did that on 2026-09-09
# and only dsp4_scope.check_chip caught it — through dsp4_diag.py the card
# looks healthy with a wrong CHIP_ID, and every number taken through it is
# fiction. The chip selects (6 = chip 1, 24 = chip 2) are therefore HELD AS
# OUTPUTS DRIVEN HIGH, the two SPI_RDY lines (8, 12) are plain inputs, which
# is what gpiod claims them as, and only the SPI and JTAG pins go back to a0.
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

PRODUCT="${PRODUCT:-d24}"
# THE SCOPE CLASS, OVERRIDABLE (S29). Empty = the product's own default.
# `SCOPE_ID=1` on a D32 arm sends the D32 masks with the D24 scope word, so
# the 32 snake nodes are gated off exactly the way every other product gates
# them and nothing else about the arm changes. See dsp4_config.py.
SCOPE_ID="${SCOPE_ID:-}"
SCOPE_ARG=""
[ -n "$SCOPE_ID" ] && SCOPE_ARG="--scope-id $SCOPE_ID"

ready() {
  timeout 60 python3 - <<'PY' 2>/dev/null
import sys
sys.argv = ['p']
import dsp4_scope as S
ok = 0
try:
    sc = S.Scope(2)
    sc.d.resync()
    for _ in range(6):
        if sc.rd(0xE000) == 0xD5B40001 and sc.rd(0xE001) == 2 and sc.rd(0xE002) >= 6:
            ok = 1
            break
except Exception:
    pass
print(ok)
PY
}

for cycle in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  python3 dsp4_config.py --product "$PRODUCT" $SCOPE_ARG --chip 1 \
          >/dev/null 2>&1; sleep 3
  python3 dsp4_config.py --product "$PRODUCT" $SCOPE_ARG --chip 2 \
          --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: chip 2 link never usable"; continue; }
  python3 dsp4_diag.py --chip 2 >/dev/null 2>&1
  # WHICH SCOPE CLASS THE PART IS ACTUALLY IN (S29). `_product_id` is
  # published at DIAG_PRODUCT_ID (0xE010) and it is the only word the scope
  # gates read, so an arm that claims to have gated the snake off says so
  # here in the part's own words rather than in the invocation's.
  for C in 1 2; do
      PID=$(python3 dsp4_diag.py --chip $C 2>/dev/null \
            | awk '/PRODUCT_ID/ {print $2}')
      echo "    chip $C: PRODUCT_ID (scope class) = ${PID:-unreadable}"
  done
  python3 gainfix.py >/dev/null 2>&1

  if [ "${DRIVEN:-0}" = "0" ]; then
      python3 dsp4_capacity.py --dwell "${DWELL:-45}" \
              --tag "${TAG:-silence}" --json "${OUT:-capacity.json}"
      exit $?
  fi

  # ------------------------------------------------------------------
  # THE DRIVEN LADDER (S19). THREE ROWS ON ONE BOOT, ONE CLOCK, ONE IMAGE.
  #
  # Until S19 every capacity row in this tree was row A, and nobody said
  # so. S18 then measured what row A is worth on chip 2 -- 92.7 % silent
  # against 112.3 % with the dynamics engaged, same image, same product --
  # and the record had no number a budget could use. Taking all three on
  # ONE boot is what makes them subtractable: the same measured clock, the
  # same DMA phase, the same parameter state except for the one thing each
  # step changes.
  #
  #   A  sil-default   silent, the config the product boots with.
  #                    Comparable with every figure already in the record,
  #                    which is the only reason it is still taken.
  #   B  sil-load      silent, with the LOAD config applied: every bus
  #                    assign and send open, every dynamics node on with a
  #                    -60 dB threshold. B - A is what the CONFIGURATION
  #                    costs (more crosspoints accumulate), with no signal
  #                    anywhere.
  #   C  driven        the same config with the stimulus playing. C - B is
  #                    what the SIGNAL costs, which is the whole of the
  #                    dynamics' expensive branch and nothing else.
  #
  # C is the product number. The regime is PROVED on both chips before C
  # is taken (`--require-driven`: every envelope word live), because a
  # driven row whose graph was quietly still on the cheap branch is the
  # error this whole instrument exists to end.
  # ------------------------------------------------------------------
  P="${PREFIX:-cap}"
  LANDED="landed-$PRODUCT.json"
  # HOW MANY FX ENGINES THIS PRODUCT DEFINES (S28-2). The image carries six
  # and the landed map is what says how many the product has: D16 and D12
  # define four, so `loadfx` reaches Fx001..Fx004 and the other two stay
  # unfed on their cheap branch. Read off the map rather than the product
  # name, so a product whose def changes does not need this script changed.
  FXN=$(python3 - "$LANDED" <<'PYEOF'
import json, re, sys
n = 0
for cell in json.load(open(sys.argv[1]))['cells']:
    m = re.match(r'^Fx(\d+)', cell)
    if m:
        n = max(n, int(m.group(1)))
print(n)
PYEOF
)
  echo "    product defines $FXN FX engine(s) (from $LANDED)"
  bash /home/app/drive_audio.sh stop >/dev/null 2>&1

  echo "--- row A: silent, default config"
  python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag sil-default \
          --json "$P-A-sil-default.json" || exit 5

  echo "--- load config"
  MODE="${SETUP_MODE:-load}"
  FXTYPE="${FXTYPE:-3}"
  python3 dsp4_driven_setup.py --chip 1 --mode "$MODE" --fx-type "$FXTYPE" \
      --landed "$LANDED" \
      > "$P-setup-c1.log" 2>&1; echo "    chip 1: $(tail -1 "$P-setup-c1.log")"
  python3 dsp4_driven_setup.py --chip 2 --mode "$MODE" --fx-type "$FXTYPE" \
      --landed "$LANDED" \
      > "$P-setup-c2.log" 2>&1; echo "    chip 2: $(tail -1 "$P-setup-c2.log")"

  echo "--- row B: silent, load config"
  python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag sil-load \
          --json "$P-B-sil-load.json" || exit 5

  echo "--- stimulus on"
  bash /home/app/drive_audio.sh start || exit 6
  sleep 3
  RQ=""
  case "$MODE" in
      load)   RQ="--require-driven" ;;
      loadfx) RQ="--require-driven --require-fx --fx-type $FXTYPE --fx-engines ${FXN:-0}" ;;
  esac
  python3 dsp4_c2regime.py --chip 1 --tag driven $RQ \
          --json "$P-regime-c1.json" > "$P-regime-c1.log" 2>&1
  R1=$?
  python3 dsp4_c2regime.py --chip 2 --tag driven $RQ \
          --json "$P-regime-c2.json" > "$P-regime-c2.log" 2>&1
  R2=$?
  grep -h "DRIVEN REGIME\|FX REGIME\|FX SCOPE" "$P-regime-c1.log" "$P-regime-c2.log" \
      2>/dev/null
  if [ "$R1" != "0" ] || [ "$R2" != "0" ]; then
      echo "    REGIME NOT PROVEN (chip1 rc=$R1 chip2 rc=$R2) -- row C is taken"
      echo "    anyway and is labelled, because a partial regime is a"
      echo "    measurement of a partial regime and not nothing; see the logs."
  fi

  echo "--- row C: DRIVEN"
  python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag driven \
          --json "$P-C-driven.json"
  RC=$?

  # ------------------------------------------------------------------
  # THE FX LADDER (S21), OPTIONAL, ON THE SAME BOOT AS ROW C.
  #
  # PW's headroom rule needs the FX engines' cost, and a cost is a
  # DIFFERENCE. Taking the difference across boots would put the
  # instrument's own boot-to-boot spread (±0.3 points, S20) into a number
  # that is itself only a few points, so every rung is taken here: same
  # image, same measured clock, same DMA phase, same routes and dynamics,
  # and the ONLY thing that changes between two rungs is the six engines'
  # `Type` cell (or their `On` cell for the `off` rung).
  #
  #   FXTYPES="off 3 0 2"   the baseline, the reverb, echo, doubling
  #
  # The regime is proved before every rung, and a rung whose regime does
  # not prove is labelled rather than dropped -- a partial regime is a
  # measurement of a partial regime.
  # ------------------------------------------------------------------
  for T in ${FXTYPES:-}; do
      echo "--- rung fx=$T"
      if [ "$T" = "off" ]; then
          M="fxoff"; FT=""
      else
          M="fxtype"; FT="--fx-type $T"
      fi
      python3 dsp4_driven_setup.py --chip 2 --mode "$M" $FT \
              --landed "$LANDED" > "$P-fx$T-setup.log" 2>&1
      echo "    setup: $(tail -1 "$P-fx$T-setup.log")"
      if [ "$T" = "off" ]; then
          python3 dsp4_c2regime.py --chip 2 --tag "fx-$T" \
                  --json "$P-fx$T-regime.json" > "$P-fx$T-regime.log" 2>&1
      else
          python3 dsp4_c2regime.py --chip 2 --tag "fx-$T" --require-fx \
                  --fx-type "$T" --fx-engines "${FXN:-0}" \
                  --json "$P-fx$T-regime.json" \
                  > "$P-fx$T-regime.log" 2>&1
      fi
      RF=$?
      grep -h "FX REGIME" "$P-fx$T-regime.log" 2>/dev/null
      [ "$RF" = "0" ] || echo "    FX REGIME NOT PROVEN (rc=$RF) -- the rung is"\
          "taken anyway and labelled; see $P-fx$T-regime.log"
      python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag "fx-$T" \
              --json "$P-D-fx$T.json" || RC=$?
  done

  # THE LOAD, PUT BACK, IF BOTH LADDERS RUN ON THIS BOOT (S29).
  #
  # The FX ladder's `off` rung leaves the six engines OFF, and the USE
  # ladder's `--mode use` writes crosspoint families only -- it does not
  # touch FX. So a boot that ran `FXTYPES="off"` and then went straight into
  # USELEVELS would take S24's worst-use rung with the plugin load absent,
  # which is not the row S24 measured and not the row that overruns. Until
  # S29 no arm set both variables, so this could not happen; S29 needs rows
  # A/B/C/D and the worst-use rung on ONE boot, and this is what makes that
  # legitimate. An arm that sets only one of the two is untouched.
  if [ -n "${FXTYPES:-}" ] && [ -n "${USELEVELS:-}" ]; then
      echo "--- the load, re-applied before the USE ladder"
      for C in 1 2; do
          python3 dsp4_driven_setup.py --chip $C --mode "$MODE" \
                  --fx-type "$FXTYPE" --landed "$LANDED" \
                  > "$P-reload-c$C.log" 2>&1
          echo "    chip $C: $(tail -1 "$P-reload-c$C.log")"
      done
      python3 dsp4_c2regime.py --chip 2 --tag reload $RQ \
              --json "$P-reload-regime.json" > "$P-reload-regime.log" 2>&1
      RR=$?
      grep -h "DRIVEN REGIME\|FX REGIME\|FX SCOPE" "$P-reload-regime.log" \
          2>/dev/null
      [ "$RR" = "0" ] || echo "    REGIME NOT PROVEN after the reload"\
          "(rc=$RR) -- the USE rungs are taken anyway and labelled;"\
          "see $P-reload-regime.log"
  fi

  # ------------------------------------------------------------------
  # THE USE LADDER (S24), OPTIONAL, ON THE SAME BOOT AS ROW C.
  #
  # S23's rows price every new node RUNNING and its write-up says in as
  # many words what they do not price: the two costs proportional to USE.
  # An aux sum whose six coefficients are all zero takes the block-level
  # bypass; a matrix bus row whose thirty-two are all zero is skipped by
  # the fabric for one compare per block. So a desk that actually sends an
  # FX return to an aux, or a channel to a matrix, pays more than those
  # rows show -- and by how much was the one capacity question S23 left
  # open.
  #
  # Each rung is `fxaux:mtx` -- FX returns opened into EVERY aux bus, and
  # strips opened into EVERY matrix bus. Every rung writes the WHOLE
  # family, sources above the count explicitly off, so a rung is a
  # complete state and the ladder can be read in any order:
  #
  #   USELEVELS="0:0 1:0 6:0 0:1 0:32 6:32"
  #     0:0    the crosspoints closed -- the CONTROL, and it must
  #            reproduce row C on this same boot or the ladder is not
  #            measuring what it claims to
  #     1:0    one FX return into each of the twelve aux buses: what a bus
  #            costs when it stops being empty
  #     6:0    all six: the per-crosspoint slope, (6:0 - 1:0) / 12 / 5
  #     0:1    one strip into each of the four matrix buses
  #     0:32   all thirty-two
  #     6:32   WORST USE -- everything the desk can send, at once
  #
  # The FX-return aux crosspoints are chip 2's and the matrix sends are
  # chip 1's, so both chips are written at every rung.
  # ------------------------------------------------------------------
  # A rung is `fxaux:mtx` or `fxaux/buses:mtx/buses` -- the second form
  # is the BUS axis, which the first ladder said is the one that matters:
  # 1:0 cost chip 2 9.77 points and 6:0 cost 0.11 more, so almost the
  # whole price is a bus losing its bypass rather than a crosspoint doing
  # a MAC. `1/4:0` = one FX return into aux buses 1-4 and nothing else.
  for U in ${USELEVELS:-}; do
      UF="${U%%:*}"; UM="${U##*:}"
      UFB=0; UMB=0
      case "$UF" in */*) UFB="${UF##*/}"; UF="${UF%%/*}" ;; esac
      case "$UM" in */*) UMB="${UM##*/}"; UM="${UM%%/*}" ;; esac
      T="$UF-$UFB-$UM-$UMB"
      echo "--- rung use=$UF/${UFB:-all} aux : $UM/${UMB:-all} matrix" \
           "(sources per bus / buses)"
      for C in 1 2; do
          python3 dsp4_driven_setup.py --chip $C --mode use \
                  --use-fxaux "$UF" --use-fxaux-buses "$UFB" \
                  --use-mtx "$UM" --use-mtx-buses "$UMB" \
                  --landed "$LANDED" > "$P-use$T-c$C.log" 2>&1
          echo "    chip $C: $(tail -1 "$P-use$T-c$C.log")"
      done
      python3 dsp4_c2regime.py --chip 2 --tag "use-$T" \
              --json "$P-use$T-regime.json" \
              > "$P-use$T-regime.log" 2>&1
      RU=$?
      grep -h "DRIVEN REGIME" "$P-use$T-regime.log" 2>/dev/null
      [ "$RU" = "0" ] || echo "    REGIME NOT PROVEN (rc=$RU) -- the rung is"\
          "taken anyway and labelled; see $P-use$T-regime.log"
      python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag "use-$T" \
              --json "$P-E-use$T.json" || RC=$?
  done

  bash /home/app/drive_audio.sh stop >/dev/null 2>&1
  exit $RC
done
echo "no usable boot in 3 cycles"
exit 4
