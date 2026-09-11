#!/bin/bash
# s33flip_run.sh — bench half of the S32 gate-4 flip proof, repeated on the
# FINAL candidate-B bytes (S33 gate 4).
#
# capacity_run.sh's boot/config ladder, unchanged — it is the one that works
# and it is the one every capacity row in this programme was taken through.
# Then the CM4's playback is started (the Pi path is live under the standing
# `dsp4-pcm-slave` overlay on any bitstream — S29 proved it stage by stage)
# and tools/pi/dsp4_s32_flip.py flips the host cell and reads the node's own
# state and its published block back out of the part.
#
# Runs from $STAGE and never from ~/dspboot (S10-7).
set -u
STAGE="${STAGE:-/home/app/dspcap/s33b}"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  echo ">>> BENCH LOCKED: waiting for the card." >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=s33flip_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" \
    > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

sudo systemctl stop matrix-app >/dev/null 2>&1
# CANONICAL BENCH PIN HAND-BACK (S8-3) — check_bench_pins.sh enforces this
# text byte for byte across every run/flash script in the tree.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

PRODUCT="${PRODUCT:-d32}"
echo "  image: $(md5sum chip1.ldr chip2.ldr | cut -c1-8 | tr '\n' ' ')"

ready() {
  timeout 60 python3 - <<'PY' 2>/dev/null
import sys
sys.argv = ['p']
import dsp4_scope as S
ok = 0
try:
    sc = S.Scope(2)
    sc.d.resync()
    for _ in range(6):
        if sc.rd(0xE000) == 0xD5B40001 and sc.rd(0xE001) == 2 and sc.rd(0xE002) >= 6:
            ok = 1
            break
except Exception:
    pass
print(ok)
PY
}

for cycle in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  python3 dsp4_config.py --product "$PRODUCT" --chip 1 >/dev/null 2>&1; sleep 3
  python3 dsp4_config.py --product "$PRODUCT" --chip 2 \
          --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: chip 2 link never usable"; continue; }
  for C in 1 2; do
      PID=$(python3 dsp4_diag.py --chip $C 2>/dev/null | awk '/PRODUCT_ID/ {print $2}')
      echo "    chip $C: PRODUCT_ID (scope class) = ${PID:-unreadable}"
  done
  python3 gainfix.py >/dev/null 2>&1

  echo "--- stimulus on"
  bash /home/app/drive_audio.sh start || { echo "no stimulus"; }
  sleep 3
  echo "--- the flip"
  python3 dsp4_s32_flip.py --landed "landed-$PRODUCT.json" \
          --nodes "${NODES:-C2_PI_IN,C2_SNK_IN_01,C2_SNK_IN_02,C2_SNK_IN_03,C2_SNK_IN_04}" \
          --json "${OUT:-s33-flip.json}"
  RC=$?
  bash /home/app/drive_audio.sh stop >/dev/null 2>&1
  exit $RC
done
echo "no usable boot in 3 cycles"
exit 4
