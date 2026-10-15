#!/bin/bash
# App-only flash: writes the .img at 0x08001000, never touching the
# bootloader pages (which WRP additionally protects). An interrupted run
# leaves a CRC-invalid app -> bootloader triple-blink, rails per the rocker
# (rocker-gate bootloader), unit reflashable: the field-update path
# (fn.fw_update).
#
# HOT-ATTACH ONLY — never `reset halt` (PW ruling 2026-09-18). The CM4
# running this script is powered by rails U34's own pins enable; a reset
# with the pins hi-Z (pull-downs since 2026-09-13) switches the CM4 off
# mid-flash (incident 2026-09-15). So: attach without reset, halt the
# running core (GPIO output latches keep driving the rails), erase+write
# the app region, verify, then restart with SYSRESETREQ. The ~ms hi-Z
# window at that restart is covered by the rocker-follow mod (rev C test
# batch hand mod, rev D copper: enables pulled up from a rocker-switched
# 3V3_SW net) and by the bootloader driving the rail pins first thing.
# `program` is not used: it does `reset init` internally.
# Prereq: +12V input present (mux gate drive is raw +12V); +5V5 >= 4.85 V.
set -e
IMG="${1:-$(dirname "$0")/pwr-mcu.img}"
ADDR=0x08001000
sudo openocd -f /home/app/pwr-mcu-swd.cfg \
    -c "pwrmcu.cpu configure -event reset-start {}" \
    -c "pwrmcu.cpu configure -event reset-init {}" \
    -c "init" \
    -c "cortex_m reset_config sysresetreq" \
    -c "halt" \
    -c "echo {GPIOA ODR before flash (bit2 UPS_EN, bit3 PSU_DIG_EN):}" \
    -c "mdw 0x48000014" \
    -c "flash write_image erase $IMG $ADDR" \
    -c "verify_image $IMG $ADDR" \
    -c "reset run" \
    -c "shutdown"
