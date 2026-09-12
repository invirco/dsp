#!/usr/bin/env python3
"""dump.py <chip> [peek_hex ...] — full diag block via DiagLink.resync(),
which phases on loaded links where the dsp4_diag CLI path refuses."""
import sys
CHIP = int(sys.argv[1]); PEEKS = [int(x,16) for x in sys.argv[2:]]
sys.argv = ['d']
import dsp4_diag as D
link = D.SpiLink('0.0', 1000000, 6 if CHIP==1 else 24,
                 rdy_gpio=8 if CHIP==1 else 12)
diag = D.DiagLink(link); diag.resync()
for addr, name, fmt in D.REGISTERS:
    got = None
    for _ in range(30):
        try:
            got = diag.read(addr); break
        except IOError:
            continue
    if got is None:
        print(f'  {name:15s} --'); continue
    print(f'  {name:15s} ' + (f'0x{got:08X}' if fmt=='hex' else str(got)))
for p in PEEKS:
    got = None
    for _ in range(30):
        try:
            got = diag.peek(p); break
        except IOError:
            continue
    print(f'  peek 0x{p:08X}   ' + ('--' if got is None else f'{got} (0x{got:08X})'))
