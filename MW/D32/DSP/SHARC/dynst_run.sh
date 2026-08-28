#!/bin/bash
# dynst_run.sh — boot the staged image and read the paired-dynamics verdict.
#
# Same boot/config retry ladder as sigprofile_run.sh: this bench needs up to
# three boot attempts and three config attempts on a bad day, and a peek is
# a two-transaction handshake the diag ISR backstop cannot serve, so "MAGIC
# reads but peeks return None" means the MAIN LOOP is wedged -- not that the
# numbers are zero.
set -u
CCLK="${1:-983040000}"
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

for attempt in 1 2 3; do
  G=$(boot_and_config)
  if [ "$G" = "0" ]; then echo "  (attempt $attempt: never reached stage 6)"; continue; fi
  python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A"
  sleep 3
  OUT=$(python3 dynst_read.py "$CCLK" 2>&1)
  echo "$OUT"
  echo "$OUT" | grep -q "^done      = 1" && exit 0
  echo "  (attempt $attempt: verdict unreadable — main loop wedged or link down)"
done
echo "no readable verdict in 3 attempts"
exit 4
