"""s57_outnoise.py <capture.json ...> [--floor DBFS] — AUX 1 OUTPUT noise through the loop (J45 -> cable -> J25),
MIC 5 code 0, TEST_OSC off. Per capture and energy-averaged: raw DC-24 kHz, 20 Hz-20 kHz unweighted, 20-20k
A-weighted (dsp4_fft.band_power). dBu at the XLR two ways, stated side by side:
  PW's rule     dBu = lane dBFS + 17.55
  sine-RMS ref  dBu = lane dBFS + 3.01 + 17.55   (+17.55 dBu is a full-scale SINE's RMS; RmsResult and the FFT put
                that sine at -3.01 dBFS, so a noise power in those dBFS sits 3.01 dB above the plain sum)
Converter-floor correction: power-subtract the 150 ohm code-0 floor (--floor, default -113.8 dBFS, the node's DC-24 kHz
figure; exact for the raw column; for the band columns it over-subtracts, because the in-band floor is lower, so the
corrected band figures are a LOWER bound and the uncorrected ones an upper bound).
Top ten lines from the averaged PSD (s57_avgpsd method), in dBFS and dBu."""
import json, math, subprocess, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import s57_analyse as A
args = [a for a in sys.argv[1:]]
floor = -113.8
if '--floor' in args:
    i = args.index('--floor'); floor = float(args[i + 1]); del args[i:i + 2]
FS = 48000.0
def emean(v): return 10 * math.log10(sum(10 ** (x / 10) for x in v) / len(v))
def sub(l, f): d = 10 ** (l / 10) - 10 ** (f / 10); return 10 * math.log10(d) if d > 0 else float('-inf')
rows = []
for fn in args:
    c, x = A.load(fn)
    lst = list(x - x.mean())
    rows.append({'file': fn.rsplit('/', 1)[-1], 'overruns': c.get('overruns'),
                 'raw': A.db(float(np.mean((x - x.mean()) ** 2))),
                 'b20k': A.F.band_power(lst, FS, 20, 20000)[0], 'a20k': A.F.band_power(lst, FS, 20, 20000, aweight=True)[0]})
for r in rows:
    print('%-14s ovr +%s  raw %.2f  20-20k %.2f  A %.2f dBFS' % (r['file'], r['overruns'], r['raw'], r['b20k'], r['a20k']))
avg = {k: emean([r[k] for r in rows]) for k in ('raw', 'b20k', 'a20k')}
print('\nenergy average over %d captures (dBFS; dBu PW rule / sine-RMS ref; floor-corrected by %.1f dBFS):' % (len(rows), floor))
for k, lab in (('b20k', '20 Hz-20 kHz unweighted'), ('a20k', '20 Hz-20 kHz A-weighted'), ('raw', 'DC-24 kHz raw')):
    fc = sub(avg[k], floor)
    print('  %-24s %8.2f dBFS  = %7.2f / %7.2f dBu   corrected %8.2f dBFS = %7.2f / %7.2f dBu'
          % (lab, avg[k], avg[k] + 17.55, avg[k] + 20.56, fc, fc + 17.55, fc + 20.56))
P = None
for fn in args:
    c, x = A.load(fn); p, bw = A.psd_bh7(x); P = p if P is None else P + p
P /= len(args)
def med(i, h=80): return float(np.median(P[max(1, i - h):min(len(P), i + h)]))
pk = []
for i in range(9, len(P) - 6):
    if P[i] == P[i - 5:i + 6].max() and P[i] > 1.26 * med(i):
        pk.append((A.db(max(float(P[i - 5:i + 6].sum()) - 11 * med(i), 1e-30)), i * bw, A.db(P[i] / med(i))))
pk.sort(reverse=True)

print('\ntop ten local maxima above 1 dB (averaged PSD, band power minus local median; ranked by level; < 3 dB above floor = not resolved as a line):')
for l, hz, ab in pk[:10]:
    print('  %9.1f Hz  %8.2f dBFS  = %7.2f / %7.2f dBu   (%.1f dB above floor)' % (hz, l, l + 17.55, l + 20.56, ab))
print('\nOUTPUT NOISE DONE: 20-20k unweighted %.2f dBu, A-weighted %.2f dBu (PW rule; sine-RMS ref %.2f / %.2f dBu)'
      % (avg['b20k'] + 17.55, avg['a20k'] + 17.55, avg['b20k'] + 20.56, avg['a20k'] + 20.56))
