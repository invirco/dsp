#!/bin/bash
# bqst_run.sh — boot the staged image and read the biquad self-test verdict.
set -u
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
# Retry BOOT AND CONFIG TOGETHER, not one then the other. A boot that
# leaves chip 2 answering can still leave chip 1's diag link out of phase,
# and re-running config alone never recovers it -- measured 2026-08-29,
# where three config retries in a row read MAGIC 0 and a single further
# boot+config came up first time.
for t in 1 2 3 4 5; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  python3 dsp4_diag.py --chip 1 2>&1 | grep -q "MAGIC          0xD5B40001" && break
done
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|MAGIC"
python3 dsp4_bq_verify.py /home/app/dspboot/chip1.sym.json "$1"
