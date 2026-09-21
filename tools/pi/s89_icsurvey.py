#!/usr/bin/env python3
"""s89_icsurvey.py <symdir> <chip> <n> -- how many words carry bit 31 across a
whole inter-chip DMA region. Chip 1 reads the SEND ring, chip 2 the RECV ring."""
import json, sys
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
SYMDIR, CHIP = _A[0], int(_A[1])
NW = int(_A[2]) if len(_A) > 2 else 4
sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
syms = json.load(open('%s/chip%d.sym.json' % (SYMDIR, CHIP)))
if 'symbols' in syms: syms = syms['symbols']
def A(n):
    v = syms[n]
    return int(v, 0) if isinstance(v, str) else v
if CHIP == 1:
    act, offt, strt, n = '_ic_tx_active_buf', '_c1_ic_tx_off', '_c1_ic_tx_stride', 41
else:
    act, offt, strt, n = '_ic_rx_active_buf', '_c2_ic_rx_off', '_c2_ic_rx_stride', 41
base = sc.peek(A(act))
tot = neg = live = 0
rows = []
for e in range(n):
    off = sc.peek(A(offt) + e); st = sc.peek(A(strt) + e)
    ws = [sc.peek(base + off + k * st) & 0xFFFFFFFF for k in range(NW)]
    nb = sum(1 for w in ws if w & 0x80000000)
    dis = len(set(ws))
    tot += NW; neg += nb
    if dis > 1: live += 1
    rows.append((e, off, st, nb, dis, ws[0]))
for e, off, st, nb, dis, w0 in rows:
    print('  entry %2d off %4d stride %3d  bit31 %d/%d  distinct %d  first %08X'
          % (e, off, st, nb, NW, dis, w0))
print('chip %d: %d of %d words carry bit 31; %d of %d entries moving'
      % (CHIP, neg, tot, live, n))
