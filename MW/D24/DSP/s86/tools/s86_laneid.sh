#!/bin/bash
set -u
STAGE=/home/app/s83tn
OUTDIR=/home/app/s86
mkdir -p "$OUTDIR"; cd "$STAGE"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"; flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s86_laneid.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect fd1cbfc1 2>&1 | sed 's/^/  /' )
sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
BOOTED=0
for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
  python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1
  sleep 3
  G1=0; G2=0
  for t in 1 2 3 4 5 6; do
    O=$(python3 dsp4_diag.py --chip 1 2>&1)
    echo "$O" | grep -q "MAGIC          0xD5B40001" && { S1=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}'); [ -n "$S1" ] && [ "$S1" -ge 6 ] 2>/dev/null && G1=1; }
    O2=$(python3 dsp4_diag.py --chip 2 2>&1)
    echo "$O2" | grep -q "MAGIC          0xD5B40001" && { S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}'); [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && G2=1; }
    [ "$G1" = "1" ] && [ "$G2" = "1" ] && { BOOTED=1; break; }
    sleep 1
  done
  [ "$BOOTED" = "1" ] && break
done
echo "  chip1 stage ${S1:-?}, chip2 stage ${S2:-?}"
[ "$BOOTED" = "1" ] || { echo "!! not booted"; exit 5; }
python3 $STAGE/s86_rxscan.py --symdir "$STAGE" --reps 12 --laneid \
    --tag laneid --json "$OUTDIR/rx-laneid.json" 2>&1 | tee "$OUTDIR/rx-laneid.txt"
