#!/bin/bash
# pairgraph_run.sh — bench half of pairgraph.sh (see that file).
#
# Same boot/config retry ladder as sigprofile_run.sh: this bench needs up
# to three boot attempts and three config attempts on a bad day, and a
# capture taken through a half-configured graph is fiction.
set -u
STRIP="$1"; N="$2"; TAG="$3"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      if echo "$O" | grep -q "MAGIC          0xD5B40001"; then
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}'); T=$(echo "$O"|grep TICKS|awk '{print $2}')
        if [ -n "$S" ] && [ "$T" != "0" ] && [ "$S" -ge 6 ] 2>/dev/null; then GOT=1; break; fi
      fi; sleep 1
    done
    [ "$GOT" = "1" ] && break
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
  D=$(python3 dsp4_diag.py --chip 1 2>&1)
  echo "$D" | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A" | sed 's/^/  /'
  S=$(echo "$D" | grep BOOT_STAGE | awk '{print $2}')
  if [ -z "$S" ] || [ "$S" -lt 6 ] 2>/dev/null; then
    echo "  (attempt $attempt: BOOT_STAGE reads $S — link down, re-booting)"
    continue
  fi
  python3 gainfix.py 2 2>&1 | sed 's/^/  /'
  if python3 dsp4_pairgraph.py --strip "$STRIP" -n "$N" --tag "$TAG" \
       --out "pairgraph_$TAG.json"; then
    exit 0
  fi
  echo "  (attempt $attempt: no capture — re-booting)"
done
echo "no usable capture in 5 attempts"
exit 4
