#!/usr/bin/env python3
"""Generate Topology E block-style schematic as hand-crafted SVG.

All components are rectangles on a grid. All wires are orthogonal.
Zero wire crossings by design.
"""

OUTPUT = "/home/peter/Stonepower Dropbox/Peter Watts/VSCODE/MicPre/schematic_topology_e_block.svg"

# ── Grid constants ──────────────────────────────────────────
# Column centers (X)
LEFT = 260       # Left leg center
MID  = 510       # Center axis
RIGHT = 760      # Right leg center

# Input chains go further out
FAR_LEFT = 30
FAR_RIGHT = 990

# Input connector positions (outside pad components)
INP_L_X  = -140   # J1 Pin 2 (left of pad + relay C)
INP_R_X  = 1150   # J1 Pin 3 (right of pad + relay C)

# Row centers (Y) — top to bottom (3.3V, no cascode, AC-coupled)
Y_VCC    = 50
Y_RLOAD  = 130    # R7/R8
Y_Q3     = 220    # PNP mirror
Y_OUT    = 320    # Output tap → C7/C8 AC coupling → R15/R16 → ADC
Y_Q1     = 470    # Diff pair (gap for output chain + labels)
Y_INPUT  = 470    # Input chain (same row as Q1)
Y_EMIT   = 570    # Emitter junction + gain degeneration (between emitters)
Y_Q2     = 690    # Tail current source
Y_R5     = 780    # R5
Y_GND    = 850    # Ground
Y_PAD    = 470    # Input pad row (same as input chain)

# Component sizes
TW, TH = 64, 50   # Transistor box
RW, RH = 54, 28   # Resistor box
CW, CH = 54, 28   # Capacitor box (same as resistor — fits name+value)
SW, SH = 56, 26   # Switch/relay box

# ── SVG builder ─────────────────────────────────────────────
lines = []

def svg_start(w, h):
    pad = 260  # left padding for J1 labels + pad relay C
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w+pad}" height="{h}" '
                 f'viewBox="{-pad} 0 {w+pad} {h}" font-family="Consolas, monospace" font-size="11">')
    lines.append(f'<rect x="{-pad}" width="{w+pad}" height="{h}" fill="white"/>')
    lines.append('<defs>')
    lines.append('  <marker id="dot" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" markerHeight="4">')
    lines.append('    <circle cx="3" cy="3" r="3" fill="black"/>')
    lines.append('  </marker>')
    lines.append('</defs>')

def svg_end():
    lines.append('</svg>')

def rect(x, y, w, h, label, sublabel=None, fill='#f8f8f8', stroke='black', text_color='black', stroke_w=1.5):
    """Rectangle centered at (x,y) with label inside."""
    lines.append(f'<rect x="{x-w//2}" y="{y-h//2}" width="{w}" height="{h}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}" rx="3"/>')
    if sublabel:
        lines.append(f'<text x="{x}" y="{y-6}" text-anchor="middle" dominant-baseline="middle" '
                     f'fill="{text_color}" font-size="10" font-weight="bold">{label}</text>')
        lines.append(f'<text x="{x}" y="{y+7}" text-anchor="middle" dominant-baseline="middle" '
                     f'fill="{text_color}" font-size="9">{sublabel}</text>')
    else:
        lines.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
                     f'fill="{text_color}" font-size="10" font-weight="bold">{label}</text>')

def transistor(x, y, name, part, kind='NPN', fill='#e8f0ff'):
    """Transistor as labeled rectangle with B/C/E pin labels on edges."""
    rect(x, y, TW, TH, name, part, fill=fill, stroke='#336')
    # Pin labels outside the box
    if kind == 'NPN':
        # C top, E bottom, B on one side (determined by caller via label placement)
        lines.append(f'<text x="{x}" y="{y-TH//2-4}" text-anchor="middle" font-size="8" fill="#666">C</text>')
        lines.append(f'<text x="{x}" y="{y+TH//2+10}" text-anchor="middle" font-size="8" fill="#666">E</text>')
    else:  # PNP
        # E top, C bottom
        lines.append(f'<text x="{x}" y="{y-TH//2-4}" text-anchor="middle" font-size="8" fill="#666">E</text>')
        lines.append(f'<text x="{x}" y="{y+TH//2+10}" text-anchor="middle" font-size="8" fill="#666">C</text>')

def resistor(x, y, name, value, fill='#fff8e8', stroke='#996', text_color='#663'):
    rect(x, y, RW, RH, name, value, fill=fill, stroke=stroke, text_color=text_color)

def capacitor(x, y, name, value, fill='#e8ffe8', stroke='#696'):
    rect(x, y, CW, CH, name, value, fill=fill, stroke=stroke, text_color='#363')

def switch(x, y, name, fill='#ffe8e8', stroke='#c44'):
    rect(x, y, SW, SH, name, fill=fill, stroke=stroke, text_color='#933')

def wire(x1, y1, x2, y2, color='black', width=1.2):
    lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{color}" stroke-width="{width}"/>')

def wire_L(x1, y1, x2, y2, bend='h_first', color='black', width=1.2):
    """L-shaped orthogonal wire: horizontal-first or vertical-first."""
    if bend == 'h_first':
        wire(x1, y1, x2, y1, color, width)
        wire(x2, y1, x2, y2, color, width)
    else:
        wire(x1, y1, x1, y2, color, width)
        wire(x1, y2, x2, y2, color, width)

def dot(x, y, r=3):
    lines.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="black"/>')

def label(x, y, text, anchor='middle', color='black', size=11, weight='normal'):
    lines.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" dominant-baseline="middle" '
                 f'fill="{color}" font-size="{size}" font-weight="{weight}">{text}</text>')

def ground(x, y):
    """Simple ground symbol."""
    w = 16
    wire(x, y, x, y+8)
    wire(x-w//2, y+8, x+w//2, y+8)
    wire(x-w//3, y+13, x+w//3, y+13)
    wire(x-w//6, y+18, x+w//6, y+18)

def vcc(x, y, txt='3.3V'):
    """VCC arrow/label."""
    wire(x, y, x, y-15)
    label(x, y-22, txt, color='red', size=10, weight='bold')

def box_annotation(x, y, w, h, text, color='darkorange'):
    """Dashed annotation box."""
    lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                 f'fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="6,3" rx="8"/>')
    label(x + w//2, y - 8, text, color=color, size=10, weight='bold')


# ═══════════════════════════════════════════════════════════
# BUILD THE SCHEMATIC
# ═══════════════════════════════════════════════════════════
svg_start(1310, 1050)

# ── Title ──
label(MID, 16, 'Topology E: 4-Step Series-R Direct-to-ADC Mic Preamp (3.3V, AC-coupled)', size=14, weight='bold')

# ── 3.3V Supply ──
vcc(LEFT, Y_VCC, '3.3V')
vcc(RIGHT, Y_VCC, '3.3V')
wire(LEFT, Y_VCC, LEFT, Y_RLOAD - RH//2)   # VCC to R7
wire(RIGHT, Y_VCC, RIGHT, Y_RLOAD - RH//2) # VCC to R8

# ── R7, R8 collector loads (includes degeneration) ──
resistor(LEFT, Y_RLOAD, 'R7', '1K1')
resistor(RIGHT, Y_RLOAD, 'R8', '1K1')
wire(LEFT, Y_RLOAD + RH//2, LEFT, Y_Q3 - TH//2)
wire(RIGHT, Y_RLOAD + RH//2, RIGHT, Y_Q3 - TH//2)

# ── Q3a, Q3b PNP mirror ──
transistor(LEFT, Y_Q3, 'Q3a', 'MMDT4403', kind='PNP', fill='#fce4ec')
transistor(RIGHT, Y_Q3, 'Q3b', 'MMDT4403', kind='PNP', fill='#fce4ec')

# B labels on inner side
label(LEFT + TW//2 + 10, Y_Q3, 'B', size=8, color='#666')
label(RIGHT - TW//2 - 10, Y_Q3, 'B', size=8, color='#666')

# Mirror base tie — horizontal wire between Q3a.B and Q3b.B
Q3A_B_X = LEFT + TW//2
Q3B_B_X = RIGHT - TW//2
wire(Q3A_B_X, Y_Q3, Q3B_B_X, Y_Q3, color='#336')
dot(Q3A_B_X, Y_Q3)

# Diode-connect Q3a: B to C (L-shaped: right from base, then down to collector)
# Base is at (Q3A_B_X, Y_Q3), collector is at (LEFT, Y_Q3 + TH//2)
# Route: go right to a point, then down... but B is already on the tie wire.
# Instead: short vertical from base down to C level, then left to C
DIODE_X = Q3A_B_X + 15  # slightly right of base
wire(DIODE_X, Y_Q3, DIODE_X, Y_Q3 + TH//2 + 15, color='#336')
wire(DIODE_X, Y_Q3 + TH//2 + 15, LEFT, Y_Q3 + TH//2 + 15, color='#336')
wire(LEFT, Y_Q3 + TH//2, LEFT, Y_Q3 + TH//2 + 15, color='#336')
dot(DIODE_X, Y_Q3)
label(DIODE_X + 20, Y_Q3 + TH//2 + 8, 'diode conn.', size=8, color='#999')

# Q3 collectors to output tap row
wire(LEFT, Y_Q3 + TH//2, LEFT, Y_OUT)
wire(RIGHT, Y_Q3 + TH//2, RIGHT, Y_OUT)
dot(LEFT, Y_OUT)
dot(RIGHT, Y_OUT)

# ── Output taps → AC coupling → anti-alias filter → AK4619 ──
# Left side: collector → C7 (AC coupling) → R15 (100R) → AK4619 LRIN1+
C7_X  = LEFT - 80
R15_X = LEFT - 160
AK_P_X = -50

wire(LEFT, Y_OUT, C7_X + CW//2, Y_OUT)
dot(LEFT, Y_OUT)
capacitor(C7_X, Y_OUT, 'C7', '10µF')
wire(C7_X - CW//2, Y_OUT, R15_X + RW//2, Y_OUT)
resistor(R15_X, Y_OUT, 'R15', '100R')
# C3 shunt to VCOM (anti-alias LP: fc = 723 kHz)
C3_Y = Y_OUT + 40
wire(R15_X - RW//2, Y_OUT, AK_P_X, Y_OUT)
dot(R15_X - RW//2, Y_OUT)
wire(R15_X - RW//2, Y_OUT, R15_X - RW//2, C3_Y - CH//2)
capacitor(R15_X - RW//2, C3_Y, 'C3', '2n2 C0G')
label(R15_X - RW//2, C3_Y + CH//2 + 12, 'VCOM', color='blue', size=9)
label(AK_P_X - 5, Y_OUT, '→ AK4619 LRIN1+', anchor='end', color='blue', size=9, weight='bold')

# Right side: collector → C8 (AC coupling) → R16 (100R) → AK4619 LRIN1−
C8_X  = RIGHT + 80
R16_X = RIGHT + 160
AK_N_X = 1070

wire(RIGHT, Y_OUT, C8_X - CW//2, Y_OUT)
dot(RIGHT, Y_OUT)
capacitor(C8_X, Y_OUT, 'C8', '10µF')
wire(C8_X + CW//2, Y_OUT, R16_X - RW//2, Y_OUT)
resistor(R16_X, Y_OUT, 'R16', '100R')
# C4 shunt to VCOM (anti-alias LP: fc = 723 kHz)
C4_Y = Y_OUT + 40
wire(R16_X + RW//2, Y_OUT, AK_N_X, Y_OUT)
dot(R16_X + RW//2, Y_OUT)
wire(R16_X + RW//2, Y_OUT, R16_X + RW//2, C4_Y - CH//2)
capacitor(R16_X + RW//2, C4_Y, 'C4', '2n2 C0G')
label(R16_X + RW//2, C4_Y + CH//2 + 12, 'VCOM', color='blue', size=9)
label(AK_N_X + 5, Y_OUT, 'AK4619 LRIN1− ←', anchor='start', color='blue', size=9, weight='bold')

# C6 annotation (differential cap between ADC inputs)
label(MID, Y_OUT - 15, 'C6 1nF C0G between LRIN1+ and LRIN1− (differential)', color='gray', size=9)
label(MID, Y_OUT + 15, 'C7/C8: AC coupling (electrolytic) — no VCOM needed on preamp', color='#933', size=9, weight='bold')

# Collector continues down to Q1 (no cascode)
wire(LEFT, Y_OUT, LEFT, Y_Q1 - TH//2)
wire(RIGHT, Y_OUT, RIGHT, Y_Q1 - TH//2)

# ── Q1a, Q1b Differential Pair NPN ──
transistor(LEFT, Y_Q1, 'Q1a', 'DMMT3904W', kind='NPN', fill='#e8f0ff')
transistor(RIGHT, Y_Q1, 'Q1b', 'DMMT3904W', kind='NPN', fill='#e8f0ff')

# B labels on OUTER side (inputs come from outside)
label(LEFT - TW//2 - 10, Y_Q1, 'B', size=8, color='#666')
label(RIGHT + TW//2 + 10, Y_Q1, 'B', size=8, color='#666')

# ── Input chains — go outward from Q1 bases ──
Q1A_B_X = LEFT - TW//2
Q1B_B_X = RIGHT + TW//2

# Left input: Q1a base ← R1 ← C1 ← R13/48V ← PAD ← J1 pin 2
R1_X = LEFT - 105
C1_X = LEFT - 195
R13_X = LEFT - 105
PAD_X = LEFT - 285   # pad components X position
INP_X = INP_L_X

# Continuous horizontal wire from Q1a base to C1
wire(Q1A_B_X, Y_Q1, C1_X + CW//2, Y_Q1)

# R1 (100M to VBIAS) — vertical tap above the input line
R1_Y = Y_Q1 - 50
resistor(R1_X, R1_Y, 'R1', '100M')
wire(R1_X, Y_Q1, R1_X, R1_Y + RH//2)
dot(R1_X, Y_Q1)
label(R1_X, R1_Y - RH//2 - 10, 'VBIAS 1.65V', color='blue', size=9)

# C1 coupling cap — inline on the horizontal wire
capacitor(C1_X, Y_Q1, 'C1', '10µF')

# R13 phantom feed — vertical above C1 junction
R13_Y = Y_Q1 - 50
wire(C1_X, Y_Q1, C1_X, R13_Y + RH//2)
dot(C1_X, Y_Q1)
resistor(C1_X, R13_Y, 'R13', '6K8')
label(C1_X, R13_Y - RH//2 - 10, '48V', color='red', size=10, weight='bold')

# −20 dB Input Pad: R_PAD_S (1K5 series) + R_PAD_SH (150R shunt) with Relay C bypass
# Pad is between C1 and J1
R_PAD_S_X = PAD_X
R_PAD_SH_Y = Y_Q1 + 50  # shunt resistor below signal line

wire(C1_X - CW//2, Y_Q1, R_PAD_S_X + RW//2, Y_Q1)
resistor(R_PAD_S_X, Y_Q1, 'R_S', '1K5', fill='#ffe8ff', stroke='#a3a', text_color='#636')

# Shunt resistor to ground
resistor(R_PAD_S_X, R_PAD_SH_Y, 'R_SH', '150R', fill='#ffe8ff', stroke='#a3a', text_color='#636')
wire(R_PAD_S_X, Y_Q1, R_PAD_S_X, R_PAD_SH_Y - RH//2)
dot(R_PAD_S_X, Y_Q1)
wire(R_PAD_S_X, R_PAD_SH_Y + RH//2, R_PAD_S_X, R_PAD_SH_Y + RH//2 + 12)
ground(R_PAD_S_X, R_PAD_SH_Y + RH//2 + 12)

# Relay C bypass directly above R_S (vertical wires only, no wire-through-box)
RELAY_C_Y = Y_Q1 - 48
switch(R_PAD_S_X, RELAY_C_Y, '2N7002×2')
wire(R_PAD_S_X + RW//2, Y_Q1, R_PAD_S_X + RW//2, RELAY_C_Y + SH//2)
wire(R_PAD_S_X - RW//2, RELAY_C_Y + SH//2, R_PAD_S_X - RW//2, Y_Q1)
dot(R_PAD_S_X + RW//2, Y_Q1)
dot(R_PAD_S_X - RW//2, Y_Q1)
label(R_PAD_S_X, RELAY_C_Y - 18, '−20 dB PAD', color='#636', size=9, weight='bold')
label(R_PAD_S_X, RELAY_C_Y - 32, 'Vpk ≈ 1.1V · VG_ON ≥ 2.6V · VG_OFF ≤ 0V', color='#777', size=10)

# J1 Pin 2
wire(R_PAD_S_X - RW//2, Y_Q1, INP_X, Y_Q1)
label(INP_X - 5, Y_Q1 - 15, 'J1 Pin 2 (Hot +)', anchor='end', color='black', size=10, weight='bold')

# Right input: Q1b base ← R2 ← C2 ← R14/48V ← PAD ← J1 pin 3
R2_X = RIGHT + 105
C2_X = RIGHT + 195
R14_X = RIGHT + 105
PAD_R_X = RIGHT + 285   # pad components X position (right side)

# Continuous horizontal wire from Q1b base to C2
wire(Q1B_B_X, Y_Q1, C2_X - CW//2, Y_Q1)

# R2 (100M to VBIAS) — vertical tap above the input line
R2_Y = Y_Q1 - 50
resistor(R2_X, R2_Y, 'R2', '100M')
wire(R2_X, Y_Q1, R2_X, R2_Y + RH//2)
dot(R2_X, Y_Q1)
label(R2_X, R2_Y - RH//2 - 10, 'VBIAS 1.65V', color='blue', size=9)

# C2 coupling cap — inline on the horizontal wire
capacitor(C2_X, Y_Q1, 'C2', '10µF')

R14_Y = Y_Q1 - 50
wire(C2_X, Y_Q1, C2_X, R14_Y + RH//2)
dot(C2_X, Y_Q1)
resistor(C2_X, R14_Y, 'R14', '6K8')
label(C2_X, R14_Y - RH//2 - 10, '48V', color='red', size=10, weight='bold')

# −20 dB Input Pad (right side): R_PAD_S2 (1K5 series) + R_PAD_SH2 (150R shunt)
R_PAD_S2_X = PAD_R_X
R_PAD_SH2_Y = Y_Q1 + 50

wire(C2_X + CW//2, Y_Q1, R_PAD_S2_X - RW//2, Y_Q1)
resistor(R_PAD_S2_X, Y_Q1, 'R_S', '1K5', fill='#ffe8ff', stroke='#a3a', text_color='#636')

# Shunt resistor to ground
resistor(R_PAD_S2_X, R_PAD_SH2_Y, 'R_SH', '150R', fill='#ffe8ff', stroke='#a3a', text_color='#636')
wire(R_PAD_S2_X, Y_Q1, R_PAD_S2_X, R_PAD_SH2_Y - RH//2)
dot(R_PAD_S2_X, Y_Q1)
wire(R_PAD_S2_X, R_PAD_SH2_Y + RH//2, R_PAD_S2_X, R_PAD_SH2_Y + RH//2 + 12)
ground(R_PAD_S2_X, R_PAD_SH2_Y + RH//2 + 12)

# Relay C bypass (right side) — directly above R_S, vertical wires only
RELAY_CR_Y = Y_Q1 - 48
switch(R_PAD_S2_X, RELAY_CR_Y, '2N7002×2')
wire(R_PAD_S2_X - RW//2, Y_Q1, R_PAD_S2_X - RW//2, RELAY_CR_Y + SH//2)
wire(R_PAD_S2_X + RW//2, RELAY_CR_Y + SH//2, R_PAD_S2_X + RW//2, Y_Q1)
dot(R_PAD_S2_X - RW//2, Y_Q1)
dot(R_PAD_S2_X + RW//2, Y_Q1)
label(R_PAD_S2_X, RELAY_CR_Y - 18, '−20 dB PAD', color='#636', size=9, weight='bold')
label(R_PAD_S2_X, RELAY_CR_Y - 32, 'Vpk ≈ 1.1V · VG_ON ≥ 2.6V · VG_OFF ≤ 0V', color='#777', size=10)

wire(R_PAD_S2_X + RW//2, Y_Q1, INP_R_X, Y_Q1)
label(INP_R_X + 5, Y_Q1 - 15, 'J1 Pin 3 (Cold −)', anchor='start', color='black', size=10, weight='bold')

# ── Emitter degeneration between emitters + Gain switching ──
wire(LEFT, Y_Q1 + TH//2, LEFT, Y_EMIT)
wire(RIGHT, Y_Q1 + TH//2, RIGHT, Y_EMIT)

# R_A between LEFT emitter and midpoint
R_A_X = 385
wire(LEFT, Y_EMIT, R_A_X - RW//2, Y_EMIT)
resistor(R_A_X, Y_EMIT, 'R_A', '150R', fill='#fff0e0', stroke='darkorange', text_color='#c60')
wire(R_A_X + RW//2, Y_EMIT, MID, Y_EMIT)

# FET A bypass above R_A
FET_Y = Y_EMIT - 40
wire(R_A_X - RW//2, Y_EMIT, R_A_X - RW//2, FET_Y + SH//2)
switch(R_A_X, FET_Y, '2N7002×2')
wire(R_A_X + RW//2, FET_Y + SH//2, R_A_X + RW//2, Y_EMIT)
dot(R_A_X - RW//2, Y_EMIT)
dot(R_A_X + RW//2, Y_EMIT)
label(R_A_X, FET_Y - 16, 'Vpk ≈ 1.3V · VG_ON ≥ 2.8V · VG_OFF ≤ 0V', color='#777', size=9)

# Midpoint → Q2 tail
dot(MID, Y_EMIT)

# R_B between midpoint and RIGHT emitter
R_B_X = 635
wire(MID, Y_EMIT, R_B_X - RW//2, Y_EMIT)
resistor(R_B_X, Y_EMIT, 'R_B', '470R', fill='#fff0e0', stroke='darkorange', text_color='#c60')
wire(R_B_X + RW//2, Y_EMIT, RIGHT, Y_EMIT)

# FET B bypass above R_B
wire(R_B_X - RW//2, Y_EMIT, R_B_X - RW//2, FET_Y + SH//2)
switch(R_B_X, FET_Y, '2N7002×2')
wire(R_B_X + RW//2, FET_Y + SH//2, R_B_X + RW//2, Y_EMIT)
dot(R_B_X - RW//2, Y_EMIT)
dot(R_B_X + RW//2, Y_EMIT)
label(R_B_X, FET_Y - 16, 'Vpk ≈ 1.3V · VG_ON ≥ 2.8V · VG_OFF ≤ 0V', color='#777', size=9)

box_annotation(R_A_X - RW//2 - 20, FET_Y - 30, R_B_X - R_A_X + RW + 40, Y_EMIT - FET_Y + 50, 'GAIN DEGENERATION (A, B)')

# ── Q2a Tail current source ──
wire(MID, Y_EMIT, MID, Y_Q2 - TH//2)
transistor(MID, Y_Q2, 'Q2a', 'DMMT3904W', kind='NPN', fill='#e8f0ff')

# B label on left
label(MID - TW//2 - 10, Y_Q2, 'B', size=8, color='#666')

# R4 base bias — goes left then down
R4_X = MID - 80
R4_Y = Y_Q2 + 35
wire(MID - TW//2, Y_Q2, R4_X, Y_Q2)
wire(R4_X, Y_Q2, R4_X, R4_Y - RH//2)
resistor(R4_X, R4_Y, 'R4', '10K')
wire(R4_X, R4_Y + RH//2, R4_X, R4_Y + RH//2 + 15)
ground(R4_X, R4_Y + RH//2 + 15)

# C5 bootstrap annotation
label(R4_X - 50, Y_Q2, 'bootstrap C5 10µF', anchor='end', color='gray', size=9)

# R5 emitter degeneration
wire(MID, Y_Q2 + TH//2, MID, Y_R5 - RH//2)
resistor(MID, Y_R5, 'R5', '330R')
wire(MID, Y_R5 + RH//2, MID, Y_GND)
ground(MID, Y_GND)

# ═══════════════════════════════════════════════════════════
# GAIN TABLE (bottom right)
# ═══════════════════════════════════════════════════════════
TBL_X = 770
TBL_Y = Y_Q2 - 20
label(TBL_X, TBL_Y, 'GAIN TABLE', anchor='start', color='#666', size=10, weight='bold')
table_lines = [
    ('Switch A', 'Switch B', 'RE', 'Gain'),
    ('Closed', 'Closed', '0Ω', '×40 (32 dB)'),
    ('Open', 'Closed', '150R', '×10 (20 dB)'),
    ('Closed', 'Open', '470R', '×4  (12 dB)'),
    ('Open', 'Open', '620R', '×2.5 (8 dB)'),
]
for i, row in enumerate(table_lines):
    y = TBL_Y + 18 + i * 16
    color = '#444' if i == 0 else '#666'
    weight_t = 'bold' if i == 0 else 'normal'
    txt = f'{row[0]:8s}  {row[1]:8s}  {row[2]:5s}  {row[3]}'
    label(TBL_X, y, txt, anchor='start', color=color, size=9, weight=weight_t)
label(TBL_X, TBL_Y + 18 + 6 * 16, 'Total range: −4 to 68 dB', anchor='start', color='#888', size=9)
label(TBL_X, TBL_Y + 18 + 7 * 16, '(with AK4619 −12 to +36 dB digital vol)', anchor='start', color='#888', size=9)

# ═══════════════════════════════════════════════════════════
# AK4619 INFO (bottom left)
# ═══════════════════════════════════════════════════════════
AK_X = 30
AK_Y = Y_Q2 - 20
ak_lines = [
    'AK4619 4ch Codec',
    '24-bit · 106 dB SNR',
    'Digital Vol: −12 to +36 dB',
    '(0.5 dB steps) · I²C ctrl',
    'I²S/TDM → MCU',
]
for i, t in enumerate(ak_lines):
    label(AK_X, AK_Y + i * 15, t, anchor='start', color='royalblue', size=9)

# BOM summary
BOM_Y = AK_Y + len(ak_lines) * 15 + 15
bom_lines = [
    'BOM (per ch): ~35 parts · ~$1.20 @1k',
    'Q1,Q2: DMMT3904W · Q3: MMDT4403',
    '3× 2N7002 back-to-back pairs',
    'C7/C8: 10µF elec (AC coupling)',
    'R_S/R_SH: −20dB pad',
]
for i, t in enumerate(bom_lines):
    label(AK_X, BOM_Y + i * 14, t, anchor='start', color='#888', size=8)

# Input impedance
IMP_Y = BOM_Y + len(bom_lines) * 14 + 18
imp_lines = [
    'INPUT IMPEDANCE (differential)',
    'Phantom ON:  ~12 kΩ  (6K8 per leg dominates)',
    'Phantom OFF: ~140–260 kΩ  (β-limited, gain dependent)',
]
label(AK_X, IMP_Y, imp_lines[0], anchor='start', color='#555', size=9, weight='bold')
for i, t in enumerate(imp_lines[1:]):
    label(AK_X, IMP_Y + 14 + i * 14, t, anchor='start', color='#666', size=9)

# FET switch notes
FET_Y = IMP_Y + 14 + len(imp_lines[1:]) * 14 + 18
fet_lines = [
    'FET SWITCHES (2N7002 back-to-back pairs)',
    'Emitter DC ≈ 1.0V · Vpk ≈ 1.1V',
    'Pad AC-coupled: Vpk ≈ 1.1V (mic max)',
    'VG_ON must exceed Vpk + Vgs(th)_max',
    '2N7002 (Vgs(th) 2.5V): VG ≥ 3.6V — needs charge pump',
    'BSS138 (Vgs(th) 1.5V): VG ≥ 2.6V — 3.3V OK ✔',
]
label(AK_X, FET_Y, fet_lines[0], anchor='start', color='#555', size=9, weight='bold')
for i, t in enumerate(fet_lines[1:]):
    label(AK_X, FET_Y + 14 + i * 14, t, anchor='start', color='#666', size=9)

svg_end()

# ── Write output ──
with open(OUTPUT, 'w') as f:
    f.write('\n'.join(lines))
print(f'Written to {OUTPUT}')
