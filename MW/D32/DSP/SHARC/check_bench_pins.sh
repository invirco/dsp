#!/bin/bash
# check_bench_pins.sh — the S8-3 bench-procedure defect must not come back.
#
# `pinctrl set 6,7,8,... ,24,25 a0` — the pin hand-back line every
# run and flash script in this tree carried until 2026-09-09 — puts GPIO24
# into ALT0, which on this part is SD0_DAT2 and NOT a deasserted chip select.
# Chip 2's CS then sits asserted while chip 1's boot stream is clocked out and
# the card comes up as TWO CHIP 1s. Six consecutive boots did that, and only a
# CHIP_ID read catches it: dsp4_diag.py reports a healthy part, so every
# number taken through such a boot is fiction (findings S8-3).
#
# The corrected sequence is CANONICAL TEXT. This script is what makes it one
# place rather than thirty: it fails if any run/flash script has drifted from
# it, or if the old line reappears anywhere that is procedure rather than
# record. The Python side is dsp4_boot.PIN_HANDBACK, which is the same three
# lines and is applied by dsp4_boot.py itself on every boot.
#
# Run it from anywhere. Exit 0 = clean.
set -u
cd "$(dirname "$0")/../../../.."      # repo root
RC=0

CANON_1='sudo pinctrl set 6,24 op dh >/dev/null 2>&1'
CANON_2='sudo pinctrl set 8,12 ip >/dev/null 2>&1'
CANON_3='sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1'

# 1. The old line must not survive in anything executable or in a procedure
#    document. Historical write-ups QUOTE it and must keep quoting it, so the
#    record files are named here rather than pattern-matched away.
RECORD='^(findings\.md|tasks\.md|MW/D32/DSP/dsp4-(order-defect|chan-mask|loop-latency)-20260909\.md)$'
# Built from parts so this script does not trip over its own prose.
BAD="pinctrl set 6,7,8,9,10,"'11,12,22,23,24,25 a0'
while IFS=: read -r f _; do
    [ -z "$f" ] && continue
    f="${f#./}"
    case "$f" in attic/*|archive/*) continue;; esac
    if ! printf '%s\n' "$f" | grep -Eq "$RECORD"; then
        echo "STALE PIN LINE: $f still carries '$BAD'"; RC=1
    fi
done < <(grep -rln "$BAD" --exclude-dir=.git --exclude-dir=attic \
                  --exclude-dir=archive --exclude-dir=defs . 2>/dev/null | sed 's/$/:/')

# 2. Every bench run script must carry the canonical three lines verbatim.
for f in MW/D32/DSP/SHARC/*_run.sh; do
    grep -q "python3 dsp4_boot.py" "$f" || continue
    grep -q "pinctrl" "$f" || continue          # boots via dsp4_boot.py alone
    for c in "$CANON_1" "$CANON_2" "$CANON_3"; do
        grep -qF -- "$c" "$f" || { echo "PIN DRIFT: $f is missing: $c"; RC=1; }
    done
done

# 3. The Python side must agree with the shell side.
python3 - <<'PY' || RC=1
import re, sys
s = open('tools/pi/dsp4_boot.py').read()
m = re.search(r'PIN_HANDBACK = \(\n(.*?)\n\)', s, re.S)
if not m:
    print('PIN DRIFT: dsp4_boot.PIN_HANDBACK not found'); sys.exit(1)
got = re.findall(r"\('([^']+)',\s*'([^']+)'\)", m.group(1))
want = [('6,24', 'op dh'), ('8,12', 'ip'), ('7,9,10,11,22,23,25', 'a0')]
if got != want:
    print('PIN DRIFT: dsp4_boot.PIN_HANDBACK is %r, canonical is %r'
          % (got, want)); sys.exit(1)
PY

[ "$RC" = "0" ] && echo "bench pins: canonical everywhere"
exit $RC
