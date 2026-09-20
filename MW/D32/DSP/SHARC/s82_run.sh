#!/bin/bash
# s82_run.sh — bench half of s82.sh. Boots the STAGED SIGNED PAIR, proves the
# part reads back the signed configuration's triple, and re-takes the
# converter observations on the post-S34 shipping bitstream.
#
# S81 measured the codec return lanes on `a1f6672af6c3` (exact digital zero)
# and on this tree's bitstream (moving converter noise). PW adopted the fix on
# 2026-09-20, so `a1f6672af6c3` is retired and the A side of that A/B can no
# longer be flashed. What this script takes is the B side on the SIGNED pair,
# with the same two-sided controls dsp4_inscan.py carries, plus the AN_EN
# raise the dispatch authorises for this gate only.
#
# Usage: s82_run.sh <stage-dir> <out.json>
set -u
STAGE="$1"; OUT="$2"
cd "$STAGE"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=s82_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

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
  GOT=0
  # CONFIGURED TWICE, as the standing recipe requires.
  for c in 1 2; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1
    sleep 3
    G1=0; G2=0
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      echo "$O" | grep -q "MAGIC          0xD5B40001" && {
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S" ] && [ "$S" -ge 6 ] 2>/dev/null && G1=1; }
      O2=$(python3 dsp4_diag.py --chip 2 2>&1)
      echo "$O2" | grep -q "MAGIC          0xD5B40001" && {
        S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && G2=1; }
      [ "$G1" = "1" ] && [ "$G2" = "1" ] && { GOT=1; break; }
      sleep 1
    done
  done
  [ "$GOT" = "1" ] && { BOOTED=1; break; }
  echo "(attempt $attempt: chips not both RUNNING)"
done
[ "$BOOTED" = "1" ] || { echo "S82: the pair did not come up"; exit 1; }

echo "=== boot state ==="
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "MAGIC|CHIP_ID|BOOT_STAGE|ERR_COUNT|RESP_DROP|FRAME_COUNT"
python3 dsp4_diag.py --chip 2 2>&1 | grep -E "MAGIC|CHIP_ID|BOOT_STAGE|ERR_COUNT|RESP_DROP|FRAME_COUNT"

echo
echo "=== GATE 1 ON THE PART: the signed triple, both chips ==="
for c in 1 2; do
  echo "-- chip $c"
  python3 dsp4_buildcfg.py --chip $c --expect-shipping 2>&1 | tail -30
  echo "   exit=$?"
done

echo
echo "=== GATE 1 NEGATIVE CONTROL: the part scored against the OLD triple ==="
echo "  (0xCF45FF10/0xE2018264/0xC47C0F26 -- what a pre-S82 image reads.)"
python3 dsp4_buildcfg.py --expect-shipping \
    --word 0xCF45FF10,0xE2018264,0xC47C0F26 2>&1 | tail -20
echo "  exit=$?"

echo
echo "=== GATE 0: the input lanes, RAILS DOWN (AN_EN lo) ==="
sudo pinctrl get 26
python3 dsp4_inscan.py 1 12 2>&1 | tail -50

echo
echo "=== GATE 0: the input lanes, RAILS UP (AN_EN hi, this gate only) ==="
sudo pinctrl set 26 op dh; sleep 2; sudo pinctrl get 26
python3 dsp4_inscan.py 1 12 2>&1 | tail -50
echo "-- the four codec return lanes and the four AK5558 lanes, word for word"
python3 - <<'PY'
import sys, json
sys.path.insert(0, '/home/app/dspboot')
sys.argv = ['p']
import dsp4_scope as S
sc = S.Scope(1)
syms = json.load(open('chip1.sym.json'))
for n in ('_buf_C1_XIN_CODEC_01','_buf_C1_XIN_CODEC_02','_buf_C1_XIN_CODEC_03',
          '_buf_C1_XIN_CODEC_04','_buf_C1_IN_01','_buf_C1_IN_02','_buf_C1_IN_09',
          '_buf_C1_IN_17','_buf_C1_XIN_MEMS'):
    a = syms.get(n)
    if a is None:
        print('%-24s NOT IN MAP' % n); continue
    vals = []
    for i in range(8):
        try:
            vals.append('%08x' % (sc.peek(int(a)) & 0xFFFFFFFF))
        except Exception as e:
            vals.append('ERR')
    print('%-24s %s' % (n, ' '.join(vals)))
PY

echo
echo "=== GATE 0: rails back down, READ BACK ==="
sudo pinctrl set 26 op dl; sleep 1; sudo pinctrl get 26
