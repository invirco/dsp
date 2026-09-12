#!/usr/bin/env python3
"""s39_rxraw.py — dump RAW converter words per arm; interpret on the host.

The four-arm run through a Q1.31 reading showed every arm pinned at full
scale, including with AUX 1 muted -- i.e. the reading does not respond to
what the DSP drives. Before concluding anything about the analog loop,
the WORDS themselves have to be looked at, because the first sample of
them did not look like Q1.31 audio:

  0x7FFCF800 0x7FFEB300 0x00018600 0x0003B300 0x00025000 ...

Every word is either just under 0x80000000 or just over 0x00000000, and
the low seven bits are always clear. Read as Q1.31 that is a square wave
at full scale. Shifted LEFT one bit it is a small signal straddling zero:
0x7FFCF800 << 1 = 0xFFF9F000 = -0.00019, 0x00018600 << 1 = 0x00030C00 =
+0.00009. This dumps the words and scores BOTH readings so the question
is settled on the data.
"""
import sys, time, json, struct, math
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
N = int(_argv[2]) if len(_argv) > 2 else 64
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

ent  = sc1.peek(sc1.sym['_c1_rx_node_entry'])
off  = sc1.peek(sc1.sym['_c1_rx_off'] + ent)
strd = sc1.peek(sc1.sym['_c1_rx_stride'] + ent)

def grab(n):
    out = []
    for i in range(n):
        try:
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            out.append(sc1.peek(b + off + (i % 16) * strd))
        except IOError:
            pass
    return out

def sgn(v, bits=32):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v

def score(words):
    """Two readings of the same words."""
    asis = [sgn(w) / float(1 << 31) for w in words]
    sh1  = [sgn((w << 1) & 0xFFFFFFFF) / float(1 << 31) for w in words]
    def stat(v):
        pk = max(abs(x) for x in v); rms = math.sqrt(sum(x*x for x in v)/len(v))
        return pk, rms
    return stat(asis), stat(sh1)

def arm(tag, note, aux_mute, send_on, send_lin):
    cw(sc2, 2, 'Aux%03dMute001' % AUX, 1 if aux_mute else 0)
    cw(sc1, 1, 'Chan001AuxOn%03d' % AUX, 1 if send_on else 0)
    if send_lin is not None:
        cw(sc1, 1, 'Chan001AuxSend%03d' % AUX, f32(send_lin), 4)
    time.sleep(1.5)
    w = grab(N)
    if not w:
        print('ARM %s %s -- UNREADABLE' % (tag, note)); return None
    (pa, ra), (ps, rs) = score(w)
    lo7 = sum(1 for x in w if x & 0x7F)
    hi = sum(1 for x in w if 0x40000000 <= x < 0x80000000)
    lo = sum(1 for x in w if x < 0x40000000)
    d = lambda v: '-inf  ' if v <= 0 else '%+6.2f' % (20*math.log10(v))
    print('ARM %s  %s' % (tag, note))
    print('     raw[0:6] %s' % ' '.join('0x%08X' % x for x in w[:6]))
    print('     as Q1.31     peak %.6f %s dBFS   rms %.6f %s dBFS'
          % (pa, d(pa), ra, d(ra)))
    print('     <<1 (Q1.31)  peak %.6f %s dBFS   rms %.6f %s dBFS'
          % (ps, d(ps), rs, d(rs)))
    print('     words with low 7 bits set: %d/%d   in [0.5,1): %d   in [0,0.5): %d'
          % (lo7, len(w), hi, lo))
    return ps, rs

cw(sc1, 1, 'Chan001Gain001', f32(1.0), 1)
cw(sc1, 1, 'Chan001Level001', f32(1.0), 4)
cw(sc1, 1, 'Chan001Mute001', 0)
cw(sc1, 1, 'Chan001AuxPick%03d' % AUX, 3)
cw(sc2, 2, 'Aux%03dLevel001' % AUX, f32(1.0), 4)

A = arm('A', 'aux 1 master MUTED, send off',   True,  False, 0.0)
B = arm('B', 'aux 1 open, ch1 send OFF',       False, False, 0.0)
C = arm('C', 'aux 1 open, ch1 send -40 dB',    False, True,  0.01)
D = arm('D', 'aux 1 open, ch1 send  0 dB',     False, True,  1.0)
E = arm('E', 'aux 1 master MUTED (repeat A)',  True,  False, 0.0)

print('\n--- shifted-reading rms by arm (the one that responds, if any) ---')
for tag, r in (('A', A), ('B', B), ('C', C), ('D', D), ('E', E)):
    print('  %s  rms %s' % (tag, '--' if r is None else '%.8f' % r[1]))
