import fitz, os, math
SRC = "/home/peter/dsp/MW/D24/HW/schematics/D24 DSP.pdf"
OUT = "/home/peter/dsp/MW/D24/HW/schematics/D24 DSP rev C - review markup 2026-07-30.pdf"
RED = (0.75, 0, 0); FILL = (1, 0.94, 0.94)
doc = fitz.open(SRC)

# scratch page for measuring text height (deleted before save)
scratch = doc.new_page(-1, width=1200, height=1200)

def measure_height(width, text, fs):
    r = fitz.Rect(10, 10, 10 + width, 1100)
    leftover = scratch.insert_textbox(r, text, fontsize=fs, fontname="helv")
    return (1100 - 10) - leftover

def note(pno, x0, y0, x1, text, arrows=(), fs=6.5):
    page = doc[pno]
    pad = 3
    h = measure_height((x1 - x0) - 2 * pad, text, fs)
    rect = fitz.Rect(x0, y0, x1, y0 + h + 2 * pad)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=RED, fill=FILL, width=1)
    for (sx, sy), (tx, ty) in arrows:
        shape.draw_line(fitz.Point(sx, sy), fitz.Point(tx, ty))
        ang = math.atan2(ty - sy, tx - sx)
        for da in (math.radians(155), -math.radians(155)):
            shape.draw_line(fitz.Point(tx, ty),
                            fitz.Point(tx + 6 * math.cos(ang + da),
                                       ty + 6 * math.sin(ang + da)))
    shape.finish(color=RED, width=0.8)
    shape.commit()
    inner = fitz.Rect(x0 + pad, y0 + pad, x1 - pad, y0 + h + 2 * pad)
    page.insert_textbox(inner, text, fontsize=fs, fontname="helv", color=RED)
    return rect

# ---------- Page 1 (ROOT) ----------
note(0, 845, 95, 1130,
 "REVIEW: Block labels 'ADSP21560' (below DSPA and DSPB blocks) are stale - "
 "detail sheets U5/U6 correctly say ADSP-21564. Update in rev D. Also DSPB "
 "left label 'TDM B IN' should read 'BCK B IN' (pairs with FS B IN).", fs=6)
note(0, 940, 175, 1185,
 "ANALOG RESOLUTION - DSPA (U6) INPUTS (left side of block)\n"
 "I0/I1/I2 = AD0/1/2: mic/line ch 1-24 from the three ADC8 blocks on D24 "
 "Analog rev B (TDM8 via FPC J41/J58, C1/L0 clock pair).\n"
 "I3 = AD3: NO ADC on D24 Analog - net driven only via D32_COMPAT J33 / "
 "LOGIC NET mux ('ADC/NET 25-32' is network-only on D24).\n"
 "I4 CODEC = AK4916 CODEC4 on ANALOG board (talkback XLR + aux in) -> "
 "CDC_O on PLL8_0.\n"
 "I7 MEMS = surface MEMS mics on switch panels -> LVDS (J12/J13) -> "
 "ADAU7302 on Digital bd -> M_BCK/M_FS/M_I2S (PLL7 grp).\n"
 "I5 snake / I6 Pi PCM: digital only.", fs=6)
note(0, 470, 390, 720,
 "CROSS-BOARD NOTES (D24 Digital rev C + D24 Analog rev B):\n"
 "- Converter clocks = C1 (TDM8 BCK 12.288M) + L0 (FS 48k), LOGIC-"
 "generated, 33R series on Digital (R111/R112), re-buffered by LVC1G17 "
 "(U97/U98) on Analog.\n"
 "- VERIFY: hardware-map says FPC J41/J42 carry PLL3-6 clock groups; "
 "Analog rev B J58/J59 pinouts name only C1/L0 + AD/DA/CDC. Confirm FPC "
 "pin alignment (PLL3-6 possibly unused on D24).\n"
 "- Converter + mic-gain SPI = Pi SPI0 branch (R109 on Digital) with "
 "CS_C/CS_M via ADC FPC; mic gain via SHIFT daisy-chain on Analog bd.\n"
 "- hardware-map.md CORRECTION: AK4916 is NOT on the DSP card - it is "
 "the AUX_IO 'CODEC4' on the Analog PCBA (PLL8 net naming unchanged).", fs=6)
note(0, 960, 485, 1187,
 "ANALOG RESOLUTION - DSPB (U5) OUTPUTS (right side of block)\n"
 "O0 = DA0 -> DAC8 OUT_1-8 (line outs 1-8) via FPC J42/J59.\n"
 "O1 'DAC 9-16': physical DAC data line is DA3 (OUT_9-16 block input = "
 "DA3). DA1 dead-ends at Digital J18 (spare) - LOGIC must route O1 -> DA3.\n"
 "O2 = CDC_I -> AK4916 codec DAC: talkback speaker feed (SPKR -> TS482 amp "
 "on Digital -> panels) + aux out.\n"
 "O3 'DAC MAIN': NO sink found on D24 Analog rev B (phones amps are fed "
 "analog diff pairs) - VERIFY intended target.\n"
 "O4-O7 = NET to option cards; DA2 -> D32_COMPAT J33 only: digital.", fs=6)

# ---------- Page 2 (LOGIC) ----------
note(1, 850, 5, 1185,
 "ANALOG BOUNDARY at J1/J2 (X LOGIC IO): AD0-2 = mic ch 1-24 (TDM8 from "
 "ADC8s); AD3 = D32-compat/NET only; DA0 = line outs 1-8; DA3 = outs "
 "9-16; DA1 spare (dead-end on Digital); DA2 = D32_COMPAT. C1/L0 = "
 "converter BCK/FS pair. All other audio nets here (NI/NO, PCM, MEMS/M_*, "
 "PLL1-2) resolve to digital sources only.", fs=6)
note(1, 1015, 648, 1187,
 "NOTE (SPI-RAM): U2 1117-1V8 feeds CPLD VCCINT + DSP VDD_REF. Adding "
 "1.8V octal PSRAMs: budget ~50-100mA each here, or use 3V PSRAM if "
 "xSPI I/O runs on VDD_EXT 3V3.",
 arrows=[((1015, 660), (905, 565))], fs=6)
note(1, 470, 752, 870,
 "CORRECTION: AK4916 'CODEC4' lives on the ANALOG board (AUX_IO block: "
 "talkback XLR, aux in, SPKR out) - these stubs are net aliases only. "
 "PLL8_0 = CDC_O -> DSPA I4 (codec return); PLL8_1 = CDC_I <- DSPB O2. "
 "Update hardware-map.md ('AK4916 codec on DSP card' is wrong).",
 arrows=[((790, 752), (922, 670))], fs=6)

# ---------- Page 4 (DSPB, U5) ----------
note(3, 45, 470, 315,
 "REVIEW / SPI-RAM option: xSPI_RWDS (p9) and xSPI_SEL2 (p23) are NC and "
 "PA_02/03/06/07/08/09/10 are free, so an octal xSPI PSRAM is pin-feasible "
 "on this package. BUT OSPI0 shares the SPI2 / Port-A pin group: the Pi "
 "link already occupies PA_00/01/04/05 (SPI2 MISO/MOSI/CLK/SEL). Next rev: "
 "route Pi RUNTIME param link via SPI0/SPI1 and keep SPI2 for slave boot "
 "only; verify exact OSPI pin mux + OSPI I/O voltage domain on LQFP "
 "(VDD_EXT=3V3 here; 133-200MHz octal PSRAMs are 1.8V - may need 3V-capable "
 "PSRAM variant).",
 arrows=[((300, 470), (306, 334)), ((300, 500), (306, 411))], fs=6)
note(3, 400, 32, 785,
 "OK: SYS_BMODE[2:0] strapped 0b010 (BMODE2=GND p82, BMODE1=VDD_EXT p106, "
 "BMODE0=GND p105) = SPI2 slave boot, matches decision D1 (Pi masters boot). "
 "VERIFY: JTG_TRST (p103) appears floating - H1S2 JTAG header carries only "
 "TCK/TDO/TDI/TMS. Confirm internal pull, else add 10K to GND.",
 arrows=[((500, 78), (500, 152))], fs=6.5)
note(3, 860, 508, 1145,
 "REVIEW: 'CAPS' child sheets (pages 9-10) are EMPTY - VDD_INT / VDD_EXT / "
 "VDD_REF decoupling for U5/U6 is not captured anywhere. Populate before "
 "layout release (cf. LOGIC sheet C8-C21 style arrays).",
 arrows=[((1035, 508), (1032, 480))], fs=6)
note(3, 45, 595, 315,
 "ANALOG RESOLUTION (U5 = DSPB, output DSP): O0 (DAI0 p2) = DA0 -> line "
 "outs 1-8; O1 'DAC 9-16' -> physical line is DA3 (DA1 is spare); O2 = "
 "CDC_I codec (talkback SPKR + aux out); O3 'DAC MAIN' = no sink on D24 "
 "Analog rev B (VERIFY); O4-O7 = NET (digital). Inputs I0-I7 = 128 mix "
 "buses from DSPA (digital).", fs=6)

# ---------- Page 5 (DSPA, U6) ----------
note(4, 45, 470, 315,
 "REVIEW: same notes as DSPB sheet (p4/10) apply to U6: OSPI0/xSPI shares "
 "Port A with the Pi SPI2 link (PA_00/01/04/05); xSPI_RWDS/xSPI_SEL2 NC; "
 "PA_02/03/06-10 free; BMODE=0b010 SPI2 slave boot OK; CAPS decoupling "
 "sheet empty.",
 arrows=[((300, 470), (306, 334))], fs=6)
note(4, 45, 555, 315,
 "ANALOG RESOLUTION (U6 = DSPA, input DSP): I0/I1/I2 (DAI0 p1/3/5) = mic "
 "ch 1-24 via AD0-2; I3 = no D24 ADC (D32-compat/NET only); I4 (DAI1 p1) "
 "= AK4916 talkback/aux ADC via CDC_O; I7 = MEMS surface mics; I5 snake / "
 "I6 Pi PCM = digital. Outputs O0-O7 = 128 mix buses to DSPB (digital).", fs=6)

# ---------- Page 8 (R sheet) ----------
note(7, 150, 330, 480,
 "REVIEW (SPI-RAM option): both DSPs share ONE Pi SPI bus, split via 33R "
 "into CK1/CK2 branches. Because OSPI0 reuses the same DSP Port-A pins, a "
 "PSRAM retrofit affects BOTH chips and OSPI clocks (133MHz+ DDR) cannot "
 "tolerate these stubs/branches. Next rev: separate runtime param link "
 "(SPI0/SPI1) per DSP, keep this bus for boot only.",
 arrows=[((250, 330), (230, 300)), ((330, 330), (400, 300))], fs=6)

# ---------- Pages 9-10 (empty CAPS sheets) ----------
for pno in (8, 9):
    note(pno, 380, 330, 820,
     "REVIEW: EMPTY SHEET. This is the 'CAPS' child sheet referenced by the "
     "CAPS block on the DSPA/DSPB pages - the supply decoupling for the two "
     "ADSP-21564s (VDD_INT 0V9, VDD_EXT 3V3, VDD_REF 1V8) is missing from "
     "the design. Add bulk + per-pin 100nF arrays before rev D layout/fab.",
     fs=8)

doc.delete_page(doc.page_count - 1)  # remove measuring scratch page
doc.save(OUT + ".tmp"); doc.close(); os.replace(OUT + ".tmp", OUT)
print("rebuilt (baked-in, exact-height boxes)")
out = fitz.open(OUT)
print("pages:", out.page_count)
pix = out[0].get_pixmap(matrix=fitz.Matrix(1.4,1.4)); pix.save("final2_p1.png")
pix = out[3].get_pixmap(matrix=fitz.Matrix(1.4,1.4)); pix.save("final2_p4.png")
print("done")
