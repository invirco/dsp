"""T4 (noise floor per MGN2R code) and T4b (EIN, both weightings) on the talkback input.

WHAT THE SOURCE IS MATTERS MORE THAN THE NUMBER. Run with `--source loop` the talkback XLR
is terminated by the AUX 1 output stage through PW's cable, which is the only source the
bench has until the 150 ohm shunt is fitted; the test set says that figure is quoted as a
reference with its source named, not as the spec EIN. Run with `--source 150r` the same
battery is the real thing.

T4b IS TAKEN FROM THE CAPTURE, NOT FROM NoiseResult. NoiseResult is DC to 24 kHz and the
spec figure is 20 Hz - 20 kHz, unweighted AND A-weighted (PW 09-16); the node's raw figure
is carried in the table beside them for continuity. Input-referring uses the loop gain at
THAT code (S57-R): ADC full scale at the XLR = DAC full scale - loop gain at the code, and
the loop gain is never subtracted twice.
"""
import json
import subprocess
import sys

sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

SOURCE = sys.argv[1] if len(sys.argv) > 1 else 'loop'
LOOP_GAIN = {}               # filled from T1

r = T.Rig()
t1 = json.load(open(T.DATA + '/set.json'))['t1']
for row in t1:
    LOOP_GAIN[row['code']] = row['gain_db']

out = {'source': SOURCE, 't4': [], 't4b': []}
r.osc(on=False)
r.meas(T.TALK)

print('T4  noise floor per MGN2R code, tone off, source = %s\n' % SOURCE, flush=True)
print('code  MGN dB   loop dB   lane dBFS   NoiseResult dBFS   noise dBu (in)   ADC FS dBu',
      flush=True)
for c in range(12):
    r.mgn2r(c)
    p = r.point(3)
    g = LOOP_GAIN[c]
    # A noise POWER converts as lane dBFS + 3.01 + FS dBu (S57-O, the mean-square convention).
    dbu = p['rms_dbfs'] + 3.01 + T.adc_fs_dbu(g)
    row = {'code': c, 'mgn_db': T.MGN_DB[c], 'loop_db': g, 'rms_dbfs': p['rms_dbfs'],
           'noise_dbfs': p['noise_dbfs'], 'noise_dbu': dbu, 'adc_fs_dbu': T.adc_fs_dbu(g)}
    out['t4'].append(row)
    print('%4d  %+6.1f  %+8.3f  %10.3f  %17.3f  %14.2f  %+11.2f'
          % (c, T.MGN_DB[c], g, p['rms_dbfs'], p['noise_dbfs'], dbu, T.adc_fs_dbu(g)),
          flush=True)


def capture_fft(code, tag):
    """One 16k capture of the talkback lane, analysed in-band unweighted and A-weighted."""
    r.mgn2r(code)
    r.meas(T.TALK)
    r._close()
    try:
        f = '%s/cap_%s_code%d.json' % (T.DATA, tag, code)
        cmd = [sys.executable, '/home/app/s69/dsp4_fft.py', '--capture', '16384',
               '--symdir', '/home/app/s69', '--band', '20-20000', '--aweight', '--save', f]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    finally:
        subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
        r._open()
    return p.stdout + p.stderr


print('\nT4b  EIN from the capture, 16384 samples, tone off\n', flush=True)
for c in (11, 0):
    txt = capture_fft(c, SOURCE)
    out['t4b'].append({'code': c, 'mgn_db': T.MGN_DB[c], 'loop_db': LOOP_GAIN[c],
                       'adc_fs_dbu': T.adc_fs_dbu(LOOP_GAIN[c]), 'fft': txt})
    print('--- MGN %+5.1f dB (code %d), loop %+0.3f dB, ADC FS at the XLR %+0.2f dBu ---'
          % (T.MGN_DB[c], c, LOOP_GAIN[c], T.adc_fs_dbu(LOOP_GAIN[c])), flush=True)
    print(txt, flush=True)

r.mgn2r(T.MGN_INIT)
T.save('t4_%s.json' % SOURCE, out)
