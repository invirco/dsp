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
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

attempt() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP_ID before believing anything: chip 2 can come up running chip 1's
    # firmware, and then every symbol address is wrong.
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
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
