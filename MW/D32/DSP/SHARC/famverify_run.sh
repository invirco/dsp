#!/bin/bash
# famverify_run.sh — bench half of famverify.sh.
#
# Boot and config are RETRIED TOGETHER and the readiness gate is the PACED
# reader, for the reason goldnode_run.sh and conform_run.sh both carry: a
# boot that leaves chip 2 answering can still leave chip 1's diag link a
# word out of phase, re-running config alone never recovers it, and
# dsp4_diag.py's unpaced reader returns a well-formed WRONG answer rather
# than an error when it does.
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
  # BOOT UNTIL CHIP 2 ANSWERS AS CHIP 2. dsp4_boot.py can leave chip 2
  # running chip 1's firmware, and a mis-addressed link then answers as
  # chip 1 regardless -- so every chip-2 symbol address is wrong and the
  # capture is fiction. c2gold_run.sh established this retry; the first
  # run of this bar skipped it and lost every chip-2 family with
  # "link answers as CHIP 1".
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  python3 dsp4_config.py --product "$PRODUCT" --chip 1 >/dev/null 2>&1; sleep 3
  # CHIP 2 NEEDS ITS OWN CS AND RDY LINES. Without them dsp4_config.py
  # configures chip 1 a second time and chip 2's main loop, which is gated
  # on CONFIG_COMMIT, never runs its node graph at all.
  python3 dsp4_config.py --product "$PRODUCT" --chip 2 \
          --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: link never usable"; continue; }
  # The scope link needs a resync the diag link does not; a diag read walks
  # it back (the same guard goldnode_run.sh and bqst_run.sh take).
  python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
  # gainfix repairs the CFG_COMMIT header word that lands in strip 1's gain
  # on roughly one boot in three (bench recipe item 7a). A dead strip is a
  # CHEAP strip and it would read as INERT for every family downstream.
  python3 gainfix.py >/dev/null 2>&1
  ARGS="--landed landed-$PRODUCT.json --n ${N:-64} --json ${OUT:-famverify.json}"
  ARGS="$ARGS --bq-arm ${BQ_ARM:-float}"
  [ -n "${FAMILIES:-}" ] && ARGS="$ARGS --families $FAMILIES"
  [ -n "${CHIPS:-}" ] && ARGS="$ARGS --chips $CHIPS"
  python3 dsp4_family_verify.py $ARGS
  exit $?
done
echo "no usable boot in 3 cycles"
exit 4
