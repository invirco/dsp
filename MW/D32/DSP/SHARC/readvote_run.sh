#!/bin/bash
# readvote_run.sh — bench half of readvote.sh (see tools/pi/dsp4_readvote.py).
set -u
cd /home/app/dspboot
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  holder="$(cat "$BENCH_LOCKFILE.info" 2>/dev/null)"
  echo ">>> BENCH LOCKED: waiting for the card ($BENCH_LOCKFILE)." >&2
  [ -n "$holder" ] && echo ">>> held by: $holder" >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=readvote_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
# Boot and config first — the measurement is about a part known to be HEALTHY.
for t in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  S=$(python3 dsp4_diag.py --chip 1 2>&1 | grep -E "^BOOT_STAGE" | awk '{print $2}')
  M=$(python3 dsp4_diag.py --chip 1 2>&1 | grep -E "^MAGIC" | awk '{print $2}')
  echo "  boot attempt $t: BOOT_STAGE $S MAGIC $M"
  [ "$S" = "7" ] && break
done
python3 dsp4_readvote.py "$@"
