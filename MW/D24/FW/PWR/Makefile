# Build host = flash host = the D24 CM4 (gcc-arm-none-eabi via apt).
# Images:
#   boot.bin          — 4 KB WRP bootloader @ 0x08000000 (flash-boot.sh;
#                       WRP must be off to reflash it)
#   pwr-mcu.img       — app @ 0x08001000, full rail authority (flash-app.sh)
#   pwr-mcu-safe.img  — BENCH_SAFE app: rails assert-only, never cut.
#                       Flash first on a freshly reworked board.
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
CFLAGS  = -mcpu=cortex-m0 -mthumb -Os -Wall -Wextra -ffreestanding -nostdlib
DEPS    = main.c config.h board.h pwr-mcu.ld

all: boot.bin pwr-mcu.img pwr-mcu-safe.img

boot.elf: boot.c board.h boot.ld
	$(CC) $(CFLAGS) -T boot.ld -o $@ boot.c -lgcc

pwr-mcu.elf: $(DEPS)
	$(CC) $(CFLAGS) -T pwr-mcu.ld -o $@ main.c -lgcc

pwr-mcu-safe.elf: $(DEPS)
	$(CC) $(CFLAGS) -DBENCH_SAFE -T pwr-mcu.ld -o $@ main.c -lgcc

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	arm-none-eabi-size $<

%.img: %.bin
	python3 mkimage.py $< $@

clean:
	rm -f *.elf *.bin *.img
