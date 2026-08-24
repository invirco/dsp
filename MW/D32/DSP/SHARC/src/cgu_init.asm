/*======================================================================
 * cgu_init.asm — raise the core clock. PREPARED, NOT ENABLED.
 *
 * The part runs on CGU reset defaults (decision D10): SYS_CLKIN0
 * 24.576 MHz, MSEL=40, the PLL's built-in /2, CSEL=1, giving CCLK
 * 491.52 MHz. The datasheet rates the ADSP-21564 at 800 MHz
 * (ADSP-21564KSWZ8) or 1 GHz (ADSP-21564KSWZ10), so the part is running
 * at roughly half its rated speed and the whole cycle budget is
 * correspondingly halved.
 *
 * DSP4_CCLK_TARGET selects:
 *      0   leave the reset defaults alone            (DEFAULT)
 *    786   786.432 MHz — legal on BOTH speed grades
 *    983   983.040 MHz — ADSP-21564KSWZ10 ONLY, over spec on a KSWZ8
 *
 * ------------------------------------------------------------------
 * DO NOT ENABLE UNTIL THE PART MARKING ON U5/U6 HAS BEEN READ.
 * 983.04 MHz on a KSWZ8 is out of specification.
 * ------------------------------------------------------------------
 *
 * DIVIDER MATH — and one constraint that defeats the obvious plan.
 *
 * Table 14 requires fCCLK = 2 x fSYSCLK, and fSYSCLK = N x fSCLK0 with
 * **N restricted to 2..6**. That last limit means SCLK0 CANNOT be held at
 * its present 61.44 MHz once CCLK moves: at CCLK 983.04, SYSCLK is pinned
 * at 491.52 and the reachable SCLK0 values are 245.76, 163.84, 122.88,
 * 98.304 and 81.92 — 61.44 needs N=8, which the part does not offer.
 * S0SEL=6 is the closest legal value in both targets.
 *
 *   target      MSEL  CGU0_CTL     CGU0_DIV     CCLK     SYSCLK   SCLK0    SCLK1
 *   today         40  0x00002800   0x05144281   491.520  245.760  61.440   122.880
 *   786.432 MHz   64  0x00004000   0x051442C1   786.432  393.216  65.536   196.608
 *   983.040 MHz   80  0x00005000   0x051442C1   983.040  491.520  81.920   245.760
 *
 * All rows satisfy fPLLCLK 0.40-1.00 GHz (Table 15), fCCLK 400-1000,
 * fSYSCLK 200-500, fSCLK0 30-125, fSCLK1 <= 333.3 and fSYSCLK >= fSCLK1.
 * The CGU0_DIV encoding above was verified by decoding the values D10
 * measured off the running part: 0x05144281 decodes to CSEL=1, SYSSEL=2,
 * S0SEL=4, S1SEL=2, DSEL=20, OSEL=20, exactly as D10 recorded.
 *
 * WHAT MOVES WITH SCLK0, and must be re-derived before first run:
 *   - SPI2, the CM4 parameter link: its baud divider is off SCLK0, so the
 *     divisor must change or the link speed moves by the same ratio.
 *   - Timers: fTMRCLKEXT <= fSCLK0/4.
 *   - The SPORTs are EXTERNALLY clocked by the CPLD, and Table 14 only
 *     requires fSPTCLKEXT <= fSCLK0 (max 62.5 MHz receiving). Raising
 *     SCLK0 is therefore harmless for the audio path -- but note 61.44
 *     was already above that 62.5 MHz receive limit's neighbourhood, so
 *     re-read Table 14 against the actual BCK before trusting this.
 *   - Everything timed in CCLK: DIAG_TPERIOD, the dma_config.c busy-loop
 *     delays, and the profile instrument's cycles-per-tick.
 *
 * ERRATA: the silicon anomaly list (NR004940B, Rev B, March 2025) has
 * thirteen entries and NONE of them concerns the CGU, the PLL or clock
 * switching. Checked 2026-08-24.
 *
 * SEQUENCE: this follows ADI's own power service (adi_pwr_2156x.c, the
 * CGU_CTL path) rather than an invented one -- bypass the PLL, write CTL,
 * un-bypass, wait for clock alignment, then write DIV with UPDT.
 *
 * WHEN TO CALL IT: D10's objection to programming the CGU was a PLL
 * relock with the boot kernel's SPI transfer still in flight. That
 * objection is about WHEN, not whether. This runs after boot is complete
 * and before audio starts.
 *======================================================================*/

#ifndef DSP4_CCLK_TARGET
#define DSP4_CCLK_TARGET 0
#endif

#if DSP4_CCLK_TARGET != 0

#define CGU0_CTL      0x3108D000
#define CGU0_PLLCTL   0x3108D004
#define CGU0_STAT     0x3108D008
#define CGU0_DIV      0x3108D00C

#define PLLCTL_PLLBPST  0x00000001
#define PLLCTL_PLLBPCL  0x00000002
#define STAT_PLLBP      0x00000002
#define STAT_PLOCK      0x00000004
#define STAT_CLKSALGN   0x00000008
#define DIV_UPDT        0x40000000

#if DSP4_CCLK_TARGET == 786
#define NEW_CTL  0x00004000        /* MSEL=64 -> CCLK 786.432 MHz */
#elif DSP4_CCLK_TARGET == 983
#define NEW_CTL  0x00005000        /* MSEL=80 -> CCLK 983.040 MHz */
#else
#error "DSP4_CCLK_TARGET must be 0, 786 or 983"
#endif
#define NEW_DIV  0x051442C1        /* CSEL=1 SYSSEL=2 S0SEL=6 S1SEL=2 */

.section/pm seg_pmco;
.global _cgu_raise_cclk;
_cgu_raise_cclk:
    /* MMRs are reached by absolute address, the same idiom main.asm and
     * diag.asm use for SPI2_STAT -- the i8..i15 DAG set addresses PM, not
     * DM, so it cannot be used for these. */

    /* ---- 1. bypass the PLL ---- */
    r1 = PLLCTL_PLLBPST;
    dm(CGU0_PLLCTL) = r1;
.cgu_wait_bp:
    r1 = dm(CGU0_STAT);
    r2 = STAT_PLLBP;
    r1 = r1 and r2;
    r1 = pass r1;
    if eq jump (pc, .cgu_wait_bp);

    /* ---- 2. new MSEL, while bypassed ---- */
    r1 = NEW_CTL;
    dm(CGU0_CTL) = r1;
    nop;
    nop;
    nop;
    nop;

    /* ---- 3. release the bypass and let the PLL relock ---- */
    r1 = PLLCTL_PLLBPCL;
    dm(CGU0_PLLCTL) = r1;
.cgu_wait_nobp:
    r1 = dm(CGU0_STAT);
    r2 = STAT_PLLBP;
    r1 = r1 and r2;
    r1 = pass r1;
    if ne jump (pc, .cgu_wait_nobp);

    /* ---- 4. wait for the clocks to realign ---- */
.cgu_wait_algn:
    r1 = dm(CGU0_STAT);
    r2 = STAT_CLKSALGN;
    r1 = r1 and r2;
    r1 = pass r1;
    if ne jump (pc, .cgu_wait_algn);

    /* ---- 5. new dividers, with UPDT ---- */
    r1 = NEW_DIV;
    r2 = DIV_UPDT;
    r1 = r1 or r2;
    dm(CGU0_DIV) = r1;
    nop;
    nop;
.cgu_wait_updt:
    r1 = dm(CGU0_DIV);
    r2 = DIV_UPDT;
    r1 = r1 and r2;
    r1 = pass r1;
    if eq jump (pc, .cgu_wait_updt);

.cgu_wait_algn2:
    r1 = dm(CGU0_STAT);
    r2 = STAT_CLKSALGN;
    r1 = r1 and r2;
    r1 = pass r1;
    if ne jump (pc, .cgu_wait_algn2);
    rts;
_cgu_raise_cclk.end:

#endif /* DSP4_CCLK_TARGET */
