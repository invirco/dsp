#!/usr/bin/env python3
"""s63_analyse.py DATA_DIR [XLR ...] — S63 gain-change artefact tables from s63_run.py's captures (desk, numpy).

Per capture: 16,384 samples, Q4.28 (0 dBFS = 1.0), the change ~100 ms in. `e_host` = the host event mapped to a capture
sample by s63lib.span: the pass-1 CS_M rising edge for a hardware step (proved the applying edge by s63_latch.py), the
Gain001 write for a trim. Measured on MIC 5: a trim starts moving at e_host +0 (the map is good to a block); a hardware
step reaches 50 % ~9-10 ms after the latch edge (the preamp's control path), and multi-bit steps glitch before that.

SILENT (A) — the artefact alone. x = the lane; d = 10 ms boxcar of x (DC; 480 samples also null 1 kHz), h = x - d (AC).
Window W = [e_host, e_host + 60 ms), pre = [.., e_host - 96).
  floor       RMS of h over [e_host + 6000, end) (the new floor, > 125 ms after the event); floor peak = the largest
              |h| in any 100 ms of it
  peak        max |x - mean(pre)| in W, dBFS. DETECTED if the AC peak in W is > 3 dB over the larger of the new floor
              peak and the old (pre-change) floor's peak, or the DC excursion (below) is > DC_K (1.5) x the floor RMS. Calibration: on the four no-change captures, at every
              480-sample offset, the AC peak never exceeded the floor RMS by more than 14.6 dB (about the floor
              peak) and the DC excursion never exceeded 0.90 x the floor RMS. Not detected = "in floor" (pass).
  duration    ms from e_host until the 5 ms RMS envelope of h stays within 1 dB of the floor for 20 ms (0 if not detected)
  energy      10 log10(sum h^2 over [e_host, e_host + max(duration, 10 ms)) / (N floor^2)), dB re the new floor
  DC step     signed extreme of d - mean(pre) in [e_host, e_host + 50 ms); tau: grid fit a exp(-t/tau) + c from the extreme
              to the end (0.5 ms .. 2 s); pump = ms from e_host until |d - c| stays < DC_K x floor RMS. A pump still
              open at the capture end reads "> N ms"; tau at the grid edge (no decay inside the capture) reads "drift".
  character   octave-band excess of a 1,024-sample Hann segment from e_host over the late floor's: none (< 1 dB overall
              and not detected), thump (> 60 % of the excess energy < 125 Hz, or a DC step with pump > 10 ms), click
              (>= 3 bands > 3 dB), zipper (one line > 15 dB over the median excess), else "click (weak)"

TONE (B) — the residual. f fitted jointly on pre and post; a sin + b cos + c fitted on pre = [0, e_host - 96) and
post = [e50 + 100 ms, end). e50 = the first sample after e_host where the 1-cycle amplitude envelope crosses 50 % of the
way to the new level. IDEAL = pre sinusoid before e50, post sinusoid from e50 (pre DC throughout), an instantaneous step
at the transition's midpoint. RESIDUAL r = x - ideal: the peak/duration/energy/character metrics above on r (window from e_host,
floor = r's late RMS: tone THD+N + noise); the DC column is the fitted DC shift c_post - c_pre (the boxcar of r carries
the transition itself, so no pump is judged on the tone). Also: level change vs the S55 law, phase step, delay e_host -> e50, 10-90 % time, settle to within
0.1 dB, and the EXCURSION: the envelope's largest overshoot past the louder level / undershoot past the quieter one
(dB), which is how a multi-bit step's glitch shows; > 1 dB past the step is noted "glitch" beside the verdict.

PASS/FLAG — PW's S63 limit: artefact peak at the lane <= -60 dBFS and no DC pump > 50 ms. Applied as written to both
cases; on TONE the residual against an INSTANTANEOUS step also carries the transition itself (a 3 ms linear ramp of a
12 dB step leaves ~-18 dBFS), so the tone flag says "the change is not instantaneous", not "an artefact was added"."""
import json, math, os, sys
import numpy as np

FS = 48000.0
WIN = 4800
BOX = 480
AC_DETECT_DB = float(os.environ.get('AC_DETECT_DB', '3.0'))
DC_K = float(os.environ.get('DC_K', '1.5'))
TAU_MAX = 2.0
AC_WIN = 2880          # 60 ms: every MIC 5 transition is inside it (delay <= 15 ms, settle to 0.1 dB <= 25 ms)


def db(v):
    return 20 * math.log10(v) if v > 0 else -999.0


def load_bin(ddir, name):
    fn = os.path.join(ddir, name + '.bin')
    if os.path.exists(fn):
        return np.fromfile(fn, '<i4').astype(np.float64) / 2 ** 28
    import lzma
    with lzma.open(fn + '.xz') as f:
        return np.frombuffer(f.read(), '<i4').astype(np.float64) / 2 ** 28


def load(ddir, xlr):
    recs = [json.loads(l) for l in open(os.path.join(ddir, xlr + '.jsonl'))]
    raw = load_bin(ddir, xlr)
    for r in recs:
        r['x'] = raw[r['bin_off']:r['bin_off'] + r['n']]
    return recs


def host_event(r):
    for k in ('s_latch_hi', 's_write_lo'):
        if r.get(k) is not None:
            return float(r[k])
    return float(r['at'])


def change_type(r):
    code_ch = r['from'][0] != r['to'][0]
    trim_ch = abs(r['from'][1] - r['to'][1]) > 1e-9
    return 'combo' if code_ch and trim_ch else ('code' if code_ch else ('trim' if trim_ch else 'null'))


def boxcar(x, k=BOX):
    c = np.cumsum(np.concatenate(([0.0], x)))
    i = np.arange(len(x))
    lo = np.maximum(0, i - k // 2)
    hi = np.minimum(len(x), i + k // 2)
    return (c[hi] - c[lo]) / (hi - lo)


def sinfit(x, w, lo, hi):
    n = np.arange(lo, hi)
    A = np.stack([np.sin(w * n), np.cos(w * n), np.ones_like(n, dtype=float)], 1)
    coef, *_ = np.linalg.lstsq(A, x[lo:hi], rcond=None)
    return coef


def sinval(coef, w, n):
    return coef[0] * np.sin(w * n) + coef[1] * np.cos(w * n)


def fit_freq(x, segs, f0=1000.0):
    def err(f):
        w = 2 * math.pi * f / FS
        t = 0.0
        for a, b in segs:
            c = sinfit(x, w, a, b)
            n = np.arange(a, b)
            t += float(np.sum((x[a:b] - sinval(c, w, n) - c[2]) ** 2))
        return t
    best = f0
    for span in (1.0, 0.1, 0.01, 0.001):
        best = min([best + span * k for k in range(-10, 11)], key=err)
    return best


def envelope_ms(h, e, floor, n):
    thr = floor * 10 ** (1 / 20.0)
    hop, wl = 48, 240
    last_hi, quiet, t = None, 0, e
    while t + wl <= n:
        if math.sqrt(float(np.mean(h[t:t + wl] ** 2))) > thr:
            last_hi, quiet = t, 0
        else:
            quiet += 1
            if quiet * hop >= 960:
                break
        t += hop
    return 0.0 if last_hi is None else (last_hi + wl - e) / FS * 1000


def dc_fit(d, e, mu_pre, floor_rms, n):
    seg = d[e:min(n, e + 2400)] - mu_pre
    k = int(np.argmax(np.abs(seg)))
    step = float(seg[k])
    thr = DC_K * floor_rms
    out = {'dc_step': step, 'dc_step_dbfs': db(abs(step)), 'dc_step_x_floor': abs(step) / floor_rms, 'tau_ms': None,
           'pump_ms': 0.0, 'pump_open': False, 'drift': False, 'dc_detect': abs(step) > thr}
    if not out['dc_detect']:
        return out
    end = n - BOX // 2
    y = d[e + k:end] - mu_pre
    t = np.arange(len(y)) / FS
    best = None
    for tau in np.exp(np.linspace(math.log(0.0005), math.log(TAU_MAX), 140)):
        A = np.stack([np.exp(-t / tau), np.ones_like(t)], 1)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((y - A @ coef) ** 2))
        if best is None or sse < best[0]:
            best = (sse, tau, coef)
    _, tau, (a, c) = best
    out['tau_ms'] = tau * 1000
    out['dc_final'] = float(c)
    out['drift'] = tau >= TAU_MAX * 0.95
    dev = np.abs(d[e:end] - mu_pre - c)
    above = np.nonzero(dev >= thr)[0]
    if len(above) == 0:
        out['pump_ms'] = 0.0
    elif above[-1] >= len(dev) - 96:
        out['pump_ms'] = len(dev) / FS * 1000
        out['pump_open'] = True
    else:
        out['pump_ms'] = (above[-1] + 1) / FS * 1000
    return out


def spectrum(seg):
    wnd = np.hanning(len(seg))
    return np.fft.rfftfreq(len(seg), 1 / FS), np.abs(np.fft.rfft(seg * wnd)) ** 2 / np.sum(wnd ** 2)


def character(sig, h, e, n, detected, tone):
    N = 1024
    lo = min(max(0, e), n - N)
    f, Sa = spectrum(sig[lo:lo + N])
    segs = [h[s:s + N] for s in range(e + 6000, n - N + 1, N // 2)]
    if not segs:
        return 'n/a', {}
    Sf = np.mean([spectrum(s)[1] for s in segs], 0)
    keep = f > 0
    if tone:
        for m in range(1, 21):
            keep &= np.abs(f - 1000.0 * m) > 60
    edges = [0, 125, 250, 500, 1000, 2000, 4000, 8000, 16000, 24001]
    exc_db, exc_e = [], []
    for a, b in zip(edges, edges[1:]):
        sel = keep & (f >= a) & (f < b)
        ea, ef = float(np.sum(Sa[sel])), float(np.sum(Sf[sel]))
        exc_db.append(10 * math.log10(ea / ef) if ef > 0 and ea > 0 else 0.0)
        exc_e.append(max(ea - ef, 0.0))
    tot_db = 10 * math.log10(float(np.sum(Sa[keep])) / float(np.sum(Sf[keep])))
    rel = 10 * np.log10((Sa[keep] + 1e-30) / (Sf[keep] + 1e-30))
    line = float(np.max(rel) - np.median(rel))
    info = {'excess_total_db': round(tot_db, 2), 'band_excess_db': [round(v, 1) for v in exc_db], 'line_over_median_db': round(line, 1)}
    if tot_db < 1.0 and not detected:
        return 'none', info
    se = sum(exc_e)
    if se > 0 and exc_e[0] / se > 0.6:
        return 'thump', info
    if sum(1 for v in exc_db if v > 3.0) >= 3:
        return 'click', info
    if line > 15.0:
        return 'zipper', info
    return ('click (weak)' if detected else 'none'), info


def tone_model(x, eh):
    """(f, w, cpre, cpost, e50, env) for a tone capture with the change at host sample eh"""
    n = len(x)
    pre_hi = int(eh) - 96
    f = fit_freq(x, [(0, pre_hi), (n - 4096, n)])
    w = 2 * math.pi * f / FS
    cpre = sinfit(x, w, 0, pre_hi)
    Apre = math.hypot(cpre[0], cpre[1])
    P = int(round(FS / f))
    ts = np.arange(max(0, int(eh) - 480), min(n - P, int(eh) + 4800), 4)
    env = np.array([math.hypot(*sinfit(x, w, s, s + P)[:2]) for s in ts]), ts + P / 2
    Apost_guess = math.hypot(*sinfit(x, w, n - 4096, n)[:2])
    e50 = int(eh)
    if abs(Apost_guess - Apre) > 1e-3 * max(Apre, Apost_guess):
        frac = (env[0] - Apre) / (Apost_guess - Apre)
        idx = np.nonzero((frac >= 0.5) & (env[1] >= eh))[0]
        if len(idx):
            e50 = int(env[1][idx[0]])
    cpost = sinfit(x, w, min(n - 4096, e50 + WIN), n)
    return f, w, cpre, cpost, e50, env


def analyse_one(r):
    x = r['x']
    n = len(x)
    eh = int(round(host_event(r)))
    tone = r['stim'] == 'tone'
    out = {'e_host': eh}
    if tone:
        f, w, cpre, cpost, e50, (ea, et) = tone_model(x, eh)
        idx = np.arange(n)
        ideal = np.where(idx < e50, sinval(cpre, w, idx), sinval(cpost, w, idx)) + cpre[2]
        sig = x - ideal
        Apre, Apost = math.hypot(cpre[0], cpre[1]), math.hypot(cpost[0], cpost[1])
        ph = (math.degrees(math.atan2(cpost[1], cpost[0]) - math.atan2(cpre[1], cpre[0])) + 180) % 360 - 180
        t1090 = settle = None
        exc_over = exc_under = 0.0
        if abs(Apost - Apre) > 1e-3 * max(Apre, Apost):
            frac = (ea - Apre) / (Apost - Apre)
            post = et >= eh
            i10 = np.nonzero(post & (frac >= 0.1))[0]
            i90 = np.nonzero(post & (frac >= 0.9))[0]
            if len(i10) and len(i90):
                t1090 = (et[i90[0]] - et[i10[0]]) / FS * 1000
            off = np.nonzero(post & (np.abs(20 * np.log10(np.maximum(ea, 1e-12) / Apost)) > 0.1))[0]
            settle = ((et[off[-1]] - eh) / FS * 1000) if len(off) else 0.0
            sel = ea[post]
            exc_over = max(0.0, db(float(np.max(sel))) - db(max(Apre, Apost)))
            exc_under = min(0.0, db(float(np.min(sel))) - db(min(Apre, Apost)))
        out.update({'freq': f, 'e50': e50, 'delay_ms': (e50 - eh) / FS * 1000, 'level_change_db': db(Apost) - db(Apre),
                    'phase_step_deg': ph, 't10_90_ms': t1090, 'settle_01db_ms': settle,
                    'excursion_over_db': exc_over, 'excursion_under_db': exc_under})
    else:
        sig = x
    d = boxcar(sig)
    h = sig - d
    mu_pre = float(np.mean(sig[:eh - 96]))
    late = h[eh + 6000:]
    floor = math.sqrt(float(np.mean(late ** 2)))
    floor_pk = max(float(np.max(np.abs(late[s:s + WIN]))) for s in range(0, max(1, len(late) - WIN + 1), WIN // 2))
    pre = h[BOX // 2:eh - 96]
    floor_pk_old = float(np.max(np.abs(pre))) if len(pre) else 0.0
    whi = min(n, eh + AC_WIN)
    ac_pk = float(np.max(np.abs(h[eh:whi])))
    pk = float(np.max(np.abs(sig[eh:whi] - mu_pre)))
    if tone:
        # the tone residual's boxcar carries the transition itself: DC is judged from the fits, not from d
        dc = {'dc_step': float(cpost[2] - cpre[2]), 'dc_step_dbfs': db(abs(float(cpost[2] - cpre[2]))), 'tau_ms': None,
              'pump_ms': 0.0, 'pump_open': False, 'drift': False, 'dc_detect': False}
        dc['dc_step_x_floor'] = abs(dc['dc_step']) / floor
    else:
        dc = dc_fit(d, eh, mu_pre, floor, n)
    ac_detect = ac_pk > max(floor_pk, floor_pk_old) * 10 ** (AC_DETECT_DB / 20.0)
    detected = ac_detect or dc['dc_detect']
    dur = envelope_ms(h, eh, floor, n) if detected else 0.0
    elen = int(max(dur, 10.0) / 1000 * FS)
    energy = 10 * math.log10(float(np.sum(h[eh:eh + elen] ** 2)) / (elen * floor ** 2))
    ch, info = character(sig, h, eh, n, detected, tone)
    pump = dc['pump_ms'] if dc['dc_detect'] else 0.0
    if dc['dc_detect'] and pump > 10 and ch in ('none', 'click (weak)'):
        ch = 'thump'
    notes = []
    if not detected:
        notes.append('in floor')
    if detected and db(pk) > -60.0:
        notes.append('peak')
    if pump > 50.0:
        notes.append('pump')
    if tone and (out.get('excursion_over_db', 0.0) > 1.0 or out.get('excursion_under_db', 0.0) < -1.0):
        notes.append('glitch')
    verdict = 'FLAG' if ('peak' in notes or 'pump' in notes) else 'PASS'
    out.update({'floor_rms_dbfs': db(floor), 'floor_pk_dbfs': db(floor_pk), 'floor_pk_old_dbfs': db(floor_pk_old), 'ac_pk_dbfs': db(ac_pk), 'peak_dbfs': db(pk),
                'detected': detected, 'ac_detect': ac_detect, 'duration_ms': dur, 'energy_db': energy, 'char': ch,
                'spectrum': info, 'verdict': verdict, 'notes': notes, **dc})
    return out


def fmt_state(s, kind):
    c, t = s
    if kind in ('hw_up', 'hw_dn', 'bit', 'null', 'latch'):
        return '%d' % c
    if kind == 'combo':
        return 'c%d %+.3f' % (c, t)
    return '%+g dB' % t


def dcs(a):
    if not a['dc_detect']:
        return '—'
    s = '%s%.1f' % ('↑' if a['dc_step'] >= 0 else '↓', a['dc_step_dbfs'])
    if a['drift']:
        return '%s / drift, %s' % (s, ('> %.0f ms' % a['pump_ms']) if a['pump_open'] else '%.0f ms' % a['pump_ms'])
    return '%s / τ %.0f ms, pump %s%.0f ms' % (s, a['tau_ms'], '> ' if a['pump_open'] else '', a['pump_ms'])


GROUPS = [('null', 'NO CHANGE (the analysis floor)'), ('hw', 'HARDWARE STEPS — consecutive table codes, trim 0 dB'),
          ('bit', 'MAJOR-CARRY CODE CHANGES, trim 0 dB'), ('trim', 'DIGITAL TRIM at code 0 (Gain001, GainFast ramp)'),
          ('combo', 'COMBINED — target 30 ↔ 31 dB through the table (code latch, then the trim write)')]
STIMS = [('silent', 'A SILENT (oscillator off; source = loop cable into the AUX 1 output stage)'),
         ('tone', 'B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point')]


def table_md(xlr, rows):
    L = []
    for stim, title in STIMS:
        for g, gt in GROUPS:
            sel = [a for a in rows if a['stim'] == stim and (a['kind'].startswith('hw') if g == 'hw' else a['kind'] == g)]
            if not sel:
                continue
            L += ['', '**%s — %s — %s**' % (xlr, title, gt), '']
            if stim == 'silent':
                L += ['| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |',
                      '|---|---|---:|---:|---:|---|---|---|---|']
            else:
                L += ['| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |',
                      '|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|']
            for a in sel:
                pk = ('%.1f' % a['peak_dbfs']) if a['detected'] else '≤ floor'
                v = '%s%s' % (a['verdict'], (' (%s)' % ', '.join(a['notes'])) if a['notes'] else '')
                fr, to = fmt_state(a['from'], a['kind']), fmt_state(a['to'], a['kind'])
                if stim == 'silent':
                    L.append('| %s | %s | %s | %.0f | %+.1f | %s | %s | %.1f / %.1f | %s |' % (
                        fr, to, pk, a['duration_ms'], a['energy_db'], dcs(a), a['char'], a['floor_rms_dbfs'], a['floor_pk_dbfs'], v))
                else:
                    o = lambda k, f='%.1f': (f % a[k]) if a.get(k) is not None else '—'
                    L.append('| %s | %s | %+.2f (%+.2f) | %+.2f | %s | %s | %s | %s / %s | %s | %.0f | %+.1f | %s | %s | %.1f | %s |' % (
                        fr, to, a['level_change_db'], a['law_change_db'], a['phase_step_deg'],
                        o('delay_ms') if a['kind'] != 'null' else '—', o('t10_90_ms'), o('settle_01db_ms'),
                        '%+.1f' % a['excursion_over_db'], '%+.1f' % a['excursion_under_db'], pk, a['duration_ms'], a['energy_db'],
                        '%s%.1f (%.1f)' % ('↑' if a['dc_step'] >= 0 else '↓', a['dc_step_dbfs'], a['dc_step_x_floor']), a['char'], a['floor_rms_dbfs'], v))
    return L


def summary(xlr, rows):
    real = [a for a in rows if a['kind'] != 'null']
    s = {}
    for stim in ('silent', 'tone'):
        sel = [a for a in real if a['stim'] == stim]
        det = [a for a in sel if a['detected']]
        worst = max(det, key=lambda a: a['peak_dbfs'], default=None)
        pumps = [a for a in sel if a['dc_detect']]
        lp = max(pumps, key=lambda a: a['pump_ms'], default=None)
        s[stim] = {'n': len(sel), 'pass': sum(1 for a in sel if a['verdict'] == 'PASS'), 'detected': len(det),
                   'flag_peak': sum(1 for a in sel if 'peak' in a['notes']), 'flag_pump': sum(1 for a in sel if 'pump' in a['notes']),
                   'worst': worst and '%.1f dBFS %s %s→%s' % (worst['peak_dbfs'], worst['kind'], fmt_state(worst['from'], worst['kind']), fmt_state(worst['to'], worst['kind'])),
                   'longest_pump': lp and '%s%.0f ms %s %s→%s' % ('> ' if lp['pump_open'] else '', lp['pump_ms'], lp['kind'], fmt_state(lp['from'], lp['kind']), fmt_state(lp['to'], lp['kind']))}
    tone = [a for a in real if a['stim'] == 'tone']
    hw = [a for a in tone if a['kind'] in ('hw_up', 'hw_dn', 'bit', 'combo')]
    tr = [a for a in tone if a['kind'] == 'trim']
    ex = max(hw, key=lambda a: max(a['excursion_over_db'], -a['excursion_under_db']), default=None)
    s['hw_delay_ms'] = [round(min(a['delay_ms'] for a in hw), 2), round(float(np.median([a['delay_ms'] for a in hw])), 2), round(max(a['delay_ms'] for a in hw), 2)] if hw else None
    s['trim_delay_ms'] = [round(min(a['delay_ms'] for a in tr), 2), round(max(a['delay_ms'] for a in tr), 2)] if tr else None
    s['worst_excursion'] = ex and '%+.1f / %+.1f dB %s %s→%s' % (ex['excursion_over_db'], ex['excursion_under_db'], ex['kind'], fmt_state(ex['from'], ex['kind']), fmt_state(ex['to'], ex['kind']))
    s['glitch_steps'] = sum(1 for a in hw if a['excursion_over_db'] > 1.0 or a['excursion_under_db'] < -1.0)
    s['null_detected'] = sum(1 for a in rows if a['kind'] == 'null' and a['detected'])
    A, B = s['silent'], s['tone']
    line = ('**%s summary.** SILENT: %d transitions, **%d PASS / %d FLAG** (%d peak, %d pump); artefact detected above the floor on %d; '
            'worst %s; longest pump %s. TONE: %d PASS / %d FLAG against an instantaneous step (worst residual %s); '
            'hardware delay latch→50 %% %s ms (min/median/max); trim write→50 %% %s ms; %d of %d hardware/combined steps glitch '
            '> 1 dB past the step (worst %s). No-change captures detected: %d of %d.') % (
        xlr, A['n'], A['pass'], A['n'] - A['pass'], A['flag_peak'], A['flag_pump'], A['detected'], A['worst'] or 'none',
        A['longest_pump'] or 'none', B['pass'], B['n'] - B['pass'], B['worst'] or 'none',
        '/'.join('%.1f' % v for v in s['hw_delay_ms']) if s['hw_delay_ms'] else '—',
        '..'.join('%.1f' % v for v in s['trim_delay_ms']) if s['trim_delay_ms'] else '—',
        s['glitch_steps'], len(hw), s['worst_excursion'] or '—', s['null_detected'], sum(1 for a in rows if a['kind'] == 'null'))
    return s, line


def main(argv):
    ddir = argv[0]
    xlrs = argv[1:] or sorted(f[:-6] for f in os.listdir(ddir) if f.endswith('.jsonl') and f[:1] == 'J')
    allres, md, lines = {}, [], []
    for xlr in xlrs:
        rows = []
        recs = load(ddir, xlr)
        for r in recs:
            if r.get('invalid'):
                continue
            a = analyse_one(r)
            a.update({k: r[k] for k in ('stim', 'kind', 'from', 'to', 'overruns', 'map_resid_samples', 'osc_dbfs_pk', 'law_from', 'law_to')})
            a['law_change_db'] = (r['law_to'] + r['to'][1]) - (r['law_from'] + r['from'][1])
            if change_type(r) == 'combo':
                a['trim_after_latch_ms'] = (r['s_write_lo'] - r['s_latch_hi']) / FS * 1000
            rows.append(a)
        s, line = summary(xlr, rows)
        allres[xlr] = {'summary': s, 'invalid': sum(1 for r in recs if r.get('invalid')), 'overruns': sum(r['overruns'] for r in recs),
                       'rows': [{k: v for k, v in a.items()} for a in rows]}
        md += table_md(xlr, rows) + ['', line]
        lines.append(line)
    print('\n'.join(md))
    json.dump(allres, open(os.path.join(ddir, 's63_results.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main(sys.argv[1:])
