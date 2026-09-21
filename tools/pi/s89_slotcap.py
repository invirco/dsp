#!/usr/bin/env python3
"""s89_slotcap.py <symdir> <chip> <symbol> <n> [out.json]
COHERENT capture of a per-sample node slot, via _scope_record in the block loop.

S89 only ever PEEKED the Monitor output slot -- 16 words, one SPI transaction
each, every word from a different audio block (see [[dsp4-peek-is-not-a-block]]).
That cannot see a defect whose period IS the block. _scope_record stores
_scope_src[_sample_idx] once per sample into _scope_buf, so this is contiguous
audio and an FFT of it means something."""
import json, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR, CHIP, SYM = _A[0], int(_A[1]), _A[2]
N = int(_A[3]) if len(_A) > 3 else 1024
OUT = _A[4] if len(_A) > 4 else None

sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
addr = sc.addr(SYM)
print('%s at 0x%06X, capturing %d contiguous samples' % (SYM, addr, N))
sc.arm(addr, inj=0, amp=0, mode=1)
got = sc.wait(timeout=8.0)
ws = sc.fetch(N)
def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w
x = [s32(w) / float(1 << 28) for w in ws]
nz = sum(1 for v in x if v != 0.0)
print('captured %s samples, %d non-zero' % (got, nz))
print('first 16 Q4.28: ' + ' '.join('%+.5f' % v for v in x[:16]))
if OUT:
    json.dump({'node': SYM, 'fs': 48000, 'scale': 'q4.28', 'samples': ws}, open(OUT, 'w'))
    print('written', OUT)
