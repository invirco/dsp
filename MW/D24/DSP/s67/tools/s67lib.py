"""s67lib — the first mixer function on the part: strip 5 through gain -> EQ/dyn -> fader -> pan -> bus assign -> the
chip-1 MAIN L/R and AUX 1 sums, measured with TEST_MEAS where the strip maths ends: at the bus (S67).

PAIR ~/s67 (DSP4_TEST_NODES=1 + the S67 bus taps): MeasChan / XtalkSrc / XtalkDst 33/34 = chip-1 MAIN L/R bus block,
35..46 = AUX 1..12, 47..50 = GRP 1..4 (tools/dsp/dsp_codegen.py TEST_MEAS_BUS_CODES). Every reading is the window's
coherent fit against TEST_OSC's own reference (s54lib.Rig.windows: H = loop transfer, |H| dB and phase), so a level
is a coherent level and not an RMS.

Stimulus: 'analog' = TEST_OSC on donor strip 6 -> AUX 1 -> J45 -> loop cable -> J25 -> MIC 5 preamp -> strip 5 lane
(the real analog input); 'osc' = TEST_OSC injected at strip 5's input node (replaces the lane), or OscChan 99 (every
strip) for the two-strip sum. Strip 5 is never on AUX 1 in 'analog' mode: AUX 1 is the loop's own source.

Nothing here writes AN_EN (GPIO 26); the bring-up script does, once, per the dispatch."""
import json, math, os, subprocess, sys, time

os.environ['SYMDIR'] = os.environ.get('SYMDIR', '/home/app/s67')
HOME = '/home/app/s67'
sys.path.insert(0, HOME)
sys.path.insert(1, '/home/app/s54')
import s54lib as T                                          # noqa: E402
import pan_table as PT                                      # noqa: E402
X = T.X
DATA = os.environ.get('S67_DATA', HOME + '/data')
os.makedirs(DATA, exist_ok=True)

STRIP, DONOR, OTHER = 5, 6, 6
MAIN_L, MAIN_R, AUX1 = 33, 34, 35
A_LCR_LAW = 4966                    # Sys LcrLaw (chip 1 0x1366)
A_LCR_ON5 = 0x134A                  # C1_FDR_05 LcrOn (no D24 cell)
A_EQ5, A_EQ5_SWAP = 0x0250, 0x0264  # C1_EQ_05 20 float coeffs (4 x b0 b1 b2 a1 a2), swap trigger
A_COMP5 = dict(on=0x0278, thr=0x0279, rat=0x027A, att=0x027B, rel=0x027C, make=0x027D, knee=0x027E, par=0x027F)
UNITY_BQ = [1.0, 0.0, 0.0, 0.0, 0.0]
FS = 48000.0


def P(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def db(x):
    return 20 * math.log10(x) if x > 0 else float('-inf')


def rbj_peaking(f0, q, gain_db):
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / FS
    al = math.sin(w0) / (2.0 * q)
    b0, b1, b2 = 1 + al * A, -2 * math.cos(w0), 1 - al * A
    a0, a1, a2 = 1 + al / A, -2 * math.cos(w0), 1 - al / A
    return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0]


def bq_mag_db(c, f):
    b0, b1, b2, a1, a2 = c
    w = 2 * math.pi * f / FS
    z1 = complex(math.cos(w), -math.sin(w))
    z2 = z1 * z1
    return db(abs((b0 + b1 * z1 + b2 * z2) / (1 + a1 * z1 + a2 * z2)))


def pan_legs(law, idx):
    """(gL, gR) linear, a non-LCR strip, the node's own table (tools/dsp/pan_table.py)."""
    l, _, r = PT.read_legs(law, idx, 0)
    return l / 2.0 ** 28, r / 2.0 ** 28


class Rig(T.Rig):
    def __init__(self, logpath):
        super().__init__(logpath)
        for s_ in ('_buf_C1_BUS_MAIN_L', '_buf_C1_BUS_AUX_01'):
            if s_ not in self.sc.sym:
                raise SystemExit('%s absent from the map' % s_)
        self.mode = None

    # ---- cells ----------------------------------------------------------
    def cw(self, name, val, ramp=0):
        """Write a cell and read it back. A RAMPED float cell reads back the ramp's own end point, which for a send
        is not always the target word: AuxSend001 1.0 by ramp 4 lands on 0x3F800002 (+2.4e-7) and stays there, so
        a ramped write is accepted within 1e-5 of the target."""
        if not ramp:
            return self.c1.wv(name, val, ramp)
        for _ in range(6):
            self._retry(self.c1.w, name, val, ramp)
            time.sleep(0.05)
            got = self.cr(name)
            if got == val & 0xFFFFFFFF or abs(X.from_f32(got) - X.from_f32(val)) <= 1e-5 * max(1.0, abs(X.from_f32(val))):
                return True
        raise SystemExit('%s did not land: wanted 0x%08X read 0x%08X' % (name, val & 0xFFFFFFFF, got))

    def cr(self, name):
        return self._retry(self.c1.r, name)

    def level(self, lin, strip=STRIP):
        self.cw('Chan%03dLevel001' % strip, X.f32(lin), 4)

    def pan_idx(self, idx, strip=STRIP):
        self.cw('Chan%03dPan001' % strip, X.f32(PT.pan_of(idx)), 4)

    def an_en(self):
        return subprocess.run(['pinctrl', 'get', '26'], capture_output=True, text=True).stdout.strip()

    def overruns(self):
        return self._retry(self.sc.peek, self.sc.sym['_diag_blk_overrun'])

    def busword(self, sym, n=16):
        a = self.sc.sym[sym]
        return [self._retry(self.sc.peek, a + i) for i in range(n)]

    # ---- the base image -------------------------------------------------
    def base(self, mode):
        """Strips 1-24 muted, off MAIN and AUX 1-8, except strip 5 (and strip 6: the analog donor on AUX 1 alone, or
        the second summing strip in 'osc' mode, muted until used). Strip 5 transparent: gain unity, EQ unity, gate/
        comp/tube off, fader unity, pan centre (idx 63), on MAIN, off AUX 1 (AuxSend 1.0 PostFdr ready)."""
        c1 = self.c1
        self.mode = mode
        for s in range(1, 25):
            if s in (STRIP, DONOR):
                continue
            pfx = 'Chan%03d' % s
            if self.cr(pfx + 'Mute001') != 1:
                self.cw(pfx + 'Mute001', 1)
            if self.cr(pfx + 'MainOn001') != 0:
                self.cw(pfx + 'MainOn001', 0)
            for a in range(1, 9):
                if self.cr(pfx + 'AuxOn%03d' % a) != 0:
                    self.cw(pfx + 'AuxOn%03d' % a, 0)
        for s in (STRIP, DONOR):
            pfx = 'Chan%03d' % s
            self.cw(pfx + 'Gain001', X.f32(1.0), 1)
            self.cw(pfx + 'Pol001', 0)
            self.cw(pfx + 'Level001', X.f32(1.0), 4)
            for k in ('CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001'):
                self.cw(pfx + k, 0)
            for a in range(1, 9):
                self.cw(pfx + 'AuxOn%03d' % a, 0)
            self.cw(pfx + 'Mute001', 0)
            self.cw('Chan%03dAuxPick001' % s, 3)
            self.cw('Chan%03dAuxSend001' % s, X.f32(1.0), 4)
            self.pan_idx(PT.PAN_CENTRE, s)
        self.eq_bands([UNITY_BQ] * 4)
        self.wv(A_LCR_LAW, 0)
        self.wv(A_LCR_ON5, 0)
        self.cw('Chan%03dMainOn001' % STRIP, 1)
        if mode == 'analog':
            self.cw('Chan%03dAuxOn001' % DONOR, 1)
        else:
            self.cw('Chan%03dMute001' % DONOR, 1)

    # ---- EQ / comp on strip 5 ------------------------------------------
    def eq_bands(self, bands):
        """bands: DIRECT-FORM (b0 b1 b2 a1 a2) per band. The wire under DSP4_BQ_FLOAT=1 (shipping and this pair) is
        the OFFSET encoding (b0, b1+2b0, b2-b0, 2+a1, 1-a2) -- tools/dsp/geq_ref.offset_form -- NOT direct form:
        direct RBJ words written raw are a different, here unstable, filter (S67-5)."""
        # tools/pi/dsp4_bqwire.py's check, inline (this lib is staged flat on the bench): refuse a fixed-arm image
        cfg = self.rd(0xE0EA)
        if (cfg & 0xFF000000) != 0xCF000000 or not (cfg >> 12) & 1:
            raise SystemExit('DIAG_BUILD_CFG 0x%08X is not a DSP4_BQ_FLOAT=1 image: eq_bands writes the offset form' % cfg)
        for b, c in enumerate(bands):
            b0, b1, b2, a1, a2 = c
            for j, v in enumerate((b0, b1 + 2.0 * b0, b2 - b0, 2.0 + a1, 1.0 - a2)):
                self.wv(A_EQ5 + 5 * b + j, X.f32(v))
        for _ in range(3):
            self._retry(self.c1.raw_w, A_EQ5_SWAP, 1)
        time.sleep(0.1)

    def comp(self, on, thr=None, ratio=None, knee=None):
        if thr is not None:
            self.wv(A_COMP5['thr'], X.f32(thr))
        if ratio is not None:
            self.wv(A_COMP5['rat'], X.f32(ratio))
        if knee is not None:
            self.wv(A_COMP5['knee'], X.f32(knee))
        self.wv(A_COMP5['on'], 1 if on else 0)

    def comp_state(self):
        return {k: (self.rd(a) if k == 'on' else X.from_f32(self.rd(a))) for k, a in A_COMP5.items()}

    # ---- the measurement --------------------------------------------------
    def m(self, chans, n=3, settle=3, tag=''):
        """{chan: {'H_db', 'H_deg', 'coh_pk_dbfs', 'rms', 'noise'}} averaged over n untorn windows each."""
        out = {}
        for ch in chans:
            self.meas(ch)
            rec = self.windows(n, settle_windows=settle, tag='%s/%d' % (tag, ch))
            d = {k: T.summ(rec, k) for k in ('H_db', 'coh_pk_dbfs', 'rms', 'noise')}
            d['H_deg'] = T.phase_avg(rec) if any('H_deg' in r for r in rec['rows']) else None
            d['spread'] = T.spread(rec, 'H_db')
            out[ch] = d
        return out


def save(name, obj):
    with open('%s/%s.json' % (DATA, name), 'w') as f:
        json.dump(obj, f, indent=1)
