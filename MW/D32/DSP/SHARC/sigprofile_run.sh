#!/bin/bash
# sigprofile_run.sh — bench half of sigprofile.sh.
#
# profile_run.sh's twin, with the two hardened probes the 2026-08-28
# root-cause added: every point is only accepted once the GAIN coefficient
# witness says strip 1 is actually carrying its input (roughly one boot in
# three lands the CFG_COMMIT header word in _gain_coeff_C1_GAIN_01 and the
# whole chain then measures the SILENCE cost while BOOT_STAGE, pass rate,
# DMA and SPORT all read clean), and the cycle read is taken twice with a
# link-sanity check either side.
set -u
PT="$1"; PP="$2"; DWELL="$3"
cd /home/app/dspboot
sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      if echo "$O" | grep -q "MAGIC          0xD5B40001"; then
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}'); T=$(echo "$O"|grep TICKS|awk '{print $2}')
        if [ -n "$S" ] && [ "$T" != "0" ] && [ "$S" -ge 6 ] 2>/dev/null; then GOT=1; break; fi
      fi; sleep 1
    done
    [ "$GOT" = "1" ] && break
  done
  echo "$GOT"
}

for attempt in 1 2 3; do
  G=$(boot_and_config)
  [ "$G" = "0" ] && { echo "  (attempt $attempt: never reached stage 6)"; continue; }
  # Repair the coefficient over the link before spending a reboot on it.
  python3 gainfix.py 2>&1 | sed 's/^/  /'
  sleep "$DWELL"
  R=$(python3 - "$PT" "$PP" <<'PYEOF'
import json, sys
addrs = sys.argv[1:3]
sys.argv = ['p']
import dsp4_diag as D
link = D.SpiLink('0.0', 1000000, 6, rdy_gpio=8)
diag = D.DiagLink(link); diag.resync()

def sane():
    try:
        return (diag.read(0xE000) == 0xD5B40001 and diag.read(0xE005) != 0)
    except IOError:
        return False

def peek(a):
    for _ in range(12):
        if not sane():
            continue
        try:
            v = diag.peek(a)
        except IOError:
            continue
        if sane():
            return v
    return None

# WITNESS FIRST. A point whose strip 1 runs on the CFG_COMMIT header word
# reports the silence cycle count and nothing else notices.
sym = json.load(open('chip1.sym.json'))
gname = '_gain_coeff_C1_GAIN_01'
g = peek(sym[gname]) if gname in sym else None
if g is None:
    print('WITNESS-UNREADABLE'); sys.exit(2)
if g != 0x3F800000:
    print(f'WITNESS-DEAD 0x{g:08X}'); sys.exit(3)

c = peek(int(addrs[0], 16))
p = peek(int(addrs[1], 16))
if c is None or p is None or p == 0:
    print(f'unreadable (cyc={c} passes={p})'); sys.exit(1)
print(f'passes={p}  {c} cycles/pass  gain_coeff=0x{g:08X} OK')
PYEOF
)
  RC=$?
  case "$R" in
    WITNESS-DEAD*|WITNESS-UNREADABLE*) echo "  (attempt $attempt: $R — re-running boot+config)";;
    *) echo "$R"; exit $RC;;
  esac
done
echo "no clean witness in 3 attempts"
exit 4
