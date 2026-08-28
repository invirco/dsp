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
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
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
