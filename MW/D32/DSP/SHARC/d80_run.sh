#!/bin/bash
# d80_run.sh — bench half of d80.sh. Boots the staged image, configures
# BOTH chips, and then reads the chip-2 METERS at a LADDER of elapsed times off
# ONE boot, with the frame counter and the overrun counter beside every read.
#
# D80 asks whether the 0.4-0.9 % cross-build meter delta is arithmetic or a
# point on a convergence curve. A meter is a per-BLOCK IIR: a 300 ms RMS
# window is ~9.6 s of WALL CLOCK under DEC=32 and the 1.333 s peak decay is
# ~43 s, so a 12 s dwell reads a curve, not a value -- and the two arms run
# at different speeds, so they read it at different points. Capturing the
# same meters repeatedly against FRAME_COUNT lets the two arms be compared at
# equal GRAPH PASSES instead of equal wall clock, which is the comparison the
# instrument should have been making.
#
# Usage: d80_run.sh "12,30,60,120,240" OUT.json
set -u
TIMES="$1"; OUT="$2"
cd "${STAGE:-/home/app/dspboot}"

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=d80_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

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

for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    # CHIP-IDENTITY GATE (S8-3). dsp4_boot.py now applies the canonical
    # pin hand-back and reads CHIP_ID back itself, so this is the second
    # of two; it is here as well because this loop's own retry is what
    # decides whether a measurement is taken, and a boot that came up as
    # two chip 1s must NOT be one of the tries that counts as success.
    python3 dsp4_checkchip.py --quiet || continue
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
  python3 - "$OUT" "$TIMES" <<'PYEOF'
import json, sys, time
out = sys.argv[1]
times = [float(t) for t in sys.argv[2].split(',')]
sys.argv = ['p']
import dsp4_diag as D

# CALIBRATES the answer phase (D74), exactly as c2gold_run.sh does: a
# register that reads 0 is not a measurement until this has run.
dg = None
for _ in range(4):
    try:
        dg = D.DiagLink(D.SpiLink('0.0', 1000000, 24, rdy_gpio=12))
        dg.resync()
        break
    except (IOError, OSError):
        dg = None
if dg is None:
    print('UNPHASED: the parameter link would not phase to chip 2')
    sys.exit(3)


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


def reg(a):
    for _ in range(12):
        try:
            v = dg.read(a)
        except IOError:
            continue
        if v is not None:
            return v
    return None


sym = json.load(open('chip2.sym.json'))
# The meter set is c2gold's, so the two instruments name the same probes.
METERS = ['C2_MTR_AUX_01', 'C2_MTR_AUX_04', 'C2_MTR_AUX_07', 'C2_MTR_AUX_12',
          'C2_MTR_GRP_01', 'C2_MTR_GRP_04',
          'C2_MTR_MAIN_01', 'C2_MTR_MAIN_02', 'C2_MTR_MAIN_03',
          'C2_MTR_MAIN_04', 'C2_MTR_SUB',
          'C2_MTR_FX_01', 'C2_MTR_FX_06']
# The dynamics switches, so a capture cannot be attributed to an engaged
# GATE/COMP that was never on.
WITNESS = ('_gate_on_C2_GRP_GATE_01', '_comp_on_C2_GRP_COMP_01',
           '_comp_on_C2_MAIN_OCOMP_01', '_comp_on_C2_SUB_COMP',
           '_comp_on_C2_MAIN_COMP')

t0 = time.monotonic()
caps = []
for want in times:
    dt = want - (time.monotonic() - t0)
    if dt > 0:
        time.sleep(dt)
    # THE COUNTERS BRACKET THE READ. A meter capture takes seconds over this
    # link, and FRAME_COUNT advances the whole time; quoting one value would
    # attribute a spread of graph passes to a point. Both ends are recorded
    # and the analysis uses the midpoint, with the spread on the table.
    fc0 = reg(0xE004)
    ov0 = reg(0xE00A)
    rec = {}
    bad = False
    for mid in METERS:
        for pfx in ('_mtr_peak_', '_mtr_rms_'):
            nm = pfx + mid
            if nm not in sym:
                continue
            v = peek(sym[nm])
            if v is None:
                bad = True
                continue
            rec[nm] = v
    fc1 = reg(0xE004)
    ov1 = reg(0xE00A)
    caps.append({'t': round(time.monotonic() - t0, 2),
                 'frame0': fc0, 'frame1': fc1,
                 'ovr0': ov0, 'ovr1': ov1,
                 'unreadable': bad, 'm': rec})
    print('  t=%6.1fs  frame %s..%s  overrun %s  probes %d%s'
          % (caps[-1]['t'], fc0, fc1, ov1, len(rec),
             '  (SOME UNREADABLE)' if bad else ''))

wit = {w: peek(sym[w]) for w in WITNESS if w in sym}
json.dump({'caps': caps, 'witness': wit}, open(out, 'w'))
print('  dynamics witness: ' + ' '.join(
    '%s=%s' % (k.replace('_C2_', ' '), v) for k, v in wit.items()))
print('%d captures written' % len(caps))
PYEOF
  RC=$?
  [ "$RC" = "0" ] && exit 0
  echo "(attempt $attempt: capture failed rc=$RC)"
done
echo "no clean capture in 3 attempts"
exit 4
