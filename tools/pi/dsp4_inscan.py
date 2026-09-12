#!/usr/bin/env python3
"""inscan.py <chip> [n_slots] [reps] — are the TDM input lanes carrying anything?

Peeks _rx_slot_C1_IN_NN repeatedly. A lane fed by a clocked converter
varies sample to sample even with nothing plugged in (the converter's own
noise floor); a lane fed by an unclocked one is a constant. So the
question answered here is "does it MOVE", not "is it non-zero" -- a stuck
non-zero word is just as dead as a stuck zero.
"""
import sys, json, time
CHIP = int(sys.argv[1]) if len(sys.argv) > 1 else 1
N    = int(sys.argv[2]) if len(sys.argv) > 2 else 24
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sys.argv = ['i']
import dsp4_diag as D
sym = json.load(open('/home/app/dspboot/chip%d.sym.json' % CHIP))
link = D.SpiLink('0.0', 1000000, 6 if CHIP==1 else 24,
                 rdy_gpio=8 if CHIP==1 else 12)
diag = D.DiagLink(link); diag.resync()

def peek(a, patience=25):
    for _ in range(patience):
        try:
            if diag.read(0xE000) != 0xD5B40001: continue
            v = diag.peek(a)
            if diag.read(0xE000) != 0xD5B40001: continue
            if v == 0xFFFFFFFF: continue     # the link's "I don't know"
            return v
        except IOError:
            continue
    return None

moving = dead = unread = 0
for i in range(1, N+1):
    name = '_rx_slot_C%d_IN_%02d' % (CHIP, i)
    if name not in sym:
        continue
    a = sym[name]
    vals = []
    for _ in range(REPS):
        v = peek(a)
        if v is not None: vals.append(v)
        time.sleep(0.02)
    if not vals:
        print('  IN_%02d  UNREADABLE' % i); unread += 1; continue
    uniq = set(vals)
    tag = 'MOVING' if len(uniq) > 1 else 'STATIC'
    if len(uniq) > 1: moving += 1
    else: dead += 1
    print('  IN_%02d  %s  %d distinct in %d reads   e.g. %s'
          % (i, tag, len(uniq), len(vals),
             ' '.join('0x%08X' % v for v in vals[:4])))
print('chip%d: MOVING %d / STATIC %d / UNREADABLE %d' % (CHIP, moving, dead, unread))
