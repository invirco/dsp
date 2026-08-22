#!/usr/bin/env python3
"""Add the rev-D mod list to the DSP4 mods markup.

IMPORTANT — this builds ON TOP OF the existing marked-up file, not on the
raw schematic. `D24 DSP mods.pdf` in the _Matrix store is PW's working
document: it already carries MOD A/B (CLKIN level+freq, fitted), MOD C
(SPI_RDY pull), MOD D (JTAG), the !RST_D dual-master note and PW's own
annotations on it. Regenerating from `D24 DSP.pdf` would throw all of
that away. SRC below is the marked-up file for exactly that reason.

Colour convention, inherited from that document — do not invent a third:
    RED   = proposed, NOT yet on hardware
    BLUE  = fitted and scope-verified (and, added here, checked against
            the data sheet and correct, so no change)

Content comes from the single rev-D list, Dropbox
`TransferOnly/PCB mods/dsp4-revD-modlist.md`. Edit the list first; this
script is a view of it. Pin facts come from `MW/D32/DSP/dsp4-pin-audit.md`.

Markup mechanics (see the pdf-schematic-markup note): notes are BAKED into
page content with draw_rect + insert_textbox, never PDF annotations —
annotation text is re-laid-out per viewer and showed as huge empty pink
areas in Peter's viewer while looking fine in a render. Each box is
measured on a scratch page and drawn at exactly that height. These Proteus
print-to-PDF sheets have NO text layer, so every coordinate below was
picked off a rendered grid overlay, not guessed.

Needs PyMuPDF, which is not in the system python here:
    python3 -m venv /tmp/mkvenv && /tmp/mkvenv/bin/pip install PyMuPDF
    /tmp/mkvenv/bin/python rebuild-revd-mods-markup.py
"""
import math
import os

try:
    import pymupdf as fitz
except ImportError:
    import fitz

MODS = os.path.expanduser(
    "~/Stonepower Dropbox/Peter Watts/_Matrix/Products/D24/hw/_mods")
SRC = os.path.join(MODS, "D24 DSP mods.pdf")
OUT = os.path.join(MODS, "D24 DSP mods 2026-08-22.pdf")

RED = (0.75, 0, 0)
RFILL = (1, 0.94, 0.94)
BLUE = (0, 0.25, 0.75)
BFILL = (0.94, 0.96, 1)

doc = fitz.open(SRC)
scratch = doc.new_page(-1, width=1200, height=1200)


def measure_height(width, text, fs):
    r = fitz.Rect(10, 10, 10 + width, 1100)
    leftover = scratch.insert_textbox(r, text, fontsize=fs, fontname="helv")
    return (1100 - 10) - leftover


def note(pno, x0, y0, x1, text, arrows=(), fs=6, colour=RED, fill=RFILL):
    page = doc[pno]
    pad = 3
    h = measure_height((x1 - x0) - 2 * pad, text, fs)
    rect = fitz.Rect(x0, y0, x1, y0 + h + 2 * pad)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=colour, fill=fill, width=1)
    for (sx, sy), (tx, ty) in arrows:
        shape.draw_line(fitz.Point(sx, sy), fitz.Point(tx, ty))
        ang = math.atan2(ty - sy, tx - sx)
        for da in (math.radians(155), -math.radians(155)):
            shape.draw_line(fitz.Point(tx, ty),
                            fitz.Point(tx + 6 * math.cos(ang + da),
                                       ty + 6 * math.sin(ang + da)))
    shape.finish(color=colour, width=0.8)
    shape.commit()
    inner = fitz.Rect(x0 + pad, y0 + pad, x1 - pad, y0 + h + 2 * pad)
    page.insert_textbox(inner, text, fontsize=fs, fontname="helv",
                        color=colour)
    return rect


# ================================================================ page 1
note(0, 900, 20, 1180,
 "REV-D MOD LIST ADDED 2026-08-22. Red = proposed, not yet on hardware. "
 "Blue = fitted and verified, or checked against the data sheet and "
 "correct. Source list: Dropbox TransferOnly/PCB mods/"
 "dsp4-revD-modlist.md (authoritative). Rationale: D8/D10/D14 in "
 "dsp4-architecture-decisions.md. Pin facts: MW/D32/DSP/dsp4-pin-audit.md.")

note(0, 900, 95, 1180,
 "MOD 2 - the Pi runtime parameter link moves off SPI2 to SPI0/SPI1 per "
 "DSP; SPI2 becomes BOOT-ONLY. This frees the Port-A group "
 "(PA_00/01/04/05) that MOD 1 wants for OSPI0/xSPI, and splits the 33R "
 "CK1/CK2 branch.\n"
 "It also settles a polarity clash: boot and runtime share SPI2 today and "
 "DISAGREE on SPI_RDY sense by design - the on-chip boot kernel is fixed "
 "active-LOW, the runtime firmware sets FCPL=1 active-HIGH. MOD 9's "
 "pull-up plus this split is what resolves it.")

note(0, 400, 715, 870,
 "DOC FIX D2 - the 'ADSP21560' labels under the DSPA and DSPB blocks are "
 "stale; the detail sheets U5/U6 correctly say ADSP-21564.\n"
 "DOC FIX D3 - the DSPB left-hand label 'TDM B IN' should read 'BCK B IN', "
 "to pair with 'FS B IN'.")

# ================================================================ page 2
# (45,758) not (45,500): at y=500 the box clipped U1 and the U3 designator
# text. The clean band on this sheet is below the C8-C12 row and left of
# the title block.
note(1, 45, 758, 860,
 "MOD 3 - U3: 5M1270ZT144C4N -> 5M570ZT144C4N. Same TQFP-144 land pattern; "
 "ONE trace moves (the MEMS input off PIN_137, which is not user I/O on "
 "the 570Z). The C4 SPEED GRADE IS MANDATORY: C5 fails timing at 36.9 MHz "
 "against the 49.152 MHz SYSCLK; C4 closes at 51.95 MHz, about 5% margin.\n\n"
 "MOD 4 - hardwiring pass: product-static routing becomes copper and "
 "D24/D32 differences become 0R-strap / BOM variants. Scope is limited to "
 "facts PROVEN at rev-C bring-up. The CPLD keeps clkgen, the Pi PCM "
 "reframer, reset glue and the matrix/UART routing.\n\n"
 "MOD 6 - specify the LOGIC UART/matrix routing matrix (closes "
 "TODO(uart-passthrough)): SRX/MRX and S0-S3/BUSY are multi-drop across "
 "U7/U8/LOGIC/harness, and U9 (74LVC1G157) muxes the SRX source. Rev D "
 "SPECIFIES this - it does not delete it. The matrix is load-bearing for "
 "console control.")

# ================================================================ page 3
# (45,25) not (700,380): at 700,380 the box landed on R67/R68/LD4/LD5.
# The whole top-left quadrant of this sheet is empty.
note(2, 45, 25, 500,
 "MOD 5 - U7: STM32U575RIT6 -> STM32G0B1RET6. Same LQFP-64 land pattern "
 "but an INCOMPATIBLE pinout (no VBAT, merged VDDA, PF2-NRST), so the U7 "
 "region re-routes and all ~45 signals re-map, supplies and decoupling "
 "included. Sizing driver: 6 USART + 2 LPUART covers the serial hub, plus "
 "12 ADC channels for PAD0-11. Firmware ports M33 -> M0+.\n"
 "(U535RET6 would be a zero-effort drop-in, but only if rev C is ever "
 "re-BOMed rather than re-spun.)")

# ==================================== pages 4 and 5, one set per DSP sheet
for pno, blk, rrdy in ((3, "DSPB", "R22"), (4, "DSPA", "R34")):
    r = note(pno, 700, 15, 1180,
     "MOD 12 - LIVENESS SIGNALS. All three are N/C on rev C, confirmed pin "
     "by pin in the 2026-08-22 pin audit:\n"
     "  SYS_CLKOUT (p10) - ADDED 2026-08-22, and it is the valuable one. "
     "With BMODE non-zero the part outputs SYS_CLKIN here as soon as reset "
     "deasserts: no code, no firmware, no JTAG, so power + clock + reset "
     "state are all readable at ONE pad. Rev C brings it nowhere, which is "
     "why this bring-up had to infer liveness from a GPIO pulse train.\n"
     "  SYS_RESOUT (p107) - route to the S MCU or the CPLD as reset-done.\n"
     "  SYS_FAULT (p102) - needs the external pull-up the data sheet "
     "requires (Table 13) if it is used at all. This is the one place the "
     "board contradicts a stated data sheet requirement.\n"
     "CORRECTION to the MOD D note below: the '10K JTG_TRST->GND' is NOT "
     "required. JTG_TRST has an INTERNAL pull-down, present both during "
     "and after reset (Table 13), so floating JTAG already holds the TAP "
     "in reset - the safe state. Fit it only as belt-and-braces on a "
     "populated header. Rev-D list mod 7 is closed for this reason.")

    note(pno, 700, r.y1 + 8, 1180,
     "MOD 1 - xSPI PSRAM on OSPI0, one per DSP. Shares the Port-A pins "
     "with SPI2, which is why MOD 2 moves the runtime link off SPI2. "
     "xSPI_RWDS (p9) and xSPI_SEL2 (p23) are N/C today and the HyperRAM "
     "2.0 option needs RWDS. Voltage gate is answered: OSPI pins are "
     "VDD_EXT 3.3 V, so 1.8 V-only octal parts are excluded.\n"
     "MOD 13 - TEST POINTS. Rev C has none: the only probe points on the "
     "whole clock and boot path are 22R pads on a fitted stack. Rev D: TPs "
     "for +0.9 V, +1V8, +3V3, DSP_CLK at each DSP, SYS_HWRST, SPI2 CLK and "
     "MOSI, and SYS_CLKOUT per MOD 12.\n"
     "MOD 14 - DRAWING ONLY. The CAPS block on this sheet points at a "
     "child sheet (PDF pages 9-10) that is EMPTY. PW confirmed the caps "
     "ARE fitted on the parts, so the board is right and only the drawing "
     "is wrong. Draw the sub-sheets so BOM and schematic agree.")

    note(pno, 20, 700, 700,
     f"CHECKED 2026-08-22 AGAINST DATA SHEET Rev. A - CORRECT, NO CHANGE "
     f"({blk}). SYS_BMODE[2:0] = 0b010 = SPI2 slave boot: BMODE0 (p105) -> "
     f"GND, BMODE1 (p106) -> VDD_EXT, BMODE2 (p82) -> GND, all three "
     f"explicitly strapped, so the two the data sheet says must not float "
     f"do not.  |  SPI2 pin group matches Tables 10/11: PA_00 MISO, PA_01 "
     f"MOSI, PA_04 CLK, PA_05 SEL1 with SPI2_SS on the input tap, all mux "
     f"function 0; PB_05 SPI2_RDY is mux function 1.  |  DAI0/DAI1 pin "
     f"19/20 asymmetry is real and correct: DAI0 19=BCK1 20=FS1, DAI1 "
     f"19=FS3 20=BCK3.  |  Supplies VDD_INT 0.9 V / VDD_EXT 3.3 V / "
     f"VDD_REF 1.8 V all inside the data sheet windows, measured in spec "
     f"2026-08-21.  |  Only SYS_CLKIN0 and SYS_XTAL0 are VDD_INT-domain "
     f"signal pins on the whole part, so MOD A's fault has no twin "
     f"elsewhere on this sheet.\n"
     f"NOTE, not a board fault: the firmware had never written PORTx_FER "
     f"or PORTx_MUX, so SPI2 came up correctly configured and connected to "
     f"no pads at all. Fixed in firmware 2026-08-22.",
     colour=BLUE, fill=BFILL)

# =========================================================== pages 9 & 10
for pno in (8, 9):
    note(pno, 380, 300, 820,
     "DOC FIX D1 / MOD 14 - EMPTY SHEET. This is the CAPS child sheet that "
     "the CAPS block on the DSPA and DSPB pages points at: the supply "
     "decoupling for the two ADSP-21564s (VDD_INT 0V9, VDD_EXT 3V3, "
     "VDD_REF 1V8). The caps ARE fitted on the physical board - PW "
     "confirmed 2026-08-21 - so this is a drawing defect, not a hardware "
     "one, and it was never a suspect in the boot failure. Draw bulk plus "
     "the per-pin 100nF arrays here before rev-D layout, so the BOM and "
     "the schematic agree.", fs=8)

doc.delete_page(doc.page_count - 1)          # drop the measuring scratch page
doc.save(OUT + ".tmp")
doc.close()
os.replace(OUT + ".tmp", OUT)
print("wrote", OUT)
