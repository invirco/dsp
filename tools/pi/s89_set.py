#!/usr/bin/env python3
"""s89_set.py <symdir> <cell>=<val>[:ramp] ...  -- write/read named cells by contract name.

Values: 0x.. raw word, f<float> as IEEE-754, plain int. A bare cell name reads it.
Nothing here peeks; every read is an SPI parameter read through the image's own
dispatch table (the S39-2 rule).

A NAME MAY ALSO BE AN ADDRESS: `cN@ADDR` (e.g. `c2@2175`, `c2@0x87F`) reaches a
chip-N dispatch address directly. It is the SAME path -- the image's own
dispatch table, never a peek -- and it exists for words that are DISPATCHED BUT
NOT CELLED, which today means the S122 panel-haptic block: the cell family is
proposed and not landed (cell names are forever; PW rules them), so until it is
there is no contract name to write. An address form is deliberately ugly to
type: a word that has a cell should be written by its cell.
"""
import json, re, struct, sys, time
_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _ARGV[0]
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def from_f32(w): return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]

class Chip:
    def __init__(self, n):
        self.n = n
        self.sc = S.Scope(n, symfile='%s/chip%d.sym.json' % (SYMDIR, n))
        self.sc.d.resync(); self.sc.check_chip()
    def addr(self, name):
        e = L.get(name)
        return None if e is None or e[0] != self.n else e[2]

chips = {}
_RAW = re.compile(r'^c([12])@(0[xX][0-9a-fA-F]+|\d+)$')

def chip_for(name):
    m = _RAW.match(name)
    if m:
        n = int(m.group(1))
        if n not in chips: chips[n] = Chip(n)
        return chips[n], int(m.group(2), 0)
    e = L.get(name)
    if e is None: return None, None
    n = e[0]
    if n not in chips: chips[n] = Chip(n)
    return chips[n], e[2]

for spec in _ARGV[1:]:
    ramp = 0
    if ':' in spec:
        spec, r = spec.rsplit(':', 1); ramp = int(r)
    if '=' in spec:
        name, val = spec.split('=', 1)
        w = f32(val[1:]) if val.startswith('f') else int(val, 0)
        c, a = chip_for(name)
        if c is None: print('%-26s NOT IN CONTRACT' % name); continue
        c.sc.d.link.write(a, w & 0xFFFFFFFF, ramp)
        time.sleep(0.05)
    else:
        name = spec
        c, a = chip_for(name)
        if c is None: print('%-26s NOT IN CONTRACT' % name); continue
    time.sleep(0.15)
    got = c.sc.rd(a)
    print('%-26s chip%d addr %-6d 0x%08X  %.6f' % (name, c.n, a, got, from_f32(got)))
