#!/usr/bin/env python3
"""s39_cost.py <chip> <symdir> [seconds] — the block-cost instrument.

S38-3 read `_proc_cyc` / `_proc_passes` as 0 on BOTH chips and concluded
the image was uninstrumented. There is no such build: main.asm writes all
three words at the end of every block pass on both chips, with no #if
around them. The zeros were the host symbol map, not the image.

Reports, per window:
  _proc_passes   block passes completed        (must advance)
  _proc_cyc      cycles in the LAST pass
  _proc_cyc_max  worst pass since DIAG_CLEAR
  DIAG_FRAME_COUNT, DIAG_BLK_OVERRUN

and turns _proc_cyc into a share of the per-block budget, which at
BLOCK=16 / 48 kHz and the measured core clock is cclk / 3000 cycles.
"""
import sys, time, json
_argv = list(sys.argv)
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

CHIP   = int(_argv[1]) if len(_argv) > 1 else 1
SYMDIR = _argv[2] if len(_argv) > 2 else '/home/app/s39'
SECS   = float(_argv[3]) if len(_argv) > 3 else 30.0

sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()
sym = sc.sym

def pk(name):
    if name not in sym:
        return None
    try:
        return sc.peek(sym[name])
    except IOError:
        return None

def rg(reg):
    try:
        return sc.rd(reg)
    except IOError:
        return None

# DIAG_CLEAR zeroes _proc_cyc_max and the overrun counter; _proc_cyc and
# _proc_passes are deliberately left alone by the handler (diag.asm), so
# passes is a free-running total and is differenced here.
sc.d.write(0xE0FF, 1); time.sleep(0.5)

p0 = pk('_proc_passes'); t0 = time.time()
o0 = rg(0xE00A)
print('chip %d  start: _proc_passes %s  BLK_OVERRUN %s' % (CHIP, p0, o0))
time.sleep(SECS)
p1 = pk('_proc_passes'); t1 = time.time()
o1 = rg(0xE00A)
cyc = pk('_proc_cyc'); cmax = pk('_proc_cyc_max')

el = t1 - t0
print('chip %d  end  : _proc_passes %s  BLK_OVERRUN %s   (%.1f s)'
      % (CHIP, p1, o1, el))
if p0 is not None and p1 is not None:
    d = p1 - p0
    print('  passes in window : %d  -> %.1f blocks/s  (nominal 3000)' % (d, d / el))
    miss = 3000.0 * el - d
    print('  shortfall vs 3000/s : %.0f blocks  = %.2f %%' % (miss, 100.0 * miss / (3000.0 * el)))
if o0 is not None and o1 is not None:
    print('  BLK_OVERRUN delta : %d  -> %.1f /s' % (o1 - o0, (o1 - o0) / el))
print('  _proc_cyc (last pass) : %s' % cyc)
print('  _proc_cyc_max         : %s' % cmax)
# budget: cclk / 3000 cycles per block at BLOCK=16, 48 kHz
for label, cclk in (('983.04 MHz', 983_040_000),):
    b = cclk / 3000.0
    if cyc:
        print('  budget at %s = %.0f cyc/block -> last pass %.1f %%, worst %.1f %%'
              % (label, b, 100.0 * cyc / b,
                 100.0 * cmax / b if cmax else float('nan')))
