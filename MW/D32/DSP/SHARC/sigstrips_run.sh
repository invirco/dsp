#!/bin/bash
# sigstrips_run.sh — bench half of sigstrips.sh (see that file).
# Boots the image already staged in ~/dspboot, scores it, and then proves
# the dynamics were on their SIGNAL path for that same run. The witness is
# not optional: a ceiling taken with the gate shut is a silence number.
set -u
PP="$1"; N="$2"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
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
echo "$R" | tail -3
python3 dsp4_dyn_witness.py "$N" 2>&1 | tail -2
