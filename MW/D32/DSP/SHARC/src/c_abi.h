/*======================================================================
 * c_abi.h — the cc21k C calling convention, for the assembly side.
 *
 * WHY THIS EXISTS (P2.2, 2026-08-21). main.asm called the three C
 * config functions with a plain `call`, and the four small assembly
 * helpers that C calls returned with a plain `rts`. Neither is the
 * convention cc21k generates, and the mismatch is what wedged the
 * firmware in `_sru_init`: every SRU register write in it completed
 * (proved standalone by src/blink/sruprobe.asm — all 36 DAI0 writes,
 * with the routing read back afterwards), but the function could not
 * return, so the core vectored into whatever the frame happened to
 * contain. It looked exactly like a peripheral that would not respond.
 *
 * THE CONVENTION, taken from what the compiler emits (compile any C
 * file with -S and read it) and from CCES's own
 * SHARC/lib/src/libc_src/set_c.asm:
 *
 *   caller:   cjump fn (db);
 *             dm(i7,m7) = r2;      <- delay slot 1, frame slot
 *             dm(i7,m7) = pc;      <- delay slot 2, return address
 *
 *   callee:   i12 = dm(m7,i6);     <- fetch that return address
 *             jump (m14,i12) (db);
 *             rframe;              <- delay slot 1, unwind the frame
 *             nop;                 <- delay slot 2
 *
 * and it only works if the compiler's DAG registers are set up:
 * M7 = -1 (the stack push), M14 = 1 (the return jump lands one past
 * the stored address), M5/M6/M13/M15 as below. main.asm set B/I/L for
 * the stack but never touched a single M register — with M7 and M14
 * left at whatever the boot kernel had put there, the push and the
 * return both went somewhere arbitrary.
 *
 * Arguments are R4, R8, R12 (then the stack); the return value is R0.
 * That part the existing helpers already had right.
 *
 * Infrastructure (hand-maintained). Include from assembly only.
 *======================================================================*/

#ifndef _DSP4_C_ABI_H
#define _DSP4_C_ABI_H

/*----------------------------------------------------------------------
 * C_RUNTIME_INIT — the compiler-register half of CCES's
 * ___lib_setup_c, which this firmware does not link (it has its own
 * _start, not the CCES CRT). Must run before the first C call.
 *
 * Deliberate differences from set_c.asm, all of them documented rather
 * than accidental:
 *   - L6/L7 stay 0. ADI makes the stack a circular buffer purely so an
 *     overflow wraps instead of running away; linear is fine and is
 *     what this file has always used.
 *   - NESTM is NOT set. diag.asm and the SEC handler are written for
 *     non-nesting interrupts (TMZLI must never preempt _sec_isr), and
 *     set_c.asm's choice would silently reverse that.
 *   - MMASK is left alone for the same reason: the ISRs here manage
 *     their own mode bits.
 *   - IRPTEN is left alone; _diag_init owns it.
 *--------------------------------------------------------------------*/
#define C_RUNTIME_INIT                                                  \
    m5  = 0;                                                            \
    m6  = 1;                                                            \
    m7  = -1;                                                           \
    m13 = 0;                                                            \
    m14 = 1;                                                            \
    m15 = -1;                                                           \
    l0 = 0;  l1 = 0;  l2 = 0;  l3 = 0;                                  \
    l4 = 0;  l5 = 0;                                                    \
    l8 = 0;  l9 = 0;  l10 = 0; l11 = 0;                                 \
    l12 = 0; l13 = 0; l14 = 0; l15 = 0;                                 \
    b7 = ldf_stack_space;                                               \
    i7 = ((ldf_stack_space + ldf_stack_length - 4)                      \
          - ((ldf_stack_space + ldf_stack_length - 4) % 8));            \
    l7 = 0;                                                             \
    b6 = ldf_stack_space;                                               \
    i6 = i7;                                                            \
    l6 = 0;                                                             \
    bit clr mode1 (BITM_REGF_MODE1_SRD1H | BITM_REGF_MODE1_SRD1L |      \
                   BITM_REGF_MODE1_SRD2H | BITM_REGF_MODE1_SRD2L |      \
                   BITM_REGF_MODE1_ALUSAT | BITM_REGF_MODE1_TRUNCATE);  \
    bit set mode1 (BITM_REGF_MODE1_RND32 | BITM_REGF_MODE1_CBUFEN);     \
    nop;                                                                \
    nop;

/*----------------------------------------------------------------------
 * CCALL(fn) — call a C function from assembly.
 *
 * Clobbers whatever the callee clobbers (r0-r2, r4, r8, r12, i12 and
 * the argument registers). Pass arguments in r4/r8/r12 BEFORE the
 * macro; the two stores are delay slots and must not be displaced.
 *--------------------------------------------------------------------*/
#define CCALL(fn)                                                       \
    cjump fn (db);                                                      \
    dm(i7,m7) = r2;                                                     \
    dm(i7,m7) = pc;

/*----------------------------------------------------------------------
 * C_RETURN — return from an assembly function that C called.
 *
 * Use INSTEAD of rts. Valid for a leaf with no frame of its own, which
 * is all four of ours; anything that allocates locals must also do the
 * matching `modify(i7,-n) (nw)` prologue the compiler emits.
 * Clobbers i12.
 *--------------------------------------------------------------------*/
#define C_RETURN                                                        \
    i12 = dm(m7,i6);                                                    \
    jump (m14,i12) (db);                                                \
    rframe;                                                             \
    nop;

#endif /* _DSP4_C_ABI_H */
