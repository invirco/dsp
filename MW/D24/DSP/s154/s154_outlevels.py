#!/usr/bin/env python3
"""s154_outlevels.py -- the S154 hard-pan sweep, read at the chip-2 output blocks.

Drives TEST_OSC (already routed by the caller) through a list of levels and pan
positions and reads the peak of each output node's own block buffer with
single-word peeks spread across the block (a live block cannot be bulk read:
it moves between the checksum and the stream). Each peek lands at an unrelated
phase, so the max of REPS of them finds the 1 kHz crest: 4.8 % of phases are
within 0.1 dB of it, so 400 peeks miss by more than 0.1 dB with p < 1e-8. Optional raw dispatch
writes (`c2@ADDR=VAL`) are applied first, so the same sweep runs with the
uncelled main-path compressors as found and switched off.

usage: s154_outlevels.py SYMDIR [--set c2@1414=0 ...] [--levels -32,-22,-12,-6]
                                [--pans 0,0.25,0.5,1] [--strip 24] [--setup 1]

--setup 1 writes the S121 list's standing cells (strips transparent, bus
masters unity; output-bus processing left as the image booted it) and then
the strip onto MAIN (MainOn) AND aux 1 at unity post-fader, so one sweep reads
MAIN and AUX at the same send. It needs the strip to be 24 (the list's donor).
"""
import math, random, sys, time
ARGS = sys.argv[1:]; sys.argv = ['s']
sys.path.insert(0, '/home/app/selftest'); sys.path.insert(0, '/home/app/dspboot')
import d24_patch as PT

SYMDIR = ARGS[0]
opt = {'--set': [], '--levels': '-32,-22,-12,-6', '--pans': '0', '--strip': '24',
       '--reps': '400', '--setup': '0', '--nodes': '',
       '--prefix': '_blk_'}
i = 1
while i < len(ARGS):
    k = ARGS[i]
    if k == '--set':
        opt['--set'].append(ARGS[i + 1])
    else:
        opt[k] = ARGS[i + 1]
    i += 2
LEVELS = [float(x) for x in opt['--levels'].split(',')]
PANS = [float(x) for x in opt['--pans'].split(',')]
STRIP = int(opt['--strip']); REPS = int(opt['--reps'])
# C2_MON_OUT_R is not here: its `_blk_` word reads a constant +11.97 dB on
# both pairs, so it is not an audio block.
NODES = ['C2_AUX_OUT_01', 'C2_MON_OUT_L', 'C2_PHN_OUT_L', 'C2_PHN_OUT_R',
         'C2_MAIN_OUT_01', 'C2_MAIN_OUT_02']
if opt['--nodes']:
    NODES = opt['--nodes'].split(',')

u = PT.Unit(symdir=SYMDIR)
sc2 = u.chip(2)
if opt['--setup'] == '1':
    L = PT.PatchList('/home/app/selftest/s121')
    bad = u.write(L.standing())
    bad += u.write(['Chan%03dMainOn001=1' % STRIP, 'Chan%03dCtrOn001=0' % STRIP,
                    'Chan%03dAuxOn001=1' % STRIP, 'Chan%03dAuxSend001=f1.0' % STRIP,
                    'Chan%03dAuxPick001=3' % STRIP])
    u.osc(chan=STRIP, freq=1000.0, level_dbfs=-32.0, on=True)
    print('setup: standing %d cells + MAIN and AUX 1 route, %d did not read '
          'back %s' % (len(L.standing()), len(bad), bad[:6]))
for spec in opt['--set']:
    name, _, val = spec.partition('=')
    a = int(name.split('@')[1], 0)
    w = PT.f32(val[1:]) if val.startswith('f') else int(val, 0)
    sc2.d.link.write(a, w & 0xFFFFFFFF, 0)
    time.sleep(0.05)
    print('set %s -> 0x%08X (reads 0x%08X)' % (name, w & 0xFFFFFFFF, sc2.rd(a)))

def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

def peak_db(sym):
    addr = sc2.sym[opt['--prefix'] + sym]
    pk = 0.0
    for k in range(REPS):
        # RANDOM offset and a random pause: a fixed stride phase-locked to the
        # 1 kHz tone on the first run and read whole rows 0.69 dB low.
        time.sleep(random.uniform(0, 0.0015))
        try:
            w = sc2.peek(addr + random.randrange(32))
        except IOError:
            continue
        pk = max(pk, abs(s32(w)) / float(1 << 28))
    return 20 * math.log10(pk) if pk > 0 else -999.0

print('strip %d; columns = peak dBFS (Q4.28, 1.0 = 0 dBFS) of each node block'
      % STRIP)
print('%6s %5s ' % ('osc', 'pan') + ' '.join('%14s' % n[3:] for n in NODES))
for pan in PANS:
    bad = u.write(['Chan%03dPan001=f%g' % (STRIP, pan)])
    if bad:
        raise SystemExit('pan did not read back: %s' % bad)
    for lv in LEVELS:
        u.osc(level_dbfs=lv, on=True)
        time.sleep(1.2)
        row = [peak_db(n) for n in NODES]
        a = row[0]
        print('%6.1f %5.2f ' % (lv, pan) + ' '.join('%14.2f' % v for v in row)
              + '   MAIN-AUX L %+6.2f R %+6.2f'
              % (row[-2] - a if row[-2] > -900 else -99,
                 row[-1] - a if row[-1] > -900 else -99))
        sys.stdout.flush()
