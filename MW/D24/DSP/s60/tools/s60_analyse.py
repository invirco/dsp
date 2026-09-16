#!/usr/bin/env python3
"""s60_analyse.py <datadir> — deconvolve the S60 captures against the captured strip-6 reference and score them
against the S54/S55 tone results for J25 (MIC 5). Desk-side (numpy if present); writes <datadir>/../results.json."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', '..', 'tools', 'pi'))
import dsp4_chirp as CH                 # noqa: E402
import dsp4_fft as FFT                  # noqa: E402

D = sys.argv[1]
TAG = sys.argv[2] if len(sys.argv) > 2 else ''
# per-code tag override, e.g. 63=_lf: the settled run's code 63 was switched up under the previous stimulus (S60-3)
OVR = dict((int(a.split('=')[0]), a.split('=')[1]) for a in sys.argv[3:])
ld = lambda t: json.load(open(os.path.join(D, t + '.json')))
smp = lambda c: [(v - (1 << 32) if v & 0x80000000 else v) / float(1 << 28) for v in c['samples']]

# tone results, J25: S54 t2.out (code 0, osc -20) and t2c63.out (code 63), coherent gain re 1 kHz
TONE = {0: {20: 5.164 - 5.578, 50: 5.528 - 5.578, 100: 5.590 - 5.578, 1000: 0.0, 10000: 5.639 - 5.578,
            20000: 5.461 - 5.578},
        63: {20: -2.060, 50: -0.442, 100: -0.120, 1000: 0.0, 10000: 0.065, 20000: -0.113}}
T1 = {0: 5.578, 1: 18.423, 2: 25.041, 4: 32.475, 8: 39.927, 16: 47.169, 32: 53.744, 63: 58.717}
PTS = (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000)

ref = ld('ref_strip6_m20')
xr = smp(ref)
out = {'ref_overruns': ref['overruns'], 'codes': {}}
print('reference: strip 6 post-fader, level %.6f, overruns %d' % (ref['osc_level'], ref['overruns']))
for code in (0, 1, 2, 4, 8, 16, 32, 63):
    tg = OVR.get(code, TAG)
    c1 = ld('chirp%s_c%02d_1' % (tg, code))
    y = smp(c1)
    f2 = 'chirp%s_c%02d_2' % (tg, code)
    y2 = smp(ld(f2)) if os.path.exists(os.path.join(D, f2 + '.json')) else None
    x = [v * c1['osc_level'] / ref['osc_level'] for v in xr]
    r = CH.analyse(y, x, 0, points=PTS, y2=y2)
    pk = max(abs(v) for v in y)
    row = {'osc_dbfs_pk': c1['osc_dbfs_pk'], 'lane_pk_dbfs': 20 * math.log10(pk), 'overruns': c1['overruns'],
           'gain_1k': r['gain_1k_db'], 'd_gain_vs_T1': r['gain_1k_db'] - T1[code], 'latency_peak': r['latency_peak'],
           'latency_gd': r['latency_gd_1k_10k'], 'latency_gd12': r['latency_gd_1k_2k'], 'polarity': r['polarity'], 'response': r['response'],
           'harmonics': r['harmonics'], 'thd_db': r['thd_db'], 'thd_pct': r['thd_pct'], 'snr': r.get('snr'),
           'repeat_db': r.get('repeat_rms_db')}
    if code in TONE:
        rd = dict(r['response'])
        row['vs_tone'] = {f: rd[f] - TONE[code][f] for f in TONE[code]}
    row['files'] = [c1['tag'], f2 if y2 is not None else None]
    out['codes'][code] = row
    CH.report(r, '\n=== code %d  (osc %.2f dBFS pk, lane peak %.2f dBFS, overruns %d)' %
              (code, c1['osc_dbfs_pk'], row['lane_pk_dbfs'], c1['overruns']))
    print('  gain vs T1 %.3f dB: %+.3f dB' % (T1[code], row['d_gain_vs_T1']))
    if 'vs_tone' in row:
        print('  chirp - tone, dB: ' + ', '.join('%g Hz %+.3f' % (f, d) for f, d in sorted(row['vs_tone'].items())))

# THD+N tone captures, FFT method
for code in (0, 63):
    t = 'thdn%s_c%02d' % (OVR.get(code, TAG), code)
    if os.path.exists(os.path.join(D, t + '.json')):
        c = ld(t)
        res = FFT.analyse(smp(c), 48000.0)
        out['thdn_%d' % code] = {'osc': c['osc_dbfs_pk'], 'fund_dbfs': res['fund_dbfs'], 'thdn_db': res['thdn_db'],
                                 'thdn_pct': 100 * 10 ** (res['thdn_db'] / 20), 'thd_db': res['thd_db'],
                                 'overruns': c['overruns']}
        print('\nTHD+N code %d: osc %.2f, fundamental %.2f dBFS rms, THD+N %.2f dB = %.4f %%, THD(2..10) %.2f dB'
              % (code, c['osc_dbfs_pk'], res['fund_dbfs'], res['thdn_db'], 100 * 10 ** (res['thdn_db'] / 20),
                 res['thd_db']))
t = 'ein%s_c63_loopsrc' % TAG
if os.path.exists(os.path.join(D, t + '.json')):
    c = ld(t)
    s = smp(c)
    ub, _ = FFT.band_power(s, 48000.0, 20.0, 20000.0)
    ab, _ = FFT.band_power(s, 48000.0, 20.0, 20000.0, aweight=True)
    out['ein_loopsrc'] = {'band_dbfs': ub, 'a_dbfs': ab, 'overruns': c['overruns']}
    print('\nnoise code 63, loop cable as source: 20-20k %.2f dBFS, A %.2f dBFS (input-referred: -58.717 dB)'
          % (ub, ab))
json.dump(out, open(os.path.join(D, '..', 'results%s.json' % TAG), 'w'), indent=1)
