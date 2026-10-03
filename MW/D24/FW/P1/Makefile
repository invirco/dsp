# P1 application, headless: make CUBE=~/build-p1
# CMSIS headers come from the P1 CubeIDE project (Drivers/CMSIS).
# One image for both display polarities since S169 (no P1-cc build).
CUBE ?= $(HOME)/build-p1
CC = arm-none-eabi-gcc
CFLAGS = -mcpu=cortex-m0plus -mthumb -Os -ffunction-sections -fdata-sections -Wall \
	-DSTM32C031xx -I$(CUBE)/Drivers/CMSIS/Device/ST/STM32C0xx/Include -I$(CUBE)/Drivers/CMSIS/Include
LDFLAGS = -T STM32C031K4UX_FLASH.ld -Wl,--gc-sections -Wl,-Map=P1.map --specs=nano.specs --specs=nosys.specs

P1.bin: P1.elf
	arm-none-eabi-objcopy -O binary $< $@
	arm-none-eabi-objcopy -O ihex $< P1.hex
	arm-none-eabi-size $<

P1.elf: main.c system_stm32c0xx.c startup_stm32c031k4ux.s
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

clean:
	rm -f P1.elf P1.bin P1.hex P1.map
