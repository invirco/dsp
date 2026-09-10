#!/bin/bash
set -u
PP="$1"
cd "${STAGE:-/home/app/dspboot}"
sudo systemctl stop matrix-app >/dev/null 2>&1
for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
done
for c in 1 2 3; do
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
  R=$(python3 audio_verdict.py 3 "$PP" 2>&1)
  echo "$R" | grep -q "BOOT_STAGE 7" && { echo "$R" | tail -3; exit 0; }
done
echo "$R" | tail -3
