#!/bin/bash
# s86_handback.sh — the shipping bitstream read back, the landed instrument
# proved on the part, the SAFE image on the chain, the unit as found.
#
# The last reading of the session is taken with `tools/pi/dsp4_rxscan.py` —
# the tool this session landed — rather than with the session-local copy, so
# what goes into the record is the artifact the next session will run.
set -u
OUTDIR=/home/app/s86
STAGE="${STAGE:-/home/app/s83tn}"
mkdir -p "$OUTDIR"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"
printf 'pid=%s script=s86_handback.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
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

echo "=== the shipping label, read off the part ==="
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect 83b3cc22 2>&1 | sed 's/^/  /' )

sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

cd "$STAGE"
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

echo
echo "=== rails UP, 595 unmuted gain 63 — the session's headline, re-taken ==="
echo "    with tools/pi/dsp4_rxscan.py, the instrument this session landed"
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26
sudo bash -c "$(declare -f tobits chain_write); chain_write 0xFC"; sleep 2
python3 /home/app/dspboot/dsp4_rxscan.py --symdir "$STAGE" --reps 16 \
    --tag handback --json "$OUTDIR/rx-handback.json" 2>&1 \
    | tee "$OUTDIR/rx-handback.txt" | tail -60

echo
echo "=== the 595 SAFE image restored (S70-7), rails DOWN ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"
sudo pinctrl set 26 op dl; sleep 1
echo "=== unit as found ==="
pinctrl get 26; pinctrl get 27
( cd /home/app/dspboot && python3 dsp4_logic_id.py --expect 83b3cc22 2>&1 | sed 's/^/  /' )
sudo systemctl start matrix-app >/dev/null 2>&1; sleep 8
systemctl is-active matrix-app
