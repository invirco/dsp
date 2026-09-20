#!/bin/bash
# s82mic5_run.sh — MIC 5's OWN LANE, with the 595 chain unmuted at maximum gain.
#
# MIC 5 is J25 -> U39 (AD 1) -> AIN 8 -> slot 7 -> packed rx 15 -> `C1_IN_16`
# (tools/pi/d24_inputs.py). The earlier pass read 01/02/05/09/17, one on each
# converter, and none of them is MIC 5's: `C1_IN_05` is rx 4 = J18 = MIC 14.
# The dispatch asked for MIC 5 specifically, so MIC 5's lane is read by name.
set -u
STAGE="${STAGE:-/home/app/ship_s82}"
cd "$STAGE"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
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
lanes() {
  echo "-- $1"
  python3 - <<'PY'
import sys, json
sys.path.insert(0, '/home/app/dspboot'); sys.argv=['p']
import dsp4_scope as S
sc = S.Scope(1, symfile='chip1.sym.json')
syms = json.load(open('chip1.sym.json'))
for n in ('_buf_C1_IN_16','_buf_C1_IN_15','_buf_C1_IN_08','_buf_C1_XIN_CODEC_01'):
    a = syms.get(n)
    if a is None: print('%-24s NOT IN MAP' % n); continue
    v=[]
    for i in range(10):
        try: v.append('%08x' % (sc.peek(int(a)) & 0xFFFFFFFF))
        except Exception: v.append('--ERR---')
    print('%-24s %-2s distinct  %s' % (n, len(set(v)), ' '.join(v)))
PY
}
echo "=== MIC 5 (_buf_C1_IN_16), rails up, 595 UNMUTED at gain 63 ==="
sudo pinctrl set 26 op dh; sleep 3; sudo pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 1
lanes "rails up / chain 0xFC"
echo
echo "=== handback: SAFE image, rails down ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl get 27; sudo pinctrl set 26 op dl; sleep 1; sudo pinctrl get 26
