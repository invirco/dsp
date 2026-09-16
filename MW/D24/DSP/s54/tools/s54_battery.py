#!/usr/bin/env python3
"""s54_battery.py <gate> [args] — T1..T8 on the MIC 5 -> AUX 1 loop, no-tap pair, TEST_MEAS only.

  t1t4                 level law (codes 0..63, three levels each) + tone-off floor at every code
  t2 <G16-G0 dB>       frequency response at code 0 (osc -20 dBFS) and code 16 (same lane level)
  t3 <G0 dB>           THD+N vs lane level at 1 kHz code 0, then the clip hunt
  t58 <G0 dB>          phase vs frequency (latency T8, polarity T5)
  t6 <G0 dB>           mute depth, register mute bit, alternating arms
  t7 <G0 dB>           crosstalk: every other strip 1..24
  handback             MIC 5 open code 0, 1 kHz -20 dBFS on strip 6, MeasChan 20

Every record goes to /home/app/s54/s54_<gate>.jsonl.
"""
import math, os, sys, time
_ARGV = list(sys.argv)   # s52lib clears sys.argv on import
import s54lib as T
X = T.X

gate = _ARGV[1]
args = [float(a) for a in _ARGV[2:]]
R = T.Rig('/home/app/s54/s54_%s%s.jsonl' % (gate, os.environ.get('TAG', '')))
P = lambda *a: print(*a, flush=True)

CODES = [int(c) for c in os.environ.get('CODES', '0,2,4,6,8,12,16,24,32,48,63').split(',')]
FREQS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000]
STRIP_KEYS = ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001'] + \
             ['AuxOn%03d' % a for a in range(1, 9)] + ['Mute001']


def mtr_peak(n=24):
    m = 0.0
    for _ in range(n):
        m = max(m, X.from_f32(R.peek('_mtr_peak_C1_MTR_20')))
        time.sleep(0.01)
    return m


if gate == 't1t4':
    R.meas(T.LOOP)
    for code in CODES:
        p15 = R.chain(code)
        R.osc(1000.0, -80.0)
        pr = R.windows(3, settle_windows=4, tag='t1probe')
        g = T.summ(pr, 'H_db')
        L0 = min(-10.0 - g, -3.0)
        P('code %2d %s  probe(-80) coherent gain %+.2f dB -> osc %.2f dBFS for a -10 dBFS lane peak' % (code, p15, g, L0))
        for dl in (0.0, -10.0, -20.0):
            R.osc(None, L0 + dl)
            m = R.windows(3, settle_windows=3, tag='t1')
            P('   osc %7.2f  RMS %8.2f  gain(rms) %+7.3f  gain(coh) %+7.3f  THD+N %7.2f dB  noise %8.2f  phase %7.1f'
              % (L0 + dl, T.summ(m, 'rms'), T.summ(m, 'gain_rms_db'), T.summ(m, 'H_db'), T.summ(m, 'thd'),
                 T.summ(m, 'noise'), T.phase_avg(m)))
        R.osc(on=False)
        f = R.windows(4, settle_windows=4, tag='t4')
        P('   tone OFF floor RMS %8.2f dBFS (windows %s)' % (T.summ(f, 'rms'), ' '.join('%.2f' % r['rms'] for r in f['rows'])))

elif gate == 't2':
    d16 = args[0]
    for code, L in ((0, -20.0), (16, -20.0 - d16)):
        R.chain(code)
        for f in FREQS:
            R.osc(float(f), L)
            sw = 8 if f <= 50 else 4
            R.meas(T.LOOP)
            m = R.windows(4, settle_windows=sw, tag='t2loop')
            line = 'code %2d f %6d osc %7.2f  loop RMS %8.2f  coh %+7.3f dB  %7.1f deg  THD+N %7.2f' % (
                code, f, L, T.summ(m, 'rms'), T.summ(m, 'H_db'), T.phase_avg(m), T.summ(m, 'thd'))
            if code == 0:
                R.meas(T.DONOR)
                d = R.windows(3, settle_windows=3, tag='t2dig')
                line += '   | digital ref RMS %8.3f coh %+.3f' % (T.summ(d, 'rms'), T.summ(d, 'H_db'))
            P(line + '  (settle %d windows, spread %.3f dB)' % (sw, T.spread(m, 'H_db')))
    R.meas(T.LOOP)

elif gate == 't3':
    g0 = args[0]
    R.chain(0); R.meas(T.LOOP)
    R.osc(1000.0, -20.0)
    R.windows(2, settle_windows=3, tag='t3cal')
    P('meter peak at osc -20 (lane pk %.2f expected): %.2f dBFS' % (-20 + g0, T.dbv(mtr_peak())))
    for tgt in (-60, -40, -30, -20, -18, -16, -14, -13, -12, -11, -10, -8, -6, -3, -1, -0.5, 0, 0.5, 1, 2, 3, 4, 5):
        L = tgt - g0
        if L > 0:
            break
        R.osc(None, L)
        m = R.windows(4, settle_windows=8, tag='t3')
        pk = mtr_peak()
        thd = T.summ(m, 'thd')
        P('lane target %+5.1f  osc %7.2f  RMS %8.2f  coh pk %8.2f  THD+N %8.2f dB = %9.5f %%  noise %8.2f  meter pk %.6f (%+.3f dBFS)%s'
          % (tgt, L, T.summ(m, 'rms'), T.summ(m, 'coh_pk_dbfs'), thd, T.pct(thd), T.summ(m, 'noise'), pk, T.dbv(pk),
             '  <-- FS' if pk >= 0.9999 else ''))
        T.log({'ev': 't3peak', 'target': tgt, 'osc': L, 'meter_peak': pk})

elif gate == 't58':
    g0 = args[0]
    R.chain(0); R.meas(T.LOOP)
    L = -20.0 - g0   # lane -20 dBFS peak: below the code-0 overload at osc -18.5 (S54 knee)
    fl = [1000 + 100 * i for i in range(11)] + [2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000]
    pts = []
    for f in fl:
        R.osc(float(f), L)
        m = R.windows(3, settle_windows=4, tag='t58')
        ph = T.phase_avg(m)
        pts.append((f, ph))
        P('f %6d  coh %+7.3f dB  phase %8.2f deg  (spread %.3f dB)' % (f, T.summ(m, 'H_db'), ph, T.spread(m, 'H_db')))
    # unwrap along frequency using the running slope
    un = [pts[0][1]]
    slope = None
    for i in range(1, len(pts)):
        f0, f1 = pts[i - 1][0], pts[i][0]
        pred = un[-1] + (slope * (f1 - f0) if slope is not None else 0.0)
        v = pts[i][1]
        v += 360.0 * round((pred - v) / 360.0)
        un.append(v)
        if i >= 2:
            fs_ = [p[0] for p in pts[:i + 1]]
            n = len(fs_); mx = sum(fs_) / n; my = sum(un) / n
            slope = sum((a - mx) * (b - my) for a, b in zip(fs_, un)) / sum((a - mx) ** 2 for a in fs_)
        elif i == 1:
            slope = (un[1] - un[0]) / (f1 - f0)
    for lo, hi in ((1000, 2000), (1000, 10000), (2000, 15000)):
        sel = [(p[0], u) for p, u in zip(pts, un) if lo <= p[0] <= hi]
        n = len(sel); mx = sum(a for a, _ in sel) / n; my = sum(b for _, b in sel) / n
        sl = sum((a - mx) * (b - my) for a, b in sel) / sum((a - mx) ** 2 for a, _ in sel)
        ic = my - sl * mx
        res = max(abs(b - (ic + sl * a)) for a, b in sel)
        D = -sl / 360.0 * T.FS
        P('fit %5d..%5d Hz: delay %.3f samples = %.4f ms; phase intercept %.1f deg (mod 360: %.1f); max residual %.2f deg'
          % (lo, hi, D, 1000 * D / T.FS, ic, ic % 360.0, res))
        T.log({'ev': 't8fit', 'lo': lo, 'hi': hi, 'delay_samples': D, 'intercept_deg': ic, 'resid_deg': res})
    T.log({'ev': 't8pts', 'pts': pts, 'unwrapped': un})

elif gate == 't6':
    g0, code, tgt = args[0], int(args[1]), args[2]
    R.meas(T.LOOP)
    R.osc(1000.0, tgt - g0)
    P('T6 at code %d, osc %.2f dBFS (lane target %.1f dBFS pk)' % (code, tgt - g0, tgt))
    for arm, mute in enumerate((0, 1, 0, 1, 0)):
        p15 = R.chain(code, mute=mute)
        m = R.windows(4, settle_windows=4, tag='t6_mute%d' % mute)
        P('arm %d mute=%d %s  RMS %8.2f dBFS  coh pk %8.2f dBFS  (coh gain %+8.2f dB)  THD+N %7.2f  noise %8.2f'
          % (arm, mute, p15, T.summ(m, 'rms'), T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'H_db'), T.summ(m, 'thd'), T.summ(m, 'noise')))
    R.osc(on=False)
    for mute in (1, 0):
        R.chain(code, mute=mute)
        f = R.windows(4, settle_windows=4, tag='t6_off_mute%d' % mute)
        P('tone OFF mute=%d  RMS %8.2f dBFS' % (mute, T.summ(f, 'rms')))
    R.chain(0)

elif gate == 't7':
    g0, code, tgt = args[0], int(args[1]), args[2]
    R.chain(code)
    R.osc(1000.0, tgt - g0)
    P('T7 at code %d, osc %.2f dBFS (lane target %.1f dBFS pk)' % (code, tgt - g0, tgt))
    R.meas(T.LOOP)
    ref = R.windows(4, settle_windows=4, tag='t7ref')
    refpk = T.summ(ref, 'coh_pk_dbfs'); refrms = T.summ(ref, 'rms')
    P('strip 20 (source): RMS %.2f dBFS, coherent peak %.2f dBFS' % (refrms, refpk))
    worst = None
    for n in [s for s in range(1, 25) if s not in (T.DONOR, T.LOOP)]:
        pfx = 'Chan%03d' % n
        saved = {k: R.c1.r(pfx + k) for k in STRIP_KEYS}
        X.strip_unity(R.c1, n)
        R.meas(n, xsrc=T.LOOP, xdst=n)
        m = R.windows(3, settle_windows=4, tag='t7_s%02d' % n)
        xt_coh = T.summ(m, 'coh_pk_dbfs') - refpk
        P('strip %2d  RMS %8.2f dBFS  coh pk %8.2f dBFS  xtalk(coh) %8.2f dB  XtalkResult %8.2f dB  (was Mute=%d)'
          % (n, T.summ(m, 'rms'), T.summ(m, 'coh_pk_dbfs'), xt_coh, T.summ(m, 'xtalk'), saved['Mute001']))
        T.log({'ev': 't7', 'strip': n, 'xt_coh_db': xt_coh, 'saved': saved})
        if worst is None or xt_coh > worst[1]:
            worst = (n, xt_coh)
        for k in reversed(STRIP_KEYS):
            R.c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))
    P('WORST neighbour: strip %d at %.2f dB (coherent)' % worst)
    # control: same strip with the tone OFF -> the coherent detector's own floor
    n = worst[0]; pfx = 'Chan%03d' % n
    saved = {k: R.c1.r(pfx + k) for k in STRIP_KEYS}
    X.strip_unity(R.c1, n)
    R.meas(n)
    R.osc(on=False)
    R.osc(1000.0, tgt - g0, on=True)   # restore the tone (level/freq words) ...
    R.wv(T.A_OSCCHAN, 0)                # ... but inject nowhere: reference runs, no stimulus
    m = R.windows(3, settle_windows=4, tag='t7_ctrl_s%02d' % n)
    P('CONTROL strip %d, reference running, OscChan 0 (no stimulus): coh pk %.2f dBFS -> floor %.2f dB re source; RMS %.2f'
      % (n, T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'coh_pk_dbfs') - refpk, T.summ(m, 'rms')))
    for k in reversed(STRIP_KEYS):
        R.c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))
    R.osc(1000.0, tgt - g0)
    R.meas(T.LOOP)
    R.chain(0)

elif gate == 'handback':
    R.chain(0)
    R.osc(1000.0, -20.0)
    R.meas(T.LOOP)
    m = R.windows(3, settle_windows=3, tag='handback')
    P('handback: RMS %.2f dBFS  THD+N %.2f dB  noise %.2f dBFS  coh gain %+.3f dB'
      % (T.summ(m, 'rms'), T.summ(m, 'thd'), T.summ(m, 'noise'), T.summ(m, 'H_db')))

elif gate == 't1all':
    # HUB ADDENDUM 09:58: all 64 codes, lane peak kept in [-20, -6] dBFS, level carried from the previous code.
    # Strip 6 feeds AUX 1 only (MainOn 0, CompOn 0; S54-2), so no osc level here reaches the chip-2 MAIN overrun.
    R.meas(T.LOOP)
    L = float(os.environ.get('START_OSC', '-25.58'))
    for code in range(int(os.environ.get('START_CODE', '0')), 64):
        p15 = R.chain(code)
        for attempt in range(8):
            R.osc(1000.0, L)
            m = R.windows(2, settle_windows=4, tag='t1all_try')
            pk = T.summ(m, 'coh_pk_dbfs'); thd = T.summ(m, 'thd')
            # clipping is judged on LEVEL only: at high codes THD+N is the noise floor (-36 dB at lane -16 dBFS
            # rms on code 63), which is not a clip (first run of this gate stepped the osc to zero on it)
            if pk > -6.0:
                L -= 20.0 if pk > -1.5 else (pk + 13.0)
            elif pk < -20.0:
                L = min(L + (-13.0 - pk), -3.0)
                if L == -3.0 and attempt > 2:
                    break
            else:
                break
        m = R.windows(3, settle_windows=2, tag='t1all')
        mp = mtr_peak(16)
        P('code %2d %s osc %7.2f  lane RMS %8.2f  coh pk %7.2f  gain(rms) %+8.3f  gain(coh) %+8.3f  THD+N %7.2f dB = %.4f %%  mtr pk %+.2f'
          % (code, p15, L, T.summ(m, 'rms'), T.summ(m, 'coh_pk_dbfs'), T.summ(m, 'gain_rms_db'), T.summ(m, 'H_db'),
             T.summ(m, 'thd'), T.pct(T.summ(m, 'thd')), T.dbv(mp)))
        T.log({'ev': 't1all', 'code': code, 'osc': L, 'rms': T.summ(m, 'rms'), 'coh_pk': T.summ(m, 'coh_pk_dbfs'),
               'gain_rms': T.summ(m, 'gain_rms_db'), 'gain_coh': T.summ(m, 'H_db'), 'thd': T.summ(m, 'thd'),
               'mtr_pk': mp, 'p15': p15})
    R.chain(0); R.osc(1000.0, -20.0)
