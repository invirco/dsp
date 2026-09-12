#!/usr/bin/env python3
"""s39_loop.py — IS THE AUX 1 -> MIC 1 PATCH CARRYING AUDIO, ELECTRICALLY?

Four arms on the same boot, every reading an SPI meter read (no symbol
map anywhere -- see dsp4_s39_symcheck.py for why that matters):

  A  strip 1 MUTED, aux send OFF      -- the floor of the instrument
  B  strip 1 open, aux send OFF       -- LOOP OPEN: what MIC 1 hears with
                                         nothing driving AUX 1. This is
                                         the mic pre's own noise floor.
  C  strip 1 open, aux send -40 dB    -- LOOP CLOSED at a loop gain far
                                         below 1: a stable rise over B is
                                         the patch carrying signal.
  D  strip 1 open, aux send unity     -- LOOP CLOSED at loop gain >= 1

A rises only in C and D, and returns to the floor in A, when the signal
is real and travelling DSP -> DAC -> AUX 1 XLR -> MIC 1 -> ADC -> DSP.
If MIC 1's lane were dead, C and D would read exactly what B reads.

The meters are linear peak (Mtr001) and linear TRUE rms (Mtr002); they
are float words the kernel publishes and the dispatch table exposes
read-only, so reading them costs the audio path nothing.
"""
import json, sys, time, math, struct
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

AUX = 1
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
f32 = lambda x: struct.unpack('<I', struct.pack('<f', float(x)))[0]
un  = lambda w: struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]
db  = lambda v: '-inf   ' if v <= 0 else '%+7.2f' % (20 * math.log10(v))


class Chip:
    def __init__(self, n):
        self.n = n
        self.sc = S.Scope(n, symfile='/home/app/dspboot/chip%d.sym.json' % n)
        self.sc.d.resync(); self.sc.check_chip()
    def a(self, name):
        e = L.get(name)
        return e[2] if e and e[0] == self.n else None
    def w(self, name, val, ramp=0):
        a = self.a(name)
        if a is None: return False
        self.sc.d.link.write(a, val & 0xFFFFFFFF, ramp); time.sleep(S.SETTLE)
        return True
    def r(self, name):
        a = self.a(name)
        if a is None: return None
        try: return self.sc.rd(a)
        except IOError: return None


c1, c2 = Chip(1), Chip(2)

# DIAG_CLEAR resets _mtr_peak's high-water mark; without it every arm
# inherits the loudest thing that happened in any earlier arm and the
# whole experiment reads as one flat pinned line.
DIAG_CLEAR = 0xE0FF


def clear_and_settle(seconds=2.0):
    for ch in (c1, c2):
        try: ch.sc.d.write(DIAG_CLEAR, 1)
        except IOError: pass
    time.sleep(seconds)


def sample(n=4, gap=0.25):
    """Peak is a decaying high-water mark and rms is a 300 ms average, so
    take several and print them all -- a single reading cannot tell a
    settled level from one point on a decay."""
    out = {}
    for name, ch in (('Chan001Mtr001', c1), ('Chan001Mtr002', c1),
                     ('Aux001Mtr001', c2)):
        vals = []
        for _ in range(n):
            v = ch.r(name)
            if v is not None: vals.append(un(v))
            time.sleep(gap)
        out[name] = vals
    return out


def arm(tag, mute, send_lin, note):
    c1.w('Chan001Mute001', 1 if mute else 0)
    if send_lin is None:
        c1.w('Chan001AuxOn%03d' % AUX, 0)
    else:
        c1.w('Chan001AuxSend%03d' % AUX, f32(send_lin), 4)
        c1.w('Chan001AuxOn%03d' % AUX, 1)
    clear_and_settle()
    m = sample()
    print('\nARM %s  %s' % (tag, note))
    for name, vals in m.items():
        if not vals:
            print('  %-14s --' % name); continue
        print('  %-14s %s   |  peak-of-run %.6f = %s dBFS'
              % (name, ' '.join('%.6f' % v for v in vals),
                 max(vals), db(max(vals))))
    return m


# leave the strip's own chain at unity throughout; only MUTE and the AUX
# SEND move between arms, so nothing else can explain a difference.
c1.w('Chan001Gain001', f32(1.0), 1)
c1.w('Chan001Level001', f32(1.0), 4)
c1.w('Chan001Pan001', f32(0.0), 4)
c1.w('Chan001AuxPick%03d' % AUX, 3)
c2.w('Aux%03dLevel001' % AUX, f32(1.0), 4)
c2.w('Aux%03dMute001' % AUX, 0)

A = arm('A', True,  None,   'strip 1 MUTED, aux send OFF  -- instrument floor')
B = arm('B', False, None,   'strip 1 OPEN,  aux send OFF  -- LOOP OPEN, mic 1 floor')
C = arm('C', False, 0.01,   'strip 1 OPEN,  aux send -40 dB -- LOOP CLOSED, gain << 1')
D = arm('D', False, 1.0,    'strip 1 OPEN,  aux send  0 dB  -- LOOP CLOSED, gain >= 1')

print('\n--- verdict ---')
for name in ('Chan001Mtr001', 'Chan001Mtr002', 'Aux001Mtr001'):
    pk = lambda m: (max(m[name]) if m[name] else float('nan'))
    print('  %-14s A %s  B %s  C %s  D %s'
          % (name, db(pk(A)), db(pk(B)), db(pk(C)), db(pk(D))))

# leave it safe: loop open, strip unmuted
c1.w('Chan001AuxOn%03d' % AUX, 0)
c1.w('Chan001AuxSend%03d' % AUX, f32(0.0), 4)
print('\nleft with the aux send OFF (loop open), strip 1 unmuted.')
