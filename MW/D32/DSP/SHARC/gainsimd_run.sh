#!/bin/bash
# gainsimd_run.sh — bench half of gainsimd.sh (see that file).
#
# pairgraph_run.sh with ONE difference: it sets strip 1 and 2's GAIN to a
# value the caller chooses instead of to unity. That is the whole point of
# the bar -- at unity gain against a +/-0.5 square every product's low 28
# bits are zero, so truncation and rounding give the same answer and no
# capture can tell a correct rounding from a missing one.
set -u
STRIP="$1"; N="$2"; TAG="$3"; BQ="${4:-}"; GVAL="${5:-1.0}"
cd /home/app/dspboot
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

# THE READINESS CHECK USES THE PACED READER, NOT dsp4_diag.py, and this
# file learned that late. conform_run.sh recorded it on 2026-08-29: five
# boots in a row were discarded there because dsp4_diag.py could not answer
# the link after a config while dsp4_scope's paced, VOTED read returned
# BOOT_STAGE 7 off the same part, first try. This script kept the diag gate
# and spent 2026-08-30 discarding good boots for it -- busgold, bqgraph and
# every captable point that reported "BOOT_STAGE reads  — link down" were
# gated on the instrument that cannot read the link, not on the part.
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
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
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

# THE WITNESS COMES BEFORE THE CAPTURE, for the same reason it does in
# sigprofile_run.sh: roughly one boot+config in three leaves strip 1's GAIN
# coefficient holding the CFG_COMMIT header word, and a capture taken in
# that state is a capture of a dead strip -- which is all zeros, which is
# also what a dropped arm looks like. gainfix repairs it over the link.
for attempt in 1 2 3 4 5; do
  G=$(boot_and_config)
  [ "$G" = "0" ] && { echo "  (attempt $attempt: never reached stage 6)"; continue; }
  python3 dsp4_diag.py --chip 1 2>&1 \
    | grep -E "BOOT_STAGE|DMA0_STAT|SPORT0_ERR_A" | sed 's/^/  /'
  # THE SCOPE LINK NEEDS A RESYNC that the diag link does not. dsp4_diag
  # answers cleanly while Scope(1).check_chip() reads CHIP 0 -- the two
  # open the transaction differently and the parameter link can be sitting
  # one word out of phase. A diag read walks it back into phase, so every
  # scope-side tool here gets one in front of it and a few goes at it.
  # Without this the run burns all five boot attempts on a link state.
  #
  # EXPLAINED 2026-08-31 (D74): the word of phase is real and this note had
  # it right; what it could not know is that BOTH tools were guessing at it
  # from the echo's position, which cannot distinguish the two
  # arrangements. dsp4_diag.py now calibrates the phase against DIAG_MAGIC
  # and dsp4_scope.py decodes with the same answer, so the diag read in
  # front is no longer load-bearing. The ladder is left in place because it
  # also covers boot and config retries, which are separate matters.
  for g in 1 2 3 4 5 6; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    python3 gainfix.py 2 "$GVAL" > /tmp/gf.log 2>&1 && break
    sleep 2
  done
  sed 's/^/  /' /tmp/gf.log
  for g in 1 2 3 4; do
    python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
    if python3 dsp4_pairgraph.py --strip "$STRIP" -n "$N" --tag "$TAG" $BQ \
         --gain "$GVAL" --out "pairgraph_$TAG.json"; then
      exit 0
    fi
    sleep 2
  done
  echo "  (attempt $attempt: no capture — re-booting)"
done
echo "no usable capture in 5 attempts"
exit 4
