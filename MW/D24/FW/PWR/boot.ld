/* Bootloader: first 4 KB of the STM32F030F4 (WRP block 0 = pages 0-3).
   No .data/.bss — boot.c keeps all state on the stack (the app's .noinit
   reset log and the mailbox must survive it). The ASSERTs make a stray
   global a link error instead of a silent orphan section. */
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

  .data : { *(.data*) } > RAM AT> FLASH
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
  ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "boot.c must not use globals")
}
