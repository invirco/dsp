#!/bin/bash
# s83_gate2b.sh — the lane read with the 595 chain UNMUTED AT GAIN 63 and the
# rails up. The first gate-2 pass read the lanes with the SAFE image on the
# chain (every preamp muted/shunted), which is a confound this removes: S82
# proved the unmuted arm reads zero on ONE lane by name, and this reads ALL
# THIRTY-TWO in the same condition, with the tone on the AUX 1 bus.
set -u
STAGE=/home/app/s83tn
cd "$STAGE"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"

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

echo "=== rails UP ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
echo "=== 595 chain: every register UNMUTED at gain 63, phantom off (0xFC) ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2

echo "=== the lanes, chain 0xFC, rails up, tone OFF ==="
SYMDIR=$STAGE python3 $STAGE/s83_lanescan.py --symdir $STAGE --reps 16 \
    --tag chain-FC-rails-up --json /home/app/s83/lanes-chainFC.json 2>&1 | \
    grep -vE "^_buf|^IN_(0[1-9]|1[0-9]|2[0-9]|3[0-2]) +16 +1 " | head -40
echo
echo "--- the full table is in lanes-chainFC.json; the summary: ---"
python3 - <<'PY'
import json
d = json.load(open('/home/app/s83/lanes-chainFC.json'))
mv = [l for l in d['lanes'] if l.get('distinct', 0) > 1]
zz = [l for l in d['lanes'] if l.get('distinct') == 1 and l.get('min') == 0]
ot = [l for l in d['lanes'] if l.get('distinct') == 1 and l.get('min') != 0]
print('FRAME_COUNT +%d, dead-symbol distinct %s' % (d['frame_count_delta'], d['dead_symbol_distinct']))
print('MOVING      %2d: %s' % (len(mv), ', '.join('%s(%d distinct, %.1f dBFS)' % (l['lane'], l['distinct'], l['peak_dbfs']) for l in mv)))
print('STATIC ZERO %2d: %s' % (len(zz), ', '.join(l['lane'] for l in zz)))
print('STATIC other%2d: %s' % (len(ot), ', '.join('%s(%s)' % (l['lane'], l['words'][0]) for l in ot)))
PY

echo
echo "=== the 595 chain read back, then the SAFE image restored (S70-7) ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
echo "=== rails DOWN, CS_M back to ip pu ==="
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26; pinctrl get 27
