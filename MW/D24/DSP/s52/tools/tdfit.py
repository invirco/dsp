"""tdfit.py cap.json start end — least-squares DC + fundamental (+ h2..h10) over [start,end); THD+N/THD/noise in dB."""
import json, math, sys
def s32(w): return w - (1 << 32) if w & 0x80000000 else w
v = [s32(x) / 2 ** 28 for x in json.load(open(sys.argv[1]))['samples']]
a, b = int(sys.argv[2]), int(sys.argv[3]); x = v[a:b]; n = len(x)
def solve(M, y):  # normal equations, gaussian elimination
    k = len(M[0]); ATA = [[sum(M[r][i] * M[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    ATy = [sum(M[r][i] * y[r] for r in range(n)) for i in range(k)]
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(ATA[r][i])); ATA[i], ATA[p] = ATA[p], ATA[i]; ATy[i], ATy[p] = ATy[p], ATy[i]
        for r in range(i + 1, k):
            f = ATA[r][i] / ATA[i][i]
            for c in range(i, k): ATA[r][c] -= f * ATA[i][c]
            ATy[r] -= f * ATy[i]
    s = [0] * k
    for i in reversed(range(k)): s[i] = (ATy[i] - sum(ATA[i][c] * s[c] for c in range(i + 1, k))) / ATA[i][i]
    return s
def fit(f0, H):
    cols = [[1.0] * n]
    for h in range(1, H + 1):
        w = 2 * math.pi * f0 * h / 48000
        cols += [[math.sin(w * i) for i in range(n)], [math.cos(w * i) for i in range(n)]]
    M = [[c[r] for c in cols] for r in range(n)]
    s = solve(M, x)
    model = [sum(s[j] * M[r][j] for j in range(len(s))) for r in range(n)]
    res = [x[r] - model[r] for r in range(n)]
    return s, math.sqrt(sum(e * e for e in res) / n)
best = min(((f, fit(f, 1)[1]) for f in [999.9 + 0.01 * i for i in range(21)]), key=lambda t: t[1]); f0 = best[0]
s1, r1 = fit(f0, 1); s10, r10 = fit(f0, 10)
fund_rms = math.hypot(s1[1], s1[2]) / math.sqrt(2)
harm = math.sqrt(sum((s10[2*h-1] ** 2 + s10[2*h] ** 2) / 2 for h in range(2, 11)))
db = lambda q: 20 * math.log10(q)
print('%s [%d:%d] n=%d f0=%.2f Hz  fund %.2f dBFS rms  THD+N %.2f dB  THD(2..10) %.2f dB  noise(after h1..h10) %.2f dBFS  DC %.2e'
      % (sys.argv[1].rsplit('/', 1)[-1], a, b, n, f0, db(fund_rms), db(r1 / fund_rms), db(harm / fund_rms), db(r10), s1[0]))
for h in (2, 3):
    print('   h%d %.2f dBc' % (h, db(math.hypot(s10[2*h-1], s10[2*h]) / math.sqrt(2) / fund_rms)))
