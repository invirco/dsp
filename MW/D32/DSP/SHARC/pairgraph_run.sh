#!/bin/bash
# pairgraph_run.sh — bench half of pairgraph.sh (see that file).
#
# Same boot/config retry ladder as sigprofile_run.sh: this bench needs up
# to three boot attempts and three config attempts on a bad day, and a
# capture taken through a half-configured graph is fiction.
set -u
STRIP="$1"; N="$2"; TAG="$3"; BQ="${4:-}"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

# THE READINESS CHECK USES THE PACED READER, NOT dsp4_diag.py, and this
# file learned that late. conform_run.sh recorded it on 2026-08-29: five
# boots in a row were discarded there because dsp4_diag.py could not answer
# the link after a config while dsp4_scope's paced, VOTED read returned
# BOOT_STAGE 7 off the same part, first try. This script kept the diag gate
# and spent 2026-08-30 discarding good boots for it -- busgold, bqgraph and
# every captable point that reported "BOOT_STAGE reads  — link down" were
# gated on the instrument that cannot read the link, not on the part.
probe() {   # C=<chip> MODE=ident|ready -> prints 1 or 0
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
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    [ "$(C=1 MODE=ready probe)" = "1" ] && { GOT=1; break; }
  done
  echo "$GOT"
}

# THE WITNESS COMES BEFORE THE CAPTURE, for the same reason it does in
# sigprofile_run.sh: roughly one boot+config in three leaves strip 1's GAIN
# coefficient holding the CFG_COMMIT header word, and a capture taken in
# that state is a capture of a dead strip -- which is all zeros, which is
# also what a dropped arm looks like. gainfix repairs it over the link.
for attempt in 1 2 3 4 5; do
  G=$(boot_and_config)
  [ "$G" = "0" ] && { echo "  (attempt $attempt: never reached stage 6)"; continue; }
  python3 dsp4_diag.py --chip 1 2>&1 \
    | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A" | sed 's/^/  /'
  # THE SCOPE LINK NEEDS A RESYNC that the diag link does not. dsp4_diag
  # answers cleanly while Scope(1).check_chip() reads CHIP 0 -- the two
  # open the transaction differently and the parameter link can be sitting
  # one word out of phase. A diag read walks it back into phase, so every
  # scope-side tool here gets one in front of it and a few goes at it.
  # Without this the run burns all five boot attempts on a link state.
  #
  # EXPLAINED 2026-08-31 (D74): the word of phase is real and this note had
  # it right; what it could not know is that BOTH tools were guessing at it
  # from the echo's position, which cannot distinguish the two
  # arrangements. dsp4_diag.py now calibrates the phase against DIAG_MAGIC
  # and dsp4_scope.py decodes with the same answer, so the diag read in
  # front is no longer load-bearing. The ladder is left in place because it
  # also covers boot and config retries, which are separate matters.
  for g in 1 2 3 4 5 6; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    python3 gainfix.py 2 > /tmp/gf.log 2>&1 && break
    sleep 2
  done
  sed 's/^/  /' /tmp/gf.log
  for g in 1 2 3 4; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    if python3 dsp4_pairgraph.py --strip "$STRIP" -n "$N" --tag "$TAG" $BQ \
         --out "pairgraph_$TAG.json"; then
      exit 0
    fi
    sleep 2
  done
  echo "  (attempt $attempt: no capture — re-booting)"
done
echo "no usable capture in 5 attempts"
exit 4
