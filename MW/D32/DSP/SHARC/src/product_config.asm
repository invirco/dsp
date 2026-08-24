/*======================================================================
 * product_config.asm — boot-time product configuration (decision D3)
 *
 * ONE firmware image serves D24 and D32. At boot the Pi/CM4 host (D1)
 * writes the config registers below over the normal SPI parameter
 * protocol, then writes CONFIG_COMMIT; commit applies the input patch
 * and scope gates and releases the main loop (_boot_config_received).
 *
 * Register block (flat SPI address space, far above the generated
 * parameter dispatch table; same layout on both chips — each chip has
 * its own CS, the host writes each chip it needs):
 *
 *   0xF000  PRODUCT_ID   0 = D32 (default), 1 = D24
 *   0xF001  CHAN_MASK    active input strips (bit n = strip n+1);
 *                        D24 boots 0x00FFFFFF (strips 25-32 NET-only)
 *   0xF002  AUX_MASK     active aux buses
 *   0xF003  OUT_MUX      bit 0: B_O2 content select, 0 = D24 codec,
 *                        1 = D32 snake. Stored only for now — the D32
 *                        snake output patch is not generated yet; the
 *                        TX gather must consume this when it lands.
 *   0xF004  CONFIG_COMMIT  write 1: apply patch + gates, release boot
 *   0xF010+ INPUT_PATCH  (chip 1 only) one reg per packed RX channel i:
 *                        packed default index whose slot var receives
 *                        DMA channel i (identity by default). Used for
 *                        the D24 console-channel interleave — see
 *                        MW/D32/DSP/product-config.md for the table.
 *
 * Product ids here must match the generated scope_gates.asm (0=D32,
 * 1=D24). Infrastructure (hand-maintained).
 *======================================================================*/

#include "diag.h"

#define CFG_BASE        0xF000
#define CFG_PRODUCT_ID  0xF000
#define CFG_CHAN_MASK   0xF001
#define CFG_AUX_MASK    0xF002
#define CFG_OUT_MUX     0xF003
#define CFG_COMMIT      0xF004
#define CFG_PATCH_BASE  0xF010

.section/dm seg_dmda;

.global _product_id;
.var _product_id = 0;             /* 0 = D32 (default), 1 = D24 */
.global _out_mux;
.var _out_mux = 0;

.extern _chan_mask;
.extern _aux_mask;
.extern _boot_config_received;
.extern _diag_boot_stage;

#if CHIP_ID == 1
.extern _rx_patch_regs;
.extern _c1_rx_slot_count;
#endif

.section/pm seg_pmco;

.extern _scope_gates_apply;
#if DSP4_BQ_SELFTEST
.extern _bq_selftest;
#endif
#if CHIP_ID == 1
.extern _rx_patch_apply;
#endif

/*----------------------------------------------------------------------
 * _product_config_write — dispatch one config register write
 * In: r2 = SPI address (>= 0xF000), r1 = value
 * Called from the SPI RX ISR; clobbers r0-r6, i0-i2, m1 (ISR-owned).
 *----------------------------------------------------------------------*/
.global _product_config_write;
_product_config_write:
    r4 = CFG_PRODUCT_ID;
    comp(r2, r4);
    if eq jump (pc, .cfg_product);
    r4 = CFG_CHAN_MASK;
    comp(r2, r4);
    if eq jump (pc, .cfg_chan);
    r4 = CFG_AUX_MASK;
    comp(r2, r4);
    if eq jump (pc, .cfg_aux);
    r4 = CFG_OUT_MUX;
    comp(r2, r4);
    if eq jump (pc, .cfg_outmux);
    r4 = CFG_COMMIT;
    comp(r2, r4);
    if eq jump (pc, .cfg_commit);

#if CHIP_ID == 1
    /* Input patch regs: 0xF010 .. 0xF010 + rx_slot_count - 1 */
    r4 = CFG_PATCH_BASE;
    comp(r2, r4);
    if lt jump (pc, .cfg_ignore);
    r2 = r2 - r4;                 /* patch index */
    r4 = dm(_c1_rx_slot_count);
    comp(r2, r4);
    if ge jump (pc, .cfg_ignore);
    i0 = _rx_patch_regs;
    m1 = r2;
    modify(i0, m1);
    dm(i0, 0) = r1;
    rts;
#endif

.cfg_ignore:
    rts;                          /* unknown config register: ignore */

.cfg_product:
    dm(_product_id) = r1;
    rts;
.cfg_chan:
    dm(_chan_mask) = r1;
    rts;
.cfg_aux:
    dm(_aux_mask) = r1;
    rts;
.cfg_outmux:
    dm(_out_mux) = r1;
    rts;

.cfg_commit:
    jump _product_config_commit;  /* tail call; commit's rts returns to ISR */
_product_config_write.end:

/*----------------------------------------------------------------------
 * _product_config_commit — apply configuration and release boot
 *----------------------------------------------------------------------*/
.global _product_config_commit;
_product_config_commit:
/* DSP4_COMMIT_STAGE bisects this function, because a single write of
 * CONFIG_COMMIT (0xF004) is what kills the part: all 50 data writes
 * before it leave the link perfectly healthy at BOOT_STAGE 5 with blocks
 * still arriving, and this one write stops the core dead -- main loop,
 * 1 kHz timer ISR and all. 0 = neither call, 1 = rx patch only,
 * 2 = both (production). */
#ifndef DSP4_COMMIT_STAGE
#define DSP4_COMMIT_STAGE 2
#endif
#if CHIP_ID == 1
#if DSP4_COMMIT_STAGE >= 1
    call _rx_patch_apply;         /* rebuild RX ptr table from patch regs */
#endif
#endif
#if DSP4_BQ_SELFTEST
    call _bq_selftest;            /* debug: block vs per-sample cascade */
#endif
#if DSP4_COMMIT_STAGE >= 2
    r0 = dm(_product_id);
    call _scope_gates_apply;      /* force-off wrong-product enables */
#endif
    r0 = 1;
    dm(_boot_config_received) = r0;
    /* Config landed. The LED now shows 6 flashes until the first audio
     * block arrives, which separates "the host never configured me"
     * from "I am configured and the audio clock is dead". */
    r0 = DIAG_STAGE_CONFIGED;
    dm(_diag_boot_stage) = r0;
    rts;
_product_config_commit.end:
