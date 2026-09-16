#!/usr/bin/env python3
"""s55_run.py — S55 hands-free: the mic test on every powered channel, PW moves the cables, nobody types.

Loop: DAC -> AUX 1 (J45) -> loop cable -> J2x -> preamp -> lane (strip) -> TEST_MEAS. Stimulus TEST_OSC on donor
strip 6 -> AUX 1 (strip 1, an unpowered lane, when the channel under test IS strip 6: J27 under the S58 patch, J32 before). All 16 powered registers
open at code 0, INSTR byte (p24) 0x00, images sent by s55_chain (spidev; chain-set cannot gain p0 = J42).

  WATCH   tone on AUX 1; scan the 16 powered lanes (raw RX peeks); the lane carrying it names the XLR (3 scans agree).
  LOOP    T1 all 64 codes, T2 codes 0/63, T3 code 0 (-20/-10/-6/-3 lane pk) + code 63 (-3), T5/T8 phase fit.
  SHUNT   osc off, register at code 63, TEST_MEAS RMS on the lane; < -70 dBFS for 12 s = the 150 ohm is on.
  NOISE   T4/T4b: codes 63 and 0, TEST_MEAS windows + 16k capture-arm captures (EIN/A-weight/sub-20 Hz on the desk).
  -> register back to code 0, tone back on, strip restored, WATCH.

Every record -> /home/app/s55/s55_run.jsonl; human lines -> stdout (PROMPT lines are for PW).
AN_EN (GPIO 26) is read before every channel and never written."""
import json, math, os, subprocess, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56'); sys.path.insert(0, '/home/app/s55')
_ARGV = list(sys.argv)
import s54lib as T
import s55_chain as CH
import dsp4_meascap as MC
X = T.X

HOME = '/home/app/s55'
DATA = HOME + '/data'
os.makedirs(DATA, exist_ok=True)
# XLR, send position p, lane (strip), panel name -- from the one map (tools/pi/d24_inputs.py): the 16 powered XLRs
# (U39 + U60; U15 = J15-J22 has no rails), strip under the landed D24_INPUT_PATCH. S55 ran under the pre-S58 patch,
# so its records' "lane" is d24_inputs.strip(xlr, PRE_S58_PATCH).
sys.path.insert(0, '/home/app/dspboot')
import d24_inputs as D24
CHANNELS = [(r.xlr, r.send, r.strip(), r.name) for r in D24.XLRS if r.adc in ('U39', 'U60')]
BY_LANE = {c[2]: c for c in CHANNELS}
# MIC 5's S54 law (loop gain dB per code): only the osc level's first guess per code
G5 = [5.578, 18.423, 25.041, 27.713, 32.475, 33.711, 35.267, 36.18, 39.927, 40.472, 41.219, 41.691, 42.869, 43.26, 43.808,
      44.16, 47.169, 47.409, 47.752, 47.976, 48.564, 48.769, 49.063, 49.255, 50.227, 50.396, 50.639, 50.801, 51.228, 51.378,
      51.597, 51.741, 53.744, 53.859, 54.02, 54.129, 54.42, 54.525, 54.674, 54.776, 55.298, 55.391, 55.527, 55.618, 55.864,
      55.952, 56.08, 56.164, 57.001, 57.076, 57.189, 57.265, 57.467, 57.539, 57.645, 57.715, 58.086, 58.155, 58.254, 58.318,
      58.496, 58.562, 58.656, 58.717]
FREQS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000]
STRIP_KEYS = ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001'] + \
             ['AuxOn%03d' % a for a in range(1, 9)] + ['Mute001']
DETECT_PK, DETECT_MARGIN, DETECT_SCANS = -35.0, 15.0, 3
SHUNT_DBFS, SHUNT_HOLD_S = -70.0, 12.0
WAIT_NOTE_S = 600.0


def P(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def PROMPT(msg):
    P('PROMPT >>> ' + msg)
    T.log({'ev': 'prompt', 'msg': msg})


class Abort(Exception):
    pass


class S55(T.Rig):
    def __init__(self):
        super().__init__(HOME + '/s55_run.jsonl')
        self.image = [0x00] * 16 + [0x01] * 8 + [0x00]
        self.donor = 6
        self.saved = {}

    # the 595 image: every powered register open at code 0 except the one under test
    def chain(self, code, p=None, mute=0):
        img = list(self.image)
        if p is not None:
            img[p] = CH.byte(mute=mute, gain=code)
        for attempt in range(4):
            ok, got = CH.send(img)
            if ok:
                break
        T.log({'ev': 'chain', 'p': p, 'code': code, 'verified': ok, 'img': ['%02X' % b for b in img]})
        if not ok:
            raise SystemExit('chain image NOT VERIFIED (p %s code %s): got %s' % (p, code, got))
        self.code = code
        return 'p%s=0x%02X' % (p, img[p]) if p is not None else 'base'

    def osc(self, freq=None, level_db=None, on=True, chan=None):
        return super().osc(freq, level_db, on, chan=self.donor if chan is None else chan)

    def an_en(self):
        out = subprocess.run(['pinctrl', 'get', '26'], capture_output=True, text=True).stdout
        return '| hi' in out, out.strip()

    def strip_save(self, n):
        return {k: self.c1.r('Chan%03d%s' % (n, k)) for k in STRIP_KEYS}

    def strip_restore(self, n, saved):
        pfx = 'Chan%03d' % n
        for k in reversed(STRIP_KEYS):
            self.c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))

    def set_donor(self, d):
        """TEST_OSC's strip -> AUX 1 alone (MainOn 0, CompOn 0: S54-2's chip-2 overrun), the other donor off AUX 1."""
        other = 1 if d == 6 else 6
        if d == 1 and 1 not in self.saved:
            self.saved[1] = self.strip_save(1)
        if d == 1:
            X.strip_unity(self.c1, 1)
            for k in ('AuxSend001', 'AuxPick001'):
                if self.c1.r('Chan001' + k) != self.c1.r('Chan006' + k):
                    self.c1.wv('Chan001' + k, self.c1.r('Chan006' + k), 4 if k == 'AuxSend001' else 0)
        if other == 1 and 1 in self.saved:
            self.strip_restore(1, self.saved.pop(1))
        else:
            self.c1.wv('Chan%03dAuxOn001' % other, 0)
        self.c1.wv('Chan%03dAuxOn001' % d, 1)
        self.c1.wv('Chan%03dMainOn001' % d, 0)
        self.c1.wv('Chan%03dCompOn001' % d, 0)
        self.c1.wv('Chan%03dMute001' % d, 0)
        self.donor = d
        self.wv(T.A_OSCCHAN, d)
        on = [s for s in range(1, 25) if self.c1.r('Chan%03dAuxOn001' % s) == 1]
        T.log({'ev': 'donor', 'donor': d, 'auxon1': on})
        return on

    def mtr_peak(self, lane, n=24):
        m = 0.0
        for _ in range(n):
            m = max(m, X.from_f32(self.peek('_mtr_peak_C1_MTR_%02d' % lane)))
            time.sleep(0.01)
        return m

    def scan(self, lanes):
        res = {}
        for n in lanes:
            try:
                e, r, pk = X.lane(self.c1, n, reads=16)
            except (IOError, OSError):
                self.sc.d.resync(); e, r, pk = X.lane(self.c1, n, reads=16)
            res[n] = (r, pk)
        return res


def summ(m, k):
    return T.summ(m, k)


# ---------------------------------------------------------------- phases
def watch(R, done):
    R.osc(1000.0, -20.0)
    t0 = last_note = time.time()
    hist = []
    lanes = [c[2] for c in CHANNELS]
    told_done = None
    nxt = [c for c in CHANNELS if c[0] not in done]
    P('WATCH: 1 kHz -20 dBFS on strip %d -> AUX 1; all powered registers open at code 0; done: %s' % (R.donor, sorted(done)))
    while True:
        res = R.scan(lanes)
        srt = sorted(lanes, key=lambda n: -(res[n][1] if res[n][1] is not None else -999))
        a, b = srt[0], srt[1]
        pa, pb = res[a][1], res[b][1]
        hit = a if (pa is not None and pa > DETECT_PK and (pb is None or pa - pb > DETECT_MARGIN)) else None
        hist = (hist + [hit])[-DETECT_SCANS:]
        if hit and hist.count(hit) == DETECT_SCANS:
            ch = BY_LANE[hit]
            if ch[0] in done:
                if told_done != ch[0]:
                    PROMPT('%s (%s) is already DONE — move the loop cable to the next XLR' % (ch[0], ch[3]))
                    told_done = ch[0]
                    last_note = time.time()
            else:
                T.log({'ev': 'detect', 'xlr': ch[0], 'lane': hit, 'pk': pa, 'second': [b, pb],
                       'all': {n: res[n] for n in lanes}})
                P('DETECT: tone on lane %d (pk %.2f dBFS; next lane %d at %.2f) -> %s (%s)' % (hit, pa, b, pb, ch[0], ch[3]))
                return ch
        if time.time() - last_note > WAIT_NOTE_S:
            exp = nxt[0] if nxt else None
            PROMPT('WAITING — cable in %s?' % ('%s (%s)' % (exp[0], exp[3]) if exp else 'the next XLR'))
            T.log({'ev': 'waiting', 'since_s': round(time.time() - t0), 'top': [[n, res[n][1]] for n in srt[:3]]})
            last_note = time.time()
        time.sleep(0.3)


def loop_set(R, ch):
    xlr, p, lane, panel = ch
    tag = xlr
    rec = {'xlr': xlr, 'p': p, 'lane': lane, 'panel': panel}
    R.meas(lane)
    # presence at code 0
    R.chain(0, p)
    R.osc(1000.0, -20.0)
    m = R.windows(3, settle_windows=4, tag=tag + ':presence')
    g0 = summ(m, 'H_db')
    P('%s presence: code 0 osc -20 -> coh gain %+.3f dB, lane coh pk %.2f dBFS' % (xlr, g0, summ(m, 'coh_pk_dbfs')))
    if g0 < -10:
        raise Abort('no loop at code 0 (coh gain %.2f dB)' % g0)

    # ---- T1: all 64 codes, lane coherent peak kept in [-20, -6] dBFS
    t1 = []
    for code in range(64):
        R.chain(code, p)
        L = min(-13.0 - (G5[code] + (t1[-1]['gain_coh'] - G5[code - 1] if t1 else g0 - G5[0])), -3.0)
        for attempt in range(8):
            R.osc(1000.0, L)
            m = R.windows(2, settle_windows=4, tag=tag + ':t1try')
            pk = summ(m, 'coh_pk_dbfs')
            if pk > -6.0:
                L -= 20.0 if pk > -1.5 else (pk + 13.0)
            elif pk < -20.0:
                if L >= -3.0 and attempt > 1:
                    break
                L = min(L + (-13.0 - pk), -3.0)
            else:
                break
        m = R.windows(3, settle_windows=2, tag=tag + ':t1')
        g = summ(m, 'H_db')
        if g < g0 - 3.0:
            raise Abort('T1 code %d: coh gain %.2f dB under code 0 (%.2f) — loop lost' % (code, g, g0))
        mp = R.mtr_peak(lane, 12)
        row = {'code': code, 'osc': L, 'rms': summ(m, 'rms'), 'coh_pk': summ(m, 'coh_pk_dbfs'), 'gain_rms': summ(m, 'gain_rms_db'),
               'gain_coh': g, 'thd': summ(m, 'thd'), 'mtr_pk': mp, 'spread': T.spread(m, 'H_db')}
        t1.append(row)
        T.log(dict(ev='t1all', xlr=xlr, **row))
        P('%s T1 code %2d osc %7.2f  lane coh pk %7.2f  gain %+8.3f dB (rms %+8.3f)  THD+N %7.2f dB' %
          (xlr, code, L, row['coh_pk'], g, row['gain_rms'], row['thd']))
    rec['t1'] = t1
    G = {r['code']: r['gain_coh'] for r in t1}

    # ---- T2: code 0 (osc -20) and code 63 (lane -20 pk)
    t2 = {}
    for code, L in ((0, -20.0), (63, -20.0 - G[63])):
        R.chain(code, p)
        pts = []
        for f in FREQS:
            R.osc(float(f), L)
            m = R.windows(6 if f <= 50 else 4, settle_windows=16 if f <= 50 else 6, tag=tag + ':t2c%d' % code)
            pts.append({'f': f, 'gain': summ(m, 'H_db'), 'phase': T.phase_avg(m), 'rms': summ(m, 'rms'),
                        'thd': summ(m, 'thd'), 'spread': T.spread(m, 'H_db')})
        g1k = [q for q in pts if q['f'] == 1000][0]['gain']
        for q in pts:
            q['re1k'] = q['gain'] - g1k
            T.log(dict(ev='t2', xlr=xlr, code=code, **q))
        t2[code] = pts
        P('%s T2 code %d re 1 kHz: %s' % (xlr, code, '  '.join('%d:%+.2f' % (q['f'], q['re1k']) for q in pts)))
    rec['t2'] = t2

    # ---- T3: code 0 at lane -20/-10/-6/-3 dBFS pk, code 63 at -3
    t3 = []
    for code, targets in ((0, (-20.0, -10.0, -6.0, -3.0)), (63, (-3.0,))):
        R.chain(code, p)
        for tgt in targets:
            L = tgt - G[code]
            for i in range(5):
                R.osc(1000.0, L)
                m = R.windows(2, settle_windows=6, tag=tag + ':t3trim')
                pk = summ(m, 'coh_pk_dbfs')
                if pk < -40:
                    raise Abort('T3 code %d: lane at floor (%.2f) — loop lost' % (code, pk))
                if abs(pk - tgt) <= 0.03:
                    break
                L += tgt - pk
            m = R.windows(6, settle_windows=6, tag=tag + ':t3')
            mp = R.mtr_peak(lane, 40)
            row = {'code': code, 'target': tgt, 'osc': L, 'coh_pk': summ(m, 'coh_pk_dbfs'), 'rms': summ(m, 'rms'),
                   'thd': summ(m, 'thd'), 'noise': summ(m, 'noise'), 'mtr_pk': mp, 'thd_w': [r['thd'] for r in m['rows']]}
            t3.append(row)
            T.log(dict(ev='t3', xlr=xlr, **row))
            P('%s T3 code %2d lane %+.1f dBFS pk (coh %.2f): THD+N %.2f dB = %.5f %%  noise %.2f  meter pk %.2f dBFS%s' %
              (xlr, code, tgt, row['coh_pk'], row['thd'], T.pct(row['thd']), row['noise'], T.dbv(mp), '  <-- FS' if mp >= 0.9999 else ''))
    rec['t3'] = t3

    # ---- T5/T8: phase vs frequency at code 0, lane -20 dBFS pk
    R.chain(0, p)
    L = -20.0 - G[0]
    fl = [1000 + 100 * i for i in range(11)] + [2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000]
    pts = []
    for f in fl:
        R.osc(float(f), L)
        m = R.windows(3, settle_windows=4, tag=tag + ':t58')
        pts.append((f, T.phase_avg(m)))
    un = [pts[0][1]]
    slope = None
    for i in range(1, len(pts)):
        f0, f1 = pts[i - 1][0], pts[i][0]
        pred = un[-1] + (slope * (f1 - f0) if slope is not None else 0.0)
        v = pts[i][1]
        v += 360.0 * round((pred - v) / 360.0)
        un.append(v)
        fs_ = [q[0] for q in pts[:i + 1]]
        n = len(fs_); mx = sum(fs_) / n; my = sum(un) / n
        slope = sum((a - mx) * (b - my) for a, b in zip(fs_, un)) / sum((a - mx) ** 2 for a in fs_)
    fits = []
    for lo, hi in ((1000, 2000), (1000, 10000), (2000, 15000)):
        sel = [(q[0], u) for q, u in zip(pts, un) if lo <= q[0] <= hi]
        n = len(sel); mx = sum(a for a, _ in sel) / n; my = sum(b for _, b in sel) / n
        sl = sum((a - mx) * (b - my) for a, b in sel) / sum((a - mx) ** 2 for a, _ in sel)
        ic = my - sl * mx
        res = max(abs(b - (ic + sl * a)) for a, b in sel)
        D = -sl / 360.0 * T.FS
        fits.append({'lo': lo, 'hi': hi, 'delay_samples': D, 'intercept_deg': ic % 360.0, 'resid_deg': res})
        T.log(dict(ev='t8fit', xlr=xlr, **fits[-1]))
    ic = fits[0]['intercept_deg']
    pol = 'INVERTED' if 90 < ic < 270 else 'in phase'
    rec['t58'] = {'pts': pts, 'unwrapped': un, 'fits': fits, 'polarity': pol}
    T.log({'ev': 't58', 'xlr': xlr, 'pts': pts, 'unwrapped': un, 'polarity': pol})
    P('%s T8 %.2f samples (1-2 kHz, resid %.2f deg; 1-10 kHz %.2f)  T5 intercept %.1f deg -> %s' %
      (xlr, fits[0]['delay_samples'], fits[0]['resid_deg'], fits[1]['delay_samples'], ic, pol))
    return rec


def shunt_wait(R, ch):
    xlr, p, lane, panel = ch
    R.osc(on=False)
    R.chain(63, p)
    R.meas(lane)
    P('SHUNT: TEST_OSC off, %s at code 63, watching lane %d for < %.0f dBFS' % (xlr, lane, SHUNT_DBFS))
    since = None
    t0 = last_print = time.time()
    next_note = t0 + WAIT_NOTE_S
    last = None
    while True:
        m = R.windows(1, settle_windows=1, tag=xlr + ':shuntwatch')
        v = m['rows'][0]['rms']
        if last is None or abs(v - last) > 6 or time.time() - last_print > 60:
            P('  %s lane %d RMS %.2f dBFS' % (xlr, lane, v))
            last, last_print = v, time.time()
        if v < SHUNT_DBFS:
            since = since or time.time()
            if time.time() - since >= SHUNT_HOLD_S:
                T.log({'ev': 'shunt_on', 'xlr': xlr, 'rms': v, 'waited_s': round(time.time() - t0)})
                P('%s: floor %.2f dBFS held %.0f s -> 150 ohm taken as fitted' % (xlr, v, SHUNT_HOLD_S))
                return
        else:
            since = None
        if time.time() > next_note:
            PROMPT('WAITING — 150 Ω on %s (%s)?' % (xlr, panel))
            next_note += WAIT_NOTE_S


def noise(R, ch):
    xlr, p, lane, panel = ch
    out = {}
    for code, ncap in ((63, 6), (0, 3)):
        R.chain(code, p)
        m = R.windows(8, settle_windows=24, tag=xlr + ':t4c%d' % code)
        caps = []
        for i in range(ncap):
            cap = MC.capture(16384, '/home/app/s56', sc=R.sc, log=lambda *a: None)
            node = R.windows(1, settle_windows=1, tag=xlr + ':t4cap')
            cap.update({'xlr': xlr, 'lane': lane, 'code': code, 'idx': i, 't_arm': round(time.time(), 3),
                        'node_rms_dbfs': node['rows'][0]['rms'], 'source': '150 ohm'})
            fn = '%s/%s_c%02d_%d.json' % (DATA, xlr, code, i)
            json.dump(cap, open(fn, 'w'))
            caps.append({'file': os.path.basename(fn), 'overruns': cap['overruns'], 'node_rms': node['rows'][0]['rms']})
        m2 = R.windows(4, settle_windows=1, tag=xlr + ':t4c%d_after' % code)
        row = {'code': code, 'rms': summ(m, 'rms'), 'noise': summ(m, 'noise'), 'rms_w': [r['rms'] for r in m['rows']],
               'rms_after': summ(m2, 'rms'), 'caps': caps}
        out[code] = row
        T.log(dict(ev='t4', xlr=xlr, **row))
        P('%s T4 code %2d (150 ohm): RmsResult %.2f dBFS NoiseResult %.2f (after captures %.2f); %d captures, overruns %s' %
          (xlr, code, row['rms'], row['noise'], row['rms_after'], ncap, [c['overruns'] for c in caps]))
    if out[63]['rms_after'] > SHUNT_DBFS:
        T.log({'ev': 'shunt_lost', 'xlr': xlr, 'rms': out[63]['rms_after']})
        P('%s WARNING: code-63 floor rose to %.2f dBFS during T4 — source changed?' % (xlr, out[63]['rms_after']))
    return out


def main():
    done = set(a for a in os.environ.get('DONE', 'J25').split(',') if a)
    only = os.environ.get('ONLY')
    R = S55()
    ok, pin = R.an_en()
    P('AN_EN: %s' % pin)
    if not ok:
        raise SystemExit('AN_EN is LOW: analog off — blocked (never written by this session)')
    R.saved[6] = R.strip_save(6)
    T.log({'ev': 'start', 'done': sorted(done), 'strip6': R.saved[6], 'an_en': pin})
    R.chain(0)
    P('base image VERIFIED; strips on AUX 1: %s' % R.set_donor(6))
    while True:
        ch = watch(R, done)
        xlr, p, lane, panel = ch
        if only and xlr != only:
            continue
        ok, pin = R.an_en()
        if not ok:
            raise SystemExit('AN_EN went LOW — blocked')
        saved = R.strip_save(lane)
        T.log({'ev': 'channel_start', 'xlr': xlr, 'lane': lane, 'saved': saved})
        try:
            if lane == 6:
                R.set_donor(1)
            X.strip_unity(R.c1, lane)
            rec = loop_set(R, ch)
            json.dump(rec, open('%s/%s_loop.json' % (DATA, xlr), 'w'))
            PROMPT('%s (%s) LOOP SET DONE — fit the 150 Ω on %s' % (xlr, panel, xlr))
            shunt_wait(R, ch)
            rec['t4'] = noise(R, ch)
            json.dump(rec, open('%s/%s_loop.json' % (DATA, xlr), 'w'))
            done.add(xlr)
            T.log({'ev': 'channel_done', 'xlr': xlr})
        except Abort as e:
            T.log({'ev': 'abort', 'xlr': xlr, 'why': str(e)})
            P('%s ABORTED: %s — back to WATCH, nothing recorded as done' % (xlr, e))
        finally:
            R.osc(on=False)
            R.chain(0)
            R.strip_restore(lane, saved)
            if R.donor != 6:
                R.set_donor(6)
            R.meas(T.LOOP)
        if xlr in done:
            PROMPT('%s (%s) DONE — move the loop cable to the next XLR' % (xlr, panel))


if __name__ == '__main__':
    main()
