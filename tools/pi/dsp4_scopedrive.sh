#!/bin/bash
# dsp4_scopedrive.sh — bench wrapper for dsp4_scopedrive.py.
#
# Drives SCK (GPIO11, J6 pin 23), MOSI (GPIO10, J6 pin 19) and !RST_D
# (GPIO16, J6 pin 36) as steady push-pull square waves so a scope probe can
# be clipped on and left there. Each net gets a different frequency, so the
# scope identifies which pin the probe is on: SCK 1 kHz, MOSI 500 Hz,
# RST_D 250 Hz.
#
#   dsp4_scopedrive.sh start          # all three
#   dsp4_scopedrive.sh start SCK,MOSI # leave the DSPs out of reset
#   dsp4_scopedrive.sh hold RST_D=0   # hold one pin at DC, for a DMM
#   dsp4_scopedrive.sh status
#   dsp4_scopedrive.sh log            # follow the Pi-side readback
#   dsp4_scopedrive.sh stop           # stop AND give SPI0 its pins back
#
# start stops matrix-app (it must not be driving the bus underneath a
# measurement) and stop restarts it. GPIO10/11 belong to spidev normally,
# so no boot can run while this is driving; stop restores the ALT0 mux,
# which nothing else does — not even a matrix-app restart.
set -u
DIR=/home/app/dspboot
PID=$DIR/scopedrive.pid
LOG=$DIR/scopedrive.log

case "${1:-}" in
start)
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already running (pid $(cat "$PID")); stop it first"; exit 1
  fi
  sudo systemctl stop matrix-app
  cd "$DIR" || exit 1
  nohup python3 dsp4_scopedrive.py --pins "${2:-SCK,MOSI,RST_D}" \
      >"$LOG" 2>&1 &
  echo $! > "$PID"
  sleep 1
  echo "driving (pid $(cat "$PID")); matrix-app stopped. Log: $LOG"
  head -20 "$LOG"
  ;;
hold)
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already running (pid $(cat "$PID")); stop it first"; exit 1
  fi
  [ -n "${2:-}" ] || { echo "usage: $0 hold RST_D=0"; exit 1; }
  sudo systemctl stop matrix-app
  cd "$DIR" || exit 1
  nohup python3 dsp4_scopedrive.py --hold "$2" >"$LOG" 2>&1 &
  echo $! > "$PID"
  sleep 1
  echo "holding (pid $(cat "$PID")); matrix-app stopped. Log: $LOG"
  head -20 "$LOG"
  ;;
stop)
  if [ -f "$PID" ]; then
    kill "$(cat "$PID")" 2>/dev/null
    for _ in $(seq 1 20); do kill -0 "$(cat "$PID")" 2>/dev/null || break
      sleep 0.2; done
    rm -f "$PID"
  fi
  cd "$DIR" && python3 dsp4_scopedrive.py --restore
  sudo systemctl restart matrix-app
  echo "stopped; pins restored; matrix-app restarted."
  ;;
status)
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "running (pid $(cat "$PID"))"; tail -5 "$LOG"
  else
    echo "not running"
  fi
  pinctrl get 9,10,11,16
  ;;
log) tail -f "$LOG" ;;
*) sed -n '2,20p' "$0"; exit 1 ;;
esac
