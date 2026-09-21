#!/usr/bin/env python3
"""s89_cyc.py <symdir> <chip> [dwell_s] -- the WORST-BLOCK high-water mark.

BLK_OVERRUN is blind to this. It counts only blocks where _block_ready was
still set when the ISR fired, i.e. a SUSTAINED backlog. A block that goes over
budget occasionally -- a periodic design burst, say -- finishes late, drops no
flag and is invisible in the overrun delta. `_proc_cyc_max` is the latch that
sees it (the capacity doc's own case: 124.06 % latched on an arm whose average
was 60.27 %).

DIAG_CLEAR (0xE0FF) zeroes the latch, so the boot-and-config transient is not
counted (S13-2: chip 2 once read 376 % of budget purely from the config ladder).
"""
import sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR, CHIP = _A[0], int(_A[1])
DWELL = float(_A[2]) if len(_A) > 2 else 6.0
DIAG_CLEAR = 0xE0FF
BUDGET = 327680.0          # block 16 at 983.04 MHz

sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
for n in ('_proc_cyc', '_proc_cyc_max', '_proc_passes'):
    if n not in sc.sym:
        print('%s ABSENT from this image' % n); sys.exit(2)
sc.d.write(DIAG_CLEAR, 1)
time.sleep(0.3)
p0 = sc.peek(sc.sym['_proc_passes'])
time.sleep(DWELL)
cyc = sc.peek(sc.sym['_proc_cyc'])
mx = sc.peek(sc.sym['_proc_cyc_max'])
p1 = sc.peek(sc.sym['_proc_passes'])
print('chip %d over %.1f s: %d block passes' % (CHIP, DWELL, p1 - p0))
print('  _proc_cyc      %9d  = %6.2f %% of budget   (the LAST block)')     % () if False else None
print('  _proc_cyc      %9d  = %6.2f %% of budget   (the LAST block)' % (cyc, 100.0*cyc/BUDGET))
print('  _proc_cyc_max  %9d  = %6.2f %% of budget   (the WORST block since clear)%s'
      % (mx, 100.0*mx/BUDGET, '   <-- OVER BUDGET' if mx > BUDGET else ''))
