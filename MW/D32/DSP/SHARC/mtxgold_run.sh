#!/bin/bash
# mtxgold_run.sh — bench half of mtxgold.sh (see that file).
#
# ONE BOOT, FOUR CAPTURES. That is the whole reason this is not four calls
# to pairgraph_run.sh: the claim is that three buses carry the SAME SUM,
# and comparing captures taken across three boots would put the boot
# between them as a variable. The retry ladder is pairgraph_run.sh's,
# unchanged.
set -u
STRIP="${1:-1}"; N="${2:-256}"
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

probe() {   # C=<chip> MODE=ident|ready -> prints 1 or 0
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
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
    [ "$(C=1 MODE=ready probe)" = "1" ] && { GOT=1; break; }
  done
  echo "$GOT"
}

for attempt in 1 2 3 4 5; do
  G=$(boot_and_config)
  [ "$G" = "0" ] && { echo "  (attempt $attempt: never reached stage 6)"; continue; }
  python3 dsp4_diag.py --chip 1 2>&1 \
    | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A" | sed 's/^/  /'
  for g in 1 2 3 4 5 6; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    python3 gainfix.py 2 > /tmp/gf.log 2>&1 && break
    sleep 2
  done
  sed 's/^/  /' /tmp/gf.log
  OK=1
  # aux1 IS TAKEN TWICE, FIRST AND LAST, AND THAT IS THE CONTROL ON THIS
  # WHOLE BAR. A capture is 256 samples from the arm, and the strip's gate
  # and compressor are wherever their envelopes happen to be when the arm
  # lands -- which depends on how long ago the previous capture's step
  # stopped. So "two buses differ by 1,412 LSB" is only a claim about the
  # buses if two captures of the SAME bus differ by less. `aux1b` is that
  # measurement, taken on the same boot with the same graph.
  for arm in aux1 mtx1 mtx2 aux1b; do
    xp="${arm%b}"
    GOT=0
    for g in 1 2 3 4; do
      python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
      # --force: this bar is the one that DOES compare captures within a
      # single boot, and the `aux1b` arm above is its control -- so the
      # S23-1 refusal in dsp4_pairgraph.py (which stops a bar comparing a
      # later capture against a first-capture golden) is not the guard
      # this loop wants. Every capture here is stamped `forced` and with
      # its position in the boot.
      if python3 dsp4_pairgraph.py --strip "$STRIP" -n "$N" --xp "$xp" \
           --force --tag "$arm" --out "mtxgold_$arm.json"; then GOT=1; break; fi
      sleep 2
    done
    [ "$GOT" = "1" ] || OK=0
  done
  # The negative control goes LAST: it leaves the assign bit at 0, which
  # is not a state the positive captures may be taken in.
  for g in 1 2 3 4; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    if python3 dsp4_pairgraph.py --strip "$STRIP" -n "$N" --xp mtx1 --xp-off \
         --force --tag mtx1off --out "mtxgold_mtx1off.json"; then break; fi
    sleep 2
  done
  [ "$OK" = "1" ] && exit 0
  echo "  (attempt $attempt: an arm produced no capture — re-booting)"
done
echo "no usable mtxgold run in 5 attempts"
exit 4
