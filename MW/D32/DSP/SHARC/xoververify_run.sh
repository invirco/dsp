#!/bin/bash
# xoververify_run.sh — bench half of xoververify.sh.
#
# famverify_run.sh's boot/config ladder, unchanged: boot until chip 2
# answers AS chip 2, configure BOTH chips (chip 2's main loop is gated on
# CONFIG_COMMIT and never runs its graph without it), gate on the PACED
# reader, repair the CFG_COMMIT header word that lands in strip 1's gain on
# roughly one boot in three.
set -u
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

PRODUCT="${PRODUCT:-d24}"

ready() {
  timeout 60 python3 - <<'PY' 2>/dev/null
import sys
sys.argv = ['p']
import dsp4_scope as S
ok = 0
try:
    sc = S.Scope(2)
    sc.d.resync()
    for _ in range(6):
        if sc.rd(0xE000) == 0xD5B40001 and sc.rd(0xE001) == 2 and sc.rd(0xE002) >= 6:
            ok = 1
            break
except Exception:
    pass
print(ok)
PY
}

for cycle in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  python3 dsp4_config.py --product "$PRODUCT" --chip 1 >/dev/null 2>&1; sleep 3
  python3 dsp4_config.py --product "$PRODUCT" --chip 2 \
          --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: chip 2 link never usable"; continue; }
  python3 dsp4_diag.py --chip 2 >/dev/null 2>&1
  python3 gainfix.py >/dev/null 2>&1
  ARGS="--landed landed-$PRODUCT.json --n ${N:-1024} --json ${OUT:-xoververify.json}"
  python3 dsp4_xover_verify.py $ARGS
  exit $?
done
echo "no usable boot in 3 cycles"
exit 4
