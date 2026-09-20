#!/bin/bash
# s84_gate2.sh — THE S83 SWEEP, REPEATED ON THE BITSTREAM THE BENCH LIVED ON.
#
# S83 read every chip-1 input lane on BOTH current bitstreams, rails up, 595
# chain unmuted at gain 63, and got exact digital zero on all 32 AK5558 mic
# lanes while the four codec lanes carried their own dithered floor. The flash
# log (gate 1) says the bench carried `s41_mhrx_pullup_off.15f3ae07dae1` from
# 2026-09-13T13:11:14Z to 2026-09-19T21:47:06Z — six days that contain
# 2026-09-16, the day S54-S58 measured real preamp noise on this unit. So the
# same sweep runs here on s41's bitstream, and it is the same sweep: same
# lanescan, same two controls, same chain image, same rails.
#
#   MUST MOVE      FRAME_COUNT advances (the block ISR is turning)
#   MUST NOT MOVE  _rx_slot_C1_IN_01 (a symbol nothing writes)
#
# THE FLOOR IS THE ANSWER, NOT THE TONE. A live AK5558 at gain 63 dithers; a
# dead lane is exact zero. The AUX 1 -> MIC 5 cable is unconfirmed (S83-Q2, with
# PW) so the tone arm is run for what it is worth and the floor arm is the
# verdict.
#
# s41's slot map differs from HEAD's ONLY in the A_I3 comment, the A_I4/MIX_1
# codec comments and the six A_I6 Pi TDM8 rows added at 1dc67f39 — the
# A_I0/A_I1/A_I2 rows that carry IN_01..IN_24 are byte-identical, so
# `MIC 5 -> _buf_C1_IN_16` holds on this bitstream too and the lane names mean
# the same thing they meant in S83.
set -u
STAGE="${STAGE:-/home/app/s83tn}"
OUTDIR=/home/app/s84
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s84_gate2.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

mkdir -p "$OUTDIR"

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

echo "=== AN_EN and CS_M as found ==="
pinctrl get 26; pinctrl get 27
echo "=== the pair that will be booted ==="
md5sum chip1.ldr chip2.ldr

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

# THE BOOT IS A GATE, NOT A PRINTOUT (S83-2). A part below BOOT_STAGE 6 is not
# turning the graph and every lane below it reads silence with a confident
# shape. MAGIC is checked before BOOT_STAGE is believed.
BOOTED=0
for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  CFG1=$(python3 dsp4_config.py --product d24 --chip 1 2>&1); sleep 2
  CFG2=$(python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 2>&1)
  sleep 3
  case "$CFG1$CFG2" in
    *ERROR*|*Traceback*)
      echo "  config REFUSED:"
      printf '%s\n%s\n' "$CFG1" "$CFG2" | grep -E 'ERROR|Error' | head -2 | sed 's/^/    /' ;;
  esac
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
echo "=== boot: chip1 stage ${S1:-?}, chip2 stage ${S2:-?} ==="
if [ "$BOOTED" != "1" ]; then
  echo "!! THE PAIR IS NOT AT BOOT_STAGE 6 ON s41's BITSTREAM."
  echo "   That is itself a reading: the graph is not turning, so no lane"
  echo "   verdict is takeable and none is printed."
  exit 5
fi

echo "=== rails UP (S70 recipe, authorised) ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
echo "=== 595 chain: every register UNMUTED at gain 63, phantom off (0xFC) ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2

echo
echo "=== THE FLOOR ARM: every lane, chain 0xFC, rails up, no stimulus ==="
SYMDIR=$STAGE python3 $STAGE/s83_lanescan.py --symdir $STAGE --reps 16 \
    --tag s41-chain-FC-rails-up --json $OUTDIR/lanes-s41-chainFC.json 2>&1 | head -12

python3 - <<PY
import json
d = json.load(open('$OUTDIR/lanes-s41-chainFC.json'))
mv = [l for l in d['lanes'] if l.get('distinct', 0) > 1]
zz = [l for l in d['lanes'] if l.get('distinct') == 1 and l.get('min') == 0]
ot = [l for l in d['lanes'] if l.get('distinct') == 1 and l.get('min') != 0]
print('FRAME_COUNT +%d, dead-symbol distinct %s' % (d['frame_count_delta'], d['dead_symbol_distinct']))
print('MOVING      %2d: %s' % (len(mv), ', '.join('%s(%d distinct, %.1f dBFS)' % (l['lane'], l['distinct'], l['peak_dbfs']) for l in mv)))
print('STATIC ZERO %2d: %s' % (len(zz), ', '.join(l['lane'] for l in zz)))
print('STATIC other%2d: %s' % (len(ot), ', '.join('%s(%s)' % (l['lane'], l['words'][0]) for l in ot)))
mic = [l for l in d['lanes'] if l['lane'].startswith('IN_')]
micmv = [l for l in mic if l.get('distinct', 0) > 1]
print()
print('MIC-ADC LANES (IN_01..IN_32): %d of %d MOVING' % (len(micmv), len(mic)))
PY

echo
echo "=== THE TONE ARM: the S83 one-tone sweep, same chain, same rails ==="
S83_OUT=$OUTDIR/gate2-s41.json SYMDIR=$STAGE \
    timeout 900 python3 $STAGE/s83_gate2.py 2>&1 | tail -50

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26; pinctrl get 27
