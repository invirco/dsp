"""s56_gate1.py <tag> <strip> <freq> <osc_dbfs_pk> <N> [compon] — one capture vs TEST_MEAS on the same signal."""
import json, math, os, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
A = sys.argv[1:]
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
import dsp4_fft as F
X = T.X
tag, strip, freq, lvl, N = A[0], int(A[1]), float(A[2]), float(A[3]), int(A[4])
compon = int(A[5]) if len(A) > 5 else None
r = T.Rig(logpath='/home/app/s56/s56_gate1.jsonl')
c1 = r.c1
if compon is not None:
    c1.wv('Chan%03dCompOn001' % strip, compon)
r.osc(freq=freq, level_db=lvl, on=True, chan=6)
r.meas(strip)
settle = 16 if freq < 100 else 4
pre = r.windows(4, settle_windows=settle, tag=tag + ':pre')
cap = MC.capture(N, '/home/app/s56', sc=r.sc)
post = r.windows(4, settle_windows=1, tag=tag + ':post')
json.dump(cap, open('/home/app/s56/cap_%s.json' % tag, 'w'))
sig = [X.s32(v) / float(1 << 28) for v in cap['samples']]
res = F.analyse(sig, 48000.0)
rows = pre['rows'] + post['rows']
def m(k): return sum(w[k] for w in rows) / len(rows)
def sp(k): return max(w[k] for w in rows) - min(w[k] for w in rows)
pk = max(abs(x) for x in sig)
# zero crossings (rising) and cycles covered
zc = [i for i in range(1, len(sig)) if sig[i - 1] < 0 <= sig[i]]
cyc = len(sig) * freq / 48000.0
out = {'tag': tag, 'strip': strip, 'freq': freq, 'osc_dbfs_pk': lvl, 'N': len(sig), 'overruns': cap['overruns'],
       'compon': compon, 'node': {'rms': m('rms'), 'thd': m('thd'), 'noise': m('noise'), 'rms_spread': sp('rms'),
       'thd_spread': sp('thd'), 'noise_spread': sp('noise'), 'windows': len(rows)},
       'fft': {k: res[k] for k in ('fund_hz', 'fund_dbfs', 'total_dbfs', 'thdn_db', 'thdn_dbfs', 'thd_db', 'noise_dbfs',
               'dc_dbfs', 'floor_bin_dbfs', 'crowded', 'tone', 'engine')},
       'harmonics': [(h['n'], round(h['dbc'], 2)) for h in res['harmonics'][:5]],
       'sample_peak': pk, 'rising_zero_crossings': len(zc), 'cycles_in_capture': cyc}
T.log({'ev': 'gate1', **out})
n, f = out['node'], out['fft']
print('== %s: strip %d, %.2f Hz, osc %.2f dBFS pk, N %d, overruns +%d, CompOn %s' % (tag, strip, freq, lvl, len(sig), cap['overruns'], compon))
print('  %-22s %12s %12s %8s' % ('', 'TEST_MEAS', 'FFT', 'delta'))
print('  %-22s %12.3f %12.3f %8.3f   (node spread %.3f over %d windows)' % ('RMS / total, dBFS', n['rms'], f['total_dbfs'], f['total_dbfs'] - n['rms'], n['rms_spread'], n['windows']))
print('  %-22s %12s %12.3f' % ('fundamental, dBFS', '', f['fund_dbfs']))
print('  %-22s %12.3f %12.3f %8.3f   (node spread %.3f)' % ('THD+N, dB', n['thd'], f['thdn_db'], f['thdn_db'] - n['thd'], n['thd_spread']))
print('  %-22s %11.5f%% %11.5f%%' % ('THD+N, %', T.pct(n['thd']), T.pct(f['thdn_db'])))
print('  %-22s %12.3f %12.3f %8.3f   (node spread %.3f)' % ('noise+dist, dBFS', n['noise'], f['thdn_dbfs'], f['thdn_dbfs'] - n['noise'], n['noise_spread']))
print('  %-22s %12s %12.3f   = %.5f %%' % ('THD (2..10), dB', '', f['thd_db'], T.pct(f['thd_db'])))
print('  %-22s %12s %12.3f' % ('noise only, dBFS', '', f['noise_dbfs']))
print('  fund %.4f Hz, harmonics dBc %s, sample peak %.5f (%.2f dBFS), %d rising zero crossings, %.2f cycles, crowded %s tone %s' % (
    f['fund_hz'], out['harmonics'], pk, 20 * math.log10(pk) if pk else -999, len(zc), cyc, f['crowded'], f['tone']))
