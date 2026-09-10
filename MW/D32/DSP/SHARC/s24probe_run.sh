#!/bin/bash
# s24probe_run.sh — bench half of s24probe.sh (see that file).
#
# Same boot/config retry ladder as conform_run.sh. The S24 gate is chip
# 2's alone -- the main output strips' own Level and Mute -- but BOTH
# chips are still configured, because the signal the bar needs at the
# output has to come down the whole graph from chip 1's strips. A verdict
# taken through a half-configured graph is fiction.
set -u
OUT_N="${1:-1}"
PRODUCT="${PRODUCT:-d24}"
cd "${STAGE:-/home/app/dspboot}"
sudo systemctl stop matrix-app >/dev/null 2>&1
# BENCH PIN HAND-BACK — the corrected sequence (S8-3, 2026-09-09).
# The line that used to be here, `pinctrl set 6,7,8,9,10,11,12,22,23,24,25
# a0`, is WRONG: GPIO24 in ALT0 is SD0_DAT2, not a deasserted chip select,
# so chip 2's CS sits asserted while chip 1's boot stream clocks out and the
# card comes up as TWO CHIP 1s. Six consecutive boots did that on 2026-09-09
# and only dsp4_scope.check_chip caught it — through dsp4_diag.py the card
# looks healthy with a wrong CHIP_ID, and every number taken through it is
# fiction. The chip selects (6 = chip 1, 24 = chip 2) are therefore HELD AS
# OUTPUTS DRIVEN HIGH, the two SPI_RDY lines (8, 12) are plain inputs, which
# is what gpiod claims them as, and only the SPI and JTAG pins go back to a0.
# CANONICAL TEXT — check_bench_pins.sh enforces it byte for byte across every
# run/flash script in the tree. Change it there, not here.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1

# C=<chip> MODE=ident|ready probe -> prints 1 or 0
probe() {
  timeout 120 python3 - <<'EOF' 2>/dev/null
import os
import sys
sys.argv = ['p']
import dsp4_scope as S
chip = int(os.environ.get('C', '1'))
mode = os.environ.get('MODE', 'ident')
sc = S.Scope(chip)
sc.d.resync()
ok = 0
for _ in range(6):
    try:
        if sc.rd(0xE000) != 0xD5B40001 or sc.rd(0xE001) != chip:
            continue
        if mode == 'ready' and sc.rd(0xE002) < 6:
            continue
        ok = 1
        break
    except IOError:
        pass
print(ok)
EOF
}

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    [ "$(C=2 MODE=ident probe)" = "1" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product "$PRODUCT" --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product "$PRODUCT" --chip 2 >/dev/null 2>&1; sleep 2
    [ "$(C=1 MODE=ready probe)" = "1" ] || continue
    [ "$(C=2 MODE=ready probe)" = "1" ] && { GOT=1; break; }
  done
  echo "$GOT"
}

for attempt in 1 2 3 4 5; do
  G=$(boot_and_config)
  if [ "$G" != "1" ]; then
    echo "  (attempt $attempt: both chips never reached stage 6)"; continue
  fi
  python3 dsp4_diag.py --chip 1 2>&1 \
    | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A" | sed 's/^/  /'
  # gainfix repairs the one-in-three boot that leaves strip 1's GAIN
  # coefficient holding the CFG_COMMIT header word; see pairgraph_run.sh.
  for g in 1 2 3 4 5 6; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    python3 gainfix.py 2 > /tmp/gf.log 2>&1 && break
    sleep 2
  done
  sed 's/^/  /' /tmp/gf.log
  for g in 1 2 3 4; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    python3 dsp4_s24_probe.py "$OUT_N" && exit 0
    sleep 2
  done
  echo "  (attempt $attempt: no verdict — re-booting)"
done
echo "no usable S24 probe run in 5 attempts"
exit 4
