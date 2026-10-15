/* Bootloader: first 4 KB of the STM32F030F4 (WRP block 0 = pages 0-3).
   No .data/.bss — boot.c deliberately uses no writable globals. */
MEMORY
{
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 4K
  RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 4K
}

SECTIONS
{
  .text :
  {
    KEEP(*(.isr_vector))
    *(.text*)
    *(.rodata*)
  } > FLASH
}
