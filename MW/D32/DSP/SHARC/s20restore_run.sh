#!/bin/bash
# s20restore_run.sh — bench half of s20restore.sh (S20).
set -u
PAIR="${PAIR:-blk}"
SCRATCH="${SCRATCH:-/home/app/dspcap/restore}"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"
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

# COPY, NEVER BOOT FROM ~/dspboot (S10-7): the staged pairs are the artifacts
# the window rolls back to.
mkdir -p "$SCRATCH"
for f in /home/app/dspboot/*.py; do ln -sfn "$f" "$SCRATCH/$(basename "$f")"; done
cp "/home/app/dspboot/${PAIR}_chip1.ldr" "$SCRATCH/chip1.ldr"
cp "/home/app/dspboot/${PAIR}_chip2.ldr" "$SCRATCH/chip2.ldr"
if [ -f "/home/app/dspboot/${PAIR}_chip1.sym.json" ]; then
  cp "/home/app/dspboot/${PAIR}_chip1.sym.json" "$SCRATCH/chip1.sym.json"
  cp "/home/app/dspboot/${PAIR}_chip2.sym.json" "$SCRATCH/chip2.sym.json"
  echo "restore: ${PAIR}_* has symbol maps — cycle words are quotable"
else
  echo "restore: ${PAIR}_* has NO symbol map (it predates the practice) —"
  echo "restore: cycle words are NOT quotable for it; DIAG_FRAME_COUNT and"
  echo "restore: DIAG_BLK_OVERRUN are named registers and are unaffected"
fi
echo "restore: booting $PAIR  $(md5sum "$SCRATCH/chip1.ldr" | cut -c1-8) / $(md5sum "$SCRATCH/chip2.ldr" | cut -c1-8)"
cd "$SCRATCH"
for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
  python3 dsp4_checkchip.py --quiet || continue
  ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
  [ "$ID" = "2" ] && break
done
python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
for c in 1 2; do
  python3 dsp4_diag.py --chip $c 2>&1 | grep -E "CHIP_ID|BOOT_STAGE|MAGIC" | sed "s/^/  chip$c /"
done
# The OVERRUN line is the point of this dwell, and it carries a '%' -- an
# earlier filter here dropped it along with the meaningless cycle words. Keep
# the arbiter and the frame count; drop only the cycle words a stale map makes
# fiction.
python3 dsp4_capacity.py --dwell "${DWELL:-30}" --tag restore --json restore.json \
    2>&1 | grep -viE "_proc_cyc|budget cycles|CCLK decoded" | tail -20
sudo systemctl start matrix-app >/dev/null 2>&1; sleep 8
systemctl is-active matrix-app | sed 's/^/  matrix-app: /'
sudo journalctl -u matrix-app --since "-30 s" --no-pager 2>/dev/null \
    | grep -ciE "H1S1|H1S3|H1S4" | sed 's/^/  MCU announce lines: /'
