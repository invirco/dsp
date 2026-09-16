"""s64lib — the chip-2 RTA filterbank (S64) on the bench: diag registers, the 62 band words, the stand-in source pair.

Pair ~/s64 (DSP4_TEST_NODES=1 DSP4_RTA=1; chip1 57948d77 = S62's, chip2 9ea76239). Stimulus = TEST_OSC on strip 6 -> AUX 1
(the S56 donor route, unity), so the RTA's L is pointed at `_blk_C2_MIX_AUX_01` and R at `_blk_C2_MIX_AUX_02` (nothing
sends to AUX 2): the graph has no cue bus (S64-1) and the kernel's source is a pointer pair, so the stand-in costs the
same as any source. Law: dBFS = 10 log10(word), the TEST_MEAS RmsResult law (-20 dBFS pk -> -23.01)."""
import math, os, sys, time
os.environ['SYMDIR'] = os.environ.get('SYMDIR', '/home/app/s64')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/dspboot')
import s54lib as T                                          # noqa: E402
X = T.X
RTA_ON, RTA_MODE, RTA_RESET, RTA_SEQ, RTA_SRC_L, RTA_SRC_R, RTA_OUT, RTA_BANDS = range(0xE0C0, 0xE0C8)
G = 10 ** 0.3
CENTRES = [1000.0 * G ** (k / 3.0) for k in range(-17, 14)]
LABELS = ['20', '25', '31.5', '40', '50', '63', '80', '100', '125', '160', '200', '250', '315', '400', '500', '630', '800',
          '1k', '1.25k', '1.6k', '2k', '2.5k', '3.15k', '4k', '5k', '6.3k', '8k', '10k', '12.5k', '16k', '20k']


def db10(w):
    v = X.from_f32(w)
    return 10 * math.log10(v) if v > 0 else float('-inf')


class Rta:
    def __init__(self, rig):
        self.R = rig
        self.c2 = X.Chip(2)
        self.sc = self.c2.sc
        if '_rta_out' not in self.sc.sym:
            raise SystemExit('_rta_out absent from %s/chip2.sym.json: not the RTA pair' % os.environ['SYMDIR'])
        nb = self.rd(RTA_BANDS)
        if nb != 31:
            raise SystemExit('RTA_BANDS reads %r, expected 31: the image is not the RTA build' % nb)
        out = self.rd(RTA_OUT)
        if out != self.sc.sym['_rta_out']:
            raise SystemExit('RTA_OUT 0x%X != map _rta_out 0x%X: stale map' % (out, self.sc.sym['_rta_out']))
        self.out = out

    def rd(self, reg):
        return self.R._retry(self.sc.rd, reg)

    def wr(self, reg, val):
        return self.R._retry(self.sc.wr, reg, val)

    def peek(self, a):
        return self.R._retry(self.sc.peek, a)

    def src(self, left, right):
        self.wr(RTA_SRC_L, self.sc.sym['_blk_' + left])
        self.wr(RTA_SRC_R, self.sc.sym['_blk_' + right])

    def bands(self):
        """62 values, dB: [L 1..31], [R 1..31]."""
        w = [self.peek(self.out + i) for i in range(62)]
        return [db10(v) for v in w[:31]], [db10(v) for v in w[31:]]

    def band(self, ch, i):
        return db10(self.peek(self.out + (31 if ch == 'R' else 0) + i))


def nearest(f):
    return min(range(31), key=lambda i: abs(math.log(CENTRES[i] / f)))
