#!/bin/bash
# dsp4_boot_verify.sh — one clean boot + config + verdict on a DSP4 card.
#
# Runs ON THE PI. Give it the directory holding chip1.ldr / chip2.ldr:
#
#     bash dsp4_boot_verify.sh /home/app/dspboot          # shipping image
#     bash dsp4_boot_verify.sh /home/app/dspboot/work     # a work image
#
# Why it exists: the parameter link drifts out of word phase after a while,
# and once it has, dsp4_diag.py rejects perfectly good answers because the
# ECHO does not match. Reads taken straight after a fresh boot are in phase;
# reads taken later often are not. So this does boot, config and judgement in
# ONE pass, and judges the audio with dsp4_audio_verdict.py (which reads
# FRAME_COUNT and the DMA/SPORT status) rather than with a diag block that
# may refuse to answer.
#
# A post-config diag read failing here says nothing about the card -- the
# verdict line above it is the measurement.
set -u
cd /home/app/dspboot
DIR="${1:-/home/app/dspboot}"
sudo systemctl stop matrix-app >/dev/null 2>&1
# linuxgpiod and dsp4_boot leave GPIOs claimed; without this the SPI link is
# dead on both chips with a known-good image and it looks like a dead card.
# The canonical hand-back (S8-3): CHIP SELECTS DRIVEN HIGH, ready lines as
# inputs, only the SPI and JTAG pins to a0. Giving 6 and 24 to a0 boots chip
# 2 with chip 1's firmware. check_bench_pins.sh enforces this text.
sudo pinctrl set 6,24 op dh >/dev/null 2>&1
sudo pinctrl set 8,12 ip >/dev/null 2>&1
sudo pinctrl set 7,9,10,11,22,23,25 a0 >/dev/null 2>&1
sleep 0.3
python3 dsp4_boot.py --dir "$DIR" 2>&1 | grep -E "chip [12]:|booted"
python3 dsp4_checkchip.py || exit 3   # a wrong CHIP_ID makes everything below fiction
sleep 0.6
echo "--- pre-config diag ---"
python3 dsp4_diag.py --chip 1 2>&1 | grep -E "MAGIC|BOOT_STAGE|FRAME_COUNT|TICKS" \
  || echo "  (link out of phase)"
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 1 2>&1 | tail -1
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 2 2>&1 | tail -1
sleep 1.0
echo "--- verdict ---"
timeout 60 python3 dsp4_audio_verdict.py 3 2>&1 | tail -4
echo "--- post-config diag ---"
python3 dsp4_diag.py --chip 1 2>&1 \
  | grep -E "MAGIC|BOOT_STAGE|BOOT_CFG|FRAME_COUNT|TICKS|BLK_OVER|SPORT0_ERR|PRODUCT" \
  || echo "  (link out of phase — see the verdict above)"
