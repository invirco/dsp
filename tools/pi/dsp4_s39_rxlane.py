#!/usr/bin/env python3
"""s39_rxlane.py — READ THE CONVERTER INPUT WHERE THE KERNEL READS IT.

S38-6 scanned `_rx_slot_C1_IN_nn` and found all twelve STATIC ZERO, and
took that as "the input lanes are dead, so a converter clock is not
sufficient". Those variables are dead BY CONSTRUCTION: under
DSP4_BLOCK_KERNELS `_C1_IN_nn_process` reads the SPORT DMA buffer
straight into the block pool, and C1_IN_01.asm says so in its own comment
-- "the slot var is unreferenced -- kept as a scalar purely so
block_io.asm's tables still resolve". Reading them measures nothing.

The lane the kernel actually reads is
    _rx_active_buf + _c1_rx_off[e] + i * _c1_rx_stride[e]
for i in 0..BLOCK-1, with e = _c1_rx_node_entry[strip-1]. That is what
this reads.

THE READ IS A MOSAIC, NOT A BLOCK. Each peek is a two-transaction
handshake serviced once per block, so sixteen consecutive words come from
sixteen DIFFERENT blocks. Peak and activity are meaningful; waveform
shape is NOT, and no frequency is claimed from it.

Arms (the mic pre is live and unchanged throughout; only what drives
AUX 1 moves):
  A  aux 1 master MUTED                 -- nothing driving the XLR
  B  aux 1 open, ch1 send OFF           -- bus open, still nothing to send
  C  aux 1 open, ch1 send -40 dB        -- loop closed, loop gain << 1
  D  aux 1 open, ch1 send   0 dB        -- loop closed, loop gain >= 1
"""
import sys, time, json, struct, math
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
NREAD  = int(_argv[2]) if len(_argv) > 2 else 48
AUX = 1
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
f32 = lambda x: struct.unpack('<I', struct.pack('<f', float(x)))[0]

sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR); sc2.d.resync(); sc2.check_chip()

def cw(sc, chip, name, val, ramp=0):
    e = L.get(name)
    if not e or e[0] != chip:
        return False
    sc.d.link.write(e[2], val & 0xFFFFFFFF, ramp); time.sleep(S.SETTLE)
    return True

rxb  = sc1.peek(sc1.sym['_rx_active_buf'])
ent  = sc1.peek(sc1.sym['_c1_rx_node_entry'])
off  = sc1.peek(sc1.sym['_c1_rx_off'] + ent)
strd = sc1.peek(sc1.sym['_c1_rx_stride'] + ent)
print('lane 1: _rx_active_buf 0x%05X  entry %d  off %d  stride %d\n' % (rxb, ent, off, strd))

def q31(w):
    return (w - (1 << 32) if w & 0x80000000 else w) / float(1 << 31)

def measure(n):
    """Sample the lane at ONE fixed slot repeatedly. A fixed slot read
    many times crosses many blocks, so this is a sample of the lane's
    amplitude distribution -- which is what an arm comparison needs."""
    vals = []
    for i in range(n):
        try:
            # re-read _rx_active_buf each time: the DMA ping-pongs and a
            # stale base would read the half the DSP is not filling.
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            vals.append(q31(sc1.peek(b + off + (i % 16) * strd)))
        except IOError:
            pass
    return vals

def report(tag, note):
    time.sleep(1.5)
    v = measure(NREAD)
    if not v:
        print('ARM %s  %-42s UNREADABLE' % (tag, note)); return None
    pk = max(abs(x) for x in v)
    rms = math.sqrt(sum(x * x for x in v) / len(v))
    nz = sum(1 for x in v if abs(x) > 1e-6)
    dbp = '-inf' if pk <= 0 else '%+.2f' % (20 * math.log10(pk))
    dbr = '-inf' if rms <= 0 else '%+.2f' % (20 * math.log10(rms))
    print('ARM %s  %-42s peak %.6f (%s dBFS)  rms %.6f (%s dBFS)  '
          '%d/%d non-zero' % (tag, note, pk, dbp, rms, dbr, nz, len(v)))
    return pk

# strip 1's own chain stays at unity all the way through; only the aux
# master mute and the ch1->aux send move.
cw(sc1, 1, 'Chan001Gain001', f32(1.0), 1)
cw(sc1, 1, 'Chan001Level001', f32(1.0), 4)
cw(sc1, 1, 'Chan001Mute001', 0)
cw(sc1, 1, 'Chan001AuxPick%03d' % AUX, 3)
cw(sc2, 2, 'Aux%03dLevel001' % AUX, f32(1.0), 4)

def arm_setup(aux_mute, send_on, send_lin):
    cw(sc2, 2, 'Aux%03dMute001' % AUX, 1 if aux_mute else 0)
    cw(sc1, 1, 'Chan001AuxOn%03d' % AUX, 1 if send_on else 0)
    if send_lin is not None:
        cw(sc1, 1, 'Chan001AuxSend%03d' % AUX, f32(send_lin), 4)

arm_setup(True,  False, 0.0);  A = report('A', 'aux 1 master MUTED, send off')
arm_setup(False, False, 0.0);  B = report('B', 'aux 1 open, ch1 send OFF')
arm_setup(False, True,  0.01); C = report('C', 'aux 1 open, ch1 send -40 dB')
arm_setup(False, True,  1.0);  D = report('D', 'aux 1 open, ch1 send  0 dB')
arm_setup(True,  False, 0.0);  E = report('E', 'aux 1 master MUTED again (repeat of A)')

print('\n--- verdict ---')
print('  A (silent) %s   B %s   C %s   D %s   E (repeat A) %s'
      % tuple('%.6f' % x if x is not None else '--' for x in (A, B, C, D, E)))
if A is not None and D is not None and A > 0:
    print('  D / A = %.1f x  (%.1f dB)' % (D / A, 20 * math.log10(D / A)))
