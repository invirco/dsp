#!/bin/bash
# cfgstress_run.sh — bench half of cfgstress.sh (see dsp4_cfgstress.py).
set -u
cd /home/app/dspboot
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  holder="$(cat "$BENCH_LOCKFILE.info" 2>/dev/null)"
  echo ">>> BENCH LOCKED: waiting for the card ($BENCH_LOCKFILE)." >&2
  [ -n "$holder" ] && echo ">>> held by: $holder" >&2
  flock "$BENCH_LOCK_FD"
  echo ">>> BENCH LOCKED: acquired, proceeding." >&2
fi
printf 'pid=%s script=cfgstress_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1
python3 dsp4_cfgstress.py "$@"
