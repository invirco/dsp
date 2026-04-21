#!/usr/bin/env python3
"""Single graph: analog, digital (DSP trim), and combined gain from 0-60dB."""
import math

Rf = 4990.0
Rds = 3.0
R = [15.0, 37.4, 93.1, 232.0, 590.0, 1470.0]

out = []
for m in range(64):
    G = sum(1.0 / (R[i] + Rds) for i in range(6) if m & (1 << i))
    db = 20 * math.log10(1 + Rf * G) if G > 0 else 0.0
    out.append((db, m))
out.sort()
dbs = [g[0] for g in out]

# 1dB mapping 0-60
mapping = []
for t in range(61):
    bi = min(range(len(out)), key=lambda j: abs(out[j][0] - t))
    analog = out[bi][0]
    trim = t - analog
    mapping.append((t, analog, trim, t))  # target, analog, dsp_trim, combined

W, H = 950, 520
ML, MR, MT, MB = 80, 150, 50, 60
PW = W - ML - MR
PH = H - MT - MB
YMAX = 65.0
XMAX = 60.0

def sx(v):
    return ML + v / XMAX * PW

def sy(v):
    return MT + PH - v / YMAX * PH

svg = []
svg.append('<?xml version="1.0" encoding="UTF-8"?>')
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}">'.format(W, H))
svg.append('<style>')
svg.append('  text {{ font-family: "Helvetica Neue", monospace; font-size: 12px; fill: #333; }}')
svg.append('  .title {{ font-size: 16px; font-weight: bold; }}')
svg.append('  .sub {{ font-size: 11px; fill: #666; }}')
svg.append('</style>')
svg.append('<rect width="100%" height="100%" fill="white"/>')

# Title
svg.append('<text x="{}" y="22" class="title">Mic Preamp Gain: Analog + DSP Trim + Combined Output (0-60 dB)</text>'.format(ML))
svg.append('<text x="{}" y="38" class="sub">Rf=4K99 | R: 1K47, 590R, 232R, 93R1, 37R4, 15R | 2N7002 (Rds~3R)</text>'.format(ML))

# Grid
for g in range(0, 66, 5):
    y = sy(g)
    w = "0.5" if g % 10 else "0.8"
    c = "#eee" if g % 10 else "#ccc"
    svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="{}" stroke-width="{}"/>'.format(ML, y, ML+PW, y, c, w))
    if g % 10 == 0:
        svg.append('<text x="{}" y="{:.1f}" text-anchor="end">{}</text>'.format(ML-5, y+4, g))

for g in range(0, 61, 5):
    x = sx(g)
    w = "0.5" if g % 10 else "0.8"
    c = "#eee" if g % 10 else "#ccc"
    svg.append('<line x1="{:.1f}" y1="{}" x2="{:.1f}" y2="{}" stroke="{}" stroke-width="{}"/>'.format(x, MT, x, MT+PH, c, w))
    if g % 10 == 0:
        svg.append('<text x="{:.1f}" y="{}" text-anchor="middle">{}</text>'.format(x, MT+PH+15, g))

# Axes
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#333" stroke-width="1.5"/>'.format(ML, MT, ML, MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#333" stroke-width="1.5"/>'.format(ML, MT+PH, ML+PW, MT+PH))
svg.append('<text x="{:.0f}" y="{}" text-anchor="middle" font-size="13">Target Gain (dB)</text>'.format(ML + PW/2, MT+PH+40))
svg.append('<text x="{}" y="{:.0f}" text-anchor="middle" transform="rotate(-90,{},{:.0f})" font-size="13">Gain (dB)</text>'.format(ML-55, MT+PH/2, ML-55, MT+PH/2))

# Ideal line
svg.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="6,4"/>'.format(
    sx(0), sy(0), sx(60), sy(60)))

# --- Analog gain (blue) ---
pts_a = " ".join("{:.1f},{:.1f}".format(sx(t), sy(analog)) for t, analog, trim, combined in mapping)
svg.append('<polyline points="{}" stroke="#2563eb" stroke-width="2" fill="none"/>'.format(pts_a))
for t, analog, trim, combined in mapping:
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2.5" fill="#2563eb" opacity="0.6"/>'.format(sx(t), sy(analog)))

# --- DSP trim (orange) ---
pts_d = " ".join("{:.1f},{:.1f}".format(sx(t), sy(trim)) for t, analog, trim, combined in mapping)
svg.append('<polyline points="{}" stroke="#ea580c" stroke-width="2" fill="none"/>'.format(pts_d))
for t, analog, trim, combined in mapping:
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2" fill="#ea580c" opacity="0.6"/>'.format(sx(t), sy(trim)))

# Zero line for DSP reference
svg.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="#ea580c" stroke-width="0.5" stroke-dasharray="3,3" opacity="0.4"/>'.format(
    sx(0), sy(0), sx(60), sy(0)))

# --- Combined (green) ---
pts_c = " ".join("{:.1f},{:.1f}".format(sx(t), sy(combined)) for t, analog, trim, combined in mapping)
svg.append('<polyline points="{}" stroke="#16a34a" stroke-width="2.5" fill="none"/>'.format(pts_c))
for t, analog, trim, combined in mapping:
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2.5" fill="#16a34a"/>'.format(sx(t), sy(combined)))

# Legend
LX = ML + PW + 15
LY = MT + 20

items = [
    ("#16a34a", 2.5, "Combined", "(analog+DSP)"),
    ("#2563eb", 2.0, "Analog only", "(switched R)"),
    ("#ea580c", 2.0, "DSP trim", "(digital)"),
    ("#e0e0e0", 1.0, "Ideal", "(y = x)"),
]
for color, sw, label, sub in items:
    da = ' stroke-dasharray="6,4"' if color == "#e0e0e0" else ""
    svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" stroke-width="{}"{} />'.format(LX, LY, LX+25, LY, color, sw, da))
    svg.append('<circle cx="{}" cy="{}" r="2.5" fill="{}"/>'.format(LX+12, LY, color))
    svg.append('<text x="{}" y="{}">{}</text>'.format(LX+32, LY+4, label))
    svg.append('<text x="{}" y="{}" class="sub">{}</text>'.format(LX+32, LY+16, sub))
    LY += 35

# Stats
LY += 15
max_trim = max(abs(m[2]) for m in mapping)
max_gap = max(dbs[i+1]-dbs[i] for i in range(len(dbs)-1))
svg.append('<text x="{}" y="{}" class="sub">Max analog gap: {:.1f} dB</text>'.format(LX, LY, max_gap))
LY += 16
svg.append('<text x="{}" y="{}" class="sub">Max DSP trim: {:.1f} dB</text>'.format(LX, LY, max_trim))
LY += 16
svg.append('<text x="{}" y="{}" class="sub">Analog range: 0-{:.1f} dB</text>'.format(LX, LY, dbs[-1]))
LY += 16
n_analog_only = sum(1 for t, a, tr, c in mapping if abs(tr) < 0.5)
svg.append('<text x="{}" y="{}" class="sub">Steps within 0.5dB: {}/61</text>'.format(LX, LY, n_analog_only))

svg.append('</svg>')

with open("gain_all.svg", "w") as f:
    f.write("\n".join(svg))
print("Written: gain_all.svg")
print("Analog range: 0 - {:.1f} dB".format(dbs[-1]))
print("Max gap: {:.1f} dB, Max DSP trim: {:.1f} dB".format(max_gap, max_trim))
