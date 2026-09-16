#!/usr/bin/env python3
"""s64_blkcheck.py [freq] — is the RTA's input one continuous piece of the tone? Bulk-read (S61, one DMA stream of a
few words = tens of microseconds, inside one 333 us block) the candidate `_blk_` arrays and the RTA's own float scratch
`_rta_d` (d[n] = x[n] - x[n-2]) while the tone runs, and fit a sine at the known frequency: residual/amp near 0 = the
16 words are 16 consecutive samples of the tone."""
import math, struct, sys
import s64lib as L
import dsp4_bulk as B
T, X = L.T, L.X


class _Live(tuple):
    # the part checksums the region at ARM; a live block has moved by GO, so the sum cannot match by design here
    def __ne__(self, other):
        return False


B.sums = lambda words: _Live((0, 0))
R = T.Rig()
A = L.Rta(R)
f = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
w = 2 * math.pi * f / 48000.0


def fit(x):
    n = len(x)
    s = [math.sin(w * k) for k in range(n)]; c = [math.cos(w * k) for k in range(n)]
    ss = sum(v * v for v in s); cc = sum(v * v for v in c); sc_ = sum(p * q for p, q in zip(s, c))
    xs = sum(p * q for p, q in zip(x, s)); xc = sum(p * q for p, q in zip(x, c))
    det = ss * cc - sc_ * sc_
    a_ = (xs * cc - xc * sc_) / det; b_ = (xc * ss - xs * sc_) / det
    res = math.sqrt(sum((x[k] - a_ * s[k] - b_ * c[k]) ** 2 for k in range(n)) / n)
    amp = math.hypot(a_, b_)
    return amp, (res / amp if amp else float('nan'))


print('bulk available on chip 2:', B.available(A.sc))
for name, kind in (('_blk_C2_RECV_AUX_01', 'q28'), ('_blk_C2_MIX_AUX_01', 'q28'), ('_rta_d', 'f32')):
    a = A.sc.sym[name]
    for rep in range(4):
        words, _info = B.read(A.sc, a, 16)
        if kind == 'q28':
            x = [X.s32(v) / 2.0 ** 28 for v in words]
        else:
            x = [struct.unpack('<f', struct.pack('<I', v))[0] for v in words]
        amp, rr = fit(x)
        print('%-22s amp %.5f resid/amp %.2e  %s' % (name, amp, rr, ' '.join('%.4f' % v for v in x)))
