"""s69lib -- the standard audio test set (T1-T8) on the TALKBACK input, AUX 1 -> J1 loop.

THE PATH. TEST_OSC injects into donor strip 6, which is routed to AUX 1; AUX 1's DAC drives
the rear XLR J45; PW's cable carries that to the talkback XLR J1. J1 pin 2 -> C4 -> AK4619
IN4N and pin 3 -> C11 -> IN4P, SO THE TALKBACK ARRIVES INVERTED BY WIRING (on record since
2026-09-11). IN4 -> MIC Gain Amp 2 Rch -> ADC2 Rch -> SDOUT = CDC_O -> PLL8_0 ->
CPLD i_dspa[4] (raw pass-through) -> DSPA DAI1 I4 = SPORT4, TDM256 I2S, 32-bit slots,
256 fs; the codec's own lane is SLOT 0 (cs_mask 0x000D on sport 4 = slots 0, 2, 3; MFD 2).

THE MEASUREMENT POINT IS `_buf_C1_XIN_CODEC_01`, MeasChan 51 -- the S69 tap. It is the
converter's output block at full rate, before anything in the graph has touched it, which
is the right place to measure an INPUT path. It is also the ONLY place: `C1_XIN_CODEC_01`
feeds only `C1_TALK_01`, which writes a SCALAR once per block and whose fan-out is the gap
dsp-unmapped.csv records against Talk001Dest002/3 -- so MeasChan 1..32 (strips) and 33..50
(buses, S67) all miss the talkback path entirely.

GAIN IS INSIDE THE CODEC, NOT ON THE 595 CHAIN: MGN2R[3:0] in register 05H, twelve codes
-6 .. +27 dB in 3 dB steps (Table 9), driven through H1S1 by tools/pi/codec4619.py over the
matrix bus (PW ruling 2026-09-19; the dedicated CS6 wire comes later). The 595 chain is not
touched by this session at all.

TWO MASTERS. H1S1's SPI shares SCK/MOSI copper with the CM4's SPI0, so the DSP link must be
QUIET around a codec write. `Rig.mgn2r()` closes the Scope, runs the write as a separate
process, then re-opens and re-phases -- that is why it is a method here and not a call.
"""
import json
import math
import os
import subprocess
import sys
import time

SYMDIR = os.environ.setdefault('SYMDIR', '/home/app/s69')
sys.path.insert(0, '/home/app/s69')
sys.path.insert(0, '/home/app/s54')
sys.path.insert(0, '/home/app/dspboot')
import s52lib as X                                          # noqa: E402

FS = 48000.0
A_MEASCHAN, A_RMS, A_THD, A_NOISE, A_XSRC, A_XDST, A_XTALK, A_SEQ = range(4967, 4975)
A_OSCON, A_OSCFREQ, A_OSCLEVEL, A_OSCCHAN = range(4975, 4979)
A_SWEEPON, A_SWEEPSTEP = 4979, 4980
A_CAPARM, A_CAPREADY = 4981, 4982

DONOR = 6                    # the strip TEST_OSC injects into -> AUX 1 -> J45
TALK_MEAS = 51               # S69: MeasChan for _buf_C1_XIN_CODEC_01 (CODEC_RET_1)
CODEC_TOOL = '/home/app/s69/codec4619.py'
# MIC Gain AMP setting, AK4619 Table 9. Twelve codes only; 0xC..0xF are undefined.
MGN_DB = {0: -6.0, 1: -3.0, 2: 0.0, 3: 3.0, 4: 6.0, 5: 9.0, 6: 12.0,
          7: 15.0, 8: 18.0, 9: 21.0, 10: 24.0, 11: 27.0}
MGN_INIT = 11                # what StartAK4619() leaves the part at (+27 dB)
# PW's DMM at J45 pins 2-3, 2026-09-16: 1.11 V RMS at -20 dBFS -> full scale 11.1 V RMS.
DAC_FS_DBU = 23.13
WIN_S = 4096 / FS
DATA = '/home/app/s69/data'
LOG = None


def log(rec):
    rec['t'] = round(time.time(), 3)
    if LOG:
        LOG.write(json.dumps(rec) + '\n')
        LOG.flush()


def pct(db):
    """THD/THD+N as a percentage. Every THD figure is reported both ways (test-set rule)."""
    return 100.0 * 10 ** (db / 20.0)


def dbv(x):
    return 20 * math.log10(x) if x > 0 else float('-inf')


class Rig:
    def __init__(self, logpath=None):
        global LOG
        subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
        os.makedirs(DATA, exist_ok=True)
        if logpath:
            LOG = open(logpath, 'a')
        self.code = None            # the MGN2R code currently on the part
        self.mgn2l = MGN_INIT       # 05H is one byte: the other nibble has to be tracked
        self._open()

    def _open(self):
        self.c1 = X.Chip(1)
        self.sc = self.c1.sc
        for s_ in ('_osc_blk_q_C1_TEST_OSC', '_meas_a_C1_TEST_MEAS',
                   '_meas_b_C1_TEST_MEAS', '_buf_C1_XIN_CODEC_01'):
            if s_ not in self.sc.sym:
                raise SystemExit('%s absent from %s: not the S69 pair' % (s_, SYMDIR))
        if '_scope_inj_blk' in self.sc.sym:
            raise SystemExit('this map carries the block tap: S69 runs on a NO-TAP pair only')

    def _close(self):
        try:
            self.sc.d.link.spi.close()
        except Exception:
            pass
        self.c1 = self.sc = None

    # ---- link helpers --------------------------------------------------
    def _retry(self, fn, *a):
        err = None
        for _ in range(6):
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

    # ---- the codec gain lever -------------------------------------------
    def mgn2r(self, code, settle=0.35):
        """Set MGN2R (ADC2 Rch mic amp) through H1S1, with the DSP link shut.

        THE LINK IS CLOSED FOR THE DURATION, not merely idle: H1S1's SPI master and the
        CM4's SPI0 are the same SCK/MOSI copper, and a codec write that lands inside a
        DSP transaction corrupts both. Closing the Scope is the only way to be sure no
        other thread of this process clocks the bus while H1S1 has the wire."""
        if not 0 <= code <= 11:
            raise SystemExit('MGN2R code %d is outside 0..11 (Table 9 defines twelve)' % code)
        self._close()
        try:
            r = subprocess.run([sys.executable, CODEC_TOOL, '--mgn2r', str(code),
                                '--mgn2l', str(self.mgn2l)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                raise SystemExit('codec4619 failed: %s%s' % (r.stdout, r.stderr))
            out = r.stdout.strip()
            time.sleep(settle)
        finally:
            subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
            self._open()
        self.code = code
        log({'ev': 'mgn2r', 'code': code, 'db': MGN_DB[code], 'tool': out})
        return out

    def codec_reg(self, reg, val, settle=0.35):
        """Any single codec register, same two-master discipline as mgn2r()."""
        self._close()
        try:
            r = subprocess.run([sys.executable, CODEC_TOOL, '--reg', '%02X' % reg,
                                '--val', '%02X' % val], capture_output=True,
                               text=True, timeout=30)
            if r.returncode != 0:
                raise SystemExit('codec4619 failed: %s%s' % (r.stdout, r.stderr))
            time.sleep(settle)
        finally:
            subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
            self._open()
        log({'ev': 'codec_reg', 'reg': reg, 'val': val})

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

    def meas(self, chan=TALK_MEAS, xsrc=0, xdst=0):
        self.wv(A_MEASCHAN, chan)
        self.wv(A_XSRC, xsrc)
        self.wv(A_XDST, xdst)

    def window(self, n=2, timeout=12.0):
        """Wait for _meas_seq_ to advance n times.

        TWICE after any change, never once: the first window after a parameter moves has
        no previous fit, so ThdResult reads 0.00 dB by construction (S49 gotcha)."""
        s0 = self.rd(A_SEQ)
        t0 = time.time()
        seen = 0
        while seen < n:
            if time.time() - t0 > timeout:
                raise SystemExit('_meas_seq_ did not advance %d times in %.1fs '
                                 '(graph stalled?)' % (n, timeout))
            time.sleep(WIN_S / 2)
            s = self.rd(A_SEQ)
            if s != s0:
                seen += 1
                s0 = s
        return s0

    def results(self):
        """RmsResult / ThdResult / NoiseResult, read either side of the window serial.

        The serial is read before AND after: a reader that sees it move across the three
        results was handed a torn window and has to take them again."""
        for _ in range(8):
            s0 = self.rd(A_SEQ)
            rms = X.from_f32(self.rd(A_RMS))
            thd = X.from_f32(self.rd(A_THD))
            nse = X.from_f32(self.rd(A_NOISE))
            if self.rd(A_SEQ) == s0:
                return {'seq': s0, 'rms_dbfs': rms, 'thd_db': thd, 'noise_dbfs': nse}
        raise SystemExit('could not read an untorn results window')

    def point(self, n=2):
        self.window(n)
        return self.results()

    # ---- the phasor fit (loop gain AND polarity in one window) ----------
    def fit(self):
        """The window's own coherent fit: |H| is the loop gain, arg(H) carries the
        latency and the polarity.

        TEST_OSC is a magic-circle resonator (s' = s + k c, c' = c - k s'), so with
        s = S z^n, c = C z^n we have C/S = (z-1)/k. A measured x = a s + b c has phasor
        X = S (a + b r), r = (z-1)/k; the injected block is s*L*cos(w/2) and
        |S| = 1/cos(w/2), so H = (a + b r) / (L cos(w/2)). Same algebra as S54 -- it is
        the reference implementation and nothing here changes it."""
        import cmath
        a = X.from_f32(self.peek('_meas_a_C1_TEST_MEAS'))
        b = X.from_f32(self.peek('_meas_b_C1_TEST_MEAS'))
        k = X.from_f32(self.peek('_osc_k_C1_TEST_OSC'))
        w = 2 * math.pi * self.freq / FS
        z = cmath.exp(1j * w)
        r = (z - 1) / k
        L = 10 ** (self.level_db / 20.0)
        H = (a + b * r) / (L * math.cos(w / 2))
        return {'gain_db': dbv(abs(H)), 'phase_deg': math.degrees(cmath.phase(H)),
                'a': a, 'b': b}


def adc_fs_dbu(loop_gain_db):
    """The ADC's full scale at the talkback XLR, for the code the loop gain was measured at.

    S57-R: derive it as DAC_FS - loop_gain AT THAT CODE. Never subtract the loop gain from
    a full scale that already had a different code's loop gain taken out of it -- that is
    the double-count that cost S57 a re-run."""
    return DAC_FS_DBU - loop_gain_db
