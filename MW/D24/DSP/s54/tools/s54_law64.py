#!/usr/bin/env python3
"""s54_law64.py <t1all.jsonl>... — the 64-code MIC 5 gain law: table, bit-pattern check, steps, first-cut trim table.

BIT-PATTERN MODEL. The code's six bits switch stages; the measured law is additive in LINEAR gain, not in dB
(code 3 = code 1 + code 2 - code 0 to 0.2 %), which is what parallel-switched feedback resistors give
(G = 1 + Rf * sum(bit_i / R_i)). So the model is  G_lin(code) = g0 + sum_i bit_i * d_i, fitted by least squares
over all 64 codes; a code whose measured gain misses the model by more than FLAG_DB is a stage not switching
(or switching wrong). Gains are the loop gain osc(strip 6 digital) -> MIC 5 lane, dB; hardware gain re code 0 is
that minus code 0's.
"""
import json, math, sys

FLAG_DB = 0.25
rows = {}
for p in sys.argv[1:]:
    for l in open(p):
        r = json.loads(l)
        if r.get('ev') == 't1all':
            rows[r['code']] = r
rep = {}
for p in sys.argv[1:]:
    for l in open(p):
        r = json.loads(l)
        if r.get('ev') == 't1all':
            rep.setdefault(r['code'], []).append(r['gain_coh'])
codes = sorted(rows)
assert codes == list(range(64)), 'missing codes: %s' % sorted(set(range(64)) - set(codes))
g = {c: rows[c]['gain_coh'] for c in codes}
lin = {c: 10 ** (g[c] / 20.0) for c in codes}


def solve(A, y):
    k = len(A[0]); n = len(A)
    M = [[sum(A[r][i] * A[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    v = [sum(A[r][i] * y[r] for r in range(n)) for i in range(k)]
    for i in range(k):
        p = max(range(i, k), key=lambda q: abs(M[q][i])); M[i], M[p] = M[p], M[i]; v[i], v[p] = v[p], v[i]
        for q in range(i + 1, k):
            f = M[q][i] / M[i][i]
            for c in range(i, k):
                M[q][c] -= f * M[i][c]
            v[q] -= f * v[i]
    x = [0.0] * k
    for i in reversed(range(k)):
        x[i] = (v[i] - sum(M[i][c] * x[c] for c in range(i + 1, k))) / M[i][i]
    return x


A = [[1.0] + [float((c >> b) & 1) for b in range(6)] for c in codes]
# weighted by 1/G so every code's RELATIVE error counts equally (an unweighted fit is decided by the top codes
# and mis-flags the bottom ones by several dB)
x = solve([[a / lin[c] for a in A[c]] for c in codes], [1.0 for c in codes])
model = {c: sum(a * b for a, b in zip(A[c], x)) for c in codes}
print('LINEAR-ADDITIVE MODEL  G = %.4f + sum(bit_i * d_i)   (loop gain, linear)' % x[0])
for b in range(6):
    print('  bit %d (code %2d, byte bit Q%d): d = %8.4f   alone: %+.3f dB over code 0'
          % (b, 1 << b, b + 2, x[b + 1], 20 * math.log10((x[0] + x[b + 1]) / x[0])))
print('')
print('| code | byte | osc dBFS pk | lane RMS dBFS | lane coh pk dBFS | loop gain dB | re code 0 dB | model dB | miss dB | THD+N dB | THD+N % |')
print('|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
flags = []
for c in codes:
    r = rows[c]; md = 20 * math.log10(model[c]); miss = g[c] - md
    if abs(miss) > FLAG_DB:
        flags.append((c, miss))
    print('| %d | 0x%02X | %.2f | %.2f | %.2f | %+.3f | %+.3f | %+.3f | %+.3f%s | %.2f | %.4f |'
          % (c, c << 2, r['osc'], r['rms'], r['coh_pk'], g[c], g[c] - g[0], md, miss, ' **FLAG**' if abs(miss) > FLAG_DB else '',
             r['thd'], 100 * 10 ** (r['thd'] / 20)))
print('')
mono = all(g[c + 1] > g[c] for c in range(63))
print('monotonic in code order: %s' % mono)
if not mono:
    print('  non-monotonic code steps: %s' % ', '.join('%d->%d %+.3f' % (c, c + 1, g[c + 1] - g[c]) for c in range(63) if g[c + 1] <= g[c]))
srt = sorted(codes, key=lambda c: g[c])
steps = [(g[srt[i + 1]] - g[srt[i]], srt[i], srt[i + 1]) for i in range(63)]
print('sorted by gain, the 63 steps (dB): %s' % ', '.join('%.3f' % s for s, _, _ in sorted(steps)))
big = max(steps)
print('largest gap in the SORTED law: %.3f dB between code %d (%+.3f re 0) and code %d (%+.3f re 0)'
      % (big[0], big[1], g[big[1]] - g[0], big[2], g[big[2]] - g[0]))
print('smallest gap: %.3f dB (codes %d, %d)' % min(steps))
print('code-order largest step: %s' % max((g[c + 1] - g[c], c) for c in range(63)).__repr__())
dup = {c: v for c, v in rep.items() if len(v) > 1}
if dup:
    print('repeat measurements (same session, run 1 vs run 2): %d codes, max |diff| %.4f dB'
          % (len(dup), max(abs(v[-1] - v[0]) for v in dup.values())))
print('flags (|miss| > %.2f dB): %s' % (FLAG_DB, flags or 'none'))
print('')
print('FIRST-CUT TRIM TABLE (gain re code 0; hw = largest measured hardware gain <= target; trim = target - hw >= 0)')
print('| target dB | code | hw dB re code 0 | trim dB |')
print('|---:|---:|---:|---:|')
worst = 0.0
for t in range(0, 61):
    cand = [c for c in codes if g[c] - g[0] <= t + 1e-9]
    c = max(cand, key=lambda q: g[q])
    hw = g[c] - g[0]; trim = t - hw
    worst = max(worst, trim if t <= g[srt[-1]] - g[0] else 0)
    print('| %d | %d | %.3f | %.3f |' % (t, c, hw, trim))
print('')
print('largest trim inside the hardware range (target <= %.2f dB): %.3f dB' % (g[srt[-1]] - g[0], worst))
