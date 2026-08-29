#!/bin/bash
# conform_run.sh — bench half of conform.sh (see that file).
#
# Same boot/config retry ladder as pairgraph_run.sh, with one instrument
# changed. A conformance verdict taken through a half-configured graph is
# fiction -- an unconfigured strip answers every read with whatever the
# boot left behind, which reads exactly like a cell that does not exist --
# so the ladder has to be able to tell a configured part from an
# unconfigured one.
#
# THE READINESS CHECK USES THE PACED READER, NOT dsp4_diag.py.
# 2026-08-29: five boots in a row were discarded here because
# dsp4_diag.py could not answer the link at all after a config ("response
# out of step reading 0xE004 ... Check RESP_DROP") and even reported
# "CONFIG_COMMIT DID NOT LAND" -- while dsp4_scope's paced, voted read
# returned BOOT_STAGE 7 and PRODUCT_ID 1 off the same part, first try.
# Gating a run on the instrument that cannot read the link is how a
# working bench gets written off as dead.
set -u
CHIP="$1"; TAG="$2"
PHASE="${PHASE:-all}"; LIMIT="${LIMIT:-0}"; NEGCTL="${NEGCTL:-0}"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

# C=<chip> MODE=ident|ready probe -> prints 1 or 0
probe() {
  timeout 120 python3 - <<'EOF' 2>/dev/null
import os
import sys
sys.argv = ['p']
import dsp4_scope as S
chip = int(os.environ.get('C', '1'))
mode = os.environ.get('MODE', 'ident')
sc = S.Scope(chip)
sc.d.resync()
ok = 0
for _ in range(6):
    try:
        # CHIP_ID is checked because dsp4_boot.py can silently leave chip 2
        # running chip 1's firmware (dsp4_scope.Scope.check_chip carries the
        # same warning): every symbol address would then be wrong and every
        # verdict fiction.
        if sc.rd(0xE000) != 0xD5B40001 or sc.rd(0xE001) != chip:
            continue
        if mode == 'ready' and sc.rd(0xE002) < 6:
            continue
        ok = 1
        break
    except IOError:
        pass
print(ok)
EOF
}

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    [ "$(C=2 MODE=ident probe)" = "1" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product d24 --chip 2 >/dev/null 2>&1; sleep 2
    [ "$(C=$CHIP MODE=ready probe)" = "1" ] && { GOT=1; break; }
  done
  echo "$GOT"
}

LIM=""; [ "$LIMIT" != "0" ] && LIM="--limit $LIMIT"

for attempt in 1 2 3 4 5; do
  G=$(boot_and_config)
  if [ "$G" != "1" ]; then
    echo "  (attempt $attempt: chip $CHIP never reached stage 6)"; continue
  fi
  # gainfix repairs the one-in-three boot that leaves strip 1's GAIN
  # coefficient holding the CFG_COMMIT header word; see pairgraph_run.sh.
  if [ "$CHIP" = "1" ]; then python3 gainfix.py 2 2>&1 | sed 's/^/  /'; fi

  OK=0
  python3 dsp4_conform.py --plan plan.json --chip "$CHIP" --phase "$PHASE" \
      $LIM --out "conform_${TAG}_c${CHIP}.json" && OK=1
  if [ "$OK" = "1" ] && [ "$NEGCTL" = "1" ] && [ "$CHIP" = "1" ]; then
    # THE HARNESS MUST BE ABLE TO FAIL. Two controls, both required:
    #   1. a deliberately wrong expected unit must fail its cell
    #   2. writing without reading back must come out UNVERIFIED, never PASS
    python3 dsp4_conform.py --plan plan.json --chip 1 --phase effect \
        --negctl-unit ChanGateRng \
        --out "conform_${TAG}_c1_negunit.json" || OK=0
    python3 dsp4_conform.py --plan plan.json --chip 1 --phase presence \
        --no-verify --limit 64 \
        --out "conform_${TAG}_c1_noverify.json" || OK=0
  fi
  [ "$OK" = "1" ] && exit 0
  echo "  (attempt $attempt: harness did not complete — re-booting)"
done
echo "no usable conformance run in 5 attempts"
exit 4
