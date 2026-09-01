#!/bin/bash
# c2gold_run.sh — bench half of c2gold.sh. Boots the staged image, configures
# BOTH chips (chip 2's main loop is gated on CONFIG_COMMIT: without one its
# node graph never runs at all), lets the graph settle, and dumps every probe
# word to JSON.
set -u
DWELL="$1"; OUT="$2"
cd /home/app/dspboot

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=c2gold_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  GOT=0
  for c in 1 2 3; do
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
    [ "$GOT" = "1" ] && break
  done
  [ "$GOT" = "0" ] && { echo "(attempt $attempt: chips not both RUNNING)"; continue; }
  sleep "$DWELL"
  python3 - "$OUT" <<'PYEOF'
import json, sys
out = sys.argv[1]
sys.argv = ['p']
import dsp4_diag as D

dg = D.DiagLink(D.SpiLink('0.0', 1000000, 24, rdy_gpio=12))
dg.resync()      # CALIBRATES the answer phase (D74). A register that reads 0
                 # is not a measurement until this has run.

def sane():
    try:
        return (dg.read(0xE000) == 0xD5B40001 and dg.read(0xE001) == 2
                and dg.read(0xE005) != 0)
    except IOError:
        return False

def peek(a):
    for _ in range(12):
        if not sane():
            continue
        try:
            v = dg.peek(a)
        except IOError:
            continue
        if sane():
            return v
    return None

sym = json.load(open('chip2.sym.json'))
# One node per family per chain, plus the meters whose decimation the
# conversion is supposed to have fixed.
BUFS = [
    'C2_SNK_IN_01', 'C2_CODEC_AUX_IN', 'C2_PI_IN', 'C2_USB_IN',
    'C2_AUX_FDR_01', 'C2_AUX_EQ_01', 'C2_AUX_GEQ_01', 'C2_AUX_AFB_01',
    'C2_AUX_LIM_01', 'C2_AUX_DLY_01', 'C2_AUX_OUT_01',
    'C2_AUX_FDR_07', 'C2_AUX_GEQ_07', 'C2_AUX_OUT_07',
    'C2_GRP_FDR_01', 'C2_GRP_EQ_01', 'C2_GRP_GEQ_01', 'C2_GRP_GATE_01',
    'C2_GRP_COMP_01',
    'C2_SUB_FDR', 'C2_SUB_EQ', 'C2_SUB_COMP', 'C2_SUB_LIM', 'C2_SUB_DLY',
    'C2_SUB_OUT',
    'C2_MIX_MAIN_L', 'C2_MIX_MAIN_R', 'C2_MAIN_FDR', 'C2_MAIN_GEQ',
    'C2_MAIN_COMP', 'C2_MAIN_LIM', 'C2_MAIN_DLY', 'C2_MAIN_XOVER',
    'C2_MAIN_OEQ_01', 'C2_MAIN_OCOMP_01', 'C2_MAIN_OLIM_01', 'C2_MAIN_OUT_01',
    'C2_FX_ENG_01', 'C2_FX_FDR_01',
    'C2_MON', 'C2_MON_DLY', 'C2_MON_OUT',
    'C2_MAIN_ST_OUT', 'C2_CODEC_AUX_OUT',
]
METERS = ['C2_MTR_AUX_01', 'C2_MTR_AUX_07', 'C2_MTR_GRP_01', 'C2_MTR_MAIN_01',
          'C2_MTR_SUB', 'C2_MTR_FX_01']

res = {}
missing = []
for nid in BUFS:
    nm = '_buf_' + nid
    if nm not in sym:
        missing.append(nm); continue
    v = peek(sym[nm])
    if v is None:
        print('UNREADABLE ' + nm); sys.exit(2)
    res[nm] = v
for mid in METERS:
    for pfx in ('_mtr_peak_', '_mtr_rms_'):
        nm = pfx + mid
        if nm not in sym:
            missing.append(nm); continue
        v = peek(sym[nm])
        if v is None:
            print('UNREADABLE ' + nm); sys.exit(2)
        res[nm] = v
json.dump(res, open(out, 'w'))
print(f'{len(res)} probes captured'
      + (f', {len(missing)} absent from the map: {missing}' if missing else ''))
PYEOF
  RC=$?
  [ "$RC" = "0" ] && exit 0
  echo "(attempt $attempt: capture failed rc=$RC)"
done
echo "no clean capture in 3 attempts"
exit 4
