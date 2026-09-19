/*======================================================================
 * extram.asm — xSPI0 / HyperBus external RAM layer for the ADSP-21564.
 *
 * WHAT THIS IS FOR
 *
 * PW ruling 2026-09-19 evening: "dsp ram is required, but needs to work
 * without it until dsp board modified -- code it in place." One 64 Mbit
 * 3.0 V HyperRAM per ADSP-21564 on xSPI0 is the bulk store the delay
 * lines want (D8, dsp4-architecture-decisions.md). The part is NOT on
 * the rev C board. Everything here is therefore gated on DSP4_EXTRAM and
 * the pool above it (lib/mem_pool.asm) falls back to the L2 layout that
 * ships today -- byte for byte -- when the flag is off or the probe
 * comes back empty.
 *
 * THE TRANSPORT, AND WHY IT IS NOT THE xSPI's OWN DMA
 *
 * The xSPI controller (Cadence xSPI/OSPI IP at 0x31070000) exposes the
 * device three ways: STIG command registers (CMD0..CMD5), its own SDMA,
 * and the DAC -- a DIRECT ACCESS memory window. The datasheet's Table 5
 * maps SPI1/SPI2/xSPI0 memory at byte address 0x60000000-0x6FFFFFFF, so
 * once the controller is in DAC/HyperBus mode the RAM is ordinary system
 * memory to every requester on the fabric, the MDMA channels included.
 *
 * So the block staging is plain MDMA -- the same DDE this firmware
 * already drives for the SPORT rings -- and not a second, unfamiliar DMA
 * engine. MDMA0 (DMA8 src / DMA9 dst, 0x310A7000) is free: dma_config.c
 * uses DMA0..7 and DMA10..17 for the SPORTs and nothing else claims an
 * MDMA pair.
 *
 * REGISTER-BASED ARMING, NOT DESCRIPTOR LISTS. dma_config.c records, at
 * length, that descriptor-list arming has never worked on this part --
 * ERRC = 3 the moment CFG is written, for lists this firmware built and
 * for a self-referencing descriptor built word by word in the probe. The
 * rings are armed in AUTOBUFFER flow instead. This module obeys the same
 * finding: every transfer is programmed straight into the channel
 * registers in STOP flow. That costs six MMR writes a transfer and buys
 * a path that is known to work on this silicon.
 *
 * THE CLOCK, FROM THE DATASHEET AND NOT FROM A HABIT
 *
 * ADSP-21560/21561/21564/21568 Rev. A (Feb 2026) Table 14:
 *     fxSPICLKPROG, with data training and WITHOUT DQS      125    MHz
 *     fxSPICLKPROG, with data training and WITH DQS         166.66 MHz
 *     (footnote 5: with the offline PHY training methodology, 80 MHz
 *      without DQS and 125 MHz with DQS)
 * HyperBus drives RWDS as the read strobe, which is the DQS case, so the
 * SILICON allows 166.66 MHz (125 MHz if the PHY is trained offline).
 *
 * THE RAM IS THE BINDING LIMIT, NOT THE DSP. VDD_EXT on this part is
 * 3.13-3.47 V with no 1.8 V option (Table 13), so the RAM must be a
 * 3.0 V HyperRAM, and the 3.0 V members of both candidate families are
 * the 100 MHz grades. 100 MHz DDR octal = 200 MB/s raw. See the S75
 * report for the part-number discrepancy this raises.
 *
 * XSPI_CLK_MHZ below is therefore 100, and the divider is derived from
 * the CDU_CLKO10 root the datasheet names (fxSPICLKPROG = fCDU_CLKO10).
 *
 * WHAT IS NOT PROVEN HERE
 *
 * Not one instruction in this file has been executed on silicon: the
 * rev C board has no RAM and the S75 session was desk-only and
 * read-only. The register sequence follows the datasheet, the CCES MMR
 * map (sys/ADSP-21564W.h) and the HyperBus protocol; the PHY training
 * values are the reset defaults and WILL need a trained DLL on real
 * hardware. Every entry point is bounded -- no unbounded spin -- so a
 * part that never answers falls back rather than hanging, which is the
 * property the fallback depends on. See MW/D24/DSP/s75/extram-pool.md
 * for the bench check that closes this out.
 *======================================================================*/

#ifndef DSP4_EXTRAM
#define DSP4_EXTRAM 0
#endif

#if DSP4_EXTRAM

#include "dsp_block.h"

/* ---- xSPI controller MMRs (sys/ADSP-21564W.h) ---------------------- */
#define XSPI_CMD0               0x31070000
#define XSPI_CMD1               0x31070004
#define XSPI_CMD2               0x31070008
#define XSPI_CMD3               0x3107000C
#define XSPI_CMD4               0x31070010
#define XSPI_CMD5               0x31070014
#define XSPI_CMD_STAT_PTR       0x31070040
#define XSPI_CMD_STAT           0x31070044
#define XSPI_GSTAT              0x31070100
#define XSPI_ISTAT              0x31070110
#define XSPI_INT_EN             0x31070114
#define XSPI_WORKMODE_CTL       0x31070230
#define XSPI_DMA_CTL            0x3107023C
#define XSPI_DAC_CFG            0x31070398
#define XSPI_DAC_REMAPADDR0     0x3107039C
#define XSPI_SEQ_GCTL0          0x31070390
#define XSPI_SEQ_GCTL1          0x31070394
#define XSPI_MINICTL_CLKMODE    0x31071008
#define XSPI_MINICTL_DEV_DLY    0x31071010
#define XSPI_MINICTL_DEV_ACT_MAX 0x31071018
#define XSPI_PHY_DLL_CTL        0x31071034
#define XSPI_PHY_DQ_TR          0x31072000
#define XSPI_PHY_DQS_TR         0x31072004
#define XSPI_PHY_GATE_LPBK_CTL  0x31072008
#define XSPI_PHY_DLL_MSTR_CTL   0x3107200C
#define XSPI_PHY_DLL_SLAVE_CTL  0x31072010

#define XSPI_GSTAT_INIT_PASS    0x00010000
#define XSPI_GSTAT_INIT_FAIL    0x00000300
#define XSPI_GSTAT_CTL_BUSY     0x00000080
#define XSPI_ISTAT_STIG_DONE    0x00800000
#define XSPI_ISTAT_CTL_IDLE     0x00010000
#define XSPI_ISTAT_ERRS         0x1F100000  /* DIR_* errors + CMD_IGNORED */

/* ---- pad / pin mux -------------------------------------------------
 * Octal HyperBus needs ELEVEN signals and on this package they are:
 *   xSPI0_CLK, SEL1, MISO/D1, MOSI/D0, D2..D7  -> PA_00..PA_09
 *   xSPI0_RWDS                                  -> a dedicated lead (9)
 * Datasheet Table 10 (Port A multiplexing) and the 120-lead assignment
 * table: leads 14,15,16,18,19,20,21,25,26,27 are PA_00..PA_09 and lead 9
 * is xSPI_RWDS -- which is exactly the mod sheet's "Port A leads 14-27,
 * RWDS lead 9, SEL1 = CS#".
 *
 * PA_00/01/04/05 are SPI2 at mux function 0 and xSPI0 at function 1;
 * PA_06..09 are SPI0 at function 0 and xSPI0 at function 2. THIS TAKES
 * BOTH SPI2 AND SPI0 AWAY. SPI2 is today's Pi parameter link AND the
 * slave-boot port. See finding S75-1: bringing xSPI0 up on a modded card
 * costs the control link unless it has already moved to SPI1. */
#define PORTA_MUX               0x31004010
#define PORTA_FER               0x31004000
#define PORTA_FER_SET           0x31004004
#define PADS_PCFG0              0x31004404

#define XSPI_PADS_PEN           0x00700000  /* CLKb | SEL2b | RWDS pin enable */

/* PA_00..PA_05 -> function 1 (01b), PA_06..PA_09 -> function 2 (10b).
 * MUX is two bits per pin: pin n occupies bits [2n+1:2n]. */
#define PORTA_MUX_XSPI          0x000AA555
#define PORTA_FER_XSPI          0x000003FF  /* PA_00..PA_09 peripheral */

/* ---- MDMA0: DMA8 = source, DMA9 = destination ---------------------- */
#define MDMA_SRC_BASE           0x310A7000
#define MDMA_DST_BASE           0x310A7080
#define MDMA_OFF_ADDR           0x04
#define MDMA_OFF_CFG            0x08
#define MDMA_OFF_XCNT           0x0C
#define MDMA_OFF_XMOD           0x10
#define MDMA_OFF_YCNT           0x14
#define MDMA_OFF_YMOD           0x18
#define MDMA_OFF_STAT           0x30

#define MDMA_SRC_ADDR           (MDMA_SRC_BASE + MDMA_OFF_ADDR)
#define MDMA_SRC_CFG            (MDMA_SRC_BASE + MDMA_OFF_CFG)
#define MDMA_SRC_XCNT           (MDMA_SRC_BASE + MDMA_OFF_XCNT)
#define MDMA_SRC_XMOD           (MDMA_SRC_BASE + MDMA_OFF_XMOD)
#define MDMA_SRC_YCNT           (MDMA_SRC_BASE + MDMA_OFF_YCNT)
#define MDMA_SRC_YMOD           (MDMA_SRC_BASE + MDMA_OFF_YMOD)
#define MDMA_SRC_STAT           (MDMA_SRC_BASE + MDMA_OFF_STAT)
#define MDMA_DST_ADDR           (MDMA_DST_BASE + MDMA_OFF_ADDR)
#define MDMA_DST_CFG            (MDMA_DST_BASE + MDMA_OFF_CFG)
#define MDMA_DST_XCNT           (MDMA_DST_BASE + MDMA_OFF_XCNT)
#define MDMA_DST_XMOD           (MDMA_DST_BASE + MDMA_OFF_XMOD)
#define MDMA_DST_YCNT           (MDMA_DST_BASE + MDMA_OFF_YCNT)
#define MDMA_DST_YMOD           (MDMA_DST_BASE + MDMA_OFF_YMOD)
#define MDMA_DST_STAT           (MDMA_DST_BASE + MDMA_OFF_STAT)

/* STOP flow, 32-bit words, MSIZE 4 bytes, no interrupt. The pool polls;
 * it has two whole blocks of slack and an interrupt per transfer at
 * 53 transfers a block would be a 159 kHz ISR for no benefit. */
#define MDMA_CFG_RD1D           0x00000221  /* EN, READ,  PSIZE04 MSIZE04 */
#define MDMA_CFG_WR1D           0x00000223  /* EN, WRITE, PSIZE04 MSIZE04 */
#define MDMA_CFG_RD2D           0x04000221  /* + TWOD */
#define MDMA_CFG_WR2D           0x04000223
#define MDMA_STAT_RUN           0x00000700  /* RUN field, non-zero = busy */

/* The external window. Table 5: xSPI0 memory, byte address space. */
#define EXTRAM_BASE             0x60000000
#define EXTRAM_BYTES            0x00800000  /* 64 Mbit = 8 MB */

/* ---- HyperBus command/address ---------------------------------------
 * A HyperBus transaction opens with a 48-bit CA word, MSB first:
 *   CA[47] = 1 read / 0 write
 *   CA[46] = 1 register space / 0 memory space
 *   CA[45] = 1 linear burst / 0 wrapped
 *   CA[44:16] = address[31:3], CA[15:3] reserved 0, CA[2:0] = address[2:0]
 * The ID registers live in register space at word address 0 (ID0) and
 * 1 (ID1). The STIG path sends the CA through CMD0..CMD5 and reads the
 * returned word out of CMD_STAT. */
#define HB_CA_RD_REG_HI         0xE0000000  /* read | register | linear */

/* Bounded-timeout limits. 1,048,576 iterations of a four-instruction
 * poll is ~8 ms at 491.52 MHz and ~4 ms at 983.04 MHz -- four orders of
 * magnitude above any legitimate STIG completion, so an expiry is never
 * a false alarm; it means no device answered. The MDMA limit is tighter
 * because it is polled inside the audio block. */
#define XSPI_STIG_LIMIT         0x00100000
#define XSPI_INIT_LIMIT         0x00100000

/* ---- state ---------------------------------------------------------- */
.section/dm seg_dmda;

/* 1 = a device answered the probe and passed the pattern test. This is
 * the ONE word the pool reads; everything else here is evidence. */
.global _extram_present;
.var _extram_present = 0;

/* Raw ID register reads, published so the bench can see WHICH part is
 * fitted rather than only that one is. 0xFFFFFFFF = the bus floated. */
.global _extram_id0;
.var _extram_id0 = 0;
.global _extram_id1;
.var _extram_id1 = 0;

/* Why the probe said no. 0 = present. See diag.h DIAG_EXTRAM_STAT. */
.global _extram_fail;
.var _extram_fail = 0;
#define EXF_NONE        0
#define EXF_CTL_INIT    1   /* controller never reported INIT_PASS */
#define EXF_STIG_TMO    2   /* a STIG command never completed */
#define EXF_ID_FLOAT    3   /* ID read all-ones or all-zeros: no device */
#define EXF_PATTERN     4   /* ID plausible, array write/read-back wrong */
#define EXF_FORCED_OFF  5   /* product config forced the L2 backend */

/* Pattern-test scratch, and the two addresses it uses. Two addresses a
 * long way apart catch a floating bus that happens to hold the pattern
 * and an aliasing window that is smaller than it claims. */
.var _extram_pat_rb0 = 0;
.var _extram_pat_rb1 = 0;

/* Transfers issued / completed, free-running. The bench reads the pair
 * to see the staging actually running rather than merely configured. */
.global _extram_xfers;
.var _extram_xfers = 0;
.global _extram_stalls;
.var _extram_stalls = 0;


.section/pm seg_pmco;

/*----------------------------------------------------------------------
 * _extram_init — pads, controller, PHY. Leaves the DAC window live.
 *
 * Out: nothing. _extram_fail is set if the controller never came up;
 *      _extram_probe is the thing that decides presence.
 * Clobbers: r0-r4.
 *
 * ORDERING MATTERS AND IS NOT OBVIOUS. The pads move to xSPI0 FIRST,
 * which is the instant SPI2 stops being connected to anything. On a card
 * whose parameter link is still on SPI2 that is the end of host control,
 * so main.asm calls this only when the product configuration has already
 * said the card is modded (see CFG_EXTRAM) -- never speculatively.
 *--------------------------------------------------------------------*/
.global _extram_init;
_extram_init:
    /* 1. dedicated pins (RWDS, SEL2b, CLKb) out of their default
     *    three-state, then Port A to the xSPI0 mux function. */
    r0 = dm(PADS_PCFG0);
    r1 = XSPI_PADS_PEN;
    r0 = r0 or r1;
    dm(PADS_PCFG0) = r0;

    r0 = PORTA_MUX_XSPI;
    dm(PORTA_MUX) = r0;
    r0 = PORTA_FER_XSPI;
    dm(PORTA_FER_SET) = r0;

    /* 2. clock mode 0 (CPOL=0/CPHA=0, what HyperBus wants) and the chip
     *    select start/end/deassert delays. CSSOT/CSEOT of 2 xSPI clocks
     *    and a minimum deassertion of 4 covers the HyperRAM tCSHI. */
    r0 = 0;
    dm(XSPI_MINICTL_CLKMODE) = r0;
    r0 = 0x04000202;
    dm(XSPI_MINICTL_DEV_DLY) = r0;

    /* 3. tCSM -- the HyperRAM's maximum CS# low time, which exists
     *    because distributed refresh only runs between transactions.
     *    The 3.0 V parts specify 4 us; at 100 MHz that is 400 clocks.
     *    Programming it here means the CONTROLLER breaks a burst that
     *    would violate it, rather than the RAM losing data silently.
     *    Every transfer this module issues is far shorter (a 128-byte
     *    read is ~84 clocks), so it never fires in normal running -- it
     *    is the guard, not the mechanism. */
    r0 = 400;
    dm(XSPI_MINICTL_DEV_ACT_MAX) = r0;

    /* 4. DAC: bank 0, RWDS byte-mask capture on (HyperBus masks write
     *    bytes with RWDS), no address remap -- the device is mapped
     *    1:1 at EXTRAM_BASE and is smaller than the window. */
    r0 = 0x00000010;            /* RWDS_CAP_EN, DAC_BNK_NUM = 0 */
    dm(XSPI_DAC_CFG) = r0;

    /* 5. PHY: reset defaults, DLL in bypass. A HyperBus read is strobed
     *    by RWDS, so the gate/loopback path is what carries it.
     *    THESE ARE NOT TRAINED VALUES. On silicon the DLL master/slave
     *    delays must be swept against a known pattern at temperature --
     *    the datasheet's "with data training" is doing real work in the
     *    166.66 MHz number. At 100 MHz with DQS the reset defaults are
     *    the starting point and the bench check says so. */
    r0 = 0;
    dm(XSPI_PHY_DLL_CTL) = r0;
    dm(XSPI_PHY_GATE_LPBK_CTL) = r0;

    /* 6. controller work mode: normal operation, stop on error. */
    r0 = 0x00000008;            /* ON_ERR = 1, WORKMODE = 0 */
    dm(XSPI_WORKMODE_CTL) = r0;

    /* 7. wait, BOUNDED, for the controller to report initialisation
     *    complete. A controller that never does is EXF_CTL_INIT and the
     *    pool stays on L2. */
    r3 = XSPI_INIT_LIMIT;
.exi_wait:
    r0 = dm(XSPI_GSTAT);
    r1 = XSPI_GSTAT_INIT_PASS;
    r1 = r0 and r1;
    r1 = pass r1;
    if ne jump (pc, .exi_ok);
    r3 = r3 - 1;
    if ne jump (pc, .exi_wait);
    r0 = EXF_CTL_INIT;
    dm(_extram_fail) = r0;
    rts;
.exi_ok:
    rts;
_extram_init.end:


/*----------------------------------------------------------------------
 * _extram_stig — one STIG command, bounded.
 *
 * In:  r0 = CMD0 value (CA[47:16]), r1 = CMD1 value (CA[15:0] + flags)
 * Out: r0 = returned word, r1 = 0 on success / 1 on timeout
 * Clobbers: r2-r4.
 *--------------------------------------------------------------------*/
_extram_stig:
    dm(XSPI_CMD0) = r0;
    dm(XSPI_CMD1) = r1;
    r2 = XSPI_ISTAT_STIG_DONE;
    dm(XSPI_ISTAT) = r2;        /* W1C the previous completion */
    r2 = 1;
    dm(XSPI_CMD5) = r2;         /* execute */

    r3 = XSPI_STIG_LIMIT;
.exs_wait:
    r2 = dm(XSPI_ISTAT);
    r4 = XSPI_ISTAT_STIG_DONE;
    r4 = r2 and r4;
    r4 = pass r4;
    if ne jump (pc, .exs_done);
    r3 = r3 - 1;
    if ne jump (pc, .exs_wait);
    r0 = 0;
    r1 = 1;
    rts;
.exs_done:
    r0 = dm(XSPI_CMD_STAT);
    r1 = 0;
    rts;
_extram_stig.end:


/*----------------------------------------------------------------------
 * _extram_probe — is there a HyperRAM on this card?
 *
 * Out: r0 = 1 present, 0 absent. _extram_present set to the same.
 * Clobbers: r0-r8, i0.
 *
 * TWO TESTS, AND WHY BOTH.
 *
 * (a) The ID registers. HyperBus register space word 0 and 1 carry the
 *     Manufacturer / Device ID. This is the test the dispatch asked for
 *     and it is the one that identifies the part -- but the ID ENCODING
 *     DIFFERS BETWEEN THE TWO CANDIDATE FAMILIES, so accepting a
 *     specific value would reject the other vendor's part. What is
 *     checked here is only that the bus did not float: an all-ones or
 *     all-zeros read is no device. The raw words are published for the
 *     bench to identify.
 *
 * (b) A write / read-back pattern at two widely separated array
 *     addresses. This is the vendor-independent gate and it is the one
 *     the pool's decision actually hangs on. It also catches the case
 *     the ID test cannot: a device that answers register space and has
 *     no working array (unconfigured latency, untrained PHY, a
 *     half-soldered data lane).
 *
 * The array is written before the pool has laid anything out in it, so
 * the two words this dirties are of no consequence.
 *--------------------------------------------------------------------*/
.global _extram_probe;
_extram_probe:
    r8 = 0;
    dm(_extram_present) = r8;

    /* Already failed in init? Do not touch the bus. */
    r0 = dm(_extram_fail);
    r0 = pass r0;
    if ne jump (pc, .exp_absent);

    /* ---- (a) ID0 at register-space word 0 ---- */
    r0 = HB_CA_RD_REG_HI;
    r1 = 0;
    call _extram_stig;
    r2 = pass r1;
    if ne jump (pc, .exp_tmo);
    dm(_extram_id0) = r0;
    r7 = r0;

    /* ---- ID1 at register-space word 1 ---- */
    r0 = HB_CA_RD_REG_HI;
    r1 = 1;
    call _extram_stig;
    r2 = pass r1;
    if ne jump (pc, .exp_tmo);
    dm(_extram_id1) = r0;

    /* Floated bus? Both all-ones or both all-zeros. */
    r0 = dm(_extram_id0);
    r1 = dm(_extram_id1);
    r2 = r0 or r1;
    r2 = pass r2;
    if eq jump (pc, .exp_float);
    r2 = r0 and r1;
    r3 = -1;
    comp(r2, r3);
    if eq jump (pc, .exp_float);

    /* ---- (b) pattern at the first and last usable array words ---- */
    r0 = EXTRAM_BASE;
    i0 = r0;
    r1 = 0xA5C35A3C;
    dm(i0, 0) = r1;

    r0 = EXTRAM_BASE + EXTRAM_BYTES - 4;
    i0 = r0;
    r2 = 0x5A3CA5C3;
    dm(i0, 0) = r2;

    /* Read them BACK IN THE OTHER ORDER. A read-back that immediately
     * follows its own write can be served by a write buffer and prove
     * nothing; reading the far address first forces the near one out. */
    r0 = EXTRAM_BASE + EXTRAM_BYTES - 4;
    i0 = r0;
    r4 = dm(i0, 0);
    dm(_extram_pat_rb1) = r4;
    r0 = EXTRAM_BASE;
    i0 = r0;
    r3 = dm(i0, 0);
    dm(_extram_pat_rb0) = r3;

    r5 = 0xA5C35A3C;
    comp(r3, r5);
    if ne jump (pc, .exp_pattern);
    r5 = 0x5A3CA5C3;
    comp(r4, r5);
    if ne jump (pc, .exp_pattern);

    /* Present. */
    r0 = 1;
    dm(_extram_present) = r0;
    r1 = EXF_NONE;
    dm(_extram_fail) = r1;
    rts;

.exp_tmo:
    r0 = EXF_STIG_TMO;
    dm(_extram_fail) = r0;
    jump (pc, .exp_absent);
.exp_float:
    r0 = EXF_ID_FLOAT;
    dm(_extram_fail) = r0;
    jump (pc, .exp_absent);
.exp_pattern:
    r0 = EXF_PATTERN;
    dm(_extram_fail) = r0;
.exp_absent:
    r0 = 0;
    dm(_extram_present) = r0;
    rts;
_extram_probe.end:


/*----------------------------------------------------------------------
 * _extram_mdma_busy — is MDMA0 still running?
 * Out: r0 = non-zero if busy.
 * Clobbers: r0, r1.
 *--------------------------------------------------------------------*/
.global _extram_mdma_busy;
_extram_mdma_busy:
    r0 = dm(MDMA_DST_STAT);
    r1 = MDMA_STAT_RUN;
    r0 = r0 and r1;
    rts;
_extram_mdma_busy.end:


/*----------------------------------------------------------------------
 * _extram_mdma_1d — arm a one-dimensional MDMA0 transfer.
 *
 * In:  r0 = source byte address
 *      r1 = destination byte address
 *      r2 = word count (32-bit words)
 * Out: nothing; the transfer runs to completion on its own.
 * Clobbers: r3.
 *
 * The caller has already established the channel is idle. Six MMR
 * writes; all posted, so the core does not stall on them.
 *--------------------------------------------------------------------*/
.global _extram_mdma_1d;
_extram_mdma_1d:
    dm(MDMA_SRC_ADDR) = r0;
    dm(MDMA_SRC_XCNT) = r2;
    r3 = 4;
    dm(MDMA_SRC_XMOD) = r3;
    dm(MDMA_DST_ADDR) = r1;
    dm(MDMA_DST_XCNT) = r2;
    dm(MDMA_DST_XMOD) = r3;
    /* Destination is armed before the source: the DST channel is the one
     * that drives completion, and a source that starts filling a FIFO no
     * destination is draining is the one ordering that can overrun. */
    r3 = MDMA_CFG_WR1D;
    dm(MDMA_DST_CFG) = r3;
    r3 = MDMA_CFG_RD1D;
    dm(MDMA_SRC_CFG) = r3;
    r3 = dm(_extram_xfers);
    r3 = r3 + 1;
    dm(_extram_xfers) = r3;
    rts;
_extram_mdma_1d.end:


/*----------------------------------------------------------------------
 * _extram_mdma_2d_src — arm a transfer whose SOURCE is two dimensional.
 *
 * In:  r0 = source byte address
 *      r1 = destination byte address (linear)
 *      r2 = X word count per row
 *      r3 = Y row count
 *      r4 = Y byte stride between rows
 *
 * This is the read-ahead shape: the pool's history store is laid out
 * hist[slot][line][BLOCK], so one line's window across two consecutive
 * slots is two rows of BLOCK words separated by the whole line stride.
 * One transfer, two rows, instead of two transfers.
 * Clobbers: r5.
 *--------------------------------------------------------------------*/
.global _extram_mdma_2d_src;
_extram_mdma_2d_src:
    dm(MDMA_SRC_ADDR) = r0;
    dm(MDMA_SRC_XCNT) = r2;
    r5 = 4;
    dm(MDMA_SRC_XMOD) = r5;
    dm(MDMA_SRC_YCNT) = r3;
    dm(MDMA_SRC_YMOD) = r4;

    r5 = r2 * r3 (ssi);
    dm(MDMA_DST_ADDR) = r1;
    dm(MDMA_DST_XCNT) = r5;
    r5 = 4;
    dm(MDMA_DST_XMOD) = r5;

    r5 = MDMA_CFG_WR1D;
    dm(MDMA_DST_CFG) = r5;
    r5 = MDMA_CFG_RD2D;
    dm(MDMA_SRC_CFG) = r5;
    r5 = dm(_extram_xfers);
    r5 = r5 + 1;
    dm(_extram_xfers) = r5;
    rts;
_extram_mdma_2d_src.end:

#endif /* DSP4_EXTRAM */
