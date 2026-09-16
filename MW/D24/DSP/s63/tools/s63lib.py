"""s63lib — S63 gain-change artefacts: a TEST_MEAS capture that SPANS a gain change.

THE SPAN CAPTURE. Clear CaptureReady, arm 16,384 samples on MeasChan, poll `_meas_cap_idx_C1_TEST_MEAS` (samples
copied so far, whole blocks of 16) until it reaches AT (~100 ms), make the change, poll idx once more, wait for Ready,
bulk-read the buffer (dsp4_bulk, S62 handshake pair). Every idx poll is bracketed by host time, so the polls give the
host-clock -> capture-sample map: sample(t) = 48000 (t - T0), T0 = median over the last polls of t_mid - (idx + 8)/48000;
the poll residuals' spread is that map's uncertainty. The change's own host bracket is mapped through it.

THE CHANGES.
  hardware step  the 25-byte 595 image by spidev (s55_chain's wire protocol, two passes, pass 2 MISO = image), but
                 CS_M (GPIO 27) is driven by a GPCLR0/GPSET0 write on /dev/gpiomem, not by a `pinctrl` process: the
                 latch is ONE register write whose host time is known to ~10 us. GPIO 27 is already an output (FSEL 1)
                 and its function and pull are never touched, so there is no ownership to release and it cannot float
                 (the S49 CS_M / U2 trap). The pass-1 rising edge is the latch that changes the gain; pass 2 re-latches
                 the same bytes and verifies them.
  digital trim   Chan<nnn>Gain001 by one raw link write with ramp profile 1 (GainFast, the one the GAIN node carries:
                 up 3 ms, down 8 ms, exp), bracketed by host time; read back after the capture.

Nothing here writes AN_EN (GPIO 26)."""
import json, math, mmap, os, struct, subprocess, sys, time

os.environ['SYMDIR'] = os.environ.get('SYMDIR', '/home/app/s63')
HOME = '/home/app/s63'
# the bulk/handshake modules from HOME, imported BEFORE s54lib puts dspboot at the head of sys.path
sys.path.insert(0, HOME)
import dsp4_bulk as BULK                                   # noqa: E402
import dsp4_meascap as MC                                  # noqa: E402
for _p in ('/home/app/s55', '/home/app/s54'):
    sys.path.insert(1, _p)
import s54lib as T                                         # noqa: E402
import spidev                                              # noqa: E402
sys.path.insert(0, '/home/app/dspboot')
import d24_inputs as D24                                   # noqa: E402
X = T.X
FS = 48000.0
SYMDIR = os.environ['SYMDIR']
IDX = '_meas_cap_idx_C1_TEST_MEAS'
DATA = os.environ.get('S63_DATA', HOME + '/data')
os.makedirs(DATA, exist_ok=True)
assert os.path.dirname(os.path.abspath(BULK.__file__)) == HOME, BULK.__file__
assert os.path.dirname(os.path.abspath(MC.__file__)) == HOME, MC.__file__

# the universal table's 25 hardware steps (defs/common/tables/mic-gain-law.csv, S55)
TABLE_CODES = [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 13, 15, 17, 20, 23, 25, 29, 31, 37, 42, 47, 53, 61, 63]
LAW = '/home/app/s63/law.csv'          # S55 per-channel loop gain at 1 kHz, every code (MW/D24/DSP/s55/law.csv)


def P(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def loop_gain(xlr):
    """{code: loop gain dB} for XLR 'J25' from the S55 law (osc on strip 6 -> AUX 1 -> cable -> lane)."""
    g = {}
    for line in open(LAW):
        c = line.strip().split(',')
        if c[0].startswith(xlr + ' '):
            g[int(c[1])] = float(c[2])
    assert len(g) == 64, (xlr, len(g))
    return g


# ---------------------------------------------------------------- CS_M by register
class Gpio27:
    GPSET0, GPCLR0, GPLEV0 = 0x1C, 0x28, 0x34
    BIT = 1 << 27

    def __init__(self):
        fd = os.open('/dev/gpiomem', os.O_RDWR | os.O_SYNC)
        self.m = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        os.close(fd)
        fsel = (struct.unpack_from('<I', self.m, 0x08)[0] >> 21) & 7
        if fsel != 1:
            raise SystemExit('GPIO 27 is not an output (FSEL %d): refusing to drive CS_M by register' % fsel)

    def lo(self):
        struct.pack_into('<I', self.m, self.GPCLR0, self.BIT)

    def hi(self):
        struct.pack_into('<I', self.m, self.GPSET0, self.BIT)

    def level(self):
        return (struct.unpack_from('<I', self.m, self.GPLEV0)[0] >> 27) & 1


G27 = None


def chain_send_timed(image, speed=100000, fix_cs=True, gap_s=0.0, times=None):
    """s55_chain.send with CS_M by register; returns (ok, got, t_latch_lo, t_latch_hi) for the pass-1 latch.
    gap_s: a pause between the passes (the latch test); times: a list that receives every edge (pass, 'lo'/'hi', t)."""
    global G27
    if G27 is None:
        G27 = Gpio27()
    assert len(image) == 25
    spi = spidev.SpiDev(); spi.open(0, 0)
    old = (spi.mode, spi.max_speed_hz, spi.no_cs)
    got, tl = [], None
    try:
        spi.no_cs = True; spi.mode = 0; spi.max_speed_hz = speed
        for k in range(2):
            if k and gap_s:
                time.sleep(gap_s)
            t2 = time.time(); G27.lo()
            got.append(spi.xfer2(list(image)))
            t0 = time.time(); G27.hi(); t1 = time.time()
            if times is not None:
                times += [(k + 1, 'lo', t2), (k + 1, 'hi', t0)]
            if k == 0:
                tl = (t0, t1)
    finally:
        G27.hi()
        spi.mode, spi.max_speed_hz, spi.no_cs = old
        spi.close()
    if fix_cs:
        subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
    return got[1] == list(image), got, tl[0], tl[1]


def byte(mute=0, phantom=0, gain=0):
    return (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1)


# ---------------------------------------------------------------- the rig
class Rig(T.Rig):
    """S55's image (the 16 powered registers open at code 0, U15's muted, INSTR 0) with the channel under test at
    its code; strip 6 = TEST_OSC donor on AUX 1 (strip 1 when the lane IS strip 6)."""

    def __init__(self, logpath):
        super().__init__(logpath)
        self.base = [0x00] * 16 + [0x01] * 8 + [0x00]
        self.p = None
        self.code = None
        self.trim_db = None
        self.lane = None
        self.gain_addr = None
        self.t_change = 0.0

    def select(self, xlr, p, lane):
        self.xlr, self.p, self.lane = xlr, p, lane
        self.gain_addr = X.L['Chan%03dGain001' % lane][2]

    def image(self, code):
        img = list(self.base)
        img[self.p] = byte(gain=code)
        return img

    def set_code(self, code):
        for _ in range(4):
            ok, got, a, b = chain_send_timed(self.image(code))
            if ok:
                break
        if not ok:
            raise SystemExit('chain image code %d NOT VERIFIED: %s' % (code, got))
        T.log({'ev': 'chain', 'p': self.p, 'code': code, 'verified': ok})
        self.code = code
        self.t_change = time.time()

    def set_trim(self, db):
        self.c1_gain_wv(10 ** (db / 20.0))
        self.trim_db = db
        self.t_change = time.time()

    def c1_gain_wv(self, lin):
        w = X.f32(lin)
        for _ in range(8):
            self._retry(self.c1.raw_w, self.gain_addr, w, 1)
            if self.rd(self.gain_addr) == w:
                return
        raise SystemExit('Gain001 on strip %d did not land' % self.lane)

    def tone(self, level_db):
        if level_db is None:
            if self.rd(T.A_OSCON) != 0:
                self.wv(T.A_OSCON, 0)
                self.t_change = time.time()
            self.on = False
            return
        w = X.f32(10 ** (level_db / 20.0))
        changed = False
        if self.rd(T.A_OSCFREQ) != X.f32(1000.0):
            self.wv(T.A_OSCFREQ, X.f32(1000.0)); changed = True
        if self.rd(T.A_OSCLEVEL) != w:
            self.wv(T.A_OSCLEVEL, w); changed = True
        if self.rd(T.A_OSCON) != 1:
            self.wv(T.A_OSCON, 1); changed = True
        if changed:
            self.t_change = time.time()
        self.on = True

    # ---- the span capture ------------------------------------------------
    def span(self, change, at=4800, n=16384, timeout=3.0, fit_last=40):
        sc = self.sc
        pk = lambda a: MC._retry(sc, sc.peek, a)
        a_idx = sc.sym[IDX]
        ovr_sym = sc.sym['_diag_blk_overrun']
        for attempt in range(3):
            for _ in range(8):
                sc.d.write(MC.A_CAP_READY, 0)
                time.sleep(0.002)
                if self.rd(MC.A_CAP_READY) == 0:
                    break
            else:
                raise IOError('CaptureReady would not clear')
            ovr0 = pk(ovr_sym)
            sc.d.write(MC.A_CAP_ARM, n)
            t_arm = time.time()
            pts, dropped = [], False
            while True:
                t0 = time.time(); v = pk(a_idx); t1 = time.time()
                pts.append((t0, t1, v))
                if v >= at:
                    break
                if v == 0 and t1 - t_arm > 0.5:
                    dropped = True
                    break
            if dropped:
                T.log({'ev': 'span_arm_dropped', 'attempt': attempt})
                continue
            ev = change()
            t0 = time.time(); v_after = pk(a_idx); t1 = time.time()
            pts_after = (t0, t1, v_after)
            got = 0
            te = time.time()
            while time.time() - te < timeout:
                time.sleep(0.03)
                try:
                    if sc._ask(MC.A_CAP_READY):
                        got = self.rd(MC.A_CAP_READY)
                        break
                except (IOError, OSError):
                    pass
            if not got:
                T.log({'ev': 'span_never_ready', 'attempt': attempt})
                continue
            ovr1 = pk(ovr_sym)
            tr = time.time()
            vals, binfo = BULK.read(sc, sc.sym[MC.BUF], got, log=lambda *a: None)
            read_s = time.time() - tr
            break
        else:
            raise IOError('span capture failed 3 times')
        # host clock -> capture sample map from the polls that ran while the buffer filled
        use = [q for q in pts if q[2] > 0][-fit_last:]
        offs = sorted(((q[0] + q[1]) / 2 - (q[2] + 8) / FS) for q in use)
        T0 = offs[len(offs) // 2]
        res = [(((q[0] + q[1]) / 2 - T0) * FS - q[2]) for q in use]
        smp = lambda t: (t - T0) * FS
        rec = {'n': got, 'at': at, 'overruns': (ovr1 - ovr0) & 0xFFFFFFFF, 'read_s': round(read_s, 3),
               'read_sum': binfo.get('sum'), 'polls': len(pts), 'fit_n': len(use),
               'map_resid_samples': [round(min(res), 1), round(max(res), 1)],
               'poll_dt_ms_median': round(1000 * sorted(q[1] - q[0] for q in pts)[len(pts) // 2], 3),
               'idx_before': pts[-1][2], 'idx_after': v_after,
               'idx_after_pred': round(smp((pts_after[0] + pts_after[1]) / 2), 1)}
        for k, v in ev.items():
            if k.startswith('t_'):
                rec['s' + k[1:]] = round(smp(v), 1)
            else:
                rec[k] = v
        return rec, vals


def save(vals, rec, tag):
    """samples as little-endian int32 appended to DATA/<tag>.bin; rec (+ offset) appended to DATA/<tag>.jsonl"""
    fn = '%s/%s.bin' % (DATA, tag)
    off = os.path.getsize(fn) // 4 if os.path.exists(fn) else 0
    with open(fn, 'ab') as f:
        f.write(struct.pack('<%dI' % len(vals), *vals))
    rec['bin_off'] = off
    with open('%s/%s.jsonl' % (DATA, tag), 'a') as f:
        f.write(json.dumps(rec) + '\n')


def quick(vals, s_ev):
    """on-bench glance: peak dBFS before the change vs the 100 ms after it (Q4.28, 0 dBFS = 1.0)"""
    x = [(v - (1 << 32) if v & 0x80000000 else v) / float(1 << 28) for v in vals]
    e = int(max(0, min(len(x) - 1, s_ev)))
    pre = max(abs(v) for v in x[max(0, e - 4000):max(1, e - 200)])
    post = max(abs(v) for v in x[e:e + 4800]) if e < len(x) else 0.0
    return T.dbv(pre), T.dbv(post)
