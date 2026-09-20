#!/bin/bash
# s85_handback.sh — the adopted shipping label on the part, the witness read
# back through it, and the unit as found.
#
# The gate 1 reading was taken on `dsp4_logic_adwit.f2f33d97f578`, which no
# longer rebuilds from HEAD (S85-11 moved CFG_BITS into the hash). Rather than
# leave the session's headline measurement resting on an artifact that cannot
# be rebuilt, it is re-taken HERE, on the bitstream that is actually adopted —
# which can carry it because the witness now ships in every configuration.
set -u
OUTDIR=/home/app/s85
mkdir -p "$OUTDIR"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"
printf 'pid=%s script=s85_handback.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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

echo "=== the adopted shipping label, read off the part ==="
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect 83b3cc22 2>&1 | sed 's/^/  /' )

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

echo
echo "=== rails UP, 595 unmuted gain 63 -- the same condition gate 1 used ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2

echo
echo "=== GATE 1, RE-TAKEN ON THE SHIPPING BITSTREAM ==="
python3 /home/app/dsp4_ad_witness.py --reps 3 2>&1 | tee "$OUTDIR/edges-shipping.txt" \
    | grep -E "knock [123]:|->|VERDICT|advanced|ad\[[0-9]\]  sample|!!"

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1
echo "=== unit as found ==="
pinctrl get 26; pinctrl get 27
sudo systemctl start matrix-app >/dev/null 2>&1; sleep 8
systemctl is-active matrix-app
