#!/bin/bash
# goldnode_run.sh — bench half of goldnode.sh.
#
# Boot, configure, then verify. The boot+config RETRY IS TOGETHER and the
# readiness gate is the PACED reader, for the reason bqst_run.sh and
# conform_run.sh both carry: a boot that leaves chip 2 answering can still
# leave chip 1's diag link a word out of phase, re-running config alone
# never recovers it, and dsp4_diag.py's unpaced reader returns a
# well-formed WRONG answer rather than an error when it does.
set -u
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

ready() {
  timeout 60 python3 - <<'PY' 2>/dev/null
import sys
sys.argv = ['p']
import dsp4_scope as S
ok = 0
try:
    sc = S.Scope(1)
    sc.d.resync()
    for _ in range(6):
        if sc.rd(0xE000) == 0xD5B40001 and sc.rd(0xE001) == 1:
            ok = 1
            break
except Exception:
    pass
print(ok)
PY
}

for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: link never usable"; continue; }
  # The scope link needs a resync the diag link does not; a diag read
  # walks it back (the same guard pairgraph_run.sh and bqst_run.sh take).
  python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
  python3 dsp4_node_verify.py --nodes "${NODES:-GATE,COMP,TUBE,FDR}" \
          --n "${N:-96}"
  RC=$?
  [ $RC -eq 2 ] || exit $RC       # 2 = could not measure; try another boot
  echo "cycle $cycle: no measurable stimulus, re-booting"
done
echo "no usable measurement in 3 boot cycles"
exit 4
