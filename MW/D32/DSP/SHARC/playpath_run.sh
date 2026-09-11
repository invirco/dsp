#!/bin/bash
# playpath_run.sh — bench half of playpath.sh.  See tools/pi/dsp4_s29_playpath.py.
#
# Boot the staged pair, configure it, put the main bus in the pass-through
# state the latency arm uses, and then walk the playback chain stage by
# stage with the stimulus on and off.  It answers ONE question -- where the
# CM4's playback stops on its way to C2_MAIN_ST_OUT -- and it answers it
# without the duplex PCM overlay, because every reading is taken off the
# DSP over SPI and not through the capture path.
set -u
STAGE="${STAGE:-/home/app/dspboot}"
cd "$STAGE"
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

if [ "${BOOT:-1}" = "1" ]; then
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  for c in 1 2 3; do
    python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 2 \
            --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
    S1=$(python3 dsp4_diag.py --chip 1 2>&1 | grep BOOT_STAGE | awk '{print $2}')
    S2=$(python3 dsp4_diag.py --chip 2 2>&1 | grep BOOT_STAGE | awk '{print $2}')
    [ -n "$S1" ] && [ "$S1" -ge 6 ] 2>/dev/null && \
    [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && break
  done
  echo "  boot: chip1 stage=$S1 chip2 stage=$S2"
  python3 gainfix.py 2>&1 | sed 's/^/  /'
fi

# THE PASS-THROUGH STATE, the same one latency_run.sh sets: every strip off
# the main bus and muted, the groups muted, USB/BT/codec-aux off, and the Pi
# playback input open at unity into an unmuted, undelayed main chain.
if [ "${PASSTHRU:-1}" = "1" ]; then
  python3 dsp4_passthru_setup.py 2>&1 | sed 's/^/  /'
fi

python3 dsp4_s29_playpath.py --samples "${SAMPLES:-12}" ${EXTRA:-}
