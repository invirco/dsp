"""s57_bands.py <capture.json ...> — band split of each capture's power (DC removed): <5, 5-20, 20-200, 200-2k,
2k-20k, 20k-24k Hz, as dBFS, plus the sub-20 Hz waveform's peak-to-peak and zero-crossing count (is the excess a
drift/step or an oscillation), and 1024-window RMS of the 20 Hz-20 kHz band alone."""
import json, math, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import s57_analyse as A
EDGES = [(0.1, 5), (5, 20), (20, 200), (200, 2000), (2000, 20000), (20000, 24000)]
def bands(path):
    c, x = A.load(path)
    x = x - x.mean(); n = len(x)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / 48000.0)
    P = np.abs(X) ** 2 / n ** 2; P[1:-1] *= 2
    out = {'file': path.rsplit('/', 1)[-1], 'code': c.get('code'), 'mode': c.get('mode'), 't_arm': c.get('t_arm'),
           'total': A.db(float(P.sum()))}
    for lo, hi in EDGES:
        out['%g-%g' % (lo, hi)] = A.db(float(P[(f >= lo) & (f < hi)].sum()))
    Y = X.copy(); Y[f >= 20] = 0; lf = np.fft.irfft(Y, n)
    out['lf_pp'] = float(lf.max() - lf.min()); out['lf_pp_dbfs'] = 20 * math.log10(out['lf_pp'])
    Y = X.copy(); Y[(f < 20) | (f > 20000)] = 0; ab = np.fft.irfft(Y, n)
    w = [A.db(float(np.mean(ab[j:j + 1024] ** 2))) for j in range(0, n - 1023, 1024)]
    out['aud_w1024_spread'] = max(w) - min(w)
    # dominant sub-20 Hz bins
    m = (f > 0) & (f < 20)
    k = np.argsort(P[m])[::-1][:3]
    out['lf_top_hz'] = [round(float(f[m][i]), 2) for i in k]
    return out
if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(json.dumps(bands(p)), flush=True)
