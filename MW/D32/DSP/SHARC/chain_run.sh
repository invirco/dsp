#!/bin/bash
# chain_run.sh — boot the staged image, configure, run chain.py.
#
# The retry sits around chain.py, not around dsp4_diag: CONFIG_COMMIT
# leaves the parameter link one word out of phase often enough that
# BOOT_STAGE reads 0 or MAGIC reads 0 from a part that is running
# perfectly well, and re-opening the link is what clears it. chain.py's
# own check_chip is the honest gate (it refuses a link answering as chip
# 0), so retry THAT and only fall back to a fresh boot when a whole
# batch of attempts fails.
set -u
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
# chain_run.sh has no parent script to stage its tools, so it says so rather
# than failing three boots in a row with a misleading message.
[ -f /home/app/dspboot/dsp4_checkchip.py ] || {
  echo "chain_run.sh: /home/app/dspboot/dsp4_checkchip.py is missing — scp it"
  echo "  from tools/pi/ first; the chip-identity gate (S8-3) is not optional." >&2
  exit 3; }
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  for t in 1 2 3 4 5 6 7 8; do
    O=$(python3 chain.py 2>&1)
    # Retry on ANY unusable link, not just the CHIP-id refusal: a
    # CFG_COMMIT phase slip also shows up as a parameter write that will
    # not read back (chain.py's first wrv raises), and as a strip whose
    # GAIN target has been zeroed. Both are the same defect and both are
    # cleared by re-opening the link or re-running boot+config.
    case "$O" in
      *"link answers as CHIP"*|*"Traceback"*|*"would not take"*) sleep 2; continue;;
    esac
    python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|FRAME_COUNT|DMA0_STAT|SPORT0_ERR_A"
    echo "$O"
    exit 0
  done
  echo "cycle $cycle: link never usable, re-booting"
done
echo "chain.py never got a usable link"
exit 1
