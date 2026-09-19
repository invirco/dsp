"""T1, T2, T3, T5 and T8 on the talkback input, with the donor strip's compressor bypassed.

The first pass of T1/T3 was taken through the donor strip's own compressor and every point
above an oscillator level of -18 dBFS was compressed before it reached the DAC. This is
the same battery on a transparent stimulus.

T5 AND T8 COME OUT OF ONE SCAN. The coherent fit returns arg(H) as well as |H|, but a
phase at a single frequency cannot separate polarity from delay -- they differ by 180
degrees and the loop is several milliseconds long, so the phase has already turned through
whole turns at 1 kHz. Stepping 50 Hz at a time keeps each step under 180 degrees however
long the loop is (up to 10 ms), so the phase unwraps; the slope is the latency and the
intercept at DC is the polarity, with nothing assumed about either.
"""
import math
import sys

sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

r = T.Rig()
print('AUX 1 bus proof %.3f dBFS\n' % r.prove_route(), flush=True)
out = {'t1': [], 't2': {}, 't3': [], 'phase': []}

# ---------------------------------------------------------------------------- T1
print('T1  code  MGN dB   osc dBFS   lane dBFS  peak dBFS   loop dB    dev     step    '
      'THD+N dB   ADC FS dBu', flush=True)
for c in range(12):
    lvl = T.osc_for(c)
    r.mgn2r(c)
    p = r.tone(1000.0, lvl)
    p['code'], p['mgn_db'] = c, T.MGN_DB[c]
    p['adc_fs_dbu'] = T.adc_fs_dbu(p['gain_db'])
    p['step_db'] = (p['gain_db'] - out['t1'][-1]['gain_db']) if out['t1'] else None
    p['dev_db'] = (p['gain_db'] - (out['t1'][0]['gain_db'] + T.MGN_DB[c] - T.MGN_DB[0])
                   if out['t1'] else 0.0)
    out['t1'].append(p)
    print('    %4d  %+6.1f  %9.2f  %10.3f  %9.3f  %+8.3f  %+6.3f  %s  %9.2f  %+10.2f'
          % (c, T.MGN_DB[c], lvl, p['rms_dbfs'], p['rms_dbfs'] + 3.01, p['gain_db'],
             p['dev_db'], '  ----' if p['step_db'] is None else '%+6.3f' % p['step_db'],
             p['thd_db'], p['adc_fs_dbu']), flush=True)
steps = [x['step_db'] for x in out['t1'][1:]]
print('    steps: min %+0.3f  max %+0.3f  largest deviation from 3.000 dB %+0.3f  monotonic %s'
      % (min(steps), max(steps), max(abs(s - 3.0) for s in steps),
         all(out['t1'][i]['gain_db'] > out['t1'][i - 1]['gain_db'] for i in range(1, 12))),
      flush=True)

# ---------------------------------------------------------------------------- T2
FREQS = (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000)
print('\nT2  frequency response, lane at about -20 dBFS, re 1 kHz', flush=True)
for c in (0, 11):
    lvl = T.osc_for(c, -20.0)
    r.mgn2r(c)
    rows = []
    for f in FREQS:
        p = r.tone(float(f), lvl)
        p['freq_hz'] = float(f)
        rows.append(p)
    ref = next(x['gain_db'] for x in rows if x['freq_hz'] == 1000.0)
    for x in rows:
        x['re_1k_db'] = x['gain_db'] - ref
    out['t2']['code%d' % c] = rows
    print('   MGN %+5.1f dB (code %d), osc %.2f dBFS:' % (T.MGN_DB[c], c, lvl), flush=True)
    print('      ' + '  '.join('%6d' % f for f in FREQS), flush=True)
    print('      ' + '  '.join('%+6.2f' % x['re_1k_db'] for x in rows), flush=True)

# ---------------------------------------------------------------------------- T3
print('\nT3  THD+N vs level', flush=True)
print('  MGN dB  target  osc dBFS   lane dBFS    THD+N dB        %     noise dBFS    dBu in',
      flush=True)
for c in (2, 11):
    r.mgn2r(c)
    for tgt in (-20.0, -10.0, -6.0, -3.0):
        lvl = T.osc_for(c, tgt)
        p = r.tone(1000.0, lvl)
        p['code'], p['target_dbfs'] = c, tgt
        p['in_dbu'] = T.dbfs_to_dbu(p['rms_dbfs'], p['gain_db'])
        out['t3'].append(p)
        print('  %+6.1f  %6.1f  %8.2f  %10.3f  %11.2f  %8.4f  %11.3f  %+9.2f'
              % (T.MGN_DB[c], tgt, lvl, p['rms_dbfs'], p['thd_db'], T.pct(p['thd_db']),
                 p['noise_dbfs'], p['in_dbu']), flush=True)

# ---------------------------------------------------------------------------- T5 + T8
print('\nT5/T8  phase scan at MGN 0 dB, lane about -20 dBFS', flush=True)
r.mgn2r(2)
lvl = T.osc_for(2, -20.0)
prev, turns = None, 0.0
for f in range(500, 1501, 50):
    p = r.tone(float(f), lvl)
    ph = p['phase_deg']
    if prev is not None:
        d = ph - prev
        while d > 180.0:
            d -= 360.0
            turns -= 360.0
        while d < -180.0:
            d += 360.0
            turns += 360.0
    prev = ph
    p['freq_hz'], p['unwrapped_deg'] = float(f), ph + turns
    out['phase'].append(p)
xs = [x['freq_hz'] for x in out['phase']]
ys = [x['unwrapped_deg'] for x in out['phase']]
n = len(xs)
mx, my = sum(xs) / n, sum(ys) / n
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
inter = my - slope * mx
tau_s = -slope / 360.0
resid = max(abs(y - (inter + slope * x)) for x, y in zip(xs, ys))
dc = ((inter % 360.0) + 360.0) % 360.0
out['t8'] = {'slope_deg_per_hz': slope, 'intercept_deg': inter, 'tau_s': tau_s,
             'tau_samples': tau_s * T.FS, 'max_residual_deg': resid, 'dc_phase_deg': dc,
             'polarity': 'INVERTED' if 90.0 < dc < 270.0 else 'in phase'}
for x in out['phase'][::4]:
    print('   %6.0f Hz  phase %+8.2f  unwrapped %+10.2f' % (x['freq_hz'], x['phase_deg'],
                                                            x['unwrapped_deg']), flush=True)
print('   slope %.6f deg/Hz -> latency %.4f ms = %.2f samples at 48 kHz (max residual %.2f deg)'
      % (slope, tau_s * 1e3, tau_s * T.FS, resid), flush=True)
print('   phase extrapolated to DC = %+.2f deg  ->  T5 POLARITY: %s'
      % (dc, out['t8']['polarity']), flush=True)

r.osc(on=False)
r.mgn2r(T.MGN_INIT)
T.save('set.json', out)
