#!/usr/bin/env python3
"""Combined analog + digital gain plot — shows 1dB steps achieved by analog switching + DSP trim.
Includes EIN trace showing noise performance at each gain setting."""
import math

Rf = 4990.0
Rds = 3.0
R = [15.0, 37.4, 93.1, 232.0, 590.0, 1470.0]

# === EIN constants (from micpre.md) ===
SOURCE_R = 150              # ohm
EN_SOURCE = 1.58            # nV/√Hz (150 Ω thermal)
EN_DIFF = 1.05              # nV/√Hz (MMDT4403 diff pair, rbb' ~20 Ω)
EN_OPAMP = 0.8              # nV/√Hz (NJM2068M)
IN_OPAMP = 0.4e-3           # nA/√Hz → 0.4 pA/√Hz (NJM2068M current noise)
EN_FET_1F = 0.4             # nV/√Hz (FET 1/f + thermal per switch, estimated)
G_DISCRETE = 2.5            # ×2.5 (8 dB) — fixed discrete stage gain
BW = 19980                  # Hz (20–20 kHz)
REF_DBU = 0.7746            # V (0 dBu)
K_BOLTZ = 1.38e-23
TEMP = 298                  # K

def calc_ein(mask):
    """EIN in dBu for a given FET switch mask (0–63).
    Includes source, diff pair, op-amp, feedback network, and FET noise."""
    # Compute Rg (parallel combination of selected R+Rds)
    if mask == 0:
        Rg = float('inf')
        n_fets = 0
    else:
        G_cond = sum(1.0 / (R[i] + Rds) for i in range(6) if mask & (1 << i))
        Rg = 1.0 / G_cond
        n_fets = bin(mask).count('1')

    # Feedback network thermal noise: sqrt(4kT * Rg) at the inverting input
    # (Rf noise is negligible when referred to input at any gain)
    if mask == 0:
        en_feedback = 0.0
    else:
        en_feedback = math.sqrt(4 * K_BOLTZ * TEMP * Rg) * 1e9  # nV/√Hz

    # FET 1/f + thermal noise in Rg path (scales with sqrt of active FETs)
    en_fets = EN_FET_1F * math.sqrt(n_fets) if n_fets > 0 else 0.0

    # Op-amp current noise through Rf||Rg
    if mask == 0:
        Rf_par_Rg = Rf  # follower mode
    else:
        Rf_par_Rg = Rf * Rg / (Rf + Rg)
    en_in_current = IN_OPAMP * Rf_par_Rg  # nV/√Hz at inverting input

    # All noise referred to mic input (divide by G_discrete)
    en_total_sq = (
        EN_SOURCE**2 +
        EN_DIFF**2 +
        (EN_OPAMP / G_DISCRETE)**2 +
        (en_feedback / G_DISCRETE)**2 +
        (en_fets / G_DISCRETE)**2 +
        (en_in_current / G_DISCRETE)**2 +
        (IN_OPAMP * 1e-3 * SOURCE_R)**2  # current noise through source at non-inv input
    )
    noise_v = math.sqrt(en_total_sq) * 1e-9 * math.sqrt(BW)
    return 20 * math.log10(noise_v / REF_DBU)

out = []
for m in range(64):
    G = sum(1.0 / (R[i] + Rds) for i in range(6) if m & (1 << i))
    db = 20 * math.log10(1 + Rf * G) if G > 0 else 0.0
    out.append((db, m))
out.sort()

dbs = [g[0] for g in out]
max_db_int = int(dbs[-1])

# 1dB mapping: for each target, find nearest analog step + DSP trim
mapping = []
for t in range(max_db_int + 1):
    bi = min(range(len(out)), key=lambda j: abs(out[j][0] - t))
    analog = out[bi][0]
    trim = t - analog
    mask = out[bi][1]
    ein = calc_ein(mask)
    mapping.append((t, analog, trim, mask, ein))

# SVG
W, H = 900, 500
ML, MR, MT, MB = 80, 160, 40, 60
PW = W - ML - MR
PH = H - MT - MB

max_gain = max(max_db_int, dbs[-1])

# EIN axis range
ein_values = [m[4] for m in mapping]
EIN_MIN = math.floor(min(ein_values)) - 1
EIN_MAX = math.ceil(max(ein_values)) + 1

def sx(v):
    return ML + v / max_gain * PW

def sy(v):
    return MT + PH - v / max_gain * PH

def sy_ein(v):
    return MT + (EIN_MAX - v) / (EIN_MAX - EIN_MIN) * PH

svg = []
svg.append('<?xml version="1.0" encoding="UTF-8"?>')
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(W, H, W, H))
svg.append('<style>')
svg.append('  text { font-family: monospace; font-size: 12px; fill: #333; }')
svg.append('  .title { font-size: 15px; font-weight: bold; }')
svg.append('  .subtitle { font-size: 11px; fill: #666; }')
svg.append('</style>')
svg.append('<rect width="100%" height="100%" fill="white"/>')

# Title
svg.append('<text x="{}" y="20" class="title">Mic Preamp: Combined Analog + Digital Gain (0 to {} dB in 1 dB steps)</text>'.format(ML, max_db_int))
svg.append('<text x="{}" y="34" class="subtitle">MMDT4403 diff pair · NJM2068M · Rf=4K99 | R: 1K47, 590R, 232R, 93R1, 37R4, 15R | 2N7002 (Rds~3R) | 150 Ω source</text>'.format(ML))

# Grid
for g in range(0, int(max_gain) + 1, 5):
    y = sy(g)
    svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#eee" stroke-width="0.5"/>'.format(ML, y, ML+PW, y))
    if g % 10 == 0:
        svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#ccc" stroke-width="0.5"/>'.format(ML, y, ML+PW, y))
        svg.append('<text x="{}" y="{:.1f}" text-anchor="end">{} dB</text>'.format(ML-5, y+4, g))
    x = sx(g)
    svg.append('<line x1="{:.1f}" y1="{}" x2="{:.1f}" y2="{}" stroke="#eee" stroke-width="0.5"/>'.format(x, MT, x, MT+PH))
    if g % 10 == 0:
        svg.append('<line x1="{:.1f}" y1="{}" x2="{:.1f}" y2="{}" stroke="#ccc" stroke-width="0.5"/>'.format(x, MT, x, MT+PH))
        svg.append('<text x="{:.1f}" y="{}" text-anchor="middle">{}</text>'.format(x, MT+PH+15, g))

# Axes
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#333" stroke-width="1"/>'.format(ML, MT, ML, MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#333" stroke-width="1"/>'.format(ML, MT+PH, ML+PW, MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#333" stroke-width="1"/>'.format(ML+PW, MT, ML+PW, MT+PH))
svg.append('<text x="{:.0f}" y="{}" text-anchor="middle">Target Gain (dB)</text>'.format(ML + PW/2, MT+PH+35))
svg.append('<text x="{}" y="{:.0f}" text-anchor="middle" transform="rotate(-90,{},{:.0f})">Output Gain (dB)</text>'.format(ML-50, MT+PH/2, ML-50, MT+PH/2))

# Right axis — EIN ticks
svg.append('<text x="{}" y="{:.0f}" text-anchor="middle" fill="#9333ea" transform="rotate(90,{},{:.0f})">EIN (dBu) — 150 Ω</text>'.format(ML+PW+50, MT+PH/2, ML+PW+50, MT+PH/2))
for ein_tick in range(EIN_MIN, EIN_MAX + 1):
    y = sy_ein(ein_tick)
    if MT <= y <= MT + PH:
        svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#9333ea" stroke-width="0.5" opacity="0.3"/>'.format(ML, y, ML+PW, y))
        svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#9333ea" stroke-width="1"/>'.format(ML+PW, y, ML+PW+5, y))
        svg.append('<text x="{}" y="{:.1f}" fill="#9333ea">{}</text>'.format(ML+PW+8, y+4, ein_tick))

# Ideal line (y=x)
svg.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="#ddd" stroke-width="1.5" stroke-dasharray="6,4"/>'.format(
    sx(0), sy(0), sx(max_db_int), sy(max_db_int)))

# Analog-only: for each 1dB target, show the analog step chosen (blue dots)
for t, analog, trim, mask, ein in mapping:
    x = sx(t)
    y = sy(analog)
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="3" fill="#2563eb" opacity="0.5"/>'.format(x, y))

# Analog line
pts_a = " ".join("{:.1f},{:.1f}".format(sx(t), sy(analog)) for t, analog, trim, mask, ein in mapping)
svg.append('<polyline points="{}" stroke="#2563eb" stroke-width="1.5" fill="none" opacity="0.6"/>'.format(pts_a))

# DSP trim arrows: vertical lines from analog to target
for t, analog, trim, mask, ein in mapping:
    x = sx(t)
    y_a = sy(analog)
    y_t = sy(t)
    if abs(trim) > 0.1:
        color = "#16a34a" if trim > 0 else "#dc2626"
        svg.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="{}" stroke-width="1" opacity="0.4"/>'.format(
            x, y_a, x, y_t, color))

# Combined output (analog + DSP = target): green line, should be perfect staircase
pts_c = " ".join("{:.1f},{:.1f}".format(sx(t), sy(t)) for t, analog, trim, mask, ein in mapping)
svg.append('<polyline points="{}" stroke="#16a34a" stroke-width="2.5" fill="none"/>'.format(pts_c))

# Combined dots
for t, analog, trim, mask, ein in mapping:
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2.5" fill="#16a34a"/>'.format(sx(t), sy(t)))

# === EIN trace (purple, right axis) ===
pts_ein = " ".join("{:.1f},{:.1f}".format(sx(t), sy_ein(ein)) for t, analog, trim, mask, ein in mapping)
svg.append('<polyline points="{}" stroke="#9333ea" stroke-width="2.5" fill="none"/>'.format(pts_ein))
for t, analog, trim, mask, ein in mapping:
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2" fill="#9333ea"/>'.format(sx(t), sy_ein(ein)))

# EIN value annotations at key points
ein_0 = mapping[0][4]
ein_mid = mapping[len(mapping)//2][4]
ein_max = mapping[-1][4]
svg.append('<text x="{:.1f}" y="{:.1f}" fill="#9333ea" font-size="10" text-anchor="middle">{:.1f}</text>'.format(
    sx(0), sy_ein(ein_0) - 8, ein_0))
svg.append('<text x="{:.1f}" y="{:.1f}" fill="#9333ea" font-size="10" text-anchor="middle">{:.1f}</text>'.format(
    sx(len(mapping)//2), sy_ein(ein_mid) - 8, ein_mid))
svg.append('<text x="{:.1f}" y="{:.1f}" fill="#9333ea" font-size="10" text-anchor="middle">{:.1f}</text>'.format(
    sx(max_db_int), sy_ein(ein_max) - 8, ein_max))

# Legend
LX = ML + PW + 10
LY = MT + 20
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#16a34a" stroke-width="2.5"/>'.format(LX, LY, LX+25, LY))
svg.append('<circle cx="{}" cy="{}" r="2.5" fill="#16a34a"/>'.format(LX+12, LY))
svg.append('<text x="{}" y="{}">Combined</text>'.format(LX+30, LY+4))

LY += 22
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#2563eb" stroke-width="1.5" opacity="0.6"/>'.format(LX, LY, LX+25, LY))
svg.append('<circle cx="{}" cy="{}" r="3" fill="#2563eb" opacity="0.5"/>'.format(LX+12, LY))
svg.append('<text x="{}" y="{}">Analog only</text>'.format(LX+30, LY+4))

LY += 22
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#ddd" stroke-width="1.5" stroke-dasharray="6,4"/>'.format(LX, LY, LX+25, LY))
svg.append('<text x="{}" y="{}">Ideal (y=x)</text>'.format(LX+30, LY+4))

LY += 22
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#16a34a" stroke-width="1" opacity="0.4"/>'.format(LX+5, LY-5, LX+5, LY+5))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#dc2626" stroke-width="1" opacity="0.4"/>'.format(LX+15, LY-5, LX+15, LY+5))
svg.append('<text x="{}" y="{}">DSP trim</text>'.format(LX+30, LY+4))

LY += 22
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#9333ea" stroke-width="2.5"/>'.format(LX, LY, LX+25, LY))
svg.append('<circle cx="{}" cy="{}" r="2" fill="#9333ea"/>'.format(LX+12, LY))
svg.append('<text x="{}" y="{}" fill="#9333ea">EIN (dBu)</text>'.format(LX+30, LY+4))

LY += 30
svg.append('<text x="{}" y="{}" class="subtitle">Max gap: {:.1f} dB</text>'.format(LX, LY, max(dbs[i+1]-dbs[i] for i in range(len(dbs)-1))))
LY += 16
svg.append('<text x="{}" y="{}" class="subtitle">Max trim: {:.1f} dB</text>'.format(LX, LY, max(abs(m[2]) for m in mapping)))
LY += 16
svg.append('<text x="{}" y="{}" class="subtitle">Range: 0-{} dB</text>'.format(LX, LY, max_db_int))
LY += 16
svg.append('<text x="{}" y="{}" class="subtitle" fill="#9333ea">EIN: {:.1f} to {:.1f}</text>'.format(LX, LY, max(ein_values), min(ein_values)))

svg.append('</svg>')

with open("gain_combined.svg", "w") as f:
    f.write("\n".join(svg))
print("Written: gain_combined.svg")
