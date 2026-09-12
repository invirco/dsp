#!/usr/bin/env python3
"""cclk.py <chip> <seconds> — the diag-timer rate, MAGIC-guarded.

dsp4_diag.py --rate reads TICKS unguarded, and on a chip whose main loop
is over budget the answer can come from a different request — which is
how it printed a NEGATIVE tick delta. Every read here is bracketed by
MAGIC, and TICKS and FRAME_COUNT are taken in the same guarded window so
the two rates are directly comparable.
"""
import sys, time
CHIP = int(sys.argv[1]); W = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
sys.argv = ['c']
import dsp4_diag as D
link = D.SpiLink('0.0', 1000000, 6 if CHIP==1 else 24,
                 rdy_gpio=8 if CHIP==1 else 12)
diag = D.DiagLink(link); diag.resync()

def snap(patience=60):
    for _ in range(patience):
        try:
            if diag.read(0xE000) != 0xD5B40001: continue
            t = diag.read(0xE005); f = diag.read(0xE004)
            if diag.read(0xE000) != 0xD5B40001: continue
            return t, f, time.time()
        except IOError:
            continue
    return None

a = snap()
if a is None: print(f'chip{CHIP}: link never answered'); sys.exit(2)
time.sleep(W)
b = snap()
if b is None: print(f'chip{CHIP}: link stopped'); sys.exit(2)
dt = b[2] - a[2]
dtick = b[0] - a[0]; dfrm = b[1] - a[1]
print(f'chip{CHIP}: TICKS {a[0]} -> {b[0]}  delta {dtick} in {dt:.2f} s '
      f'= {dtick/dt:.2f} Hz  (nominal 1000 Hz)')
print(f'chip{CHIP}: FRAME_COUNT delta {dfrm} = {dfrm/dt:.1f}/s  (nominal 3000)')
print(f'chip{CHIP}: core clock ratio to nominal = {dtick/dt/1000:.5f}')
