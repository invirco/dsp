"""GATE 1 (the lever on analog) and T1 (the gain law) on the talkback input.

GATE 1 is the dispatch's own witness: 05H := 0xB2 -- MGN2L left at +27 dB, MGN2R to 0 dB --
must drop the tone by 27.0 +/- 0.2 dB, and the twelve MGN2R codes must step 3.00 dB apart,
monotonically. It is run at ONE oscillator level so the step size is read off a single
straight line with nothing rescaled between points.

T1 is the same twelve codes measured properly: the level chosen PER CODE so the lane peaks
at about -6.5 dBFS, which is what the test set asks for and what keeps the top codes out of
the converter's last dB. The coherent fit is the gain figure (it is immune to the noise
floor that limited S69's tone-off table); RmsResult is quoted beside it.
"""
import json
import sys
import time

sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

r = T.Rig()
print('AUX 1 bus proof: %.3f dBFS' % r.prove_route(), flush=True)
out = {'gate1': {}, 't1': [], 'volad': []}

# ---------------------------------------------------------------- GATE 1, the 27 dB drop
FIX = T.osc_for(11)                       # the level the +27 dB code wants; used for all of gate 1
print('gate 1 fixed oscillator level %.2f dBFS' % FIX, flush=True)
r.mgn2r(11)
a = r.tone(1000.0, FIX)
r.codec_reg(0x05, 0xB2)                   # MGN2L +27 (unchanged), MGN2R 0 dB -- the dispatch's own write
r.code, r.mgn2l = 2, 11
b = r.tone(1000.0, FIX)
drop_rms = a['rms_dbfs'] - b['rms_dbfs']
drop_fit = a['gain_db'] - b['gain_db']
out['gate1'] = {'osc_dbfs': FIX, 'at_27': a, 'at_0': b,
                'drop_rms_db': drop_rms, 'drop_fit_db': drop_fit,
                'pass': abs(drop_fit - 27.0) <= 0.2}
print('GATE 1  +27 -> 0 dB: RmsResult %9.3f -> %9.3f = %.3f dB;  fit %+8.3f -> %+8.3f = %.3f dB  [%s]'
      % (a['rms_dbfs'], b['rms_dbfs'], drop_rms, a['gain_db'], b['gain_db'], drop_fit,
         'PASS' if out['gate1']['pass'] else 'FAIL'), flush=True)

# ---------------------------------------------------------------- GATE 1, twelve codes, one level
print('\ncode  MGN dB   osc dBFS   lane dBFS   loop dB    step    THD+N dB    noise dBFS', flush=True)
fixed = []
for c in range(12):
    r.mgn2r(c)
    p = r.tone(1000.0, FIX)
    p['code'], p['mgn_db'] = c, T.MGN_DB[c]
    step = p['gain_db'] - fixed[-1]['gain_db'] if fixed else None
    p['step_db'] = step
    fixed.append(p)
    print('%4d  %+6.1f  %9.2f  %10.3f  %+8.3f  %s  %9.2f  %10.3f'
          % (c, T.MGN_DB[c], FIX, p['rms_dbfs'], p['gain_db'],
             '  ----' if step is None else '%+6.3f' % step, p['thd_db'], p['noise_dbfs']),
          flush=True)
out['gate1_sweep'] = fixed

# ---------------------------------------------------------------- T1, level chosen per code
print('\nT1  code  MGN dB   osc dBFS   lane dBFS  peak dBFS   loop dB    dev     step    '
      'THD+N dB   ADC FS dBu', flush=True)
for c in range(12):
    lvl = T.osc_for(c)
    r.mgn2r(c)
    p = r.tone(1000.0, lvl)
    p['code'], p['mgn_db'] = c, T.MGN_DB[c]
    p['adc_fs_dbu'] = T.adc_fs_dbu(p['gain_db'])
    p['dev_db'] = p['gain_db'] - (out['t1'][0]['gain_db'] + (T.MGN_DB[c] - T.MGN_DB[0])) if out['t1'] else 0.0
    p['step_db'] = p['gain_db'] - out['t1'][-1]['gain_db'] if out['t1'] else None
    out['t1'].append(p)
    print('    %4d  %+6.1f  %9.2f  %10.3f  %9.3f  %+8.3f  %+6.3f  %s  %9.2f  %+10.2f'
          % (c, T.MGN_DB[c], lvl, p['rms_dbfs'], p['rms_dbfs'] + 3.01, p['gain_db'],
             p['dev_db'], '  ----' if p['step_db'] is None else '%+6.3f' % p['step_db'],
             p['thd_db'], p['adc_fs_dbu']), flush=True)

# ---------------------------------------------------------------- level independence (test-set T1)
print('\nlevel independence at MGN 0 dB (code 2), three drives:', flush=True)
r.mgn2r(2)
ind = []
base = T.osc_for(2)
for d in (0.0, -10.0, -20.0):
    p = r.tone(1000.0, base + d)
    ind.append(p)
    print('   osc %7.2f dBFS -> lane %9.3f dBFS, loop %+8.4f dB' % (base + d, p['rms_dbfs'], p['gain_db']),
          flush=True)
spread = max(x['gain_db'] for x in ind) - min(x['gain_db'] for x in ind)
print('   spread %.4f dB  [%s]' % (spread, 'PASS' if spread <= 0.05 else 'over 0.05 dB'), flush=True)
out['level_independence'] = {'rows': ind, 'spread_db': spread}

# ---------------------------------------------------------------- ADC2 Rch digital volume
print('\nADC2 Rch digital volume (09H), expected exact, at MGN 0 dB:', flush=True)
ref = r.tone(1000.0, base)
for db in (6.0, -6.0, -20.0):
    r.volad2r(db)
    p = r.tone(1000.0, base)
    got = p['gain_db'] - ref['gain_db']
    out['volad'].append({'nominal_db': db, 'code': T.vol_code(db), 'measured_db': got,
                         'err_db': got - db, 'row': p})
    print('   %+6.1f dB (code 0x%02X): measured %+8.3f dB, error %+7.3f dB'
          % (db, T.vol_code(db), got, got - db), flush=True)
r.volad2r(0.0)
p = r.tone(1000.0, base)
print('   restored 0.0 dB: %+8.3f dB from reference' % (p['gain_db'] - ref['gain_db']), flush=True)
out['volad_restore_db'] = p['gain_db'] - ref['gain_db']

r.osc(on=False)
r.mgn2r(T.MGN_INIT)
T.save('g1_t1.json', out)
