"""s56_setup.py — the S54 hand-back image on whatever pair is running: strip 6 -> AUX 1 donor
(CompOn 0, MainOn 0), the MIC 5 strip transparent, TEST_OSC 1 kHz -20 dBFS pk on strip 6, MeasChan = the MIC 5 strip."""
import os, sys, subprocess
SYMDIR = os.environ.get('SYMDIR', '/home/app/s56')
subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
out = subprocess.run(['python3', 'dsp4_apply_strip.py', '6', '1', SYMDIR], capture_output=True, text=True).stdout
print('\n'.join(out.splitlines()[-3:]))
subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
sys.path.insert(0, '/home/app/s54')
import s54lib as T
X = T.X
r = T.Rig()
c1 = r.c1
X.strip_unity(c1, T.LOOP)
c1.wv('Chan006CompOn001', 0)
c1.wv('Chan006MainOn001', 0)
r.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
r.meas(T.LOOP)
for s in (6, T.LOOP):
    p = 'Chan%03d' % s
    print(s, {k: c1.r(p + k) for k in ('Mute001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001', 'AuxOn001', 'Pol001')})
print('muted 1-24:', [s for s in range(1, 25) if c1.r('Chan%03dMute001' % s) == 1])
print('MeasChan', r.rd(T.A_MEASCHAN), 'OscOn', r.rd(T.A_OSCON), 'OscChan', r.rd(T.A_OSCCHAN),
      'freq %.3f level %.6f' % (X.from_f32(r.rd(T.A_OSCFREQ)), X.from_f32(r.rd(T.A_OSCLEVEL))))
