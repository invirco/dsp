#!/bin/bash
# bqeverify_run.sh — boot the staged image and read the round-once verdict.
set -u
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
# Retry BOOT AND CONFIG TOGETHER, not one then the other. A boot that
# leaves chip 2 answering can still leave chip 1's diag link out of phase,
# and re-running config alone never recovers it -- measured 2026-08-29,
# where three config retries in a row read MAGIC 0 and a single further
# boot+config came up first time.
#
# AND THE READINESS CHECK USES THE PACED READER, NOT dsp4_diag.py, for
# the reason conform_run.sh and pairgraph_run.sh carry: the DSP services
# this link once per audio block, dsp4_diag's unpaced reader out-runs it
# and then returns a well-formed WRONG answer. Gating on it cost this bar
# two whole sessions of "MAGIC 0x00000000 -- this is NOT diag firmware"
# on a part that answered `MAGIC 0xD5B40001, CHIP_ID 1, FRAME_COUNT
# moving` through dsp4_scope seconds later (2026-08-30).
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

for t in 1 2 3 4 5; do
  python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
  python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 3
  [ "$(ready)" = "1" ] && break
done
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "BOOT_STAGE|MAGIC" \
  || echo "  (dsp4_diag could not answer; the paced reader is the gate)"
# AND THE SCOPE LINK NEEDS A RESYNC THE DIAG LINK DOES NOT, the second
# half of the same 2026-08-29 finding: dsp4_diag answers cleanly while
# Scope(1).check_chip() reads CHIP 0, because the two open the
# transaction differently and the parameter link can be sitting one word
# out of phase. A diag read walks it back. pairgraph_run.sh takes one in
# front of every scope-side tool; this bar needs the same.
# RETRY THE LINK, NOT THE VERDICT. dsp4_bqe_verify.py exits 1 when it
# SCORED the part and the part was wrong, and 2/3 when it could not read
# the part at all. Retrying a scored failure six times prints the same
# wrong answer six times and buries it; only a link failure is worth
# another go.
for g in 1 2 3 4 5 6; do
  python3 dsp4_diag.py --chip 1 >/dev/null 2>&1
  python3 dsp4_bqe_verify.py /home/app/dspboot/chip1.sym.json \
      /home/app/dspboot/bqe_vectors.json "$1"
  rc=$?
  [ $rc -eq 0 ] && exit 0
  [ $rc -eq 1 ] && exit 1
  sleep 2
done
exit 3
