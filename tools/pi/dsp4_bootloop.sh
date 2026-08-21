#!/bin/bash
# dsp4_bootloop.sh — repeat a real boot on demand, so the boot-shaped
# edges recur on a scope.
#
# A single boot is ~8 ms of 1 MHz SPI and one 50 ms !RST_D pulse, which is
# hard to catch by hand. This repeats it every few seconds until stopped.
# Unlike dsp4_scopedrive.sh this is the REAL traffic — SPI mode 1, the
# actual .ldr, the CS window — so it is what to probe once the level check
# has passed.
#
#   dsp4_bootloop.sh start            # rdyprobe1.ldr on chip 1, every 3 s
#   dsp4_bootloop.sh start 2          # chip 2 (rdyprobe2.ldr)
#   dsp4_bootloop.sh start 1 5        # chip 1, every 5 s
#   dsp4_bootloop.sh status
#   dsp4_bootloop.sh log
#   dsp4_bootloop.sh stop
#
# start stops matrix-app (it shares CS1-6 with H1S1) and stop restarts it.
# GPIO10/11 must be in ALT0 for spidev to clock anything: this script sets
# that mux on every start, because releasing a gpiod line leaves the pin an
# input and nothing puts it back.
set -u
DIR=/home/app/dspboot
PID=$DIR/bootloop.pid
LOG=$DIR/bootloop.log

case "${1:-}" in
start)
  CHIP="${2:-1}"; PERIOD="${3:-3}"
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already running (pid $(cat "$PID")); stop it first"; exit 1
  fi
  sudo systemctl stop matrix-app
  pinctrl set 9 a0; pinctrl set 10 a0; pinctrl set 11 a0
  cd "$DIR" || exit 1
  nohup bash -c "while true; do
      echo \"--- \$(date -Is) boot chip $CHIP ---\"
      python3 dsp4_boot.py --ldr rdyprobe$CHIP.ldr --chip $CHIP 2>&1
      sleep $PERIOD
    done" >"$LOG" 2>&1 &
  echo $! > "$PID"
  sleep 2
  echo "boot loop running (pid $(cat "$PID")), chip $CHIP every ${PERIOD}s; \
matrix-app stopped. Log: $LOG"
  tail -8 "$LOG"
  ;;
stop)
  if [ -f "$PID" ]; then
    pkill -P "$(cat "$PID")" 2>/dev/null
    kill "$(cat "$PID")" 2>/dev/null
    rm -f "$PID"
  fi
  sudo systemctl restart matrix-app
  echo "stopped; matrix-app restarted."
  ;;
status)
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "running (pid $(cat "$PID"))"; tail -8 "$LOG"
  else
    echo "not running"
  fi
  ;;
log) tail -f "$LOG" ;;
*) sed -n '2,20p' "$0"; exit 1 ;;
esac
