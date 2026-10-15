# D24 power MCU (U34, STM32F030F4P6). Builds on the desk or on the D24 CM4
# (gcc-arm-none-eabi via apt).
# Images:
#   boot.bin          — 4 KB WRP bootloader @ 0x08000000 (flash-boot.sh;
#                       WRP must be off to reflash it)
#   pwr-mcu.img       — app @ 0x08001000, full rail authority (flash-app.sh,
#                       or over the host link: tools/pi/d24_pwrlink.py update)
#   pwr-mcu-safe.img  — BENCH_SAFE app: rails assert-only, never cut.
# `make check` = size gates + the off-target tests in tests/.
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
CFLAGS  = -mcpu=cortex-m0 -mthumb -Os -Wall -Wextra -ffreestanding -nostdlib
APPSRC  = main.c link.c p1.c
APPDEPS = $(APPSRC) config.h board.h link.h proto.h p1.h pwr-mcu.ld
BOOTSRC = boot.c bootcmd.c link.c
BOOTDEPS = $(BOOTSRC) board.h config.h link.h proto.h bootcmd.h boot.ld

all: boot.bin pwr-mcu.img pwr-mcu-safe.img

boot.elf: $(BOOTDEPS)
	$(CC) $(CFLAGS) -T boot.ld -o $@ $(BOOTSRC) -lgcc

pwr-mcu.elf: $(APPDEPS)
	$(CC) $(CFLAGS) -T pwr-mcu.ld -o $@ $(APPSRC) -lgcc

pwr-mcu-safe.elf: $(APPDEPS)
	$(CC) $(CFLAGS) -DBENCH_SAFE -T pwr-mcu.ld -o $@ $(APPSRC) -lgcc

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	arm-none-eabi-size $<

%.img: %.bin
	python3 mkimage.py $< $@

# GATE: boot within 4 KB, images within 12 KB, every image's CRC re-checked
sizes: all
	@python3 tools/gate.py boot.bin pwr-mcu.img pwr-mcu-safe.img

check: sizes
	$(MAKE) -C tests

clean:
	rm -f *.elf *.bin *.img
	$(MAKE) -C tests clean

.PHONY: all sizes check clean
