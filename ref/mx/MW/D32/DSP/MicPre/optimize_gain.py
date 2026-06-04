#!/usr/bin/env python3
"""
Mic preamp gain resistor calculator — pure Python, no dependencies.
Non-inverting: Gain = 1 + Rf/Rg, Rf = 4.99k
6 switched resistors (2N7002, Rds~3R).
Constraint: max analog gap <= 6 dB. Find maximum achievable gain.
Outputs res.md.
"""
import math, sys

Rf = 4990.0
Rds = 3.0
MAX_GAP = 6.0  # dB

E96 = [1.00,1.02,1.05,1.07,1.10,1.13,1.15,1.18,1.21,1.24,1.27,1.30,1.33,1.37,
       1.40,1.43,1.47,1.50,1.54,1.58,1.62,1.65,1.69,1.74,1.78,1.82,1.87,1.91,
       1.96,2.00,2.05,2.10,2.15,2.21,2.26,2.32,2.37,2.43,2.49,2.55,2.61,2.67,
       2.74,2.80,2.87,2.94,3.01,3.09,3.16,3.24,3.32,3.40,3.48,3.57,3.65,3.74,
       3.83,3.92,4.02,4.12,4.22,4.32,4.42,4.53,4.64,4.75,4.87,4.99,5.11,5.23,
       5.36,5.49,5.62,5.76,5.90,6.04,6.19,6.34,6.49,6.65,6.81,6.98,7.15,7.32,
       7.50,7.68,7.87,8.06,8.25,8.45,8.66,8.87,9.09,9.31,9.53,9.76]
E96V = sorted(b * 10**d for d in range(6) for b in E96)

def snap(R):
    return min(E96V, key=lambda x: abs(x - R))

def gains64(R):
    out = []
    for m in range(64):
        G = sum(1.0 / (R[i] + Rds) for i in range(6) if m & (1 << i))
        db = 20 * math.log10(1 + Rf * G) if G > 0 else 0.0
        out.append((db, m))
    out.sort()
    return out

def max_gap(R):
    gs = gains64(R)
    dbs = [g[0] for g in gs]
    return max(dbs[i+1] - dbs[i] for i in range(len(dbs)-1))

def top_gain(R):
    gs = gains64(R)
    return gs[-1][0]

# --- Analytical starting point ---
# First step constrains: 20*log10(1 + Rf*G0) <= 6 dB
# G0 <= (10^(6/20) - 1) / Rf = 0.9953 / 4990
G0_max = (10**(MAX_GAP / 20) - 1) / Rf
print("Max G0 for {:.0f}dB first step: {:.6f} S".format(MAX_GAP, G0_max), file=sys.stderr)
print("Corresponding R: {:.0f} ohm".format(1.0/G0_max - Rds), file=sys.stderr)

# Binary-weighted baseline: max gain = 20*log10(1 + 63*Rf*G0)
binary_max = 20 * math.log10(1 + 63 * Rf * G0_max)
print("Binary-weighted max: {:.1f} dB".format(binary_max), file=sys.stderr)

# --- Try super-binary weighting to push higher ---
# At high gain, dB gaps compress, so we can use larger conductance jumps.
# Search: try weight ratios beyond 2x and check all gaps.
print("", file=sys.stderr)
print("Searching for optimal weighting...", file=sys.stderr)

best_top = 0
best_R = None

# Try many different weight patterns
# Weights define conductance multiples: w0=1, then w1, w2, w3, w4, w5
# Must have w_i <= 2*sum(w_0..w_{i-1}) + 1 for gap-free integer coverage (binary)
# But we can exceed this if the dB gap stays <= 6 dB

for w1 in [2, 3]:
    for w2 in range(4, 9):
        for w3 in range(8, 25):
            for w4 in range(16, 70):
                for w5 in range(32, 200):
                    weights = [1, w1, w2, w3, w4, w5]
                    total = sum(weights)
                    G0 = G0_max  # max allowed for 6dB first step
                    R = [1.0 / (w * G0) - Rds for w in weights]
                    if any(r < 1.0 for r in R):
                        continue
                    mg = max_gap(R)
                    if mg <= MAX_GAP:
                        tg = top_gain(R)
                        if tg > best_top:
                            best_top = tg
                            best_R = list(R)

print("Best raw: {:.1f} dB  R={}".format(best_top, [round(r,1) for r in best_R]), file=sys.stderr)

# Snap to E96 and refine
Re = sorted(snap(r) for r in best_R)

# Local grid refinement: maximize top gain while keeping max_gap <= 6
print("E96 refinement (maximize range, gap <= {:.0f} dB)...".format(MAX_GAP), file=sys.stderr)
best_tg = top_gain(Re) if max_gap(Re) <= MAX_GAP else 0
for _pass in range(10):
    improved = False
    for i in range(6):
        ci = min(range(len(E96V)), key=lambda j: abs(E96V[j] - Re[i]))
        for off in range(-15, 16):
            ni = max(0, min(len(E96V) - 1, ci + off))
            trial = list(Re)
            trial[i] = E96V[ni]
            trial.sort()
            mg = max_gap(trial)
            if mg <= MAX_GAP:
                tg = top_gain(trial)
                if tg > best_tg:
                    best_tg = tg
                    Re = trial
                    improved = True
    if not improved:
        break

Re = sorted(Re)
gs = gains64(Re)
dbs = [g[0] for g in gs]
gaps = [dbs[i+1] - dbs[i] for i in range(len(dbs)-1)]
mean_gap = sum(gaps) / len(gaps)
mg = max(gaps)

solo = [round(20 * math.log10(1 + Rf / (r + Rds)), 1) for r in Re]

# 1 dB mapping (up to achieved max)
max_db_int = int(dbs[-1])
mapping = []
for target in range(max_db_int + 1):
    bi = min(range(len(gs)), key=lambda j: abs(gs[j][0] - target))
    analog = gs[bi][0]
    trim = target - analog
    mask = gs[bi][1]
    mapping.append({"target": target, "analog_db": round(analog, 2),
                    "dsp_trim": round(trim, 2), "mask": mask})
max_trim = max(abs(m["dsp_trim"]) for m in mapping)

# Summary
print("", file=sys.stderr)
print("Final resistors: {}".format(Re), file=sys.stderr)
print("Solo gains: {}".format(solo), file=sys.stderr)
print("Gain range: {:.1f} to {:.1f} dB".format(dbs[0], dbs[-1]), file=sys.stderr)
print("Max gap: {:.2f} dB".format(mg), file=sys.stderr)
print("Mean gap: {:.2f} dB".format(mean_gap), file=sys.stderr)
print("Max DSP trim: {:.2f} dB".format(max_trim), file=sys.stderr)

# --- Generate Markdown ---
L = []
a = L.append

a("# Mic Preamp — Switched Gain Resistor Design")
a("")
a("## Circuit")
a("")
a("- **Topology:** Non-inverting (Gain = 1 + Rf / Rg)")
a("- **Rf:** 4.99k")
a("- **Rg:** Parallel combination of up to 6 switched resistors")
a("- **Switches:** 2N7002 N-FET (Rds_on ~ 3R)")
a("- **Gain range:** {:.1f} dB to {:.1f} dB".format(dbs[0], dbs[-1]))
a("- **Total analog steps:** {} (6 switches = 64 combos incl. 0 dB)".format(len(gs)))
a("- **Max analog gap:** {:.2f} dB (constraint: <= {:.0f} dB)".format(mg, MAX_GAP))
a("- **Mean analog gap:** {:.2f} dB".format(mean_gap))
a("- **Max DSP trim needed:** {:.2f} dB".format(max_trim))
a("")
a("### Design Method")
a("")
a("Constraint: maximum single analog gain step <= {:.0f} dB.".format(MAX_GAP))
a("The binding limit is the first step (0 dB to smallest-R solo gain),")
a("which sets the minimum conductance quantum. Conductance weights are")
a("then optimised (super-binary) to push the maximum gain as high as")
a("possible while keeping all 64-combination gaps within {:.0f} dB.".format(MAX_GAP))
a("Values snapped to E96 and locally refined.")
a("")

a("## Selected Resistors (E96)")
a("")
a("| # | R value | Solo Gain | Conductance Weight |")
a("|---|---------|-----------|-------------------|")
for i, r in enumerate(Re):
    if r >= 1000:
        rv = "{:.2f}k".format(r / 1000)
    else:
        rv = "{:.0f}R".format(r)
    weight = round((1.0/(r + Rds)) / (1.0/(Re[0] + Rds)), 1)
    a("| R{} | {} | {:.1f} dB | {:.1f}x |".format(i+1, rv, solo[i], weight))
a("")

a("## All 64 Analog Gain Steps")
a("")
a("| Step | Gain (dB) | Gap (dB) | R1 | R2 | R3 | R4 | R5 | R6 |")
a("|------|-----------|----------|----|----|----|----|----|----|")
for i, (db, mask) in enumerate(gs):
    gap = gaps[i-1] if i > 0 else 0.0
    sw = ["ON" if mask & (1 << j) else "-" for j in range(6)]
    a("| {} | {:.2f} | {:.2f} | {} |".format(i, db, gap, " | ".join(sw)))
a("")

a("## 1 dB Gain Mapping (0 to {} dB)".format(max_db_int))
a("")
a("| Target | Analog | DSP Trim | R1 | R2 | R3 | R4 | R5 | R6 |")
a("|--------|--------|----------|----|----|----|----|----|----|")
for m in mapping:
    mask = m["mask"]
    sw = ["1" if mask & (1 << j) else "0" for j in range(6)]
    a("| {} dB | {:.2f} dB | {:+.2f} dB | {} |".format(
        m["target"], m["analog_db"], m["dsp_trim"], " | ".join(sw)))
a("")

# --- ASCII graphs ---
W = 72

a("## Analog Gain Curve")
a("")
a("```")
H = 25
for row in range(H, -1, -1):
    db_at = dbs[-1] * row / H
    label = "{:5.1f}|".format(db_at)
    chars = [" "] * W
    for i, d in enumerate(dbs):
        x = int(i * (W - 1) / (len(dbs) - 1))
        y_pos = d / dbs[-1] * H
        if abs(y_pos - row) < 0.6:
            chars[x] = "*"
    a(label + "".join(chars))
a("     +" + "-" * W + "> Step (0-63)")
a("```")
a("")

a("## Gap Distribution")
a("")
a("```")
GH = 12
for row in range(GH, -1, -1):
    gap_at = mg * row / GH
    label = "{:4.1f}|".format(gap_at)
    chars = [" "] * W
    for i, g in enumerate(gaps):
        x = int(i * (W - 1) / max(len(gaps) - 1, 1))
        y_pos = g / mg * GH
        if abs(y_pos - row) < 0.6:
            chars[x] = "#"
    a(label + "".join(chars))
a("    +" + "-" * W + "> Step")
a("```")
a("")

a("## DSP Trim per 1 dB Step")
a("")
a("```")
trims = [m["dsp_trim"] for m in mapping]
mt = max(abs(t) for t in trims) if max(abs(t) for t in trims) > 0 else 1
TH = 10
mid = TH // 2
for row in range(TH, -1, -1):
    trim_at = mt * (row - mid) / mid
    label = "{:+5.2f}|".format(trim_at)
    chars = [" "] * W
    for i, t in enumerate(trims):
        x = int(i * (W - 1) / max(len(trims) - 1, 1))
        y_pos = mid + (t / mt * mid)
        if abs(y_pos - row) < 0.6:
            chars[x] = "+"
    a(label + "".join(chars))
a("     +" + "-" * W + "> Target (0-60 dB)")
a("```")
a("")

a("## EIN Notes")
a("")
a("- At low gain (high Rg), EIN dominated by op-amp input noise")
a("- At high gain (low Rg), 2N7002 Rds_on (~3R) adds Johnson noise but is small vs Rg")
a("- Max DSP trim of {:.2f} dB keeps digital gain-up minimal".format(max_trim))
a("- Worst EIN jump at largest analog gap ({:.2f} dB) — DSP bridges this".format(mg))
a("- For best EIN at high gain, prefer DSP trim slightly negative (analog above target)")
a("")
a("---")
a("*Generated by optimize_gain.py*")

with open("res.md", "w") as f:
    f.write("\n".join(L) + "\n")
print("\nWritten: res.md", file=sys.stderr)
