#!/bin/bash
# bqst_run.sh — boot the staged image and read the biquad self-test verdict.
set -u
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
  ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
done
for c in 1 2 3; do
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  O=$(python3 dsp4_diag.py --chip 1 2>&1)
  echo "$O" | grep -q "MAGIC          0xD5B40001" && break
done
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|MAGIC"
python3 bqst_read.py "$@"
