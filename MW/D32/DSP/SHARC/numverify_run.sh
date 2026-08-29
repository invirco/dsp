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
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
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
