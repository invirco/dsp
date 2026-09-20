#!/bin/bash
# s84_gate3.sh — THE ad[0..2] WITNESS, read off the part.
#
# Gate 2 found every AK5558 mic lane at exact digital zero on the bitstream
# the bench lived on for the six days that contain S54-S58's live preamp
# noise, which makes three bitstreams with the same answer and closes the
# bisect branch: there is no commit to find, because there is no bitstream on
# which these lanes have ever been seen to work by this instrument.
#
# So this is the hub's authorised knock (S83-Q1): the LOGIC counts
# ones/toggles/frames on ad[0..2] and hands them back on a third knock.
# `dsp4_logic_adwit.cbf1dbb1424a` is that build -- the shipping RTL plus the
# witness, nothing else -- and it is a DIAGNOSTIC: the shipping bitstream goes
# back at handback and is read back by its design ID.
#
# THE CONTROL ARM IS NOT OPTIONAL AND IT IS FREE. `dsp4_ad_witness.py` asks
# cdc_o the same question with the same counter on the same sample strobe in
# the same bitstream, and cdc_o is the lane S83 and S84 both measured LIVE. An
# instrument that answers "zero" on a build where it cannot work is worse than
# no instrument (S80-19); an instrument that answers "zero" here and "data"
# one knock later has proved itself on the part.
set -u
OUTDIR=/home/app/s84
mkdir -p "$OUTDIR"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s84_gate3.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

echo "=== what is on the part (it must be the witness build) ==="
cd /home/app/dspboot && python3 dsp4_logic_id.py --expect dbb1424a 2>&1 | sed 's/^/  /'

echo
echo "=== ARM A: RAILS DOWN, 595 as found ==="
pinctrl get 26
python3 /home/app/dsp4_ad_witness.py --reps 3 2>&1 | tee "$OUTDIR/witness-rails-down.txt"

echo
echo "=== ARM B: RAILS UP (S70 recipe, authorised), 595 unmuted gain 63 ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2
python3 /home/app/dsp4_ad_witness.py --reps 3 2>&1 | tee "$OUTDIR/witness-rails-up.txt"

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26; pinctrl get 27
