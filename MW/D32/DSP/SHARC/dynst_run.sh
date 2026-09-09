#!/bin/bash
# dynst_run.sh — boot the staged image and read the paired-dynamics verdict.
#
# Same boot/config retry ladder as sigprofile_run.sh: this bench needs up to
# three boot attempts and three config attempts on a bad day, and a peek is
# a two-transaction handshake the diag ISR backstop cannot serve, so "MAGIC
# reads but peeks return None" means the MAIN LOOP is wedged -- not that the
# numbers are zero.
set -u
CCLK="${1:-983040000}"
cd /home/app/dspboot
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

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      if echo "$O" | grep -q "MAGIC          0xD5B40001"; then
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}'); T=$(echo "$O"|grep TICKS|awk '{print $2}')
        if [ -n "$S" ] && [ "$T" != "0" ] && [ "$S" -ge 6 ] 2>/dev/null; then GOT=1; break; fi
      fi; sleep 1
    done
    [ "$GOT" = "1" ] && break
  done
  echo "$GOT"
}

for attempt in 1 2 3; do
  G=$(boot_and_config)
  if [ "$G" = "0" ]; then echo "  (attempt $attempt: never reached stage 6)"; continue; fi
  python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A"
  sleep 3
  OUT=$(python3 dynst_read.py "$CCLK" 2>&1)
  echo "$OUT"
  echo "$OUT" | grep -q "^done      = 1" && exit 0
  echo "  (attempt $attempt: verdict unreadable — main loop wedged or link down)"
done
echo "no readable verdict in 3 attempts"
exit 4
