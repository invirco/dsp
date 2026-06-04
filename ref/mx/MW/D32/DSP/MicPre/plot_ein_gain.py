#!/usr/bin/env python3
"""Generate SVG plot: EIN + Headroom vs Total Gain (0–60 dB) for 3-step relay + AK4619 topology."""

import math

# === Constants ===
SOURCE_R = 150          # ohm
EN_SOURCE = 1.58        # nV/√Hz (150 Ω thermal)
EN_DIFF = 0.95          # nV/√Hz (DMMT3904W, current mirror, cascode)
EN_ADC = 35.0           # nV/√Hz (AK4619)
BW = 19980              # Hz (20–20k)
REF_DBU = 0.7746        # V (0 dBu)

# Analog gain steps (linear, dB)
# Max output swing for each: ×4→+16dBu, ×10→+8dBu, ×40→-4dBu (3.3V supply, ±0.5Vrms)
STEPS = [
    (4,   12, 16, "#e74c3c", "×4 (12 dB) — R2=470R"),     # red
    (10,  20,  8, "#f39c12", "×10 (20 dB) — R1=150R"),    # orange
    (40,  32, -4, "#27ae60", "×40 (32 dB) — 0R"),         # green
]
#       ^lin ^dB ^max_in  ^color    ^label

# AK4619 digital range
DIG_MIN = -12   # dB (below this = mute)
DIG_MAX = 36    # dB

# === SVG layout ===
W, H = 960, 540
ML, MR, MT, MB = 80, 80, 60, 70   # margins (MR wider for right y-axis, MT for subtitle)
PW = W - ML - MR   # plot width
PH = H - MT - MB   # plot height

# Axes ranges
X_MIN, X_MAX = 0, 60       # total gain dB
Y_MIN, Y_MAX = -130, -110  # EIN dBu (left axis)
H_MIN, H_MAX = -10, 20     # Headroom dBu (right axis)

def x_px(db):
    return ML + (db - X_MIN) / (X_MAX - X_MIN) * PW

def y_px(ein):
    return MT + (Y_MAX - ein) / (Y_MAX - Y_MIN) * PH

def h_px(hdr):
    return MT + (H_MAX - hdr) / (H_MAX - H_MIN) * PH

def calc_ein(analog_linear):
    adc_referred = EN_ADC / analog_linear
    en_total = math.sqrt(EN_SOURCE**2 + EN_DIFF**2 + adc_referred**2)
    noise_v = en_total * 1e-9 * math.sqrt(BW)
    return 20 * math.log10(noise_v / REF_DBU)

# === Assign analog gain for each total gain step ===
points = []  # (total_gain_dB, ein_dBu, step_index, max_input_dBu)
for total in range(X_MIN, X_MAX + 1):
    # Pick highest analog gain whose digital offset is within AK4619 range
    best = None
    for i, (g_lin, g_db, max_in, color, label) in enumerate(STEPS):
        digital = total - g_db
        if DIG_MIN <= digital <= DIG_MAX:
            best = i  # higher i = higher analog gain = better EIN
    if best is None:
        best = 0  # fallback to lowest
    g_lin = STEPS[best][0]
    max_in = STEPS[best][2]
    ein = calc_ein(g_lin)
    points.append((total, ein, best, max_in))

# === Build SVG ===
svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Arial, sans-serif">')
svg.append('<style>')
svg.append('  .title { font-size: 15px; font-weight: bold; fill: #222; }')
svg.append('  .subtitle { font-size: 12px; fill: #555; }')
svg.append('  .axis-label { font-size: 13px; fill: #333; }')
svg.append('  .tick-label { font-size: 11px; fill: #555; }')
svg.append('  .legend-text { font-size: 12px; fill: #333; }')
svg.append('  .grid { stroke: #e0e0e0; stroke-width: 0.5; }')
svg.append('  .axis { stroke: #333; stroke-width: 1.5; fill: none; }')
svg.append('  .annotation { font-size: 10px; fill: #666; }')
svg.append('</style>')

# Background
svg.append(f'<rect width="{W}" height="{H}" fill="white" rx="4"/>')

# Title
svg.append(f'<text x="{W/2}" y="24" class="title" text-anchor="middle">'
           f'EIN vs Total Gain — 3-Step Relay + AK4619 (Topology D)</text>')
svg.append(f'<text x="{W/2}" y="40" class="subtitle" text-anchor="middle">'
           f'2 relays, 2 independent emitter degeneration resistors: R1 = 150R (×10), R2 = 470R (×4), both bypassed = ×40</text>')

# Grid lines — horizontal (EIN)
for ein in range(-130, -109, 2):
    y = y_px(ein)
    if MT <= y <= MT + PH:
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML+PW}" y2="{y:.1f}" class="grid"/>')
        svg.append(f'<text x="{ML-8}" y="{y+4:.1f}" class="tick-label" text-anchor="end">{ein}</text>')

# Grid lines — vertical (gain)
for g in range(0, 61, 5):
    x = x_px(g)
    svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+PH}" class="grid"/>')
    svg.append(f'<text x="{x:.1f}" y="{MT+PH+16}" class="tick-label" text-anchor="middle">{g}</text>')

# Axes
svg.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+PH}" class="axis"/>')
svg.append(f'<line x1="{ML}" y1="{MT+PH}" x2="{ML+PW}" y2="{MT+PH}" class="axis"/>')

# Axis labels
svg.append(f'<text x="{W/2}" y="{H-12}" class="axis-label" text-anchor="middle">Total Gain (dB)</text>')
svg.append(f'<text x="18" y="{H/2}" class="axis-label" text-anchor="middle" '
           f'transform="rotate(-90 18 {H/2})">EIN (dBu) — 150 Ω, 20 Hz–20 kHz</text>')

# === Draw colored EIN regions ===
# Draw filled regions behind the line for each analog step
segments = []  # group consecutive points by step
current_seg = [points[0]]
for p in points[1:]:
    if p[2] == current_seg[-1][2]:
        current_seg.append(p)
    else:
        segments.append(current_seg)
        current_seg = [p]
segments.append(current_seg)

for seg in segments:
    step_idx = seg[0][2]
    color = STEPS[step_idx][3]
    # Fill band
    x1 = x_px(seg[0][0])
    x2 = x_px(seg[-1][0])
    y_ein = y_px(seg[0][1])
    svg.append(f'<rect x="{x1:.1f}" y="{y_ein:.1f}" width="{x2-x1:.1f}" '
               f'height="{MT+PH-y_ein:.1f}" fill="{color}" opacity="0.12" />')

# === Draw EIN line ===
# Build path
path_parts = []
for i, (total, ein, step_idx, _max_in) in enumerate(points):
    x = x_px(total)
    y = y_px(ein)
    cmd = "M" if i == 0 else "L"
    # Check for step transition
    if i > 0 and points[i][2] != points[i-1][2]:
        # End previous color segment, start new
        prev_color = STEPS[points[i-1][2]][3]
        svg.append(f'<path d="{" ".join(path_parts)}" fill="none" stroke="{prev_color}" stroke-width="3"/>')
        # Vertical transition line
        y_prev = y_px(points[i-1][1])
        svg.append(f'<line x1="{x:.1f}" y1="{y_prev:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                   f'stroke="#999" stroke-width="1.5" stroke-dasharray="4,3"/>')
        path_parts = [f"M {x:.1f} {y:.1f}"]
    else:
        path_parts.append(f"{cmd} {x:.1f} {y:.1f}")
# Final segment
last_color = STEPS[points[-1][2]][3]
svg.append(f'<path d="{" ".join(path_parts)}" fill="none" stroke="{last_color}" stroke-width="3"/>')

# === Annotate EIN values on each plateau ===
for seg in segments:
    mid_gain = (seg[0][0] + seg[-1][0]) / 2
    ein = seg[0][1]
    step_idx = seg[0][2]
    color = STEPS[step_idx][3]
    label = STEPS[step_idx][4]
    x = x_px(mid_gain)
    y = y_px(ein) - 12
    svg.append(f'<text x="{x:.1f}" y="{y:.1f}" class="axis-label" text-anchor="middle" '
               f'fill="{color}" font-weight="bold">{ein:.1f} dBu</text>')
    svg.append(f'<text x="{x:.1f}" y="{y+15:.1f}" class="annotation" text-anchor="middle" '
               f'fill="{color}">{label}</text>')

# === Mark transition points ===
transitions = []
for i in range(1, len(points)):
    if points[i][2] != points[i-1][2]:
        transitions.append(points[i][0])

for t_gain in transitions:
    x = x_px(t_gain)
    svg.append(f'<line x1="{x:.1f}" y1="{MT+PH}" x2="{x:.1f}" y2="{MT+PH+6}" stroke="#999" stroke-width="1"/>')
    svg.append(f'<text x="{x:.1f}" y="{MT+PH+30}" class="annotation" text-anchor="middle">↑ relay switch</text>')

# === Max input level annotation bar at top ===
max_inputs = [
    (0, 7, "+16 dBu max in", "#e74c3c"),
    (8, 19, "+8 dBu max in", "#f39c12"),
    (20, 60, "−4 dBu max in", "#27ae60"),
]
for g_start, g_end, label, color in max_inputs:
    x1 = x_px(g_start)
    x2 = x_px(g_end)
    y = MT - 8
    svg.append(f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{color}" stroke-width="3" />')
    mid = (x1 + x2) / 2
    svg.append(f'<text x="{mid:.1f}" y="{y-5}" class="annotation" text-anchor="middle" fill="{color}">{label}</text>')

# === Legend ===
lx = ML + PW - 200
ly = MT + 18
svg.append(f'<rect x="{lx-8}" y="{ly-14}" width="210" height="80" fill="white" stroke="#ccc" rx="4"/>')
for i, (g_lin, g_db, max_in, color, label) in enumerate(STEPS):
    yy = ly + i * 20
    svg.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+25}" y2="{yy}" stroke="{color}" stroke-width="3"/>')
    svg.append(f'<text x="{lx+32}" y="{yy+4}" class="legend-text">{label} analog</text>')
# Digital note
svg.append(f'<text x="{lx}" y="{ly + len(STEPS) * 20 + 6}" class="annotation">AK4619 digital: 0.5 dB steps throughout</text>')

# === Relay state table ===
tx = ML + 10
ty = MT + PH - 60
svg.append(f'<rect x="{tx-4}" y="{ty-14}" width="180" height="60" fill="white" fill-opacity="0.9" stroke="#ccc" rx="3"/>')
svg.append(f'<text x="{tx}" y="{ty}" class="annotation" font-weight="bold">Relay state (emitter degeneration):</text>')
relay_states = [
    ("R1 in (150R), R2 bypassed", "×10", "#f39c12"),
    ("R1 bypassed, R2 in (470R)", "×4", "#e74c3c"),
    ("Both bypassed (0R)", "×40", "#27ae60"),
]
for i, (state, gain, color) in enumerate(relay_states):
    yy = ty + 14 + i * 14
    svg.append(f'<rect x="{tx}" y="{yy-8}" width="8" height="8" fill="{color}"/>')
    svg.append(f'<text x="{tx+12}" y="{yy}" class="annotation">{state} → {gain}</text>')

# === Footer note ===
svg.append(f'<text x="{ML}" y="{H-4}" class="annotation">'
           f'150 Ω source · DMMT3904W diff pair · current mirror + cascode · AK4619 ADC (35 nV/√Hz) · '
           f'R1 = 150R, R2 = 470R (independent, each with relay bypass) · '
           f'Digital: −12 to +36 dB (0.5 dB steps)</text>')

svg.append('</svg>')

# Write
outpath = "/home/peter/Stonepower Dropbox/Peter Watts/VSCODE/MicPre/ein_vs_gain_3step.svg"
with open(outpath, "w") as f:
    f.write("\n".join(svg))
print(f"Written to {outpath}")
