#!/bin/bash
# S170 bench proof (c): forced update at 19:00:00 with a slowed write, for PW's timed cable pull.
cd /home/app/s170
t=$(date -d "19:00:00" +%s); n=$(date +%s); [ $t -gt $n ] && sleep $((t-n))
if fuser /dev/serial0 >/dev/null 2>&1; then echo "$(date +%T) /dev/serial0 BUSY: not run"; exit 3; fi
./pedal-update update --force --block-delay-ms 1500
echo "exit=$?"
./pedal-update v
./pedal-update info
echo END
