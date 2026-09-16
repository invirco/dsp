"""s57_analyse.py <capture.json ...> — the S57 noise anatomy of tone-off captures (desk, numpy).
Per capture: RMS / peak / crest; band 20-20k unweighted + A (dsp4_fft.band_power); mains lines 50..400 Hz and their
share; impulsive excursions > 4 sigma (robust sigma), their width, rate, the RMS with them excised; short-window RMS
spread; spectral slope; narrow lines above the local floor. JSON lines out; dBu input-referred via G(code)."""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../../tools/pi'))
import dsp4_fft as F

FS = 48000.0
G = {0: 5.578, 16: 47.17, 32: 53.74, 48: 57.00, 63: 58.717}     # S54 T1 loop gains, dB
ADC_FS_DBU_C0 = 17.55                                            # FS SINE at the mic XLR, code 0 (RMS volts)
# RmsResult / the FFT put a full-scale sine at -3.01 dBFS (mean square), so a noise power P dBFS is
# P + 3.01 dB re the FS sine: dBu at the input = P + 3.01 + 17.55 - (G(code) - G(0)).
def dbu_in(p, code):
    return p + 3.0103 + ADC_FS_DBU_C0 - (G[code] - G[0])

def db(x): return 10 * math.log10(x) if x > 0 else -999.0

def load(path):
    c = json.load(open(path))
    v = np.array(c['samples'], dtype=np.int64)
    v = np.where(v >= 1 << 31, v - (1 << 32), v).astype(float) / (1 << 28)
    return c, v

def psd_bh7(x):
    n = len(x)
    w = np.array(F.blackman_harris(n))
    X = np.fft.rfft((x - x.mean()) * w)
    p = np.abs(X) ** 2 / (n * np.sum(w * w))
    p[1:-1] *= 2
    return p, FS / n

def anat(path):
    c, x = load(path)
    code = c.get('code', 63)
    n = len(x)
    ms = float(np.mean(x * x)); xa = x - x.mean(); msac = float(np.mean(xa * xa))
    pk = float(np.max(np.abs(xa)))
    out = {'file': os.path.basename(path), 'tag': c.get('tag'), 'idx': c.get('idx'), 't_arm': c.get('t_arm'), 'code': code,
           'tone': c.get('tone', 0), 'overruns': c.get('overruns'), 'node_rms': c.get('node_rms_dbfs'),
           'rms_dbfs': db(ms), 'rms_ac_dbfs': db(msac), 'dc': float(x.mean()), 'peak': pk,
           'peak_dbfs': 20 * math.log10(pk), 'crest_db': 20 * math.log10(pk / math.sqrt(msac))}
    lst = list(x)
    out['b20k_dbfs'] = F.band_power(lst, FS, 20.0, 20000.0)[0]
    out['a20k_dbfs'] = F.band_power(lst, FS, 20.0, 20000.0, aweight=True)[0]
    p, bw = psd_bh7(x)
    f = np.arange(len(p)) * bw
    tot = p[1:].sum()
    # local floor: running median over +-60 bins
    k = np.arange(len(p))
    def floor_at(i, half=60):
        lo, hi = max(1, i - half), min(len(p), i + half)
        return float(np.median(p[lo:hi]))
    mains = []
    msum = 0.0
    for h in range(1, 9):
        c0 = int(round(50.0 * h / bw))
        s = p[c0 - 5:c0 + 6].sum()
        fl = floor_at(c0) * 11
        ex = max(s - fl, 0.0)
        msum += ex
        mains.append({'hz': 50 * h, 'line_dbfs': db(ex), 'above_floor_db': db(s / fl) if fl else 0})
    out['mains'] = mains
    out['mains_share_pct'] = 100 * msum / tot
    out['mains_dbfs'] = db(msum)
    # spectral densities by decade (dBFS/Hz) and slope 100 Hz-10 kHz (median-smoothed, dB/decade)
    def dens(lo, hi):
        m = (f >= lo) & (f < hi)
        return db(float(np.median(p[m])) / bw)
    out['dens'] = {'20-200': dens(20, 200), '200-2k': dens(200, 2000), '2k-20k': dens(2000, 20000)}
    edges = np.logspace(2, 4, 13)
    fc, dv = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (f >= a) & (f < b)
        fc.append(math.log10(math.sqrt(a * b))); dv.append(10 * math.log10(float(np.median(p[m]))))
    out['slope_db_dec'] = float(np.polyfit(fc, dv, 1)[0])
    # lines: bins 12 dB above the running median, grouped
    lines = []
    i = 10
    while i < len(p) - 1:
        fl = floor_at(i)
        if p[i] > fl * 10 ** 1.2:
            j = i
            while j + 1 < len(p) and p[j + 1] > fl * 10 ** 1.2:
                j += 1
            seg = p[max(1, i - 4):j + 5]
            kk = max(1, i - 4) + int(np.argmax(seg))
            lines.append({'hz': round(kk * bw, 1), 'dbfs': round(db(float(seg.sum() - fl * len(seg))), 2),
                          'above_db': round(db(p[kk] / fl), 1)})
            i = j + 6
        else:
            i += 1
    out['lines'] = sorted(lines, key=lambda d: -d['dbfs'])[:12]
    # impulsive: robust sigma, > 4 sigma excursions, merged within 16 samples
    for lab, y in (('raw', xa), ('hp200', hp(xa, 200.0))):
        sig = 1.4826 * float(np.median(np.abs(y - np.median(y))))
        idx = np.nonzero(np.abs(y) > 4 * sig)[0]
        ev = []
        for t in idx:
            if ev and t - ev[-1][1] <= 16:
                ev[-1][1] = t
            else:
                ev.append([t, t])
        mask = np.ones(n, bool)
        for a, b in ev:
            mask[max(0, a - 64):b + 65] = False
        ex = float(np.mean(y[mask] ** 2)) if mask.any() else 0.0
        kurt = float(np.mean(y ** 4) / np.mean(y ** 2) ** 2)
        out['imp_' + lab] = {'sigma_dbfs': 20 * math.log10(sig), 'rms_over_sigma_db': 10 * math.log10(np.mean(y * y)) - 20 * math.log10(sig),
                             'events': len(ev), 'rate_hz': len(ev) / (n / FS),
                             'widths': [int(b - a + 1) for a, b in ev][:20],
                             'excised_pct': 100 * (1 - mask.mean()), 'rms_dbfs': db(float(np.mean(y * y))),
                             'rms_excised_dbfs': db(ex), 'kurtosis': kurt,
                             'gauss_expect_samples': float(n * math.erfc(4 / math.sqrt(2)))}
    # short-window RMS (1024 = 21 ms)
    wr = [db(float(np.mean(xa[j:j + 1024] ** 2))) for j in range(0, n - 1023, 1024)]
    out['win1024'] = {'min': min(wr), 'max': max(wr), 'spread': max(wr) - min(wr), 'vals': [round(v, 2) for v in wr]}
    return out

def hp(y, fc):
    Y = np.fft.rfft(y); fr = np.fft.rfftfreq(len(y), 1 / FS)
    Y[fr < fc] = 0
    return np.fft.irfft(Y, len(y))

if __name__ == '__main__':
    for pth in sys.argv[1:]:
        print(json.dumps(anat(pth)), flush=True)
