#!/usr/bin/env python3
"""dsp4_apply_strip.py <strip> — write a strip's per-strip NODE STATE, and
prove it landed WITHOUT using the host symbol map.

WHAT WRITES PER-STRIP NODE STATE ON A D24 (S39-1). Nothing on the host
does today, and there is no separate "apply"/"commit"/"scene" step in the
kernel to find: `chip1/spi_handler.asm` resolves every parameter address
through `_spi_dispatch_c1`, a GENERATED table whose entry for SPI address
0 is literally `_gain_coeff_C1_GAIN_01`. An SPI parameter write IS the
apply path -- direct to the node's own DM word, with `_ramp_set_target`
for the ramped ones -- and the read path (`.spi_read`) resolves the SAME
table to the SAME word, so there is no shadow store anywhere.

The gap is therefore entirely on the HOST side:
  * `dsp4_config.py --product d24` writes the product SCOPE only;
  * `matrix-app` has no DSP address for any strip cell (`MW/D24/MX/
    _matrix.csv` carries 0 DspAdd rows of 4985);
so a D24 boots with every strip at its BUILD-TIME initialiser and nothing
ever moves it. This tool is the missing writer, by cell name out of the
landed contract.

WHY NOT ONE peek() ANYWHERE IN HERE (S39-2). Every read-back is an SPI
PARAMETER read, which resolves its address inside the image. The diag
peek window takes a raw word address from the host's symbol map, and on
this bench that map is not the running image's -- see
`dsp4_s39_symcheck.py`. A peek read-back cannot distinguish "the kernel
holds zero" from "the map sent the read somewhere else".
"""
import json, sys, time
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

STRIP = int(sys.argv[1]) if len(sys.argv) > 1 else 1
AUX   = int(sys.argv[2]) if len(sys.argv) > 2 else 1
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']


def f32(x):
    import struct
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def from_f32(w):
    import struct
    return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]


class Chip:
    def __init__(self, n):
        self.n = n
        self.sc = S.Scope(n, symfile='/home/app/dspboot/chip%d.sym.json' % n)
        self.sc.d.resync(); self.sc.check_chip()

    def cell(self, name):
        e = L.get(name)
        if e is None or e[0] != self.n:
            return None
        return e[2]

    def w(self, name, val, ramp=0):
        a = self.cell(name)
        if a is None:
            return False
        self.sc.d.link.write(a, val & 0xFFFFFFFF, ramp)
        time.sleep(S.SETTLE)
        return True

    def r(self, name):
        a = self.cell(name)
        if a is None:
            return None
        try:
            return self.sc.rd(a)
        except IOError:
            return None


c1, c2 = Chip(1), Chip(2)
missing = []


def W(chip, name, val, ramp=0):
    if not chip.w(name, val, ramp):
        missing.append(name)


# ---- 1. every strip off both buses, muted two ways ----------------------
for s in range(1, 33):
    W(c1, 'Chan%03dMainOn001' % s, 0)
    W(c1, 'Chan%03dAuxOn%03d' % (s, AUX), 0)
    W(c1, 'Chan%03dMute001' % s, 1)
for fam in ('Usb', 'Bt', 'CodecAux', 'Pi'):
    W(c2, '%s001On001' % fam, 0)
for g in range(1, 5):
    W(c2, 'Grp%03dMute001' % g, 1)

# ---- 2. the destination chains at unity, unmuted ------------------------
W(c2, 'Main001Level001', f32(1.0), 4)
W(c2, 'Main001Mute001', 0)
W(c2, 'Aux%03dLevel001' % AUX, f32(1.0), 4)
W(c2, 'Aux%03dMute001' % AUX, 0)

# ---- 3. the strip's own node state, head to tail ------------------------
#   GAIN coeff unity, polarity normal, fader unity, pan centre, unmuted,
#   on MAIN and on AUX n at unity, picked POST-FADER (pickoff 3).
W(c1, 'Chan%03dGain001' % STRIP, f32(1.0), 1)
W(c1, 'Chan%03dPol001' % STRIP, 0)
W(c1, 'Chan%03dLevel001' % STRIP, f32(1.0), 4)
W(c1, 'Chan%03dPan001' % STRIP, f32(0.0), 4)
W(c1, 'Chan%03dMute001' % STRIP, 0)
W(c1, 'Chan%03dMainOn001' % STRIP, 1)
W(c1, 'Chan%03dAuxPick%03d' % (STRIP, AUX), 3)
W(c1, 'Chan%03dAuxSend%03d' % (STRIP, AUX), f32(1.0), 4)
W(c1, 'Chan%03dAuxOn%03d' % (STRIP, AUX), 1)
time.sleep(0.5)

# ---- 4. READ IT ALL BACK THROUGH THE IMAGE'S OWN DISPATCH TABLE ---------
print('strip %d -> MAIN and AUX %d, read back over the SPI parameter link'
      % (STRIP, AUX))
print('  %-24s %-10s %-12s %s' % ('cell', 'wanted', 'read', 'verdict'))
CHECK = [
    (c1, 'Chan%03dGain001' % STRIP,          f32(1.0), 'f'),
    (c1, 'Chan%03dPol001' % STRIP,           0,        'i'),
    (c1, 'Chan%03dLevel001' % STRIP,         f32(1.0), 'f'),
    (c1, 'Chan%03dPan001' % STRIP,           f32(0.0), 'f'),
    (c1, 'Chan%03dMute001' % STRIP,          0,        'i'),
    (c1, 'Chan%03dMainOn001' % STRIP,        1,        'i'),
    (c1, 'Chan%03dAuxOn%03d' % (STRIP, AUX), 1,        'i'),
    (c1, 'Chan%03dAuxSend%03d' % (STRIP, AUX), f32(1.0), 'f'),
    (c1, 'Chan%03dAuxPick%03d' % (STRIP, AUX), 3,      'i'),
    (c2, 'Aux%03dLevel001' % AUX,            f32(1.0), 'f'),
    (c2, 'Aux%03dMute001' % AUX,             0,        'i'),
    (c2, 'Main001Level001',                  f32(1.0), 'f'),
    (c2, 'Main001Mute001',                   0,        'i'),
]
ok = bad = unread = 0
for chip, name, want, kind in CHECK:
    got = chip.r(name)
    if got is None:
        print('  %-24s %-10s %-12s UNREADABLE' % (name, hex(want), '--'))
        unread += 1; continue
    shown = ('%.6f' % from_f32(got)) if kind == 'f' else str(got)
    if got == want:
        ok += 1; verdict = 'ok'
    else:
        bad += 1; verdict = '**MISMATCH (wanted %s)**' % (
            ('%.6f' % from_f32(want)) if kind == 'f' else want)
    print('  %-24s %-10s %-12s %s'
          % (name, ('%.4f' % from_f32(want)) if kind == 'f' else want,
             shown, verdict))
print('  read back: %d ok / %d mismatch / %d unreadable; cells not in the '
      'contract: %s' % (ok, bad, unread,
                        ', '.join(sorted(set(missing))) if missing else 'none'))

# ---- 5. THE METERS -- a map-free level reading of the live chain --------
print('\nmeters (linear, SPI read-back -- no symbol map involved):')
for chip, name, what in ((c1, 'Chan%03dMtr001' % STRIP, 'strip peak, post-trim'),
                         (c1, 'Chan%03dMtr002' % STRIP, 'strip rms, post-fader'),
                         (c2, 'Aux%03dMtr001' % AUX,    'aux %d peak' % AUX),
                         (c2, 'Main001Mtr001',          'main peak')):
    for rep in range(3):
        v = chip.r(name)
        if v is None:
            print('  %-18s %-22s --' % (name, what)); break
        lin = from_f32(v)
        import math
        db = '-inf' if lin <= 0 else '%.2f dBFS' % (20 * math.log10(lin))
        print('  %-18s %-22s 0x%08X  %.9f  %s' % (name, what, v, lin, db))
        time.sleep(0.3)
