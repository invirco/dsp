/* STM32F030F4P6: 16 KB flash, 4 KB SRAM.
   App region: 12 KB above the 4 KB WRP bootloader (boot.ld). The app is
   flashed as the mkimage.py output (length patched, CRC32 appended). */
MEMORY
{
  FLASH (rx) : ORIGIN = 0x08001000, LENGTH = 12K
  RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 4K
}

SECTIONS
{
  /* Reset log: survives every reset except power-on (SRAM keeps its
     contents through NRST/watchdog/software resets). Never zeroed. */
  .noinit (NOLOAD) :
  {
    _snoinit = .;
    *(.noinit*)
    _enoinit = .;
  } > RAM

  .text :
  {
    KEEP(*(.isr_vector))
    KEEP(*(.app_header))
    *(.text*)
    *(.rodata*)
  } > FLASH

  _sidata = LOADADDR(.data);
  .data :
  {
    _sdata = .;
    *(.data*)
    _edata = .;
  } > RAM AT> FLASH

  .bss :
  {
    _sbss = .;
    *(.bss*)
    *(COMMON)
    _ebss = .;
  } > RAM
}
