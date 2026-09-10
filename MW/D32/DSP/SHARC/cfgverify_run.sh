#!/bin/bash
# cfgverify_run.sh — bench half of cfgverify.sh (S20). Boot the staged image
# and print the two configuration words each chip reads back.
set -u
STAGE="${STAGE:-/home/app/dspboot}"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  echo ">>> BENCH LOCKED: waiting for the card." >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=cfgverify_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" \
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

for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
  python3 dsp4_checkchip.py --quiet || continue
  ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
  [ "$ID" = "2" ] && break
done
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 1 >/dev/null 2>&1; sleep 3
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 2 \
        --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
python3 gainfix.py >/dev/null 2>&1

for c in 1 2; do
  python3 dsp4_diag.py --chip $c 2>&1 | grep -E "CHIP_ID|BOOT_STAGE" | sed "s/^/CHIP$c /"
  python3 - "$c" <<'PY'
import sys
sys.path.insert(0, '/home/app/dspboot')
import dsp4_buildcfg as B
c = int(sys.argv[1])
w, w2 = B.read_word(c)
print('CHIP%d CFGWORDS 0x%08X,0x%08X' % (c, w, w2 if w2 is not None else 0))
for line in B.describe(B.decode(w)):
    print('CHIP%d   %s' % (c, line))
for line in B.describe2(B.decode2(w2)):
    print('CHIP%d   %s' % (c, line))
PY
done
