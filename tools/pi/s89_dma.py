#!/usr/bin/env python3
"""s89_dma.py <symdir> <chip> <activebuf_sym> <off_tbl> <stride_tbl> <entry>
Peek one block of one lane straight out of a DMA ring, using the part's OWN
off/stride tables (never a host-side idea of the layout)."""
import json, math, sys
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR, CHIP = _A[0], int(_A[1])
ACT, OFFT, STRT, ENT = _A[2], _A[3], _A[4], int(_A[5])
Q = 1 << 28
sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
syms = json.load(open('%s/chip%d.sym.json' % (SYMDIR, CHIP)))
if 'symbols' in syms: syms = syms['symbols']
def A(n):
    v = syms[n]
    return int(v, 0) if isinstance(v, str) else v
def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

base = sc.peek(A(ACT))
off = sc.peek(A(OFFT) + ENT)
stride = sc.peek(A(STRT) + ENT)
print('%s = 0x%X   off[%d] = %d   stride[%d] = %d' % (ACT, base, ENT, off, ENT, stride))
ws = [sc.peek(base + off + k * stride) for k in range(16)]
print('   words  ' + ' '.join('%08X' % (w & 0xFFFFFFFF) for w in ws[:8]))
print('          ' + ' '.join('%08X' % (w & 0xFFFFFFFF) for w in ws[8:]))
print('   Q4.28  ' + ' '.join('%+.5f' % (s32(w) / Q) for w in ws[:8]))
print('          ' + ' '.join('%+.5f' % (s32(w) / Q) for w in ws[8:]))
neg = sum(1 for w in ws if w & 0x80000000)
print('   words with bit31 set: %d of 16' % neg)
