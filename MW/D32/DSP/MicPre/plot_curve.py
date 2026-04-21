#!/usr/bin/env python3
"""Generate SVG line plots for mic preamp gain curve."""
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
gaps = [dbs[i+1] - dbs[i] for i in range(len(dbs)-1)]

# 1dB mapping
max_db_int = int(dbs[-1])
mapping = []
for t in range(max_db_int + 1):
    bi = min(range(len(out)), key=lambda j: abs(out[j][0] - t))
    trim = t - out[bi][0]
    mapping.append((t, out[bi][0], trim))

# SVG dimensions
W, H = 800, 400
ML, MR, MT, MB = 70, 30, 30, 50  # margins
PW = W - ML - MR
PH = H - MT - MB

def sx(v, vmin, vmax):
    return ML + (v - vmin) / (vmax - vmin) * PW

def sy(v, vmin, vmax):
    return MT + PH - (v - vmin) / (vmax - vmin) * PH

svg = []
svg.append('<?xml version="1.0" encoding="UTF-8"?>')
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(W, H*3+60, W, H*3+60))
svg.append('<style>')
svg.append('  text { font-family: monospace; font-size: 12px; fill: #333; }')
svg.append('  .title { font-size: 16px; font-weight: bold; }')
svg.append('  .axis { stroke: #333; stroke-width: 1; }')
svg.append('  .grid { stroke: #ddd; stroke-width: 0.5; }')
svg.append('  .line1 { stroke: #2563eb; stroke-width: 2; fill: none; }')
svg.append('  .line2 { stroke: #dc2626; stroke-width: 2; fill: none; }')
svg.append('  .line3 { stroke: #16a34a; stroke-width: 2; fill: none; }')
svg.append('  .dot { fill: #2563eb; }')
svg.append('</style>')
svg.append('<rect width="100%" height="100%" fill="white"/>')

# --- Plot 1: Gain curve ---
y_off = 0
svg.append('<text x="{}" y="{}" class="title">Analog Gain vs Step (R: 1K47, 590R, 232R, 93R1, 37R4, 15R  |  Rf=4K99)</text>'.format(ML, y_off + 20))

# Grid
for g in range(0, int(dbs[-1]) + 10, 10):
    if g > dbs[-1]:
        break
    y = sy(g, 0, dbs[-1]) + y_off
    svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="grid"/>'.format(ML, y, ML+PW, y))
    svg.append('<text x="{}" y="{}" text-anchor="end">{} dB</text>'.format(ML-5, y+4, g))

for s in range(0, 64, 8):
    x = sx(s, 0, 63)
    svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="grid"/>'.format(x, y_off+MT, x, y_off+MT+PH))
    svg.append('<text x="{}" y="{}" text-anchor="middle">{}</text>'.format(x, y_off+MT+PH+15, s))

# Axes
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT, ML, y_off+MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT+PH, ML+PW, y_off+MT+PH))
svg.append('<text x="{}" y="{}" text-anchor="middle">Step #</text>'.format(ML + PW/2, y_off+MT+PH+35))

# Line
pts = " ".join("{:.1f},{:.1f}".format(sx(i, 0, 63), sy(d, 0, dbs[-1]) + y_off) for i, d in enumerate(dbs))
svg.append('<polyline points="{}" class="line1"/>'.format(pts))

# Dots
for i, d in enumerate(dbs):
    svg.append('<circle cx="{:.1f}" cy="{:.1f}" r="2.5" class="dot"/>'.format(sx(i, 0, 63), sy(d, 0, dbs[-1]) + y_off))

# --- Plot 2: Gap distribution ---
y_off = H + 20
mg = max(gaps)
svg.append('<text x="{}" y="{}" class="title">Gap Between Adjacent Steps (max = {:.1f} dB)</text>'.format(ML, y_off + 20, mg))

for g_val in range(0, int(mg) + 2, 2):
    if g_val > mg:
        break
    y = sy(g_val, 0, mg) + y_off
    svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="grid"/>'.format(ML, y, ML+PW, y))
    svg.append('<text x="{}" y="{}" text-anchor="end">{} dB</text>'.format(ML-5, y+4, g_val))

svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT, ML, y_off+MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT+PH, ML+PW, y_off+MT+PH))
svg.append('<text x="{}" y="{}" text-anchor="middle">Step #</text>'.format(ML + PW/2, y_off+MT+PH+35))

pts = " ".join("{:.1f},{:.1f}".format(sx(i, 0, len(gaps)-1), sy(g, 0, mg) + y_off) for i, g in enumerate(gaps))
svg.append('<polyline points="{}" class="line2"/>'.format(pts))

# Bars for gaps
bar_w = PW / len(gaps) * 0.6
for i, g in enumerate(gaps):
    x = sx(i, 0, len(gaps)-1)
    y_top = sy(g, 0, mg) + y_off
    y_bot = sy(0, 0, mg) + y_off
    svg.append('<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" fill="#dc2626" opacity="0.3"/>'.format(
        x - bar_w/2, y_top, bar_w, y_bot - y_top))

# --- Plot 3: DSP trim ---
y_off = H * 2 + 40
trims = [m[2] for m in mapping]
mt = max(abs(t) for t in trims)

svg.append('<text x="{}" y="{}" class="title">DSP Trim per 1 dB Target Step (max = {:.1f} dB)</text>'.format(ML, y_off + 20, mt))

for g_val in range(-int(mt)-1, int(mt)+2):
    if abs(g_val) > mt + 1:
        continue
    y = sy(g_val, -mt, mt) + y_off
    svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="grid"/>'.format(ML, y, ML+PW, y))
    svg.append('<text x="{}" y="{}" text-anchor="end">{:+d} dB</text>'.format(ML-5, y+4, g_val))

# Zero line
y_zero = sy(0, -mt, mt) + y_off
svg.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#999" stroke-width="1" stroke-dasharray="4,4"/>'.format(ML, y_zero, ML+PW, y_zero))

svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT, ML, y_off+MT+PH))
svg.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(ML, y_off+MT+PH, ML+PW, y_off+MT+PH))
svg.append('<text x="{}" y="{}" text-anchor="middle">Target Gain (dB)</text>'.format(ML + PW/2, y_off+MT+PH+35))

pts = " ".join("{:.1f},{:.1f}".format(sx(m[0], 0, max_db_int), sy(m[2], -mt, mt) + y_off) for m in mapping)
svg.append('<polyline points="{}" class="line3"/>'.format(pts))

# Target labels
for s in range(0, max_db_int + 1, 10):
    x = sx(s, 0, max_db_int)
    svg.append('<line x1="{:.1f}" y1="{}" x2="{:.1f}" y2="{}" class="grid"/>'.format(x, y_off+MT, x, y_off+MT+PH))
    svg.append('<text x="{:.1f}" y="{}" text-anchor="middle">{}</text>'.format(x, y_off+MT+PH+15, s))

svg.append('</svg>')

with open("gain_curve.svg", "w") as f:
    f.write("\n".join(svg))
print("Written: gain_curve.svg")
