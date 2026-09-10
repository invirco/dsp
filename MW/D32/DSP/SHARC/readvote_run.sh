#!/bin/bash
# readvote_run.sh — bench half of readvote.sh (see tools/pi/dsp4_readvote.py).
set -u
cd "${STAGE:-/home/app/dspboot}"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  holder="$(cat "$BENCH_LOCKFILE.info" 2>/dev/null)"
  echo ">>> BENCH LOCKED: waiting for the card ($BENCH_LOCKFILE)." >&2
  [ -n "$holder" ] && echo ">>> held by: $holder" >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=readvote_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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
# Boot and config first — the measurement is about a part known to be HEALTHY.
for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  S=$(python3 dsp4_diag.py --chip 1 2>&1 | grep -E "^BOOT_STAGE" | awk '{print $2}')
  M=$(python3 dsp4_diag.py --chip 1 2>&1 | grep -E "^MAGIC" | awk '{print $2}')
  echo "  boot attempt $t: BOOT_STAGE $S MAGIC $M"
  [ "$S" = "7" ] && break
done
python3 dsp4_readvote.py "$@"
