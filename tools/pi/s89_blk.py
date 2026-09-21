#!/usr/bin/env python3
"""s89_blk.py <symdir> <chip> <sym> [<sym>...] -- peek one BLOCK (16 words) of a
per-sample node array and report it as Q4.28, with the FOLD METRIC.

FOLD METRIC. A 1 kHz tone at 48 kHz moves at most 2*pi*1000/48000 = 0.1309 of
its own peak between adjacent samples. The metric is
    20*log10( max|x[n]-x[n-1]| / (0.1309 * max|x|) )
so a clean tone reads about 0 dB and anything that jumps by more than the tone
can reads positive. Clean <= 1 dB, folded >= 10 dB (hub, S89).
"""
import json, math, sys
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR, CHIP = _A[0], int(_A[1])
Q = 1 << 28
sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
syms = json.load(open('%s/chip%d.sym.json' % (SYMDIR, CHIP)))
if 'symbols' in syms: syms = syms['symbols']

def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

for name in _A[2:]:
    if name.startswith('0x'):
        base = int(name, 16)
    else:
        if name not in syms:
            print('%s: not in map' % name); continue
        base = syms[name]
        base = int(base, 0) if isinstance(base, str) else base
    ws = [sc.peek(base + k) for k in range(16)]
    x = [s32(w) / Q for w in ws]
    pk = max(abs(v) for v in x)
    d = [abs(x[i] - x[i - 1]) for i in range(1, 16)]
    md = max(d)
    lim = 0.13090 * pk
    fold = 20 * math.log10(md / lim) if lim > 0 and md > 0 else float('-inf')
    print('%-34s base 0x%06X' % (name, base))
    print('   words  ' + ' '.join('%08X' % (w & 0xFFFFFFFF) for w in ws[:8]))
    print('          ' + ' '.join('%08X' % (w & 0xFFFFFFFF) for w in ws[8:]))
    print('   Q4.28  ' + ' '.join('%+.5f' % v for v in x[:8]))
    print('          ' + ' '.join('%+.5f' % v for v in x[8:]))
    print('   peak %.6f (%.2f dBFS)   max|dx| %.6f   FOLD %+.2f dB' %
          (pk, 20 * math.log10(pk) if pk > 0 else -999, md, fold))
