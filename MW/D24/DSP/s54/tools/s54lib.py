"""s54lib — the standard audio test set (T1-T8) driver for the MIC 5 -> AUX 1 loop, no-tap pair.

Stimulus = TEST_OSC on donor strip 6 (-> AUX 1 -> DAC -> J25 -> MIC 5 -> the MIC 5 strip).
Measurement = TEST_MEAS on the MIC 5 strip: RmsResult / ThdResult / NoiseResult, plus the
window's own fit coefficients `_meas_a_` / `_meas_b_` (peeked), which give the
tone's COHERENT amplitude and phase against the injected reference.

Phasor algebra (TEST_OSC is a magic-circle resonator, s' = s + k c, c' = c - k s'):
with s = S z^n and c = C z^n, C/S = (z-1)/k, z = e^{jw}. A measured x = a s + b c
has the phasor X = S (a + b r), r = (z-1)/k. The injected block is s * L * cos(w/2)
and |S| = 1/cos(w/2), so the loop transfer is H = (a + b r) / (L cos(w/2)):
|H| is the loop gain, arg(H) = -w D + analog phase (+pi if inverted).
"""
import cmath, json, math, os, subprocess, sys, time

os.environ.setdefault('SYMDIR', '/home/app/s51_119ea9d9')
import s52lib as X                                          # noqa: E402

FS = 48000.0
A_MEASCHAN, A_RMS, A_THD, A_NOISE, A_XSRC, A_XDST, A_XTALK, A_SEQ = range(4967, 4975)
A_OSCON, A_OSCFREQ, A_OSCLEVEL, A_OSCCHAN = range(4975, 4979)
sys.path.insert(0, '/home/app/dspboot')
import d24_inputs as D24                                     # noqa: E402
DONOR, LOOP = 6, D24.MIC5_STRIP     # MIC 5 = J25's strip under the landed D24_INPUT_PATCH (5 since S58; 20 before)
WIN_S = 4096 / FS
LOG = None


def log(rec):
    rec['t'] = round(time.time(), 3)
    if LOG:
        LOG.write(json.dumps(rec) + '\n'); LOG.flush()


def pct(db):
    return 100.0 * 10 ** (db / 20.0)


def dbv(x):
    return 20 * math.log10(x) if x > 0 else float('-inf')


class Rig:
    def __init__(self, logpath=None):
        global LOG
        subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
        if logpath:
            LOG = open(logpath, 'a')
        self.c1 = X.Chip(1)
        self.sc = self.c1.sc
        for s_ in ('_osc_blk_q_C1_TEST_OSC', '_meas_a_C1_TEST_MEAS', '_meas_b_C1_TEST_MEAS', '_osc_k_C1_TEST_OSC'):
            if s_ not in self.sc.sym:
                raise SystemExit('%s absent from %s: not the TEST_NODES pair' % (s_, X.SYMDIR))
        if '_scope_inj_blk' in self.sc.sym and '_scope_sq_phase' in self.sc.sym:
            raise SystemExit('this map carries the block tap: S54 runs on a NO-TAP pair only')
        self.code = None

    # ---- link helpers --------------------------------------------------
    def _retry(self, fn, *a):
        for i in range(6):
            try:
                return fn(*a)
            except (IOError, OSError) as e:
                err = e
                time.sleep(0.05)
                try:
                    self.sc.d.resync()
                except Exception:
                    pass
        raise err

    def wv(self, addr, val):
        val &= 0xFFFFFFFF
        for _ in range(8):
            self._retry(self.c1.raw_w, addr, val)
            if self._retry(self.sc.rd, addr) == val:
                return
        raise SystemExit('write %d <- 0x%08X did not land' % (addr, val))

    def rd(self, addr):
        return self._retry(self.sc.rd, addr)

    def peek(self, name):
        return self._retry(self.sc.peek, self.sc.sym[name])

    # ---- analog chain --------------------------------------------------
    def chain(self, code, mute=0):
        """MIC 5's register (J25 = U41, chain index 9 = send position 15) alone open, phantom off, every other register
        muted, INSTR byte (send position 24 = U34) 0x00: the image as bytes on the wire, by spidev (s55_chain), so it
        does not depend on which side of the app's 2026-09-16 wire-order fix `chain-set`'s channel labels are."""
        sys.path.insert(0, '/home/app/s55')
        import s55_chain as CH
        img = [0x01] * 25
        img[D24.MIC5.send] = CH.byte(mute=mute, gain=code)
        img[24] = 0x00
        for attempt in range(4):
            ok, got = CH.send(img)
            if ok:
                break
        byte = 'p%d=0x%02X' % (D24.MIC5.send, img[D24.MIC5.send])
        log({'ev': 'chain', 'code': code, 'mute': mute, 'verified': ok, 'p15': byte, 'img': ['%02X' % b for b in img]})
        if not ok:
            raise SystemExit('chain image code %d mute %d NOT VERIFIED: %s' % (code, mute, got))
        subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
        self.code = code
        return byte

    # ---- oscillator / measurement ---------------------------------------
    def osc(self, freq=None, level_db=None, on=True, chan=DONOR):
        if freq is not None:
            self.wv(A_OSCFREQ, X.f32(freq))
        if level_db is not None:
            self.wv(A_OSCLEVEL, X.f32(10 ** (level_db / 20.0)))
        self.wv(A_OSCCHAN, chan)
        self.wv(A_OSCON, 1 if on else 0)
        self.freq = X.from_f32(self.rd(A_OSCFREQ))
        self.level_db = dbv(X.from_f32(self.rd(A_OSCLEVEL))) if on else None
        self.on = on

    def meas(self, chan, xsrc=0, xdst=0):
        self.wv(A_MEASCHAN, chan)
        self.wv(A_XSRC, xsrc)
        self.wv(A_XDST, xdst)
        self.mchan = chan

    def windows(self, n, settle_windows=3, tag=''):
        """Wait until the serial has advanced settle_windows past now, then take n untorn windows
        (distinct serials). Returns the rows and the serial delta from the change."""
        seq0 = self.rd(A_SEQ)
        while (self.rd(A_SEQ) - seq0) & 0xFFFFFFFF < settle_windows:
            time.sleep(WIN_S / 2)
        rows, seen = [], None
        k = self.sc.peek(self.sc.sym['_osc_k_C1_TEST_OSC'])
        kf = X.from_f32(k)
        while len(rows) < n:
            s1 = self.rd(A_SEQ)
            if s1 == seen:
                time.sleep(WIN_S / 3); continue
            rms = X.from_f32(self.rd(A_RMS)); thd = X.from_f32(self.rd(A_THD)); nse = X.from_f32(self.rd(A_NOISE))
            xtk = X.from_f32(self.rd(A_XTALK))
            a = X.from_f32(self.peek('_meas_a_C1_TEST_MEAS')); b = X.from_f32(self.peek('_meas_b_C1_TEST_MEAS'))
            s2 = self.rd(A_SEQ)
            if s2 != s1:
                continue
            seen = s1
            row = {'seq': s1, 'dseq': (s1 - seq0) & 0xFFFFFFFF, 'rms': rms, 'thd': thd, 'noise': nse, 'xtalk': xtk,
                   'a': a, 'b': b}
            if self.on and kf > 0:
                w = 2 * math.pi * self.freq / FS
                z = cmath.exp(1j * w)
                r = (z - 1) / kf
                L = 10 ** (self.level_db / 20.0)
                H = (a + b * r) / (L * math.cos(w / 2))
                row['H_db'] = dbv(abs(H)); row['H_deg'] = math.degrees(cmath.phase(H))
                row['coh_pk_dbfs'] = dbv(abs(a + b * r) / math.cos(w / 2))
                row['gain_rms_db'] = rms - (self.level_db - 3.0103)
            rows.append(row)
        rec = {'ev': 'meas', 'tag': tag, 'code': self.code, 'meas': self.mchan, 'freq': self.freq if self.on else None,
               'osc_dbfs_pk': self.level_db, 'on': self.on, 'k': kf, 'rows': rows}
        log(rec)
        return rec


def summ(rec, key):
    v = [r[key] for r in rec['rows'] if key in r]
    return sum(v) / len(v) if v else None


def spread(rec, key):
    v = [r[key] for r in rec['rows'] if key in r]
    return (max(v) - min(v)) if v else None


def phase_avg(rec):
    v = [cmath.exp(1j * math.radians(r['H_deg'])) for r in rec['rows'] if 'H_deg' in r]
    return math.degrees(cmath.phase(sum(v)))
