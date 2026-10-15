#!/bin/bash
# Flash pwr-mcu-blink (pwr-mcu-safe.bin) into U34 over SWD mux ch1 (run on
# the D24 CM4). The cfg is hot-attach-safe (reset_config none).
# HOT-ATTACH ONLY — never `reset halt` (PW ruling 2026-09-18; see
# flash-app.sh). Note this image leaves every rail pin hi-Z: with the
# 2026-09-13 pull-downs the rails drop at the SYSRESETREQ restart, so on a
# rev C this is a bench image for a unit on an external supply, not a
# recovery image. Prereq: +12V input present (mux gate drive is raw +12V).
set -e
BIN="${1:-$(dirname "$0")/pwr-mcu-safe.bin}"
ADDR=0x08000000
sudo openocd -f /home/app/pwr-mcu-swd.cfg \
    -c "pwrmcu.cpu configure -event reset-start {}" \
    -c "pwrmcu.cpu configure -event reset-init {}" \
    -c "init" \
    -c "cortex_m reset_config sysresetreq" \
    -c "halt" \
    -c "echo {GPIOA ODR before flash (bit2 UPS_EN, bit3 PSU_DIG_EN):}" \
    -c "mdw 0x48000014" \
    -c "flash write_image erase $BIN $ADDR" \
    -c "verify_image $BIN $ADDR" \
    -c "reset run" \
    -c "shutdown"
