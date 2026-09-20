#!/bin/bash
# s83_handback.sh — the unit as found: the AS-FOUND pair back on the part, the
# 595 SAFE image written AFTER the last DSP boot (S70-7), AN_EN low, CS_M back
# to `ip pu`, matrix-app restarted and its MCU verdict read from the WHOLE log.
set -u
STAGE=/home/app/s78restore
cd "$STAGE"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"

echo "=== the as-found pair ==="
md5sum chip1.ldr chip2.ldr

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
  for c in 1 2; do
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
  [ "$BOOTED" = "1" ] && break
done
echo "  boot: chip1 stage=${S1:-?} chip2 stage=${S2:-?}  (booted=$BOOTED)"
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "MAGIC|CHIP_ID|BOOT_STAGE|ERR_COUNT|FRAME_COUNT"
python3 dsp4_diag.py --chip 2 2>&1 | grep -E "MAGIC|CHIP_ID|BOOT_STAGE|ERR_COUNT|FRAME_COUNT"

tobits() { local v="$1" i out=""; for ((i=7;i>=0;i--)); do out+=$(( (v>>i)&1 )); done; printf '%s' "$out"; }
chain_write() {
  local V=$(( $1 )) IMG="" i bits p1 p2
  bits=$(tobits "$V"); [ ${#bits} -eq 8 ] || { echo "  REFUSING"; return 1; }
  for i in $(seq 1 24); do IMG+="$bits"; done; IMG+="00000000"
  pinctrl set 9 ip pd; pinctrl set 10 op dl; pinctrl set 11 op dl; pinctrl set 27 op dh
  pass() { local out="" i b r; pinctrl set 27 op dl
    for ((i=0;i<200;i++)); do b=${IMG:$i:1}
      if [ "$b" = "1" ]; then pinctrl set 10 op dh; else pinctrl set 10 op dl; fi
      r=$(pinctrl get 9); case "$r" in *"| hi"*) out+="1";; *) out+="0";; esac
      pinctrl set 11 op dh; pinctrl set 11 op dl; done
    pinctrl set 27 op dh; printf '%s' "$out"; }
  p1=$(pass); p2=$(pass)
  [ "$p2" = "$IMG" ] && echo "  595 SAFE image VERIFIED 200/200 at 0x$(printf '%02X' $V)" || echo "  595 MISMATCH"
  pinctrl set 9 a0 pd; pinctrl set 10 a0 pd; pinctrl set 11 a0 pd; pinctrl set 27 ip pu
}
echo "=== the 595 SAFE image, written AFTER the last DSP boot (S70-7) ==="
sudo bash -c "$(declare -f tobits chain_write); chain_write 0x01"

echo "=== pins ==="
sudo pinctrl set 26 op dl
pinctrl get 26; pinctrl get 27

echo "=== matrix-app ==="
sudo systemctl start matrix-app; sleep 25
systemctl is-active matrix-app
grep -cE "MCU .*verified|announc" /home/app/logs/log 2>/dev/null || true
grep -E "verified after S_RUN|MCU not verified|MCUs verified|S_RUN" /home/app/logs/log 2>/dev/null | tail -6
