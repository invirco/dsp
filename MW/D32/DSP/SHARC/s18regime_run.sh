#!/bin/bash
# s18regime_run.sh — bench half of s18regime.sh (S17-6).
#
# capacity_run.sh's boot/config ladder, unchanged, with ONE addition: after
# the capacity dwell it also snapshots chip 2's branch state
# (dsp4_c2regime.py) on the SAME boot, so the cost regime and the graph state
# that produced it are one record. Boots are numbered and every artefact is
# tagged with the number, because the whole question is what differs BETWEEN
# boots.
set -u
STAGE="${STAGE:-/home/app/dspboot}"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  echo ">>> BENCH LOCKED: waiting for the card." >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=s18regime_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" \
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
BOOTS="${BOOTS:-6}"
DWELL="${DWELL:-45}"
PREFIX="${PREFIX:-s18r}"

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

for b in $(seq 1 "$BOOTS"); do
  echo "########## BOOT $b ##########"
  got=0
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
    [ "$(ready)" = "1" ] || { echo "boot $b cycle $cycle: chip 2 link never usable"; continue; }
    python3 dsp4_diag.py --chip 2 >/dev/null 2>&1
    python3 gainfix.py >/dev/null 2>&1
    got=1; break
  done
  [ "$got" = "1" ] || { echo "boot $b: no usable boot in 3 cycles"; continue; }
  python3 dsp4_capacity.py --dwell "$DWELL" --json "$PREFIX-cap-b$b.json"
  python3 dsp4_c2regime.py --chip 2 --tag "b$b" --json "$PREFIX-regime-b$b.json"
done
