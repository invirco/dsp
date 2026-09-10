#!/bin/bash
# numverify_run.sh — bench half of numverify.sh. Boot the staged image,
# configure it, then read the self-test's results back.
#
# The self-test runs from the main loop once, BEFORE any configuration is
# needed -- it touches no node state and no parameter -- so this does not
# repair a strip or wait for a time constant the way mtrverify_run.sh
# does. What it does need is a link that answers as chip 1, which is the
# usual CONFIG_COMMIT phase-slip retry.
set -u
ARG="${1:-}"
cd "${STAGE:-/home/app/dspboot}"
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

for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  for t in 1 2 3 4 5 6; do
    OUT=$(python3 dsp4_num_verify.py $ARG 2>&1); RC=$?
    case "$OUT" in
      *"link answers as CHIP"*|*Traceback*|*"NEVER RAN"*) sleep 2; continue;;
    esac
    echo "$OUT"
    exit $RC
  done
  echo "cycle $cycle: link never usable"
done
echo "no usable link in 3 boot cycles"
exit 4
