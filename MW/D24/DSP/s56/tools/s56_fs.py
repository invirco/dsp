"""s56_fs.py — the 0.98 FS ceiling, digital: TEST_OSC injected into the MIC 5 strip INPUT block (after C1_IN_nn, before
C1_GAIN_nn), swept through and past full scale. Reads the SAME meter S54-5 read (_mtr_peak_C1_MTR_nn, the MIC 5 strip
gain-stage block peak), TEST_MEAS on the MIC 5 strip post-fader, and a 4096 capture's sample peak + FFT THD+N."""
import json, math, os, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
import dsp4_fft as F
X = T.X
r = T.Rig(logpath='/home/app/s56/s56_fs.jsonl'); sc = r.sc; c1 = r.c1
MP = sc.sym['_mtr_peak_C1_MTR_%02d' % T.LOOP]
for k in ('CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'Mute001'):
    assert c1.r('Chan%03d' % T.LOOP + k) == 0, k
print('the MIC 5 strip gain %.4f level %.4f' % (X.from_f32(c1.r('Chan%03dGain001' % T.LOOP)), X.from_f32(c1.r('Chan%03dLevel001' % T.LOOP))))
r.meas(T.LOOP)
rows = []
print('%8s %9s | %9s %9s | %9s %9s %9s | %9s %9s' % ('osc pk', 'dBFS', 'meter pk', 'dBFS', 'rms', 'THD+N', '%', 'cap pk', 'FFT THDN'))
for lin in [0.5, 0.9, 0.95, 0.979, 1.0, 1.02, 1.1, 1.259, 1.585, 2.0, 4.0]:
    r.osc(freq=1000.0, level_db=20 * math.log10(lin), on=True, chan=T.LOOP)
    w = r.windows(3, settle_windows=3, tag='fs_%.3f' % lin)
    mp = [X.from_f32(r._retry(sc.peek, MP)) for _ in range(6)]
    cap = MC.capture(4096, '/home/app/s56', sc=sc, log=lambda *a: None)
    sig = [X.s32(v) / float(1 << 28) for v in cap['samples']]
    res = F.analyse(sig, 48000.0)
    cpk = max(abs(x) for x in sig)
    thd = sum(x['thd'] for x in w['rows']) / 3; rms = sum(x['rms'] for x in w['rows']) / 3
    row = {'osc_lin': lin, 'meter_pk_max': max(mp), 'meter_pk_min': min(mp), 'rms': rms, 'thd': thd, 'cap_peak': cpk,
           'cap_max': max(sig), 'cap_min': min(sig), 'fft_thdn': res['thdn_db'], 'fft_fund': res['fund_dbfs'], 'overruns': cap['overruns']}
    rows.append(row); T.log({'ev': 'fs', **row})
    print('%8.3f %9.2f | %9.4f %9.2f | %9.2f %9.2f %9.5f | %9.4f %9.2f  ovr+%d' % (lin, 20 * math.log10(lin), max(mp), 20 * math.log10(max(mp)),
          rms, thd, T.pct(thd), cpk, res['thdn_db'], cap['overruns']))
