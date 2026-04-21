#!/usr/bin/env python3
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

print("R values: {}".format(R))
print("Range: {:.1f} to {:.1f} dB".format(dbs[0], dbs[-1]))
print("Max gap: {:.2f} dB".format(max(gaps)))
print("Mean gap: {:.2f} dB".format(sum(gaps)/len(gaps)))
print()
for i, r in enumerate(R):
    print("  R{}={:.0f}R  solo={:.1f}dB".format(i+1, r, 20*math.log10(1+Rf/(r+Rds))))

max_db_int = int(dbs[-1])
max_trim = 0
for t in range(max_db_int + 1):
    bi = min(range(len(out)), key=lambda j: abs(out[j][0] - t))
    trim = t - out[bi][0]
    if abs(trim) > max_trim:
        max_trim = abs(trim)
print("\nMax DSP trim: {:.2f} dB".format(max_trim))

W = 70
H = 25
print("\nGain curve (64 steps):\n")
for row in range(H, -1, -1):
    db_at = dbs[-1] * row / H
    label = "{:5.1f}|".format(db_at)
    chars = [" "] * W
    for i, d in enumerate(dbs):
        x = int(i * (W - 1) / (len(dbs) - 1))
        y_pos = d / dbs[-1] * H
        if abs(y_pos - row) < 0.6:
            chars[x] = "*"
    print(label + "".join(chars))
print("     +" + "-" * W + "> Step")
print("      0" + " " * (W - 8) + "63")

mg = max(gaps)
GH = 12
print("\nGap distribution:\n")
for row in range(GH, -1, -1):
    gap_at = mg * row / GH
    label = "{:4.1f}|".format(gap_at)
    chars = [" "] * W
    for i, g in enumerate(gaps):
        x = int(i * (W - 1) / max(len(gaps) - 1, 1))
        y_pos = g / mg * GH
        if abs(y_pos - row) < 0.6:
            chars[x] = "#"
    print(label + "".join(chars))
print("    +" + "-" * W + "> Step")

print("\nStep | Gain(dB) | Gap(dB) | Switches (R1..R6)")
print("-----|----------|---------|-------------------")
for i, (db, mask) in enumerate(out):
    gap = gaps[i-1] if i > 0 else 0.0
    sw = "".join(["1" if mask & (1 << j) else "0" for j in range(6)])
    print("{:4d} | {:7.2f}  | {:6.2f}  | {}".format(i, db, gap, sw))
