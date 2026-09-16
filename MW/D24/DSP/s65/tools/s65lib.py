"""s65lib — the cue bus and the RTA on chip 1 (S65) on the bench.

Pair ~/s65 (DSP4_TEST_NODES=1 DSP4_CUE=1 DSP4_RTA=1). The cue / RTA cells are PROPOSED (S65) and live on chip 1's
parameter link directly after the dispatch table, at CUE_SPI_BASE = 4984 (0x1378); cue.asm's cue_spi_layout() is the
one place the offsets are decided and this file mirrors it. Band words are read through the parameter link one raw
word each -- the path the METER block at 0x1200 uses. Law: dBFS = 10 log10(word) (-20 dBFS pk sine -> -23.01)."""
import math, os, sys, time
os.environ['SYMDIR'] = os.environ.get('SYMDIR', '/home/app/s65')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/dspboot')
import s54lib as T                                          # noqa: E402
X = T.X
BASE = 4984
N_CELLS = 118


def SEL(strip):
    return BASE + strip - 1


MAIN_SEL = BASE + 32


def AUX_SEL(n):
    return BASE + 32 + n


def GRP_SEL(n):
    return BASE + 44 + n


MODE, SRC, ACTIVE = BASE + 49, BASE + 50, BASE + 51
RTA_ON, RTA_MODE, RTA_RESET = BASE + 52, BASE + 53, BASE + 54
MTR_L, MTR_R = BASE + 56, BASE + 87
DIAG_RTA_BANDS, DIAG_RTA_OUT = 0xE0C7, 0xE0C6
MON_INPUTSEL_C2 = 0x06FC      # Mon001InputSel001 on chip 2; 13 = Cue under DSP4_CUE
G = 10 ** 0.3
CENTRES = [1000.0 * G ** (k / 3.0) for k in range(-17, 14)]
LABELS = ['20', '25', '31.5', '40', '50', '63', '80', '100', '125', '160', '200', '250', '315', '400', '500', '630', '800',
          '1k', '1.25k', '1.6k', '2k', '2.5k', '3.15k', '4k', '5k', '6.3k', '8k', '10k', '12.5k', '16k', '20k']


def db10(w):
    v = X.from_f32(w)
    return 10 * math.log10(v) if v > 0 else float('-inf')


def nearest(f):
    return min(range(31), key=lambda i: abs(math.log(CENTRES[i] / f)))


class Cue:
    def __init__(self, rig):
        self.R = rig
        self.sc = rig.sc
        for s_ in ('_cue_spi_ptr', '_rta_out', '_buf_C1_CUE_L'):
            if s_ not in self.sc.sym:
                raise SystemExit('%s absent from %s/chip1.sym.json: not the S65 pair' % (s_, os.environ['SYMDIR']))
        nb = self.R.rd(DIAG_RTA_BANDS)
        if nb != 31:
            raise SystemExit('chip-1 RTA_BANDS reads %r, expected 31: the image is not the S65 build' % nb)
        out = self.R.rd(DIAG_RTA_OUT)
        if out != self.sc.sym['_rta_out']:
            raise SystemExit('RTA_OUT 0x%X != map _rta_out 0x%X: stale map' % (out, self.sc.sym['_rta_out']))

    def rd(self, a):
        return self.R.rd(a)

    def wr(self, a, v):
        return self.R.wv(a, v)

    def raw(self, a, v):
        return self.R._retry(self.R.c1.raw_w, a, v & 0xFFFFFFFF)

    def clear(self):
        for s in range(1, 33):
            if self.rd(SEL(s)):
                self.wr(SEL(s), 0)
        for a in [MAIN_SEL] + [AUX_SEL(n) for n in range(1, 13)] + [GRP_SEL(n) for n in range(1, 5)]:
            if self.rd(a):
                self.wr(a, 0)

    def mrd(self, a, tries=4):
        """A METER word: it moves every block, so the scope's settle-vote (two agreeing answers) cannot apply. One
        paced ask per try; a dropped answer reads 0 on this link, so the first non-zero answer is taken and 0 only
        when every try says so (a genuinely silent band)."""
        for _ in range(tries):
            try:
                v = self.sc._ask(a)
            except (IOError, OSError):
                v = None
                try:
                    self.sc.d.resync()
                except Exception:
                    pass
            if v:
                return v
        return 0

    def bands(self):
        """62 values, dB: [L 1..31], [R 1..31], through the parameter link."""
        w = [self.mrd(MTR_L + i) for i in range(62)]
        return [db10(v) for v in w[:31]], [db10(v) for v in w[31:]]

    def band(self, ch, i):
        return db10(self.mrd((MTR_R if ch == 'R' else MTR_L) + i))

    def peek(self, name, off=0):
        return self.R._retry(self.sc.peek, self.sc.sym[name] + off)
