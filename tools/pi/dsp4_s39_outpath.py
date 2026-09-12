#!/usr/bin/env python3
"""s39_outpath.py — where does strip 1 stop on the way to AUX 1's XLR?

Each point is sampled REPEATEDLY at a fixed offset rather than read as
one contiguous block. A peek is a two-transaction handshake serviced once
per block, so sixteen consecutive addresses come from sixteen different
blocks -- a mosaic. "Is this point ever non-zero over N blocks" is a
question a mosaic CAN answer; "what is the waveform" is not, and none is
claimed.

Path: strip 1 GAIN -> ... -> FDR -> RTG -> chip 1 aux bus accumulator ->
_tx_slot_C1_BUS_AUX_01_SEND (the interchip send) -> chip 2
_buf_C2_MIX_AUX_01 -> AUX 1 chain -> chip 2 TX DMA -> DAC -> XLR.
"""
import sys, time, json, struct
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
REPS = int(_argv[2]) if len(_argv) > 2 else 24
AUX = 1
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
f32 = lambda x: struct.unpack('<I', struct.pack('<f', float(x)))[0]

sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR); sc2.d.resync(); sc2.check_chip()

def cw(sc, chip, name, val, ramp=0):
    e = L.get(name)
    if not e or e[0] != chip: return False
    sc.d.link.write(e[2], val & 0xFFFFFFFF, ramp); time.sleep(S.SETTLE)
    return True

# strip 1 wide open onto MAIN and AUX 1
for n, v, r in (('Chan001Gain001', f32(1.0), 1), ('Chan001Level001', f32(1.0), 4),
                ('Chan001Pan001', f32(0.0), 4), ('Chan001Mute001', 0, 0),
                ('Chan001MainOn001', 1, 0), ('Chan001AuxPick001', 3, 0),
                ('Chan001AuxSend001', f32(1.0), 4), ('Chan001AuxOn001', 1, 0)):
    cw(sc1, 1, n, v, r)
for n, v, r in (('Aux001Level001', f32(1.0), 4), ('Aux001Mute001', 0, 0),
                ('Main001Level001', f32(1.0), 4), ('Main001Mute001', 0, 0)):
    cw(sc2, 2, n, v, r)
time.sleep(1.0)

def probe(sc, tag, addr, n=REPS):
    """Sample ONE address over n blocks. Reports how often it is non-zero."""
    vals = []
    for _ in range(n):
        try:
            vals.append(sc.peek(addr))
        except IOError:
            pass
        time.sleep(0.01)
    if not vals:
        print('  %-34s UNREADABLE' % tag); return
    nz = [v for v in vals if v not in (0,)]
    q = lambda w: (w - (1 << 32) if w & 0x80000000 else w) / float(1 << 28)
    pk = max(abs(q(v)) for v in vals)
    print('  %-34s %2d/%2d non-zero, %2d distinct | |peak| %.6f (Q4.28) | %s'
          % (tag, len(nz), len(vals), len(set(vals)), pk,
             ' '.join('0x%08X' % v for v in vals[:3])))

B1 = sc1.sym['_blk_pool']
print('=== chip 1: pool slots, each sampled over %d blocks ===' % REPS)
for name, slot in (('chainA  (IN / post-FDR)', 0), ('chainB  (post GAIN)', 1),
                   ('FDR L', 2), ('FDR R', 3),
                   ('tap post-trim', 4), ('tap EQ', 5),
                   ('tap pre-fader', 6), ('tap post-fader', 7)):
    probe(sc1, name, B1 + slot * 16 + 4)     # word 4 of each slot

print('\n=== chip 1: the FADER and ROUTER node state (SPI read, in-image) ===')
for chip, sc, cell in ((1, sc1, 'Chan001Level001'), (1, sc1, 'Chan001Mute001'),
                       (1, sc1, 'Chan001Pan001'), (1, sc1, 'Chan001AuxOn001'),
                       (1, sc1, 'Chan001AuxSend001'), (1, sc1, 'Chan001AuxPick001'),
                       (1, sc1, 'Chan001MainOn001')):
    e = L[cell]
    try:
        v = sc.rd(e[2])
        f = struct.unpack('<f', struct.pack('<I', v))[0]
        print('  %-22s spi 0x%04X = 0x%08X  (float %.6f)' % (cell, e[2], v, f))
    except IOError:
        print('  %-22s unreadable' % cell)

print('\n=== chip 1: aux bus accumulator and the interchip send ===')
for n in ('_bus_acc_aux_01', '_tx_slot_C1_BUS_AUX_01_SEND'):
    if n in sc1.sym:
        probe(sc1, n, sc1.sym[n] + 2)
    else:
        print('  %-34s not in map' % n)

print('\n=== chip 2: the aux 1 mix and chain ===')
for n in ('_buf_C2_MIX_AUX_01', '_buf_C2_AUX_AFB_01', '_buf_C2_MIX_MAIN_L',
          '_buf_C2_MAIN_FDR'):
    if n in sc2.sym:
        probe(sc2, n, sc2.sym[n] + 2)
    else:
        print('  %-34s not in map' % n)

print('\n=== chip 2: the TX DMA buffer -- what actually reaches the DACs ===')
try:
    tb = sc2.peek(sc2.sym['_tx_active_buf'])
    print('  _tx_active_buf 0x%05X' % tb)
    for lane in range(0, 8):
        off = sc2.peek(sc2.sym['_c2_tx_off'] + lane)
        strd = sc2.peek(sc2.sym['_c2_tx_stride'] + lane)
        probe(sc2, 'TX lane %d (off %d stride %d)' % (lane, off, strd),
              tb + off + 2 * strd, n=8)
except (IOError, KeyError) as exc:
    print('  unreadable: %s' % exc)
