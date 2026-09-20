#!/bin/bash
# s83_run.sh — bench half of s83.sh. Boots the staged DSP4_TEST_NODES arm of the
# signed pair, states the triple it reads back, and takes the two analog gates.
#
# THE BOOT IS A GATE, NOT A PRINTOUT (S83-2). A part below BOOT_STAGE 6 is not
# turning the graph, so every measurement below it is a reading of silence with
# a confident shape. latency.sh took twenty reps off exactly that and famverify
# wrote a full 27-family table of dashes and exited 0. Neither happens here.
set -u
STAGE="${STAGE:-/home/app/s83tn}"
GATES="${GATES:-2,4}"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s83_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

mkdir -p /home/app/s83

echo "=== AN_EN and CS_M as found ==="
pinctrl get 26; pinctrl get 27

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
  [ "$BOOTED" = "1" ] && break
  echo "  (attempt $attempt: chip1 stage=${S1:-?} chip2 stage=${S2:-?} — re-booting)"
done
echo "  boot: chip1 stage=${S1:-?} chip2 stage=${S2:-?}"
[ "$BOOTED" = "1" ] || { echo "S83: the TEST_NODES pair did not come up — NO MEASUREMENT"; exit 1; }

echo
echo "=== the arm's own triple, both chips ==="
python3 dsp4_buildcfg.py --chip 1 --word 0xCF45FF10,0xE3018E6F,0xC47C0F26 2>&1 | tail -6
python3 dsp4_buildcfg.py --chip 2 --word 0xCF45FF10,0xE3018E6F,0xC47C0F26 2>&1 | tail -6
python3 gainfix.py 2>&1 | sed 's/^/  /'

echo
echo "=== the rails UP (authorised for gates 2 and 4 only) ==="
sudo pinctrl set 26 op dh; sleep 3; pinctrl get 26

case ",$GATES," in *,2,*)
  echo
  echo "=== GATE 2 — MIC 5's lane: the 595 chain unmuted at gain 63, then the tone ==="
  python3 /home/app/s54/s54_txpeek.py 2>/dev/null | head -3 || true
  SYMDIR="$STAGE" python3 /home/app/s83/s83_gate2.py 2>&1
  ;;
esac

case ",$GATES," in *,4,*)
  echo
  echo "=== GATE 4 — the talkback loop, T1 then T3 ==="
  SYMDIR="$STAGE" python3 /home/app/s70/s70_g1_t1.py 2>&1
  echo
  SYMDIR="$STAGE" python3 /home/app/s70/s70_t3.py 2>&1
  ;;
esac

echo
echo "=== rails DOWN ==="
sudo pinctrl set 26 op dl; sleep 1; pinctrl get 26
