#!/bin/bash
# s86_gate1.sh — IS THE RECEIVE PATH ALIVE? Read the DMA region, rails down
# and rails up, in one boot.
#
# The reading S80-S85 took was `_buf_C1_IN_nn`, which no block kernel writes.
# This reads `_rx_active_buf + off + k*stride` -- the SPORT RX DMA region
# itself -- for all 47 chip-1 RX entries, and carries the old symbol beside
# it as a control in the SAME pass so the two readings cannot be blamed on
# different bitstreams, rail states or boots.
#
# Rails down first, then up: a converter lane must answer differently to the
# analog front end coming alive, and that difference is the proof that what
# the DMA carries is the AK5558s and not a pattern from somewhere else.
set -u
STAGE="${STAGE:-/home/app/s83tn}"
OUTDIR=/home/app/s86
TAG="${TAG:-ship}"
EXPECT="${EXPECT:-83b3cc22}"
REPS="${REPS:-32}"
LANEID="${LANEID:-}"
mkdir -p "$OUTDIR"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s86_gate1.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

tobits() { local v="$1" i out=""; for ((i=7;i>=0;i--)); do out+=$(( (v>>i)&1 )); done; printf '%s' "$out"; }
chain_write() {
  local V=$(( $1 )) IMG="" i bits p1 p2
  bits=$(tobits "$V"); [ ${#bits} -eq 8 ] || { echo "  REFUSING: '${bits}'"; return 1; }
  for i in $(seq 1 24); do IMG+="$bits"; done; IMG+="00000000"
  [ ${#IMG} -eq 200 ] || { echo "  REFUSING: ${#IMG} bits"; return 1; }
  pinctrl set 9 ip pd; pinctrl set 10 op dl; pinctrl set 11 op dl; pinctrl set 27 op dh
  pass() { local out="" i b r; pinctrl set 27 op dl
    for ((i=0;i<200;i++)); do b=${IMG:$i:1}
      if [ "$b" = "1" ]; then pinctrl set 10 op dh; else pinctrl set 10 op dl; fi
      r=$(pinctrl get 9); case "$r" in *"| hi"*) out+="1";; *) out+="0";; esac
      pinctrl set 11 op dh; pinctrl set 11 op dl; done
    pinctrl set 27 op dh; printf '%s' "$out"; }
  echo "  sending 0x$(printf '%02X' $V) = $bits x24 + 00000000"
  p1=$(pass); p2=$(pass)
  [ "$p2" = "$IMG" ] && echo "  VERIFIED 200/200 at 0x$(printf '%02X' $V)" || echo "  MISMATCH"
  pinctrl set 9 a0 pd; pinctrl set 10 a0 pd; pinctrl set 11 a0 pd; pinctrl set 27 ip pu
}

echo "=== what is on the part ==="
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect "$EXPECT" 2>&1 | sed 's/^/  /' )

sudo systemctl stop matrix-app >/dev/null 2>&1

echo "=== boot the pair ==="
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
    echo "$O" | grep -q "MAGIC          0xD5B40001" && {
      S1=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}')
      [ -n "$S1" ] && [ "$S1" -ge 6 ] 2>/dev/null && G1=1; }
    O2=$(python3 dsp4_diag.py --chip 2 2>&1)
    echo "$O2" | grep -q "MAGIC          0xD5B40001" && {
      S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}')
      [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && G2=1; }
    [ "$G1" = "1" ] && [ "$G2" = "1" ] && { BOOTED=1; break; }
    sleep 1
  done
  [ "$BOOTED" = "1" ] && break
done
echo "  chip1 stage ${S1:-?}, chip2 stage ${S2:-?}"
[ "$BOOTED" = "1" ] || { echo "!! not booted -- no reading is takeable"; exit 5; }

echo
echo "=== ARM A: rails DOWN, 595 as found ==="
sudo pinctrl set 26 op dl; sleep 2; pinctrl get 26
python3 $STAGE/s86_rxscan.py --symdir "$STAGE" --reps "$REPS" $LANEID \
    --tag "$TAG-rails-down" --json "$OUTDIR/rx-$TAG-down.json" 2>&1 \
    | tee "$OUTDIR/rx-$TAG-down.txt"

echo
echo "=== ARM B: rails UP, 595 unmuted gain 63 ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2
python3 $STAGE/s86_rxscan.py --symdir "$STAGE" --reps "$REPS" $LANEID \
    --tag "$TAG-rails-up" --json "$OUTDIR/rx-$TAG-up.json" 2>&1 \
    | tee "$OUTDIR/rx-$TAG-up.txt"

echo
echo "=== summary ==="
python3 - <<PY
import json
for t in ('down', 'up'):
    d = json.load(open('$OUTDIR/rx-$TAG-%s.json' % t))
    print('rails %-5s  FRAME_COUNT +%-7d  mic %2d/%2d carrying, XIN %2d/%2d carrying'
          % (t, d['frame_count_delta'], d['mic_alive'], d['mic_read'],
             d['xin_alive'], d['xin_read']))
    for k, v in d['controls'].items():
        print('              control %-20s %d distinct, %s' % (k, v['distinct'], v['value']))
PY
