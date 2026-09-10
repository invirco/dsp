#!/bin/bash
# goldnode_run.sh — bench half of goldnode.sh.
#
# Boot, configure, then verify. The boot+config RETRY IS TOGETHER and the
# readiness gate is the PACED reader, for the reason bqst_run.sh and
# conform_run.sh both carry: a boot that leaves chip 2 answering can still
# leave chip 1's diag link a word out of phase, re-running config alone
# never recovers it, and dsp4_diag.py's unpaced reader returns a
# well-formed WRONG answer rather than an error when it does.
set -u
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

ready() {
  timeout 60 python3 - <<'PY' 2>/dev/null
import sys
sys.argv = ['p']
import dsp4_scope as S
ok = 0
try:
    sc = S.Scope(1)
    sc.d.resync()
    for _ in range(6):
        if sc.rd(0xE000) == 0xD5B40001 and sc.rd(0xE001) == 1:
            ok = 1
            break
except Exception:
    pass
print(ok)
PY
}

for cycle in 1 2 3; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 6
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] || { echo "cycle $cycle: link never usable"; continue; }
  # The scope link needs a resync the diag link does not; a diag read
  # walks it back (the same guard pairgraph_run.sh and bqst_run.sh take).
  python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
  # STRIPS, plural (S22-1). The gate is run as a PAIR under DSP4_SIMD_DYN
  # and the two strips of a pair are not interchangeable evidence: one is
  # the pair kernel's PEx and the other its PEy, and until the block-rate
  # witness was emitted on the paired branch at all, neither could be
  # scored. STRIPS="1 2" walks a whole pair.
  RC=0
  for _strip in ${STRIPS:-1}; do
    [ "${STRIPS:-1}" = "1" ] || echo "=== strip $_strip ==="
    python3 dsp4_node_verify.py --nodes "${NODES:-GATE,COMP,TUBE,FDR}" \
            --n "${N:-96}" --strip "$_strip"
    _rc=$?
    [ $_rc -eq 0 ] || RC=$_rc
  done
  [ $RC -eq 2 ] || exit $RC       # 2 = could not measure; try another boot
  echo "cycle $cycle: no measurable stimulus, re-booting"
done
echo "no usable measurement in 3 boot cycles"
exit 4
