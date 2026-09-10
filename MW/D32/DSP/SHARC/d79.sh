#!/bin/bash
# d79.sh — D79: THE STRAY CONFIG WORD, ROOT-CAUSED AND FIXED IN THE FIRMWARE.
#
# D79 (2026-08-28 on chip 1, 2026-09-01 on chip 2) is ONE defect with two
# faces. The parameter protocol is two words with no framing: `word0[31:16] =
# address`, `word1 = value`. Lose ONE word out of the DSP's receive stream and
# every request after it is a word out of phase -- the DSP reads the previous
# transaction's VALUE as the next one's ADDRESS. Config values are small
# integers, so `value >> 16` is ZERO for nearly all of them, and SPI address
# 0x0000 is a LIVE AUDIO PARAMETER on both chips:
#
#     chip 1  0x0000 = _gain_coeff_C1_GAIN_01     strip 1's gain
#     chip 2  0x0000 = _fdr_level_C2_AUX_FDR_01   aux 1's fader head
#
# The value written there is the NEXT transaction's HEADER word: 0xF0040000 on
# chip 1 (CFG_COMMIT is register 0xF004) and 0xE0FE0000 on chip 2 (DIAG_NOP).
# Both are exactly what was reported. Chip 2 never "needed a gainfix of its
# own" -- it needed the same word to stop going missing.
#
# WHERE THE WORD GOES: _diag_timer_isr's stuck-partial-request recovery
# (diag.asm, 2026-08-22) discards a word from SPI2_RFIFO after three
# consecutive 1 ms ticks that find the RX FIFO neither empty nor full. The
# host's config burst is 51 back-to-back transactions at 1 MHz -- 32 us a word
# -- so a 1 kHz tick that keeps landing inside the second word sees "part
# full" three ticks running and throws a LIVE word away. The recovery designed
# to unwedge the link is what corrupts the config.
#
# THE FIX IS DSP4_SPI_PARTIAL_FIX2 AND IT WAS ALREADY IN THE TREE, DEFAULTED
# OFF. It arms the recovery only while `_spi_rx_count` is standing still,
# which is what residue looks like (the original 2026-08-22 capture: SPI_RX_
# COUNT frozen at 74) and what a busy link never does.
#
# TWO ARMS, and the control is the one that must FAIL:
#   arm off  DSP4_SPI_PARTIAL_FIX2=0 -- the shipping default until 2026-09-10
#   arm on   DSP4_SPI_PARTIAL_FIX2=1 -- the gate
# Both carry DSP4_CFG_WATCH=1 so the recovery's own counters are readable;
# that switch adds registers and changes nothing about the recovery itself.
#
#   ./d79.sh                 # 12 boots per arm
#   BOOTS=24 ./d79.sh
#   ARMS="1" ./d79.sh        # the fixed arm only
set -u
BOOTS="${BOOTS:-12}"
ARMS="${ARMS:-0 1}"
WORK="${WORK:-/tmp/d79}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
# THE SHARED SCRATCH SLOT, NAMED (S16-9). ~/dspboot/chip{1,2}.ldr is not a
# staged pair -- it is whatever the last measurement run left there, and this
# script overwrites it. The staged pairs are the PREFIXED ones (blk_*, cand_*,
# geq_*, dyn_*, flr_*, conf_*, ship_*, tx_*, s16_*) and nothing here writes
# those. STAGE names a directory of this run's own when the image must survive
# the next script; it defaults to the scratch slot so nothing that calls this
# changes behaviour.
STAGE="${STAGE:-/home/app/dspboot}"

# A staging path other than ~/dspboot needs the shared bench helpers the run
# script imports. Symlinked, not copied, so there is one working set and a
# staged run cannot drift from it.
if [ "$STAGE" != "/home/app/dspboot" ]; then
  ssh $BENCH "mkdir -p '$STAGE' && for f in /home/app/dspboot/*.py; do \
      ln -sfn \"\$f\" '$STAGE'/\$(basename \"\$f\"); done" || exit 3
fi
mkdir -p "$WORK"

run_arm() {   # $1 = DSP4_SPI_PARTIAL_FIX2 (0|1)
  local K="$1"
  local D="$WORK/fix2-$K"
  DSP_BUILD_DIR="$D" DSP4_BISECT=0 DSP4_CFG_WATCH=1 \
    DSP4_SPI_PARTIAL_FIX2=$K ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM fix2=$K BUILD FAILED (see $D.log)" >&2; return 1; fi
  echo "  fix2=$K image: chip1.ldr $(md5sum $D/chip1.ldr | cut -c1-8) chip2.ldr $(md5sum $D/chip2.ldr | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:$STAGE/
  scp -q $ROOT/tools/pi/dsp4_d79.py $ROOT/tools/pi/dsp4_config.py \
         $ROOT/tools/pi/dsp4_diag.py $ROOT/tools/pi/dsp4_scope.py $BENCH:$STAGE/
  # BENCH PROCEDURE (S8-3): the boot tool and the chip-identity gate go
  # with every run, so a bench cannot be left on a stale dsp4_boot.py that
  # still hands GPIO 6/24 to a0. Path is script-relative, not $ROOT: not
  # every script in here defines one.
  scp -q "$(dirname "$0")/../../../../tools/pi/dsp4_checkchip.py" "$(dirname "$0")/../../../../tools/pi/dsp4_boot.py" $BENCH:$STAGE/
  scp -q d79_run.sh $BENCH:/home/app/
  ssh $BENCH "STAGE='$STAGE' bash /home/app/d79_run.sh $BOOTS $STAGE/d79fix2-$K.json" \
    2>&1 | sed "s/^/  fix2=$K: /"
  scp -q $BENCH:$STAGE/d79fix2-$K.json "$WORK/" 2>/dev/null
}

echo "=== D79: the word at SPI dispatch index 0, $BOOTS boots per arm ==="
for K in $ARMS; do
  echo "--- DSP4_SPI_PARTIAL_FIX2=$K ---"
  run_arm "$K" || exit 1
done
