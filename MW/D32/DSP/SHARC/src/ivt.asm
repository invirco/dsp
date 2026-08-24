/*======================================================================
 * ivt.asm — ADSP-21564 Interrupt Vector Table (static, fixed at boot)
 *
 * Placed in seg_rth at NW address 0x00090000 by the LDF, assembled with
 * -nwc so every entry is a 48-bit NW instruction. Each vector entry is
 * exactly 4 instructions (offset = slot index × 4).
 *
 * The slot names and offsets below are the HARDWARE table, taken from
 * the CCES core support file
 * SHARC/lib/src/crt_src/int_vector_code_SC5XX.asm under __ADSP2156x__
 * (cross-checked against the ADI_CID_* codes in SHARC/include/
 * interrupt.h, whose top byte is the IRPTL/IMASK bit). Do not renumber
 * them by hand.
 *
 * Vectors used here:
 *   0x004  RSTI  -> _start
 *   0x03C  SECI  -> _sec_isr, which demuxes ALL peripheral sources
 *                   (block-clock SPORT DMA, SPI2 param link) via
 *                   SEC_CSID. System events route through the SEC on
 *                   2156x — there are no direct per-peripheral core
 *                   vectors, so this is the only live handler.
 *   0x058  TMZLI -> _diag_timer_isr, the core-timer tick behind the LED
 *                   fault codes (diag.asm). Core-internal: it does not
 *                   pass through the SEC, does not depend on the audio
 *                   clock, and is armed before any peripheral bring-up
 *                   runs — so it still flashes when everything the SECI
 *                   path needs is dead. Lower priority than SECI, so
 *                   audio always wins.
 * Everything else is an RTI filler.
 *
 * HISTORY — 2026-08-11: this table used to open with an unnumbered
 * `_ivt_default` filler block, which pushed every labelled entry one
 * slot later than its comment claimed. Reset survived by luck (the
 * filler landed on EMUI, so `jump _start` landed on RSTI), but
 * `jump _sec_isr` landed at 0x040 — a reserved slot — while SECI at
 * 0x03C held an RTI. On hardware that is a DSP that boots, reaches
 * .wait_boot, and hangs forever: no block-clock interrupt, no SPI
 * parameter interrupt, no product config. Verified against the linked
 * chip1.dxe before and after. Never place unnumbered code in this
 * section.
 *
 * Infrastructure (hand-maintained).
 *======================================================================*/

.extern _start;
.extern _sec_isr;
.extern _diag_timer_isr;

.section/pm seg_rth;

/* Offset 0x000 — EMUI    Emulator interrupt          */ rti; nop; nop; nop;
/* Offset 0x004 — RSTI    Reset                       */ jump _start; nop; nop; nop;
/* Offset 0x008 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x00C — PARI    L1 parity error             */ rti; nop; nop; nop;
/* Offset 0x010 — ILOPI   Illegal opcode              */ rti; nop; nop; nop;
/* Offset 0x014 — CB7I    Circular buffer 7 overflow  */ rti; nop; nop; nop;
#if DSP4_SIMD_STRIPS
/* Offset 0x018 — IICDI   Unaligned long-word access  */ jump _iicdi_isr; nop; nop; nop;
#else
/* Offset 0x018 — IICDI   Unaligned long-word access  */ rti; nop; nop; nop;
#endif
/* Offset 0x01C — SOVFI   Status/loop/PC stack        */ rti; nop; nop; nop;
/* Offset 0x020 — ILADI   Illegal address space       */ rti; nop; nop; nop;
/* Offset 0x024 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x028 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x02C — TMZHI   Timer=0 (high priority)     */ rti; nop; nop; nop;
/* Offset 0x030 — BKPI    Hardware breakpoint         */ rti; nop; nop; nop;
/* Offset 0x034 — FIRI    FIR channel completion      */ rti; nop; nop; nop;
/* Offset 0x038 — IIRI    IIR channel completion      */ rti; nop; nop; nop;

/* ====================================================================
 * Offset 0x03C — SECI: system event controller. The ONLY live
 * peripheral path — SPORT DMA block clock and the SPI2 parameter link
 * both arrive here and are demuxed by _sec_isr via SEC_CSID.
 * ==================================================================== */
                                                          jump _sec_isr; nop; nop; nop;

/* Offset 0x040 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x044 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x048 — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x04C — (reserved)                          */ rti; nop; nop; nop;
/* Offset 0x050 — RINSEQI Restricted instr. sequence  */ rti; nop; nop; nop;
/* Offset 0x054 — CB15I   Circular buffer 15 overflow */ rti; nop; nop; nop;
#if DSP4_BISECT == 26
/* TEMP bisect rung 26 (2026-08-22): the TMZLI vector, but with nothing
 * behind it. Rung 24 showed the core dies once the core timer is the
 * only unmasked interrupt, and this splits that in two — an RTI-only
 * vector still dying means the fault is in TAKING the interrupt (the
 * NW-coded IVT jumping into VISA code, the status stack, MODE1); the
 * core surviving means the fault is inside _diag_timer_isr's body. */
/* Offset 0x058 — TMZLI   Timer=0 (low priority)      */ rti; nop; nop; nop;
#else
/* Offset 0x058 — TMZLI   Timer=0 (low priority)      */ jump _diag_timer_isr; nop; nop; nop;
#endif
/* Offset 0x05C — FIXI    Fixed-point overflow        */ rti; nop; nop; nop;
/* Offset 0x060 — FLTOI   Float overflow              */ rti; nop; nop; nop;
/* Offset 0x064 — FLTUI   Float underflow             */ rti; nop; nop; nop;
/* Offset 0x068 — FLTII   Float invalid               */ rti; nop; nop; nop;
/* Offset 0x06C — EMULI   Emulator low priority       */ rti; nop; nop; nop;
/* Offset 0x070 — SFT0I   User software interrupt 0   */ rti; nop; nop; nop;
/* Offset 0x074 — SFT1I   User software interrupt 1   */ rti; nop; nop; nop;
/* Offset 0x078 — SFT2I   User software interrupt 2   */ rti; nop; nop; nop;
/* Offset 0x07C — SFT3I   User software interrupt 3   */ rti; nop; nop; nop;

/* End of the hardware table (0x080). The LDF region mem_iv_code runs to
 * 0x00090103; the remainder is left unwritten rather than padded with
 * fillers that only pretend to be vectors. */
