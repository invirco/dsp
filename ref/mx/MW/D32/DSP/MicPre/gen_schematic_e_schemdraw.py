#!/usr/bin/env python3
"""Generate Topology E schematic using schemdraw — v2 clean layout.

Key improvements over v1:
- White background
- Wider leg spacing (10 units) — less crowding
- Q1a/Q1b bases face OUTWARD — input wires don't cross transistors
- L-shaped diode-connect on Q3a — no diagonal crossings
- C6 shown as annotation — eliminates long horizontal crossing wire
- R12 bias goes downward — no horizontal crossing in center
- Merged OUT_P/OUT_N labels into output filter paths
"""

import schemdraw
import schemdraw.elements as elm
import re

OUTPUT = "/home/peter/Stonepower Dropbox/Peter Watts/VSCODE/MicPre/schematic_topology_e.svg"

d = schemdraw.Drawing(backend='svg', show=False, fontsize=11)

LEG_SPACING = 10  # Wide horizontal separation between left and right legs

# ============================================================
# 3.3V SUPPLY RAILS
# ============================================================
d += elm.Line().right(1).at((0, 0)).color('red')
VCC_LEFT = d.here
d += elm.Vdd().label('3.3V').color('red')

d += elm.Line().right(LEG_SPACING).at(VCC_LEFT)
VCC_RIGHT = d.here
d += elm.Vdd().label('3.3V').color('red')

# ============================================================
# LEFT LEG — Collector load + mirror degeneration
# ============================================================
d += elm.Resistor().down().at(VCC_LEFT).label('R7\n1K0', loc='right')
R7_BOT = d.here
d += elm.Resistor().down().label('R10\n100R', loc='right')
R10_BOT = d.here

# Q3a — PNP mirror (left, diode-connected)
# Flipped: base RIGHT (toward center) for mirror base tie
Q3a = (elm.BjtPnp(circle=True)
       .anchor('emitter').flip()
       .at(R10_BOT)
       .label('Q3a', loc='left')
       .label('MMDT4403', loc='left', ofst=(0, -0.4), fontsize=8))
d += Q3a

# ============================================================
# RIGHT LEG — Collector load + mirror degeneration
# ============================================================
d += elm.Resistor().down().at(VCC_RIGHT).label('R8\n1K0', loc='right')
R8_BOT = d.here
d += elm.Resistor().down().label('R11\n100R', loc='right')
R11_BOT = d.here

# Q3b — PNP mirror (right)
# Default: base LEFT (toward center) for mirror base tie
Q3b = (elm.BjtPnp(circle=True)
       .anchor('emitter')
       .at(R11_BOT)
       .label('Q3b', loc='right'))
d += Q3b

# ── Mirror base tie ──
d += elm.Line().at(Q3a.base).to(Q3b.base)
d += elm.Dot().at(Q3a.base)

# ── Diode-connect Q3a — L-shaped route (no diagonal) ──
# Vertical from base Y down to collector Y, then horizontal to collector
dc_bend = (Q3a.base[0], Q3a.collector[1])
d += elm.Line().at(Q3a.base).to(dc_bend)
d += elm.Line().at(dc_bend).to(Q3a.collector)
d += elm.Dot().at(Q3a.collector)

# ============================================================
# OUTPUT TAPS
# ============================================================
d += elm.Line().down(0.5).at(Q3a.collector)
OUTP = d.here
d += elm.Dot()

d += elm.Line().down(0.5).at(Q3b.collector)
OUTN = d.here
d += elm.Dot()

# ============================================================
# Q4 CASCODE — MMDT2227 NPN dual, common-base
# Bases INWARD for cascode tie
# ============================================================
Q4a = (elm.BjtNpn(circle=True)
       .anchor('collector').flip()
       .at(OUTP)
       .label('Q4a', loc='left'))
d += Q4a

Q4b = (elm.BjtNpn(circle=True)
       .anchor('collector')
       .at(OUTN)
       .label('Q4b', loc='right')
       .label('MMDT2227', loc='right', ofst=(0, -0.4), fontsize=8))
d += Q4b

# ── Cascode base tie ──
d += elm.Line().at(Q4a.base).to(Q4b.base)
CAS_MID = ((Q4a.base[0] + Q4b.base[0])/2, Q4a.base[1])
d += elm.Dot().at(CAS_MID)

# R12 bias — goes DOWN from midpoint (avoids horizontal crossing)
d += elm.Resistor().down(2).at(CAS_MID).label('R12\n10K', loc='right')
d += elm.Label().label('VBIAS', loc='right').color('blue')

# ============================================================
# Q1 DIFFERENTIAL PAIR — DMMT3904W NPN dual
# *** Bases face OUTWARD so input wires don't cross ***
# ============================================================
# Q1a: DEFAULT orientation → base LEFT (outward)
Q1a = (elm.BjtNpn(circle=True)
       .anchor('collector')
       .at(Q4a.emitter)
       .label('Q1a', loc='right')
       .label('DMMT3904W', loc='right', ofst=(0, -0.4), fontsize=8))
d += Q1a

# Q1b: FLIPPED → base RIGHT (outward)
Q1b = (elm.BjtNpn(circle=True)
       .anchor('collector').flip()
       .at(Q4b.emitter)
       .label('Q1b', loc='left'))
d += Q1b

# ============================================================
# EMITTER JUNCTION
# ============================================================
d += elm.Line().at(Q1a.emitter).down(0.5)
EMIT_LEFT = d.here
d += elm.Line().at(Q1b.emitter).down(0.5)
EMIT_RIGHT = d.here

d += elm.Line().at(EMIT_LEFT).to(EMIT_RIGHT)
EMIT_MID = ((EMIT_LEFT[0] + EMIT_RIGHT[0])/2, EMIT_LEFT[1])
d += elm.Dot().at(EMIT_MID)

# ============================================================
# GAIN SWITCHING NETWORK — Series R_A + R_B with relay bypasses
# ============================================================
d += elm.Line().down(0.5).at(EMIT_MID)
GS_TOP = d.here

d += elm.Annotate().at(GS_TOP).delta(3.5, -4.5).label('GAIN SWITCHING\nNETWORK').color('darkorange')

# R_A = 150R with Relay A bypass
d += elm.Resistor().down().at(GS_TOP).label('R_A\n150R', loc='right').color('darkorange')
RA_BOT = d.here
d += elm.Dot().at(GS_TOP)

d += elm.Line().right(2.5).at(GS_TOP)
d += elm.Switch().down().label('Relay A', loc='right').color('firebrick')
d += elm.Line().left(2.5)
d += elm.Dot().at(RA_BOT)

# R_B = 470R with Relay B bypass
d += elm.Line().down(0.3).at(RA_BOT)
RB_TOP = d.here

d += elm.Resistor().down().at(RB_TOP).label('R_B\n470R', loc='right').color('darkorange')
RB_BOT = d.here
d += elm.Dot().at(RB_TOP)

d += elm.Line().right(2.5).at(RB_TOP)
d += elm.Switch().down().label('Relay B', loc='right').color('firebrick')
d += elm.Line().left(2.5)
d += elm.Dot().at(RB_BOT)

# ============================================================
# TAIL CURRENT SOURCE — Q2a + R5
# ============================================================
d += elm.Line().down(0.3).at(RB_BOT)
TAIL_TOP = d.here

Q2a = (elm.BjtNpn(circle=True)
       .anchor('collector')
       .at(TAIL_TOP)
       .label('Q2a', loc='right')
       .label('DMMT3904W', loc='right', ofst=(0, -0.4), fontsize=8))
d += Q2a

d += elm.Resistor().down().at(Q2a.emitter).label('R5\n3K3', loc='right')
d += elm.Ground()

d += elm.Resistor().down().at(Q2a.base).label('R4\n10K', loc='left')
d += elm.Ground()

d += elm.Annotate().at(Q2a.base).delta(-2.5, 0.5).label('bootstrap\nC5 10µF').color('gray')

# ============================================================
# INPUT SECTION — wires go OUTWARD from Q1 bases, no crossing
# ============================================================
# Q1a: base LEFT → input chain goes LEFT
d += elm.Line().left(1.5).at(Q1a.base)
INP = d.here
d += elm.Dot()

d += elm.Resistor().up(2).at(INP).label('R1\n100M', loc='right')
d += elm.Label().label('VBIAS\n1.65V', loc='right').color('blue')

d += elm.Capacitor().left(2.5).at(INP).label('C1\n10µF', loc='top')
C1_L = d.here
d += elm.Dot().at(C1_L)

d += elm.Resistor().up(2).at(C1_L).label('R13\n6K8', loc='right')
d += elm.Label().label('48V').color('red')

d += elm.Line().left(1.5).at(C1_L)
d += elm.Label().label('J1 Pin 2\n(Hot +)', loc='left')

# Q1b: base RIGHT → input chain goes RIGHT
d += elm.Line().right(1.5).at(Q1b.base)
INN = d.here
d += elm.Dot()

d += elm.Resistor().up(2).at(INN).label('R2\n100M', loc='left')
d += elm.Label().label('VBIAS\n1.65V', loc='left').color('blue')

d += elm.Capacitor().right(2.5).at(INN).label('C2\n10µF', loc='top')
C2_R = d.here
d += elm.Dot().at(C2_R)

d += elm.Resistor().up(2).at(C2_R).label('R14\n6K8', loc='left')
d += elm.Label().label('48V').color('red')

d += elm.Line().right(1.5).at(C2_R)
d += elm.Label().label('J1 Pin 3\n(Cold −)', loc='right')

# ============================================================
# OUTPUT FILTER — R15/R16 + C3/C4 → AK4619
# ============================================================
# OUT_P → left → R15 → C3 → AK4619 LRIN1+
d += elm.Line().left(2).at(OUTP)
d += elm.Resistor().left().label('R15\n100R', loc='top')
d += elm.Capacitor().left().label('C3\n220pF', loc='top')
AK_P = d.here
d += elm.Label().label('→ AK4619\nLRIN1+', loc='left').color('blue')

# OUT_N → right → R16 → C4 → AK4619 LRIN1−
d += elm.Line().right(2).at(OUTN)
d += elm.Resistor().right().label('R16\n100R', loc='top')
d += elm.Capacitor().right().label('C4\n220pF', loc='top')
AK_N = d.here
d += elm.Label().label('AK4619\nLRIN1− ←', loc='right').color('blue')

# C6 — annotation instead of long crossing wire
d += elm.Annotate().at(AK_P).delta(0.5, 1.5).label('C6 100pF between\nLRIN1+ and LRIN1−', fontsize=8).color('gray')

# ============================================================
# ANNOTATIONS
# ============================================================
d += elm.Annotate().at((5, 3)).label('Topology E: 4-Step Series-R\nDirect-to-ADC Mic Preamp').color('black')

tbl = (
    "GAIN TRUTH TABLE\n"
    "────────────────────────────────\n"
    "Relay A  Relay B  RE    Gain\n"
    "────────────────────────────────\n"
    "Closed   Closed   0Ω    ×40 (32 dB)\n"
    "Open     Closed   150R  ×10 (20 dB)\n"
    "Closed   Open     470R  ×4  (12 dB)\n"
    "Open     Open     620R  ×2.5 (8 dB)\n"
    "────────────────────────────────\n"
    "Total range: −4 to 68 dB\n"
    "(with AK4619 digital vol)"
)
d += elm.Annotate().at((16, -8)).label(tbl, fontsize=8).color('gray')

ak_info = (
    "AK4619 4ch Codec\n"
    "24-bit · 106 dB SNR\n"
    "Digital Vol: −12 to +36 dB\n"
    "(0.5 dB steps) · I²C ctrl\n"
    "I²S/TDM → MCU"
)
d += elm.Annotate().at((-10, -4)).label(ak_info, fontsize=9).color('royalblue')

bom = (
    "BOM (per ch): ~37 parts · ~$1.37 @1k\n"
    "Q1,Q2: DMMT3904W · Q3: MMDT4403\n"
    "Q4: MMDT2227 · 2× SPST relay"
)
d += elm.Annotate().at((-10, -14)).label(bom, fontsize=8).color('gray')

# ============================================================
# SAVE + WHITE BACKGROUND
# ============================================================
d.save(OUTPUT)

# Post-process SVG: add white background rectangle
with open(OUTPUT, 'r') as f:
    svg = f.read()
svg = re.sub(r'(<svg[^>]*>)', r'\1\n<rect width="100%" height="100%" fill="white"/>', svg)
with open(OUTPUT, 'w') as f:
    f.write(svg)

print(f"Written to {OUTPUT}")

# Debug coordinates
def pp(name, pt):
    print(f"  {name:16s} ({pt[0]:6.2f}, {pt[1]:6.2f})")

print(f"\nKey positions:")
pp("VCC_LEFT", VCC_LEFT)
pp("VCC_RIGHT", VCC_RIGHT)
pp("OUTP", OUTP)
pp("OUTN", OUTN)
pp("Q3a.emit", Q3a.emitter)
pp("Q3a.base", Q3a.base)
pp("Q3a.coll", Q3a.collector)
pp("Q3b.emit", Q3b.emitter)
pp("Q3b.base", Q3b.base)
pp("Q3b.coll", Q3b.collector)
pp("Q4a.coll", Q4a.collector)
pp("Q4a.base", Q4a.base)
pp("Q4a.emit", Q4a.emitter)
pp("Q4b.coll", Q4b.collector)
pp("Q4b.base", Q4b.base)
pp("Q4b.emit", Q4b.emitter)
pp("Q1a.coll", Q1a.collector)
pp("Q1a.base", Q1a.base)
pp("Q1a.emit", Q1a.emitter)
pp("Q1b.coll", Q1b.collector)
pp("Q1b.base", Q1b.base)
pp("Q1b.emit", Q1b.emitter)
pp("EMIT_LEFT", EMIT_LEFT)
pp("EMIT_RIGHT", EMIT_RIGHT)
pp("EMIT_MID", EMIT_MID)
