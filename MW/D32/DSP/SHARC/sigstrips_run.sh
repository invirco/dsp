#!/bin/bash
# sigstrips_run.sh — bench half of sigstrips.sh (see that file).
# Boots the image already staged in ~/dspboot, scores it, and then proves
# the dynamics were on their SIGNAL path for that same run. The witness is
# not optional: a ceiling taken with the gate shut is a silence number.
#
# The witness also has to be allowed to FAIL THE POINT AND RETRY, because
# roughly a third of boot+config cycles leave strip 1's GAIN coefficient
# holding 0xF0040000 -- the CFG_COMMIT transaction's own header word --
# instead of 1.0, which zeroes everything downstream of GAIN while
# BOOT_STAGE, pass rate, DMA and SPORT all stay clean (root-caused
# 2026-08-28; see tasks.md). In that state a signal build silently reports
# the SILENCE cycle count, 17% low. Re-running boot+config clears it.
set -u
PP="$1"; N="$2"
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

attempt() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
    # CHIP_ID before believing anything: chip 2 can come up running chip 1's
    # firmware, and then every symbol address is wrong.
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
    # Repair any strip whose GAIN coefficient the config commit zeroed,
    # over the link, before spending a whole reboot on it. A dead strip is
    # a CHEAP strip, so it flatters a ceiling rather than failing it.
    python3 gainfix.py "$N" 2>&1 | sed 's/^/  /'
    R=$(python3 audio_verdict.py 3 "$PP" 2>&1)
    echo "$R" | grep -q "BOOT_STAGE 7" && break
  done
  W=$(python3 dsp4_dyn_witness.py "$N" 2>&1 | tail -2)
}

for try in 1 2 3; do
  attempt
  case "$W" in *"SIGNAL PRESENT"*|*"SILENT"*) break;; esac
  echo "  (retry $try: witness says the strip is not carrying signal)"
done
echo "$R" | tail -3
echo "$W"
