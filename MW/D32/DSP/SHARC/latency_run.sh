#!/bin/bash
# latency_run.sh — bench half of the through-DSP latency arm.
#
# The instrument is dsp4_dsp_latency.py, NOT dsp4_loop_latency.py: the
# through-DSP path is not bit-transparent, so a per-word vote for an offset
# finds spurious modes (that is where the 2026-09-08 figure of 14,550 came
# from). Every candidate offset is scored by the fraction of frames carrying
# the exact expected value and the answer is quoted only with its margin.
#
# Quote DIFFERENCES between arms measured the same way. The absolute number
# carries the deliberate 0.3 s arecord pre-roll and the ALSA start offset.
set -u
STAGE="${STAGE:-/home/app/dspboot}"
cd "$STAGE"
BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {FD}>"$BENCH_LOCKFILE"; flock "$FD"
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

# LOGIC-ONLY arm: no DSP boot at all, the CPLD loops the Pi back on itself.
if [ "${LOGIC_ONLY:-0}" = "1" ]; then
  python3 dsp4_dsp_latency.py --reps "${REPS:-20}"
  exit $?
fi

# THE READINESS GATE IS A GATE NOW (S83). What was here booted once,
# configured up to three times, printed whatever stage it had reached and
# went on to take twenty reps regardless. On 2026-09-20 it printed
# `chip1 stage=5 chip2 stage=5` on all four boots of S82 and the bar
# reported forty confident-looking rows of a flat field. Two changes, both
# taken from s82_run.sh, which reaches stage 7 on the same pair:
#
#   * the CONFIG TOOL'S OUTPUT IS READ. `dsp4_config.py` exits at import
#     when `input_patch.json` is not beside it, and that was the whole
#     fault -- a staged arm never had one (latency.sh, S83-2). Sending
#     that to /dev/null is what made a deterministic, one-line error look
#     like a flaky part for a session and a half.
#   * the WHOLE boot is retried, and a part that will not come up STOPS
#     the run. MAGIC is checked before BOOT_STAGE is believed, because a
#     stage read off a link that is not answering is not a stage.
BOOTED=0
for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    python3 dsp4_checkchip.py --quiet || continue
    ID=$(python3 dsp4_diag.py --chip 2 2>&1 | grep CHIP_ID | awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  for c in 1 2; do
    CFG1=$(python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 1 2>&1); sleep 2
    CFG2=$(python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 2 \
                  --cs-gpio 24 --rdy-gpio 12 2>&1)
    sleep 3
    case "$CFG1$CFG2" in
      *ERROR*|*Traceback*)
        echo "  config REFUSED — the arm is not configured:"
        printf '%s\n%s\n' "$CFG1" "$CFG2" | grep -E 'ERROR|Error' | head -2 | sed 's/^/    /'
        ;;
    esac
    G1=0; G2=0
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      echo "$O" | grep -q "MAGIC          0xD5B40001" && {
        S1=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S1" ] && [ "$S1" -ge 6 ] 2>/dev/null && G1=1; }
      O2=$(python3 dsp4_diag.py --chip 2 2>&1)
      echo "$O2" | grep -q "MAGIC          0xD5B40001" && {
        S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && G2=1; }
      [ "$G1" = "1" ] && [ "$G2" = "1" ] && { BOOTED=1; break; }
      sleep 1
    done
    [ "$BOOTED" = "1" ] && break
  done
  [ "$BOOTED" = "1" ] && break
  echo "  (attempt $attempt: chip1 stage=${S1:-?} chip2 stage=${S2:-?} — re-booting)"
done
echo "  boot: chip1 stage=${S1:-?} chip2 stage=${S2:-?}"
if [ "$BOOTED" != "1" ]; then
  echo "LATENCY: NO MEASUREMENT — the pair is not at BOOT_STAGE 6 on both"
  echo "chips, so the graph is not turning and nothing in a capture can"
  echo "correlate with the stimulus. Fix the boot, not the capture path."
  exit 1
fi
python3 gainfix.py 2>&1 | sed 's/^/  /'
# PASS-THROUGH FIRST, OR THE ARM MEASURES NOTHING. Seventeen sources sum
# into C2_MIX_MAIN_L and the main chain's nodes come up at their landed
# values, so the Pi's stimulus arrives back riding the other sixteen and
# the offset scorer finds NO coherent frames at all -- measured
# 2026-09-09 on this arm before the setup was added: 20 reps, offset
# 14,779 on every one, coherent 0.0 %, peak width 400. An offset with a
# zero coherent fraction is not a latency; it is the scorer reporting
# that the stimulus never came back.
python3 dsp4_passthru_setup.py 2>&1 | tail -6 | sed 's/^/  /'
python3 dsp4_dsp_latency.py --reps "${REPS:-20}"
