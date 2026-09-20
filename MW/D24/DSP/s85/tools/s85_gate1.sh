#!/bin/bash
# s85_gate1.sh — THE CAPTURE LAUNCH PHASE, MEASURED: ad[0..2] counted on
# bck8_launch beside bck8_sample, in one bitstream, rails down and rails up.
#
# Both banks count the SAME 256 bit periods of the SAME frames, 40.69 ns
# apart on an 81.38 ns bit period. A lane whose counts depend on WHICH of the
# two it is sampled at is a lane whose data edge is sitting on one of them:
# that is the launch phase, and the fix is in the LOGIC. A lane that reads the
# same on both is stable across at least half a bit period at these pins.
#
# The rails arm is not decoration: S84-4 found ad[1]/ad[2] roughly DOUBLE
# their toggles when the analog rails come up and ad[0] does not, and that is
# re-taken here on both edges, because a phase fault and a signal-dependent
# toggle count look alike in one reading and not in two.
set -u
OUTDIR=/home/app/s85
mkdir -p "$OUTDIR"
STAGE="${STAGE:-/home/app/s83tn}"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s85_gate1.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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

EXPECT="${EXPECT:-3d97f578}"
echo "=== what is on the part ==="
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect "$EXPECT" 2>&1 | sed 's/^/  /' )

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

echo
echo "=== ARM 1: rails DOWN, 595 as found ==="
pinctrl get 26
python3 /home/app/dsp4_ad_witness.py --reps 2 2>&1 | tee "$OUTDIR/edges-rails-down.txt" \
    | grep -E "knock [12]:|->|VERDICT|advanced|ad\[[0-9]\]  sample|!!"

echo
echo "=== rails UP, 595 unmuted gain 63 ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2

echo
echo "=== ARM 2: rails UP, 595 0xFC ==="
python3 /home/app/dsp4_ad_witness.py --reps 3 2>&1 | tee "$OUTDIR/edges-rails-up.txt" \
    | grep -E "knock [123]:|->|VERDICT|advanced|ad\[[0-9]\]  sample|!!"

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26; pinctrl get 27
