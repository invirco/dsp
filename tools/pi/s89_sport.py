#!/usr/bin/env python3
"""s89_sport.py <symdir> <chip> -- read SPORT CTL/MCTL/CS0 for the inter-chip
half of this chip, straight off the part (MMR peek, writes nothing)."""
import json, sys
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
SYMDIR, CHIP = _A[0], int(_A[1])
BASE, STRIDE, HALFB = 0x31002000, 0x100, 0x80
sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
half = HALFB if CHIP == 1 else 0          # chip1 IC = TX (half B), chip2 IC = RX (half A)
print('chip %d inter-chip half %s' % (CHIP, 'B (TX)' if half else 'A (RX)'))
for sp in (0, 1, 2):
    a = BASE + sp * STRIDE + half
    ctl, mctl, cs0 = sc.peek(a + 0x00), sc.peek(a + 0x08), sc.peek(a + 0x0C)
    print('  SPORT%d  CTL 0x%08X  SLEN %2d  SPTRAN %d  FSR %d  CKRE %d  ICLK %d  IFS %d  DTYPE %d  LSBF %d  SPEN %d'
          % (sp, ctl, (ctl >> 4) & 0x1F, (ctl >> 26) & 1, (ctl >> 25) & 1,
             (ctl >> 24) & 1, (ctl >> 1) & 1, (ctl >> 22) & 1,
             (ctl >> 2) & 3, (ctl >> 9) & 1, ctl & 1))
    print('          MCTL 0x%08X  MCE %d  MFD %2d  WSIZE %2d  WOFF %2d  MCPDE %d   CS0 0x%08X'
          % (mctl, mctl & 1, (mctl >> 4) & 0xF, (mctl >> 16) & 0x1F,
             (mctl >> 24) & 0x1F, (mctl >> 2) & 1, cs0))
# and the converter half for reference
half2 = 0 if CHIP == 1 else HALFB
print('chip %d converter half %s' % (CHIP, 'A (RX)' if half2 == 0 else 'B (TX)'))
for sp in (0, 1, 2):
    a = BASE + sp * STRIDE + half2
    ctl, mctl = sc.peek(a + 0x00), sc.peek(a + 0x08)
    print('  SPORT%d  CTL 0x%08X  SLEN %2d   MCTL 0x%08X  MFD %2d  WSIZE %2d'
          % (sp, ctl, (ctl >> 4) & 0x1F, mctl, (mctl >> 4) & 0xF, (mctl >> 16) & 0x1F))
