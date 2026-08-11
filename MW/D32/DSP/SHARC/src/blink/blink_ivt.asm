/*======================================================================
 * blink_ivt.asm — minimal interrupt vector table for the blink image.
 *
 * Same hardware layout rule as src/ivt.asm: NW instructions at
 * 0x00090000, 4 per slot, RSTI at offset 0x004 (slot 0 is EMUI). The
 * blink image enables no interrupts, so RSTI is the only live entry —
 * but the two leading slots still have to exist or reset lands in the
 * wrong place.
 *
 * Assembled with -nwc (NW code), like the main IVT.
 *======================================================================*/

.extern _start;

.section/pm seg_rth;

/* Offset 0x000 — EMUI  Emulator interrupt */ rti;  nop; nop; nop;
/* Offset 0x004 — RSTI  Reset              */ jump _start; nop; nop; nop;
