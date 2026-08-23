#!/bin/bash
# bisect_run.sh <repeats> <stamp_addr> <expected> — bench side.
set -u
N="$1"; ADDR="$2"; EXPECT="$3"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
ALIVE=0; RUNS=0
for r in $(seq 1 "$N"); do
  ok=0
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && { ok=1; break; }
  done
  [ "$ok" = "0" ] && { echo "  run $r: BOOT FAILED (chip2 never took its own image)"; continue; }

  # Prove the build flags reached the RUNNING image before measuring anything.
  ST=""
  for t in 1 2 3 4 5 6; do
    V=$(python3 dsp4_diag.py --chip 1 --peek "$ADDR" 2>&1 | tail -1 | grep -oE '0x[0-9A-Fa-f]{8}$')
    [ -n "$V" ] && { ST=$V; break; }
  done
  if [ -z "$ST" ]; then echo "  run $r: could not read _build_flags"; continue; fi
  if [ "$((ST))" -ne "$((EXPECT))" ]; then
    printf '  ABORT: running image has _build_flags=%s, expected 0x%08X — the flags did NOT reach the assembler\n' "$ST" "$EXPECT"
    exit 3
  fi

  RUNS=$((RUNS+1))
  res=DEAD
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      if echo "$O" | grep -q "MAGIC          0xD5B40001"; then
        T=$(echo "$O"|grep TICKS|awk '{print $2}'); S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}')
        if [ -n "$S" ] && [ "$T" != "0" ] && [ "$S" -ge 6 ] 2>/dev/null; then
          res="ALIVE stage=$S $(echo "$O"|grep -oE 'BLK_OVERRUN *[0-9]+'|tr -s ' ')"
          break
        fi
      fi; sleep 1
    done
    case "$res" in ALIVE*) break;; esac
  done
  echo "  run $r: $res"
  case "$res" in ALIVE*) ALIVE=$((ALIVE+1));; esac
done
echo "RESULT: $ALIVE alive / $RUNS verified runs"
