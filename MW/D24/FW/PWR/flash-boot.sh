#!/bin/bash
# Bootloader flash (0x08000000, pages 0-3). WRP must be OFF for this to
# succeed — disable first if set:
#   ... -c "init; halt; flash protect 0 0 0 off; stm32f1x options_load 0"
# and re-enable afterwards (see tasks/def notes). Normal firmware work uses
# flash-app.sh only. Bench only: the bootloader is never replaced in the field.
#
# HOT-ATTACH ONLY — never `reset halt` (PW ruling 2026-09-18; see
# flash-app.sh for why). The running core is halted with its rail pins
# still driven, pages 0-3 are erased and written, and SYSRESETREQ boots
# the new bootloader. Do not run this against a blank or crashed U34 from
# the CM4: with no firmware driving the rails the CM4 is not powered —
# that case is J32 with an external probe.
set -e
BIN="${1:-$(dirname "$0")/boot.bin}"
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
