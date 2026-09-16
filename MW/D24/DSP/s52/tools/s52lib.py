"""s52lib — shared bench helpers for S52 (s49tap pair)."""
import json, math, struct, sys, time
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

import os
SYMDIR = os.environ.get('SYMDIR', '/home/app/s49tap')
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
CFG_COMMIT, CFG_PATCH_BASE = 0xF004, 0xF010
from dsp4_config import D24_INPUT_PATCH as _P  # the landed patch (S58: netlist order)
D24_PATCH = list(_P)


def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def from_f32(w): return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]
def s32(w): return w - (1 << 32) if w & 0x80000000 else w
def db(x): return 20 * math.log10(x) if x > 0 else float('-inf')


class Chip:
    def __init__(self, n):
        self.n = n
        self.sc = S.Scope(n, symfile='%s/chip%d.sym.json' % (SYMDIR, n))
        self.sc.d.resync(); self.sc.check_chip()

    def raw_w(self, addr, val, ramp=0):
        self.sc.d.link.write(addr, val & 0xFFFFFFFF, ramp)
        time.sleep(S.SETTLE)

    def w(self, name, val, ramp=0):
        e = L[name]; assert e[0] == self.n, name
        self.raw_w(e[2], val, ramp)

    def r(self, name):
        return self.sc.rd(L[name][2])

    def wv(self, name, val, ramp=0, tries=6):
        for _ in range(tries):
            self.w(name, val, ramp)
            if self.r(name) == (val & 0xFFFFFFFF):
                return True
        raise SystemExit('%s did not land' % name)


def lane(c1, n, reads=32):
    sc = c1.sc
    e = sc.peek(sc.sym['_c1_rx_node_entry'] + n - 1)
    off = sc.peek(sc.sym['_c1_rx_off'] + e); st = sc.peek(sc.sym['_c1_rx_stride'] + e)
    w = []
    for i in range(reads):
        try:
            b = sc.peek(sc.sym['_rx_active_buf'])
            w.append(sc.peek(b + off + (i % 16) * st))
        except IOError:
            pass
    if not w:
        return e, None, None
    r = math.sqrt(sum((s32(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    return e, db(r), db(max(abs(s32(x)) / 2.0 ** 31 for x in w))


def node_entry(c1, n):
    return c1.sc.peek(c1.sc.sym['_c1_rx_node_entry'] + n - 1)


def apply_patch(c1, patch):
    for i, v in enumerate(patch):
        c1.raw_w(CFG_PATCH_BASE + i, v)
    c1.raw_w(CFG_COMMIT, 1)
    time.sleep(0.5)


def strip_unity(c1, s):
    """Strip s transparent: unity gain/fader, unmuted, dynamics/EQ/tube off, off both buses."""
    p = 'Chan%03d' % s
    c1.wv(p + 'Gain001', f32(1.0), 1)
    c1.wv(p + 'Pol001', 0)
    c1.wv(p + 'Level001', f32(1.0), 4)
    for k in ('CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001'):
        c1.wv(p + k, 0)
    for a in range(1, 9):
        c1.wv(p + 'AuxOn%03d' % a, 0)
    c1.wv(p + 'Mute001', 0)
