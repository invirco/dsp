#!/usr/bin/env python3
"""Generate SVG plot: EIN vs Total Gain — 4-step + AK4619.
5V supply, 470R/680R output divider, optional −20 dB input pad."""

import math

# === Constants ===
EN_SOURCE = 1.58        # nV/√Hz (150 Ω thermal)
EN_DIFF = 0.95          # nV/√Hz (DMMT3904W, current mirror, cascode)
EN_ADC = 35.0           # nV/√Hz (AK4619)
BW = 19980              # Hz (20–20k)
REF_DBU = 0.7746        # V (0 dBu)

# Output divider: R17/R18=470R series, R19/R20=680R shunt to VCOM
DIVIDER_RATIO = 680 / (470 + 680)   # 0.591
DIVIDER_DB = 20 * math.log10(DIVIDER_RATIO)  # −4.6 dB

# Input pad: R_S=1K5 series, R_SH=150R shunt → −20.8 dB
PAD_ATTEN = 150 / (1500 + 150)     # 0.0909
PAD_DB = 20 * math.log10(PAD_ATTEN)  # −20.8 dB
EN_PAD = math.sqrt(4 * 1.38e-23 * 298 * 136) * 1e9  # ~1.50 nV/√Hz

# 5V supply → max preamp diff output ≈ 0 dBu (1.0 Vrms)
MAX_OUT_DBU = 0

# 4 analog gain steps (preamp gain before divider)
# max_in = MAX_OUT_DBU − preamp_gain_dB (at mic input, pad OFF)
STEPS = [
    (2.5,   8, -8,  "#9b59b6", "×2.5 (8 dB)"),    # purple — both R in
    (4,    12, -12, "#e74c3c", "×4 (12 dB)"),       # red — R_B only
    (10,   20, -20, "#f39c12", "×10 (20 dB)"),      # orange — R_A only
    (40,   32, -32, "#27ae60", "×40 (32 dB)"),      # green — both bypassed
]

DIG_MIN = -12
DIG_MAX = 36

# === SVG layout ===
W, H = 960, 780
ML, MR, MT, MB = 80, 80, 80, 120
PW = W - ML - MR
PH = H - MT - MB

X_MIN, X_MAX = -10, 65
Y_MIN, Y_MAX = -130, -108

def x_px(db):
    return ML + (db - X_MIN) / (X_MAX - X_MIN) * PW

def y_px(ein):
    return MT + (Y_MAX - ein) / (Y_MAX - Y_MIN) * PH

def calc_ein(preamp_linear):
    """EIN in dBu referred to mic input (pad OFF). Includes divider."""
    g_eff = preamp_linear * DIVIDER_RATIO
    adc_referred = EN_ADC / g_eff
    en_total = math.sqrt(EN_SOURCE**2 + EN_DIFF**2 + adc_referred**2)
    noise_v = en_total * 1e-9 * math.sqrt(BW)
    return 20 * math.log10(noise_v / REF_DBU)

def calc_ein_pad(preamp_linear):
    """EIN in dBu referred to mic input (pad ON). Includes divider + pad."""
    g_eff = preamp_linear * DIVIDER_RATIO
    en_pad_ref = EN_PAD / PAD_ATTEN
    en_diff_ref = EN_DIFF / PAD_ATTEN
    en_adc_ref = EN_ADC / (g_eff * PAD_ATTEN)
    en_total = math.sqrt(EN_SOURCE**2 + en_pad_ref**2 + en_diff_ref**2 + en_adc_ref**2)
    noise_v = en_total * 1e-9 * math.sqrt(BW)
    return 20 * math.log10(noise_v / REF_DBU)

# === Assign best analog gain for each 1 dB total gain step ===
# Total gain = effective_analog_dB + digital_dB
# effective_analog_dB = preamp_dB + DIVIDER_DB
points = []
for total in range(X_MIN, X_MAX + 1):
    best = None
    for i, (g_lin, g_db, max_in, color, label) in enumerate(STEPS):
        g_eff_db = g_db + DIVIDER_DB
        digital = total - g_eff_db
        if DIG_MIN <= digital <= DIG_MAX:
            best = i
    if best is None:
        continue
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
svg.append('  .legend-text { font-size: 11px; fill: #333; }')
svg.append('  .grid { stroke: #e0e0e0; stroke-width: 0.5; }')
svg.append('  .axis { stroke: #333; stroke-width: 1.5; fill: none; }')
svg.append('  .annotation { font-size: 10px; fill: #666; }')
svg.append('</style>')

svg.append(f'<rect width="{W}" height="{H}" fill="white" rx="4"/>')

# Title
svg.append(f'<text x="{W/2}" y="24" class="title" text-anchor="middle">'
           f'EIN vs Total Gain — 4-Step + AK4619 (5V Supply + Output Divider)</text>')
svg.append(f'<text x="{W/2}" y="40" class="subtitle" text-anchor="middle">'
           f'R_A=150R, R_B=470R emitter degen · 470R/680R output divider ({DIVIDER_DB:.1f} dB) · Relay C: −20 dB input pad</text>')

# Grid — horizontal
for ein in range(-130, -107, 2):
    y = y_px(ein)
    if MT <= y <= MT + PH:
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML+PW}" y2="{y:.1f}" class="grid"/>')
        svg.append(f'<text x="{ML-8}" y="{y+4:.1f}" class="tick-label" text-anchor="end">{ein}</text>')

# Grid — vertical
for g in range(X_MIN, X_MAX + 1, 5):
    x = x_px(g)
    svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+PH}" class="grid"/>')
    svg.append(f'<text x="{x:.1f}" y="{MT+PH+16}" class="tick-label" text-anchor="middle">{g}</text>')

# 0 dB reference line
x0 = x_px(0)
svg.append(f'<line x1="{x0:.1f}" y1="{MT}" x2="{x0:.1f}" y2="{MT+PH}" stroke="#333" stroke-width="1" stroke-dasharray="6,3"/>')

# Axes
svg.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+PH}" class="axis"/>')
svg.append(f'<line x1="{ML}" y1="{MT+PH}" x2="{ML+PW}" y2="{MT+PH}" class="axis"/>')
svg.append(f'<line x1="{ML+PW}" y1="{MT}" x2="{ML+PW}" y2="{MT+PH}" class="axis"/>')

# Axis labels
svg.append(f'<text x="{W/2}" y="{MT+PH+34}" class="axis-label" text-anchor="middle">Total Gain (dB)</text>')
svg.append(f'<text x="18" y="{H/2}" class="axis-label" text-anchor="middle" '
           f'transform="rotate(-90 18 {H/2})">EIN (dBu) — 150 Ω, 20 Hz–20 kHz</text>')

# === Colored EIN regions ===
segments = []
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
    x1 = x_px(seg[0][0])
    x2 = x_px(seg[-1][0])
    y_ein = y_px(seg[0][1])
    svg.append(f'<rect x="{x1:.1f}" y="{y_ein:.1f}" width="{x2-x1:.1f}" '
               f'height="{MT+PH-y_ein:.1f}" fill="{color}" opacity="0.12" />')

# === EIN line (colored by segment) ===
path_parts = []
for i, (total, ein, step_idx, max_in) in enumerate(points):
    x = x_px(total)
    y = y_px(ein)
    cmd = "M" if i == 0 else "L"
    if i > 0 and points[i][2] != points[i-1][2]:
        prev_color = STEPS[points[i-1][2]][3]
        svg.append(f'<path d="{" ".join(path_parts)}" fill="none" stroke="{prev_color}" stroke-width="3"/>')
        y_prev = y_px(points[i-1][1])
        svg.append(f'<line x1="{x:.1f}" y1="{y_prev:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                   f'stroke="#999" stroke-width="1.5" stroke-dasharray="4,3"/>')
        path_parts = [f"M {x:.1f} {y:.1f}"]
    else:
        path_parts.append(f"{cmd} {x:.1f} {y:.1f}")
last_color = STEPS[points[-1][2]][3]
svg.append(f'<path d="{" ".join(path_parts)}" fill="none" stroke="{last_color}" stroke-width="3"/>')

# === Headroom line (dashed, right axis) ===
HR_MIN, HR_MAX = -35, 0
hr_path = []
for i, (total, ein, step_idx, max_in) in enumerate(points):
    x = x_px(total)
    y = MT + (HR_MAX - max_in) / (HR_MAX - HR_MIN) * PH
    cmd = "M" if i == 0 else "L"
    if i > 0 and points[i][2] != points[i-1][2]:
        svg.append(f'<path d="{" ".join(hr_path)}" fill="none" stroke="#3498db" stroke-width="2" stroke-dasharray="8,4"/>')
        y_prev_hr = MT + (HR_MAX - points[i-1][3]) / (HR_MAX - HR_MIN) * PH
        svg.append(f'<line x1="{x:.1f}" y1="{y_prev_hr:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                   f'stroke="#3498db" stroke-width="1" stroke-dasharray="3,3"/>')
        hr_path = [f"M {x:.1f} {y:.1f}"]
    else:
        hr_path.append(f"{cmd} {x:.1f} {y:.1f}")
svg.append(f'<path d="{" ".join(hr_path)}" fill="none" stroke="#3498db" stroke-width="2" stroke-dasharray="8,4"/>')

# Right axis ticks for headroom
svg.append(f'<text x="{W-18}" y="{H/2}" class="axis-label" text-anchor="middle" fill="#3498db" '
           f'transform="rotate(90 {W-18} {H/2})">Max Input (dBu)</text>')
for hdr in range(-35, 1, 5):
    y = MT + (HR_MAX - hdr) / (HR_MAX - HR_MIN) * PH
    if MT <= y <= MT + PH:
        svg.append(f'<line x1="{ML+PW}" y1="{y:.1f}" x2="{ML+PW+5}" y2="{y:.1f}" stroke="#3498db" stroke-width="1"/>')
        svg.append(f'<text x="{ML+PW+8}" y="{y+4:.1f}" class="tick-label" fill="#3498db">{hdr:+d}</text>')

# === EIN annotations per segment ===
ein_offsets = [30, 16, 30, 16]
for si, seg in enumerate(segments):
    mid_gain = (seg[0][0] + seg[-1][0]) / 2
    ein = seg[0][1]
    step_idx = seg[0][2]
    color = STEPS[step_idx][3]
    label = STEPS[step_idx][4]
    x = x_px(mid_gain)
    offset = ein_offsets[si % len(ein_offsets)]
    y = y_px(ein) + offset
    svg.append(f'<text x="{x:.1f}" y="{y:.1f}" class="axis-label" text-anchor="middle" '
               f'fill="{color}" font-weight="bold">{ein:.1f} dBu</text>')
    svg.append(f'<text x="{x:.1f}" y="{y+14:.1f}" class="annotation" text-anchor="middle" '
               f'fill="{color}">{label}</text>')

# === DNR annotations ===
# Stagger vertically along the arrow to avoid overlapping EIN text below
dnr_y_biases = [0.30, 0.50, 0.35, 0.55]  # fraction along arrow (0=hr end, 1=ein end)
for si, seg in enumerate(segments):
    step_idx = seg[0][2]
    color = STEPS[step_idx][3]
    ein = seg[0][1]
    max_in = seg[0][3]
    dnr = max_in - ein
    mid_gain = (seg[0][0] + seg[-1][0]) / 2
    x = x_px(mid_gain)
    y_ein_px = y_px(ein)
    y_hr_px = MT + (HR_MAX - max_in) / (HR_MAX - HR_MIN) * PH
    # Arrow line
    svg.append(f'<line x1="{x:.1f}" y1="{y_ein_px:.1f}" x2="{x:.1f}" y2="{y_hr_px:.1f}" '
               f'stroke="{color}" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>')
    ah = 4
    svg.append(f'<polygon points="{x-ah:.1f},{y_ein_px-ah:.1f} {x+ah:.1f},{y_ein_px-ah:.1f} {x:.1f},{y_ein_px:.1f}" '
               f'fill="{color}" opacity="0.6"/>')
    svg.append(f'<polygon points="{x-ah:.1f},{y_hr_px+ah:.1f} {x+ah:.1f},{y_hr_px+ah:.1f} {x:.1f},{y_hr_px:.1f}" '
               f'fill="{color}" opacity="0.6"/>')
    # Label centered on arrow, staggered vertically
    bias = dnr_y_biases[si % len(dnr_y_biases)]
    y_label = y_hr_px + bias * (y_ein_px - y_hr_px)
    svg.append(f'<rect x="{x-26:.1f}" y="{y_label-7:.1f}" width="52" height="14" fill="white" opacity="0.85" rx="2"/>')
    svg.append(f'<text x="{x:.1f}" y="{y_label+4:.1f}" class="annotation" text-anchor="middle" '
               f'fill="{color}" font-weight="bold">{dnr:.0f} dB DNR</text>')

# === Relay switch markers ===
for i in range(1, len(points)):
    if points[i][2] != points[i-1][2]:
        x = x_px(points[i][0])
        svg.append(f'<line x1="{x:.1f}" y1="{MT+PH}" x2="{x:.1f}" y2="{MT+PH+4}" stroke="#999" stroke-width="1"/>')
        svg.append(f'<text x="{x:.1f}" y="{MT+PH+42}" class="annotation" text-anchor="middle" fill="#999">relay</text>')

# === Max input bars at top ===
top_offsets = [-4, -16, -4, -16]
for si, seg in enumerate(segments):
    step_idx = seg[0][2]
    color = STEPS[step_idx][3]
    max_in = seg[0][3]
    x1 = x_px(seg[0][0])
    x2 = x_px(seg[-1][0])
    y = MT + top_offsets[si % len(top_offsets)]
    svg.append(f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="{color}" stroke-width="3" />')
    mid = (x1 + x2) / 2
    sign = "+" if max_in >= 0 else ""
    svg.append(f'<text x="{mid:.1f}" y="{y-5}" class="annotation" text-anchor="middle" fill="{color}">'
               f'{sign}{max_in} dBu max in</text>')

# === Legend === (upper-right, row 1)
BOX_W = 230
BOX_MARGIN = 20
lx = ML + PW - BOX_W - 10
ly = MT + 18
svg.append(f'<rect x="{lx-8}" y="{ly-14}" width="230" height="138" fill="white" stroke="#ccc" rx="4"/>')
for i, (g_lin, g_db, max_in, color, label) in enumerate(STEPS):
    yy = ly + i * 20
    svg.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+25}" y2="{yy}" stroke="{color}" stroke-width="3"/>')
    svg.append(f'<text x="{lx+32}" y="{yy+4}" class="legend-text">{label} analog</text>')
yy = ly + len(STEPS) * 20
svg.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+25}" y2="{yy}" stroke="#3498db" stroke-width="2" stroke-dasharray="6,3"/>')
svg.append(f'<text x="{lx+32}" y="{yy+4}" class="legend-text" fill="#3498db">Max input level (dBu)</text>')
yy2 = yy + 20
svg.append(f'<line x1="{lx+5}" y1="{yy2-4}" x2="{lx+5}" y2="{yy2+4}" stroke="#666" stroke-width="1" stroke-dasharray="3,2"/>')
svg.append(f'<polygon points="{lx+3},{yy2-2} {lx+7},{yy2-2} {lx+5},{yy2-5}" fill="#666"/>')
svg.append(f'<polygon points="{lx+3},{yy2+2} {lx+7},{yy2+2} {lx+5},{yy2+5}" fill="#666"/>')
svg.append(f'<text x="{lx+32}" y="{yy2+4}" class="legend-text">Dynamic range (DNR)</text>')
svg.append(f'<text x="{lx}" y="{yy2+18}" class="annotation">AK4619 digital: 0.5 dB steps throughout</text>')

# === Relay state table === (upper-right, row 2 — below legend)
RELAY_BOX_W = 175
tx = ML + PW - RELAY_BOX_W - 10
ty = ly - 14 + 138 + BOX_MARGIN
svg.append(f'<rect x="{tx-4}" y="{ty-14}" width="175" height="88" fill="white" fill-opacity="0.9" stroke="#ccc" rx="3"/>')
svg.append(f'<text x="{tx}" y="{ty}" class="annotation" font-weight="bold">Relay state (pad OFF):</text>')
relay_states = [
    ("Both open", "×2.5", "#9b59b6"),
    ("A closed, B open", "×4", "#e74c3c"),
    ("A open, B closed", "×10", "#f39c12"),
    ("Both closed", "×40", "#27ae60"),
]
for i, (state, gain, color) in enumerate(relay_states):
    yy = ty + 14 + i * 14
    svg.append(f'<rect x="{tx}" y="{yy-8}" width="8" height="8" fill="{color}"/>')
    svg.append(f'<text x="{tx+12}" y="{yy}" class="annotation">{state} → {gain}</text>')
yy_pad = ty + 14 + len(relay_states) * 14
svg.append(f'<text x="{tx}" y="{yy_pad}" class="annotation" fill="#636">Relay C: −20 dB pad</text>')

# === Pad ON annotation box === (upper-right, row 3 — below relay table)
PAD_BOX_W = 290
px = ML + PW - PAD_BOX_W - 10
py = ty - 14 + 88 + BOX_MARGIN
svg.append(f'<rect x="{px-4}" y="{py-14}" width="290" height="82" fill="white" fill-opacity="0.92" '
           f'stroke="#a3a" stroke-width="1.5" rx="4" stroke-dasharray="5,3"/>')
svg.append(f'<text x="{px}" y="{py}" class="annotation" font-weight="bold" fill="#636">'
           f'WITH −20 dB INPUT PAD (Relay C):</text>')
svg.append(f'<text x="{px}" y="{py+13}" class="annotation" fill="#636">'
           f'Adds +{abs(PAD_DB):.0f} dB headroom, EIN degrades ≈{abs(PAD_DB):.0f} dB</text>')

# Compute pad-ON numbers for best/worst cases
ein_pad_best = calc_ein_pad(40)   # ×40 = best EIN
ein_pad_worst = calc_ein_pad(2.5) # ×2.5 = worst EIN
max_in_best = -32 + abs(PAD_DB)   # ×40 pad ON
max_in_worst = -8 + abs(PAD_DB)   # ×2.5 pad ON

svg.append(f'<text x="{px}" y="{py+28}" class="annotation" fill="#27ae60">'
           f'×40 pad ON: EIN {ein_pad_best:.1f} dBu · max {max_in_best:+.0f} dBu · '
           f'DNR {max_in_best - ein_pad_best:.0f} dB</text>')
svg.append(f'<text x="{px}" y="{py+41}" class="annotation" fill="#9b59b6">'
           f'×2.5 pad ON: EIN {ein_pad_worst:.1f} dBu · max {max_in_worst:+.0f} dBu · '
           f'DNR {max_in_worst - ein_pad_worst:.0f} dB</text>')
svg.append(f'<text x="{px}" y="{py+56}" class="annotation" fill="#636" font-style="italic">'
           f'Use for: loud condensers, DI, close-mic drums</text>')

# Footer
svg.append(f'<text x="{ML}" y="{H-4}" class="annotation">'
           f'5V supply · DMMT3904W · current mirror + cascode · 470R/680R output divider · '
           f'AK4619 (35 nV/√Hz) · R_A=150R, R_B=470R · '
           f'Pad: 1K5/150R (−{abs(PAD_DB):.0f} dB) · Digital: −12 to +36 dB (0.5 dB)</text>')

svg.append('</svg>')

outpath = "/home/peter/Stonepower Dropbox/Peter Watts/VSCODE/MicPre/ein_vs_gain_4step.svg"
with open(outpath, "w") as f:
    f.write("\n".join(svg))
print(f"Written to {outpath}")
