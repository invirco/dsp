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
  python3 dsp4_config.py --product "$PRODUCT" --chip 1 >/dev/null 2>&1; sleep 3
  python3 dsp4_config.py --product "$PRODUCT" --chip 2 \
          --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: chip 2 link never usable"; continue; }
  python3 dsp4_diag.py --chip 2 >/dev/null 2>&1
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
      loadfx) RQ="--require-driven --require-fx --fx-type $FXTYPE" ;;
  esac
  python3 dsp4_c2regime.py --chip 1 --tag driven $RQ \
          --json "$P-regime-c1.json" > "$P-regime-c1.log" 2>&1
  R1=$?
  python3 dsp4_c2regime.py --chip 2 --tag driven $RQ \
          --json "$P-regime-c2.json" > "$P-regime-c2.log" 2>&1
  R2=$?
  grep -h "DRIVEN REGIME\|FX REGIME" "$P-regime-c1.log" "$P-regime-c2.log" \
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
                  --fx-type "$T" --json "$P-fx$T-regime.json" \
                  > "$P-fx$T-regime.log" 2>&1
      fi
      RF=$?
      grep -h "FX REGIME" "$P-fx$T-regime.log" 2>/dev/null
      [ "$RF" = "0" ] || echo "    FX REGIME NOT PROVEN (rc=$RF) -- the rung is"\
          "taken anyway and labelled; see $P-fx$T-regime.log"
      python3 dsp4_capacity.py --dwell "${DWELL:-45}" --tag "fx-$T" \
              --json "$P-D-fx$T.json" || RC=$?
  done

  bash /home/app/drive_audio.sh stop >/dev/null 2>&1
  exit $RC
done
echo "no usable boot in 3 cycles"
exit 4
