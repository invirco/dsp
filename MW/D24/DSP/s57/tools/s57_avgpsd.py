"""s57_avgpsd.py <capture.json ...> — the AVERAGED BH7 PSD of a set of captures (bin variance down by the count), then:
the level of every mains multiple 50..1000 Hz and every suspect (fs/n for n=2..48, 1 kHz USB SOF / 8 kHz USB HS /
8 kHz = the 1 MHz converter clock's alias at fs 48 k, 16/24 kHz) against the local median, and the strongest narrow
lines anywhere. Lines are band power (+-5 bins) minus the local median floor, dBFS; 'above' is peak bin re median."""
import json, math, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import s57_analyse as A
files = sys.argv[1:]
P = None
for fn in files:
    c, x = A.load(fn)
    p, bw = A.psd_bh7(x)
    P = p if P is None else P + p
P /= len(files)
f = np.arange(len(P)) * bw
def med(i, h=80):
    return float(np.median(P[max(1, i - h):min(len(P), i + h)]))
def line(hz):
    k = int(round(hz / bw)); s = P[k - 5:k + 6]; fl = med(k)
    return {'hz': hz, 'bin_hz': round(float(f[k - 5 + int(np.argmax(s))]), 1), 'above_db': round(A.db(float(s.max()) / fl), 2),
            'line_dbfs': round(A.db(max(float(s.sum()) - 11 * fl, 0.0)), 2), 'floor_dbfs_per_bin': round(A.db(fl), 2)}
out = {'n_caps': len(files), 'bin_hz': bw, 'total_dbfs': A.db(float(P[1:].sum())),
       'mains': [line(50.0 * h) for h in range(1, 21)],
       'suspects': [line(48000.0 / n) for n in range(2, 49) if 48000.0 / n <= 23900] + [line(1000.0), line(8000.0)]}
peaks = []
i = 12
while i < len(P) - 6:
    fl = med(i)
    if P[i] > 4 * fl and P[i] == P[i - 5:i + 6].max():
        peaks.append({'hz': round(float(f[i]), 1), 'above_db': round(A.db(P[i] / fl), 2),
                      'line_dbfs': round(A.db(max(float(P[i - 5:i + 6].sum()) - 11 * fl, 0.0)), 2)})
        i += 6
    else:
        i += 1
out['peaks'] = sorted(peaks, key=lambda d: -d['above_db'])[:20]
print(json.dumps(out))
