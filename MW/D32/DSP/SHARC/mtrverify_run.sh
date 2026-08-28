#!/bin/bash
# mtrverify_run.sh — bench half of mtrverify.sh.
# Boots the staged image, configures it, repairs strip 1's GAIN over the
# link, lets the meter settle past its longest time constant, then runs
# the golden-reference comparison.
set -u
DWELL="${1:-20}"
MTR="${2:-C1_MTR_01}"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    O=$(python3 dsp4_diag.py --chip 1 2>&1)
    echo "$O" | grep -q "MAGIC          0xD5B40001" && break
  done
  # A strip running on the CFG_COMMIT header word meters SILENCE, and every
  # word below would then be compared against the wrong stimulus.
  python3 gainfix.py 2>&1 | sed 's/^/  /'
  G=${PIPESTATUS[0]}
  [ "$G" = "0" ] || { echo "  (attempt $attempt: gain witness still bad)"; continue; }
  sleep "$DWELL"
  # The diag link can come back a transaction out of phase and then
  # answers CHIP_ID 0; that is a link state, not a measurement, so retry
  # rather than reporting it as a meter result.
  for v in 1 2 3; do
    OUT=$(python3 dsp4_mtr_verify.py "$MTR" 2>&1); RC=$?
    case "$OUT" in *"link answers as CHIP"*|*UNREADABLE*) sleep 2; continue;; esac
    echo "$OUT"; exit $RC
  done
  echo "$OUT"
  echo "  (attempt $attempt: link never came into phase)" 
done
echo "no clean witness in 3 attempts"
exit 4
