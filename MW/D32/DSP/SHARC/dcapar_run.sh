#!/bin/bash
# dcapar_run.sh — bench half of dcapar.sh (see that file).
#
# Same boot/config retry ladder as conform_run.sh, unchanged, with the
# conformance sweep replaced by the D57/D59 probe. The ladder is the part
# that has to be identical: a defaults measurement taken through a
# half-configured graph is fiction, and an unconfigured strip answers
# every read with whatever the boot left behind.
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
CHIP=1
STRIP="${STRIP:-1}"; WORDS="${WORDS:-32}"; ATTEMPTS="${ATTEMPTS:-5}"
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

for attempt in $(seq 1 "${ATTEMPTS:-5}"); do
  G=$(boot_and_config)
  if [ "$G" != "1" ]; then
    echo "  (attempt $attempt: chip 1 never reached stage 6)"; continue
  fi
  # gainfix repairs the one-in-three boot that leaves strip 1's GAIN
  # coefficient holding the CFG_COMMIT header word; see pairgraph_run.sh.
  python3 gainfix.py 2 2>&1 | sed 's/^/  /'
  # Exit 0 means MEASURED, whatever the verdict: a before run is supposed
  # to report FAIL and re-booting five times over an expected failure is
  # only a way to spend the bench. Exit 2 is "could not measure".
  python3 dsp4_dcapar_probe.py --strip "$STRIP" --words "$WORDS" && exit 0
  echo "  (attempt $attempt: the probe could not measure — re-booting)"
done
echo "no usable dcapar run in $ATTEMPTS attempts"
exit 4
