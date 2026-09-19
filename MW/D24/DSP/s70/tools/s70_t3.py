"""T3 (THD+N vs level) and the LOOP'S OWN COMPRESSION KNEE.

T1 came back with codes 0 and 1 off the 3 dB law -- 2.7 dB and 0.45 dB low -- while codes
2..11 stepped 3.000 dB apart to within 0.006 dB. Those two are the only codes whose
non-clipping level needs the oscillator ABOVE -18 dBFS, so the suspect is not the codec's
gain law but the loop: something between the DAC and the codec's input pins compresses
above about +2 dBu at the XLR.

The discriminator is whether the knee sits at a fixed OSCILLATOR level (= a fixed analog
voltage on the cable, so the DAC output stage, the cable or the talkback input network --
all ahead of the mic amp) or at a fixed LANE level (= the ADC, so behind it). This sweeps
the same oscillator ladder at three gain codes 18 dB apart and reads both.
"""
import sys
sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

r = T.Rig()
r.prove_route()
out = {'knee': [], 't3': [], 't1_low': []}

print('KNEE: the same oscillator ladder at three codes\n')
print('code  MGN dB   osc dBFS   XLR dBu   lane dBFS   loop dB   dev from small-signal   THD+N dB      %',
      flush=True)
for c in (0, 5, 11):
    r.mgn2r(c)
    ref = None
    for lvl in (-45.0, -40.0, -35.0, -30.0, -27.0, -24.0, -21.0, -19.0, -17.0, -15.0, -13.0, -12.0):
        if lvl + T.loop_est(c) > -1.0:          # do not drive the lane into the converter's last dB
            continue
        p = r.tone(1000.0, lvl)
        if ref is None:
            ref = p['gain_db']
        p['code'], p['dev_db'] = c, p['gain_db'] - ref
        out['knee'].append(p)
        print('%4d  %+6.1f  %9.1f  %+8.2f  %10.3f  %+8.3f  %+18.3f  %10.2f  %8.4f'
              % (c, T.MGN_DB[c], lvl, T.DAC_FS_DBU + lvl, p['rms_dbfs'], p['gain_db'],
                 p['dev_db'], p['thd_db'], T.pct(p['thd_db'])), flush=True)
    print(flush=True)

print('T1 REDO, codes 0 and 1 inside the linear region (lane peak -20 dBFS):\n', flush=True)
for c in (0, 1, 2):
    r.mgn2r(c)
    p = r.tone(1000.0, T.osc_for(c, -20.0))
    p['code'], p['mgn_db'] = c, T.MGN_DB[c]
    out['t1_low'].append(p)
    print('code %2d  MGN %+5.1f  osc %7.2f  lane %9.3f  loop %+8.3f  THD+N %8.2f dB'
          % (c, T.MGN_DB[c], T.osc_for(c, -20.0), p['rms_dbfs'], p['gain_db'], p['thd_db']),
          flush=True)

print('\nT3: THD+N vs level\n')
print('  MGN dB  lane target  osc dBFS   lane dBFS    THD+N dB        %     noise dBFS   loop dB',
      flush=True)
for c, targets in ((2, (-20.0, -10.0, -6.0, -3.0)), (11, (-20.0, -10.0, -6.0, -3.0))):
    r.mgn2r(c)
    for tgt in targets:
        lvl = T.osc_for(c, tgt)
        p = r.tone(1000.0, lvl)
        p['code'], p['target_dbfs'] = c, tgt
        out['t3'].append(p)
        print('  %+6.1f  %11.1f  %8.2f  %10.3f  %11.2f  %8.4f  %11.3f  %+8.3f'
              % (T.MGN_DB[c], tgt, lvl, p['rms_dbfs'], p['thd_db'], T.pct(p['thd_db']),
                 p['noise_dbfs'], p['gain_db']), flush=True)
    print(flush=True)

r.osc(on=False)
r.mgn2r(T.MGN_INIT)
T.save('t3_knee.json', out)
