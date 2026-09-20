#!/bin/bash
# s84_gate3b.sh — THE TWO-SIDED READING, in one pass, on one bitstream.
#
# Gate 2 read `_buf_C1_IN_*` as exact digital zero on s41's bitstream. Gate 3
# read ad[0..2] as CARRYING DATA on the witness bitstream. Those are two runs
# on two bitstreams and a careful reader is entitled to ask whether the
# difference is the bitstream. So this takes both readings in the SAME run, in
# the SAME conditions, on the SAME bitstream: the witness build is the shipping
# RTL plus counters, so the lane path through it is the shipping lane path.
#
#   the pins   ad[0..2] at the CPLD, via the third knock
#   the buffers `_buf_C1_IN_*` in the DSP, via the SPI peek
#
# If the pins move and the buffers are zero in one pass, the fault is between
# i_dspa[0..2] and the graph buffer, and it is in this repo's own domain --
# the slot map, the lane config, the SPORT or the RX DMA -- not on the analog
# board and not in the CPLD.
set -u
STAGE="${STAGE:-/home/app/s83tn}"
OUTDIR=/home/app/s84
mkdir -p "$OUTDIR"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s84_gate3b.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect dbb1424a 2>&1 | sed 's/^/  /' )

echo "=== THE PINS, before the DSP is booted (the knock needs no DSP) ==="
sudo systemctl stop matrix-app >/dev/null 2>&1
python3 /home/app/dsp4_ad_witness.py --reps 2 2>&1 | grep -E "knock 1|knock 2|->|VERDICT|advanced" \
    | tee "$OUTDIR/pins-preboot.txt"

echo
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
[ "$BOOTED" = "1" ] || { echo "!! not booted -- no two-sided reading is takeable"; exit 5; }

echo
echo "=== rails UP, 595 unmuted gain 63 ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2

echo
echo "=== SIDE 1: THE BUFFERS the DSP reads ==="
SYMDIR=$STAGE python3 $STAGE/s83_lanescan.py --symdir $STAGE --reps 16 \
    --tag adwit-chain-FC-rails-up --json "$OUTDIR/lanes-adwit.json" 2>&1 | head -6
python3 - <<PY
import json
d = json.load(open('$OUTDIR/lanes-adwit.json'))
mic = [l for l in d['lanes'] if l['lane'].startswith('IN_')]
mv  = [l for l in mic if l.get('distinct', 0) > 1]
cod = [l for l in d['lanes'] if 'CODEC' in l['lane']]
cmv = [l for l in cod if l.get('distinct', 0) > 1]
print('FRAME_COUNT +%d, dead-symbol distinct %s' % (d['frame_count_delta'], d['dead_symbol_distinct']))
print('mic lanes   IN_01..IN_32: %d of %d MOVING' % (len(mv), len(mic)))
print('codec lanes XIN_CODEC_*  : %d of %d MOVING' % (len(cmv), len(cod)))
PY

echo
echo "=== SIDE 2: THE PINS, same rails, same chain, same bitstream ==="
python3 /home/app/dsp4_ad_witness.py --reps 2 2>&1 | grep -E "knock 1|knock 2|->|VERDICT|advanced" \
    | tee "$OUTDIR/pins-booted.txt"

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26; pinctrl get 27
