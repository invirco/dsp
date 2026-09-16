"""s57_handback.py — S57 close: MIC 5 code 0 unmuted phantom off, TEST_OSC off, strip 20 OFF AUX 1 (nothing on AUX 1),
MeasChan 20; everything read back. AN_EN is read (pinctrl get), never written."""
import os, subprocess, sys
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
X = T.X
r = T.Rig(logpath='/home/app/s57/s57_handback.jsonl'); c1 = r.c1
r.osc(on=False); r.meas(20)
c1.wv('Chan020AuxOn001', 0)
b = r.chain(0)
on = [s for s in range(1, 25) if c1.r('Chan%03dAuxOn001' % s) == 1]
m = r.windows(3, settle_windows=30, tag='handback')
an = subprocess.run(['pinctrl', 'get', '26,27'], capture_output=True, text=True).stdout.strip().replace('\n', ' | ')
rec = {'ev': 'handback', 'chain': b, 'osc_on': r.rd(T.A_OSCON), 'meas': r.rd(T.A_MEASCHAN), 'auxon1': on,
       's20': {k: c1.r('Chan020' + k) for k in ('Mute001', 'MainOn001', 'AuxOn001')}, 'lane_rms': [w['rms'] for w in m['rows']], 'gpio': an}
T.log(rec); print(rec, flush=True)
