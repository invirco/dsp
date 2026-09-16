#!/usr/bin/env python3
"""s63_thd_analyse.py DATA_DIR [XLR] [NAME] — T3 THD ONLY (h2..h10) from s63_thd.py's bin-centred captures (desk, numpy).

Each capture: 16,320 samples = 340 cycles of 1 kHz, so harmonic k sits on bin 340 k; rectangular window (coherent).
Per capture X = rfft(x) * 2 / N (peak amplitude per bin). COHERENT AVERAGE: each capture's bins are rotated by
exp(-j k phi1) with phi1 = that capture's fundamental phase and k = bin / 340 (the harmonic number; fractional for
the bins between), then averaged as complex numbers: the harmonics add in phase, uncorrelated noise falls by N in power.
  per-bin floor  median |X_avg|^2 over 20 Hz-20 kHz, excluding the DC bin, +-3 bins round every harmonic of 1 kHz and
                 below 100 Hz; also the single-capture floor the same way (the 10 log N the averaging bought)
  h_k            |X_avg[340 k]| in dBc; power-corrected for the floor (|h|^2 - floor); "< floor" when within 3 dB of it
  THD            sqrt(sum_{k=2..10} h_k^2) / h_1, dB and %, from the floor-corrected harmonics
                 (and the THD bound if every "< floor" harmonic sat at the floor)"""
import json, math, os, sys
import numpy as np

CYC = 340


def main(argv):
    ddir = argv[0]
    xlr = argv[1] if len(argv) > 1 else 'J25'
    name = argv[2] if len(argv) > 2 else 'thd_' + xlr
    recs = [json.loads(l) for l in open(os.path.join(ddir, name + '.jsonl'))]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from s63_analyse import load_bin
    raw = load_bin(ddir, name)
    out = {}
    lines = []
    for code in sorted(set(r['code'] for r in recs), reverse=True):
        rs = [r for r in recs if r['code'] == code]
        Xs = []
        for r in rs:
            x = raw[r['bin_off']:r['bin_off'] + r['n']]
            N = len(x)
            X = np.fft.rfft(x) * 2 / N
            phi1 = np.angle(X[CYC])
            k = np.arange(len(X)) / CYC
            Xs.append(X * np.exp(-1j * k * phi1))
        Xs = np.array(Xs)
        Xavg = Xs.mean(0)
        f = np.fft.rfftfreq(N, 1 / 48000.0)
        mask = (f >= 100) & (f <= 20000)
        for h in range(1, 21):
            mask[max(0, h * CYC - 3):h * CYC + 4] = False
        floor_avg = float(np.median(np.abs(Xavg[mask]) ** 2))
        floor_one = float(np.median(np.abs(Xs[:, mask]) ** 2))
        A1 = abs(Xavg[CYC])
        harm, thd_p, thd_bound = {}, 0.0, 0.0
        for h in range(2, 11):
            p = abs(Xavg[h * CYC]) ** 2
            pc = p - floor_avg
            below = p < floor_avg * 10 ** 0.3
            harm[h] = {'dbc': 10 * math.log10(max(pc, 1e-30) / A1 ** 2) if not below else None,
                       'raw_dbc': 10 * math.log10(p / A1 ** 2), 'below_floor': bool(below)}
            if not below:
                thd_p += pc
            thd_bound += max(pc, floor_avg) if not below else floor_avg
        thd = math.sqrt(thd_p) / A1 if thd_p > 0 else 0.0
        bound = math.sqrt(thd_bound) / A1
        res = {'n': len(rs), 'overruns': sum(r['overruns'] for r in rs), 'osc_dbfs_pk': rs[0]['osc_dbfs_pk'],
               'fund_dbfs_pk': 20 * math.log10(A1),
               'floor_bin_avg_dbfs': 10 * math.log10(floor_avg), 'floor_bin_avg_dbc': 10 * math.log10(floor_avg / A1 ** 2),
               'floor_bin_single_dbc': 10 * math.log10(floor_one / A1 ** 2),
               'harmonics': harm, 'thd_db': 20 * math.log10(thd) if thd > 0 else None, 'thd_pct': 100 * thd,
               'thd_bound_db': 20 * math.log10(bound), 'thd_bound_pct': 100 * bound}
        out[code] = res
        hs = ' '.join('h%d %s' % (h, ('%.1f' % v['dbc']) if v['dbc'] is not None else '<fl') for h, v in harm.items())
        lines.append('code %d: fundamental %.2f dBFS pk (osc %.2f), %d captures, overruns %d; THD(h2-h10) %s dB = %.5f %% '
                     '(bound %.2f dB = %.5f %%); per-bin floor %.1f dBc averaged (single capture %.1f dBc); %s' % (
                         code, res['fund_dbfs_pk'], res['osc_dbfs_pk'], res['n'], res['overruns'],
                         '%.2f' % res['thd_db'] if res['thd_db'] is not None else '< floor', res['thd_pct'],
                         res['thd_bound_db'], res['thd_bound_pct'], res['floor_bin_avg_dbc'], res['floor_bin_single_dbc'], hs))
    print('\n'.join(lines))
    json.dump(out, open(os.path.join(ddir, 's63_%s.json' % name), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
