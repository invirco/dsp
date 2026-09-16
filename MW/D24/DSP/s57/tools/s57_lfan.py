"""s57_lfan.py <lf_*.json ...> — spectrum of the slow RX-lane record (s57_lfrec.py): resampled to a uniform grid at
the record's own mean rate, Hann-windowed 50%-overlap segments of 8 s. Point samples alias the audio-band noise flat
across 0..rate/2; a concentrated sub-20 Hz component stands above that floor. Prints total variance (dBFS), the
aliased-white floor density, band powers above that floor (<0.5, 0.5-2, 2-5, 5-20 Hz), and the top peaks."""
import json, math, sys
import numpy as np
def db(x): return 10 * math.log10(x) if x > 0 else -999.0
for fn in sys.argv[1:]:
    d = json.load(open(fn))
    t = np.array(d['t']); v = np.array(d['v'], float) / 2 ** 31
    v -= v.mean()
    rate = (len(t) - 1) / (t[-1] - t[0])
    tu = np.arange(t[0], t[-1], 1 / rate)
    vu = np.interp(tu, t, v)
    L = int(8 * rate); hop = L // 2
    w = np.hanning(L); S = None; k = 0
    for s in range(0, len(vu) - L + 1, hop):
        X = np.fft.rfft((vu[s:s + L] - vu[s:s + L].mean()) * w)
        p = np.abs(X) ** 2 / (rate * np.sum(w * w)); p[1:-1] *= 2
        S = p if S is None else S + p; k += 1
    S /= k
    f = np.fft.rfftfreq(L, 1 / rate); bw = f[1]
    floor = float(np.median(S[(f > 60) & (f < rate / 2 * 0.9)]))      # per-Hz density of the aliased white noise
    out = {'file': fn.rsplit('/', 1)[-1], 'n': len(v), 'rate': round(rate, 1), 'segments': k, 'var_dbfs': db(float(np.mean(v * v))),
           'floor_dbfs_per_hz': db(floor)}
    for lo, hi in ((0.1, 0.5), (0.5, 2), (2, 5), (5, 20), (20, 60)):
        m = (f >= lo) & (f < hi)
        ex = float(np.sum(S[m] - floor) * bw)
        out['%g-%g_excess_dbfs' % (lo, hi)] = db(ex)
        out['%g-%g_re_floor_db' % (lo, hi)] = round(db(float(np.mean(S[m])) / floor), 1)
    m = (f > 0.1) & (f < 60)
    idx = np.argsort(S[m])[::-1][:6]
    out['peaks'] = [(round(float(f[m][i]), 3), round(db(float(S[m][i]) / floor), 1)) for i in idx]
    print(json.dumps(out))
