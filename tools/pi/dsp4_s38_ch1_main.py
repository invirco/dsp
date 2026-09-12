#!/usr/bin/env python3
"""s38_ch1_main.py — route CHANNEL 1 to MAIN L/R at unity, and nothing else.

The shipping configuration does NOT carry a channel->main route:
`dsp4_config.py --product d24` writes only the product SCOPE (PRODUCT_ID,
CHAN_MASK, AUX_MASK, OUT_MUX, the patch list, COMMIT). Per-strip routing
is matrix-app's job over the parameter link, and matrix-app is stopped for
bench work — so with the shipping config alone, strip 1 reaches no output.
This sets that route explicitly, by cell name out of the landed contract,
so PW can put a mic on channel 1.

Every strip is silenced TWO independent ways (MainOn=0 AND Mute=1) before
strip 1 is opened, because one inert cell would otherwise leave the bus
live and read as a pedestal under the mic.
"""
import json, sys, time
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
from dsp4_conform import Part, f32

L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
written, missing = [], []

def w(part, cell, val, ramp=0):
    if cell not in L:
        missing.append(cell); return False
    part.write(L[cell][2], val, ramp)
    written.append(cell); return True

p1, p2 = Part(1), Part(2)

# ---- 1. every strip off the main bus and muted ---------------------------
for s in range(1, 33):
    w(p1, 'Chan%03dMainOn001' % s, 0)
    w(p1, 'Chan%03dMute001'  % s, 1)     # bool on this wire, so 1 not f32

# ---- 2. the other seventeen main-bus sources on chip 2 -------------------
for fam in ('Usb', 'Bt', 'CodecAux', 'Pi'):
    w(p2, '%s001On001' % fam, 0)
for g in range(1, 5):
    w(p2, 'Grp%03dMute001' % g, 1)

# ---- 3. the main chain itself: unity, unmuted, no delay, flat -----------
w(p2, 'Main001Level001', f32(1.0), 4)
w(p2, 'Main001Mute001', 0)
w(p2, 'Main001Delay001', f32(0.0))
for b in range(1, 29):
    w(p2, 'Main001Geq%03d' % b, f32(0.0))

# ---- 4. NOW open strip 1 only -------------------------------------------
w(p1, 'Chan001Level001', f32(1.0), 4)    # unity
w(p1, 'Chan001Pan001',   f32(0.0), 4)    # centre -> equal L and R
w(p1, 'Chan001Mute001',  0)
w(p1, 'Chan001MainOn001', 1)
time.sleep(1.0)

print('cells written: %d   missing from the contract: %s'
      % (len(written), ', '.join(sorted(set(missing))) if missing else 'none'))
print('CHANNEL 1 -> MAIN L/R at unity, pan centre. Cells changed:')
for c in ('Chan001Level001', 'Chan001Pan001', 'Chan001Mute001',
          'Chan001MainOn001', 'Main001Level001', 'Main001Mute001'):
    print('   %-18s %s' % (c, L.get(c)))

# ---- 5. read the chain back, so "it is routed" is a reading -------------
for sym in ('_buf_C1_FDR_01', '_buf_C1_RTG_01', '_buf_C2_MIX_MAIN_L',
            '_buf_C2_MIX_MAIN_R', '_buf_C2_MAIN_FDR', '_buf_C2_MAIN_ST_OUT'):
    part = p1 if '_C1_' in sym else p2
    if sym in part.sc.sym:
        try:
            print('  %-22s 0x%08X' % (sym, part.sc.peek(part.sc.sym[sym])))
        except Exception as exc:
            print('  %-22s unreadable (%s)' % (sym, exc))
    else:
        print('  %-22s not in the chip %d map' % (sym, part.chip))
